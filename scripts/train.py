#!/usr/bin/env python3
import argparse
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Train a CCTV-optimized YOLO11 model")
    parser.add_argument("--model", type=str, default="yolo11x.pt", help="Pretrained weights (yolo11m.pt, yolo11l.pt, yolo11x.pt)")
    parser.add_argument("--data", type=str, default="config/cctv_person.yaml", help="Path to data.yaml")
    parser.add_argument("--epochs", type=int, default=150, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=8, help="Batch size (reduce to 4 or 8 if OOM occurs on 11GB VRAM)")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size")
    parser.add_argument("--device", type=str, default="0", help="CUDA device index (e.g. 0)")
    args = parser.parse_args()

    print(f"Loading pretrained weights: {args.model}")
    model = YOLO(args.model)

    print("Starting YOLO training pipeline with CCTV optimizations...")
    # Training configuration customized for RTX 2080 Ti (11GB) VRAM limits
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        
        # Optimization settings
        optimizer="AdamW",
        lr0=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        amp=True,                # Mixed precision (saves ~40% VRAM, speeds up RTX 2080 Ti)
        accumulate=2,            # Gradient accumulation (simulates batch=16 with batch=8)
        cache=False,             # Disable image caching in RAM/VRAM to prevent OOM
        workers=8,               # DataLoader worker threads
        
        # Augmentations designed for CCTV person detection (density, occlusion, scaling)
        mosaic=1.0,              # Combine 4 images into one to learn context
        mixup=0.15,              # Blend images to handle dense scenes
        copy_paste=0.30,         # Copy segmentations to new backgrounds
        scale=0.5,               # Multi-scale zooming for small/distant targets
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,               # Jitter brightness/saturation for low-light/IR
        fliplr=0.5,              # Horizontal mirror flip
        
        # Close mosaic during the final epochs to stabilize bounding boxes
        close_mosaic=15,         # Disable mosaic augmentation during final 15 epochs
        
        # Validation
        val=True,
        save=True,
        project="runs/detect",
        name="cctv_person_model"
    )
    print("Training run completed successfully.")

if __name__ == "__main__":
    main()
