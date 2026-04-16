// SerpAPI Flight Search
// Extracted from app.js

// ==================== SERPAPI FLIGHT SEARCH ====================

let serpSelectedOutbound = null;
let serpSelectedReturn = null;
let serpMultiCityLegCount = 2;
let _serpFlightUIInitialized = false;

function initSerpFlightUI() {
  if (_serpFlightUIInitialized) return;
  _serpFlightUIInitialized = true;
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

  // Auto-calculation cho tổng số người
  if (tripGuestNamesEl) tripGuestNamesEl.addEventListener("input", (e) => {
    if (typeof window.calcPassengerCounts === 'function') window.calcPassengerCounts(e.target.value);
  });
  if (serpPassengerNamesEl) serpPassengerNamesEl.addEventListener("input", (e) => {
    if (typeof window.calcPassengerCounts === 'function') window.calcPassengerCounts(e.target.value);
  });

  prefillSerpPassengerInfo();
}

function addMultiCityLeg() {
  serpMultiCityLegCount++;
  const idx = serpMultiCityLegCount;
  const row = document.createElement("div");
  row.className = "row";
  row.style.marginTop = "6px";
  row.style.alignItems = "end";
  row.innerHTML = `
    <div><label>Chặng ${idx}: Sân bay đi</label><input type="text" class="mc-dep" placeholder="IATA" /></div>
    <div><label>Sân bay đến</label><input type="text" class="mc-arr" placeholder="IATA" /></div>
    <div><label>Ngày bay</label><input type="date" class="mc-date" /></div>
    <button type="button" class="mc-remove-btn" style="padding:6px 10px;background:#ef4444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;white-space:nowrap;" title="Xóa chặng này">✕</button>
  `;
  row.querySelector(".mc-remove-btn").addEventListener("click", () => {
    if (serpMultiCityLegsEl.children.length <= 2) {
      alert("Cần ít nhất 2 chặng bay.");
      return;
    }
    row.remove();
    // Re-number remaining legs
    serpMultiCityLegsEl.querySelectorAll(".row").forEach((r, i) => {
      const label = r.querySelector("label");
      if (label) label.textContent = `Chặng ${i + 1}: Sân bay đi`;
    });
  });
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

    // Build route summary showing all segments
    let routeSummary;
    if (legs.length >= 2) {
      // Multi-leg: show each segment
      routeSummary = legs.map(l => {
        const ld = (l.departure_airport || {}).id || "?";
        const la = (l.arrival_airport || {}).id || "?";
        return `${ld} → ${la}`;
      }).join(" • ");
    } else {
      routeSummary = `${depAirport.id || "?"} → ${arrAirport.id || "?"}`;
    }

    const legsHtml = legs.map((l, li) => {
      const ldep = l.departure_airport || {};
      const larr = l.arrival_airport || {};
      let layoverHtml = "";
      if (li < legs.length - 1 && li < layovers.length) {
        const lo = layovers[li];
        layoverHtml = `<span style="color:#d97706;font-size:12px;margin-left:8px;">⏱ ${_formatDuration(lo.duration)} tại ${lo.name} (${lo.id})</span>`;
      }
      // Add leg label for multi-leg
      const legLabel = legs.length >= 2
        ? `<span style="display:inline-block;background:#1E3A8A;color:#fff;padding:1px 6px;border-radius:4px;font-size:11px;font-weight:600;margin-right:6px;">Chặng ${li + 1}</span>`
        : "";
      return `<div style="font-size:13px;margin-top:4px;">
        ${legLabel}${_formatTime(ldep.time)} ${ldep.id} → ${_formatTime(larr.time)} ${larr.id}
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
            <span style="color:#6b7280;font-size:13px;margin-left:8px;">${routeSummary}</span>
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
      } else if (flightType === "3" && selected.departure_token) {
        // Multi-city: fetch next leg using departure_token
        serpSearchNextLeg(selected.departure_token, payload);
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

async function serpSearchNextLeg(departureToken, originalPayload) {
  serpReturnResultsEl.innerHTML = "<p style='color:#d97706;'>⏳ Đang tìm chuyến bay chặng tiếp theo...</p>";

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
      serpReturnResultsEl.innerHTML = "<span style='color:#d97706;'>Không tìm thấy chuyến bay cho chặng tiếp theo.</span>";
      showSerpGenerateArea();
      return;
    }

    serpReturnResultsEl.innerHTML = `<h3 style="margin-bottom:8px;">✈️ Chọn chuyến bay chặng tiếp theo (${allFlights.length} kết quả)</h3>`;
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

window.calcPassengerCounts = function(text) {
  if (!text || !text.trim()) {
    if (typeof serpAdultsEl !== 'undefined' && serpAdultsEl) serpAdultsEl.value = 1;
    if (typeof serpChildrenEl !== 'undefined' && serpChildrenEl) serpChildrenEl.value = 0;
    if (typeof serpHotelAdultsEl !== 'undefined' && serpHotelAdultsEl) serpHotelAdultsEl.value = 1;
    if (typeof serpHotelChildrenEl !== 'undefined' && serpHotelChildrenEl) serpHotelChildrenEl.value = 0;
    return;
  }
  const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
  let childrenCount = 0;
  let adultsCount = 0;
  lines.forEach(line => {
    if (/\[child\]/i.test(line)) {
      childrenCount++;
    } else {
      adultsCount++;
    }
  });
  if (typeof serpAdultsEl !== 'undefined' && serpAdultsEl) serpAdultsEl.value = adultsCount;
  if (typeof serpChildrenEl !== 'undefined' && serpChildrenEl) serpChildrenEl.value = childrenCount;
  if (typeof serpHotelAdultsEl !== 'undefined' && serpHotelAdultsEl) serpHotelAdultsEl.value = adultsCount;
  if (typeof serpHotelChildrenEl !== 'undefined' && serpHotelChildrenEl) serpHotelChildrenEl.value = childrenCount;
};

function prefillSerpPassengerInfo() {
  const tripGuestNames = tripGuestNamesEl?.value?.trim();
  if (tripGuestNames && serpPassengerNamesEl) {
    serpPassengerNamesEl.value = tripGuestNames;
  }
  const contactName = tripGuestNamesEl?.value?.trim().split("\n")[0] || "";
  if (contactName && serpContactNameEl) {
    serpContactNameEl.value = contactName.replace(/\s*\[child\]\s*/gi, "").toUpperCase();
  }
  if (tripGuestNames) {
    window.calcPassengerCounts(tripGuestNames);
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
  const isMultiCity = flightType === "3";
  if (isRoundTrip && !serpSelectedReturn) {
    alert("Vui lòng chọn chuyến bay về.");
    return;
  }
  if (isMultiCity && !serpSelectedReturn) {
    alert("Vui lòng chọn chuyến bay chặng tiếp theo.");
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
    label: isRoundTrip ? "Departure" : (isMultiCity ? "Leg 1" : "Departure"),
    flights: outboundFlights,
    layovers: outboundLayovers,
    extensions: outboundExtensions,
    airline_logo: serpSelectedOutbound.airline_logo || "",
  }];

  if ((isRoundTrip || isMultiCity) && serpSelectedReturn) {
    const retFlights = serpSelectedReturn.flights || [];
    const retLayovers = serpSelectedReturn.layovers || [];
    const retExtensions = serpSelectedReturn.extensions || [];
    directions.push({
      label: isRoundTrip ? "Return" : "Leg 2",
      flights: retFlights,
      layovers: retLayovers,
      extensions: retExtensions,
      airline_logo: serpSelectedReturn.airline_logo || "",
    });
  }

  // Pricing: use the latest selected price (for multi-city, leg 2 price is the combined total)
  let totalPrice;
  if ((isRoundTrip || isMultiCity) && serpSelectedReturn?.price) {
    totalPrice = Math.max(serpSelectedOutbound.price || 0, serpSelectedReturn.price || 0);
  } else {
    totalPrice = serpSelectedOutbound.price || 0;
  }

  // Lấy ngày đáp chuyến bay đi để gán làm Check-in mặc định cho khách sạn
  const lastOutboundLeg = outboundFlights[outboundFlights.length - 1];
  if (lastOutboundLeg?.arrival_airport?.time) {
    window.flightArrivalDate = lastOutboundLeg.arrival_airport.time.split(" ")[0];
  } else if (serpOutboundDateEl?.value) {
    window.flightArrivalDate = serpOutboundDateEl.value;
  }

  // Lấy ngày khởi hành chuyến về để làm Check-out mặc định cho khách sạn
  if ((isRoundTrip || isMultiCity) && serpSelectedReturn) {
    const retFlights = serpSelectedReturn.flights || [];
    const firstReturnLeg = retFlights[0];
    if (firstReturnLeg?.departure_airport?.time) {
      window.flightReturnDate = firstReturnLeg.departure_airport.time.split(" ")[0];
      } else if (serpReturnDateEl?.value) {
      window.flightReturnDate = serpReturnDateEl.value;
    }
  } else if (serpReturnDateEl?.value) {
    window.flightReturnDate = serpReturnDateEl.value;
  } else if (tripTravelEndDateEl?.value) {
    window.flightReturnDate = tripTravelEndDateEl.value;
  }
  const numAdults = parseInt(serpAdultsEl?.value) || 1;
  const numChildren = parseInt(serpChildrenEl?.value) || 0;
  const totalPax = numAdults + numChildren;
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
    flightBookingResultEl.style.minHeight = "600px";
    flightBookingResultEl.style.height = "600px";
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

// Self-initialization fallback: ensure initSerpFlightUI runs
// even if events.js fails to call it
if (document.readyState === "complete" || document.readyState === "interactive") {
  // DOM already loaded, init immediately
  setTimeout(initSerpFlightUI, 0);
} else {
  document.addEventListener("DOMContentLoaded", initSerpFlightUI);
}
window.addEventListener("load", initSerpFlightUI);
