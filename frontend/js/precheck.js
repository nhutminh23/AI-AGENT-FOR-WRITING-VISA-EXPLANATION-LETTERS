// Pre-check / Process Functions
// Extracted from app.js

// ==================== PRE-CHECK / PROCESS FUNCTIONS ====================

let precheckFolders = []; // store scan results globally (folder-grouped)
const PRECHECK_SNAPSHOT_KEY = "precheck_snapshot_v1";
const PRECHECK_SNAPSHOT_MAX_AGE_MS = 1000 * 60 * 60 * 24; // 24h

function _collectPrecheckRowDrafts() {
  const rows = document.querySelectorAll("#precheckResults tr[data-filepath]");
  const drafts = {};

  rows.forEach((row) => {
    const filePath = row.dataset.filepath;
    if (!filePath) return;

    const docTypeInput = row.querySelector("td:nth-child(3) input");
    const suggestedInput = row.querySelector("td:last-child input");

    drafts[filePath] = {
      doc_type: docTypeInput ? docTypeInput.value : "",
      suggested_name: suggestedInput ? suggestedInput.value : "",
      doc_disabled: !!(docTypeInput && docTypeInput.disabled),
      suggested_disabled: !!(suggestedInput && suggestedInput.disabled),
    };
  });

  return drafts;
}

function _applyPrecheckRowDrafts(drafts) {
  if (!drafts || typeof drafts !== "object") return;

  const rows = document.querySelectorAll("#precheckResults tr[data-filepath]");
  rows.forEach((row) => {
    const filePath = row.dataset.filepath;
    if (!filePath || !drafts[filePath]) return;

    const draft = drafts[filePath];
    const docTypeInput = row.querySelector("td:nth-child(3) input");
    const suggestedInput = row.querySelector("td:last-child input");

    if (docTypeInput && typeof draft.doc_type === "string") {
      docTypeInput.value = draft.doc_type;
    }
    if (suggestedInput && typeof draft.suggested_name === "string") {
      suggestedInput.value = draft.suggested_name;
    }

    if (docTypeInput && typeof draft.doc_disabled === "boolean") {
      docTypeInput.disabled = draft.doc_disabled;
    }
    if (suggestedInput && typeof draft.suggested_disabled === "boolean") {
      suggestedInput.disabled = draft.suggested_disabled;
      if (suggestedInput.disabled) {
        suggestedInput.style.background = "rgba(16,185,129,0.2)";
        suggestedInput.style.color = "#6ee7b7";
      }
    }
  });
}

function _bindPrecheckAutosave() {
  if (window._precheckAutosaveBound) return;

  const resultsDiv = document.getElementById("precheckResults");
  if (!resultsDiv) return;

  resultsDiv.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (!target.id.startsWith("doctype_") && !target.id.startsWith("suggested_")) return;

    if (typeof savePrecheckSnapshot === "function") {
      savePrecheckSnapshot(window._precheckLastScanData || null);
    }
  });

  window._precheckAutosaveBound = true;
}

function savePrecheckSnapshot(scanData) {
  try {
    const data = scanData || window._precheckLastScanData;
    if (!data || !Array.isArray(data.folders)) return;

    const applyBtn = document.getElementById("applyRenameBtn");
    const sendMultiBtn = document.getElementById("sendMultiToSplitterBtn");

    const payload = {
      version: 1,
      saved_at: Date.now(),
      input_dir: (document.getElementById("precheckInputDir")?.value || "input").trim(),
      scan_data: data,
      row_drafts: _collectPrecheckRowDrafts(),
      ui_state: {
        apply_disabled: !!(applyBtn && applyBtn.disabled),
        apply_text: applyBtn ? applyBtn.textContent : "",
        apply_display: applyBtn ? applyBtn.style.display : "",
        send_multi_display: sendMultiBtn ? sendMultiBtn.style.display : "",
      },
    };

    localStorage.setItem(PRECHECK_SNAPSHOT_KEY, JSON.stringify(payload));
  } catch (e) {
    console.warn("Could not save precheck snapshot:", e);
  }
}

function clearPrecheckSnapshot() {
  try {
    localStorage.removeItem(PRECHECK_SNAPSHOT_KEY);
  } catch (e) {
    console.warn("Could not clear precheck snapshot:", e);
  }
}

