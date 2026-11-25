import os
import sys
import time
import uuid
import shutil
import subprocess
import threading
from typing import Dict, Any, List, Optional
from app.power import acquire_anti_sleep, release_anti_sleep

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(BASE_DIR, "tools", "rnnoise")
DEFAULT_AUDIO_OUTPUT = os.path.join(BASE_DIR, "output", "Audio_Enhanced")
TEMP_DIR = os.path.join(BASE_DIR, "temp_jobs")
AUDIO_UPLOADS_DIR = os.path.join(TEMP_DIR, "audio_uploads")
PREVIEW_DIR = os.path.join(TEMP_DIR, "audio_previews")

os.makedirs(DEFAULT_AUDIO_OUTPUT, exist_ok=True)
os.makedirs(AUDIO_UPLOADS_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.opus', '.aiff'}

# In-memory tracking for audio enhancement jobs
audio_jobs: Dict[str, Dict[str, Any]] = {}
active_audio_processes: Dict[str, subprocess.Popen] = {}
audio_lock = threading.Lock()

def get_rnnoise_model_path(model_filename: str) -> str:
    """
    Returns a forward-slash relative path (e.g. tools/rnnoise/bd.rnnn)
    so FFmpeg filtergraph never chokes on Windows drive letter colons (D:).
    """
    rel_path = f"tools/rnnoise/{model_filename}"
    abs_path = os.path.join(TOOLS_DIR, model_filename)
    if os.path.exists(abs_path):
        return rel_path
    
    # Fallback to bd.rnnn
    abs_fallback = os.path.join(TOOLS_DIR, "bd.rnnn")
    if os.path.exists(abs_fallback):
        return "tools/rnnoise/bd.rnnn"
    return ""

def get_audio_enhancer_status() -> Dict[str, Any]:
    rnnoise_ready = os.path.exists(os.path.join(TOOLS_DIR, "bd.rnnn"))
    return {
        "engine": "FFmpeg Neural DSP + RNNoise",
        "rnnoise_installed": rnnoise_ready,
        "models": [
            {
                "id": "studio-podcast",
                "label": "🎙️ Studio Podcast AI (Adobe Style)",
                "description": "Dual-Stage Neural Denoise + De-reverb + Studio Warmth EQ + Broadcast Loudness (-15 LUFS).",
                "default": True
            },
            {
                "id": "crisp-voiceover",
                "label": "⚡ Crisp Voiceover (Clean Denoise)",
                "description": "Pembersihan desis mic & kebisingan latar belakang dengan vokal jernih alami.",
                "default": False
            },
            {
                "id": "broadcast-warmth",
                "label": "📻 Broadcast Warmth & Leveler",
                "description": "Karakter suara narator tebal, bass hangat, dan dynamic leveler untuk narasi cerita manhwa.",
                "default": False
            },
            {
                "id": "smart-polish",
                "label": "🪄 Smart Audio Polish (Instant)",
                "description": "De-hum, noise gate adaptif, dan normalisasi EBU R128 standar YouTube tanpa distorsi.",
                "default": False
            }
        ]
    }

def format_time_hms(seconds: float) -> str:
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
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"

def get_audio_duration(file_path: str) -> float:
    """Uses ffprobe to obtain exact audio duration in seconds."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(proc.stdout.strip())
    except Exception:
        return 0.0

def scan_input_audio(folder_paths: List[str]) -> Dict[str, Any]:
    """
    Scans list of folders or audio file paths, organizing them into structured folder groups,
    preserving full subfolder hierarchy.
    """
    detected_folders = []
    total_audio_files = 0

    for raw_path in folder_paths:
        if not raw_path or not os.path.exists(raw_path):
            continue
        abs_p = os.path.abspath(raw_path)

        if os.path.isfile(abs_p):
            ext = os.path.splitext(abs_p)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                detected_folders.append({
                    "folder_name": "Audio_Tunggal",
                    "rel_path": "Audio_Tunggal",
                    "folder_path": os.path.dirname(abs_p),
                    "audio_count": 1,
                    "audio_files": [abs_p]
                })
                total_audio_files += 1

        elif os.path.isdir(abs_p):
            norm_p = os.path.normpath(abs_p)
            parts = norm_p.split(os.sep)
            rel_folder = ""
            if "audio_uploads" in parts:
                idx = parts.index("audio_uploads")
                if len(parts) > idx + 2:
                    rel_folder = os.path.join(*parts[idx+2:])

            # Direct audio files inside abs_p
            direct_audios = []
            for entry in os.scandir(abs_p):
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in AUDIO_EXTENSIONS:
                        direct_audios.append(entry.path)

            if direct_audios:
                rel_path = rel_folder if rel_folder else os.path.basename(abs_p)
                display_name = rel_path.replace(os.sep, " / ")
                detected_folders.append({
                    "folder_name": display_name,
                    "rel_path": rel_path,
                    "folder_path": abs_p,
                    "audio_count": len(direct_audios),
                    "audio_files": direct_audios
                })
                total_audio_files += len(direct_audios)
            else:
                for root, dirs, files in os.walk(abs_p):
                    auds = [os.path.join(root, f) for f in files if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS]
                    if auds:
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
                            "audio_count": len(auds),
                            "audio_files": auds
                        })
                        total_audio_files += len(auds)

    return {
        "total_folders": len(detected_folders),
        "total_audio_files": total_audio_files,
        "folders": [
            {
                "folder_name": f["folder_name"],
                "rel_path": f.get("rel_path", f["folder_name"]),
                "folder_path": f["folder_path"],
                "audio_count": f["audio_count"]
            }
            for f in detected_folders
        ],
        "_raw_data": detected_folders
    }

def build_ffmpeg_filter_chain(mode: str, strength_pct: int = 85) -> str:
    """
    Constructs high-end DSP studio filter chains based on selected mode and strength (0 - 100%).
    All model paths use relative forward-slash paths for FFmpeg safety.
    """
    strength = max(0.1, min(1.0, strength_pct / 100.0))
    rnnoise_bd = get_rnnoise_model_path("bd.rnnn")
    rnnoise_cb = get_rnnoise_model_path("cb.rnnn")
    rnnoise_mp = get_rnnoise_model_path("mp.rnnn")

    if mode == "studio-podcast":
        # Adobe Podcast Style:
        # Highpass -> Neural RNNoise -> De-esser -> Vocal Warmth / Air EQ -> Dynaudnorm -> EBU R128 Loudnorm
        deess_i = round(0.5 + (0.4 * strength), 2)
        warmth_g = round(2.0 + (1.2 * strength), 1)
        clarity_g = round(1.5 + (1.2 * strength), 1)
        
        chain_parts = [
            "highpass=f=75",
            f"arnndn=m='{rnnoise_bd}'" if rnnoise_bd else "afftdn=nr=18:nf=-25",
            f"deesser=i={deess_i}:m=0.5:f=0.5",
            f"equalizer=f=150:t=q:w=1.2:g={warmth_g}",
            "equalizer=f=450:t=q:w=1.5:g=-1.8",
            f"equalizer=f=3500:t=q:w=1.0:g={clarity_g}",
            "treble=g=1.5:f=8000",
            "dynaudnorm=f=150:g=15:m=10:p=0.9",
            "loudnorm=I=-15:TP=-1.5:LRA=9"
        ]
        return ",".join(chain_parts)

    elif mode == "crisp-voiceover":
        # Ultra Crisp & Denoised Voice:
        deess_i = round(0.4 + (0.4 * strength), 2)
        chain_parts = [
            "highpass=f=80",
            f"arnndn=m='{rnnoise_cb}'" if rnnoise_cb else "afftdn=nr=15:nf=-22",
            f"deesser=i={deess_i}",
            "equalizer=f=3200:t=q:w=1.0:g=2.2",
            "treble=g=2.2:f=7500",
            "dynaudnorm=f=200:g=12:m=8:p=0.95",
            "loudnorm=I=-16:TP=-1.5:LRA=10"
        ]
        return ",".join(chain_parts)

    elif mode == "broadcast-warmth":
        # Deep Narrator Voice (Rich chest resonance & compression):
        bass_g = round(2.5 + (1.5 * strength), 1)
        chain_parts = [
            "highpass=f=70",
            f"arnndn=m='{rnnoise_mp}'" if rnnoise_mp else "afftdn=nr=14:nf=-20",
            f"equalizer=f=120:t=q:w=1.0:g={bass_g}",
            "equalizer=f=500:t=q:w=1.2:g=-2.0",
            "equalizer=f=4000:t=q:w=1.2:g=2.5",
            "compand=attacks=0.02:decays=0.2:points=-60/-60|-24/-18|-12/-8|0/-3:gain=2",
            "loudnorm=I=-14:TP=-1.0:LRA=8"
        ]
        return ",".join(chain_parts)

    else:
        # Smart Audio Polish: Instant FFT denoise, gate & leveler
        nr_val = int(12 + (10 * strength))
        chain_parts = [
            "highpass=f=80",
            f"afftdn=nr={nr_val}:nf=-24",
            "deesser=i=0.6",
            "dynaudnorm=f=150:g=15:m=8:p=0.95",
            "loudnorm=I=-16:TP=-1.5:LRA=11"
        ]
        return ",".join(chain_parts)

def generate_preview_sample(input_path: str, output_path: str, job_id: str):
    """Creates a max 30s preview clip of both before and after audio for browser player comparison."""
    try:
        before_preview = os.path.join(PREVIEW_DIR, f"{job_id}_before.mp3")
        after_preview = os.path.join(PREVIEW_DIR, f"{job_id}_after.mp3")

        # Create max 30s before sample
        subprocess.run([
            "ffmpeg", "-y", "-i", os.path.abspath(input_path),
            "-t", "30", "-codec:a", "libmp3lame", "-b:a", "192k",
            os.path.abspath(before_preview)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)

        # Create max 30s after sample
        subprocess.run([
            "ffmpeg", "-y", "-i", os.path.abspath(output_path),
            "-t", "30", "-codec:a", "libmp3lame", "-b:a", "192k",
            os.path.abspath(after_preview)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)
    except Exception as e:
        print(f"Warning creating audio preview: {e}", flush=True)

def run_audio_enhancement_process(
    job_id: str,
    folder_data: List[Dict[str, Any]],
    target_base_dir: str,
    mode: str = "studio-podcast",
    strength_pct: int = 85,
    output_format: str = "auto"
):
    job = audio_jobs[job_id]
    total_audio_all = sum(f["audio_count"] for f in folder_data)
    job["total_audio"] = total_audio_all
    job["status"] = "processing"
    job["progress"] = 1
    job["message"] = f"Menyiapkan filter studio untuk {total_audio_all} file audio..."

    acquire_anti_sleep(f"audio_{job_id}")

    processed_count = 0
    start_time = time.time()
    os.makedirs(target_base_dir, exist_ok=True)
    first_processed_pair = None

    try:
        filter_chain = build_ffmpeg_filter_chain(mode, strength_pct)

        print("\n" + "=" * 70, flush=True)
        print(f"🎙️ [AUDIO ENHANCER STUDIO] Memulai Peningkatan Kualitas Suara", flush=True)
        print(f"   • Total Folder : {len(folder_data)} folder", flush=True)
        print(f"   • Total Audio  : {total_audio_all} file", flush=True)
        print(f"   • Mode Suara   : {mode} (Intensitas {strength_pct}%)", flush=True)
        print(f"   • Folder Output: {os.path.abspath(target_base_dir)}", flush=True)
        print("=" * 70 + "\n", flush=True)

        for f_idx, f_info in enumerate(folder_data):
            folder_display = f_info.get("folder_name", "Folder")
            folder_rel = f_info.get("rel_path") or folder_display.replace(" / ", os.sep)
            audio_list = f_info.get("audio_files", [])

            out_folder_path = os.path.join(target_base_dir, folder_rel)
            os.makedirs(out_folder_path, exist_ok=True)

            folder_start_time = time.time()
            print(f"\n📂 [{f_idx + 1}/{len(folder_data)}] Memproses Folder: {folder_display} ({len(audio_list)} audio)", flush=True)
            print("-" * 70, flush=True)

            job["current_folder"] = folder_display
            job["message"] = f"[{f_idx + 1}/{len(folder_data)}] Memproses {folder_display} ({len(audio_list)} audio)..."

            for audio_path in audio_list:
                if job.get("status") == "cancelled":
                    print("\n⏹️ [AUDIO ENHANCER] Dibatalkan oleh pengguna.\n", flush=True)
                    return

                fn = os.path.basename(audio_path)
                name_part, ext_part = os.path.splitext(fn)
                
                # Determine output extension:
                # If output_format is "mp3": use .mp3
                # If output_format is "wav": use .wav
                # If output_format is "auto": match input format (.mp3 for mp3/m4a/aac, .wav for wav/flac)
                clean_ext = ext_part.lower()
                if output_format == "wav":
                    out_ext = ".wav"
                elif output_format == "mp3":
                    out_ext = ".mp3"
                else:
                    out_ext = ".mp3" if clean_ext in ('.mp3', '.m4a', '.aac', '.wma', '.ogg') else ".wav"

                out_fn = f"{name_part}_enhanced{out_ext}"
                out_audio_path = os.path.join(out_folder_path, out_fn)

                audio_num = processed_count + 1
                t0 = time.time()
                total_dur = get_audio_duration(audio_path)

                # Process DSP filters to high-fidelity 48kHz PCM WAV first
                # (Prevents known libmp3lame floating-point psymodel assertion crash on Windows)
                is_mp3_dest = (out_ext == ".mp3")
                intermediate_wav = os.path.join(TEMP_DIR, f"dsp_{uuid.uuid4().hex[:8]}.wav") if is_mp3_dest else out_audio_path

                cmd_dsp = [
                    "ffmpeg",
                    "-y",
                    "-i", os.path.abspath(audio_path),
                    "-af", filter_chain,
                    "-codec:a", "pcm_s16le",
                    "-ar", "48000",
                    "-ac", "2",
                    os.path.abspath(intermediate_wav)
                ]

                proc = subprocess.Popen(
                    cmd_dsp,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=BASE_DIR
                )

                with audio_lock:
                    active_audio_processes[job_id] = proc

                stderr_lines = []
                for line in iter(proc.stderr.readline, ''):
                    stderr_lines.append(line)
                    if "time=" in line and total_dur > 0:
                        try:
                            idx = line.find("time=")
                            time_str = line[idx+5:idx+16].strip()
                            parts = time_str.split(":")
                            curr_sec = float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
                            pct_file = min(99.0, (curr_sec / total_dur) * 100.0)
                            
                            live_bar = make_progress_bar(pct_file, width=20)
                            sys.stdout.write(f"\r   Audio {audio_num}/{total_audio_all} ({fn}) : {live_bar}")
                            sys.stdout.flush()
                        except Exception:
                            pass

                proc.wait()

                with audio_lock:
                    active_audio_processes.pop(job_id, None)

                # Strictly check if FFmpeg succeeded
                if proc.returncode != 0:
                    err_msg = "".join(stderr_lines[-12:]).strip()
                    if is_mp3_dest and os.path.exists(intermediate_wav):
                        try: os.remove(intermediate_wav)
                        except Exception: pass
                    raise RuntimeError(f"FFmpeg gagal memproses {fn} (Code {proc.returncode}): {err_msg}")

                # If destination is MP3, transcode the clean PCM WAV to 320k MP3 (runs in ~0.5s at 80x speed)
                if is_mp3_dest:
                    cmd_mp3 = [
                        "ffmpeg",
                        "-y",
                        "-i", os.path.abspath(intermediate_wav),
                        "-codec:a", "libmp3lame",
                        "-b:a", "320k",
                        "-ar", "48000",
                        os.path.abspath(out_audio_path)
                    ]
                    res_mp3 = subprocess.run(cmd_mp3, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, cwd=BASE_DIR)
                    if os.path.exists(intermediate_wav):
                        try: os.remove(intermediate_wav)
                        except Exception: pass
                    if res_mp3.returncode != 0:
                        raise RuntimeError(f"Gagal mengonversi ke MP3: {res_mp3.stderr.strip()}")

                if not os.path.exists(out_audio_path) or os.path.getsize(out_audio_path) == 0:
                    raise RuntimeError(f"File output {out_fn} tidak berhasil dibuat atau kosong.")

                dur = max(0.01, time.time() - t0)
                done_bar = make_progress_bar(100.0, width=20)
                sys.stdout.write(f"\r   Audio {audio_num}/{total_audio_all} ({fn}) : {done_bar} | Selesai ({dur:.2f}s)\n")
                sys.stdout.flush()

                # Generate preview for the first completed audio file
                if first_processed_pair is None and os.path.exists(out_audio_path):
                    first_processed_pair = (audio_path, out_audio_path)
                    generate_preview_sample(audio_path, out_audio_path, job_id)

                processed_count += 1
                elapsed = max(0.1, time.time() - start_time)
                speed = elapsed / max(1, processed_count)
                remaining = (total_audio_all - processed_count) * speed

                pct = int((processed_count / max(1, total_audio_all)) * 98)
                job["progress"] = max(2, pct)
                job["processed_audio"] = processed_count
                job["eta_seconds"] = int(remaining)
                job["message"] = f"[{processed_count}/{total_audio_all}] {folder_display} -> {out_fn} (~{int(remaining)}d lagi)"

            folder_duration = max(0.01, time.time() - folder_start_time)
            folder_avg = folder_duration / max(1, len(audio_list))
            folder_time_str = format_time_hms(folder_duration)
            print("-" * 70, flush=True)
            print(f"📁 [FOLDER AUDIO SELESAI] {folder_display}", flush=True)
            print(f"   • Jumlah Audio  : {len(audio_list)} file", flush=True)
            print(f"   • Waktu Folder  : {folder_time_str} (~{folder_avg:.2f}s per audio)", flush=True)
            print(f"   • Tersimpan di  : {os.path.abspath(out_folder_path)}", flush=True)
            print("-" * 70, flush=True)

        total_time = max(0.01, time.time() - start_time)
        total_avg = total_time / max(1, processed_count)
        total_time_str = format_time_hms(total_time)

        print("\n" + "=" * 70, flush=True)
        print(f"🎉 [SEMUA PROSES AUDIO ENHANCER SELESAI]", flush=True)
        print(f"   • Total Folder      : {len(folder_data)} folder", flush=True)
        print(f"   • Total Audio       : {processed_count}/{total_audio_all} file", flush=True)
        print(f"   • Total Waktu Proses: {total_time_str} ({total_time:.2f} detik)", flush=True)
        print(f"   • Rata-rata/Audio   : {total_avg:.2f} detik", flush=True)
        print(f"   • Lokasi Output     : {os.path.abspath(target_base_dir)}", flush=True)
        print("=" * 70 + "\n", flush=True)

        job["progress"] = 100
        job["status"] = "completed"
        job["processed_audio"] = processed_count
        job["output_folder"] = os.path.abspath(target_base_dir)
        job["total_duration_text"] = total_time_str
        job["has_preview"] = (first_processed_pair is not None)
        job["message"] = f"Selesai! Berhasil meningkatkan {processed_count} audio ke dalam {len(folder_data)} folder dalam {total_time_str}."

    except Exception as e:
        import traceback
        traceback.print_exc()
        job["status"] = "failed"
        job["error"] = str(e)
        job["message"] = f"Terjadi kesalahan pemrosesan audio: {str(e)}"
    finally:
        release_anti_sleep(f"audio_{job_id}")
        with audio_lock:
            active_audio_processes.pop(job_id, None)
