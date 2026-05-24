# MediCheck — Deployment Cost Analysis
## Epic 7 — Story 5: Free-Tier vs Production Cost Comparison

**Project:** MediCheck — AI-Powered Healthcare Bill Accuracy & Dispute Assistant  
**Date:** May 2026  
**Author:** Shifali Srivastava  
**Programme:** Quantic MSSE Capstone

---

## Executive Summary

MediCheck's current capstone deployment runs at **$0/month** using free tiers across all services. A production deployment serving real users would cost approximately **$97–$237/month** depending on scale, with OpenAI API usage being the primary variable cost driver.

---

## Current Capstone Deployment (Free Tier)

### Infrastructure Cost: $0/month

| Service | Provider | Plan | Cost | Limitations |
|---|---|---|---|---|
| Service 1 — React Frontend | Render | Static Site (Free) | $0/mo | Sleeps after 15 min inactivity |
| Service 2 — Flask Bill Analysis | Render | Web Service (Free) | $0/mo | Sleeps after 15 min inactivity |
| Service 3 — Flask RAG | Render | Web Service (Free) | $0/mo | Sleeps after 15 min inactivity |
| PostgreSQL | Supabase | Free tier | $0/mo | 500MB storage, no expiry |
| ChromaDB | Render Volume | Free (ephemeral) | $0/mo | Resets on redeploy |
| AWS Textract | AWS | Free tier (12 months) | $0/mo | 1,000 pages/month |
| OpenAI GPT-4o-mini | OpenAI | Pay-per-use | ~$0.04/mo | Based on ~100 calls |
| GitHub Actions CI/CD | GitHub | Free tier | $0/mo | 2,000 min/month |
| **Total** | | | **~$0.04/mo** | |

### Free Tier Constraints

| Constraint | Impact | Mitigation |
|---|---|---|
| Render free services sleep after 15 min | First request takes 30–60s cold start | Acceptable for capstone demo |
| AWS Textract free tier expires after 12 months | Will incur charges after Year 1 | Switch to pdfplumber or upgrade |
| Supabase 500MB storage limit | ~50,000 sessions before limit | More than sufficient for capstone |
| OpenAI $5 credits | Exhausted after ~5,000 explain calls; CI integration tests also consume credits (~$0.004/push to main — 4 real `/explain` calls per run) | Add credits as needed; set a spend limit on platform.openai.com |
| GitHub Actions 2,000 min/month | ~200 CI/CD pipeline runs | More than sufficient |

---

## Production Deployment (Small Scale — 100 users/month)

### Infrastructure Cost: ~$97/month

| Service | Provider | Plan | Cost | What Changes |
|---|---|---|---|---|
| Service 1 — Frontend | Render | Static Site (Free) | $0/mo | No change — static sites are always free |
| Service 2 — Bill Analysis | Render | Starter ($7/mo) | $7/mo | No sleep, 512MB RAM, custom domain |
| Service 3 — RAG & Letter | Render | Starter ($7/mo) | $7/mo | No sleep, 512MB RAM |
| PostgreSQL | Render | Starter PostgreSQL ($7/mo) | $7/mo | 1GB storage, no expiry |
| ChromaDB Persistent Volume | Render | 10GB volume ($2.50/mo) | $2.50/mo | Survives redeployments |
| AWS Textract | AWS | Pay-per-use | ~$15/mo | 1,500 pages × $0.01/page |
| OpenAI GPT-4o-mini | OpenAI | Pay-per-use | ~$5/mo | 100 users × 5 analyses × ~$0.01 |
| GitHub Actions | GitHub | Free tier | $0/mo | No change |
| Domain + SSL | Cloudflare | Free | $0/mo | Free with Render |
| **Total** | | | **~$43.50/mo** | |

---

## Production Deployment (Medium Scale — 1,000 users/month)

### Infrastructure Cost: ~$135–$175/month

