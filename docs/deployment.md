# Deployment Notes

## Simple Demo Deployment

Recommended beginner-friendly deployment split:

- Frontend: Vercel
- Backend: Render / Fly.io / Railway
- Database: Neon / Supabase Postgres with pgvector
- Redis: Upstash Redis

## Production-Style Deployment

- AWS ECS/Fargate for backend and worker
- RDS PostgreSQL with pgvector
- ElastiCache Redis
- S3 for file uploads
- CloudFront + Vercel/AWS Amplify for frontend
- GitHub Actions for CI/CD

## Environment Variables

Backend:

```text
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
JWT_SECRET=...
ACCESS_TOKEN_EXPIRE_MINUTES=1440
AI_PROVIDER=mock
```

Frontend:

```text
NEXT_PUBLIC_API_URL=https://your-backend-url
```
