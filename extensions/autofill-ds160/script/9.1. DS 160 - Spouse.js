// ==UserScript==
// @name         09.1. DS 160 - Spouse
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v1.0
// @description  1 click điền Spouse + tự tick Do Not Know cho POB City khi để trống + hỗ trợ tên quốc gia đầy đủ
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_family2.aspx?node=Spouse
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        // Spouse's Full Name
        surname: "Nguyen",           // Họ vợ/chồng
        givenName: "Thi Lan",        // Tên vợ/chồng

        // DOB (để trống bất kỳ trường nào = không điền)
        dobDay: "15",
        dobMonth: "JAN",             // JAN, FEB, MAR...
        dobYear: "1985",

        // Nationality (có thể viết "Vietnam" hoặc "VTNM")
        nationality: "Vietnam",

        // Place of Birth
        pobCity: "",                 // Để trống = tự tick "Do Not Know"
        pobCountry: "Vietnam",

        // Spouse's Address Type
        // H = Same as Home Address
        // M = Same as Mailing Address
        // U = Same as U.S. Contact Address
        // D = Do Not Know
        // O = Other (Specify Address)
        addressType: "D"             // Thường dùng "D" hoặc "H"
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

    function selectCountry(dropdownId, countryName) {
        const select = document.getElementById(dropdownId);
        if (!select) return;
        const name = (countryName || "").toUpperCase().trim();
        for (let opt of select.options) {
            if (opt.value === name || opt.text.toUpperCase().includes(name) || opt.text.toUpperCase().includes("VIETNAM")) {
                select.value = opt.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL SPOUSE (v1.0)", "color:#0066cc;font-weight:bold");

        // Spouse Surnames & Given Names
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxSpouseSurname").value = config.surname;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxSpouseGivenName").value = config.givenName;

        // DOB
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlDOBDay").value = config.dobDay;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlDOBMonth").value = config.dobMonth;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxDOBYear").value = config.dobYear;

        // Nationality
        selectCountry("ctl00_SiteContentPlaceHolder_FormView1_ddlSpouseNatDropDownList", config.nationality);

        // Place of Birth - City + Do Not Know
        const cityInput = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxSpousePOBCity");
        const cityNA = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexSPOUSE_POB_CITY_NA");
        if (cityInput) cityInput.value = config.pobCity || "";
        if (cityNA) {
            const isNA = !config.pobCity || config.pobCity.trim() === "";
            cityNA.checked = isNA;
            if (isNA && cityInput) cityInput.value = "";
            cityNA.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // Place of Birth - Country
        selectCountry("ctl00_SiteContentPlaceHolder_FormView1_ddlSpousePOBCountry", config.pobCountry);

        // Spouse's Address Type
        const addrType = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlSpouseAddressType");
        if (addrType) {
            addrType.value = config.addressType;
            addrType.dispatchEvent(new Event('change', { bubbles: true }));
        }

        console.log("%c🎉 HOÀN TẤT SPOUSE v1.0!", "color:green;font-weight:bold");
        alert("✅ ĐÃ ĐIỀN XONG SPOUSE (v1.0)!\n• Tự tick Do Not Know cho POB City khi để trống\n• Hỗ trợ tên quốc gia đầy đủ\nKiểm tra lại rồi Next nhé Paul!");
    }

    // ================== NÚT AUTO FILL ==================
    function addButton() {
        if (document.getElementById("autoFillSpouseBtn")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillSpouseBtn";
        btn.innerHTML = "🛠 AUTO FILL SPOUSE";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();