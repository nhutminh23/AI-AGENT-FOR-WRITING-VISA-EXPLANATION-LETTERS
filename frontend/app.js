const fileListEl = document.getElementById("fileList");
const resultEl = document.getElementById("result");
const summaryEl = document.getElementById("summary");
const summaryItineraryEl = document.getElementById("summaryItinerary");
const stepsListEl = document.getElementById("stepsList");
const inputDirEl = document.getElementById("inputDir");
const outputPathEl = document.getElementById("outputPath");
const itineraryOutputEl = document.getElementById("itineraryOutput");
const itParticipantsEl = document.getElementById("itParticipants");
const itAdditionalInfoEl = document.getElementById("itAdditionalInfo");
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
const bookingSourceDbEl = document.getElementById("bookingSourceDb");
const bookingSourceFileEl = document.getElementById("bookingSourceFile");
const fileSelectRowEl = document.getElementById("fileSelectRow");
const dbBookingStatusEl = document.getElementById("dbBookingStatus");

// Toggle file selection visibility based on booking source
function updateBookingSourceUI() {
  const isDb = bookingSourceDbEl.checked;
  fileSelectRowEl.style.display = isDb ? "none" : "flex";
  if (isDb) checkDbBookingStatus();
}
bookingSourceDbEl.addEventListener("change", updateBookingSourceUI);
bookingSourceFileEl.addEventListener("change", updateBookingSourceUI);

async function checkDbBookingStatus() {
  const pid = getProjectId();
  if (!pid) {
    dbBookingStatusEl.innerHTML = '<span style="color:#d97706;">⚠️ Chưa có project. Hãy tạo booking AI trước.</span>';
    return;
  }
  try {
    const res = await fetch(`/api/booking/latest_html?project_id=${pid}`);
    const data = await res.json();
    if (data.has_booking) {
      const hotelCount = (data.hotel_htmls || []).length;
      dbBookingStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Có booking trong DB: ${hotelCount} khách sạn + 1 vé máy bay</span>`;
    } else {
      dbBookingStatusEl.innerHTML = '<span style="color:#d97706;">⚠️ Chưa có booking trong DB. Hãy tạo booking AI trước.</span>';
    }
  } catch (e) {
    dbBookingStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Lỗi kiểm tra DB</span>';
  }
}

// Extract itinerary info from booking data
const extractItineraryBtn = document.getElementById("extractItineraryBtn");
const extractStatusEl = document.getElementById("extractStatus");

extractItineraryBtn.addEventListener("click", async () => {
  extractItineraryBtn.disabled = true;
  extractItineraryBtn.textContent = "⏳ Đang trích xuất...";
  extractStatusEl.textContent = "";

  try {
    const pid = getProjectId();
    const url = "/api/booking/trip/latest" + (pid ? `?project_id=${pid}` : "");
    const res = await fetch(url);
    const data = await res.json();
    const ti = data.trip_info || {};

    // Auto-fill form fields from trip info
    const guests = ti.guest_names || [];
    const guestStr = Array.isArray(guests) ? guests.join("\n") : String(guests);
    if (guestStr) itParticipantsEl.value = guestStr;
    if (ti.travel_start_date) itTravelStartDateEl.value = ti.travel_start_date;
    if (ti.travel_end_date) itTravelEndDateEl.value = ti.travel_end_date;
    if (ti.travel_purpose) itTravelPurposeEl.value = ti.travel_purpose;

    extractStatusEl.innerHTML = '<span style="color:#16a34a;">✅ Đã trích xuất thành công! Kiểm tra và chỉnh sửa bên dưới.</span>';
  } catch (e) {
    extractStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${e.message}</span>`;
  } finally {
    extractItineraryBtn.disabled = false;
    extractItineraryBtn.textContent = "🔍 Trích xuất thông tin lịch trình";
  }
});

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
const pdfMergeFileInput = document.getElementById("pdfMergeFileInput");
const pdfMergeFileList = document.getElementById("pdfMergeFileList");
const pdfMergeOutputName = document.getElementById("pdfMergeOutputName");
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
const btnCreateProject = document.getElementById("btnCreateProject");
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

projectSelectEl.addEventListener("change", async () => {
  const val = projectSelectEl.value;
  currentProjectId = val ? parseInt(val) : null;
  btnRenameProject.style.display = currentProjectId ? "" : "none";
  btnDeleteProject.style.display = currentProjectId ? "" : "none";
  localStorage.setItem("currentProjectId", currentProjectId || "");

  // Khi đổi hồ sơ, reload lại các dữ liệu phụ thuộc project
  try {
    await loadSteps();
    await loadLatestItinerary();
    await loadLatestBooking();
    await loadItineraryContext();
    await loadLatestTripInfo();
    await loadClassifierFiles();
    await loadSplitterFileList();
    await loadOutputHistory();
  } catch (e) {
    console.error("Failed to reload project-scoped data:", e);
  }
});

btnNewProject.addEventListener("click", async () => {
  if (!currentProjectId) {
    alert("Vui lòng chọn một hồ sơ ở dropdown. Nếu chưa có, tạo hồ sơ bằng cách thêm từ API hoặc dùng nút Đổi tên để đặt tên.");
    return;
  }
  if (!confirm("Xóa toàn bộ dữ liệu hồ sơ này (phần tách, booking, lịch trình, thư…) để làm người mới? Bạn có thể bỏ file mới vào và làm lại từ đầu.")) return;
  try {
    const res = await fetch(`/api/projects/${currentProjectId}/clear`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert("Lỗi: " + (data.error || "không xác định"));
      return;
    }
    await loadSteps();
    await loadLatestItinerary();
    await loadLatestBooking();
    await loadItineraryContext();
    await loadLatestTripInfo();
    await loadClassifierFiles();
    await loadSplitterFileList();
    await loadOutputHistory();
    if (typeof loadFilteredFiles === 'function') await loadFilteredFiles();
    alert("Đã xóa dữ liệu. Bạn có thể bỏ file mới vào và làm lại từ đầu.");
  } catch (e) {
    alert("Lỗi: " + e.message);
  }
});

