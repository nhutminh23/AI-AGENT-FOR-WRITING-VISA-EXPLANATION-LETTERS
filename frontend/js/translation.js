/**
 * Inject print-preview CSS so the iframe looks like the actual printed output.
 * Shows paginated A4 pages with visible boundaries, gaps between pages,
 * and page-break behavior identical to the browser's print dialog.
 */
function wrapForPrintPreview(html) {
  if (!html) return html;
  // These MUST match the @page content-page margin in the print functions
  // @page content-page { margin: 15mm 18mm; size: A4; }
  const PAGE_MARGIN_TB = '15mm';  // top/bottom @page margin
  const PAGE_MARGIN_LR = '18mm';  // left/right @page margin
  const printPreviewCSS = `<style data-print-preview>
    /* ===== PAGINATED A4 PREVIEW (synced with print output) ===== */
    body {
      background: #d1d5db !important;
      margin: 0 !important;
      padding: 20px 0 !important;
      display: flex !important;
      flex-direction: column !important;
      align-items: center !important;
    }
    .a4-page, .a4 {
      width: 210mm !important;
      min-height: 297mm !important;
      height: auto !important;
      margin: 0 auto 24px auto !important;
      /*
       * CRITICAL: padding MUST match the @page content-page margin.
       * In print, @page handles per-page margins and .a4-page padding = 0.
       * In preview, we simulate it with padding so vùng nội dung = y hệt.
       */
      padding: ${PAGE_MARGIN_TB} ${PAGE_MARGIN_LR} !important;

      background-color: #fff !important;
      /* Draw a red line every 297mm to show exact physical page breaks */
      background-image: repeating-linear-gradient(
        to bottom,
        transparent,
        transparent calc(297mm - 2px),
        #ef4444 calc(297mm - 2px),
        #ef4444 297mm
      ) !important;

      box-sizing: border-box !important;
      box-shadow: 0 2px 12px rgba(0,0,0,0.18) !important;
      overflow: visible !important;
      position: relative !important;
      page-break-after: always !important;
      break-after: page !important;
    }
    .a4-page:last-child, .a4:last-child {
      margin-bottom: 20px !important;
    }
  </style>`;
  // Insert right before </head> if exists, otherwise before </html> or at end
  if (html.includes('</head>')) {
    return html.replace('</head>', printPreviewCSS + '\n</head>');
  } else if (html.includes('</html>')) {
    return html.replace('</html>', printPreviewCSS + '\n</html>');
  }
  return html + printPreviewCSS;
}

async function loadTranslationTemplates() {
  const res = await fetch("/api/translate/templates");
  const data = await res.json();
  translationTemplatesCache = data.templates || [];
}

// ==================== DB PERSISTENCE HELPERS ====================

/** Save or update a translation flow to the database. */
async function autoSaveTranslationFlow(flowId) {
  try {
    const filename = document.getElementById(`transUploadedName-${flowId}`)?.value || "";
    const fileRef = document.getElementById(`transUploadedRef-${flowId}`)?.value || "";
    const templateName = document.getElementById(`transTemplate-${flowId}`)?.value || "auto";
    const sourceLang = document.getElementById(`transSourceLang-${flowId}`)?.value || "vi";
    const ocrText = document.getElementById(`transOcr-${flowId}`)?.value || "";
    const translatedText = document.getElementById(`transTranslated-${flowId}`)?.value || "";
    const htmlContent = document.getElementById(`transHtmlSource-${flowId}`)?.value || "";
    const saveName = document.getElementById(`transSaveName-${flowId}`)?.value || "";
    const payload = { filename, file_ref: fileRef, template_name: templateName,
      source_lang: sourceLang, ocr_text: ocrText, translated_text: translatedText,
      html_content: htmlContent, save_name: saveName, status: "done" };

    const dbId = _flowDbIds[flowId];
    if (dbId) {
      // Update existing
      await fetch(`/api/translate/flows/${dbId}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      // Create new
      const res = await fetch("/api/translate/flows", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const saved = await res.json();
        _flowDbIds[flowId] = saved.id;
      }
    }
  } catch (e) {
    // Silent — don't block the user workflow for a save failure
  }
}

/** Delete a single translation flow from UI and DB. */
async function deleteTranslationFlow(flowId) {
  const card = document.getElementById(`translateFlow-${flowId}`);
  if (card) card.remove();
  const dbId = _flowDbIds[flowId];
  if (dbId) {
    try { await fetch(`/api/translate/flows/${dbId}`, { method: "DELETE" }); } catch (_) {}
    delete _flowDbIds[flowId];
  }
  // Reset counter when all flows are deleted individually
  if (translateFlowsContainerEl && translateFlowsContainerEl.querySelectorAll(".translate-flow-card").length === 0) {
    translationFlowCounter = 0;
  }
}

/** Delete all translation flows from UI and DB. */
async function deleteAllTranslationFlows() {
  if (!confirm("Xóa tất cả luồng dịch? Hành động này không thể hoàn tác.")) return;
  if (translateFlowsContainerEl) translateFlowsContainerEl.innerHTML = "";
  try { await fetch("/api/translate/flows", { method: "DELETE" }); } catch (_) {}
  Object.keys(_flowDbIds).forEach(k => delete _flowDbIds[k]);
  translationFlowCounter = 0;  // Reset counter so next flow starts at #1
}

/** Restore saved flows from DB on page load. */
async function restoreTranslationFlows() {
  try {
    const res = await fetch("/api/translate/flows");
    if (!res.ok) return;
    const { flows } = await res.json();
    if (!flows || flows.length === 0) return;
    for (const f of flows) {
      // createTranslateFlow increments translationFlowCounter internally
      createTranslateFlow();
      const flowId = translationFlowCounter;  // grab the id it just created
      _flowDbIds[flowId] = f.id;
      // Populate fields from DB data
      const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
      set(`transUploadedName-${flowId}`, f.filename);
      set(`transUploadedRef-${flowId}`, f.file_ref);
      set(`transTemplate-${flowId}`, f.template_name);
      set(`transSourceLang-${flowId}`, f.source_lang);
      set(`transOcr-${flowId}`, f.ocr_text);
      set(`transTranslated-${flowId}`, f.translated_text);
      set(`transHtmlSource-${flowId}`, f.html_content);
      set(`transSaveName-${flowId}`, f.save_name);
      // Show file info
      if (f.filename) {
        const fileInfoEl = document.getElementById(`transFileInfo-${flowId}`);
        if (fileInfoEl) fileInfoEl.innerHTML = `📄 <b>${escapeHtml(f.filename)}</b> <span style="color:#16a34a;">✅ (đã lưu)</span>`;
      }
      // Render HTML preview
      if (f.html_content) {
        const previewEl = document.getElementById(`transPreview-${flowId}`);
        if (previewEl) previewEl.srcdoc = wrapForPrintPreview(f.html_content);
      }
      // Update status indicator
      const statusEl = document.getElementById(`transStatus-${flowId}`);
      if (statusEl && f.status === "done") {
        statusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã khôi phục từ lần dịch trước.</span>`;
      }
      // Show reattach button (file object is always lost after F5)
      if (f.filename) {
        const reattachBtn = document.getElementById(`transReattachBtn-${flowId}`);
        if (reattachBtn) reattachBtn.style.display = "inline-block";
      }
    }
  } catch (e) {
    // Silent — don't block init
  }
}

async function loadTranslationSourceFiles() {
  const inputDir = (inputDirEl?.value || "").trim() || "input";
  const res = await fetch(`/api/files?input_dir=${encodeURIComponent(inputDir)}`);
  const data = await res.json();
  translationSourceFilesCache = data.files || [];
}

function translationTemplateOptionsHtml(selectedName = "auto") {
  let html = `<option value="auto" ${selectedName === "auto" ? "selected" : ""}>🤖 Tự động nhận diện</option>`;
  if (translationTemplatesCache.length) {
    html += translationTemplatesCache
      .map((tpl) => {
        const sel = tpl.name === selectedName ? "selected" : "";
        return `<option value="${escapeHtml(tpl.name)}" ${sel}>${escapeHtml(tpl.name)}</option>`;
      })
      .join("");
  }
  return html;
}

