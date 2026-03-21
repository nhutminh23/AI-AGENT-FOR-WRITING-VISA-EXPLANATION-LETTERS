// Edit PDF Functions
// Extracted from app.js

// ==================== EDIT PDF FUNCTIONS ====================

let editPdfInited = false;

// ===== Visual PDF Editor State =====
let _epdf = {
  file: null,           // original File object
  pdfDoc: null,         // PDF.js document
  pages: [],            // text block data from server [{pageIndex, width, height, blocks:[{text,bbox,font,fontSize,color}]}]
  edits: {},            // {blockKey: {find, replace, fontname}} — pending edits
  currentPage: 0,       // 0-indexed
  totalPages: 0,
  scale: 1.5,           // rendering scale
};

function initEditPdfUI() {
  if (editPdfInited) return;
  editPdfInited = true;

  const fileInput = document.getElementById("editPdfFileInput");
  fileInput.addEventListener("change", _epdfOnFileSelect);

  document.getElementById("editPdfPrevPage").addEventListener("click", () => _epdfGoPage(-1));
  document.getElementById("editPdfNextPage").addEventListener("click", () => _epdfGoPage(1));
  document.getElementById("editPdfZoomIn").addEventListener("click", () => _epdfZoom(0.25));
  document.getElementById("editPdfZoomOut").addEventListener("click", () => _epdfZoom(-0.25));
  document.getElementById("editPdfSaveBtn").addEventListener("click", _epdfSave);
}

async function _epdfOnFileSelect() {
  const fileInput = document.getElementById("editPdfFileInput");
  if (!fileInput.files || !fileInput.files[0]) return;

  _epdf.file = fileInput.files[0];
  _epdf.edits = {};
  _epdf.currentPage = 0;
  _epdfUpdateEditCount();

  const statusEl = document.getElementById("editPdfStatus");
  statusEl.innerHTML = `<div style="display:flex;align-items:center;gap:8px;"><div class="spinner" style="width:18px;height:18px;border:3px solid #e5e7eb;border-top:3px solid #4f46e5;border-radius:50%;animation:spin 0.8s linear infinite;"></div> Đang phân tích PDF...</div>`;

  try {
    // 1. Extract text objects from server
    const formData = new FormData();
    formData.append("file", _epdf.file);
    const resp = await fetch("/api/pdf/extract-objects", { method: "POST", body: formData });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${err.error || resp.statusText}</span>`;
      return;
    }
    const data = await resp.json();
    _epdf.pages = data.pages || [];

    // 2. Load PDF with PDF.js
    const arrayBuf = await _epdf.file.arrayBuffer();
    _epdf.pdfDoc = await pdfjsLib.getDocument({ data: arrayBuf }).promise;
    _epdf.totalPages = _epdf.pdfDoc.numPages;

    statusEl.innerHTML = `<span style="color:#16a34a;">✅ Loaded ${_epdf.totalPages} trang, ${_epdf.pages.reduce((s, p) => s + p.blocks.length, 0)} text blocks.</span>`;

    document.getElementById("editPdfViewer").style.display = "block";
    document.getElementById("editPdfResultSection").style.display = "none";

    await _epdfRenderPage();
  } catch (e) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${e.message}</span>`;
  }
}

async function _epdfRenderPage() {
  const pageIdx = _epdf.currentPage;
  const pageNum = pageIdx + 1;

  // Update page info
  document.getElementById("editPdfPageInfo").textContent = `${pageNum} / ${_epdf.totalPages}`;
  document.getElementById("editPdfZoomInfo").textContent = `${Math.round(_epdf.scale * 100)}%`;

  // Render canvas with PDF.js
  const page = await _epdf.pdfDoc.getPage(pageNum);
  const viewport = page.getViewport({ scale: _epdf.scale });
  const canvas = document.getElementById("editPdfCanvas");
  const ctx = canvas.getContext("2d");
  canvas.width = viewport.width;
  canvas.height = viewport.height;

  await page.render({ canvasContext: ctx, viewport }).promise;

  // Build overlay
  _epdfBuildOverlay(pageIdx, viewport);
}

function _epdfBuildOverlay(pageIdx, viewport) {
  const overlay = document.getElementById("editPdfOverlay");
  overlay.innerHTML = "";
  overlay.style.width = viewport.width + "px";
  overlay.style.height = viewport.height + "px";

  const pageData = _epdf.pages[pageIdx];
  if (!pageData) return;

  const scaleX = viewport.width / pageData.width;
  const scaleY = viewport.height / pageData.height;

  pageData.blocks.forEach((block, blockIdx) => {
    const [x0, y0, x1, y1] = block.bbox;
    const key = `${pageIdx}_${blockIdx}`;

    const div = document.createElement("div");
    div.className = "epdf-text-block";
    div.dataset.key = key;
    div.style.cssText = `
      position:absolute;
      left:${x0 * scaleX}px;
      top:${y0 * scaleY}px;
      width:${(x1 - x0) * scaleX}px;
      height:${(y1 - y0) * scaleY}px;
      cursor:pointer;
      border:1px solid transparent;
      border-radius:2px;
      transition:border-color 0.15s, background 0.15s;
      box-sizing:border-box;
    `;

    // Show edit indicator if already edited
    if (_epdf.edits[key]) {
      div.style.border = "2px solid #f59e0b";
      div.style.background = "rgba(245,158,11,0.12)";
      div.title = `Đã sửa: "${_epdf.edits[key].replace}"`;
    }

    div.addEventListener("mouseenter", () => {
      if (!div.querySelector("textarea")) {
        div.style.border = "1px solid #4f46e5";
        div.style.background = "rgba(79,70,229,0.08)";
      }
    });
    div.addEventListener("mouseleave", () => {
      if (!div.querySelector("textarea")) {
        if (_epdf.edits[key]) {
          div.style.border = "2px solid #f59e0b";
          div.style.background = "rgba(245,158,11,0.12)";
        } else {
          div.style.border = "1px solid transparent";
          div.style.background = "transparent";
        }
      }
    });

    div.addEventListener("click", (e) => {
      e.stopPropagation();
      if (div.querySelector("textarea")) return; // already editing
      _epdfStartEdit(div, key, block);
    });

    overlay.appendChild(div);
  });
}