btnCreateProject.addEventListener("click", async () => {
  const name = prompt("Nhập tên hồ sơ mới (VD: Dữ liệu khách hàng B):");
  if (!name || !name.trim()) return;
  try {
    const res = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    });
    const newProject = await res.json();
    if (!res.ok) {
      alert("Lỗi: " + (newProject.error || "không xác định"));
      return;
    }
    
    currentProjectId = newProject.id || newProject.project_id;
    if (!currentProjectId) {
      // In case the API returns the project id under a different key but usually it's `id`
      const listRes = await fetch("/api/projects");
      const listData = await listRes.json();
      const projects = listData.projects || [];
      if (projects.length > 0) {
        const added = projects.find(p => p.name === name.trim());
        if (added) currentProjectId = added.id;
      }
    }
    
    localStorage.setItem("currentProjectId", currentProjectId);
    
    await loadProjects();
    
    try {
      await loadSteps();
      await loadLatestItinerary();
      await loadLatestBooking();
      await loadItineraryContext();
      await loadLatestTripInfo();
      await loadClassifierFiles();
      await loadSplitterFileList();
      await loadOutputHistory();
      if (typeof loadFilteredFiles === 'function') await loadFilteredFiles();
    } catch (e) {
      console.error("Failed to reload project-scoped data:", e);
    }
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

// Đảm bảo luôn có ít nhất 1 hồ sơ (chỉ cần 1 hồ sơ, làm mới khi đổi người)
async function ensureOneProject() {
  const res = await fetch("/api/projects");
  const data = await res.json();
  const projects = data.projects || [];
  if (projects.length === 0) {
    await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Hồ sơ" }),
    });
  }
  await loadProjects();
  const list = (await fetch("/api/projects").then((r) => r.json())).projects || [];
  if (list.length > 0 && !currentProjectId) {
    currentProjectId = list[0].id;
    localStorage.setItem("currentProjectId", currentProjectId);
    projectSelectEl.value = currentProjectId;
    btnRenameProject.style.display = "";
    btnDeleteProject.style.display = "";
  }
}

// Restore project from localStorage
(async () => {
  await ensureOneProject();
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
  checkDbBookingStatus();
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
  const fileRows = files
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
  classifierFileListEl.innerHTML = `<details style="border:1px solid #e5e7eb; border-radius:8px; overflow:hidden;">
    <summary style="padding:10px 14px; background:#f0f4ff; cursor:pointer; font-weight:600; color:#1e40af; font-size:0.95em;">
      📂 ${files.length} file trong thư mục input — click để xem
    </summary>
    <div style="max-height:300px; overflow-y:auto;">${fileRows}</div>
  </details>`;
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

// ==================== MANUAL PDF SPLIT (Tab ②) ====================

// State for manual split
let manualSplitState = {
  source: "upload",       // "upload" or "ai"
  pageCount: 0,
  tempId: null,            // for uploaded files
  tempPath: null,
  uploadFilename: null,
  aiFileId: null,          // for AI splitter files
  aiFilename: null,
  lastManualId: null,      // last manual split result ID
};

// Toggle source panels
document.querySelectorAll('input[name="manualSplitSource"]').forEach((radio) => {
  radio.addEventListener("change", (e) => {
    manualSplitState.source = e.target.value;
    const uploadPanel = document.getElementById("manualSplitUploadPanel");
    const aiPanel = document.getElementById("manualSplitAIPanel");
    const formArea = document.getElementById("manualSplitFormArea");
    const resultArea = document.getElementById("manualSplitResultArea");
    if (uploadPanel) uploadPanel.style.display = e.target.value === "upload" ? "block" : "none";
    if (aiPanel) aiPanel.style.display = e.target.value === "ai" ? "block" : "none";
    if (formArea) formArea.style.display = "none";
    if (resultArea) resultArea.style.display = "none";
    manualSplitState.pageCount = 0;
    if (e.target.value === "ai") loadManualSplitAIFiles();
  });
});

// Load AI splitter output files into searchable grouped list
let _aiFileGroups = []; // cache for search filtering

async function loadManualSplitAIFiles() {
  const listEl = document.getElementById("manualSplitAIFileList");
  if (!listEl) return;
  listEl.innerHTML = '<div style="padding:12px; color:#888;">Đang tải...</div>';
  try {
    const res = await fetch("/api/ai-splitter/list-outputs");
    const data = await res.json();
    _aiFileGroups = data.groups || [];
    renderAIFileList("");
  } catch (e) {
    listEl.innerHTML = `<div style="padding:12px; color:red;">Lỗi: ${e.message}</div>`;
  }
}

function renderAIFileList(query) {
  const listEl = document.getElementById("manualSplitAIFileList");
  if (!listEl) return;
  const q = (query || "").toLowerCase().trim();

  if (_aiFileGroups.length === 0) {
    listEl.innerHTML = '<div style="padding:12px; color:#888;">Chưa có file đã tách.</div>';
    return;
  }

  let html = '';
  let matchCount = 0;
  for (const group of _aiFileGroups) {
    const sourceLabel = group.source_filename || group.folder_id;
    const typeIcon = group.source_type === "ai" ? "🤖" : "✂️";
    const typeBg = group.source_type === "ai" ? "#e0e7ff" : "#fef3c7";

    const filteredFiles = group.files.filter(f => {
      if (!q) return true;
      return f.filename.toLowerCase().includes(q) || sourceLabel.toLowerCase().includes(q);
    });

    if (filteredFiles.length === 0) continue;
    matchCount += filteredFiles.length;

    // Auto-open if searching, collapsed if not
    const openAttr = q ? "open" : "";
    html += `<details ${openAttr} style="border-bottom:1px solid #e5e7eb;">
      <summary style="padding:8px 10px; background:${typeBg}; cursor:pointer; font-size:0.85em; font-weight:600; user-select:none;">
        ${typeIcon} ${sourceLabel} (${filteredFiles.length} file)
      </summary>`;
    for (const f of filteredFiles) {
      const sizeMB = (f.size / 1024 / 1024).toFixed(1);
      html += `<div class="ai-file-pick-row" data-file-id="${f.file_id}" data-filename="${f.filename}"
        style="padding:8px 12px; padding-left:24px; border-bottom:1px solid #f0f0f0; cursor:pointer; display:flex; justify-content:space-between; align-items:center; transition:background 0.15s;"
        onmouseover="this.style.background='#e0e7ff'" onmouseout="this.style.background='transparent'">
        <div>
          <span style="font-size:0.9em;">${f.filename}</span>
          <small style="color:#888; margin-left:4px;">(${sizeMB} MB)</small>
        </div>
        <span style="font-size:0.8em; color:#4f46e5;">📄 Chọn</span>
      </div>`;
    }
    html += `</details>`;
  }

  if (matchCount === 0) {
    html = `<div style="padding:12px; color:#888;">Không tìm thấy file khớp "${query}"</div>`;
  }

  listEl.innerHTML = html;
}

// Search filter
const manualSplitAISearchEl = document.getElementById("manualSplitAISearch");
if (manualSplitAISearchEl) {
  manualSplitAISearchEl.addEventListener("input", (e) => {
    renderAIFileList(e.target.value);
  });
}

// Click to select file from list
document.addEventListener("click", async (e) => {
  const row = e.target.closest(".ai-file-pick-row");
  if (!row) return;
  const fileId = row.dataset.fileId;
  const filename = row.dataset.filename;
  if (!fileId || !filename) return;

  const infoEl = document.getElementById("manualSplitAIInfo");
  const formArea = document.getElementById("manualSplitFormArea");
  const resultArea = document.getElementById("manualSplitResultArea");
  if (infoEl) infoEl.textContent = `⏳ Đang đọc ${filename}...`;
  if (resultArea) resultArea.style.display = "none";

  // Highlight selected row
  document.querySelectorAll(".ai-file-pick-row").forEach(r => r.style.background = "transparent");
  row.style.background = "#c7d2fe";

  try {
    const res = await fetch("/api/manual-split/get-page-count", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_id: fileId, filename }),
    });
    const data = await res.json();
    if (!res.ok) { if (infoEl) infoEl.textContent = `Lỗi: ${data.error}`; return; }
    manualSplitState.pageCount = data.page_count;
    manualSplitState.aiFileId = fileId;
    manualSplitState.aiFilename = filename;
    manualSplitState.tempId = null;
    manualSplitState.tempPath = null;
    manualSplitState.uploadFilename = null;
    if (infoEl) infoEl.innerHTML = `<div style="font-size:1.1em; font-weight:700; color:#1e40af; padding:8px 0;">✅ ${filename} — ${data.page_count} trang</div>`;
    if (data.page_count <= 1) {
      if (infoEl) infoEl.innerHTML += `<div style="color:#dc2626; font-weight:600;">⚠️ File chỉ có 1 trang, không cần tách.</div>`;
      if (formArea) formArea.style.display = "none";
      return;
    }
    const maxSplits = data.page_count;
    const pageInfoEl = document.getElementById("pdfManualPageInfo");
    if (pageInfoEl) pageInfoEl.textContent = `File có ${data.page_count} trang. Tách tối đa ${maxSplits} file.`;
    if (pdfManualCountEl) { pdfManualCountEl.max = maxSplits; pdfManualCountEl.value = Math.min(parseInt(pdfManualCountEl.value)||1, maxSplits); }
    if (formArea) formArea.style.display = "block";
  } catch (err) {
    if (infoEl) infoEl.textContent = `Lỗi: ${err.message}`;
  }
});

