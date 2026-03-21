// Output History
// Extracted from app.js

// ==================== OUTPUT HISTORY (persistent across F5) ====================

async function loadOutputHistory() {
  const listEl = document.getElementById("splitterOutputHistoryList");
  if (!listEl) return;
  try {
    const pid = getProjectId();
    const url = "/api/ai-splitter/list-outputs" + (pid ? "?project_id=" + pid : "");
    const res = await fetch(url);
    const data = await res.json();
    const groups = data.groups || [];
    if (groups.length === 0) {
      listEl.innerHTML = '<div class="hint">Chưa có file nào đã tách. Hãy tách file ở Tab ① hoặc Tab ②.</div>';
      return;
    }
    let html = '';
    let totalFiles = 0;
    // Merge toolbar
    html += `<div id="mergeToolbar" style="display:none; padding:10px 12px; background:#fef3c7; border:2px solid #f59e0b; border-radius:8px; margin-bottom:10px; position:sticky; top:0; z-index:10;">
      <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
        <span id="mergeCount" style="font-weight:600;">0 file đã chọn</span>
        <input type="text" id="mergeOutputName" placeholder="Tên file sau khi gộp (mặc định = file đầu tiên)" style="flex:1; min-width:200px; padding:6px 10px; border:1px solid #d1d5db; border-radius:4px;" />
        <button id="mergeSelectedBtn" style="padding:8px 16px; background:#4f46e5; color:#fff; border:none; border-radius:6px; cursor:pointer; font-weight:600;">📎 Gộp file</button>
        <button id="clearMergeBtn" style="padding:8px 12px; background:#6b7280; color:#fff; border:none; border-radius:6px; cursor:pointer;">✕ Bỏ chọn</button>
      </div>
    </div>`;

    for (const group of groups) {
      const sourceLabel = group.source_filename || group.folder_id;
      const typeLabel = group.source_type === 'ai'
        ? `🤖 AI: ${sourceLabel}`
        : `✂️ Thủ công: ${sourceLabel}`;
      const typeBg = group.source_type === 'ai' ? '#e0e7ff' : '#fef3c7';
      html += `<div style="padding:8px 12px; background:${typeBg}; border-radius:6px; margin-bottom:4px;">
        <strong>${typeLabel}</strong> — ${group.files.length} file
      </div>`;
      for (const f of group.files) {
        const sizeMB = (f.size / 1024 / 1024).toFixed(1);
        totalFiles++;
        html += `<div style="padding:6px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center; padding-left:12px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <input type="checkbox" class="merge-check" data-file-id="${f.file_id}" data-filename="${f.filename}" style="width:18px; height:18px; cursor:pointer;" />
            <span class="merge-order-badge" style="display:none; width:20px; height:20px; background:#4f46e5; color:white; border-radius:50%; font-size:0.7em; font-weight:700; align-items:center; justify-content:center;"></span>
            <div>
              <strong>${f.filename}</strong>
              <small style="color:#888; margin-left:6px;">(${sizeMB} MB)</small>
            </div>
          </div>
          <div style="display:flex; gap:6px;">
            <a href="/api/ai-splitter/view/${f.file_id}/${encodeURIComponent(f.filename)}" target="_blank"
               style="text-decoration:none; padding:4px 10px; background:#f59e0b; color:white; border-radius:4px; font-size:0.8em;">
              👁 Xem
            </a>
            <a href="/api/ai-splitter/download/${f.file_id}/${encodeURIComponent(f.filename)}"
               style="text-decoration:none; padding:4px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.8em;">
              ⬇
            </a>
          </div>
        </div>`;
      }
    }
    listEl.innerHTML = `<div class="hint" style="margin-bottom:8px;">Tổng: ${totalFiles} file trong ${groups.length} nhóm · ☑️ Tick chọn file cần gộp</div>` + html;

    // Wire up merge checkbox events
    setupMergeCheckboxes();
  } catch (e) {
    listEl.innerHTML = `Lỗi: ${e.message}`;
  }
}