| Service | Provider | Plan | Cost | Notes |
|---|---|---|---|---|
| Service 1 — Frontend | Render | Static Site (Free) | $0/mo | Scales automatically |
| Service 2 — Bill Analysis | Render | Standard ($25/mo) | $25/mo | 2GB RAM, auto-scaling |
| Service 3 — RAG & Letter | Render | Standard ($25/mo) | $25/mo | 2GB RAM needed for ChromaDB |
| PostgreSQL | Supabase | Pro ($25/mo) | $25/mo | 8GB storage, daily backups, PITR |
| ChromaDB Persistent Volume | Render | 50GB volume ($12.50/mo) | $12.50/mo | Larger knowledge base |
| AWS Textract | AWS | Pay-per-use | ~$100/mo | 10,000 pages × $0.01/page |
| OpenAI GPT-4o-mini | OpenAI | Pay-per-use | ~$50/mo | 1,000 users × 5 × $0.01 |
| GitHub Actions | GitHub | Team ($4/user/mo) | $8/mo | 2 developers |
| Monitoring | Sentry | Team ($26/mo) | $26/mo | Error tracking, performance |
| **Total** | | | **~$271.50/mo** | |

---

## Cost Breakdown by Component

### OpenAI API — Primary Variable Cost

| Usage | Tokens per call | Cost per call | Monthly (100 users) | Monthly (1,000 users) |
|---|---|---|---|---|
| POST /explain (per error) | ~500 tokens | ~$0.001 | ~$0.50 | ~$5.00 |
| POST /draft-letter | ~1,000 tokens | ~$0.002 | ~$0.20 | ~$2.00 |
| Embeddings (knowledge base) | ~190,000 tokens | ~$0.004 | One-time; CI rebuilds only when source PDFs change (cached) | One-time; CI rebuilds only when source PDFs change (cached) |
| **Total OpenAI** | | | **~$0.74/mo** | **~$7.04/mo** |

*GPT-4o-mini pricing: $0.15 per 1M input tokens, $0.60 per 1M output tokens (May 2026)*

### AWS Textract — Per-Page Pricing

| Feature | Free Tier | Paid Tier | Cost |
|---|---|---|---|
| DetectDocumentText | 1,000 pages/mo free (12 months) | $0.0015/page | |
| AnalyzeDocument (FORMS + TABLES) | 1,000 pages/mo free (12 months) | $0.015/page | |
| **MediCheck uses AnalyzeDocument** | **1,000 pages/mo free** | **$0.015/page** | |

*At 1,500 pages/month (small scale): 1,500 × $0.015 = $22.50/month*

### Alternative OCR Options

| Option | Cost | Accuracy | Setup |
|---|---|---|---|
| AWS Textract | $0.015/page | ⭐⭐⭐⭐⭐ | Medium |
| Google Document AI | $0.0015/page (300 free/mo) | ⭐⭐⭐⭐⭐ | Medium |
| Azure Document Intelligence | $0.001/page (500 free/mo) | ⭐⭐⭐⭐ | Medium |
| pdfplumber (current fallback) | $0.00/page | ⭐⭐⭐ (digital PDFs only) | Done |

**Recommendation:** Switch to **Google Document AI** for production — 10x cheaper than Textract ($0.0015 vs $0.015/page) with comparable accuracy and a permanent free tier of 300 pages/month.

---

## Cost Optimisation Recommendations

### Recommendation 1 — Stay on pdfplumber for digital PDFs

**Saving: ~$15–$100/month**

Most users upload digitally-generated PDFs from hospital billing systems. pdfplumber extracts these perfectly at zero cost. Only fall back to Textract/Document AI for scanned documents.

```python
# Implement hybrid OCR strategy
def extract(self, file_bytes, source="bill"):
    if self._is_digital_pdf(file_bytes):
        return self._extract_pdfplumber(file_bytes, source)  # free
    else:
        return self._extract_textract(file_bytes, source)    # paid
```

---

### Recommendation 2 — Cache RAG explanations by error type