// Upload file from computer and get page count
const manualSplitUploadBtn = document.getElementById("manualSplitUploadBtn");
if (manualSplitUploadBtn) {
  manualSplitUploadBtn.addEventListener("click", async () => {
    const fileInput = document.getElementById("manualSplitFileInput");
    const infoEl = document.getElementById("manualSplitUploadInfo");
    const formArea = document.getElementById("manualSplitFormArea");
    const resultArea = document.getElementById("manualSplitResultArea");
    if (!fileInput || !fileInput.files || !fileInput.files.length) {
      alert("Vui lòng chọn file PDF."); return;
    }
    manualSplitUploadBtn.disabled = true;
    manualSplitUploadBtn.textContent = "⏳ Đang đọc...";
    if (infoEl) infoEl.textContent = "Đang upload...";
    if (resultArea) resultArea.style.display = "none";
    try {
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      const res = await fetch("/api/manual-split/upload-get-page-count", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error}`); return; }
      manualSplitState.pageCount = data.page_count;
      manualSplitState.tempId = data.temp_id;
      manualSplitState.tempPath = data.temp_path;
      manualSplitState.uploadFilename = data.filename;
      manualSplitState.aiFileId = null;
      manualSplitState.aiFilename = null;
      if (infoEl) infoEl.innerHTML = `<div style="font-size:1.1em; font-weight:700; color:#1e40af; padding:8px 0;">✅ ${data.filename} — ${data.page_count} trang</div>`;
      if (data.page_count <= 1) {
        if (infoEl) infoEl.innerHTML += `<div style="color:#dc2626; font-weight:600;">⚠️ File chỉ có 1 trang, không cần tách.</div>`;
        if (formArea) formArea.style.display = "none";
        return;
      }
      const maxSplits = data.page_count;
      const pageInfoEl = document.getElementById("pdfManualPageInfo");
      if (pageInfoEl) pageInfoEl.textContent = `File có ${data.page_count} trang. Tách tối đa ${maxSplits} file.`;
      if (pdfManualCountEl) { pdfManualCountEl.max = maxSplits; pdfManualCountEl.value = Math.min(parseInt(pdfManualCountEl.value)||1, maxSplits); }
      if (formArea) formArea.style.display = "block";
    } catch (e) {
      if (infoEl) infoEl.textContent = `Lỗi: ${e.message}`;
    } finally {
      manualSplitUploadBtn.disabled = false;
      manualSplitUploadBtn.textContent = "📄 Đọc file";
    }
  });
}

function buildPdfManualSegments() {
  if (!pdfManualCountEl || !pdfManualSegmentsEl) return;
  const count = parseInt(pdfManualCountEl.value || "0", 10) || 0;
  const maxAllowed = Math.max(1, manualSplitState.pageCount || 20);
  const safeCount = Math.max(1, Math.min(count, maxAllowed));
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
            <input id="pdf-segmentStart-${i}" type="number" min="1" max="${manualSplitState.pageCount}" />
          </div>
          <div>
            <label for="pdf-segmentEnd-${i}">Đến trang</label>
            <input id="pdf-segmentEnd-${i}" type="number" min="1" max="${manualSplitState.pageCount}" />
          </div>
        </div>
      </div>
    `);
  }
  pdfManualSegmentsEl.innerHTML = parts.join("");
}

async function runPdfManualSplit() {
  const count = parseInt(pdfManualCountEl.value || "0", 10) || 0;
  const segments = [];
  for (let i = 1; i <= count; i++) {
    const nameEl = document.getElementById(`pdf-segmentName-${i}`);
    const startEl = document.getElementById(`pdf-segmentStart-${i}`);
    const endEl = document.getElementById(`pdf-segmentEnd-${i}`);
    if (!nameEl || !startEl || !endEl) continue;
    const output_name = nameEl.value.trim();
    const start_page = parseInt(startEl.value || "0", 10);
    const end_page = parseInt(endEl.value || "0", 10) || manualSplitState.pageCount;
    if (!output_name || !start_page) continue;
    segments.push({ output_name, start_page, end_page });
  }
  if (!segments.length) {
    alert("Vui lòng nhập đầy đủ tên file và khoảng trang cho ít nhất 1 file con.");
    return;
  }

  const originalText = pdfRunSplitBtn.textContent;
  pdfRunSplitBtn.disabled = true;
  pdfRunSplitBtn.textContent = "⏳ Đang tách...";
  const resultArea = document.getElementById("manualSplitResultArea");
  const resultList = document.getElementById("manualSplitResultList");
  if (resultArea) resultArea.style.display = "none";

  try {
    let data;
    if (manualSplitState.source === "upload" && manualSplitState.tempPath) {
      // Upload source — use upload-and-split endpoint
      const fileInput = document.getElementById("manualSplitFileInput");
      if (!fileInput || !fileInput.files || !fileInput.files.length) {
        alert("File upload không còn, vui lòng chọn lại."); return;
      }
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      formData.append("segments", JSON.stringify(segments));
      const pid = getProjectId();
      if (pid) formData.append("project_id", String(pid));
      const res = await fetch("/api/manual-split/upload-and-split", { method: "POST", body: formData });
      data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error || "không xác định"}`); return; }
    } else if (manualSplitState.source === "ai" && manualSplitState.aiFileId) {
      // AI source — use existing split_manual endpoint
      const res = await fetch("/api/classifier/split_manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_file_id: manualSplitState.aiFileId,
          source_filename: manualSplitState.aiFilename,
          segments,
          project_id: getProjectId() || null,
        }),
      });
      data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error || "không xác định"}`); return; }
    } else {
      alert("Vui lòng chọn file nguồn trước."); return;
    }

    // Display results
    manualSplitState.lastManualId = data.manual_id;
    if (resultArea) resultArea.style.display = "block";
    if (resultList) {
      let html = `<div style="padding:8px 12px; background:#f0f4ff; border-radius:6px; margin-bottom:8px;">
        <strong>📁 ${data.source}</strong> → ${data.segments?.length || 0} file (${data.total_pages} trang)
        ${data.removed_original ? `<br><small style="color:#dc2626;">🗑️ Đã xóa file gốc: ${data.removed_original}</small>` : ""}
      </div>`;
      for (const seg of (data.segments || [])) {
        html += `<div style="padding:6px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center; padding-left:24px;">
          <div>
            <strong>${seg.output_name}.pdf</strong>
            <br><small style="color:#666;">Trang ${seg.start_page}-${seg.end_page}</small>
          </div>
          <div style="display:flex; gap:6px;">
            <a href="/api/ai-splitter/view/${data.manual_id}/${encodeURIComponent(seg.to)}" target="_blank"
               style="text-decoration:none; padding:4px 10px; background:#f59e0b; color:white; border-radius:4px; font-size:0.85em;">
              👁 Xem
            </a>
            <a href="/api/ai-splitter/download/${data.manual_id}/${encodeURIComponent(seg.to)}"
               style="text-decoration:none; padding:4px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.85em;">
              ⬇ Download
            </a>
          </div>
        </div>`;
      }
      resultList.innerHTML = html;
    }

    // Clear form
    if (pdfManualSegmentsEl) pdfManualSegmentsEl.innerHTML = "";
    if (pdfManualCountEl) pdfManualCountEl.value = "1";
  } catch (error) {
    alert(`Lỗi: ${error.message}`);
  } finally {
    pdfRunSplitBtn.disabled = false;
    pdfRunSplitBtn.textContent = originalText;
  }
}

