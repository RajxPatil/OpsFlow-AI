import hashlib
import math
import re

from app.ai.providers.base import AIProvider
from app.ai.schemas import AgentSuggestion
from app.enums import ActionType


CATEGORY_KEYWORDS = {
    "billing": ["refund", "invoice", "payment", "gst", "charged", "debit", "billing"],
    "bug": ["crash", "error", "bug", "failure", "not working", "otp", "login"],
    "delivery": ["delivery", "late", "courier", "shipment", "delay"],
    "incident": ["multiple", "urgent", "outage", "several", "many users", "down"],
    "feedback": ["praise", "thanks", "positive", "feature request", "request"],
}


class MockAIProvider(AIProvider):
    name = "mock"

    def suggest_actions_for_work_item(
        self,
        title: str,
        body: str,
        customer: str | None,
        priority: str,
    ) -> list[AgentSuggestion]:
        return suggest_actions_for_work_item(title, body, customer, priority)


def classify_text(title: str, body: str, priority: str = "medium") -> tuple[str, float, list[str]]:
    text = f"{title} {body}".lower()
    scores: dict[str, int] = {}
    matched: list[str] = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in text:
                score += 1
                matched.append(keyword)
        scores[category] = score

    if priority.lower() in {"urgent", "critical", "high"}:
        scores["incident"] += 1

    category = max(scores, key=scores.get)
    raw_score = scores[category]

    if raw_score == 0:
        return "general", 0.62, []

    confidence = min(0.93, 0.60 + raw_score * 0.08)
    return category, confidence, matched[:5]


def suggest_actions_for_work_item(
    title: str,
    body: str,
    customer: str | None,
    priority: str,
) -> list[AgentSuggestion]:
    category, confidence, matched = classify_text(title, body, priority)
    customer_name = customer or "customer"
    matched_text = ", ".join(matched) if matched else "general support signals"

    suggestions: list[AgentSuggestion] = []

    if category in {"billing", "delivery", "bug", "incident"} or priority.lower() in {
        "high",
        "urgent",
        "critical",
    }:
        suggestions.append(
            AgentSuggestion(
                action_type=ActionType.escalate_issue,
                title=f"Escalate {category} issue for {customer_name}",
                payload={
                    "category": category,
                    "priority": priority,
                    "assignee": "ops-lead",
                    "sla_hours": 4 if priority.lower() == "urgent" else 12,
                    "requires_human_review": True,
                    "ai_provider": "mock",
                },
                explanation=(
                    f"The item was classified as {category} with confidence {confidence:.2f}. "
                    f"Signals: {matched_text}. Priority is {priority}, so escalation is safer before execution."
                ),
                confidence=confidence,
                category=category,
            )
        )

    draft = build_reply_draft(category, customer_name, title)

    suggestions.append(
        AgentSuggestion(
            action_type=ActionType.draft_reply,
            title=f"Draft customer reply for {customer_name}",
            payload={
                "draft_reply": draft,
                "tone": "empathetic-professional",
                "requires_human_review": True,
                "ai_provider": "mock",
            },
            explanation=(
                "A response draft is recommended because the work item contains a customer-facing "
                f"support request. Category: {category}. Signals: {matched_text}."
            ),
            confidence=max(0.68, confidence - 0.03),
            category=category,
        )
    )

    if category == "incident":
        suggestions.append(
            AgentSuggestion(
                action_type=ActionType.slack_alert,
                title=f"Send Slack incident alert for {customer_name}",
                payload={
                    "channel": "#ops-incidents",
                    "severity": priority,
                    "summary": title,
                    "requires_human_review": True,
                    "ai_provider": "mock",
                },
                explanation=(
                    f"Incident-like signals were detected ({matched_text}). The platform prepares "
                    "a Slack alert but waits for human approval before execution."
                ),
                confidence=max(0.74, confidence - 0.01),
                category=category,
            )
        )

    if category in {"bug", "incident"}:
        suggestions.append(
            AgentSuggestion(
                action_type=ActionType.github_issue,
                title=f"Open engineering issue: {title[:72]}",
                payload={
                    "repo": "opsflow/demo-product",
                    "labels": [category, priority.lower()],
                    "issue_title": title,
                    "requires_human_review": True,
                    "ai_provider": "mock",
                },
                explanation=(
                    f"This issue appears engineering-actionable. A GitHub issue is drafted with "
                    f"category {category} and signals: {matched_text}."
                ),
                confidence=max(0.70, confidence - 0.02),
                category=category,
            )
        )

    if category in {"bug", "incident", "feedback"}:
        suggestions.append(
            AgentSuggestion(
                action_type=ActionType.create_task,
                title=f"Create internal task: {title[:72]}",
                payload={
                    "task_title": title,
                    "category": category,
                    "labels": [category, priority.lower()],
                    "owner": "engineering" if category in {"bug", "incident"} else "product",
                    "requires_human_review": True,
                    "ai_provider": "mock",
                },
                explanation=(
                    "The issue likely requires internal follow-up beyond a support reply. "
                    f"Category {category} was selected from signals: {matched_text}."
                ),
                confidence=max(0.70, confidence - 0.02),
                category=category,
            )
        )

    return suggestions


def build_reply_draft(category: str, customer_name: str, title: str) -> str:
    templates = {
        "billing": (
            f"Hi {customer_name}, thanks for flagging this. We understand the urgency around your "
            "billing/refund concern. Our team is reviewing the transaction details and will share "
            "a confirmed update shortly."
        ),
        "bug": (
            f"Hi {customer_name}, thanks for reporting this issue. We are sharing the details with "
            "our engineering team and will update you once the root cause is confirmed."
        ),
        "delivery": (
            f"Hi {customer_name}, sorry about the delay. We are checking the delivery status and "
            "will get back with the latest ETA as soon as possible."
        ),
        "incident": (
            f"Hi {customer_name}, we are treating this as a high-priority issue. Our operations team "
            "is investigating and will share an update shortly."
        ),
        "feedback": (
            f"Hi {customer_name}, thank you for sharing this feedback. We appreciate it and will pass "
            "it to the relevant team."
        ),
        "general": (
            f"Hi {customer_name}, thanks for reaching out. We are reviewing your request regarding "
            f"'{title}' and will update you shortly."
        ),
    }

    return templates.get(category, templates["general"])


def hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    vector = [0.0] * dimensions

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [round(x / norm, 6) for x in vector]
