const fileListEl = document.getElementById("fileList");
const resultEl = document.getElementById("result");
const stepProgressEl = document.getElementById("stepProgress");
const summaryEl = document.getElementById("summary");
const summaryItineraryEl = document.getElementById("summaryItinerary");
const stepsListEl = document.getElementById("stepsList");
const inputDirEl = document.getElementById("inputDir");
const outputPathEl = document.getElementById("outputPath");
const itineraryOutputEl = document.getElementById("itineraryOutput");
const refreshBtn = document.getElementById("refreshBtn");
const loadStepsBtn = document.getElementById("loadStepsBtn");
const runAllBtn = document.getElementById("runAllBtn");
const runItineraryBtn = document.getElementById("runItineraryBtn");
const summaryItineraryBtn = document.getElementById("summaryItineraryBtn");
const flightFileEl = document.getElementById("flightFile");
const hotelFileEl = document.getElementById("hotelFile");
const itineraryResultEl = document.getElementById("itineraryResult");

const tabButtons = document.querySelectorAll(".tab-btn");
const letterSection = document.getElementById("letterSection");
const itinerarySection = document.getElementById("itinerarySection");
const bookingSection = document.getElementById("bookingSection");

// Booking elements
const guestNameEl = document.getElementById("guestName");
const startDateEl = document.getElementById("startDate");
const destinationEl = document.getElementById("destination");
const numDaysEl = document.getElementById("numDays");
const originAirportEl = document.getElementById("originAirport");
const bookingOutputEl = document.getElementById("bookingOutput");
const runBookingBtn = document.getElementById("runBookingBtn");
const hotelBookingTabsEl = document.getElementById("hotelBookingTabs");
const hotelBookingResultEl = document.getElementById("hotelBookingResult");
const flightBookingResultEl = document.getElementById("flightBookingResult");

// AI Booking elements
const extractTripBtn = document.getElementById("extractTripBtn");
const tripInfoPanelEl = document.getElementById("tripInfoPanel");
const runAIBookingBtn = document.getElementById("runAIBookingBtn");
const bookingOutputAIEl = document.getElementById("bookingOutputAI");
const aiBookingStatusEl = document.getElementById("aiBookingStatus");
const aiReasoningSectionEl = document.getElementById("aiReasoningSection");
const aiReasoningEl = document.getElementById("aiReasoning");

let cachedFiles = [];
let hotelHtmls = [];

function renderFiles(files) {
  if (!files || files.length === 0) {
    fileListEl.classList.add("empty");
    fileListEl.textContent = "Không có file nào trong thư mục input.";
    return;
  }

  fileListEl.classList.remove("empty");
  cachedFiles = files;
  const rows = files
    .map(
      (f) =>
        `<div class="file-row">
          <span class="file-name">${f.name}</span>
          <span class="file-domain">${f.domain}</span>
        </div>`
    )
    .join("");
  fileListEl.innerHTML = rows;
  renderFileOptions();
}

async function fetchFiles() {
  const inputDir = inputDirEl.value.trim() || "input";
  fileListEl.textContent = "Đang tải...";
  const res = await fetch(`/api/files?input_dir=${encodeURIComponent(inputDir)}`);
  const data = await res.json();
  renderFiles(data.files || []);
}

function formatStage(stage) {
  const labelMap = {
    ingest: "Trích xuất văn bản",
    extract: "Trích xuất 5 nhóm",
    summary: "Tổng hợp thông tin",
    risk: "Điểm cần giải trình",
    writer: "Viết thư",
  };
  return labelMap[stage] || stage;
}

function appendStepProgress(line) {
  if (stepProgressEl.textContent === "Chưa chạy.") {
    stepProgressEl.textContent = "";
  }
  stepProgressEl.textContent += `${line}\n`;
}

function renderSteps(steps) {
  const stepOrder = ["ingest", "extract", "summary", "risk", "writer"];
  const statusMap = {};
  (steps || []).forEach((s) => {
    statusMap[s.name] = s.done;
  });
  const rows = stepOrder
    .map((name) => {
      const done = Boolean(statusMap[name]);
      return `
        <div class="step-row">
          <div>
            <div class="step-name">${formatStage(name)}</div>
            <div class="step-status">${done ? "Đã hoàn thành" : "Chưa chạy"}</div>
          </div>
          <button class="step-btn" data-step="${name}" data-done="${done}">
            ${done ? "Chạy lại" : "Chạy bước"}
          </button>
        </div>
      `;
    })
    .join("");
  stepsListEl.innerHTML = rows;
}

async function loadSteps() {
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  stepsListEl.textContent = "Đang tải...";
  const res = await fetch(`/api/steps?output=${encodeURIComponent(outputPath)}`);
  const data = await res.json();
  renderSteps(data.steps || []);
  await fetchSummary();
}

