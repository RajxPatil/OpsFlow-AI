from app.agent import suggest_actions_for_work_item


def test_incident_generates_human_approved_integration_actions():
    suggestions = suggest_actions_for_work_item(
        "Checkout outage impacting multiple merchants",
        "Several merchants report checkout down after the latest release.",
        "Merchant Ops",
        "urgent",
    )
    action_types = {s.action_type.value for s in suggestions}
    assert "slack_alert" in action_types
    assert "github_issue" in action_types
    assert "draft_reply" in action_types


def test_payloads_keep_human_review_boundary():
    suggestions = suggest_actions_for_work_item("Refund request", "Payment was debited twice", "Ananya", "high")
    draft = next(s for s in suggestions if s.action_type.value == "draft_reply")
    assert draft.payload["requires_human_review"] is True
