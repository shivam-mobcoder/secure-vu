from ultralytics import YOLO
import cv2
import supervision as sv
import numpy as np
import os
import threading
import time

# ========================= CONFIG =========================
RTSP_URLS = {
    1: "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=1&subtype=1",
    2: "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=2&subtype=1",
    3: "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=3&subtype=1",
    4: "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=4&subtype=1",
}

MODEL_PATH = "yolo26n.pt" 
# Fallback search path
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = "models/yolo/yolo26n.pt"

CONF_THRESHOLD = 0.20
GRID_SIZE = (640, 360) # Size per camera tile in display
# ==========================================================

class CameraStream:
    def __init__(self, cam_id, url, model):
        self.cam_id = cam_id
        self.url = url
        self.model = model
        self.cap = cv2.VideoCapture()
        self.frame = np.zeros((GRID_SIZE[1], GRID_SIZE[0], 3), dtype=np.uint8)
        self.running = False
        self.box_annotator = sv.BoxAnnotator(thickness=1)
        self.label_annotator = sv.LabelAnnotator()

    def start(self):
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.open(self.url, cv2.CAP_FFMPEG)
        if self.cap.isOpened():
            self.running = True
            threading.Thread(target=self.update, daemon=True).start()
            print(f"✅ Camera {self.cam_id} started.")
        else:
            print(f"❌ Camera {self.cam_id} failed to open.")

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            
            # Inference
            results = self.model(frame, imgsz=640, conf=CONF_THRESHOLD, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = detections[detections.class_id == 0]

            # Annotate
            annotated = self.box_annotator.annotate(scene=frame, detections=detections)
            annotated = self.label_annotator.annotate(scene=annotated, detections=detections)
            
            # Resize for grid
            self.frame = cv2.resize(annotated, GRID_SIZE)

    def stop(self):
        self.running = False
        self.cap.release()

def run_grid_test():
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Error: Model not found.")
        return

    model = YOLO(MODEL_PATH)
    streams = []

    for cam_id, url in RTSP_URLS.items():
        s = CameraStream(cam_id, url, model)
        s.start()
        streams.append(s)

    print("🎥 4-Camera Grid Test Started. Press 'ESC' to quit.")

    while True:
        # Create 2x2 grid
        row1 = np.hstack((streams[0].frame, streams[1].frame))
        row2 = np.hstack((streams[2].frame, streams[3].frame))
        grid = np.vstack((row1, row2))

        cv2.imshow("SecureVU 4-Camera Monitor", grid)

        if cv2.waitKey(1) & 0xFF == 27:
            break

    for s in streams:
        s.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_grid_test()
