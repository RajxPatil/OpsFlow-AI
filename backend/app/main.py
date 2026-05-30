from typing import Annotated
from uuid import UUID

import redis
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, get_demo_workspace, verify_password
from app.config import settings
from app.database import Base, engine, get_db
from app.enums import ActionStatus
from app.models import (
    AuditLog,
    DataChunk,
    DataSource,
    IngestionJob,
    IntegrationEvent,
    SuggestedAction,
    User,
    WorkItem,
)

from app.schemas import (
    AuditLogOut,
    ConnectorOut,
    GenerateActionsResult,
    IngestionJobOut,
    LoginRequest,
    MetricsOut,
    SearchResultOut,
    SuggestedActionDetailOut,
    SuggestedActionOut,
    Token,
    UploadResult,
    UserOut,
    WorkItemOut,
    WorkspaceOut,
)

from app.services import (
    action_detail,
    compute_metrics,
    create_audit_log,
    create_ingestion_job,
    generate_actions,
    mock_connectors,
    review_action,
    semantic_search_work_items,
    similar_work_items,
    process_ingestion_job,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="OpsFlow AI API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.backend_cors_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def enqueue_ingestion_job(job_id: UUID) -> None:
    client = redis.from_url(settings.redis_url)
    client.lpush("opsflow:ingestion_jobs", str(job_id))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "opsflow-ai-api", "version": "0.2.0"}

@app.get("/system/status")
def system_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    redis_ok = False
    db_ok = False

    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        redis.from_url(settings.redis_url).ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    provider_descriptions = {
        "mock": "Deterministic local demo agent. No external API key required.",
        "openai": "OpenAI-backed structured action generation.",
        "deepseek": "DeepSeek-backed structured action generation.",
        "gemini": "Gemini-backed structured action generation.",
        "ollama": "Local model-backed structured action generation.",
    }

    return {
        "api": "ok",
        "database": "ok" if db_ok else "down",
        "redis": "ok" if redis_ok else "down",
        "ai_provider": settings.ai_provider,
        "ai_description": provider_descriptions.get(
            settings.ai_provider,
            "Configured AI provider for structured workflow recommendations.",
        ),
    }


@app.post("/demo/reset")
def reset_demo(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    workspace = get_demo_workspace(db, current_user)

    db.query(IntegrationEvent).filter(
        IntegrationEvent.workspace_id == workspace.id
    ).delete(synchronize_session=False)

    db.query(SuggestedAction).filter(
        SuggestedAction.workspace_id == workspace.id
    ).delete(synchronize_session=False)

    db.query(DataChunk).filter(
        DataChunk.workspace_id == workspace.id
    ).delete(synchronize_session=False)

    db.query(WorkItem).filter(
        WorkItem.workspace_id == workspace.id
    ).delete(synchronize_session=False)

    db.query(DataSource).filter(
        DataSource.workspace_id == workspace.id
    ).delete(synchronize_session=False)

    db.query(IngestionJob).filter(
        IngestionJob.workspace_id == workspace.id
    ).delete(synchronize_session=False)

    db.query(AuditLog).filter(
        AuditLog.workspace_id == workspace.id
    ).delete(synchronize_session=False)

    create_audit_log(
        db=db,
        workspace_id=workspace.id,
        actor_id=current_user.id,
        event_type="demo_reset",
        entity_type="workspace",
        entity_id=workspace.id,
        description="Demo workspace was reset for a fresh recruiter walkthrough.",
        metadata={"reset_by": current_user.email},
    )

    db.commit()

    return {
        "status": "reset",
        "message": "Demo workspace reset successfully. Upload the sample CSV to replay the workflow.",
    }

@app.post("/auth/login", response_model=Token)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> Token:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return Token(access_token=create_access_token(user.email))


@app.get("/auth/me", response_model=UserOut)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@app.get("/workspaces/demo", response_model=WorkspaceOut)
def demo_workspace(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return get_demo_workspace(db, current_user)


@app.post("/sources/upload_csv", response_model=UploadResult)
async def upload_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")
    workspace = get_demo_workspace(db, current_user)
    try:
        job = create_ingestion_job(db, workspace, current_user, file.filename, await file.read())
        if settings.process_jobs_inline:
            job = process_ingestion_job(db, job.id)
        else:
            enqueue_ingestion_job(job.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResult(job_id=job.id, status=job.status, row_count=job.row_count)


@app.get("/jobs", response_model=list[IngestionJobOut])
def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    return db.query(IngestionJob).filter(IngestionJob.workspace_id == workspace.id).order_by(IngestionJob.created_at.desc()).limit(25).all()


@app.get("/workitems", response_model=list[WorkItemOut])
def list_work_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    return db.query(WorkItem).filter(WorkItem.workspace_id == workspace.id).order_by(WorkItem.created_at.desc()).limit(100).all()


@app.get("/search/work-items", response_model=list[SearchResultOut])
def search_work_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(8, ge=1, le=20),
):
    workspace = get_demo_workspace(db, current_user)
    return semantic_search_work_items(db, workspace, q, limit)


@app.get("/workitems/{work_item_id}/similar", response_model=list[SearchResultOut])
def get_similar_work_items(
    work_item_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(5, ge=1, le=20),
):
    workspace = get_demo_workspace(db, current_user)
    return similar_work_items(db, workspace, work_item_id, limit)


@app.post("/actions/generate", response_model=GenerateActionsResult)
def generate_ai_actions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    generated = generate_actions(db, workspace, current_user)
    return GenerateActionsResult(generated_actions=generated)


@app.get("/actions", response_model=list[SuggestedActionOut])
def list_actions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    return db.query(SuggestedAction).filter(SuggestedAction.workspace_id == workspace.id).order_by(SuggestedAction.created_at.desc()).limit(100).all()


@app.get("/actions/{action_id}", response_model=SuggestedActionDetailOut)
def get_action_detail(
    action_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    try:
        detail = action_detail(db, workspace, action_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    action = detail["action"]
    return SuggestedActionDetailOut(
        **SuggestedActionOut.model_validate(action).model_dump(),
        work_item=action.work_item,
        evidence=detail["evidence"],
        simulated_integrations=detail["simulated_integrations"],
    )


@app.post("/actions/{action_id}/approve", response_model=SuggestedActionOut)
def approve_action(
    action_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    try:
        return review_action(db, workspace, current_user, action_id, ActionStatus.approved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/actions/{action_id}/reject", response_model=SuggestedActionOut)
def reject_action(
    action_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    try:
        return review_action(db, workspace, current_user, action_id, ActionStatus.rejected)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/audit", response_model=list[AuditLogOut])
def list_audit_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    return db.query(AuditLog).filter(AuditLog.workspace_id == workspace.id).order_by(AuditLog.created_at.desc()).limit(100).all()


@app.get("/metrics", response_model=MetricsOut)
def metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = get_demo_workspace(db, current_user)
    return compute_metrics(db, workspace)


@app.get("/connectors", response_model=list[ConnectorOut])
def connectors(current_user: Annotated[User, Depends(get_current_user)]):
    return mock_connectors()
