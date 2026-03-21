// Pipeline Connection Functions
// Extracted from app.js

// ==================== PIPELINE CONNECTION FUNCTIONS ====================


async function sendToInput() {
  const btn = document.getElementById("sendToInputBtn");
  if (!btn) return;

  // Check if output has been saved first
  try {
    const checkRes = await fetch("/api/classifier/last-result");
    const checkData = await checkRes.json();
    if (checkData.exists) {
      alert("⚠️ Vui lòng lưu kết quả phân loại trước khi chuyển!\n\nBấm nút '💾 Lưu vào output folder' trước.");
      return;
    }
  } catch(e) {}

  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Đang chuyển file...";
  try {
    const res = await fetch("/api/pipeline/send-to-input", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_dir: "booking/input" }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Lỗi: ${data.error}`);
      return;
    }
    alert(`✅ Đã chuyển ${data.count} file sang ${data.target_dir}`);
    setActiveTab("booking");
    fetchFiles();
  } catch (e) {
    alert(`Lỗi: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
  }
}


function formatStage(stage) {
  const labelMap = {
    ingest: "Trích xuất văn bản",
    summary: "Tổng hợp thông tin",
    writer: "Viết thư",
  };
  return labelMap[stage] || stage;
}

function getWriterContextValue() {
  const el = document.getElementById("writerContext");
  return el ? el.value.trim() : writerContextCache;
}

function setWriterContextValue(value) {
  writerContextCache = value || "";
  const el = document.getElementById("writerContext");
  if (el) el.value = writerContextCache;
}

function setStepLog(step, content) {
  stepLogs[step] = content || "";
  const target = stepsListEl.querySelector(`[data-step-log="${step}"]`);
  if (target) target.textContent = stepLogs[step] || "";
}

function appendStepLog(step, line) {
  const prev = stepLogs[step];
  if (!prev || prev === "Chưa chạy.") {
    stepLogs[step] = `${line}`;
  } else {
    stepLogs[step] += `\n${line}`;
  }
  const target = stepsListEl.querySelector(`[data-step-log="${step}"]`);
  if (target) target.textContent = stepLogs[step];
}

function showStepLog(step, forceOpen = true) {
  const logs = stepsListEl.querySelectorAll(".step-log");
  logs.forEach((el) => el.classList.add("hidden"));
  if (!forceOpen) {
    activeStepLog = null;
    return;
  }
  const target = stepsListEl.querySelector(`[data-step-log="${step}"]`);
  if (target) {
    target.classList.remove("hidden");
    activeStepLog = step;
  }
}

function resetDownstreamLogs(step) {
  const idx = LETTER_STEP_ORDER.indexOf(step);
  if (idx === -1) return;
  LETTER_STEP_ORDER.slice(idx + 1).forEach((s) => {
    setStepLog(s, "Chưa chạy.");
  });
}

function renderSteps(steps) {
  const stepOrder = LETTER_STEP_ORDER;
  const statusMap = {};
  (steps || []).forEach((s) => {
    statusMap[s.name] = s.done;
  });
  const rows = stepOrder
    .map((name, index) => {
      const done = Boolean(statusMap[name]);
      const prereqDone = stepOrder.slice(0, index).every((prev) => Boolean(statusMap[prev]));
      const canRun = done || prereqDone;
      const runLabel = done ? "Chạy lại" : "Chạy bước";
      const logText = stepLogs[name] || "Chưa chạy.";
      return `
        <div class="step-row">
          <div class="step-main">
            <div class="step-info">
              <div class="step-name">${formatStage(name)}</div>
              <div class="step-status">${done ? "Đã hoàn thành" : "Chưa chạy"}</div>
            </div>
            <div class="step-actions">
              <button class="step-btn" data-step="${name}" data-done="${done}" ${
                canRun ? "" : "disabled"
              }>
                ${runLabel}
              </button>
              <button class="step-log-toggle" data-step-log-toggle="${name}">Trạng thái</button>
            </div>
          </div>
          ${
            name === "writer"
              ? `<div class="writer-context-inline">
                  <label for="writerContext">Thông tin bổ sung cho bước "Viết thư"</label>
                  <textarea id="writerContext" rows="4"></textarea>
                </div>`
              : ""
          }
          <div class="step-log ${
            activeStepLog === name ? "" : "hidden"
          }" data-step-log="${name}">${logText}</div>
          ${
            !canRun
              ? `<div class="hint">Cần hoàn thành bước trước để chạy bước này.</div>`
              : ""
          }
        </div>
      `;
    })
    .join("");
  stepsListEl.innerHTML = rows;
  setWriterContextValue(writerContextCache);
}

async function loadSteps() {
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  stepsListEl.textContent = "Đang tải...";
  const res = await fetch(`/api/steps?output=${encodeURIComponent(outputPath)}`);
  const data = await res.json();
  renderSteps(data.steps || []);
  await fetchSummary();
  await fetchWriterContext();
}

async function fetchSummary() {
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  const res = await fetch(`/api/summary?output=${encodeURIComponent(outputPath)}`);
  const data = await res.json();
  summaryEl.textContent = data.summary_profile || "Chưa có dữ liệu.";
}

async function fetchWriterContext() {
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  const res = await fetch(
    `/api/writer_context?output=${encodeURIComponent(outputPath)}`
  );
  const data = await res.json();
  setWriterContextValue(data.writer_context || "");
}

async function runIngestStream(force = false) {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  setStepLog("ingest", "");
  if (force) resetDownstreamLogs("ingest");
  showStepLog("ingest", true);
  appendStepLog("ingest", "Bắt đầu: Trích xuất văn bản");

  return new Promise((resolve) => {
    const params = new URLSearchParams({
      input_dir: inputDir,
      output: outputPath,
      force: force ? "1" : "0",
    });
    const source = new EventSource(`/api/ingest_stream?${params.toString()}`);
    source.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "progress") {
        appendStepLog("ingest", data.message);
      }
      if (data.type === "done") {
        appendStepLog("ingest", "Hoàn thành: Trích xuất văn bản");
        source.close();
        resolve();
      }
    };
    source.onerror = () => {
      appendStepLog("ingest", "Lỗi khi trích xuất văn bản.");
      source.close();
      resolve();
    };
  });
}

