// ==UserScript==
// @name         07. DS 160 - Passport Information
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.1
// @description  Fix hoàn toàn Issuance Date & Expiration Date (nhận cả số 10 hoặc OCT)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/Passport_Visa_Info.aspx?node=PptVisa
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        pptType: "R",
        pptNumber: "A12345678",
        bookNumber: "",                  // để trống = tự tick Does Not Apply
        issuedCountry: "Vietnam",
        issuedCity: "Ho Chi Minh City",
        issuedState: "",
        issuedCountryRegion: "Vietnam",
        issuance: { day: "15", month: "06", year: "2019" },   // month: "06" hoặc "JUN" hoặc "6" đều được
        expiration: { day: "15", month: "06", year: "2029" },
        noExpiration: false,             // true = tick "No Expiration"
        everLost: "Y",
        lost: {
            number: "",
            country: "Vietnam",
            explain: "Lost during travel in 2022"
        }
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

    function normalizeMonth(m) {
        if (!m) return "";
        const str = String(m).trim().toUpperCase();
        const map = {
            "1":"01","JAN":"01","2":"02","FEB":"02","3":"03","MAR":"03",
            "4":"04","APR":"04","5":"05","MAY":"05","6":"06","JUN":"06",
            "7":"07","JUL":"07","8":"08","AUG":"08","9":"09","SEP":"09",
            "10":"10","OCT":"10","11":"11","NOV":"11","12":"12","DEC":"12"
        };
        return map[str] || str.padStart(2, "0");
    }

    function selectCountry(dropdownId, countryName) {
        const select = document.getElementById(dropdownId);
        if (!select) return;
        const name = (countryName || "").toUpperCase().trim();
        for (let opt of select.options) {
            if (opt.value.toUpperCase() === name || opt.text.toUpperCase().includes(name) || opt.text.toUpperCase().includes("VIETNAM")) {
                select.value = opt.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL PASSPORT (v7.1)", "color:#0066cc;font-weight:bold");

        // Passport Type & Number
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_TYPE").value = config.pptType;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_NUM").value = config.pptNumber;

        // Book Number - tự tick Does Not Apply
        const bookInput = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_BOOK_NUM");
        const bookNA = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexPPT_BOOK_NUM_NA");
        if (bookInput) bookInput.value = config.bookNumber || "";
        if (bookNA) {
            const isNA = !config.bookNumber || config.bookNumber.trim() === "";
            bookNA.checked = isNA;
            if (isNA && bookInput) bookInput.value = "";
        }

        // Country & Issued Place
        selectCountry("ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_CNTRY", config.issuedCountry);
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_ISSUED_IN_CITY").value = config.issuedCity;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_ISSUED_IN_STATE").value = config.issuedState || "";
        selectCountry("ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_IN_CNTRY", config.issuedCountryRegion);

        // ================== ISSUANCE DATE (đã fix) ==================
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_DTEDay").value = config.issuance.day;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_ISSUED_DTEMonth").value = normalizeMonth(config.issuance.month);
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_ISSUEDYear").value = config.issuance.year;

        // ================== EXPIRATION DATE (đã fix) ==================
        const expNA = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbxPPT_EXPIRE_NA");
        if (config.noExpiration && expNA) {
            expNA.checked = true;
            expNA.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_EXPIRE_DTEDay").value = config.expiration.day;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPPT_EXPIRE_DTEMonth").value = normalizeMonth(config.expiration.month);
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxPPT_EXPIREYear").value = config.expiration.year;
        }

        // Lost/Stolen (giữ nguyên như cũ)
        const lostYes = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_rblLOST_PPT_IND_0");
        const lostNo = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_rblLOST_PPT_IND_1");
        if (config.everLost === "Y" && lostYes) lostYes.click();
        else if (lostNo) lostNo.click();

        if (config.everLost === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlLostPPT_ctl00_tbxLOST_PPT_NUM");
            const lostNum = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlLostPPT_ctl00_tbxLOST_PPT_NUM");
            const lostNA = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlLostPPT_ctl00_cbxLOST_PPT_NUM_UNKN_IND");
            if (lostNum) lostNum.value = config.lost.number || "";
            if (lostNA) {
                const isUnknown = !config.lost.number || config.lost.number.trim() === "";
                lostNA.checked = isUnknown;
            }
            selectCountry("ctl00_SiteContentPlaceHolder_FormView1_dtlLostPPT_ctl00_ddlLOST_PPT_NATL", config.lost.country);
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dtlLostPPT_ctl00_tbxLOST_PPT_EXPL").value = config.lost.explain || "";
        }

        console.log("%c🎉 HOÀN TẤT PASSPORT v7.1 - Date đã fix!", "color:green;font-weight:bold");
        alert("✅ ĐÃ ĐIỀN XONG PASSPORT (v7.1)!\n• Issuance Date & Expiration Date đã điền đúng\n• Month nhận cả số 10 hoặc OCT\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillPassportBtn")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillPassportBtn";
        btn.innerHTML = "🛠 AUTO FILL PASSPORT v7.1";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();