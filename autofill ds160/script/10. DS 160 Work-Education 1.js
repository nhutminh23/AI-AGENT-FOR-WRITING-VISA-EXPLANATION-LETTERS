// ==UserScript==
// @name         10. DS 160 Work-Education 1
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.0
// @description  Fix lỗi tháng (10 hoặc OCT đều được) + tự động chờ form OTHER
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_workeducation1.aspx?node=WorkEducation1
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        occupation: "O",
        specifyOther: "Driver",
        employerName: "Duoc Kim Do Company Limited",
        address: {
            street1: "31/3-31/5 Pham Phu Thu Street",
            street2: "Ward 11, Tan Binh",
            city: "Ho Chi Minh City",
            state: "",
            stateNA: true,
            zip: "",
            zipNA: true,
            phone: "02839711994",
            country: "VTNM"
        },
        startDate: {
            day: "1",
            month: "10",        // Dùng "10" hoặc "OCT" đều được
            year: "2024"
        },
        monthlyIncome: "20000000 VND",
        incomeNA: false,
        duties: "Drive company vehicles."
    };
    // =================================================================

    // ===================== HÀM CHUYỂN ĐỔI THÁNG (SỬA LỖI) =====================
    function normalizeMonth(m) {
        if (!m) return "";
        const str = String(m).trim().toUpperCase();
        const map = {
            "1":"1","JAN":"1","2":"2","FEB":"2","3":"3","MAR":"3","4":"4","APR":"4",
            "5":"5","MAY":"5","6":"6","JUN":"6","7":"7","JUL":"7","8":"8","AUG":"8",
            "9":"9","SEP":"9","10":"10","OCT":"10","11":"11","NOV":"11","12":"12","DEC":"12"
        };
        return map[str] || str;
    }

    function normalizeOccupation(o) {
        const map = { /* giữ nguyên như cũ */ };
        const upper = String(o).trim().toUpperCase();
        return map[upper] || o;
    }
    // =================================================================

    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function waitForElement(selector, timeout = 7000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const el = document.querySelector(selector);
            if (el) return el;
            await sleep(200);
        }
        return null;
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL WORK/EDUCATION (v7.0)", "color:#0066cc;font-weight:bold");

        // Primary Occupation
        const occSelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPresentOccupation");
        occSelect.value = normalizeOccupation(config.occupation);
        occSelect.dispatchEvent(new Event('change', { bubbles: true }));

        // Nếu là OTHER
        if (config.occupation.toUpperCase() === "OTHER" || config.occupation === "O") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxExplainOtherPresentOccupation");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxExplainOtherPresentOccupation").value = config.specifyOther;
        }

        // Chờ form Employer/School
        await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchName");

        // Điền thông tin
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchName").value = config.employerName;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchAddr1").value = config.address.street1;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchAddr2").value = config.address.street2 || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxEmpSchCity").value = config.address.city;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxWORK_EDUC_ADDR_STATE").value = config.address.state || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbxWORK_EDUC_ADDR_STATE_NA").checked = config.address.stateNA;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxWORK_EDUC_ADDR_POSTAL_CD").value = config.address.zip || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbxWORK_EDUC_ADDR_POSTAL_CD_NA").checked = config.address.zipNA;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxWORK_EDUC_TEL").value = config.address.phone;

        // Country
        const countrySelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlEmpSchCountry");
        countrySelect.value = config.address.country === "Vietnam" ? "VTNM" : config.address.country;

        // Start Date - THÁNG ĐÃ SỬA
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlEmpDateFromDay").value = config.startDate.day;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlEmpDateFromMonth").value = normalizeMonth(config.startDate.month);
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxEmpDateFromYear").value = config.startDate.year;

        // Monthly Income & Duties
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxCURR_MONTHLY_SALARY").value = config.monthlyIncome;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbxCURR_MONTHLY_SALARY_NA").checked = config.incomeNA;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxDescribeDuties").value = config.duties;

        console.log("%c🎉 HOÀN TẤT WORK/EDUCATION v7.0 - Tháng đã fix!", "color:green;font-weight:bold");
        alert("✅ ĐÃ ĐIỀN XONG WORK/EDUCATION (v7.0)!\n• Tháng 10 hoặc OCT đều hoạt động\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillWorkEduBtn")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillWorkEduBtn";
        btn.innerHTML = "🛠 AUTO FILL WORK/EDUCATION v7.0";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();