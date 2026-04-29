from ultralytics import YOLO
import cv2
import supervision as sv
import numpy as np

# ========================= CONFIG =========================
DEBUG = True                    # False kar do agar silent chahiye
CONF_THRESHOLD = 0.3            # Slightly lower for better detection in varying light
# =======================================================

# Load model
model = YOLO("yolo26n.pt")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# Actual resolution check
actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
print(f"📷 Actual Resolution: {actual_w}x{actual_h}")

# Virtual restricted zone (red box)
zone_polygon = np.array([[400, 200], [900, 200], [900, 500], [400, 500]])
zone = sv.PolygonZone(
    polygon=zone_polygon,
    triggering_anchors=[sv.Position.CENTER]
)

# NOTE: zone is required during initialization in this version of supervision
zone_annotator = sv.PolygonZoneAnnotator(
    zone=zone, 
    thickness=3, 
    color=sv.Color.RED
)

box_annotator = sv.BoxAnnotator(thickness=2)
label_annotator = sv.LabelAnnotator()

print("🎥 Secure VU Test Started! Red box cross kar ke dekh...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run YOLO
    results = model(frame, conf=CONF_THRESHOLD, verbose=False)[0]
    detections = sv.Detections.from_ultralytics(results)

    # 🔥 PERSON ONLY FILTER
    if len(detections) > 0:
        person_mask = detections.class_id == 0
        detections = detections[person_mask]

    # Zone check
    mask = zone.trigger(detections=detections)
    in_zone_count = np.sum(mask)

    # Clean Debug
    if DEBUG and len(detections) > 0:
        print(f"DEBUG: {len(detections)} person(s) detected. In zone: {in_zone_count}")
    
    if in_zone_count > 0:
        print("🚨 INTRUSION DETECTED! Boundary crossed!")

    # Draw everything
    annotated_frame = box_annotator.annotate(scene=frame, detections=detections)
    annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections)
    annotated_frame = zone_annotator.annotate(scene=annotated_frame)

    cv2.imshow("Secure VU Test - YOLO26-n (Final Clean)", annotated_frame)

    if cv2.waitKey(1) & 0xFF == 27:  # Esc to quit
        break

cap.release()
cv2.destroyAllWindows()