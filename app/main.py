import os
import io
import uuid
import zipfile
import shutil
import asyncio
import threading
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image

from app.scraper import (
    fetch_chapter_info,
    fetch_shinigami_chapter_by_id,
    detect_manga_series,
    is_shinigami_url,
    HEADERS
)
from app.gpu import get_gpu_info
from app.slicer import process_and_slice_chapter
from app.enhancer import (
    get_enhancer_status,
    scan_input_folders,
    run_enhancement_process,
    enhancement_jobs,
    active_processes
)
from app.power import (
    acquire_anti_sleep,
    release_anti_sleep,
    toggle_anti_sleep,
    get_anti_sleep_status
)
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMP_DIR = os.path.join(BASE_DIR, "temp_jobs")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="BS Manhwa Recap Slicer")

# Filter out frequent polling logs from terminal output so it stays clean
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(endpoint in msg for endpoint in (
            "/api/cache-info",
            "/api/status/",
            "/api/enhancer/status/",
            "/api/gpu-info",
            "/api/default-folders",
            "/api/anti-sleep/status"
        ))

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# High-concurrency thread pool for GPU/CPU acceleration
executor = ThreadPoolExecutor(max_workers=8)

# In-memory jobs tracking
jobs: Dict[str, Dict[str, Any]] = {}

def calculate_cache_size() -> Dict[str, Any]:
    total_size = 0
    total_files = 0
    total_jobs = 0

    if os.path.exists(TEMP_DIR):
        for entry in os.scandir(TEMP_DIR):
            if entry.is_dir():
                total_jobs += 1
                for root, dirs, files in os.walk(entry.path):
                    for f in files:
                        try:
                            total_size += os.path.getsize(os.path.join(root, f))
                            total_files += 1
                        except OSError:
                            pass

    size_mb = round(total_size / (1024 * 1024), 2)
    size_text = f"{size_mb} MB" if size_mb < 1024 else f"{round(size_mb / 1024, 2)} GB"
    return {
        "size_bytes": total_size,
        "size_mb": size_mb,
        "size_text": size_text,
        "total_jobs": total_jobs,
        "total_files": total_files
    }

def clear_all_cache(keep_job_id: Optional[str] = None) -> Dict[str, Any]:
    initial = calculate_cache_size()
    deleted_jobs = 0

    if os.path.exists(TEMP_DIR):
        for entry in os.scandir(TEMP_DIR):
            if entry.is_dir():
                if keep_job_id and entry.name == keep_job_id:
                    continue
                try:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    deleted_jobs += 1
                except Exception:
                    pass

    # Clean in-memory jobs dict
    keys_to_remove = [k for k in list(jobs.keys()) if k != keep_job_id]
    for k in keys_to_remove:
        jobs.pop(k, None)

    after = calculate_cache_size()
    freed_mb = round(initial["size_mb"] - after["size_mb"], 2)
    return {
        "freed_mb": max(0, freed_mb),
        "deleted_jobs": deleted_jobs,
        "current_cache": after
    }

class DetectRequest(BaseModel):
    url: str

class ProcessBatchRequest(BaseModel):
    url: str
    start_chapter: Optional[float] = None
    end_chapter: Optional[float] = None
    max_parallel_chapters: Optional[int] = 5
    use_gpu: bool = True
    filter_banners: bool = True
    filter_speech_bubbles: bool = True
    split_long_panels: bool = True
    auto_clean_old_cache: bool = True
    target_folder: Optional[str] = None
    auto_export_folder: bool = False
    max_panel_height: int = 2500
    gutter_min_height: int = 25

class CreateFolderRequest(BaseModel):
    parent_path: str
    folder_name: str

class ExportFolderRequest(BaseModel):
    target_folder: Optional[str] = None
    filenames: Optional[List[str]] = None
    open_after: bool = True

class OpenFolderRequest(BaseModel):
    path: str

class DownloadZipRequest(BaseModel):
    filenames: Optional[List[str]] = None

class EnhanceScanRequest(BaseModel):
    folder_paths: List[str]

