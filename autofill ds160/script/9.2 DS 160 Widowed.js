// ==UserScript==
// @name         09.2. DS 160 - Former Spouse
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v1.1
// @description  1 click điền Former Spouse + Fix lỗi chọn tháng Date of Marriage
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_family4.aspx?node=PrevSpouse
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        spouses: [
            {
                surname: "Nguyen",
                givenName: "Thi D",
                dobDay: "10",
                dobMonth: "5",               // "5" hoặc "MAY" đều được
                dobYear: "1980",
                nationality: "Vietnam",

                // Nơi sinh
                pobCity: "",                 // Để trống = tự tick Do Not Know
                pobCountry: "Vietnam",

                // Kết hôn
                domDay: "15",
                domMonth: "AUG",             // "8" hoặc "AUG" đều được
                domYear: "2005",

                // Ly hôn / Kết thúc
                domEndDay: "20",
                domEndMonth: "10",           // "10" hoặc "OCT" đều được
                domEndYear: "2010",
                howEnded: "Divorce",
                countryTerminated: "Vietnam"
            }
        ]
    };
    // =================================================================

    // Dùng cho trường Date of Birth (value="JAN")
    function normalizeMonth(m) {
        if (!m) return "";
        const map = {"1":"JAN","2":"FEB","3":"MAR","4":"APR","5":"MAY","6":"JUN",
                     "7":"JUL","8":"AUG","9":"SEP","10":"OCT","11":"NOV","12":"DEC"};
        m = String(m).trim().toUpperCase();
        return map[m] || m;
    }

    // Dùng cho trường Date of Marriage (value="1")
    function normalizeMonthNumber(m) {
        if (!m) return "";
        const map = {
            "JAN":"1", "01":"1", "1":"1",
            "FEB":"2", "02":"2", "2":"2",
            "MAR":"3", "03":"3", "3":"3",
            "APR":"4", "04":"4", "4":"4",
            "MAY":"5", "05":"5", "5":"5",
            "JUN":"6", "06":"6", "6":"6",
            "JUL":"7", "07":"7", "7":"7",
            "AUG":"8", "08":"8", "8":"8",
            "SEP":"9", "09":"9", "9":"9",
            "OCT":"10", "10":"10",
            "NOV":"11", "11":"11",
            "DEC":"12", "12":"12"
        };
        m = String(m).trim().toUpperCase();
        return map[m] || m;
    }

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
            el.value = value || "";
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
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
        console.log("%c🚀 BẮT ĐẦU AUTO FILL FORMER SPOUSE (v1.1)", "color:#0066cc;font-weight:bold");

        // 1. Điền số lượng Former Spouses để trigger postback
        const numInput = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxNumberOfPrevSpouses");
        if (numInput && numInput.value !== String(config.spouses.length)) {
            numInput.value = config.spouses.length;
            numInput.dispatchEvent(new Event('change', { bubbles: true }));
            await sleep(1500); // Chờ hệ thống CEAC load AJAX
        }

        // Đợi form của người đầu tiên xuất hiện
        await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_ctl00_tbxSURNAME");

        // 2. Lặp qua mảng spouses để điền
        for (let i = 0; i < config.spouses.length; i++) {
            const sp = config.spouses[i];

            // Kích hoạt Add Another nếu đang điền người thứ 2 trở lên
            if (i > 0) {
                const addBtnId = `ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_ctl0${i-1}_InsertButtonSpouse`;
                const addBtn = document.getElementById(addBtnId);
                if (addBtn) {
                    addBtn.click();
                    await sleep(1500); // Chờ block mới render
                }
            }

            const prefix = i === 0 ? "ctl00" : `ctl0${i}`;

            // Name
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_tbxSURNAME`, sp.surname);
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_tbxGIVEN_NAME`, sp.givenName);

            // DOB (Sử dụng normalizeMonth)
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlDOBDay`, sp.dobDay);
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlDOBMonth`, normalizeMonth(sp.dobMonth));
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_tbxDOBYear`, sp.dobYear);

            // Nationality
            selectCountry(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlSpouseNatDropDownList`, sp.nationality);

            // POB City + Do Not Know
            const cityInput = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_tbxSpousePOBCity`);
            const cityNA = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_cbxSPOUSE_POB_CITY_NA`);
            if (cityInput) cityInput.value = sp.pobCity || "";
            if (cityNA) {
                const isNA = !sp.pobCity || sp.pobCity.trim() === "";
                cityNA.checked = isNA;
                cityNA.dispatchEvent(new Event('change', { bubbles: true }));
            }

            // POB Country
            selectCountry(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlSpousePOBCountry`, sp.pobCountry);

            // Date of Marriage (Sử dụng normalizeMonthNumber)
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlDomDay`, sp.domDay);
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlDomMonth`, normalizeMonthNumber(sp.domMonth));
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_txtDomYear`, sp.domYear);

            // Date Marriage Ended (Sử dụng normalizeMonthNumber)
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlDomEndDay`, sp.domEndDay);
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlDomEndMonth`, normalizeMonthNumber(sp.domEndMonth));
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_txtDomEndYear`, sp.domEndYear);

            // How Ended & Terminated Country
            setValue(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_tbxHowMarriageEnded`, sp.howEnded);
            selectCountry(`ctl00_SiteContentPlaceHolder_FormView1_DListSpouse_${prefix}_ddlMarriageEnded_CNTRY`, sp.countryTerminated);
        }

        console.log("%c🎉 HOÀN TẤT FORMER SPOUSE v1.1!", "color:green;font-weight:bold");
        alert("✅ ĐÃ ĐIỀN XONG FORMER SPOUSE (v1.1)!\n• Đã đồng bộ tổng số Former Spouses\n• Đã FIX lỗi không chọn được tháng kết hôn\nKiểm tra lại rồi Next nhé Paul!");
    }

    // ================== NÚT AUTO FILL ==================
    function addButton() {
        if (document.getElementById("autoFillFormerSpouseBtn")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillFormerSpouseBtn";
        btn.innerHTML = "🛠 AUTO FILL FORMER SPOUSE";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();