import os
import math
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Callable, Tuple
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

Image.MAX_IMAGE_PIXELS = None

# Enable hardware acceleration in OpenCV
try:
    if cv2.ocl.haveOpenCL():
        cv2.ocl.setUseOpenCL(True)
except Exception:
    pass

def detect_banners(images: List[Image.Image]) -> Tuple[List[int], int]:
    if not images:
        return [], 720

    widths = [im.width for im in images]
    mode_width = Counter(widths).most_common(1)[0][0]
    banner_indices = []

    for i in range(min(3, len(images))):
        im = images[i]
        aspect_ratio = im.width / max(1, im.height)
        if im.width != mode_width or aspect_ratio > 1.15 or im.height < 550:
            banner_indices.append(i)
        else:
            break

    for i in range(len(images) - 1, max(-1, len(images) - 4), -1):
        if i in banner_indices:
            continue
        im = images[i]
        aspect_ratio = im.width / max(1, im.height)
        if im.width != mode_width or aspect_ratio > 1.15 or im.height < 650:
            banner_indices.append(i)
        else:
            break

    return banner_indices, mode_width

def is_standalone_speech_bubble(img_pil: Image.Image, use_gpu: bool = True) -> bool:
    """
    Detects whether an extracted panel is a standalone/isolated speech bubble
    (both regular oval bubbles and action/spiky bubbles with speed lines).
    """
    arr = np.array(img_pil)
    if arr.ndim == 2:
        return True

    h, w = arr.shape[:2]
    # Very tall panels (>1500px) are almost certainly scenes, not standalone speech bubbles
    if h > 1500:
        return False

    # Subsample 2x for fast analysis
    sub = arr[::2, ::2, :3]

    if use_gpu and cv2.ocl.haveOpenCL():
        try:
            # Execute color transforms directly in GPU VRAM
            u_img = cv2.UMat(sub)
            u_hsv = cv2.cvtColor(u_img, cv2.COLOR_RGB2HSV)
            u_gray = cv2.cvtColor(u_img, cv2.COLOR_RGB2GRAY)
            hsv_arr = u_hsv.get()
            gray = u_gray.get()
        except Exception:
            hsv_arr = cv2.cvtColor(sub, cv2.COLOR_RGB2HSV)
            gray = cv2.cvtColor(sub, cv2.COLOR_RGB2GRAY)
    else:
        hsv_arr = cv2.cvtColor(sub, cv2.COLOR_RGB2HSV)
        gray = cv2.cvtColor(sub, cv2.COLOR_RGB2GRAY)

    sat = hsv_arr[:, :, 1]
    colored_pct = float(np.mean(sat > 25) * 100)

    # Speech bubbles are predominantly monochrome (black text & bubble on light or dark background)
    if colored_pct > 6.5:
        return False

    # White / light background (including light speed/motion lines)
    light_pct = float(np.mean(gray > 185) * 100)
    # Dark ink (bubble outline, spiky dialogue border, text)
    dark_pct = float(np.mean(gray < 40) * 100)
    bg_ink_pct = light_pct + dark_pct

    # Border background ratio
    border_pixels = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
    border_bg_pct = float(np.mean((border_pixels > 180) | (border_pixels < 40)) * 100)

    # Standard oval bubble or spiky bubble with speed lines
    return (bg_ink_pct > 60.0) and (border_bg_pct > 65.0)

def generate_thumbnail(panel_img: Image.Image, max_w: int = 380, use_gpu: bool = True) -> Image.Image:
    """
    Generates preview thumbnail utilizing GPU hardware scaling when enabled.
    """
    arr = np.array(panel_img)
    h, w = arr.shape[:2]
    if w <= max_w:
        return panel_img.copy()

    target_h = int(h * (max_w / w))
    if use_gpu and cv2.ocl.haveOpenCL():
        try:
            u_arr = cv2.UMat(arr)
            u_resized = cv2.resize(u_arr, (max_w, target_h), interpolation=cv2.INTER_AREA)
            return Image.fromarray(u_resized.get())
        except Exception:
            pass

    thumb = panel_img.copy()
    thumb.thumbnail((max_w, 2000), Image.Resampling.LANCZOS)
    return thumb

