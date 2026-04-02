// ==UserScript==
// @name         IMMI Visitor Short Stay Visa - AutoFill Page 3/20 (FULL)
// @namespace    https://tampermonkey.net/
// @version      1.0
// @description  Autofill toàn bộ trang 3/20 + popup National Identity Card. 2 nút riêng biệt.
// @author       Grok (team hỗ trợ)
// @match        https://online.immi.gov.au/elp/app*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // ==================== CONFIG (CHỈ SỬA ĐOẠN NÀY) ====================
const CONFIG = {
    // Passport details (lấy chính xác từ hồ sơ)
    familyName: "NGUYEN",
    givenNames: "THI HA PHUONG",
    sex: "F",                          // Female
    dateOfBirth: "10 Mar 1988",
    passportNumber: "C8161337",
    countryOfPassport: "VNM",
    nationality: "VNM",
    dateOfIssue: "11 Sep 2019",
    dateOfExpiry: "11 Sep 2029",
    placeOfIssue: "VIETNAM IMMIGRATION DEPARTMENT",

    // National Identity Card
    hasNationalID: true,
    nationalFamilyName: "NGUYEN",
    nationalGivenNames: "THI HA PHUONG",
    nationalIDNumber: "031188003197",
    nationalCountry: "VIET",
    nationalDateOfIssue: "29 Jul 2022",
    nationalDateOfExpiry: "10 Mar 2028",

    // Các phần còn lại
    pacificAustraliaCard: "2",
    townCity: "Hai Phong",
    stateProvince: "Hai Phong",
    countryOfBirth: "VIET",
    relationshipStatus: "M",           // M = Married (đã có giấy kết hôn)
    otherNames: "2",
    citizenOfPassportCountry: "1",
    citizenOfOtherCountry: "2",
    previouslyTravelled: "2",
    previouslyAppliedVisa: "2",
    hasGrantNumber: "2",
    otherPassports: "2",
    otherIdentityDocs: "2",
    healthExamination: "2"
};
    // =================================================================

    let mainBtn = null;
    let nationalBtn = null;

    function addButtons() {
        // Nút chính trang 3
        if (!document.getElementById('immi-autofill-page3')) {
            mainBtn = document.createElement('button');
            mainBtn.id = 'immi-autofill-page3';
            mainBtn.textContent = 'Autofill Page 3';
            mainBtn.style.cssText = `
                position:fixed; top:30px; left:200px; z-index:999999;
                padding:14px 24px; background:#0066cc; color:white;
                border:none; border-radius:8px; font-weight:bold; cursor:pointer;
            `;
            mainBtn.onclick = () => { if(confirm('Autofill trang 3/20?')) startMainAutofill(); };
            document.body.appendChild(mainBtn);
        }

        // Nút National ID (chỉ hiện khi popup mở)
        if (!document.getElementById('immi-autofill-national')) {
            nationalBtn = document.createElement('button');
            nationalBtn.id = 'immi-autofill-national';
            nationalBtn.textContent = 'Autofill NationalID';
            nationalBtn.style.cssText = `
                position:fixed; top: 80px; left:200px; z-index:999999;
                padding:12px 20px; background:#ff6600; color:white;
                border:none; border-radius:8px; font-weight:bold; cursor:pointer;
                display:none;
            `;
            nationalBtn.onclick = () => startNationalAutofill();
            document.body.appendChild(nationalBtn);
        }
    }

    // ==================== AUTOFILL TRANG CHÍNH ====================
    async function startMainAutofill() {
        console.log('🚀 Autofill Page 3/20 bắt đầu...');

        // Family name + Given names
        setTextInput("Family name", CONFIG.familyName);
        setTextInput("Given names", CONFIG.givenNames);

        // Sex
        clickRadioByValue("Sex", CONFIG.sex);

        // Dates
        setDateInput("Date of birth", CONFIG.dateOfBirth);
        setDateInput("Date of issue", CONFIG.dateOfIssue);
        setDateInput("Date of expiry", CONFIG.dateOfExpiry);

        // Passport number
        setTextInput("Passport number", CONFIG.passportNumber);

        // Country & Nationality
        setSelectByLabel("Country of passport", CONFIG.countryOfPassport);
        setSelectByLabel("Nationality of passport holder", CONFIG.nationality);

        // Place of issue
        setTextInput("Place of issue / issuing authority", CONFIG.placeOfIssue);

        // National Identity Card
        if (CONFIG.hasNationalID) {
            clickRadioByText("Does this applicant have a national identity card?", "Yes");
            await delay(1200); // đợi popup mở
            nationalBtn.style.display = 'block';
            console.log('✅ Đã chọn Yes National ID - popup đang mở');
        } else {
            clickRadioByText("Does this applicant have a national identity card?", "No");
        }

        // Các Yes/No còn lại (mặc định No)
        clickRadioByText("Is the applicant a Pacific-Australia Card holder?", CONFIG.pacificAustraliaCard === "1" ? "Yes" : "No");
        setTextInput("Town / City", CONFIG.townCity);
        setTextInput("State / Province", CONFIG.stateProvince);
        setSelectByLabel("Country of birth", CONFIG.countryOfBirth);

        setSelectByLabel("Relationship status", CONFIG.relationshipStatus);

        clickRadioByText("Is this applicant currently, or have they ever been known by any other names?", CONFIG.otherNames === "1" ? "Yes" : "No");
        clickRadioByText("Is this applicant a citizen of the selected country of passport", CONFIG.citizenOfPassportCountry === "1" ? "Yes" : "No");
        clickRadioByText("Is this applicant a citizen of any other country?", CONFIG.citizenOfOtherCountry === "1" ? "Yes" : "No");

        clickRadioByText("Has this applicant previously travelled to Australia?", CONFIG.previouslyTravelled === "1" ? "Yes" : "No");
        clickRadioByText("Has this applicant previously applied for a visa to Australia?", CONFIG.previouslyAppliedVisa === "1" ? "Yes" : "No");
        clickRadioByText("Does this applicant have an Australian visa grant number?", CONFIG.hasGrantNumber === "1" ? "Yes" : "No");

        clickRadioByText("Does this applicant have any other passports or documents for travel?", CONFIG.otherPassports === "1" ? "Yes" : "No");
        clickRadioByText("Does this applicant have other identity documents?", CONFIG.otherIdentityDocs === "1" ? "Yes" : "No");
        clickRadioByText("Has this applicant undertaken a health examination for an Australian visa in the last 12 months?", CONFIG.healthExamination === "1" ? "Yes" : "No");

        console.log('🎉 TRANG 3 HOÀN TẤT!');
        alert('✅ Autofill trang 3/20 xong!\nKiểm tra lại rồi nhấn Next.');
    }

    // ==================== AUTOFILL POPUP NATIONAL ID ====================
    async function startNationalAutofill() {
        if (!document.querySelector('button[title="Cancel the current entry"]')) {
            alert('❌ Popup National ID chưa mở!');
            return;
        }

        console.log('🚀 Đang fill National ID popup...');

        setTextInputPopup("Family name", CONFIG.nationalFamilyName);
        setTextInputPopup("Given names", CONFIG.nationalGivenNames);
        setTextInputPopup("Identification number", CONFIG.nationalIDNumber);
        setSelectPopup("Country of issue", CONFIG.nationalCountry);

        setDateInputPopup("Date of issue", CONFIG.nationalDateOfIssue);
        setDateInputPopup("Date of expiry", CONFIG.nationalDateOfExpiry);

        console.log('✅ National ID popup đã điền xong!');
        alert('✅ National ID đã autofill!\nNhấn Confirm trên popup.');
    }

    // ==================== HELPER FUNCTIONS ====================
    function setTextInput(label, value) {
        const lbl = Array.from(document.querySelectorAll('label.wc-label')).find(l => l.textContent.includes(label));
        if (lbl) {
            const input = lbl.closest('.wc-row').querySelector('input[type="text"]');
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('input', {bubbles:true}));
            }
        }
    }

    function setDateInput(label, value) {
        const lbl = Array.from(document.querySelectorAll('label.wc-label')).find(l => l.textContent.includes(label));
        if (lbl) {
            const input = lbl.closest('.wc-row').querySelector('input[type="text"]');
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('change', {bubbles:true}));
            }
        }
    }

    function clickRadioByValue(label, value) {
        const radios = document.querySelectorAll('input[type="radio"]');
        for (let r of radios) {
            if (r.value === value && r.closest('fieldset') && r.closest('fieldset').textContent.includes(label)) {
                r.click();
                return;
            }
        }
    }

    function clickRadioByText(labelText, optionText) {
        const labels = Array.from(document.querySelectorAll('label.wc-option'));
        for (let l of labels) {
            if (l.textContent.trim() === optionText) {
                const fieldset = l.closest('fieldset');
                if (fieldset && fieldset.textContent.includes(labelText)) {
                    l.querySelector('input').click();
                    return;
                }
            }
        }
    }

    function setSelectByLabel(label, value) {
        const lbl = Array.from(document.querySelectorAll('label.wc-label')).find(l => l.textContent.includes(label));
        if (lbl) {
            const select = lbl.closest('.wc-row').querySelector('select');
            if (select) {
                select.value = value;
                select.dispatchEvent(new Event('change', {bubbles:true}));
            }
        }
    }

    // Helper cho popup National ID
    function setTextInputPopup(label, value) {
        const lbl = Array.from(document.querySelectorAll('label.wc-label')).find(l => l.textContent.includes(label));
        if (lbl) {
            const input = lbl.closest('.wc-row').querySelector('input[type="text"]');
            if (input) input.value = value;
        }
    }

    function setDateInputPopup(label, value) {
        const lbl = Array.from(document.querySelectorAll('label.wc-label')).find(l => l.textContent.includes(label));
        if (lbl) {
            const input = lbl.closest('.wc-row').querySelector('input[type="text"]');
            if (input) input.value = value;
        }
    }

    function setSelectPopup(label, value) {
        const lbl = Array.from(document.querySelectorAll('label.wc-label')).find(l => l.textContent.includes(label));
        if (lbl) {
            const select = lbl.closest('.wc-row').querySelector('select');
            if (select) select.value = value;
        }
    }

    function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

    // Theo dõi popup National ID
    const observer = new MutationObserver(() => {
        if (document.querySelector('button[title="Cancel the current entry"]')) {
            nationalBtn.style.display = 'block';
        } else {
            nationalBtn.style.display = 'none';
        }
    });

    // Khởi chạy
    window.addEventListener('load', () => {
        addButtons();
        observer.observe(document.body, { childList: true, subtree: true });
        console.log('%c✅ 2 nút Autofill Page 3 + National ID đã sẵn sàng!', 'color:#0066cc; font-weight:bold');
    });
})();