async function fetchSummary() {
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  const res = await fetch(`/api/summary?output=${encodeURIComponent(outputPath)}`);
  const data = await res.json();
  summaryEl.textContent = data.summary_profile || "Chưa có dữ liệu.";
  summaryItineraryEl.textContent = data.summary_profile || "Chưa có dữ liệu.";
}

async function runIngestStream(force = false) {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  appendStepProgress("Bắt đầu: Trích xuất văn bản");

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
        appendStepProgress(data.message);
      }
      if (data.type === "done") {
        appendStepProgress("Hoàn thành: Trích xuất văn bản");
        source.close();
        resolve();
      }
    };
    source.onerror = () => {
      appendStepProgress("Lỗi khi trích xuất văn bản.");
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

  appendStepProgress(`Bắt đầu: ${formatStage(step)}`);

  const res = await fetch("/api/run_step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      input_dir: inputDir,
      output: outputPath,
      step,
      force,
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    if (data.error === "missing_prerequisite") {
      appendStepProgress(
        `Thiếu bước trước: ${formatStage(data.missing)} (hãy chạy trước)`
      );
    } else {
      appendStepProgress("Lỗi khi chạy bước.");
    }
    return;
  }

  if (data.status === "cached") {
    appendStepProgress(`Đã có cache: ${formatStage(step)}`);
  } else {
    appendStepProgress(`Hoàn thành: ${formatStage(step)}`);
  }

  if (data.letter) {
    resultEl.textContent = data.letter || "Không có kết quả.";
  }

  await fetchSummary();
  await loadSteps();
}

function renderFileOptions() {
  const makeOptions = (files) =>
    [
      '<option value="">-- Chọn file --</option>',
      ...files.map((f) => `<option value="${f.name}">${f.name}</option>`),
    ].join("");

  flightFileEl.innerHTML = makeOptions(cachedFiles);
  hotelFileEl.innerHTML = makeOptions(cachedFiles);
}

async function runItinerary() {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputPath = itineraryOutputEl.value.trim() || "output/itinerary.html";
  const flightFile = flightFileEl.value;
  const hotelFile = hotelFileEl.value;

  if (!flightFile || !hotelFile) {
    itineraryResultEl.srcdoc =
      "<p>Vui lòng chọn đủ file vé máy bay và khách sạn.</p>";
    return;
  }

  itineraryResultEl.srcdoc = "<p>Đang tạo lịch trình, vui lòng chờ...</p>";
  const res = await fetch("/api/itinerary/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      input_dir: inputDir,
      output: outputPath,
      flight_file: flightFile,
      hotel_file: hotelFile,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    if (data.error === "missing_summary") {
      itineraryResultEl.srcdoc =
        "<p>Chưa có summary 5 nhóm. Vui lòng chạy các bước hồ sơ trước.</p>";
    } else {
      itineraryResultEl.srcdoc = "<p>Lỗi khi tạo lịch trình.</p>";
    }
    return;
  }
  itineraryResultEl.srcdoc = data.itinerary || "<p>Không có kết quả.</p>";
}

async function loadLatestItinerary() {
  const outputPath = itineraryOutputEl.value.trim() || "output/itinerary.html";
  const res = await fetch(
    `/api/itinerary/latest?output=${encodeURIComponent(outputPath)}`
  );
  const data = await res.json();
  itineraryResultEl.srcdoc = data.itinerary || "<p>Chưa chạy.</p>";
}

function setActiveTab(tab) {
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  if (tab === "letter") {
    letterSection.classList.remove("hidden");
    itinerarySection.classList.add("hidden");
    bookingSection.classList.add("hidden");
  } else if (tab === "itinerary") {
    letterSection.classList.add("hidden");
    itinerarySection.classList.remove("hidden");
    bookingSection.classList.add("hidden");
  } else if (tab === "booking") {
    letterSection.classList.add("hidden");
    itinerarySection.classList.add("hidden");
    bookingSection.classList.remove("hidden");
    loadLatestBooking();
  }
}

async function runAll() {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  appendStepProgress("Bắt đầu: Chạy tất cả");

  const res = await fetch("/api/run_all", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      input_dir: inputDir,
      output: outputPath,
      force: true,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    appendStepProgress("Lỗi khi chạy tất cả.");
    return;
  }
  if (data.letter) {
    resultEl.textContent = data.letter || "Không có kết quả.";
  }
  appendStepProgress("Hoàn thành: Chạy tất cả");
  await fetchSummary();
  await loadSteps();
}

async function ensureSummaryForItinerary() {
  const outputPath = outputPathEl.value.trim() || "output/letter.txt";
  const res = await fetch(`/api/summary?output=${encodeURIComponent(outputPath)}`);
  const data = await res.json();
  if (data.summary_profile) {
    summaryItineraryEl.textContent = data.summary_profile;
    return;
  }
  await runStep("ingest", true);
  await runStep("extract", true);
  await runStep("summary", true);
}

