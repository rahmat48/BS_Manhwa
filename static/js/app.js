// Manhwa Recap Slicer - Frontend Logic (GPU & Batch Episode Support)

let currentJobId = null;
let currentResults = null;
let allPanels = [];
let selectedRelPaths = new Set();
let currentFilter = 'all';
let currentChapterTab = 'all';

// DOM Elements
const urlInput = document.getElementById('url-input');
const btnPasteSample = document.getElementById('btn-paste-sample');
const btnDetectSeries = document.getElementById('btn-detect-series');
const btnStartProcess = document.getElementById('btn-start-process');
const btnProcessLabel = document.getElementById('btn-process-label');

const btnToggleAntiSleep = document.getElementById('btn-toggle-anti-sleep');
const antiSleepStatus = document.getElementById('anti-sleep-status');
const antiSleepDot = document.getElementById('anti-sleep-dot');

const gpuBadge = document.getElementById('gpu-badge');
const gpuNameLabel = document.getElementById('gpu-name-label');
const gpuLoadLabel = document.getElementById('gpu-load-label');
const gpuVramLabel = document.getElementById('gpu-vram-label');
const optUseGpu = document.getElementById('opt-use-gpu');
const gpuSubtext = document.getElementById('gpu-subtext');

const seriesDetectionCard = document.getElementById('series-detection-card');
const detectedMangaTitle = document.getElementById('detected-manga-title');
const detectedCurrentCh = document.getElementById('detected-current-ch');
const detectedMinCh = document.getElementById('detected-min-ch');
const detectedMaxCh = document.getElementById('detected-max-ch');
const startChapterInput = document.getElementById('start-chapter-input');
const endChapterInput = document.getElementById('end-chapter-input');
const zipFolderPreview = document.getElementById('zip-folder-preview');

const chapterRangeWarning = document.getElementById('chapter-range-warning');
const chapterRangeWarningText = document.getElementById('chapter-range-warning-text');
const btnFixToMax = document.getElementById('btn-fix-to-max');
const resultsWarningBanner = document.getElementById('results-warning-banner');
const resultsWarningText = document.getElementById('results-warning-text');

// Target Folder Direct Save Elements
const targetFolderInput = document.getElementById('target-folder-input');
const optAutoExportFolder = document.getElementById('opt-auto-export-folder');
const btnBrowseFolder = document.getElementById('btn-browse-folder');
const btnBrowseLabel = document.getElementById('btn-browse-label');
const btnPresetOutput = document.getElementById('btn-preset-output');
const btnPresetDesktop = document.getElementById('btn-preset-desktop');
const btnPresetDownloads = document.getElementById('btn-preset-downloads');

const btnExecuteTransfer = document.getElementById('btn-execute-transfer');
const selectedMoveBadge = document.getElementById('selected-move-badge');
const btnTransferCountLabel = document.getElementById('btn-transfer-count-label');

const exportSuccessBanner = document.getElementById('export-success-banner');
const exportFolderPathDisplay = document.getElementById('export-folder-path-display');
const exportCountLabel = document.getElementById('export-count-label');
const btnOpenFolderPrimary = document.getElementById('btn-open-folder-primary');
const btnExportFolderCustom = document.getElementById('btn-export-folder-custom');

const optFilterBanners = document.getElementById('opt-filter-banners');
const optFilterSpeechBubbles = document.getElementById('opt-filter-speech-bubbles');
const optSplitLong = document.getElementById('opt-split-long');
const optAutoCleanCache = document.getElementById('opt-auto-clean-cache');

const navCacheSize = document.getElementById('nav-cache-size');
const btnClearCacheNav = document.getElementById('btn-clear-cache-nav');
const settingsCacheText = document.getElementById('settings-cache-text');
const btnClearCacheSettings = document.getElementById('btn-clear-cache-settings');
const btnClearCacheResults = document.getElementById('btn-clear-cache-results');

const toast = document.getElementById('toast');
const toastIcon = document.getElementById('toast-icon');
const toastMessage = document.getElementById('toast-message');

const progressCard = document.getElementById('progress-card');
const progressTitle = document.getElementById('progress-title');
const progressSubtitle = document.getElementById('progress-subtitle');
const progressPct = document.getElementById('progress-pct');
const progressBarFill = document.getElementById('progress-bar-fill');

const errorCard = document.getElementById('error-card');
const errorMessage = document.getElementById('error-message');

const resultsSection = document.getElementById('results-section');
const resChapterTitle = document.getElementById('res-chapter-title');
const statTotalChapters = document.getElementById('stat-total-chapters');
const statTotalPanels = document.getElementById('stat-total-panels');
const statSpeechBubbles = document.getElementById('stat-speech-bubbles');
const statParallelWorkers = document.getElementById('stat-parallel-workers');
const statGpuUsed = document.getElementById('stat-gpu-used');
const parallelWorkersText = document.getElementById('parallel-workers-text');

const episodeTabsContainer = document.getElementById('episode-tabs-container');
const checkSelectAll = document.getElementById('check-select-all');
const btnSelectArtOnly = document.getElementById('btn-select-art-only');
const btnSelectEverything = document.getElementById('btn-select-everything');
const selectedCountLabel = document.getElementById('selected-count');
const downloadBtnCount = document.getElementById('download-btn-count');
const btnDownloadZip = document.getElementById('btn-download-zip');
const panelsGrid = document.getElementById('panels-grid');

const previewModal = document.getElementById('preview-modal');
const modalTitle = document.getElementById('modal-title');
const modalDim = document.getElementById('modal-dim');
const modalImg = document.getElementById('modal-img');
const modalDownloadBtn = document.getElementById('modal-download-btn');
const modalCloseBtn = document.getElementById('modal-close-btn');

const sampleUrl = 'https://s1.shinigami.mx/chapter/b0bd977b-4a42-49c9-9d7e-3bfb44ac521d#mode=strip';

// 1. Fetch GPU Hardware Info on Load & Live Utilization / VRAM
async function checkGpuHardware() {
  try {
    const res = await fetch('/api/gpu-info');
    if (!res.ok) return;
    const gpu = await res.json();
    if (gpu.available) {
      if (gpuNameLabel) gpuNameLabel.textContent = gpu.short_name || gpu.name;
      if (gpuLoadLabel) gpuLoadLabel.textContent = `${gpu.gpu_util_pct || 0}%`;
      if (gpuVramLabel) gpuVramLabel.textContent = gpu.vram_used_text || `${gpu.vram_used_gb || 0} / ${gpu.vram_gb} GB`;

      if (gpuSubtext) gpuSubtext.textContent = `Aktif (${gpu.name} - ${gpu.vram_text})`;
      if (optUseGpu) optUseGpu.checked = true;
      if (gpuBadge) gpuBadge.classList.remove('hidden');
    } else {
      if (gpuNameLabel) gpuNameLabel.textContent = 'CPU Mode';
      if (gpuLoadLabel) gpuLoadLabel.textContent = 'CPU';
      if (gpuVramLabel) gpuVramLabel.textContent = 'N/A';
      if (gpuSubtext) gpuSubtext.textContent = 'GPU tidak terdeteksi (Fallback CPU)';
      if (optUseGpu) optUseGpu.checked = false;
      if (gpuBadge) gpuBadge.classList.remove('hidden');
    }
  } catch (err) {
    console.error('GPU check failed:', err);
  }
}
checkGpuHardware();
// Poll live GPU load and VRAM usage every 2.5 seconds
setInterval(checkGpuHardware, 2500);

// Anti-Sleep / Prevent PC & Screen Sleep Controller
let screenWakeLock = null;
let isAntiSleepActive = false;

async function requestScreenWakeLock() {
  try {
    if ('wakeLock' in navigator && !screenWakeLock) {
      screenWakeLock = await navigator.wakeLock.request('screen');
      screenWakeLock.addEventListener('release', () => {
        screenWakeLock = null;
      });
    }
  } catch (err) {
    console.warn('Wake Lock request:', err.message);
  }
}

