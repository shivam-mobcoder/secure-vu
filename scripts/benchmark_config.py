#!/usr/bin/env python3
"""
Benchmark detection config profiles and log results to MLflow.

Usage:
    uv run --group mlops scripts/benchmark_config.py --preset poc
    uv run --group mlops scripts/benchmark_config.py --preset all
    uv run --group mlops scripts/benchmark_config.py --profile yolo_conf=0.18,yolo_width=1280
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PRESETS: dict[str, dict[str, str]] = {
    "poc": {
        "YOLO_MIN_CONF": "0.18",
        "YOLO_INPUT_WIDTH": "1280",
        "YOLO_INPUT_HEIGHT": "1280",
        "FACE_RECOGNITION_THRESHOLD": "0.25",
        "FACE_EVERY_N_FRAMES": "3",
        "PROCESSING_FPS": "15",
        "MODEL_SELECT": "6",
        "MODEL_RUNTIME": "pytorch",
    },
    "balanced": {
        "YOLO_MIN_CONF": "0.25",
        "YOLO_INPUT_WIDTH": "640",
        "YOLO_INPUT_HEIGHT": "640",
        "FACE_RECOGNITION_THRESHOLD": "0.30",
        "FACE_EVERY_N_FRAMES": "5",
        "PROCESSING_FPS": "20",
        "MODEL_SELECT": "6",
        "MODEL_RUNTIME": "pytorch",
    },
    "accuracy": {
        "YOLO_MIN_CONF": "0.15",
        "YOLO_INPUT_WIDTH": "1280",
        "YOLO_INPUT_HEIGHT": "1280",
        "FACE_RECOGNITION_THRESHOLD": "0.22",
        "FACE_EVERY_N_FRAMES": "1",
        "PROCESSING_FPS": "10",
        "MODEL_SELECT": "6",
        "MODEL_RUNTIME": "pytorch",
    },
}


def _parse_profile_string(raw: str) -> dict[str, str]:
    mapping = {
        "yolo_conf": "YOLO_MIN_CONF",
        "yolo_width": "YOLO_INPUT_WIDTH",
        "yolo_height": "YOLO_INPUT_HEIGHT",
        "face_thresh": "FACE_RECOGNITION_THRESHOLD",
        "face_every": "FACE_EVERY_N_FRAMES",
        "processing_fps": "PROCESSING_FPS",
    }
    out: dict[str, str] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip()
        env_key = mapping.get(key, key.upper())
        out[env_key] = val.strip()
    return out


def _sample_system_stats(duration: float = 10.0, interval: float = 2.0) -> dict[str, float]:
    try:
        import psutil
    except ImportError:
        return {"avg_cpu_percent": 0.0, "avg_ram_percent": 0.0}

    import subprocess

    def _gpu_util() -> float:
        try:
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
            ).strip()
            return float(out.split("\n")[0])
        except Exception:
            return 0.0

    cpu_vals: list[float] = []
    ram_vals: list[float] = []
    gpu_vals: list[float] = []
    end = time.time() + duration
    while time.time() < end:
        cpu_vals.append(float(psutil.cpu_percent(interval=0.1)))
        ram_vals.append(float(psutil.virtual_memory().percent))
        gpu_vals.append(_gpu_util())
        time.sleep(interval)

    metrics = {
        "avg_cpu_percent": sum(cpu_vals) / len(cpu_vals) if cpu_vals else 0.0,
        "avg_ram_percent": sum(ram_vals) / len(ram_vals) if ram_vals else 0.0,
    }
    if gpu_vals:
        metrics["avg_gpu_util"] = sum(gpu_vals) / len(gpu_vals)
    return metrics


def _benchmark_yolo_inference(profile: dict[str, str]) -> dict[str, float]:
    weights = REPO_ROOT / "models" / "yolo" / "secure_cv_best.pt"
    if not weights.exists():
        return {"yolo_inference_ms": -1.0}

    try:
        import numpy as np
        import torch
        from ultralytics import YOLO
    except ImportError:
        return {"yolo_inference_ms": -1.0}

    w = int(profile.get("YOLO_INPUT_WIDTH", "640"))
    h = int(profile.get("YOLO_INPUT_HEIGHT", "640"))
    conf = float(profile.get("YOLO_MIN_CONF", "0.25"))
    model = YOLO(str(weights))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    dummy = np.zeros((h, w, 3), dtype=np.uint8)

    # Warmup
    for _ in range(2):
        model(dummy, imgsz=max(w, h), verbose=False, conf=conf)

    times: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        model(dummy, imgsz=max(w, h), verbose=False, conf=conf)
        times.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = sum(times) / len(times)
    return {
        "yolo_inference_ms": avg_ms,
        "estimated_yolo_fps": 1000.0 / avg_ms if avg_ms > 0 else 0.0,
    }


def run_profile(name: str, profile: dict[str, str], duration: float) -> None:
    from app import ml_tracking

    saved_env: dict[str, str | None] = {}
    for key, val in profile.items():
        saved_env[key] = os.environ.get(key)
        os.environ[key] = val

    try:
        yolo_metrics = _benchmark_yolo_inference(profile)
        sys_metrics = _sample_system_stats(duration=duration)
        metrics = {**yolo_metrics, **sys_metrics}
        run_id = ml_tracking.log_deployment_run(
            source=f"benchmark_{name}",
            extra_params={"benchmark_profile": name, **profile},
            metrics=metrics,
        )
        print(f"Profile '{name}' logged (run={run_id}): {metrics}")
    finally:
        for key, old in saved_env.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark SecureVu config profiles")
    parser.add_argument(
        "--preset",
        choices=["poc", "balanced", "accuracy", "all"],
        default="poc",
        help="Named profile preset(s)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="",
        help="Custom profile e.g. yolo_conf=0.18,yolo_width=1280",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="System sampling duration per profile (seconds)",
    )
    args = parser.parse_args()

    profiles: dict[str, dict[str, str]] = {}
    if args.profile:
        profiles["custom"] = _parse_profile_string(args.profile)
    elif args.preset == "all":
        profiles = dict(PRESETS)
    else:
        profiles[args.preset] = PRESETS[args.preset]

    for name, profile in profiles.items():
        run_profile(name, profile, args.duration)


if __name__ == "__main__":
    main()