// Download button for manual split results
const manualSplitDownloadBtn = document.getElementById("manualSplitDownloadBtn");
if (manualSplitDownloadBtn) {
  manualSplitDownloadBtn.addEventListener("click", () => {
    if (!manualSplitState.lastManualId) { alert("Chưa có kết quả tách."); return; }
    // Download all files individually (no ZIP for manual splits)
    const links = document.querySelectorAll("#manualSplitResultList a[href*='/download/']");
    links.forEach((a) => { const w = window.open(a.href, "_blank"); if (w) w.focus(); });
  });
}

// Send manual split results to classifier
const manualSplitToClassifierBtn = document.getElementById("manualSplitToClassifierBtn");
if (manualSplitToClassifierBtn) {
  manualSplitToClassifierBtn.addEventListener("click", async () => {
    if (!manualSplitState.lastManualId) { alert("Chưa có kết quả tách."); return; }
    manualSplitToClassifierBtn.disabled = true;
    manualSplitToClassifierBtn.textContent = "⏳ Đang chuyển...";
    try {
      const res = await fetch("/api/manual-split/send-to-classifier", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ manual_id: manualSplitState.lastManualId }),
      });
      const data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error}`); return; }
      alert(`✅ Đã chuyển ${data.count} file sang ${data.target_dir}`);
      setActiveTab("classifier");
      loadClassifierFiles();
    } catch (e) { alert(`Lỗi: ${e.message}`); }
    finally {
      manualSplitToClassifierBtn.disabled = false;
      manualSplitToClassifierBtn.textContent = "➡️ Chuyển sang Phân loại";
    }
  });
}

function updatePdfMergeFileListDisplay() {
  if (!pdfMergeFileList || !pdfMergeFileInput) return;
  const files = Array.from(pdfMergeFileInput.files || []);
  if (files.length === 0) {
    pdfMergeFileList.textContent = "Chưa chọn file. Thứ tự hiển thị = thứ tự trang.";
    pdfMergeFileList.className = "hint";
    return;
  }
  pdfMergeFileList.className = "";
  pdfMergeFileList.innerHTML = files.map((f, i) => `${i + 1}. ${f.name}`).join("<br>");
}

if (pdfMergeFileInput) {
  pdfMergeFileInput.addEventListener("change", updatePdfMergeFileListDisplay);
}

async function runPdfMerge() {
  if (!pdfMergeFileInput) {
    alert("Không tìm thấy ô chọn file.");
    return;
  }
  const files = Array.from(pdfMergeFileInput.files || []).filter((f) => f.name && f.name.toLowerCase().endsWith(".pdf"));
  if (files.length === 0) {
    alert("Vui lòng chọn ít nhất 1 file PDF từ máy tính (thứ tự chọn = thứ tự trang).");
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

  if (!useDb) {
    const flightFile = flightFileEl.value;
    const hotelFile = hotelFileEl.value;
    if (!flightFile || !hotelFile) {
      itineraryResultEl.srcdoc =
        "<p>Vui lòng chọn đủ file vé máy bay và khách sạn.</p>";
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
      payload.flight_file = flightFileEl.value;
      payload.hotel_file = hotelFileEl.value;
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
    loadFilteredFiles();
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

async function loadFilteredFiles() {
  const inputDir = inputDirEl.value.trim() || "input";
  const tableEl = document.getElementById("filteredFilesTable");
  const statusEl = document.getElementById("filteredFilesStatus");
  if (!tableEl) return;

  tableEl.innerHTML = "";
  if (statusEl) statusEl.textContent = "";

  try {
    const pid = getProjectId();
    const res = await fetch(`/api/booking/filtered-files?input_dir=${encodeURIComponent(inputDir)}${pid ? `&project_id=${pid}` : ''}`);
    const data = await res.json();

    if (!data.matched || data.matched.length === 0) {
      tableEl.innerHTML = `<div style="padding:10px; background:#fef2f2; border-radius:6px; color:#991b1b; font-size:0.85em;">
        ⚠️ Chưa có file nào khớp tiền tố trong <b>${inputDir}</b>.
        Hãy chạy phân loại → lưu → chuyển file trước.
      </div>`;
      if (statusEl) statusEl.textContent = `(0/${data.total || 0} file)`;
      return;
    }

    if (statusEl) statusEl.textContent = `(${data.matched.length}/${data.total} file)`;

    const rows = data.matched.map((f, i) =>
      `<div style="display:flex; align-items:center; gap:8px; padding:4px 10px; font-size:0.85em; ${i % 2 === 0 ? 'background:rgba(99,102,241,0.05);' : ''}">
        <span style="padding:1px 6px; background:#e0e7ff; color:#4338ca; border-radius:10px; font-size:0.8em; white-space:nowrap;">${f.label}</span>
        <span style="color:#374151; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${f.filename}">📄 ${f.filename}</span>
      </div>`
    ).join("");

    let html = `<div style="border:1px solid #e5e7eb; border-radius:6px; overflow:hidden; max-height:220px; overflow-y:auto;">
      ${rows}
    </div>`;

    if (data.other && data.other.length > 0) {
      html += `<details style="margin-top:6px;">
        <summary style="cursor:pointer; font-size:0.8em; color:#9ca3af;">📁 ${data.other.length} file khác (bỏ qua)</summary>
        <div style="padding:4px 10px; font-size:0.8em; color:#9ca3af; max-height:120px; overflow-y:auto;">
          ${data.other.map(f => `<div style="padding:1px 0;">• ${f.filename}</div>`).join("")}
        </div>
      </details>`;
    }

    tableEl.innerHTML = html;
  } catch (e) {
    tableEl.innerHTML = `<div style="color:#dc2626; font-size:0.85em;">❌ Lỗi: ${e.message}</div>`;
  }
}

async function extractTripInfo() {
  const inputDir = inputDirEl.value.trim() || "input";
  const originalBtnText = extractTripBtn.textContent;
  extractTripBtn.textContent = "⏳ Đang trích xuất...";
  extractTripBtn.disabled = true;

  // Step 1: Show which files will be read
  let fileListHtml = "";
  let matchedCount = 0;
  try {
    const fRes = await fetch(`/api/booking/filtered-files?input_dir=${encodeURIComponent(inputDir)}`);
    const fData = await fRes.json();
    matchedCount = fData.matched?.length || 0;
    if (fData.matched && fData.matched.length > 0) {
      fileListHtml = fData.matched.map((f, i) =>
        `<div style="padding:3px 0; display:flex; align-items:center; gap:6px;">
          <span class="extract-spinner" style="display:inline-block; width:12px; height:12px; border:2px solid #3b82f6; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></span>
          <span style="color:#1e293b; font-size:0.85em;">📄 ${f.filename}</span>
        </div>`
      ).join("");
    }
  } catch(e) {}

  tripInfoPanelEl.innerHTML = `
    <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
    <div style="padding:16px; background:#f0f9ff; border:1px solid #bae6fd; border-radius:8px;">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
        <div style="width:18px; height:18px; border:3px solid #3b82f6; border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></div>
        <span style="font-weight:600; color:#1e40af; font-size:1em;">Đang trích xuất thông tin chuyến đi...</span>
      </div>
      <div class="extract-steps" style="display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap;">
        <span style="padding:3px 10px; background:#dcfce7; color:#166534; border-radius:14px; font-size:0.8em; border:1px solid #86efac;">① Quét file ✅</span>
        <span style="padding:3px 10px; background:#3b82f6; color:#fff; border-radius:14px; font-size:0.8em; font-weight:600;">② Đọc nội dung...</span>
        <span style="padding:3px 10px; background:#e2e8f0; color:#94a3b8; border-radius:14px; font-size:0.8em;">③ AI phân tích</span>
      </div>
      ${fileListHtml ? `<div style="background:#fff; border-radius:6px; padding:8px 12px; border:1px solid #e2e8f0; max-height:200px; overflow-y:auto;">
        <div style="font-size:0.75em; color:#64748b; margin-bottom:4px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">📂 Đang đọc ${matchedCount} file</div>
        ${fileListHtml}
      </div>` : ""}
      <div style="margin-top:8px; font-size:0.78em; color:#94a3b8;">⏱️ Có thể mất 30s – 2 phút tùy số file</div>
    </div>`;

  // Step 2: update to AI phase after a delay
  const phaseTimer = setTimeout(() => {
    const steps = tripInfoPanelEl.querySelectorAll(".extract-steps > span");
    if (steps.length >= 3) {
      steps[1].style.background = "#dcfce7"; steps[1].style.color = "#166534"; steps[1].style.border = "1px solid #86efac"; steps[1].style.fontWeight = "normal"; steps[1].textContent = "② Đọc nội dung ✅";
      steps[2].style.background = "#3b82f6"; steps[2].style.color = "#fff"; steps[2].style.fontWeight = "600"; steps[2].textContent = "③ AI đang phân tích...";
    }
    // Stop file spinners
    tripInfoPanelEl.querySelectorAll(".extract-spinner").forEach(s => {
      s.style.animation = "none"; s.style.border = "none"; s.innerHTML = "✅"; s.style.fontSize = "12px";
    });
  }, 5000);

  try {
    const res = await fetch("/api/booking/extract_trip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir, project_id: getProjectId() }),
    });

    clearTimeout(phaseTimer);
    const data = await res.json();

    if (!res.ok) {
      tripInfoPanelEl.innerHTML = `<div style="padding:12px; color:#dc2626;">❌ Lỗi: ${data.error || "Không thể trích xuất"}</div>`;
      return;
    }

    setTripInfoForm(data.trip_info);
    tripInfoPanelEl.innerHTML = `<div style="padding:12px; color:#34d399; font-weight:600;">
      ✅ Trích xuất thành công! Kiểm tra và bổ sung thông tin bên dưới → 💾 Lưu.
    </div>`;
  } catch (error) {
    clearTimeout(phaseTimer);
    tripInfoPanelEl.innerHTML = `<div style="padding:12px; color:#dc2626;">❌ Lỗi: ${error.message}</div>`;
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

  // Build step-by-step progress UI
  const stepLabels = {
    1: "Trích xuất thông tin chuyến đi",
    2: "AI chọn khách sạn & chuyến bay",
    3: "Tạo file HTML booking",
  };
  aiBookingStatusEl.innerHTML = `
    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin:8px 0;">
      <div style="font-weight:600; margin-bottom:12px; color:#334155;">📋 Tiến trình tạo booking</div>
      ${Object.entries(stepLabels).map(([k, v]) => `
        <div id="ai-step-${k}" style="display:flex; align-items:center; gap:8px; padding:6px 8px; margin:4px 0; border-radius:6px; background:#fff; border:1px solid #e2e8f0; transition:all 0.3s;">
          <span id="ai-step-icon-${k}" style="font-size:16px;">⬜</span>
          <span style="color:#475569; font-size:0.9em;">${v}</span>
          <span id="ai-step-msg-${k}" style="margin-left:auto; font-size:0.8em; color:#94a3b8;"></span>
        </div>
      `).join("")}
    </div>`;

  hotelBookingResultEl.srcdoc = "<p style='color:#94a3b8;padding:20px;'>⏳ Đang tạo booking...</p>";
  flightBookingResultEl.srcdoc = "<p style='color:#94a3b8;padding:20px;'>⏳ Đang tạo booking...</p>";
  aiReasoningSectionEl.style.display = "none";

  function updateStep(step, msg, done) {
    const iconEl = document.getElementById(`ai-step-icon-${step}`);
    const msgEl = document.getElementById(`ai-step-msg-${step}`);
    const rowEl = document.getElementById(`ai-step-${step}`);
    if (!iconEl) return;
    if (msg.startsWith("✅")) {
      iconEl.textContent = "✅";
      if (rowEl) { rowEl.style.background = "#f0fdf4"; rowEl.style.borderColor = "#86efac"; }
      if (msgEl) { msgEl.textContent = "Xong"; msgEl.style.color = "#16a34a"; }
    } else if (msg.startsWith("⏳")) {
      iconEl.innerHTML = '<span style="display:inline-block;animation:spin 1s linear infinite;">⏳</span>';
      if (rowEl) { rowEl.style.background = "#fffbeb"; rowEl.style.borderColor = "#fcd34d"; }
      if (msgEl) { msgEl.textContent = "Đang xử lý..."; msgEl.style.color = "#d97706"; }
    } else if (msg.startsWith("❌")) {
      iconEl.textContent = "❌";
      if (rowEl) { rowEl.style.background = "#fef2f2"; rowEl.style.borderColor = "#fca5a5"; }
      if (msgEl) { msgEl.textContent = msg; msgEl.style.color = "#dc2626"; }
    }
  }

  try {
    const res = await fetch("/api/booking/ai_generate_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_dir: inputDir,
        output_dir: outputDir,
        trip_info: editedTripInfo,
        project_id: getProjectId(),
      }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line in buffer

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          const step = evt.step;
          const msg = evt.msg;

          if (step === -1) {
            // Error
            aiBookingStatusEl.innerHTML += `<div style="color:#dc2626; margin-top:8px;">${msg}</div>`;
            return;
          }

          updateStep(step, msg);

          if (step === 4 && evt.data) {
            finalData = evt.data;
          }
        } catch (e) { /* skip parse errors */ }
      }
    }

    if (!finalData) {
      aiBookingStatusEl.innerHTML += '<div style="color:#dc2626; margin-top:8px;">❌ Không nhận được kết quả từ server</div>';
      return;
    }

    const data = finalData;

    // Update trip info panel
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

    aiBookingStatusEl.innerHTML += `<div style="color:#16a34a; font-weight:600; margin-top:8px;">
      ${data.used_cache
        ? "✅ Hoàn thành! (dùng cache - không tốn token)"
        : "✅ Hoàn thành! AI đã tạo booking thành công."}
    </div>`;
    // Refresh DB booking status for itinerary section
    checkDbBookingStatus();
  } catch (error) {
    aiBookingStatusEl.innerHTML += `<div style="color:#dc2626; margin-top:8px;">❌ Lỗi: ${error.message}</div>`;
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
    const pid = getProjectId();
    const res = await fetch("/api/pipeline/send-to-splitter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_paths: multiFiles, project_id: pid || null }),
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
  await loadOutputHistory();
});

// ==================== AI PDF SPLITTER ====================

// Load file list from splitter_uploads
async function loadSplitterFileList() {
  const listEl = document.getElementById("splitterFileList");
  if (!listEl) return;
  try {
    const pid = getProjectId();
    const url = "/api/ai-splitter/list" + (pid ? "?project_id=" + pid : "");
    const res = await fetch(url);
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
      const displayName = f.display_name || f.filename;
      return `<div class="file-row" style="align-items:center;">
        <div style="flex:1;">
          <span class="file-name">📄 ${displayName}</span>
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
    const res = await fetch("/api/ai-splitter/delete-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: getProjectId() || null }),
    });
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
        body: JSON.stringify({ filename: fname, project_id: getProjectId() || null }),
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
              // Cập nhật ngay phần "Tất cả file đã tách" sau mỗi file tách xong
              await loadOutputHistory();
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
          <div style="display:flex; gap:6px;">
            <a href="/api/ai-splitter/view/${group.file_id}/${encodeURIComponent(f.filename)}" target="_blank"
               style="text-decoration:none; padding:4px 10px; background:#f59e0b; color:white; border-radius:4px; font-size:0.8em;">
              👁 Xem
            </a>
            <a href="/api/ai-splitter/download/${group.file_id}/${encodeURIComponent(f.filename)}"
               style="text-decoration:none; padding:4px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.8em;">
              ⬇
            </a>
          </div>
        </div>`;
      }
    }
    resultsDiv.innerHTML = html;
  }

  if (splitAllBtn) { splitAllBtn.disabled = false; splitAllBtn.textContent = "✂️ Tách tất cả"; }
  loadOutputHistory();
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
        body: JSON.stringify({ filename, project_id: getProjectId() || null }),
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
      const pid = getProjectId();
      if (pid) formData.append("project_id", String(pid));
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
        await loadOutputHistory();
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
        <div style="display:flex; gap:6px;">
          <a href="/api/ai-splitter/view/${currentFileId}/${encodeURIComponent(f.filename)}" target="_blank"
             style="text-decoration:none; padding:4px 12px; background:#f59e0b; color:white; border-radius:4px; font-size:0.85em;">
            👁 Xem
          </a>
          <a href="/api/ai-splitter/download/${currentFileId}/${encodeURIComponent(f.filename)}"
             style="text-decoration:none; padding:4px 12px; background:#4f46e5; color:white; border-radius:4px; font-size:0.85em;">
            ⬇ Download
          </a>
        </div>
      </div>`;
    }).join("");
  }

  downloadAllBtn.addEventListener("click", () => {
    if (!currentFileId) return;
    window.location.href = `/api/ai-splitter/download-zip/${currentFileId}`;
  });
})();

