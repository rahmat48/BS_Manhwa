import os
import sys
import glob
import time
import uuid
import shutil
import subprocess
import threading
from typing import Dict, Any, List, Optional
from PIL import Image
from app.power import acquire_anti_sleep, release_anti_sleep

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(BASE_DIR, "tools", "realesrgan")
REALESRGAN_EXE = os.path.join(TOOLS_DIR, "realesrgan-ncnn-vulkan.exe")
MODELS_DIR = os.path.join(TOOLS_DIR, "models")

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

# Tracking for enhancement jobs
enhancement_jobs: Dict[str, Dict[str, Any]] = {}
active_processes: Dict[str, subprocess.Popen] = {}
jobs_lock = threading.Lock()

def get_enhancer_status() -> Dict[str, Any]:
    return {
        "engine_installed": os.path.exists(REALESRGAN_EXE),
        "engine_path": REALESRGAN_EXE,
        "models": [
            {
                "id": "realesrgan-x4plus-anime",
                "label": "⚡ 2x Anime HD (1440p) - Rekomendasi Utama",
                "description": "Menajamkan garis komik & bersihkan kompresi, sangat pas untuk timeline video.",
                "scale": 2,
                "model_name": "realesrgan-x4plus-anime",
                "default": True
            },
            {
                "id": "realesrgan-x4plus-anime-4x",
                "label": "🔥 4x Anime Ultra (4K / 2880p)",
                "description": "Detail maksimal, sangat cocok untuk panel cover atau Thumbnail YouTube.",
                "scale": 4,
                "model_name": "realesrgan-x4plus-anime",
                "default": False
            },
            {
                "id": "realesr-animevideov3-2x",
                "label": "🚀 Fast Anime V3 (Mode Super Kencang)",
                "description": "Model paling ringan dan ngebut jika Anda memproses ratusan panel sekaligus.",
                "scale": 2,
                "model_name": "realesr-animevideov3",
                "default": False
            },
            {
                "id": "smart-polish",
                "label": "🪄 Smart Digital Polish (Instan / Non-AI)",
                "description": "Penajaman kontras & tepi digital cepat via OpenCV tanpa beban komputasi AI.",
                "scale": 1,
                "model_name": "smart-polish",
                "default": False
            }
        ]
    }

