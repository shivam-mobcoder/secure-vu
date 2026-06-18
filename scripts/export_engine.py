#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

# Resolve root path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

def main():
    parser = argparse.ArgumentParser(description="Export YOLO PyTorch weights to TensorRT engine")
    parser.add_argument("--weights", type=str, default="models/yolo/secure_cv_best.pt", help="Path to input .pt weights")
    parser.add_argument("--imgsz", type=int, default=640, help="Export image resolution size")
    args = parser.parse_args()

    weights_path = Path(args.weights)
    if not weights_path.is_absolute():
        weights_path = REPO_ROOT / weights_path

    if not weights_path.exists():
        print(f"ERROR: Weights file not found at {weights_path}")
        sys.exit(1)

    print(f"Importing Ultralytics YOLO...")
    from ultralytics import YOLO

    print(f"Loading weights: {weights_path}")
    model = YOLO(str(weights_path))

    print(f"Exporting model to TensorRT format with options:")
    print(f"  - Format: engine")
    print(f"  - Precision: FP16 (half=True)")
    print(f"  - Dynamic Batch/Shapes: dynamic=True")
    print(f"  - Image size: {args.imgsz}")
    
    try:
        # Exporting to TensorRT (.engine)
        output_path = model.export(
            format="engine",
            imgsz=args.imgsz,
            half=True,
            dynamic=True,
            device=0
        )
        print(f"SUCCESS: Model exported successfully to {output_path}")
    except Exception as e:
        print(f"ERROR: Export failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
