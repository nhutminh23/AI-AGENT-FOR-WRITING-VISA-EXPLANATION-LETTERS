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
  const mode = document.querySelector('input[name="bookingSource"]:checked')?.value || "db";
  const runBtn = document.getElementById("runItineraryBtn");
  const originalBtnText = runBtn.textContent;

  // For file upload mode: read HTML content from uploaded files
  let uploadedFlightHtml = null;
  let uploadedHotelHtmls = null;
  let pdfExtractedText = null;

  if (mode === "file") {
    // HTML file mode
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
  } else if (mode === "pdf") {
    // PDF upload mode — extract text from PDF via backend
    const pdfFiles = fullPdfInputEl?.files || [];
    if (pdfFiles.length === 0) {
      itineraryResultEl.srcdoc = "<p>Vui lòng chọn file PDF lịch trình.</p>";
      syncCombinedPreviews();
      return;
    }
    try {
      if (pdfExtractStatusEl) pdfExtractStatusEl.textContent = "⏳ Đang đọc PDF...";
      const fd = new FormData();
      fd.append("pdf_file", pdfFiles[0]);
      const extractRes = await fetch("/api/itinerary/extract-pdf", { method: "POST", body: fd });
      const extractData = await extractRes.json();
      if (!extractRes.ok) {
        if (pdfExtractStatusEl) pdfExtractStatusEl.textContent = `❌ ${extractData.error || "Lỗi đọc PDF"}`;
        itineraryResultEl.srcdoc = `<p>❌ Lỗi đọc PDF: ${extractData.error || "unknown"}</p>`;
        syncCombinedPreviews();
        return;
      }
      pdfExtractedText = extractData.text || "";
      if (pdfExtractStatusEl) pdfExtractStatusEl.textContent = `✅ Đã đọc ${extractData.pages || 0} trang (${pdfExtractedText.length} ký tự)`;
    } catch (e) {
      if (pdfExtractStatusEl) pdfExtractStatusEl.textContent = `❌ ${e.message}`;
      itineraryResultEl.srcdoc = `<p>❌ Lỗi: ${e.message}</p>`;
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
    if (mode === "db") {
      payload.from_db = true;
    } else if (mode === "pdf") {
      // Send extracted PDF text as combined booking text
      payload.pdf_extracted_text = pdfExtractedText;
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
    // Reload trip data from server, then fill passenger info
    loadLatestTripInfo().then(() => prefillSerpPassengerInfo());
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

