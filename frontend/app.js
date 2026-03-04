const fileListEl = document.getElementById("fileList");
const resultEl = document.getElementById("result");
const summaryEl = document.getElementById("summary");
const summaryItineraryEl = document.getElementById("summaryItinerary");
const stepsListEl = document.getElementById("stepsList");
const inputDirEl = document.getElementById("inputDir");
const outputPathEl = document.getElementById("outputPath");
const itineraryOutputEl = document.getElementById("itineraryOutput");
const itParticipantsEl = document.getElementById("itParticipants");
const itTravelPurposeEl = document.getElementById("itTravelPurpose");
const itTravelStartDateEl = document.getElementById("itTravelStartDate");
const itTravelEndDateEl = document.getElementById("itTravelEndDate");
const saveItineraryContextBtn = document.getElementById("saveItineraryContextBtn");
const refreshBtn = document.getElementById("refreshBtn");
const loadStepsBtn = document.getElementById("loadStepsBtn");
const runAllBtn = document.getElementById("runAllBtn");
const runItineraryBtn = document.getElementById("runItineraryBtn");
const exportItineraryPdfBtn = document.getElementById("exportItineraryPdfBtn");
const flightFileEl = document.getElementById("flightFile");
const hotelFileEl = document.getElementById("hotelFile");
const itineraryResultEl = document.getElementById("itineraryResult");

const tabButtons = document.querySelectorAll(".tab-btn");
const letterSection = document.getElementById("letterSection");
const itinerarySection = document.getElementById("itinerarySection");
const bookingSection = document.getElementById("bookingSection");
const outputsSection = document.getElementById("outputsSection");
const classifierSection = document.getElementById("classifierSection");
const pdfSection = document.getElementById("pdfSection");

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
const saveTripInfoBtn = document.getElementById("saveTripInfoBtn");
const tripInfoPanelEl = document.getElementById("tripInfoPanel");
const tripGuestNamesEl = document.getElementById("tripGuestNames");
const tripDestinationCountryEl = document.getElementById("tripDestinationCountry");
const tripCitiesPlanEl = document.getElementById("tripCitiesPlan");
const tripTravelStartDateEl = document.getElementById("tripTravelStartDate");
const tripTravelEndDateEl = document.getElementById("tripTravelEndDate");
const tripNumNightsEl = document.getElementById("tripNumNights");
const tripOriginCityEl = document.getElementById("tripOriginCity");
const tripOriginAirportEl = document.getElementById("tripOriginAirport");
const tripReturnPointEl = document.getElementById("tripReturnPoint");
const tripDestinationAirportHintEl = document.getElementById("tripDestinationAirportHint");
const tripReturnAirportHintEl = document.getElementById("tripReturnAirportHint");
const tripTravelPurposeEl = document.getElementById("tripTravelPurpose");
const tripTravelerProfileEl = document.getElementById("tripTravelerProfile");
const runAIBookingBtn = document.getElementById("runAIBookingBtn");
const bookingOutputAIEl = document.getElementById("bookingOutputAI");
const aiBookingStatusEl = document.getElementById("aiBookingStatus");
const aiReasoningSectionEl = document.getElementById("aiReasoningSection");
const aiReasoningEl = document.getElementById("aiReasoning");

// PDF Export buttons
const exportHotelPdfBtn = document.getElementById("exportHotelPdfBtn");
const exportFlightPdfBtn = document.getElementById("exportFlightPdfBtn");
const exportAllHotelPdfBtn = document.getElementById("exportAllHotelPdfBtn");
const exportCombinedItineraryPdfBtn = document.getElementById("exportCombinedItineraryPdfBtn");
const exportCombinedFlightPdfBtn = document.getElementById("exportCombinedFlightPdfBtn");
const exportCombinedHotelPdfBtn = document.getElementById("exportCombinedHotelPdfBtn");
const exportCombinedAllPdfBtn = document.getElementById("exportCombinedAllPdfBtn");
const combinedItineraryResultEl = document.getElementById("combinedItineraryResult");
const combinedFlightBookingResultEl = document.getElementById("combinedFlightBookingResult");
const combinedHotelBookingResultEl = document.getElementById("combinedHotelBookingResult");
const classifierInputDirEl = document.getElementById("classifierInputDir");
const classifierOutputDirEl = document.getElementById("classifierOutputDir");
const loadClassifierFilesBtn = document.getElementById("loadClassifierFilesBtn");
const runClassifierBtn = document.getElementById("runClassifierBtn");
const classifierFileListEl = document.getElementById("classifierFileList");
const classifierResultEl = document.getElementById("classifierResult");
const manualSplitSourceFileEl = document.getElementById("manualSplitSourceFile");
const manualSplitCountEl = document.getElementById("manualSplitCount");
const buildManualSegmentsBtn = document.getElementById("buildManualSegmentsBtn");
const manualSplitSegmentsContainerEl = document.getElementById("manualSplitSegmentsContainer");
const runManualSplitBtn = document.getElementById("runManualSplitBtn");

// PDF tools tab elements
const pdfManualSourceFileEl = document.getElementById("pdfManualSourceFile");
const pdfManualCountEl = document.getElementById("pdfManualCount");
const pdfBuildSplitFormBtn = document.getElementById("pdfBuildSplitFormBtn");
const pdfManualSegmentsEl = document.getElementById("pdfManualSegments");
const pdfRunSplitBtn = document.getElementById("pdfRunSplitBtn");
const pdfMergeFilesEl = document.getElementById("pdfMergeFiles");
const pdfMergePrefixEl = document.getElementById("pdfMergePrefix");
const pdfMergeDocTypeEl = document.getElementById("pdfMergeDocType");
const pdfMergeDocTypeCustomEl = document.getElementById("pdfMergeDocTypeCustom");
const pdfMergeGenBtn = document.getElementById("pdfMergeGenBtn");
const pdfMergePreviewEl = document.getElementById("pdfMergePreview");
const pdfRunMergeBtn = document.getElementById("pdfRunMergeBtn");
const pdfToolsResultEl = document.getElementById("pdfToolsResult");
const pdfRenameSourceFileEl = document.getElementById("pdfRenameSourceFile");
const pdfRenamePrefixEl = document.getElementById("pdfRenamePrefix");
const pdfRenameDocTypeEl = document.getElementById("pdfRenameDocType");
const pdfRenameDocTypeCustomEl = document.getElementById("pdfRenameDocTypeCustom");
const pdfRenameGenBtn = document.getElementById("pdfRenameGenBtn");
const pdfRunRenameBtn = document.getElementById("pdfRunRenameBtn");
const pdfRenamePreviewEl = document.getElementById("pdfRenamePreview");

let cachedFiles = [];
let hotelHtmls = [];
let writerContextCache = "";
let activeStepLog = null;
let classifierFilesCache = [];
let pdfFilesCache = [];
let currentProjectId = null;

// ==================== PROJECT MANAGEMENT ====================

const projectSelectEl = document.getElementById("projectSelect");
const btnNewProject = document.getElementById("btnNewProject");
const btnRenameProject = document.getElementById("btnRenameProject");
const btnDeleteProject = document.getElementById("btnDeleteProject");

function getProjectId() {
  return currentProjectId;
}

async function loadProjects() {
  try {
    const res = await fetch("/api/projects");
    const data = await res.json();
    projectSelectEl.innerHTML = '<option value="">-- Chọn hồ sơ --</option>';
    (data.projects || []).forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      projectSelectEl.appendChild(opt);
    });
    if (currentProjectId) {
      projectSelectEl.value = currentProjectId;
    }
  } catch (e) {
    console.error("Failed to load projects:", e);
  }
}

projectSelectEl.addEventListener("change", () => {
  const val = projectSelectEl.value;
  currentProjectId = val ? parseInt(val) : null;
  btnRenameProject.style.display = currentProjectId ? "" : "none";
  btnDeleteProject.style.display = currentProjectId ? "" : "none";
  localStorage.setItem("currentProjectId", currentProjectId || "");
});

btnNewProject.addEventListener("click", async () => {
  const name = prompt("Tên hồ sơ mới (VD: Hồ sơ Nguyễn Văn A - Úc):");
  if (!name || !name.trim()) return;
  try {
    const res = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    });
    const project = await res.json();
    currentProjectId = project.id;
    localStorage.setItem("currentProjectId", currentProjectId);
    await loadProjects();
    projectSelectEl.value = currentProjectId;
    btnRenameProject.style.display = "";
    btnDeleteProject.style.display = "";
  } catch (e) {
    alert("Lỗi: " + e.message);
  }
});

