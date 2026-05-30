import os
import time

import httpx


BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
DEMO_EMAIL = os.getenv("TEST_EMAIL", "demo@opsflow.ai")
DEMO_PASSWORD = os.getenv("TEST_PASSWORD", "demo123")

SAMPLE_CSV = """title,body,customer,channel,priority,status
Duplicate payment refund issue,"Customer says payment was debited twice and refund is still not visible on invoice.",Ananya,email,high,open
Login OTP error,"User cannot login because OTP verification keeps failing on mobile app.",Rohit,chat,medium,open
Delivery delay escalation,"Shipment is delayed by 5 days and customer is asking for urgent update.",Priya,email,high,open
Checkout outage for many users,"Multiple users report checkout down and payment failed after order confirmation.",Ops Team,slack,urgent,open
"""


def login_headers(client: httpx.Client) -> dict:
    response = client.post(
        "/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def wait_for_completed_job(client: httpx.Client, headers: dict, job_id: str) -> dict:
    for _ in range(30):
        response = client.get("/jobs", headers=headers)
        assert response.status_code == 200, response.text

        jobs = response.json()
        job = next((item for item in jobs if item["id"] == job_id), None)

        if job and job["status"] == "completed":
            return job

        if job and job["status"] == "failed":
            raise AssertionError(f"Ingestion job failed: {job}")

        time.sleep(0.5)

    raise AssertionError("Timed out waiting for ingestion job to complete")


def test_opsflow_end_to_end_workflow_smoke():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text

        headers = login_headers(client)

        reset = client.post("/demo/reset", headers=headers)
        assert reset.status_code == 200, reset.text

        upload = client.post(
            "/sources/upload_csv",
            headers=headers,
            files={
                "file": (
                    "test_tickets.csv",
                    SAMPLE_CSV.encode("utf-8"),
                    "text/csv",
                )
            },
        )
        assert upload.status_code == 200, upload.text

        job_id = upload.json()["job_id"]
        job = wait_for_completed_job(client, headers, job_id)

        assert job["inserted_work_items"] >= 4
        assert job["generated_actions"] >= 1

        actions_response = client.get("/actions", headers=headers)
        assert actions_response.status_code == 200, actions_response.text

        actions = actions_response.json()
        pending_actions = [item for item in actions if item["status"] == "pending"]

        assert pending_actions, "Expected at least one pending AI action"

        action_id = pending_actions[0]["id"]

        detail = client.get(f"/actions/{action_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["evidence"], "Expected action evidence to be present"

        approve_once = client.post(f"/actions/{action_id}/approve", headers=headers)
        assert approve_once.status_code == 200, approve_once.text
        assert approve_once.json()["status"] == "approved"

        approve_twice = client.post(f"/actions/{action_id}/approve", headers=headers)
        assert approve_twice.status_code == 200, approve_twice.text
        assert approve_twice.json()["status"] == "approved"

        reject_after_approve = client.post(f"/actions/{action_id}/reject", headers=headers)
        assert reject_after_approve.status_code == 400
        assert "already been reviewed" in reject_after_approve.text

        search = client.get(
            "/search/work-items",
            headers=headers,
            params={"q": "refund payment failed", "limit": 5},
        )
        assert search.status_code == 200, search.text

        results = search.json()
        assert results, "Expected semantic search results"
        assert "similarity" in results[0]
        assert "work_item" in results[0]

        work_item_id = results[0]["work_item"]["id"]
        similar = client.get(f"/workitems/{work_item_id}/similar", headers=headers)
        assert similar.status_code == 200, similar.text
        assert isinstance(similar.json(), list)