// ==================== BOOKING FUNCTIONS ====================

function renderHotelTabs(htmls) {
  hotelHtmls = htmls;
  if (!htmls || htmls.length === 0) {
    hotelBookingTabsEl.innerHTML = "";
    hotelBookingResultEl.srcdoc = "<p>Chưa có booking.</p>";
    return;
  }

  const tabs = htmls.map((_, i) => 
    `<button class="hotel-tab-btn ${i === 0 ? 'active' : ''}" data-index="${i}">Khách sạn ${i + 1}</button>`
  ).join("");
  hotelBookingTabsEl.innerHTML = tabs;
  
  // Show first hotel
  hotelBookingResultEl.srcdoc = htmls[0];
}

function showHotelTab(index) {
  if (hotelHtmls[index]) {
    hotelBookingResultEl.srcdoc = hotelHtmls[index];
    // Update active tab
    document.querySelectorAll('.hotel-tab-btn').forEach((btn, i) => {
      btn.classList.toggle('active', i === index);
    });
  }
}

async function runBookingGeneration() {
  const guestName = guestNameEl.value.trim();
  const startDate = startDateEl.value;
  const destination = destinationEl.value;
  const numDays = parseInt(numDaysEl.value);
  const originAirport = originAirportEl.value;
  const outputDir = bookingOutputEl.value.trim() || "output";

  if (!guestName) {
    alert("Vui lòng nhập tên khách!");
    return;
  }

  hotelBookingResultEl.srcdoc = "<p>Đang tạo booking, vui lòng chờ...</p>";
  flightBookingResultEl.srcdoc = "<p>Đang tạo booking, vui lòng chờ...</p>";

  try {
    const res = await fetch("/api/booking/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        guest_name: guestName,
        start_date: startDate,
        destination,
        num_days: numDays,
        origin_airport: originAirport,
        output_dir: outputDir
      }),
    });

    const data = await res.json();
    
    if (!res.ok) {
      hotelBookingResultEl.srcdoc = `<p>Lỗi: ${data.error || "Không thể tạo booking"}</p>`;
      flightBookingResultEl.srcdoc = `<p>Lỗi: ${data.error || "Không thể tạo booking"}</p>`;
      return;
    }

    // Display hotel bookings with tabs
    renderHotelTabs(data.hotel_htmls || []);

    // Display flight booking
    flightBookingResultEl.srcdoc = data.flight_html || "<p>Không có kết quả.</p>";

  } catch (error) {
    hotelBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
    flightBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
  }
}

async function loadLatestBooking() {
  const outputDir = bookingOutputEl.value.trim() || "output";
  
  try {
    const res = await fetch(`/api/booking/latest?output_dir=${encodeURIComponent(outputDir)}`);
    const data = await res.json();
    
    renderHotelTabs(data.hotel_htmls || []);
    flightBookingResultEl.srcdoc = data.flight_html || "<p>Chưa có booking.</p>";
  } catch (error) {
    console.error("Error loading booking:", error);
  }
}

async function loadDestinations() {
  try {
    const res = await fetch("/api/booking/destinations");
    const data = await res.json();
    
    const datalistEl = document.getElementById("destinationList");
    if (data.destinations && data.destinations.length > 0 && datalistEl) {
      datalistEl.innerHTML = data.destinations
        .map(d => `<option value="${d}">`)
        .join("");
    }
  } catch (error) {
    console.error("Error loading destinations:", error);
  }
}

// ==================== AI BOOKING FUNCTIONS ====================

function formatTripInfo(info) {
  if (!info) return "Không có dữ liệu.";
  let lines = [];
  if (info.guest_names && info.guest_names.length > 0)
    lines.push(`👤 Hành khách: ${info.guest_names.join(", ")}`);
  if (info.destination_country)
    lines.push(`🌍 Điểm đến: ${info.destination_country}`);
  if (info.cities_to_visit && info.cities_to_visit.length > 0)
    lines.push(`🏙️ Thành phố: ${info.cities_to_visit.join(", ")}`);
  if (info.travel_start_date)
    lines.push(`📅 Ngày đi: ${info.travel_start_date}`);
  if (info.travel_end_date)
    lines.push(`📅 Ngày về: ${info.travel_end_date}`);
  if (info.num_nights)
    lines.push(`🌙 Số đêm: ${info.num_nights}`);
  if (info.origin_city)
    lines.push(`📍 Xuất phát: ${info.origin_city}`);
  if (info.origin_airport)
    lines.push(`✈️ Sân bay: ${info.origin_airport}`);
  if (info.travel_purpose)
    lines.push(`🎯 Mục đích: ${info.travel_purpose}`);
  if (info.traveler_profile)
    lines.push(`💼 Profile: ${info.traveler_profile}`);
  return lines.join("\n");
}