// ==================== OUTPUT HISTORY (persistent across F5) ====================

async function loadOutputHistory() {
  const listEl = document.getElementById("splitterOutputHistoryList");
  if (!listEl) return;
  try {
    const pid = getProjectId();
    const url = "/api/ai-splitter/list-outputs" + (pid ? "?project_id=" + pid : "");
    const res = await fetch(url);
    const data = await res.json();
    const groups = data.groups || [];
    if (groups.length === 0) {
      listEl.innerHTML = '<div class="hint">Chưa có file nào đã tách. Hãy tách file ở Tab ① hoặc Tab ②.</div>';
      return;
    }
    let html = '';
    let totalFiles = 0;
    // Merge toolbar
    html += `<div id="mergeToolbar" style="display:none; padding:10px 12px; background:#fef3c7; border:2px solid #f59e0b; border-radius:8px; margin-bottom:10px; position:sticky; top:0; z-index:10;">
      <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
        <span id="mergeCount" style="font-weight:600;">0 file đã chọn</span>
        <input type="text" id="mergeOutputName" placeholder="Tên file sau khi gộp (mặc định = file đầu tiên)" style="flex:1; min-width:200px; padding:6px 10px; border:1px solid #d1d5db; border-radius:4px;" />
        <button id="mergeSelectedBtn" style="padding:8px 16px; background:#4f46e5; color:#fff; border:none; border-radius:6px; cursor:pointer; font-weight:600;">📎 Gộp file</button>
        <button id="clearMergeBtn" style="padding:8px 12px; background:#6b7280; color:#fff; border:none; border-radius:6px; cursor:pointer;">✕ Bỏ chọn</button>
      </div>
    </div>`;

    for (const group of groups) {
      const sourceLabel = group.source_filename || group.folder_id;
      const typeLabel = group.source_type === 'ai'
        ? `🤖 AI: ${sourceLabel}`
        : `✂️ Thủ công: ${sourceLabel}`;
      const typeBg = group.source_type === 'ai' ? '#e0e7ff' : '#fef3c7';
      html += `<div style="padding:8px 12px; background:${typeBg}; border-radius:6px; margin-bottom:4px;">
        <strong>${typeLabel}</strong> — ${group.files.length} file
      </div>`;
      for (const f of group.files) {
        const sizeMB = (f.size / 1024 / 1024).toFixed(1);
        totalFiles++;
        html += `<div style="padding:6px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center; padding-left:12px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <input type="checkbox" class="merge-check" data-file-id="${f.file_id}" data-filename="${f.filename}" style="width:18px; height:18px; cursor:pointer;" />
            <span class="merge-order-badge" style="display:none; width:20px; height:20px; background:#4f46e5; color:white; border-radius:50%; font-size:0.7em; font-weight:700; align-items:center; justify-content:center;"></span>
            <div>
              <strong>${f.filename}</strong>
              <small style="color:#888; margin-left:6px;">(${sizeMB} MB)</small>
            </div>
          </div>
          <div style="display:flex; gap:6px;">
            <a href="/api/ai-splitter/view/${f.file_id}/${encodeURIComponent(f.filename)}" target="_blank"
               style="text-decoration:none; padding:4px 10px; background:#f59e0b; color:white; border-radius:4px; font-size:0.8em;">
              👁 Xem
            </a>
            <a href="/api/ai-splitter/download/${f.file_id}/${encodeURIComponent(f.filename)}"
               style="text-decoration:none; padding:4px 10px; background:#4f46e5; color:white; border-radius:4px; font-size:0.8em;">
              ⬇
            </a>
          </div>
        </div>`;
      }
    }
    listEl.innerHTML = `<div class="hint" style="margin-bottom:8px;">Tổng: ${totalFiles} file trong ${groups.length} nhóm · ☑️ Tick chọn file cần gộp</div>` + html;

    // Wire up merge checkbox events
    setupMergeCheckboxes();
  } catch (e) {
    listEl.innerHTML = `Lỗi: ${e.message}`;
  }
}

