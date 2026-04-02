// ==UserScript==
// @name         IMMI Visitor Short Stay Visa - AutoFill Page 11/20 (Current Employment)
// @namespace    https://tampermonkey.net/
// @version      1.0
// @description  Autofill Current overseas employment (Trang 11) - chỉ chạy khi click button
// @author       Grok (team hỗ trợ)
// @match        https://online.immi.gov.au/elp/app*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // ==================== CONFIG - CHỈNH SỬA TẠI ĐÂY ====================
    const CONFIG = {
        employmentStatus: "1",              // 1 = Employed (mặc định)

        occupationGrouping: "2",            // 1=Managers, 2=Professionals, 3=Technicians..., 070299=Other
        occupationOther: "",                // Chỉ điền nếu occupationGrouping = "070299"

        organisation: "Công ty ABC Việt Nam",
        startDate: "15 Mar 2022",           // DD MMM YYYY

        // Organisation address (overseas)
        country: "VIET",                    // VIET = Vietnam
        address1: "123 Đường Nguyễn Huệ",
        address2: "Quận 1",
        suburbTown: "Phường Bến Nghé",
        stateProvince: "TP. Hồ Chí Minh",   // text (không phải select)
        postcode: "700000",

        // Contact person details
        contactFamilyName: "Nguyen",
        contactGivenNames: "Van A",
        position: "Quản lý Nhân sự",
        businessPhone: "0281234567",
        mobilePhone: "0912345678",

        // Email
        email: "hr@abccompany.com"
    };
    // ===================================================================

    let autofillBtn = null;

    function addAutofillButton() {
        if (document.getElementById('immi-autofill-page11')) return;

        autofillBtn = document.createElement('button');
        autofillBtn.id = 'immi-autofill-page11';
        autofillBtn.textContent = 'Autofill Page 11';
        autofillBtn.style.cssText = `
            position: fixed; bottom: 80px; right: 30px; z-index: 9999999;
            padding: 14px 28px; background: #0066cc; color: white;
            border: none; border-radius: 8px; font-weight: bold; cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;
        autofillBtn.onclick = () => {
            if (confirm('Autofill Current Employment (Trang 11)?')) startAutofill();
        };
        document.body.appendChild(autofillBtn);
    }

    async function startAutofill() {
        console.log('🚀 Bắt đầu autofill Trang 11 - Current Employment...');

        // 1. Chọn Employment status = Employed
        setSelect("Employment status", CONFIG.employmentStatus);
        await delay(1200);   // Đợi panel động hiện ra

        // 2. Occupation grouping
        setSelect("Occupation grouping", CONFIG.occupationGrouping);
        await delay(600);
        if (CONFIG.occupationGrouping === "070299" && CONFIG.occupationOther) {
            setText("Occupation", CONFIG.occupationOther);
        }

        // 3. Organisation & Start date
        setText("Organisation", CONFIG.organisation);
        setDate("Start date with current employer", CONFIG.startDate);

        // 4. Organisation address
        setSelect("Country", CONFIG.country);
        await delay(800);
        setText("Address", CONFIG.address1);
        setText("Address 2", CONFIG.address2);
        setText("Suburb / Town", CONFIG.suburbTown);
        setText("State or Province", CONFIG.stateProvince);   // text input cho overseas
        setText("Postal code", CONFIG.postcode);

        // 5. Contact person details
        setText("Family name", CONFIG.contactFamilyName);
        setText("Given names", CONFIG.contactGivenNames);
        setText("Position", CONFIG.position);
        setText("Business phone", CONFIG.businessPhone);
        setText("Mobile / Cell phone", CONFIG.mobilePhone);

        // 6. Email
        setEmail("Email address", CONFIG.email);

        console.log('✅ PAGE 11 HOÀN TẤT!');
        alert('✅ Autofill Current Employment xong!\nNhấn "Save" hoặc "Confirm".');
    }

    // ==================== HELPERS ====================
    function setSelect(labelText, value) {
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const select = label.closest('.wc-row')?.querySelector('select');
            if (select) {
                select.value = value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    function setText(labelText, value) {
        if (!value) return;
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const input = label.closest('.wc-row')?.querySelector('input[type="text"], textarea');
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    function setEmail(labelText, value) {
        if (!value) return;
        const label = [...document.querySelectorAll('label.wc-label')].find(l => l.textContent.includes(labelText));
        if (label) {
            const input = label.closest('.wc-row')?.querySelector('input[type="email"]');
            if (input) {
                input.value = value;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
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
    setInterval(init, 2000);   // Đảm bảo button luôn hiện

    console.log('✅ Script Trang 11 v1.0 đã tải thành công!');
})();