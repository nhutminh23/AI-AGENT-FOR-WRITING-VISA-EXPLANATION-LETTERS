// ==UserScript==
// @name         01. DS 160 - Personal 1
// @namespace    http://tampermonkey.net/
// @version      2026-03-05-v6.5
// @description  1 click điền Personal 1 - Đã fix Native Alphabet + Other Names + Telecode
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_personal.aspx?node=Personal1
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        surname: "TO",
        givenName: "THI MY LE",

        // Full Name in Native Alphabet
        hasNativeName: true,
        nativeName: "TÔ THỊ MỸ LỆ",          // ← Điền tên tiếng Việt đầy đủ

        // Other Names (maiden, alias...)
        hasOtherNames: false,
        otherSurname: "PHAM",
        otherGivenName: "MINH",

        // Telecode
        hasTelecode: false,
        // telecodeSurname: "1 2 3 4",
        // telecodeGivenName: "1 2 3 4",

        gender: "F",
        maritalStatus: "M",
        dobDay: "01",
        dobMonth: "JAN",
        dobYear: "1977",
        pobCity: "GIA LAI",
        pobState: null,                     // để null nếu không áp dụng
        pobCountry: "Vietnam"
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

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL Personal 1", "color:#0066cc;font-weight:bold");

        // 1. Họ và Tên
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_SURNAME", config.surname);
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_GIVEN_NAME", config.givenName);

        // 2. Full Name in Native Alphabet
        const nativeCheckbox = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_FULL_NAME_NATIVE_NA");
        if (nativeCheckbox) {
            if (config.hasNativeName) {
                if (nativeCheckbox.checked) nativeCheckbox.click();
                const nativeField = await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_FULL_NAME_NATIVE");
                if (nativeField) setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_FULL_NAME_NATIVE", config.nativeName);
            } else {
                if (!nativeCheckbox.checked) nativeCheckbox.click();
            }
        }

        // 3. Have you ever used other names?
        if (config.hasOtherNames) {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblOtherNames_0");
            const otherSurname = await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_DListAlias_ctl00_tbxSURNAME");
            if (otherSurname) {
                setValue("ctl00_SiteContentPlaceHolder_FormView1_DListAlias_ctl00_tbxSURNAME", config.otherSurname);
                setValue("ctl00_SiteContentPlaceHolder_FormView1_DListAlias_ctl00_tbxGIVEN_NAME", config.otherGivenName);
            }
        } else {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblOtherNames_1");
        }

        // 4. Do you have a telecode?
        if (config.hasTelecode) {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblTelecodeQuestion_0");
            const teleSurname = await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_TelecodeSURNAME");
            if (teleSurname) {
                setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_TelecodeSURNAME", config.telecodeSurname);
                setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_TelecodeGIVEN_NAME", config.telecodeGivenName);
            }
        } else {
            triggerRadio("ctl00_SiteContentPlaceHolder_FormView1_rblTelecodeQuestion_1");
        }

        // 5. Gender, Marital Status, DOB
        const genderSelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_GENDER");
        if (genderSelect) { genderSelect.value = config.gender; genderSelect.dispatchEvent(new Event('change', { bubbles: true })); }

        const maritalSelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_MARITAL_STATUS");
        if (maritalSelect) { maritalSelect.value = config.maritalStatus; maritalSelect.dispatchEvent(new Event('change', { bubbles: true })); }

        setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlDOBDay", config.dobDay);
        setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlDOBMonth", config.dobMonth);
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxDOBYear", config.dobYear);

        // 6. Place of Birth
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_POB_CITY", config.pobCity);

        const countrySelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlAPP_POB_CNTRY");
        if (countrySelect) {
            countrySelect.value = config.pobCountry === "Vietnam" ? "VTNM" : config.pobCountry;
            countrySelect.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // State/Province (nếu có)
        if (config.pobState) {
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_POB_ST_PROVINCE", config.pobState);
        } else {
            const na = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_POB_ST_PROVINCE_NA");
            if (na && !na.checked) na.click();
        }

        alert("✅ ĐÃ ĐIỀN XONG PERSONAL 1!\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillPersonal1")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillPersonal1";
        btn.textContent = "🛠 AUTO FILL PERSONAL 1";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();