function setupMergeCheckboxes() {
  const toolbar = document.getElementById("mergeToolbar");
  const countEl = document.getElementById("mergeCount");
  const nameInput = document.getElementById("mergeOutputName");
  if (!toolbar) return;

  // Track click order (not DOM order)
  let mergeOrder = [];

  function updateToolbar() {
    if (mergeOrder.length >= 2) {
      toolbar.style.display = "block";
      countEl.textContent = `${mergeOrder.length} file đã chọn`;
      // Default name = first clicked file's name (without .pdf)
      if (!nameInput.dataset.userEdited) {
        nameInput.value = (mergeOrder[0]?.filename || "").replace(/\.pdf$/i, "");
      }
    } else {
      toolbar.style.display = "none";
    }
    // Show order badges
    document.querySelectorAll(".merge-check").forEach(cb => {
      const badge = cb.parentElement.querySelector(".merge-order-badge");
      const idx = mergeOrder.findIndex(m => m.fileId === cb.dataset.fileId && m.filename === cb.dataset.filename);
      if (badge) {
        if (idx >= 0) {
          badge.textContent = idx + 1;
          badge.style.display = "inline-flex";
        } else {
          badge.style.display = "none";
        }
      }
    });
  }

  document.querySelectorAll(".merge-check").forEach(cb => {
    cb.addEventListener("change", () => {
      const entry = { fileId: cb.dataset.fileId, filename: cb.dataset.filename };
      if (cb.checked) {
        mergeOrder.push(entry);
      } else {
        mergeOrder = mergeOrder.filter(m => !(m.fileId === entry.fileId && m.filename === entry.filename));
        // Reset name default when unchecking
        if (mergeOrder.length > 0 && !nameInput.dataset.userEdited) {
          nameInput.value = (mergeOrder[0]?.filename || "").replace(/\.pdf$/i, "");
        }
      }
      updateToolbar();
    });
  });

  // Track manual name edits
  if (nameInput) {
    nameInput.addEventListener("input", () => { nameInput.dataset.userEdited = "true"; });
  }

  // Clear selection
  const clearBtn = document.getElementById("clearMergeBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      document.querySelectorAll(".merge-check:checked").forEach(cb => { cb.checked = false; });
      mergeOrder = [];
      toolbar.style.display = "none";
      if (nameInput) { nameInput.value = ""; delete nameInput.dataset.userEdited; }
      updateToolbar();
    });
  }

  // Merge button — uses mergeOrder (click order)
  const mergeBtn = document.getElementById("mergeSelectedBtn");
  if (mergeBtn) {
    mergeBtn.addEventListener("click", async () => {
      if (mergeOrder.length < 2) { alert("Chọn ít nhất 2 file để gộp."); return; }
      const files = mergeOrder.map(m => ({ file_id: m.fileId, filename: m.filename }));
      const outputName = (nameInput?.value || "").trim() || mergeOrder[0]?.filename?.replace(/\.pdf$/i, "") || "Merged";

      const fileList = mergeOrder.map((m, i) => `  ${i+1}. ${m.filename}`).join("\n");
      if (!confirm(`Gộp ${mergeOrder.length} file theo thứ tự:\n${fileList}\n\nTên file output: ${outputName}.pdf\n\nBấm OK để xác nhận.`)) return;

      mergeBtn.disabled = true;
      mergeBtn.textContent = "⏳ Đang gộp...";
      try {
        const res = await fetch("/api/ai-splitter/merge-outputs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ files, output_name: outputName }),
        });
        const result = await res.json();
        if (!res.ok) { alert(`Lỗi: ${result.error}`); return; }
        alert(`✅ Đã gộp ${mergeOrder.length} file → ${result.merged_file} (${result.total_pages} trang)`);
        mergeOrder = [];
        if (nameInput) { nameInput.value = ""; delete nameInput.dataset.userEdited; }
        await loadOutputHistory();
      } catch (e) { alert(`Lỗi: ${e.message}`); }
      finally {
        mergeBtn.disabled = false;
        mergeBtn.textContent = "📎 Gộp file";
      }
    });
  }
}

