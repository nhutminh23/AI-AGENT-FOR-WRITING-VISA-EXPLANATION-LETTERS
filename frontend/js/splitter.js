// Manual PDF Split (Tab 2)
// Extracted from app.js

// ==================== MANUAL PDF SPLIT (Tab ②) ====================

// State for manual split
let manualSplitState = {
  source: "upload",       // "upload" or "ai"
  pageCount: 0,
  tempId: null,            // for uploaded files
  tempPath: null,
  uploadFilename: null,
  aiFileId: null,          // for AI splitter files
  aiFilename: null,
  lastManualId: null,      // last manual split result ID
};

// Toggle source panels
document.querySelectorAll('input[name="manualSplitSource"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    manualSplitState.source = e.target.value;
    const uploadPanel = document.getElementById("manualSplitUploadPanel");
    const aiPanel = document.getElementById("manualSplitAIPanel");
    const formArea = document.getElementById("manualSplitFormArea");
    const resultArea = document.getElementById("manualSplitResultArea");
    if (uploadPanel) uploadPanel.style.display = e.target.value === "upload" ? "block" : "none";
    if (aiPanel) aiPanel.style.display = e.target.value === "ai" ? "block" : "none";
    if (formArea) formArea.style.display = "none";
    if (resultArea) resultArea.style.display = "none";
    manualSplitState.pageCount = 0;
    if (e.target.value === "ai") loadManualSplitAIFiles();
  });
});

// Load AI splitter output files into searchable grouped list
let _aiFileGroups = []; // cache for search filtering

async function loadManualSplitAIFiles() {
  const listEl = document.getElementById("manualSplitAIFileList");
  if (!listEl) return;
  listEl.innerHTML = '<div style="padding:12px; color:#888;">Đang tải...</div>';
  try {
    const res = await fetch("/api/ai-splitter/list-outputs");
    const data = await res.json();
    _aiFileGroups = data.groups || [];
    renderAIFileList("");
  } catch (e) {
    listEl.innerHTML = `<div style="padding:12px; color:red;">Lỗi: ${e.message}</div>`;
  }
}

function renderAIFileList(query) {
  const listEl = document.getElementById("manualSplitAIFileList");
  if (!listEl) return;
  const q = (query || "").toLowerCase().trim();

  if (_aiFileGroups.length === 0) {
    listEl.innerHTML = '<div style="padding:12px; color:#888;">Chưa có file đã tách.</div>';
    return;
  }

  let html = '';
  let matchCount = 0;
  for (const group of _aiFileGroups) {
    const sourceLabel = group.source_filename || group.folder_id;
    const typeIcon = group.source_type === "ai" ? "🤖" : "✂️";
    const typeBg = group.source_type === "ai" ? "#e0e7ff" : "#fef3c7";

    const filteredFiles = group.files.filter(f => {
      if (!q) return true;
      return f.filename.toLowerCase().includes(q) || sourceLabel.toLowerCase().includes(q);
    });

    if (filteredFiles.length === 0) continue;
    matchCount += filteredFiles.length;

    // Auto-open if searching, collapsed if not
    const openAttr = q ? "open" : "";
    html += `<details ${openAttr} style="border-bottom:1px solid #e5e7eb;">
      <summary style="padding:8px 10px; background:${typeBg}; cursor:pointer; font-size:0.85em; font-weight:600; user-select:none;">
        ${typeIcon} ${sourceLabel} (${filteredFiles.length} file)
      </summary>`;
    for (const f of filteredFiles) {
      const sizeMB = (f.size / 1024 / 1024).toFixed(1);
      html += `<div class="ai-file-pick-row" data-file-id="${f.file_id}" data-filename="${f.filename}"
        style="padding:8px 12px; padding-left:24px; border-bottom:1px solid #f0f0f0; cursor:pointer; display:flex; justify-content:space-between; align-items:center; transition:background 0.15s;"
        onmouseover="this.style.background='#e0e7ff'" onmouseout="this.style.background='transparent'">
        <div>
          <span style="font-size:0.9em;">${f.filename}</span>
          <small style="color:#888; margin-left:4px;">(${sizeMB} MB)</small>
        </div>
        <span style="font-size:0.8em; color:#4f46e5;">📄 Chọn</span>
      </div>`;
    }
    html += `</details>`;
  }

  if (matchCount === 0) {
    html = `<div style="padding:12px; color:#888;">Không tìm thấy file khớp "${query}"</div>`;
  }

  listEl.innerHTML = html;
}

// Search filter
const manualSplitAISearchEl = document.getElementById("manualSplitAISearch");
if (manualSplitAISearchEl) {
  manualSplitAISearchEl.addEventListener("input", (e) => {
    renderAIFileList(e.target.value);
  });
}

// Click to select file from list
document.addEventListener("click", async (e) => {
  const row = e.target.closest(".ai-file-pick-row");
  if (!row) return;
  const fileId = row.dataset.fileId;
  const filename = row.dataset.filename;
  if (!fileId || !filename) return;

  const infoEl = document.getElementById("manualSplitAIInfo");
  const formArea = document.getElementById("manualSplitFormArea");
  const resultArea = document.getElementById("manualSplitResultArea");
  if (infoEl) infoEl.textContent = `⏳ Đang đọc ${filename}...`;
  if (resultArea) resultArea.style.display = "none";

  // Highlight selected row
  document.querySelectorAll(".ai-file-pick-row").forEach(r => r.style.background = "transparent");
  row.style.background = "#c7d2fe";

  try {
    const res = await fetch("/api/manual-split/get-page-count", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: fileId, filename }),
    });
    const data = await res.json();
    if (!res.ok) { if (infoEl) infoEl.textContent = `Lỗi: ${data.error}`; return; }
    manualSplitState.pageCount = data.page_count;
    manualSplitState.aiFileId = fileId;
    manualSplitState.aiFilename = filename;
    manualSplitState.tempId = null;
    manualSplitState.tempPath = null;
    manualSplitState.uploadFilename = null;
    if (infoEl) infoEl.innerHTML = `<div style="font-size:1.1em; font-weight:700; color:#1e40af; padding:8px 0;">✅ ${filename} — ${data.page_count} trang</div>`;
    if (data.page_count <= 1) {
      if (infoEl) infoEl.innerHTML += `<div style="color:#dc2626; font-weight:600;">⚠️ File chỉ có 1 trang, không cần tách.</div>`;
      if (formArea) formArea.style.display = "none";
      return;
    }
    const maxSplits = data.page_count;
    const pageInfoEl = document.getElementById("pdfManualPageInfo");
    if (pageInfoEl) pageInfoEl.textContent = `File có ${data.page_count} trang. Tách tối đa ${maxSplits} file.`;
    if (pdfManualCountEl) { pdfManualCountEl.max = maxSplits; pdfManualCountEl.value = Math.min(parseInt(pdfManualCountEl.value)||1, maxSplits); }
    if (formArea) formArea.style.display = "block";
  } catch (err) {
    if (infoEl) infoEl.textContent = `Lỗi: ${err.message}`;
  }
});

