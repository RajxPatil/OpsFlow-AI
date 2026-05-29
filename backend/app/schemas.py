from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.enums import ActionStatus, ActionType, JobStatus, WorkItemStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class WorkspaceOut(BaseModel):
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class WorkItemOut(BaseModel):
    id: UUID
    title: str
    body: str
    customer: str | None
    channel: str
    priority: str
    status: WorkItemStatus
    category: str | None
    risk_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SuggestedActionOut(BaseModel):
    id: UUID
    work_item_id: UUID
    action_type: ActionType
    title: str
    payload: dict
    explanation: str
    confidence: float
    status: ActionStatus
    created_at: datetime
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SuggestedActionDetailOut(SuggestedActionOut):
    work_item: WorkItemOut
    evidence: list[dict]
    simulated_integrations: list[dict]


class AuditLogOut(BaseModel):
    id: UUID
    event_type: str
    entity_type: str
    entity_id: UUID | None
    description: str
    metadata_json: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngestionJobOut(BaseModel):
    id: UUID
    filename: str
    source_type: str
    status: JobStatus
    row_count: int
    inserted_work_items: int
    generated_actions: int
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UploadResult(BaseModel):
    job_id: UUID
    status: JobStatus
    row_count: int


class GenerateActionsResult(BaseModel):
    generated_actions: int


class MetricsOut(BaseModel):
    total_work_items: int
    pending_actions: int
    approved_actions: int
    rejected_actions: int
    approval_rate: float
    estimated_minutes_saved: int
    failed_actions: int
    high_risk_items: int
    completed_jobs: int
    queued_jobs: int


class ConnectorOut(BaseModel):
    id: str
    name: str
    provider: str
    status: str
    description: str
    last_sync: str
    records: int
    

class SearchResultOut(BaseModel):
    work_item: WorkItemOut
    similarity: float
    matched_content: str
    reason: str
