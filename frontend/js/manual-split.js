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