btnRenameProject.addEventListener("click", async () => {
  if (!currentProjectId) return;
  const name = prompt("Tên mới:");
  if (!name || !name.trim()) return;
  try {
    await fetch(`/api/projects/${currentProjectId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    });
    await loadProjects();
  } catch (e) {
    alert("Lỗi: " + e.message);
  }
});

btnDeleteProject.addEventListener("click", async () => {
  if (!currentProjectId) return;
  if (!confirm("Xóa hồ sơ này? Dữ liệu sẽ mất!")) return;
  try {
    await fetch(`/api/projects/${currentProjectId}`, { method: "DELETE" });
    currentProjectId = null;
    localStorage.removeItem("currentProjectId");
    btnRenameProject.style.display = "none";
    btnDeleteProject.style.display = "none";
    await loadProjects();
  } catch (e) {
    alert("Lỗi: " + e.message);
  }
});

// Restore project from localStorage
(async () => {
  const saved = localStorage.getItem("currentProjectId");
  if (saved) {
    currentProjectId = parseInt(saved);
  }
  await loadProjects();
  if (currentProjectId) {
    projectSelectEl.value = currentProjectId;
    btnRenameProject.style.display = "";
    btnDeleteProject.style.display = "";
  }
})();

const PDF_RENAME_PREFIX_OPTIONS = [
  { value: "PERSONAL", label: "HO SO CA NHAN / PERSONAL" },
  { value: "TRAVEL HISTORY", label: "LICH SU DU LICH / TRAVEL HISTORY" },
  { value: "EMPLOYMENT", label: "CONG VIEC / EMPLOYMENT" },
  { value: "FINANCES", label: "TAI CHINH / FINANCES" },
  { value: "PURPOSE", label: "MUC DICH CHUYEN DI / PURPOSE" },
];

const PDF_RENAME_DOC_TYPE_SUGGESTIONS = [
  { value: "BIRTH CERT", label: "GIAY KHAI SINH / BIRTH CERT" },
  { value: "MARRIAGE CERT", label: "GIAY KET HON / MARRIAGE CERT" },
  { value: "DIVORCE CERT", label: "GIAY LY HON / DIVORCE CERT" },
  { value: "LEAVE LETTER", label: "DON XIN NGHI PHEP / LEAVE LETTER" },
  { value: "LABOR CONTRACT", label: "HOP DONG LAO DONG / LABOR CONTRACT" },
  { value: "LEASE AGREEMENT", label: "HOP DONG THUE NHA / LEASE AGREEMENT" },
  { value: "SOCIAL INSURANCE", label: "BAO HIEM XA HOI / SOCIAL INSURANCE" },
  { value: "LAND CERT", label: "GIAY TO DAT / LAND CERT" },
  { value: "BUSINESS LICENSE", label: "GIAY PHEP KINH DOANH / BUSINESS LICENSE" },
  { value: "TAX", label: "THUE / TAX" },
  { value: "BANK STATEMENT", label: "SAO KE / BANK STATEMENT" },
  { value: "PASSPORT", label: "HO CHIEU / PASSPORT" },
  { value: "NATIONAL ID", label: "CAN CUOC CONG DAN / NATIONAL ID" },
  { value: "BALANCE CERT", label: "XAC NHAN SO DU / BALANCE CERT" },
];
const LETTER_STEP_ORDER = ["ingest", "summary", "writer"];
const stepLogs = {
  ingest: "Chưa chạy.",
  summary: "Chưa chạy.",
  writer: "Chưa chạy.",
};
const DEFAULT_TRIP_INFO = {
  guest_names: [],
  destination_country: "",
  cities_to_visit: [],
  city_stays: [],
  travel_start_date: "",
  travel_end_date: "",
  num_nights: 0,
  origin_city: "",
  origin_airport: "",
  return_point: "",
  destination_airport_hint: "",
  return_airport_hint: "",
  travel_purpose: "",
  traveler_profile: "",
};

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

function renderClassifierFiles(files) {
  const deleteAllBtn = document.getElementById("deleteAllClassifierBtn");
  if (!files || files.length === 0) {
    classifierFileListEl.classList.add("empty");
    classifierFileListEl.textContent = "Không có file nào trong thư mục input phân loại.";
    if (deleteAllBtn) deleteAllBtn.style.display = "none";
    return;
  }
  if (deleteAllBtn) deleteAllBtn.style.display = "inline-block";
  classifierFileListEl.classList.remove("empty");
  classifierFileListEl.innerHTML = files
    .map(
      (f) => `<div class="file-row" style="align-items:center;">
        <div style="flex:1;">
          <span class="file-name">${f.rel_path || f.name}</span>
          <span class="file-domain">${f.domain}</span>
        </div>
        <button class="classifier-delete-btn" data-filename="${f.rel_path || f.name}" 
                style="padding:5px 12px; background:#dc2626; color:#fff; border:none; border-radius:5px; cursor:pointer; font-size:12px;">
          🗑️
        </button>
      </div>`
    )
    .join("");
}

async function loadClassifierFiles() {
  const inputDir = classifierInputDirEl.value.trim() || "phanloai/input";
  classifierFileListEl.textContent = "Đang tải...";
  const res = await fetch(`/api/classifier/files?input_dir=${encodeURIComponent(inputDir)}`);
  const data = await res.json();
  if (!data.exists) {
    classifierFileListEl.classList.add("empty");
    classifierFileListEl.textContent = `Không tìm thấy thư mục: ${inputDir}`;
    return;
  }
  classifierFilesCache = data.files || [];
  renderClassifierFiles(classifierFilesCache);
}

async function deleteClassifierFile(filename) {
  if (!confirm(`Xóa file "${filename}"?`)) return;
  const inputDir = classifierInputDirEl.value.trim() || "phanloai/input";
  try {
    await fetch("/api/classifier/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir, filename }),
    });
    await loadClassifierFiles();
  } catch (e) { alert(`Lỗi: ${e.message}`); }
}

async function deleteAllClassifierFiles() {
  if (!confirm("Xóa TẤT CẢ file trong thư mục phân loại?")) return;
  const inputDir = classifierInputDirEl.value.trim() || "phanloai/input";
  try {
    const res = await fetch("/api/classifier/delete-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir }),
    });
    const data = await res.json();
    alert(`✅ Đã xóa ${data.deleted_count} file.`);
    await loadClassifierFiles();
  } catch (e) { alert(`Lỗi: ${e.message}`); }
}

// Classifier delete-all button
const deleteAllClassifierBtn = document.getElementById("deleteAllClassifierBtn");
if (deleteAllClassifierBtn) {
  deleteAllClassifierBtn.addEventListener("click", deleteAllClassifierFiles);
}

// Classifier per-file delete delegation
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".classifier-delete-btn");
  if (!btn) return;
  const filename = btn.dataset.filename;
  if (filename) deleteClassifierFile(filename);
});

// === PDF tools helpers ===

async function loadPdfFiles() {
  const inputDir = "pdf/input";
  try {
    const res = await fetch(`/api/classifier/files?input_dir=${encodeURIComponent(inputDir)}`);
    const data = await res.json();
    if (!data.exists) {
      pdfFilesCache = [];
      if (pdfManualSourceFileEl) {
        pdfManualSourceFileEl.innerHTML =
          '<option value="">-- Không tìm thấy thư mục pdf/input --</option>';
      }
      if (pdfMergeFilesEl) {
        pdfMergeFilesEl.innerHTML = "";
      }
      return;
    }
    pdfFilesCache = data.files || [];
    renderPdfSourceOptions();
  } catch (err) {
    console.error("loadPdfFiles error", err);
  }
}

function renderPdfSourceOptions() {
  const pdfs = (pdfFilesCache || []).filter((f) =>
    (f.name || "").toLowerCase().endsWith(".pdf")
  );

  if (pdfManualSourceFileEl) {
    if (!pdfs.length) {
      pdfManualSourceFileEl.innerHTML =
        '<option value="">-- Không có file PDF nào trong pdf/input --</option>';
    } else {
      pdfManualSourceFileEl.innerHTML = pdfs
        .map((f) => {
          const value = f.rel_path || f.name;
          const label = f.rel_path || f.name;
          return `<option value="${value}">${label}</option>`;
        })
        .join("");
    }
  }

  if (pdfMergeFilesEl) {
    if (!pdfs.length) {
      pdfMergeFilesEl.innerHTML = "";
    } else {
      pdfMergeFilesEl.innerHTML = pdfs
        .map((f) => {
          const value = f.rel_path || f.name;
          const label = f.rel_path || f.name;
          return `<option value="${value}">${label}</option>`;
        })
        .join("");
    }
  }

  if (pdfRenameSourceFileEl) {
    if (!pdfs.length) {
      pdfRenameSourceFileEl.innerHTML =
        '<option value="">-- Không có file PDF nào trong pdf/input --</option>';
    } else {
      pdfRenameSourceFileEl.innerHTML = pdfs
        .map((f) => {
          const value = f.rel_path || f.name;
          const label = f.rel_path || f.name;
          return `<option value="${value}">${label}</option>`;
        })
        .join("");
    }
  }

  if (pdfRenamePrefixEl) {
    pdfRenamePrefixEl.innerHTML = PDF_RENAME_PREFIX_OPTIONS.map(
      (opt) => `<option value="${opt.value}">${opt.label}</option>`
    ).join("");
  }

  if (pdfRenameDocTypeEl) {
    const options = PDF_RENAME_DOC_TYPE_SUGGESTIONS.map(
      (opt) => `<option value="${opt.value}">${opt.label}</option>`
    );
    options.push('<option value="__CUSTOM__">Khác (tự nhập / dùng AI)</option>');
    pdfRenameDocTypeEl.innerHTML = options.join("");
  }

  if (pdfMergePrefixEl) {
    pdfMergePrefixEl.innerHTML = PDF_RENAME_PREFIX_OPTIONS.map(
      (opt) => `<option value="${opt.value}">${opt.label}</option>`
    ).join("");
  }

  if (pdfMergeDocTypeEl) {
    const options = PDF_RENAME_DOC_TYPE_SUGGESTIONS.map(
      (opt) => `<option value="${opt.value}">${opt.label}</option>`
    );
    options.push('<option value="__CUSTOM__">Khác (tự nhập / dùng AI)</option>');
    pdfMergeDocTypeEl.innerHTML = options.join("");
  }

  updatePdfRenamePreview();
  updatePdfMergePreview();
}

function updatePdfRenamePreview() {
  if (!pdfRenamePreviewEl) return;
  const prefix = (pdfRenamePrefixEl?.value || "").trim() || "[PREFIX]";
  let docType = "[DOC_TYPE]";
  if (pdfRenameDocTypeEl) {
    const selected = (pdfRenameDocTypeEl.value || "").trim();
    if (selected === "__CUSTOM__") {
      if (pdfRenameDocTypeCustomEl) {
        const custom = (pdfRenameDocTypeCustomEl.value || "").trim();
        if (custom) {
          docType = custom;
        }
        pdfRenameDocTypeCustomEl.style.display = "block";
      }
    } else {
      docType = selected || "[DOC_TYPE]";
      if (pdfRenameDocTypeCustomEl) {
        pdfRenameDocTypeCustomEl.style.display = "none";
      }
    }
  }
  pdfRenamePreviewEl.textContent = `Tên mới sẽ có dạng: ${prefix} - ${docType}.pdf`;
}

function updatePdfMergePreview() {
  if (!pdfMergePreviewEl) return;
  const prefix = (pdfMergePrefixEl?.value || "").trim() || "[PREFIX]";
  let docType = "[DOC_TYPE]";
  if (pdfMergeDocTypeEl) {
    const selected = (pdfMergeDocTypeEl.value || "").trim();
    if (selected === "__CUSTOM__") {
      if (pdfMergeDocTypeCustomEl) {
        const custom = (pdfMergeDocTypeCustomEl.value || "").trim();
        if (custom) {
          docType = custom;
        }
        pdfMergeDocTypeCustomEl.style.display = "block";
      }
    } else {
      docType = selected || "[DOC_TYPE]";
      if (pdfMergeDocTypeCustomEl) {
        pdfMergeDocTypeCustomEl.style.display = "none";
      }
    }
  }
  pdfMergePreviewEl.textContent = `Tên file output sẽ có dạng: ${prefix} - ${docType}.pdf`;
}

function getPdfMergeOutputName() {
  const prefix = (pdfMergePrefixEl?.value || "").trim();
  if (!prefix) return "";
  let docType = "";
  if (pdfMergeDocTypeEl) {
    const selected = (pdfMergeDocTypeEl.value || "").trim();
    if (selected === "__CUSTOM__") {
      docType = (pdfMergeDocTypeCustomEl?.value || "").trim();
    } else {
      docType = selected;
    }
  }
  if (!docType) return "";
  return `${prefix} - ${docType}`;
}

function buildManualSegments() {
  const count = parseInt(manualSplitCountEl.value || "0", 10) || 0;
  const safeCount = Math.max(1, Math.min(count, 10));
  manualSplitCountEl.value = safeCount;
  const parts = [];
  for (let i = 1; i <= safeCount; i++) {
    parts.push(`
      <div class="manual-segment" data-index="${i}" style="margin-top:8px; padding:8px; border:1px dashed #e5e7eb; border-radius:6px;">
        <div class="row">
          <div>
            <label for="segmentName-${i}">File ${i} - Tên file output (không cần .pdf)</label>
            <input id="segmentName-${i}" type="text" />
          </div>
          <div>
            <label for="segmentStart-${i}">Từ trang</label>
            <input id="segmentStart-${i}" type="number" min="1" />
          </div>
          <div>
            <label for="segmentEnd-${i}">Đến trang</label>
            <input id="segmentEnd-${i}" type="number" min="1" />
          </div>
        </div>
      </div>
    `);
  }
  manualSplitSegmentsContainerEl.innerHTML = parts.join("");
}

function buildPdfManualSegments() {
  if (!pdfManualCountEl || !pdfManualSegmentsEl) return;
  const count = parseInt(pdfManualCountEl.value || "0", 10) || 0;
  const safeCount = Math.max(1, Math.min(count, 10));
  pdfManualCountEl.value = safeCount;
  const parts = [];
  for (let i = 1; i <= safeCount; i++) {
    parts.push(`
      <div class="manual-segment" data-index="${i}" style="margin-top:8px; padding:8px; border:1px dashed #e5e7eb; border-radius:6px;">
        <div class="row">
          <div>
            <label for="pdf-segmentName-${i}">File ${i} - Tên file output (không cần .pdf)</label>
            <input id="pdf-segmentName-${i}" type="text" />
          </div>
          <div>
            <label for="pdf-segmentStart-${i}">Từ trang</label>
            <input id="pdf-segmentStart-${i}" type="number" min="1" />
          </div>
          <div>
            <label for="pdf-segmentEnd-${i}">Đến trang</label>
            <input id="pdf-segmentEnd-${i}" type="number" min="1" />
          </div>
        </div>
      </div>
    `);
  }
  pdfManualSegmentsEl.innerHTML = parts.join("");
}

async function runPdfManualSplit() {
  const inputDir = "pdf/input";
  const outputDir = "pdf/output";
  if (!pdfManualSourceFileEl) {
    alert("Không tìm thấy danh sách file nguồn.");
    return;
  }
  const source = pdfManualSourceFileEl.value;
  if (!source) {
    alert("Vui lòng chọn file nguồn (PDF).");
    return;
  }
  const count = parseInt(pdfManualCountEl.value || "0", 10) || 0;
  const segments = [];
  for (let i = 1; i <= count; i++) {
    const nameEl = document.getElementById(`pdf-segmentName-${i}`);
    const startEl = document.getElementById(`pdf-segmentStart-${i}`);
    const endEl = document.getElementById(`pdf-segmentEnd-${i}`);
    if (!nameEl || !startEl || !endEl) continue;
    const output_name = nameEl.value.trim();
    const start_page = parseInt(startEl.value || "0", 10);
    const end_page = parseInt(endEl.value || "0", 10);
    if (!output_name || !start_page || !end_page) continue;
    segments.push({ output_name, start_page, end_page });
  }
  if (!segments.length) {
    alert("Vui lòng nhập đầy đủ tên file và khoảng trang cho ít nhất 1 file con.");
    return;
  }
  const originalText = pdfRunSplitBtn.textContent;
  pdfRunSplitBtn.disabled = true;
  pdfRunSplitBtn.textContent = "Đang tách...";
  if (pdfToolsResultEl) {
    pdfToolsResultEl.textContent = "Đang tách file PDF theo cấu hình bạn nhập...";
  }
  try {
    const res = await fetch("/api/classifier/split_manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir, output_dir: outputDir, source, segments }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (pdfToolsResultEl) {
        pdfToolsResultEl.textContent = `Lỗi tách file: ${data.error || "không xác định"}`;
      }
      return;
    }
    const lines = [];
    lines.push("Tách file thủ công hoàn thành.");
    lines.push(`- File nguồn: ${data.source}`);
    lines.push(`- Tổng số trang file nguồn: ${data.total_pages}`);
    lines.push(`- Số file con tạo ra: ${data.segments?.length || 0}`);
    lines.push("");
    lines.push("Chi tiết:");
    (data.segments || []).forEach((seg) => {
      lines.push(
        `- ${seg.output_name}.pdf (trang ${seg.start_page}-${seg.end_page}) -> ${seg.to}`
      );
    });
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = lines.join("\n");
    }

    // Đóng/clear form tách sau khi thực hiện xong
    if (pdfManualSegmentsEl) pdfManualSegmentsEl.innerHTML = "";
    if (pdfManualCountEl) pdfManualCountEl.value = "1";
    await loadPdfFiles();
  } catch (error) {
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Lỗi tách file: ${error.message}`;
    }
  } finally {
    pdfRunSplitBtn.disabled = false;
    pdfRunSplitBtn.textContent = originalText;
  }
}

async function runPdfMerge() {
  const inputDir = "pdf/input";
  const outputDir = "pdf/output";
  if (!pdfMergeFilesEl) {
    alert("Không tìm thấy danh sách file để nối.");
    return;
  }
  const selected = Array.from(pdfMergeFilesEl.options)
    .filter((opt) => opt.selected)
    .map((opt) => opt.value);
  if (!selected.length) {
    alert("Vui lòng chọn ít nhất 2 file PDF để nối.");
    return;
  }
  const output_name = getPdfMergeOutputName();
  if (!output_name) {
    alert("Vui lòng chọn tiền tố loại hồ sơ và tên giấy tờ.");
    return;
  }
  const originalText = pdfRunMergeBtn.textContent;
  pdfRunMergeBtn.disabled = true;
  pdfRunMergeBtn.textContent = "Đang nối...";
  if (pdfToolsResultEl) {
    pdfToolsResultEl.textContent = "Đang nối các file PDF...";
  }
  try {
    const res = await fetch("/api/pdf/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_dir: inputDir,
        output_dir: outputDir,
        files: selected,
        output_name,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (pdfToolsResultEl) {
        pdfToolsResultEl.textContent = `Lỗi nối PDF: ${data.error || "không xác định"}`;
      }
      return;
    }
    const lines = [];
    lines.push("Nối PDF hoàn thành.");
    lines.push(`- Số file nguồn: ${data.file_count}`);
    lines.push(`- Tổng số trang: ${data.total_pages}`);
    lines.push(`- File kết quả: ${data.output_file}`);
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = lines.join("\n");
    }
    await loadPdfFiles();
  } catch (error) {
    if (pdfToolsResultEl) {
      pdfToolsResultEl.textContent = `Lỗi nối PDF: ${error.message}`;
    }
  } finally {
    pdfRunMergeBtn.disabled = false;
    pdfRunMergeBtn.textContent = originalText;
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
  const countLines = Object.keys(counts).map((k) => `- ${k}: ${counts[k]} file`);
  const splitLogs = data.split_logs || [];
  const splitLines = splitLogs.flatMap((x) => {
    const outputs = (x.outputs || []).map(
      (o) => `  - ${o.doc_type_en}.pdf (${o.person_name}, trang ${o.pages})`
    );
    return [`- ${x.source_file}: tách ${x.detected_documents} tài liệu`, ...outputs];
  });
  const copiedLines = (data.copied || []).map(
    (m) => `- ${m.source} -> ${m.person_name}/${m.doc_type_en} (${m.to})`
  );
  return [
    "Phân loại hoàn thành.",
    `- Input: ${data.input_dir || ""}`,
    `- Output: ${data.output_dir || ""}`,
    `- Tổng file đã xử lý: ${data.copied_count || 0}`,
    `- File bỏ qua/lỗi: ${data.skipped_count || 0}`,
    "",
    "Thống kê theo từng người:",
    ...countLines,
    "",
    ...(splitLines.length > 0
      ? ["PDF nhiều giấy tờ đã tách:", ...splitLines, ""]
      : []),
    "",
    "Chi tiết:",
    ...(copiedLines.length > 0 ? copiedLines : ["- Không có file nào được ghi ra output."]),
  ].join("\n");
}

async function runClassifier() {
  const inputDir = classifierInputDirEl.value.trim() || "phanloai/input";
  const outputDir = classifierOutputDirEl.value.trim() || "phanloai/output";
  const originalText = runClassifierBtn.textContent;
  runClassifierBtn.disabled = true;
  runClassifierBtn.textContent = "Đang phân loại...";
  classifierResultEl.textContent = "AI đang phân tích và phân loại file...";
  try {
    const res = await fetch("/api/classifier/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir, output_dir: outputDir }),
    });
    const data = await res.json();
    if (!res.ok) {
      classifierResultEl.textContent = `Lỗi: ${data.error || "Không thể phân loại file."}`;
      return;
    }
    classifierResultEl.textContent = formatClassifierResult(data);
    await loadClassifierFiles();
    // Store output paths for save button
    window._classifierTempOutput = data._temp_output;
    window._classifierFinalOutput = data._final_output;
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
          saveBtn.disabled = true;
          saveBtn.textContent = "⏳ Đang lưu...";
          try {
            const res = await fetch("/api/classifier/save-output", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                temp_output: window._classifierTempOutput,
                output_dir: window._classifierFinalOutput,
              }),
            });
            const result = await res.json();
            if (res.ok) {
              alert(`✅ Đã lưu ${result.file_count} file vào: ${result.output_dir}`);
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

// ==================== PIPELINE CONNECTION FUNCTIONS ====================

async function sendToClassifier() {
  const btn = document.getElementById("sendToClassifierBtn");
  if (!btn) return;
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Đang chuyển file...";
  try {
    const res = await fetch("/api/pipeline/send-to-classifier", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Lỗi: ${data.error}`);
      return;
    }
    alert(`✅ Đã chuyển ${data.count} file sang ${data.target_dir}`);
    setActiveTab("classifier");
    loadClassifierFiles();
  } catch (e) {
    alert(`Lỗi: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
  }
}

async function sendToInput() {
  const btn = document.getElementById("sendToInputBtn");
  if (!btn) return;
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Đang chuyển file...";
  try {
    const res = await fetch("/api/pipeline/send-to-input", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
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
  const fileValue = (f) => f.rel_path || f.name;
  const fileLabel = (f) => f.rel_path || f.name;
  const makeOptions = (files) =>
    [
      '<option value="">-- Chọn file --</option>',
      ...files.map((f) => `<option value="${fileValue(f)}">${fileLabel(f)}</option>`),
    ].join("");

  flightFileEl.innerHTML = makeOptions(cachedFiles);
  hotelFileEl.innerHTML = makeOptions(cachedFiles);
}

function collectItineraryFormData() {
  return {
    participants: itParticipantsEl.value.trim(),
    travel_purpose: itTravelPurposeEl.value.trim(),
    travel_start_date: itTravelStartDateEl.value.trim(),
    travel_end_date: itTravelEndDateEl.value.trim(),
  };
}

function applyItineraryFormData(formData = {}) {
  itParticipantsEl.value = formData.participants || "";
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
  const flightFile = flightFileEl.value;
  const hotelFile = hotelFileEl.value;
  const formData = collectItineraryFormData();
  const summaryProfile = buildItinerarySummaryFromForm(formData);

  if (!flightFile || !hotelFile) {
    itineraryResultEl.srcdoc =
      "<p>Vui lòng chọn đủ file vé máy bay và khách sạn.</p>";
    syncCombinedPreviews();
    return;
  }
  if (!summaryProfile) {
    itineraryResultEl.srcdoc =
      "<p>Vui lòng nhập thông tin đầu vào lịch trình trước khi tạo.</p>";
    syncCombinedPreviews();
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
      summary_profile: summaryProfile,
      project_id: getProjectId(),
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    if (data.error === "missing_itinerary_summary") {
      itineraryResultEl.srcdoc =
        "<p>Chưa có dữ liệu lịch trình. Vui lòng nhập form và bấm lưu trước.</p>";
    } else if (data.error === "missing_files") {
      itineraryResultEl.srcdoc = "<p>Không tìm thấy file vé máy bay hoặc khách sạn đã chọn.</p>";
    } else {
      itineraryResultEl.srcdoc = "<p>Lỗi khi tạo lịch trình.</p>";
    }
    syncCombinedPreviews();
    return;
  }
  itineraryResultEl.srcdoc = data.itinerary || "<p>Không có kết quả.</p>";
  syncCombinedPreviews();
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

function setActiveTab(tab) {
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  // Hide all sections first
  const allSections = [letterSection, itinerarySection, bookingSection,
    outputsSection, classifierSection, pdfSection];
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
    loadLatestBooking();
    loadLatestTripInfo();
  } else if (tab === "outputs") {
    outputsSection.classList.remove("hidden");
    loadLatestItinerary().then(syncCombinedPreviews);
    loadLatestBooking().then(syncCombinedPreviews);
    syncCombinedPreviews();
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
  }
}

async function runAll() {
  for (const step of LETTER_STEP_ORDER) {
    await runStep(step, true);
  }
}

// ==================== BOOKING FUNCTIONS ====================

function renderHotelTabs(htmls) {
  hotelHtmls = htmls;
  if (!htmls || htmls.length === 0) {
    hotelBookingTabsEl.innerHTML = "";
    hotelBookingResultEl.srcdoc = "<p>Chưa có booking.</p>";
    syncCombinedPreviews();
    return;
  }

  const tabs = htmls.map((_, i) => 
    `<button class="hotel-tab-btn ${i === 0 ? 'active' : ''}" data-index="${i}">Khách sạn ${i + 1}</button>`
  ).join("");
  hotelBookingTabsEl.innerHTML = tabs;
  
  // Show first hotel
  hotelBookingResultEl.srcdoc = htmls[0];
  syncCombinedPreviews();

  // Show export button
  exportHotelPdfBtn.style.display = "inline-block";
  // Show "export all" only when there are 2+ hotels
  if (htmls.length >= 2) {
    exportAllHotelPdfBtn.style.display = "inline-block";
  } else {
    exportAllHotelPdfBtn.style.display = "none";
  }
}

function showHotelTab(index) {
  if (hotelHtmls[index]) {
    hotelBookingResultEl.srcdoc = hotelHtmls[index];
    syncCombinedPreviews();
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

    let data;
    try {
      const responseText = await res.text();
      data = JSON.parse(responseText);
    } catch (e) {
      throw new Error("❌ Có lỗi Server Nội bộ. Vui lòng mở bảng Terminal đen lên xem nó báo lỗi gì nhé!");
    }
    
    if (!res.ok) {
      hotelBookingResultEl.srcdoc = `<p>Lỗi: ${data.error || "Không thể tạo booking"}</p>`;
      flightBookingResultEl.srcdoc = `<p>Lỗi: ${data.error || "Không thể tạo booking"}</p>`;
      syncCombinedPreviews();
      return;
    }

    // Display hotel bookings with tabs
    renderHotelTabs(data.hotel_htmls || []);

    // Display flight booking
    flightBookingResultEl.srcdoc = data.flight_html || "<p>Không có kết quả.</p>";
    if (data.flight_html) {
      exportFlightPdfBtn.style.display = "inline-block";
    }
    syncCombinedPreviews();

  } catch (error) {
    hotelBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
    flightBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
    syncCombinedPreviews();
  }
}

async function loadLatestBooking() {
  const outputDir = bookingOutputEl.value.trim() || "output";
  
  try {
    const res = await fetch(`/api/booking/latest?output_dir=${encodeURIComponent(outputDir)}`);
    const data = await res.json();
    
    renderHotelTabs(data.hotel_htmls || []);
    flightBookingResultEl.srcdoc = data.flight_html || "<p>Chưa có booking.</p>";
    if (data.flight_html) {
      exportFlightPdfBtn.style.display = "inline-block";
    }
    syncCombinedPreviews();
  } catch (error) {
    console.error("Error loading booking:", error);
    syncCombinedPreviews();
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
  if (info.return_point)
    lines.push(`↩️ Điểm về: ${info.return_point}`);
  if (info.destination_airport_hint)
    lines.push(`🛬 Sân bay gợi ý điểm đến: ${info.destination_airport_hint}`);
  if (info.return_airport_hint)
    lines.push(`🛫 Sân bay gợi ý điểm về: ${info.return_airport_hint}`);
  if (info.travel_purpose)
    lines.push(`🎯 Mục đích: ${info.travel_purpose}`);
  if (info.traveler_profile)
    lines.push(`💼 Profile: ${info.traveler_profile}`);
  if (info.city_stays && info.city_stays.length > 0)
    lines.push(
      `🏨 Phân bổ đêm: ${info.city_stays
        .map((c) => `${c.city} (${c.nights})`)
        .join(", ")}`
    );
  return lines.join("\n");
}

function normalizeTripInfo(info) {
  return { ...DEFAULT_TRIP_INFO, ...(info || {}) };
}

function setTripInfoForm(info) {
  const merged = normalizeTripInfo(info);
  tripGuestNamesEl.value = (merged.guest_names || []).join("\n");
  tripDestinationCountryEl.value = merged.destination_country || "";
  const cityStays = Array.isArray(merged.city_stays) ? merged.city_stays : [];
  if (cityStays.length > 0) {
    tripCitiesPlanEl.value = cityStays
      .map((item) =>
        item && item.city
          ? item.nights && Number(item.nights) > 0
            ? `${item.city} ${item.nights}`
            : `${item.city}`
          : ""
      )
      .filter(Boolean)
      .join("\n");
  } else {
    tripCitiesPlanEl.value = (merged.cities_to_visit || []).join("\n");
  }
  tripTravelStartDateEl.value = merged.travel_start_date || "";
  tripTravelEndDateEl.value = merged.travel_end_date || "";
  tripNumNightsEl.value = Number(merged.num_nights || 0);
  tripOriginCityEl.value = merged.origin_city || "";
  tripOriginAirportEl.value = merged.origin_airport || "";
  tripReturnPointEl.value = merged.return_point || "";
  tripDestinationAirportHintEl.value = merged.destination_airport_hint || "";
  tripReturnAirportHintEl.value = merged.return_airport_hint || "";
  tripTravelPurposeEl.value = merged.travel_purpose || "";
  tripTravelerProfileEl.value = merged.traveler_profile || "";
}

function getTripInfoFromForm() {
  const guest_names = tripGuestNamesEl.value
    .split(/\r?\n|,/)
    .map((s) => s.trim())
    .filter(Boolean);
  const cityPlanLines = tripCitiesPlanEl.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const city_stays = cityPlanLines
    .map((line) => {
      const m = line.match(/^(.*?)(?:\s+(\d+))?$/);
      const city = (m?.[1] || "").trim();
      const nights = parseInt((m?.[2] || "0").trim(), 10);
      return { city, nights: Number.isFinite(nights) ? nights : 0 };
    })
    .filter((x) => x.city);
  const cities_to_visit = city_stays.map((x) => x.city);

  return normalizeTripInfo({
    guest_names,
    destination_country: tripDestinationCountryEl.value.trim(),
    cities_to_visit,
    city_stays,
    travel_start_date: tripTravelStartDateEl.value.trim(),
    travel_end_date: tripTravelEndDateEl.value.trim(),
    num_nights: parseInt(tripNumNightsEl.value || "0", 10) || 0,
    origin_city: tripOriginCityEl.value.trim(),
    origin_airport: tripOriginAirportEl.value.trim().toUpperCase(),
    return_point: tripReturnPointEl.value.trim(),
    destination_airport_hint: tripDestinationAirportHintEl.value.trim().toUpperCase(),
    return_airport_hint: tripReturnAirportHintEl.value.trim().toUpperCase(),
    travel_purpose: tripTravelPurposeEl.value.trim(),
    traveler_profile: tripTravelerProfileEl.value.trim(),
  });
}

async function extractTripInfo() {
  const inputDir = inputDirEl.value.trim() || "input";
  const originalBtnText = extractTripBtn.textContent;
  extractTripBtn.textContent = "⏳ Đang trích xuất...";
  extractTripBtn.disabled = true;
  tripInfoPanelEl.innerHTML = "⏳ Đang đọc và phân tích các file có tiền tố THONG TIN CHUYEN DI / HO SO CA NHAN / MUC DICH CHUYEN DI...";

  try {
    const res = await fetch("/api/booking/extract_trip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir, project_id: getProjectId() }),
    });

    const data = await res.json();

    if (!res.ok) {
      tripInfoPanelEl.textContent = `❌ Lỗi: ${data.error || "Không thể trích xuất"}`;
      return;
    }

    setTripInfoForm(data.trip_info);
    tripInfoPanelEl.textContent = `✅ Trích xuất thành công.\n\n${formatTripInfo(data.trip_info)}`;
  } catch (error) {
    tripInfoPanelEl.textContent = `❌ Lỗi: ${error.message}`;
  } finally {
    extractTripBtn.textContent = originalBtnText;
    extractTripBtn.disabled = false;
  }
}

async function saveTripInfo() {
  const originalBtnText = saveTripInfoBtn.textContent;
  saveTripInfoBtn.textContent = "⏳ Đang lưu...";
  saveTripInfoBtn.disabled = true;
  try {
    const tripInfo = getTripInfoFromForm();
    const res = await fetch("/api/booking/trip/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trip_info: tripInfo, project_id: getProjectId() }),
    });
    const data = await res.json();
    if (!res.ok) {
      tripInfoPanelEl.textContent = `❌ Lỗi lưu: ${data.error || "Không thể lưu"}`;
      return;
    }
    setTripInfoForm(data.trip_info);
    tripInfoPanelEl.textContent = "✅ Đã lưu thông tin chuyến đi.";
  } catch (error) {
    tripInfoPanelEl.textContent = `❌ Lỗi lưu: ${error.message}`;
  } finally {
    saveTripInfoBtn.textContent = originalBtnText;
    saveTripInfoBtn.disabled = false;
  }
}

async function loadLatestTripInfo() {
  try {
    const res = await fetch("/api/booking/trip/latest" + (getProjectId() ? `?project_id=${getProjectId()}` : ""));
    const data = await res.json();
    setTripInfoForm(data.trip_info || {});
  } catch (error) {
    setTripInfoForm({});
  }
}

async function runAIBooking() {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputDir = bookingOutputAIEl.value.trim() || "output";
  const originalBtnText = runAIBookingBtn.textContent;

  const editedTripInfo = getTripInfoFromForm();

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
        trip_info: editedTripInfo,
        project_id: getProjectId(),
      }),
    });

    let data;
    try {
      const responseText = await res.text();
      data = JSON.parse(responseText);
    } catch (e) {
      throw new Error("❌ Có lỗi Server Nội bộ (như thiếu API Key, gõ sai thư mục...). Vui lòng mở cái bảng Terminal đen lên xem nó báo lỗi chữ gì nha!");
    }

    if (!res.ok) {
      aiBookingStatusEl.textContent = `❌ Lỗi: ${data.error || "Không thể tạo booking"}`;
      hotelBookingResultEl.srcdoc = `<p>Lỗi: ${data.error || "Không thể tạo booking"}</p>`;
      flightBookingResultEl.srcdoc = "";
      syncCombinedPreviews();
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
    if (data.flight_html) {
      exportFlightPdfBtn.style.display = "inline-block";
    }
    syncCombinedPreviews();

    aiBookingStatusEl.textContent = data.used_cache
      ? "✅ Hoàn thành! (dùng dữ liệu đã cache - không tốn token). Bấm 'Trích xuất từ input' để tạo mới."
      : "✅ Hoàn thành! AI đã tạo booking thành công.";
  } catch (error) {
    aiBookingStatusEl.textContent = `❌ Lỗi: ${error.message}`;
    hotelBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
    flightBookingResultEl.srcdoc = "";
    syncCombinedPreviews();
  } finally {
    runAIBookingBtn.textContent = originalBtnText;
    runAIBookingBtn.disabled = false;
  }
}