function translationFileOptionsHtml(selectedValue = "") {
  const options = ['<option value="">-- Chọn file cần dịch --</option>'];
  for (const f of translationSourceFilesCache) {
    const value = f.rel_path || f.name || "";
    const sel = value === selectedValue ? "selected" : "";
    options.push(
      `<option value="${escapeHtml(value)}" ${sel}>${escapeHtml(value)}</option>`
    );
  }
  return options.join("");
}

function updateTranslateFlowStep(flowId, step, state, message = "") {
  const iconEl = document.getElementById(`transStepIcon-${flowId}-${step}`);
  const msgEl = document.getElementById(`transStepMsg-${flowId}-${step}`);
  const rowEl = document.getElementById(`transStepRow-${flowId}-${step}`);
  if (!iconEl || !msgEl || !rowEl) return;

  if (state === "running") {
    iconEl.textContent = "⏳";
    rowEl.style.background = "#fffbeb";
    rowEl.style.borderColor = "#fcd34d";
    msgEl.textContent = message || "Đang xử lý...";
    msgEl.style.color = "#d97706";
  } else if (state === "done") {
    iconEl.textContent = "✅";
    rowEl.style.background = "#f0fdf4";
    rowEl.style.borderColor = "#86efac";
    msgEl.textContent = message || "Xong";
    msgEl.style.color = "#16a34a";
  } else if (state === "error") {
    iconEl.textContent = "❌";
    rowEl.style.background = "#fef2f2";
    rowEl.style.borderColor = "#fca5a5";
    msgEl.textContent = message || "Lỗi";
    msgEl.style.color = "#dc2626";
  } else {
    iconEl.textContent = "⬜";
    rowEl.style.background = "#fff";
    rowEl.style.borderColor = "#e2e8f0";
    msgEl.textContent = "";
    msgEl.style.color = "#94a3b8";
  }
}

