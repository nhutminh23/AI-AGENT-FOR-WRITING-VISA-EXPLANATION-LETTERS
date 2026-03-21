// SerpAPI Hotel Search
// Extracted from app.js

// ==================== SERPAPI HOTEL SEARCH ====================

/**
 * Parse the tripCitiesPlan textarea into structured stops.
 * Format per line: "CityName (nights) OptionalHotelHint"
 * Examples:
 *   Paris Ibis Paris Tour Eiffel Cambronne 15ème (3)
 *   Lyon Novotel Lyon Centre Part-Dieu (2)
 *   Annecy Hotel Allobroges Park Hotel (1)
 */
function parseCitiesPlan(text) {
  const lines = text.trim().split("\n").filter(l => l.trim());
  const stops = [];
  for (const line of lines) {
    const trimmed = line.trim();
    // Match pattern: anything (number) optionally followed by more text
    // But the format from the screenshot is: "Paris Ibis Paris Tour Eiffel Cambronne 15ème (3)"
    // So everything before (N) could be city+hotel mixed, we need a smarter parse.
    // Strategy: extract (N) for nights, then split remaining by first word as city
    const nightsMatch = trimmed.match(/\((\d+)\)/);
    if (!nightsMatch) continue;
    const nights = parseInt(nightsMatch[1]);
    // Remove the (N) part to get the rest
    const rest = trimmed.replace(/\(\d+\)/, "").trim();
    // First word (or first word before known hotel keywords) is the city
    // Simple heuristic: first word is city, rest is hotel hint
    const words = rest.split(/\s+/);
    const city = words[0] || "";
    const hotelHint = words.length > 1 ? rest : "";
    stops.push({ city, nights, hotel_hint: hotelHint });
  }
  return stops;
}

