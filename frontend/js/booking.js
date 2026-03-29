// Booking + AI Booking Functions
// Extracted from app.js

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
  if (info.additional_info)
    lines.push(`📝 Thông tin bổ sung: ${info.additional_info}`);
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
  if (tripOriginCityEl) tripOriginCityEl.value = merged.origin_city || "";
  if (tripOriginAirportEl) tripOriginAirportEl.value = merged.origin_airport || "";
  if (tripReturnPointEl) tripReturnPointEl.value = merged.return_point || "";
  if (tripDestinationAirportHintEl) tripDestinationAirportHintEl.value = merged.destination_airport_hint || "";
  if (tripReturnAirportHintEl) tripReturnAirportHintEl.value = merged.return_airport_hint || "";
  if (tripTravelPurposeEl) tripTravelPurposeEl.value = merged.travel_purpose || "";
  if (tripTravelerProfileEl) tripTravelerProfileEl.value = merged.traveler_profile || "";
  if (tripAdditionalInfoEl) tripAdditionalInfoEl.value = merged.additional_info || "";

  prefillSerpPassengerInfo();
  if (serpDepartureIdEl && !serpDepartureIdEl.value && merged.origin_airport) {
    serpDepartureIdEl.value = merged.origin_airport.toUpperCase();
  }
  if (serpArrivalIdEl && !serpArrivalIdEl.value && merged.destination_airport_hint) {
    serpArrivalIdEl.value = merged.destination_airport_hint.toUpperCase();
  }
  if (serpOutboundDateEl && !serpOutboundDateEl.value && merged.travel_start_date) {
    serpOutboundDateEl.value = merged.travel_start_date;
  }
  if (serpReturnDateEl && !serpReturnDateEl.value && merged.travel_end_date) {
    serpReturnDateEl.value = merged.travel_end_date;
  }
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
    origin_city: (tripOriginCityEl?.value || "").trim(),
    origin_airport: (tripOriginAirportEl?.value || "").trim().toUpperCase(),
    return_point: (tripReturnPointEl?.value || "").trim(),
    destination_airport_hint: (tripDestinationAirportHintEl?.value || "").trim().toUpperCase(),
    return_airport_hint: (tripReturnAirportHintEl?.value || "").trim().toUpperCase(),
    travel_purpose: (tripTravelPurposeEl?.value || "").trim(),
    traveler_profile: (tripTravelerProfileEl?.value || "").trim(),
    additional_info: (tripAdditionalInfoEl?.value || "").trim(),
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
    prefillSerpPassengerInfo(); // Update Flight tab immediately
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

/* Map IATA codes to popular Countries */
const IATA_TO_COUNTRY = {
  "YYZ": "Canada", "YVR": "Canada", "YUL": "Canada", "YYC": "Canada", "YOW": "Canada",
  "CDG": "France", "ORY": "France", "NCE": "France", "LYS": "France",
  "SYD": "Australia", "MEL": "Australia", "BNE": "Australia", "PER": "Australia", "ADL": "Australia",
  "LHR": "United Kingdom", "LGW": "United Kingdom", "MAN": "United Kingdom", "EDI": "United Kingdom",
  "JFK": "USA", "LAX": "USA", "ORD": "USA", "SFO": "USA", "MIA": "USA", "EWR": "USA", "SEA": "USA",
  "FRA": "Germany", "MUC": "Germany", "BER": "Germany", "DUS": "Germany",
  "FCO": "Italy", "MXP": "Italy", "VCE": "Italy", "NAP": "Italy",
  "HND": "Japan", "NRT": "Japan", "KIX": "Japan", "NGO": "Japan",
  "ICN": "South Korea", "GMP": "South Korea", "CJU": "South Korea",
  "PEK": "China", "PVG": "China", "CAN": "China", "SZX": "China",
  "MAD": "Spain", "BCN": "Spain", "AGP": "Spain", "PMI": "Spain",
  "AKL": "New Zealand", "WLG": "New Zealand", "CHC": "New Zealand",
  "DEL": "India", "BOM": "India", "BLR": "India"
};

