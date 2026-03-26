// Column Resize
// Extracted from app.js

// ==================== COLUMN RESIZE ====================
function initColumnResize() {
  document.querySelectorAll('.col-resize-handle').forEach(handle => {
    handle.addEventListener('mousedown', function(e) {
      e.preventDefault();
      const th = this.parentElement;
      const table = th.closest('table');
      const startX = e.pageX;
      const startW = th.offsetWidth;
      this.classList.add('active');

      const onMouseMove = (ev) => {
        const diff = ev.pageX - startX;
        const newW = Math.max(50, startW + diff);
        th.style.width = newW + 'px';
      };
      const onMouseUp = () => {
        this.classList.remove('active');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      };
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });
  });
}

// Auto-update suggested name when user edits doc_type
function updateSuggestedName(inputEl) {
  const row = inputEl.closest("tr");
  if (!row) return;
  const person = row.dataset.person || "UNKNOWN";
  const origExt = row.dataset.ext || "";
  const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'];
  const outExt = IMAGE_EXTS.includes(origExt.toLowerCase()) ? '.pdf' : origExt;
  const docType = inputEl.value.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '');
  const suggestedInput = row.querySelector('td:last-child input');
  if (suggestedInput) {
    suggestedInput.value = `${person}_${docType}${outExt}`;
  }
}

// Apply rename to all files
async function applyRename() {
  const applyBtn = document.getElementById("applyRenameBtn");
  const renameProgress = document.getElementById("renameProgress");
  const renameStatus = document.getElementById("renameStatusText");

  // Collect all rename pairs from the table (SKIP files that need splitting)
  const rows = document.querySelectorAll("#precheckResults tr[data-filepath]");
  const renames = [];
  let skippedSplit = 0;
  rows.forEach(row => {
    const path = row.dataset.filepath;
    const suggestedInput = row.querySelector('td:last-child input');
    const newName = suggestedInput ? suggestedInput.value.trim() : "";
    // Skip files flagged as needs_split — they must be split first
    if (row.dataset.needsSplit === 'true') {
      skippedSplit++;
      return;
    }
    if (path && newName) {
      renames.push({ path, new_name: newName });
    }
  });

  if (renames.length === 0 && skippedSplit > 0) {
    alert(`⚠️ Tất cả ${skippedSplit} file đều cần tách trước.\nHãy tách file ở Tab ① trước rồi quay lại.`);
    return;
  }
  if (renames.length === 0) { alert("Không có file nào để đổi tên."); return; }
  if (skippedSplit > 0) {
    alert(`ℹ️ Đã bỏ qua ${skippedSplit} file cần tách.\nChỉ đổi tên ${renames.length} file OK.`);
  }

  applyBtn.disabled = true;
  applyBtn.textContent = "⏳ Đang đổi tên...";
  renameProgress.style.display = "block";
  renameStatus.textContent = `Đang đổi tên ${renames.length} file...`;

  try {
    const res = await fetch("/api/processor/apply-rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ renames }),
    });
    const data = await res.json();
    if (!res.ok) {
      renameStatus.textContent = `Lỗi: ${data.error}`;
      return;
    }

    renameProgress.style.display = "none";
    const converted = (data.renamed || []).filter(r => r.converted).length;
    const msg = `✅ Đã đổi tên ${data.renamed_count} file thành công!` +
      (converted > 0 ? ` 📄 ${converted} file ảnh đã convert sang PDF.` : '') +
      (data.error_count > 0 ? ` ⚠️ ${data.error_count} file lỗi.` : '');
    alert(msg);

    // Update table: show new names as "File gốc" and disable inputs
    if (data.renamed && data.renamed.length > 0) {
      for (const r of data.renamed) {
        rows.forEach(row => {
          const suggestedInput = row.querySelector('td:last-child input');
          if (suggestedInput && suggestedInput.value.trim() === r.new) {
            // Update the filename cell
            const filenameCell = row.querySelector('td:nth-child(2)');
            if (filenameCell) filenameCell.textContent = r.new;
            // Update the filepath for splitter
            row.dataset.filepath = r.path;
            // Disable inputs since rename is done
            const docTypeInput = row.querySelector('td:nth-child(3) input');
            if (docTypeInput) docTypeInput.disabled = true;
            suggestedInput.disabled = true;
            suggestedInput.style.background = 'rgba(16,185,129,0.2)'; suggestedInput.style.color = '#6ee7b7';
          }
        });
      }
    }

    applyBtn.textContent = "✅ Đã đổi tên xong!";
    applyBtn.style.background = "#6b7280";
    applyBtn.disabled = true;

  } catch (e) {
    renameStatus.textContent = `Lỗi: ${e.message}`;
  }
}


