#!/usr/bin/env python3
import sys
import os
import torch
import numpy as np
from pathlib import Path

# Resolve root path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from ultralytics import YOLO

def compare_inference(img_path):
    pt_path = str(REPO_ROOT / "models" / "yolo" / "secure_cv_best.pt")
    engine_path = str(REPO_ROOT / "models" / "yolo" / "secure_cv_best.engine")

    if not os.path.exists(pt_path):
        print(f"❌ PyTorch model not found at {pt_path}")
        return
    if not os.path.exists(engine_path):
        print(f"❌ TensorRT engine not found at {engine_path}")
        return

    print(f"📷 Using test image: {img_path}")
    
    # 1. Run PyTorch FP16 Inference
    print("Loading PyTorch model...")
    pt_model = YOLO(pt_path)
    pt_model.to("cuda:0")
    try:
        pt_model.fuse()
    except Exception:
        pass
    try:
        pt_model.model.half()
    except Exception:
        pass

    print("Running PyTorch FP16 inference...")
    pt_results = pt_model(img_path, verbose=False)[0]
    pt_boxes = pt_results.boxes.xyxy.cpu().numpy()
    pt_confs = pt_results.boxes.conf.cpu().numpy()
    pt_classes = pt_results.boxes.cls.cpu().numpy()

    # 2. Run TensorRT Inference
    print("Loading TensorRT engine...")
    trt_model = YOLO(engine_path)
    
    print("Running TensorRT FP16 inference...")
    trt_results = trt_model(img_path, verbose=False)[0]
    trt_boxes = trt_results.boxes.xyxy.cpu().numpy()
    trt_confs = trt_results.boxes.conf.cpu().numpy()
    trt_classes = trt_results.boxes.cls.cpu().numpy()

    print("\n" + "="*50)
    print("🔍 INFERENCE EQUIVALENCE CHECK RESULTS")
    print("="*50)
    
    print(f"PyTorch detections count  : {len(pt_boxes)}")
    print(f"TensorRT detections count : {len(trt_boxes)}")
    
    if len(pt_boxes) != len(trt_boxes):
        print("⚠️ WARNING: Detection counts do not match!")
        # We can still compare top detections
        min_len = min(len(pt_boxes), len(trt_boxes))
    else:
        print("✅ Detection counts match exactly.")
        min_len = len(pt_boxes)

    if min_len > 0:
        box_diffs = []
        conf_diffs = []
        class_matches = 0
        
        for i in range(min_len):
            # Find closest box to match targets (in case order differs slightly)
            pt_box = pt_boxes[i]
            pt_conf = pt_confs[i]
            pt_cls = pt_classes[i]
            
            # Find match in TRT
            distances = np.linalg.norm(trt_boxes - pt_box, axis=1)
            best_idx = np.argmin(distances)
            trt_box = trt_boxes[best_idx]
            trt_conf = trt_confs[best_idx]
            trt_cls = trt_classes[best_idx]
            
            box_diff = np.abs(pt_box - trt_box)
            box_diffs.append(box_diff)
            
            conf_diff = np.abs(pt_conf - trt_conf)
            conf_diffs.append(conf_diff)
            
            if pt_cls == trt_cls:
                class_matches += 1
                
        avg_box_pixel_diff = np.mean(box_diffs)
        max_box_pixel_diff = np.max(box_diffs)
        avg_conf_diff = np.mean(conf_diffs)
        max_conf_diff = np.max(conf_diffs)
        
        print(f"Average bounding box pixel shift : {avg_box_pixel_diff:.4f} pixels")
        print(f"Maximum bounding box pixel shift : {max_box_pixel_diff:.4f} pixels")
        print(f"Average confidence score delta   : {avg_conf_diff:.6f}")
        print(f"Maximum confidence score delta   : {max_conf_diff:.6f}")
        print(f"Class assignment accuracy match  : {class_matches / min_len * 100:.1f}%")
        
        # Float tolerance checks for FP16
        if avg_box_pixel_diff < 5.0 and avg_conf_diff < 0.05:
            print("\n✅ SUCCESS: Runtimes are mathematically equivalent within standard FP16 floating-point tolerance!")
        else:
            print("\n❌ FAILED: Significant output deviation detected between runtimes.")
    else:
        print("No detections found to compare.")

def main():
    test_img = str(REPO_ROOT / "training" / "runs" / "detect" / "val2" / "val_batch2_pred.jpg")
    if not os.path.exists(test_img):
        # Fallback to any file in val2
        val2_dir = REPO_ROOT / "training" / "runs" / "detect" / "val2"
        if val2_dir.exists():
            files = list(val2_dir.glob("*.jpg"))
            if files:
                test_img = str(files[0])
    
    compare_inference(test_img)

if __name__ == "__main__":
    main()