// ==================== PRE-CHECK FUNCTIONS ====================

let precheckResults = []; // store scan results globally

async function precheckScan() {
  const inputDir = document.getElementById("precheckInputDir").value.trim() || "input";
  const scanBtn = document.getElementById("precheckScanBtn");
  const progressDiv = document.getElementById("precheckProgress");
  const statusText = document.getElementById("precheckStatusText");
  const resultsCard = document.getElementById("precheckResultsCard");
  const summaryDiv = document.getElementById("precheckSummary");
  const resultsDiv = document.getElementById("precheckResults");

  scanBtn.disabled = true;
  scanBtn.textContent = "⏳ Đang quét...";
  progressDiv.style.display = "block";
  statusText.textContent = "AI đang quét và phân tích tất cả file... (có thể mất vài phút)";
  resultsCard.style.display = "none";

  try {
    const res = await fetch("/api/precheck/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusText.textContent = `Lỗi: ${data.error}`;
      return;
    }

    precheckResults = data.files || [];
    progressDiv.style.display = "none";
    resultsCard.style.display = "block";

    // Summary
    summaryDiv.innerHTML = `
      📁 Tổng: <strong>${data.total_files}</strong> file &nbsp;|&nbsp;
      ✅ Sạch: <strong>${data.clean_count}</strong> &nbsp;|&nbsp;
      ⚠️ Cần tách: <strong style="color:#dc2626;">${data.multi_doc_count}</strong>
    `;

    // Results table
    let html = `<table style="width:100%; border-collapse:collapse; font-size:0.9em;">
      <thead>
        <tr style="background:#f1f5f9; text-align:left;">
          <th style="padding:8px; border-bottom:2px solid #e2e8f0;">Trạng thái</th>
          <th style="padding:8px; border-bottom:2px solid #e2e8f0;">File</th>
          <th style="padding:8px; border-bottom:2px solid #e2e8f0;">Trang</th>
          <th style="padding:8px; border-bottom:2px solid #e2e8f0;">Số giấy tờ</th>
          <th style="padding:8px; border-bottom:2px solid #e2e8f0;">Loại giấy tờ</th>
        </tr>
      </thead>
      <tbody>`;

    for (const f of precheckResults) {
      const status = f.needs_split
        ? '<span style="color:#dc2626; font-weight:bold;">⚠️ Cần tách</span>'
        : '<span style="color:#16a34a;">✅ Sạch</span>';
      const rowBg = f.needs_split ? "background:#fef2f2;" : "";
      html += `
        <tr style="${rowBg} border-bottom:1px solid #e2e8f0;">
          <td style="padding:8px;">${status}</td>
          <td style="padding:8px; word-break:break-all;" title="${f.path}">${f.filename}</td>
          <td style="padding:8px; text-align:center;">${f.page_count}</td>
          <td style="padding:8px; text-align:center; font-weight:bold; ${f.doc_count >= 2 ? 'color:#dc2626;' : ''}">${f.doc_count}</td>
          <td style="padding:8px; font-size:0.85em;">${(f.doc_types || []).join(", ")}</td>
        </tr>`;
    }
    html += "</tbody></table>";
    resultsDiv.innerHTML = html;

    // Show/hide pipeline buttons
    const sendMultiBtn = document.getElementById("sendMultiToSplitterBtn");
    const sendCleanBtn = document.getElementById("sendCleanToClassifierBtn");
    if (sendMultiBtn) sendMultiBtn.style.display = data.multi_doc_count > 0 ? "inline-block" : "none";
    if (sendCleanBtn) sendCleanBtn.style.display = data.clean_count > 0 ? "inline-block" : "none";

  } catch (e) {
    statusText.textContent = `Lỗi: ${e.message}`;
  } finally {
    scanBtn.disabled = false;
    scanBtn.textContent = "🔍 Quét tất cả file";
  }
}

