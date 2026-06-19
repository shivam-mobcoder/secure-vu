#!/usr/bin/env python3
"""
train_yolo.py — Fine-tune YOLOv11 on the Secure CV person-detection dataset.

Usage:
    uv run scripts/train_yolo.py

Output:
    - Best weights copied to models/yolo/secure_cv_best.pt
    - training_log.txt
    - MLflow run under securevu-training (if MLFLOW_ENABLE=1)
"""

import csv
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DATA_YAML = REPO_ROOT / "datasets" / "secure_cv_v4" / "data.yaml"
OUTPUT_DIR = REPO_ROOT / "runs" / "train"
FINAL_WEIGHTS_DIR = REPO_ROOT / "models" / "yolo"
LOG_FILE = REPO_ROOT / "training_log.txt"

BASE_MODEL = "yolo11m.pt"
EPOCHS = 100
IMGSZ = 640
BATCH_SIZE = 16
PATIENCE = 15
OPTIMIZER = "AdamW"
LR0 = 0.001
LRF = 0.01
MOMENTUM = 0.937
WEIGHT_DECAY = 0.0005
WARMUP_EPOCHS = 3
WARMUP_MOMENTUM = 0.8
HSV_H = 0.015
HSV_S = 0.7
HSV_V = 0.4
MOSAIC = 1.0
MIXUP = 0.1
FLIPUD = 0.0
FLIPLR = 0.5
DEGREES = 5.0
TRANSLATE = 0.1
SCALE = 0.5
SHEAR = 2.0
PERSPECTIVE = 0.0001
CLOSE_MOSAIC = 10
DEVICE = "0"
PROJECT_NAME = "secure_cv_training"

_log_lines: list[str] = []


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    _log_lines.append(line)


def flush_log() -> None:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(_log_lines) + "\n")
    log(f"Log written to {LOG_FILE}")


def _dataset_counts() -> dict[str, int]:
    counts = {}
    for split in ["train", "valid", "test"]:
        img_dir = REPO_ROOT / "datasets" / "secure_cv_v4" / split / "images"
        counts[split] = len(list(img_dir.glob("*"))) if img_dir.exists() else 0
    return counts


def _training_params(counts: dict[str, int]) -> dict:
    return {
        "base_model": BASE_MODEL,
        "epochs": EPOCHS,
        "imgsz": IMGSZ,
        "batch_size": BATCH_SIZE,
        "patience": PATIENCE,
        "optimizer": OPTIMIZER,
        "lr0": LR0,
        "lrf": LRF,
        "momentum": MOMENTUM,
        "weight_decay": WEIGHT_DECAY,
        "warmup_epochs": WARMUP_EPOCHS,
        "mosaic": MOSAIC,
        "mixup": MIXUP,
        "device": DEVICE,
        "train_images": counts.get("train", 0),
        "valid_images": counts.get("valid", 0),
        "test_images": counts.get("test", 0),
    }


def _log_epoch_metrics_from_csv(mlflow, results_csv: Path) -> None:
    if not results_csv.exists():
        return
    with open(results_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows):
        step = i + 1
        for key, val in row.items():
            key_clean = (key or "").strip()
            if not key_clean:
                continue
            try:
                mlflow.log_metric(key_clean, float(val), step=step)
            except (ValueError, TypeError):
                pass


def main() -> None:
    log("=" * 72)
    log("  SECURE CV — YOLO TRAINING SCRIPT")
    log("=" * 72)

    if not DATA_YAML.exists():
        log(f"Dataset YAML not found: {DATA_YAML}")
        sys.exit(1)

    counts = _dataset_counts()
    params = _training_params(counts)
    for k, v in params.items():
        log(f"  {k}: {v}")

    try:
        from ultralytics import YOLO
    except ImportError:
        log("ultralytics not installed")
        sys.exit(1)

    try:
        from app import ml_tracking
    except ImportError:
        ml_tracking = None  # type: ignore

    mlflow = ml_tracking._mlflow_client() if ml_tracking else None
    run_id = None
    run_ctx = None
    if mlflow:
        try:
            mlflow.set_experiment(ml_tracking.MLFLOW_EXPERIMENT_TRAINING)
            run_ctx = mlflow.start_run(
                run_name=f"secure_cv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            run_ctx.__enter__()
            for k, v in params.items():
                mlflow.log_param(k, v)
            for k, v in ml_tracking.get_git_metadata().items():
                mlflow.set_tag(k, v)
        except Exception as e:
            log(f"MLflow run start skipped: {e}")
            run_ctx = None

    log("Loading base model...")
    model = YOLO(BASE_MODEL)

    log("Starting training...")
    t0 = time.time()
    model.train(
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
        save_period=10,
        plots=True,
        val=True,
        verbose=True,
        seed=42,
        amp=True,
        cos_lr=True,
        workers=8,
    )
    elapsed = time.time() - t0
    log(f"Training completed in {elapsed / 60:.1f} minutes")

    train_dir = OUTPUT_DIR / PROJECT_NAME
    best_pt = train_dir / "weights" / "best.pt"
    results_csv = train_dir / "results.csv"

    if mlflow and run_ctx:
        try:
            _log_epoch_metrics_from_csv(mlflow, results_csv)
        except Exception as e:
            log(f"MLflow epoch metrics skipped: {e}")

    test_metrics = None
    if best_pt.exists():
        log("Running test validation...")
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
            log(f"  mAP50:     {test_metrics.box.map50:.4f}")
            log(f"  mAP50-95:  {test_metrics.box.map:.4f}")
            log(f"  Precision: {test_metrics.box.mp:.4f}")
            log(f"  Recall:    {test_metrics.box.mr:.4f}")
            if mlflow:
                mlflow.log_metric("test_mAP50", float(test_metrics.box.map50))
                mlflow.log_metric("test_mAP50-95", float(test_metrics.box.map))
                mlflow.log_metric("test_precision", float(test_metrics.box.mp))
                mlflow.log_metric("test_recall", float(test_metrics.box.mr))
        except Exception as e:
            log(f"Test validation failed: {e}")

    dest = FINAL_WEIGHTS_DIR / "secure_cv_best.pt"
    if best_pt.exists():
        FINAL_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            backup = FINAL_WEIGHTS_DIR / (
                f"secure_cv_best_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
            )
            shutil.copy2(dest, backup)
        shutil.copy2(best_pt, dest)
        log(f"Best weights copied to: {dest}")

    if mlflow and run_ctx:
        try:
            if best_pt.exists():
                mlflow.log_artifact(str(best_pt), artifact_path="weights")
            if results_csv.exists():
                mlflow.log_artifact(str(results_csv))
            if LOG_FILE.exists():
                mlflow.log_artifact(str(LOG_FILE))
            plots_dir = train_dir
            for plot in plots_dir.glob("*.png"):
                mlflow.log_artifact(str(plot))
            run_id = mlflow.active_run().info.run_id if mlflow.active_run() else None
        except Exception as e:
            log(f"MLflow artifacts skipped: {e}")
        try:
            run_ctx.__exit__(None, None, None)
        except Exception:
            pass

    if ml_tracking and dest.exists() and run_id:
        try:
            version = ml_tracking.register_yolo_model(
                dest, training_run_id=run_id, tags={"source": "training"}
            )
            if version:
                log(f"Model registry version: {version}")
        except Exception as e:
            log(f"Model registry skipped: {e}")

    flush_log()


if __name__ == "__main__":
    main()