function createTranslateFlow() {
  if (!translateFlowsContainerEl) return;
  translationFlowCounter += 1;
  const flowId = translationFlowCounter;
  const html = `
    <section class="translate-flow-card" id="translateFlow-${flowId}" style="border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:16px; background:#fff;">
      <div class="card-header-row" style="display:flex; justify-content:space-between; align-items:center;">
        <h3 style="margin:0;">Luồng dịch #${flowId}</h3>
        <button id="transDeleteBtn-${flowId}" type="button" title="Xóa luồng dịch này" style="background:#ef4444; color:#fff; border:none; border-radius:6px; padding:4px 10px; cursor:pointer; font-size:0.85em;">🗑️ Xóa</button>
      </div>

      <!-- Upload row -->
      <div class="row" style="margin-top:10px;">
        <div>
          <label for="transUpload-${flowId}">Upload file cần dịch</label>
          <div style="display:flex; gap:8px; align-items:center; margin-top:6px; flex-wrap:wrap;">
            <input id="transUpload-${flowId}" type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.webp,.txt,.doc,.docx" />
            <button id="transUploadBtn-${flowId}" type="button" style="padding:8px 14px; background:#4f46e5;">📤 Upload</button>
          </div>
          <input id="transUploadedRef-${flowId}" type="hidden" value="" />
          <input id="transUploadedName-${flowId}" type="hidden" value="" />
          <div style="display:flex; align-items:center; gap:8px; margin-top:6px;">
            <div id="transFileInfo-${flowId}" style="font-size:0.85em; color:#64748b;"></div>
            <input id="transReattachInput-${flowId}" type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.webp" style="display:none;" />
            <button id="transReattachBtn-${flowId}" type="button" title="Gắn lại file gốc (nếu bị mất sau F5)" style="display:none; background:#f59e0b; color:#fff; border:none; border-radius:4px; padding:3px 10px; cursor:pointer; font-size:0.8em;">🔄 Gắn lại file gốc</button>
          </div>
        </div>
        <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
          <div>
            <label for="transSourceLang-${flowId}" style="font-size:0.85em; display:block; margin-bottom:4px;">Ngôn ngữ nguồn</label>
            <select id="transSourceLang-${flowId}" style="padding:6px 10px; border-radius:6px; border:1px solid #cbd5e1; font-size:0.85em;">
              <option value="tiếng Việt" selected>🇻🇳 Tiếng Việt</option>
              <option value="tiếng Trung">🇨🇳 Tiếng Trung</option>
              <option value="tiếng Nhật">🇯🇵 Tiếng Nhật</option>
              <option value="tiếng Hàn">🇰🇷 Tiếng Hàn</option>
              <option value="tiếng Pháp">🇫🇷 Tiếng Pháp</option>
              <option value="ngôn ngữ gốc (tự nhận diện)">🌐 Tự nhận diện</option>
            </select>
          </div>
          <div>
            <label for="transTemplate-${flowId}" style="font-size:0.85em; display:block; margin-bottom:4px;">HTML template</label>
            <select id="transTemplate-${flowId}" style="padding:6px 10px; border-radius:6px; border:1px solid #cbd5e1; font-size:0.85em;">${translationTemplateOptionsHtml("auto")}</select>
          </div>
        </div>
        <button id="transRunBtn-${flowId}" style="background:#2563eb; align-self:flex-end;">🚀 OCR + Dịch + Tạo HTML</button>
      </div>

      <div class="translate-status" id="transStatus-${flowId}" style="margin-top:8px; padding:6px; font-size:0.9em;">Chưa chạy.</div>

      <!-- Progress steps -->
      <div style="margin-top:8px;">
        <div id="transStepRow-${flowId}-1" style="display:flex; gap:8px; align-items:center; border:1px solid #e2e8f0; border-radius:6px; padding:6px 8px; margin-bottom:4px;">
          <span id="transStepIcon-${flowId}-1">⬜</span>
          <span style="font-size:0.9em; color:#475569;">OCR + Dịch sang tiếng Anh</span>
          <span id="transStepMsg-${flowId}-1" style="margin-left:auto; font-size:0.8em; color:#94a3b8;"></span>
        </div>
        <div id="transStepRow-${flowId}-2" style="display:flex; gap:8px; align-items:center; border:1px solid #e2e8f0; border-radius:6px; padding:6px 8px;">
          <span id="transStepIcon-${flowId}-2">⬜</span>
          <span style="font-size:0.9em; color:#475569;">Tạo HTML theo template</span>
          <span id="transStepMsg-${flowId}-2" style="margin-left:auto; font-size:0.8em; color:#94a3b8;"></span>
        </div>
      </div>

      <!-- OCR + Translation textareas (collapsed) -->
      <details style="margin-top:12px;">
        <summary style="cursor:pointer; font-weight:600; font-size:0.9em; color:#64748b;">📄 Văn bản OCR & Bản dịch (ấn để xem)</summary>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:8px;">
          <div>
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
              <label style="font-weight:600; font-size:0.9em;">🧾 Văn bản OCR</label>
              <button type="button" class="trans-copy-btn" data-target="transOcr-${flowId}" style="padding:2px 8px; font-size:0.8em; background:#64748b; border:none; color:#fff; border-radius:4px; cursor:pointer;">📋 Copy</button>
            </div>
            <textarea id="transOcr-${flowId}" style="width:100%; min-height:180px; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:0.85em; font-family:monospace; resize:vertical;" placeholder="Chưa có dữ liệu OCR..."></textarea>
          </div>
          <div>
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
              <label style="font-weight:600; font-size:0.9em;">🌐 Bản dịch tiếng Anh</label>
              <button type="button" class="trans-copy-btn" data-target="transTranslated-${flowId}" style="padding:2px 8px; font-size:0.8em; background:#64748b; border:none; color:#fff; border-radius:4px; cursor:pointer;">📋 Copy</button>
            </div>
            <textarea id="transTranslated-${flowId}" style="width:100%; min-height:180px; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:0.85em; font-family:monospace; resize:vertical;" placeholder="Chưa có bản dịch..."></textarea>
          </div>
        </div>
      </details>



      <!-- HTML Source Editor (expanded by default) -->
      <div style="margin-top:12px;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
          <label style="font-weight:600; font-size:0.9em;">✏️ Sửa HTML source code</label>
          <div style="display:flex; gap:6px;">
            <button id="transCopyPromptBtn-${flowId}" type="button" style="background:#8b5cf6; padding:4px 12px; font-size:0.85em; color:#fff; border:none; border-radius:4px; cursor:pointer;" title="Copy Prompt + Code để check AI">🤖 Prompt Check AI</button>
            <button id="transApplyHtmlBtn-${flowId}" type="button" style="background:#0ea5e9; padding:4px 12px; font-size:0.85em;">▶️ Áp dụng</button>
            <button type="button" class="trans-copy-btn" data-target="transHtmlSource-${flowId}" style="padding:4px 12px; font-size:0.85em; background:#64748b; border:none; color:#fff; border-radius:4px; cursor:pointer;">📋 Copy</button>
          </div>
        </div>
        <textarea id="transHtmlSource-${flowId}" style="width:100%; min-height:300px; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:0.82em; font-family:monospace; resize:vertical;" placeholder="HTML source code sẽ hiện ở đây sau khi tạo..."></textarea>
      </div>

      <!-- Save row -->
      <div class="row" style="margin-top:12px; align-items:center;">
        <div style="flex:1;">
          <label for="transSaveName-${flowId}">Tên file lưu</label>
          <input id="transSaveName-${flowId}" type="text" placeholder="VD: khai-sinh-da-dich.html" style="width:100%;" />
        </div>
        <button id="transSaveHtmlBtn-${flowId}" type="button" style="background:#16a34a; padding:8px 14px;">💾 Lưu HTML</button>
        <button id="transSavePdfBtn-${flowId}" type="button" style="background:#dc2626; padding:8px 14px;">📥 Lưu PDF</button>
      </div>

      <!-- HTML Preview iframe -->
      <div style="margin-top:12px;">
        <label style="font-weight:600;">Kết quả HTML</label>
        <iframe id="transPreview-${flowId}" style="width:100%; height:85vh; border:1px solid #cbd5e1; border-radius:6px; margin-top:4px; background:#f8fafc;" title="Translation HTML Preview"></iframe>
      </div>
    </section>
  `;
  translateFlowsContainerEl.insertAdjacentHTML("beforeend", html);

  // Event listeners
  const runBtn = document.getElementById(`transRunBtn-${flowId}`);
  if (runBtn) runBtn.addEventListener("click", () => runTranslateFlow(flowId));

  const uploadBtn = document.getElementById(`transUploadBtn-${flowId}`);
  if (uploadBtn) uploadBtn.addEventListener("click", () => uploadTranslateFile(flowId));

  const saveBtn = document.getElementById(`transSaveHtmlBtn-${flowId}`);
  if (saveBtn) saveBtn.addEventListener("click", () => saveTranslateHtml(flowId));

  // Delete flow button
  const deleteBtn = document.getElementById(`transDeleteBtn-${flowId}`);
  if (deleteBtn) deleteBtn.addEventListener("click", () => deleteTranslationFlow(flowId));

  // Reattach original file button (manual fallback)
  const reattachBtn = document.getElementById(`transReattachBtn-${flowId}`);
  const reattachInput = document.getElementById(`transReattachInput-${flowId}`);
  if (reattachBtn && reattachInput) {
    reattachBtn.addEventListener("click", () => reattachInput.click());
    reattachInput.addEventListener("change", () => {
      const file = reattachInput.files && reattachInput.files[0];
      if (!file) return;
      _transOriginalFiles[flowId] = file;
      reattachBtn.style.display = "none";
      const fileInfoEl = document.getElementById(`transFileInfo-${flowId}`);
      if (fileInfoEl) {
        fileInfoEl.innerHTML = `📄 <b>${escapeHtml(file.name)}</b> <span style="color:#16a34a;">✅ Đã gắn lại file gốc</span>`;
      }
    });
  }

  const applyHtmlBtn = document.getElementById(`transApplyHtmlBtn-${flowId}`);
  if (applyHtmlBtn) {
    applyHtmlBtn.addEventListener("click", () => {
      const srcEl = document.getElementById(`transHtmlSource-${flowId}`);
      const previewEl = document.getElementById(`transPreview-${flowId}`);
      if (srcEl && previewEl) previewEl.srcdoc = wrapForPrintPreview(srcEl.value);
      // Auto-save to DB after applying edits
      autoSaveTranslationFlow(flowId);
    });
  }

  // AI Prompt Double Check button
  const copyPromptBtn = document.getElementById(`transCopyPromptBtn-${flowId}`);
  if (copyPromptBtn) {
    copyPromptBtn.addEventListener("click", () => {
      const srcEl = document.getElementById(`transHtmlSource-${flowId}`);
      if (!srcEl || !srcEl.value) {
        alert("Chưa có code HTML để copy prompt.");
        return;
      }
      
      const promptText = `You are an Expert Translator and a Pixel-Perfect UI/UX Developer specializing in official government and legal documents. 

My goal is to submit a translated document to the Consulate. It must be 100% accurate in content, meaning NO translation errors, NO omitted/missing text, and the layout must structurally mirror the original document perfectly so the Consulate officer can cross-reference it easily.

I am attaching:
1. The ORIGINAL DOCUMENT (Image/PDF).
2. The CURRENT HTML DRAFT of the translation (pasted below).

YOUR TASKS:
Step 1: Deep Content Audit (Zero Data Loss)
- Scan every single word, number, date, stamp, and signature in the original document.
- Compare it against the HTML draft. 
- Did the previous AI miss anything? (Headers, footers, microscopic text, stamps, table cells). If yes, TRANSLATE AND ADD IT BACK. Do not cut corners. Do not summarize. Maintain 100% completeness.
- Are the translations of legal terms, names, and numbers entirely accurate? If not, fix them.

Step 2: Structural & Layout Audit
- Does the HTML layout visually match the original document? (e.g., tables, left/right alignments, bold/italic text, spacing).
- Fix any broken table structures or misaligned text so the translated HTML looks like a carbon copy of the original PDF. Keep the existing CSS structure intact, just fix the HTML elements and inline alignment if necessary.

Step 3: Final Output
- Output the ENTIRE, fully corrected, full-page HTML code. 
- Do not use placeholders like "<!-- rest of code here -->". I need the full copy-pasteable HTML.
- Return the code strictly inside an \`\`\`html markup block.

--- CURRENT HTML DRAFT ---
${srcEl.value}`;

      navigator.clipboard.writeText(promptText).then(() => {
        const originalText = copyPromptBtn.innerText;
        copyPromptBtn.innerText = "✔️ Đã copy Prompt!";
        setTimeout(() => copyPromptBtn.innerText = originalText, 2000);
      }).catch(err => {
        console.error("Failed to copy:", err);
        alert("Trình duyệt không hỗ trợ copy tự động, vui lòng tự dán ra.");
      });
    });
  }


  const savePdfBtn = document.getElementById(`transSavePdfBtn-${flowId}`);
  if (savePdfBtn) {
    savePdfBtn.addEventListener("click", async () => {
      const previewEl = document.getElementById(`transPreview-${flowId}`);

      if (!previewEl || !previewEl.srcdoc) {
        alert("Chưa có bản dịch để xuất PDF.");
        return;
      }

      // Show loading state
      const origText = savePdfBtn.textContent;
      savePdfBtn.disabled = true;
      savePdfBtn.textContent = "⏳ Đang chuẩn bị PDF...";

      try {
        // Get stored original File object (try cache first, then fallback to input)
        let originalFile = (window._transOriginalFiles || {})[flowId];
        if (!originalFile) {
          const inputEl = document.getElementById(`transUpload-${flowId}`);
          if (inputEl && inputEl.files && inputEl.files[0]) {
            originalFile = inputEl.files[0];
          }
        }

        // Fetch original pages (POST file directly) + certification template concurrently
        let origFetch = Promise.resolve(null);
        if (originalFile) {
          const fd = new FormData();
          fd.append("file", originalFile);
          origFetch = fetch("/api/translate/original_pages", { method: "POST", body: fd });
        } else {
          // Fallback: use file_ref (for restored flows after F5)
          const fileRefEl = document.getElementById(`transUploadedRef-${flowId}`);
          const fileRef = fileRefEl?.value?.trim();
          if (fileRef) {
            origFetch = fetch("/api/translate/original_pages_by_ref", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ file_ref: fileRef }),
            });
          }
        }
        const [origRes, certRes] = await Promise.all([
          origFetch,
          fetch("/api/translate/certification_template")
        ]);

        // --- Part 1: Original document pages as images ---
        let originalPagesHtml = "";
        if (origRes && origRes.ok) {
          const origData = await origRes.json();
          if (origData.pages && origData.pages.length > 0) {
            originalPagesHtml = origData.pages.map((p, i) => {
              return `<div class="original-page">
                <img src="${p.data_url}" style="width:100%; height:auto; display:block;" />
              </div>`;
            }).join("\n");
          }
        } else if (origRes && !origRes.ok) {
          const errBody = await origRes.text().catch(() => "");
          console.warn("[CombinedPDF] Original pages fetch failed:", origRes.status, errBody);
          // Don't block PDF — just warn user
          if (!confirm("⚠️ Không lấy được ảnh gốc (file có thể đã bị xóa hoặc server restart).\n\nBấm OK để tiếp tục xuất PDF chỉ có bản dịch + xác nhận.\nBấm Cancel để hủy.")) {
            savePdfBtn.disabled = false;
            savePdfBtn.textContent = origText;
            return;
          }
        } else {
          console.warn("[CombinedPDF] No original file available (null response). PDF will only contain translation + cert.");
        }

        // --- Part 2: Translated HTML — prefer textarea source (user may have edited) ---
        const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
        const translatedHtml = (htmlSrcEl?.value?.trim()) || previewEl.srcdoc || "";

        // --- Part 3: Certification template with current date ---
        let certHtml = "";
        if (certRes && certRes.ok) {
          const certData = await certRes.json();
          certHtml = certData.html || "";
          // Replace hardcoded date with current date (DD/MM/YYYY)
          const now = new Date();
          const dd = String(now.getDate()).padStart(2, "0");
          const mm = String(now.getMonth() + 1).padStart(2, "0");
          const yyyy = now.getFullYear();
          const currentDate = `${dd}/${mm}/${yyyy}`;
          // Replace the date in the template (pattern: Date: DD/MM/YYYY)
          certHtml = certHtml.replace(/Date:\s*\d{2}\/\d{2}\/\d{4}/, `Date: ${currentDate}`);
        }

        // --- Extract styles and body from translated HTML ---
        const extractStyles = (html) => {
          const styles = [];
          const regex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
          let m;
          while ((m = regex.exec(html)) !== null) styles.push(m[1]);
          return styles.join("\n");
        };
        const extractBody = (html) => {
          const m = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
          return m ? m[1] : html;
        };

        // Scope CSS to avoid conflicts
        const scopeStyles = (css, scopeClass) => {
          // Properties that must be stripped from body/html scoped rules
          const bodyStripProps = /\b(display|padding|margin|background[^:]*|justify-content|align-items|min-height|height|overflow|gap|flex-direction)\s*:[^;]+;?/gi;
          // 1) Strip @page rules (outer container handles them)
          let cleaned = css.replace(/@page\s*\{[^}]*\}/gi, "");
          // 2) Strip @media print blocks (outer handles print; nested {} breaks regex)
          cleaned = cleaned.replace(/@media\s+print\s*\{[\s\S]*?\}\s*\}/gi, "");
          // 3) Scope remaining simple rules
          return cleaned.replace(/([^{}@]+)\{([^{}]+)\}/g, (match, sel, body) => {
            let isBodyRule = false;
            const scopedSel = sel.split(",").map(s => {
              s = s.trim();
              if (!s || s.startsWith("@") || s.startsWith("/*")) return s;
              if (s === "body" || s === "html") { isBodyRule = true; return "." + scopeClass; }
              return "." + scopeClass + " " + s;
            }).join(", ");
            const cleanBody = isBodyRule ? body.replace(bodyStripProps, "") : body;
            return scopedSel + "{" + cleanBody + "}";
          });
        };

        // Build combined sections
        let allStyles = "";
        let allSections = "";

        // Section 1: Original pages (just images, no special CSS needed)
        if (originalPagesHtml) {
          allSections += `<div class="doc-section doc-original">${originalPagesHtml}</div>\n`;
        }

        // Section 2: Translated document (scoped CSS)
        if (translatedHtml) {
          const transStyles = extractStyles(translatedHtml);
          const transBody = extractBody(translatedHtml);
          allStyles += `/* Translated doc styles */\n${scopeStyles(transStyles, "doc-translated")}\n`;
          allStyles += `.doc-translated .a4, .doc-translated .a4-page { min-height: auto !important; height: auto !important; }\n`;
          allSections += `<div class="doc-section doc-translated">${transBody}</div>\n`;
        }

        // Section 3: Certification page (scoped CSS)
        if (certHtml) {
          const certStyles = extractStyles(certHtml);
          const certBody = extractBody(certHtml);
          allStyles += `/* Certification styles */\n${scopeStyles(certStyles, "doc-cert")}\n`;
          allStyles += `.doc-cert .a4-page { min-height: auto !important; height: auto !important; }\n`;
          allSections += `<div class="doc-section doc-cert">${certBody}</div>\n`;
        }

        // Build final combined HTML
        const combinedHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Combined Translation PDF</title>
  <style>
    html, body { background: #fff !important; margin: 0; padding: 0; }
    body { display: block !important; }
    .doc-section { display: block !important; width: 100% !important; background: #fff !important; }
    .doc-section + .doc-section { page-break-before: always; }
    .original-page { display: block; width: 100%; }
    .original-page + .original-page { page-break-before: always; }
    .original-page img { width: 100%; height: auto; display: block; }

    /* Named page: only TRANSLATED docs get @page margins (cert keeps its own padding) */
    @page { margin: 0; size: A4; }
    @page content-page { margin: 15mm 18mm; size: A4; }
    .doc-translated { page: content-page; }

    @media print {
      body { margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .doc-section { background: #fff !important; }
      .original-page { height: 100vh; display: flex; align-items: center; justify-content: center; }
      .original-page + .original-page { page-break-before: always; }
      .original-page img { max-height: 100vh; max-width: 100vw; height: auto; width: auto; }
      /* @page margin handles spacing for translated docs, so remove their padding */
      .doc-translated .a4, .doc-translated .a4-page {
        margin: 0 !important; padding: 0 !important; width: 100% !important;
        box-shadow: none !important; border: none !important;
        min-height: auto !important; height: auto !important;
        overflow: visible !important; background: #fff !important;
      }
      /* Cert keeps its own padding — only strip visual chrome */
      .doc-cert .a4, .doc-cert .a4-page {
        margin: 0 !important; box-shadow: none !important; border: none !important;
        min-height: auto !important; height: auto !important;
        overflow: visible !important; background: #fff !important;
      }
    }
    ${allStyles}
  </style>
</head>
<body>
  ${allSections}
</body>
</html>`;


        const printWin = window.open("", "_blank");
        if (!printWin) {
          alert("Trình duyệt chặn popup. Vui lòng cho phép popup rồi thử lại.");
          return;
        }
        printWin.document.open();
        printWin.document.write(combinedHtml);
        printWin.document.close();

        // Wait for ALL images to load before printing
        const allImgs = printWin.document.querySelectorAll("img");
        if (allImgs.length > 0) {
          let loaded = 0;
          const checkPrint = () => { if (++loaded >= allImgs.length) setTimeout(() => printWin.print(), 300); };
          allImgs.forEach(img => {
            if (img.complete) { checkPrint(); }
            else { img.onload = checkPrint; img.onerror = checkPrint; }
          });
          // Fallback: print after 5s even if images haven't finished
          setTimeout(() => { if (loaded < allImgs.length) printWin.print(); }, 5000);
        } else {
          setTimeout(() => printWin.print(), 500);
        }

      } catch (err) {
        console.error("Combined PDF error:", err);
        alert("Lỗi xuất PDF: " + (err.message || err));
      } finally {
        savePdfBtn.disabled = false;
        savePdfBtn.textContent = origText;
      }
    });
  }

  // Copy buttons
  const flowCard = document.getElementById(`translateFlow-${flowId}`);
  if (flowCard) {
    flowCard.querySelectorAll(".trans-copy-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-target");
        const el = targetId ? document.getElementById(targetId) : null;
        if (el) {
          const text = el.value !== undefined ? el.value : el.textContent;
          navigator.clipboard.writeText(text || "").then(() => {
            const orig = btn.textContent;
            btn.textContent = "✅ Đã copy!";
            setTimeout(() => { btn.textContent = orig; }, 1500);
          });
        }
      });
    });
  }
}

// Cache uploaded File objects for combined PDF export (survives server restart)
const _transOriginalFiles = window._transOriginalFiles || (window._transOriginalFiles = {});

async function uploadTranslateFile(flowId) {
  const inputEl = document.getElementById(`transUpload-${flowId}`);
  const statusEl = document.getElementById(`transStatus-${flowId}`);
  const uploadBtn = document.getElementById(`transUploadBtn-${flowId}`);
  const uploadedRefEl = document.getElementById(`transUploadedRef-${flowId}`);
  const uploadedNameEl = document.getElementById(`transUploadedName-${flowId}`);
  const fileInfoEl = document.getElementById(`transFileInfo-${flowId}`);
  if (!inputEl || !statusEl || !uploadBtn || !uploadedRefEl || !uploadedNameEl) return;

  const file = inputEl.files && inputEl.files[0];
  if (!file) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Vui lòng chọn file để upload.</span>`;
    return;
  }

  const originalText = uploadBtn.textContent;
  uploadBtn.disabled = true;
  uploadBtn.textContent = "⏳ Đang upload...";
  statusEl.textContent = "Đang upload file...";

  try {
    const fd = new FormData();
    fd.append("file", file);
    const pid = getProjectId();
    const url = "/api/translate/upload" + (pid ? `?project_id=${pid}` : "");
    const res = await fetch(url, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) {
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ Upload lỗi: ${escapeHtml(data.error || "không xác định")}</span>`;
      return;
    }

    const fileRef = data.file_ref;
    const uploadedDisplayName = data.filename || file.name;
    uploadedRefEl.value = fileRef;
    uploadedNameEl.value = uploadedDisplayName;
    // Store File object for combined PDF export
    _transOriginalFiles[flowId] = file;
    // File preview info
    const sizeKB = (file.size / 1024).toFixed(1);
    const ext = uploadedDisplayName.split(".").pop().toUpperCase();
    if (fileInfoEl) {
      fileInfoEl.innerHTML = `📄 <b>${escapeHtml(uploadedDisplayName)}</b> — ${sizeKB} KB — ${ext}`;
    }
    // Auto-suggest save name
    const saveNameEl = document.getElementById(`transSaveName-${flowId}`);
    if (saveNameEl && !saveNameEl.value) {
      const base = uploadedDisplayName.replace(/\.[^.]+$/, "");
      saveNameEl.value = `${base}.translated.html`;
    }
    statusEl.innerHTML = `<span style="color:#16a34a;">✅ Upload thành công: <b>${escapeHtml(uploadedDisplayName)}</b> (${sizeKB} KB)</span>`;
  } catch (e) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Upload lỗi: ${escapeHtml(e.message)}</span>`;
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = originalText;
  }
}

async function saveTranslateHtml(flowId) {
  const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
  const saveNameEl = document.getElementById(`transSaveName-${flowId}`);
  const saveBtn = document.getElementById(`transSaveHtmlBtn-${flowId}`);
  const statusEl = document.getElementById(`transStatus-${flowId}`);
  if (!htmlSrcEl || !saveNameEl || !saveBtn || !statusEl) return;

  const htmlContent = (htmlSrcEl.value || "").trim();
  const fileName = (saveNameEl.value || "").trim();
  if (!htmlContent) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Chưa có HTML để lưu.</span>`;
    return;
  }
  if (!fileName) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Vui lòng nhập tên file trước khi lưu.</span>`;
    return;
  }

  const original = saveBtn.textContent;
  saveBtn.disabled = true;
  saveBtn.textContent = "⏳ Đang lưu...";
  try {
    const res = await fetch("/api/translate/save_html", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_name: fileName,
        html_content: htmlContent,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lưu HTML lỗi: ${escapeHtml(data.error || "không xác định")}</span>`;
      return;
    }
    statusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã lưu HTML: <b>${escapeHtml(data.saved_name || fileName)}</b> (dich/html)</span>`;
  } catch (e) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lưu HTML lỗi: ${escapeHtml(e.message)}</span>`;
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = original;
  }
}

async function rebuildTranslateHtml(flowId) {
  const translatedEl = document.getElementById(`transTranslated-${flowId}`);
  const ocrEl = document.getElementById(`transOcr-${flowId}`);
  const templateEl = document.getElementById(`transTemplate-${flowId}`);
  const previewEl = document.getElementById(`transPreview-${flowId}`);
  const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
  const rebuildBtn = document.getElementById(`transRebuildBtn-${flowId}`);
  const rebuildStatusEl = document.getElementById(`transRebuildStatus-${flowId}`);
  if (!translatedEl || !rebuildBtn) return;

  const translatedText = (translatedEl.value || "").trim();
  if (!translatedText) {
    if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Chưa có bản dịch để tạo HTML.</span>`;
    return;
  }

  const original = rebuildBtn.textContent;
  rebuildBtn.disabled = true;
  rebuildBtn.textContent = "⏳ Đang tạo lại...";
  if (rebuildStatusEl) rebuildStatusEl.textContent = "";

  try {
    const res = await fetch("/api/translate/rebuild_html", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        translated_text: translatedText,
        ocr_text: ocrEl ? ocrEl.value : "",
        template_name: templateEl ? templateEl.value : "a4.html",
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      const errMsg = data.error === "quota_exceeded"
        ? `⚠️ HẾT QUOTA OpenAI! ${data.detail || "Vui lòng kiểm tra billing."}`
        : `❌ ${data.error || "Lỗi"}`;
      if (data.error === "quota_exceeded") alert(errMsg);
      if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#dc2626;font-weight:bold;">${escapeHtml(errMsg)}</span>`;
      return;
    }
    const newHtml = data.html || "";
    if (previewEl) previewEl.srcdoc = wrapForPrintPreview(newHtml);
    if (htmlSrcEl) htmlSrcEl.value = newHtml;
    if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã tạo lại HTML thành công.</span>`;
    // Auto-save to DB
    autoSaveTranslationFlow(flowId);
  } catch (e) {
    if (rebuildStatusEl) rebuildStatusEl.innerHTML = `<span style="color:#dc2626;">❌ ${escapeHtml(e.message)}</span>`;
  } finally {
    rebuildBtn.disabled = false;
    rebuildBtn.textContent = original;
  }
}

async function runTranslateFlow(flowId) {
  const templateEl = document.getElementById(`transTemplate-${flowId}`);
  const runBtn = document.getElementById(`transRunBtn-${flowId}`);
  const statusEl = document.getElementById(`transStatus-${flowId}`);
  const ocrEl = document.getElementById(`transOcr-${flowId}`);
  const translatedEl = document.getElementById(`transTranslated-${flowId}`);
  const previewEl = document.getElementById(`transPreview-${flowId}`);
  const uploadedRefEl = document.getElementById(`transUploadedRef-${flowId}`);
  const uploadedNameEl = document.getElementById(`transUploadedName-${flowId}`);
  const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
  const saveNameEl = document.getElementById(`transSaveName-${flowId}`);
  const sourceLangEl = document.getElementById(`transSourceLang-${flowId}`);
  if (!templateEl || !runBtn || !statusEl || !ocrEl || !translatedEl || !previewEl || !uploadedRefEl || !uploadedNameEl || !htmlSrcEl || !saveNameEl) return;

  const inputFile = (uploadedRefEl.value || "").trim();
  const templateName = templateEl.value || "a4.html";
  const sourceLang = sourceLangEl ? sourceLangEl.value : "tiếng Việt";
  if (!inputFile) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Vui lòng upload file trước khi chạy.</span>`;
    return;
  }

  const originalText = runBtn.textContent;
  runBtn.disabled = true;
  runBtn.textContent = "⏳ Đang chạy...";
  statusEl.textContent = "Đang xử lý...";
  updateTranslateFlowStep(flowId, 1, "idle");
  updateTranslateFlowStep(flowId, 2, "idle");
  updateTranslateFlowStep(flowId, 3, "idle");

  try {
    const res = await fetch("/api/translate/run_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_dir: (inputDirEl?.value || "").trim() || "input",
        file_ref: inputFile,
        template_name: templateName,
        flow_id: flowId,
        project_id: getProjectId(),
        source_lang: sourceLang,
      }),
    });
    if (!res.ok || !res.body) {
      let detail = "Không thể chạy dịch.";
      try {
        const data = await res.json();
        detail = data.error || detail;
      } catch (e) {}
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ ${escapeHtml(detail)}</span>`;
      updateTranslateFlowStep(flowId, 1, "error", detail);
      return;
    }

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
        let evt = null;
        try {
          evt = JSON.parse(line.slice(6));
        } catch (e) {
          continue;
        }
        const step = Number(evt.step || 0);
        const msg = String(evt.msg || "");
        if (step === -1) {
          const isQuota = msg.toLowerCase().includes("quota") || msg.includes("HẾT QUOTA");
          if (isQuota) alert(msg);
          statusEl.innerHTML = `<span style="color:#dc2626;${isQuota ? 'font-weight:bold;font-size:1.1em;' : ''}">${isQuota ? '⚠️' : '❌'} ${escapeHtml(msg || "Có lỗi xảy ra.")}</span>`;
          updateTranslateFlowStep(flowId, 1, "error", msg);
          updateTranslateFlowStep(flowId, 2, "error", msg);
          return;
        }
        if (step >= 1 && step <= 2) {
          if (msg.startsWith("✅")) {
            updateTranslateFlowStep(flowId, step, "done", msg.replace(/^✅\s*/, ""));
          } else if (msg.startsWith("⏳") || msg.startsWith("🔄")) {
            updateTranslateFlowStep(flowId, step, "running", msg.replace(/^[⏳🔄]\s*/, ""));
          }
        }
        if (step === 3 && evt.data) {
          finalData = evt.data;
        }
      }
    }

    if (finalData) {
      ocrEl.value = finalData.translated_text || "(OCR+Dịch gộp — xem bên phải)";
      translatedEl.value = finalData.translated_text || "Không có bản dịch.";
      const htmlContent = finalData.html || "<p>Không có HTML.</p>";
      previewEl.srcdoc = wrapForPrintPreview(htmlContent);
      htmlSrcEl.value = htmlContent;
      const uploadedName = uploadedNameEl.value || "translated-document";
      const base = uploadedName.replace(/\.[^.]+$/, "");
      if (!saveNameEl.value) saveNameEl.value = `${base}.translated.html`;
      statusEl.innerHTML = `<span style="color:#16a34a;">✅ Hoàn tất. Sửa bản dịch/HTML rồi lưu PDF.</span>`;
      // Auto-save to DB
      autoSaveTranslationFlow(flowId);
    } else {
      statusEl.innerHTML = '<span style="color:#dc2626;">❌ Không nhận được kết quả từ server.</span>';
      updateTranslateFlowStep(flowId, 2, "error", "Không có dữ liệu trả về");
    }
  } catch (error) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(error.message)}</span>`;
    updateTranslateFlowStep(flowId, 1, "error", error.message);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = originalText;
  }
}