def find_best_split_point(variance_profile: np.ndarray, ideal_y: int, search_window: int = 300) -> int:
    start = max(0, ideal_y - search_window)
    end = min(len(variance_profile), ideal_y + search_window)
    if start >= end:
        return ideal_y
    window = variance_profile[start:end]
    min_idx = int(np.argmin(window))
    return start + min_idx

def extract_panel_slice(
    slices: List[Image.Image],
    offsets: List[int],
    slice_heights: List[int],
    p_start: int,
    p_end: int,
    comic_width: int
) -> Image.Image:
    p_h = p_end - p_start
    panel_img = Image.new('RGB', (comic_width, p_h), color=(255, 255, 255))

    for idx, offset in enumerate(offsets):
        h = slice_heights[idx]
        c_start = offset
        c_end = offset + h

        o_start = max(p_start, c_start)
        o_end = min(p_end, c_end)

        if o_start < o_end:
            local_top = o_start - c_start
            local_bottom = o_end - c_start
            dest_top = o_start - p_start

            chunk = slices[idx]
            if chunk.width != comic_width:
                chunk = chunk.resize((comic_width, chunk.height), Image.Resampling.LANCZOS)

            cropped = chunk.crop((0, local_top, comic_width, local_bottom))
            panel_img.paste(cropped, (0, dest_top))

    return panel_img

def compute_single_slice_profile(im: Image.Image, comic_width: int, variance_threshold: float, use_gpu: bool) -> Tuple[np.ndarray, np.ndarray]:
    """Processes a single slice on GPU/CPU to compute variance and gutter profile."""
    if im.width != comic_width:
        im = im.resize((comic_width, im.height), Image.Resampling.LANCZOS)
    arr = np.array(im, dtype=np.uint8)

    if use_gpu and cv2.ocl.haveOpenCL():
        try:
            # GPU hardware reduction & variance
            f_arr = arr[:, ::3, :3].astype(np.float32)
            u_f = cv2.UMat(f_arr)
            u_mean = cv2.reduce(u_f, 1, cv2.REDUCE_AVG) # shape (H, 1, 3)
            r_mean = u_mean.get().mean(axis=(1, 2))

            r_var = np.var(f_arr, axis=1).mean(axis=1)
            is_gut = (r_var < variance_threshold) | (r_mean > 248.0) | (r_mean < 8.0)
            return is_gut, r_var
        except Exception:
            pass

    sub = arr[:, ::3, :3] if arr.ndim == 3 else np.stack([arr[:, ::3]]*3, axis=-1)
    r_var = np.var(sub, axis=1).mean(axis=1)
    r_mean = np.mean(sub, axis=(1, 2))
    is_gut = (r_var < variance_threshold) | (r_mean > 248.0) | (r_mean < 8.0)
    return is_gut, r_var

