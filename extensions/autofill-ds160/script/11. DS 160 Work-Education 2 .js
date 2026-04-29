// ==UserScript==
// @name         11. DS 160 Work-Education 2 
// @namespace    http://tampermonkey.net/
// @version      2026-03-05-v6.4
// @description  1 click điền hết + đã fix lỗi tháng (hỗ trợ "3" hoặc "MAR")
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_workeducation2.aspx?node=WorkEducation2
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        hasPreviousEmployed: "Y",
        previousEmployers: [
            {
                employerName: "Old Company Ltd",
                street1: "456 Le Loi",
                street2: "",
                city: "Ho Chi Minh City",
                state: "Ho Chi Minh",
                stateNA: false,
                zip: "700000",
                zipNA: false,
                country: "Vietnam",
                phone: "0909876543",
                jobTitle: "Senior Designer",
                supervisorSurname: "Tran",
                supervisorGiven: "Van B",
                supervisorSurnameNA: false,
                supervisorGivenNA: false,
                from: { day: "1", month: "3", year: "2020" },   // ← "3" hoặc "MAR" đều được
                to:   { day: "31", month: "12", year: "2022" },  // ← "12" hoặc "DEC"
                duties: "Design marketing materials and manage client projects"
            }
        ],

        hasEducation: "Y",
        schools: [
            {
                name: "University of Science",
                street1: "227 Nguyen Van Cu",
                street2: "",
                city: "Ho Chi Minh City",
                state: "Ho Chi Minh",
                stateNA: false,
                zip: "700000",
                zipNA: false,
                country: "Vietnam",
                courseOfStudy: "Graphic Design",
                from: { day: "1", month: "9", year: "2016" },
                to:   { day: "30", month: "6", year: "2020" }
            }
        ]
    };
    // =================================================================

    // ===================== HÀM CHUYỂN ĐỔI THÁNG (ĐÃ FIX) =====================
    function normalizeMonth(m) {
        const nameToNum = {
            "JAN":"1","FEB":"2","MAR":"3","APR":"4","MAY":"5","JUN":"6",
            "JUL":"7","AUG":"8","SEP":"9","OCT":"10","NOV":"11","DEC":"12"
        };
        m = String(m).trim().toUpperCase();
        return nameToNum[m] || m;   // Nếu là số thì giữ nguyên, nếu là tên thì chuyển thành số
    }

    function normalizeCountry(c) {
        return String(c).toUpperCase() === "VIETNAM" ? "VTNM" : c;
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

    function setCheckbox(id, checked) {
        const cb = document.getElementById(id);
        if (cb) {
            cb.checked = checked;
            cb.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU ONE-CLICK FULL v6.4 (đã fix tháng)", "color:#0066cc;font-weight:bold");

        // ================== PREVIOUS EMPLOYED ==================
        triggerRadio("PreviouslyEmployed", config.hasPreviousEmployed);

        if (config.hasPreviousEmployed === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl00_tbEmployerName");

            config.previousEmployers.forEach((emp, i) => {
                const p = `ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEmpl_ctl0${i}`;
                document.getElementById(p + "_tbEmployerName").value = emp.employerName;
                document.getElementById(p + "_tbEmployerStreetAddress1").value = emp.street1;
                document.getElementById(p + "_tbEmployerStreetAddress2").value = emp.street2 || "";
                document.getElementById(p + "_tbEmployerCity").value = emp.city;
                document.getElementById(p + "_tbxPREV_EMPL_ADDR_STATE").value = emp.state;
                setCheckbox(p + "_cbxPREV_EMPL_ADDR_STATE_NA", emp.stateNA);
                document.getElementById(p + "_tbxPREV_EMPL_ADDR_POSTAL_CD").value = emp.zip;
                setCheckbox(p + "_cbxPREV_EMPL_ADDR_POSTAL_CD_NA", emp.zipNA);

                const countrySel = document.getElementById(p + "_DropDownList2");
                if (countrySel) countrySel.value = normalizeCountry(emp.country);

                document.getElementById(p + "_tbEmployerPhone").value = emp.phone;
                document.getElementById(p + "_tbJobTitle").value = emp.jobTitle;

                document.getElementById(p + "_tbSupervisorSurname").value = emp.supervisorSurname;
                setCheckbox(p + "_cbxSupervisorSurname_NA", emp.supervisorSurnameNA);
                document.getElementById(p + "_tbSupervisorGivenName").value = emp.supervisorGiven;
                setCheckbox(p + "_cbxSupervisorGivenName_NA", emp.supervisorGivenNA);

                // From date (đã fix)
                document.getElementById(p + "_ddlEmpDateFromDay").value = emp.from.day;
                document.getElementById(p + "_ddlEmpDateFromMonth").value = normalizeMonth(emp.from.month);
                document.getElementById(p + "_tbxEmpDateFromYear").value = emp.from.year;

                // To date (đã fix)
                document.getElementById(p + "_ddlEmpDateToDay").value = emp.to.day;
                document.getElementById(p + "_ddlEmpDateToMonth").value = normalizeMonth(emp.to.month);
                document.getElementById(p + "_tbxEmpDateToYear").value = emp.to.year;

                document.getElementById(p + "_tbDescribeDuties").value = emp.duties;
            });
        }

        // ================== EDUCATION ==================
        triggerRadio("OtherEduc", config.hasEducation);

        if (config.hasEducation === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl00_tbxSchoolName");

            config.schools.forEach((sch, i) => {
                const p = `ctl00_SiteContentPlaceHolder_FormView1_dtlPrevEduc_ctl0${i}`;
                document.getElementById(p + "_tbxSchoolName").value = sch.name;
                document.getElementById(p + "_tbxSchoolAddr1").value = sch.street1;
                document.getElementById(p + "_tbxSchoolAddr2").value = sch.street2 || "";
                document.getElementById(p + "_tbxSchoolCity").value = sch.city;
                document.getElementById(p + "_tbxEDUC_INST_ADDR_STATE").value = sch.state;
                setCheckbox(p + "_cbxEDUC_INST_ADDR_STATE_NA", sch.stateNA);
                document.getElementById(p + "_tbxEDUC_INST_POSTAL_CD").value = sch.zip;
                setCheckbox(p + "_cbxEDUC_INST_POSTAL_CD_NA", sch.zipNA);

                const countrySel = document.getElementById(p + "_ddlSchoolCountry");
                if (countrySel) countrySel.value = normalizeCountry(sch.country);

                document.getElementById(p + "_tbxSchoolCourseOfStudy").value = sch.courseOfStudy;

                // From date (đã fix)
                document.getElementById(p + "_ddlSchoolFromDay").value = sch.from.day;
                document.getElementById(p + "_ddlSchoolFromMonth").value = normalizeMonth(sch.from.month);
                document.getElementById(p + "_tbxSchoolFromYear").value = sch.from.year;

                // To date (đã fix)
                document.getElementById(p + "_ddlSchoolToDay").value = sch.to.day;
                document.getElementById(p + "_ddlSchoolToMonth").value = normalizeMonth(sch.to.month);
                document.getElementById(p + "_tbxSchoolToYear").value = sch.to.year;
            });
        }

        finish();
    }

    function finish() {
        console.log("%c🎉 HOÀN TẤT ONE-CLICK FULL v6.4 (tháng đã fix)!", "color:green;font-weight:bold;font-size:16px");
        alert("✅ ĐÃ ĐIỀN HẾT + THÁNG ĐÃ HOẠT ĐỘNG!\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillWorkEdu2v64")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillWorkEdu2v64";
        btn.textContent = "🛠 AUTO FILL WORK/EDUCATION 2 (1 CLICK v6.4)";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();