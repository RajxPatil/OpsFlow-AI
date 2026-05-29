from dataclasses import dataclass

from app.enums import ActionType


@dataclass(frozen=True)
class AgentSuggestion:
    action_type: ActionType
    title: str
    payload: dict
    explanation: str
    confidence: float
    category: str
