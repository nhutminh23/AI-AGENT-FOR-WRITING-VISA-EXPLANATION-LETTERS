/**
 * Workspace-based Translation Flow
 * 
 * Loads workspace list from Drive → auto-scan bilingual → create streams.
 * Replaces manual file upload as primary workflow.
 */

// Current active workspace name (for mark_complete)
let _activeWorkspaceName = "";
const ACTIVE_WORKSPACES_STORAGE_KEY = "activeWorkspaces";
let _activeWorkspaceNames = new Set();
const _workspaceDisplayNames = new Map();

function _normalizeWorkspaceName(name) {
  return String(name || "").trim();
}

function _workspaceCountLabel(count) {
  return `${count} hồ sơ`;
}

function _workspaceDisplayName(workspaceName) {
  const normalized = _normalizeWorkspaceName(workspaceName);
  return _workspaceDisplayNames.get(normalized) || normalized;
}

function _persistActiveWorkspaces() {
  const list = Array.from(_activeWorkspaceNames).filter(Boolean);
  try {
    if (list.length) {
      localStorage.setItem(ACTIVE_WORKSPACES_STORAGE_KEY, JSON.stringify(list));
    } else {
      localStorage.removeItem(ACTIVE_WORKSPACES_STORAGE_KEY);
    }
  } catch (_) {}

  try {
    if (_activeWorkspaceName) {
      localStorage.setItem("activeWorkspace", _activeWorkspaceName);
    } else {
      localStorage.removeItem("activeWorkspace");
    }
  } catch (_) {}
}

function _restoreActiveWorkspaces() {
  const restored = new Set();

  try {
    const raw = localStorage.getItem(ACTIVE_WORKSPACES_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        for (const item of parsed) {
          const normalized = _normalizeWorkspaceName(item);
          if (normalized) restored.add(normalized);
        }
      }
    }
  } catch (_) {}

  try {
    const single = _normalizeWorkspaceName(localStorage.getItem("activeWorkspace") || "");
    if (single) restored.add(single);
  } catch (_) {}

  _activeWorkspaceNames = restored;
  _activeWorkspaceName = _activeWorkspaceNames.values().next().value || "";
}

function getActiveWorkspaceNames() {
  return Array.from(_activeWorkspaceNames);
}

function syncActiveWorkspacesFromList(workspaceNames = []) {
  const next = new Set();
  for (const name of workspaceNames || []) {
    const normalized = _normalizeWorkspaceName(name);
    if (normalized) next.add(normalized);
  }
  _activeWorkspaceNames = next;

  if (!_activeWorkspaceNames.has(_activeWorkspaceName)) {
    _activeWorkspaceName = _activeWorkspaceNames.values().next().value || "";
  }

  _persistActiveWorkspaces();
  refreshWorkspaceCompletePanel();
}

function registerActiveWorkspace(workspaceName) {
  const normalized = _normalizeWorkspaceName(workspaceName);
  if (!normalized) return;
  _activeWorkspaceNames.add(normalized);
  _activeWorkspaceName = normalized;
  _persistActiveWorkspaces();
  refreshWorkspaceCompletePanel();
}

function unregisterActiveWorkspace(workspaceName) {
  const normalized = _normalizeWorkspaceName(workspaceName);
  if (!normalized) return;
  _activeWorkspaceNames.delete(normalized);
  if (_activeWorkspaceName === normalized) {
    _activeWorkspaceName = _activeWorkspaceNames.values().next().value || "";
  }
  _persistActiveWorkspaces();
  refreshWorkspaceCompletePanel();
}

