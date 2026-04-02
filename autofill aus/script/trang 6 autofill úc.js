// ==UserScript==
// @name         IMMI Visitor Short Stay Visa - AutoFill Page 6/20
// @namespace    https://tampermonkey.net/
// @version      1.0
// @description  Autofill toàn bộ trang 6/20 (Country of residence + Department office + Residential address + Phones + Postal address + Email). Chỉ chạy khi click button.
// @author       Grok (team hỗ trợ)
// @match        https://online.immi.gov.au/elp/app*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // ==================== CONFIG - CHỈNH SỬA TẠI ĐÂY ====================
const CONFIG = {
    usualCountry: "VIET",

    closestOffice: "Vietnam, Hanoi",   // Phù hợp nhất vì khách ở Hải Phòng (miền Bắc)

    residential: {
        country: "VIET",
        address1: "TDP Thuy Son 1",
        address2: "",
        suburbTown: "Thuy Nguyen",
        stateProvince: "VNSG",
        postalCode: "180000"
    },

    phones: {
        home: "",
        business: "",
        mobile: "0912345678"           // ← Thay bằng số điện thoại thật của khách
    },

    postalSameAsResidential: true,
    email: "your.email@gmail.com"      // ← Thay bằng email thật của khách
};
    // ===================================================================

    function addAutofillButton() {
        if (document.getElementById('immi-autofill-page6')) return;

        const btn = document.createElement('button');
        btn.id = 'immi-autofill-page6';
        btn.textContent = 'Autofill Page 6';
        btn.style.cssText = `
                position:fixed; top:30px; left:540px; z-index:999999;
                padding:14px 24px; background:#0066cc; color:white;
                border:none; border-radius:8px; font-weight:bold; cursor:pointer;
        `;
        btn.onclick = () => {
            if (confirm('Autofill trang 6/20?')) startAutofill();
        };
        document.body.appendChild(btn);
    }

    async function startAutofill() {
        console.log('🚀 Bắt đầu Autofill trang 6/20...');

        // 1. Country of residence
        setSelect("Usual country of residence", CONFIG.usualCountry);

        // 2. Department office (combobox)
        setComboBox("Office", CONFIG.closestOffice);

        // 3. Residential address
        setSelect("Country", CONFIG.residential.country, true); // residential section
        await delay(800); // chờ form update state dropdown
        setText("Address", CONFIG.residential.address1);
        setText("Address 2", CONFIG.residential.address2);
        setText("Suburb / Town", CONFIG.residential.suburb);
        setSelectVietnamProvince(CONFIG.residential.stateProvince);
        setText("Postal code", CONFIG.residential.postalCode);

        // 4. Contact telephone numbers
        setText("Home phone", CONFIG.phones.home);
        setText("Business phone", CONFIG.phones.business);
        setText("Mobile / Cell phone", CONFIG.phones.mobile);

        // 5. Postal address
        clickRadioPostalSame(CONFIG.postalSameAsResidential ? "Yes" : "No");
        if (!CONFIG.postalSameAsResidential) {
            await delay(1000);
            // Nếu cần điền postal riêng, copy lại residential (bạn có thể chỉnh CONFIG)
            setSelect("Country", CONFIG.residential.country, false); // postal section
            setText("Address", CONFIG.residential.address1, false);
            setText("Address 2", CONFIG.residential.address2, false);
            setText("Suburb / Town", CONFIG.residential.suburb, false);
            setSelectVietnamProvince(CONFIG.residential.stateProvince, false);
            setText("Postal code", CONFIG.residential.postalCode, false);
        }

        // 6. Email address
        setText("Email address", CONFIG.email);

        console.log('🎉 TRANG 6 HOÀN TẤT!');
        alert('✅ Autofill trang 6/20 xong!\nKiểm tra lại Closest Office và State/Province.');
    }

    // ==================== HELPER FUNCTIONS ====================
    function setSelect(labelText, value, isResidential = true) {
        const labels = document.querySelectorAll('label.wc-label');
        for (let label of labels) {
            if (label.textContent.includes(labelText)) {
                const row = label.closest('.wc-row');
                const select = row ? row.querySelector('select') : null;
                if (select) {
                    select.value = value;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    return;
                }
            }
        }
    }

    function setComboBox(labelText, value) {
        const labels = document.querySelectorAll('label.wc-label');
        for (let label of labels) {
            if (label.textContent.includes(labelText)) {
                const input = label.closest('.wc-row').querySelector('input[type="text"]');
                if (input) {
                    input.value = value;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    // Tự động chọn gợi ý nếu có
                    setTimeout(() => {
                        const suggestion = document.querySelector(`span[data-wc-value="${value}"]`);
                        if (suggestion) suggestion.click();
                    }, 300);
                    return;
                }
            }
        }
    }

    function setText(labelText, value, isResidential = true) {
        const labels = document.querySelectorAll('label.wc-label');
        for (let label of labels) {
            if (label.textContent.includes(labelText)) {
                const input = label.closest('.wc-row').querySelector('input[type="text"]');
                if (input) {
                    input.value = value;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    return;
                }
            }
        }
    }

    function setSelectVietnamProvince(value, isResidential = true) {
        // Tìm select có các option VNxx
        const selects = document.querySelectorAll('select');
        for (let sel of selects) {
            if (Array.from(sel.options).some(opt => opt.value.startsWith('VN'))) {
                sel.value = value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
    }

    function clickRadioPostalSame(optionText) {
        const labels = document.querySelectorAll('label.wc-option');
        for (let label of labels) {
            if (label.textContent.trim() === optionText && 
                label.closest('fieldset') && 
                label.closest('fieldset').textContent.includes('postal address the same')) {
                label.querySelector('input[type="radio"]').click();
                return;
            }
        }
    }

    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ==================== RUN ====================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addAutofillButton);
    } else {
        addAutofillButton();
    }

    // MutationObserver để button luôn hiện
    const observer = new MutationObserver(addAutofillButton);
    observer.observe(document.body, { childList: true, subtree: true });
})();