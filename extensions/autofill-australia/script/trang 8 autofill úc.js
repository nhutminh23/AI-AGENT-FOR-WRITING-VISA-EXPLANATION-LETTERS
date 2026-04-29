// ==UserScript==
// @name         IMMI Visitor Short Stay Visa - AutoFill Page 8/20 (Non-accompanying member)
// @namespace    https://tampermonkey.net/
// @version      1.0
// @description  Autofill Non-accompanying member of the family unit (Trang 8) - button riêng
// @author       Grok (team hỗ trợ)
// @match        https://online.immi.gov.au/elp/app*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // ==================== CONFIG - CHỈNH SỬA TẠI ĐÂY ====================
    const CONFIG = {
        relationship: "33",           // Mã relationship (xem danh sách bên dưới)
        // 39=Aunt, 35=Brother, 33=Friend, 3=Spouse/De Facto, 2=Parent...
        familyName: "Nguyen",
        givenNames: "Thi B",
        sex: "F",                     // F = Female, M = Male, U = Other
        dateOfBirth: "20 Apr 1995",   // Định dạng: DD MMM YYYY
        countryOfBirth: "VIET"        // Mã quốc gia (VIET = Vietnam, xem danh sách dài trong HTML)
    };
    // ===================================================================

    let autofillBtn = null;

    function addAutofillButton() {
        if (document.getElementById('immi-autofill-page8')) return;

        autofillBtn = document.createElement('button');
        autofillBtn.id = 'immi-autofill-page8';
        autofillBtn.textContent = 'Autofill Page 8';
        autofillBtn.style.cssText = `
                position:fixed; top:30px; left:710px; z-index:999999;
                padding:14px 24px; background:#0066cc; color:white;
                border:none; border-radius:8px; font-weight:bold; cursor:pointer;
        `;
        autofillBtn.onclick = () => {
            if (confirm('Autofill Non-accompanying member (Trang 8)?')) startAutofill();
        };
        document.body.appendChild(autofillBtn);
    }

    async function startAutofill() {
        console.log('🚀 Bắt đầu autofill Trang 8 - Non-accompanying member...');

        // Relationship
        setSelect("Relationship to the applicant", CONFIG.relationship);
        await delay(600);

        // Names
        setText("Family name", CONFIG.familyName);
        setText("Given names", CONFIG.givenNames);

        // Sex
        clickRadioSex(CONFIG.sex);

        // Date of birth
        setDate("Date of birth", CONFIG.dateOfBirth);

        // Country of birth
        setSelect("Country of birth", CONFIG.countryOfBirth);

        console.log('✅ PAGE 8 HOÀN TẤT!');
        alert('✅ Autofill Non-accompanying member xong!\nNhấn "Save" hoặc "Confirm".');
    }

    // ==================== HELPERS (giống Trang 5) ====================
    function setSelect(labelText, value) {
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const select = label.closest('.wc-row')?.querySelector('select');
            if (select) {
                select.value = value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                console.log(`✅ ${labelText}: ${value}`);
            }
        }
    }

    function setText(labelText, value) {
        if (!value) return;
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const input = label.closest('.wc-row')?.querySelector('input[type="text"]');
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    function clickRadioSex(value) {
        const radios = [...document.querySelectorAll('input[type="radio"]')];
        const target = radios.find(r => r.value === value && r.closest('fieldset')?.textContent.includes('Sex'));
        if (target) target.click();
    }

    function setDate(labelText, value) {
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const input = label.closest('.wc-row')?.querySelector('input[type="text"]');
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

    // ==================== KHỞI CHẠY ====================
    function init() {
        addAutofillButton();
    }

    init();
    setInterval(init, 2000);  // Đảm bảo button luôn hiện

    console.log('✅ Script Trang 8 v1.0 đã tải thành công!');
})();