async function _hasRealFilesInInput(inputDir = "input") {
  const res = await fetch(`/api/files?input_dir=${encodeURIComponent(inputDir)}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "Không đọc được danh sách file input");
  }

  const files = Array.isArray(data.files) ? data.files : [];
  return files.some((f) => {
    const name = String(f?.name || "");
    return name && !name.startsWith(".") && !name.startsWith("_") && name !== "_meta.json";
  });
}

function _renderPrecheckResults(data, options = {}) {
  const progressDiv = document.getElementById("precheckProgress");
  const resultsCard = document.getElementById("precheckResultsCard");
  const summaryDiv = document.getElementById("precheckSummary");
  const resultsDiv = document.getElementById("precheckResults");
  const statusText = document.getElementById("precheckStatusText");
  if (!summaryDiv || !resultsDiv || !resultsCard) return;

  precheckFolders = data.folders || [];
  window._precheckLastScanData = data;

  if (progressDiv) progressDiv.style.display = "none";
  resultsCard.style.display = "block";

  const oldAlerts = document.querySelectorAll(".precheck-quota-alert");
  oldAlerts.forEach((node) => node.remove());

  // Summary
  const translateInfo = data.translate_count > 0
    ? ` &nbsp;|&nbsp; 📝 Bản dịch: <strong style="color:#60a5fa;">${data.translate_count}</strong>` : '';
  summaryDiv.innerHTML = `
      📁 Tổng: <strong>${data.total_files}</strong> file &nbsp;|&nbsp;
      ✅ OK: <strong style="color:#4ade80;">${data.clean_count}</strong> &nbsp;|&nbsp;
      ⚠️ Cần tách: <strong style="color:#f87171;">${data.multi_doc_count}</strong>${translateInfo}
    `;

  // Quota exhausted alert
  if (data.quota_exhausted) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'precheck-quota-alert';
    alertDiv.style.cssText = 'background:rgba(220,38,38,0.1); border:2px solid rgba(220,38,38,0.4); border-radius:8px; padding:12px 16px; margin:8px 0 12px 0; color:#fca5a5;';
    alertDiv.innerHTML = `
        <strong>⚠️ API Key hết quota!</strong><br>
        <span style="font-size:0.9em;">
          OpenAI API đã hết hạn mức sử dụng. <strong>${data.quota_error_count}/${data.total_files}</strong> file không thể phân loại bằng AI.<br>
          Các file bị ảnh hưởng sẽ được phân loại dựa trên tên file (có thể kém chính xác hơn).<br>
          👉 Kiểm tra tại: <a href="https://platform.openai.com/account/billing" target="_blank" style="color:#93c5fd;">platform.openai.com/account/billing</a>
        </span>
      `;
    summaryDiv.parentElement.insertBefore(alertDiv, summaryDiv.nextSibling);
  }

  // Results table grouped by folder
  let html = '';
  let fileIdx = 0;
  for (const folder of precheckFolders) {
    html += `<div style="margin-bottom:20px;">
        <h3 style="margin:0 0 8px 0; padding:8px 12px; background:rgba(99,102,241,0.15); border:1px solid rgba(99,102,241,0.3); border-radius:8px; font-size:0.95em; color:#a5b4fc;">
          📁 ${folder.folder_name} <span style="color:#94a3b8; font-weight:normal; font-size:0.85em;">→ ${folder.person_name}</span>
        </h3>
        <table class="precheck-table" style="width:100%; border-collapse:collapse; font-size:0.88em; table-layout:fixed;">
          <thead>
            <tr style="background:rgba(51,65,85,0.6); text-align:left;">
              <th class="resizable-th" style="padding:6px 8px; border-bottom:2px solid rgba(148,163,184,0.3); width:80px; position:relative; color:#cbd5e1;">Trạng thái<div class="col-resize-handle"></div></th>
              <th class="resizable-th" style="padding:6px 8px; border-bottom:2px solid rgba(148,163,184,0.3); width:25%; position:relative; color:#cbd5e1;">File gốc<div class="col-resize-handle"></div></th>
              <th class="resizable-th" style="padding:6px 8px; border-bottom:2px solid rgba(148,163,184,0.3); width:25%; position:relative; color:#cbd5e1;">Loại giấy tờ (AI)<div class="col-resize-handle"></div></th>
              <th style="padding:6px 8px; border-bottom:2px solid rgba(148,163,184,0.3); color:#cbd5e1;">Tên mới gợi ý</th>
            </tr>
          </thead>
          <tbody>`;

    for (const f of folder.files) {
      const status = f.is_translate
        ? '<span style="background:#1e3a5f; color:#60a5fa; padding:2px 8px; border-radius:4px; font-weight:600; font-size:0.85em;">📝 Dịch</span>'
        : f.needs_split
        ? '<span style="background:#5f1e1e; color:#f87171; padding:2px 8px; border-radius:4px; font-weight:600; font-size:0.85em;">⚠️ Ghép</span>'
        : '<span style="background:#1e3a2a; color:#4ade80; padding:2px 8px; border-radius:4px; font-weight:600; font-size:0.85em;">✅ OK</span>';
      const rowBg = f.needs_split ? "background:rgba(220,38,38,0.08);" : f.is_translate ? "background:rgba(59,130,246,0.08);" : "";
      const uid = `f${fileIdx++}`;
      const subInfo = (f.sub_path && f.sub_path !== f.filename)
        ? `<div style="font-size:0.7em; color:#94a3b8; margin-top:1px;">📂 ${f.sub_path}</div>` : '';

      html += `
          <tr style="${rowBg} border-bottom:1px solid rgba(148,163,184,0.15);" data-filepath="${f.path}" data-person="${folder.person_name}" data-ext="${f.ext}" data-filename="${f.filename}" data-needs-split="${f.needs_split ? 'true' : 'false'}">
            <td style="padding:6px 8px;">${status}</td>
            <td style="padding:6px 8px; overflow:hidden; text-overflow:ellipsis; color:#e2e8f0;" title="${f.path}">${f.filename}${subInfo}</td>
            <td style="padding:6px 8px; overflow:hidden;">
              <input type="text" id="doctype_${uid}" value="${f.doc_type_en || 'DOCUMENT'}"
                     style="width:100%; box-sizing:border-box; padding:4px 6px; border:1px solid rgba(148,163,184,0.3); border-radius:4px; font-size:0.9em; background:rgba(30,41,59,0.8); color:#e2e8f0;"
                     oninput="updateSuggestedName(this)" />
              ${f.needs_split ? `<div style="font-size:0.75em; color:#f87171; margin-top:2px;">${f.doc_count} giấy tờ: ${(f.doc_types || []).join(', ')}</div>` : ''}
            </td>
            <td style="padding:6px 8px; overflow:hidden;">
              <input type="text" id="suggested_${uid}" value="${f.suggested_name || f.filename}"
                     style="width:100%; box-sizing:border-box; padding:4px 6px; border:1px solid rgba(148,163,184,0.3); border-radius:4px; font-size:0.9em; background:rgba(30,41,59,0.6); color:#f1f5f9;" />
            </td>
          </tr>`;
    }
    html += '</tbody></table></div>';
  }
  resultsDiv.innerHTML = html;

  detectMergeGroups();
  initColumnResize();

  const applyBtn = document.getElementById("applyRenameBtn");
  const sendMultiBtn = document.getElementById("sendMultiToSplitterBtn");
  if (applyBtn) applyBtn.style.display = data.total_files > 0 ? "inline-block" : "none";
  if (sendMultiBtn) sendMultiBtn.style.display = data.multi_doc_count > 0 ? "inline-block" : "none";

  if (options.rowDrafts) {
    _applyPrecheckRowDrafts(options.rowDrafts);
  }

  if (options.uiState) {
    if (applyBtn) {
      if (typeof options.uiState.apply_display === "string") {
        applyBtn.style.display = options.uiState.apply_display;
      }
      if (typeof options.uiState.apply_text === "string" && options.uiState.apply_text.trim()) {
        applyBtn.textContent = options.uiState.apply_text;
      }
      if (typeof options.uiState.apply_disabled === "boolean") {
        applyBtn.disabled = options.uiState.apply_disabled;
        if (applyBtn.disabled) {
          applyBtn.style.background = "#6b7280";
        }
      }
    }
    if (sendMultiBtn && typeof options.uiState.send_multi_display === "string") {
      sendMultiBtn.style.display = options.uiState.send_multi_display;
    }
  }

  if (options.fromCache && statusText) {
    statusText.textContent = "✅ Đã khôi phục dữ liệu đang làm dở sau khi tải lại trang.";
  }

  _bindPrecheckAutosave();
}

async function restorePrecheckSnapshot() {
  try {
    const raw = localStorage.getItem(PRECHECK_SNAPSHOT_KEY);
    if (!raw) return false;

    const snapshot = JSON.parse(raw);
    if (!snapshot || !snapshot.scan_data || !Array.isArray(snapshot.scan_data.folders)) {
      return false;
    }

    const savedAt = Number(snapshot.saved_at || 0);
    if (savedAt > 0 && Date.now() - savedAt > PRECHECK_SNAPSHOT_MAX_AGE_MS) {
      clearPrecheckSnapshot();
      return false;
    }

    const inputDir = (snapshot.input_dir || "input").trim() || "input";
    try {
      const hasRealFiles = await _hasRealFilesInInput(inputDir);
      if (!hasRealFiles) {
        clearPrecheckSnapshot();
        return false;
      }
    } catch (e) {
      console.warn("Could not verify input before snapshot restore:", e);
    }

    _renderPrecheckResults(snapshot.scan_data, {
      rowDrafts: snapshot.row_drafts || {},
      uiState: snapshot.ui_state || {},
      fromCache: true,
    });

    // Re-check Push-to-Drive visibility after UI restore.
    if (typeof checkDriveFolderStatus === "function") {
      Promise.resolve(checkDriveFolderStatus()).catch((err) => {
        console.warn("Could not refresh Drive button after restore:", err);
      });
      setTimeout(() => {
        Promise.resolve(checkDriveFolderStatus()).catch(() => {});
      }, 1200);
    }

    return true;
  } catch (e) {
    console.warn("Could not restore precheck snapshot:", e);
    return false;
  }
}

window.savePrecheckSnapshot = savePrecheckSnapshot;
window.restorePrecheckSnapshot = restorePrecheckSnapshot;
window.clearPrecheckSnapshot = clearPrecheckSnapshot;

window.addEventListener("load", async () => {
  await restorePrecheckSnapshot();
});

async function precheckScan() {
  const inputDir = document.getElementById("precheckInputDir").value.trim() || "input";
  const scanBtn = document.getElementById("precheckScanBtn");
  const progressDiv = document.getElementById("precheckProgress");
  const statusText = document.getElementById("precheckStatusText");
  const resultsCard = document.getElementById("precheckResultsCard");
  const summaryDiv = document.getElementById("precheckSummary");
  const resultsDiv = document.getElementById("precheckResults");

  scanBtn.disabled = true;
  scanBtn.textContent = "⏳ Đang quét...";
  progressDiv.style.display = "block";
  statusText.textContent = "AI đang quét & phân loại tất cả file... (có thể mất vài phút)";
  resultsCard.style.display = "none";

  // Poll progress every 1.5s for real-time updates
  const progressInterval = setInterval(async () => {
    try {
      const pRes = await fetch("/api/precheck/progress");
      const prog = await pRes.json();
      if (prog.running && prog.total > 0) {
        const pct = Math.round((prog.done / prog.total) * 100);
        statusText.textContent = `📄 Đang xử lý: ${prog.current_file || '...'} (${prog.done}/${prog.total} — ${pct}%)`;
      }
    } catch (e) { /* ignore */ }
  }, 1500);

  try {
    const res = await fetch("/api/precheck/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir }),
    });
    clearInterval(progressInterval);
    const data = await res.json();
    if (!res.ok) {
      statusText.textContent = `Lỗi: ${data.error}`;
      return;
    }

    _renderPrecheckResults(data);
    savePrecheckSnapshot(data);

  } catch (e) {
    clearInterval(progressInterval);
    statusText.textContent = `Lỗi: ${e.message}`;
  } finally {
    scanBtn.disabled = false;
    scanBtn.textContent = "🔍 Quét & Phân loại";
  }
}

