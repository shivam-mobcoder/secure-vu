# SecureVU CCTV — Integration Guide for RTSP Streams

Respected Sir,

For our upcoming tests on the actual CCTV feeds (instead of the local webcam), please find the integrated RTSP credentials and the necessary code adjustments below.

### 1. RTSP Stream URLs
These are the sub-streams (optimized for AI detection speed) currently active on the SecureVU server:

*   **Camera 1**: `rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=1&subtype=1`
*   **Camera 2**: `rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=2&subtype=1`
*   **Camera 3**: `rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=3&subtype=1`
*   **Camera 4**: `rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=4&subtype=1`

---

### 2. Implementation Steps
To switch from your current webcam script to these feeds, please update the `cv2.VideoCapture` section in your code as follows:

```python
import cv2

# --- UPDATED CCTV INITIALIZATION ---
# Pick any URL from the list above
CCTV_URL = "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=1&subtype=1"

# We use the FFMPEG backend and a minimal buffer for real-time low-latency performance
cap = cv2.VideoCapture()
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Keeps the feed from lagging behind
cap.open(CCTV_URL, cv2.CAP_FFMPEG)

if not cap.isOpened():
    print("Error: Could not connect to the CCTV stream. Please check network connectivity.")
# ------------------------------------
```

### 3. Technical Notes
*   **Sub-stream (`subtype=1`)**: I have configured these URLs to use the sub-stream specifically. This provides a smoother 20-30 FPS for AI models compared to the high-bandwidth main-stream, which can sometimes cause network jitter.
*   **Nano Model Optimization**: For these CCTV angles, the `yolo26n.pt` model performs best when the input resolution is kept at `640px` and the confidence threshold is around `0.20`.

Please let me know if you face any connectivity issues while testing.

Best regards,
SecureVU Team
