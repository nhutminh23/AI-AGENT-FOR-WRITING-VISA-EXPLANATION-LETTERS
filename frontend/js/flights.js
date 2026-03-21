// SerpAPI Flight Search
// Extracted from app.js

// ==================== SERPAPI FLIGHT SEARCH ====================

let serpSelectedOutbound = null;
let serpSelectedReturn = null;
let serpMultiCityLegCount = 2;

function initSerpFlightUI() {
  if (!serpFlightTypeEl) return;

  if (tripOriginAirportEl?.value && serpDepartureIdEl && !serpDepartureIdEl.value) {
    serpDepartureIdEl.value = tripOriginAirportEl.value.trim().toUpperCase();
  }
  if (tripDestinationAirportHintEl?.value && serpArrivalIdEl && !serpArrivalIdEl.value) {
    serpArrivalIdEl.value = tripDestinationAirportHintEl.value.trim().toUpperCase();
  }
  if (tripTravelStartDateEl?.value && serpOutboundDateEl && !serpOutboundDateEl.value) {
    serpOutboundDateEl.value = tripTravelStartDateEl.value.trim();
  }
  if (tripTravelEndDateEl?.value && serpReturnDateEl && !serpReturnDateEl.value) {
    serpReturnDateEl.value = tripTravelEndDateEl.value.trim();
  }

  serpFlightTypeEl.addEventListener("change", () => {
    const t = serpFlightTypeEl.value;
    if (t === "3") {
      serpStandardParamsEl.style.display = "none";
      serpMultiCityParamsEl.style.display = "block";
      if (!serpMultiCityLegsEl.children.length) {
        serpMultiCityLegCount = 0;
        addMultiCityLeg();
        addMultiCityLeg();
      }
    } else {
      serpStandardParamsEl.style.display = "block";
      serpMultiCityParamsEl.style.display = "none";
      serpReturnDateDivEl.style.display = t === "1" ? "block" : "none";
    }
    serpOutboundResultsEl.innerHTML = "";
    serpReturnResultsEl.innerHTML = "";
    serpGenerateAreaEl.style.display = "none";
    serpSelectedOutbound = null;
    serpSelectedReturn = null;
  });
  serpReturnDateDivEl.style.display = serpFlightTypeEl.value === "1" ? "block" : "none";

  if (serpAddLegBtn) serpAddLegBtn.addEventListener("click", addMultiCityLeg);
  if (serpSearchBtn) serpSearchBtn.addEventListener("click", serpSearchFlights);
  if (serpGenerateBtn) serpGenerateBtn.addEventListener("click", serpGenerateTicket);

  prefillSerpPassengerInfo();
}

function addMultiCityLeg() {
  serpMultiCityLegCount++;
  const idx = serpMultiCityLegCount;
  const row = document.createElement("div");
  row.className = "row";
  row.style.marginTop = "6px";
  row.innerHTML = `
    <div><label>Chặng ${idx}: Sân bay đi</label><input type="text" class="mc-dep" placeholder="IATA" /></div>
    <div><label>Sân bay đến</label><input type="text" class="mc-arr" placeholder="IATA" /></div>
    <div><label>Ngày bay</label><input type="date" class="mc-date" /></div>
  `;
  serpMultiCityLegsEl.appendChild(row);
}

function _formatDuration(mins) {
  if (!mins) return "";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const parts = [];
  if (h) parts.push(`${h}h`);
  if (m) parts.push(`${m}m`);
  return parts.join(" ") || "0m";
}

function _formatTime(timeStr) {
  if (!timeStr) return "";
  const parts = timeStr.split(" ");
  if (parts.length < 2) return timeStr;
  const [hh, mm] = parts[1].split(":");
  let h = parseInt(hh, 10);
  const ampm = h >= 12 ? "PM" : "AM";
  if (h > 12) h -= 12;
  if (h === 0) h = 12;
  return `${h}:${mm} ${ampm}`;
}

