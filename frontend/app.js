const fileListEl = document.getElementById("fileList");
const resultEl = document.getElementById("result");
const stepProgressEl = document.getElementById("stepProgress");
const summaryEl = document.getElementById("summary");
const riskPointsEl = document.getElementById("riskPoints");
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

let cachedFiles = [];

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

  if (data.risk_points) {
    riskPointsEl.textContent = data.risk_points.join("\n") || "Chưa có dữ liệu.";
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
  } else {
    itinerarySection.classList.remove("hidden");
    letterSection.classList.add("hidden");
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

refreshBtn.addEventListener("click", fetchFiles);
loadStepsBtn.addEventListener("click", loadSteps);
runItineraryBtn.addEventListener("click", runItinerary);
runAllBtn.addEventListener("click", runAll);
summaryItineraryBtn.addEventListener("click", ensureSummaryForItinerary);
stepsListEl.addEventListener("click", (event) => {
  const btn = event.target.closest(".step-btn");
  if (!btn) return;
  const step = btn.dataset.step;
  const done = btn.dataset.done === "true";
  if (step) runStep(step, done);
});

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
});

window.addEventListener("load", () => {
  fetchFiles();
  loadSteps();
  loadLatestItinerary();
});
