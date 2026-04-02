// ==UserScript==
// @name         IMMI Visitor Short Stay Visa - AutoFill Page 9/20 + Inline Contact
// @namespace    https://tampermonkey.net/
// @version      1.3
// @description  Fix email Contact in Australia (type=email) + debug log
// @author       Grok (team hỗ trợ)
// @match        https://online.immi.gov.au/elp/app*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

// ==================== CONFIG - CHỈNH SỬA TẠI ĐÂY ====================
const CONFIG = {
    // === Phần chính trang 9 ===
    multipleEntry: "No",                    // Single entry (an toàn nhất cho Tourist stream)
    lengthOfStay: "12",                     // Giữ nguyên theo mẫu bạn cung cấp
    plannedArrival: "01 May 2026",
    plannedDeparture: "30 May 2026",
    isParentOfAustralian: "No",
    undertakeStudy: "No",
    visitRelatives: "Yes",                  // Quan trọng - thăm em gái

    // === Phần inline Contact in Australia (Em gái - người liên lạc phù hợp nhất) ===
    contact: {
        relationship: "34",                 // 34 = Sister (em gái)
        familyName: "NGUYEN",
        givenNames: "THI PHUONG THAO",
        sex: "F",
        dateOfBirth: "28 May 1990",
        address1: "380 KEIRA ST",
        address2: "",
        suburbTown: "WOLLONGONG",
        stateProvince: "NSW",
        postcode: "2500",
        homePhone: "",
        businessPhone: "",
        mobilePhone: "",                    // ← Thêm số điện thoại Úc của em gái nếu có
        email: "",                          // ← Thêm email của em gái nếu có
        residencyStatus: "3"                // Temporary (Bridging B visa)
    }
};
    // ===================================================================

    let mainBtn = null;
    let contactBtn = null;

    function addMainButton() {
        if (document.getElementById('immi-autofill-page9')) return;
        mainBtn = document.createElement('button');
        mainBtn.id = 'immi-autofill-page9';
        mainBtn.textContent = 'Autofill Page 9';
        mainBtn.style.cssText = `
                position:fixed; top:30px; left:880px; z-index:999999;
                padding:14px 24px; background:#0066cc; color:white;
                border:none; border-radius:8px; font-weight:bold; cursor:pointer;
`;
        mainBtn.onclick = () => confirm('Autofill trang 9/20?') && startMainAutofill();
        document.body.appendChild(mainBtn);
    }

    function addContactButton() {
        if (document.getElementById('immi-autofill-contact')) return;
        contactBtn = document.createElement('button');
        contactBtn.id = 'immi-autofill-contact';
        contactBtn.textContent = 'Autofill Contact';
        contactBtn.style.cssText = `                position:fixed; top:80px; left:880px; z-index:999999;
                padding:14px 24px; background:#ff6600; color:white;
                border:none; border-radius:8px; font-weight:bold; cursor:pointer;display:none;`;
        contactBtn.onclick = () => confirm('Autofill form Contact?') && startContactAutofill();
        document.body.appendChild(contactBtn);
    }

    async function startMainAutofill() { /* giữ nguyên như script cũ */ 
        console.log('🚀 Autofill trang 9 bắt đầu...');
        clickRadio("Does the applicant intend to enter Australia on more than one occasion?", CONFIG.multipleEntry);
        await delay(800);
        setSelect("Length of stay in Australia", CONFIG.lengthOfStay);
        setDate("Planned arrival date", CONFIG.plannedArrival);
        setDate("Planned final departure date", CONFIG.plannedDeparture);
        clickRadio("Is the applicant a parent or step-parent of an Australian citizen or Australian permanent resident?", CONFIG.isParentOfAustralian);
        clickRadio("Will the applicant undertake a course of study in Australia?", CONFIG.undertakeStudy);
        clickRadio("Will the applicant visit any relatives, friends or contacts while in Australia?", CONFIG.visitRelatives);
        console.log('✅ TRANG 9 HOÀN TẤT!');
        alert('✅ Autofill trang 9 xong! Bây giờ click "Add" để mở Contact.');
    }

    async function startContactAutofill() {
        await delay(600);   // ← Đợi form inline load xong
        const c = CONFIG.contact;
        console.log('🚀 Bắt đầu autofill Contact in Australia...');

        setSelectContact("Relationship to the applicant", c.relationship);
        setTextContact("Family name", c.familyName);
        setTextContact("Given names", c.givenNames);
        clickRadioContact("Sex", c.sex);
        setDateContact("Date of birth", c.dateOfBirth);
        setTextContact("Address", c.address1);
        setTextContact("Address 2", c.address2);
        setTextContact("Suburb / Town", c.suburbTown);
        setSelectContact("State / Territory", c.stateProvince);
        setTextContact("Postcode", c.postcode);
        setTextContact("Home phone", c.homePhone);
        setTextContact("Business phone", c.businessPhone);
        setTextContact("Mobile / Cell phone", c.mobilePhone);
        setTextContact("Email address", c.email);           // ← Bây giờ sẽ điền được
        setSelectContact("Australian residency status", c.residencyStatus);

        console.log('✅ CONTACT IN AUSTRALIA HOÀN TẤT!');
        alert('✅ Autofill Contact xong! Nhấn "Save" hoặc "Confirm".');
    }

    // ==================== HELPERS CHUNG (giữ nguyên) ====================
    function clickRadio(labelText, optionText) { /* giữ nguyên */ 
        const labels = [...document.querySelectorAll('label.wc-option')];
        const target = labels.find(l => l.textContent.trim() === optionText && l.closest('fieldset')?.textContent.includes(labelText));
        if (target) target.querySelector('input').click();
    }
    function setSelect(labelText, value) { /* giữ nguyên */ 
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const select = label.closest('.wc-row')?.querySelector('select');
            if (select) { select.value = value; select.dispatchEvent(new Event('change', { bubbles: true })); }
        }
    }
    function setDate(labelText, value) { /* giữ nguyên */ 
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

    // ==================== HELPERS CHO CONTACT (ĐÃ SỬA) ====================
    function setTextContact(labelText, value) {
        if (!value) return;
        const label = [...document.querySelectorAll('label.wc-label')].find(l => 
            l.textContent.trim().includes(labelText)
        );
        if (!label) {
            console.log(`❌ Không tìm thấy label: ${labelText}`);
            return;
        }
        const row = label.closest('.wc-row') || label.closest('.wc-panel');
        const input = row?.querySelector('input[type="text"], input[type="email"], input[type="tel"]');
        
        if (input) {
            input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            console.log(`✅ Điền thành công: ${labelText} = ${value}`);
        } else {
            console.log(`❌ Không tìm thấy input cho: ${labelText}`);
        }
    }

    function setDateContact(labelText, value) { /* giữ nguyên */ 
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const input = label.closest('.wc-row')?.querySelector('input[type="text"]');
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }
    function clickRadioContact(labelText, value) { /* giữ nguyên */ 
        const radios = [...document.querySelectorAll('input[type="radio"]')];
        const target = radios.find(r => r.value === value && r.closest('fieldset')?.textContent.includes(labelText));
        if (target) target.click();
    }
    function setSelectContact(labelText, value) { /* giữ nguyên */ 
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const select = label.closest('.wc-row')?.querySelector('select');
            if (select) { select.value = value; select.dispatchEvent(new Event('change', { bubbles: true })); }
        }
    }

    // ==================== OBSERVER & INIT ====================
    const observer = new MutationObserver(() => {
        const heading = [...document.querySelectorAll('h2, h3')].find(el => el.textContent.includes('Contact in Australia'));
        if (contactBtn) contactBtn.style.display = heading ? 'block' : 'none';
    });

    function init() {
        addMainButton();
        addContactButton();
    }

    init();
    setInterval(init, 2000);
    observer.observe(document.body, { childList: true, subtree: true });

    console.log('✅ Script v1.3 đã chạy - Email Contact đã được fix!');
})();