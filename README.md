# ✂️ BS Manhwa Recap Slicer & AI Enhancer Studio (Local)

Aplikasi web studio lokal yang dirancang khusus untuk pembuat konten **Manhwa Recap (YouTube, TikTok, Shorts)** untuk memotong panel komik secara otomatis, serta meningkatkan resolusi gambar manhwa menggunakan AI Super-Resolution (**Real-ESRGAN Vulkan GPU Accelerated**).

---

## ✨ Fitur Unggulan

### 1. ✂️ Pemotong Panel Otomatis (Manhwa Slicer)
- **⚡ Deteksi & Akselerasi GPU Otomatis**:
  - Otomatis mendeteksi kartu grafis (misal: **NVIDIA GeForce GTX 1650 4GB VRAM**) dengan monitoring beban GPU (`%`) dan VRAM secara *live*.
  - Menggunakan thread paralel berkemampuan tinggi untuk download dan pemotongan berkecepatan tinggi.
- **📚 Deteksi Seri & Rentang Episode (Batch Chapter)**:
  - Cukup masukkan 1 link chapter, aplikasi otomatis mengenali judul komik dan nomor episode saat ini.
  - Tersedia opsi rentang episode: **Dari Chapter X sampai Chapter Y**.
- **📁 File Rapi Tertata per Folder Episode**:
  - Hasil panel komik otomatis dikelompokkan ke dalam subfolder masing-masing episode (`Chapter_01`, `Chapter_02`, dst.).
- **✂️ Dynamic Panel Slicing (Lebar Asli)**:
  - Mempertahankan lebar asli komik (`~720px`) tanpa distorsi agar leluasa diedit atau di-crop di timeline Premiere / CapCut.
- **🛡️ Auto-Stitching & Anti-Potong Balon**:
  - Menyatukan potongan strip terlebih dahulu, lalu memotong persis di celah kosong (*gutter*) antar-panel tanpa memotong balon percakapan.
- **📏 Penanganan Panel Panjang (>2500px)**:
  - Panel super panjang otomatis disimpan versi **Full Original** dan dibuatkan versi **Split (Bagian 1, Bagian 2)**.
- **🧹 Auto-Filter Banner & Watermark**:
  - Menyingkirkan cover, banner credit, dan watermark Discord di awal / akhir chapter secara otomatis.

---

### 2. ✨ Peningkat Kualitas Gambar AI (Image Enhancer)
- **🚀 Akselerasi GPU Vulkan (Real-ESRGAN NCNN)**:
  - Meningkatkan ketajaman garis seni (*line-art*) dan resolusi gambar manhwa hingga **2x (2K)** atau **4x (4K)** tanpa blur.
  - Sangat cepat (~0.2s - 1.2s per gambar pada GTX 1650).
- **📂 Multi-Folder Drag & Drop Hirarkis**:
  - Cukup seret 1 folder atau banyak folder episode sekaligus dari Windows Explorer.
  - Struktur folder asal (contoh: `Manhwa A -> Episode 1 -> 1.png`) otomatis dipertahankan secara utuh pada folder output tujuan.
- **📊 Terminal Live Progress Bar**:
  - Monitoring progress 1–100% gaya installer pada command prompt.
  - Menampilkan durasi pengerjaan per-gambar, rangkuman waktu per-folder, dan total waktu keseluruhan proses.
- **☕ Floating Anti-Sleep Controller**:
  - Tombol melayang di pojok kanan bawah untuk mencegah Windows / layar masuk ke mode Sleep selama proses rendering berlangsung.

---

## 🚀 Cara Menjalankan Aplikasi

### Cara 1: Menggunakan `run.bat` (Rekomendasi 1-Klik)
Cukup **klik dua kali** file `run.bat` di folder project ini:
- Server akan otomatis mengecek dependensi, menjalankan backend di `http://localhost:8000`, dan membuka browser secara otomatis.

### Cara 2: Manual via Terminal
```bash
python run_server.py
```
Akses di browser: `http://localhost:8000`

---

## 📁 Struktur Direktori
```
BS_Manhwa/
├── app/
│   ├── main.py          # Backend FastAPI, API endpoints, dan background executor
│   ├── enhancer.py      # Engine Real-ESRGAN NCNN Vulkan & image upscaling
│   ├── gpu.py           # Monitoring live pemakaian GPU (%) & VRAM (nvidia-smi)
│   ├── power.py         # Pencegah mode sleep (Windows Kernel32 Execution State)
│   ├── scraper.py       # Scraper & fetcher Shinigami API
│   └── slicer.py        # Algoritma dynamic panel slicing & celah komik
├── static/
│   ├── index.html       # Web Studio UI (Dark Mode, Tab Slicer/Enhancer, Floating Anti-Sleep)
│   ├── css/style.css    # Custom Styling
│   └── js/app.js        # Logic Frontend & interaksi Drag-and-Drop
├── tools/
│   └── realesrgan/      # Binary Real-ESRGAN NCNN Vulkan & model AI weights
├── temp_jobs/           # Folder cache kerja sementara
├── output/              # Folder penyimpanan hasil potong & enhance
├── requirements.txt     # Dependensi Python
├── run_server.py        # Server runner & browser launcher
├── run.bat              # Script starter Windows anti force-close
└── README.md
```

---

## 📄 Lisensi
Dibuat untuk penggunaan pembuatan konten Manhwa Recap personal & studio.