class EnhanceStartRequest(BaseModel):
    folder_paths: List[str]
    target_folder: Optional[str] = None
    model_name: str = "realesrgan-x4plus-anime"
    scale: int = 2
    open_folder_after: bool = True

def get_system_drives() -> List[str]:
    drives = []
    import string
    if os.name == 'nt':
        for letter in string.ascii_uppercase:
            d = f"{letter}:\\"
            if os.path.exists(d):
                drives.append(d)
    else:
        drives = ["/"]
    return drives

def download_images_parallel(img_urls: List[str], max_workers: int = 8) -> List[Image.Image]:
    """Downloads images in parallel using thread pool."""
    results = [None] * len(img_urls)
    session = requests.Session()
    session.headers.update(HEADERS)

    def _fetch_one(idx: int, u: str):
        try:
            r = session.get(u, timeout=25)
            if r.status_code == 200:
                im = Image.open(io.BytesIO(r.content)).convert('RGB')
                results[idx] = im
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pool.map(lambda item: _fetch_one(item[0], item[1]), enumerate(img_urls))

    return [im for im in results if im is not None]

def run_batch_job(job_id: str, req: ProcessBatchRequest):
    acquire_anti_sleep(f"slice_{job_id}")
    job = jobs[job_id]
    job_dir = os.path.join(TEMP_DIR, job_id)
    panels_base_dir = os.path.join(job_dir, "panels")
    thumbs_base_dir = os.path.join(job_dir, "thumbs")

    try:
        gpu_info = get_gpu_info()
        gpu_text = f"[{gpu_info['name']}]" if req.use_gpu and gpu_info['available'] else "[CPU Multi-Thread]"
        job["status"] = "processing"
        job["progress"] = 5
        job["message"] = f"Mendeteksi informasi chapter... {gpu_text}"

        # 1. Detect series & chapters to process
        target_chapters = []
        manga_title = "Manhwa Chapter"
        warning_msg = None

        if is_shinigami_url(req.url):
            series_info = detect_manga_series(req.url)
            manga_title = series_info.get("manga_title", "Manhwa")
            all_chs = series_info.get("chapters", [])

            s_num = req.start_chapter if req.start_chapter is not None else series_info.get("current_chapter", 1)
            e_num = req.end_chapter if req.end_chapter is not None else s_num

            # Ensure proper order
            if s_num > e_num:
                s_num, e_num = e_num, s_num

            max_avail_num = series_info.get("max_chapter")
            if req.end_chapter is not None and max_avail_num is not None and req.end_chapter > max_avail_num:
                warning_msg = f"Chapter {int(req.end_chapter)} belum tersedia di website! Chapter paling baru saat ini adalah Chapter {int(max_avail_num)}."

            for ch in all_chs:
                num = ch.get("chapter_number")
                if num is not None and s_num <= num <= e_num:
                    target_chapters.append(ch)

            if not target_chapters and all_chs:
                target_chapters = [all_chs[0]]

        if not target_chapters:
            # Generic single chapter
            info = fetch_chapter_info(req.url)
            manga_title = info.get("title", "Manhwa Chapter")
            target_chapters = [{
                "chapter_number": info.get("chapter_number", 1),
                "chapter_id": info.get("chapter_id", "ch_1"),
                "image_urls": info.get("image_urls", []),
                "chapter_title": info.get("title", "")
            }]

        job["title"] = manga_title
        total_chs = len(target_chapters)
        job["total_chapters"] = total_chs

        # Dynamic parallel workers:
        # User requested: max 5 concurrent workers, following the number of chapters chosen (e.g. 2 ch -> 2 workers, 5 ch -> 5 workers, 10 ch -> 5 workers)
        max_cap = req.max_parallel_chapters if (req.max_parallel_chapters and 1 <= req.max_parallel_chapters <= 5) else 5
        parallel_workers = min(max_cap, max(1, total_chs))

        job["progress"] = 8
        job["message"] = f"Menyiapkan {parallel_workers} worker paralel untuk {total_chs} episode {gpu_text}..."

        progress_lock = threading.Lock()
        chapter_progress = {i: 0.0 for i in range(total_chs)}
        chapter_status = {i: "Mengantre..." for i in range(total_chs)}

        def update_chapter_progress(c_idx: int, pct: float, msg: str):
            with progress_lock:
                chapter_progress[c_idx] = pct
                chapter_status[c_idx] = msg

                done_count = sum(1 for p in chapter_progress.values() if p >= 100.0)
                avg_pct = sum(chapter_progress.values()) / max(1, total_chs)

                # Overall progress scale: 10% -> 95%
                job["progress"] = int(10 + (avg_pct * 0.85))

                active_msgs = []
                for i in range(total_chs):
                    if 0 < chapter_progress[i] < 100.0:
                        c_num = target_chapters[i].get("chapter_number", i + 1)
                        active_msgs.append(f"Ch {c_num}: {chapter_status[i]}")

                if active_msgs:
                    detail = " | ".join(active_msgs[:2])
                    job["message"] = f"[{done_count}/{total_chs} Selesai | Paralel {parallel_workers}x] {detail}"
                else:
                    job["message"] = f"[{done_count}/{total_chs} Selesai] Memproses {total_chs} chapter ({parallel_workers} worker)..."

        def process_single_chapter(ch_idx: int, ch_data: dict):
            ch_num = ch_data.get("chapter_number", ch_idx + 1)
            ch_folder = f"Chapter_{ch_num}"
            ch_panels_dir = os.path.join(panels_base_dir, ch_folder)
            ch_thumbs_dir = os.path.join(thumbs_base_dir, ch_folder)

            try:
                update_chapter_progress(ch_idx, 10, "Mengunduh gambar...")

                if "image_urls" in ch_data and ch_data["image_urls"]:
                    img_urls = ch_data["image_urls"]
                else:
                    ch_detail = fetch_shinigami_chapter_by_id(ch_data["chapter_id"])
                    img_urls = ch_detail.get("image_urls", [])

                if not img_urls:
                    update_chapter_progress(ch_idx, 100, "Tidak ada gambar")
                    return None

                raw_images = download_images_parallel(img_urls, max_workers=6)
                if not raw_images:
                    update_chapter_progress(ch_idx, 100, "Gagal mengunduh gambar")
                    return None

                update_chapter_progress(ch_idx, 40, f"Memotong {len(raw_images)} panel...")

                def on_slice_progress(pct: float, msg: str):
                    c_pct = 40.0 + (pct * 0.55)
                    update_chapter_progress(ch_idx, c_pct, msg)

                ch_res = process_and_slice_chapter(
                    raw_images=raw_images,
                    output_dir=ch_panels_dir,
                    thumbs_dir=ch_thumbs_dir,
                    use_gpu=req.use_gpu,
                    filter_banners=req.filter_banners,
                    filter_speech_bubbles=req.filter_speech_bubbles,
                    split_long_panels=req.split_long_panels,
                    max_panel_height=req.max_panel_height,
                    gutter_min_height=req.gutter_min_height,
                    progress_callback=on_slice_progress
                )

                formatted_panels = []
                for p in ch_res["panels"]:
                    rel_path = f"{ch_folder}/{p['filename']}"
                    rel_thumb = f"{ch_folder}/{p['thumb_filename']}"
                    formatted_panels.append({
                        **p,
                        "chapter_number": ch_num,
                        "chapter_folder": ch_folder,
                        "rel_path": rel_path,
                        "rel_thumb": rel_thumb,
                        "preview_url": f"/api/image/{job_id}/thumb/{rel_thumb}",
                        "full_url": f"/api/image/{job_id}/full/{rel_path}"
                    })

                update_chapter_progress(ch_idx, 100, f"Selesai ({len(formatted_panels)} panel)")

                return {
                    "chapter_index": ch_idx,
                    "chapter_number": ch_num,
                    "chapter_label": f"Chapter {ch_num}",
                    "chapter_folder": ch_folder,
                    "comic_width": ch_res["comic_width"],
                    "total_height": ch_res["total_height"],
                    "total_panels": len(formatted_panels),
                    "excluded_banners_count": ch_res["excluded_banners_count"],
                    "speech_bubbles_count": ch_res.get("speech_bubbles_count", 0),
                    "panels": formatted_panels
                }
            except Exception as e:
                import traceback
                traceback.print_exc()
                update_chapter_progress(ch_idx, 100, f"Error: {str(e)[:30]}")
                return None

        # Execute chapters concurrently
        with ThreadPoolExecutor(max_workers=parallel_workers) as pool:
            futures = [
                pool.submit(process_single_chapter, idx, ch)
                for idx, ch in enumerate(target_chapters)
            ]
            raw_results = [f.result() for f in futures]

        all_chapter_results = [r for r in raw_results if r is not None]
        all_chapter_results.sort(key=lambda c: c["chapter_number"])

        if not all_chapter_results:
            raise ValueError("Tidak ada chapter yang berhasil diunduh dan dipotong.")

        total_panels_all = sum(c["total_panels"] for c in all_chapter_results)
        total_bubbles = sum(c.get("speech_bubbles_count", 0) for c in all_chapter_results)

        # Panel disimpan di cache (temp_jobs). Tidak diekspor otomatis agar user bisa memilih manual.
        job["result"] = {
            "manga_title": manga_title,
            "warning": warning_msg,
            "gpu_used": req.use_gpu and gpu_info["available"],
            "gpu_name": gpu_info["name"] if req.use_gpu else "CPU",
            "total_chapters": len(all_chapter_results),
            "total_panels": total_panels_all,
            "total_speech_bubbles": total_bubbles,
            "parallel_workers": parallel_workers,
            "exported_folder": None,
            "exported_count": 0,
            "chapters": all_chapter_results
        }
        job["status"] = "completed"
        job["progress"] = 100
        job["message"] = f"Berhasil memotong {total_panels_all} panel ke cache! Silakan pilih folder tujuan untuk memindahkan gambar."

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = f"Error: {str(e)}"
    finally:
        release_anti_sleep(f"slice_{job_id}")

