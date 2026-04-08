// ==UserScript==
// @name         09. DS 160 - Family Information
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.1
// @description  Fix hoàn toàn: cho phép chỉ nhập năm sinh (không tự tick Do Not Know)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_family1.aspx?node=Relatives
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        // Father
        father: {
            surname: "Nguyen",
            givenName: "Van A",
            dobDay: "",              // ← Để trống nếu không biết
            dobMonth: "",            // ← Để trống nếu không biết
            dobYear: "1970",         // ← Chỉ điền năm thì form vẫn nhận
            inUS: "N"
        },
        // Mother
        mother: {
            surname: "Tran",
            givenName: "Thi B",
            dobDay: "20",
            dobMonth: "8",           
            dobYear: "1975",
            inUS: "N"
        },
        // Immediate Relatives (hỗ trợ nhiều người)
        hasImmediateRelatives: "Y",
        relatives: [
            {
                surname: "Nguyen",
                givenName: "Thi C",
                relationship: "SPOUSE",   // S=SPOUSE, F=FIANCÉ, C=CHILD, B=SIBLING
                status: "U.S. CITIZEN"    // S=CITIZEN, C=LPR, P=NONIMMIGRANT, O=OTHER
            },
            {
                surname: "Tran",
                givenName: "Van B",
                relationship: "CHILD",
                status: "LPR"
            }
        ],
        hasOtherRelatives: "N"
    };
    // =================================================================

    function normalizeMonth(m) {
        if (!m) return ""; // Xử lý an toàn khi để trống tháng
        const map = {"1":"JAN","2":"FEB","3":"MAR","4":"APR","5":"MAY","6":"JUN",
                     "7":"JUL","8":"AUG","9":"SEP","10":"OCT","11":"NOV","12":"DEC"};
        m = String(m).trim().toUpperCase();
        return map[m] || m;
    }

    function normalizeRelationship(r) {
        const map = {"SPOUSE":"S","FIANCÉ":"F","FIANCÉE":"F","CHILD":"C","SIBLING":"B",
                     "S":"S","F":"F","C":"C","B":"B"};
        return map[String(r).trim().toUpperCase()] || r;
    }

    function normalizeStatus(s) {
        const map = {"U.S. CITIZEN":"S","CITIZEN":"S","LPR":"C","LEGAL PERMANENT RESIDENT":"C",
                     "NONIMMIGRANT":"P","OTHER":"O","S":"S","C":"C","P":"P","O":"O"};
        return map[String(s).trim().toUpperCase()] || s;
    }

    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function waitForElement(selector, timeout = 6000) {
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
        const no = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${name}_1`);
        const target = value === "Y" ? yes : no;
        if (target) {
            target.checked = true;
            target.click();
            target.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function setCheckbox(id, checked) {
        const cb = document.getElementById(id);
        if (cb) cb.checked = checked;
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU ONE-CLICK FULL FAMILY (v7.1)", "color:#0066cc;font-weight:bold");

        // ================== FATHER ==================
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxFATHER_SURNAME").value = config.father.surname;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxFATHER_GIVEN_NAME").value = config.father.givenName;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlFathersDOBDay").value = config.father.dobDay || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlFathersDOBMonth").value = normalizeMonth(config.father.dobMonth);
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxFathersDOBYear").value = config.father.dobYear || "";
        setCheckbox("ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_SURNAME_UNK_IND", !config.father.surname);
        setCheckbox("ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_GIVEN_NAME_UNK_IND", !config.father.givenName);
        
        // Chỉ tick Do Not Know nếu cả Ngày, Tháng, Năm đều trống
        const isFatherDobUnknown = !config.father.dobDay && !config.father.dobMonth && !config.father.dobYear;
        setCheckbox("ctl00_SiteContentPlaceHolder_FormView1_cbxFATHER_DOB_UNK_IND", isFatherDobUnknown);
        
        triggerRadio("FATHER_LIVE_IN_US_IND", config.father.inUS);

        // ================== MOTHER ==================
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMOTHER_SURNAME").value = config.mother.surname;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMOTHER_GIVEN_NAME").value = config.mother.givenName;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlMothersDOBDay").value = config.mother.dobDay || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlMothersDOBMonth").value = normalizeMonth(config.mother.dobMonth);
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMothersDOBYear").value = config.mother.dobYear || "";
        setCheckbox("ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_SURNAME_UNK_IND", !config.mother.surname);
        setCheckbox("ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_GIVEN_NAME_UNK_IND", !config.mother.givenName);
        
        // Chỉ tick Do Not Know nếu cả Ngày, Tháng, Năm đều trống
        const isMotherDobUnknown = !config.mother.dobDay && !config.mother.dobMonth && !config.mother.dobYear;
        setCheckbox("ctl00_SiteContentPlaceHolder_FormView1_cbxMOTHER_DOB_UNK_IND", isMotherDobUnknown);
        
        triggerRadio("MOTHER_LIVE_IN_US_IND", config.mother.inUS);

        // ================== IMMEDIATE RELATIVES ==================
        triggerRadio("US_IMMED_RELATIVE_IND", config.hasImmediateRelatives);

        if (config.hasImmediateRelatives === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dlUSRelatives_ctl00_tbxUS_REL_SURNAME");

            for (let i = 0; i < config.relatives.length; i++) {
                const rel = config.relatives[i];

                if (i > 0) {
                    const addBtn = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dlUSRelatives_ctl0${i-1}_InsertButtonUSRelative`);
                    if (addBtn) {
                        addBtn.click();
                        await sleep(800); 
                    }
                }

                const prefix = i === 0 ? "ctl00" : `ctl0${i}`;
                document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dlUSRelatives_${prefix}_tbxUS_REL_SURNAME`).value = rel.surname;
                document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dlUSRelatives_${prefix}_tbxUS_REL_GIVEN_NAME`).value = rel.givenName;
                triggerDropdown(`ctl00_SiteContentPlaceHolder_FormView1_dlUSRelatives_${prefix}_ddlUS_REL_TYPE`, normalizeRelationship(rel.relationship));
                triggerDropdown(`ctl00_SiteContentPlaceHolder_FormView1_dlUSRelatives_${prefix}_ddlUS_REL_STATUS`, normalizeStatus(rel.status));
            }
        } else {
            triggerRadio("US_OTHER_RELATIVE_IND", config.hasOtherRelatives);
        }

        finish();
    }

    function triggerDropdown(id, value) {
        const select = document.getElementById(id);
        if (select) {
            select.value = value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function finish() {
        console.log("%c🎉 HOÀN TẤT ONE-CLICK FULL FAMILY v7.1!", "color:green;font-weight:bold;font-size:16px");
        alert("✅ ĐÃ ĐIỀN XONG FAMILY (v7.1)!\n• Đã hỗ trợ điền riêng Năm sinh (bỏ trống Ngày/Tháng)\n• Relatives tự động Add Another\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillFamilyv71")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillFamilyv71";
        btn.textContent = "🛠 AUTO FILL FAMILY (1 CLICK v7.1)";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();