def format_time_hms(seconds: float) -> str:
    """Format durasi detik ke teks rapi (contoh: 1m 15s atau 14.2s)."""
    seconds = max(0.0, seconds)
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}j {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    else:
        return f"{seconds:.2f}s"

def make_progress_bar(pct: float, width: int = 20) -> str:
    """Membuat visual progress bar 1-100% gaya installer (contoh: [██████████░░░░░░░░░░]  50.0%)."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"

def scan_input_folders(folder_paths: List[str]) -> Dict[str, Any]:
    """
    Scans list of folders or directories, detecting all images
    and organizing them into structured folder groups, preserving full subfolder hierarchy.
    """
    detected_folders = []
    total_images = 0

    for raw_path in folder_paths:
        if not raw_path or not os.path.exists(raw_path):
            continue
        abs_p = os.path.abspath(raw_path)

        if os.path.isdir(abs_p):
            norm_p = os.path.normpath(abs_p)
            parts = norm_p.split(os.sep)
            rel_folder = ""
            if "enhance_uploads" in parts:
                idx = parts.index("enhance_uploads")
                # parts[idx+1] is the batch_id folder
                if len(parts) > idx + 2:
                    rel_folder = os.path.join(*parts[idx+2:])

            # 1. Check for direct images inside abs_p
            direct_images = []
            for entry in os.scandir(abs_p):
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        direct_images.append(entry.path)

            if direct_images:
                rel_path = rel_folder if rel_folder else os.path.basename(abs_p)
                display_name = rel_path.replace(os.sep, " / ")
                detected_folders.append({
                    "folder_name": display_name,
                    "rel_path": rel_path,
                    "folder_path": abs_p,
                    "images_count": len(direct_images),
                    "images": direct_images
                })
                total_images += len(direct_images)
            else:
                # 2. If no direct images, recursively walk to find any subfolders with images
                for root, dirs, files in os.walk(abs_p):
                    imgs = [os.path.join(root, f) for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
                    if imgs:
                        if rel_folder:
                            sub_rel = os.path.relpath(root, abs_p)
                            rel_path = os.path.join(rel_folder, sub_rel) if sub_rel != "." else rel_folder
                        else:
                            rel_path = os.path.relpath(root, os.path.dirname(abs_p))
                        display_name = rel_path.replace(os.sep, " / ")
                        detected_folders.append({
                            "folder_name": display_name,
                            "rel_path": rel_path,
                            "folder_path": os.path.abspath(root),
                            "images_count": len(imgs),
                            "images": imgs
                        })
                        total_images += len(imgs)

    return {
        "total_folders": len(detected_folders),
        "total_images": total_images,
        "folders": [
            {
                "folder_name": f["folder_name"],
                "rel_path": f.get("rel_path", f["folder_name"]),
                "folder_path": f["folder_path"],
                "images_count": f["images_count"]
            }
            for f in detected_folders
        ],
        "_raw_data": detected_folders
    }

def apply_smart_polish_opencv(in_path: str, out_path: str):
    """Fallback non-AI fast sharpening and contrast enhancement."""
    import cv2
    import numpy as np
    
    img = cv2.imread(in_path, cv2.IMREAD_COLOR)
    if img is None:
        shutil.copy2(in_path, out_path)
        return

    # Unsharp mask for crisp line-art
    gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
    unsharp = cv2.addWeighted(img, 1.35, gaussian, -0.35, 0)

    # Slight adaptive contrast on Luminance (LAB color space)
    lab = cv2.cvtColor(unsharp, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)

    cv2.imwrite(out_path, enhanced, [cv2.IMWRITE_PNG_COMPRESSION, 3])

def run_enhancement_process(
    job_id: str,
    folder_data: List[Dict[str, Any]],
    target_base_dir: str,
    model_name: str = "realesrgan-x4plus-anime",
    scale: int = 2
):
    job = enhancement_jobs[job_id]
    total_images_all = sum(f["images_count"] for f in folder_data)
    job["total_images"] = total_images_all
    job["status"] = "processing"
    job["progress"] = 1
    job["message"] = f"Menyiapkan GPU untuk memproses {total_images_all} gambar..."

    # Aktifkan proteksi sleep otomatis selama render berlangsung
    acquire_anti_sleep(f"enhance_{job_id}")

    # Ensure Vulkan ignores broken third-party layers like old AMD switchable graphics
    clean_env = os.environ.copy()
    clean_env["VK_LOADER_LAYERS_DISABLE"] = "~all~"

    processed_count = 0
    start_time = time.time()
    os.makedirs(target_base_dir, exist_ok=True)

    try:
        is_smart_polish = (model_name == "smart-polish")

        # Terminal banner log
        print("\n" + "=" * 70, flush=True)
        print(f"🚀 [ENHANCER STUDIO] Memulai Peningkatan Kualitas Gambar", flush=True)
        print(f"   • Total Folder : {len(folder_data)} folder", flush=True)
        print(f"   • Total Gambar : {total_images_all} gambar", flush=True)
        print(f"   • Model & Skala: {model_name} ({scale}x) | Akselerasi GPU Vulkan", flush=True)
        print(f"   • Folder Output: {os.path.abspath(target_base_dir)}", flush=True)
        print("=" * 70 + "\n", flush=True)

        for f_idx, f_info in enumerate(folder_data):
            folder_display = f_info.get("folder_name", "Folder")
            folder_rel = f_info.get("rel_path") or folder_display.replace(" / ", os.sep)
            in_folder_path = f_info["folder_path"]
            img_list = f_info.get("images", [])

            # Target directory mirrors the input subfolder structure cleanly!
            out_folder_path = os.path.join(target_base_dir, folder_rel)
            os.makedirs(out_folder_path, exist_ok=True)

            folder_start_time = time.time()
            print(f"\n📂 [{f_idx + 1}/{len(folder_data)}] Memproses Folder: {folder_display} ({len(img_list)} gambar)", flush=True)
            print("-" * 70, flush=True)

            job["current_folder"] = folder_display
            job["message"] = f"[{f_idx + 1}/{len(folder_data)}] Memproses {folder_display} ({len(img_list)} gambar)..."

            if is_smart_polish:
                for img_path in img_list:
                    if job.get("status") == "cancelled":
                        print("\n⏹️ [ENHANCER] Dibatalkan oleh pengguna.\n", flush=True)
                        return

                    fn = os.path.basename(img_path)
                    out_img_path = os.path.join(out_folder_path, fn)

                    img_num = processed_count + 1
                    t0 = time.time()

                    apply_smart_polish_opencv(img_path, out_img_path)

                    dur = max(0.01, time.time() - t0)
                    prog_bar = make_progress_bar(100.0, width=20)
                    print(f"   Img {img_num}/{total_images_all} ({fn}) : {prog_bar} | Selesai ({dur:.2f}s)", flush=True)

                    processed_count += 1
                    pct = int((processed_count / max(1, total_images_all)) * 100)
                    job["progress"] = pct
                    job["processed_images"] = processed_count
                    job["message"] = f"Memproses {folder_display}: {fn} ({processed_count}/{total_images_all})"

            else:
                # Real-ESRGAN NCNN Vulkan processing
                for img_path in img_list:
                    if job.get("status") == "cancelled":
                        print("\n⏹️ [ENHANCER] Dibatalkan oleh pengguna.\n", flush=True)
                        return

                    fn = os.path.basename(img_path)
                    name_part, ext_part = os.path.splitext(fn)
                    # Output PNG
                    out_fn = f"{name_part}.png"
                    out_img_path = os.path.join(out_folder_path, out_fn)

                    img_num = processed_count + 1
                    t0 = time.time()

                    cmd = [
                        REALESRGAN_EXE,
                        "-i", os.path.abspath(img_path),
                        "-o", os.path.abspath(out_img_path),
                        "-n", model_name,
                        "-s", str(scale),
                        "-g", "0"  # Dedicated GPU (GTX 1650)
                    ]

                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=clean_env,
                        text=True,
                        cwd=TOOLS_DIR
                    )

                    with jobs_lock:
                        active_processes[job_id] = proc

                    # Real-time monitoring of progress from stderr with live progress bar
                    for raw_line in iter(proc.stderr.readline, ''):
                        line = raw_line.strip()
                        if "%" in line:
                            try:
                                pct_val = float(line.replace("%", "").strip())
                                live_bar = make_progress_bar(pct_val, width=20)
                                sys.stdout.write(f"\r   Img {img_num}/{total_images_all} ({fn}) : {live_bar}")
                                sys.stdout.flush()
                            except ValueError:
                                pass

                    proc.wait()

                    with jobs_lock:
                        active_processes.pop(job_id, None)

                    dur = max(0.01, time.time() - t0)
                    done_bar = make_progress_bar(100.0, width=20)
                    sys.stdout.write(f"\r   Img {img_num}/{total_images_all} ({fn}) : {done_bar} | Selesai ({dur:.2f}s)\n")
                    sys.stdout.flush()

                    processed_count += 1
                    elapsed = max(0.1, time.time() - start_time)
                    speed = elapsed / max(1, processed_count)
                    remaining = (total_images_all - processed_count) * speed

                    pct = int((processed_count / max(1, total_images_all)) * 98)
                    job["progress"] = max(2, pct)
                    job["processed_images"] = processed_count
                    job["eta_seconds"] = int(remaining)
                    job["message"] = f"[{processed_count}/{total_images_all}] {folder_display} -> {out_fn} (~{int(remaining)}d lagi)"

            # Cetak rangkuman waktu untuk 1 folder yang baru selesai
            folder_duration = max(0.01, time.time() - folder_start_time)
            folder_avg = folder_duration / max(1, len(img_list))
            folder_time_str = format_time_hms(folder_duration)
            print("-" * 70, flush=True)
            print(f"📁 [FOLDER SELESAI] {folder_display}", flush=True)
            print(f"   • Jumlah Gambar : {len(img_list)} gambar", flush=True)
            print(f"   • Waktu Folder  : {folder_time_str} (~{folder_avg:.2f}s per gambar)", flush=True)
            print(f"   • Tersimpan di  : {os.path.abspath(out_folder_path)}", flush=True)
            print("-" * 70, flush=True)

        total_time = max(0.01, time.time() - start_time)
        total_avg = total_time / max(1, processed_count)
        total_time_str = format_time_hms(total_time)

        print("\n" + "=" * 70, flush=True)
        print(f"🎉 [SEMUA PROSES ENHANCER SELESAI]", flush=True)
        print(f"   • Total Folder      : {len(folder_data)} folder", flush=True)
        print(f"   • Total Gambar      : {processed_count}/{total_images_all} gambar", flush=True)
        print(f"   • Total Waktu Proses: {total_time_str} ({total_time:.2f} detik)", flush=True)
        print(f"   • Rata-rata/Gambar  : {total_avg:.2f} detik", flush=True)
        print(f"   • Lokasi Output     : {os.path.abspath(target_base_dir)}", flush=True)
        print("=" * 70 + "\n", flush=True)

        job["progress"] = 100
        job["status"] = "completed"
        job["processed_images"] = processed_count
        job["output_folder"] = target_base_dir
        job["total_duration_text"] = total_time_str
        job["message"] = f"Selesai! Berhasil meng-enhance {processed_count} gambar ke dalam {len(folder_data)} folder dalam {total_time_str}."

    except Exception as e:
        import traceback
        traceback.print_exc()
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = f"Terjadi kesalahan: {str(e)}"
    finally:
        release_anti_sleep(f"enhance_{job_id}")
        with jobs_lock:
            active_processes.pop(job_id, None)

# Auto sleep-lock protection on upscale tasks

# Output directory hierarchy preservation enabled

# Installer-style progress bar rendering enabled

# Per-folder and batch benchmark reporting enabled