// Refresh output history
const refreshOutputHistoryBtn = document.getElementById("refreshOutputHistoryBtn");
if (refreshOutputHistoryBtn) {
  refreshOutputHistoryBtn.addEventListener("click", loadOutputHistory);
}

// Clear all outputs
const clearAllOutputsBtn = document.getElementById("clearAllOutputsBtn");
if (clearAllOutputsBtn) {
  clearAllOutputsBtn.addEventListener("click", async () => {
    if (!confirm("Xóa TẤT CẢ kết quả đã tách (AI + thủ công)?\nHành động này không thể hoàn tác!")) return;
    clearAllOutputsBtn.disabled = true;
    clearAllOutputsBtn.textContent = "⏳ Đang xóa...";
    try {
      const res = await fetch("/api/ai-splitter/clear-outputs", { method: "POST" });
      const data = await res.json();
      alert(`✅ Đã xóa ${data.deleted_count} mục.`);
      await loadOutputHistory();
      // Also hide the current results card
      const resultsCard = document.getElementById("splitterResultsCard");
      if (resultsCard) resultsCard.style.display = "none";
    } catch (e) { alert(`Lỗi: ${e.message}`); }
    finally {
      clearAllOutputsBtn.disabled = false;
      clearAllOutputsBtn.textContent = "🗑️ Xóa tất cả kết quả";
    }
  });
}

