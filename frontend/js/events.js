// Event Listeners
// Extracted from app.js

// ==================== EVENT LISTENERS ====================

if (refreshBtn) refreshBtn.addEventListener("click", fetchFiles);
if (loadStepsBtn) loadStepsBtn.addEventListener("click", loadSteps);
if (runItineraryBtn) runItineraryBtn.addEventListener("click", runItinerary);
if (runAllBtn) runAllBtn.addEventListener("click", runAll);
if (saveItineraryContextBtn) saveItineraryContextBtn.addEventListener("click", saveItineraryContext);
if (runBookingBtn) runBookingBtn.addEventListener("click", runBookingGeneration);
if (extractTripBtn) extractTripBtn.addEventListener("click", extractTripInfo);
if (saveTripInfoBtn) saveTripInfoBtn.addEventListener("click", saveTripInfo);
if (analyzeSampleV2Btn) analyzeSampleV2Btn.addEventListener("click", analyzeSampleLetterV2);
if (generateLetterV2Btn) generateLetterV2Btn.addEventListener("click", generateLetterV2);
if (runAIBookingHotelBtn) runAIBookingHotelBtn.addEventListener("click", () => runAIBooking("hotel"));
if (bookingModeHotelBtn) bookingModeHotelBtn.addEventListener("click", () => setBookingMode("hotel"));
if (bookingModeFlightBtn) bookingModeFlightBtn.addEventListener("click", () => setBookingMode("flight"));
if (loadClassifierFilesBtn) loadClassifierFilesBtn.addEventListener("click", loadClassifierFiles);
if (runClassifierBtn) runClassifierBtn.addEventListener("click", runClassifier);
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

if (exportHotelPdfBtn) exportHotelPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(hotelBookingResultEl, "Hotel Booking");
});

if (exportFlightPdfBtn) exportFlightPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(flightBookingResultEl, "Flight Booking");
});

if (exportItineraryPdfBtn) exportItineraryPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(itineraryResultEl, "Travel Itinerary");
});

if (exportCombinedItineraryPdfBtn) exportCombinedItineraryPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(combinedItineraryResultEl, "Travel Itinerary");
});

if (exportCombinedFlightPdfBtn) exportCombinedFlightPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(combinedFlightBookingResultEl, "Flight Booking");
});

if (exportCombinedHotelPdfBtn) exportCombinedHotelPdfBtn.addEventListener("click", () => {
  printIframeAsPdf(combinedHotelBookingResultEl, "Hotel Booking");
});

