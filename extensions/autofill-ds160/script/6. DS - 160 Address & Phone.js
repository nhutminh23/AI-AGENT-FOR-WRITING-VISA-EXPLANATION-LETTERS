// ==UserScript==
// @name         06. DS 160 - Address & Phone
// @namespace    http://tampermonkey.net/
// @version      2026-03-05-v7.1
// @description  1 click điền hết + tự tick Does Not Apply + fix Social Media + nhiều Add Another
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_contact.aspx?node=AddressPhone
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        // Home Address
        home: {
            street1: "123 Nguyen Hue",
            street2: "Apt 456",
            city: "Ho Chi Minh City",
            state: "",           // để trống = tự tick Does Not Apply
            zip: "",             // để trống = tự tick Does Not Apply
            country: "Vietnam"
        },

        // Mailing Address
        mailingSameAsHome: "N",
        mailing: {
            street1: "456 Le Loi",
            street2: "",
            city: "Ho Chi Minh City",
            state: "",
            zip: "",
            country: "Vietnam"
        },

        // Phone
        primaryPhone: "0901234567",
        secondaryPhone: "",      // để trống = tự tick Does Not Apply
        workPhone: "",           // để trống = tự tick Does Not Apply

        // Additional Phone (có thể nhiều dòng)
        additionalPhones: ["0987654321", "0912345678"],

        // Email
        email: "your.email@gmail.com",

        // Additional Email (có thể nhiều dòng)
        additionalEmails: ["old.email@gmail.com", "backup@gmail.com"],

        // Social Media (có thể nhiều dòng)
        socials: [
            { platform: "FCBK", handle: "@yourfacebook" },
            { platform: "INST", handle: "@yourinstagram" }
        ],

        // Additional Social (có thể nhiều dòng)
        otherSocial: "Y",
        additionalSocials: [
            { platform: "TIKTOK", handle: "@yourtiktok" }
        ]
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

    function triggerRadio(name, value) {
        const yes = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${name}_0`);
        const no  = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${name}_1`);
        const target = value === "Y" ? yes : no;
        if (target) {
            target.checked = true;
            target.click();
            target.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function selectCountry(ddlId, countryName) {
        const ddl = document.getElementById(ddlId);
        if (!ddl) return;
        const search = (countryName || "").toUpperCase().trim();
        for (let opt of ddl.options) {
            if (opt.value.toUpperCase() === search || opt.text.toUpperCase().includes(search)) {
                ddl.value = opt.value;
                ddl.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
        }
    }

    async function addAnother(btnId) {
        const btn = document.getElementById(btnId);
        if (btn) {
            btn.click();
            await sleep(700);
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU ONE-CLICK FULL v7.1", "color:#0066cc;font-weight:bold");

        // Home Address
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_LN1").value = config.home.street1;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_LN2").value = config.home.street2 || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_CITY").value = config.home.city;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_STATE").value = config.home.state || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_ADDR_STATE_NA").checked = !config.home.state;
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_ADDR_POSTAL_CD").value = config.home.zip || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_ADDR_POSTAL_CD_NA").checked = !config.home.zip;
        selectCountry("ctl00_SiteContentPlaceHolder_FormView1_ddlCountry", config.home.country);

        // Mailing Address
        triggerRadio("MailingAddrSame", config.mailingSameAsHome);
        if (config.mailingSameAsHome === "N") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxMAILING_ADDR_LN1");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMAILING_ADDR_LN1").value = config.mailing.street1;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMAILING_ADDR_LN2").value = config.mailing.street2 || "";
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMAILING_ADDR_CITY").value = config.mailing.city;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMAILING_ADDR_STATE").value = config.mailing.state || "";
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexMAILING_ADDR_STATE_NA").checked = !config.mailing.state;
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxMAILING_ADDR_POSTAL_CD").value = config.mailing.zip || "";
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexMAILING_ADDR_POSTAL_CD_NA").checked = !config.mailing.zip;
            selectCountry("ctl00_SiteContentPlaceHolder_FormView1_ddlMailCountry", config.mailing.country);
        }

        // Phone
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_HOME_TEL").value = config.primaryPhone;

        // Secondary Phone - tự tick Does Not Apply nếu trống
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_MOBILE_TEL").value = config.secondaryPhone || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_MOBILE_TEL_NA").checked = !config.secondaryPhone;

        // Work Phone - tự tick Does Not Apply nếu trống
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_BUS_TEL").value = config.workPhone || "";
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_cbexAPP_BUS_TEL_NA").checked = !config.workPhone;

        // Additional Phone (hỗ trợ nhiều dòng)
        triggerRadio("AddPhone", config.additionalPhones.length > 0 ? "Y" : "N");
        if (config.additionalPhones.length > 0) {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlAddPhone_ctl00_tbxAddPhoneInfo");
            for (let i = 0; i < config.additionalPhones.length; i++) {
                if (i > 0) await addAnother("ctl00_SiteContentPlaceHolder_FormView1_dtlAddPhone_ctl00_InsertButtonADDL_PHONE");
                const input = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlAddPhone_ctl0${i}_tbxAddPhoneInfo`);
                if (input) input.value = config.additionalPhones[i];
            }
        }

        // Email
        document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxAPP_EMAIL_ADDR").value = config.email;

        // Additional Email (hỗ trợ nhiều dòng)
        triggerRadio("AddEmail", config.additionalEmails.length > 0 ? "Y" : "N");
        if (config.additionalEmails.length > 0) {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlAddEmail_ctl00_tbxAddEmailInfo");
            for (let i = 0; i < config.additionalEmails.length; i++) {
                if (i > 0) await addAnother("ctl00_SiteContentPlaceHolder_FormView1_dtlAddEmail_ctl00_InsertButtonADDL_EMAIL");
                const input = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlAddEmail_ctl0${i}_tbxAddEmailInfo`);
                if (input) input.value = config.additionalEmails[i];
            }
        }

        // Social Media (hỗ trợ nhiều dòng)
        for (let i = 0; i < config.socials.length; i++) {
            if (i > 0) await addAnother("ctl00_SiteContentPlaceHolder_FormView1_dtlSocial_ctl00_InsertButtonSOCIAL_MEDIA_INFO");
            const prefix = i === 0 ? "ctl00" : `ctl0${i}`;
            const ddl = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlSocial_${prefix}_ddlSocialMedia`);
            if (ddl) {
                ddl.value = config.socials[i].platform;
                ddl.dispatchEvent(new Event('change', { bubbles: true }));
            }
            await sleep(700); // chờ identifier enable
            const handle = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlSocial_${prefix}_tbxSocialMediaIdent`);
            if (handle) handle.value = config.socials[i].handle;
        }

        // Additional Social (hỗ trợ nhiều dòng)
        triggerRadio("AddSocial", config.additionalSocials.length > 0 ? "Y" : "N");
        if (config.additionalSocials.length > 0) {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlAddSocial_ctl00_tbxAddSocialPlat");
            for (let i = 0; i < config.additionalSocials.length; i++) {
                if (i > 0) await addAnother("ctl00_SiteContentPlaceHolder_FormView1_dtlAddSocial_ctl00_InsertButtonADDL_SOCIAL_MEDIA");
                const plat = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlAddSocial_ctl0${i}_tbxAddSocialPlat`);
                const hand = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlAddSocial_ctl0${i}_tbxAddSocialHand`);
                if (plat) plat.value = config.additionalSocials[i].platform;
                if (hand) hand.value = config.additionalSocials[i].handle;
            }
        }

        alert("✅ ĐÃ ĐIỀN XONG ADDRESS & PHONE (v7.1 - Does Not Apply + nhiều Add Another)!\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillContactv7")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillContactv7";
        btn.textContent = "🛠 AUTO FILL ADDRESS & PHONE (1 CLICK v7.1)";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();