function refreshWorkspaceCompletePanel() {
  if (!workspaceCompletePanelEl || !workspaceCompleteInfoEl) return;

  const count = _activeWorkspaceNames.size;
  if (count <= 0) {
    workspaceCompletePanelEl.style.display = "none";
    workspaceCompleteInfoEl.innerHTML = "📂 Đang dịch: <strong>---</strong>";
    if (markCompleteBtn) markCompleteBtn.textContent = "🚀 Báo cáo: Đã Dịch Xong";
    return;
  }

  workspaceCompletePanelEl.style.display = "block";
  workspaceCompleteInfoEl.innerHTML = `📂 Đang dịch: <strong>${escapeHtml(_workspaceCountLabel(count))}</strong>`;
  if (markCompleteBtn) {
    markCompleteBtn.textContent = count > 1
      ? `🚀 Báo cáo: Đã Dịch Xong (${count} hồ sơ)`
      : "🚀 Báo cáo: Đã Dịch Xong";
  }
}

function _flowWorkspaceName(flowId) {
  const input = document.getElementById(`transWorkspace-${flowId}`);
  return _normalizeWorkspaceName(input?.value || "");
}

async function _deleteDbFlowsForWorkspaces(workspaceNames = []) {
  const targets = new Set((workspaceNames || []).map(_normalizeWorkspaceName).filter(Boolean));
  if (targets.size === 0) return;

  try {
    const res = await fetch("/api/translate/flows");
    if (!res.ok) return;

    const payload = await res.json();
    const flows = Array.isArray(payload?.flows) ? payload.flows : [];

    for (const f of flows) {
      const workspace = _normalizeWorkspaceName(f.workspace);
      if (!targets.has(workspace) || !f.id) continue;
      try {
        await fetch(`/api/translate/flows/${f.id}`, { method: "DELETE" });
      } catch (_) {}

      for (const [flowId, dbId] of Object.entries(_flowDbIds)) {
        if (Number(dbId) === Number(f.id)) {
          delete _flowDbIds[flowId];
        }
      }
    }
  } catch (_) {}
}

function _removeFlowCardsForWorkspaces(workspaceNames = []) {
  if (!translateFlowsContainerEl) return;

  const targets = new Set((workspaceNames || []).map(_normalizeWorkspaceName).filter(Boolean));
  if (targets.size === 0) return;

  const cards = translateFlowsContainerEl.querySelectorAll(".translate-flow-card");
  cards.forEach((card) => {
    const flowId = Number(String(card.id || "").replace("translateFlow-", ""));
    if (!Number.isFinite(flowId)) return;
    const workspace = _flowWorkspaceName(flowId);
    if (!targets.has(workspace)) return;
    card.remove();
    delete _flowDbIds[flowId];
  });

  if (translateFlowsContainerEl.querySelectorAll(".translate-flow-card").length === 0) {
    translationFlowCounter = 0;
  }
}

_restoreActiveWorkspaces();
refreshWorkspaceCompletePanel();

if (typeof window !== "undefined") {
  window.syncActiveWorkspacesFromList = syncActiveWorkspacesFromList;
  window.getActiveWorkspaceNames = getActiveWorkspaceNames;
  window.refreshWorkspaceCompletePanel = refreshWorkspaceCompletePanel;
}

/**
 * Load available translation workspaces from the backend.
 */
async function loadTranslationWorkspaces() {
  if (!workspaceSelectEl) return;

  try {
    const res = await fetch("/api/translate/workspaces");
    const data = await res.json();
    const workspaces = data.workspaces || [];

    _workspaceDisplayNames.clear();

    workspaceSelectEl.innerHTML = "";

    if (workspaces.length === 0) {
      workspaceSelectEl.innerHTML = '<option value="">🚫 Chưa có hồ sơ nào (chờ Drive CHECK)</option>';
      refreshWorkspaceCompletePanel();
      return;
    }

    workspaceSelectEl.innerHTML = '<option value="">-- Chọn hồ sơ để dịch --</option>';
    for (const ws of workspaces) {
      _workspaceDisplayNames.set(_normalizeWorkspaceName(ws.dir_name), String(ws.base_name || ws.dir_name));
      const label = `${ws.base_name} (${ws.file_count} file)`;
      const opt = document.createElement("option");
      opt.value = ws.dir_name;
      opt.textContent = label;
      opt.dataset.baseName = ws.base_name;
      workspaceSelectEl.appendChild(opt);
    }

    refreshWorkspaceCompletePanel();
    if (typeof refreshTranslationFlowWorkspaceLabels === "function") {
      refreshTranslationFlowWorkspaceLabels();
    }
  } catch (e) {
    console.error("Failed to load workspaces:", e);
    workspaceSelectEl.innerHTML = '<option value="">❌ Lỗi tải danh sách</option>';
    refreshWorkspaceCompletePanel();
  }
}