function buildCombinedHotelsHtml(htmls, autoPrint = false) {
  // Extract <style> blocks from HTML string
  const extractStyles = (html) => {
    const styles = [];
    const regex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
    let match;
    while ((match = regex.exec(html)) !== null) {
      styles.push(match[1]);
    }
    return styles.join("\n");
  };

  // Extract <body> content from HTML string
  const extractBody = (html) => {
    const match = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    return match ? match[1] : html;
  };

  // Scope CSS: prefix every selector with .hotel-N to avoid conflicts
  const scopeStyles = (css, scopeClass) => {
    let remaining = css;

    // Process @media blocks
    const mediaRegex = /@media\s+[^{]+\{([\s\S]*?\})\s*\}/g;
    let mediaMatch;
    const mediaBlocks = [];
    while ((mediaMatch = mediaRegex.exec(css)) !== null) {
      const inner = mediaMatch[1];
      const scoped = inner.replace(/([^{}@]+)\{([^{}]+)\}/g, (m, sel, body) => {
        const scopedSel = sel.split(',').map(s => {
          s = s.trim();
          if (!s || s.startsWith('@')) return s;
          if (s === 'body' || s === 'html') return '.' + scopeClass;
          return '.' + scopeClass + ' ' + s;
        }).join(', ');
        return scopedSel + '{' + body + '}';
      });
      mediaBlocks.push(mediaMatch[0].replace(mediaMatch[1], scoped));
    }

    // Remove @media from remaining
    remaining = remaining.replace(mediaRegex, '');

    // Scope remaining rules
    const scoped = remaining.replace(/([^{}@]+)\{([^{}]+)\}/g, (m, sel, body) => {
      const scopedSel = sel.split(',').map(s => {
        s = s.trim();
        if (!s || s.startsWith('@') || s.startsWith('/*')) return s;
        if (s === 'body' || s === 'html') return '.' + scopeClass;
        return '.' + scopeClass + ' ' + s;
      }).join(', ');
      return scopedSel + '{' + body + '}';
    });

    return scoped + '\n' + mediaBlocks.join('\n');
  };

  let allStyles = '';
  let allSections = '';

  (htmls || []).forEach((html, i) => {
    const scopeClass = 'hotel-' + i;
    const styles = extractStyles(html);
    const body = extractBody(html);

    allStyles += `
      /* Hotel ${i} styles */
      ${scopeStyles(styles, scopeClass)}
      .${scopeClass} .a4, .${scopeClass} .a4-page {
        min-height: auto !important;
        height: auto !important;
        page-break-after: auto !important;
      }
    `;

    const pageBreak = i > 0 ? 'page-break-before: always;' : '';
    allSections += `<div class="hotel-section ${scopeClass}" style="${pageBreak}">${body}</div>\n`;
  });

  const printScript = autoPrint ? `
    window.onload = function() {
      setTimeout(function() { window.print(); }, 400);
    };` : '';

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Hotel Bookings</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    ${autoPrint
      ? `body { background: #fff; margin: 0; padding: 0; }`
      : `body { background: #e5e7eb; margin: 0; padding: 20px 0; }`
    }
    @media print {
      @page { size: A4; margin: 10mm; }
      body { background: #fff !important; padding: 0 !important; }
      .hotel-section { box-shadow: none !important; margin: 0 !important; }
    }
    ${!autoPrint ? `
    .hotel-section {
      background: #fff;
      max-width: 800px;
      margin: 20px auto;
      box-shadow: 0 2px 12px rgba(0,0,0,0.15);
      border-radius: 2px;
      overflow: hidden;
    }
    ` : ''}
    ${allStyles}
  </style>
</head>
<body>
  ${allSections}
  <script>${printScript}<\/script>
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

  const combinedHtml = buildCombinedHotelsHtml(hotelHtmls, true);

  printWin.document.open();
  printWin.document.write(combinedHtml);
  printWin.document.close();
}

function printCombinedPackagePdf() {
  // Read from ORIGINAL individual result iframes (not combined preview)
  const itineraryDoc =
    itineraryResultEl?.contentDocument ||
    itineraryResultEl?.contentWindow?.document;
  const flightDoc =
    flightBookingResultEl?.contentDocument ||
    flightBookingResultEl?.contentWindow?.document;

  const hasItinerary = itineraryDoc?.body?.innerHTML?.trim();
  const hasFlight = flightDoc?.body?.innerHTML?.trim();
  const hasHotel = hotelHtmls && hotelHtmls.length > 0;

  if (!hasItinerary || !hasFlight || !hasHotel) {
    alert("Cần đủ 3 nội dung: lịch trình, booking máy bay, booking khách sạn.");
    return;
  }

  const printWin = window.open("", "_blank");
  if (!printWin) {
    alert("Trình duyệt đã chặn cửa sổ popup. Vui lòng cho phép popup rồi thử lại.");
    return;
  }

  // Extract <style> blocks from HTML string
  const extractStyles = (html) => {
    const styles = [];
    const regex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
    let match;
    while ((match = regex.exec(html)) !== null) {
      styles.push(match[1]);
    }
    return styles.join("\n");
  };

  // Extract <body> content from HTML string
  const extractBody = (html) => {
    const match = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    return match ? match[1] : html;
  };

  // Get full HTML from iframe document
  const getFullHtml = (doc) => {
    return doc.documentElement?.outerHTML || doc.body?.innerHTML || "";
  };

  // Scope CSS: prefix every selector with .doc-N to avoid conflicts
  const scopeStyles = (css, scopeClass) => {
    // Remove @media blocks first, process them separately
    let result = '';
    let remaining = css;

    // Process @media blocks
    const mediaRegex = /@media\s+[^{]+\{([\s\S]*?\})\s*\}/g;
    let mediaMatch;
    const mediaBlocks = [];
    while ((mediaMatch = mediaRegex.exec(css)) !== null) {
      const inner = mediaMatch[1];
      // Scope the inner rules
      const scoped = inner.replace(/([^{}@]+)\{([^{}]+)\}/g, (m, sel, body) => {
        const scopedSel = sel.split(',').map(s => {
          s = s.trim();
          if (!s || s.startsWith('@')) return s;
          if (s === 'body' || s === 'html') return '.' + scopeClass;
          return '.' + scopeClass + ' ' + s;
        }).join(', ');
        return scopedSel + '{' + body + '}';
      });
      mediaBlocks.push(mediaMatch[0].replace(mediaMatch[1], scoped));
    }

    // Remove @media from remaining
    remaining = remaining.replace(mediaRegex, '');

    // Scope remaining rules
    const scoped = remaining.replace(/([^{}@]+)\{([^{}]+)\}/g, (m, sel, body) => {
      const scopedSel = sel.split(',').map(s => {
        s = s.trim();
        if (!s || s.startsWith('@') || s.startsWith('/*')) return s;
        if (s === 'body' || s === 'html') return '.' + scopeClass;
        return '.' + scopeClass + ' ' + s;
      }).join(', ');
      return scopedSel + '{' + body + '}';
    });

    return scoped + '\n' + mediaBlocks.join('\n');
  };

  // Build sections from all documents
  const docHtmls = [
    getFullHtml(itineraryDoc),
    getFullHtml(flightDoc),
    ...hotelHtmls
  ];

  let allStyles = '';
  let allSections = '';

  docHtmls.forEach((html, i) => {
    const scopeClass = 'doc-' + i;
    const styles = extractStyles(html);
    const body = extractBody(html);

    // Scope the CSS and add print overrides
    allStyles += `
      /* Document ${i} styles */
      ${scopeStyles(styles, scopeClass)}
      .${scopeClass} .a4, .${scopeClass} .a4-page {
        min-height: auto !important;
        height: auto !important;
        page-break-after: auto !important;
      }
    `;

    const pageBreak = i > 0 ? 'page-break-before: always;' : '';
    allSections += `<div class="${scopeClass}" style="${pageBreak}">${body}</div>\n`;
  });

  const combinedHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Combined Package PDF</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #fff; margin: 0; padding: 0; }
    @media print {
      @page { size: A4; margin: 10mm; }
    }
    ${allStyles}
  </style>
</head>
<body>
  ${allSections}
</body>
</html>`;

  printWin.document.open();
  printWin.document.write(combinedHtml);
  printWin.document.close();

  printWin.onload = () => {
    setTimeout(() => { printWin.print(); }, 500);
  };
  setTimeout(() => { printWin.print(); }, 1000);
}

if (exportAllHotelPdfBtn) exportAllHotelPdfBtn.addEventListener("click", printAllHotelsAsPdf);
if (exportCombinedAllPdfBtn) exportCombinedAllPdfBtn.addEventListener("click", printCombinedPackagePdf);

if (stepsListEl) {
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
}

if (stepsListEl) {
  stepsListEl.addEventListener("input", (event) => {
    const target = event.target;
    if (target && target.id === "writerContext") {
      writerContextCache = target.value || "";
    }
  });
}

if (hotelBookingTabsEl) {
  hotelBookingTabsEl.addEventListener("click", (event) => {
    const btn = event.target.closest(".hotel-tab-btn");
    if (!btn) return;
    const index = parseInt(btn.dataset.index);
    showHotelTab(index);
  });
}

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
});

if (addTranslateFlowBtn) {
  addTranslateFlowBtn.addEventListener("click", async () => {
    await loadTranslationTemplates();
    createTranslateFlow();
  });
}
if (addTranslateFlowBtnFallback) {
  addTranslateFlowBtnFallback.addEventListener("click", async () => {
    await loadTranslationTemplates();
    createTranslateFlow();
  });
}
if (bulkCheckBtn) {
  bulkCheckBtn.addEventListener("click", () => runBulkBilingualCheck());
}
if (bulkCreateStreamsBtn) {
  bulkCreateStreamsBtn.addEventListener("click", () => bulkCreateTranslateStreams());
}
if (bulkTranslateAllBtn) {
  bulkTranslateAllBtn.addEventListener("click", () => runTranslateAll());
}
if (bulkPrintAllPdfBtn) {
  bulkPrintAllPdfBtn.addEventListener("click", () => printAllTranslationFlows());
}

// Workspace-based translation events
if (workspaceScanBtn) {
  workspaceScanBtn.addEventListener("click", () => runWorkspaceScan());
}
if (workspaceScanAllBtn) {
  workspaceScanAllBtn.addEventListener("click", () => runAllWorkspacesScan());
}
if (refreshWorkspacesBtn) {
  refreshWorkspacesBtn.addEventListener("click", () => loadTranslationWorkspaces());
}
if (markCompleteBtn) {
  markCompleteBtn.addEventListener("click", () => markWorkspaceComplete());
}

window.addEventListener("load", async () => {
  setActiveTab("precheck");

  // Keep boot resilient: one failing task must not block the rest.
  const safeAwait = async (label, fn) => {
    try {
      await fn();
    } catch (e) {
      console.warn(`[boot] ${label} failed:`, e);
    }
  };

  await safeAwait("fetchFiles", () => fetchFiles());
  await safeAwait("loadSteps", () => loadSteps());
  await safeAwait("loadLatestBooking", () => loadLatestBooking());
  await safeAwait("loadLatestTripInfo", () => loadLatestTripInfo());
  await safeAwait("loadDestinations", () => loadDestinations());
  await safeAwait("loadClassifierFiles", () => loadClassifierFiles());
  await safeAwait("initTranslationSection", () => initTranslationSection());
  await safeAwait("loadLatestLetterV2", () => loadLatestLetterV2());

  try {
    initSerpFlightUI();
  } catch (e) {
    console.warn("[boot] initSerpFlightUI failed:", e);
  }
  try {
    setBookingMode("hotel");
  } catch (e) {
    console.warn("[boot] setBookingMode failed:", e);
  }
  try {
    syncCombinedPreviews();
  } catch (e) {
    console.warn("[boot] syncCombinedPreviews failed:", e);
  }

  await safeAwait("loadOutputHistory", () => loadOutputHistory());
  await safeAwait("checkDriveFolderStatus", () => checkDriveFolderStatus()); // Show Push-to-Drive button if Drive folders exist
  await safeAwait("loadTranslationWorkspaces", () => loadTranslationWorkspaces()); // Load workspace dropdown
});


// ==================== PIPELINE BUTTON LISTENERS ====================
const sendToInputBtn = document.getElementById("sendToInputBtn");
if (sendToInputBtn) {
  sendToInputBtn.addEventListener("click", sendToInput);
}

// Pre-check / Process button listeners
const precheckScanBtn = document.getElementById("precheckScanBtn");
if (precheckScanBtn) {
  precheckScanBtn.addEventListener("click", precheckScan);
}
const applyRenameBtn = document.getElementById("applyRenameBtn");
if (applyRenameBtn) {
  applyRenameBtn.addEventListener("click", applyRename);
}
const sendMultiToSplitterBtn = document.getElementById("sendMultiToSplitterBtn");
if (sendMultiToSplitterBtn) {
  sendMultiToSplitterBtn.addEventListener("click", sendMultiToSplitter);
}
const pushToDriveBtn = document.getElementById("pushToDriveBtn");
if (pushToDriveBtn) {
  pushToDriveBtn.addEventListener("click", pushPipelineToDrive);
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

