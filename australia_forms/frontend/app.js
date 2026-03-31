/**
 * Australia Form 54 — app.js
 * All-in-one: step navigation, prompt, JSON parsing, form building, PDF filling.
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// -----------------------------------------------------------------------
// Field definitions (matches fill_54.py semantic keys)
// -----------------------------------------------------------------------
const APPLICANT_FIELDS = [
    { key: "ap_family_name",  label: "Family Name" },
    { key: "ap_given_name",   label: "Given Name(s)" },
    { key: "ap_dob",          label: "Date of Birth (DD/MM/YYYY)" },
    { key: "ap_marital",      label: "Marital Status" },
    { key: "ap_home_addr1",   label: "Home Address Line 1" },
    { key: "ap_home_addr2",   label: "Home Address Line 2" },
    // Note: ap.prev = 'Previous visits to Australia' date — not filled automatically
];

const SPOUSE_FIELDS = [
    { key: "as_family_name",  label: "Family Name" },
    { key: "as_given_name",   label: "Given Name(s)" },
    { key: "as_dob",          label: "Date of Birth" },
    { key: "as_marital",      label: "Marital Status" },
    { key: "as_home_addr1",   label: "Home Address Line 1" },
    { key: "as_home_addr2",   label: "Home Address Line 2" },
];

const DEFACTO_FIELDS = [
    { key: "as_defacto_family",  label: "Family Name" },
    { key: "as_defacto_given",   label: "Given Name(s)" },
    { key: "as_defacto_dob",     label: "Date of Birth" },
    { key: "as_defacto_marital", label: "Marital Status" },
    { key: "as_defacto_addr1",   label: "Home Address Line 1" },
    { key: "as_defacto_addr2",   label: "Home Address Line 2" },
];

const PERSON_FIELDS = [
    { subkey: "family_name",  label: "Family Name" },
    { subkey: "given_name",   label: "Given Name(s)" },
    { subkey: "dob",          label: "Date of Birth" },
    { subkey: "marital",      label: "Marital Status" },
    { subkey: "home_addr1",   label: "Home Address Line 1" },
    { subkey: "home_addr2",   label: "Home Address Line 2" },
    // prev_country removed: ap.prev / fm.*.prev = 'Previous visits to Australia' (date)
];

// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
let formData = {};
let promptText = "";

// -----------------------------------------------------------------------
// Step navigation
// -----------------------------------------------------------------------
function goToStep(n) {
    $$(".step-content").forEach((el) => el.classList.remove("active"));
    $(`#step${n}`)?.classList.add("active");
    $$(".steps-bar .step").forEach((el) => {
        const s = parseInt(el.dataset.step);
        el.classList.toggle("active", s === n);
        el.classList.toggle("completed", s < n);
    });
}

// -----------------------------------------------------------------------
// Step 1: Load & Copy Prompt
// -----------------------------------------------------------------------
async function loadPrompt() {
    try {
        const res = await fetch("/australia/api/prompt-template-54");
        const data = await res.json();
        if (data.prompt) {
            promptText = data.prompt;
            $("#promptDisplay").textContent = promptText;
            $("#copyPromptBtn").disabled = false;
        } else {
            $("#promptDisplay").textContent = "❌ Could not load prompt.";
        }
    } catch {
        $("#promptDisplay").textContent = "❌ Failed to load prompt template.";
    }
}

$("#copyPromptBtn")?.addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText(promptText);
        const status = $("#copyStatus");
        status.className = "status-msg success";
        status.textContent = "✅ Prompt copied to clipboard!";
        setTimeout(() => (status.textContent = ""), 3000);
    } catch {
        $("#copyStatus").className = "status-msg error";
        $("#copyStatus").textContent = "❌ Copy failed. Please select and copy manually.";
    }
});

$("#goToStep2Btn")?.addEventListener("click", () => goToStep(2));

// -----------------------------------------------------------------------
// Step 2: Parse JSON
// -----------------------------------------------------------------------
$("#backToStep1Btn")?.addEventListener("click", () => goToStep(1));

function parseGrokJson(raw) {
    let text = raw.trim();
    // Strip ```json ... ``` wrapper
    const cbMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (cbMatch) text = cbMatch[1].trim();

    try {
        return { success: true, data: JSON.parse(text) };
    } catch (e) {
        return { success: false, error: `Invalid JSON: ${e.message}` };
    }
}

function mapJsonToFormData(json) {
    const fd = {};

    // Applicant
    const ap = json.applicant || {};
    fd.ap_family_name  = ap.family_name || "";
    fd.ap_given_name   = ap.given_name || "";
    fd.ap_dob          = ap.dob || "";
    fd.ap_marital      = ap.marital_status || "";
    fd.ap_home_addr1   = ap.home_address_line1 || "";
    fd.ap_home_addr2   = ap.home_address_line2 || "";
    // ap_prev_country removed: ap.prev = 'Previous visits to Australia' date

    // Spouse
    const sp = json.spouse || {};
    fd.as_family_name  = sp.family_name || "";
    fd.as_given_name   = sp.given_name || "";
    fd.as_dob          = sp.dob || "";
    fd.as_marital      = sp.marital_status || "";
    fd.as_home_addr1   = sp.home_address_line1 || "";
    fd.as_home_addr2   = sp.home_address_line2 || "";
    // as_prev_country removed: as.prev = 'Previous visits to Australia' date

    // De facto partner
    const df = json.defacto_partner || {};
    if (df && df.family_name) {
        fd.as_defacto_family  = df.family_name || "";
        fd.as_defacto_given   = df.given_name || "";
        fd.as_defacto_dob     = df.dob || "";
        fd.as_defacto_marital = df.marital_status || "";
        fd.as_defacto_addr1   = df.home_address_line1 || "";
        fd.as_defacto_addr2   = df.home_address_line2 || "";
        // as_defacto_prev removed: as.defacto prev = 'Previous visits to Australia'
    }

    // Parents (max 2)
    const parents = json.parents || [];
    parents.slice(0, 2).forEach((p, i) => {
        fd[`parent_${i}_family_name`]  = p.family_name || "";
        fd[`parent_${i}_given_name`]   = p.given_name || "";
        fd[`parent_${i}_dob`]          = p.dob || "";
        fd[`parent_${i}_marital`]      = p.marital_status || "";
        fd[`parent_${i}_home_addr1`]   = p.home_address_line1 || "";
        fd[`parent_${i}_home_addr2`]   = p.home_address_line2 || "";
        // prev_country removed: fm.par prev = 'Previous visits to Australia'
    });

    // Siblings (max 3)
    const sibs = json.siblings || [];
    sibs.slice(0, 3).forEach((s, i) => {
        fd[`sibling_${i}_family_name`]  = s.family_name || "";
        fd[`sibling_${i}_given_name`]   = s.given_name || "";
        fd[`sibling_${i}_dob`]          = s.dob || "";
        fd[`sibling_${i}_marital`]      = s.marital_status || "";
        fd[`sibling_${i}_home_addr1`]   = s.home_address_line1 || "";
        fd[`sibling_${i}_home_addr2`]   = s.home_address_line2 || "";
        // prev_country removed: fm.sib prev = 'Previous visits to Australia'
    });

    // Children (max 3)
    const kids = json.children || [];
    kids.slice(0, 3).forEach((c, i) => {
        fd[`child_${i}_family_name`]  = c.family_name || "";
        fd[`child_${i}_given_name`]   = c.given_name || "";
        fd[`child_${i}_dob`]          = c.dob || "";
        fd[`child_${i}_marital`]      = c.marital_status || "";
        fd[`child_${i}_home_addr1`]   = c.home_address_line1 || "";
        fd[`child_${i}_home_addr2`]   = c.home_address_line2 || "";
        // prev_country removed: m.prev = 'Previous visits to Australia'
    });

    return fd;
}

$("#applyJsonBtn")?.addEventListener("click", () => {
    const raw = $("#jsonInput")?.value || "";
    const result = parseGrokJson(raw);
    const status = $("#jsonStatus");

    if (!result.success) {
        status.className = "status-msg error";
        status.textContent = `❌ ${result.error}`;
        return;
    }

    formData = mapJsonToFormData(result.data);
    buildReviewForm(formData, result.data);

    status.className = "status-msg success";
    status.textContent = "✅ JSON applied! Moving to review...";
    setTimeout(() => goToStep(3), 500);
});

// -----------------------------------------------------------------------
// Step 3: Build review form
// -----------------------------------------------------------------------
// Marital status options for form 54
const MARITAL_OPTIONS = [
    { value: "", label: "— Select —" },
    { value: "M", label: "M — Married" },
    { value: "E", label: "E — Engaged" },
    { value: "F", label: "F — De facto" },
    { value: "S", label: "S — Separated" },
    { value: "D", label: "D — Divorced" },
    { value: "W", label: "W — Widowed" },
    { value: "N", label: "N — Never married / Single" },
];

function isMaritalKey(key) {
    return key.includes("marital") || key.endsWith("_mar");
}

function createFieldInput(key, label, value) {
    const div = document.createElement("div");
    div.className = "form-field";

    if (isMaritalKey(key)) {
        // Render dropdown for marital status
        const normalizedValue = normalizeMaritalClient(value);
        const opts = MARITAL_OPTIONS.map(o =>
            `<option value="${o.value}"${o.value === normalizedValue ? " selected" : ""}>${o.label}</option>`
        ).join("");
        div.innerHTML = `
            <label>${label} <span style="font-size:11px;color:#f59e0b;">(code)</span></label>
            <select data-key="${key}">${opts}</select>
        `;
    } else {
        div.innerHTML = `
            <label>${label}</label>
            <input type="text" data-key="${key}" value="${(value || "").replace(/"/g, "&quot;")}">
        `;
    }
    return div;
}

function normalizeMaritalClient(value) {
    if (!value) return "";
    const map = {
        "married": "M", "engaged": "E", "de facto": "F", "defacto": "F",
        "separated": "S", "divorced": "D", "widowed": "W",
        "never married": "N", "single": "N", "minor": "N",
        "m": "M", "e": "E", "f": "F", "s": "S", "d": "D", "w": "W", "n": "N",
    };
    return map[value.trim().toLowerCase()] || value.trim();
}

function buildPersonCard(title, prefix, idx, data) {
    const card = document.createElement("div");
    card.className = "person-card";
    card.innerHTML = `<h4>${title}</h4><div class="form-grid"></div>`;
    const grid = card.querySelector(".form-grid");

    PERSON_FIELDS.forEach((f) => {
        const key = `${prefix}_${idx}_${f.subkey}`;
        grid.appendChild(createFieldInput(key, f.label, data[key] || ""));
    });

    return card;
}

function buildReviewForm(fd, rawJson) {
    // Applicant
    const apGrid = $("#applicantFields");
    apGrid.innerHTML = "";
    APPLICANT_FIELDS.forEach((f) => {
        apGrid.appendChild(createFieldInput(f.key, f.label, fd[f.key] || ""));
    });

    // Spouse
    const spGrid = $("#spouseFields");
    spGrid.innerHTML = "";
    SPOUSE_FIELDS.forEach((f) => {
        spGrid.appendChild(createFieldInput(f.key, f.label, fd[f.key] || ""));
    });

    // De Facto
    const dfSection = $("#defactoSection");
    if (rawJson.defacto_partner && rawJson.defacto_partner?.family_name) {
        dfSection.style.display = "block";
        const dfGrid = $("#defactoFields");
        dfGrid.innerHTML = "";
        DEFACTO_FIELDS.forEach((f) => {
            dfGrid.appendChild(createFieldInput(f.key, f.label, fd[f.key] || ""));
        });
    } else {
        dfSection.style.display = "none";
    }

    // Parents
    const parentsBox = $("#parentsContainer");
    parentsBox.innerHTML = "";
    const parentCount = (rawJson.parents || []).length;
    for (let i = 0; i < Math.max(parentCount, 2); i++) {
        parentsBox.appendChild(
            buildPersonCard(`Parent ${i + 1}`, "parent", i, fd)
        );
    }

    // Siblings
    const sibsBox = $("#siblingsContainer");
    sibsBox.innerHTML = "";
    const sibCount = (rawJson.siblings || []).length;
    for (let i = 0; i < Math.min(Math.max(sibCount, 0), 3); i++) {
        sibsBox.appendChild(
            buildPersonCard(`Sibling ${i + 1}`, "sibling", i, fd)
        );
    }

    // Children
    const kidsBox = $("#childrenContainer");
    kidsBox.innerHTML = "";
    const kidCount = (rawJson.children || []).length;
    for (let i = 0; i < Math.min(Math.max(kidCount, 0), 3); i++) {
        kidsBox.appendChild(
            buildPersonCard(`Child ${i + 1}`, "child", i, fd)
        );
    }
}

function collectFormData() {
    const fd = {};
    // Collect text inputs
    $$("input[data-key]").forEach((input) => {
        fd[input.dataset.key] = input.value.trim();
    });
    // Collect select dropdowns (marital status)
    $$("select[data-key]").forEach((sel) => {
        fd[sel.dataset.key] = sel.value.trim();
    });
    return fd;
}


$("#backToStep2Btn")?.addEventListener("click", () => goToStep(2));

// -----------------------------------------------------------------------
// Step 3→4: Fill PDF
// -----------------------------------------------------------------------
$("#fillBtn")?.addEventListener("click", async () => {
    const btn = $("#fillBtn");
    const status = $("#fillStatus");

    btn.disabled = true;
    btn.textContent = "⏳ Generating PDF...";
    status.textContent = "";

    const fields = collectFormData();

    try {
        const res = await fetch("/australia/api/fill-54", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ form_fields: fields }),
        });
        const data = await res.json();

        if (data.success) {
            const dl = $("#downloadLink");
            dl.href = data.download_url;
            dl.download = data.filename;
            goToStep(4);
        } else {
            status.className = "status-msg error";
            status.textContent = `❌ ${data.error}`;
        }
    } catch (err) {
        status.className = "status-msg error";
        status.textContent = `❌ Network error: ${err.message}`;
    }

    btn.disabled = false;
    btn.textContent = "✍️ Fill PDF & Download";
});

// -----------------------------------------------------------------------
// Step 4: Start Over
// -----------------------------------------------------------------------
$("#startOverBtn")?.addEventListener("click", () => {
    formData = {};
    $("#jsonInput").value = "";
    $("#jsonStatus").textContent = "";
    $("#fillStatus").textContent = "";
    goToStep(1);
});

// -----------------------------------------------------------------------
// Boot
// -----------------------------------------------------------------------
(async function init() {
    // Check template
    try {
        const res = await fetch("/australia/api/check-template");
        const data = await res.json();
        const badge = $("#templateStatus");
        if (data.form54_available) {
            badge.className = "status-badge ok";
            badge.textContent = "✅ Template ready";
        } else {
            badge.className = "status-badge error";
            badge.textContent = "❌ Template 54.pdf missing";
        }
    } catch {
        const badge = $("#templateStatus");
        badge.className = "status-badge error";
        badge.textContent = "❌ Server error";
    }

    // Load prompt
    loadPrompt();
})();