async function initTranslationSection() {
  if (!translateFlowsContainerEl) return;
  if (translateFlowsContainerEl.dataset.inited === "1") return;
  try {
    await loadTranslationTemplates();
    if ((translationTemplatesCache || []).length === 0) {
      console.warn("No translation templates found.");
    }
    // Don't auto-create a flow — user will use bulk upload or manual add
    // Restore saved flows from DB
    await restoreTranslationFlows();
    translateFlowsContainerEl.dataset.inited = "1";
  } catch (e) {
    translateFlowsContainerEl.innerHTML = `<div class="card" style="color:#dc2626;">❌ Không thể khởi tạo tab dịch: ${escapeHtml(e.message)}</div>`;
  }
}

// Store bulk check results globally for stream creation
let _bulkCheckResults = [];

async function runBulkBilingualCheck() {
  if (!bulkTranslateFilesEl || !bulkCheckBtn) return;
  const files = bulkTranslateFilesEl.files;
  if (!files || files.length === 0) {
    if (bulkCheckStatusEl) bulkCheckStatusEl.innerHTML = '<span style="color:#dc2626;">❌ Chưa chọn file nào.</span>';
    return;
  }

  // Show progress
  const origText = bulkCheckBtn.textContent;
  bulkCheckBtn.disabled = true;
  bulkCheckBtn.textContent = "⏳ Đang quét...";
  if (bulkCheckStatusEl) bulkCheckStatusEl.innerHTML = `⏳ Đang upload & quét ${files.length} file (chỉ trang đầu)...`;
  if (bulkCheckProgressEl) {
    bulkCheckProgressEl.style.display = "block";
    bulkCheckProgressBarEl.style.width = "30%";
  }

  try {
    const fd = new FormData();
    for (let i = 0; i < files.length; i++) {
      fd.append("files", files[i]);
    }

    if (bulkCheckProgressBarEl) bulkCheckProgressBarEl.style.width = "60%";

    const res = await fetch("/api/translate/check_bilingual", { method: "POST", body: fd });
    const data = await res.json();

    if (bulkCheckProgressBarEl) bulkCheckProgressBarEl.style.width = "100%";

    if (!res.ok) {
      if (bulkCheckStatusEl) bulkCheckStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(data.error || 'unknown')}</span>`;
      return;
    }

    _bulkCheckResults = data.results || [];

    // Render results table
    if (bulkResultsBodyEl) {
      bulkResultsBodyEl.innerHTML = _bulkCheckResults.map((r, i) => {
        let statusBadge;
        if (r.needs_translation) {
          statusBadge = '<span style="background:#fef2f2; color:#dc2626; padding:2px 8px; border-radius:4px; font-size:0.85em;">📝 Cần dịch</span>';
        } else if (r.is_bilingual) {
          statusBadge = '<span style="background:#f0fdf4; color:#16a34a; padding:2px 8px; border-radius:4px; font-size:0.85em;">✅ Đã song ngữ</span>';
        } else {
          statusBadge = '<span style="background:#fffbeb; color:#d97706; padding:2px 8px; border-radius:4px; font-size:0.85em;">⏭️ Bỏ qua</span>';
        }
        const docType = r.doc_type ? escapeHtml(r.doc_type) : (r.languages || []).join(", ") || "—";
        return `<tr style="border-bottom:1px solid #e2e8f0;">
          <td style="padding:6px 8px;">${i + 1}</td>
          <td style="padding:6px 8px; word-break:break-all;">${escapeHtml(r.filename)}</td>
          <td style="padding:6px 8px; text-align:center; font-size:0.85em;">${docType}</td>
          <td style="padding:6px 8px; text-align:center;">${statusBadge}</td>
          <td style="padding:6px 8px; font-size:0.85em; color:#64748b;">${escapeHtml(r.reason || '')}</td>
        </tr>`;
      }).join("");
    }

    // Summary
    if (bulkResultSummaryEl) {
      const skipCount = data.skipped || 0;
      bulkResultSummaryEl.innerHTML = `📊 ${data.total} file | <span style="color:#dc2626;">${data.needs_translation} cần dịch</span> | <span style="color:#16a34a;">${data.already_bilingual} song ngữ</span> | <span style="color:#d97706;">${skipCount} bỏ qua</span>`;
    }

    // Show results area
    if (bulkCheckResultsEl) bulkCheckResultsEl.style.display = "block";
    if (bulkManualFallbackEl) bulkManualFallbackEl.style.display = "none";
    if (bulkCheckStatusEl) bulkCheckStatusEl.innerHTML = `<span style="color:#16a34a;">✅ Quét xong ${data.total} file!</span>`;

  } catch (e) {
    if (bulkCheckStatusEl) bulkCheckStatusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${escapeHtml(e.message)}</span>`;
  } finally {
    bulkCheckBtn.disabled = false;
    bulkCheckBtn.textContent = origText;
    setTimeout(() => {
      if (bulkCheckProgressEl) bulkCheckProgressEl.style.display = "none";
    }, 1000);
  }
}

