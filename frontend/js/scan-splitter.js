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
      const baseName = r.filename.replace(/\.pdf$/i, "");
      html += `<div id="scanRow-${i}" style="display:flex; align-items:center; gap:8px; padding:8px 6px; border-bottom:1px solid #f3f4f6; flex-wrap: wrap;">
        <span style="min-width:24px; font-weight:600; color:#4f46e5;">${i + 1}.</span>
        <span style="flex:0 0 auto; font-size:0.93em;">📄 <span style="color:#6b7280;">(Trang ${r.pages}, ${r.page_count} trang)</span>${noCertTag}</span>
        <input type="text" id="scanRename-${i}" value="${baseName}" data-original="${r.filename}"
               style="flex:1; min-width:200px; padding:4px 8px; border:1px solid #cbd5e1; border-radius:4px; font-size:0.88em; background:#1e293b; color:#e2e8f0;"
               title="Đổi tên file"/>
        <div style="display:flex; gap:4px; flex-shrink:0;">
          <button onclick="window._scanRenameFile(${i})"
             style="padding:4px 10px; background:#10b981; color:#fff; border:none; border-radius:4px; font-size:0.85em; cursor:pointer;" title="Đổi tên">✏️ Đổi tên</button>
          <a id="scanView-${i}" href="/api/scan-splitter/view/${encodeURIComponent(r.filename)}" target="_blank"
             style="padding:4px 10px; background:#f59e0b; color:#fff; text-decoration:none; border-radius:4px; font-size:0.85em;">👁 Xem</a>
          <a id="scanDl-${i}" href="/api/scan-splitter/download/${encodeURIComponent(r.filename)}" 
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

  // Global rename handler for scan split results
  window._scanRenameFile = async function(idx) {
    const input = document.getElementById(`scanRename-${idx}`);
    if (!input) return;
    const oldFilename = input.dataset.original;
    let newName = input.value.trim();
    if (!newName) { alert("Tên file không được để trống!"); return; }
    if (!newName.toLowerCase().endsWith(".pdf")) newName += ".pdf";
    if (newName === oldFilename) return; // No change

    try {
      const resp = await fetch("/api/scan-splitter/rename", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ old_filename: oldFilename, new_filename: newName })
      });
      const data = await resp.json();
      if (!resp.ok) { alert(data.error || "Rename failed"); return; }

      // Update stored filename
      const finalName = data.new_filename;
      input.dataset.original = finalName;
      input.value = finalName.replace(/\.pdf$/i, "");

      // Update view/download links
      const viewLink = document.getElementById(`scanView-${idx}`);
      const dlLink = document.getElementById(`scanDl-${idx}`);
      if (viewLink) viewLink.href = `/api/scan-splitter/view/${encodeURIComponent(finalName)}`;
      if (dlLink) {
        dlLink.href = `/api/scan-splitter/download/${encodeURIComponent(finalName)}`;
        dlLink.download = finalName;
      }

      // Brief green flash to indicate success
      input.style.borderColor = "#10b981";
      setTimeout(() => { input.style.borderColor = "#cbd5e1"; }, 1500);
    } catch (e) {
      alert("Lỗi đổi tên: " + e.message);
    }
  };

  if (downloadZipBtn) {
    downloadZipBtn.addEventListener("click", () => {
      window.location.href = "/api/scan-splitter/download-zip";
    });
  }
})();