// Send all outputs to classifier
const sendAllToClassifierBtn = document.getElementById("sendAllToClassifierBtn");
if (sendAllToClassifierBtn) {
  sendAllToClassifierBtn.addEventListener("click", async () => {
    sendAllToClassifierBtn.disabled = true;
    sendAllToClassifierBtn.textContent = "⏳ Đang chuyển...";
    try {
      const res = await fetch("/api/pipeline/send-to-classifier", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (!res.ok) { alert(`Lỗi: ${data.error}`); return; }
      alert(`✅ Đã chuyển ${data.count} file sang ${data.target_dir}`);
      setActiveTab("classifier");
      loadClassifierFiles();
    } catch (e) { alert(`Lỗi: ${e.message}`); }
    finally {
      sendAllToClassifierBtn.disabled = false;
      sendAllToClassifierBtn.textContent = "➡️ Chuyển tất cả sang Phân loại";
    }
  });
}

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

// Restore last classifier result on page load
(async function restoreClassifierResult() {
  try {
    // Try fetching from server (scans _temp_output folder)
    let data = null;
    try {
      const res = await fetch("/api/classifier/last-result");
      const json = await res.json();
      if (json.exists && json.copied && json.copied.length > 0) {
        data = json;
      }
    } catch(e) {}

    // Fallback: try localStorage
    if (!data) {
      const saved = localStorage.getItem("classifierLastResult");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.copied && parsed.copied.length > 0) data = parsed;
      }
    }

    if (!data) return;

    // Render result
    classifierResultEl.innerHTML = formatClassifierResult(data);
    setupClassifierRename();

    // Restore global vars
    window._classifierTempOutput = data._temp_output;
    window._classifierFinalOutput = data._final_output;

    // Show pipeline buttons + save button
    const pipelineBtns = document.getElementById("pipelineToInputBtns");
    if (pipelineBtns) {
      pipelineBtns.style.display = "flex";
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
              localStorage.removeItem("classifierLastResult");
              classifierResultEl.innerHTML = "<div style='padding:12px; color:#34d399;'>✅ Đã lưu thành công. Chạy phân loại mới để xem kết quả.</div>";
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
  } catch (e) { /* ignore restore errors */ }
})();