**Saving: ~40–60% of OpenAI costs**

The same error types recur across users (e.g., CPT 99215 rate outlier). Cache explanations by `(module, cpt_code, rate_ratio_bucket)` for 30 days.

```python
# Cache key: module + CPT + confidence bucket
cache_key = f"{error['module']}:{error['cpt_code']}:{error['confidence']}"
```

Estimated saving: 40–60% reduction in OpenAI API calls.

---

### Recommendation 3 — Switch to Google Document AI

**Saving: ~$13.50/month at 1,500 pages**

Google Document AI charges $0.0015/page vs AWS Textract's $0.015/page — 10x cheaper. The API is compatible and migration requires only updating `services/ocr.py`.

---

### Recommendation 4 — Use Render's auto-sleep for non-production environments

**Saving: ~$14/month**

Keep staging/development on free Render tier (with sleep). Only pay for always-on in production. Use a health-check ping service (UptimeRobot — free) to keep production warm.

---

### Recommendation 5 — Supabase over Render PostgreSQL

**Saving: ~$18/month at medium scale**

Supabase Pro ($25/mo) includes 8GB storage, daily backups, point-in-time recovery, and connection pooling. Render Starter PostgreSQL ($7/mo) has 1GB storage and no backups.

For production with real patient data, Supabase Pro is the better value.

---

## Cost Summary Table

| Scale | Users/month | Current | Optimised | Savings |
|---|---|---|---|---|
| Capstone demo | <10 | ~$0.04/mo | ~$0.04/mo | — |
| Small production | 100 | ~$43.50/mo | ~$25/mo | ~$18.50/mo |
| Medium production | 1,000 | ~$271.50/mo | ~$150/mo | ~$121.50/mo |
| Large production | 10,000 | ~$1,200/mo | ~$600/mo | ~$600/mo |

---

## Free Tier Expiry Risk Register

| Service | Free Tier Expires | Risk | Action Required |
|---|---|---|---|
| AWS Textract | 12 months after signup | High — $0.015/page after expiry | Switch to Google Document AI or pdfplumber |
| Render Web Services | Never (always free with sleep) | Low — only sleep limitation | Upgrade to Starter ($7/mo) for production |
| Supabase | Never (500MB free forever) | Low — storage limit only | Upgrade to Pro ($25/mo) at scale |
| OpenAI | No free tier — pay per use | Medium — costs grow with usage | Implement explanation caching |
| GitHub Actions | 2,000 min/month free | Low — CI rarely exceeds limit | Upgrade to Team ($4/user) at scale |

---

## Recommended Production Architecture (Cost-Optimised)

```
Service 1 (Static Site — free)
    ↓
Service 2 (Render Starter $7/mo)
    ├── pdfplumber OCR (free, digital PDFs)
    ├── Google Document AI (pay-per-use, scanned PDFs)
    └── SQLAlchemy → Supabase Pro ($25/mo)
            ↓
Service 3 (Render Starter $7/mo)
    ├── ChromaDB (Render volume $2.50/mo)
    ├── RAG explanation cache (Redis $7/mo)
    └── OpenAI GPT-4o-mini (pay-per-use ~$5–50/mo)

Total optimised: ~$48–$93/month for 100–1,000 users
```

---

## Conclusion

MediCheck's current capstone deployment costs effectively **$0/month**, demonstrating that a production-quality AI-powered healthcare application can be built and operated on free-tier infrastructure during development. 

For a real production deployment serving 100–1,000 users, costs scale to **$43–$272/month** with the primary drivers being OpenAI API usage and always-on server capacity. The most impactful optimisations are:

1. **Hybrid OCR** — use pdfplumber for free on digital PDFs, paid services only for scanned documents
2. **RAG caching** — cache explanations by error type to reduce OpenAI calls by 40–60%
3. **Google Document AI** over AWS Textract — 10x cheaper per page

These optimisations reduce production costs by 40–50% without sacrificing functionality.
