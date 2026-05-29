from app.ai.providers.base import AIProvider
from app.ai.providers.gemini_provider import GeminiAIProvider
from app.ai.providers.mock_provider import MockAIProvider, hash_embedding
from app.config import settings


def get_ai_provider() -> AIProvider:
    provider = settings.ai_provider.lower().strip()

    if provider == "gemini":
        return GeminiAIProvider()

    return MockAIProvider()


def suggest_actions_for_work_item(
    title: str,
    body: str,
    customer: str | None,
    priority: str,
):
    provider = get_ai_provider()
    return provider.suggest_actions_for_work_item(title, body, customer, priority)


__all__ = ["suggest_actions_for_work_item", "hash_embedding", "get_ai_provider"]
