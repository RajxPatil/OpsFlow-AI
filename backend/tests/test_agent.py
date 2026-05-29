from app.agent import classify_text, hash_embedding, suggest_actions_for_work_item
from app.enums import ActionType


def test_classifies_billing_issue():
    category, confidence, matched = classify_text("Refund not processed", "Payment debited and refund pending", "high")
    assert category == "billing"
    assert confidence >= 0.68
    assert "refund" in matched or "payment" in matched


def test_suggests_human_review_actions():
    actions = suggest_actions_for_work_item("App crash", "Android app crashes during checkout", "Priya", "urgent")
    action_types = {action.action_type for action in actions}
    assert ActionType.draft_reply in action_types
    assert ActionType.escalate_issue in action_types
    assert any(action.payload.get("requires_human_review") for action in actions if action.action_type == ActionType.draft_reply)


def test_hash_embedding_is_deterministic_and_64_dimensional():
    vec1 = hash_embedding("refund pending")
    vec2 = hash_embedding("refund pending")
    assert vec1 == vec2
    assert len(vec1) == 64