async function runStep(step, force = false) {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  if (step === "ingest") {
    await runIngestStream(force);
    await loadSteps();
    return;
  }

  setStepLog(step, "");
  if (force) resetDownstreamLogs(step);
  showStepLog(step, true);
  appendStepLog(step, `Bắt đầu: ${formatStage(step)}`);

  const res = await fetch("/api/run_step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      input_dir: inputDir,
      output: outputPath,
      step,
      force,
      writer_context: getWriterContextValue(),
      project_id: getProjectId(),
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    if (data.error === "missing_prerequisite") {
      appendStepLog(
        step,
        `Thiếu bước trước: ${formatStage(data.missing)} (hãy chạy trước)`
      );
    } else {
      appendStepLog(step, "Lỗi khi chạy bước.");
    }
    return;
  }

  if (data.status === "cached") {
    appendStepLog(step, `Đã có cache: ${formatStage(step)}`);
  } else {
    appendStepLog(step, `Hoàn thành: ${formatStage(step)}`);
  }

  if (data.letter) {
    resultEl.textContent = data.letter || "Không có kết quả.";
  }

  await fetchSummary();
  await loadSteps();
}

function renderFileOptions() {
  // No-op: file upload pickers don't need server-side file list
}

function collectItineraryFormData() {
  return {
    participants: itParticipantsEl.value.trim(),
    additional_info: itAdditionalInfoEl.value.trim(),
    travel_purpose: itTravelPurposeEl.value.trim(),
    travel_start_date: itTravelStartDateEl.value.trim(),
    travel_end_date: itTravelEndDateEl.value.trim(),
  };
}

function applyItineraryFormData(formData = {}) {
  itParticipantsEl.value = formData.participants || "";
  itAdditionalInfoEl.value = formData.additional_info || "";
  itTravelPurposeEl.value = formData.travel_purpose || "";
  itTravelStartDateEl.value = formData.travel_start_date || "";
  itTravelEndDateEl.value = formData.travel_end_date || "";
}

function buildItinerarySummaryFromForm(formData) {
  const hasAnyValue = Object.values(formData).some((value) => Boolean(value));
  if (!hasAnyValue) return "";

  const sections = [
    "Core itinerary inputs:",
    formData.participants ? `- Participant(s): ${formData.participants}` : "",
    formData.additional_info ? `- Additional information: ${formData.additional_info}` : "",
    formData.travel_start_date && formData.travel_end_date
      ? `- Travel period: From ${formData.travel_start_date} to ${formData.travel_end_date}`
      : "",
    formData.travel_purpose ? `- travel_purpose: ${formData.travel_purpose}` : "",
    formData.travel_start_date && !formData.travel_end_date
      ? `- travel_start_date: ${formData.travel_start_date}`
      : "",
    !formData.travel_start_date && formData.travel_end_date
      ? `- travel_end_date: ${formData.travel_end_date}`
      : "",
  ];
  return sections.filter(Boolean).join("\n").trim();
}

async function runItinerary() {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputPath = itineraryOutputEl.value.trim() || "output/itinerary.html";
  const formData = collectItineraryFormData();
  const summaryProfile = buildItinerarySummaryFromForm(formData);
  const useDb = bookingSourceDbEl.checked;
  const runBtn = document.getElementById("runItineraryBtn");
  const originalBtnText = runBtn.textContent;

  // For file upload mode: read HTML content from uploaded files
  let uploadedFlightHtml = null;
  let uploadedHotelHtmls = null;
  if (!useDb) {
    const flightFiles = flightFileInputEl?.files || [];
    const hotelFiles = hotelFileInputEl?.files || [];
    if (flightFiles.length === 0 || hotelFiles.length === 0) {
      itineraryResultEl.srcdoc =
        "<p>Vui lòng chọn đủ file vé máy bay và file booking khách sạn.</p>";
      syncCombinedPreviews();
      return;
    }
    try {
      uploadedFlightHtml = await readFileAsText(flightFiles[0]);
      uploadedHotelHtmls = [];
      for (const f of hotelFiles) {
        uploadedHotelHtmls.push(await readFileAsText(f));
      }
    } catch (e) {
      itineraryResultEl.srcdoc = `<p>Lỗi đọc file: ${e.message}</p>`;
      syncCombinedPreviews();
      return;
    }
  }

  // Auto-save context silently before generating
  if (summaryProfile) {
    try {
      await fetch("/api/itinerary/context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_dir: inputDir,
          output: outputPath,
          summary_profile: summaryProfile,
          project_id: getProjectId(),
        }),
      });
    } catch (e) { /* ignore save errors */ }
  }

  runBtn.textContent = "⏳ Đang xử lý...";
  runBtn.disabled = true;

  // Build step progress UI
  const itStepLabels = {
    1: "Tải dữ liệu booking",
    2: "Trích xuất nội dung",
    3: "AI viết lịch trình chi tiết",
    4: "Lưu kết quả",
  };
  itineraryResultEl.srcdoc = `<html><body style="font-family:Arial,sans-serif;padding:16px;margin:0;">
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px;">
      <div style="font-weight:600; margin-bottom:12px; color:#334155;">📋 Tiến trình tạo lịch trình</div>
      ${Object.entries(itStepLabels).map(([k, v]) => `
        <div id="it-step-${k}" style="display:flex; align-items:center; gap:8px; padding:6px 8px; margin:4px 0; border-radius:6px; background:#fff; border:1px solid #e2e8f0; transition:all 0.3s;">
          <span id="it-step-icon-${k}" style="font-size:16px;">⬜</span>
          <span style="color:#475569; font-size:0.9em;">${v}</span>
          <span id="it-step-msg-${k}" style="margin-left:auto; font-size:0.8em; color:#94a3b8;"></span>
        </div>
      `).join("")}
    </div>
  </body></html>`;

  function updateItStep(step, msg) {
    const iframe = itineraryResultEl;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc) return;
    const iconEl = doc.getElementById("it-step-icon-" + step);
    const msgEl = doc.getElementById("it-step-msg-" + step);
    const rowEl = doc.getElementById("it-step-" + step);
    if (!iconEl) return;
    if (msg.startsWith("✅")) {
      iconEl.textContent = "✅";
      if (rowEl) { rowEl.style.background = "#f0fdf4"; rowEl.style.borderColor = "#86efac"; }
      if (msgEl) { msgEl.textContent = "Xong"; msgEl.style.color = "#16a34a"; }
    } else if (msg.startsWith("⏳")) {
      iconEl.textContent = "⏳";
      if (rowEl) { rowEl.style.background = "#fffbeb"; rowEl.style.borderColor = "#fcd34d"; }
      if (msgEl) { msgEl.textContent = "Đang xử lý..."; msgEl.style.color = "#d97706"; }
    } else if (msg.startsWith("❌")) {
      iconEl.textContent = "❌";
      if (rowEl) { rowEl.style.background = "#fef2f2"; rowEl.style.borderColor = "#fca5a5"; }
      if (msgEl) { msgEl.textContent = msg; msgEl.style.color = "#dc2626"; }
    }
  }

  try {
    const payload = {
      input_dir: inputDir,
      output: outputPath,
      summary_profile: summaryProfile,
      project_id: getProjectId(),
    };
    if (useDb) {
      payload.from_db = true;
    } else {
      // Send uploaded HTML content directly
      payload.flight_html = uploadedFlightHtml;
      payload.hotel_htmls = uploadedHotelHtmls;
    }

    const res = await fetch("/api/itinerary/run_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          if (evt.step === -1) {
            updateItStep(1, evt.msg);
            return;
          }
          updateItStep(evt.step, evt.msg);
          if (evt.step === 5 && evt.data) {
            finalData = evt.data;
          }
        } catch (e) { /* skip */ }
      }
    }

    if (finalData) {
      itineraryResultEl.srcdoc = finalData.itinerary || "<p>Không có kết quả.</p>";
    } else {
      itineraryResultEl.srcdoc = "<p>❌ Không nhận được kết quả từ server.</p>";
    }
    syncCombinedPreviews();
  } catch (error) {
    itineraryResultEl.srcdoc = `<p>❌ Lỗi: ${error.message}</p>`;
    syncCombinedPreviews();
  } finally {
    runBtn.textContent = originalBtnText;
    runBtn.disabled = false;
  }
}