function _formatDate(timeStr) {
  if (!timeStr) return "";
  const d = new Date(timeStr.split(" ")[0] + "T00:00:00");
  const days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
  const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  return `${days[d.getDay()]}, ${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

function _formatPrice(amount, currency) {
  if (currency === "VND") {
    return Number(amount).toLocaleString("vi-VN") + " ₫";
  }
  return `${Number(amount).toLocaleString()} ${currency}`;
}

function renderFlightResults(flights, containerId, selectionCallback) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!flights || flights.length === 0) {
    container.innerHTML = "<p style='color:#94a3b8;'>Không tìm thấy chuyến bay nào.</p>";
    return;
  }

  let html = "";
  flights.forEach((option, idx) => {
    const legs = option.flights || [];
    const layovers = option.layovers || [];
    const stops = layovers.length;
    const stopsText = stops === 0 ? "Bay thẳng" : `${stops} điểm dừng`;
    const price = option.price || 0;
    const dur = _formatDuration(option.total_duration);
    const firstLeg = legs[0] || {};
    const lastLeg = legs[legs.length - 1] || {};
    const depAirport = firstLeg.departure_airport || {};
    const arrAirport = lastLeg.arrival_airport || {};
    const airline = firstLeg.airline || "";
    const logo = firstLeg.airline_logo || option.airline_logo || "";

    const legsHtml = legs.map((l, li) => {
      const ldep = l.departure_airport || {};
      const larr = l.arrival_airport || {};
      let layoverHtml = "";
      if (li < legs.length - 1 && li < layovers.length) {
        const lo = layovers[li];
        layoverHtml = `<span style="color:#d97706;font-size:12px;margin-left:8px;">⏱ ${_formatDuration(lo.duration)} tại ${lo.name} (${lo.id})</span>`;
      }
      return `<div style="font-size:13px;margin-top:4px;">
        ${_formatTime(ldep.time)} ${ldep.id} → ${_formatTime(larr.time)} ${larr.id}
        &nbsp;|&nbsp; ${l.airline || ""} ${l.flight_number || ""} &nbsp;|&nbsp; ${l.airplane || ""} &nbsp;|&nbsp; ${_formatDuration(l.duration)}
        ${layoverHtml}
      </div>`;
    }).join("");

    const extsHtml = (option.extensions || []).map(e => `<span style="font-size:12px;color:#6b7280;margin-right:8px;">${e}</span>`).join("");

    html += `<div class="serp-flight-option" data-idx="${idx}" style="border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin-bottom:8px;cursor:pointer;transition:all 0.2s;background:#fff;"
      onmouseover="this.style.borderColor='#4f46e5';this.style.background='#f8fafc';"
      onmouseout="this.style.borderColor='#e2e8f0';this.style.background='#fff';">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div style="display:flex;align-items:center;gap:10px;">
          <img src="${logo}" width="32" alt="${airline}" style="border-radius:4px;">
          <div>
            <strong>${_formatTime(depAirport.time)} – ${_formatTime(arrAirport.time)}</strong>
            <span style="color:#6b7280;font-size:13px;margin-left:8px;">${depAirport.id} → ${arrAirport.id}</span>
          </div>
        </div>
        <div style="text-align:right;">
          <div style="font-weight:700;font-size:16px;color:#16a34a;">${_formatPrice(price, serpCurrencyEl?.value || "USD")}</div>
          <div style="font-size:13px;color:#6b7280;">${dur} • ${stopsText}</div>
        </div>
      </div>
      ${legsHtml}
      <div style="margin-top:6px;">${extsHtml}</div>
    </div>`;
  });

  container.innerHTML = html;

  container.querySelectorAll(".serp-flight-option").forEach(el => {
    el.addEventListener("click", () => {
      container.querySelectorAll(".serp-flight-option").forEach(e => {
        e.style.borderColor = "#e2e8f0";
        e.style.background = "#fff";
      });
      el.style.borderColor = "#4f46e5";
      el.style.background = "#eef2ff";
      const idx = parseInt(el.dataset.idx, 10);
      selectionCallback(flights[idx], idx);
    });
  });
}

async function serpSearchFlights() {
  if (!serpSearchBtn) return;
  const flightType = serpFlightTypeEl.value;
  serpSearchBtn.disabled = true;
  serpSearchBtn.textContent = "⏳ Đang tìm...";
  serpSearchStatusEl.innerHTML = "";
  serpOutboundResultsEl.innerHTML = "";
  serpReturnResultsEl.innerHTML = "";
  serpGenerateAreaEl.style.display = "none";
  serpSelectedOutbound = null;
  serpSelectedReturn = null;

  try {
    let payload;
    if (flightType === "3") {
      const legs = [];
      serpMultiCityLegsEl.querySelectorAll(".row").forEach(row => {
        const dep = row.querySelector(".mc-dep")?.value.trim().toUpperCase();
        const arr = row.querySelector(".mc-arr")?.value.trim().toUpperCase();
        const date = row.querySelector(".mc-date")?.value;
        if (dep && arr && date) legs.push({ departure_id: dep, arrival_id: arr, date });
      });
      if (legs.length < 2) {
        serpSearchStatusEl.innerHTML = "<span style='color:#dc2626;'>Cần ít nhất 2 chặng bay.</span>";
        return;
      }
      payload = {
        type: "3",
        departure_id: legs[0].departure_id,
        arrival_id: legs[0].arrival_id,
        outbound_date: legs[0].date,
        multi_city_json: JSON.stringify(legs),
        adults: parseInt(serpAdultsEl.value) || 1,
        children: parseInt(serpChildrenEl.value) || 0,
        currency: serpCurrencyEl.value || "USD",
      };
    } else {
      payload = {
        type: flightType,
        departure_id: serpDepartureIdEl.value.trim().toUpperCase(),
        arrival_id: serpArrivalIdEl.value.trim().toUpperCase(),
        outbound_date: serpOutboundDateEl.value,
        adults: parseInt(serpAdultsEl.value) || 1,
        children: parseInt(serpChildrenEl.value) || 0,
        currency: serpCurrencyEl.value || "USD",
      };
      if (flightType === "1" && serpReturnDateEl.value) {
        payload.return_date = serpReturnDateEl.value;
      }
    }

    const res = await fetch("/api/flights/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      serpSearchStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${data.error}</span>`;
      return;
    }

    const allFlights = [...(data.best_flights || []), ...(data.other_flights || [])];
    if (allFlights.length === 0) {
      serpSearchStatusEl.innerHTML = "<span style='color:#d97706;'>Không tìm thấy chuyến bay nào.</span>";
      return;
    }

    const label = flightType === "1" ? "Chọn chuyến bay đi" : "Chọn chuyến bay";
    serpOutboundResultsEl.innerHTML = `<h3 style="margin-bottom:8px;">✈️ ${label} (${allFlights.length} kết quả)</h3>`;
    const listDiv = document.createElement("div");
    listDiv.id = "serpOutboundList";
    listDiv.style.maxHeight = "400px";
    listDiv.style.overflowY = "auto";
    serpOutboundResultsEl.appendChild(listDiv);

    renderFlightResults(allFlights, "serpOutboundList", (selected) => {
      serpSelectedOutbound = selected;
      if (flightType === "1" && selected.departure_token) {
        serpSearchReturnFlights(selected.departure_token, payload);
      } else {
        serpSelectedReturn = null;
        serpReturnResultsEl.innerHTML = "";
        showSerpGenerateArea();
      }
    });

    serpSearchStatusEl.innerHTML = `<span style='color:#16a34a;'>✅ Tìm thấy ${allFlights.length} chuyến bay.</span>`;
  } catch (e) {
    serpSearchStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${e.message}</span>`;
  } finally {
    serpSearchBtn.disabled = false;
    serpSearchBtn.textContent = "🔍 Tìm chuyến bay";
  }
}

async function serpSearchReturnFlights(departureToken, originalPayload) {
  serpReturnResultsEl.innerHTML = "<p style='color:#d97706;'>⏳ Đang tìm chuyến bay về...</p>";

  try {
    const payload = {
      ...originalPayload,
      departure_token: departureToken,
    };
    const res = await fetch("/api/flights/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      serpReturnResultsEl.innerHTML = `<span style='color:#dc2626;'>❌ ${data.error}</span>`;
      return;
    }

    const allFlights = [...(data.best_flights || []), ...(data.other_flights || [])];
    if (allFlights.length === 0) {
      serpReturnResultsEl.innerHTML = "<span style='color:#d97706;'>Không tìm thấy chuyến bay về.</span>";
      return;
    }

    serpReturnResultsEl.innerHTML = `<h3 style="margin-bottom:8px;">🔄 Chọn chuyến bay về (${allFlights.length} kết quả)</h3>`;
    const listDiv = document.createElement("div");
    listDiv.id = "serpReturnList";
    listDiv.style.maxHeight = "400px";
    listDiv.style.overflowY = "auto";
    serpReturnResultsEl.appendChild(listDiv);

    renderFlightResults(allFlights, "serpReturnList", (selected) => {
      serpSelectedReturn = selected;
      showSerpGenerateArea();
    });
  } catch (e) {
    serpReturnResultsEl.innerHTML = `<span style='color:#dc2626;'>❌ ${e.message}</span>`;
  }
}

function prefillSerpPassengerInfo() {
  const tripGuestNames = tripGuestNamesEl?.value?.trim();
  if (tripGuestNames && serpPassengerNamesEl && !serpPassengerNamesEl.value.trim()) {
    serpPassengerNamesEl.value = tripGuestNames;
  }
  const contactName = tripGuestNamesEl?.value?.trim().split("\n")[0] || "";
  if (contactName && serpContactNameEl && !serpContactNameEl.value.trim()) {
    serpContactNameEl.value = contactName.replace(/\s*\[child\]\s*/gi, "").toUpperCase();
  }
}

function showSerpGenerateArea() {
  if (!serpGenerateAreaEl) return;
  serpGenerateAreaEl.style.display = "block";
}

async function serpGenerateTicket() {
  if (!serpSelectedOutbound) {
    alert("Vui lòng chọn chuyến bay trước.");
    return;
  }
  const flightType = serpFlightTypeEl.value;
  const isRoundTrip = flightType === "1";
  if (isRoundTrip && !serpSelectedReturn) {
    alert("Vui lòng chọn chuyến bay về.");
    return;
  }

  const templateType = serpFlightTemplateEl?.value || "vivavivu";
  const currency = serpCurrencyEl?.value || "USD";

  const passengerLines = (serpPassengerNamesEl?.value || "").trim().split("\n").filter(Boolean);
  const passengers = passengerLines.map(name => ({
    name: name.replace(/\s*\[child\]\s*/gi, "").toUpperCase().trim(),
    dob: "\u2013",
    ticket_price: "\u2013",
    fee: "\u2013",
    total: "\u2013",
  }));

  const contact = {
    name: (serpContactNameEl?.value || "").trim(),
    email: (serpContactEmailEl?.value || "").trim(),
    phone: (serpContactPhoneEl?.value || "").trim(),
  };

  const tripTypeLabels = { "1": "Round trip", "2": "One way", "3": "Multi-city" };
  const tripType = tripTypeLabels[flightType] || "One way";

  const outboundFlights = serpSelectedOutbound.flights || [];
  const outboundLayovers = serpSelectedOutbound.layovers || [];
  const outboundExtensions = serpSelectedOutbound.extensions || [];
  const firstDep = outboundFlights[0]?.departure_airport?.time || "";

  const directions = [{
    label: isRoundTrip ? "Departure" : (flightType === "3" ? "Leg 1" : "Departure"),
    flights: outboundFlights,
    layovers: outboundLayovers,
    extensions: outboundExtensions,
    airline_logo: serpSelectedOutbound.airline_logo || "",
  }];

  if (isRoundTrip && serpSelectedReturn) {
    const retFlights = serpSelectedReturn.flights || [];
    const retLayovers = serpSelectedReturn.layovers || [];
    const retExtensions = serpSelectedReturn.extensions || [];
    directions.push({
      label: "Return",
      flights: retFlights,
      layovers: retLayovers,
      extensions: retExtensions,
      airline_logo: serpSelectedReturn.airline_logo || "",
    });
  }

  // SerpAPI Google Flights returns prices that are TOTAL for all passengers.
  // For round trip, each direction's price is the total for all pax for THAT direction.
  // We use the higher of outbound/return as the full round-trip total for all pax.
  let totalPrice;
  if (isRoundTrip && serpSelectedReturn?.price) {
    // Use the larger price — typically the updated round-trip total
    totalPrice = Math.max(serpSelectedOutbound.price || 0, serpSelectedReturn.price || 0);
  } else {
    totalPrice = serpSelectedOutbound.price || 0;
  }
  const numAdults = parseInt(serpAdultsEl?.value) || 1;
  const numChildren = parseInt(serpChildrenEl?.value) || 0;
  const totalPax = numAdults + numChildren;
  // Price per person = total / number of passengers
  const perPerson = totalPax > 0 ? Math.round(totalPrice / totalPax) : totalPrice;
  passengers.forEach(p => {
    p.ticket_price = _formatPrice(perPerson, currency);
    p.total = _formatPrice(perPerson, currency);
  });

  serpGenerateBtn.disabled = true;
  serpGenerateBtn.textContent = "⏳ Đang tạo vé...";
  serpGenerateStatusEl.innerHTML = "";

  try {
    const payload = {
      template_type: templateType,
      trip_type: tripType,
      selected_outbound: serpSelectedOutbound,
      selected_return: serpSelectedReturn,
      contact,
      passengers,
      total_price: totalPrice,
      discount: "0",
      currency,
      directions,
      output_dir: bookingOutputAIEl?.value?.trim() || "output",
      project_id: getProjectId(),
    };

    const res = await fetch("/api/flights/generate_from_serp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      serpGenerateStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${data.error}</span>`;
      return;
    }

    flightBookingResultEl.srcdoc = data.flight_html || "<p>Không có kết quả.</p>";
    if (data.flight_html) exportFlightPdfBtn.style.display = "inline-block";
    setBookingMode("flight");
    syncCombinedPreviews();
    serpGenerateStatusEl.innerHTML = templateType === "vivavivu"
      ? "<span style='color:#16a34a;'>✅ Tạo vé Vivavivu thành công!</span>"
      : "<span style='color:#16a34a;'>✅ Tạo vé Vietnam Airlines thành công!</span>";
  } catch (e) {
    serpGenerateStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${e.message}</span>`;
  } finally {
    serpGenerateBtn.disabled = false;
    serpGenerateBtn.textContent = "✅ Tạo vé booking";
  }
}

