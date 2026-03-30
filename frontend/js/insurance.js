/* ═══════════════════════════════════════════════════════════════
   insurance.js — Insurance PDF Editor Module (Tab ⑨)
   Choose template → Input dates → Extract JSON → Copy Grok → Apply
   ═══════════════════════════════════════════════════════════════ */

// State
let _insCurrentTemplate = null;
let _insOriginalSummary = null;
let _insAutoFields = null;
let _insGrokPrompt = "";

// DOM refs
const insuranceSection = document.getElementById("insuranceSection");

function initInsuranceUI() {
  // Template card click handlers
  document.querySelectorAll(".ins-template-card").forEach((card) => {
    card.addEventListener("click", () => {
      const tpl = card.dataset.template;
      _insSelectTemplate(tpl);
    });
    card.addEventListener("mouseenter", () => {
      card.style.borderColor = "#7c3aed";
      card.style.background = "#1e1b4b22";
    });
    card.addEventListener("mouseleave", () => {
      if (card.dataset.template !== _insCurrentTemplate) {
        card.style.borderColor = "#334155";
        card.style.background = "";
      }
    });
  });

  // Back button
  const backBtn = document.getElementById("insBackBtn");
  if (backBtn) backBtn.addEventListener("click", _insResetToStep1);

  // Copy Prompt button
  const copyBtn = document.getElementById("insCopyPromptBtn");
  if (copyBtn) copyBtn.addEventListener("click", _insCopyPrompt);

  // Apply button
  const applyBtn = document.getElementById("insApplyBtn");
  if (applyBtn) applyBtn.addEventListener("click", _insApplyChanges);

  // View PDF button
  const viewBtn = document.getElementById("insViewBtn");
  if (viewBtn) viewBtn.addEventListener("click", () => {
    const iframe = document.getElementById("insPreview");
    if (iframe) {
      iframe.style.display = iframe.style.display === "none" ? "block" : "none";
    }
  });

  // Auto-calculate trip days when dates change
  const fromInput = document.getElementById("insPeriodFrom");
  const toInput = document.getElementById("insPeriodTo");
  if (fromInput && toInput) {
    fromInput.addEventListener("change", _insUpdateTripDays);
    toInput.addEventListener("change", _insUpdateTripDays);
  }

  // Extract button (after filling dates)
  const extractBtn = document.getElementById("insExtractBtn");
  if (extractBtn) extractBtn.addEventListener("click", _insExtractData);
}