async function loadLatestItinerary() {
  const outputPath = itineraryOutputEl.value.trim() || "output/itinerary.html";
  const res = await fetch(
    `/api/itinerary/latest?output=${encodeURIComponent(outputPath)}`
  );
  const data = await res.json();
  itineraryResultEl.srcdoc = data.itinerary || "<p>Chưa chạy.</p>";
  syncCombinedPreviews();
}

async function loadItineraryContext() {
  const outputPath = itineraryOutputEl.value.trim() || "output/itinerary.html";
  const res = await fetch(
    `/api/itinerary/context/latest?output=${encodeURIComponent(outputPath)}`
  );
  const data = await res.json();
  summaryItineraryEl.textContent = data.summary_profile || "Chưa có dữ liệu.";
  applyItineraryFormData(data.form_data || {});
}

async function saveItineraryContext() {
  const outputPath = itineraryOutputEl.value.trim() || "output/itinerary.html";
  const formData = collectItineraryFormData();
  const previewSummary = buildItinerarySummaryFromForm(formData);

  if (!previewSummary) {
    summaryItineraryEl.textContent =
      "Vui lòng nhập ít nhất một trường thông tin cần thiết.";
    return;
  }

  const originalText = saveItineraryContextBtn.textContent;
  saveItineraryContextBtn.disabled = true;
  saveItineraryContextBtn.textContent = "Đang lưu...";

  try {
    summaryItineraryEl.textContent = "Đang lưu thông tin lịch trình...";
    const res = await fetch("/api/itinerary/context/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output: outputPath,
        form_data: formData,
        project_id: getProjectId(),
      }),
    });

    let data;
    try {
      const text = await res.text();
      data = JSON.parse(text);
    } catch (e) {
      summaryItineraryEl.textContent =
        "Lỗi lưu thông tin: Server không trả JSON (có thể bạn chưa restart server).";
      return;
    }

    if (!res.ok) {
      summaryItineraryEl.textContent = `Lỗi lưu thông tin: ${data.error || "không xác định"}`;
      return;
    }

    summaryItineraryEl.textContent = data.summary_profile || "Không có dữ liệu.";
  } catch (error) {
    summaryItineraryEl.textContent = `Lỗi lưu thông tin: ${error.message}`;
  } finally {
    saveItineraryContextBtn.disabled = false;
    saveItineraryContextBtn.textContent = originalText;
  }
}

function syncCombinedPreviews() {
  if (combinedItineraryResultEl) {
    combinedItineraryResultEl.srcdoc =
      itineraryResultEl?.srcdoc || "<p>Chưa có kết quả lịch trình.</p>";
  }
  if (combinedFlightBookingResultEl) {
    combinedFlightBookingResultEl.srcdoc =
      flightBookingResultEl?.srcdoc || "<p>Chưa có kết quả booking máy bay.</p>";
  }
  if (combinedHotelBookingResultEl) {
    if (hotelHtmls && hotelHtmls.length > 0) {
      combinedHotelBookingResultEl.srcdoc = buildCombinedHotelsHtml(hotelHtmls);
    } else {
      combinedHotelBookingResultEl.srcdoc =
        hotelBookingResultEl?.srcdoc || "<p>Chưa có kết quả booking khách sạn.</p>";
    }
  }
}

function setBookingMode(mode = "hotel") {
  const isFlight = mode === "flight";
  if (bookingHotelPageEl) bookingHotelPageEl.classList.toggle("hidden", isFlight);
  if (bookingFlightPageEl) bookingFlightPageEl.classList.toggle("hidden", !isFlight);
  if (manualBookingOverrideSectionEl) manualBookingOverrideSectionEl.classList.toggle("hidden", isFlight);

  if (bookingModeHotelBtn) {
    bookingModeHotelBtn.style.background = isFlight ? "#64748b" : "#2563eb";
  }
  if (bookingModeFlightBtn) {
    bookingModeFlightBtn.style.background = isFlight ? "#2563eb" : "#64748b";
  }

  if (isFlight) {
    prefillSerpPassengerInfo();
  }
}