async function sendMultiToSplitter() {
  const multiFiles = precheckResults.filter(f => f.needs_split).map(f => f.path);
  if (multiFiles.length === 0) { alert("Không có file cần tách."); return; }
  const btn = document.getElementById("sendMultiToSplitterBtn");
  btn.disabled = true; btn.textContent = "Đang chuyển...";
  try {
    const res = await fetch("/api/pipeline/send-to-splitter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_paths: multiFiles }),
    });
    const data = await res.json();
    if (!res.ok) { alert(`Lỗi: ${data.error}`); return; }
    alert(`✅ Đã chuyển ${data.count} file sang splitter_uploads.\nHãy upload từng file ở Tab ① để tách.`);
    setActiveTab("aisplitter");
  } catch (e) { alert(`Lỗi: ${e.message}`); }
  finally { btn.disabled = false; btn.textContent = "⚠️ Gửi file cần tách → Tab ① Tách PDF (AI)"; }
}

async function sendCleanToClassifier() {
  const cleanFiles = precheckResults.filter(f => !f.needs_split).map(f => f.path);
  if (cleanFiles.length === 0) { alert("Không có file sạch."); return; }
  const btn = document.getElementById("sendCleanToClassifierBtn");
  btn.disabled = true; btn.textContent = "Đang chuyển...";
  try {
    const res = await fetch("/api/pipeline/send-clean-to-classifier", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_paths: cleanFiles }),
    });
    const data = await res.json();
    if (!res.ok) { alert(`Lỗi: ${data.error}`); return; }
    alert(`✅ Đã chuyển ${data.count} file sạch sang ${data.target_dir}.\nChuyển sang Tab ③ để phân loại.`);
    setActiveTab("classifier");
    loadClassifierFiles();
  } catch (e) { alert(`Lỗi: ${e.message}`); }
  finally { btn.disabled = false; btn.textContent = "✅ Gửi file sạch → Tab ③ Phân loại"; }
}