async function serpSearchHotels() {
  if (!serpHotelSearchBtn) return;
  const citiesText = tripCitiesPlanEl?.value?.trim();
  const startDate = tripTravelStartDateEl?.value?.trim();

  if (!citiesText) {
    serpHotelSearchStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ Vui lòng nhập thành phố & số đêm ở Bước 1.</span>`;
    return;
  }
  if (!startDate) {
    serpHotelSearchStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ Vui lòng nhập ngày đi ở Bước 1.</span>`;
    return;
  }

  const stops = parseCitiesPlan(citiesText);
  if (stops.length === 0) {
    serpHotelSearchStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ Không parse được thành phố. Định dạng: "Paris (3)" hoặc "Lyon Novotel (2)"</span>`;
    return;
  }

  serpHotelSearchBtn.disabled = true;
  serpHotelSearchBtn.textContent = "⏳ Đang tìm...";
  serpHotelSearchStatusEl.innerHTML = `<span style='color:#d97706;'>🔍 Đang tìm khách sạn cho ${stops.length} thành phố...</span>`;
  serpHotelResultsEl.innerHTML = "";
  serpHotelGenerateAreaEl.style.display = "none";
  serpSelectedHotels = {};

  try {
    const payload = {
      start_date: startDate,
      stops,
      adults: parseInt(serpHotelAdultsEl?.value) || 2,
      children: parseInt(serpHotelChildrenEl?.value) || 0,
      currency: serpHotelCurrencyEl?.value || "USD",
    };

    const res = await fetch("/api/hotels/search-itinerary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      serpHotelSearchStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${data.error}</span>`;
      return;
    }

    const allStops = data.stops || [];
    if (allStops.length === 0) {
      serpHotelSearchStatusEl.innerHTML = `<span style='color:#d97706;'>Không tìm thấy kết quả.</span>`;
      return;
    }

    // Render results for each city
    allStops.forEach((stop, idx) => {
      renderHotelStopResults(stop, idx);
    });

    const totalHotels = allStops.reduce((sum, s) => sum + (s.properties?.length || 0), 0);
    serpHotelSearchStatusEl.innerHTML = `<span style='color:#16a34a;'>✅ Tìm thấy ${totalHotels} khách sạn cho ${allStops.length} thành phố.</span>`;

  } catch (e) {
    serpHotelSearchStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${e.message}</span>`;
  } finally {
    serpHotelSearchBtn.disabled = false;
    serpHotelSearchBtn.textContent = "🔍 Tìm khách sạn";
  }
}

function renderHotelStopResults(stop, stopIdx) {
  const container = document.createElement("div");
  container.style.cssText = "margin-bottom:16px; border:1px solid #e2e8f0; border-radius:10px; overflow:hidden;";

  const hasError = stop.error;
  const properties = stop.properties || [];

  // Header
  const header = document.createElement("div");
  header.style.cssText = "background:#f8fafc; padding:12px 16px; border-bottom:1px solid #e2e8f0; cursor:pointer; display:flex; justify-content:space-between; align-items:center;";
  header.innerHTML = `
    <div>
      <strong style="font-size:1.05em;">🏨 ${stop.city}</strong>
      <span style="color:#64748b; font-size:0.85em; margin-left:8px;">
        ${stop.nights} đêm · ${stop.check_in} → ${stop.check_out}
      </span>
      ${stop.hotel_hint ? `<span style="color:#4f46e5; font-size:0.8em; margin-left:6px;">🔍 "${stop.hotel_hint}"</span>` : ""}
    </div>
    <span style="font-size:0.85em; color:#64748b;">${properties.length} kết quả ▼</span>
  `;

  const body = document.createElement("div");
  body.style.cssText = "padding:8px; max-height:400px; overflow-y:auto;";

  header.addEventListener("click", () => {
    body.style.display = body.style.display === "none" ? "block" : "none";
  });

  if (hasError) {
    body.innerHTML = `<div style="color:#dc2626; padding:8px;">❌ Lỗi: ${stop.error}</div>`;
  } else if (properties.length === 0) {
    body.innerHTML = `<div style="color:#d97706; padding:8px;">Không tìm thấy khách sạn nào.</div>`;
  } else {
    properties.forEach((prop, propIdx) => {
      const card = document.createElement("div");
      const isSelected = serpSelectedHotels[stopIdx]?.name === prop.name;
      card.style.cssText = `display:flex; gap:12px; padding:10px; margin:6px 0; border:2px solid ${isSelected ? "#4f46e5" : "#e2e8f0"}; border-radius:8px; cursor:pointer; transition:all 0.2s; background:${isSelected ? "#eef2ff" : "#fff"};`;
      card.addEventListener("mouseenter", () => { if (!isSelected) card.style.borderColor = "#a5b4fc"; });
      card.addEventListener("mouseleave", () => { if (!isSelected) card.style.borderColor = "#e2e8f0"; });

      // Thumbnail
      const imgSrc = prop.images?.[0]?.thumbnail || prop.images?.[0]?.original_image || "";
      const imgHtml = imgSrc
        ? `<img src="${imgSrc}" style="width:100px; height:75px; object-fit:cover; border-radius:6px; flex-shrink:0;" onerror="this.style.display='none'" />`
        : `<div style="width:100px; height:75px; background:#f1f5f9; border-radius:6px; display:flex; align-items:center; justify-content:center; flex-shrink:0; color:#94a3b8;">🏨</div>`;

      // Rating stars
      const rating = prop.overall_rating || prop.rating || 0;
      const reviews = prop.reviews || 0;
      const ratingHtml = rating ? `⭐ ${rating}${reviews ? ` (${reviews})` : ""}` : "";

      // Price
      const price = prop.rate_per_night?.lowest || prop.price || prop.extracted_price || "";
      const totalPrice = prop.total_rate?.lowest || "";

      // Hotel class (can be number or string like "4-star tourist hotel")
      const hcRaw = prop.hotel_class || 0;
      const hcNum = typeof hcRaw === "number" ? hcRaw : parseInt(String(hcRaw).replace(/\D/g, "") || "0");
      const hotelClass = hcNum > 0 ? "⭐".repeat(Math.min(hcNum, 5)) : "";

      card.innerHTML = `
        ${imgHtml}
        <div style="flex:1; min-width:0;">
          <div style="font-weight:600; font-size:0.95em; margin-bottom:2px;">${prop.name || "Unknown Hotel"}</div>
          <div style="font-size:0.8em; color:#64748b; margin-bottom:3px;">${hotelClass} ${prop.type || "Hotel"}</div>
          <div style="font-size:0.8em; color:#64748b;">${ratingHtml}</div>
          ${prop.amenities ? `<div style="font-size:0.75em; color:#94a3b8; margin-top:2px;">${(prop.amenities || []).slice(0, 4).join(" · ")}</div>` : ""}
        </div>
        <div style="text-align:right; flex-shrink:0;">
          ${price ? `<div style="font-weight:700; color:#16a34a; font-size:1.05em;">${price}</div>` : ""}
          ${price ? `<div style="font-size:0.75em; color:#94a3b8;">/đêm</div>` : ""}
          ${totalPrice ? `<div style="font-size:0.8em; color:#475569; margin-top:2px;">Tổng: ${totalPrice}</div>` : ""}
          ${isSelected ? `<div style="color:#4f46e5; font-weight:600; font-size:0.85em; margin-top:4px;">✅ Đã chọn</div>` : ""}
        </div>
      `;

      card.addEventListener("click", () => {
        serpSelectedHotels[stopIdx] = { ...prop, _stop: stop };
        // Update visual feedback in-place (no re-render!)
        body.querySelectorAll("div").forEach(c => {
          if (c.style.borderRadius === "8px") {
            c.style.borderColor = "#e2e8f0";
            c.style.background = "#fff";
            // Remove old "Đã chọn" badges
            const badge = c.querySelector(".hotel-selected-badge");
            if (badge) badge.remove();
          }
        });
        card.style.borderColor = "#4f46e5";
        card.style.background = "#eef2ff";
        // Add selected badge
        const rightDiv = card.querySelector("div[style*='text-align:right']");
        if (rightDiv && !rightDiv.querySelector(".hotel-selected-badge")) {
          const badge = document.createElement("div");
          badge.className = "hotel-selected-badge";
          badge.style.cssText = "color:#4f46e5; font-weight:600; font-size:0.85em; margin-top:4px;";
          badge.textContent = "✅ Đã chọn";
          rightDiv.appendChild(badge);
        }
        // Show generate button if at least one hotel selected
        serpHotelGenerateAreaEl.style.display = "block";
        // Show selection summary
        const selectedCount = Object.keys(serpSelectedHotels).length;
        serpHotelGenerateStatusEl.innerHTML = `<span style='color:#4f46e5;'>🏨 Đã chọn ${selectedCount} khách sạn. Bấm "Tạo booking" để sinh HTML.</span>`;
      });

      body.appendChild(card);
    });
  }

  container.appendChild(header);
  container.appendChild(body);
  serpHotelResultsEl.appendChild(container);
}

async function serpGenerateHotelBooking() {
  const selectedCount = Object.keys(serpSelectedHotels).length;
  if (selectedCount === 0) {
    alert("Vui lòng chọn ít nhất 1 khách sạn.");
    return;
  }

  serpHotelGenerateBtn.disabled = true;
  serpHotelGenerateBtn.textContent = "⏳ Đang tạo booking...";
  serpHotelGenerateStatusEl.innerHTML = "";
  // Mutual lock: disable AI button while SerpAPI is generating
  if (runAIBookingHotelBtn) { runAIBookingHotelBtn.disabled = true; runAIBookingHotelBtn.style.opacity = '0.5'; }
  const aiBookingStatusEl = document.getElementById('aiBookingStatus');
  if (aiBookingStatusEl) aiBookingStatusEl.innerHTML = `<span style='color:#d97706; font-size:0.85em;'>⏳ Đang chờ SerpAPI Booking hoàn thành...</span>`;

  try {
    // Build hotel data for each selected stop
    const hotelStops = Object.entries(serpSelectedHotels).map(([idx, hotel]) => ({
      city: hotel._stop?.city || "",
      check_in: hotel._stop?.check_in || "",
      check_out: hotel._stop?.check_out || "",
      nights: hotel._stop?.nights || 1,
      hotel_name: hotel.name || "",
      hotel_address: hotel.address || hotel.extracted_address || hotel.location || "",
      hotel_class: hotel.hotel_class || hotel.extracted_hotel_class || 0,
      rating: hotel.overall_rating || hotel.rating || 0,
      price_per_night: hotel.rate_per_night?.lowest || hotel.price || "",
      total_price: hotel.total_rate?.lowest || "",
      amenities: (hotel.amenities || []).slice(0, 6),
      thumbnail: hotel.images?.[0]?.thumbnail || "",
      // hotel.type is property category (e.g. "hotel", "resort") — NOT room type
      room_type: hotel.room_type || "",
      phone: hotel.phone || "",
      property_type: hotel.type || "",
      // property_token for SerpAPI Property Details API (to get address, phone, rooms)
      property_token: hotel.property_token || "",
      check_in_time: hotel.check_in_time || "",
      check_out_time: hotel.check_out_time || "",
      description: hotel.description || "",
    }));

    // Separate adults and children - children are marked with [child]
    const allNames = (tripGuestNamesEl?.value || "").trim().split("\n").filter(Boolean);
    const adults = allNames.filter(n => !/\[child\]/i.test(n)).map(n => n.trim());
    const children = allNames.filter(n => /\[child\]/i.test(n)).map(n => n.replace(/\s*\[child\]\s*/gi, "").trim());

    const payload = {
      hotel_stops: hotelStops,
      guests: adults,
      children: children,
      num_rooms: parseInt(tripNumRoomsEl?.value || "0") || 0,
      output_dir: bookingOutputAIEl?.value?.trim() || "output",
      project_id: getProjectId(),
    };

    const res = await fetch("/api/hotels/generate-booking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      serpHotelGenerateStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${data.error}</span>`;
      return;
    }

    // Show results using tabs (same as AI booking flow)
    if (data.hotel_htmls && data.hotel_htmls.length > 0) {
      renderHotelTabs(data.hotel_htmls);
    } else if (data.hotel_html) {
      renderHotelTabs([data.hotel_html]);
    }
    syncCombinedPreviews();
    const fileCount = data.file_count || 1;
    serpHotelGenerateStatusEl.innerHTML = `<span style='color:#16a34a;'>✅ Tạo ${fileCount} booking khách sạn thành công! (Agoda template)</span>`;
  } catch (e) {
    serpHotelGenerateStatusEl.innerHTML = `<span style='color:#dc2626;'>❌ ${e.message}</span>`;
  } finally {
    serpHotelGenerateBtn.disabled = false;
    serpHotelGenerateBtn.textContent = "✅ Tạo booking từ kết quả";
    // Mutual unlock: re-enable AI button
    if (runAIBookingHotelBtn) { runAIBookingHotelBtn.disabled = false; runAIBookingHotelBtn.style.opacity = ''; }
    const aiBookingStatusEl2 = document.getElementById('aiBookingStatus');
    if (aiBookingStatusEl2 && aiBookingStatusEl2.textContent.includes('Đang chờ')) aiBookingStatusEl2.textContent = 'Chưa chạy.';
  }
}

