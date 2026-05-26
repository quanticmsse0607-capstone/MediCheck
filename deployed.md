# MediCheck — Deployed Service URLs

All three services are deployed on Render's free tier from this repository.

| Service | Description | URL |
|---------|-------------|-----|
| Service 1 — Frontend | React + Vite SPA | https://medicheck-frontend-i3rv.onrender.com |
| Service 2 — Bill Analysis API | Flask REST API | https://medicheck-bill-analysis.onrender.com |
| Service 3 — RAG & Letter Service | Flask RAG microservice | https://medicheck-rag.onrender.com |

## Health Check Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Service 2 | `GET /health` | `{"status": "ok", "service": "bill-analysis"}` |
| Service 3 | `GET /health` | `{"status": "ok", "service": "rag"}` |

## Notes

- Free tier services spin down after 15 minutes of inactivity. Allow up to 30 seconds for a cold start.
- For the Sprint 6 presentation, open all three service URLs at least 2 minutes before recording to warm them up.