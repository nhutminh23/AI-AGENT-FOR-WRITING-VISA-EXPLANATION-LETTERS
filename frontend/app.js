const fileListEl = document.getElementById("fileList");
const resultEl = document.getElementById("result");
const summaryEl = document.getElementById("summary");
const letterV2SampleFileEl = document.getElementById("letterV2SampleFile");
const letterV2SampleTextEl = document.getElementById("letterV2SampleText");
const analyzeSampleV2Btn = document.getElementById("analyzeSampleV2Btn");
const letterV2ContextEl = document.getElementById("letterV2Context");
const generateLetterV2Btn = document.getElementById("generateLetterV2Btn");
const letterV2StatusEl = document.getElementById("letterV2Status");
const letterV2StyleProfileEl = document.getElementById("letterV2StyleProfile");
const letterV2QualityReportEl = document.getElementById("letterV2QualityReport");
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
const flightFileInputEl = document.getElementById("flightFileInput");
const hotelFileInputEl = document.getElementById("hotelFileInput");
const flightFilePreviewEl = document.getElementById("flightFilePreview");
const hotelFilePreviewEl = document.getElementById("hotelFilePreview");
const itineraryResultEl = document.getElementById("itineraryResult");
const bookingSourceDbEl = document.getElementById("bookingSourceDb");
const bookingSourceFileEl = document.getElementById("bookingSourceFile");
const bookingSourcePdfEl = document.getElementById("bookingSourcePdf");
const fileSelectRowEl = document.getElementById("fileSelectRow");
const pdfUploadRowEl = document.getElementById("pdfUploadRow");
const fullPdfInputEl = document.getElementById("fullPdfInput");
const pdfExtractStatusEl = document.getElementById("pdfExtractStatus");
const dbBookingStatusEl = document.getElementById("dbBookingStatus");

// File preview updates
if (flightFileInputEl) flightFileInputEl.addEventListener("change", () => {
  const f = flightFileInputEl.files[0];
  flightFilePreviewEl.textContent = f ? `✈️ ${f.name}` : "";
});
if (hotelFileInputEl) hotelFileInputEl.addEventListener("change", () => {
  const files = hotelFileInputEl.files;
  if (files.length > 0) {
    hotelFilePreviewEl.textContent = `🏨 ${Array.from(files).map(f => f.name).join(", ")}`;
  } else {
    hotelFilePreviewEl.textContent = "";
  }
});

// Helper: read file as text via FileReader (returns Promise)
function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`Không đọc được file: ${file.name}`));
    reader.readAsText(file);
  });
}

