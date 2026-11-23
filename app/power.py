import sys
import ctypes
import threading
from typing import Dict, Any

# Windows Kernel32 Execution States
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

_is_anti_sleep_active = False
_active_reasons = set()
_lock = threading.Lock()

def set_windows_sleep_prevention(enable: bool = True, keep_display: bool = True) -> bool:
    """Menginstruksikan Windows Kernel agar tidak mematikan PC/layar ke mode Sleep."""
    if sys.platform != "win32":
        return False
    try:
        if enable:
            flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            if keep_display:
                flags |= ES_DISPLAY_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(flags)
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        return True
    except Exception as e:
        print(f"[WARN] Gagal mengatur SetThreadExecutionState: {e}")
        return False

def acquire_anti_sleep(reason: str = "manual") -> Dict[str, Any]:
    """Mengaktifkan pencegahan Sleep dengan pencatatan alasan (manual/render/slicer)."""
    global _is_anti_sleep_active
    with _lock:
        _active_reasons.add(reason)
        _is_anti_sleep_active = True
        set_windows_sleep_prevention(True, keep_display=True)
    return get_anti_sleep_status()

def release_anti_sleep(reason: str = "manual") -> Dict[str, Any]:
    """Melepaskan proteksi Sleep untuk alasan tertentu."""
    global _is_anti_sleep_active
    with _lock:
        _active_reasons.discard(reason)
        if not _active_reasons:
            _is_anti_sleep_active = False
            set_windows_sleep_prevention(False)
    return get_anti_sleep_status()

def toggle_anti_sleep(reason: str = "manual") -> Dict[str, Any]:
    """Toggle manual status anti-sleep."""
    with _lock:
        if reason in _active_reasons:
            return release_anti_sleep(reason)
        else:
            return acquire_anti_sleep(reason)

def get_anti_sleep_status() -> Dict[str, Any]:
    """Mengembalikan status live apakah PC sedang dicegah tidur."""
    return {
        "active": _is_anti_sleep_active,
        "reasons": list(_active_reasons)
    }
