import subprocess
import shutil
import cv2
import time
from typing import Dict, Any

_static_gpu_info = None
_last_query_time = 0.0
_last_live_stats = {
    "gpu_util_pct": 0,
    "vram_used_mb": 0,
    "vram_used_gb": 0.0,
    "vram_pct": 0,
    "temperature_c": None
}

def get_gpu_info() -> Dict[str, Any]:
    global _static_gpu_info, _last_query_time, _last_live_stats
    now = time.time()

    # 1. Query static info once if not loaded
    if _static_gpu_info is None:
        _static_gpu_info = {
            "available": False,
            "name": "CPU Only",
            "short_name": "CPU",
            "vram_mb": 0,
            "vram_gb": 0.0,
            "vram_text": "N/A",
            "driver_version": "N/A",
            "backend": "CPU (Multi-Threaded)",
            "opencl_available": False
        }

        if shutil.which("nvidia-smi"):
            try:
                cmd = "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
                if output:
                    line = output.splitlines()[0]
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        gpu_name, mem_str, driver = parts[0], parts[1], parts[2]
                        vram_mb = int(mem_str) if mem_str.isdigit() else 0
                        vram_gb = round(vram_mb / 1024, 1)
                        short_name = gpu_name.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
                        _static_gpu_info["available"] = True
                        _static_gpu_info["name"] = gpu_name
                        _static_gpu_info["short_name"] = short_name
                        _static_gpu_info["vram_mb"] = vram_mb
                        _static_gpu_info["vram_gb"] = vram_gb
                        _static_gpu_info["vram_text"] = f"{vram_gb} GB" if vram_gb >= 1 else f"{vram_mb} MB"
                        _static_gpu_info["driver_version"] = driver
                        _static_gpu_info["backend"] = "NVIDIA CUDA / Hardware Vectorized"
            except Exception:
                pass

        try:
            if cv2.ocl.haveOpenCL():
                _static_gpu_info["opencl_available"] = True
                if not _static_gpu_info["available"]:
                    dev = cv2.ocl.Device.getDefault()
                    _static_gpu_info["available"] = True
                    _static_gpu_info["name"] = dev.name()
                    _static_gpu_info["short_name"] = dev.name()
                    _static_gpu_info["backend"] = "OpenCL Hardware Accelerated"
        except Exception:
            pass

    # 2. Query dynamic live stats (throttled to at most once every 0.7s)
    if _static_gpu_info["available"] and (now - _last_query_time > 0.7):
        _last_query_time = now
        if shutil.which("nvidia-smi"):
            try:
                cmd = "nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader,nounits"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
                if output:
                    line = output.splitlines()[0]
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        util_str = parts[0]
                        used_str = parts[1]
                        temp_str = parts[2] if len(parts) >= 3 else None

                        util_pct = int(util_str) if util_str.isdigit() else 0
                        used_mb = int(used_str) if used_str.isdigit() else 0
                        total_mb = _static_gpu_info["vram_mb"]
                        vram_pct = int(round((used_mb / max(1, total_mb)) * 100))

                        _last_live_stats = {
                            "gpu_util_pct": util_pct,
                            "vram_used_mb": used_mb,
                            "vram_used_gb": round(used_mb / 1024, 2),
                            "vram_pct": vram_pct,
                            "temperature_c": int(temp_str) if (temp_str and temp_str.isdigit()) else None
                        }
            except Exception:
                pass

    used_gb = _last_live_stats.get("vram_used_gb", 0.0)
    total_gb = _static_gpu_info.get("vram_gb", 4.0)

    return {
        **_static_gpu_info,
        **_last_live_stats,
        "vram_used_text": f"{used_gb:.1f} / {total_gb} GB"
    }

# Real-time GPU metrics and NVML engine active
