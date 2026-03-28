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

