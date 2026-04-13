/**
 * Workspace-based Translation Flow
 * 
 * Loads workspace list from Drive → auto-scan bilingual → create streams.
 * Replaces manual file upload as primary workflow.
 */

// Current active workspace name (for mark_complete)
let _activeWorkspaceName = "";

/**
 * Load available translation workspaces from the backend.
 */
async function loadTranslationWorkspaces() {
  if (!workspaceSelectEl) return;

  try {
    const res = await fetch("/api/translate/workspaces");
    const data = await res.json();
    const workspaces = data.workspaces || [];

    workspaceSelectEl.innerHTML = "";

    if (workspaces.length === 0) {
      workspaceSelectEl.innerHTML = '<option value="">🚫 Chưa có hồ sơ nào (chờ Drive CHECK)</option>';
      return;
    }

    workspaceSelectEl.innerHTML = '<option value="">-- Chọn hồ sơ để dịch --</option>';
    for (const ws of workspaces) {
      const label = `${ws.base_name} (${ws.file_count} file)`;
      const opt = document.createElement("option");
      opt.value = ws.dir_name;
      opt.textContent = label;
      opt.dataset.baseName = ws.base_name;
      workspaceSelectEl.appendChild(opt);
    }
  } catch (e) {
    console.error("Failed to load workspaces:", e);
    workspaceSelectEl.innerHTML = '<option value="">❌ Lỗi tải danh sách</option>';
  }
}

/**
 * Scan the selected workspace: auto-detect bilingual → show results → create streams.
 */
