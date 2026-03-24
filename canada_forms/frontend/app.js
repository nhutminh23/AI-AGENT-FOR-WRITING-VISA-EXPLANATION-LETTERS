/**
 * Canada IMM5645E — Frontend Application Logic
 *
 * 4-step wizard: Upload → Extract → Review/Edit → Fill/Download
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let selectedFiles = [];
let sessionId = null;
let extractedData = null; // { raw, form_fields, confidence }

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const uploadZone = $("#uploadZone");
const fileInput = $("#fileInput");
const fileListEl = $("#fileList");
const fileListItems = $("#fileListItems");
const uploadBtn = $("#uploadBtn");
const uploadStatus = $("#uploadStatus");
const extractBtn = $("#extractBtn");
const skipExtractBtn = $("#skipExtractBtn");
const extractLoading = $("#extractLoading");
const extractStatus = $("#extractStatus");
const fillBtn = $("#fillBtn");
const fillStatus = $("#fillStatus");
const downloadLink = $("#downloadLink");
const startOverBtn = $("#startOverBtn");
const templateStatus = $("#templateStatus");
const addChildBtn = $("#addChildBtn");
const addSiblingBtn = $("#addSiblingBtn");

// ---------------------------------------------------------------------------
// Step Navigation
// ---------------------------------------------------------------------------
function goToStep(stepNum) {
    $$(".step-content").forEach((el) => el.classList.remove("active"));
    $(`#step${stepNum}`).classList.add("active");

    $$(".steps-bar .step").forEach((el) => {
        const s = parseInt(el.dataset.step);
        el.classList.toggle("active", s === stepNum);
        el.classList.toggle("completed", s < stepNum);
    });
}

// ---------------------------------------------------------------------------
// Upload Zone handlers
// ---------------------------------------------------------------------------
uploadZone.addEventListener("click", () => fileInput.click());

uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
});
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener("change", () => handleFiles(fileInput.files));

function handleFiles(fileList) {
    for (const f of fileList) {
        // Avoid duplicates
        if (!selectedFiles.some((sf) => sf.name === f.name && sf.size === f.size)) {
            selectedFiles.push(f);
        }
    }
    renderFileList();
}

function renderFileList() {
    if (selectedFiles.length === 0) {
        fileListEl.style.display = "none";
        uploadBtn.disabled = true;
        return;
    }
    fileListEl.style.display = "block";
    uploadBtn.disabled = false;

    fileListItems.innerHTML = selectedFiles
        .map(
            (f, i) => `
        <div class="file-item">
            <span class="file-name">${f.name}</span>
            <span class="file-size">${(f.size / 1024).toFixed(1)} KB</span>
            <button class="file-remove" onclick="removeFile(${i})">×</button>
        </div>`
        )
        .join("");
}

window.removeFile = function (index) {
    selectedFiles.splice(index, 1);
    renderFileList();
};

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------
uploadBtn.addEventListener("click", async () => {
    if (selectedFiles.length === 0) return;

    uploadBtn.disabled = true;
    uploadBtn.textContent = "⏳ Uploading...";
    uploadStatus.textContent = "";

    const formData = new FormData();
    selectedFiles.forEach((f) => formData.append("files", f));

    try {
        const res = await fetch("/canada/api/upload", { method: "POST", body: formData });
        const data = await res.json();

        if (!res.ok) throw new Error(data.error || "Upload failed");

        sessionId = data.session_id;
        uploadStatus.className = "status-msg success";
        uploadStatus.textContent = `✅ ${data.count} file(s) uploaded`;

        setTimeout(() => goToStep(2), 500);
    } catch (e) {
        uploadStatus.className = "status-msg error";
        uploadStatus.textContent = `❌ ${e.message}`;
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = "⬆️ Upload & Continue";
    }
});

// ---------------------------------------------------------------------------
// AI Extraction
// ---------------------------------------------------------------------------
extractBtn.addEventListener("click", async () => {
    if (!sessionId) {
        extractStatus.className = "status-msg error";
        extractStatus.textContent = "❌ No files uploaded yet";
        return;
    }

    extractBtn.disabled = true;
    skipExtractBtn.disabled = true;
    extractLoading.style.display = "block";
    extractStatus.textContent = "";

    try {
        const res = await fetch("/canada/api/extract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.error || "Extraction failed");

        extractedData = data;
        extractStatus.className = "status-msg success";
        extractStatus.textContent = `✅ Extracted from ${data.files_processed} file(s)`;

        populateFormFromExtraction(data);
        setTimeout(() => goToStep(3), 500);
    } catch (e) {
        extractStatus.className = "status-msg error";
        extractStatus.textContent = `❌ ${e.message}`;
    } finally {
        extractBtn.disabled = false;
        skipExtractBtn.disabled = false;
        extractLoading.style.display = "none";
    }
});

skipExtractBtn.addEventListener("click", () => {
    extractedData = null;
    initEmptyForm();
    goToStep(3);
});

// ---------------------------------------------------------------------------
// Form Building Helpers
// ---------------------------------------------------------------------------
const PERSON_FIELDS = [
    { key: "name", label: "Full Name", type: "text", fullWidth: true },
    { key: "dob", label: "Date of Birth", type: "date" },
    { key: "cob", label: "Country of Birth", type: "text" },
    { key: "address", label: "Current Address", type: "text", fullWidth: true },
    { key: "occupation", label: "Occupation", type: "text" },
    {
        key: "marital_status",
        label: "Marital Status",
        type: "select",
        options: ["", "Single", "Married", "Common-Law", "Divorced", "Separated", "Widowed", "Annulled"],
    },
];

function createFormField(fieldDef, prefix, value, confidence) {
    const div = document.createElement("div");
    div.className = "form-field" + (fieldDef.fullWidth ? " full-width" : "");

    const confBadge = confidence
        ? `<span class="badge badge-${confidence}">${confidence}</span>`
        : "";

    let inputHtml;
    const id = `${prefix}_${fieldDef.key}`;

    if (fieldDef.type === "select") {
        const opts = fieldDef.options
            .map((o) => `<option value="${o}" ${o === value ? "selected" : ""}>${o || "— Select —"}</option>`)
            .join("");
        inputHtml = `<select id="${id}" data-field="${prefix}_${fieldDef.key}">${opts}</select>`;
    } else {
        const v = value || "";
        inputHtml = `<input type="${fieldDef.type}" id="${id}" data-field="${prefix}_${fieldDef.key}" value="${v.replace(/"/g, "&quot;")}">`;
    }

    div.innerHTML = `<label>${fieldDef.label} ${confBadge}</label>${inputHtml}`;
    return div;
}

function buildPersonSection(containerId, prefix, data, confidences) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";

    PERSON_FIELDS.forEach((fd) => {
        const value = data ? data[fd.key] : "";
        const confKey = `${prefix}.${fd.key}`;
        const conf = confidences?.[confKey]?.level || null;
        container.appendChild(createFormField(fd, prefix, value, conf));
    });
}

// ---------------------------------------------------------------------------
// Children & Siblings (dynamic add/remove)
// ---------------------------------------------------------------------------
let childCount = 0;
let siblingCount = 0;

const CHILD_FIELDS = [
    { key: "name", label: "Full Name", type: "text", fullWidth: true },
    { key: "relationship", label: "Relationship", type: "select", options: ["", "Son", "Daughter"] },
    { key: "dob", label: "Date of Birth", type: "date" },
    { key: "cob", label: "Country of Birth", type: "text" },
    { key: "address", label: "Current Address", type: "text", fullWidth: true },
    { key: "occupation", label: "Occupation", type: "text" },
    {
        key: "marital_status",
        label: "Marital Status",
        type: "select",
        options: ["", "Single", "Married", "Common-Law", "Divorced", "Separated", "Widowed", "Annulled"],
    },
];

const SIBLING_FIELDS = [
    { key: "name", label: "Full Name", type: "text", fullWidth: true },
    { key: "relationship", label: "Relationship", type: "select", options: ["", "Brother", "Sister"] },
    { key: "dob", label: "Date of Birth", type: "date" },
    { key: "cob", label: "Country of Birth", type: "text" },
    { key: "address", label: "Current Address", type: "text", fullWidth: true },
    { key: "occupation", label: "Occupation", type: "text" },
    {
        key: "marital_status",
        label: "Marital Status",
        type: "select",
        options: ["", "Single", "Married", "Common-Law", "Divorced", "Separated", "Widowed", "Annulled"],
    },
];

function addPersonCard(containerId, indexPrefix, index, fields, data, maxLabel) {
    const container = document.getElementById(containerId);
    const card = document.createElement("div");
    card.className = "person-card";
    card.id = `${indexPrefix}_card_${index}`;

    const header = document.createElement("div");
    header.className = "person-card-header";
    header.innerHTML = `
        <span class="person-card-title">${maxLabel} ${index + 1}</span>
        <div>
            <select data-field="${indexPrefix}_${index}_accompanying" style="margin-right:8px;padding:4px 8px;background:var(--bg-input);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);font-size:12px;">
                <option value="">Accompanying?</option>
                <option value="yes" ${data?.accompanying === true ? "selected" : ""}>Yes</option>
                <option value="no" ${data?.accompanying === false ? "selected" : ""}>No</option>
            </select>
            <button class="btn btn-sm btn-danger" onclick="this.closest('.person-card').remove()">×</button>
        </div>`;
    card.appendChild(header);

    const grid = document.createElement("div");
    grid.className = "form-grid";
    fields.forEach((fd) => {
        const value = data ? data[fd.key] : "";
        grid.appendChild(createFormField(fd, `${indexPrefix}_${index}`, value, null));
    });
    card.appendChild(grid);
    container.appendChild(card);
}

addChildBtn.addEventListener("click", () => {
    if (childCount >= 4) {
        alert("Maximum 4 children (form limit for Section B)");
        return;
    }
    addPersonCard("childrenContainer", "child", childCount, CHILD_FIELDS, null, "Child");
    childCount++;
});

addSiblingBtn.addEventListener("click", () => {
    if (siblingCount >= 7) {
        alert("Maximum 7 siblings (form limit for Section C)");
        return;
    }
    addPersonCard("siblingsContainer", "sibling", siblingCount, SIBLING_FIELDS, null, "Sibling");
    siblingCount++;
});

// ---------------------------------------------------------------------------
// Populate form from AI extraction
// ---------------------------------------------------------------------------
function populateFormFromExtraction(data) {
    const raw = data.raw || {};
    const conf = data.confidence || {};

    // Application type
    const appType = raw.application_type || "visitor";
    const radio = document.querySelector(`input[name="appType"][value="${appType}"]`);
    if (radio) radio.checked = true;

    // Applicant
    buildPersonSection("applicantFields", "app", raw.applicant, conf);

    // Spouse
    buildPersonSection("spouseFields", "spouse", raw.spouse, conf);
    const spouseAcc = raw.spouse?.accompanying;
    if (spouseAcc === true) $("#spouseAccompanying").value = "yes";
    else if (spouseAcc === false) $("#spouseAccompanying").value = "no";

    // Mother
    buildPersonSection("motherFields", "mother", raw.mother, conf);
    const motherAcc = raw.mother?.accompanying;
    if (motherAcc === true) $("#motherAccompanying").value = "yes";
    else if (motherAcc === false) $("#motherAccompanying").value = "no";

    // Father
    buildPersonSection("fatherFields", "father", raw.father, conf);
    const fatherAcc = raw.father?.accompanying;
    if (fatherAcc === true) $("#fatherAccompanying").value = "yes";
    else if (fatherAcc === false) $("#fatherAccompanying").value = "no";

    // Children
    childCount = 0;
    document.getElementById("childrenContainer").innerHTML = "";
    const children = raw.children || [];
    children.forEach((child) => {
        addPersonCard("childrenContainer", "child", childCount, CHILD_FIELDS, child, "Child");
        childCount++;
    });

    // Siblings
    siblingCount = 0;
    document.getElementById("siblingsContainer").innerHTML = "";
    const siblings = raw.siblings || [];
    siblings.forEach((sib) => {
        addPersonCard("siblingsContainer", "sibling", siblingCount, SIBLING_FIELDS, sib, "Sibling");
        siblingCount++;
    });
}

function initEmptyForm() {
    buildPersonSection("applicantFields", "app", {}, {});
    buildPersonSection("spouseFields", "spouse", {}, {});
    buildPersonSection("motherFields", "mother", {}, {});
    buildPersonSection("fatherFields", "father", {}, {});
    childCount = 0;
    siblingCount = 0;
    document.getElementById("childrenContainer").innerHTML = "";
    document.getElementById("siblingsContainer").innerHTML = "";
}

// ---------------------------------------------------------------------------
// Collect form data for filling
// ---------------------------------------------------------------------------
function collectFormData() {
    const fields = {};

    // Application type
    const appType = document.querySelector('input[name="appType"]:checked')?.value || "visitor";
    ["visitor", "worker", "student", "other"].forEach((t) => {
        fields[t] = t === appType ? "1" : "0";
    });

    // Gather all input/select elements with data-field
    $$("[data-field]").forEach((el) => {
        const key = el.dataset.field;
        const val = el.value?.trim();
        if (val) fields[key] = val;
    });

    // Accompanying fields
    [
        { sel: "#spouseAccompanying", yesKey: "spouse_accompanying_yes", noKey: "spouse_accompanying_no" },
        { sel: "#motherAccompanying", yesKey: "mother_accompanying_yes", noKey: "mother_accompanying_no" },
        { sel: "#fatherAccompanying", yesKey: "father_accompanying_yes", noKey: "father_accompanying_no" },
    ].forEach(({ sel, yesKey, noKey }) => {
        const val = $(sel)?.value;
        if (val === "yes") { fields[yesKey] = true; fields[noKey] = false; }
        else if (val === "no") { fields[yesKey] = false; fields[noKey] = true; }
    });

    return fields;
}

// ---------------------------------------------------------------------------
// Fill & Download
// ---------------------------------------------------------------------------
fillBtn.addEventListener("click", async () => {
    const formFields = collectFormData();
    const filledCount = Object.keys(formFields).length;

    if (filledCount < 3) {
        fillStatus.className = "status-msg error";
        fillStatus.textContent = "❌ Please fill in at least some fields before generating the PDF";
        return;
    }

    fillBtn.disabled = true;
    fillBtn.textContent = "⏳ Generating PDF...";
    fillStatus.textContent = "";

    try {
        const res = await fetch("/canada/api/fill", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                form_fields: formFields,
                session_id: sessionId || "manual",
            }),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.error || "Fill failed");

        downloadLink.href = data.download_url;
        downloadLink.download = data.filename;
        goToStep(4);
    } catch (e) {
        fillStatus.className = "status-msg error";
        fillStatus.textContent = `❌ ${e.message}`;
    } finally {
        fillBtn.disabled = false;
        fillBtn.textContent = "✍️ Fill PDF & Download";
    }
});

// ---------------------------------------------------------------------------
// Start Over
// ---------------------------------------------------------------------------
startOverBtn.addEventListener("click", () => {
    selectedFiles = [];
    sessionId = null;
    extractedData = null;
    childCount = 0;
    siblingCount = 0;
    renderFileList();
    uploadStatus.textContent = "";
    extractStatus.textContent = "";
    fillStatus.textContent = "";
    goToStep(1);
});

// ---------------------------------------------------------------------------
// Init: check template
// ---------------------------------------------------------------------------
async function checkTemplate() {
    try {
        const res = await fetch("/canada/api/check-template");
        const data = await res.json();
        if (data.available) {
            templateStatus.className = "status-badge ok";
            templateStatus.textContent = "✅ Template ready";
        } else {
            templateStatus.className = "status-badge error";
            templateStatus.textContent = "❌ Template missing";
        }
    } catch {
        templateStatus.className = "status-badge error";
        templateStatus.textContent = "❌ Cannot connect";
    }
}

// Boot
checkTemplate();
initEmptyForm();