// Upload file from computer and get page count
const manualSplitUploadBtn = document.getElementById("manualSplitUploadBtn");
if (manualSplitUploadBtn) {
  manualSplitUploadBtn.addEventListener("click", async () => {
    const fileInput = document.getElementById("manualSplitFileInput");
    const infoEl = document.getElementById("manualSplitUploadInfo");
    const formArea = document.getElementById("manualSplitFormArea");
    const resultArea = document.getElementById("manualSplitResultArea");
    if (!fileInput || !fileInput.files || !fileInput.files.length) {
      alert("Vui lòng chọn file PDF."); return;
    }
    manualSplitUploadBtn.disabled = true;
    manualSplitUploadBtn.textContent = "⏳ Đang đọc...";
    if (infoEl) infoEl.textContent = "Đang upload...";
    if (resultArea) resultArea.style.display = "none";
    try {
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      const res = await fetch("/api/manual-split/upload-get-page-count", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error}`); return; }
      manualSplitState.pageCount = data.page_count;
      manualSplitState.tempId = data.temp_id;
      manualSplitState.tempPath = data.temp_path;
      manualSplitState.uploadFilename = data.filename;
      manualSplitState.aiFileId = null;
      manualSplitState.aiFilename = null;
      if (infoEl) infoEl.innerHTML = `<div style="font-size:1.1em; font-weight:700; color:#1e40af; padding:8px 0;">✅ ${data.filename} — ${data.page_count} trang</div>`;
      if (data.page_count <= 1) {
        if (infoEl) infoEl.innerHTML += `<div style="color:#dc2626; font-weight:600;">⚠️ File chỉ có 1 trang, không cần tách.</div>`;
        if (formArea) formArea.style.display = "none";
        return;
      }
      const maxSplits = data.page_count;
      const pageInfoEl = document.getElementById("pdfManualPageInfo");
      if (pageInfoEl) pageInfoEl.textContent = `File có ${data.page_count} trang. Tách tối đa ${maxSplits} file.`;
      if (pdfManualCountEl) { pdfManualCountEl.max = maxSplits; pdfManualCountEl.value = Math.min(parseInt(pdfManualCountEl.value)||1, maxSplits); }
      if (formArea) formArea.style.display = "block";
    } catch (e) {
      if (infoEl) infoEl.textContent = `Lỗi: ${e.message}`;
    } finally {
      manualSplitUploadBtn.disabled = false;
      manualSplitUploadBtn.textContent = "📄 Đọc file";
    }
  });
}

function buildPdfManualSegments() {
  if (!pdfManualCountEl || !pdfManualSegmentsEl) return;
  const count = parseInt(pdfManualCountEl.value || "0", 10) || 0;
  const maxAllowed = Math.max(1, manualSplitState.pageCount || 20);
  const safeCount = Math.max(1, Math.min(count, maxAllowed));
  pdfManualCountEl.value = safeCount;
  const parts = [];
  for (let i = 1; i <= safeCount; i++) {
    parts.push(`
      <div class="manual-segment" data-index="${i}" style="margin-top:8px; padding:8px; border:1px dashed #e5e7eb; border-radius:6px;">
        <div class="row">
          <div>
            <label for="pdf-segmentName-${i}">File ${i} - Tên file output (không cần .pdf)</label>
            <input id="pdf-segmentName-${i}" type="text" />
          </div>
          <div>
            <label for="pdf-segmentStart-${i}">Từ trang</label>
            <input id="pdf-segmentStart-${i}" type="number" min="1" max="${manualSplitState.pageCount}" value="${i === 1 ? 1 : ''}" />
          </div>
          <div>
            <label for="pdf-segmentEnd-${i}">Đến trang</label>
            <input id="pdf-segmentEnd-${i}" type="number" min="1" max="${manualSplitState.pageCount}" />
          </div>
        </div>
      </div>
    `);
  }
  pdfManualSegmentsEl.innerHTML = parts.join("");

  // Auto-cascade: when end page changes, fill next file's start page
  const maxPage = manualSplitState.pageCount || 9999;
  for (let i = 1; i <= safeCount; i++) {
    const endEl = document.getElementById(`pdf-segmentEnd-${i}`);
    if (endEl) {
      endEl.addEventListener('input', () => {
        let val = parseInt(endEl.value, 10);
        if (isNaN(val) || val < 1) return;
        if (val > maxPage) { val = maxPage; endEl.value = val; }
        const nextStart = document.getElementById(`pdf-segmentStart-${i + 1}`);
        if (nextStart && val + 1 <= maxPage) nextStart.value = val + 1;
      });
    }
  }
}

async function runPdfManualSplit() {
  const count = parseInt(pdfManualCountEl.value || "0", 10) || 0;
  const segments = [];
  for (let i = 1; i <= count; i++) {
    const nameEl = document.getElementById(`pdf-segmentName-${i}`);
    const startEl = document.getElementById(`pdf-segmentStart-${i}`);
    const endEl = document.getElementById(`pdf-segmentEnd-${i}`);
    if (!nameEl || !startEl || !endEl) continue;
    const output_name = nameEl.value.trim();
    const start_page = parseInt(startEl.value || "0", 10);
    const end_page = parseInt(endEl.value || "0", 10) || manualSplitState.pageCount;
    if (!output_name || !start_page) continue;
    segments.push({ output_name, start_page, end_page });
  }
  if (!segments.length) {
    alert("Vui lòng nhập đầy đủ tên file và khoảng trang cho ít nhất 1 file con.");
    return;
  }

  const originalText = pdfRunSplitBtn.textContent;
  pdfRunSplitBtn.disabled = true;
  pdfRunSplitBtn.textContent = "⏳ Đang tách...";
  const resultArea = document.getElementById("manualSplitResultArea");
  const resultList = document.getElementById("manualSplitResultList");
  if (resultArea) resultArea.style.display = "none";

  try {
    let data;
    if (manualSplitState.source === "upload" && manualSplitState.tempPath) {
      // Upload source — use upload-and-split endpoint
      const fileInput = document.getElementById("manualSplitFileInput");
      if (!fileInput || !fileInput.files || !fileInput.files.length) {
        alert("File upload không còn, vui lòng chọn lại."); return;
      }
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      formData.append("segments", JSON.stringify(segments));
      const pid = getProjectId();
      if (pid) formData.append("project_id", String(pid));
      const res = await fetch("/api/manual-split/upload-and-split", { method: "POST", body: formData });
      data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error || "không xác định"}`); return; }
    } else if (manualSplitState.source === "ai" && manualSplitState.aiFileId) {
      // AI source — use existing split_manual endpoint
      const res = await fetch("/api/classifier/split_manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_file_id: manualSplitState.aiFileId,
          source_filename: manualSplitState.aiFilename,
          segments,
          project_id: getProjectId() || null,
        }),
      });
      data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error || "không xác định"}`); return; }
    } else {
      alert("Vui lòng chọn file nguồn trước."); return;
    }

    // Display results
    manualSplitState.lastManualId = data.manual_id;
    if (resultArea) resultArea.style.display = "block";
    if (resultList) {
      let html = `<div style="padding:8px 12px; background:#f0f4ff; border-radius:6px; margin-bottom:8px;">
        <strong>📁 ${data.source}</strong> → ${data.segments?.length || 0} file (${data.total_pages} trang)
        ${data.removed_original ? `<br><small style="color:#dc2626;">🗑️ Đã xóa file gốc: ${data.removed_original}</small>` : ""}
      </div>`;
      for (const seg of (data.segments || [])) {
        html += `<div style="padding:6px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center; padding-left:24px;">
          <div>
            <strong>${seg.output_name}.pdf</strong>
            <br><small style="color:#666;">Trang ${seg.start_page}-${seg.end_page}</small>
          </div>
          <div style="display:flex; gap:6px;">
            <a href="/api/ai-splitter/view/${data.manual_id}/${encodeURIComponent(seg.to)}" target="_blank"
               style="text-decoration:none; padding:4px 10px; background:#f59e0b; color:white; border-radius:4px; font-size:0.85em;">
              👁 Xem
            </a>
            <a href="/api/ai-splitter/download/${data.manual_id}/${encodeURIComponent(seg.to)}"
               style="text-decoration:none; padding:4px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.85em;">
              ⬇ Download
            </a>
          </div>
        </div>`;
      }
      resultList.innerHTML = html;
    }

    // Clear form
    if (pdfManualSegmentsEl) pdfManualSegmentsEl.innerHTML = "";
    if (pdfManualCountEl) pdfManualCountEl.value = "1";
  } catch (error) {
    alert(`Lỗi: ${error.message}`);
  } finally {
    pdfRunSplitBtn.disabled = false;
    pdfRunSplitBtn.textContent = originalText;
  }
}

// Download button for manual split results
const manualSplitDownloadBtn = document.getElementById("manualSplitDownloadBtn");
if (manualSplitDownloadBtn) {
  manualSplitDownloadBtn.addEventListener("click", () => {
    if (!manualSplitState.lastManualId) { alert("Chưa có kết quả tách."); return; }
    // Download all files as ZIP
    window.location.href = `/api/ai-splitter/download-zip/${manualSplitState.lastManualId}`;
  });
}

// Track merge files in user-specified order
let pdfMergeFilesArray = [];

function updatePdfMergeFileListDisplay() {
  if (!pdfMergeFileList || !pdfMergeFileInput) return;
  // APPEND new files to the end (preserves selection order across multiple picks)
  const newFiles = Array.from(pdfMergeFileInput.files || []);
  for (const f of newFiles) {
    // Skip duplicates (same name + same size)
    const isDup = pdfMergeFilesArray.some(existing => existing.name === f.name && existing.size === f.size);
    if (!isDup) {
      pdfMergeFilesArray.push(f);
    }
  }
  renderPdfMergeFileList();
}

function renderPdfMergeFileList() {
  if (!pdfMergeFileList) return;
  if (pdfMergeFilesArray.length === 0) {
    pdfMergeFileList.textContent = "Chưa chọn file. Chọn từng file theo thứ tự muốn ghép (file chọn trước = trang trước).";
    pdfMergeFileList.className = "hint";
    return;
  }
  pdfMergeFileList.className = "";
  const n = pdfMergeFilesArray.length;
  const btnStyle = 'padding:2px 6px; font-size:12px; cursor:pointer; border:1px solid #d1d5db; border-radius:4px; background:#fff; line-height:1;';
  let html = '<div style="font-size:0.85em; color:#6b7280; margin-bottom:4px;">📌 Kéo thả ☰ để sắp xếp | Bấm nút để di chuyển nhanh</div>';
  pdfMergeFilesArray.forEach((f, i) => {
    html += `<div class="merge-file-row" draggable="true" data-idx="${i}"
      style="display:flex; align-items:center; gap:4px; padding:6px 4px; border-bottom:1px solid #f3f4f6; border:2px solid transparent; border-radius:4px; transition:border-color 0.15s; cursor:grab;">
      <span style="cursor:grab; font-size:16px; color:#9ca3af; padding-right:2px;" title="Kéo để sắp xếp">☰</span>
      <span style="min-width:24px; font-weight:600; color:#4f46e5;">${i + 1}.</span>
      <span style="flex:1; font-size:0.93em; cursor:pointer; user-select:text;" title="Click để dùng tên này" onclick="fillMergeOutputName('${f.name}')" onmouseover="this.style.textDecoration='underline';this.style.color='#4f46e5'" onmouseout="this.style.textDecoration='none';this.style.color='inherit'">${f.name}</span>
      <button type="button" onclick="jumpMergeFile(${i},'top')" style="${btnStyle}"${i === 0 ? ' disabled' : ''} title="Lên đầu">⏫</button>
      <button type="button" onclick="jumpMergeFile(${i},'bottom')" style="${btnStyle}"${i === n - 1 ? ' disabled' : ''} title="Xuống cuối">⏬</button>
      <button type="button" onclick="jumpMergeFile(${i},'remove')" style="${btnStyle} color:#dc2626;" title="Xóa file">❌</button>
    </div>`;
  });
  pdfMergeFileList.innerHTML = html;

  // Setup HTML5 drag-and-drop (same technique as ilovepdf)
  let dragSrcIdx = null;
  const rows = pdfMergeFileList.querySelectorAll('.merge-file-row');
  rows.forEach(row => {
    row.addEventListener('dragstart', (e) => {
      dragSrcIdx = parseInt(row.dataset.idx);
      e.dataTransfer.effectAllowed = 'move';
      row.style.opacity = '0.4';
    });
    row.addEventListener('dragend', () => {
      row.style.opacity = '1';
      rows.forEach(r => r.style.borderColor = 'transparent');
    });
    row.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      rows.forEach(r => r.style.borderColor = 'transparent');
      row.style.borderColor = '#4f46e5';
    });
    row.addEventListener('dragleave', () => {
      row.style.borderColor = 'transparent';
    });
    row.addEventListener('drop', (e) => {
      e.preventDefault();
      const dropIdx = parseInt(row.dataset.idx);
      if (dragSrcIdx !== null && dragSrcIdx !== dropIdx) {
        const [item] = pdfMergeFilesArray.splice(dragSrcIdx, 1);
        pdfMergeFilesArray.splice(dropIdx, 0, item);
        renderPdfMergeFileList();
      }
      dragSrcIdx = null;
    });
  });
}

// Move a file: top, bottom, or remove
window.jumpMergeFile = function(index, action) {
  if (action === 'remove') {
    pdfMergeFilesArray.splice(index, 1);
  } else if (action === 'top') {
    const [item] = pdfMergeFilesArray.splice(index, 1);
    pdfMergeFilesArray.unshift(item);
  } else if (action === 'bottom') {
    const [item] = pdfMergeFilesArray.splice(index, 1);
    pdfMergeFilesArray.push(item);
  }
  renderPdfMergeFileList();
};

// Click a filename to fill the output name input
window.fillMergeOutputName = function(name) {
  const input = document.getElementById("pdfMergeOutputName");
  if (input) {
    // Remove .pdf extension
    input.value = name.replace(/\.pdf$/i, "");
    input.focus();
  }
};

if (pdfMergeFileInput) {
  pdfMergeFileInput.addEventListener("change", updatePdfMergeFileListDisplay);
}

const pdfClearMergeBtn = document.getElementById("pdfClearMergeBtn");
if (pdfClearMergeBtn) {
  pdfClearMergeBtn.addEventListener("click", () => {
    pdfMergeFilesArray = [];
    if (pdfMergeFileInput) pdfMergeFileInput.value = "";
    renderPdfMergeFileList();
  });
}

// ═══════════════════════════════════════════════════════════════
// SCAN SPLITTER — Split scanned PDFs by Translation Certification
// ═══════════════════════════════════════════════════════════════

(function initScanSplitter() {
  const runBtn = document.getElementById("scanSplitRunBtn");
  const fileInput = document.getElementById("scanSplitFileInput");
  const progressArea = document.getElementById("scanSplitProgressArea");
  const progressText = document.getElementById("scanSplitProgressText");
  const progressBar = document.getElementById("scanSplitProgressBar");
  const pageGrid = document.getElementById("scanSplitPageGrid");
  const errorArea = document.getElementById("scanSplitErrorArea");
  const resultArea = document.getElementById("scanSplitResultArea");
  const resultTitle = document.getElementById("scanSplitResultTitle");
  const resultList = document.getElementById("scanSplitResultList");
  const downloadZipBtn = document.getElementById("scanSplitDownloadZipBtn");

  if (!runBtn || !fileInput) return;

  let pollTimer = null;

  runBtn.addEventListener("click", async () => {
    if (!fileInput.files || fileInput.files.length === 0) {
      alert("Vui lòng chọn file PDF scan trước.");
      return;
    }
    const file = fileInput.files[0];
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Chỉ hỗ trợ file PDF.");
      return;
    }

    // Reset UI
    progressArea.style.display = "block";
    errorArea.style.display = "none";
    resultArea.style.display = "none";
    progressBar.style.width = "0%";
    progressText.textContent = "Đang upload file...";
    pageGrid.innerHTML = "";
    runBtn.disabled = true;
    runBtn.textContent = "⏳ Đang xử lý...";

    // Upload
    const formData = new FormData();
    formData.append("file", file);
    try {
      const resp = await fetch("/api/scan-splitter/split", { method: "POST", body: formData });
      const data = await resp.json();
      if (data.error) {
        showError(data.error);
        resetBtn();
        return;
      }
      // Start polling
      startPolling();
    } catch (e) {
      showError("Lỗi kết nối: " + e.message);
      resetBtn();
    }
  });

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const resp = await fetch("/api/scan-splitter/progress");
        const p = await resp.json();
        updateProgress(p);
        if (!p.running) {
          clearInterval(pollTimer);
          pollTimer = null;
          resetBtn();
          if (p.error) {
            showError(p.error);
          } else if (p.results && p.results.length > 0) {
            showResults(p);
          }
        }
      } catch (e) {
        clearInterval(pollTimer);
        pollTimer = null;
        resetBtn();
      }
    }, 500);
  }

  function updateProgress(p) {
    const total = p.total || 1;
    const done = p.done || 0;
    const pct = Math.round((done / total) * 100);
    progressBar.style.width = pct + "%";
    progressText.textContent = p.current_page || `Đang quét... ${done}/${total}`;

    // Build page grid if not yet built
    if (total > 0 && pageGrid.children.length === 0) {
      for (let i = 0; i < total; i++) {
        const cell = document.createElement("div");
        cell.style.cssText = "width:22px; height:22px; border-radius:3px; background:#e5e7eb; display:flex; align-items:center; justify-content:center; font-size:9px; color:#6b7280; transition:background 0.2s;";
        cell.textContent = i + 1;
        cell.title = `Trang ${i + 1}`;
        pageGrid.appendChild(cell);
      }
    }
    // Highlight scanned pages
    const cells = pageGrid.children;
    for (let i = 0; i < Math.min(done, cells.length); i++) {
      cells[i].style.background = "#d1d5db";
      cells[i].style.color = "#374151";
    }

    // If results available during polling, highlight cert pages
    if (p.results && p.results.length > 0) {
      p.results.forEach(r => {
        const endIdx = r.end_page - 1;
        if (endIdx < cells.length && !r.no_cert) {
          cells[endIdx].style.background = "#10b981";
          cells[endIdx].style.color = "#fff";
          cells[endIdx].textContent = "✓";
          cells[endIdx].title = `Trang ${endIdx + 1} — Xác nhận dịch ✅`;
        }
      });
    }
  }

  function showResults(p) {
    const results = p.results;
    const certCount = results.filter(r => !r.no_cert).length;
    resultTitle.textContent = `✅ Kết quả: Tìm thấy ${certCount} xác nhận dịch → ${results.length} file`;
    resultArea.style.display = "block";

    let html = "";
    results.forEach((r, i) => {
      const noCertTag = r.no_cert ? ' <span style="color:#f59e0b; font-size:0.85em;">⚠️ Không có xác nhận dịch</span>' : '';
      html += `<div style="display:flex; align-items:center; gap:8px; padding:8px 6px; border-bottom:1px solid #f3f4f6;">
        <span style="min-width:24px; font-weight:600; color:#4f46e5;">${i + 1}.</span>
        <span style="flex:1; font-size:0.93em;">📄 Hồ sơ ${i + 1} <span style="color:#6b7280;">(Trang ${r.pages}, ${r.page_count} trang)</span>${noCertTag}</span>
        <div style="display:flex; gap:4px;">
          <a href="/api/scan-splitter/view/${encodeURIComponent(r.filename)}" target="_blank"
             style="padding:4px 10px; background:#f59e0b; color:#fff; text-decoration:none; border-radius:4px; font-size:0.85em;">👁 Xem</a>
          <a href="/api/scan-splitter/download/${encodeURIComponent(r.filename)}" 
             style="padding:4px 10px; background:#4f46e5; color:#fff; text-decoration:none; border-radius:4px; font-size:0.85em;"
             download="${r.filename}">⬇ Tải</a>
        </div>
      </div>`;
    });
    resultList.innerHTML = html;

    // Highlight cert pages in grid
    const cells = pageGrid.children;
    results.forEach(r => {
      const endIdx = r.end_page - 1;
      if (endIdx < cells.length && !r.no_cert) {
        cells[endIdx].style.background = "#10b981";
        cells[endIdx].style.color = "#fff";
        cells[endIdx].textContent = "✓";
      }
    });
  }

  function showError(msg) {
    errorArea.style.display = "block";
    errorArea.textContent = "❌ " + msg;
  }

  function resetBtn() {
    runBtn.disabled = false;
    runBtn.textContent = "🔍 Quét & Tách";
  }

  if (downloadZipBtn) {
    downloadZipBtn.addEventListener("click", () => {
      window.location.href = "/api/scan-splitter/download-zip";
    });
  }
})();

async function runPdfMerge() {
  if (!pdfMergeFileInput) {
    alert("Không tìm thấy ô chọn file.");
    return;
  }
  const files = pdfMergeFilesArray.filter((f) => f.name && f.name.toLowerCase().endsWith(".pdf"));
  if (files.length === 0) {
    alert("Vui lòng chọn ít nhất 1 file PDF từ máy tính. Dùng nút ⬆⬇ để sắp xếp thứ tự.");
    return;
  }
  const output_name = (pdfMergeOutputName && pdfMergeOutputName.value || "").trim();
  if (!output_name) {
    alert("Vui lòng nhập tên file sau khi nối.");
    return;
  }
  const originalText = pdfRunMergeBtn ? pdfRunMergeBtn.textContent : "";
  if (pdfRunMergeBtn) {
    pdfRunMergeBtn.disabled = true;
    pdfRunMergeBtn.textContent = "Đang nối...";
  }
  if (pdfToolsResultEl) {
    pdfToolsResultEl.textContent = "Đang nối các file PDF...";
  }
  try {
    const formData = new FormData();
    for (const file of files) {
      formData.append("file", file);
    }
    formData.append("output_name", output_name);
    const res = await fetch("/api/pdf/merge-upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      if (pdfToolsResultEl) {
        pdfToolsResultEl.textContent = `Lỗi nối PDF: ${data.error || "không xác định"}`;
      }
      return;
    }
    const lines = [];
    lines.push("Nối PDF hoàn thành.");
    lines.push(`- Số file nguồn: ${data.file_count}`);
    lines.push(`- Tổng số trang: ${data.total_pages}`);
    lines.push(`- File kết quả: ${data.output_file}`);
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = lines.join("\n");
    }
    await loadPdfFiles();
  } catch (error) {
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Lỗi nối PDF: ${error.message}`;
    }
  } finally {
    if (pdfRunMergeBtn) {
      pdfRunMergeBtn.disabled = false;
      pdfRunMergeBtn.textContent = originalText;
    }
  }
}