async function bulkCreateTranslateStreams() {
  if (!_bulkCheckResults || _bulkCheckResults.length === 0) return;

  await loadTranslationTemplates();

  const needsTranslation = _bulkCheckResults.filter(r => r.needs_translation);
  if (needsTranslation.length === 0) {
    alert("Không có file nào cần dịch!");
    return;
  }

  // Clear existing flows
  if (translateFlowsContainerEl) translateFlowsContainerEl.innerHTML = "";
  translationFlowCounter = 0;
  Object.keys(_flowDbIds).forEach(k => delete _flowDbIds[k]);

  // Build a filename → File lookup from the bulk upload input
  const bulkFiles = bulkTranslateFilesEl ? Array.from(bulkTranslateFilesEl.files) : [];
  const fileByName = {};
  for (const f of bulkFiles) {
    fileByName[f.name] = f;
    // Also try sanitized name (spaces etc)
    const safeName = f.name.replace(/[\\/:*?"<>|\x00-\x1f]+/g, ' ').replace(/\s+/g, ' ').trim();
    fileByName[safeName] = f;
  }

  // Create a stream for each file that needs translation, pre-setting the upload token
  for (const r of needsTranslation) {
    createTranslateFlow();
    const flowId = translationFlowCounter;

    // Set the uploaded ref (file_ref) so runTranslateFlow can use it
    const uploadedRefEl = document.getElementById(`transUploadedRef-${flowId}`);
    const uploadedNameEl = document.getElementById(`transUploadedName-${flowId}`);
    const fileInfoEl = document.getElementById(`transFileInfo-${flowId}`);
    const saveNameEl = document.getElementById(`transSaveName-${flowId}`);
    const statusEl = document.getElementById(`transStatus-${flowId}`);

    if (uploadedRefEl) uploadedRefEl.value = r.file_ref || "";
    if (uploadedNameEl) uploadedNameEl.value = r.filename || "";
    if (fileInfoEl) fileInfoEl.innerHTML = `📄 <b>${escapeHtml(r.filename)}</b> — <span style="color:#16a34a;">Đã upload sẵn</span>`;
    if (statusEl) statusEl.innerHTML = '<span style="color:#16a34a;">✅ File đã sẵn sàng để dịch.</span>';

    // Store browser File object for combined PDF export (original pages)
    const matchedFile = fileByName[r.filename];
    if (matchedFile) {
      _transOriginalFiles[flowId] = matchedFile;
    }

    // Auto-suggest save name
    if (saveNameEl) {
      const base = (r.filename || "file").replace(/\.[^.]+$/, "");
      saveNameEl.value = `${base}.translated.html`;
    }
  }

  // Show translate-all button
  if (bulkTranslateAllBtn) bulkTranslateAllBtn.style.display = "inline-block";
  if (bulkPrintAllPdfBtn) bulkPrintAllPdfBtn.style.display = "inline-block";
  if (bulkCreateStreamsBtn) {
    bulkCreateStreamsBtn.textContent = `✅ Đã tạo ${needsTranslation.length} luồng`;
    bulkCreateStreamsBtn.disabled = true;
  }
}

async function runTranslateAll() {
  const flowCards = translateFlowsContainerEl?.querySelectorAll(".translate-flow-card") || [];
  if (flowCards.length === 0) {
    alert("Chưa có luồng dịch nào.");
    return;
  }

  if (bulkTranslateAllBtn) {
    bulkTranslateAllBtn.disabled = true;
    bulkTranslateAllBtn.textContent = "⏳ Đang dịch song song...";
  }

  let doneCount = 0;
  const total = flowCards.length;

  // Build parallel promises for all flows
  const promises = Array.from(flowCards).map(card => {
    const flowId = parseInt(card.id.replace("translateFlow-", ""), 10);
    if (isNaN(flowId)) return Promise.resolve();

    const refEl = document.getElementById(`transUploadedRef-${flowId}`);
    if (!refEl || !refEl.value) {
      console.warn(`Flow ${flowId}: no file_ref, skipping`);
      return Promise.resolve();
    }

    // Highlight as running
    card.style.boxShadow = "0 0 0 3px #3b82f6";

    return runTranslateFlow(flowId)
      .then(() => {
        doneCount++;
        card.style.boxShadow = "0 0 0 3px #16a34a";
        if (bulkTranslateAllBtn) {
          bulkTranslateAllBtn.textContent = `⏳ Đang dịch... (${doneCount}/${total})`;
        }
      })
      .catch(e => {
        doneCount++;
        console.error(`Flow ${flowId} failed:`, e);
        card.style.boxShadow = "0 0 0 3px #dc2626";
        if (bulkTranslateAllBtn) {
          bulkTranslateAllBtn.textContent = `⏳ Đang dịch... (${doneCount}/${total})`;
        }
      });
  });

  // Run ALL in parallel
  await Promise.all(promises);

  if (bulkTranslateAllBtn) {
    bulkTranslateAllBtn.disabled = false;
    bulkTranslateAllBtn.textContent = `✅ Đã dịch xong ${doneCount}/${total} luồng`;
  }

  // Show print-all button after translation completes
  if (bulkPrintAllPdfBtn) bulkPrintAllPdfBtn.style.display = "inline-block";
}

/**
 * Print ALL translation flows in one go.
 * For each flow: Original pages → Translated HTML → Certification page.
 * All combined into a single print window.
 */
async function printAllTranslationFlows() {
  const flowCards = translateFlowsContainerEl?.querySelectorAll(".translate-flow-card") || [];
  if (flowCards.length === 0) {
    alert("Chưa có luồng dịch nào.");
    return;
  }

  if (bulkPrintAllPdfBtn) {
    bulkPrintAllPdfBtn.disabled = true;
    bulkPrintAllPdfBtn.textContent = "⏳ Đang chuẩn bị PDF...";
  }

  try {
    // Fetch certification template once (shared across all flows)
    let certHtml = "";
    try {
      const certRes = await fetch("/api/translate/certification_template");
      if (certRes.ok) {
        const certData = await certRes.json();
        certHtml = certData.html || "";
        const now = new Date();
        const dd = String(now.getDate()).padStart(2, "0");
        const mm = String(now.getMonth() + 1).padStart(2, "0");
        const yyyy = now.getFullYear();
        certHtml = certHtml.replace(/Date:\s*\d{2}\/\d{2}\/\d{4}/, `Date: ${dd}/${mm}/${yyyy}`);
      }
    } catch (e) {
      console.warn("[PrintAll] Cert template fetch failed:", e);
    }

    // Helper functions
    const extractStyles = (html) => {
      const styles = [];
      const regex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
      let m;
      while ((m = regex.exec(html)) !== null) styles.push(m[1]);
      return styles.join("\n");
    };
    const extractBody = (html) => {
      const m = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
      return m ? m[1] : html;
    };
    // Properties to strip from body/html rules (they break the combined layout)
    const bodyStripProps = /\b(display|padding|margin|background[^:]*|justify-content|align-items|min-height|height|overflow|gap|flex-direction)\s*:[^;]+;?/gi;
    const scopeStyles = (css, scopeClass) => {
      // 1) Strip @page rules entirely (the outer print container handles @page)
      let cleaned = css.replace(/@page\s*\{[^}]*\}/gi, "");
      // 2) Strip @media print blocks entirely (outer container handles print rules;
      //    these nested blocks can't be parsed by simple regex and cause CSS leaks)
      cleaned = cleaned.replace(/@media\s+print\s*\{[\s\S]*?\}\s*\}/gi, "");
      // 3) Scope remaining simple rules
      return cleaned.replace(/([^{}@]+)\{([^{}]+)\}/g, (match, sel, body) => {
        let isBodyRule = false;
        const scopedSel = sel.split(",").map(s => {
          s = s.trim();
          if (!s || s.startsWith("@") || s.startsWith("/*")) return s;
          if (s === "body" || s === "html") { isBodyRule = true; return "." + scopeClass; }
          return "." + scopeClass + " " + s;
        }).join(", ");
        const cleanBody = isBodyRule ? body.replace(bodyStripProps, "") : body;
        return scopedSel + "{" + cleanBody + "}";
      });
    };

    let allStyles = "";
    let allSections = "";
    let flowIndex = 0;

    for (const card of flowCards) {
      const flowId = parseInt(card.id.replace("translateFlow-", ""), 10);
      if (isNaN(flowId)) continue;

      const previewEl = document.getElementById(`transPreview-${flowId}`);
      // Auto-sync: if user edited HTML source, use that instead of stale srcdoc
      const htmlSrcEl = document.getElementById(`transHtmlSource-${flowId}`);
      if (htmlSrcEl && htmlSrcEl.value.trim()) {
        previewEl.srcdoc = wrapForPrintPreview(htmlSrcEl.value);
      }
      const translatedHtml = htmlSrcEl?.value?.trim() || previewEl?.srcdoc || "";
      if (!translatedHtml) {
        console.warn(`[PrintAll] Flow ${flowId}: no translated HTML, skipping`);
        continue;
      }

      if (bulkPrintAllPdfBtn) {
        bulkPrintAllPdfBtn.textContent = `⏳ Chuẩn bị luồng ${flowIndex + 1}/${flowCards.length}...`;
      }

      // --- Part 1: Original pages ---
      let originalPagesHtml = "";
      let originalFile = (window._transOriginalFiles || {})[flowId];
      if (!originalFile) {
        const inputEl = document.getElementById(`transUpload-${flowId}`);
        if (inputEl?.files?.[0]) originalFile = inputEl.files[0];
      }
      if (originalFile) {
        try {
          const fd = new FormData();
          fd.append("file", originalFile);
          const origRes = await fetch("/api/translate/original_pages", { method: "POST", body: fd });
          if (origRes.ok) {
            const origData = await origRes.json();
            if (origData.pages?.length > 0) {
              originalPagesHtml = origData.pages.map(p =>
                `<div class="original-page"><img src="${p.data_url}" style="width:100%;height:auto;display:block;" /></div>`
              ).join("\n");
            }
          }
        } catch (e) {
          console.warn(`[PrintAll] Flow ${flowId}: original pages failed:`, e);
        }
      } else {
        // Fallback: use file_ref (for restored flows after F5)
        const fileRefEl = document.getElementById(`transUploadedRef-${flowId}`);
        const fileRef = fileRefEl?.value?.trim();
        if (fileRef) {
          try {
            const origRes = await fetch("/api/translate/original_pages_by_ref", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ file_ref: fileRef }),
            });
            if (origRes.ok) {
              const origData = await origRes.json();
              if (origData.pages?.length > 0) {
                originalPagesHtml = origData.pages.map(p =>
                  `<div class="original-page"><img src="${p.data_url}" style="width:100%;height:auto;display:block;" /></div>`
                ).join("\n");
              }
            }
          } catch (e) {
            console.warn(`[PrintAll] Flow ${flowId}: original pages by ref failed:`, e);
          }
        }
      }

      const flowScopeClass = `flow-trans-${flowIndex}`;
      const flowCertScopeClass = `flow-cert-${flowIndex}`;

      // --- Part 2: Translated HTML (scoped) ---
      if (translatedHtml) {
        const transStyles = extractStyles(translatedHtml);
        const transBody = extractBody(translatedHtml);
        allStyles += `/* Flow ${flowId} translated */\n${scopeStyles(transStyles, flowScopeClass)}\n`;
        allStyles += `.${flowScopeClass} .a4, .${flowScopeClass} .a4-page { min-height: auto !important; height: auto !important; }\n`;
      }

      // --- Part 3: Certification (scoped) ---
      if (certHtml) {
        const certStyles = extractStyles(certHtml);
        allStyles += `/* Flow ${flowId} cert */\n${scopeStyles(certStyles, flowCertScopeClass)}\n`;
        allStyles += `.${flowCertScopeClass} .a4-page { min-height: auto !important; height: auto !important; }\n`;
      }

      // Build sections for this flow
      if (originalPagesHtml) {
        allSections += `<div class="doc-section doc-original">${originalPagesHtml}</div>\n`;
      }
      if (translatedHtml) {
        allSections += `<div class="doc-section ${flowScopeClass}">${extractBody(translatedHtml)}</div>\n`;
      }
      if (certHtml) {
        allSections += `<div class="doc-section ${flowCertScopeClass}">${extractBody(certHtml)}</div>\n`;
      }

      flowIndex++;
    }

    if (!allSections) {
      alert("Không có luồng nào có bản dịch để in.");
      return;
    }

    // Build final combined HTML
    const combinedHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>All Translations PDF</title>
  <style>
    html, body { background: #fff !important; margin: 0; padding: 0; }
    body { display: block !important; }
    .doc-section { display: block !important; width: 100% !important; background: #fff !important; }
    .doc-section + .doc-section { page-break-before: always; }
    .original-page { display: block; width: 100%; }
    .original-page + .original-page { page-break-before: always; }
    .original-page img { width: 100%; height: auto; display: block; }

    /* Named page: only TRANSLATED docs get @page margins (cert keeps its own padding) */
    @page { margin: 0; size: A4; }
    @page content-page { margin: 15mm 18mm; size: A4; }
    .doc-translated, [class*='flow-trans-'] { page: content-page; }

    @media print {
      body { margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .doc-section { background: #fff !important; }
      .original-page { height: 100vh; display: flex; align-items: center; justify-content: center; }
      .original-page + .original-page { page-break-before: always; }
      .original-page img { max-height: 100vh; max-width: 100vw; height: auto; width: auto; }
      /* Only strip padding on translated docs (cert keeps its own layout) */
      .doc-translated .a4, .doc-translated .a4-page,
      [class*='flow-trans-'] .a4, [class*='flow-trans-'] .a4-page {
        margin: 0 !important; padding: 0 !important; width: 100% !important;
        box-shadow: none !important; border: none !important;
        min-height: auto !important; height: auto !important;
        overflow: visible !important; background: #fff !important;
      }
      /* Cert keeps its own padding — only strip visual chrome */
      .doc-cert .a4, .doc-cert .a4-page,
      [class*='flow-cert-'] .a4, [class*='flow-cert-'] .a4-page {
        margin: 0 !important; box-shadow: none !important; border: none !important;
        min-height: auto !important; height: auto !important;
        overflow: visible !important; background: #fff !important;
      }
    }
    
    ${allStyles}
  </style>
</head>
<body>
  ${allSections}
</body>
</html>`;


    const printWin = window.open("", "_blank");
    if (!printWin) {
      alert("Trình duyệt chặn popup. Vui lòng cho phép popup rồi thử lại.");
      return;
    }
    printWin.document.open();
    printWin.document.write(combinedHtml);
    printWin.document.close();

    // Wait for all images to load before printing
    const allImgs = printWin.document.querySelectorAll("img");
    if (allImgs.length > 0) {
      let loaded = 0;
      const checkPrint = () => { if (++loaded >= allImgs.length) setTimeout(() => printWin.print(), 400); };
      allImgs.forEach(img => {
        if (img.complete) { checkPrint(); }
        else { img.onload = checkPrint; img.onerror = checkPrint; }
      });
      setTimeout(() => { if (loaded < allImgs.length) printWin.print(); }, 8000);
    } else {
      setTimeout(() => printWin.print(), 600);
    }

  } catch (err) {
    console.error("[PrintAll] Error:", err);
    alert("Lỗi xuất PDF tổng: " + (err.message || err));
  } finally {
    if (bulkPrintAllPdfBtn) {
      bulkPrintAllPdfBtn.disabled = false;
      bulkPrintAllPdfBtn.textContent = "🖨️ In tất cả PDF";
    }
  }
}