// ==================== EVENT LISTENERS ====================

refreshBtn.addEventListener("click", fetchFiles);
loadStepsBtn.addEventListener("click", loadSteps);
runItineraryBtn.addEventListener("click", runItinerary);
runAllBtn.addEventListener("click", runAll);
saveItineraryContextBtn.addEventListener("click", saveItineraryContext);
runBookingBtn.addEventListener("click", runBookingGeneration);
extractTripBtn.addEventListener("click", extractTripInfo);
saveTripInfoBtn.addEventListener("click", saveTripInfo);
runAIBookingBtn.addEventListener("click", runAIBooking);
loadClassifierFilesBtn.addEventListener("click", loadClassifierFiles);
runClassifierBtn.addEventListener("click", runClassifier);
if (pdfBuildSplitFormBtn) {
  pdfBuildSplitFormBtn.addEventListener("click", buildPdfManualSegments);
}
if (pdfRunSplitBtn) {
  pdfRunSplitBtn.addEventListener("click", runPdfManualSplit);
}
if (pdfRunMergeBtn) {
  pdfRunMergeBtn.addEventListener("click", runPdfMerge);
}
if (pdfRunRenameBtn) {
  pdfRunRenameBtn.addEventListener("click", runPdfRename);
}
if (pdfRenameGenBtn) {
  pdfRenameGenBtn.addEventListener("click", genPdfRenameDocType);
}
if (pdfRenamePrefixEl) {
  pdfRenamePrefixEl.addEventListener("change", updatePdfRenamePreview);
}
if (pdfRenameDocTypeEl) {
  pdfRenameDocTypeEl.addEventListener("change", updatePdfRenamePreview);
}
if (pdfRenameDocTypeCustomEl) {
  pdfRenameDocTypeCustomEl.addEventListener("input", updatePdfRenamePreview);
}
if (pdfMergeGenBtn) {
  pdfMergeGenBtn.addEventListener("click", genPdfMergeDocType);
}
if (pdfMergePrefixEl) {
  pdfMergePrefixEl.addEventListener("change", updatePdfMergePreview);
}
if (pdfMergeDocTypeEl) {
  pdfMergeDocTypeEl.addEventListener("change", updatePdfMergePreview);
}
if (pdfMergeDocTypeCustomEl) {
  pdfMergeDocTypeCustomEl.addEventListener("input", updatePdfMergePreview);
}

