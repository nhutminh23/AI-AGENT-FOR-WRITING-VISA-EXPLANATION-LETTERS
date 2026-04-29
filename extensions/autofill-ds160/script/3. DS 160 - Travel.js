// ==UserScript==
// @name         03. DS 160 - Travel
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.3
// @description  1 click điền hết Travel - ĐÃ FIX Locations (hỗ trợ nhiều Add Another)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_travel.aspx?node=Travel
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        purposeOfTrip: "B",
        specifyOther: "B1-B2",
        specificTravel: "Y", // ← Đổi thành "N" để test

        // ──────── CHỈ DÙNG KHI specificTravel = "Y" ────────
        arrival: { day: "1", month: "7", year: "2026" },
        arriveFlight: "",
        arriveCity: "New York",
        departure: { day: "9", month: "7", year: "2026" },
        departFlight: "",
        departCity: "New York",
        locations: ["A", "B"],   // ← Bây giờ hỗ trợ nhiều item

        // ──────── ĐỊA CHỈ Ở MỸ (dùng cho CẢ Yes và No) ────────
        address: {
            street1: "136 W 42nd St",
            street2: "",
            city: "New York",
            state: "NY",
            zip: "10036"
        },

        // ──────── CHỈ DÙNG KHI specificTravel = "N" ────────
        intendedArrival: { day: "15", month: "8", year: "2026" },
        lengthOfStay: "14",
        lengthUnit: "D",

        // Payer
        payer: "O",
        payerSurname: "NGUYEN",
        payerGivenName: "VAN A",
        payerPhone: "0901234567",
        payerEmail: "payer@example.com",
        payerRelationship: "P",
        payerSameAddress: "Y",
        payerAddress: {
            street1: "789 Le Loi Street",
            street2: "Floor 10",
            city: "Ho Chi Minh City",
            state: "",
            zip: "700000",
            country: "Vietnam"
        }
    };
    // =================================================================

    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
    async function waitForElement(selector, timeout = 10000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const el = document.querySelector(selector);
            if (el && el.offsetParent !== null) return el;
            await sleep(400);
        }
        return null;
    }

    function setValue(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.value = value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function triggerRadio(radioId) {
        const radio = document.getElementById(radioId);
        if (radio) {
            radio.checked = true;
            radio.click();
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL TRAVEL (v7.3)", "color:#0066cc;font-weight:bold");

        // 1. Purpose + Specify
        const purposeSelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dlPrincipalAppTravel_ctl00_ddlPurposeOfTrip");
        if (purposeSelect) {
            purposeSelect.value = config.purposeOfTrip;
            purposeSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }

        const specifySelect = await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dlPrincipalAppTravel_ctl00_ddlOtherPurpose");
        if (specifySelect) {
            specifySelect.value = config.specifyOther;
            specifySelect.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // 2. Specific Travel Plans
        triggerRadio(`ctl00_SiteContentPlaceHolder_FormView1_rblSpecificTravel_${config.specificTravel === "Y" ? "0" : "1"}`);
        await sleep(1200);

        if (config.specificTravel === "Y") {
            // === YES: lịch trình chi tiết ===
            setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlARRIVAL_US_DTEDay", config.arrival.day);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlARRIVAL_US_DTEMonth", config.arrival.month);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxARRIVAL_US_DTEYear", config.arrival.year);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxArriveFlight", config.arriveFlight);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxArriveCity", config.arriveCity);

            setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlDEPARTURE_US_DTEDay", config.departure.day);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlDEPARTURE_US_DTEMonth", config.departure.month);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxDEPARTURE_US_DTEYear", config.departure.year);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxDepartFlight", config.departFlight);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxDepartCity", config.departCity);

            // ================== LOCATIONS - ĐÃ SỬA (Add Another) ==================
            for (let i = 0; i < config.locations.length; i++) {
                const loc = config.locations[i];

                // Nếu không phải item đầu tiên → click Add Another
                if (i > 0) {
                    const addBtn = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlTravelLoc_ctl0${i-1}_InsertButtonTravelLoc`);
                    if (addBtn) {
                        addBtn.click();
                        await sleep(800); // chờ dòng mới hiện ra
                    }
                }

                const prefix = i === 0 ? "ctl00" : `ctl0${i}`;
                const field = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlTravelLoc_${prefix}_tbxSPECTRAVEL_LOCATION`);
                if (field) field.value = loc;
            }

        } else {
            // === NO: Intended Date + Length of Stay ===
            setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlTRAVEL_DTEDay", config.intendedArrival.day);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_ddlTRAVEL_DTEMonth", config.intendedArrival.month);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxTRAVEL_DTEYear", config.intendedArrival.year);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxTRAVEL_LOS", config.lengthOfStay);

            const unitSelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlTRAVEL_LOS_CD");
            if (unitSelect) {
                unitSelect.value = config.lengthUnit;
                unitSelect.dispatchEvent(new Event('change', { bubbles: true }));
            }

            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxStreetAddress1", 12000);
        }

        // ====================== ADDRESS (chung cho cả Yes/No) ======================
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxStreetAddress1", config.address.street1);
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxStreetAddress2", config.address.street2 || "");
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxCity", config.address.city);

        const stateSelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlTravelState");
        if (stateSelect) {
            for (let opt of stateSelect.options) {
                if (opt.value === config.address.state || opt.text.toUpperCase() === config.address.state.toUpperCase()) {
                    stateSelect.value = opt.value;
                    stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    break;
                }
            }
        }
        setValue("ctl00_SiteContentPlaceHolder_FormView1_tbZIPCode", config.address.zip);

        // Payer (giữ nguyên như cũ)
        const payerSelect = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlWhoIsPaying");
        if (payerSelect) {
            payerSelect.value = config.payer;
            payerSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }

        if (config.payer === "O") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxPayerSurname");
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerSurname", config.payerSurname);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerGivenName", config.payerGivenName);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerPhone", config.payerPhone);
            setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPAYER_EMAIL_ADDR", config.payerEmail);

            const rel = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPayerRelationship");
            if (rel) rel.value = config.payerRelationship;

            triggerRadio(`ctl00_SiteContentPlaceHolder_FormView1_rblPayerAddrSameAsInd_${config.payerSameAddress === "Y" ? "0" : "1"}`);

            if (config.payerSameAddress === "N") {
                await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxPayerStreetAddress1");
                setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerStreetAddress1", config.payerAddress.street1);
                setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerStreetAddress2", config.payerAddress.street2 || "");
                setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerCity", config.payerAddress.city);
                setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerStateProvince", config.payerAddress.state || "");
                setValue("ctl00_SiteContentPlaceHolder_FormView1_tbxPayerPostalZIPCode", config.payerAddress.zip);

                const ctry = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_ddlPayerCountry");
                if (ctry) ctry.value = config.payerAddress.country === "Vietnam" ? "VTNM" : config.payerAddress.country;
            }
        }

        alert("✅ ĐÃ ĐIỀN XONG TOÀN BỘ TRAVEL (v7.3)!\n• Locations đã hỗ trợ Add Another đúng cách\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addFillButton() {
        if (document.getElementById("autoFillTravelBtn")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillTravelBtn";
        btn.innerHTML = "🛠 AUTO FILL TRAVEL INFO";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addFillButton, 1500));
})();