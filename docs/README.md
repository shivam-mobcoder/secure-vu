# SecureVu Documentation

Operational guides for the **POC** branch. See [root README](../README.md) for quick start, `requirements.txt`, and Docker Compose with MLflow.

## POC & operations (start here)

| Document | Description |
|----------|-------------|
| [../handoff/README-HANDOFF.md](../handoff/README-HANDOFF.md) | Owner USB handoff + install script |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | Frozen 12-minute POC demonstration script |
| [MLFLOW.md](MLFLOW.md) | MLflow experiment and configuration tracking |
| [CCTV_INTEGRATION_GUIDE.md](CCTV_INTEGRATION_GUIDE.md) | RTSP camera integration |
| [PROJECT_CONTINUATION_GUIDE.md](PROJECT_CONTINUATION_GUIDE.md) | Migrate the project to a new machine |

## Setup & deployment

| Document | Description |
|----------|-------------|
| [DEPLOYMENT_GUIDE_SUMMARY.md](DEPLOYMENT_GUIDE_SUMMARY.md) | Deployment quick reference (POC stack + sizing) |

## Models & performance

| Document | Description |
|----------|-------------|
| [MODEL_TRAINING_REPORT.md](MODEL_TRAINING_REPORT.md) | YOLO training parameters and results |
| [MODEL_STATS_REPORT.md](MODEL_STATS_REPORT.md) | Runtime resource consumption benchmarks |

Training with MLflow: `uv run --group mlops scripts/train_yolo.py` (see [MLFLOW.md](MLFLOW.md)).

## Development log

| Document | Description |
|----------|-------------|
| [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | Chronological development notes |

## Architecture (POC branch)

Week 1 delivers a **feature-complete monolith** in `app/server.py`:

| Capability | Status |
|------------|--------|
| Live WebRTC (2–4 cams) | Done |
| YOLO + ByteTrack + InsightFace | Done |
| Rules: zones, lines, crowd, parking, loitering, motion | Done |
| Event clips | Done |
| Alert Postgres persistence (`/api/alerts`) | Done |
| Continuous recording segments (`/api/recordings`) | Done |
| Camera health API | Done |
| Admin UI: live feed, alerts hydrate, playback | Done |
| MLflow config/training tracking | Done |

**Migrations:** `001_init.sql` (core schema) + `002_poc.sql` (`alerts`, `recording_segments`).

**Dependencies:** `pyproject.toml` + `uv.lock`; pip users: `requirements.txt` (from `uv export --group mlops`).
