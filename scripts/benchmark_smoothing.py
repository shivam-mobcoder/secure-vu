#!/usr/bin/env python3
import numpy as np
import time
import os
import sys
from pathlib import Path

# Resolve root path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from app.bbox_smoother import BBoxSmoother

def generate_trajectory(n_frames=300):
    """Generate ground truth trajectory with added noise and varying confidence."""
    np.random.seed(42)
    
    # Ground truth: person walking diagonally
    gt_boxes = []
    x1, y1 = 100.0, 100.0
    w, h = 50.0, 120.0
    
    for i in range(n_frames):
        # Walk 1.5 pixels per frame
        x1 += 1.5
        y1 += 0.8
        gt_boxes.append((x1, y1, x1 + w, y1 + h))
        
    # Add noise & confidence
    noisy_boxes = []
    confidences = []
    
    for i, box in enumerate(gt_boxes):
        # First 100 frames: High confidence (0.90), low noise (std=0.5px)
        if i < 100:
            conf = 0.90
            noise_std = 0.5
        # Middle 100 frames: Medium confidence (0.70), medium noise (std=2.0px)
        elif i < 200:
            conf = 0.70
            noise_std = 2.0
        # Last 100 frames: Low confidence (0.50), high noise/jitter (std=6.0px)
        else:
            conf = 0.50
            noise_std = 6.0
            
        noise = np.random.normal(0, noise_std, 4)
        noisy_box = (
            box[0] + noise[0],
            box[1] + noise[1],
            box[2] + noise[2],
            box[3] + noise[3]
        )
        noisy_boxes.append(noisy_box)
        confidences.append(conf)
        
    return gt_boxes, noisy_boxes, confidences

def benchmark_smoother(smoother, noisy_boxes, confidences):
    smoothed_boxes = []
    prev_box = None
    
    t0 = time.perf_counter()
    for box, conf in zip(noisy_boxes, confidences):
        if prev_box is None:
            prev_box = box
            smoothed_boxes.append(box)
            continue
            
        smoothed = smoother.smooth(prev_box, box, conf)
        smoothed_boxes.append(smoothed)
        prev_box = smoothed
    t1 = time.perf_counter()
    
    latency_us = ((t1 - t0) * 1e6) / len(noisy_boxes)
    
    # Calculate statistics
    displacements = []
    for i in range(1, len(smoothed_boxes)):
        p = smoothed_boxes[i-1]
        c = smoothed_boxes[i]
        # Box shift is L2 distance between center points
        p_cx, p_cy = (p[0]+p[2])*0.5, (p[1]+p[3])*0.5
        c_cx, c_cy = (c[0]+c[2])*0.5, (c[1]+c[3])*0.5
        dist = np.sqrt((c_cx - p_cx)**2 + (c_cy - p_cy)**2)
        displacements.append(dist)
        
    avg_movement = np.mean(displacements)
    p95_movement = np.percentile(displacements, 95)
    
    return smoothed_boxes, latency_us, avg_movement, p95_movement

def main():
    print("=== SecureVU Bounding Box Smoothing Benchmark ===")
    
    gt, noisy, confs = generate_trajectory()
    
    # Raw Noisy Stats
    raw_displacements = []
    for i in range(1, len(noisy)):
        p, c = noisy[i-1], noisy[i]
        p_cx, p_cy = (p[0]+p[2])*0.5, (p[1]+p[3])*0.5
        c_cx, c_cy = (c[0]+c[2])*0.5, (c[1]+c[3])*0.5
        raw_displacements.append(np.sqrt((c_cx - p_cx)**2 + (c_cy - p_cy)**2))
    
    # 1. Fixed Mode (Legacy baseline)
    fixed_smoother = BBoxSmoother(
        mode="fixed",
        fixed_alpha=0.75
    )
    
    # 2. Adaptive Mode (New proposal)
    adaptive_smoother = BBoxSmoother(
        mode="adaptive",
        alpha_high=0.30,      # High conf: less smoothing, low lag (responsive)
        alpha_medium=0.55,    # Mid conf: standard
        alpha_low=0.80,       # Low conf: strong smoothing (stops jitter)
        conf_high=0.85,
        conf_medium=0.60
    )
    
    _, fixed_lat, fixed_avg, fixed_p95 = benchmark_smoother(fixed_smoother, noisy, confs)
    _, adapt_lat, adapt_avg, adapt_p95 = benchmark_smoother(adaptive_smoother, noisy, confs)
    
    # Separate metrics by confidence segments
    # Segment 1: High confidence (frames 0-100)
    _, _, fixed_avg_h, fixed_p95_h = benchmark_smoother(fixed_smoother, noisy[:100], confs[:100])
    _, _, adapt_avg_h, adapt_p95_h = benchmark_smoother(adaptive_smoother, noisy[:100], confs[:100])
    
    # Segment 3: Low confidence (frames 200-300)
    _, _, fixed_avg_l, fixed_p95_l = benchmark_smoother(fixed_smoother, noisy[200:300], confs[200:300])
    _, _, adapt_avg_l, adapt_p95_l = benchmark_smoother(adaptive_smoother, noisy[200:300], confs[200:300])
    
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"{'Metric':<30} | {'Fixed Mode (0.75)':<15} | {'Adaptive Mode':<15}")
    print("-"*66)
    print(f"{'Inference Latency/Box (us)':<30} | {fixed_lat:<15.4f} | {adapt_lat:<15.4f}")
    print(f"{'Overall Avg Box Movement (px)':<30} | {fixed_avg:<15.4f} | {adapt_avg:<15.4f}")
    print(f"{'Overall 95th% Movement (px)':<30} | {fixed_p95:<15.4f} | {adapt_p95:<15.4f}")
    print("-"*66)
    print(f"{'High-Conf Avg Movement (px)':<30} | {fixed_avg_h:<15.4f} | {adapt_avg_h:<15.4f}")
    print(f"{'High-Conf 95th% Movement (px)':<30} | {fixed_p95_h:<15.4f} | {adapt_p95_h:<15.4f}")
    print("-"*66)
    print(f"{'Low-Conf Avg Movement (px)':<30} | {fixed_avg_l:<15.4f} | {adapt_avg_l:<15.4f}")
    print(f"{'Low-Conf 95th% Movement (px)':<30} | {fixed_p95_l:<15.4f} | {adapt_p95_l:<15.4f}")
    print("="*60)
    print("\n💡 Note:")
    print(" - High confidence: Adaptive (alpha=0.30) allows fast tracking adjustments with less delay.")
    print(" - Low confidence: Adaptive (alpha=0.80) aggressively smooths out random detection jitter.")

if __name__ == "__main__":
    main()
