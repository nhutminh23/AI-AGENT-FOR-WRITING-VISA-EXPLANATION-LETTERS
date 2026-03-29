
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
    lines.push("✅ Nối PDF hoàn thành!");
    lines.push(`- Số file nguồn: ${data.file_count}`);
    lines.push(`- Tổng số trang: ${data.total_pages}`);
    lines.push(`- File kết quả: ${data.output_file}`);
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = lines.join("\n");
    }
    await loadPdfFiles();
    await loadMergedPdfs();
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


// ==================== MERGED PDF RESULTS ====================

function _formatFileSize(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

async function loadMergedPdfs() {
  const card = document.getElementById("mergedPdfResultsCard");
  const listEl = document.getElementById("mergedPdfResultsList");
  if (!card || !listEl) return;

  try {
    const res = await fetch("/api/pdf/merged");
    const data = await res.json();
    const records = data.merged_pdfs || [];

    if (records.length === 0) {
      card.style.display = "none";
      listEl.innerHTML = "";
      return;
    }

    card.style.display = "block";
    let html = `<div style="border:1px solid #334155; border-radius:8px; overflow:hidden;">`;
    // Header row
    html += `<div style="display:flex; align-items:center; padding:8px 12px; background:#1e293b; font-weight:600; font-size:0.85em; color:#94a3b8; border-bottom:1px solid #334155;">
      <span style="flex:1; min-width:180px;">Tên file</span>
      <span style="width:60px; text-align:center;">Trang</span>
      <span style="width:80px; text-align:center;">Dung lượng</span>
      <span style="width:60px; text-align:center;">Nguồn</span>
      <span style="width:200px; text-align:center;">Thao tác</span>
    </div>`;

    records.forEach((r) => {
      const sourceCount = (r.source_files || []).length;
      const sourceTooltip = (r.source_files || []).join("\n");
      html += `<div style="display:flex; align-items:center; padding:8px 12px; border-bottom:1px solid #1e293b; font-size:0.9em;">
        <span style="flex:1; min-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${r.filename}">📄 ${r.filename}</span>
        <span style="width:60px; text-align:center; color:#94a3b8;">${r.total_pages}</span>
        <span style="width:80px; text-align:center; color:#94a3b8;">${_formatFileSize(r.file_size)}</span>
        <span style="width:60px; text-align:center; color:#94a3b8;" title="${sourceTooltip}">${sourceCount} file</span>
        <div style="width:200px; display:flex; gap:4px; justify-content:center;">
          <a href="/api/pdf/merged/${r.id}/view" target="_blank"
             style="padding:4px 10px; background:#f59e0b; color:#fff; text-decoration:none; border-radius:4px; font-size:0.85em;">👁 Xem</a>
          <a href="/api/pdf/merged/${r.id}/download"
             style="padding:4px 10px; background:#4f46e5; color:#fff; text-decoration:none; border-radius:4px; font-size:0.85em;"
             download="${r.filename}">⬇ Tải</a>
          <button onclick="deleteMergedPdf(${r.id})"
             style="padding:4px 10px; background:#dc2626; color:#fff; border:none; border-radius:4px; font-size:0.85em; cursor:pointer;">🗑️</button>
        </div>
      </div>`;
    });

    html += `</div>`;
    listEl.innerHTML = html;
  } catch (err) {
    console.error("loadMergedPdfs error", err);
  }
}

async function deleteMergedPdf(id) {
  if (!confirm("Xóa file nối này?")) return;
  try {
    const res = await fetch(`/api/pdf/merged/${id}`, { method: "DELETE" });
    if (!res.ok) {
      const data = await res.json();
      alert("Lỗi: " + (data.error || "không xác định"));
      return;
    }
    await loadMergedPdfs();
  } catch (e) {
    alert("Lỗi: " + e.message);
  }
}

async function deleteAllMergedPdfs() {
  if (!confirm("Xóa TẤT CẢ file đã nối? (Cả file trên ổ đĩa sẽ bị xóa)")) return;
  try {
    const res = await fetch("/api/pdf/merged", { method: "DELETE" });
    const data = await res.json();
    if (res.ok) {
      await loadMergedPdfs();
    } else {
      alert("Lỗi: " + (data.error || "không xác định"));
    }
  } catch (e) {
    alert("Lỗi: " + e.message);
  }
}

// Wire up delete-all button
const deleteAllMergedBtn = document.getElementById("deleteAllMergedBtn");
if (deleteAllMergedBtn) {
  deleteAllMergedBtn.addEventListener("click", deleteAllMergedPdfs);
}

// Wire up download-all-ZIP button
const downloadAllMergedBtn = document.getElementById("downloadAllMergedBtn");
if (downloadAllMergedBtn) {
  downloadAllMergedBtn.addEventListener("click", () => {
    window.location.href = "/api/pdf/merged/download-zip";
  });
}

// Auto-load on page init
loadMergedPdfs();