async function releaseScreenWakeLock() {
  if (screenWakeLock) {
    try {
      await screenWakeLock.release();
    } catch (e) { }
    screenWakeLock = null;
  }
}

// Re-acquire screen wake lock on tab visibility change if anti-sleep is active
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && isAntiSleepActive) {
    await requestScreenWakeLock();
  }
});

function updateAntiSleepUI(active) {
  isAntiSleepActive = active;
  if (!btnToggleAntiSleep || !antiSleepStatus || !antiSleepDot) return;

  if (active) {
    btnToggleAntiSleep.classList.add('border-amber-500/50', 'bg-amber-950/90', 'text-amber-200', 'shadow-amber-500/20', 'ring-1', 'ring-amber-500/40');
    btnToggleAntiSleep.classList.remove('border-slate-700/80', 'bg-slate-900/95', 'text-slate-300');
    antiSleepDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse ring-2 ring-amber-400/50';
    antiSleepStatus.textContent = 'ON';
    antiSleepStatus.className = 'font-bold font-mono text-[11px] text-amber-300';
    btnToggleAntiSleep.title = 'Anti-Sleep AKTIF: PC & Layar tidak akan sleep saat render / idle. Klik untuk menonaktifkan.';
    requestScreenWakeLock();
  } else {
    btnToggleAntiSleep.classList.remove('border-amber-500/50', 'bg-amber-950/90', 'text-amber-200', 'shadow-amber-500/20', 'ring-1', 'ring-amber-500/40');
    btnToggleAntiSleep.classList.add('border-slate-700/80', 'bg-slate-900/95', 'text-slate-300');
    antiSleepDot.className = 'w-2.5 h-2.5 rounded-full bg-slate-600';
    antiSleepStatus.textContent = 'OFF';
    antiSleepStatus.className = 'font-bold font-mono text-[11px] text-slate-400';
    btnToggleAntiSleep.title = 'Anti-Sleep NONAKTIF: Klik untuk mencegah PC & layar sleep saat render.';
    releaseScreenWakeLock();
  }
}

async function checkAntiSleepStatus() {
  try {
    const res = await fetch('/api/anti-sleep/status');
    if (!res.ok) return;
    const data = await res.json();
    updateAntiSleepUI(data.active);
  } catch (err) {
    // Ignore fetch errors
  }
}

async function toggleAntiSleep() {
  try {
    let serverActive = null;
    try {
      const res = await fetch('/api/anti-sleep/toggle', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        serverActive = data.active;
      }
    } catch (fetchErr) {
      console.warn('Backend anti-sleep toggle unreachable, using client wake-lock fallback:', fetchErr);
    }

    // Gunakan status dari server jika endpoint tersedia, atau toggle client-side (Wake Lock) jika server belum restart
    const nextState = (serverActive !== null) ? serverActive : !isAntiSleepActive;
    updateAntiSleepUI(nextState);

    if (nextState) {
      showToast('☕ Anti-Sleep Aktif! Layar & PC dicegah dari mode sleep saat render.', '☕');
    } else {
      showToast('Anti-Sleep dinonaktifkan.', '💤');
    }
  } catch (err) {
    console.warn('Toggle anti-sleep error:', err);
  }
}

if (btnToggleAntiSleep) {
  btnToggleAntiSleep.addEventListener('click', toggleAntiSleep);
}

checkAntiSleepStatus();
// Poll anti-sleep status every 5 seconds to sync with background rendering jobs
setInterval(checkAntiSleepStatus, 5000);

// Default Folders & Preset handling
let defaultFolders = {
  output: 'D:\\CODING\\Manhwa Recap\\output',
  desktop: '',
  downloads: ''
};

async function loadDefaultFolders() {
  try {
    const res = await fetch('/api/default-folders');
    if (!res.ok) return;
    defaultFolders = await res.json();
    if (defaultFolders.output && targetFolderInput && !targetFolderInput.value) {
      targetFolderInput.value = defaultFolders.output;
    }
  } catch (err) {
    console.warn('Could not load default folders:', err);
  }
}
loadDefaultFolders();

if (btnPresetOutput) {
  btnPresetOutput.addEventListener('click', () => {
    if (defaultFolders.output) targetFolderInput.value = defaultFolders.output;
    showToast('Folder diatur ke Output Proyek', '📁');
  });
}
if (btnPresetDesktop) {
  btnPresetDesktop.addEventListener('click', () => {
    if (defaultFolders.desktop) targetFolderInput.value = defaultFolders.desktop;
    showToast('Folder diatur ke Desktop', '🖥️');
  });
}
if (btnPresetDownloads) {
  btnPresetDownloads.addEventListener('click', () => {
    if (defaultFolders.downloads) targetFolderInput.value = defaultFolders.downloads;
    showToast('Folder diatur ke Downloads', '📥');
  });
}

// In-App Folder Explorer Modal Logic
const folderPickerModal = document.getElementById('folder-picker-modal');
const btnCloseFolderModal = document.getElementById('btn-close-folder-modal');
const btnCancelFolderModal = document.getElementById('btn-cancel-folder-modal');
const btnConfirmFolderModal = document.getElementById('btn-confirm-folder-modal');
const modalConfirmBtnLabel = document.getElementById('modal-confirm-btn-label');
const btnModalFolderUp = document.getElementById('btn-modal-folder-up');
const btnModalNewFolder = document.getElementById('btn-modal-new-folder');
const modalCurrentPathText = document.getElementById('modal-current-path-text');
const modalSelectedFolderDisplay = document.getElementById('modal-selected-folder-display');
const modalDrivesList = document.getElementById('modal-drives-list');
const modalShortcutsList = document.getElementById('modal-shortcuts-list');
const modalFoldersContainer = document.getElementById('modal-folders-container');

let modalCurrentPath = '';
let modalParentPath = null;
let modalSelectedPath = '';
let onFolderConfirmCallback = null;

function openFolderPickerModal(initialPath, onConfirm) {
  onFolderConfirmCallback = onConfirm;
  if (modalConfirmBtnLabel) {
    modalConfirmBtnLabel.textContent = selectedRelPaths.size > 0
      ? `Pilih Folder Ini & Pindahkan (${selectedRelPaths.size} Gambar)`
      : 'Pilih Folder Ini';
  }
  folderPickerModal.classList.remove('hidden');
  document.body.classList.add('overflow-hidden');
  loadFolderDirectory(initialPath || (targetFolderInput ? targetFolderInput.value.trim() : ''));
}

function closeFolderPickerModal() {
  folderPickerModal.classList.add('hidden');
  document.body.classList.remove('overflow-hidden');
  onFolderConfirmCallback = null;
}

