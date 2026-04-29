// ==UserScript==
// @name         05. DS 160 - Previous U.S. Travel
// @namespace    http://tampermonkey.net/
// @version      2026-03-05-v7.0
// @description  1 click điền hết + hỗ trợ FULL Yes/No (không cần click thủ công)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_previousustravel.aspx?node=PreviousUSTravel
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        everBeenUS: "N",                    // ← Test "N" ở đây
        usVisit: { day: "15", month: "6", year: "2024", length: "10", lengthUnit: "D" },
        hadDriverLicense: "N",              // ← Test "N"
        driverLicense: { number: "1234", doNotKnow: false, state: "CA" },

        hadVisa: "N",                       // ← Test "N"
        lastVisa: { day: "20", month: "3", year: "2023", visaNumber: "1234", doNotKnowNumber: false, sameType: "Y", sameCountry: "Y", tenPrinted: "Y" },

        visaLostStolen: "N",                // ← Test "N"
        lostStolen: { year: "2023", explain: "Lost during travel" },

        visaCancelled: "N",                 // ← Test "N"
        cancelled: { explain: "test" },

        everRefused: "N",                   // ← Test "N"
        refusedExplain: "test",

        immigrantPetition: "N",             // ← Test "N"
        petitionExplain: "test"
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

    function triggerRadio(name, value) {
        const yes = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${name}_0`);
        const no  = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${name}_1`);
        const target = value === "Y" ? yes : no;
        if (target) {
            target.checked = true;
            target.click();
            target.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU ONE-CLICK FULL v7.0", "color:#0066cc;font-weight:bold;font-size:15px");

        // 1. Have you ever been in the U.S.?
        triggerRadio("PREV_US_TRAVEL_IND", config.everBeenUS);
        await sleep(800);

        if (config.everBeenUS === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_DTEDay");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_DTEDay").value = config.usVisit.day;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_DTEMonth").value = config.usVisit.month;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_tbxPREV_US_VISIT_DTEYear").value = config.usVisit.year;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_tbxPREV_US_VISIT_LOS").value = config.usVisit.length;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlPREV_US_VISIT_ctl00_ddlPREV_US_VISIT_LOS_CD").value = config.usVisit.lengthUnit;
        }

        // 2. Driver’s License?
        triggerRadio("PREV_US_DRIVER_LIC_IND", config.hadDriverLicense);
        await sleep(800);

        if (config.hadDriverLicense === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlUS_DRIVER_LICENSE_ctl00_tbxUS_DRIVER_LICENSE");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlUS_DRIVER_LICENSE_ctl00_tbxUS_DRIVER_LICENSE").value = config.driverLicense.number || "";
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlUS_DRIVER_LICENSE_ctl00_cbxUS_DRIVER_LICENSE_NA").checked = config.driverLicense.doNotKnow;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlUS_DRIVER_LICENSE_ctl00_ddlUS_DRIVER_LICENSE_STATE").value = config.driverLicense.state;
        }

        // 3. U.S. Visa?
        triggerRadio("PREV_VISA_IND", config.hadVisa);
        await sleep(800);

        if (config.hadVisa === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_FOIL_NUMBER");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPREV_VISA_ISSUED_DTEDay").value = config.lastVisa.day;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPREV_VISA_ISSUED_DTEMonth").value = config.lastVisa.month;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_ISSUED_DTEYear").value = config.lastVisa.year;

            const vNum = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_FOIL_NUMBER");
            const vNA = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbxPREV_VISA_FOIL_NUMBER_NA");
            if (vNum) vNum.value = config.lastVisa.visaNumber || "";
            if (vNA) vNA.checked = config.lastVisa.doNotKnowNumber;

            triggerRadio("PREV_VISA_SAME_TYPE_IND", config.lastVisa.sameType);
            triggerRadio("PREV_VISA_SAME_CNTRY_IND", config.lastVisa.sameCountry);
            triggerRadio("PREV_VISA_TEN_PRINT_IND", config.lastVisa.tenPrinted);
        }

        // 4. Lost or Stolen?
        triggerRadio("PREV_VISA_LOST_IND", config.visaLostStolen);
        await sleep(800);
        if (config.visaLostStolen === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_LOST_YEAR");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_LOST_YEAR").value = config.lostStolen.year;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_LOST_EXPL").value = config.lostStolen.explain;
        }

        // 5. Cancelled or Revoked?
        triggerRadio("PREV_VISA_CANCELLED_IND", config.visaCancelled);
        await sleep(800);
        if (config.visaCancelled === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_CANCELLED_EXPL");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_CANCELLED_EXPL").value = config.cancelled.explain;
        }

        // 6. Refused?
        triggerRadio("PREV_VISA_REFUSED_IND", config.everRefused);
        await sleep(800);
        if (config.everRefused === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_REFUSED_EXPL");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPREV_VISA_REFUSED_EXPL").value = config.refusedExplain;
        }

        // 7. Immigrant Petition?
        triggerRadio("IV_PETITION_IND", config.immigrantPetition);
        await sleep(800);
        if (config.immigrantPetition === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxIV_PETITION_EXPL");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxIV_PETITION_EXPL").value = config.petitionExplain;
        }

        console.log("%c🎉 HOÀN TẤT ONE-CLICK FULL v7.0!", "color:green;font-weight:bold;font-size:16px");
        alert("✅ ĐÃ ĐIỀN HẾT + TỰ ĐỘNG XỬ LÝ TẤT CẢ CÂU Yes/No!\nKiểm tra lại rồi Next nhé Paul!");
    }

    // ================== NÚT AUTO FILL ==================
    function addButton() {
        if (document.getElementById("autoFillPrevUSv7")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillPrevUSv7";
        btn.textContent = "🛠 AUTO FILL FULL (1 CLICK v7.0)";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", () => fillForm());
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();