// Toggle file selection visibility based on booking source (3 modes: db, file, pdf)
function updateBookingSourceUI() {
  const mode = document.querySelector('input[name="bookingSource"]:checked')?.value || "db";
  fileSelectRowEl.style.display = mode === "file" ? "block" : "none";
  pdfUploadRowEl.style.display = mode === "pdf" ? "block" : "none";

  if (mode === "db") {
    dbBookingStatusEl.style.display = "";
    checkDbBookingStatus();
  } else {
    dbBookingStatusEl.style.display = "none";
    if (mode === "file") {
      // Switching to HTML File mode: clear form
      if (itParticipantsEl) itParticipantsEl.value = "";
      if (itTravelStartDateEl) itTravelStartDateEl.value = "";
      if (itTravelEndDateEl) itTravelEndDateEl.value = "";
      if (itTravelPurposeEl) itTravelPurposeEl.value = "";
    }
    if (extractStatusEl) extractStatusEl.textContent = "";
  }
}
bookingSourceDbEl.addEventListener("change", updateBookingSourceUI);
bookingSourceFileEl.addEventListener("change", updateBookingSourceUI);
if (bookingSourcePdfEl) bookingSourcePdfEl.addEventListener("change", updateBookingSourceUI);

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
    const mode = document.querySelector('input[name="bookingSource"]:checked')?.value || "db";
    let ti = {};

    if (mode === "db") {
      // Mode DB: fetch from database
      const pid = getProjectId();
      const url = "/api/booking/trip/latest" + (pid ? `?project_id=${pid}` : "");
      const res = await fetch(url);
      const data = await res.json();
      ti = data.trip_info || {};
    } else if (mode === "pdf") {
      // Mode PDF: upload PDF → extract text → send to extraction
      const pdfFiles = fullPdfInputEl?.files || [];
      if (pdfFiles.length === 0) {
        extractStatusEl.innerHTML = '<span style="color:#d97706;">⚠️ Vui lòng chọn file PDF lịch trình trước.</span>';
        return;
      }
      extractStatusEl.innerHTML = '<span style="color:#d97706;">⏳ Đang đọc PDF...</span>';
      const fd = new FormData();
      fd.append("pdf_file", pdfFiles[0]);
      const pdfRes = await fetch("/api/itinerary/extract-pdf", { method: "POST", body: fd });
      const pdfData = await pdfRes.json();
      if (!pdfRes.ok) {
        extractStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi đọc PDF: ${pdfData.error || "unknown"}</span>`;
        return;
      }
      if (pdfExtractStatusEl) pdfExtractStatusEl.textContent = `✅ Đã đọc ${pdfData.pages || 0} trang`;
      // Send extracted text to extraction endpoint
      extractStatusEl.innerHTML = '<span style="color:#d97706;">⏳ AI đang phân tích nội dung...</span>';
      const res = await fetch("/api/itinerary/extract_from_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: pdfData.text }),
      });
      const data = await res.json();
      ti = data.trip_info || {};
    } else {
      // Mode File Upload: read uploaded HTML files
      const flightFiles = flightFileInputEl?.files || [];
      const hotelFiles = hotelFileInputEl?.files || [];
      if (flightFiles.length === 0 || hotelFiles.length === 0) {
        extractStatusEl.innerHTML = '<span style="color:#d97706;">⚠️ Vui lòng chọn đủ file vé máy bay và file booking khách sạn trước.</span>';
        return;
      }
      const flightHtml = await readFileAsText(flightFiles[0]);
      const hotelHtmls = [];
      for (const f of hotelFiles) {
        hotelHtmls.push(await readFileAsText(f));
      }
      const res = await fetch("/api/itinerary/extract_from_html", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ flight_html: flightHtml, hotel_htmls: hotelHtmls }),
      });
      const data = await res.json();
      ti = data.trip_info || {};
    }

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
const translateSection = document.getElementById("translateSection");
const classifierSection = document.getElementById("classifierSection");
const pdfSection = document.getElementById("pdfSection");
const editpdfSection = document.getElementById("editpdfSection");

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
const tripNumRoomsEl = document.getElementById("tripNumRooms");
const tripOriginCityEl = document.getElementById("tripOriginCity");
const tripOriginAirportEl = document.getElementById("tripOriginAirport");
const tripReturnPointEl = document.getElementById("tripReturnPoint");
const tripDestinationAirportHintEl = document.getElementById("tripDestinationAirportHint");
const tripReturnAirportHintEl = document.getElementById("tripReturnAirportHint");
const tripTravelPurposeEl = document.getElementById("tripTravelPurpose");
const tripTravelerProfileEl = document.getElementById("tripTravelerProfile");
const tripAdditionalInfoEl = document.getElementById("tripAdditionalInfo");
const bookingModeHotelBtn = document.getElementById("bookingModeHotelBtn");
const bookingModeFlightBtn = document.getElementById("bookingModeFlightBtn");
const bookingHotelPageEl = document.getElementById("bookingHotelPage");
const bookingFlightPageEl = document.getElementById("bookingFlightPage");
const manualBookingOverrideSectionEl = document.getElementById("manualBookingOverrideSection");
const runAIBookingHotelBtn = document.getElementById("runAIBookingHotelBtn");
const runAIBookingFlightBtn = document.getElementById("runAIBookingFlightBtn");
const showHotelPartBtn = document.getElementById("showHotelPartBtn");
const showFlightPartBtn = document.getElementById("showFlightPartBtn");
const hotelBookingPartEl = document.getElementById("hotelBookingPart");
const flightBookingPartEl = document.getElementById("flightBookingPart");
const bookingOutputAIEl = document.getElementById("bookingOutputAI");
const aiBookingStatusEl = document.getElementById("aiBookingStatus");
const aiReasoningSectionEl = document.getElementById("aiReasoningSection");
const aiReasoningEl = document.getElementById("aiReasoning");

// SerpAPI Flight Search elements
const serpFlightTypeEl = document.getElementById("serpFlightType");
const serpFlightTemplateEl = document.getElementById("serpFlightTemplate");
const serpDepartureIdEl = document.getElementById("serpDepartureId");
const serpArrivalIdEl = document.getElementById("serpArrivalId");
const serpOutboundDateEl = document.getElementById("serpOutboundDate");
const serpReturnDateEl = document.getElementById("serpReturnDate");
const serpReturnDateDivEl = document.getElementById("serpReturnDateDiv");
const serpStandardParamsEl = document.getElementById("serpStandardParams");
const serpMultiCityParamsEl = document.getElementById("serpMultiCityParams");
const serpMultiCityLegsEl = document.getElementById("serpMultiCityLegs");
const serpAddLegBtn = document.getElementById("serpAddLegBtn");
const serpAdultsEl = document.getElementById("serpAdults");
const serpChildrenEl = document.getElementById("serpChildren");
const serpCurrencyEl = document.getElementById("serpCurrency");
const serpSearchBtn = document.getElementById("serpSearchBtn");
const serpSearchStatusEl = document.getElementById("serpSearchStatus");
const serpOutboundResultsEl = document.getElementById("serpOutboundResults");
const serpReturnResultsEl = document.getElementById("serpReturnResults");
const serpGenerateAreaEl = document.getElementById("serpGenerateArea");
const serpContactNameEl = document.getElementById("serpContactName");
const serpContactEmailEl = document.getElementById("serpContactEmail");
const serpContactPhoneEl = document.getElementById("serpContactPhone");
const serpPassengerNamesEl = document.getElementById("serpPassengerNames");
const serpGenerateBtn = document.getElementById("serpGenerateBtn");
const serpGenerateStatusEl = document.getElementById("serpGenerateStatus");

// SerpAPI Hotel Search elements
const serpHotelSearchBtn = document.getElementById("serpHotelSearchBtn");
const serpHotelAdultsEl = document.getElementById("serpHotelAdults");
const serpHotelChildrenEl = document.getElementById("serpHotelChildren");
const serpHotelCurrencyEl = document.getElementById("serpHotelCurrency");
const serpHotelSearchStatusEl = document.getElementById("serpHotelSearchStatus");
const serpHotelResultsEl = document.getElementById("serpHotelResults");
const serpHotelGenerateAreaEl = document.getElementById("serpHotelGenerateArea");
const serpHotelGenerateBtn = document.getElementById("serpHotelGenerateBtn");
const serpHotelGenerateStatusEl = document.getElementById("serpHotelGenerateStatus");
let serpSelectedHotels = {}; // cityIndex -> selected property

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
const addTranslateFlowBtn = document.getElementById("addTranslateFlowBtn");
const addTranslateFlowBtnFallback = document.getElementById("addTranslateFlowBtnFallback");
const translateFlowsContainerEl = document.getElementById("translateFlowsContainer");
const bulkTranslateFilesEl = document.getElementById("bulkTranslateFiles");
const bulkCheckBtn = document.getElementById("bulkCheckBtn");
const bulkCheckStatusEl = document.getElementById("bulkCheckStatus");
const bulkCheckProgressEl = document.getElementById("bulkCheckProgress");
const bulkCheckProgressBarEl = document.getElementById("bulkCheckProgressBar");
const bulkCheckResultsEl = document.getElementById("bulkCheckResults");
const bulkResultsBodyEl = document.getElementById("bulkResultsBody");
const bulkResultSummaryEl = document.getElementById("bulkResultSummary");
const bulkCreateStreamsBtn = document.getElementById("bulkCreateStreamsBtn");
const bulkTranslateAllBtn = document.getElementById("bulkTranslateAllBtn");
const bulkPrintAllPdfBtn = document.getElementById("bulkPrintAllPdfBtn");
const bulkManualFallbackEl = document.getElementById("bulkManualFallback");

// Workspace selector elements (Drive auto-download)
const workspaceSelectEl = document.getElementById("workspaceSelect");
const refreshWorkspacesBtn = document.getElementById("refreshWorkspacesBtn");
const workspaceScanBtn = document.getElementById("workspaceScanBtn");
const workspaceScanStatusEl = document.getElementById("workspaceScanStatus");
const workspaceScanProgressEl = document.getElementById("workspaceScanProgress");
const workspaceScanProgressBarEl = document.getElementById("workspaceScanProgressBar");
const workspaceCompletePanelEl = document.getElementById("workspaceCompletePanel");
const workspaceCompleteInfoEl = document.getElementById("workspaceCompleteInfo");
const markCompleteBtn = document.getElementById("markCompleteBtn");

let cachedFiles = [];
let hotelHtmls = [];
let writerContextCache = "";
let letterV2StyleProfileCache = null;
let activeStepLog = null;
let classifierFilesCache = [];
let pdfFilesCache = [];
let currentProjectId = null;
let translationTemplatesCache = [];
let translationSourceFilesCache = [];
let translationFlowCounter = 0;
const _flowDbIds = {};  // Map: flowId (frontend) → db record id (backend)


// ==================== MODULES LOADED FROM js/ ====================
// projects.js, splitter.js, pipeline.js, booking.js,
// flights.js, hotels.js, precheck.js, ui-helpers.js,
// events.js, output.js, pdf-editor.js
