// Project Management
// Extracted from app.js

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
    // Letter V3 — no project-level letter loading needed
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
    // Letter V3 — no project-level letter loading needed
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
      // Letter V3 — no project-level letter loading needed
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
  additional_info: "",
};

function renderFiles(files) {
  if (!fileListEl) return;
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
  if (!inputDirEl || !fileListEl) return;
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
            <input id="segmentStart-${i}" type="number" min="1" max="${manualSplitState.pageCount || ''}" value="${i === 1 ? 1 : ''}" />
          </div>
          <div>
            <label for="segmentEnd-${i}">Đến trang</label>
            <input id="segmentEnd-${i}" type="number" min="1" max="${manualSplitState.pageCount || ''}" />
          </div>
        </div>
      </div>
    `);
  }
  manualSplitSegmentsContainerEl.innerHTML = parts.join("");

  // Auto-cascade: when end page changes, fill next file's start page
  const maxPage = manualSplitState.pageCount || 9999;
  for (let i = 1; i <= safeCount; i++) {
    const endEl = document.getElementById(`segmentEnd-${i}`);
    if (endEl) {
      endEl.addEventListener('input', () => {
        let val = parseInt(endEl.value, 10);
        if (isNaN(val) || val < 1) return;
        if (val > maxPage) { val = maxPage; endEl.value = val; }
        const nextStart = document.getElementById(`segmentStart-${i + 1}`);
        if (nextStart && val + 1 <= maxPage) nextStart.value = val + 1;
      });
    }
  }
}

