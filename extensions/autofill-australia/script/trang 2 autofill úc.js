// ==UserScript==
// @name         IMMI Visitor Short Stay Visa - AutoFill Page 2/20
// @namespace    https://tampermonkey.net/
// @version      1.4
// @description  Chỉ chạy khi click nút Autofill. Đã fix hoàn toàn phần Significant dates.
// @author       Grok
// @match        https://online.immi.gov.au/elp/app*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';
// ==================== CẤU HÌNH (BẠN CHỈ CẦN SỬA ĐOẠN NÀY) ====================
const CONFIG = {
    // Current location (mã quốc gia)
    currentLocationCode: "VIET",

    // Legal status
    legalStatusValue: "1",                    // 1 = Citizen (ở Việt Nam)

    // Purpose of stay stream
    purposeStreamValue: "29",                 // 29 = Tourist stream (đúng với hồ sơ)

    // Chỉ dùng nếu chọn Frequent Traveller (61)
    initialPurposeValue: "2",                 // 2 = Tourism

    // List all reasons for visiting Australia
    visitReasonValue: "4",                    // 4 = Family visit (ưu tiên vì thăm em gái Thi Phuong Thao Nguyen đang ở Úc)

    // Significant dates (copy nguyên văn từ đơn cũ)
    significantDatesText: "THE APPLICANT INTENDS TO VISIT AUSTRALIA FROM 15 MARCH 2026 TO 25 MARCH 2026. HOWEVER, THIS SCHEDULE IS SUBJECT TO CHANGE BASED ON THE DATE OF VISA GRANT.",

    // Group processing
    groupProcessing: "1",                     // 1 = Yes (đang nộp nhóm NGUYEN THI HA PHUONG FAMILY)

    // Special category of entry
    specialCategory: "2"                      // 2 = No
};

    let autofillBtn = null;

    function addAutofillButton() {
        if (document.getElementById('immi-autofill-btn')) return;

        autofillBtn = document.createElement('button');
        autofillBtn.id = 'immi-autofill-btn';
        autofillBtn.textContent = 'Autofill Page 2';
        autofillBtn.style.cssText = `
position: fixed; 
top: 30px;      /* Thay bottom thành top */
left: 30px;     /* Thay right thành left */
z-index: 999999;
padding: 14px 24px; 
background: #0066cc; 
color: white;
border: none; 
border-radius: 8px; 
font-weight: bold;
cursor: pointer; 
        `;
        autofillBtn.onclick = () => {
            if (confirm('Bắt đầu autofill trang 2/20?')) startAutofill();
        };
        document.body.appendChild(autofillBtn);
    }

    async function startAutofill() {
        console.log('🚀 Bắt đầu autofill...');

        // 1. Outside Australia = Yes
        const yesRadio = findRadio("Is the applicant currently outside Australia?", "Yes");
        if (yesRadio) yesRadio.click();

        await delay(1500);

        // 2. Current location & Legal status
        setSelect("Current location", CONFIG.currentLocationCode);
        setSelect("Legal status", CONFIG.legalStatusValue);

        await delay(800);

        // 3. Purpose stream
        const streamRadio = document.querySelector(`input[type="radio"][value="${CONFIG.purposeStreamValue}"]`);
        if (streamRadio) streamRadio.click();

        await delay(900);

        // 4. Frequent Traveller → initial purpose
        if (CONFIG.purposeStreamValue === "61") {
            const initRadio = document.querySelector(`input[type="radio"][value="${CONFIG.initialPurposeValue}"]`);
            if (initRadio) initRadio.click();
        }

        // 5. List all reasons
        const reasonSelect = findMultiSelect("List all reasons for visiting Australia");
        if (reasonSelect) {
            reasonSelect.value = CONFIG.visitReasonValue;
            reasonSelect.dispatchEvent(new Event('change', {bubbles: true}));
            const plusBtn = document.querySelector('.wc_btn_icon.wc-invite');
            if (plusBtn) plusBtn.click();
        }

        // 6. SIGNIFICANT DATES - ĐÃ SỬA (phần này trước bị lỗi)
        const datesLabel = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes('significant dates') || 
                      l.textContent.includes('Give details of any significant dates'));

        if (datesLabel) {
            const textareaId = datesLabel.getAttribute('for');
            const datesTA = textareaId ? document.getElementById(textareaId) : null;

            if (datesTA) {
                datesTA.value = CONFIG.significantDatesText;
                datesTA.dispatchEvent(new Event('input', { bubbles: true }));
                datesTA.dispatchEvent(new Event('change', { bubbles: true }));
                console.log('✅ Significant dates đã điền thành công!');
            }
        } else {
            console.warn('⚠️ Không tìm thấy label Significant dates');
        }

        // 7. Group processing = No
        const groupNo = findRadio("Is this application being lodged as part of a group of applications?", "No");
        if (groupNo) groupNo.click();

        await delay(600);

        // 8. Special category = No
        const specialNo = findRadio("Is the applicant travelling as a representative of a foreign government", "No");
        if (specialNo) specialNo.click();

        console.log('🎉 HOÀN TẤT!');
        alert('✅ Auto fill trang 2/20 đã xong!\nKiểm tra lại phần Significant dates trước khi Next.');
    }

    // ==================== HELPER (đã cải tiến) ====================
    function findRadio(question, option) {
        return Array.from(document.querySelectorAll('label.wc-option'))
            .find(l => l.textContent.trim() === option && 
                  l.closest('fieldset') && 
                  l.closest('fieldset').textContent.includes(question))
            ?.querySelector('input[type="radio"]');
    }

    function setSelect(labelText, value) {
        const label = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes(labelText));
        if (!label) return;
        const select = label.closest('.wc-row')?.querySelector('select') || 
                       label.parentElement.parentElement.querySelector('select');
        if (select) {
            select.value = value;
            select.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }

    function findMultiSelect(labelText) {
        const label = Array.from(document.querySelectorAll('.wc-label'))
            .find(l => l.textContent.includes(labelText));
        return label ? label.closest('.wc-panel').querySelector('select') : null;
    }

    function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

    window.addEventListener('load', addAutofillButton);
})()