function setupMergeCheckboxes() {
  const toolbar = document.getElementById("mergeToolbar");
  const countEl = document.getElementById("mergeCount");
  const nameInput = document.getElementById("mergeOutputName");
  if (!toolbar) return;

  // Track click order (not DOM order)
  let mergeOrder = [];

  function updateToolbar() {
    if (mergeOrder.length >= 2) {
      toolbar.style.display = "block";
      countEl.textContent = `${mergeOrder.length} file đã chọn`;
      // Default name = first clicked file's name (without .pdf)
      if (!nameInput.dataset.userEdited) {
        nameInput.value = (mergeOrder[0]?.filename || "").replace(/\.pdf$/i, "");
      }
    } else {
      toolbar.style.display = "none";
    }
    // Show order badges
    document.querySelectorAll(".merge-check").forEach(cb => {
      const badge = cb.parentElement.querySelector(".merge-order-badge");
      const idx = mergeOrder.findIndex(m => m.fileId === cb.dataset.fileId && m.filename === cb.dataset.filename);
      if (badge) {
        if (idx >= 0) {
          badge.textContent = idx + 1;
          badge.style.display = "inline-flex";
        } else {
          badge.style.display = "none";
        }
      }
    });
  }

  document.querySelectorAll(".merge-check").forEach(cb => {
    cb.addEventListener("change", () => {
      const entry = { fileId: cb.dataset.fileId, filename: cb.dataset.filename };
      if (cb.checked) {
        mergeOrder.push(entry);
      } else {
        mergeOrder = mergeOrder.filter(m => !(m.fileId === entry.fileId && m.filename === entry.filename));
        // Reset name default when unchecking
        if (mergeOrder.length > 0 && !nameInput.dataset.userEdited) {
          nameInput.value = (mergeOrder[0]?.filename || "").replace(/\.pdf$/i, "");
        }
      }
      updateToolbar();
    });
  });

  // Track manual name edits
  if (nameInput) {
    nameInput.addEventListener("input", () => { nameInput.dataset.userEdited = "true"; });
  }

  // Clear selection
  const clearBtn = document.getElementById("clearMergeBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      document.querySelectorAll(".merge-check:checked").forEach(cb => { cb.checked = false; });
      mergeOrder = [];
      toolbar.style.display = "none";
      if (nameInput) { nameInput.value = ""; delete nameInput.dataset.userEdited; }
      updateToolbar();
    });
  }

  // Merge button — uses mergeOrder (click order)
  const mergeBtn = document.getElementById("mergeSelectedBtn");
  if (mergeBtn) {
    mergeBtn.addEventListener("click", async () => {
      if (mergeOrder.length < 2) { alert("Chọn ít nhất 2 file để gộp."); return; }
      const files = mergeOrder.map(m => ({ file_id: m.fileId, filename: m.filename }));
      const outputName = (nameInput?.value || "").trim() || mergeOrder[0]?.filename?.replace(/\.pdf$/i, "") || "Merged";

      const fileList = mergeOrder.map((m, i) => `  ${i+1}. ${m.filename}`).join("\n");
      if (!confirm(`Gộp ${mergeOrder.length} file theo thứ tự:\n${fileList}\n\nTên file output: ${outputName}.pdf\n\nBấm OK để xác nhận.`)) return;

      mergeBtn.disabled = true;
      mergeBtn.textContent = "⏳ Đang gộp...";
      try {
        const res = await fetch("/api/ai-splitter/merge-outputs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ files, output_name: outputName }),
        });
        const result = await res.json();
        if (!res.ok) { alert(`Lỗi: ${result.error}`); return; }
        alert(`✅ Đã gộp ${mergeOrder.length} file → ${result.merged_file} (${result.total_pages} trang)`);
        mergeOrder = [];
        if (nameInput) { nameInput.value = ""; delete nameInput.dataset.userEdited; }
        await loadOutputHistory();
      } catch (e) { alert(`Lỗi: ${e.message}`); }
      finally {
        mergeBtn.disabled = false;
        mergeBtn.textContent = "📎 Gộp file";
      }
    });
  }
}

// Refresh output history
const refreshOutputHistoryBtn = document.getElementById("refreshOutputHistoryBtn");
if (refreshOutputHistoryBtn) {
  refreshOutputHistoryBtn.addEventListener("click", loadOutputHistory);
}

// Clear all outputs
const clearAllOutputsBtn = document.getElementById("clearAllOutputsBtn");
if (clearAllOutputsBtn) {
  clearAllOutputsBtn.addEventListener("click", async () => {
    if (!confirm("Xóa TẤT CẢ kết quả đã tách (AI + thủ công)?\nHành động này không thể hoàn tác!")) return;
    clearAllOutputsBtn.disabled = true;
    clearAllOutputsBtn.textContent = "⏳ Đang xóa...";
    try {
      const res = await fetch("/api/ai-splitter/clear-outputs", { method: "POST" });
      const data = await res.json();
      alert(`✅ Đã xóa ${data.deleted_count} mục.`);
      await loadOutputHistory();
      // Also hide the current results card
      const resultsCard = document.getElementById("splitterResultsCard");
      if (resultsCard) resultsCard.style.display = "none";
    } catch (e) { alert(`Lỗi: ${e.message}`); }
    finally {
      clearAllOutputsBtn.disabled = false;
      clearAllOutputsBtn.textContent = "🗑️ Xóa tất cả kết quả";
    }
  });
}

// Save all outputs to input folder
const saveOutputToInputBtn = document.getElementById("saveOutputToInputBtn");
if (saveOutputToInputBtn) {
  saveOutputToInputBtn.addEventListener("click", async () => {
    // Get target dir from precheck input field
    const precheckInput = document.getElementById("precheckInputDir");
    const targetDir = precheckInput ? precheckInput.value.trim() : "input";
    if (!confirm(`Lưu tất cả file đã tách vào thư mục "${targetDir}"?\n\nFile gốc (đã tách) sẽ bị xóa khỏi thư mục đích để tránh trùng lặp.`)) return;
    saveOutputToInputBtn.disabled = true;
    saveOutputToInputBtn.textContent = "⏳ Đang lưu...";
    try {
      const res = await fetch("/api/ai-splitter/save-to-input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_dir: targetDir, delete_originals: true }),
      });
      const data = await res.json();
      if (data.error) { alert(`Lỗi: ${data.error}`); return; }
      let msg = `✅ Đã lưu ${data.count} file vào "${data.target_dir}"!`;
      if (data.originals_deleted && data.originals_deleted.length > 0) {
        msg += `\n🗑 Đã xóa ${data.originals_deleted.length} file gốc: ${data.originals_deleted.join(", ")}`;
      }
      alert(msg);
    } catch (e) { alert(`Lỗi: ${e.message}`); }
    finally {
      saveOutputToInputBtn.disabled = false;
      saveOutputToInputBtn.textContent = "💾 Lưu vào thư mục gốc";
    }
  });
}