// PDF Export helpers
function printIframeAsPdf(iframeEl, title) {
  const iframeDoc = iframeEl.contentDocument || iframeEl.contentWindow?.document;
  if (!iframeDoc || !iframeDoc.body || iframeDoc.body.innerHTML.trim() === "") {
    alert("Chưa có nội dung để xuất PDF.");
    return;
  }

  const printWin = window.open("", "_blank");
  if (!printWin) {
    alert("Trình duyệt đã chặn cửa sổ popup. Vui lòng cho phép popup rồi thử lại.");
    return;
  }

  // Clone iframe HTML content and add print-optimized styles
  const htmlContent = iframeDoc.documentElement.outerHTML;
  printWin.document.open();
  printWin.document.write(htmlContent);
  printWin.document.close();

  // Add print-friendly CSS
  const style = printWin.document.createElement("style");
  style.textContent = `
    @media print {
      body { margin: 0; }
      @page { size: A4; margin: 10mm; }
    }
  `;
  printWin.document.head.appendChild(style);

  // Wait for content to load, then trigger print
  printWin.onload = () => {
    setTimeout(() => {
      printWin.print();
    }, 300);
  };

  // Fallback if onload doesn't fire
  setTimeout(() => {
    printWin.print();
  }, 800);
}

exportHotelPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(hotelBookingResultEl, "Hotel Booking");
});

exportFlightPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(flightBookingResultEl, "Flight Booking");
});

exportItineraryPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(itineraryResultEl, "Travel Itinerary");
});

exportCombinedItineraryPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(combinedItineraryResultEl, "Travel Itinerary");
});

exportCombinedFlightPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(combinedFlightBookingResultEl, "Flight Booking");
});

exportCombinedHotelPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(combinedHotelBookingResultEl, "Hotel Booking");
});

function buildCombinedHotelsHtml(htmls) {
  const pages = (htmls || []).map((html, i) => {
    const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    const bodyContent = bodyMatch ? bodyMatch[1] : html;
    const pageBreak = i < htmls.length - 1 ? 'style="page-break-after: always;"' : "";
    return `<section ${pageBreak}>${bodyContent}</section>`;
  });

  const headMatch = htmls[0]?.match(/<head[^>]*>([\s\S]*?)<\/head>/i);
  const headContent = headMatch ? headMatch[1] : "";

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  ${headContent}
  <style>
    @media print {
      body { margin: 0; }
      @page { size: A4; margin: 10mm; }
    }
  </style>
</head>
<body>
  ${pages.join("\n")}
</body>
</html>`;
}

// Export ALL hotel bookings as one PDF with page breaks
function printAllHotelsAsPdf() {
  if (!hotelHtmls || hotelHtmls.length === 0) {
    alert("Chưa có booking khách sạn để xuất.");
    return;
  }

  const printWin = window.open("", "_blank");
  if (!printWin) {
    alert("Trình duyệt đã chặn cửa sổ popup. Vui lòng cho phép popup rồi thử lại.");
    return;
  }

  const combinedHtml = buildCombinedHotelsHtml(hotelHtmls);

  printWin.document.open();
  printWin.document.write(combinedHtml);
  printWin.document.close();

  printWin.onload = () => {
    setTimeout(() => { printWin.print(); }, 300);
  };
  setTimeout(() => { printWin.print(); }, 800);
}

function printCombinedPackagePdf() {
  const itineraryDoc =
    combinedItineraryResultEl.contentDocument ||
    combinedItineraryResultEl.contentWindow?.document;
  const flightDoc =
    combinedFlightBookingResultEl.contentDocument ||
    combinedFlightBookingResultEl.contentWindow?.document;
  const hotelDoc =
    combinedHotelBookingResultEl.contentDocument ||
    combinedHotelBookingResultEl.contentWindow?.document;

  const hasItinerary = itineraryDoc?.body?.innerHTML?.trim();
  const hasFlight = flightDoc?.body?.innerHTML?.trim();
  const hasHotel = hotelDoc?.body?.innerHTML?.trim();

  if (!hasItinerary || !hasFlight || !hasHotel) {
    alert("Cần đủ 3 nội dung: lịch trình, booking máy bay, booking khách sạn.");
    return;
  }

  const printWin = window.open("", "_blank");
  if (!printWin) {
    alert("Trình duyệt đã chặn cửa sổ popup. Vui lòng cho phép popup rồi thử lại.");
    return;
  }

  const extractBody = (doc) => {
    const html = doc.documentElement?.outerHTML || "";
    const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    return bodyMatch ? bodyMatch[1] : doc.body.innerHTML;
  };

  const extractHead = (doc) => {
    const html = doc.documentElement?.outerHTML || "";
    const headMatch = html.match(/<head[^>]*>([\s\S]*?)<\/head>/i);
    return headMatch ? headMatch[1] : "";
  };

  const itineraryBody = extractBody(itineraryDoc);
  const flightBody = extractBody(flightDoc);
  const hotelBody = extractBody(hotelDoc);
  const mergedHead = [extractHead(itineraryDoc), extractHead(flightDoc), extractHead(hotelDoc)]
    .filter(Boolean)
    .join("\n");

  const combinedHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  ${mergedHead}
  <style>
    @media print {
      body { margin: 0; }
      @page { size: A4; margin: 10mm; }
    }
  </style>
</head>
<body>
  <section style="page-break-after: always;">${itineraryBody}</section>
  <section style="page-break-after: always;">${flightBody}</section>
  <section>${hotelBody}</section>
</body>
</html>`;

  printWin.document.open();
  printWin.document.write(combinedHtml);
  printWin.document.close();

  printWin.onload = () => {
    setTimeout(() => {
      printWin.print();
    }, 300);
  };
  setTimeout(() => {
    printWin.print();
  }, 900);
}

