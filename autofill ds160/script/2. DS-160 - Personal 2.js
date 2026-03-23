// ==UserScript==
// @name         02. DS 160 - Personal 2
// @namespace    http://tampermonkey.net/
// @version      2026-03-05-v6.7
// @description  1 click điền Personal 2 - ĐÃ FIX chọn No cho câu hỏi passport của Other Nationality
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_personalcont.aspx?node=Personal2
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        nationality: "Vietnam",
        hasOtherNationality: false,          // true = có quốc tịch khác
        otherNationality: "Canada",
        hasOtherPassport: false,            // ← Đổi thành false để test "No"
        otherPassportNumber: "AB1234567",   // chỉ dùng khi hasOtherPassport = true
        isOtherPermanentResident: false,
        otherPermanentResident: "Benin",
        nationalId: "1234",                 // để trống = tự tick Does Not Apply
        ssn1: "", ssn2: "", ssn3: "",       // để trống = tự tick
        taxId: ""                           // để trống = tự tick
    };
    // =================================================================

    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function waitForElement(selector, timeout = 8000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const el = document.querySelector(selector);
            if (el && el.offsetParent !== null) return el;
            await sleep(300);
        }
        return null;
    }

    function setValue(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.value = value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function triggerRadio(radioId) {
        const radio = document.getElementById(radioId);
        if (radio) {
            radio.checked = true;
            radio.click();
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function tickDoesNotApply(checkboxId, shouldTick) {
        const cb = document.getElementById(checkboxId);
        if (cb && cb.checked !== shouldTick) cb.click();
    }

    function selectCountryDropdown(ddlId, countryName) {
        const ddl = document.getElementById(ddlId);
        if (!ddl) return;
        const search = (countryName || "").toUpperCase().trim();
        for (let opt of ddl.options) {
            if (opt.value.toUpperCase() === search || opt.text.toUpperCase().includes(search)) {
                ddl.value = opt.value;
                ddl.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL Personal 2 (v6.7)", "color:#0066cc;font-weight:bold");

        // Quốc tịch chính
        selectCountryDropdown("ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_NATL", config.nationality);

        // ====================== OTHER NATIONALITY ======================
        if (config.hasOtherNationality) {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblAPP_OTH_NATL_IND_0");

            const otherDDL = await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlOTHER_NATL_ctl00_ddlOTHER_NATL");
            if (otherDDL) selectCountryDropdown(otherDDL.id, config.otherNationality);

            // ================== CÂU HỎI PASSPORT (ĐÃ FIX CẢ YES/NO) ==================
            await sleep(800); // chờ sub-form hiện ra

            if (config.hasOtherPassport) {
                triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_dtlOTHER_NATL_ctl00_rblOTHER_PPT_IND_0");
                const pptField = await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlOTHER_NATL_ctl00_tbxOTHER_PPT_NUM");
                if (pptField) setValue("ctl00_SiteContentPlaceHolder_FormView1_dtlOTHER_NATL_ctl00_tbxOTHER_PPT_NUM", config.otherPassportNumber);
            } else {
                triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_dtlOTHER_NATL_ctl00_rblOTHER_PPT_IND_1");
            }
        } else {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblAPP_OTH_NATL_IND_1");
        }

        // ====================== OTHER PERMANENT RESIDENT ======================
        if (config.isOtherPermanentResident) {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblPermResOtherCntryInd_0");
            const permDDL = await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlOthPermResCntry_ctl00_ddlOthPermResCntry");
            if (permDDL) selectCountryDropdown(permDDL.id, config.otherPermanentResident);
        } else {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblPermResOtherCntryInd_1");
        }

        // ====================== 3 TRƯỜNG DOES NOT APPLY ======================
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_NATIONAL_ID", config.nationalId);
        tickDoesNotApply("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_NATIONAL_ID_NA", !config.nationalId);

        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_SSN1", config.ssn1);
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_SSN2", config.ssn2);
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_SSN3", config.ssn3);
        const hasSSN = !!(config.ssn1 || config.ssn2 || config.ssn3);
        tickDoesNotApply("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_SSN_NA", !hasSSN);

        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_TAX_ID", config.taxId);
        tickDoesNotApply("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_TAX_ID_NA", !config.taxId);

        alert("✅ ĐÃ ĐIỀN XONG PERSONAL 2 (v6.7) - Đã fix chọn No cho passport!\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillPersonal2")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillPersonal2";
        btn.textContent = "🛠 AUTO FILL PERSONAL 2";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();