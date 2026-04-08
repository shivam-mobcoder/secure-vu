#!/usr/bin/env python3
"""
Real-time resource stats collector for the CCTV AI pipeline.

Samples CPU, RAM, GPU utilization, VRAM, GPU temperature, and power draw
every N seconds, writing results to a timestamped CSV and printing a
live summary to the console.

Usage:
    python scripts/collect_stats.py [--duration 120] [--interval 2] [--output stats.csv]
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    print("ERROR: psutil is required. Install with: pip install psutil")
    sys.exit(1)


def nvidia_smi_query() -> dict:
    """Query nvidia-smi for GPU metrics."""
    defaults = {
        "gpu_util": "N/A",
        "gpu_mem_used_mb": "N/A",
        "gpu_mem_total_mb": "N/A",
        "gpu_temp_c": "N/A",
        "gpu_power_w": "N/A",
        "gpu_power_limit_w": "N/A",
        "gpu_clock_mhz": "N/A",
        "gpu_mem_clock_mhz": "N/A",
    }
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu="
                "utilization.gpu,"
                "memory.used,memory.total,"
                "temperature.gpu,"
                "power.draw,power.limit,"
                "clocks.current.graphics,clocks.current.memory",
                "--format=csv,noheader,nounits",
            ],
            encoding="utf-8",
            stderr=subprocess.STDOUT,
        ).strip()
        parts = [x.strip() for x in out.split("\n")[0].split(",")]
        if len(parts) >= 8:
            return {
                "gpu_util": parts[0],
                "gpu_mem_used_mb": parts[1],
                "gpu_mem_total_mb": parts[2],
                "gpu_temp_c": parts[3],
                "gpu_power_w": parts[4],
                "gpu_power_limit_w": parts[5],
                "gpu_clock_mhz": parts[6],
                "gpu_mem_clock_mhz": parts[7],
            }
    except Exception:
        pass
    return defaults


def sample() -> dict:
    """Collect one sample of all resource metrics."""
    mem = psutil.virtual_memory()
    gpu = nvidia_smi_query()
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_cores_active": psutil.cpu_count(logical=True),
        "ram_used_mb": round(mem.used / (1024 ** 2)),
        "ram_total_mb": round(mem.total / (1024 ** 2)),
        "ram_percent": mem.percent,
        **gpu,
    }


def pretty_print(s: dict, elapsed: float, duration: float) -> None:
    """Print a single sample in a readable format."""
    bar_len = 30
    pct = min(elapsed / duration, 1.0) if duration > 0 else 0
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)

    print(f"\r{'=' * 72}")
    print(
        f"  ⏱  [{bar}] {elapsed:.0f}s / {duration:.0f}s"
    )
    print(
        f"  🖥  CPU: {s['cpu_percent']:>5.1f}%   |   "
        f"RAM: {s['ram_used_mb']}MB / {s['ram_total_mb']}MB ({s['ram_percent']}%)"
    )
    print(
        f"  🎮  GPU: {s['gpu_util']:>3}%    |   "
        f"VRAM: {s['gpu_mem_used_mb']}MB / {s['gpu_mem_total_mb']}MB"
    )
    print(
        f"  🌡  Temp: {s['gpu_temp_c']}°C   |   "
        f"Power: {s['gpu_power_w']}W / {s['gpu_power_limit_w']}W"
    )
    print(
        f"  ⚡ GPU Clock: {s['gpu_clock_mhz']}MHz   |   "
        f"Mem Clock: {s['gpu_mem_clock_mhz']}MHz"
    )
    print(f"{'=' * 72}\n")


def compute_summary(rows: list[dict]) -> dict:
    """Compute average/max/min for numeric columns."""
    numeric_keys = [
        "cpu_percent", "ram_used_mb", "ram_percent",
        "gpu_util", "gpu_mem_used_mb", "gpu_temp_c", "gpu_power_w",
    ]
    summary = {}
    for key in numeric_keys:
        vals = []
        for r in rows:
            try:
                vals.append(float(r[key]))
            except (ValueError, TypeError):
                pass
        if vals:
            summary[key] = {
                "avg": round(sum(vals) / len(vals), 1),
                "min": round(min(vals), 1),
                "max": round(max(vals), 1),
            }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Collect AI pipeline resource stats")
    parser.add_argument("--duration", type=int, default=120, help="Collection duration in seconds (default: 120)")
    parser.add_argument("--interval", type=float, default=2.0, help="Sampling interval in seconds (default: 2)")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path (default: auto-named)")
    args = parser.parse_args()

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"stats_{ts}.csv"

    output_path = Path(args.output)

    print(f"\n🔬 Resource Stats Collector")
    print(f"   Duration: {args.duration}s | Interval: {args.interval}s | Output: {output_path}")
    print(f"   Collecting {int(args.duration / args.interval)} samples...\n")

    rows: list[dict] = []
    fieldnames = None
    start = time.monotonic()

    try:
        while (time.monotonic() - start) < args.duration:
            elapsed = time.monotonic() - start
            s = sample()
            rows.append(s)
            pretty_print(s, elapsed, args.duration)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n⏹  Stopped early by user.")

    if not rows:
        print("No data collected.")
        return

    # Write CSV
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n📊 Saved {len(rows)} samples to {output_path}")

    # Print summary
    summary = compute_summary(rows)
    print(f"\n{'=' * 60}")
    print(f"  📋 SUMMARY ({len(rows)} samples over {args.duration}s)")
    print(f"{'=' * 60}")
    for key, stats in summary.items():
        label = key.replace("_", " ").title()
        print(f"  {label:.<30} avg={stats['avg']:<8} min={stats['min']:<8} max={stats['max']}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