async function loadFolderDirectory(path) {
  modalFoldersContainer.innerHTML = `
    <div class="py-12 text-center text-slate-500 text-xs flex items-center justify-center gap-2">
      <svg class="w-4 h-4 animate-spin text-brand-400" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
      </svg>
      Membaca isi direktori...
    </div>
  `;

  try {
    const url = path ? `/api/explore-folder?path=${encodeURIComponent(path)}` : '/api/explore-folder';
    const res = await fetch(url);
    if (!res.ok) throw new Error('Gagal membuka folder.');
    const data = await res.json();

    modalCurrentPath = data.current_path;
    modalParentPath = data.parent_path;
    modalSelectedPath = data.current_path;

    modalCurrentPathText.textContent = data.current_path;
    modalSelectedFolderDisplay.textContent = data.current_path;

    // Up button
    btnModalFolderUp.disabled = !modalParentPath;
    if (!modalParentPath) {
      btnModalFolderUp.classList.add('opacity-40', 'cursor-not-allowed');
    } else {
      btnModalFolderUp.classList.remove('opacity-40', 'cursor-not-allowed');
    }

    // Drives
    modalDrivesList.innerHTML = '';
    data.drives.forEach(d => {
      const isCur = modalCurrentPath.toUpperCase().startsWith(d.toUpperCase());
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `px-2 py-0.5 rounded text-[11px] font-mono font-bold transition ${isCur ? 'bg-brand-600 text-white shadow' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`;
      btn.textContent = d;
      btn.onclick = () => loadFolderDirectory(d);
      modalDrivesList.appendChild(btn);
    });

    // Shortcuts
    modalShortcutsList.innerHTML = '';
    data.shortcuts.forEach(sc => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'px-2 py-0.5 rounded text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 transition whitespace-nowrap';
      btn.textContent = sc.label;
      btn.onclick = () => loadFolderDirectory(sc.path);
      modalShortcutsList.appendChild(btn);
    });

    // Subfolders list
    modalFoldersContainer.innerHTML = '';
    if (data.folders.length === 0) {
      modalFoldersContainer.innerHTML = `
        <div class="py-12 text-center text-slate-500 text-xs">
          (Folder ini kosong / tidak memiliki subfolder)
        </div>
      `;
    } else {
      data.folders.forEach(f => {
        const item = document.createElement('div');
        item.className = 'flex items-center justify-between p-2 rounded-lg hover:bg-slate-800/80 cursor-pointer text-xs text-slate-200 transition group border border-transparent hover:border-slate-700/60';
        item.innerHTML = `
          <div class="flex items-center gap-2.5 truncate flex-1">
            <span class="text-base text-amber-400 group-hover:scale-110 transition">📁</span>
            <span class="truncate font-medium">${f.name}</span>
          </div>
          <button type="button" class="px-2 py-1 bg-slate-900 group-hover:bg-brand-600 text-slate-400 group-hover:text-white rounded text-[10px] font-semibold transition">
            Buka &rarr;
          </button>
        `;
        item.onclick = () => loadFolderDirectory(f.path);
        modalFoldersContainer.appendChild(item);
      });
    }

  } catch (err) {
    modalFoldersContainer.innerHTML = `
      <div class="py-8 text-center text-rose-400 text-xs">
        ⚠️ ${err.message}
      </div>
    `;
  }
}

if (btnModalFolderUp) {
  btnModalFolderUp.addEventListener('click', () => {
    if (modalParentPath) loadFolderDirectory(modalParentPath);
  });
}

if (btnModalNewFolder) {
  btnModalNewFolder.addEventListener('click', async () => {
    const folderName = prompt('Masukkan nama folder baru:');
    if (!folderName || !folderName.trim()) return;

    try {
      const res = await fetch('/api/create-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          parent_path: modalCurrentPath,
          folder_name: folderName.trim()
        })
      });
      if (!res.ok) throw new Error('Gagal membuat folder.');
      const d = await res.json();
      showToast(`Folder dibuat: ${folderName}`, '📁');
      await loadFolderDirectory(d.new_path);
    } catch (err) {
      showError(err.message);
    }
  });
}

if (btnConfirmFolderModal) {
  btnConfirmFolderModal.addEventListener('click', () => {
    if (onFolderConfirmCallback) {
      onFolderConfirmCallback(modalSelectedPath || modalCurrentPath);
    }
    closeFolderPickerModal();
  });
}

if (btnCloseFolderModal) btnCloseFolderModal.addEventListener('click', closeFolderPickerModal);
if (btnCancelFolderModal) btnCancelFolderModal.addEventListener('click', closeFolderPickerModal);
if (folderPickerModal) {
  folderPickerModal.addEventListener('click', (e) => {
    if (e.target === folderPickerModal) closeFolderPickerModal();
  });
}

if (btnBrowseFolder) {
  btnBrowseFolder.addEventListener('click', () => {
    const curPath = targetFolderInput ? targetFolderInput.value.trim() : '';
    openFolderPickerModal(curPath, async (chosenPath) => {
      if (chosenPath) {
        targetFolderInput.value = chosenPath;
        // Setelah user memilih folder, baru langsung pindahkan gambar yang dipilih!
        await executeTransfer(chosenPath);
      }
    });
  });
}

// Cache Management Functions
async function fetchCacheInfo() {
  try {
    const res = await fetch('/api/cache-info');
    if (!res.ok) return;
    const data = await res.json();
    if (navCacheSize) navCacheSize.textContent = data.size_text;
    if (settingsCacheText) settingsCacheText.textContent = `${data.size_text} (${data.total_jobs} Sesi)`;
  } catch (err) {
    console.error('Cache info fetch failed:', err);
  }
}
fetchCacheInfo();

async function triggerClearCache() {
  try {
    const res = await fetch('/api/clear-cache', { method: 'POST' });
    if (!res.ok) throw new Error('Gagal membersihkan cache.');
    const data = await res.json();
    await fetchCacheInfo();
    showToast(`✨ Ruang disk dibersihkan! (${data.freed_mb} MB dikosongkan)`, '🗑️');
  } catch (err) {
    showError(err.message);
  }
}

if (btnClearCacheNav) btnClearCacheNav.addEventListener('click', triggerClearCache);
if (btnClearCacheSettings) btnClearCacheSettings.addEventListener('click', triggerClearCache);
if (btnClearCacheResults) btnClearCacheResults.addEventListener('click', triggerClearCache);

function showToast(msg, icon = '✨') {
  if (!toast) return;
  toastIcon.textContent = icon;
  toastMessage.textContent = msg;
  toast.classList.remove('hidden');
  setTimeout(() => {
    toast.classList.add('hidden');
  }, 3500);
}

// 2. Paste Sample URL
btnPasteSample.addEventListener('click', () => {
  urlInput.value = sampleUrl;
  autoDetectSeries(sampleUrl);
});

// Auto-detect when URL changes or user clicks "Cek Episode Lainnya"
btnDetectSeries.addEventListener('click', () => {
  const url = urlInput.value.trim();
  if (url) autoDetectSeries(url);
});

urlInput.addEventListener('blur', () => {
  const url = urlInput.value.trim();
  if (url) autoDetectSeries(url);
});