// ── Step 1: Select template → show date form ─────────────────────
function _insSelectTemplate(templateKey) {
  _insCurrentTemplate = templateKey;

  // Highlight selected card
  document.querySelectorAll(".ins-template-card").forEach((c) => {
    const isSelected = c.dataset.template === templateKey;
    c.style.borderColor = isSelected ? "#7c3aed" : "#334155";
    c.style.background = isSelected ? "#1e1b4b33" : "";
  });

  // Show date input form (Step 1.5)
  const dateForm = document.getElementById("insDateForm");
  if (dateForm) dateForm.style.display = "block";

  // Reset later steps
  document.getElementById("insStep2").style.display = "none";
  document.getElementById("insStep3").style.display = "none";
  document.getElementById("insResultSection").style.display = "none";

  // Scroll to date form
  dateForm.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Calculate trip days from date inputs
function _insUpdateTripDays() {
  const fromStr = document.getElementById("insPeriodFrom").value;
  const toStr = document.getElementById("insPeriodTo").value;
  const daysEl = document.getElementById("insTripDays");

  if (fromStr && toStr) {
    const from = new Date(fromStr);
    const to = new Date(toStr);
    const diffMs = to - from;
    const days = Math.max(Math.ceil(diffMs / (1000 * 60 * 60 * 24)), 1);
    daysEl.textContent = `📅 ${days} ngày`;
    daysEl.style.color = "#4ade80";
  } else {
    daysEl.textContent = "";
  }
}

// ── Step 2: Extract data with user inputs ────────────────────────
async function _insExtractData() {
  const fromInput = document.getElementById("insPeriodFrom");
  const toInput = document.getElementById("insPeriodTo");
  const destInput = document.getElementById("insDestination");
  const statusEl = document.getElementById("insExtractStatus");

  const periodFrom = fromInput.value;
  const periodTo = toInput.value;

  if (!periodFrom || !periodTo) {
    statusEl.innerHTML = '<span style="color:#ef4444;">❌ Vui lòng nhập ngày đi và ngày về!</span>';
    return;
  }

  // Convert date inputs (YYYY-MM-DD) to DD/MM/YYYY
  const fmtFrom = _formatDateForApi(periodFrom);
  const fmtTo = _formatDateForApi(periodTo);
  const destination = destInput ? destInput.value : "Worldwide";

  // Show loading
  const step2 = document.getElementById("insStep2");
  const step3 = document.getElementById("insStep3");
  const jsonDisplay = document.getElementById("insJsonDisplay");
  const templateName = document.getElementById("insTemplateName");
  const autoFieldsDisplay = document.getElementById("insAutoFieldsDisplay");

  step2.style.display = "block";
  step3.style.display = "none";
  jsonDisplay.textContent = "⏳ Đang trích xuất dữ liệu & lấy giá bảo hiểm...";
  templateName.textContent = _insCurrentTemplate === "chubb"
    ? "📋 Liberty TravelCare" : "📋 Bảo Hiểm Du Lịch Chubb";

  statusEl.innerHTML = '<span style="color:#f59e0b;">⏳ Đang xử lý...</span>';

  try {
    const res = await fetch("/api/insurance/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template: _insCurrentTemplate,
        period_from: fmtFrom,
        period_to: fmtTo,
        destination: destination,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Extract failed");

    _insOriginalSummary = data.summary;
    _insAutoFields = data.auto_fields;
    _insGrokPrompt = data.grok_prompt;

    // Display extracted JSON (original PDF data)
    jsonDisplay.textContent = JSON.stringify(data.summary, null, 2);

    // Display auto-generated fields (locked — no need for Grok)
    if (autoFieldsDisplay && data.auto_fields) {
      let afHtml = '<div style="margin-bottom:6px; font-size:12px; color:#94a3b8;">🔒 Các trường tự động (không cần Grok):</div>';
      afHtml += '<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; margin-top:6px;">';
      const fieldLabels = {
        policy_no: "🔢 Policy Number",
        customer_code: "🆔 Customer Code",
        membership_no: "📌 Membership No",
        plan: "📋 Plan Type",
        nationality: "🌏 Nationality",
        region: "🗺️ Region",
        period_from: "📅 Ngày đi",
        period_to: "📅 Ngày về",
        length_of_trip: "⏱️ Số ngày",
        total_premium: "💰 Phí bảo hiểm",
      };
      for (const [key, label] of Object.entries(fieldLabels)) {
        const val = data.auto_fields[key];
        if (val) {
          const isPremium = key === "total_premium";
          afHtml += `<div style="background:${isPremium ? '#052e16' : '#1e1b4b'}; padding:10px 14px; border-radius:8px; border:1px solid ${isPremium ? '#22c55e44' : '#7c3aed44'};">
            <div style="font-size:11px; color:#94a3b8; margin-bottom:3px;">${label}</div>
            <div style="font-size:${isPremium ? '16px' : '14px'}; font-weight:${isPremium ? '700' : '500'}; color:${isPremium ? '#4ade80' : '#e2e8f0'};">${val}</div>
          </div>`;
        }
      }
      afHtml += '</div>';
      autoFieldsDisplay.innerHTML = afHtml;
      autoFieldsDisplay.style.display = "block";
    }

    // Show Step 3
    step3.style.display = "block";
    statusEl.innerHTML = '<span style="color:#4ade80;">✅ Hoàn tất! Copy prompt và paste vào Grok.</span>';
    setTimeout(() => { statusEl.textContent = ""; }, 5000);

    step2.scrollIntoView({ behavior: "smooth", block: "start" });

  } catch (err) {
    jsonDisplay.textContent = `❌ Lỗi: ${err.message}`;
    jsonDisplay.style.color = "#ef4444";
    statusEl.innerHTML = `<span style="color:#ef4444;">❌ ${err.message}</span>`;
    setTimeout(() => { jsonDisplay.style.color = "#4ade80"; }, 3000);
  }
}

// Format YYYY-MM-DD to DD/MM/YYYY
function _formatDateForApi(dateStr) {
  const [y, m, d] = dateStr.split("-");
  return `${d}/${m}/${y}`;
}

// ── Reset to Step 1 ──────────────────────────────────────────────
function _insResetToStep1() {
  _insCurrentTemplate = null;
  _insOriginalSummary = null;
  _insAutoFields = null;
  _insGrokPrompt = "";

  document.getElementById("insDateForm").style.display = "none";
  document.getElementById("insStep2").style.display = "none";
  document.getElementById("insStep3").style.display = "none";
  document.getElementById("insResultSection").style.display = "none";

  const autoFieldsDisplay = document.getElementById("insAutoFieldsDisplay");
  if (autoFieldsDisplay) autoFieldsDisplay.style.display = "none";

  // Reset card highlights
  document.querySelectorAll(".ins-template-card").forEach((c) => {
    c.style.borderColor = "#334155";
    c.style.background = "";
  });

  // Clear inputs
  const textarea = document.getElementById("insGrokInput");
  if (textarea) textarea.value = "";
  const statusEl = document.getElementById("insExtractStatus");
  if (statusEl) statusEl.textContent = "";
}

// ── Copy Grok Prompt ─────────────────────────────────────────────
async function _insCopyPrompt() {
  const statusEl = document.getElementById("insCopyStatus");
  try {
    await navigator.clipboard.writeText(_insGrokPrompt);
    statusEl.textContent = "✅ Đã copy prompt! Paste vào Grok để lấy JSON mới.";
    statusEl.style.color = "#4ade80";
    setTimeout(() => { statusEl.textContent = ""; }, 5000);
  } catch (err) {
    const ta = document.createElement("textarea");
    ta.value = _insGrokPrompt;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    statusEl.textContent = "✅ Đã copy prompt!";
    setTimeout(() => { statusEl.textContent = ""; }, 5000);
  }
}

// ── Apply Changes ────────────────────────────────────────────────
async function _insApplyChanges() {
  const textarea = document.getElementById("insGrokInput");
  const statusEl = document.getElementById("insApplyStatus");
  const resultSection = document.getElementById("insResultSection");

  const rawJson = textarea.value.trim();
  if (!rawJson) {
    statusEl.innerHTML = '<span style="color:#ef4444;">❌ Chưa paste JSON từ Grok!</span>';
    return;
  }

  // Parse JSON — handle markdown code blocks
  let updatedData;
  try {
    let cleanJson = rawJson;
    cleanJson = cleanJson.replace(/^```json?\s*/i, "").replace(/\s*```$/i, "");
    updatedData = JSON.parse(cleanJson);
  } catch (err) {
    statusEl.innerHTML = `<span style="color:#ef4444;">❌ JSON không hợp lệ: ${err.message}</span>`;
    return;
  }

  if (!_insOriginalSummary || !_insCurrentTemplate) {
    statusEl.innerHTML = '<span style="color:#ef4444;">❌ Chưa chọn mẫu bảo hiểm!</span>';
    return;
  }

  statusEl.innerHTML = '<span style="color:#f59e0b;">⏳ Đang áp dụng thay đổi lên PDF...</span>';

  try {
    const res = await fetch("/api/insurance/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template: _insCurrentTemplate,
        original: _insOriginalSummary,
        updated: updatedData,
        auto_fields: _insAutoFields || {},
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Apply failed");

    // Show success
    statusEl.innerHTML = `<span style="color:#4ade80;">✅ Hoàn tất! Đã sửa ${data.changes_applied} trường.${data.changes_failed > 0 ? ` ⚠️ ${data.changes_failed} trường không tìm thấy.` : ""}</span>`;

    // Show result section
    resultSection.style.display = "block";

    // Show result details
    const detailsEl = document.getElementById("insResultDetails");
    let detailsHtml = '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px;">';
    data.results.forEach((r) => {
      const statusIcon = r.status === "replaced" ? "✅" :
                         r.status === "unchanged" ? "➖" : "⚠️";
      const bg = r.status === "replaced" ? "#052e16" :
                 r.status === "unchanged" ? "#1e293b" : "#451a03";
      detailsHtml += `<div style="background:${bg}; padding:8px 12px; border-radius:6px; font-size:12px;">
        ${statusIcon} <strong>${r.field}</strong>
        ${r.new_value ? `→ ${r.new_value}` : ""}
      </div>`;
    });
    detailsHtml += "</div>";
    detailsEl.innerHTML = detailsHtml;

    // Load preview
    const iframe = document.getElementById("insPreview");
    iframe.src = data.download_url;
    iframe.style.display = "block";

    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });

  } catch (err) {
    statusEl.innerHTML = `<span style="color:#ef4444;">❌ Lỗi: ${err.message}</span>`;
  }
}

// Initialize when DOM ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initInsuranceUI);
} else {
  initInsuranceUI();
}
