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
        high_risk_items=2,
        completed_jobs=1,
        queued_jobs=0,
    )

    assert payload.total_work_items == 8
    assert payload.pending_actions == 3
    assert payload.approved_actions == 4
    assert payload.rejected_actions == 1
    assert payload.approval_rate == 0.8
    assert payload.estimated_minutes_saved == 34
    assert payload.failed_actions == 0
    assert payload.high_risk_items == 2
    assert payload.completed_jobs == 1
    assert payload.queued_jobs == 0
