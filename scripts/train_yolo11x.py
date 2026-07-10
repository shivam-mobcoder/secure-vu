#!/usr/bin/env python3
"""
train_yolo11x.py — Fine-tune YOLO11x on secure_cv_v4 for maximum person-detection accuracy.

Usage:
    cd object-detection-main
    uv run scripts/train_yolo11x.py

Output:
    - Best weights copied to models/yolo/secure_cv_best_x.pt
    - Log written to training_log_11x.txt
"""

import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = REPO_ROOT / "datasets" / "secure_cv_v4" / "data.yaml"
OUTPUT_DIR = REPO_ROOT / "runs" / "train"
FINAL_WEIGHTS = REPO_ROOT / "models" / "yolo" / "secure_cv_best_x.pt"
LOG_FILE = REPO_ROOT / "training_log_11x.txt"

# RTX 2080 Ti (11 GB) — 11x @ 960 batch 2; falls back to 640 if OOM
BASE_MODEL = "yolo11x.pt"
EPOCHS = 150
IMGSZ = 960
BATCH_SIZE = 4
PATIENCE = 20
PROJECT_NAME = "secure_cv_training_11x"


def log(msg: str, lines: list) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    lines.append(line)


def run_train(imgsz: int, batch: int, log_lines: list):
    from ultralytics import YOLO

    log(f"Loading base model: {BASE_MODEL} (auto-downloads if missing)", log_lines)
    model = YOLO(BASE_MODEL)

    log(f"Training @ imgsz={imgsz}, batch={batch}", log_lines)
    return model.train(
        data=str(DATA_YAML),
        epochs=EPOCHS,
        imgsz=imgsz,
        batch=batch,
        patience=PATIENCE,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        mosaic=1.0,
        mixup=0.15,
        copy_paste=0.3,
        scale=0.5,
        fliplr=0.5,
        close_mosaic=15,
        device="0",
        project=str(OUTPUT_DIR),
        name=PROJECT_NAME,
        exist_ok=True,
        save=True,
        save_period=10,
        plots=True,
        val=True,
        verbose=True,
        seed=42,
        amp=True,
        cos_lr=True,
        workers=8,
        cache=False,
    )


def main():
    log_lines: list[str] = []
    log("=" * 72, log_lines)
    log("  SECURE CV — YOLO11x TRAINING (max accuracy)", log_lines)
    log("=" * 72, log_lines)

    if not DATA_YAML.exists():
        log(f"Dataset not found: {DATA_YAML}", log_lines)
        sys.exit(1)

    for split in ("train", "valid", "test"):
        img_dir = REPO_ROOT / "datasets" / "secure_cv_v4" / split / "images"
        count = len(list(img_dir.glob("*"))) if img_dir.exists() else 0
        log(f"  {split:>6s}: {count} images", log_lines)

    t0 = time.time()
    try:
        run_train(IMGSZ, BATCH_SIZE, log_lines)
    except Exception as e:
        if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
            log(f"OOM at {IMGSZ}px — retrying at 640px batch=4", log_lines)
            try:
                run_train(640, 4, log_lines)
            except Exception as e2:
                log(f"Training failed: {e2}", log_lines)
                LOG_FILE.write_text("\n".join(log_lines) + "\n")
                sys.exit(1)
        else:
            log(f"Training failed: {e}", log_lines)
            LOG_FILE.write_text("\n".join(log_lines) + "\n")
            sys.exit(1)

    elapsed = time.time() - t0
    h, rem = divmod(int(elapsed), 3600)
    m, s = divmod(rem, 60)
    log(f"Training finished in {h}h {m}m {s}s", log_lines)

    best_pt = OUTPUT_DIR / PROJECT_NAME / "weights" / "best.pt"
    if not best_pt.exists():
        log("best.pt not found", log_lines)
        LOG_FILE.write_text("\n".join(log_lines) + "\n")
        sys.exit(1)

    FINAL_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    if FINAL_WEIGHTS.exists():
        backup = FINAL_WEIGHTS.with_name(
            f"secure_cv_best_x_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
        )
        shutil.copy2(FINAL_WEIGHTS, backup)
        log(f"Backed up previous weights to {backup.name}", log_lines)

    shutil.copy2(best_pt, FINAL_WEIGHTS)
    log(f"Best weights saved to {FINAL_WEIGHTS}", log_lines)
    log("Next: uv run scripts/export_engine.py --weights models/yolo/secure_cv_best_x.pt --imgsz 960", log_lines)
    log("Then set MODEL_SELECT=10 in .env and restart the server.", log_lines)

    LOG_FILE.write_text("\n".join(log_lines) + "\n")
    print(f"\nLog: {LOG_FILE}")


if __name__ == "__main__":
    main()
