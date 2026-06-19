# SecureVu POC — 12-Minute Demo Script

**Freeze this script on Day 1.** Do not change camera roles or zone geometry during the POC week without updating this file.

## Camera roles

| Camera | Purpose | Rules enabled |
|--------|---------|---------------|
| **Cam 1** | Face recognition + zone intrusion + unknown person | `roi_intrusion`, `unknown_person` |
| **Cam 2** | Virtual line crossing | `virtual_lines` (demo line mid-frame) |
| **Cam 3** | Crowd limit | `max_people` (threshold: 2) |
| **Cam 4** | Loitering / dwell | `roi_intrusion` + loiter (30s) or `parking_rules` |

## Pre-demo checklist

- [ ] On branch `POC`; `.env` copied from `.env.example` with `RTSP_URL_1`–`RTSP_URL_4`
- [ ] `migrations/002_poc.sql` applied (alerts + recording tables)
- [ ] `models/yolo/secure_cv_best.pt` and `pre_trained/insightface/` present
- [ ] `certs/cert.pem` and `certs/key.pem` generated
- [ ] Two faces pre-enrolled (e.g. `Demo_User_A`, `Demo_User_B`)
- [ ] Frontend built: `cd frontend/superadmin-react && npm run build`
- [ ] Stack running: `docker compose up` **or** `uv run python app/server.py`
- [ ] Optional: MLflow UI at `http://localhost:5000` (`MLFLOW_ENABLE=1`)
- [ ] Backup MP4 clips in `event_clips/` if RTSP may fail

## Demo flow (~12 minutes)

### 1. Live feed (1 min)

Open **Admin → Live Feed** (`/admin/dashboard/live-feed`). Show 2–4 cameras in grid/focus view. Confirm green live badge and smooth video.

### 2. Known face (1 min)

**Cam 1:** Pre-enrolled person walks into frame. Name appears on bounding box within ~30s.

### 3. Unknown person (1 min)

**Cam 1:** Person not in face DB enters frame. Sidebar shows **Unknown Person Detected** with `UNKNOWN_PERSON_FIRST_SEEN`. Click clip if available.

### 4. Zone intrusion (1.5 min)

**Cam 1:** Person enters configured polygon (Zone 1). Alert: **Zone Intrusion** + playable event clip.

### 5. Virtual line cross (1.5 min)

**Cam 2:** Person crosses demo virtual line. Alert: line cross + clip.

### 6. Crowd limit (1 min)

**Cam 3:** Three or more people in frame (threshold 2). Alert: **Crowd Limit Exceeded**.

### 7. Loitering (1.5 min)

**Cam 4:** Person stays inside dwell zone for 30+ seconds. Alert: **Loitering Detected** + clip.

### 8. Motion alert (1 min, stretch)

Wave hand or move object in empty scene before person detection. Alert: **Motion Detected**.  
*Fallback:* If RTSP noise causes false positives, note in demo that motion threshold is tunable via `MOTION_THRESH`.

### 9. Face enrollment (2 min)

Open **Face Enrollment**. Enroll volunteer with 3–5 frames. Return to live feed; name appears within 30s.

### 10. Work timer (30 sec)

Point out timer text on person bounding box (e.g. `0:45`).

### 11. Technical checkbox (1 min)

- Refresh browser → recent alerts still visible in sidebar (Postgres persistence).
- Open **Playback** → show at least one 5-minute recording segment.
- Optional: camera health dots (online/stale/offline).

## Fallback if RTSP fails

1. Use pre-recorded clips from `event_clips/` directory.
2. Demo on 2 live cameras + 2 background analytics only.
3. Lower `YOLO_PROCESS_EVERY_N_FRAMES=2` if GPU overloaded.

## Env profile (4 cam, RTX 2080 Ti, max accuracy)

See `.env.example` — `MODEL_SELECT=6`, `YOLO_INPUT_*=1280`, `ANALYTICS_CAMERA_IDS=1,2,3,4`.