function setBookingPart(part) {
  setBookingMode(part === "flight" ? "flight" : "hotel");
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function loadTranslationTemplates() {
  const res = await fetch("/api/translate/templates");
  const data = await res.json();
  translationTemplatesCache = data.templates || [];
}

async function loadTranslationSourceFiles() {
  const inputDir = inputDirEl.value.trim() || "input";
  const res = await fetch(`/api/files?input_dir=${encodeURIComponent(inputDir)}`);
  const data = await res.json();
  translationSourceFilesCache = data.files || [];
}

function translationTemplateOptionsHtml(selectedName = "auto") {
  let html = `<option value="auto" ${selectedName === "auto" ? "selected" : ""}>🤖 Tự động nhận diện</option>`;
  if (translationTemplatesCache.length) {
    html += translationTemplatesCache
      .map((tpl) => {
        const sel = tpl.name === selectedName ? "selected" : "";
        return `<option value="${escapeHtml(tpl.name)}" ${sel}>${escapeHtml(tpl.name)}</option>`;
      })
      .join("");
  }
  return html;
}

function translationFileOptionsHtml(selectedValue = "") {
  const options = ['<option value="">-- Chọn file cần dịch --</option>'];
  for (const f of translationSourceFilesCache) {
    const value = f.rel_path || f.name || "";
    const sel = value === selectedValue ? "selected" : "";
    options.push(
      `<option value="${escapeHtml(value)}" ${sel}>${escapeHtml(value)}</option>`
    );
  }
  return options.join("");
}

function updateTranslateFlowStep(flowId, step, state, message = "") {
  const iconEl = document.getElementById(`transStepIcon-${flowId}-${step}`);
  const msgEl = document.getElementById(`transStepMsg-${flowId}-${step}`);
  const rowEl = document.getElementById(`transStepRow-${flowId}-${step}`);
  if (!iconEl || !msgEl || !rowEl) return;

  if (state === "running") {
    iconEl.textContent = "⏳";
    rowEl.style.background = "#fffbeb";
    rowEl.style.borderColor = "#fcd34d";
    msgEl.textContent = message || "Đang xử lý...";
    msgEl.style.color = "#d97706";
  } else if (state === "done") {
    iconEl.textContent = "✅";
    rowEl.style.background = "#f0fdf4";
    rowEl.style.borderColor = "#86efac";
    msgEl.textContent = message || "Xong";
    msgEl.style.color = "#16a34a";
  } else if (state === "error") {
    iconEl.textContent = "❌";
    rowEl.style.background = "#fef2f2";
    rowEl.style.borderColor = "#fca5a5";
    msgEl.textContent = message || "Lỗi";
    msgEl.style.color = "#dc2626";
  } else {
    iconEl.textContent = "⬜";
    rowEl.style.background = "#fff";
    rowEl.style.borderColor = "#e2e8f0";
    msgEl.textContent = "";
    msgEl.style.color = "#94a3b8";
  }
}

function createTranslateFlow() {
  if (!translateFlowsContainerEl) return;
  translationFlowCounter += 1;
  const flowId = translationFlowCounter;
  const html = `
    <section class="translate-flow-card" id="translateFlow-${flowId}" style="border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:16px; background:#fff;">
      <div class="card-header-row">
        <h3 style="margin:0;">Luồng dịch #${flowId}</h3>
      </div>

      <!-- Upload row -->
      <div class="row" style="margin-top:10px;">
        <div>
          <label for="transUpload-${flowId}">Upload file cần dịch</label>
          <div style="display:flex; gap:8px; align-items:center; margin-top:6px; flex-wrap:wrap;">
            <input id="transUpload-${flowId}" type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.webp,.txt,.doc,.docx" />
            <button id="transUploadBtn-${flowId}" type="button" style="padding:8px 14px; background:#4f46e5;">📤 Upload</button>
          </div>
          <input id="transUploadedRef-${flowId}" type="hidden" value="" />
          <input id="transUploadedName-${flowId}" type="hidden" value="" />
          <div id="transFileInfo-${flowId}" style="margin-top:6px; font-size:0.85em; color:#64748b;"></div>
        </div>
        <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
          <div>
            <label for="transSourceLang-${flowId}" style="font-size:0.85em; display:block; margin-bottom:4px;">Ngôn ngữ nguồn</label>
            <select id="transSourceLang-${flowId}" style="padding:6px 10px; border-radius:6px; border:1px solid #cbd5e1; font-size:0.85em;">
              <option value="tiếng Việt" selected>🇻🇳 Tiếng Việt</option>
              <option value="tiếng Trung">🇨🇳 Tiếng Trung</option>
              <option value="tiếng Nhật">🇯🇵 Tiếng Nhật</option>
              <option value="tiếng Hàn">🇰🇷 Tiếng Hàn</option>
              <option value="tiếng Pháp">🇫🇷 Tiếng Pháp</option>
              <option value="ngôn ngữ gốc (tự nhận diện)">🌐 Tự nhận diện</option>
            </select>
          </div>
          <div>
            <label for="transTemplate-${flowId}" style="font-size:0.85em; display:block; margin-bottom:4px;">HTML template</label>
            <select id="transTemplate-${flowId}" style="padding:6px 10px; border-radius:6px; border:1px solid #cbd5e1; font-size:0.85em;">${translationTemplateOptionsHtml("auto")}</select>
          </div>
        </div>
        <button id="transRunBtn-${flowId}" style="background:#2563eb; align-self:flex-end;">🚀 OCR + Dịch + Tạo HTML</button>
      </div>

      <div class="translate-status" id="transStatus-${flowId}" style="margin-top:8px; padding:6px; font-size:0.9em;">Chưa chạy.</div>

      <!-- Progress steps -->
      <div style="margin-top:8px;">
        <div id="transStepRow-${flowId}-1" style="display:flex; gap:8px; align-items:center; border:1px solid #e2e8f0; border-radius:6px; padding:6px 8px; margin-bottom:4px;">
          <span id="transStepIcon-${flowId}-1">⬜</span>
          <span style="font-size:0.9em; color:#475569;">OCR + Dịch sang tiếng Anh</span>
          <span id="transStepMsg-${flowId}-1" style="margin-left:auto; font-size:0.8em; color:#94a3b8;"></span>
        </div>
        <div id="transStepRow-${flowId}-2" style="display:flex; gap:8px; align-items:center; border:1px solid #e2e8f0; border-radius:6px; padding:6px 8px;">
          <span id="transStepIcon-${flowId}-2">⬜</span>
          <span style="font-size:0.9em; color:#475569;">Tạo HTML theo template</span>
          <span id="transStepMsg-${flowId}-2" style="margin-left:auto; font-size:0.8em; color:#94a3b8;"></span>
        </div>
      </div>

      <!-- OCR + Translation textareas side by side -->
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px;">
        <div>
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
            <label style="font-weight:600; font-size:0.9em;">🧾 Văn bản OCR</label>
            <button type="button" class="trans-copy-btn" data-target="transOcr-${flowId}" style="padding:2px 8px; font-size:0.8em; background:#64748b; border:none; color:#fff; border-radius:4px; cursor:pointer;">📋 Copy</button>
          </div>
          <textarea id="transOcr-${flowId}" style="width:100%; min-height:180px; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:0.85em; font-family:monospace; resize:vertical;" placeholder="Chưa có dữ liệu OCR..."></textarea>
        </div>
        <div>
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
            <label style="font-weight:600; font-size:0.9em;">🌐 Bản dịch tiếng Anh</label>
            <button type="button" class="trans-copy-btn" data-target="transTranslated-${flowId}" style="padding:2px 8px; font-size:0.8em; background:#64748b; border:none; color:#fff; border-radius:4px; cursor:pointer;">📋 Copy</button>
          </div>
          <textarea id="transTranslated-${flowId}" style="width:100%; min-height:180px; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:0.85em; font-family:monospace; resize:vertical;" placeholder="Chưa có bản dịch..."></textarea>
        </div>
      </div>

      <!-- Rebuild HTML button -->
      <div style="margin-top:8px; display:flex; gap:8px; align-items:center;">
        <button id="transRebuildBtn-${flowId}" type="button" style="background:#7c3aed; padding:8px 14px;">🔄 Tạo lại HTML (từ bản dịch đã sửa)</button>
        <span id="transRebuildStatus-${flowId}" style="font-size:0.85em; color:#64748b;"></span>
      </div>

      <!-- HTML Source Editor -->
      <details style="margin-top:12px;">
        <summary style="cursor:pointer; font-weight:600; font-size:0.9em;">✏️ Sửa HTML source code</summary>
        <div style="margin-top:6px;">
          <textarea id="transHtmlSource-${flowId}" style="width:100%; min-height:250px; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:0.82em; font-family:monospace; resize:vertical;" placeholder="HTML source code sẽ hiện ở đây sau khi tạo..."></textarea>
          <div style="margin-top:6px; display:flex; gap:8px;">
            <button id="transApplyHtmlBtn-${flowId}" type="button" style="background:#0ea5e9; padding:6px 14px;">▶️ Áp dụng (reload preview)</button>
            <button type="button" class="trans-copy-btn" data-target="transHtmlSource-${flowId}" style="padding:6px 14px; background:#64748b; border:none; color:#fff; border-radius:4px; cursor:pointer;">📋 Copy HTML</button>
          </div>
        </div>
      </details>

      <!-- Save row -->
      <div class="row" style="margin-top:12px; align-items:center;">
        <div style="flex:1;">
          <label for="transSaveName-${flowId}">Tên file lưu</label>
          <input id="transSaveName-${flowId}" type="text" placeholder="VD: khai-sinh-da-dich.html" style="width:100%;" />
        </div>
        <button id="transSaveHtmlBtn-${flowId}" type="button" style="background:#16a34a; padding:8px 14px;">💾 Lưu HTML</button>
        <button id="transSavePdfBtn-${flowId}" type="button" style="background:#dc2626; padding:8px 14px;">📥 Lưu PDF</button>
      </div>

      <!-- HTML Preview iframe -->
      <div style="margin-top:12px;">
        <label style="font-weight:600;">Kết quả HTML</label>
        <iframe id="transPreview-${flowId}" style="width:100%; height:85vh; border:1px solid #cbd5e1; border-radius:6px; margin-top:4px; background:#f8fafc;" title="Translation HTML Preview"></iframe>
      </div>
    </section>
  `;
  translateFlowsContainerEl.insertAdjacentHTML("beforeend", html);

  // Auto-scroll to new flow with highlight
  const newCard = document.getElementById(`translateFlow-${flowId}`);
  if (newCard) {
    newCard.scrollIntoView({ behavior: "smooth", block: "start" });
    newCard.style.transition = "box-shadow 0.3s ease";
    newCard.style.boxShadow = "0 0 0 3px #3b82f6";
    setTimeout(() => { newCard.style.boxShadow = ""; }, 2000);
  }

  // Event listeners
  const runBtn = document.getElementById(`transRunBtn-${flowId}`);
  if (runBtn) runBtn.addEventListener("click", () => runTranslateFlow(flowId));

  const uploadBtn = document.getElementById(`transUploadBtn-${flowId}`);
  if (uploadBtn) uploadBtn.addEventListener("click", () => uploadTranslateFile(flowId));

  const saveBtn = document.getElementById(`transSaveHtmlBtn-${flowId}`);
  if (saveBtn) saveBtn.addEventListener("click", () => saveTranslateHtml(flowId));

  const rebuildBtn = document.getElementById(`transRebuildBtn-${flowId}`);
  if (rebuildBtn) rebuildBtn.addEventListener("click", () => rebuildTranslateHtml(flowId));

  const applyHtmlBtn = document.getElementById(`transApplyHtmlBtn-${flowId}`);
  if (applyHtmlBtn) {
    applyHtmlBtn.addEventListener("click", () => {
      const srcEl = document.getElementById(`transHtmlSource-${flowId}`);
      const previewEl = document.getElementById(`transPreview-${flowId}`);
      if (srcEl && previewEl) previewEl.srcdoc = srcEl.value;
    });
  }

  const savePdfBtn = document.getElementById(`transSavePdfBtn-${flowId}`);
  if (savePdfBtn) {
    savePdfBtn.addEventListener("click", async () => {
      const previewEl = document.getElementById(`transPreview-${flowId}`);

      if (!previewEl || !previewEl.srcdoc) {
        alert("Chưa có bản dịch để xuất PDF.");
        return;
      }

      // Show loading state
      const origText = savePdfBtn.textContent;
      savePdfBtn.disabled = true;
      savePdfBtn.textContent = "⏳ Đang chuẩn bị PDF...";

      try {
        // Get stored original File object (try cache first, then fallback to input)
        let originalFile = (window._transOriginalFiles || {})[flowId];
        if (!originalFile) {
          const inputEl = document.getElementById(`transUpload-${flowId}`);
          if (inputEl && inputEl.files && inputEl.files[0]) {
            originalFile = inputEl.files[0];
            console.log("[CombinedPDF] File from input fallback:", originalFile.name);
          }
        }
        console.log("[CombinedPDF] originalFile:", originalFile ? originalFile.name : "NONE");

        // Fetch original pages (POST file directly) + certification template concurrently
        let origFetch = Promise.resolve(null);
        if (originalFile) {
          const fd = new FormData();
          fd.append("file", originalFile);
          origFetch = fetch("/api/translate/original_pages", { method: "POST", body: fd });
        }
        const [origRes, certRes] = await Promise.all([
          origFetch,
          fetch("/api/translate/certification_template")
        ]);

        // --- Part 1: Original document pages as images ---
        let originalPagesHtml = "";
        if (origRes && origRes.ok) {
          const origData = await origRes.json();
          console.log("[CombinedPDF] Original pages received:", origData.pages ? origData.pages.length : 0);
          if (origData.pages && origData.pages.length > 0) {
            originalPagesHtml = origData.pages.map((p, i) => {
              return `<div class="original-page">
                <img src="${p.data_url}" style="width:100%; height:auto; display:block;" />
              </div>`;
            }).join("\n");
          }
        } else {
          console.warn("[CombinedPDF] Original pages fetch failed:", origRes ? origRes.status : "null response");
        }

        // --- Part 2: Translated HTML from preview iframe ---
        const translatedHtml = previewEl.srcdoc || "";

        // --- Part 3: Certification template with current date ---
        let certHtml = "";
        if (certRes && certRes.ok) {
          const certData = await certRes.json();
          certHtml = certData.html || "";
          // Replace hardcoded date with current date (DD/MM/YYYY)
          const now = new Date();
          const dd = String(now.getDate()).padStart(2, "0");
          const mm = String(now.getMonth() + 1).padStart(2, "0");
          const yyyy = now.getFullYear();
          const currentDate = `${dd}/${mm}/${yyyy}`;
          // Replace the date in the template (pattern: Date: DD/MM/YYYY)
          certHtml = certHtml.replace(/Date:\s*\d{2}\/\d{2}\/\d{4}/, `Date: ${currentDate}`);
        }

        // --- Extract styles and body from translated HTML ---
        const extractStyles = (html) => {
          const styles = [];
          const regex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
          let m;
          while ((m = regex.exec(html)) !== null) styles.push(m[1]);
          return styles.join("\n");
        };
        const extractBody = (html) => {
          const m = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
          return m ? m[1] : html;
        };

        // Scope CSS to avoid conflicts
        const scopeStyles = (css, scopeClass) => {
          // Properties that must be stripped from body/html scoped rules
          // (they break the parent .doc-section layout)
          const bodyStripProps = /\b(display|padding|margin|background[^:]*|justify-content|align-items|min-height|height|overflow)\s*:[^;]+;?/gi;
          return css.replace(/([^{}@]+)\{([^{}]+)\}/g, (match, sel, body) => {
            let isBodyRule = false;
            const scopedSel = sel.split(",").map(s => {
              s = s.trim();
              if (!s || s.startsWith("@") || s.startsWith("/*")) return s;
              if (s === "body" || s === "html") { isBodyRule = true; return "." + scopeClass; }
              return "." + scopeClass + " " + s;
            }).join(", ");
            // Strip layout-breaking properties from body/html rules
            const cleanBody = isBodyRule ? body.replace(bodyStripProps, "") : body;
            return scopedSel + "{" + cleanBody + "}";
          });
        };

        // Build combined sections
        let allStyles = "";
        let allSections = "";

        // Section 1: Original pages (just images, no special CSS needed)
        if (originalPagesHtml) {
          allSections += `<div class="doc-section doc-original">${originalPagesHtml}</div>\n`;
        }

        // Section 2: Translated document (scoped CSS)
        if (translatedHtml) {
          const transStyles = extractStyles(translatedHtml);
          const transBody = extractBody(translatedHtml);
          allStyles += `/* Translated doc styles */\n${scopeStyles(transStyles, "doc-translated")}\n`;
          allStyles += `.doc-translated .a4, .doc-translated .a4-page { min-height: auto !important; height: auto !important; }\n`;
          allSections += `<div class="doc-section doc-translated">${transBody}</div>\n`;
        }

        // Section 3: Certification page (scoped CSS)
        if (certHtml) {
          const certStyles = extractStyles(certHtml);
          const certBody = extractBody(certHtml);
          allStyles += `/* Certification styles */\n${scopeStyles(certStyles, "doc-cert")}\n`;
          allStyles += `.doc-cert .a4-page { min-height: auto !important; height: auto !important; }\n`;
          allSections += `<div class="doc-section doc-cert">${certBody}</div>\n`;
        }

        // Build final combined HTML
        const combinedHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Combined Translation PDF</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #fff; margin: 0; padding: 0; display: block !important; }
    .doc-section { display: block !important; width: 100% !important; overflow: hidden; }
    .doc-section + .doc-section { page-break-before: always; }
    .original-page { display: block; width: 100%; }
    .original-page + .original-page { page-break-before: always; }
    .original-page img { width: 100%; height: auto; display: block; }
    @media print {
      @page { size: A4; margin: 0; }
      .doc-section + .doc-section { page-break-before: always !important; }
      .original-page + .original-page { page-break-before: always !important; }
    }
    ${allStyles}
  </style>
</head>
<body>
  ${allSections}
</body>
</html>`;

        console.log("[CombinedPDF] Sections - original:", !!originalPagesHtml, "translated:", !!translatedHtml, "cert:", !!certHtml);

        const printWin = window.open("", "_blank");
        if (!printWin) {
          alert("Trình duyệt chặn popup. Vui lòng cho phép popup rồi thử lại.");
          return;
        }
        printWin.document.open();
        printWin.document.write(combinedHtml);
        printWin.document.close();

        // Wait for ALL images to load before printing
        const allImgs = printWin.document.querySelectorAll("img");
        console.log("[CombinedPDF] Total images to load:", allImgs.length);
        if (allImgs.length > 0) {
          let loaded = 0;
          const checkPrint = () => { if (++loaded >= allImgs.length) setTimeout(() => printWin.print(), 300); };
          allImgs.forEach(img => {
            if (img.complete) { checkPrint(); }
            else { img.onload = checkPrint; img.onerror = checkPrint; }
          });
          // Fallback: print after 5s even if images haven't finished
          setTimeout(() => { if (loaded < allImgs.length) printWin.print(); }, 5000);
        } else {
          setTimeout(() => printWin.print(), 500);
        }

      } catch (err) {
        console.error("Combined PDF error:", err);
        alert("Lỗi xuất PDF: " + (err.message || err));
      } finally {
        savePdfBtn.disabled = false;
        savePdfBtn.textContent = origText;
      }
    });
  }

  // Copy buttons
  const flowCard = document.getElementById(`translateFlow-${flowId}`);
  if (flowCard) {
    flowCard.querySelectorAll(".trans-copy-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-target");
        const el = targetId ? document.getElementById(targetId) : null;
        if (el) {
          const text = el.value !== undefined ? el.value : el.textContent;
          navigator.clipboard.writeText(text || "").then(() => {
            const orig = btn.textContent;
            btn.textContent = "✅ Đã copy!";
            setTimeout(() => { btn.textContent = orig; }, 1500);
          });
        }
      });
    });
  }
}

// Cache uploaded File objects for combined PDF export (survives server restart)
const _transOriginalFiles = window._transOriginalFiles || (window._transOriginalFiles = {});

async function uploadTranslateFile(flowId) {
  const inputEl = document.getElementById(`transUpload-${flowId}`);
  const statusEl = document.getElementById(`transStatus-${flowId}`);
  const uploadBtn = document.getElementById(`transUploadBtn-${flowId}`);
  const uploadedRefEl = document.getElementById(`transUploadedRef-${flowId}`);
  const uploadedNameEl = document.getElementById(`transUploadedName-${flowId}`);
  const fileInfoEl = document.getElementById(`transFileInfo-${flowId}`);
  if (!inputEl || !statusEl || !uploadBtn || !uploadedRefEl || !uploadedNameEl) return;

  const file = inputEl.files && inputEl.files[0];
  if (!file) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Vui lòng chọn file để upload.</span>`;
    return;
  }

  const originalText = uploadBtn.textContent;
  uploadBtn.disabled = true;
  uploadBtn.textContent = "⏳ Đang upload...";
  statusEl.textContent = "Đang upload file...";

  try {
    const fd = new FormData();
    fd.append("file", file);
    const pid = getProjectId();
    const url = "/api/translate/upload" + (pid ? `?project_id=${pid}` : "");
    const res = await fetch(url, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ Upload lỗi: ${escapeHtml(data.error || "không xác định")}</span>`;
      return;
    }

    const fileRef = data.file_ref;
    const uploadedDisplayName = data.filename || file.name;
    uploadedRefEl.value = fileRef;
    uploadedNameEl.value = uploadedDisplayName;
    // Store File object for combined PDF export
    _transOriginalFiles[flowId] = file;
    // File preview info
    const sizeKB = (file.size / 1024).toFixed(1);
    const ext = uploadedDisplayName.split(".").pop().toUpperCase();
    if (fileInfoEl) {
      fileInfoEl.innerHTML = `📄 <b>${escapeHtml(uploadedDisplayName)}</b> — ${sizeKB} KB — ${ext}`;
    }
    // Auto-suggest save name
    const saveNameEl = document.getElementById(`transSaveName-${flowId}`);
    if (saveNameEl && !saveNameEl.value) {
      const base = uploadedDisplayName.replace(/\.[^.]+$/, "");
      saveNameEl.value = `${base}.translated.html`;
    }
    statusEl.innerHTML = `<span style="color:#16a34a;">✅ Upload thành công: <b>${escapeHtml(uploadedDisplayName)}</b> (${sizeKB} KB)</span>`;
  } catch (e) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Upload lỗi: ${escapeHtml(e.message)}</span>`;
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = originalText;
  }
}

async function saveTranslateHtml(flowId) {
  const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
  const saveNameEl = document.getElementById(`transSaveName-${flowId}`);
  const saveBtn = document.getElementById(`transSaveHtmlBtn-${flowId}`);
  const statusEl = document.getElementById(`transStatus-${flowId}`);
  if (!htmlSrcEl || !saveNameEl || !saveBtn || !statusEl) return;

  const htmlContent = (htmlSrcEl.value || "").trim();
  const fileName = (saveNameEl.value || "").trim();
  if (!htmlContent) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Chưa có HTML để lưu.</span>`;
    return;
  }
  if (!fileName) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Vui lòng nhập tên file trước khi lưu.</span>`;
    return;
  }

  const original = saveBtn.textContent;
  saveBtn.disabled = true;
  saveBtn.textContent = "⏳ Đang lưu...";
  try {
    const res = await fetch("/api/translate/save_html", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_name: fileName,
        html_content: htmlContent,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lưu HTML lỗi: ${escapeHtml(data.error || "không xác định")}</span>`;
      return;
    }
    statusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã lưu HTML: <b>${escapeHtml(data.saved_name || fileName)}</b> (dich/html)</span>`;
  } catch (e) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lưu HTML lỗi: ${escapeHtml(e.message)}</span>`;
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = original;
  }
}

async function rebuildTranslateHtml(flowId) {
  const translatedEl = document.getElementById(`transTranslated-${flowId}`);
  const ocrEl = document.getElementById(`transOcr-${flowId}`);
  const templateEl = document.getElementById(`transTemplate-${flowId}`);
  const previewEl = document.getElementById(`transPreview-${flowId}`);
  const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
  const rebuildBtn = document.getElementById(`transRebuildBtn-${flowId}`);
  const rebuildStatusEl = document.getElementById(`transRebuildStatus-${flowId}`);
  if (!translatedEl || !rebuildBtn) return;

  const translatedText = (translatedEl.value || "").trim();
  if (!translatedText) {
    if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Chưa có bản dịch để tạo HTML.</span>`;
    return;
  }

  const original = rebuildBtn.textContent;
  rebuildBtn.disabled = true;
  rebuildBtn.textContent = "⏳ Đang tạo lại...";
  if (rebuildStatusEl) rebuildStatusEl.textContent = "";

  try {
    const res = await fetch("/api/translate/rebuild_html", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        translated_text: translatedText,
        ocr_text: ocrEl ? ocrEl.value : "",
        template_name: templateEl ? templateEl.value : "a4.html",
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      const errMsg = data.error === "quota_exceeded"
        ? `⚠️ HẾT QUOTA OpenAI! ${data.detail || "Vui lòng kiểm tra billing."}`
        : `❌ ${data.error || "Lỗi"}`;
      if (data.error === "quota_exceeded") alert(errMsg);
      if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#dc2626;font-weight:bold;">${escapeHtml(errMsg)}</span>`;
      return;
    }
    const newHtml = data.html || "";
    if (previewEl) previewEl.srcdoc = newHtml;
    if (htmlSrcEl) htmlSrcEl.value = newHtml;
    if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã tạo lại HTML thành công.</span>`;
  } catch (e) {
    if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#dc2626;">❌ ${escapeHtml(e.message)}</span>`;
  } finally {
    rebuildBtn.disabled = false;
    rebuildBtn.textContent = original;
  }
}

async function runTranslateFlow(flowId) {
  const templateEl = document.getElementById(`transTemplate-${flowId}`);
  const runBtn = document.getElementById(`transRunBtn-${flowId}`);
  const statusEl = document.getElementById(`transStatus-${flowId}`);
  const ocrEl = document.getElementById(`transOcr-${flowId}`);
  const translatedEl = document.getElementById(`transTranslated-${flowId}`);
  const previewEl = document.getElementById(`transPreview-${flowId}`);
  const uploadedRefEl = document.getElementById(`transUploadedRef-${flowId}`);
  const uploadedNameEl = document.getElementById(`transUploadedName-${flowId}`);
  const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
  const saveNameEl = document.getElementById(`transSaveName-${flowId}`);
  const sourceLangEl = document.getElementById(`transSourceLang-${flowId}`);
  if (!templateEl || !runBtn || !statusEl || !ocrEl || !translatedEl || !previewEl || !uploadedRefEl || !uploadedNameEl || !htmlSrcEl || !saveNameEl) return;

  const inputFile = (uploadedRefEl.value || "").trim();
  const templateName = templateEl.value || "a4.html";
  const sourceLang = sourceLangEl ? sourceLangEl.value : "tiếng Việt";
  if (!inputFile) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Vui lòng upload file trước khi chạy.</span>`;
    return;
  }

  const originalText = runBtn.textContent;
  runBtn.disabled = true;
  runBtn.textContent = "⏳ Đang chạy...";
  statusEl.textContent = "Đang xử lý...";
  updateTranslateFlowStep(flowId, 1, "idle");
  updateTranslateFlowStep(flowId, 2, "idle");
  updateTranslateFlowStep(flowId, 3, "idle");

  try {
    const res = await fetch("/api/translate/run_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_dir: inputDirEl.value.trim() || "input",
        file_ref: inputFile,
        template_name: templateName,
        flow_id: flowId,
        project_id: getProjectId(),
        source_lang: sourceLang,
      }),
    });
    if (!res.ok || !res.body) {
      let detail = "Không thể chạy dịch.";
      try {
        const data = await res.json();
        detail = data.error || detail;
      } catch (e) {}
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ ${escapeHtml(detail)}</span>`;
      updateTranslateFlowStep(flowId, 1, "error", detail);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let evt = null;
        try {
          evt = JSON.parse(line.slice(6));
        } catch (e) {
          continue;
        }
        const step = Number(evt.step || 0);
        const msg = String(evt.msg || "");
        if (step === -1) {
          const isQuota = msg.toLowerCase().includes("quota") || msg.includes("HẾT QUOTA");
          if (isQuota) alert(msg);
          statusEl.innerHTML = `<span style="color:#dc2626;${isQuota ? 'font-weight:bold;font-size:1.1em;' : ''}">${isQuota ? '⚠️' : '❌'} ${escapeHtml(msg || "Có lỗi xảy ra.")}</span>`;
          updateTranslateFlowStep(flowId, 1, "error", msg);
          updateTranslateFlowStep(flowId, 2, "error", msg);
          return;
        }
        if (step >= 1 && step <= 2) {
          if (msg.startsWith("✅")) {
            updateTranslateFlowStep(flowId, step, "done", msg.replace(/^✅\s*/, ""));
          } else if (msg.startsWith("⏳") || msg.startsWith("🔄")) {
            updateTranslateFlowStep(flowId, step, "running", msg.replace(/^[⏳🔄]\s*/, ""));
          }
        }
        if (step === 3 && evt.data) {
          finalData = evt.data;
        }
      }
    }

    if (finalData) {
      ocrEl.value = finalData.translated_text || "(OCR+Dịch gộp — xem bên phải)";
      translatedEl.value = finalData.translated_text || "Không có bản dịch.";
      const htmlContent = finalData.html || "<p>Không có HTML.</p>";
      previewEl.srcdoc = htmlContent;
      htmlSrcEl.value = htmlContent;
      const uploadedName = uploadedNameEl.value || "translated-document";
      const base = uploadedName.replace(/\.[^.]+$/, "");
      if (!saveNameEl.value) saveNameEl.value = `${base}.translated.html`;
      statusEl.innerHTML = `<span style="color:#16a34a;">✅ Hoàn tất. Sửa bản dịch/HTML rồi lưu PDF.</span>`;
    } else {
      statusEl.innerHTML = '<span style="color:#dc2626;">❌ Không nhận được kết quả từ server.</span>';
      updateTranslateFlowStep(flowId, 2, "error", "Không có dữ liệu trả về");
    }
  } catch (error) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(error.message)}</span>`;
    updateTranslateFlowStep(flowId, 1, "error", error.message);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = originalText;
  }
}

async function initTranslationSection() {
  if (!translateFlowsContainerEl) return;
  if (translateFlowsContainerEl.dataset.inited === "1") return;
  try {
    await loadTranslationTemplates();
    if ((translationTemplatesCache || []).length === 0) {
      console.warn("No translation templates found.");
    }
    createTranslateFlow();
    translateFlowsContainerEl.dataset.inited = "1";
  } catch (e) {
    translateFlowsContainerEl.innerHTML = `<div class="card" style="color:#dc2626;">❌ Không thể khởi tạo tab dịch: ${escapeHtml(e.message)}</div>`;
  }
}

function setActiveTab(tab) {
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  // Hide all sections first
  const allSections = [letterSection, itinerarySection, bookingSection,
    outputsSection, translateSection, classifierSection, pdfSection, editpdfSection];
  const aisplitterSection = document.getElementById("aisplitterSection");
  const precheckSection = document.getElementById("precheckSection");
  if (aisplitterSection) allSections.push(aisplitterSection);
  if (precheckSection) allSections.push(precheckSection);
  allSections.forEach((s) => { if (s) s.classList.add("hidden"); });

  if (tab === "letter") {
    letterSection.classList.remove("hidden");
  } else if (tab === "itinerary") {
    itinerarySection.classList.remove("hidden");
    loadLatestItinerary();
    loadItineraryContext();
  } else if (tab === "booking") {
    bookingSection.classList.remove("hidden");
    setBookingPart("hotel");
    loadLatestBooking();
    loadLatestTripInfo();
    loadFilteredFiles();
  } else if (tab === "outputs") {
    outputsSection.classList.remove("hidden");
    loadLatestItinerary().then(syncCombinedPreviews);
    loadLatestBooking().then(syncCombinedPreviews);
    syncCombinedPreviews();
  } else if (tab === "translate") {
    if (translateSection) translateSection.classList.remove("hidden");
    initTranslationSection();
  } else if (tab === "classifier") {
    classifierSection.classList.remove("hidden");
    loadClassifierFiles();
  } else if (tab === "pdf") {
    pdfSection.classList.remove("hidden");
    loadPdfFiles();
  } else if (tab === "aisplitter") {
    if (aisplitterSection) aisplitterSection.classList.remove("hidden");
    loadSplitterFileList();
  } else if (tab === "precheck") {
    if (precheckSection) precheckSection.classList.remove("hidden");
  } else if (tab === "editpdf") {
    if (editpdfSection) editpdfSection.classList.remove("hidden");
    initEditPdfUI();
  }
}

async function runAll() {
  for (const step of LETTER_STEP_ORDER) {
    await runStep(step, true);
  }
}