async function saveTripInfo() {
  const originalBtnText = saveTripInfoBtn.textContent;
  saveTripInfoBtn.textContent = "⏳ Đang lưu...";
  saveTripInfoBtn.disabled = true;
  try {
    // Đồng bộ ngược: Lấy dữ liệu tên từ ô 'Danh sách hành khách' (Tab Máy Bay) đè lại vào Form Ẩn
    // Để nếu User có tự tay sửa tên ở Tab Máy Bay thì bấm Lưu vẫn nhận được.
    const serpPassengerNamesEl = document.getElementById("serpPassengerNames");
    const tripGuestNamesEl = document.getElementById("tripGuestNames");
    if (serpPassengerNamesEl && tripGuestNamesEl) {
      if (serpPassengerNamesEl.value.trim() !== "") {
          tripGuestNamesEl.value = serpPassengerNamesEl.value;
      }
    }

    // Lắng nghe IATA sân bay khứ hồi từ form chuyến bay
    const serpArrivalIdEl = document.getElementById("serpArrivalId");
    if (serpArrivalIdEl && serpArrivalIdEl.value.trim() !== "") {
      const arrCode = serpArrivalIdEl.value.trim().toUpperCase();
      if (IATA_TO_COUNTRY[arrCode]) {
        document.getElementById("tripDestinationCountry").value = IATA_TO_COUNTRY[arrCode];
      }
    }

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
    // Auto-refresh: update flight tab with latest saved data
    prefillSerpPassengerInfo();
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

async function runAIBooking(target = "both") {
  const inputDir = inputDirEl.value.trim() || "input";
  const outputDir = bookingOutputAIEl.value.trim() || "output";
  const isHotelTarget = target === "hotel";
  const isFlightTarget = target === "flight";
  const activeBtn = isHotelTarget ? runAIBookingHotelBtn : isFlightTarget ? runAIBookingFlightBtn : runAIBookingHotelBtn;
  const originalBtnText = activeBtn ? activeBtn.textContent : "🚀 Chạy";

  const editedTripInfo = getTripInfoFromForm();

  if (runAIBookingHotelBtn) runAIBookingHotelBtn.disabled = true;
  if (runAIBookingFlightBtn) runAIBookingFlightBtn.disabled = true;
  if (activeBtn) activeBtn.textContent = "⏳ AI đang xử lý...";
  // Mutual lock: disable SerpAPI buttons while AI is running
  if (serpHotelSearchBtn) { serpHotelSearchBtn.disabled = true; serpHotelSearchBtn.style.opacity = '0.5'; }
  if (serpHotelGenerateBtn) { serpHotelGenerateBtn.disabled = true; serpHotelGenerateBtn.style.opacity = '0.5'; }
  if (serpHotelGenerateStatusEl) serpHotelGenerateStatusEl.innerHTML = `<span style='color:#d97706; font-size:0.85em;'>⏳ Đang chờ AI Booking hoàn thành...</span>`;

  // Build step-by-step progress UI
  const stepLabels = {
    1: "Trích xuất thông tin chuyến đi",
    2: isHotelTarget
      ? "AI chọn khách sạn"
      : isFlightTarget
        ? "AI chọn chuyến bay"
        : "AI chọn khách sạn & chuyến bay",
    3: isHotelTarget
      ? "Tạo file HTML khách sạn"
      : isFlightTarget
        ? "Tạo file HTML máy bay"
        : "Tạo file HTML booking",
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

  if (isHotelTarget || target === "both") {
    hotelBookingResultEl.srcdoc = "<p style='color:#94a3b8;padding:20px;'>⏳ Đang tạo booking khách sạn...</p>";
  }
  if (isFlightTarget || target === "both") {
    flightBookingResultEl.srcdoc = "<p style='color:#94a3b8;padding:20px;'>⏳ Đang tạo booking máy bay...</p>";
  }
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
        target,
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
    if (isHotelTarget || target === "both") {
      renderHotelTabs(data.hotel_htmls || []);
      setBookingPart("hotel");
    }

    // Display flight booking
    if (isFlightTarget || target === "both") {
      flightBookingResultEl.srcdoc = data.flight_html || "<p>Không có kết quả.</p>";
      if (data.flight_html) {
        exportFlightPdfBtn.style.display = "inline-block";
      }
      setBookingPart("flight");
    }
    syncCombinedPreviews();

    aiBookingStatusEl.innerHTML += `<div style="color:#16a34a; font-weight:600; margin-top:8px;">
      ${data.used_cache
        ? "✅ Hoàn thành! (dùng cache - không tốn token)"
        : isHotelTarget
          ? "✅ Hoàn thành! AI đã tạo booking khách sạn."
          : isFlightTarget
            ? "✅ Hoàn thành! AI đã tạo booking máy bay."
            : "✅ Hoàn thành! AI đã tạo booking thành công."}
    </div>`;
    // Refresh DB booking status for itinerary section
    checkDbBookingStatus();
  } catch (error) {
    aiBookingStatusEl.innerHTML += `<div style="color:#dc2626; margin-top:8px;">❌ Lỗi: ${error.message}</div>`;
    if (isHotelTarget || target === "both") {
      hotelBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
    }
    if (isFlightTarget || target === "both") {
      flightBookingResultEl.srcdoc = `<p>Lỗi: ${error.message}</p>`;
    }
    syncCombinedPreviews();
  } finally {
    if (activeBtn) activeBtn.textContent = originalBtnText;
    if (runAIBookingHotelBtn) runAIBookingHotelBtn.disabled = false;
    if (runAIBookingFlightBtn) runAIBookingFlightBtn.disabled = false;
    // Mutual unlock: re-enable SerpAPI buttons
    if (serpHotelSearchBtn) { serpHotelSearchBtn.disabled = false; serpHotelSearchBtn.style.opacity = ''; }
    if (serpHotelGenerateBtn) { serpHotelGenerateBtn.disabled = false; serpHotelGenerateBtn.style.opacity = ''; }
    if (serpHotelGenerateStatusEl && serpHotelGenerateStatusEl.textContent.includes('Đang chờ')) serpHotelGenerateStatusEl.innerHTML = '';
  }
}

// ==================== CITY WIZARD & DATE LOGIC ====================

const CITY_DB = {
  "France": ["Paris", "Lyon", "Marseille", "Nice", "Bordeaux"],
  "Canada": ["Toronto", "Vancouver", "Montreal", "Ottawa", "Calgary"],
  "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
  "United Kingdom": ["London", "Edinburgh", "Manchester", "Birmingham", "Glasgow"],
  "USA": ["New York", "Los Angeles", "Chicago", "Houston", "Miami"],
  "Germany": ["Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne"],
  "Italy": ["Rome", "Milan", "Venice", "Florence", "Naples"],
  "Japan": ["Tokyo", "Osaka", "Kyoto", "Nagoya", "Sapporo"],
  "South Korea": ["Seoul", "Busan", "Incheon", "Jeju", "Daegu"],
  "China": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu"],
  "Spain": ["Madrid", "Barcelona", "Valencia", "Seville", "Bilbao"],
  "New Zealand": ["Auckland", "Wellington", "Christchurch", "Queenstown", "Hamilton"]
};

// Auto-calculate nights
function calcTripNights() {
  if (typeof tripTravelStartDateEl !== 'undefined' && typeof tripTravelEndDateEl !== 'undefined' && typeof tripNumNightsEl !== 'undefined') {
    const start = new Date(tripTravelStartDateEl.value);
    const end = new Date(tripTravelEndDateEl.value);
    if (!isNaN(start) && !isNaN(end) && end >= start) {
      const nights = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
      tripNumNightsEl.value = nights;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof tripTravelStartDateEl !== 'undefined') tripTravelStartDateEl.addEventListener("change", calcTripNights);
  if (typeof tripTravelEndDateEl !== 'undefined') tripTravelEndDateEl.addEventListener("change", calcTripNights);

  // City Wizard Modal Logic
  const btnOpenCityWizard = document.getElementById("btnOpenCityWizard");
  const cityWizardModal = document.getElementById("cityWizardModal");
  const cityWizardList = document.getElementById("cityWizardList");
  const btnAddCustomCity = document.getElementById("btnAddCustomCity");
  const btnCityWizardConfirm = document.getElementById("btnCityWizardConfirm");

  if (btnOpenCityWizard && cityWizardModal) {
    btnOpenCityWizard.addEventListener("click", () => {
      const country = typeof tripDestinationCountryEl !== 'undefined' ? tripDestinationCountryEl.value.trim() : "";
      cityWizardList.innerHTML = "";
      
      let cities = [];
      if (country && CITY_DB[country] && CITY_DB[country].length > 0) {
        cities = [...CITY_DB[country]];
      } else if (country) {
        // Find partial match for convenience
        for (const [key, value] of Object.entries(CITY_DB)) {
          if (key.toLowerCase().includes(country.toLowerCase())) {
            cities = [...value];
            break;
          }
        }
      }
      
      // Always show at least 3 rows
      if (cities.length < 3) {
        const toAdd = 3 - cities.length;
        for (let i = 0; i < toAdd; i++) {
          cities.push("");
        }
      }
      
      cities.forEach(city => addCityRow(city));
      cityWizardModal.showModal();
    });
  }

  function addCityRow(cityName = "") {
    const row = document.createElement("div");
    row.className = "city-row";
    row.innerHTML = `
      <input type="text" class="cw-city-name" placeholder="Tên thành phố" value="${cityName}" />
      <input type="number" class="cw-city-nights" placeholder="Đêm" min="0" value="" />
      <button type="button" onclick="this.parentElement.remove()" title="Xóa">🗑️</button>
    `;
    if (cityWizardList) {
      cityWizardList.appendChild(row);
    }
  }

  if (btnAddCustomCity) {
    btnAddCustomCity.addEventListener("click", () => addCityRow(""));
  }

  if (btnCityWizardConfirm) {
    btnCityWizardConfirm.addEventListener("click", () => {
      const rows = cityWizardList.querySelectorAll(".city-row");
      const lines = [];
      rows.forEach(row => {
        const name = row.querySelector(".cw-city-name").value.trim();
        const nights = parseInt(row.querySelector(".cw-city-nights").value);
        if (name && !isNaN(nights) && nights > 0) {
          lines.push(`${name} (${nights})`);
        }
      });
      
      if (lines.length > 0 && typeof tripCitiesPlanEl !== 'undefined') {
        tripCitiesPlanEl.value = lines.join("\n");
      }
      cityWizardModal.close();
    });
  }
});