// ==================== MERGE GROUP DETECTION ====================

function getBaseName(filename) {
  // Strip extension
  const dotIdx = filename.lastIndexOf('.');
  const name = dotIdx > 0 ? filename.substring(0, dotIdx) : filename;
  // Strip trailing numbers and separators: "BHXH 1" -> "BHXH", "BHXH3" -> "BHXH", "doc (2)" -> "doc"
  return name
    .replace(/\s*\(\d+\)\s*$/, '')  // remove trailing (1), (2)
    .replace(/[\s._-]*\d+\s*$/, '') // remove trailing numbers with separators
    .trim()
    .toLowerCase();
}

function detectMergeGroups() {
  // Find all tables in the results
  const tables = document.querySelectorAll('#precheckResults table');
  window._mergeGroups = {};  // Reset merge groups
  tables.forEach((table, tableIdx) => {
    const rows = table.querySelectorAll('tr[data-filepath]');
    if (rows.length < 2) return;

    // Group by base name (SCOPED per table/person)
    const groups = {};
    rows.forEach(row => {
      const filename = row.dataset.filename || '';
      const base = getBaseName(filename);
      if (!groups[base]) groups[base] = [];
      groups[base].push({
        path: row.dataset.filepath,
        filename: filename,
        person: row.dataset.person || '',
        row: row,
      });
    });

    // Find groups with 2+ files
    for (const [base, files] of Object.entries(groups)) {
      if (files.length < 2) continue;
      // Highlight the group rows
      files.forEach(f => {
        f.row.style.borderLeft = '3px solid #f59e0b';
        f.row.style.background = 'rgba(245,158,11,0.1)';
      });
      // CRITICAL: include tableIdx in groupId to scope per person/folder
      const groupId = `grp_t${tableIdx}_${base.replace(/[^a-z0-9]/g, '_')}`;
      // Add a merge button row after the last file in the group
      const lastRow = files[files.length - 1].row;
      const mergeRow = document.createElement('tr');
      mergeRow.innerHTML = `
        <td colspan="4" style="padding:6px 8px; text-align:right;">
          <span class="merge-badge" data-group="${groupId}" style="color:#f59e0b; font-size:0.85em; margin-right:8px;">📎 ${files.length} file giống tên "${files[0].filename.replace(/[\s._-]*\d+|\s*\(\d+\)/g, '').trim()}"</span>
          <button onclick="openMergeModal('${groupId}')" 
                  style="padding:4px 12px; background:#f59e0b; color:white; border:none; border-radius:4px; cursor:pointer; font-size:0.85em;"
                  data-merge-group="${groupId}">
            📎 Gộp thành 1 PDF
          </button>
        </td>`;
      // Store group data
      mergeRow.dataset.mergeGroupId = groupId;
      window._mergeGroups[groupId] = files.map(f => ({ path: f.path, filename: f.filename, person: f.person }));
      lastRow.parentNode.insertBefore(mergeRow, lastRow.nextSibling);
    }
  });
}