async function extractTripInfo() {
  const inputDir = inputDirEl.value.trim() || "input";
  const originalBtnText = extractTripBtn.textContent;
  extractTripBtn.textContent = "⏳ Đang trích xuất...";
  extractTripBtn.disabled = true;
  tripInfoPanelEl.innerHTML = '<div style="color:#fbbf24;">⏳ Đang đọc và phân tích tất cả file trong thư mục input...<br><small>(Quá trình này có thể mất 1-2 phút tùy số lượng file)</small></div>';

  try {
    const res = await fetch("/api/booking/extract_trip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir }),
    });

    const data = await res.json();

    if (!res.ok) {
      tripInfoPanelEl.textContent = `❌ Lỗi: ${data.error || "Không thể trích xuất"}`;
      return;
    }

    tripInfoPanelEl.textContent = formatTripInfo(data.trip_info);
  } catch (error) {
    tripInfoPanelEl.textContent = `❌ Lỗi: ${error.message}`;
  } finally {
    extractTripBtn.textContent = originalBtnText;
    extractTripBtn.disabled = false;
  }
}

async function runAIBooking() {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputDir = bookingOutputAIEl.value.trim() || "output";

  const originalBtnText = runAIBookingBtn.textContent;
  runAIBookingBtn.textContent = "⏳ AI đang xử lý...";
  runAIBookingBtn.disabled = true;
  aiBookingStatusEl.innerHTML = '<div style="color:#fbbf24;">⏳ AI đang phân tích hồ sơ và chọn khách sạn, chuyến bay...<br><small>(Quá trình này có thể mất 1-3 phút)</small></div>';
  hotelBookingResultEl.srcdoc = "<p style='color:#fbbf24;padding:20px;'>⏳ Đang tạo booking, vui lòng chờ...</p>";
  flightBookingResultEl.srcdoc = "<p style='color:#fbbf24;padding:20px;'>⏳ Đang tạo booking, vui lòng chờ...</p>";
  aiReasoningSectionEl.style.display = "none";

  try {
    const res = await fetch("/api/booking/ai_generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_dir: inputDir,
        output_dir: outputDir,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      aiBookingStatusEl.textContent = `❌ Lỗi: ${data.error || "Không thể tạo booking"}`;
      hotelBookingResultEl.srcdoc = `<p>Lỗi: ${data.error || "Không thể tạo booking"}</p>`;
      flightBookingResultEl.srcdoc = "";
      return;
    }

    // Update trip info panel if available
    if (data.trip_info) {
      tripInfoPanelEl.textContent = formatTripInfo(data.trip_info);
    }

    // Show AI reasoning
    const reasoning = data.booking_data?.reasoning;
    if (reasoning) {
      aiReasoningEl.textContent = reasoning;
      aiReasoningSectionEl.style.display = "block";
    }

    // Display hotel bookings with tabs
    renderHotelTabs(data.hotel_htmls || []);

    // Display flight booking
    flightBookingResultEl.srcdoc = data.flight_html || "<p>Không có kết quả.</p>";

    aiBookingStatusEl.textContent = data.used_cache
      ? "✅ Hoàn thành! (dùng dữ liệu đã cache - không tốn token). Bấm 'Trích xuất từ input' để tạo mới."
      : "✅ Hoàn thành! AI đã tạo booking thành công.";
  } catch (error) {
    aiBookingStatusEl.textContent = `❌ Lỗi: ${error.message}`;
    hotelBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
    flightBookingResultEl.srcdoc = "";
  } finally {
    runAIBookingBtn.textContent = originalBtnText;
    runAIBookingBtn.disabled = false;
  }
}

// ==================== EVENT LISTENERS ====================

refreshBtn.addEventListener("click", fetchFiles);
loadStepsBtn.addEventListener("click", loadSteps);
runItineraryBtn.addEventListener("click", runItinerary);
runAllBtn.addEventListener("click", runAll);
summaryItineraryBtn.addEventListener("click", ensureSummaryForItinerary);
runBookingBtn.addEventListener("click", runBookingGeneration);
extractTripBtn.addEventListener("click", extractTripInfo);
runAIBookingBtn.addEventListener("click", runAIBooking);

stepsListEl.addEventListener("click", (event) => {
  const btn = event.target.closest(".step-btn");
  if (!btn) return;
  const step = btn.dataset.step;
  const done = btn.dataset.done === "true";
  if (step) runStep(step, done);
});

hotelBookingTabsEl.addEventListener("click", (event) => {
  const btn = event.target.closest(".hotel-tab-btn");
  if (!btn) return;
  const index = parseInt(btn.dataset.index);
  showHotelTab(index);
});

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
});

window.addEventListener("load", () => {
  fetchFiles();
  loadSteps();
  loadLatestItinerary();
  loadDestinations();
});

