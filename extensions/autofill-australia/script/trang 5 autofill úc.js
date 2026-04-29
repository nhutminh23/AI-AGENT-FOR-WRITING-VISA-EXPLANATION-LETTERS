// ==UserScript==
// @name         IMMI Visitor Short Stay Visa - AutoFill Page 5/20 (Travelling Companion)
// @namespace    https://tampermonkey.net/
// @version      1.0
// @description  Autofill Travelling companion (Trang 5) - button riêng, chỉ chạy khi click
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
        // 39=Aunt, 35=Brother, 11=Business Associate, 33=Friend, 3=Spouse/De Facto...
        familyName: "Nguyen",
        givenNames: "Thi B",
        sex: "F",                     // F = Female, M = Male, U = Other
        dateOfBirth: "20 Apr 1995"    // Định dạng: DD MMM YYYY
    };
    // ===================================================================

    let autofillBtn = null;

    function addAutofillButton() {
        if (document.getElementById('immi-autofill-page5')) return;

        autofillBtn = document.createElement('button');
        autofillBtn.id = 'immi-autofill-page5';
        autofillBtn.textContent = 'Autofill Page 5';
        autofillBtn.style.cssText = `
                position:fixed; top:30px; left:370px; z-index:999999;
                padding:14px 24px; background:#0066cc; color:white;
                border:none; border-radius:8px; font-weight:bold; cursor:pointer;
        `;
        autofillBtn.onclick = () => {
            if (confirm('Autofill Travelling companion (Trang 5)?')) startAutofill();
        };
        document.body.appendChild(autofillBtn);
    }

    async function startAutofill() {
        console.log('🚀 Bắt đầu autofill Trang 5 - Travelling companion...');

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

        console.log('✅ PAGE 5 HOÀN TẤT!');
        alert('✅ Autofill Travelling companion xong!\nNhấn "Save" hoặc "Confirm".');
    }

    // ==================== HELPERS ====================
    function setSelect(labelText, value) {
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const select = label.closest('.wc-row')?.querySelector('select');
            if (select) {
                select.value = value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                console.log(`✅ Relationship: ${value}`);
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
    setInterval(init, 2000);  // Đảm bảo button luôn xuất hiện

    console.log('✅ Script Trang 5 v1.0 đã tải thành công!');
})();