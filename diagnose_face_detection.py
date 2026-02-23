#!/usr/bin/env python3
"""
Diagnostic script to check why Shivam isn't being detected in live feed.
"""
import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "app"))

print("\n" + "="*70)
print("🔍 FACE RECOGNITION DIAGNOSTIC")
print("="*70)

# 1. Check environment variables
print("\n1️⃣ Environment Variables:")
face_enable = os.getenv("FACE_ENABLE", "1").strip() == "1"
face_every_n = int(os.getenv("FACE_EVERY_N_FRAMES", "5"))
print(f"   FACE_ENABLE: {face_enable} {'✅' if face_enable else '❌'}")
print(f"   FACE_EVERY_N_FRAMES: {face_every_n} (process every {face_every_n} frames)")

# 2. Check database
print("\n2️⃣ Face Database:")
db_path = Path("models/arcface/face_db/face_db.npz")
if db_path.exists():
    import numpy as np
    data = np.load(db_path, allow_pickle=True)
    labels = data["labels"]
    unique_faces = set(labels)
    print(f"   ✅ Database exists: {db_path}")
    print(f"   📊 Total embeddings: {len(labels)}")
    print(f"   👥 Identities: {unique_faces}")
    
    shivam_count = sum(1 for l in labels if l == 'Shivam')
    print(f"   👤 Shivam embeddings: {shivam_count}")
    if shivam_count == 0:
        print(f"      ⚠️ ISSUE: Shivam not in database!")
else:
    print(f"   ❌ Database not found: {db_path}")
    sys.exit(1)

# 3. Check FaceIDManager
print("\n3️⃣ FaceIDManager:")
try:
    from app.faceid import FaceIDManager
    faceid = FaceIDManager(db_path=db_path, threshold=0.3, ctx_id=-1)
    print(f"   ✅ FaceIDManager initialized")
    print(f"   ✅ Face app loaded: {faceid.app is not None}")
    print(f"   ✅ Embeddings loaded: {faceid.embeddings is not None}")
    print(f"   ✅ Threshold: {faceid.threshold}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# 4. Check issue: Only largest person gets recognized
print("\n4️⃣ Recognition Strategy:")
print(f"   ⚠️  Only the LARGEST detected person gets face recognition!")
print(f"   💡 If Shivam is smaller/further from camera, won't be recognized")
print(f"   🔧 Solution: Modify code to check ALL people or reduce threshold")

# 5. Recommendations
print("\n5️⃣ Recommendations:")
print(f"   1. Lower threshold from 0.3 to 0.25-0.2 (if embeddings are good)")
print(f"   2. Run face recognition on TOP N people (not just #1)")
print(f"   3. Check YOLO_MIN_CONF - might be too strict")
print(f"   4. Verify camera is capturing people correctly")
print(f"   5. Check /api/face/recognition-logs for actual detections")

print("\n" + "="*70 + "\n")