function openMergeModal(groupId) {
  const group = (window._mergeGroups || {})[groupId];
  if (!group || group.length < 2) return;

  // Create modal overlay
  const overlay = document.createElement('div');
  overlay.id = 'mergeModalOverlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;';

  const person = group[0].person || 'MERGED';
  const baseClean = getBaseName(group[0].filename).toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '');
  const defaultName = `${person}_${baseClean}.pdf`;

  let listHtml = '';
  group.forEach((f, i) => {
    listHtml += `
      <div class="merge-item" draggable="true" data-idx="${i}" data-path="${f.path}"
           style="padding:8px 12px; margin:4px 0; background:rgba(51,65,85,0.8); border:1px solid rgba(148,163,184,0.3); border-radius:6px; cursor:grab; display:flex; align-items:center; gap:8px; color:#e2e8f0;">
         <span style="color:#94a3b8; font-size:1.1em; cursor:grab;">☰</span>
         <span style="flex:1; color:#e2e8f0;">${f.filename}</span>
         <button onclick="moveMergeItem(this, -1)" style="border:none;background:none;cursor:pointer;font-size:1em;">⬆️</button>
         <button onclick="moveMergeItem(this, 1)" style="border:none;background:none;cursor:pointer;font-size:1em;">⬇️</button>
      </div>`;
  });

  overlay.innerHTML = `
    <div style="background:#1e293b; border:1px solid rgba(148,163,184,0.3); border-radius:12px; padding:24px; width:500px; max-width:90vw; max-height:80vh; overflow-y:auto; box-shadow:0 20px 60px rgba(0,0,0,0.5); color:#e2e8f0;">
      <h3 style="margin:0 0 16px 0; font-size:1.1em; color:#f1f5f9;">📎 Gộp ${group.length} file thành 1 PDF</h3>
      <p style="color:#94a3b8; font-size:0.85em; margin:0 0 12px 0;">Kéo thả hoặc dùng nút ⬆️⬇️ để sắp thứ tự trang:</p>
      <div id="mergeItemList" style="margin-bottom:16px;">
        ${listHtml}
      </div>
      <div style="margin-bottom:16px;">
        <label style="font-size:0.85em; color:#94a3b8;">Tên file output:</label>
        <input type="text" id="mergeOutputName" value="${defaultName}" 
               style="width:100%; padding:6px 10px; border:1px solid rgba(148,163,184,0.3); border-radius:6px; margin-top:4px; font-size:0.9em; background:rgba(30,41,59,0.8); color:#e2e8f0;" />
      </div>
      <div style="display:flex; gap:8px; justify-content:flex-end;">
        <button onclick="closeMergeModal()" style="padding:8px 16px; background:rgba(71,85,105,0.8); color:#e2e8f0; border:none; border-radius:6px; cursor:pointer;">Hủy</button>
        <button onclick="executeMerge('${groupId}')" id="mergeConfirmBtn"
                style="padding:8px 16px; background:#f59e0b; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold;">
          📎 Gộp ngay
        </button>
      </div>
    </div>`;

  document.body.appendChild(overlay);

  // Setup drag and drop
  setupMergeDragDrop();
}

function moveMergeItem(btn, direction) {
  const item = btn.closest('.merge-item');
  const list = item.parentNode;
  const items = [...list.querySelectorAll('.merge-item')];
  const idx = items.indexOf(item);
  if (direction === -1 && idx > 0) {
    list.insertBefore(item, items[idx - 1]);
  } else if (direction === 1 && idx < items.length - 1) {
    list.insertBefore(items[idx + 1], item);
  }
}

function setupMergeDragDrop() {
  const list = document.getElementById('mergeItemList');
  if (!list) return;
  let dragEl = null;
  list.addEventListener('dragstart', e => {
    dragEl = e.target.closest('.merge-item');
    if (dragEl) {
      dragEl.style.opacity = '0.5';
      e.dataTransfer.effectAllowed = 'move';
    }
  });
  list.addEventListener('dragend', e => {
    if (dragEl) dragEl.style.opacity = '1';
    dragEl = null;
  });
  list.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const target = e.target.closest('.merge-item');
    if (target && target !== dragEl) {
      const rect = target.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      if (e.clientY < midY) {
        list.insertBefore(dragEl, target);
      } else {
        list.insertBefore(dragEl, target.nextSibling);
      }
    }
  });
}

function closeMergeModal() {
  const overlay = document.getElementById('mergeModalOverlay');
  if (overlay) overlay.remove();
}

