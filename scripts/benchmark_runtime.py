#!/usr/bin/env python3
import time
import torch
import os
import sys
from pathlib import Path

# Resolve root path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))

from ultralytics import YOLO

def get_gpu_info():
    """Query nvidia-smi for current GPU memory and utilization."""
    try:
        import subprocess
        cmd = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
        output = subprocess.check_output(cmd, shell=True).decode().strip().split(",")
        gpu_util = f"{output[0].strip()}%"
        gpu_mem = f"{output[1].strip()}/{output[2].strip()} MB"
        return gpu_util, gpu_mem
    except Exception:
        return "N/A", "N/A"

def run_benchmark(model_path, is_engine=False, num_runs=200, warmup=20):
    print(f"\n🚀 Initializing benchmark for: {os.path.basename(model_path)}")
    
    # Measure memory before loading
    gpu_util_before, gpu_mem_before = get_gpu_info()
    
    # Load model
    t_start_load = time.time()
    model = YOLO(model_path)
    if not is_engine:
        model.to("cuda:0")
        try:
            model.fuse()
        except Exception:
            pass
        try:
            model.model.half()
        except Exception:
            pass
    # Force loading weights to GPU
    dummy_input = torch.zeros(1, 3, 640, 640, device="cuda:0")
    if is_engine:
        # For TensorRT, run one prediction to initialize context
        _ = model.predict(dummy_input, verbose=False)
    else:
        with torch.amp.autocast('cuda', enabled=True):
            _ = model(dummy_input, verbose=False)
            
    t_end_load = time.time()
    load_time_sec = t_end_load - t_start_load
    print(f"Loaded in {load_time_sec:.2f}s")
    
    # Measure memory after loading
    gpu_util_loaded, gpu_mem_loaded = get_gpu_info()
    
    # Warmup
    print("Running warmup...")
    for _ in range(warmup):
        if is_engine:
            _ = model.predict(dummy_input, verbose=False)
        else:
            with torch.amp.autocast('cuda', enabled=True):
                _ = model(dummy_input, verbose=False)
    torch.cuda.synchronize()
    
    # Benchmark runs
    print(f"Running benchmark ({num_runs} iterations)...")
    t0 = time.time()
    for _ in range(num_runs):
        if is_engine:
            _ = model.predict(dummy_input, verbose=False)
        else:
            with torch.amp.autocast('cuda', enabled=True):
                _ = model(dummy_input, verbose=False)
    torch.cuda.synchronize()
    t1 = time.time()
    
    total_time_ms = (t1 - t0) * 1000.0
    avg_inference_ms = total_time_ms / num_runs
    fps = num_runs / (t1 - t0)
    
    # Measure memory during load
    gpu_util_running, gpu_mem_running = get_gpu_info()
    
    # Clean up model
    del model
    torch.cuda.empty_cache()
    
    return {
        "avg_ms": avg_inference_ms,
        "fps": fps,
        "mem_loaded": gpu_mem_loaded,
        "util_running": gpu_util_running
    }

def main():
    pt_path = str(REPO_ROOT / "models" / "yolo" / "secure_cv_best.pt")
    engine_path = str(REPO_ROOT / "models" / "yolo" / "secure_cv_best.engine")
    
    print("=== SecureVU YOLO Runtime Benchmark ===")
    
    # PyTorch Benchmark
    pt_stats = None
    if os.path.exists(pt_path):
        pt_stats = run_benchmark(pt_path, is_engine=False)
    else:
        print(f"PyTorch weights not found at {pt_path}")
        
    # TensorRT Benchmark
    trt_stats = None
    if os.path.exists(engine_path):
        trt_stats = run_benchmark(engine_path, is_engine=True)
    else:
        print(f"\nTensorRT engine not found at {engine_path}. Please run scripts/export_engine.py first.")
        
    # Print comparison table
    print("\n" + "="*50)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*50)
    print(f"{'Metric':<20} | {'PyTorch FP16':<15} | {'TensorRT FP16':<15}")
    print("-"*56)
    
    if pt_stats and trt_stats:
        print(f"{'Inference (ms)':<20} | {pt_stats['avg_ms']:<15.2f} | {trt_stats['avg_ms']:<15.2f}")
        print(f"{'FPS':<20} | {pt_stats['fps']:<15.2f} | {trt_stats['fps']:<15.2f}")
        print(f"{'GPU Memory':<20} | {pt_stats['mem_loaded']:<15} | {trt_stats['mem_loaded']:<15}")
        print(f"{'GPU Utilization':<20} | {pt_stats['util_running']:<15} | {trt_stats['util_running']:<15}")
    else:
        if pt_stats:
            print(f"{'Inference (ms)':<20} | {pt_stats['avg_ms']:<15.2f} | {'N/A':<15}")
            print(f"{'FPS':<20} | {pt_stats['fps']:<15.2f} | {'N/A':<15}")
            print(f"{'GPU Memory':<20} | {pt_stats['mem_loaded']:<15} | {'N/A':<15}")
            print(f"{'GPU Utilization':<20} | {pt_stats['util_running']:<15} | {'N/A':<15}")
            
    print("="*50)

if __name__ == "__main__":
    main()