async function autoDetectSeries(url) {
  if (!url) return;
  try {
    const res = await fetch('/api/detect-manga', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    if (!res.ok) return;
    const data = await res.json();

    if (data.is_series) {
      detectedMangaTitle.textContent = data.manga_title || 'Manhwa Series';
      detectedCurrentCh.textContent = data.current_chapter;
      detectedMinCh.textContent = data.min_chapter;
      detectedMaxCh.textContent = data.max_chapter;

      startChapterInput.value = data.current_chapter;
      startChapterInput.min = data.min_chapter;
      startChapterInput.max = data.max_chapter;

      endChapterInput.value = data.current_chapter;
      endChapterInput.min = data.min_chapter;
      endChapterInput.max = data.max_chapter;

      seriesDetectionCard.classList.remove('hidden');
      updateEpisodeLabel();
    }
  } catch (err) {
    console.warn('Auto detect failed:', err);
  }
}

function updateEpisodeLabel() {
  const s = parseFloat(startChapterInput.value);
  const e = parseFloat(endChapterInput.value);
  const maxAvail = parseFloat(detectedMaxCh.textContent);

  if (!isNaN(s) && !isNaN(e)) {
    const minVal = Math.min(s, e);
    const maxVal = Math.max(s, e);
    const count = Math.floor(maxVal - minVal) + 1;
    const workers = Math.min(5, Math.max(1, count));

    if (parallelWorkersText) {
      if (count === 1) {
        parallelWorkersText.textContent = `1 Episode (Tunggal)`;
      } else if (count <= 5) {
        parallelWorkersText.textContent = `${workers} Episode Sekaligus`;
      } else {
        parallelWorkersText.textContent = `${workers} Episode Sekaligus (Antrean ${count} Episode)`;
      }
    }

    if (!isNaN(maxAvail) && maxVal > maxAvail) {
      const availCount = Math.max(1, Math.floor(maxAvail - minVal) + 1);
      const availWorkers = Math.min(5, availCount);
      if (chapterRangeWarning) {
        chapterRangeWarning.classList.remove('hidden');
        chapterRangeWarningText.innerHTML = `Chapter <strong>${maxVal}</strong> belum rilis di website! Episode terbaru saat ini adalah <strong>Chapter ${maxAvail}</strong>.`;
      }
      btnProcessLabel.textContent = `Potong Batch Chapter ${minVal} s/d ${maxAvail} (${availWorkers}x Paralel)`;
      zipFolderPreview.textContent = `Chapter_${minVal}/ s/d Chapter_${maxAvail}/`;
    } else {
      if (chapterRangeWarning) chapterRangeWarning.classList.add('hidden');
      if (s === e) {
        btnProcessLabel.textContent = `✂️ Potong Panel Chapter ${s}`;
        zipFolderPreview.textContent = `Chapter_${s}/`;
      } else {
        btnProcessLabel.textContent = `✂️ Potong Batch Chapter ${minVal} s/d ${maxVal} (${workers}x Paralel)`;
        zipFolderPreview.textContent = `Chapter_${minVal}/, Chapter_${maxVal}/, dst.`;
      }
    }
  }
}

if (btnFixToMax) {
  btnFixToMax.addEventListener('click', () => {
    const maxAvail = parseFloat(detectedMaxCh.textContent);
    if (!isNaN(maxAvail)) {
      endChapterInput.value = maxAvail;
      updateEpisodeLabel();
    }
  });
}

startChapterInput.addEventListener('input', updateEpisodeLabel);
endChapterInput.addEventListener('input', updateEpisodeLabel);

// 3. Start Processing
btnStartProcess.addEventListener('click', async () => {
  const url = urlInput.value.trim();
  if (!url) {
    showError('Silakan masukkan link URL chapter terlebih dahulu.');
    return;
  }

  hideError();
  showProgress('Memulai proses...', 'Menghubungkan ke server...', 5);
  btnStartProcess.disabled = true;

  const sVal = seriesDetectionCard.classList.contains('hidden') ? null : parseFloat(startChapterInput.value);
  const eVal = seriesDetectionCard.classList.contains('hidden') ? null : parseFloat(endChapterInput.value);

  try {
    const res = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        start_chapter: sVal,
        end_chapter: eVal,
        use_gpu: optUseGpu.checked,
        filter_banners: optFilterBanners.checked,
        filter_speech_bubbles: optFilterSpeechBubbles ? optFilterSpeechBubbles.checked : true,
        split_long_panels: optSplitLong.checked,
        auto_clean_old_cache: optAutoCleanCache ? optAutoCleanCache.checked : true,
        auto_export_folder: false,
        max_panel_height: 2500,
        gutter_min_height: 25,
        max_parallel_chapters: 5
      })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Gagal memulai pemrosesan.');
    }

    const data = await res.json();
    currentJobId = data.job_id;
    pollStatus(currentJobId);
  } catch (err) {
    btnStartProcess.disabled = false;
    hideProgress();
    showError(err.message);
  }
});

// 4. Polling Job Status
async function pollStatus(jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      if (!res.ok) throw new Error('Gagal memeriksa status job.');
      const data = await res.json();

      updateProgress(data.title || 'Sedang Memproses', data.message, data.progress);

      if (data.status === 'completed') {
        clearInterval(interval);
        setTimeout(async () => {
          hideProgress();
          btnStartProcess.disabled = false;
          await loadResults(jobId);
        }, 500);
      } else if (data.status === 'failed') {
        clearInterval(interval);
        hideProgress();
        btnStartProcess.disabled = false;
        showError(data.error || data.message || 'Proses gagal.');
      }
    } catch (err) {
      clearInterval(interval);
      hideProgress();
      btnStartProcess.disabled = false;
      showError(err.message);
    }
  }, 700);
}

// 5. Load Results
async function loadResults(jobId) {
  try {
    const res = await fetch(`/api/results/${jobId}`);
    if (!res.ok) throw new Error('Gagal mengambil data hasil potongan.');
    currentResults = await res.json();

    // Flatten all panels
    allPanels = [];
    currentResults.chapters.forEach(ch => {
      ch.panels.forEach(p => allPanels.push(p));
    });

    // Select panels that have default_selected=true (speech bubbles are unchecked by default!)
    selectedRelPaths = new Set(allPanels.filter(p => p.default_selected !== false).map(p => p.rel_path));

    // Stats
    resChapterTitle.textContent = currentResults.manga_title || 'Manhwa Chapter';
    statTotalChapters.textContent = `${currentResults.total_chapters} Episode`;
    statTotalPanels.textContent = `${currentResults.total_panels} Total Potongan`;
    if (statSpeechBubbles) {
      statSpeechBubbles.textContent = `💬 ${currentResults.total_speech_bubbles || 0} Balon Teks (Dikecualikan)`;
    }
    if (statParallelWorkers) {
      statParallelWorkers.textContent = `⚡ ${currentResults.parallel_workers || 1}x Paralel`;
    }
    statGpuUsed.textContent = currentResults.gpu_used ? `⚡ GPU: ${currentResults.gpu_name}` : 'CPU Multi-Thread';

    if (resultsWarningBanner) {
      if (currentResults.warning) {
        resultsWarningBanner.classList.remove('hidden');
        resultsWarningText.textContent = currentResults.warning;
      } else {
        resultsWarningBanner.classList.add('hidden');
      }
    }

    // Direct folder save status banner
    if (exportSuccessBanner) {
      if (currentResults.exported_folder) {
        exportSuccessBanner.classList.remove('hidden');
        if (exportFolderPathDisplay) exportFolderPathDisplay.textContent = currentResults.exported_folder;
        if (exportCountLabel) {
          const c = currentResults.exported_count !== undefined ? currentResults.exported_count : selectedRelPaths.size;
          exportCountLabel.textContent = `${c} Panel tersimpan rapi`;
        }
      } else {
        exportSuccessBanner.classList.add('hidden');
      }
    }

    // Build Episode Tabs
    buildEpisodeTabs();

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });

    renderPanelsGrid();
    updateSelectionCounts();
    fetchCacheInfo();
  } catch (err) {
    showError(err.message);
  }
}

// 6. Build Episode Tabs
function buildEpisodeTabs() {
  episodeTabsContainer.innerHTML = '';
  if (currentResults.chapters.length <= 1) {
    episodeTabsContainer.classList.add('hidden');
    return;
  }

  episodeTabsContainer.classList.remove('hidden');

  // "Semua Episode" tab
  const allTab = document.createElement('button');
  allTab.className = `px-3 py-1.5 rounded-lg font-semibold text-xs transition ${currentChapterTab === 'all' ? 'bg-brand-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`;
  allTab.textContent = `Semua (${currentResults.total_panels})`;
  allTab.onclick = () => {
    currentChapterTab = 'all';
    buildEpisodeTabs();
    renderPanelsGrid();
  };
  episodeTabsContainer.appendChild(allTab);

  // Each chapter tab
  currentResults.chapters.forEach(ch => {
    const tab = document.createElement('button');
    const isAct = currentChapterTab === ch.chapter_number.toString();
    tab.className = `px-3 py-1.5 rounded-lg font-semibold text-xs whitespace-nowrap transition ${isAct ? 'bg-brand-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`;
    tab.textContent = `Ch ${ch.chapter_number} (${ch.total_panels})`;
    tab.onclick = () => {
      currentChapterTab = ch.chapter_number.toString();
      buildEpisodeTabs();
      renderPanelsGrid();
    };
    episodeTabsContainer.appendChild(tab);
  });
}

