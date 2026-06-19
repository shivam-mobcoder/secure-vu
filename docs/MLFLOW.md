# MLflow Experiment Tracking

SecureVu uses [MLflow](https://mlflow.org/) to track training runs, deployment configuration snapshots, threshold changes, and benchmark profiles.

## Quick start

1. Copy env vars from [`.env.example`](../.env.example) (`MLFLOW_*` section).
2. Start the stack (includes MLflow on port 5000):

```bash
docker compose up --build
```

3. Open the MLflow UI: [http://localhost:5000](http://localhost:5000)

For local dev without Docker:

```bash
uv sync --group mlops
mlflow server --host 127.0.0.1 --port 5000 --backend-store-uri ./mlruns --default-artifact-root ./mlruns
```

Set `MLFLOW_TRACKING_URI=http://127.0.0.1:5000` in `.env`.

## Experiments

| Experiment | Trigger | Contents |
|------------|---------|----------|
| `securevu-training` | `uv run --group mlops scripts/train_yolo.py` | Hyperparams, per-epoch metrics, test mAP, `best.pt` artifact |
| `securevu-deployment` | Server startup, rules/toggle/face-db changes, benchmarks | Env snapshot, model SHA256, `camera_rules.json` artifact |

## What is logged

### Environment parameters (allowlist)

Model and runtime: `MODEL_SELECT`, `MODEL_RUNTIME`, `YOLO_*`, `FACE_*`, `MOTION_*`, `LINGER_SECONDS`, `PROCESSING_FPS`, `WORK_*`, `BBOX_*`, `EVENT_CLIP_ENABLE`, `ANALYTICS_*`, etc.

See [`app/ml_tracking.py`](../app/ml_tracking.py) → `ML_CONFIG_KEYS`.

### Model fingerprints

SHA256 hashes for:

- Active YOLO weights (`.pt` or TensorRT `.engine`)
- `models/arcface/face_db/face_db.npz`
- `config/camera_rules.json`
- `config/runtime_flags.json`

### Redacted (never logged)

- `DB_PASS`, `JWT_SECRET`, account passwords
- Full RTSP URLs (host-only or `redacted`)

## When runs are created

| Event | MLflow source tag |
|-------|-------------------|
| Server starts | `server_startup` |
| `POST /rules` saves camera rules | `camera_rules` |
| Event clip toggle API | `event_clips_toggle` |
| Face enroll / delete | `face_enroll`, `face_enroll_frames`, `face_delete` |
| Benchmark script | `benchmark_poc`, `benchmark_balanced`, etc. |

Config drift vs the previous deployment is tagged as `changed_params` (comma-separated env keys).

## Training workflow

```bash
uv sync --group mlops
uv run --group mlops scripts/train_yolo.py
```

This logs a training run, uploads artifacts, and registers `securevu-person-detector` in the Model Registry when MLflow is reachable.

## Benchmark workflow

Compare POC vs balanced vs accuracy profiles:

```bash
uv run --group mlops scripts/benchmark_config.py --preset all
uv run --group mlops scripts/benchmark_config.py --profile yolo_conf=0.18,yolo_width=1280
```

Metrics include average CPU/RAM/GPU utilization and single-frame YOLO inference time per profile.

## Disabling tracking

Set in `.env`:

```dotenv
MLFLOW_ENABLE=0
```

The VMS server continues normally; no MLflow calls are made.

## Comparing runs after an env change

1. Note current run in MLflow UI under `securevu-deployment`.
2. Change `.env` (e.g. `YOLO_MIN_CONF=0.25`) and restart the server.
3. Open the new run — check tag `changed_params` and diff params against the previous run.

## Storage

- Docker: `./mlruns` volume (gitignored)
- Local drift cache: `tracking/last_deployment_snapshot.json`

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No runs appear | Confirm `MLFLOW_ENABLE=1` and tracking URI reachable |
| `mlflow not installed` | `uv sync --group mlops` |
| Registry errors | Ensure training run logged `weights/best.pt` artifact first |
| Server slow on boot | MLflow logging runs in a background thread; check MLflow server health |
