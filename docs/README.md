# SecureVu Documentation

Project guides, deployment notes, model reports, and planning documents.

## Setup & operations

| Document | Description |
|----------|-------------|
| [PROJECT_CONTINUATION_GUIDE.md](PROJECT_CONTINUATION_GUIDE.md) | Migrate the project to a new machine |
| [CCTV_INTEGRATION_GUIDE.md](CCTV_INTEGRATION_GUIDE.md) | RTSP camera integration |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Full deployment guide |
| [DEPLOYMENT_GUIDE_SUMMARY.md](DEPLOYMENT_GUIDE_SUMMARY.md) | Deployment quick reference |

## Models & performance

| Document | Description |
|----------|-------------|
| [MODEL_TRAINING_REPORT.md](MODEL_TRAINING_REPORT.md) | YOLO training parameters and results |
| [MODEL_STATS_REPORT.md](MODEL_STATS_REPORT.md) | Runtime resource consumption benchmarks |
| [KT_SecureVu_Pranaya_Mathur.md](KT_SecureVu_Pranaya_Mathur.md) | Model selection knowledge transfer |

## Planning & product

| Document | Description |
|----------|-------------|
| [SECUREVU_OPTIMIZATION_PLAN.md](SECUREVU_OPTIMIZATION_PLAN.md) | Performance optimization plan |
| [SECUREVU_REFINEMENT_PLAN.md](SECUREVU_REFINEMENT_PLAN.md) | Product refinement plan |
| [CPU_ONLY_PLAN.md](CPU_ONLY_PLAN.md) | CPU-only deployment notes |
| [CLIENT_ONPREM_LICENSING_MODEL.md](CLIENT_ONPREM_LICENSING_MODEL.md) | On-prem licensing model |

## Development log

| Document | Description |
|----------|-------------|
| [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | Chronological development notes |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | Frozen 12-minute POC demonstration script |

## Architecture (POC week 1)

Week 1 delivers a **feature-complete monolith**: live WebRTC, YOLO + InsightFace analytics, rules engine, event clips, alert persistence, and continuous recording segments — all in `app/server.py`. Week 2+ may split media ingest and analytics into separate services; that refactor is explicitly out of scope for the POC branch.
