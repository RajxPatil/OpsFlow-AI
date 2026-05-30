# OpsFlow AI Demo Script

This script is designed for a 3–5 minute walkthrough of OpsFlow AI.

## Demo Goal

Show that OpsFlow AI is not just an LLM wrapper. It is a full-stack workflow automation system with ingestion, background processing, AI-generated actions, human approval, connector simulation, audit logs, and semantic search.

## Before the Demo

Start the full stack:

```bash
docker compose up --build -d
```

Open:

```txt
http://localhost:3000/dashboard
```

Use demo credentials:

```txt
Email: demo@opsflow.ai
Password: demo123
```

Recommended AI mode for live demos:

```env
AI_PROVIDER=mock
```

Use Gemini mode when you specifically want to show real LLM-backed generation:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_local_key_here
```

Never commit the real key.

## 3–5 Minute Walkthrough

### 1. Introduce the product

Suggested explanation:

> OpsFlow AI is a human-in-the-loop workflow automation platform for operations teams. It ingests tickets, generates AI-backed action recommendations, lets reviewers inspect evidence, and only executes connector actions after human approval.

### 2. Reset the demo workspace

Click **Reset Demo**.

Explain:

> This gives us a clean workspace so the demo can be repeated reliably.

### 3. Upload operational data

Upload the sample CSV from:

```txt
sample_data/demo_tickets.csv
```

Explain:

> The CSV represents messy operational tickets across billing, delivery, login, outage, and support workflows.

### 4. Show background processing

Point to job status or dashboard changes.

Explain:

> The backend creates an ingestion job and the Redis-backed worker processes the file asynchronously. The worker parses records, creates work items, stores embeddings, and generates suggested actions.

### 5. Review AI-suggested actions

Open the pending actions section.

Explain:

> Each suggested action includes an action type, confidence score, explanation, and structured payload.

Possible action types:

- Draft reply
- Escalate issue
- Create task
- Slack alert
- GitHub issue

### 6. Inspect evidence

Click **Inspect** on a suggested action.

Explain:

> The evidence drawer shows the source ticket, reasoning, payload, and execution context. This is important because reviewers need to understand why the AI suggested an action before approving it.

### 7. Approve an action

Click **Approve**.

Explain:

> Approved actions simulate execution through mock connectors. The system currently supports mock Slack, Gmail, Jira, and GitHub integrations.

### 8. Show workflow safety

Mention:

> The approve workflow is idempotent. If the same approve request is repeated, it does not create duplicate integration events. Reviewed actions cannot be arbitrarily changed.

### 9. Show audit trail

Open or scroll to audit trail.

Explain:

> Every important workflow event is recorded: ingestion, action generation, approval, rejection, and connector execution.

### 10. Use semantic search

Search one of:

```txt
refund payment failed
urgent outage
delivery delay
login OTP error
```

Explain:

> OpsFlow AI stores ticket embeddings in PostgreSQL with pgvector, so reviewers can retrieve similar historical issues.

### 11. Close with engineering summary

Suggested close:

> The project demonstrates production-style full-stack engineering: Next.js frontend, FastAPI backend, Redis worker, PostgreSQL with pgvector, AI provider abstraction, human approval workflow, idempotent state transitions, audit logging, Docker Compose, and CI-backed backend smoke tests.

## What to Highlight for SDE Interviews

Emphasize:

- It is not a chatbot.
- It has async background processing.
- It has a real workflow state machine.
- It has idempotent review behavior.
- It has vector search.
- It has auditability.
- It has Dockerized reproducibility.
- It has backend smoke tests and GitHub Actions CI.

## Common Questions and Strong Answers

### Why not execute AI actions automatically?

Because operational workflows can have business impact. The safer product pattern is to let AI recommend and humans approve.

### Why use a mock provider?

The mock provider makes demos and CI deterministic. Real LLM behavior can be enabled through the Gemini provider.

### Why Redis?

CSV ingestion, embedding generation, and action generation are background tasks. Redis lets the API stay responsive while the worker processes jobs asynchronously.

### Why pgvector?

Semantic search needs vector similarity over historical tickets. pgvector keeps structured workflow data and embedding search in the same PostgreSQL database.

### What makes this production-like?

The project includes Docker Compose, async processing, state transition safety, audit logs, provider abstraction, smoke tests, and CI.

## Demo Checklist

Before recording or showing live:

```txt
Docker running
All containers healthy
.env uses safe local key or mock mode
Demo login works
Reset Demo works
CSV upload works
Actions are generated
Inspect drawer opens
Approve/reject works
Audit trail updates
Semantic search returns results
GitHub Actions CI is green
```
