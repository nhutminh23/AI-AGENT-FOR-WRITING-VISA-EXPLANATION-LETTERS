// ==UserScript==
// @name         08. DS 160 - U.S. Point of Contact
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.0
// @description  Tối ưu: Tự tick Do Not Know & Does Not Apply khi để trống (không cần config thừa)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_uscontact.aspx?node=USContact
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        // Contact Person
        surnames: "Nguyen",
        givenNames: "Anh",

        // Organization
        orgName: "",

        // Relationship (R=RELATIVE, S=SPOUSE, C=FRIEND, B=BUSINESS ASSOCIATE, P=EMPLOYER, H=SCHOOL OFFICIAL, O=OTHER)
        relationship: "C",

        // Address & Phone của Point of Contact
        address: {
            street1: "123 Main Street",
            street2: "Apt 456",
            city: "Los Angeles",
            state: "California",               // ← BẠN CÓ THỂ VIẾT TÊN ĐẦY ĐỦ HOẶC MÃ "CA"
            zip: "90001",
            phone: "5551234567",
            email: "contact@example.com",

        }
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

    function selectState(dropdownId, stateInput) {
        const select = document.getElementById(dropdownId);
        if (!select) return;
        const input = (stateInput || "").toUpperCase().trim();
        for (let opt of select.options) {
            if (opt.value === input || opt.text.toUpperCase() === input || opt.text.toUpperCase().includes(input)) {
                select.value = opt.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
    }

    function triggerDropdown(id, value) {
        const select = document.getElementById(id);
        if (select) {
            select.value = value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL U.S. POINT OF CONTACT (v7.0)", "color:#0066cc;font-weight:bold");

        // ================== CONTACT PERSON ==================
        const surnameInput = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_SURNAME");
        const givenInput   = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_GIVEN_NAME");
        const nameNA       = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbxUS_POC_NAME_NA");

        if (surnameInput) surnameInput.value = config.surnames || "";
        if (givenInput)   givenInput.value   = config.givenNames || "";

        // TỰ TICK DO NOT KNOW nếu cả 2 trống
        if (nameNA) {
            const isNA = (!config.surnames || config.surnames.trim() === "") &&
                  (!config.givenNames || config.givenNames.trim() === "");
            nameNA.checked = isNA;
            nameNA.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // ================== ORGANIZATION ==================
        const orgInput = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ORGANIZATION");
        const orgNA    = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbxUS_POC_ORG_NA_IND");

        if (orgInput) orgInput.value = config.orgName || "";
        if (orgNA) {
            const isOrgNA = !config.orgName || config.orgName.trim() === "";
            orgNA.checked = isOrgNA;
            orgNA.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // ================== RELATIONSHIP (mở form Address) ==================
        triggerDropdown("ctl00_SiteContentPlaceHolder_FormView1_ddlUS_POC_REL_TO_APP", config.relationship);

        // Chờ form Address hiện ra
        await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_LN1");

        // ================== ADDRESS & CONTACT ==================
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_LN1").value = config.address.street1;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_LN2").value = config.address.street2 || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_CITY").value = config.address.city;
        selectState("ctl00_SiteContentPlaceHolder_FormView1_ddlUS_POC_ADDR_STATE", config.address.state);
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_ADDR_POSTAL_CD").value = config.address.zip;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_HOME_TEL").value = config.address.phone;

        // Email - TỰ TICK DOES NOT APPLY nếu trống
        const emailInput = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxUS_POC_EMAIL_ADDR");
        const emailNA    = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexUS_POC_EMAIL_ADDR_NA");
        if (emailInput) emailInput.value = config.address.email || "";
        if (emailNA) {
            const isEmailNA = !config.address.email || config.address.email.trim() === "";
            emailNA.checked = isEmailNA;
            emailNA.dispatchEvent(new Event('change', { bubbles: true }));
        }

        console.log("%c🎉 HOÀN TẤT U.S. POINT OF CONTACT v7.0!", "color:green;font-weight:bold");
        alert("✅ ĐÃ ĐIỀN XONG U.S. Point of Contact");
    }

    // ================== NÚT AUTO FILL ==================
    function addButton() {
        if (document.getElementById("autoFillUSContactBtn")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillUSContactBtn";
        btn.innerHTML = "🛠 AUTO FILL U.S. POINT OF CONTACT";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();