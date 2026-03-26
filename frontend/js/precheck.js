// Pre-check / Process Functions
// Extracted from app.js

// ==================== PRE-CHECK / PROCESS FUNCTIONS ====================

let precheckFolders = []; // store scan results globally (folder-grouped)

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

    precheckFolders = data.folders || [];
    progressDiv.style.display = "none";
    resultsCard.style.display = "block";

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
        // Show sub_path if file is in a subfolder (not directly in person folder)
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
              ${f.needs_split ? `<div style="font-size:0.75em; color:#f87171; margin-top:2px;">${f.doc_count} giấy tờ: ${(f.doc_types||[]).join(', ')}</div>` : ''}
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

    // Detect merge groups (files with similar names: strip numbers and suffixes)
    detectMergeGroups();

    // Initialize column resize handles
    initColumnResize();

    // Show/hide buttons
    const applyBtn = document.getElementById("applyRenameBtn");
    const sendMultiBtn = document.getElementById("sendMultiToSplitterBtn");
    if (applyBtn) applyBtn.style.display = data.total_files > 0 ? "inline-block" : "none";
    if (sendMultiBtn) sendMultiBtn.style.display = data.multi_doc_count > 0 ? "inline-block" : "none";

  } catch (e) {
    clearInterval(progressInterval);
    statusText.textContent = `Lỗi: ${e.message}`;
  } finally {
    scanBtn.disabled = false;
    scanBtn.textContent = "🔍 Quét & Phân loại";
  }
}