async function runWorkspaceScan() {
  if (!workspaceSelectEl || !workspaceScanBtn) return;

  const workspaceName = workspaceSelectEl.value;
  if (!workspaceName) {
    if (workspaceScanStatusEl) {
      workspaceScanStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Vui lòng chọn hồ sơ trước.</span>';
    }
    return;
  }

  // Save active workspace name
  _activeWorkspaceName = workspaceName;

  // Show progress
  const origText = workspaceScanBtn.textContent;
  workspaceScanBtn.disabled = true;
  workspaceScanBtn.textContent = "⏳ Đang quét...";
  if (workspaceScanStatusEl) {
    workspaceScanStatusEl.innerHTML = `⏳ Đang quét hồ sơ <strong>${escapeHtml(workspaceName)}</strong>...`;
  }
  if (workspaceScanProgressEl) {
    workspaceScanProgressEl.style.display = "block";
    workspaceScanProgressBarEl.style.width = "30%";
  }

  try {
    if (workspaceScanProgressBarEl) workspaceScanProgressBarEl.style.width = "60%";

    const res = await fetch("/api/translate/workspace_scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace: workspaceName }),
    });
    const data = await res.json();

    if (workspaceScanProgressBarEl) workspaceScanProgressBarEl.style.width = "100%";

    if (!res.ok) {
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(data.error || "unknown")}</span>`;
      }
      return;
    }

    // Store results for stream creation (reuse existing _bulkCheckResults)
    _bulkCheckResults = data.results || [];

    // Render results in existing table
    if (bulkResultsBodyEl) {
      bulkResultsBodyEl.innerHTML = _bulkCheckResults.map((r, i) => {
        let statusBadge;
        if (r.needs_translation) {
          statusBadge = '<span style="background:#fef2f2; color:#dc2626; padding:2px 8px; border-radius:4px; font-size:0.85em;">📝 Cần dịch</span>';
        } else if (r.is_bilingual) {
          statusBadge = '<span style="background:#f0fdf4; color:#16a34a; padding:2px 8px; border-radius:4px; font-size:0.85em;">✅ Đã song ngữ</span>';
        } else {
          statusBadge = '<span style="background:#fffbeb; color:#d97706; padding:2px 8px; border-radius:4px; font-size:0.85em;">⏭️ Bỏ qua</span>';
        }
        const docType = r.doc_type ? escapeHtml(r.doc_type) : (r.languages || []).join(", ") || "—";
        const relPath = r.rel_path ? `<br><span style="color:#94a3b8; font-size:0.8em;">${escapeHtml(r.rel_path)}</span>` : "";
        return `<tr style="border-bottom:1px solid #e2e8f0;">
          <td style="padding:6px 8px;">${i + 1}</td>
          <td style="padding:6px 8px; word-break:break-all;">${escapeHtml(r.filename)}${relPath}</td>
          <td style="padding:6px 8px; text-align:center; font-size:0.85em;">${docType}</td>
          <td style="padding:6px 8px; text-align:center;">${statusBadge}</td>
          <td style="padding:6px 8px; font-size:0.85em; color:#64748b;">${escapeHtml(r.reason || '')}</td>
        </tr>`;
      }).join("");
    }

    // Summary
    if (bulkResultSummaryEl) {
      const skipCount = data.skipped || 0;
      bulkResultSummaryEl.innerHTML = `📊 ${data.total} file | <span style="color:#dc2626;">${data.needs_translation} cần dịch</span> | <span style="color:#16a34a;">${data.already_bilingual} song ngữ</span> | <span style="color:#d97706;">${skipCount} bỏ qua</span>`;
    }

    // Show results area
    if (bulkCheckResultsEl) bulkCheckResultsEl.style.display = "block";
    if (bulkManualFallbackEl) bulkManualFallbackEl.style.display = "none";
    if (workspaceScanStatusEl) {
      workspaceScanStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Quét xong ${data.total} file từ <strong>${escapeHtml(workspaceName)}</strong>!</span>`;
    }

    // Show workspace complete panel
    if (workspaceCompletePanelEl) {
      workspaceCompletePanelEl.style.display = "block";
    }
    if (workspaceCompleteInfoEl) {
      const selectedOpt = workspaceSelectEl.options[workspaceSelectEl.selectedIndex];
      const baseName = selectedOpt?.dataset?.baseName || workspaceName;
      workspaceCompleteInfoEl.innerHTML = `📂 Đang dịch: <strong>${escapeHtml(baseName)}</strong> — ${data.needs_translation} file cần dịch`;
    }

  } catch (e) {
    if (workspaceScanStatusEl) {
      workspaceScanStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(e.message)}</span>`;
    }
  } finally {
    workspaceScanBtn.disabled = false;
    workspaceScanBtn.textContent = origText;
    setTimeout(() => {
      if (workspaceScanProgressEl) workspaceScanProgressEl.style.display = "none";
    }, 1000);
  }
}

/**
 * Mark current workspace as fully translated → Drive folder renamed to "Đang khai".
 */
async function markWorkspaceComplete() {
  if (!_activeWorkspaceName) {
    alert("Chưa chọn hồ sơ nào.");
    return;
  }

  if (!confirm(`Xác nhận đã dịch xong toàn bộ hồ sơ "${_activeWorkspaceName}"?\n\nThao tác này sẽ:\n• Đổi tên folder trên Drive thành "Đang khai"\n• Xóa workspace local`)) {
    return;
  }

  if (markCompleteBtn) {
    markCompleteBtn.disabled = true;
    markCompleteBtn.textContent = "⏳ Đang cập nhật...";
  }

  try {
    const res = await fetch("/api/translate/mark_complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace: _activeWorkspaceName }),
    });
    const data = await res.json();

    if (!res.ok) {
      alert("Lỗi: " + (data.detail || data.error || "unknown"));
      return;
    }

    alert(`✅ ${data.message}`);

    // Reset UI
    _activeWorkspaceName = "";
    try { localStorage.removeItem("activeWorkspace"); } catch (_) {}
    if (workspaceCompletePanelEl) workspaceCompletePanelEl.style.display = "none";
    if (bulkCheckResultsEl) bulkCheckResultsEl.style.display = "none";
    if (workspaceScanStatusEl) workspaceScanStatusEl.innerHTML = "";

    // Reload workspace list
    await loadTranslationWorkspaces();

  } catch (e) {
    alert("Lỗi: " + e.message);
  } finally {
    if (markCompleteBtn) {
      markCompleteBtn.disabled = false;
      markCompleteBtn.textContent = "🚀 Báo cáo: Đã Dịch Xong";
    }
  }
}




/**
 * Step 1: Stamp a translated document and show inline PDF preview.
 * User reviews the stamp before pushing to Drive.
 */
async function stampPreview(flowId) {
  const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
  const fileNameEl = document.getElementById(`transUploadedName-${flowId}`);
  const stampBtn = document.getElementById(`transStampPreviewBtn-${flowId}`);
  const stampStatusEl = document.getElementById(`transStampStatus-${flowId}`);
  const previewArea = document.getElementById(`transStampPreview-${flowId}`);
  const pdfFrame = document.getElementById(`transStampPdfFrame-${flowId}`);
  const pushBtn = document.getElementById(`transPushDriveBtn-${flowId}`);

  const htmlContent = (htmlSrcEl?.value || "").trim();
  const filename = (fileNameEl?.value || "").trim();

  if (!htmlContent) {
    if (stampStatusEl) stampStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Chưa có HTML bản dịch. Hãy dịch trước.</span>';
    return;
  }

  if (!_activeWorkspaceName) {
    if (stampStatusEl) stampStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Không tìm thấy workspace đang active.</span>';
    return;
  }

  const origText = stampBtn?.textContent || "";
  if (stampBtn) {
    stampBtn.disabled = true;
    stampBtn.textContent = "⏳ Đang đóng mộc...";
  }
  if (stampStatusEl) {
    stampStatusEl.innerHTML = '⏳ Đang chuyển HTML → PDF → Đóng mộc + giáp lai...';
  }

  const fileRefEl = document.getElementById(`transUploadedRef-${flowId}`);
  const fileRef = (fileRefEl?.value || "").trim();

  try {
    const res = await fetch("/api/translate/stamp_preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace: _activeWorkspaceName,
        filename: filename,
        file_ref: fileRef,
        html_content: htmlContent,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      if (stampStatusEl) {
        stampStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(errData.detail || errData.error || "unknown")}</span>`;
      }
      return;
    }

    // Response is a PDF blob — show inline preview
    const pdfBlob = await res.blob();
    const pdfUrl = URL.createObjectURL(pdfBlob);

    if (pdfFrame) pdfFrame.src = pdfUrl;
    if (previewArea) previewArea.style.display = "block";

    // Enable the "Push to Drive" button
    if (pushBtn) {
      pushBtn.disabled = false;
      pushBtn.style.background = "#16a34a";
      pushBtn.style.color = "#fff";
      pushBtn.style.cursor = "pointer";
    }

    if (stampStatusEl) {
      stampStatusEl.innerHTML = '<span style="color:#16a34a;">✅ Đã đóng mộc thành công! Kiểm tra PDF bên dưới rồi bấm <strong>"Gửi lên Drive"</strong>.</span>';
    }

    // Update stamp button to show done but keep re-clickable
    if (stampBtn) {
      stampBtn.textContent = "🔄 Đóng mộc lại";
      stampBtn.style.background = "#16a34a";
      stampBtn.disabled = false;  // Allow re-clicking for iterative testing
    }

  } catch (e) {
    if (stampStatusEl) {
      stampStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(e.message)}</span>`;
    }
  } finally {
    // Always re-enable stamp button
    if (stampBtn) {
      stampBtn.disabled = false;
      if (stampBtn.textContent === "⏳ Đang đóng mộc...") {
        stampBtn.textContent = origText;
      }
    }
  }
}


/**
 * Step 2: Push the already-stamped PDF to Google Drive.
 * Only enabled after stampPreview succeeds.
 */
async function pushToDrive(flowId) {
  const fileNameEl = document.getElementById(`transUploadedName-${flowId}`);
  const driveFileIdEl = document.getElementById(`transDriveFileId-${flowId}`);
  const pushBtn = document.getElementById(`transPushDriveBtn-${flowId}`);
  const stampStatusEl = document.getElementById(`transStampStatus-${flowId}`);

  const filename = (fileNameEl?.value || "").trim();
  const driveFileId = (driveFileIdEl?.value || "").trim();

  if (!_activeWorkspaceName) {
    if (stampStatusEl) stampStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Workspace không tìm thấy.</span>';
    return;
  }

  if (!confirm(`Xác nhận gửi file "${filename}" lên Google Drive?`)) return;

  const origText = pushBtn?.textContent || "";
  if (pushBtn) {
    pushBtn.disabled = true;
    pushBtn.textContent = "⏳ Đang upload...";
  }
  if (stampStatusEl) {
    stampStatusEl.innerHTML = '⏳ Đang upload lên Drive + đánh dấu file gốc...';
  }

  try {
    const res = await fetch("/api/translate/push_to_drive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace: _activeWorkspaceName,
        filename: filename,
        drive_file_id: driveFileId,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      if (stampStatusEl) {
        stampStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(data.detail || data.error || "unknown")}</span>`;
      }
      return;
    }

    // Build success message
    let msg = `✅ <strong>${escapeHtml(data.stamped_pdf || "")}</strong>`;
    if (data.drive_uploaded) {
      msg += ` | 📤 Đã upload lên Drive`;
    } else {
      msg += ` | ⚠️ Chưa upload Drive (kiểm tra kết nối)`;
    }
    if (data.original_renamed) {
      msg += ` | 📝 Đã đánh dấu [Đã dịch] trên file gốc`;
    }

    if (stampStatusEl) {
      stampStatusEl.innerHTML = `<span style="color:#16a34a;">${msg}</span>`;
    }

    // Lock both buttons as done
    if (pushBtn) {
      pushBtn.textContent = "✅ Đã gửi Drive";
      pushBtn.style.background = "#16a34a";
      pushBtn.disabled = true;
    }

  } catch (e) {
    if (stampStatusEl) {
      stampStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(e.message)}</span>`;
    }
  } finally {
    if (pushBtn && pushBtn.textContent === "⏳ Đang upload...") {
      pushBtn.disabled = false;
      pushBtn.textContent = origText;
    }
  }
}

