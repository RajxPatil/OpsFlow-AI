from abc import ABC, abstractmethod

from app.ai.schemas import AgentSuggestion


class AIProvider(ABC):
    name: str

    @abstractmethod
    def suggest_actions_for_work_item(
        self,
        title: str,
        body: str,
        customer: str | None,
        priority: str,
    ) -> list[AgentSuggestion]:
        raise NotImplementedError