function _epdfStartEdit(div, key, block) {
  const currentText = _epdf.edits[key] ? _epdf.edits[key].replace : block.text;

  div.style.border = "2px solid #4f46e5";
  div.style.background = "rgba(79,70,229,0.15)";
  div.style.zIndex = "10";

  const ta = document.createElement("textarea");
  ta.value = currentText;
  ta.style.cssText = `
    width:100%; height:100%; min-height:24px;
    border:none; outline:none; resize:both;
    background:rgba(255,255,255,0.95);
    font-size:${Math.max(11, block.fontSize * 0.8)}px;
    color:${block.color};
    font-weight:${block.bold ? "bold" : "normal"};
    font-style:${block.italic ? "italic" : "normal"};
    padding:2px 4px;
    box-sizing:border-box;
    overflow:auto;
    font-family: sans-serif;
  `;

  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      _epdfFinishEdit(div, key, block, ta.value);
    } else if (e.key === "Escape") {
      e.preventDefault();
      _epdfCancelEdit(div, key);
    }
  });

  // Prevent click from propagating
  ta.addEventListener("click", (e) => e.stopPropagation());

  div.innerHTML = "";
  div.appendChild(ta);
  ta.focus();
  ta.select();
}

function _epdfFinishEdit(div, key, block, newText) {
  div.innerHTML = "";
  div.style.zIndex = "";

  if (newText !== block.text) {
    _epdf.edits[key] = {
      find: block.text,
      replace: newText,
      fontname: block.font,
    };
    div.style.border = "2px solid #f59e0b";
    div.style.background = "rgba(245,158,11,0.12)";
    div.title = `Đã sửa: "${newText}"`;
  } else {
    // Reverted to original
    delete _epdf.edits[key];
    div.style.border = "1px solid transparent";
    div.style.background = "transparent";
    div.title = "";
  }
  _epdfUpdateEditCount();
}

function _epdfCancelEdit(div, key) {
  div.innerHTML = "";
  div.style.zIndex = "";
  if (_epdf.edits[key]) {
    div.style.border = "2px solid #f59e0b";
    div.style.background = "rgba(245,158,11,0.12)";
  } else {
    div.style.border = "1px solid transparent";
    div.style.background = "transparent";
  }
}

function _epdfUpdateEditCount() {
  const count = Object.keys(_epdf.edits).length;
  const el = document.getElementById("editPdfEditCount");
  el.textContent = count > 0 ? `📝 ${count} chỗ đã sửa` : "";
}

function _epdfGoPage(delta) {
  const next = _epdf.currentPage + delta;
  if (next < 0 || next >= _epdf.totalPages) return;
  _epdf.currentPage = next;
  _epdfRenderPage();
}

function _epdfZoom(delta) {
  const next = _epdf.scale + delta;
  if (next < 0.5 || next > 4) return;
  _epdf.scale = next;
  _epdfRenderPage();
}

async function _epdfSave() {
  const edits = Object.values(_epdf.edits);
  if (edits.length === 0) {
    alert("Chưa có chỗ nào được sửa.");
    return;
  }

  const statusEl = document.getElementById("editPdfStatus");
  statusEl.innerHTML = `<div style="display:flex;align-items:center;gap:8px;"><div class="spinner" style="width:18px;height:18px;border:3px solid #e5e7eb;border-top:3px solid #4f46e5;border-radius:50%;animation:spin 0.8s linear infinite;"></div> Đang lưu PDF (${edits.length} chỗ sửa)...</div>`;

  const formData = new FormData();
  formData.append("file", _epdf.file);
  formData.append("replacements", JSON.stringify(edits));

  try {
    const resp = await fetch("/api/pdf/edit", { method: "POST", body: formData });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${err.error || resp.statusText}</span>`;
      return;
    }

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);

    const previewEl = document.getElementById("editPdfPreview");
    const downloadLink = document.getElementById("editPdfDownloadLink");
    const resultSection = document.getElementById("editPdfResultSection");

    previewEl.src = url;
    downloadLink.href = url;
    downloadLink.download = _epdf.file.name.replace(/\.pdf$/i, "_edited.pdf");
    downloadLink.style.display = "inline-block";
    resultSection.style.display = "block";

    statusEl.innerHTML = `<span style="color:#16a34a;">✅ Đã lưu thành công ${edits.length} chỗ sửa!</span>`;
  } catch (e) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${e.message}</span>`;
  }
}

