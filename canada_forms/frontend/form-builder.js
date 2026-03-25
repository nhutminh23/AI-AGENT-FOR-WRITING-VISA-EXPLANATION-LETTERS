/**
 * form-builder.js — Step 3: Build and populate review form
 *
 * Shared form field definitions, dynamic person card creation,
 * and data collection for PDF filling.
 */

const FormBuilder = (() => {
    // -----------------------------------------------------------------------
    // Field definitions
    // -----------------------------------------------------------------------
    // Applicant & Spouse: PDF-specific marital status values
    const APPLICANT_SPOUSE_FIELDS = [
        { key: "name", label: "Full Name", type: "text", fullWidth: true },
        { key: "dob", label: "Date of Birth", type: "date" },
        { key: "cob", label: "Country of Birth", type: "text" },
        { key: "address", label: "Current Address", type: "text", fullWidth: true },
        { key: "occupation", label: "Occupation", type: "text" },
        {
            key: "marital_status",
            label: "Marital Status",
            type: "select",
            options: ["", "Annulled marriage", "Common-law", "Divorced", "Legally separated", "Married-physically present", "Married-not physically present", "Single", "Widowed"],
        },
    ];

    // Mother & Father: simple marital status values
    const PARENT_FIELDS = [
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

    // Counters
    let childCount = 0;
    let siblingCount = 0;

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------
    function createFormField(fieldDef, prefix, value) {
        const div = document.createElement("div");
        div.className = "form-field" + (fieldDef.fullWidth ? " full-width" : "");

        const id = `${prefix}_${fieldDef.key}`;
        let inputHtml;

        if (fieldDef.type === "select") {
            const opts = fieldDef.options
                .map((o) => `<option value="${o}" ${o === value ? "selected" : ""}>${o || "— Select —"}</option>`)
                .join("");
            inputHtml = `<select id="${id}" data-field="${id}">${opts}</select>`;
        } else {
            const v = value || "";
            const escaped = String(v).replace(/"/g, "&quot;");
            inputHtml = `<input type="${fieldDef.type}" id="${id}" data-field="${id}" value="${escaped}">`;
        }

        div.innerHTML = `<label>${fieldDef.label}</label>${inputHtml}`;
        return div;
    }

    // Normalize marital_status from Grok → exact PDF dropdown value
    function normalizeMaritalStatus(v) {
        if (!v) return "";
        const lower = v.toLowerCase().trim();
        const map = {
            "married": "Married-physically present",
            "single": "Single",
            "divorced": "Divorced",
            "widowed": "Widowed",
            "common-law": "Common-law",
            "commonlaw": "Common-law",
            "separated": "Legally separated",
            "annulled": "Annulled marriage",
        };
        return map[lower] || v; // Return original if already exact match
    }

    function buildPersonSection(containerId, prefix, data, fields, shouldNormalize) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = "";

        fields.forEach((fd) => {
            // Grok returns "country_of_birth", our field key is "cob"
            let value = data ? (data[fd.key] || (fd.key === "cob" ? data["country_of_birth"] : null)) : "";
            if (fd.key === "marital_status" && value && shouldNormalize) value = normalizeMaritalStatus(value);
            container.appendChild(createFormField(fd, prefix, value));
        });
    }

    function addPersonCard(containerId, indexPrefix, index, fields, data, label) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const card = document.createElement("div");
        card.className = "person-card";
        card.id = `${indexPrefix}_card_${index}`;

        const header = document.createElement("div");
        header.className = "person-card-header";
        header.innerHTML = `
            <span class="person-card-title">${label} ${index + 1}</span>
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
            let value = data ? (data[fd.key] || (fd.key === "cob" ? data["country_of_birth"] : null)) : "";
            grid.appendChild(createFormField(fd, `${indexPrefix}_${index}`, value));
        });
        card.appendChild(grid);
        container.appendChild(card);
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------
    function populateFromJson(rawData) {
        // Application type
        const appType = rawData.application_type || "visitor";
        const radio = document.querySelector(`input[name="appType"][value="${appType}"]`);
        if (radio) radio.checked = true;

        // Applicant (normalize marital status)
        buildPersonSection("applicantFields", "app", rawData.applicant, APPLICANT_SPOUSE_FIELDS, true);

        // Spouse (normalize marital status)
        buildPersonSection("spouseFields", "spouse", rawData.spouse, APPLICANT_SPOUSE_FIELDS, true);
        const spouseAcc = rawData.spouse?.accompanying;
        const spouseEl = document.getElementById("spouseAccompanying");
        if (spouseEl) {
            if (spouseAcc === true) spouseEl.value = "yes";
            else if (spouseAcc === false) spouseEl.value = "no";
        }

        // Mother
        buildPersonSection("motherFields", "mother", rawData.mother, PARENT_FIELDS, false);
        const motherAcc = rawData.mother?.accompanying;
        const motherEl = document.getElementById("motherAccompanying");
        if (motherEl) {
            if (motherAcc === true) motherEl.value = "yes";
            else if (motherAcc === false) motherEl.value = "no";
        }

        // Father
        buildPersonSection("fatherFields", "father", rawData.father, PARENT_FIELDS, false);
        const fatherAcc = rawData.father?.accompanying;
        const fatherEl = document.getElementById("fatherAccompanying");
        if (fatherEl) {
            if (fatherAcc === true) fatherEl.value = "yes";
            else if (fatherAcc === false) fatherEl.value = "no";
        }

        // Children
        childCount = 0;
        const childContainer = document.getElementById("childrenContainer");
        if (childContainer) childContainer.innerHTML = "";
        const children = rawData.children || [];
        children.forEach((child) => {
            addPersonCard("childrenContainer", "child", childCount, CHILD_FIELDS, child, "Child");
            childCount++;
        });

        // Siblings
        siblingCount = 0;
        const sibContainer = document.getElementById("siblingsContainer");
        if (sibContainer) sibContainer.innerHTML = "";
        const siblings = rawData.siblings || [];
        siblings.forEach((sib) => {
            addPersonCard("siblingsContainer", "sibling", siblingCount, SIBLING_FIELDS, sib, "Sibling");
            siblingCount++;
        });
    }

    function initEmptyForm() {
        buildPersonSection("applicantFields", "app", {}, APPLICANT_SPOUSE_FIELDS, false);
        buildPersonSection("spouseFields", "spouse", {}, APPLICANT_SPOUSE_FIELDS, false);
        buildPersonSection("motherFields", "mother", {}, PARENT_FIELDS, false);
        buildPersonSection("fatherFields", "father", {}, PARENT_FIELDS, false);
        childCount = 0;
        siblingCount = 0;
        const cc = document.getElementById("childrenContainer");
        const sc = document.getElementById("siblingsContainer");
        if (cc) cc.innerHTML = "";
        if (sc) sc.innerHTML = "";
    }

    function addChild() {
        if (childCount >= 4) {
            alert("Tối đa 4 children (giới hạn Section B)");
            return;
        }
        addPersonCard("childrenContainer", "child", childCount, CHILD_FIELDS, null, "Child");
        childCount++;
    }

    function addSibling() {
        if (siblingCount >= 7) {
            alert("Tối đa 7 siblings (giới hạn Section C)");
            return;
        }
        addPersonCard("siblingsContainer", "sibling", siblingCount, SIBLING_FIELDS, null, "Sibling");
        siblingCount++;
    }

    function collectFormData() {
        const fields = {};

        // Application type
        const appType = document.querySelector('input[name="appType"]:checked')?.value || "visitor";
        ["visitor", "worker", "student", "other"].forEach((t) => {
            fields[t] = t === appType ? "1" : "0";
        });

        // All input/select elements with data-field
        document.querySelectorAll("[data-field]").forEach((el) => {
            const key = el.dataset.field;
            const val = el.value?.trim();
            if (val) fields[key] = val;
        });

        // DEBUG: log child/sibling keys
        const debugKeys = Object.entries(fields)
            .filter(([k]) => k.includes("child") || k.includes("sibling"))
            .sort(([a], [b]) => a.localeCompare(b));
        console.log("=== collectFormData child/sibling keys ===", debugKeys);

        // Accompanying fields for Section A (spouse, mother, father)
        [
            { sel: "#spouseAccompanying", yesKey: "spouse_accompanying_yes", noKey: "spouse_accompanying_no" },
            { sel: "#motherAccompanying", yesKey: "mother_accompanying_yes", noKey: "mother_accompanying_no" },
            { sel: "#fatherAccompanying", yesKey: "father_accompanying_yes", noKey: "father_accompanying_no" },
        ].forEach(({ sel, yesKey, noKey }) => {
            const el = document.querySelector(sel);
            const val = el?.value;
            if (val === "yes") { fields[yesKey] = true; fields[noKey] = false; }
            else if (val === "no") { fields[yesKey] = false; fields[noKey] = true; }
        });

        // Accompanying fields for Section B (children) and Section C (siblings)
        document.querySelectorAll("[data-field]").forEach((el) => {
            const key = el.dataset.field;
            const val = el.value?.trim();
            // Match patterns like "child_0_accompanying" or "sibling_2_accompanying"
            const m = key.match(/^(child|sibling)_(\d+)_accompanying$/);
            if (m) {
                const prefix = m[1];
                const idx = m[2];
                if (val === "yes") {
                    fields[`${prefix}_${idx}_accompanying_yes`] = true;
                    fields[`${prefix}_${idx}_accompanying_no`] = false;
                } else if (val === "no") {
                    fields[`${prefix}_${idx}_accompanying_yes`] = false;
                    fields[`${prefix}_${idx}_accompanying_no`] = true;
                }
                // Remove the raw "child_0_accompanying" key
                delete fields[key];
            }
        });

        console.log("=== FINAL form_fields ===", JSON.stringify(fields, null, 2));

        return fields;
    }

    return {
        populateFromJson,
        initEmptyForm,
        addChild,
        addSibling,
        collectFormData,
    };
})();