// 7. Render Panels Grid
function renderPanelsGrid() {
  panelsGrid.innerHTML = '';

  const filtered = allPanels.filter(p => {
    // Episode filter
    if (currentChapterTab !== 'all' && p.chapter_number.toString() !== currentChapterTab) {
      return false;
    }
    // Variant filter
    if (currentFilter === 'all') return true;
    if (currentFilter === 'art') return !p.is_speech_bubble;
    if (currentFilter === 'bubbles') return p.is_speech_bubble;
    if (currentFilter === 'standard') return p.variant === 'standard';
    if (currentFilter === 'full') return p.variant === 'full_original';
    if (currentFilter === 'parts') return p.variant.startsWith('part_');
    return true;
  });

  if (filtered.length === 0) {
    panelsGrid.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-500 text-sm">
        Tidak ada panel pada filter ini.
      </div>
    `;
    return;
  }

  filtered.forEach(panel => {
    const isChecked = selectedRelPaths.has(panel.rel_path);
    const card = document.createElement('div');
    card.className = `panel-card bg-[#131b2e] border border-slate-800 rounded-xl overflow-hidden flex flex-col ${!isChecked ? 'deselected' : ''}`;
    card.id = `card-${panel.id}`;

    // Badge
    let badgeHtml = '';
    if (panel.is_speech_bubble) {
      badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">💬 Balon Teks</span>`;
    } else if (panel.variant === 'full_original') {
      badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">Full (>2500px)</span>`;
    } else if (panel.variant.startsWith('part_')) {
      badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Split Part</span>`;
    } else {
      badgeHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">Gambar</span>`;
    }

    card.innerHTML = `
      <div class="p-3 bg-slate-900/60 border-b border-slate-800/80 flex items-center justify-between text-xs">
        <label class="flex items-center gap-2 cursor-pointer font-semibold text-slate-200 truncate">
          <input type="checkbox" data-rel="${panel.rel_path}" class="panel-checkbox w-4 h-4 rounded text-brand-600 bg-slate-800 border-slate-700" ${isChecked ? 'checked' : ''}>
          <span class="truncate">Ch ${panel.chapter_number} - ${panel.label}</span>
        </label>
        ${badgeHtml}
      </div>

      <div class="panel-thumb-container relative h-72 flex items-center justify-center p-2 overflow-hidden cursor-pointer group" onclick="openPreview('${panel.rel_path}', 'Ch ${panel.chapter_number} - ${panel.label}', '${panel.width} × ${panel.height} px', '${panel.full_url}')">
        <img
          src="${panel.preview_url}"
          alt="${panel.label}"
          loading="lazy"
          class="max-h-full max-w-full object-contain rounded shadow transition duration-200 group-hover:scale-105"
        />
        <div class="absolute inset-0 bg-brand-600/10 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
          <span class="px-3 py-1.5 bg-slate-900/90 text-white rounded-lg text-xs font-semibold shadow-lg backdrop-blur border border-slate-700 flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
            Lihat Full
          </span>
        </div>
      </div>

      <div class="p-3 bg-slate-900/80 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
        <div class="font-mono text-[11px] text-slate-400">
          📁 ${panel.chapter_folder} • ${panel.width}×${panel.height}
        </div>
        <a
          href="${panel.full_url}"
          download="${panel.filename}"
          class="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition"
          title="Download PNG Tunggal"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
        </a>
      </div>
    `;

    const chk = card.querySelector('.panel-checkbox');
    chk.addEventListener('change', (e) => {
      const rel = e.target.dataset.rel;
      if (e.target.checked) {
        selectedRelPaths.add(rel);
        card.classList.remove('deselected');
      } else {
        selectedRelPaths.delete(rel);
        card.classList.add('deselected');
      }
      updateSelectionCounts();
    });

    panelsGrid.appendChild(card);
  });
}

// 8. Update Selection Counts
function updateSelectionCounts() {
  const count = selectedRelPaths.size;
  selectedCountLabel.textContent = count;
  downloadBtnCount.textContent = count;

  if (selectedMoveBadge) selectedMoveBadge.textContent = count;
  if (btnTransferCountLabel) btnTransferCountLabel.textContent = count;

  if (btnExecuteTransfer) {
    btnExecuteTransfer.disabled = count === 0;
    if (count === 0) {
      btnExecuteTransfer.classList.add('opacity-50', 'cursor-not-allowed');
    } else {
      btnExecuteTransfer.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  }

  checkSelectAll.checked = count === allPanels.length && allPanels.length > 0;
  btnDownloadZip.disabled = count === 0;
  if (count === 0) {
    btnDownloadZip.classList.add('opacity-50', 'cursor-not-allowed');
  } else {
    btnDownloadZip.classList.remove('opacity-50', 'cursor-not-allowed');
  }
}

// 9. Selection Buttons
checkSelectAll.addEventListener('change', (e) => {
  if (e.target.checked) {
    allPanels.forEach(p => selectedRelPaths.add(p.rel_path));
  } else {
    selectedRelPaths.clear();
  }
  renderPanelsGrid();
  updateSelectionCounts();
});

if (btnSelectArtOnly) {
  btnSelectArtOnly.addEventListener('click', () => {
    selectedRelPaths = new Set(allPanels.filter(p => !p.is_speech_bubble).map(p => p.rel_path));
    renderPanelsGrid();
    updateSelectionCounts();
    fetchCacheInfo();
  });
}

if (btnSelectEverything) {
  btnSelectEverything.addEventListener('click', () => {
    selectedRelPaths = new Set(allPanels.map(p => p.rel_path));
    renderPanelsGrid();
    updateSelectionCounts();
    fetchCacheInfo();
  });
}

// 10. Filter Chips Handling
const filterChips = document.querySelectorAll('.filter-chip');
filterChips.forEach(chip => {
  chip.addEventListener('click', (e) => {
    filterChips.forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    if (chip.id === 'filter-all') currentFilter = 'all';
    else if (chip.id === 'filter-art-only') currentFilter = 'art';
    else if (chip.id === 'filter-bubbles') currentFilter = 'bubbles';
    else if (chip.id === 'filter-standard') currentFilter = 'standard';
    else if (chip.id === 'filter-full') currentFilter = 'full';
    else if (chip.id === 'filter-parts') currentFilter = 'parts';
    renderPanelsGrid();
  });
});

// 11. Direct Folder Operations & Download ZIP
// Execute Transfer of Selected Panels Only
async function executeTransfer(targetPath) {
  if (!currentJobId || selectedRelPaths.size === 0) {
    showError('Pilih minimal 1 gambar panel untuk dipindahkan ke folder.');
    return;
  }

  const destFolder = (targetPath && targetPath.trim()) || (targetFolderInput ? targetFolderInput.value.trim() : '');
  if (!destFolder) {
    showError('Silakan pilih folder tujuan penyimpanan terlebih dahulu.');
    return;
  }

  if (btnExecuteTransfer) {
    btnExecuteTransfer.disabled = true;
    btnExecuteTransfer.innerHTML = `
      <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
      </svg>
      <span>Memindahkan ${selectedRelPaths.size} Gambar...</span>
    `;
  }

  showToast(`Sedang menyalin ${selectedRelPaths.size} gambar terpilih ke folder tujuan...`, '⏳');
  try {
    const res = await fetch(`/api/export-folder/${currentJobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_folder: destFolder,
        filenames: Array.from(selectedRelPaths),
        open_after: true
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Gagal memindahkan gambar ke folder tujuan.');
    }
    const data = await res.json();
    showToast(`✅ ${data.copied_files} gambar terpilih berhasil dipindahkan!`, '📂');
    if (exportFolderPathDisplay) exportFolderPathDisplay.textContent = data.target_folder;
    if (exportCountLabel) exportCountLabel.textContent = `${data.copied_files} Gambar terpilih`;
    if (exportSuccessBanner) {
      exportSuccessBanner.classList.remove('hidden');
      exportSuccessBanner.scrollIntoView({ behavior: 'smooth' });
    }
  } catch (err) {
    showError(err.message);
  } finally {
    if (btnExecuteTransfer) {
      btnExecuteTransfer.disabled = false;
      btnExecuteTransfer.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"/></svg>
        <span>Pindahkan <span id="btn-transfer-count-label">${selectedRelPaths.size}</span> Gambar ke Folder</span>
      `;
    }
  }
}

if (btnExecuteTransfer) {
  btnExecuteTransfer.addEventListener('click', async () => {
    await executeTransfer();
  });
}

if (btnOpenFolderPrimary) {
  btnOpenFolderPrimary.addEventListener('click', async () => {
    const targetPath = (exportFolderPathDisplay && exportFolderPathDisplay.textContent) || (targetFolderInput ? targetFolderInput.value.trim() : '');
    if (!targetPath) {
      showError('Lokasi folder belum tersedia.');
      return;
    }
    try {
      const res = await fetch('/api/open-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Gagal membuka folder di File Explorer.');
      }
      showToast('📂 Folder dibuka di File Explorer!', '📂');
    } catch (err) {
      showError(err.message);
    }
  });
}