// Event listeners for hotel search
if (serpHotelSearchBtn) serpHotelSearchBtn.addEventListener("click", serpSearchHotels);
if (serpHotelGenerateBtn) serpHotelGenerateBtn.addEventListener("click", serpGenerateHotelBooking);

// ─── Auto-load saved output files on page init (persist after F5) ───
(async function loadSavedOutputs() {
  try {
    const _t = Date.now(); // cache-buster
    const res = await fetch(`/api/output-files?_t=${_t}`);
    if (!res.ok) return;
    const files = await res.json();

    // Load itinerary
    if (files.itinerary && itineraryResultEl) {
      const itinRes = await fetch(`/api/output/itinerary.html?_t=${_t}`);
      if (itinRes.ok) {
        itineraryResultEl.srcdoc = await itinRes.text();
        console.log("[AUTO-LOAD] ✅ Itinerary loaded from disk");
      }
    }

    // Load hotel bookings
    if (files.hotel_bookings && files.hotel_bookings.length > 0) {
      const htmlPromises = files.hotel_bookings.map(f =>
        fetch(`/api/output/${f}?_t=${_t}`).then(r => r.ok ? r.text() : "")
      );
      const htmls = await Promise.all(htmlPromises);
      const validHtmls = htmls.filter(h => h);
      if (validHtmls.length > 0) {
        renderHotelTabs(validHtmls);
        console.log(`[AUTO-LOAD] ✅ ${validHtmls.length} hotel booking(s) loaded from disk`);
      }
    }
    // Sync combined previews (Kết quả tab) after loading
    syncCombinedPreviews();
    console.log("[AUTO-LOAD] ✅ Combined previews synced");
  } catch (e) {
    console.log("[AUTO-LOAD] ⚠️ Could not load saved outputs:", e.message);
  }
})();