async function executeMerge(groupId) {
  const list = document.getElementById('mergeItemList');
  const outputInput = document.getElementById('mergeOutputName');
  const confirmBtn = document.getElementById('mergeConfirmBtn');
  if (!list || !outputInput) return;

  const items = [...list.querySelectorAll('.merge-item')];
  const orderedPaths = items.map(el => el.dataset.path);
  const outputName = outputInput.value.trim() || 'merged.pdf';

  confirmBtn.disabled = true;
  confirmBtn.textContent = '⏳ Đang gộp...';

  try {
    const res = await fetch('/api/processor/merge-files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: orderedPaths, output_name: outputName }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Lỗi: ${data.error}`);
      confirmBtn.disabled = false;
      confirmBtn.textContent = '📎 Gộp ngay';
      return;
    }
    alert(`✅ Đã gộp ${data.merged_count} file → ${data.output_name} (${data.total_pages} trang)`);

    // Find the table body where the first original row lived (for inserting merged row)
    const firstOrigRow = document.querySelector(`tr[data-filepath="${orderedPaths[0]}"]`);
    const parentTbody = firstOrigRow ? firstOrigRow.parentElement : null;
    const personName = firstOrigRow ? firstOrigRow.dataset.person : '';
    const insertBefore = firstOrigRow; // we'll insert before the first original row, then remove originals

    // Remove original file rows from table (they've been deleted on disk)
    orderedPaths.forEach(p => {
      const row = document.querySelector(`tr[data-filepath="${CSS.escape(p)}"]`) || document.querySelector(`tr[data-filepath="${p}"]`);
      if (row) row.remove();
    });

    // Remove the merge group row (button row)
    const mergeGroupRow = document.querySelector(`tr[data-merge-group-id="${groupId}"]`);
    if (mergeGroupRow) mergeGroupRow.remove();

    // Insert a new row for the merged file
    if (parentTbody && data.output_path) {
      const newRow = document.createElement('tr');
      newRow.dataset.filepath = data.output_path;
      newRow.dataset.person = personName;
      newRow.dataset.ext = '.pdf';
      newRow.dataset.filename = data.output_name;
      newRow.style.background = 'rgba(22,163,106,0.1)';  // dark green = new merged file
      newRow.style.borderLeft = '3px solid #16a34a';
      const mergedUid = `merged_${Date.now()}`;
      newRow.innerHTML = `
        <td style="padding:6px 8px;"><span style="color:#4ade80;">✅ Gộp</span></td>
        <td style="padding:6px 8px; overflow:hidden; text-overflow:ellipsis; color:#e2e8f0;" title="${data.output_path}">${data.output_name}</td>
        <td style="padding:6px 8px; overflow:hidden;">
          <input type="text" id="doctype_${mergedUid}" value="MERGED"
                 style="width:100%; box-sizing:border-box; padding:4px 6px; border:1px solid rgba(148,163,184,0.3); border-radius:4px; font-size:0.9em; background:rgba(30,41,59,0.8); color:#e2e8f0;"
                 oninput="updateSuggestedName(this)" />
        </td>
        <td style="padding:6px 8px; overflow:hidden;">
          <input type="text" id="suggested_${mergedUid}" value="${data.output_name}"
                 style="width:100%; box-sizing:border-box; padding:4px 6px; border:1px solid rgba(148,163,184,0.3); border-radius:4px; font-size:0.9em; background:rgba(30,41,59,0.6); color:#f1f5f9;" />
        </td>`;
      parentTbody.appendChild(newRow);
    }

    closeMergeModal();
  } catch (e) {
    alert(`Lỗi: ${e.message}`);
    confirmBtn.disabled = false;
    confirmBtn.textContent = '📎 Gộp ngay';
  }
}

async function sendMultiToSplitter() {
  // Find all files that need splitting from the folder-grouped data
  const multiFiles = [];
  for (const folder of precheckFolders) {
    for (const f of folder.files) {
      if (f.needs_split) multiFiles.push(f.path);
    }
  }
  if (multiFiles.length === 0) { alert("Không có file cần tách."); return; }
  const btn = document.getElementById("sendMultiToSplitterBtn");
  btn.disabled = true; btn.textContent = "Đang chuyển...";
  try {
    const pid = getProjectId();
    const res = await fetch("/api/pipeline/send-to-splitter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_paths: multiFiles, project_id: pid || null }),
    });
    const data = await res.json();
    if (!res.ok) { alert(`Lỗi: ${data.error}`); return; }
    // Save mapping: stored_name → original_path for save-to-source
    if (!window._splitterSourceMap) window._splitterSourceMap = {};
    for (let i = 0; i < data.copied.length; i++) {
      window._splitterSourceMap[data.copied[i]] = multiFiles[i];
    }
    alert(`✅ Đã chuyển ${data.count} file sang splitter.\nChọn file ở Tab ① → Upload & Tách → Lưu về thư mục gốc.`);
    setActiveTab("aisplitter");
  } catch (e) { alert(`Lỗi: ${e.message}`); }
  finally { btn.disabled = false; btn.textContent = "⚠️ Gửi file ghép → Tab ① Tách PDF (AI)"; }
}

