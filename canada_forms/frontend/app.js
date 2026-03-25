/**
 * app.js — Main orchestrator
 *
 * Step navigation + event wiring.
 * Delegates logic to: PromptStep, JsonPaste, FormBuilder, PdfFiller
 */

// -----------------------------------------------------------------------
// DOM helpers
// -----------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
let parsedJsonData = null;

// -----------------------------------------------------------------------
// Step Navigation
// -----------------------------------------------------------------------
function goToStep(stepNum) {
    $$(".step-content").forEach((el) => el.classList.remove("active"));
    $(`#step${stepNum}`)?.classList.add("active");

    $$(".steps-bar .step").forEach((el) => {
        const s = parseInt(el.dataset.step);
        el.classList.toggle("active", s === stepNum);
        el.classList.toggle("completed", s < stepNum);
    });
}

// -----------------------------------------------------------------------
// Step 1: Copy Prompt
// -----------------------------------------------------------------------
$("#copyPromptBtn")?.addEventListener("click", () => PromptStep.copyPrompt());
$("#goToStep2Btn")?.addEventListener("click", () => goToStep(2));

// -----------------------------------------------------------------------
// Step 2: Paste JSON
// -----------------------------------------------------------------------
$("#backToStep1Btn")?.addEventListener("click", () => goToStep(1));

$("#applyJsonBtn")?.addEventListener("click", () => {
    const raw = $("#jsonInput")?.value || "";
    const result = JsonPaste.parseJson(raw);
    const status = $("#jsonStatus");

    if (!result.success) {
        status.className = "status-msg error";
        status.textContent = `❌ ${result.error}`;
        return;
    }

    parsedJsonData = result.data;
    FormBuilder.populateFromJson(parsedJsonData);

    status.className = "status-msg success";
    status.textContent = "✅ JSON applied! Chuyển sang Review...";

    setTimeout(() => goToStep(3), 500);
});

// -----------------------------------------------------------------------
// Step 3: Review & Edit
// -----------------------------------------------------------------------
$("#addChildBtn")?.addEventListener("click", () => FormBuilder.addChild());
$("#addSiblingBtn")?.addEventListener("click", () => FormBuilder.addSibling());
$("#backToStep2Btn")?.addEventListener("click", () => goToStep(2));

$("#fillBtn")?.addEventListener("click", async () => {
    const fillBtn = $("#fillBtn");
    const fillStatus = $("#fillStatus");

    fillBtn.disabled = true;
    fillBtn.textContent = "⏳ Đang tạo PDF...";
    fillStatus.textContent = "";

    const formFields = FormBuilder.collectFormData();
    const result = await PdfFiller.fillPdf(formFields);

    if (result.success) {
        const dl = $("#downloadLink");
        dl.href = result.downloadUrl;
        dl.download = result.filename;
        goToStep(4);
    } else {
        fillStatus.className = "status-msg error";
        fillStatus.textContent = `❌ ${result.error}`;
    }

    fillBtn.disabled = false;
    fillBtn.textContent = "✍️ Fill PDF & Download";
});

// -----------------------------------------------------------------------
// Step 4: Start Over
// -----------------------------------------------------------------------
$("#startOverBtn")?.addEventListener("click", () => {
    parsedJsonData = null;
    $("#jsonInput").value = "";
    $("#jsonStatus").textContent = "";
    $("#fillStatus").textContent = "";
    FormBuilder.initEmptyForm();
    goToStep(1);
});

// -----------------------------------------------------------------------
// Boot
// -----------------------------------------------------------------------
(async function init() {
    // Check template
    const templateOk = await PdfFiller.checkTemplate();
    const badge = $("#templateStatus");
    if (templateOk) {
        badge.className = "status-badge ok";
        badge.textContent = "✅ Template ready";
    } else {
        badge.className = "status-badge error";
        badge.textContent = "❌ Template missing";
    }

    // Load prompt
    PromptStep.loadPrompt();

    // Init empty form (for step 3 if user skips directly)
    FormBuilder.initEmptyForm();
})();