exportAllHotelPdfBtn.addEventListener("click", printAllHotelsAsPdf);
exportCombinedAllPdfBtn.addEventListener("click", printCombinedPackagePdf);

stepsListEl.addEventListener("click", (event) => {
  const btn = event.target.closest(".step-btn");
  if (btn) {
    if (btn.disabled) return;
    const step = btn.dataset.step;
    const done = btn.dataset.done === "true";
    if (step) runStep(step, done);
    return;
  }

  const toggle = event.target.closest(".step-log-toggle");
  if (!toggle) return;
  const step = toggle.dataset.stepLogToggle;
  if (!step) return;
  if (activeStepLog === step) {
    showStepLog(step, false);
  } else {
    showStepLog(step, true);
  }
});

stepsListEl.addEventListener("input", (event) => {
  const target = event.target;
  if (target && target.id === "writerContext") {
    writerContextCache = target.value || "";
  }
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

window.addEventListener("load", async () => {
  setActiveTab("precheck");
  await fetchFiles();
  await loadSteps();
  await loadLatestItinerary();
  await loadLatestBooking();
  await loadItineraryContext();
  await loadLatestTripInfo();
  await loadDestinations();
  await loadClassifierFiles();
  syncCombinedPreviews();
});

// ==================== AI PDF SPLITTER ====================

// Load file list from splitter_uploads
async function loadSplitterFileList() {
  const listEl = document.getElementById("splitterFileList");
  if (!listEl) return;
  try {
    const res = await fetch("/api/ai-splitter/list");
    const data = await res.json();
    const files = data.files || [];

    // Show/hide header buttons
    const splitAllBtn = document.getElementById("splitAllBtn");
    const deleteAllBtn = document.getElementById("deleteAllSplitterBtn");
    if (splitAllBtn) splitAllBtn.style.display = files.length > 0 ? "inline-block" : "none";
    if (deleteAllBtn) deleteAllBtn.style.display = files.length > 0 ? "inline-block" : "none";

    if (files.length === 0) {
      listEl.className = "file-list empty";
      listEl.innerHTML = "Chưa có file. Hãy quét ở Tab ⓪ rồi gửi file cần tách sang đây.";
      return;
    }
    listEl.className = "file-list";
    listEl.innerHTML = files.map(f => {
      const sizeMB = (f.size / 1024 / 1024).toFixed(1);
      return `<div class="file-row" style="align-items:center;">
        <div style="flex:1;">
          <span class="file-name">📄 ${f.filename}</span>
          <span class="file-domain">(${sizeMB} MB)</span>
        </div>
        <div style="display:flex; gap:6px;">
          <button class="splitter-process-btn" data-filename="${f.filename}" 
                  style="padding:5px 12px; background:#4f46e5; color:#fff; border:none; border-radius:5px; cursor:pointer; font-size:12px;">
            ✂️ Tách
          </button>
          <button class="splitter-delete-btn" data-filename="${f.filename}" 
                  style="padding:5px 12px; background:#dc2626; color:#fff; border:none; border-radius:5px; cursor:pointer; font-size:12px;">
            🗑️
          </button>
        </div>
      </div>`;
    }).join("");
  } catch (e) {
    listEl.innerHTML = `Lỗi: ${e.message}`;
  }
}

// Delete single file
async function deleteSplitterFile(filename) {
  if (!confirm(`Xóa file "${filename}"?`)) return;
  try {
    await fetch("/api/ai-splitter/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    });
    loadSplitterFileList();
  } catch (e) { alert(`Lỗi: ${e.message}`); }
}

// Delete all files
async function deleteAllSplitter() {
  if (!confirm("Xóa TẤT CẢ file trong danh sách chờ tách?")) return;
  try {
    const res = await fetch("/api/ai-splitter/delete-all", { method: "POST" });
    const data = await res.json();
    alert(`✅ Đã xóa ${data.deleted_count} file.`);
    loadSplitterFileList();
  } catch (e) { alert(`Lỗi: ${e.message}`); }
}

// Split all files sequentially with combined results
async function splitAllFiles() {
  const listEl = document.getElementById("splitterFileList");
  const btns = listEl ? listEl.querySelectorAll(".splitter-process-btn") : [];
  if (btns.length === 0) { alert("Không có file để tách."); return; }

  const splitAllBtn = document.getElementById("splitAllBtn");
  if (splitAllBtn) { splitAllBtn.disabled = true; splitAllBtn.textContent = "⏳ Đang tách..."; }

  const filenames = Array.from(btns).map(b => b.dataset.filename);
  const totalFiles = filenames.length;

  // Create progress panel in the splitter results area
  const progressDiv = document.getElementById("splitterProgress");
  const statusText = document.getElementById("splitterStatus");
  const classificationsCard = document.getElementById("classificationsCard");
  const classificationsDiv = document.getElementById("classificationsDiv");
  const resultsCard = document.getElementById("splitterResultsCard");
  const resultsDiv = document.getElementById("splitterResultsDiv");

  // Show overall progress
  if (progressDiv) progressDiv.style.display = "block";
  if (classificationsCard) classificationsCard.style.display = "none";
  if (resultsCard) resultsCard.style.display = "none";

  // Accumulate all output files from all processed files
  const allOutputFiles = []; // {file_id, filename, output_files}
  const allClassifications = []; // accumulated classifications with source filename
  let completedCount = 0;

  for (let i = 0; i < filenames.length; i++) {
    const fname = filenames[i];
    if (splitAllBtn) splitAllBtn.textContent = `⏳ ${i + 1}/${totalFiles}: ${fname}`;
    if (statusText) statusText.textContent = `📄 [${i + 1}/${totalFiles}] Đang tách: ${fname}...`;

    // Update progress bar
    const progressBar = document.getElementById("splitterProgressBar");
    const progressText = document.getElementById("splitterProgressText");
    if (progressBar) { progressBar.value = Math.round((i / totalFiles) * 100); progressBar.max = 100; }
    if (progressText) progressText.textContent = `File ${i + 1}/${totalFiles}`;

    try {
      const res = await fetch("/api/ai-splitter/process-local", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: fname }),
      });
      const data = await res.json();
      if (!res.ok) { console.error(`Error: ${data.error}`); continue; }

      const fileId = data.file_id;

      // Poll until this file is done — show live status
      await new Promise((resolve) => {
        let dots = 0;
        const checkDone = setInterval(async () => {
          try {
            const statusRes = await fetch(`/api/ai-splitter/status/${fileId}`);
            const statusData = await statusRes.json();

            // Live progress update
            dots = (dots + 1) % 4;
            const dotStr = ".".repeat(dots);
            const statusMap = {
              converting: `🔄 Chuyển PDF → ảnh${dotStr}`,
              classifying: `🤖 Phân loại trang ${statusData.current_page || "?"}/${statusData.page_count || "?"}${dotStr}`,
              splitting: `✂️ Đang tách file${dotStr}`,
              processing: `⚙️ Đang xử lý${dotStr}`,
            };
            if (statusText) {
              statusText.textContent = `📄 [${i + 1}/${totalFiles}] ${fname} — ${statusMap[statusData.status] || statusData.status}`;
            }

            // Update sub-progress bar
            if (statusData.page_count > 0 && progressBar) {
              const filePct = (statusData.current_page || 0) / statusData.page_count;
              const overallPct = Math.round(((i + filePct) / totalFiles) * 100);
              progressBar.value = overallPct;
            }

            if (statusData.status === "completed") {
              clearInterval(checkDone);
              completedCount++;
              // Collect this file's output files
              if (statusData.output_files && statusData.output_files.length > 0) {
                allOutputFiles.push({
                  file_id: fileId,
                  source_filename: fname,
                  output_files: statusData.output_files,
                });
              }
              // Collect classifications
              if (statusData.classifications) {
                for (const c of statusData.classifications) {
                  allClassifications.push({ ...c, source_file: fname });
                }
              }
              resolve();
            } else if (statusData.status === "error") {
              clearInterval(checkDone);
              console.error(`Error splitting ${fname}: ${statusData.error}`);
              resolve();
            }
          } catch { clearInterval(checkDone); resolve(); }
        }, 1500);
      });

    } catch (e) { console.error(`Error splitting ${fname}:`, e); }
  }

  // All done — show combined results
  if (progressBar) { progressBar.value = 100; }
  if (progressText) progressText.textContent = "100%";
  if (statusText) statusText.textContent = `✅ Đã tách xong ${completedCount}/${totalFiles} file!`;

  // Render combined output files grouped by source file
  if (resultsCard && resultsDiv && allOutputFiles.length > 0) {
    resultsCard.style.display = "block";
    let html = "";
    for (const group of allOutputFiles) {
      html += `<div style="padding:8px 12px; background:#f0f4ff; border-radius:6px; margin-bottom:8px;">
        <strong>📁 ${group.source_filename}</strong> → ${group.output_files.length} file
        <a href="/api/ai-splitter/download-zip/${group.file_id}" 
           style="margin-left:8px; text-decoration:none; padding:3px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.8em;">
          ⬇ Download ZIP
        </a>
      </div>`;
      for (const f of group.output_files) {
        const pages = f.pages.join(", ");
        html += `<div style="padding:6px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center; padding-left:24px;">
          <div>
            <strong>${f.filename}</strong>
            <br><small style="color:#666;">${f.document_type} · 👤 ${f.person_name} · ${f.pages.length} trang (${pages})</small>
          </div>
          <a href="/api/ai-splitter/download/${group.file_id}/${encodeURIComponent(f.filename)}"
             style="text-decoration:none; padding:4px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.8em;">
            ⬇
          </a>
        </div>`;
      }
    }
    resultsDiv.innerHTML = html;
  }

  if (splitAllBtn) { splitAllBtn.disabled = false; splitAllBtn.textContent = "✂️ Tách tất cả"; }
}

