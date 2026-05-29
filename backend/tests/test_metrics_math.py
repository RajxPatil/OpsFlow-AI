from app.schemas import MetricsOut


def test_metrics_contract_shape():
    payload = MetricsOut(
        total_work_items=8,
        pending_actions=3,
        approved_actions=4,
        rejected_actions=1,
        approval_rate=0.8,
        estimated_minutes_saved=34,
        failed_actions=0,
    )
    assert payload.approval_rate == 0.8
    assert payload.estimated_minutes_saved == 34