def process_and_slice_chapter(
    raw_images: List[Image.Image],
    output_dir: str,
    thumbs_dir: str,
    use_gpu: bool = True,
    filter_banners: bool = True,
    filter_speech_bubbles: bool = True,
    split_long_panels: bool = True,
    max_panel_height: int = 2500,
    gutter_min_height: int = 25,
    variance_threshold: float = 16.0,
    padding: int = 6,
    progress_callback: Callable[[float, str], None] = None
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)

    total_raw = len(raw_images)
    if progress_callback:
        progress_callback(10, f"Menganalisis {total_raw} gambar...")

    # 1. Detect banners
    banner_indices, comic_width = detect_banners(raw_images)
    excluded_banners_count = 0

    valid_slices: List[Image.Image] = []
    for idx, im in enumerate(raw_images):
        if filter_banners and idx in banner_indices:
            excluded_banners_count += 1
            continue
        valid_slices.append(im)

    if not valid_slices:
        raise ValueError("Tidak ada gambar komik yang valid untuk diproses.")

    if progress_callback:
        progress_callback(25, f"Menghitung celah antar panel (Akselerasi GPU Turbo)...")

    # 2. Build continuous profile and offsets
    slice_heights = [im.height for im in valid_slices]
    offsets = []
    curr = 0
    for h in slice_heights:
        offsets.append(curr)
        curr += h
    total_height = curr

    # Parallelize profile computation across GPU/CPU workers for maximum hardware load
    max_workers = 8 if use_gpu else 4
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(compute_single_slice_profile, im, comic_width, variance_threshold, use_gpu)
            for im in valid_slices
        ]
        results = [f.result() for f in futures]

    gutter_masks = [r[0] for r in results]
    var_profiles = [r[1] for r in results]

    full_is_gutter = np.concatenate(gutter_masks)
    full_var_profile = np.concatenate(var_profiles)

    if progress_callback:
        progress_callback(45, f"Mendeteksi posisi panel dari {total_height}px komik...")

    # 3. Detect gutters
    gutters = []
    start = None
    for y in range(total_height):
        if full_is_gutter[y] and start is None:
            start = y
        elif not full_is_gutter[y] and start is not None:
            if (y - start) >= gutter_min_height:
                gutters.append((start, y))
            start = None
    if start is not None and (total_height - start) >= gutter_min_height:
        gutters.append((start, total_height))

    # 4. Invert gutters to panel boundaries
    raw_panels: List[Tuple[int, int]] = []
    last_end = 0
    min_panel_h = 50

    for g_start, g_end in gutters:
        if g_start > last_end and (g_start - last_end) >= min_panel_h:
            p_top = max(0, last_end - padding)
            p_bottom = min(total_height, g_start + padding)
            raw_panels.append((p_top, p_bottom))
        last_end = g_end

    if last_end < total_height and (total_height - last_end) >= min_panel_h:
        p_top = max(0, last_end - padding)
        p_bottom = total_height
        raw_panels.append((p_top, p_bottom))

    if not raw_panels:
        raw_panels = [(0, total_height)]

    if progress_callback:
        progress_callback(60, f"Ditemukan {len(raw_panels)} panel. Mengekstrak dengan GPU VRAM & memfilter balon teks...")

    # 5. Extract panels and detect speech bubbles
    panels_metadata: List[Dict[str, Any]] = []
    panel_number = 1
    speech_bubbles_count = 0
    total_p = len(raw_panels)

    for p_idx, (p_start, p_end) in enumerate(raw_panels):
        p_height = p_end - p_start
        panel_full = extract_panel_slice(valid_slices, offsets, slice_heights, p_start, p_end, comic_width)

        # Detect standalone speech bubble with GPU acceleration
        is_bubble = is_standalone_speech_bubble(panel_full, use_gpu=use_gpu)
        if is_bubble:
            speech_bubbles_count += 1

        is_long = (p_height > max_panel_height) and not is_bubble

        if is_long and split_long_panels:
            # 1) Save original full version
            full_filename = f"panel_{panel_number:03d}_full.png"
            full_path = os.path.join(output_dir, full_filename)
            panel_full.save(full_path, format="PNG")

            thumb_full_fn = f"thumb_panel_{panel_number:03d}_full.webp"
            thumb_full_path = os.path.join(thumbs_dir, thumb_full_fn)
            thumb_img = generate_thumbnail(panel_full, max_w=380, use_gpu=use_gpu)
            thumb_img.save(thumb_full_path, format="WEBP", quality=82)

            panels_metadata.append({
                "id": f"p_{panel_number}_full",
                "panel_index": panel_number,
                "filename": full_filename,
                "width": comic_width,
                "height": p_height,
                "is_long": True,
                "is_speech_bubble": False,
                "variant": "full_original",
                "label": f"Panel #{panel_number} (Full Original)",
                "thumb_filename": thumb_full_fn,
                "default_selected": True
            })

            # 2) Calculate parts
            num_parts = max(2, int(round(p_height / max_panel_height)))
            part_ideal_h = p_height / num_parts
            split_points = [0]
            for part_i in range(1, num_parts):
                ideal_cut = int(p_start + part_i * part_ideal_h)
                best_cut = find_best_split_point(full_var_profile, ideal_cut, search_window=200)
                split_points.append(best_cut - p_start)
            split_points.append(p_height)

            for part_i in range(num_parts):
                y1 = split_points[part_i]
                y2 = split_points[part_i + 1]
                if y2 <= y1:
                    continue
                part_img = panel_full.crop((0, y1, comic_width, y2))
                part_h = y2 - y1

                part_fn = f"panel_{panel_number:03d}_part{part_i + 1}.png"
                part_path = os.path.join(output_dir, part_fn)
                part_img.save(part_path, format="PNG")

                thumb_part_fn = f"thumb_panel_{panel_number:03d}_part{part_i + 1}.webp"
                thumb_part_path = os.path.join(thumbs_dir, thumb_part_fn)
                t_img = generate_thumbnail(part_img, max_w=380, use_gpu=use_gpu)
                t_img.save(thumb_part_path, format="WEBP", quality=82)

                panels_metadata.append({
                    "id": f"p_{panel_number}_part{part_i + 1}",
                    "panel_index": panel_number,
                    "filename": part_fn,
                    "width": comic_width,
                    "height": part_h,
                    "is_long": True,
                    "is_speech_bubble": False,
                    "variant": f"part_{part_i + 1}",
                    "label": f"Panel #{panel_number} (Part {part_i + 1}/{num_parts})",
                    "thumb_filename": thumb_part_fn,
                    "default_selected": True
                })

            panel_number += 1

        else:
            # Standard single panel OR speech bubble panel
            filename = f"panel_{panel_number:03d}.png"
            full_path = os.path.join(output_dir, filename)
            panel_full.save(full_path, format="PNG")

            thumb_fn = f"thumb_panel_{panel_number:03d}.webp"
            thumb_path = os.path.join(thumbs_dir, thumb_fn)
            thumb_img = generate_thumbnail(panel_full, max_w=380, use_gpu=use_gpu)
            thumb_img.save(thumb_path, format="WEBP", quality=82)

            variant = "speech_bubble" if is_bubble else "standard"
            label = f"Panel #{panel_number} (Gelembung Teks)" if is_bubble else f"Panel #{panel_number}"
            default_sel = False if (is_bubble and filter_speech_bubbles) else True

            panels_metadata.append({
                "id": f"p_{panel_number}",
                "panel_index": panel_number,
                "filename": filename,
                "width": comic_width,
                "height": p_height,
                "is_long": False,
                "is_speech_bubble": is_bubble,
                "variant": variant,
                "label": label,
                "thumb_filename": thumb_fn,
                "default_selected": default_sel
            })
            panel_number += 1

        if progress_callback and (p_idx % 4 == 0 or p_idx == total_p - 1):
            pct = 60 + int((p_idx + 1) / total_p * 35)
            progress_callback(pct, f"Menyimpan panel {p_idx + 1}/{total_p}...")

    if progress_callback:
        progress_callback(100, f"Selesai! {len(panels_metadata)} potongan siap ({speech_bubbles_count} gelembung teks diabaikan).")

    return {
        "comic_width": comic_width,
        "total_height": total_height,
        "raw_panels_count": len(raw_panels),
        "total_files_generated": len(panels_metadata),
        "excluded_banners_count": excluded_banners_count,
        "speech_bubbles_count": speech_bubbles_count,
        "panels": panels_metadata
    }