function _allWorkspaceOptions() {
  if (!workspaceSelectEl) return [];

  return Array.from(workspaceSelectEl.options || [])
    .map((opt) => {
      const value = _normalizeWorkspaceName(opt.value);
      if (!value) return null;

      const baseName = String(opt.dataset?.baseName || _workspaceDisplayName(value) || value).trim();
      return {
        workspace_name: value,
        workspace_display_name: baseName || value,
      };
    })
    .filter(Boolean);
}

function _decorateWorkspaceResults(rawResults = [], workspaceName, workspaceDisplayName) {
  const normalizedName = _normalizeWorkspaceName(workspaceName);
  const displayName = String(workspaceDisplayName || _workspaceDisplayName(normalizedName) || normalizedName).trim();

  return (rawResults || []).map((r) => ({
    ...r,
    workspace_name: normalizedName,
    workspace_display_name: displayName || normalizedName,
  }));
}

async function _scanWorkspaceOnce(workspaceName) {
  const res = await fetch("/api/translate/workspace_scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspace: workspaceName }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || data.detail || "unknown");
  }

  return data;
}

function _renderWorkspaceScanResults(results = [], summaryHtml = "") {
  _bulkCheckResults = results;

  if (bulkResultsBodyEl) {
    bulkResultsBodyEl.innerHTML = results.map((r, i) => {
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
      const workspaceLabel = String(r.workspace_display_name || _workspaceDisplayName(r.workspace_name || "") || "").trim();

      return `<tr style="border-bottom:1px solid #e2e8f0;">
        <td style="padding:6px 8px;">${i + 1}</td>
        <td style="padding:6px 8px; white-space:nowrap;">${workspaceLabel ? escapeHtml(workspaceLabel) : "—"}</td>
        <td style="padding:6px 8px; word-break:break-all;">${escapeHtml(r.filename)}${relPath}</td>
        <td style="padding:6px 8px; text-align:center; font-size:0.85em;">${docType}</td>
        <td style="padding:6px 8px; text-align:center;">${statusBadge}</td>
        <td style="padding:6px 8px; font-size:0.85em; color:#64748b;">${escapeHtml(r.reason || "")}</td>
      </tr>`;
    }).join("");
  }

  if (bulkResultSummaryEl) {
    bulkResultSummaryEl.innerHTML = summaryHtml;
  }

  if (bulkCheckResultsEl) bulkCheckResultsEl.style.display = "block";
  if (bulkManualFallbackEl) bulkManualFallbackEl.style.display = "none";
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

  // Save the last selected workspace for per-flow fallback
  _activeWorkspaceName = workspaceName;
  _persistActiveWorkspaces();

  // Show progress
  const origText = workspaceScanBtn.textContent;
  const scanAllOrigText = workspaceScanAllBtn ? workspaceScanAllBtn.textContent : "";
  workspaceScanBtn.disabled = true;
  workspaceScanBtn.textContent = "⏳ Đang quét...";
  if (workspaceScanAllBtn) workspaceScanAllBtn.disabled = true;
  if (workspaceScanStatusEl) {
    workspaceScanStatusEl.innerHTML = `⏳ Đang quét hồ sơ <strong>${escapeHtml(workspaceName)}</strong>...`;
  }
  if (workspaceScanProgressEl) {
    workspaceScanProgressEl.style.display = "block";
    workspaceScanProgressBarEl.style.width = "30%";
  }

  try {
    if (workspaceScanProgressBarEl) workspaceScanProgressBarEl.style.width = "60%";

    const selectedOpt = workspaceSelectEl.options[workspaceSelectEl.selectedIndex];
    const workspaceDisplayName = String(selectedOpt?.dataset?.baseName || _workspaceDisplayName(workspaceName)).trim() || workspaceName;
    const data = await _scanWorkspaceOnce(workspaceName);
    const scopedResults = _decorateWorkspaceResults(data.results || [], workspaceName, workspaceDisplayName);

    if (workspaceScanProgressBarEl) workspaceScanProgressBarEl.style.width = "100%";

    const skipCount = data.skipped || 0;
    _renderWorkspaceScanResults(
      scopedResults,
      `📊 ${data.total} file | <span style="color:#dc2626;">${data.needs_translation} cần dịch</span> | <span style="color:#16a34a;">${data.already_bilingual} song ngữ</span> | <span style="color:#d97706;">${skipCount} bỏ qua</span> | 📂 1 hồ sơ`
    );

    if (workspaceScanStatusEl) {
      workspaceScanStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Quét xong ${data.total} file từ <strong>${escapeHtml(workspaceName)}</strong>!</span>`;
    }

    if ((data.needs_translation || 0) > 0) {
      registerActiveWorkspace(workspaceName);
    } else {
      unregisterActiveWorkspace(workspaceName);
    }

  } catch (e) {
    if (workspaceScanStatusEl) {
      workspaceScanStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(e.message)}</span>`;
    }
  } finally {
    workspaceScanBtn.disabled = false;
    workspaceScanBtn.textContent = origText;
    if (workspaceScanAllBtn) {
      workspaceScanAllBtn.disabled = false;
      workspaceScanAllBtn.textContent = scanAllOrigText || "🌐 Quét tất cả hồ sơ";
    }
    setTimeout(() => {
      if (workspaceScanProgressEl) workspaceScanProgressEl.style.display = "none";
    }, 1000);
  }
}