@app.get("/api/anti-sleep/status")
async def api_anti_sleep_status():
    return get_anti_sleep_status()

@app.post("/api/anti-sleep/toggle")
async def api_anti_sleep_toggle():
    return toggle_anti_sleep("manual")

@app.get("/api/gpu-info")
async def api_get_gpu():
    return get_gpu_info()

@app.get("/api/default-folders")
async def api_default_folders():
    user_home = os.path.expanduser("~")
    desktop = os.path.join(user_home, "Desktop")
    downloads = os.path.join(user_home, "Downloads")
    return {
        "output": os.path.abspath(DEFAULT_OUTPUT_DIR),
        "desktop": os.path.abspath(desktop) if os.path.exists(desktop) else os.path.abspath(DEFAULT_OUTPUT_DIR),
        "downloads": os.path.abspath(downloads) if os.path.exists(downloads) else os.path.abspath(DEFAULT_OUTPUT_DIR)
    }

def is_hidden_or_system(entry) -> bool:
    name = entry.name
    if name.startswith('.') or name.startswith('$') or name.lower().startswith('found.') or name.lower() == 'system volume information':
        return True
    try:
        attrs = getattr(entry.stat(), 'st_file_attributes', 0)
        # 0x2 = FILE_ATTRIBUTE_HIDDEN, 0x4 = FILE_ATTRIBUTE_SYSTEM
        if attrs & (0x2 | 0x4):
            return True
    except Exception:
        pass
    return False

