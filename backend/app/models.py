import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ActionStatus, ActionType, JobStatus, WorkItemStatus


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="owner")


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    owner: Mapped[User] = relationship(back_populates="workspaces")
    work_items: Mapped[list["WorkItem"]] = relationship(back_populates="workspace")


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class IngestionJob(Base, TimestampMixin):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="csv", nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inserted_work_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_actions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkItem(Base, TimestampMixin):
    __tablename__ = "work_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    customer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(String(50), default="csv", nullable=False)
    priority: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    status: Mapped[WorkItemStatus] = mapped_column(Enum(WorkItemStatus), default=WorkItemStatus.open, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.35, nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="work_items")
    actions: Mapped[list["SuggestedAction"]] = relationship(back_populates="work_item")


class DataChunk(Base, TimestampMixin):
    __tablename__ = "data_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    work_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_items.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(64), nullable=True)


class SuggestedAction(Base, TimestampMixin):
    __tablename__ = "suggested_actions"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    work_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_items.id"), nullable=False)
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    status: Mapped[ActionStatus] = mapped_column(Enum(ActionStatus), default=ActionStatus.pending, nullable=False)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    work_item: Mapped[WorkItem] = relationship(back_populates="actions")


class IntegrationEvent(Base, TimestampMixin):
    __tablename__ = "integration_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    suggested_action_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suggested_actions.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="simulated", nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
