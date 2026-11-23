@echo off
setlocal
title BS Manhwa Recap Slicer - Local Studio
chcp 65001 >nul

cd /d "%~dp0"

echo ========================================================
echo       BS MANHWA RECAP SLICER - LOCAL STUDIO
echo ========================================================
echo.

:: 1. Atur environment Vulkan agar selalu bersih & optimal untuk GPU GTX 1650
set VK_LOADER_LAYERS_DISABLE=~all~

:: 2. Periksa apakah Python terpasang di sistem
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di PATH sistem Anda!
    echo Silakan install Python dari python.org dan pastikan centang "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 3. Aktifkan Virtual Environment secara otomatis jika tersedia
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

:: 4. Periksa dependensi utama (Cepat, ~0.1 detik jika sudah terpasang)
python -c "import fastapi, uvicorn, PIL, cv2, requests, pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Menginstall / memperbarui dependensi yang diperlukan...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Gagal menginstall dependensi! Periksa koneksi internet Anda.
        pause
        exit /b 1
    )
) else (
    echo [OK] Dependensi sistem siap.
)

:: 5. Jalankan server melalui script runner Python yang aman & anti force-close
python run_server.py

:: 6. Jika server berhenti dengan error, tahan jendela agar error terbaca
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Aplikasi terhenti. Tekan tombol apa saja untuk menutup jendela.
    pause
)