if (btnExportFolderCustom) {
  btnExportFolderCustom.addEventListener('click', () => {
    if (!currentJobId || selectedRelPaths.size === 0) return;
    const curPath = targetFolderInput ? targetFolderInput.value.trim() : '';
    openFolderPickerModal(curPath, async (chosenPath) => {
      if (chosenPath) {
        targetFolderInput.value = chosenPath;
        await executeTransfer(chosenPath);
      }
    });
  });
}

btnDownloadZip.addEventListener('click', async () => {
  if (!currentJobId || selectedRelPaths.size === 0) return;

  btnDownloadZip.disabled = true;
  const originalText = btnDownloadZip.innerHTML;
  btnDownloadZip.innerHTML = `
    <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
    </svg>
    Mengemas ZIP Instan...
  `;

  try {
    const res = await fetch(`/api/download-zip/${currentJobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames: Array.from(selectedRelPaths) })
    });

    if (!res.ok) throw new Error('Gagal mengunduh file ZIP.');

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;

    const disposition = res.headers.get('content-disposition');
    let fn = 'Manhwa_Panels.zip';
    if (disposition && disposition.includes('filename=')) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match && match[1]) fn = match[1];
    }
    a.download = fn;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
  } catch (err) {
    showError(err.message);
  } finally {
    btnDownloadZip.disabled = false;
    btnDownloadZip.innerHTML = originalText;
  }
});

// 12. Lightbox Modal
window.openPreview = function (relPath, title, dim, fullUrl) {
  modalTitle.textContent = title;
  modalDim.textContent = dim;
  modalImg.src = fullUrl;
  modalDownloadBtn.href = fullUrl;
  modalDownloadBtn.download = relPath.split('/').pop();
  previewModal.classList.remove('hidden');
  document.body.classList.add('overflow-hidden');
};

modalCloseBtn.addEventListener('click', closeModal);
previewModal.addEventListener('click', (e) => {
  if (e.target === previewModal) closeModal();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !previewModal.classList.contains('hidden')) {
    closeModal();
  }
});

function closeModal() {
  previewModal.classList.add('hidden');
  modalImg.src = '';
  document.body.classList.remove('overflow-hidden');
}

// Helpers
function showProgress(title, subtitle, pct) {
  progressTitle.textContent = title;
  progressSubtitle.textContent = subtitle;
  progressPct.textContent = `${pct}%`;
  progressBarFill.style.width = `${pct}%`;
  progressCard.classList.remove('hidden');
  resultsSection.classList.add('hidden');
}

function updateProgress(title, subtitle, pct) {
  progressTitle.textContent = title;
  progressSubtitle.textContent = subtitle;
  progressPct.textContent = `${pct}%`;
  progressBarFill.style.width = `${pct}%`;
}

function hideProgress() {
  progressCard.classList.add('hidden');
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorCard.classList.remove('hidden');
  errorCard.scrollIntoView({ behavior: 'smooth' });
}

function hideError() {
  errorCard.classList.add('hidden');
}

// ==========================================
// IMAGE ENHANCER (AI UPSCALER STUDIO) LOGIC
// ==========================================

const tabNavSlicer = document.getElementById('tab-nav-slicer');
const tabNavEnhancer = document.getElementById('tab-nav-enhancer');
const viewSlicer = document.getElementById('view-slicer');
const viewEnhancer = document.getElementById('view-enhancer');

function switchView(tab) {
  if (tab === 'slicer') {
    viewSlicer.classList.remove('hidden');
    viewEnhancer.classList.add('hidden');
    tabNavSlicer.className = 'tab-btn px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-brand-600 text-white shadow';
    tabNavEnhancer.className = 'tab-btn px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 text-slate-400 hover:text-white hover:bg-slate-800';
  } else {
    viewSlicer.classList.add('hidden');
    viewEnhancer.classList.remove('hidden');
    tabNavEnhancer.className = 'tab-btn px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-gradient-to-r from-red-600 to-rose-600 text-white shadow-lg shadow-red-500/25';
    tabNavSlicer.className = 'tab-btn px-3.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 text-slate-400 hover:text-white hover:bg-slate-800';
  }
}

if (tabNavSlicer) tabNavSlicer.addEventListener('click', () => switchView('slicer'));
if (tabNavEnhancer) tabNavEnhancer.addEventListener('click', () => switchView('enhancer'));

// Enhancer Elements
const enhancerDropzone = document.getElementById('enhancer-dropzone');
const enhancerFileInput = document.getElementById('enhancer-file-input');
const enhancerSingleFileInput = document.getElementById('enhancer-single-file-input');
const btnBrowseEnhanceFiles = document.getElementById('btn-browse-enhance-files');
const btnBrowseEnhanceFolders = document.getElementById('btn-browse-enhance-folders');
const btnBrowseEnhanceModal = document.getElementById('btn-browse-enhance-modal');
const btnImportFromSlicer = document.getElementById('btn-import-from-slicer');
const enhancerFoldersCard = document.getElementById('enhancer-folders-card');
const enhancerSummaryText = document.getElementById('enhancer-summary-text');
const enhancerFolderChipsContainer = document.getElementById('enhancer-folder-chips-container');
const btnClearEnhanceFolders = document.getElementById('btn-clear-enhance-folders');

const enhancerTargetFolder = document.getElementById('enhancer-target-folder');
const btnBrowseEnhanceTarget = document.getElementById('btn-browse-enhance-target');
const btnPresetEnhanceDefault = document.getElementById('btn-preset-enhance-default');
const btnPresetEnhanceFileenhancer = document.getElementById('btn-preset-enhance-fileenhancer');
const btnPresetEnhanceDesktop = document.getElementById('btn-preset-enhance-desktop');

const enhanceModeCards = document.querySelectorAll('.enhance-mode-card');
const btnStartEnhance = document.getElementById('btn-start-enhance');
const btnStartEnhanceLabel = document.getElementById('btn-start-enhance-label');

const enhancerProgressCard = document.getElementById('enhancer-progress-card');
const enhancerProgressTitle = document.getElementById('enhancer-progress-title');
const enhancerProgressSubtitle = document.getElementById('enhancer-progress-subtitle');
const enhancerProgressPct = document.getElementById('enhancer-progress-pct');
const enhancerProgressBarFill = document.getElementById('enhancer-progress-bar-fill');
const btnCancelEnhance = document.getElementById('btn-cancel-enhance');

const enhancerSuccessCard = document.getElementById('enhancer-success-card');
const enhancerSuccessCount = document.getElementById('enhancer-success-count');
const enhancerSuccessPath = document.getElementById('enhancer-success-path');
const btnOpenEnhancedFolder = document.getElementById('btn-open-enhanced-folder');

// State
let selectedEnhanceFolders = new Map(); // path -> { folder_name, folder_path, images_count }
let currentEnhanceJobId = null;
let enhancePollInterval = null;

// Default output folder for enhancer
if (enhancerTargetFolder) {
  enhancerTargetFolder.value = 'D:\\CODING\\Manhwa Recap\\output\\Enhanced';
}

if (btnPresetEnhanceDefault) {
  btnPresetEnhanceDefault.addEventListener('click', () => {
    enhancerTargetFolder.value = 'D:\\CODING\\Manhwa Recap\\output\\Enhanced';
    showToast('Folder tujuan diset ke output/Enhanced', '📁');
  });
}

if (btnPresetEnhanceFileenhancer) {
  btnPresetEnhanceFileenhancer.addEventListener('click', () => {
    enhancerTargetFolder.value = 'D:\\File_Enhancer';
    showToast('Folder tujuan diset ke D:\\File_Enhancer', '📁');
  });
}

if (btnPresetEnhanceDesktop) {
  btnPresetEnhanceDesktop.addEventListener('click', () => {
    if (defaultFolders.desktop) {
      enhancerTargetFolder.value = `${defaultFolders.desktop}\\Manhwa_Enhanced`;
      showToast('Folder tujuan diset ke Desktop', '🖥️');
    }
  });
}

// Mode Selection Cards
enhanceModeCards.forEach(card => {
  card.addEventListener('click', () => {
    enhanceModeCards.forEach(c => {
      c.classList.remove('active', 'border-red-500/50', 'ring-1', 'ring-red-500/30', 'bg-slate-900/80');
      c.classList.add('border-slate-800', 'bg-slate-900/60');
      const radio = c.querySelector('input[type="radio"]');
      if (radio) radio.checked = false;
    });

    card.classList.add('active', 'border-red-500/50', 'ring-1', 'ring-red-500/30', 'bg-slate-900/80');
    card.classList.remove('border-slate-800', 'bg-slate-900/60');
    const r = card.querySelector('input[type="radio"]');
    if (r) r.checked = true;
  });
});

// Render Folder Chips
function renderEnhanceFolderChips() {
  if (selectedEnhanceFolders.size === 0) {
    enhancerFoldersCard.classList.add('hidden');
    btnStartEnhanceLabel.textContent = 'Mulai Tingkatkan Gambar';
    return;
  }

  enhancerFoldersCard.classList.remove('hidden');
  enhancerFolderChipsContainer.innerHTML = '';

  let totalImgs = 0;
  selectedEnhanceFolders.forEach((f, p) => {
    totalImgs += f.images_count;
    const chip = document.createElement('div');
    chip.className = 'flex items-center gap-2 bg-slate-900 border border-slate-700/80 px-3 py-1.5 rounded-xl text-xs text-slate-200 group';
    chip.innerHTML = `
      <span class="text-amber-400">📁</span>
      <span class="font-bold text-white">${f.folder_name}</span>
      <span class="text-[11px] text-red-300 font-mono">(${f.images_count} gambar)</span>
      <button type="button" class="ml-1 text-slate-400 hover:text-rose-400 p-0.5 rounded transition" title="Hapus folder ini">
        ✕
      </button>
    `;
    chip.querySelector('button').onclick = (e) => {
      e.stopPropagation();
      selectedEnhanceFolders.delete(p);
      renderEnhanceFolderChips();
    };
    enhancerFolderChipsContainer.appendChild(chip);
  });

  enhancerSummaryText.textContent = `${selectedEnhanceFolders.size} Folder • ${totalImgs} Total Gambar`;
  btnStartEnhanceLabel.textContent = `✨ Mulai Tingkatkan ${totalImgs} Gambar (${selectedEnhanceFolders.size} Folder)`;
}

// Add and Scan Folders
async function scanAndAddFolders(paths) {
  if (!paths || paths.length === 0) return;
  try {
    const res = await fetch('/api/enhancer/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_paths: paths })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Gagal memindai folder.');
    }

    const data = await res.json();
    if (data.folders.length === 0) {
      showToast('Tidak ada file gambar (.png, .jpg, .webp) di folder tersebut.', '⚠️');
      return;
    }

    data.folders.forEach(f => {
      selectedEnhanceFolders.set(f.folder_path, f);
    });

    renderEnhanceFolderChips();
    showToast(`Berhasil menambahkan ${data.folders.length} folder (${data.total_images} gambar)`, '📁');
  } catch (err) {
    showError(err.message);
  }
}

// Browse Folders using In-App Explorer Modal
if (btnBrowseEnhanceFiles) {
  btnBrowseEnhanceFiles.addEventListener('click', () => {
    if (enhancerSingleFileInput) enhancerSingleFileInput.click();
  });
}

// Helper recursively reads all files from a DataTransfer entry (handles directory pagination)
async function extractFilesFromDataTransfer(dataTransfer) {
  const items = dataTransfer.items;
  const files = [];

  const readAllDirEntries = async (dirReader) => {
    const entries = [];
    let batch;
    do {
      batch = await new Promise((resolve) => {
        dirReader.readEntries((results) => resolve(results || []), () => resolve([]));
      });
      if (batch && batch.length > 0) {
        entries.push(...batch);
      }
    } while (batch && batch.length > 0);
    return entries;
  };

  const traverseEntry = async (entry, currentFolder = '') => {
    if (!entry) return;
    if (entry.isFile) {
      try {
        const file = await new Promise((resolve, reject) => {
          entry.file(resolve, reject);
        });
        if (file && (file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name))) {
          file.targetFolder = currentFolder || 'Gambar_Tunggal';
          files.push(file);
        }
      } catch (e) {
        console.warn('Gagal membaca file dari entry:', entry.name, e);
      }
    } else if (entry.isDirectory) {
      const folderName = currentFolder ? `${currentFolder}/${entry.name}` : entry.name;
      const dirReader = entry.createReader();
      const subEntries = await readAllDirEntries(dirReader);
      for (const sub of subEntries) {
        await traverseEntry(sub, folderName);
      }
    }
  };

  if (items && items.length > 0 && items[0].webkitGetAsEntry) {
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry();
      if (entry) {
        await traverseEntry(entry);
      }
    }
  } else if (dataTransfer.files && dataTransfer.files.length > 0) {
    for (let i = 0; i < dataTransfer.files.length; i++) {
      const f = dataTransfer.files[i];
      if (f.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(f.name)) {
        f.targetFolder = 'Gambar_Tunggal';
        files.push(f);
      }
    }
  }

  return files;
}

// Upload extracted files to Enhancer staging area
async function uploadEnhancerFiles(files) {
  if (!files || files.length === 0) {
    showToast('Tidak ada file gambar (.png, .jpg, .webp) yang ditemukan.', '⚠️');
    return;
  }

  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    formData.append('files', f);
    formData.append('folders', f.targetFolder || 'Gambar_Tunggal');
  }

  try {
    const totalCount = files.length;
    showToast(`Mengunggah & menganalisis ${totalCount} gambar...`, '📤');

    const res = await fetch('/api/enhancer/upload-files', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Gagal memproses file yang diunggah.');
    }

    const data = await res.json();
    if (!data.folders || data.folders.length === 0) {
      showToast('Tidak ada gambar valid yang berhasil diproses.', '⚠️');
      return;
    }

    // Jika sebelumnya hanya ada "Gambar_Tunggal" dan pengguna sekarang memasukkan folder asli,
    // bersihkan Gambar_Tunggal sementara tersebut agar tampilan rapi
    const hasRealFolder = data.folders.some(f => f.folder_name !== 'Gambar_Tunggal');
    if (hasRealFolder) {
      for (const [key, val] of selectedEnhanceFolders.entries()) {
        if (val.folder_name === 'Gambar_Tunggal') {
          selectedEnhanceFolders.delete(key);
        }
      }
    }

    data.folders.forEach(f => {
      selectedEnhanceFolders.set(f.folder_path, f);
    });

    renderEnhanceFolderChips();
    const folderNames = data.folders.map(f => f.folder_name).join(', ');
    showToast(`Berhasil menambahkan: ${folderNames} (${data.total_images} gambar)`, '🖼️');
  } catch (err) {
    console.error('Upload enhancer files error:', err);
    showError(err.message || 'Gagal memproses file/folder.');
  }
}

// Native Windows Folder Picker
if (enhancerFileInput) {
  enhancerFileInput.addEventListener('change', async (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const rawFiles = Array.from(e.target.files).filter(f => /\.(png|jpe?g|webp)$/i.test(f.name));
      rawFiles.forEach(f => {
        const parts = f.webkitRelativePath ? f.webkitRelativePath.split('/') : [];
        f.targetFolder = parts.length > 1 ? parts.slice(0, -1).join('/') : 'Folder_Pilihan';
      });
      await uploadEnhancerFiles(rawFiles);
      e.target.value = '';
    }
  });
}

// Single / Multiple Image Input
if (enhancerSingleFileInput) {
  enhancerSingleFileInput.addEventListener('change', async (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const rawFiles = Array.from(e.target.files).filter(f => /\.(png|jpe?g|webp)$/i.test(f.name));
      rawFiles.forEach(f => {
        f.targetFolder = 'Gambar_Tunggal';
      });
      await uploadEnhancerFiles(rawFiles);
      e.target.value = '';
    }
  });
}

// Button "Pilih Folder..." -> Buka Pemilih Folder Windows
if (btnBrowseEnhanceFolders) {
  btnBrowseEnhanceFolders.addEventListener('click', () => {
    if (enhancerFileInput) enhancerFileInput.click();
  });
}

// Button "Jelajahi Drive (Explorer)" -> Buka Modal In-App Explorer
if (btnBrowseEnhanceModal) {
  btnBrowseEnhanceModal.addEventListener('click', () => {
    openFolderPickerModal('', (selectedPath) => {
      if (selectedPath) {
        scanAndAddFolders([selectedPath]);
      }
    });
    if (modalConfirmBtnLabel) {
      modalConfirmBtnLabel.textContent = 'Pilih Folder Ini untuk Di-enhance';
    }
  });
}

// Browse Target Output Folder
if (btnBrowseEnhanceTarget) {
  btnBrowseEnhanceTarget.addEventListener('click', () => {
    openFolderPickerModal(enhancerTargetFolder.value.trim(), (selectedPath) => {
      if (selectedPath) {
        enhancerTargetFolder.value = selectedPath;
        showToast(`Folder tujuan diubah: ${selectedPath}`, '📂');
      }
    });
    if (modalConfirmBtnLabel) {
      modalConfirmBtnLabel.textContent = 'Jadikan Folder Tujuan Hasil Enhance';
    }
  });
}

// Import Latest Slicer Output
if (btnImportFromSlicer) {
  btnImportFromSlicer.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/enhancer/last-slicer-folders');
      if (!res.ok) throw new Error('Gagal mengambil folder slicer terakhir.');
      const data = await res.json();
      if (!data.folders || data.folders.length === 0) {
        showToast('Belum ada sesi pemotongan panel sebelumnya.', 'ℹ️');
        return;
      }
      await scanAndAddFolders(data.folders);
    } catch (err) {
      showError(err.message);
    }
  });
}

// Clear all selected folders
if (btnClearEnhanceFolders) {
  btnClearEnhanceFolders.addEventListener('click', () => {
    selectedEnhanceFolders.clear();
    renderEnhanceFolderChips();
    showToast('Daftar folder dikosongkan', '🧹');
  });
}

// Drag & Drop Handling for Folder Zone
if (enhancerDropzone) {
  ['dragenter', 'dragover'].forEach(eventName => {
    enhancerDropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      enhancerDropzone.classList.add('border-red-500', 'bg-red-500/10', 'scale-[1.01]');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    enhancerDropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      enhancerDropzone.classList.remove('border-red-500', 'bg-red-500/10', 'scale-[1.01]');
    });
  });

  enhancerDropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    enhancerDropzone.classList.remove('border-red-500', 'bg-red-500/10', 'scale-[1.01]');

    try {
      showToast('Membaca folder & file yang diseret...', '⏳');
      const files = await extractFilesFromDataTransfer(e.dataTransfer);
      if (!files || files.length === 0) {
        showToast('Tidak ada file gambar (.png, .jpg, .webp) di dalam folder/file yang diseret.', '⚠️');
        return;
      }
      await uploadEnhancerFiles(files);
    } catch (err) {
      console.error('Error saat drop folder:', err);
      showError('Gagal memproses folder yang diseret: ' + err.message);
    }
  });
}

// Start Enhancement Action
if (btnStartEnhance) {
  btnStartEnhance.addEventListener('click', async () => {
    if (selectedEnhanceFolders.size === 0) {
      showToast('Silakan pilih atau seret setidaknya 1 folder terlebih dahulu.', '⚠️');
      return;
    }

    const folderPaths = Array.from(selectedEnhanceFolders.keys());
    const targetFolder = enhancerTargetFolder.value.trim() || 'D:\\CODING\\Manhwa Recap\\output\\Enhanced';

    // Get selected mode and scale
    const activeRadio = document.querySelector('input[name="enhance-mode"]:checked');
    const modelName = activeRadio ? activeRadio.value : 'realesrgan-x4plus-anime';
    const scale = activeRadio ? parseInt(activeRadio.getAttribute('data-scale') || '2', 10) : 2;

    enhancerProgressCard.classList.remove('hidden');
    enhancerSuccessCard.classList.add('hidden');
    enhancerProgressTitle.textContent = 'Menyiapkan GPU & Model AI...';
    enhancerProgressSubtitle.textContent = 'Menganalisis antrean gambar...';
    enhancerProgressPct.textContent = '2%';
    enhancerProgressBarFill.style.width = '2%';
    btnStartEnhance.disabled = true;

    try {
      const res = await fetch('/api/enhancer/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          folder_paths: folderPaths,
          target_folder: targetFolder,
          model_name: modelName,
          scale: scale,
          open_folder_after: true
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Gagal memulai enhancement.');
      }

      const data = await res.json();
      currentEnhanceJobId = data.job_id;
      pollEnhancerStatus(currentEnhanceJobId);

    } catch (err) {
      btnStartEnhance.disabled = false;
      enhancerProgressCard.classList.add('hidden');
      showError(err.message);
    }
  });
}

// Polling Enhancer Status
function pollEnhancerStatus(jobId) {
  if (enhancePollInterval) clearInterval(enhancePollInterval);

  enhancePollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/enhancer/status/${jobId}`);
      if (!res.ok) throw new Error('Gagal memeriksa status enhance.');
      const data = await res.json();

      enhancerProgressPct.textContent = `${data.progress || 0}%`;
      enhancerProgressBarFill.style.width = `${data.progress || 0}%`;
      enhancerProgressSubtitle.textContent = data.message || 'Memproses...';

      if (data.current_folder) {
        enhancerProgressTitle.textContent = `Meningkatkan ${data.current_folder}...`;
      }

      if (data.status === 'completed') {
        clearInterval(enhancePollInterval);
        enhancerProgressCard.classList.add('hidden');
        btnStartEnhance.disabled = false;

        // Show Success Card
        enhancerSuccessCard.classList.remove('hidden');
        enhancerSuccessCount.textContent = `${data.processed_images || 0} Gambar berhasil ditingkatkan`;
        enhancerSuccessPath.textContent = data.output_folder || enhancerTargetFolder.value;

        showToast(`Selesai! ${data.processed_images} gambar berhasil di-enhance.`, '🎉');

        if (btnOpenEnhancedFolder) {
          btnOpenEnhancedFolder.onclick = async () => {
            await fetch('/api/open-folder', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: data.output_folder })
            });
          };
        }

      } else if (data.status === 'failed' || data.status === 'cancelled') {
        clearInterval(enhancePollInterval);
        enhancerProgressCard.classList.add('hidden');
        btnStartEnhance.disabled = false;
        if (data.status === 'failed') {
          showError(data.error || data.message || 'Proses enhance gagal.');
        } else {
          showToast('Proses enhance dibatalkan.', '⏹️');
        }
      }

    } catch (err) {
      clearInterval(enhancePollInterval);
      enhancerProgressCard.classList.add('hidden');
      btnStartEnhance.disabled = false;
      showError(err.message);
    }
  }, 600);
}

// Cancel Enhancer Job
if (btnCancelEnhance) {
  btnCancelEnhance.addEventListener('click', async () => {
    if (!currentEnhanceJobId) return;
    try {
      await fetch(`/api/enhancer/cancel/${currentEnhanceJobId}`, { method: 'POST' });
      showToast('Membatalkan proses...', '⏹️');
    } catch (err) {
      console.warn('Gagal membatalkan:', err);
    }
  });
}

