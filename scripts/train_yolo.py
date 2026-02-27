#!/usr/bin/env python3
"""
train_yolo.py — Fine-tune YOLOv11 on the Secure CV person-detection dataset.

Usage:
    cd /home/mobcoder/Downloads/object-detection-main
    uv run scripts/train_yolo.py

Output:
    - Best weights are automatically copied to models/yolo/secure_cv_best.pt
    - A detailed training log is written to training_log.txt
"""

import os
import sys
import time
import shutil
import json
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = REPO_ROOT / "datasets" / "secure_cv_v4" / "data.yaml"
OUTPUT_DIR = REPO_ROOT / "runs" / "train"
FINAL_WEIGHTS_DIR = REPO_ROOT / "models" / "yolo"
LOG_FILE = REPO_ROOT / "training_log.txt"

# ── Hyper-parameters ───────────────────────────────────────────────────────────
# Use the YOLOv11 medium model as base (good balance of speed and accuracy)
BASE_MODEL  = "yolo11m.pt"  # Ultralytics will auto-download if not present
EPOCHS      = 100            # Max epochs (early stopping may kick in sooner)
IMGSZ       = 640            # Training resolution
BATCH_SIZE  = 16             # Adjust down if OOM
PATIENCE    = 15             # Early stopping patience
OPTIMIZER   = "AdamW"        # Optimizer
LR0         = 0.001          # Initial learning rate
LRF         = 0.01           # Final learning rate (fraction of lr0)
MOMENTUM    = 0.937
WEIGHT_DECAY= 0.0005
WARMUP_EPOCHS = 3
WARMUP_MOMENTUM = 0.8
HSV_H       = 0.015          # Hue augmentation
HSV_S       = 0.7            # Saturation augmentation
HSV_V       = 0.4            # Value (brightness) augmentation
MOSAIC      = 1.0            # Mosaic augmentation probability
MIXUP       = 0.1            # MixUp augmentation probability
FLIPUD      = 0.0            # Vertical flip
FLIPLR      = 0.5            # Horizontal flip
DEGREES     = 5.0            # Rotation degrees
TRANSLATE   = 0.1            # Translation fraction
SCALE       = 0.5            # Scale augmentation
SHEAR       = 2.0            # Shear degrees
PERSPECTIVE = 0.0001         # Perspective augmentation
CLOSE_MOSAIC = 10            # Disable mosaic for last N epochs
DEVICE      = "0"            # GPU 0
PROJECT_NAME = "secure_cv_training"

# ── Logging helpers ────────────────────────────────────────────────────────────
_log_lines = []