async function runPdfRename() {
  const inputDir = "pdf/input";
  if (!pdfRenameSourceFileEl) {
    alert("Không tìm thấy danh sách file PDF.");
    return;
  }
  const source = pdfRenameSourceFileEl.value;
  if (!source) {
    alert("Vui lòng chọn file PDF cần đổi tên.");
    return;
  }
  const prefix = (pdfRenamePrefixEl?.value || "").trim();
  let docType = "";
  if (!prefix) {
    alert("Vui lòng chọn tiền tố loại hồ sơ.");
    return;
  }
  if (!pdfRenameDocTypeEl) {
    alert("Không tìm thấy box Tên giấy tờ.");
    return;
  }
  const selected = (pdfRenameDocTypeEl.value || "").trim();
  if (selected === "__CUSTOM__") {
    const custom = (pdfRenameDocTypeCustomEl?.value || "").trim();
    if (!custom) {
      alert("Vui lòng nhập tên giấy tờ (có thể nhập tiếng Việt để gen EN).");
      return;
    }
    docType = custom;
  } else {
    docType = selected;
  }
  if (!docType) {
    alert("Vui lòng chọn hoặc nhập tên giấy tờ.");
    return;
  }

  const originalText = pdfRunRenameBtn.textContent;
  pdfRunRenameBtn.disabled = true;
  pdfRunRenameBtn.textContent = "Đang đổi tên...";
  if (pdfToolsResultEl) {
    pdfToolsResultEl.textContent = "Đang đổi tên file PDF...";
  }

  try {
    const res = await fetch("/api/pdf/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_dir: inputDir,
        source,
        prefix,
        doc_type: docType,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (pdfToolsResultEl) {
        pdfToolsResultEl.textContent = `Lỗi đổi tên PDF: ${data.error || "không xác định"}`;
      }
      return;
    }

    if (pdfToolsResultEl) {
      const lines = [];
      lines.push("Đổi tên PDF hoàn thành.");
      lines.push(`- File cũ: ${data.source}`);
      lines.push(`- Tên mới: ${data.new_name}`);
      lines.push(`- Đường dẫn mới (tương đối với pdf/input): ${data.new_rel_path}`);
      pdfToolsResultEl.textContent = lines.join("\n");
    }

    await loadPdfFiles();
  } catch (error) {
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Lỗi đổi tên PDF: ${error.message}`;
    }
  } finally {
    pdfRunRenameBtn.disabled = false;
    pdfRunRenameBtn.textContent = originalText;
  }
}

async function genPdfRenameDocType() {
  if (!pdfRenameDocTypeCustomEl) return;
  const current = (pdfRenameDocTypeCustomEl.value || "").trim();
  if (!current) {
    alert("Vui lòng nhập nội dung tiếng Việt mô tả loại giấy tờ trước khi gen tên EN.");
    return;
  }

  if (pdfToolsResultEl) {
    pdfToolsResultEl.textContent = "Đang gọi AI để gợi ý tên tiếng Anh ngắn gọn...";
  }

  try {
    const res = await fetch("/api/pdf/rename_suggest_name", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_text: current }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (pdfToolsResultEl) {
        pdfToolsResultEl.textContent = `Lỗi gen tên EN: ${data.error || "không xác định"}`;
      }
      return;
    }

    const suggested = (data.suggested_name || "").trim();
    if (suggested) {
      if (pdfRenameDocTypeEl) {
        pdfRenameDocTypeEl.value = "__CUSTOM__";
      }
      pdfRenameDocTypeCustomEl.value = suggested;
      updatePdfRenamePreview();
    }
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Gợi ý tên EN: ${suggested}`;
    }
  } catch (error) {
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Lỗi gen tên EN: ${error.message}`;
    }
  }
}

async function genPdfMergeDocType() {
  if (!pdfMergeDocTypeCustomEl) return;
  const current = (pdfMergeDocTypeCustomEl.value || "").trim();
  if (!current) {
    alert("Vui lòng nhập nội dung tiếng Việt mô tả loại giấy tờ trước khi gen tên EN.");
    return;
  }

  if (pdfToolsResultEl) {
    pdfToolsResultEl.textContent = "Đang gọi AI để gợi ý tên tiếng Anh ngắn gọn...";
  }

  try {
    const res = await fetch("/api/pdf/rename_suggest_name", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_text: current }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (pdfToolsResultEl) {
        pdfToolsResultEl.textContent = `Lỗi gen tên EN: ${data.error || "không xác định"}`;
      }
      return;
    }

    const suggested = (data.suggested_name || "").trim();
    if (suggested) {
      if (pdfMergeDocTypeEl) {
        pdfMergeDocTypeEl.value = "__CUSTOM__";
      }
      pdfMergeDocTypeCustomEl.value = suggested;
      updatePdfMergePreview();
    }
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Gợi ý tên EN: ${suggested}`;
    }
  } catch (error) {
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Lỗi gen tên EN: ${error.message}`;
    }
  }
}

function formatClassifierResult(data) {
  const counts = data.person_counts || {};
  const copied = data.copied || [];
  const skipped = data.skipped || [];
  const totalFiles = (data.copied_count || 0) + (data.skipped_count || 0);
  const unknownCount = counts["UNKNOWN PERSON"] || 0;
  const knownCount = (data.copied_count || 0) - unknownCount;
  const personCount = Object.keys(counts).filter(k => k !== "UNKNOWN PERSON").length;

  // Compact summary bar
  let html = `<div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; align-items:center;">
    <span style="padding:6px 14px; background:#4f46e5; color:white; border-radius:8px; font-weight:700; font-size:0.9em;">
      📁 ${totalFiles} file
    </span>
    <span style="padding:6px 14px; background:#059669; color:white; border-radius:8px; font-weight:700; font-size:0.9em;">
      ✅ ${knownCount} xác định • ${personCount} người
    </span>
    ${unknownCount > 0 ? `<span style="padding:6px 14px; background:#d97706; color:white; border-radius:8px; font-weight:700; font-size:0.9em;">
      ⚠️ ${unknownCount} unknown
    </span>` : ''}
    ${(data.skipped_count || 0) > 0 ? `<span style="padding:6px 14px; background:#dc2626; color:white; border-radius:8px; font-weight:700; font-size:0.9em;">
      ❌ ${data.skipped_count} bỏ qua
    </span>` : ''}
  </div>`;

  // Group by person
  const byPerson = {};
  for (const item of copied) {
    const person = item.person_name || "UNKNOWN PERSON";
    if (!byPerson[person]) byPerson[person] = [];
    byPerson[person].push(item);
  }

  const personsSorted = Object.keys(byPerson).sort((a, b) => {
    if (a === "UNKNOWN PERSON") return 1;
    if (b === "UNKNOWN PERSON") return -1;
    return a.localeCompare(b);
  });

  // All groups collapsed by default
  for (const person of personsSorted) {
    const items = byPerson[person];
    const isUnknown = person === "UNKNOWN PERSON";
    const borderColor = isUnknown ? "#f59e0b" : "#818cf8";
    const headerBg = isUnknown ? "#fffbeb" : "#eef2ff";
    const headerColor = isUnknown ? "#92400e" : "#1e40af";
    const icon = isUnknown ? "⚠️" : "👤";

    html += `<details style="margin-bottom:4px; border:1px solid ${borderColor}; border-radius:6px; overflow:hidden;">
      <summary style="padding:8px 12px; background:${headerBg}; cursor:pointer; font-weight:600; color:${headerColor}; font-size:0.9em; user-select:none;">
        ${icon} ${person} <span style="font-weight:400; color:#6b7280;">(${items.length})</span>
      </summary>
      <div style="max-height:250px; overflow-y:auto;">`;

    for (const item of items) {
      const escapedTo = (item.to || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
      const escapedPerson = (item.person_name || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
      const escapedDoc = (item.doc_type_en || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
      html += `<div class="classifier-row" data-filepath="${escapedTo}" style="padding:5px 12px; border-bottom:1px solid #f3f4f6; font-size:0.85em;">
        <div style="display:flex; align-items:center; gap:6px;">
          <span style="color:#e2e8f0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:220px;" title="${item.source}">📄 ${item.source}</span>
          <span style="color:#94a3b8;">→</span>
          <span class="cls-doctype" style="font-weight:600; color:${isUnknown ? '#fbbf24' : '#34d399'}; white-space:nowrap;">${item.doc_type_en}</span>
          <span class="cls-destpath" style="color:#94a3b8; font-size:0.8em; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:280px;" title="${item.to}">${item.to}</span>
          <button class="cls-rename-btn" data-old-path="${escapedTo}" data-person="${escapedPerson}" data-doctype="${escapedDoc}"
                  style="margin-left:auto; flex-shrink:0; padding:2px 6px; background:transparent; color:#818cf8; border:1px solid #c7d2fe; border-radius:4px; cursor:pointer; font-size:0.85em;">
            ✏️
          </button>
        </div>
        <div class="cls-rename-form" style="display:none; margin-top:6px; padding:6px; background:#f8fafc; border-radius:4px; border:1px solid #e2e8f0;">
          <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">
            <input class="cls-rename-person" value="${escapedPerson}" placeholder="Tên người" style="flex:1; min-width:120px; padding:3px 6px; border:1px solid #d1d5db; border-radius:4px; font-size:0.9em;" />
            <input class="cls-rename-doctype" value="${escapedDoc}" placeholder="Loại giấy tờ" style="flex:1; min-width:100px; padding:3px 6px; border:1px solid #d1d5db; border-radius:4px; font-size:0.9em;" />
            <button class="cls-rename-save" style="padding:3px 10px; background:#059669; color:white; border:none; border-radius:4px; cursor:pointer; font-size:0.85em;">💾</button>
            <button class="cls-rename-cancel" style="padding:3px 10px; background:#9ca3af; color:white; border:none; border-radius:4px; cursor:pointer; font-size:0.85em;">✕</button>
          </div>
        </div>
      </div>`;
    }
    html += `</div></details>`;
  }

  // Skipped
  if (skipped.length > 0) {
    html += `<details style="margin-top:4px; border:1px solid #fca5a5; border-radius:6px; overflow:hidden;">
      <summary style="padding:8px 12px; background:#fef2f2; cursor:pointer; font-weight:600; color:#991b1b; font-size:0.9em;">
        ❌ Bỏ qua (${skipped.length})
      </summary>
      <div style="padding:6px 12px; color:#991b1b; font-size:0.85em;">
        ${skipped.map(s => `<div>• ${s}</div>`).join("")}
      </div>
    </details>`;
  }

  return html;
}
function setupClassifierRename() {
  const resultEl = classifierResultEl;
  if (!resultEl) return;
  if (resultEl._renameSetupDone) return;
  resultEl._renameSetupDone = true;

  // Toggle rename form
  resultEl.addEventListener("click", (e) => {
    const renameBtn = e.target.closest(".cls-rename-btn");
    if (renameBtn) {
      const row = renameBtn.closest(".classifier-row");
      const form = row?.querySelector(".cls-rename-form");
      if (form) form.style.display = form.style.display === "none" ? "block" : "none";
      return;
    }

    // Cancel
    const cancelBtn = e.target.closest(".cls-rename-cancel");
    if (cancelBtn) {
      const form = cancelBtn.closest(".cls-rename-form");
      if (form) form.style.display = "none";
      return;
    }

    // Save
    const saveBtn = e.target.closest(".cls-rename-save");
    const isEnterOnInput = e.type === "keydown" && e.key === "Enter" && (e.target.closest(".cls-rename-person") || e.target.closest(".cls-rename-doctype"));
    if (saveBtn || isEnterOnInput) {
      const row = (saveBtn || e.target).closest(".classifier-row");
      const actualSaveBtn = row?.querySelector(".cls-rename-save");
      if (!row) return;
      const oldPath = row.dataset.filepath;
      const personInput = row.querySelector(".cls-rename-person");
      const docInput = row.querySelector(".cls-rename-doctype");
      const newPerson = (personInput?.value || "").trim();
      const newDoc = (docInput?.value || "").trim();
      if (!newPerson) { alert("Vui lòng nhập tên người."); return; }

      if (actualSaveBtn) { actualSaveBtn.disabled = true; actualSaveBtn.textContent = "⏳..."; }

      fetch("/api/classifier/rename-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_path: oldPath,
          new_person: newPerson,
          new_doc_type: newDoc,
          temp_output: window._classifierTempOutput || "phanloai/_temp_output",
        }),
      })
        .then(r => r.json())
        .then(data => {
          if (data.status === "renamed") {
            // Update row in place
            row.dataset.filepath = data.new_path;
            const docEl = row.querySelector(".cls-doctype");
            const destEl = row.querySelector(".cls-destpath");
            const btn = row.querySelector(".cls-rename-btn");
            if (docEl) { docEl.textContent = data.doc_type_en; docEl.style.color = "#059669"; }
            if (destEl) destEl.textContent = data.new_path;
            if (btn) { btn.dataset.oldPath = data.new_path; btn.dataset.person = data.person_name; btn.dataset.doctype = data.doc_type_en; }
            row.style.background = "rgba(52, 211, 153, 0.15)";
            row.style.borderLeft = "3px solid #34d399";
            const form = row.querySelector(".cls-rename-form");
            if (form) form.style.display = "none";
          } else {
            alert("Lỗi: " + (data.error || "Không thể đổi tên"));
          }
        })
        .catch(() => alert("Lỗi kết nối server"))
        .finally(() => { if (actualSaveBtn) { actualSaveBtn.disabled = false; actualSaveBtn.textContent = "💾"; } });
    }
  });

  // Enter key on inputs triggers save
  resultEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.target.closest(".cls-rename-person") || e.target.closest(".cls-rename-doctype"))) {
      const row = e.target.closest(".classifier-row");
      if (row) row.querySelector(".cls-rename-save")?.click();
    }
  });
}

async function runClassifier() {
  const inputDir = classifierInputDirEl.value.trim() || "phanloai/input";
  const outputDir = classifierOutputDirEl.value.trim() || "phanloai/output";
  const originalText = runClassifierBtn.textContent;
  runClassifierBtn.disabled = true;
  runClassifierBtn.textContent = "Đang phân loại...";
  classifierResultEl.innerHTML = "<div style='padding:20px; text-align:center; color:#6b7280;'>⏳ AI đang phân tích và phân loại file...</div>";
  try {
    const res = await fetch("/api/classifier/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir, output_dir: outputDir }),
    });
    const data = await res.json();
    if (!res.ok) {
      classifierResultEl.innerHTML = `<div style='padding:12px; color:#dc2626;'>❌ Lỗi: ${data.error || "Không thể phân loại file."}</div>`;
      return;
    }
    classifierResultEl.innerHTML = formatClassifierResult(data);
    setupClassifierRename();
    await loadClassifierFiles();
    // Store output paths for save button
    window._classifierTempOutput = data._temp_output;
    window._classifierFinalOutput = data._final_output;
    // Persist result data for page refresh
    try { localStorage.setItem("classifierLastResult", JSON.stringify(data)); } catch(e) {}
    // Show pipeline buttons
    const pipelineBtns = document.getElementById("pipelineToInputBtns");
    if (pipelineBtns) {
      pipelineBtns.style.display = "flex";
      // Add save-to-output button if not already there
      if (!document.getElementById("saveClassifierOutputBtn")) {
        const saveBtn = document.createElement("button");
        saveBtn.id = "saveClassifierOutputBtn";
        saveBtn.textContent = "💾 Lưu vào output folder";
        saveBtn.style.cssText = "background:#059669;color:#fff;padding:10px 20px;border:none;border-radius:8px;cursor:pointer;font-size:14px;";
        saveBtn.addEventListener("click", async () => {
          const cleanInput = confirm("Sau khi lưu, xóa luôn file input gốc để tiết kiệm dung lượng?\n\n• OK = Lưu + xóa input\n• Cancel = Chỉ lưu, giữ input");
          saveBtn.disabled = true;
          saveBtn.textContent = "⏳ Đang lưu...";
          try {
            const res = await fetch("/api/classifier/save-output", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                temp_output: window._classifierTempOutput,
                output_dir: window._classifierFinalOutput,
                clean_input: cleanInput,
                input_dir: classifierInputDirEl.value.trim() || "phanloai/input",
              }),
            });
            const result = await res.json();
            if (res.ok) {
              alert(`✅ Đã lưu ${result.file_count} file vào: ${result.output_dir}\n🧹 Đã dọn temp output.${cleanInput ? '\n🗑️ Đã xóa file input gốc.' : ''}`);
              await loadClassifierFiles();
            } else {
              alert(`Lỗi: ${result.error}`);
            }
          } catch (e) {
            alert(`Lỗi: ${e.message}`);
          } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = "💾 Lưu vào output folder";
          }
        });
        pipelineBtns.appendChild(saveBtn);
      }
    }
  } catch (error) {
    classifierResultEl.textContent = `Lỗi: ${error.message}`;
  } finally {
    runClassifierBtn.disabled = false;
    runClassifierBtn.textContent = originalText;
  }
}


// ==================== AI PDF SPLITTER ====================

// Load file list from splitter_uploads
async function loadSplitterFileList() {
  const listEl = document.getElementById("splitterFileList");
  if (!listEl) return;
  // Load source mapping from server (persists across page refresh)
  try {
    const mapRes = await fetch("/api/splitter/source-mapping");
    const mapData = await mapRes.json();
    if (mapData && Object.keys(mapData).length > 0) {
      window._splitterSourceMap = { ...(window._splitterSourceMap || {}), ...mapData };
    }
  } catch(e) {}
  try {
    const pid = getProjectId();
    const url = "/api/ai-splitter/list" + (pid ? "?project_id=" + pid : "");
    const res = await fetch(url);
    const data = await res.json();
    const files = data.files || [];

    // Show/hide header buttons
    const splitAllBtn = document.getElementById("splitAllBtn");
    const deleteAllBtn = document.getElementById("deleteAllSplitterBtn");
    if (splitAllBtn) splitAllBtn.style.display = files.length > 0 ? "inline-block" : "none";
    if (deleteAllBtn) deleteAllBtn.style.display = files.length > 0 ? "inline-block" : "none";

    if (files.length === 0) {
      listEl.className = "file-list empty";
      listEl.innerHTML = "Chưa có file. Hãy quét ở Tab ⓪ rồi gửi file cần tách sang đây.";
      return;
    }
    listEl.className = "file-list";
    listEl.innerHTML = files.map(f => {
      const sizeMB = (f.size / 1024 / 1024).toFixed(1);
      const displayName = f.display_name || f.filename;
      return `<div class="file-row" style="align-items:center;">
        <div style="flex:1;">
          <span class="file-name">📄 ${displayName}</span>
          <span class="file-domain">(${sizeMB} MB)</span>
        </div>
        <div style="display:flex; gap:6px;">
          <button class="splitter-process-btn" data-filename="${f.filename}" 
                  style="padding:5px 12px; background:#4f46e5; color:#fff; border:none; border-radius:5px; cursor:pointer; font-size:12px;">
            ✂️ Tách
          </button>
          <button class="splitter-delete-btn" data-filename="${f.filename}" 
                  style="padding:5px 12px; background:#dc2626; color:#fff; border:none; border-radius:5px; cursor:pointer; font-size:12px;">
            🗑️
          </button>
        </div>
      </div>`;
    }).join("");
  } catch (e) {
    listEl.innerHTML = `Lỗi: ${e.message}`;
  }
}

// Delete single file
async function deleteSplitterFile(filename) {
  if (!confirm(`Xóa file "${filename}"?`)) return;
  try {
    await fetch("/api/ai-splitter/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    });
    loadSplitterFileList();
  } catch (e) { alert(`Lỗi: ${e.message}`); }
}

// Delete all files
async function deleteAllSplitter() {
  if (!confirm("Xóa TẤT CẢ file trong danh sách chờ tách?")) return;
  try {
    const res = await fetch("/api/ai-splitter/delete-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: getProjectId() || null }),
    });
    const data = await res.json();
    alert(`✅ Đã xóa ${data.deleted_count} file.`);
    loadSplitterFileList();
  } catch (e) { alert(`Lỗi: ${e.message}`); }
}

// Split all files sequentially with combined results
async function splitAllFiles() {
  const listEl = document.getElementById("splitterFileList");
  const btns = listEl ? listEl.querySelectorAll(".splitter-process-btn") : [];
  if (btns.length === 0) { alert("Không có file để tách."); return; }

  const splitAllBtn = document.getElementById("splitAllBtn");
  if (splitAllBtn) { splitAllBtn.disabled = true; splitAllBtn.textContent = "⏳ Đang tách..."; }

  const filenames = Array.from(btns).map(b => b.dataset.filename);
  const totalFiles = filenames.length;

  // Create progress panel in the splitter results area
  const progressDiv = document.getElementById("splitterProgress");
  const statusText = document.getElementById("splitterStatus");
  const classificationsCard = document.getElementById("classificationsCard");
  const classificationsDiv = document.getElementById("classificationsDiv");
  const resultsCard = document.getElementById("splitterResultsCard");
  const resultsDiv = document.getElementById("splitterResultsDiv");

  // Show overall progress
  if (progressDiv) progressDiv.style.display = "block";
  if (classificationsCard) classificationsCard.style.display = "none";
  if (resultsCard) resultsCard.style.display = "none";

  // Accumulate all output files from all processed files
  const allOutputFiles = []; // {file_id, filename, output_files}
  const allClassifications = []; // accumulated classifications with source filename
  let completedCount = 0;

  for (let i = 0; i < filenames.length; i++) {
    const fname = filenames[i];
    if (splitAllBtn) splitAllBtn.textContent = `⏳ ${i + 1}/${totalFiles}: ${fname}`;
    if (statusText) statusText.textContent = `📄 [${i + 1}/${totalFiles}] Đang tách: ${fname}...`;

    // Update progress bar
    const progressBar = document.getElementById("splitterProgressBar");
    const progressText = document.getElementById("splitterProgressText");
    if (progressBar) { progressBar.value = Math.round((i / totalFiles) * 100); progressBar.max = 100; }
    if (progressText) progressText.textContent = `File ${i + 1}/${totalFiles}`;

    try {
      const res = await fetch("/api/ai-splitter/process-local", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: fname, project_id: getProjectId() || null }),
      });
      const data = await res.json();
      if (!res.ok) { console.error(`Error: ${data.error}`); continue; }

      const fileId = data.file_id;

      // Poll until this file is done — show live status
      await new Promise((resolve) => {
        let dots = 0;
        const checkDone = setInterval(async () => {
          try {
            const statusRes = await fetch(`/api/ai-splitter/status/${fileId}`);
            const statusData = await statusRes.json();

            // Live progress update
            dots = (dots + 1) % 4;
            const dotStr = ".".repeat(dots);
            const statusMap = {
              converting: `🔄 Chuyển PDF → ảnh${dotStr}`,
              classifying: `🤖 Phân loại trang ${statusData.current_page || "?"}/${statusData.page_count || "?"}${dotStr}`,
              splitting: `✂️ Đang tách file${dotStr}`,
              processing: `⚙️ Đang xử lý${dotStr}`,
            };
            if (statusText) {
              statusText.textContent = `📄 [${i + 1}/${totalFiles}] ${fname} — ${statusMap[statusData.status] || statusData.status}`;
            }

            // Update sub-progress bar
            if (statusData.page_count > 0 && progressBar) {
              const filePct = (statusData.current_page || 0) / statusData.page_count;
              const overallPct = Math.round(((i + filePct) / totalFiles) * 100);
              progressBar.value = overallPct;
            }

            if (statusData.status === "completed") {
              clearInterval(checkDone);
              completedCount++;
              // Collect this file's output files
              if (statusData.output_files && statusData.output_files.length > 0) {
                allOutputFiles.push({
                  file_id: fileId,
                  source_filename: fname,
                  output_files: statusData.output_files,
                });
              }
              // Collect classifications
              if (statusData.classifications) {
                for (const c of statusData.classifications) {
                  allClassifications.push({ ...c, source_file: fname });
                }
              }
              // Cập nhật ngay phần "Tất cả file đã tách" sau mỗi file tách xong
              await loadOutputHistory();
              resolve();
            } else if (statusData.status === "error") {
              clearInterval(checkDone);
              console.error(`Error splitting ${fname}: ${statusData.error}`);
              resolve();
            }
          } catch { clearInterval(checkDone); resolve(); }
        }, 1500);
      });

    } catch (e) { console.error(`Error splitting ${fname}:`, e); }
  }

  // All done — show combined results
  if (progressBar) { progressBar.value = 100; }
  if (progressText) progressText.textContent = "100%";
  if (statusText) statusText.textContent = `✅ Đã tách xong ${completedCount}/${totalFiles} file!`;

  // Render combined output files grouped by source file
  if (resultsCard && resultsDiv && allOutputFiles.length > 0) {
    resultsCard.style.display = "block";
    let html = "";
    for (const group of allOutputFiles) {
      html += `<div style="padding:8px 12px; background:#f0f4ff; border-radius:6px; margin-bottom:8px;">
        <strong>📁 ${group.source_filename}</strong> → ${group.output_files.length} file
        <a href="/api/ai-splitter/download-zip/${group.file_id}" 
           style="margin-left:8px; text-decoration:none; padding:3px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.8em;">
          ⬇ Download ZIP
        </a>
      </div>`;
      for (const f of group.output_files) {
        const pages = f.pages.join(", ");
        html += `<div style="padding:6px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center; padding-left:24px;">
          <div>
            <strong>${f.filename}</strong>
            <br><small style="color:#666;">${f.document_type} · 👤 ${f.person_name} · ${f.pages.length} trang (${pages})</small>
          </div>
          <div style="display:flex; gap:6px;">
            <a href="/api/ai-splitter/view/${group.file_id}/${encodeURIComponent(f.filename)}" target="_blank"
               style="text-decoration:none; padding:4px 10px; background:#f59e0b; color:white; border-radius:4px; font-size:0.8em;">
              👁 Xem
            </a>
            <a href="/api/ai-splitter/download/${group.file_id}/${encodeURIComponent(f.filename)}"
               style="text-decoration:none; padding:4px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.8em;">
              ⬇
            </a>
          </div>
        </div>`;
      }
    }
    resultsDiv.innerHTML = html;
  }

  if (splitAllBtn) { splitAllBtn.disabled = false; splitAllBtn.textContent = "✂️ Tách tất cả"; }
  loadOutputHistory();
}

// Refresh button
const refreshSplitterListBtn = document.getElementById("refreshSplitterListBtn");
if (refreshSplitterListBtn) {
  refreshSplitterListBtn.addEventListener("click", loadSplitterFileList);
}

// Split-all button
const splitAllBtn2 = document.getElementById("splitAllBtn");
if (splitAllBtn2) {
  splitAllBtn2.addEventListener("click", splitAllFiles);
}

// Delete-all button
const deleteAllSplitterBtn = document.getElementById("deleteAllSplitterBtn");
if (deleteAllSplitterBtn) {
  deleteAllSplitterBtn.addEventListener("click", deleteAllSplitter);
}

// Event delegation for per-file buttons
document.addEventListener("click", async (e) => {
  // Tách button
  const processBtn = e.target.closest(".splitter-process-btn");
  if (processBtn) {
    const filename = processBtn.dataset.filename;
    if (!filename) return;
    processBtn.disabled = true;
    processBtn.textContent = "⏳...";
    try {
      const res = await fetch("/api/ai-splitter/process-local", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, project_id: getProjectId() || null }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(`Lỗi: ${data.error}`);
        processBtn.disabled = false;
        processBtn.textContent = "✂️ Tách";
        return;
      }
      window.dispatchEvent(new CustomEvent("splitter-start", { detail: { file_id: data.file_id, filename: data.filename } }));
    } catch (err) {
      alert(`Lỗi: ${err.message}`);
      processBtn.disabled = false;
      processBtn.textContent = "✂️ Tách";
    }
    return;
  }

  // Delete button
  const deleteBtn = e.target.closest(".splitter-delete-btn");
  if (deleteBtn) {
    const filename = deleteBtn.dataset.filename;
    if (filename) deleteSplitterFile(filename);
    return;
  }
});

(function initAISplitter() {
  const uploadBtn = document.getElementById("splitterUploadBtn");
  const fileInput = document.getElementById("splitterFileInput");
  const progressDiv = document.getElementById("splitterProgress");
  const progressBar = document.getElementById("splitterProgressBar");
  const progressText = document.getElementById("splitterProgressText");
  const statusText = document.getElementById("splitterStatus");
  const classificationsCard = document.getElementById("splitterClassificationsCard");
  const classificationsDiv = document.getElementById("splitterClassifications");
  const resultsCard = document.getElementById("splitterResultsCard");
  const resultsDiv = document.getElementById("splitterResults");
  const downloadAllBtn = document.getElementById("splitterDownloadAllBtn");

  if (!uploadBtn) return; // safety check

  let currentFileId = null;
  let currentFilename = null;
  let pollTimer = null;

  const DOC_ICONS = {
    Passport: "🛂", Birth_Certificate: "👶", Marriage_Certificate: "💍",
    Contract: "📝", Agreement: "📝", Decision: "📄", Account_Statement: "🏦",
    Social_Insurance_Record: "📋", Power_of_Attorney: "⚖️", CCCD: "🆔",
    Business_License: "💼", Receipt_Voucher: "🧾", Price_Quotation: "💰",
    Registration_Form: "📑", Commitment_Letter: "✉️",
  };

  function getIcon(docType) {
    return DOC_ICONS[docType] || "📄";
  }

  uploadBtn.addEventListener("click", async () => {
    if (!fileInput.files || !fileInput.files.length) {
      alert("Vui lòng chọn file PDF.");
      return;
    }

    const file = fileInput.files[0];
    uploadBtn.disabled = true;
    uploadBtn.textContent = "Đang upload...";
    progressDiv.style.display = "block";
    statusText.textContent = "Đang upload file...";
    progressBar.value = 0;
    progressText.textContent = "0%";
    classificationsCard.style.display = "none";
    resultsCard.style.display = "none";

    try {
      // 1. Upload
      const formData = new FormData();
      formData.append("file", file);
      const pid = getProjectId();
      if (pid) formData.append("project_id", String(pid));
      const uploadRes = await fetch("/api/ai-splitter/upload", { method: "POST", body: formData });
      const uploadData = await uploadRes.json();
      if (uploadData.error) {
        statusText.textContent = `Lỗi: ${uploadData.error}`;
        uploadBtn.disabled = false;
        uploadBtn.textContent = "📤 Upload & Tách";
        return;
      }

      currentFileId = uploadData.file_id;
      currentFilename = uploadData.filename || file.name;
      statusText.textContent = `Đã upload ${uploadData.filename} (${uploadData.page_count} trang). Đang xử lý...`;

      // 2. Start processing
      await fetch(`/api/ai-splitter/process/${currentFileId}`, { method: "POST" });

      // 3. Poll status
      startPolling();
    } catch (err) {
      statusText.textContent = `Lỗi: ${err.message}`;
      uploadBtn.disabled = false;
      uploadBtn.textContent = "📤 Upload & Tách";
    }
  });

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(checkStatus, 1000);
  }

  // Listen for process-local events (from file list Tách buttons)
  window.addEventListener("splitter-start", (e) => {
    const { file_id, filename } = e.detail;
    currentFileId = file_id;
    currentFilename = filename;
    progressDiv.style.display = "block";
    statusText.textContent = `Đang tách ${filename}...`;
    progressBar.value = 0;
    progressText.textContent = "0%";
    classificationsCard.style.display = "none";
    resultsCard.style.display = "none";
    startPolling();
  });

  async function checkStatus() {
    if (!currentFileId) return;
    try {
      const res = await fetch(`/api/ai-splitter/status/${currentFileId}`);
      const data = await res.json();

      // Update progress
      const pct = data.page_count > 0
        ? Math.round((data.current_page / data.page_count) * 100) : 0;
      progressBar.value = pct;
      progressBar.max = 100;
      progressText.textContent = `${pct}%`;

      const statusMap = {
        converting: "Đang chuyển PDF thành ảnh...",
        classifying: `Đang phân loại trang ${data.current_page}/${data.page_count}...`,
        splitting: "Đang tách file...",
        processing: "Đang xử lý...",
      };
      statusText.textContent = statusMap[data.status] || data.status;

      // Show live classifications
      if (data.classifications && data.classifications.length > 0) {
        renderClassifications(data.classifications);
      }

      // Completed
      if (data.status === "completed") {
        clearInterval(pollTimer);
        progressBar.value = 100;
        progressText.textContent = "100%";
        statusText.textContent = `✅ Hoàn thành! Đã tách thành ${data.output_files.length} file.`;
        renderOutputFiles(data.output_files);
        await loadOutputHistory();
        uploadBtn.disabled = false;
        uploadBtn.textContent = "📤 Upload & Tách";
      } else if (data.status === "error") {
        clearInterval(pollTimer);
        statusText.textContent = `❌ Lỗi: ${data.error}`;
        uploadBtn.disabled = false;
        uploadBtn.textContent = "📤 Upload & Tách";
      }
    } catch (err) {
      console.error("Poll error:", err);
    }
  }

  function renderClassifications(cls) {
    classificationsCard.style.display = "block";
    classificationsDiv.innerHTML = cls.map((c) => {
      const icon = getIcon(c.document_type_en);
      const cont = c.is_continuation ? ' <span style="color:#888;font-size:0.85em;">↳ cont.</span>' : "";
      return `<div style="padding:4px 8px; border-bottom:1px solid #f0f0f0; font-size:0.9em;">
        <strong>P${c.page}</strong> ${icon} ${c.document_type_en}${cont}
        <span style="color:#666; margin-left:8px;">👤 ${c.person_name_en}</span>
      </div>`;
    }).join("");
    // Auto-scroll to bottom
    classificationsDiv.scrollTop = classificationsDiv.scrollHeight;
  }

  function renderOutputFiles(files) {
    resultsCard.style.display = "block";
    // Determine if we have original path info for save-to-source
    const sourceMap = window._splitterSourceMap || {};
    // Try to find original path from source mapping for current file
    let originalPath = '';
    for (const [stored, orig] of Object.entries(sourceMap)) {
      // Match by original filename (strip p{id}__ prefix)
      const cleanStored = stored.replace(/^p\d+__/, '');
      if (currentFilename && (stored === currentFilename || cleanStored === currentFilename
          || stored.includes(currentFilename) || cleanStored === currentFilename.replace(/^p\d+__/, ''))) {
        originalPath = orig;
        break;
      }
    }
    
    resultsDiv.innerHTML = files.map((f) => {
      const icon = getIcon(f.document_type);
      const pages = f.pages.join(", ");
      return `<div style="padding:8px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center;">
        <div>
          ${icon} <strong>${f.filename}</strong>
          <br><small style="color:#666;">${f.document_type} · 👤 ${f.person_name} · ${f.pages.length} trang (${pages})</small>
        </div>
        <div style="display:flex; gap:6px;">
          <a href="/api/ai-splitter/view/${currentFileId}/${encodeURIComponent(f.filename)}" target="_blank"
             style="text-decoration:none; padding:4px 12px; background:#f59e0b; color:white; border-radius:4px; font-size:0.85em;">
            👁 Xem
          </a>
          <a href="/api/ai-splitter/download/${currentFileId}/${encodeURIComponent(f.filename)}"
             style="text-decoration:none; padding:4px 12px; background:#4f46e5; color:white; border-radius:4px; font-size:0.85em;">
            ⬇ Download
          </a>
        </div>
      </div>`;
    }).join("");
    
    // Add "Save to source folder" button if we have original path
    if (originalPath) {
      const saveDiv = document.createElement('div');
      saveDiv.style.cssText = 'padding:12px; text-align:center; border-top:2px solid #e5e7eb;';
      saveDiv.innerHTML = `
        <button id="saveToSourceBtn" style="padding:8px 20px; background:#16a34a; color:white; border:none; border-radius:6px; cursor:pointer; font-size:0.95em; font-weight:600;">
          💾 Lưu ${files.length} file về thư mục gốc (xóa file cũ)
        </button>
        <div style="font-size:0.8em; color:#6b7280; margin-top:4px;">📂 ${originalPath}</div>
      `;
      resultsDiv.appendChild(saveDiv);
      document.getElementById('saveToSourceBtn').addEventListener('click', async () => {
        const btn = document.getElementById('saveToSourceBtn');
        if (!confirm(`Lưu ${files.length} file đã tách về thư mục gốc?\n\n• Xóa file gốc: ${originalPath.split(/[\\/]/).pop()}\n• Lưu ${files.length} file mới vào cùng thư mục`)) return;
        btn.disabled = true;
        btn.textContent = '⏳ Đang lưu...';
        try {
          const res = await fetch('/api/splitter/save-to-source', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_id: currentFileId, original_path: originalPath }),
          });
          const data = await res.json();
          if (!res.ok) { alert(`Lỗi: ${data.error}`); btn.disabled = false; btn.textContent = '💾 Lưu về thư mục gốc'; return; }
          btn.textContent = `✅ Đã lưu ${data.saved_count} file!`;
          btn.style.background = '#6b7280';
          let msg = `✅ Đã lưu ${data.saved_count} file về thư mục gốc!`;
          if (data.deleted_original) msg += `\n🗑 Đã xóa file gốc: ${data.original_name}`;
          msg += `\n📂 Thư mục: ${data.target_dir}`;
          if (data.errors && data.errors.length > 0) msg += `\n⚠️ ${data.errors.length} lỗi`;
          alert(msg);
        } catch (e) {
          alert(`Lỗi: ${e.message}`);
          btn.disabled = false;
          btn.textContent = '💾 Lưu về thư mục gốc';
        }
      });
    }
  }

  downloadAllBtn.addEventListener("click", () => {
    if (!currentFileId) return;
    window.location.href = `/api/ai-splitter/download-zip/${currentFileId}`;
  });
})();

