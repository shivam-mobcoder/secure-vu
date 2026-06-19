# SecureVU CCTV — Integration Guide for RTSP Streams

This guide covers RTSP configuration for the SecureVu **POC** branch (`app/server.py`).

## 1. Configure cameras in `.env`

Set one URL per camera (main stream `subtype=0` for higher quality; sub-stream `subtype=1` for lower bandwidth):

```dotenv
RTSP_URL_1=rtsp://user:pass@192.168.1.101:554/cam/realmonitor?channel=1&subtype=0
RTSP_URL_2=rtsp://user:pass@192.168.1.102:554/cam/realmonitor?channel=1&subtype=0
RTSP_URL_3=rtsp://user:pass@192.168.1.103:554/cam/realmonitor?channel=1&subtype=0
RTSP_URL_4=rtsp://user:pass@192.168.1.104:554/cam/realmonitor?channel=1&subtype=0

ANALYTICS_ALL_CCTV=1
ANALYTICS_CAMERA_IDS=1,2,3,4
```

Credentials in `.env` are **not** logged to MLflow (redacted in `app/ml_tracking.py`).

## 2. How the server opens streams

The monolith uses `SharedServerCamera` with OpenCV FFmpeg (`RTSP_USE_PYAV=0` by default). URLs are read from `RTSP_URL_*` env vars — no code changes required when switching from webcam to CCTV.

Tuning (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `RTSP_RETRY_DELAY_SEC` | Reconnect delay after read failure |
| `RTSP_OPEN_TIMEOUT_MS` | Open timeout |
| `PROCESSING_FPS` | Analytics processing rate per camera |

## 3. Sub-stream vs main-stream

| Stream | Typical use |
|--------|-------------|
| `subtype=1` (sub) | Lower bandwidth, smoother on congested LAN |
| `subtype=0` (main) | Higher resolution; use with `YOLO_INPUT_WIDTH/HEIGHT=1280` POC profile |

For the 4-camera POC on RTX 2080 Ti, main-stream at 1280 YOLO input is documented in [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

## 4. Per-camera rules

Zone, line, and crowd rules are in [`config/camera_rules.json`](../config/camera_rules.json). Edit via Admin UI or `POST /rules`. Changes are tracked in MLflow when enabled (see [MLFLOW.md](MLFLOW.md)).

## 5. Health check

```bash
curl -k -H "Authorization: Bearer <jwt>" https://localhost:8000/api/cameras/health
```

Returns `online` / `stale` / `offline` per camera based on last frame timestamp from the capture thread.

## 6. Troubleshooting

- **No video:** Verify RTSP URL in VLC first; check firewall and camera user permissions.
- **Stale health:** Increase `RTSP_RETRY_DELAY_SEC`; confirm camera supports TCP (`OPENCV_FFMPEG_CAPTURE_OPTIONS` uses `rtsp_transport;tcp` in `server.py`).
- **GPU overload:** Raise `YOLO_PROCESS_EVERY_N_FRAMES` or lower `YOLO_INPUT_WIDTH/HEIGHT`.

See [DEPLOYMENT_GUIDE_SUMMARY.md](DEPLOYMENT_GUIDE_SUMMARY.md) for network sizing and [root README](../README.md) for full setup.