def log(msg: str):
    """Print and buffer a log line."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    _log_lines.append(line)


def flush_log():
    """Write all buffered log lines to disk."""
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(_log_lines) + "\n")
    log(f"📄 Log written to {LOG_FILE}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    log("=" * 72)
    log("  SECURE CV — YOLO TRAINING SCRIPT")
    log("=" * 72)
    log("")

    # Verify dataset
    if not DATA_YAML.exists():
        log(f"❌ Dataset YAML not found: {DATA_YAML}")
        sys.exit(1)
    log(f"📂 Dataset:      {DATA_YAML}")
    log(f"🧠 Base model:   {BASE_MODEL}")
    log(f"📐 Image size:   {IMGSZ}px")
    log(f"📦 Batch size:   {BATCH_SIZE}")
    log(f"🔁 Max epochs:   {EPOCHS}")
    log(f"⏱  Patience:     {PATIENCE}")
    log(f"🎯 Optimizer:    {OPTIMIZER}")
    log(f"📈 Learning rate: {LR0} → {LR0 * LRF}")
    log(f"💻 Device:       cuda:{DEVICE}")
    log("")

    # Count images
    for split in ["train", "valid", "test"]:
        img_dir = REPO_ROOT / "datasets" / "secure_cv_v4" / split / "images"
        count = len(list(img_dir.glob("*"))) if img_dir.exists() else 0
        log(f"  {split:>6s}: {count} images")
    log("")

    # Import YOLO
    try:
        from ultralytics import YOLO
    except ImportError:
        log("❌ ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    # Load model
    log(f"🔄 Loading base model: {BASE_MODEL} ...")
    model = YOLO(BASE_MODEL)
    log("✅ Model loaded")
    log("")

    # ── Train ──────────────────────────────────────────────────────────────
    log("🚀 Starting training...")
    t0 = time.time()

    results = model.train(
        data=str(DATA_YAML),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH_SIZE,
        patience=PATIENCE,
        optimizer=OPTIMIZER,
        lr0=LR0,
        lrf=LRF,
        momentum=MOMENTUM,
        weight_decay=WEIGHT_DECAY,
        warmup_epochs=WARMUP_EPOCHS,
        warmup_momentum=WARMUP_MOMENTUM,
        hsv_h=HSV_H,
        hsv_s=HSV_S,
        hsv_v=HSV_V,
        mosaic=MOSAIC,
        mixup=MIXUP,
        flipud=FLIPUD,
        fliplr=FLIPLR,
        degrees=DEGREES,
        translate=TRANSLATE,
        scale=SCALE,
        shear=SHEAR,
        perspective=PERSPECTIVE,
        close_mosaic=CLOSE_MOSAIC,
        device=DEVICE,
        project=str(OUTPUT_DIR),
        name=PROJECT_NAME,
        exist_ok=True,
        save=True,
        save_period=10,           # Checkpoint every 10 epochs
        plots=True,               # Generate training plots
        val=True,                 # Validate after each epoch
        verbose=True,
        seed=42,
        amp=True,                 # Mixed precision
        cos_lr=True,              # Cosine LR schedule
        workers=8,
    )

    elapsed = time.time() - t0
    hours = int(elapsed // 3600)
    mins  = int((elapsed % 3600) // 60)
    secs  = int(elapsed % 60)
    log(f"")
    log(f"✅ Training completed in {hours}h {mins}m {secs}s")
    log("")

    # ── Results summary ────────────────────────────────────────────────────
    log("=" * 72)
    log("  TRAINING RESULTS")
    log("=" * 72)

    # Find the best weights
    train_dir = OUTPUT_DIR / PROJECT_NAME
    best_pt = train_dir / "weights" / "best.pt"
    last_pt = train_dir / "weights" / "last.pt"

    if best_pt.exists():
        log(f"🏆 Best weights: {best_pt} ({best_pt.stat().st_size / 1e6:.1f} MB)")
    else:
        log("⚠️  best.pt not found")
    if last_pt.exists():
        log(f"📌 Last weights: {last_pt} ({last_pt.stat().st_size / 1e6:.1f} MB)")

    # Parse results CSV if available
    results_csv = train_dir / "results.csv"
    if results_csv.exists():
        log("")
        log("📊 Final epoch metrics (from results.csv):")
        import csv
        with open(results_csv) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if rows:
            last = rows[-1]
            for k, v in last.items():
                k_clean = k.strip()
                try:
                    v_num = float(v)
                    log(f"  {k_clean:>40s}: {v_num:.6f}")
                except (ValueError, TypeError):
                    log(f"  {k_clean:>40s}: {v}")

    log("")

    # ── Validate on test set ───────────────────────────────────────────────
    log("🧪 Running validation on test set...")
    try:
        test_model = YOLO(str(best_pt))
        test_metrics = test_model.val(
            data=str(DATA_YAML),
            split="test",
            imgsz=IMGSZ,
            device=DEVICE,
            plots=True,
            save_json=True,
        )
        log(f"  mAP50:      {test_metrics.box.map50:.4f}")
        log(f"  mAP50-95:   {test_metrics.box.map:.4f}")
        log(f"  Precision:  {test_metrics.box.mp:.4f}")
        log(f"  Recall:     {test_metrics.box.mr:.4f}")
    except Exception as e:
        log(f"⚠️  Test validation failed: {e}")

    log("")

    # ── Copy best weights to models/yolo/ ──────────────────────────────────
    if best_pt.exists():
        dest = FINAL_WEIGHTS_DIR / "secure_cv_best.pt"
        FINAL_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        # Backup old weights
        if dest.exists():
            backup = FINAL_WEIGHTS_DIR / f"secure_cv_best_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
            shutil.copy2(dest, backup)
            log(f"🔒 Old weights backed up to: {backup.name}")
        shutil.copy2(best_pt, dest)
        log(f"✅ Best weights copied to: {dest}")
    else:
        log("⚠️  No best.pt to copy")

    log("")
    log("=" * 72)
    log("  TRAINING COMPLETE")
    log("=" * 72)

    # Flush log to file
    flush_log()
    print(f"\n📄 Full training log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()
