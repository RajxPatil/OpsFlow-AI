from __future__ import annotations

import time
from uuid import UUID

import redis

from app.config import settings
from app.database import SessionLocal
from app.services import process_ingestion_job

QUEUE_NAME = "opsflow:ingestion_jobs"


def main() -> None:
    client = redis.from_url(settings.redis_url)
    print("OpsFlow worker started. Redis ping:", client.ping(), flush=True)
    while True:
        try:
            item = client.brpop(QUEUE_NAME, timeout=5)
            if not item:
                continue
            _, raw_job_id = item
            job_id = UUID(raw_job_id.decode("utf-8"))
            with SessionLocal() as db:
                job = process_ingestion_job(db, job_id)
                print(f"Processed ingestion job {job.id} -> {job.status}", flush=True)
        except Exception as exc:  # pragma: no cover - long-running process guard
            print(f"Worker error: {exc}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