@app.get("/api/explore-folder")
async def api_explore_folder(path: Optional[str] = None):
    try:
        target = path.strip() if path and path.strip() else DEFAULT_OUTPUT_DIR
        if not os.path.exists(target):
            target = DEFAULT_OUTPUT_DIR

        abs_path = os.path.abspath(target)
        if not os.path.isdir(abs_path):
            abs_path = os.path.dirname(abs_path)

        parent = os.path.dirname(abs_path)
        has_parent = (parent != abs_path and os.path.exists(parent))

        entries = []
        try:
            with os.scandir(abs_path) as it:
                for entry in it:
                    if entry.is_dir() and not is_hidden_or_system(entry):
                        entries.append({
                            "name": entry.name,
                            "path": os.path.abspath(entry.path)
                        })
        except PermissionError:
            pass

        entries.sort(key=lambda x: x["name"].lower())

        user_home = os.path.expanduser("~")
        desktop = os.path.join(user_home, "Desktop")
        downloads = os.path.join(user_home, "Downloads")

        return {
            "current_path": abs_path,
            "parent_path": parent if has_parent else None,
            "drives": get_system_drives(),
            "shortcuts": [
                {"label": "📁 Output Proyek", "path": os.path.abspath(DEFAULT_OUTPUT_DIR)},
                {"label": "🖥️ Desktop", "path": os.path.abspath(desktop)},
                {"label": "📥 Downloads", "path": os.path.abspath(downloads)},
                {"label": "🏠 User Home", "path": os.path.abspath(user_home)}
            ],
            "folders": entries
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/create-folder")
async def api_create_folder(req: CreateFolderRequest):
    try:
        clean_name = "".join(c for c in req.folder_name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="Nama folder tidak boleh kosong.")
        new_dir = os.path.join(req.parent_path, clean_name)
        os.makedirs(new_dir, exist_ok=True)
        return {"status": "success", "new_path": os.path.abspath(new_dir)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/cache-info")
async def api_cache_info():
    return calculate_cache_size()

class ClearCacheRequest(BaseModel):
    keep_current: bool = False
    current_job_id: Optional[str] = None

@app.post("/api/clear-cache")
async def api_clear_cache(req: Optional[ClearCacheRequest] = None):
    keep_id = req.current_job_id if req and req.keep_current else None
    result = clear_all_cache(keep_job_id=keep_id)
    return {
        "status": "success",
        "message": f"Berhasil membersihkan {result['freed_mb']} MB cache!",
        **result
    }

@app.post("/api/detect-manga")
async def api_detect_manga(req: DetectRequest):
    if not req.url:
        raise HTTPException(status_code=400, detail="URL tidak boleh kosong.")
    try:
        return detect_manga_series(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/process")
async def api_process_batch(req: ProcessBatchRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL tidak boleh kosong.")

    # Clean old cache if enabled so disk space doesn't accumulate
    if req.auto_clean_old_cache:
        clear_all_cache(keep_job_id=None)

    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {
        "id": job_id,
        "title": "Memuat...",
        "status": "pending",
        "progress": 0,
        "message": "Menyiapkan pemrosesan...",
        "error": None,
        "result": None
    }

    executor.submit(run_batch_job, job_id, req)
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
async def api_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    return {
        "job_id": job_id,
        "title": job.get("title", ""),
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error": job["error"]
    }

@app.get("/api/results/{job_id}")
async def api_job_results(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job belum selesai diproses.")

    return {
        "job_id": job_id,
        **job["result"]
    }

@app.get("/api/image/{job_id}/thumb/{path:path}")
async def api_get_thumb(job_id: str, path: str):
    full_path = os.path.join(TEMP_DIR, job_id, "thumbs", path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Thumbnail tidak ditemukan.")
    return FileResponse(full_path, media_type="image/webp")

@app.get("/api/image/{job_id}/full/{path:path}")
async def api_get_full(job_id: str, path: str):
    full_path = os.path.join(TEMP_DIR, job_id, "panels", path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Gambar panel tidak ditemukan.")
    return FileResponse(full_path, media_type="image/png")

@app.post("/api/export-folder/{job_id}")
async def api_export_folder(job_id: str, req: ExportFolderRequest):
    job = jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job tidak ditemukan atau belum selesai.")

    panels_dir = os.path.join(TEMP_DIR, job_id, "panels")
    if not os.path.exists(panels_dir):
        raise HTTPException(status_code=404, detail="Folder panel tidak ditemukan.")

    title = job.get("result", {}).get("manga_title") or job.get("title", "Manhwa")
    clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
    clean_title = clean_title.replace(' ', '_') or "Manhwa_Panels"

    base_target = req.target_folder.strip() if (req.target_folder and req.target_folder.strip()) else DEFAULT_OUTPUT_DIR
    target_dir = os.path.join(base_target, clean_title)
    os.makedirs(target_dir, exist_ok=True)

    selected_set = set(req.filenames) if req.filenames else None
    copied = 0

    for root, dirs, files in os.walk(panels_dir):
        for file in files:
            if file.lower().endswith(".png"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, panels_dir).replace("\\", "/")
                if selected_set is None or rel_path in selected_set or file in selected_set:
                    dest_path = os.path.join(target_dir, os.path.relpath(abs_path, panels_dir))
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(abs_path, dest_path)
                    copied += 1

    final_target = os.path.abspath(target_dir)

    if req.open_after and os.name == 'nt':
        try:
            os.startfile(final_target)
        except Exception:
            pass

    return {
        "status": "success",
        "target_folder": final_target,
        "copied_files": copied,
        "message": f"Berhasil menyimpan {copied} panel ke {final_target}"
    }

@app.post("/api/open-folder")
async def api_open_folder(req: OpenFolderRequest):
    folder_path = os.path.abspath(req.path)
    if not os.path.exists(folder_path):
        raise HTTPException(status_code=404, detail=f"Folder tidak ditemukan: {folder_path}")
    try:
        if os.name == 'nt':
            os.startfile(folder_path)
        return {"status": "success", "message": f"Membuka folder {folder_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download-zip/{job_id}")
async def api_download_zip(job_id: str, req: DownloadZipRequest):
    job = jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job tidak ditemukan atau belum selesai.")

    panels_dir = os.path.join(TEMP_DIR, job_id, "panels")
    if not os.path.exists(panels_dir):
        raise HTTPException(status_code=404, detail="Folder panel tidak ditemukan.")

    selected_set = set(req.filenames) if req.filenames else None

    # Walk through panels_dir to maintain Chapter_XXX/ folder structure inside ZIP
    # Use ZIP_STORED (no slow compression lag) since PNGs are already compressed.
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_STORED) as zf:
        for root, dirs, files in os.walk(panels_dir):
            for file in sorted(files):
                if file.lower().endswith(".png"):
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, panels_dir).replace("\\", "/")
                    if selected_set is None or rel_path in selected_set or file in selected_set:
                        zf.write(abs_path, arcname=rel_path)

    zip_buffer.seek(0)
    title = job.get("result", {}).get("manga_title") or job.get("title", "Manhwa")
    clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
    clean_title = clean_title.replace(' ', '_') or "Manhwa_Panels"
    zip_filename = f"{clean_title}_Panels.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )

@app.get("/api/enhancer/info")
async def api_enhancer_info():
    return get_enhancer_status()

@app.post("/api/enhancer/scan")
async def api_enhancer_scan(req: EnhanceScanRequest):
    if not req.folder_paths:
        raise HTTPException(status_code=400, detail="Daftar folder kosong.")
    res = scan_input_folders(req.folder_paths)
    return res

@app.post("/api/enhancer/start")
async def api_enhancer_start(req: EnhanceStartRequest):
    if not req.folder_paths:
        raise HTTPException(status_code=400, detail="Pilih setidaknya 1 folder untuk di-enhance.")

    scan_res = scan_input_folders(req.folder_paths)
    if scan_res["total_images"] == 0:
        raise HTTPException(status_code=400, detail="Tidak ditemukan file gambar (.png, .jpg, .webp) di dalam folder yang dipilih.")

    job_id = uuid.uuid4().hex[:10]
    target_dir = req.target_folder.strip() if req.target_folder and req.target_folder.strip() else os.path.join(DEFAULT_OUTPUT_DIR, "Enhanced")

    enhancement_jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Menyiapkan antrean gambar...",
        "total_images": scan_res["total_images"],
        "processed_images": 0,
        "error": None,
        "target_folder": os.path.abspath(target_dir)
    }

    executor.submit(
        run_enhancement_process,
        job_id,
        scan_res["_raw_data"],
        target_dir,
        req.model_name,
        req.scale
    )

    return {"job_id": job_id, "total_images": scan_res["total_images"]}

@app.get("/api/enhancer/status/{job_id}")
async def api_enhancer_status(job_id: str):
    job = enhancement_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job enhance tidak ditemukan.")
    return job

@app.post("/api/enhancer/cancel/{job_id}")
async def api_enhancer_cancel(job_id: str):
    job = enhancement_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job enhance tidak ditemukan.")

    job["status"] = "cancelled"
    job["message"] = "Proses dibatalkan oleh pengguna."

    proc = active_processes.get(job_id)
    if proc:
        try:
            proc.kill()
        except Exception:
            pass

    return {"status": "success", "message": "Proses berhasil dibatalkan."}

@app.get("/api/enhancer/last-slicer-folders")
async def api_last_slicer_folders():
    """Returns folder paths from the most recent slicing job so user can import them in 1-click."""
    recent_folders = []
    if jobs:
        for j_id, j_data in reversed(list(jobs.items())):
            if j_data.get("status") == "completed":
                panels_dir = os.path.join(TEMP_DIR, j_id, "panels")
                if os.path.exists(panels_dir):
                    for entry in os.scandir(panels_dir):
                        if entry.is_dir():
                            recent_folders.append(os.path.abspath(entry.path))
                if recent_folders:
                    break

    if not recent_folders and os.path.exists(DEFAULT_OUTPUT_DIR):
        for entry in os.scandir(DEFAULT_OUTPUT_DIR):
            if entry.is_dir() and entry.name.lower() != "enhanced":
                for sub in os.scandir(entry.path):
                    if sub.is_dir() and sub.name.startswith("Chapter_"):
                        recent_folders.append(os.path.abspath(sub.path))

    return {"folders": recent_folders}

ENHANCE_UPLOADS_DIR = os.path.join(TEMP_DIR, "enhance_uploads")
os.makedirs(ENHANCE_UPLOADS_DIR, exist_ok=True)

@app.post("/api/enhancer/upload-files")
async def api_enhancer_upload_files(
    files: List[UploadFile] = File(...),
    folders: Optional[List[str]] = Form(None)
):
    if not files:
        raise HTTPException(status_code=400, detail="Tidak ada file yang diunggah.")

    batch_id = uuid.uuid4().hex[:8]
    batch_dir = os.path.join(ENHANCE_UPLOADS_DIR, batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    folder_map: Dict[str, Dict[str, Any]] = {}

    for idx, f in enumerate(files):
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.webp'):
            continue

        raw_folder = "Gambar_Tunggal"
        if folders and idx < len(folders) and folders[idx]:
            raw_folder = folders[idx]

        # Sanitize folder path
        parts = [p.strip() for p in raw_folder.replace("\\", "/").split("/") if p.strip() and p.strip() != ".."]
        clean_parts = ["".join(c for c in part if c.isalnum() or c in " ._-()[]").strip() for part in parts]
        clean_parts = [p for p in clean_parts if p]

        folder_rel_path = os.path.join(*clean_parts) if clean_parts else "Gambar_Tunggal"
        folder_display_name = " / ".join(clean_parts) if clean_parts else "Gambar_Tunggal"
        target_dir = os.path.join(batch_dir, *clean_parts) if clean_parts else os.path.join(batch_dir, "Gambar_Tunggal")
        os.makedirs(target_dir, exist_ok=True)

        clean_name = os.path.basename(f.filename)
        dest_path = os.path.join(target_dir, clean_name)
        with open(dest_path, "wb") as out_f:
            shutil.copyfileobj(f.file, out_f)

        folder_key = os.path.abspath(target_dir)
        if folder_key not in folder_map:
            folder_map[folder_key] = {
                "folder_name": folder_display_name,
                "rel_path": folder_rel_path,
                "folder_path": folder_key,
                "images_count": 0
            }
        folder_map[folder_key]["images_count"] += 1

    if not folder_map:
        raise HTTPException(status_code=400, detail="File yang diunggah bukan format gambar yang didukung (.png, .jpg, .webp).")

    total_imgs = sum(f["images_count"] for f in folder_map.values())
    return {
        "status": "success",
        "batch_id": batch_id,
        "folders": list(folder_map.values()),
        "total_images": total_imgs,
        "total_folders": len(folder_map)
    }

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(index_file)

# Auto sleep-lock protection on slice tasks
