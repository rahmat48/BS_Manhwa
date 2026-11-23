import os
import sys
import time
import socket
import subprocess
import threading
import webbrowser
import copy

# 1. Pastikan Vulkan Layer bersih untuk kartu grafis NVIDIA GeForce GTX 1650
os.environ["VK_LOADER_LAYERS_DISABLE"] = "~all~"

def free_port(port: int = 8000):
    """Bebaskan port jika masih ada sesi server lama yang menggantung."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return  # Port sudah bebas
        
        # Cari PID proses yang mendengarkan di port ini
        cmd = f'netstat -ano | findstr :{port}'
        out = subprocess.check_output(cmd, shell=True, text=True, errors="ignore")
        pids_killed = set()
        my_pid = os.getpid()

        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in line:
                try:
                    pid = int(parts[-1])
                    if pid != my_pid and pid > 0 and pid not in pids_killed:
                        print(f"[INFO] Membersihkan port {port} dari sesi lama (PID: {pid})...")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                        pids_killed.add(pid)
                except ValueError:
                    pass
        if pids_killed:
            time.sleep(1.0)
    except Exception:
        pass

def open_browser_delayed(url: str = "http://localhost:8000", delay_seconds: float = 1.8):
    """Buka browser otomatis saat server sudah siap."""
    time.sleep(delay_seconds)
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    print("=" * 60)
    print("        BS MANHWA RECAP SLICER - LOCAL STUDIO")
    print("============================================================")
    print()

    # Bebaskan port 8000 jika dipakai sesi sebelumnya
    free_port(8000)

    # Buka browser otomatis di latar belakang
    threading.Thread(target=open_browser_delayed, daemon=True).start()

    print("[OK] Menjalankan server di http://localhost:8000 ...")
    print("[INFO] Browser akan terbuka otomatis dalam 2 detik.")
    print("[INFO] Tekan CTRL+C di terminal ini jika ingin mematikan aplikasi.")
    print("=" * 60)
    print()

    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    # Konfigurasi filter logging agar endpoint polling tidak membanjiri terminal
    log_config = copy.deepcopy(LOGGING_CONFIG)
    log_config["filters"] = {
        "endpoint_filter": {
            "()": "app.main.EndpointFilter",
        }
    }
    if "access" in log_config.get("handlers", {}):
        log_config["handlers"]["access"]["filters"] = ["endpoint_filter"]

    try:
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            log_config=log_config,
            log_level="info",
            reload=False
        )
    except KeyboardInterrupt:
        print("\n[INFO] Server dimatikan oleh pengguna. Sampai jumpa!")
    finally:
        try:
            from app.power import set_windows_sleep_prevention
            set_windows_sleep_prevention(False)
        except Exception:
            pass
        sys.exit(0)

if __name__ == "__main__":
    main()
