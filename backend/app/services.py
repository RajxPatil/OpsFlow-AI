from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.service import hash_embedding, suggest_actions_for_work_item
from app.enums import ActionStatus, JobStatus, WorkItemStatus
from app.models import (
    AuditLog,
    DataChunk,
    DataSource,
    IngestionJob,
    IntegrationEvent,
    SuggestedAction,
    User,
    WorkItem,
    Workspace,
)


def create_audit_log(
    db: Session,
    workspace_id: UUID,
    actor_id: UUID | None,
    event_type: str,
    entity_type: str,
    entity_id: UUID | None,
    description: str,
    metadata: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        workspace_id=workspace_id,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        metadata_json=metadata or {},
    )
    db.add(log)
    return log


def _rows_from_csv(raw_bytes: bytes) -> tuple[list[dict], list[str]]:
    df = pd.read_csv(BytesIO(raw_bytes))
    required = {"title", "body"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
    df = df.fillna("")
    return df.to_dict(orient="records"), list(df.columns)


def create_ingestion_job(db: Session, workspace: Workspace, user: User, filename: str, raw_bytes: bytes) -> IngestionJob:
    rows, columns = _rows_from_csv(raw_bytes)
    job = IngestionJob(
        workspace_id=workspace.id,
        created_by_id=user.id,
        source_type="csv",
        filename=filename,
        status=JobStatus.queued,
        row_count=len(rows),
        raw_payload={"columns": columns, "rows": rows},
    )
    db.add(job)
    db.flush()
    create_audit_log(
        db,
        workspace.id,
        user.id,
        "ingestion_queued",
        "ingestion_job",
        job.id,
        f"Queued CSV ingestion job for {filename} with {len(rows)} rows",
        {"filename": filename, "rows": len(rows)},
    )
    db.commit()
    db.refresh(job)
    return job


def ingest_csv(db: Session, workspace: Workspace, user: User, filename: str, raw_bytes: bytes) -> tuple[DataSource, int]:
    """Synchronous path retained for tests and API compatibility."""
    rows, columns = _rows_from_csv(raw_bytes)
    return _insert_rows_as_work_items(db, workspace, user, filename, rows, columns)


def _insert_rows_as_work_items(db: Session, workspace: Workspace, user: User, filename: str, rows: list[dict], columns: list[str]) -> tuple[DataSource, int]:
    source = DataSource(
        workspace_id=workspace.id,
        source_type="csv",
        name=filename,
        row_count=len(rows),
        metadata_json={"columns": columns},
    )
    db.add(source)
    db.flush()

    inserted = 0
    for row in rows:
        title = str(row.get("title", "Untitled"))[:255]
        body = str(row.get("body", ""))
        priority = str(row.get("priority", "medium") or "medium").lower()
        item = WorkItem(
            workspace_id=workspace.id,
            data_source_id=source.id,
            title=title,
            body=body,
            customer=str(row.get("customer", "")) or None,
            channel=str(row.get("channel", "csv")) or "csv",
            priority=priority,
            status=WorkItemStatus(str(row.get("status", "open") or "open")) if str(row.get("status", "open") or "open") in WorkItemStatus._value2member_map_ else WorkItemStatus.open,
            risk_score=_risk_score(title, body, priority),
        )
        db.add(item)
        db.flush()
        content = f"{item.title}\n{item.body}"
        db.add(DataChunk(workspace_id=workspace.id, work_item_id=item.id, content=content, embedding=hash_embedding(content)))
        inserted += 1

    create_audit_log(db, workspace.id, user.id, "data_source_uploaded", "data_source", source.id, f"Uploaded {filename} and created {inserted} work items", {"row_count": inserted})
    db.commit()
    db.refresh(source)
    return source, inserted


def _risk_score(title: str, body: str, priority: str) -> float:
    text = f"{title} {body}".lower()
    score = 0.2
    if priority in {"high", "urgent", "critical"}:
        score += 0.35
    for token in ["outage", "failed", "urgent", "refund", "security", "breach", "blocked", "not working", "many users"]:
        if token in text:
            score += 0.08
    return min(0.98, round(score, 2))


def process_ingestion_job(db: Session, job_id: UUID) -> IngestionJob:
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise ValueError("Ingestion job not found")
    if job.status == JobStatus.completed:
        return job

    workspace = db.query(Workspace).filter(Workspace.id == job.workspace_id).first()
    user = db.query(User).filter(User.id == job.created_by_id).first()
    if not workspace or not user:
        raise ValueError("Job workspace/user missing")

    try:
        job.status = JobStatus.processing
        db.commit()
        rows = job.raw_payload.get("rows", [])
        columns = job.raw_payload.get("columns", [])
        _, inserted = _insert_rows_as_work_items(db, workspace, user, job.filename, rows, columns)
        generated = generate_actions(db, workspace, user, limit=inserted + 20)
        job.status = JobStatus.completed
        job.inserted_work_items = inserted
        job.generated_actions = generated
        job.processed_at = datetime.now(timezone.utc)
        create_audit_log(
            db,
            workspace.id,
            user.id,
            "ingestion_completed",
            "ingestion_job",
            job.id,
            f"Completed ingestion: {inserted} work items and {generated} AI actions generated",
            {"inserted": inserted, "generated_actions": generated},
        )
    except Exception as exc:  # pragma: no cover - defensive worker path
        job.status = JobStatus.failed
        job.error_message = str(exc)
        job.processed_at = datetime.now(timezone.utc)
        create_audit_log(db, job.workspace_id, job.created_by_id, "ingestion_failed", "ingestion_job", job.id, f"Ingestion failed: {exc}", {})
    db.commit()
    db.refresh(job)
    return job


def generate_actions(db: Session, workspace: Workspace, user: User, limit: int = 100) -> int:
    work_items = (
        db.query(WorkItem)
        .filter(WorkItem.workspace_id == workspace.id)
        .order_by(WorkItem.created_at.desc())
        .limit(limit)
        .all()
    )

    generated = 0
    for item in work_items:
        has_pending_or_reviewed = db.query(SuggestedAction).filter(SuggestedAction.work_item_id == item.id).first()
        if has_pending_or_reviewed:
            continue
        suggestions = suggest_actions_for_work_item(item.title, item.body, item.customer, item.priority)
        if suggestions:
            item.category = suggestions[0].category
        for suggestion in suggestions:
            db.add(
                SuggestedAction(
                    workspace_id=workspace.id,
                    work_item_id=item.id,
                    action_type=suggestion.action_type,
                    title=suggestion.title,
                    payload=suggestion.payload,
                    explanation=suggestion.explanation,
                    confidence=suggestion.confidence,
                )
            )
            generated += 1

    create_audit_log(db, workspace.id, user.id, "actions_generated", "workspace", workspace.id, f"Generated {generated} AI-suggested actions", {"generated": generated})
    db.commit()
    return generated


def review_action(db: Session, workspace: Workspace, user: User, action_id: UUID, status: ActionStatus) -> SuggestedAction:
    action = (
        db.query(SuggestedAction)
        .filter(
            SuggestedAction.id == action_id,
            SuggestedAction.workspace_id == workspace.id,
        )
        .first()
    )

    if not action:
        raise ValueError("Suggested action not found")

    # Idempotent retry path:
    # If the same approve/reject request is repeated, return the existing action
    # without creating duplicate integration events or audit logs.
    if action.status == status:
        return action

    # Prevent changing a final decision.
    if action.status != ActionStatus.pending:
        raise ValueError(
            f"Action has already been reviewed as {action.status.value}. "
            "Reviewed actions cannot be changed."
        )

    action.status = status
    action.reviewed_by_id = user.id
    action.reviewed_at = datetime.now(timezone.utc)

    if status == ActionStatus.approved:
        _simulate_integration_event(db, workspace, action)

        if action.action_type.value == "escalate_issue":
            action.work_item.status = WorkItemStatus.escalated
        elif action.action_type.value == "draft_reply":
            action.work_item.status = WorkItemStatus.in_review

    create_audit_log(
        db,
        workspace.id,
        user.id,
        f"action_{status.value}",
        "suggested_action",
        action.id,
        f"{status.value.title()} action: {action.title}",
        {
            "action_type": action.action_type.value,
            "work_item_id": str(action.work_item_id),
            "idempotent": True,
        },
    )

    db.commit()
    db.refresh(action)
    return action


def _simulate_integration_event(db: Session, workspace: Workspace, action: SuggestedAction) -> None:
    existing_event = (
        db.query(IntegrationEvent)
        .filter(
            IntegrationEvent.workspace_id == workspace.id,
            IntegrationEvent.suggested_action_id == action.id,
        )
        .first()
    )

    if existing_event:
        return

    provider = {
        "draft_reply": "gmail",
        "create_task": "jira",
        "escalate_issue": "slack",
        "update_status": "jira",
        "slack_alert": "slack",
        "github_issue": "github",
    }.get(action.action_type.value, "opsflow")

    event = IntegrationEvent(
        workspace_id=workspace.id,
        suggested_action_id=action.id,
        provider=provider,
        event_name=f"{provider}.{action.action_type.value}",
        status="simulated_success",
        request_payload=action.payload,
        response_payload={
            "external_id": f"mock-{provider}-{str(action.id)[:8]}",
            "human_approved": True,
            "idempotency_key": f"action-{action.id}",
        },
    )

    db.add(event)


def action_detail(db: Session, workspace: Workspace, action_id: UUID) -> dict:
    action = db.query(SuggestedAction).filter(SuggestedAction.id == action_id, SuggestedAction.workspace_id == workspace.id).first()
    if not action:
        raise ValueError("Suggested action not found")
    chunk = db.query(DataChunk).filter(DataChunk.work_item_id == action.work_item_id).first()
    events = db.query(IntegrationEvent).filter(IntegrationEvent.suggested_action_id == action.id).order_by(IntegrationEvent.created_at.desc()).all()
    evidence = []
    if chunk:
        evidence.append({"source": "uploaded_ticket", "content": chunk.content[:800], "reason": "Closest stored evidence chunk for this suggested action."})
    simulated_integrations = [
        {
            "provider": e.provider,
            "event_name": e.event_name,
            "status": e.status,
            "request_payload": e.request_payload,
            "response_payload": e.response_payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
    return {"action": action, "evidence": evidence, "simulated_integrations": simulated_integrations}


def compute_metrics(db: Session, workspace: Workspace) -> dict:
    total_work_items = db.query(func.count(WorkItem.id)).filter(WorkItem.workspace_id == workspace.id).scalar() or 0
    pending_actions = db.query(func.count(SuggestedAction.id)).filter(SuggestedAction.workspace_id == workspace.id, SuggestedAction.status == ActionStatus.pending).scalar() or 0
    approved_actions = db.query(func.count(SuggestedAction.id)).filter(SuggestedAction.workspace_id == workspace.id, SuggestedAction.status == ActionStatus.approved).scalar() or 0
    rejected_actions = db.query(func.count(SuggestedAction.id)).filter(SuggestedAction.workspace_id == workspace.id, SuggestedAction.status == ActionStatus.rejected).scalar() or 0
    failed_actions = db.query(func.count(SuggestedAction.id)).filter(SuggestedAction.workspace_id == workspace.id, SuggestedAction.status == ActionStatus.failed).scalar() or 0
    high_risk_items = db.query(func.count(WorkItem.id)).filter(WorkItem.workspace_id == workspace.id, WorkItem.risk_score >= 0.65).scalar() or 0
    completed_jobs = db.query(func.count(IngestionJob.id)).filter(IngestionJob.workspace_id == workspace.id, IngestionJob.status == JobStatus.completed).scalar() or 0
    queued_jobs = db.query(func.count(IngestionJob.id)).filter(IngestionJob.workspace_id == workspace.id, IngestionJob.status.in_([JobStatus.queued, JobStatus.processing])).scalar() or 0
    reviewed = approved_actions + rejected_actions
    approval_rate = round(approved_actions / reviewed, 3) if reviewed else 0.0
    estimated_minutes_saved = int(approved_actions * 7 + pending_actions * 2 + completed_jobs * 10)
    return {
        "total_work_items": total_work_items,
        "pending_actions": pending_actions,
        "approved_actions": approved_actions,
        "rejected_actions": rejected_actions,
        "approval_rate": approval_rate,
        "estimated_minutes_saved": estimated_minutes_saved,
        "failed_actions": failed_actions,
        "high_risk_items": high_risk_items,
        "completed_jobs": completed_jobs,
        "queued_jobs": queued_jobs,
    }


def mock_connectors() -> list[dict]:
    return [
        {"id": "slack", "name": "Slack Incident Channel", "provider": "slack", "status": "mock_connected", "description": "Sends human-approved escalation alerts to #ops-incidents.", "last_sync": "2 min ago", "records": 18},
        {"id": "gmail", "name": "Gmail Support Inbox", "provider": "gmail", "status": "mock_connected", "description": "Creates approved customer reply drafts without auto-sending.", "last_sync": "7 min ago", "records": 42},
        {"id": "jira", "name": "Jira Ops Board", "provider": "jira", "status": "mock_connected", "description": "Creates internal tasks for bugs, incidents, and feature requests.", "last_sync": "12 min ago", "records": 11},
        {"id": "github", "name": "GitHub Engineering Repo", "provider": "github", "status": "mock_connected", "description": "Creates engineering issues for reproducible product bugs.", "last_sync": "25 min ago", "records": 6},
    ]


def _to_float_list(vector) -> list[float]:
    if vector is None:
        return []

    if hasattr(vector, "tolist"):
        vector = vector.tolist()

    try:
        return [float(x) for x in vector]
    except TypeError:
        return []


def _cosine_similarity(a, b) -> float:
    a_vec = _to_float_list(a)
    b_vec = _to_float_list(b)

    if len(a_vec) == 0 or len(b_vec) == 0:
        return 0.0

    if len(a_vec) != len(b_vec):
        return 0.0

    dot = sum(x * y for x, y in zip(a_vec, b_vec))
    norm_a = sum(x * x for x in a_vec) ** 0.5
    norm_b = sum(y * y for y in b_vec) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return round(dot / (norm_a * norm_b), 4)


def semantic_search_work_items(
    db: Session,
    workspace: Workspace,
    query: str,
    limit: int = 8,
) -> list[dict]:
    cleaned_query = query.strip()

    if not cleaned_query:
        return []

    query_embedding = hash_embedding(cleaned_query)

    chunks = (
        db.query(DataChunk, WorkItem)
        .join(WorkItem, WorkItem.id == DataChunk.work_item_id)
        .filter(DataChunk.workspace_id == workspace.id)
        .filter(WorkItem.workspace_id == workspace.id)
        .all()
    )

    results: list[dict] = []

    for chunk, item in chunks:
        similarity = _cosine_similarity(query_embedding, chunk.embedding)

        lexical_bonus = 0.0
        text = f"{item.title} {item.body} {item.category or ''} {item.priority}".lower()

        for token in cleaned_query.lower().split():
            if len(token) >= 3 and token in text:
                lexical_bonus += 0.025

        final_score = min(1.0, round(similarity + lexical_bonus, 4))

        results.append(
            {
                "work_item": item,
                "similarity": final_score,
                "matched_content": chunk.content[:700],
                "reason": (
                    "Matched using stored ticket embedding with lightweight lexical boosting. "
                    "This demo uses deterministic local embeddings; production can swap in Gemini/OpenAI embeddings."
                ),
            }
        )

    results.sort(key=lambda row: row["similarity"], reverse=True)
    return results[: max(1, min(limit, 20))]


def similar_work_items(
    db: Session,
    workspace: Workspace,
    work_item_id: UUID,
    limit: int = 5,
) -> list[dict]:
    source_chunk = (
        db.query(DataChunk)
        .filter(DataChunk.workspace_id == workspace.id)
        .filter(DataChunk.work_item_id == work_item_id)
        .first()
    )

    if not source_chunk:
        return []

    chunks = (
        db.query(DataChunk, WorkItem)
        .join(WorkItem, WorkItem.id == DataChunk.work_item_id)
        .filter(DataChunk.workspace_id == workspace.id)
        .filter(WorkItem.workspace_id == workspace.id)
        .filter(WorkItem.id != work_item_id)
        .all()
    )

    results: list[dict] = []

    for chunk, item in chunks:
        similarity = _cosine_similarity(source_chunk.embedding, chunk.embedding)

        results.append(
            {
                "work_item": item,
                "similarity": similarity,
                "matched_content": chunk.content[:700],
                "reason": (
                    "Similar ticket found by comparing stored operational-ticket embeddings."
                ),
            }
        )

    results.sort(key=lambda row: row["similarity"], reverse=True)
    return results[: max(1, min(limit, 20))]