// Refresh button
const refreshSplitterListBtn = document.getElementById("refreshSplitterListBtn");
if (refreshSplitterListBtn) {
  refreshSplitterListBtn.addEventListener("click", loadSplitterFileList);
}

// Split-all button
const splitAllBtn2 = document.getElementById("splitAllBtn");
if (splitAllBtn2) {
  splitAllBtn2.addEventListener("click", splitAllFiles);
}

// Delete-all button
const deleteAllSplitterBtn = document.getElementById("deleteAllSplitterBtn");
if (deleteAllSplitterBtn) {
  deleteAllSplitterBtn.addEventListener("click", deleteAllSplitter);
}

// Event delegation for per-file buttons
document.addEventListener("click", async (e) => {
  // Tách button
  const processBtn = e.target.closest(".splitter-process-btn");
  if (processBtn) {
    const filename = processBtn.dataset.filename;
    if (!filename) return;
    processBtn.disabled = true;
    processBtn.textContent = "⏳...";
    try {
      const res = await fetch("/api/ai-splitter/process-local", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(`Lỗi: ${data.error}`);
        processBtn.disabled = false;
        processBtn.textContent = "✂️ Tách";
        return;
      }
      window.dispatchEvent(new CustomEvent("splitter-start", { detail: { file_id: data.file_id, filename: data.filename } }));
    } catch (err) {
      alert(`Lỗi: ${err.message}`);
      processBtn.disabled = false;
      processBtn.textContent = "✂️ Tách";
    }
    return;
  }

  // Delete button
  const deleteBtn = e.target.closest(".splitter-delete-btn");
  if (deleteBtn) {
    const filename = deleteBtn.dataset.filename;
    if (filename) deleteSplitterFile(filename);
    return;
  }
});

(function initAISplitter() {
  const uploadBtn = document.getElementById("splitterUploadBtn");
  const fileInput = document.getElementById("splitterFileInput");
  const progressDiv = document.getElementById("splitterProgress");
  const progressBar = document.getElementById("splitterProgressBar");
  const progressText = document.getElementById("splitterProgressText");
  const statusText = document.getElementById("splitterStatus");
  const classificationsCard = document.getElementById("splitterClassificationsCard");
  const classificationsDiv = document.getElementById("splitterClassifications");
  const resultsCard = document.getElementById("splitterResultsCard");
  const resultsDiv = document.getElementById("splitterResults");
  const downloadAllBtn = document.getElementById("splitterDownloadAllBtn");

  if (!uploadBtn) return; // safety check

  let currentFileId = null;
  let pollTimer = null;

  const DOC_ICONS = {
    Passport: "🛂", Birth_Certificate: "👶", Marriage_Certificate: "💍",
    Contract: "📝", Agreement: "📝", Decision: "📄", Account_Statement: "🏦",
    Social_Insurance_Record: "📋", Power_of_Attorney: "⚖️", CCCD: "🆔",
    Business_License: "💼", Receipt_Voucher: "🧾", Price_Quotation: "💰",
    Registration_Form: "📑", Commitment_Letter: "✉️",
  };

  function getIcon(docType) {
    return DOC_ICONS[docType] || "📄";
  }

  uploadBtn.addEventListener("click", async () => {
    if (!fileInput.files || !fileInput.files.length) {
      alert("Vui lòng chọn file PDF.");
      return;
    }

    const file = fileInput.files[0];
    uploadBtn.disabled = true;
    uploadBtn.textContent = "Đang upload...";
    progressDiv.style.display = "block";
    statusText.textContent = "Đang upload file...";
    progressBar.value = 0;
    progressText.textContent = "0%";
    classificationsCard.style.display = "none";
    resultsCard.style.display = "none";

    try {
      // 1. Upload
      const formData = new FormData();
      formData.append("file", file);
      const uploadRes = await fetch("/api/ai-splitter/upload", { method: "POST", body: formData });
      const uploadData = await uploadRes.json();
      if (uploadData.error) {
        statusText.textContent = `Lỗi: ${uploadData.error}`;
        uploadBtn.disabled = false;
        uploadBtn.textContent = "📤 Upload & Tách";
        return;
      }

      currentFileId = uploadData.file_id;
      statusText.textContent = `Đã upload ${uploadData.filename} (${uploadData.page_count} trang). Đang xử lý...`;

      // 2. Start processing
      await fetch(`/api/ai-splitter/process/${currentFileId}`, { method: "POST" });

      // 3. Poll status
      startPolling();
    } catch (err) {
      statusText.textContent = `Lỗi: ${err.message}`;
      uploadBtn.disabled = false;
      uploadBtn.textContent = "📤 Upload & Tách";
    }
  });

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(checkStatus, 1000);
  }

  // Listen for process-local events (from file list Tách buttons)
  window.addEventListener("splitter-start", (e) => {
    const { file_id, filename } = e.detail;
    currentFileId = file_id;
    progressDiv.style.display = "block";
    statusText.textContent = `Đang tách ${filename}...`;
    progressBar.value = 0;
    progressText.textContent = "0%";
    classificationsCard.style.display = "none";
    resultsCard.style.display = "none";
    startPolling();
  });

  async function checkStatus() {
    if (!currentFileId) return;
    try {
      const res = await fetch(`/api/ai-splitter/status/${currentFileId}`);
      const data = await res.json();

      // Update progress
      const pct = data.page_count > 0
        ? Math.round((data.current_page / data.page_count) * 100) : 0;
      progressBar.value = pct;
      progressBar.max = 100;
      progressText.textContent = `${pct}%`;

      const statusMap = {
        converting: "Đang chuyển PDF thành ảnh...",
        classifying: `Đang phân loại trang ${data.current_page}/${data.page_count}...`,
        splitting: "Đang tách file...",
        processing: "Đang xử lý...",
      };
      statusText.textContent = statusMap[data.status] || data.status;

      // Show live classifications
      if (data.classifications && data.classifications.length > 0) {
        renderClassifications(data.classifications);
      }

      // Completed
      if (data.status === "completed") {
        clearInterval(pollTimer);
        progressBar.value = 100;
        progressText.textContent = "100%";
        statusText.textContent = `✅ Hoàn thành! Đã tách thành ${data.output_files.length} file.`;
        renderOutputFiles(data.output_files);
        uploadBtn.disabled = false;
        uploadBtn.textContent = "📤 Upload & Tách";
      } else if (data.status === "error") {
        clearInterval(pollTimer);
        statusText.textContent = `❌ Lỗi: ${data.error}`;
        uploadBtn.disabled = false;
        uploadBtn.textContent = "📤 Upload & Tách";
      }
    } catch (err) {
      console.error("Poll error:", err);
    }
  }

  function renderClassifications(cls) {
    classificationsCard.style.display = "block";
    classificationsDiv.innerHTML = cls.map((c) => {
      const icon = getIcon(c.document_type_en);
      const cont = c.is_continuation ? ' <span style="color:#888;font-size:0.85em;">↳ cont.</span>' : "";
      return `<div style="padding:4px 8px; border-bottom:1px solid #f0f0f0; font-size:0.9em;">
        <strong>P${c.page}</strong> ${icon} ${c.document_type_en}${cont}
        <span style="color:#666; margin-left:8px;">👤 ${c.person_name_en}</span>
      </div>`;
    }).join("");
    // Auto-scroll to bottom
    classificationsDiv.scrollTop = classificationsDiv.scrollHeight;
  }

  function renderOutputFiles(files) {
    resultsCard.style.display = "block";
    resultsDiv.innerHTML = files.map((f) => {
      const icon = getIcon(f.document_type);
      const pages = f.pages.join(", ");
      return `<div style="padding:8px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center;">
        <div>
          ${icon} <strong>${f.filename}</strong>
          <br><small style="color:#666;">${f.document_type} · 👤 ${f.person_name} · ${f.pages.length} trang (${pages})</small>
        </div>
        <a href="/api/ai-splitter/download/${currentFileId}/${encodeURIComponent(f.filename)}"
           style="text-decoration:none; padding:4px 12px; background:#4f46e5; color:white; border-radius:4px; font-size:0.85em;">
          ⬇ Download
        </a>
      </div>`;
    }).join("");
  }

  downloadAllBtn.addEventListener("click", () => {
    if (!currentFileId) return;
    window.location.href = `/api/ai-splitter/download-zip/${currentFileId}`;
  });
})();

// ==================== PIPELINE BUTTON LISTENERS ====================
const sendToClassifierBtn = document.getElementById("sendToClassifierBtn");
if (sendToClassifierBtn) {
  sendToClassifierBtn.addEventListener("click", sendToClassifier);
}
const sendToInputBtn = document.getElementById("sendToInputBtn");
if (sendToInputBtn) {
  sendToInputBtn.addEventListener("click", sendToInput);
}

// Pre-check button listeners
const precheckScanBtn = document.getElementById("precheckScanBtn");
if (precheckScanBtn) {
  precheckScanBtn.addEventListener("click", precheckScan);
}
const sendMultiToSplitterBtn = document.getElementById("sendMultiToSplitterBtn");
if (sendMultiToSplitterBtn) {
  sendMultiToSplitterBtn.addEventListener("click", sendMultiToSplitter);
}
const sendCleanToClassifierBtn = document.getElementById("sendCleanToClassifierBtn");
if (sendCleanToClassifierBtn) {
  sendCleanToClassifierBtn.addEventListener("click", sendCleanToClassifier);
}