/**
 * Scan every workspace listed in dropdown and aggregate into one result table.
 */
async function runAllWorkspacesScan() {
  if (!workspaceSelectEl || !workspaceScanAllBtn) return;

  const workspaceItems = _allWorkspaceOptions();
  if (workspaceItems.length === 0) {
    if (workspaceScanStatusEl) {
      workspaceScanStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Chưa có hồ sơ nào để quét.</span>';
    }
    return;
  }

  const scanAllOrigText = workspaceScanAllBtn.textContent;
  const scanOneOrigText = workspaceScanBtn ? workspaceScanBtn.textContent : "";
  workspaceScanAllBtn.disabled = true;
  workspaceScanAllBtn.textContent = "⏳ Đang quét tất cả...";
  if (workspaceScanBtn) workspaceScanBtn.disabled = true;

  if (workspaceScanStatusEl) {
    workspaceScanStatusEl.innerHTML = `⏳ Đang quét ${workspaceItems.length} hồ sơ...`;
  }
  if (workspaceScanProgressEl) {
    workspaceScanProgressEl.style.display = "block";
    workspaceScanProgressBarEl.style.width = "5%";
  }

  const mergedResults = [];
  const failedWorkspaces = [];
  let successfulScans = 0;
  let sumTotal = 0;
  let sumNeedsTranslation = 0;
  let sumBilingual = 0;
  let sumSkipped = 0;

  try {
    for (let i = 0; i < workspaceItems.length; i++) {
      const item = workspaceItems[i];
      const progress = Math.round(((i + 1) / workspaceItems.length) * 100);

      if (workspaceScanProgressBarEl) {
        workspaceScanProgressBarEl.style.width = `${Math.max(5, progress)}%`;
      }
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = `⏳ Đang quét hồ sơ ${i + 1}/${workspaceItems.length}: <strong>${escapeHtml(item.workspace_display_name)}</strong>`;
      }

      try {
        const data = await _scanWorkspaceOnce(item.workspace_name);
        successfulScans += 1;
        const scoped = _decorateWorkspaceResults(data.results || [], item.workspace_name, item.workspace_display_name);
        mergedResults.push(...scoped);

        sumTotal += data.total || 0;
        sumNeedsTranslation += data.needs_translation || 0;
        sumBilingual += data.already_bilingual || 0;
        sumSkipped += data.skipped || 0;

        if ((data.needs_translation || 0) > 0) {
          registerActiveWorkspace(item.workspace_name);
        } else {
          unregisterActiveWorkspace(item.workspace_name);
        }
      } catch (err) {
        failedWorkspaces.push({
          workspace: item.workspace_display_name,
          error: err.message || "unknown",
        });
      }
    }

    if (successfulScans > 0) {
      _renderWorkspaceScanResults(
        mergedResults,
        `📊 ${sumTotal} file | <span style="color:#dc2626;">${sumNeedsTranslation} cần dịch</span> | <span style="color:#16a34a;">${sumBilingual} song ngữ</span> | <span style="color:#d97706;">${sumSkipped} bỏ qua</span> | 📂 ${successfulScans} hồ sơ`
      );
    }

    if (failedWorkspaces.length === 0) {
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã quét xong ${workspaceItems.length}/${workspaceItems.length} hồ sơ.</span>`;
      }
    } else if (failedWorkspaces.length < workspaceItems.length) {
      const failedPreview = failedWorkspaces
        .slice(0, 3)
        .map((f) => `${f.workspace}: ${f.error}`)
        .join(" | ");
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = `<span style="color:#d97706;">⚠️ Đã quét ${workspaceItems.length - failedWorkspaces.length}/${workspaceItems.length} hồ sơ. Lỗi: ${escapeHtml(failedPreview)}</span>`;
      }
    } else {
      const failedPreview = failedWorkspaces
        .slice(0, 3)
        .map((f) => `${f.workspace}: ${f.error}`)
        .join(" | ");
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Không quét được hồ sơ nào. ${escapeHtml(failedPreview)}</span>`;
      }
    }
  } catch (e) {
    if (workspaceScanStatusEl) {
      workspaceScanStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(e.message)}</span>`;
    }
  } finally {
    workspaceScanAllBtn.disabled = false;
    workspaceScanAllBtn.textContent = scanAllOrigText;
    if (workspaceScanBtn) {
      workspaceScanBtn.disabled = false;
      workspaceScanBtn.textContent = scanOneOrigText || "🤖 Quét hồ sơ đã chọn";
    }

    setTimeout(() => {
      if (workspaceScanProgressEl) workspaceScanProgressEl.style.display = "none";
    }, 1000);
  }
}

/**
 * Mark current workspace as fully translated → Drive folder renamed to "DONE".
 */
async function markWorkspaceComplete() {
  const targetWorkspaces = getActiveWorkspaceNames();
  if (targetWorkspaces.length === 0 && _activeWorkspaceName) {
    targetWorkspaces.push(_activeWorkspaceName);
  }

  if (targetWorkspaces.length === 0) {
    alert("Chưa chọn hồ sơ nào.");
    return;
  }

  const shortList = targetWorkspaces
    .slice(0, 5)
    .map((ws) => `• ${_workspaceDisplayName(ws)}`)
    .join("\n");
  const extraCount = targetWorkspaces.length - Math.min(targetWorkspaces.length, 5);
  const extraLine = extraCount > 0 ? `\n• ... và ${extraCount} hồ sơ khác` : "";
  const confirmTargetText = targetWorkspaces.length === 1
    ? `hồ sơ "${_workspaceDisplayName(targetWorkspaces[0])}"`
    : `${targetWorkspaces.length} hồ sơ`;

  if (!confirm(`Xác nhận đã dịch xong ${confirmTargetText}?\n\nDanh sách:\n${shortList}${extraLine}\n\nThao tác này sẽ:\n• Cập nhật trạng thái folder trên Drive\n• Chuyển workspace local sang "Khai Imm"`)) {
    return;
  }

  if (markCompleteBtn) {
    markCompleteBtn.disabled = true;
    markCompleteBtn.textContent = "⏳ Đang cập nhật...";
  }

  try {
    const completed = [];
    const failed = [];

    for (let idx = 0; idx < targetWorkspaces.length; idx++) {
      const workspaceName = targetWorkspaces[idx];

      if (markCompleteBtn) {
        markCompleteBtn.textContent = `⏳ Đang cập nhật... (${idx + 1}/${targetWorkspaces.length})`;
      }

      const res = await fetch("/api/translate/mark_complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace: workspaceName }),
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        completed.push(workspaceName);
        unregisterActiveWorkspace(workspaceName);
      } else {
        failed.push({
          workspace: workspaceName,
          error: data.detail || data.error || "unknown",
        });
      }
    }

    if (completed.length > 0) {
      await _deleteDbFlowsForWorkspaces(completed);
      _removeFlowCardsForWorkspaces(completed);
      if (bulkCheckResultsEl && translateFlowsContainerEl && translateFlowsContainerEl.querySelectorAll(".translate-flow-card").length === 0) {
        bulkCheckResultsEl.style.display = "none";
      }
    }

    if (completed.length > 0 && failed.length === 0) {
      const doneText = _workspaceCountLabel(completed.length);
      alert(`✅ Đã báo cáo dịch xong ${doneText}.`);
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã báo cáo dịch xong ${escapeHtml(doneText)}.</span>`;
      }
    } else if (completed.length > 0 && failed.length > 0) {
      const failText = failed
        .map((f) => `• ${_workspaceDisplayName(f.workspace)}: ${f.error}`)
        .join("\n");
      alert(`⚠️ Đã xử lý ${completed.length}/${targetWorkspaces.length} hồ sơ.\n\nLỗi:\n${failText}`);
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = `<span style="color:#d97706;">⚠️ Đã báo cáo ${completed.length}/${targetWorkspaces.length} hồ sơ. Kiểm tra lỗi trong popup.</span>`;
      }
    } else {
      const failText = failed
        .map((f) => `• ${_workspaceDisplayName(f.workspace)}: ${f.error}`)
        .join("\n");
      alert(`❌ Không báo cáo được hồ sơ nào.\n\n${failText}`);
      if (workspaceScanStatusEl) {
        workspaceScanStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Không thể cập nhật trạng thái hồ sơ lên Drive.</span>';
      }
    }

    await loadTranslationWorkspaces();

  } catch (e) {
    alert("Lỗi: " + e.message);
  } finally {
    if (markCompleteBtn) {
      markCompleteBtn.disabled = false;
    }
    refreshWorkspaceCompletePanel();
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

  const flowWorkspaceEl = document.getElementById(`transWorkspace-${flowId}`);
  const flowWorkspace = _normalizeWorkspaceName(flowWorkspaceEl?.value || "");

  // Use fallback workspace for manual mode (no Drive)
  const workspaceName = flowWorkspace || _activeWorkspaceName || "_manual_stamp";
  const isManualMode = !flowWorkspace && !_activeWorkspaceName;

  if (!flowWorkspace && _activeWorkspaceName && flowWorkspaceEl) {
    flowWorkspaceEl.value = _activeWorkspaceName;
  }

  // Hide "Push to Drive" in manual mode (no Drive folder)
  if (isManualMode && pushBtn) {
    pushBtn.style.display = "none";
  }

  try {
    const res = await fetch("/api/translate/stamp_preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace: workspaceName,
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
  const flowWorkspaceEl = document.getElementById(`transWorkspace-${flowId}`);
  const pushBtn = document.getElementById(`transPushDriveBtn-${flowId}`);
  const stampStatusEl = document.getElementById(`transStampStatus-${flowId}`);

  const filename = (fileNameEl?.value || "").trim();
  const driveFileId = (driveFileIdEl?.value || "").trim();
  const workspaceName = _normalizeWorkspaceName(flowWorkspaceEl?.value || _activeWorkspaceName || "");

  if (!workspaceName) {
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
        workspace: workspaceName,
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

