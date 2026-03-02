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
  if (!files || files.length === 0) {
    classifierFileListEl.classList.add("empty");
    classifierFileListEl.textContent = "Không có file nào trong thư mục input phân loại.";
    return;
  }
  classifierFileListEl.classList.remove("empty");
  classifierFileListEl.innerHTML = files
    .map(
      (f) => `<div class="file-row">
        <span class="file-name">${f.rel_path || f.name}</span>
        <span class="file-domain">${f.domain}</span>
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
  } catch (error) {
    classifierResultEl.textContent = `Lỗi: ${error.message}`;
  } finally {
    runClassifierBtn.disabled = false;
    runClassifierBtn.textContent = originalText;
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
  if (aisplitterSection) allSections.push(aisplitterSection);
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
      body: JSON.stringify({ input_dir: inputDir }),
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
      body: JSON.stringify({ trip_info: tripInfo }),
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
    const res = await fetch("/api/booking/trip/latest");
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
  setActiveTab("booking");
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
