import enum


class ActionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"


class ActionType(str, enum.Enum):
    draft_reply = "draft_reply"
    create_task = "create_task"
    escalate_issue = "escalate_issue"
    update_status = "update_status"
    slack_alert = "slack_alert"
    github_issue = "github_issue"


class WorkItemStatus(str, enum.Enum):
    open = "open"
    in_review = "in_review"
    resolved = "resolved"
    escalated = "escalated"


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
