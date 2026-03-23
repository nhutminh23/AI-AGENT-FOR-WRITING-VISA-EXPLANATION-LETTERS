// ==UserScript==
// @name         04. DS 160 - Travel Companions
// @namespace    http://tampermonkey.net/
// @version      2026-03-05-v7.1
// @description  1 click điền hết + hỗ trợ nhiều Add Another (Individual)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_travelcompanions.aspx?node=TravelCompanions
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        // 1. Are there other persons traveling with you?
        otherPersons: "Y",          // "Y" = Yes, "N" = No

        // ================== CHỈ DÙNG KHI otherPersons = "Y" ==================
        groupTravel: "N",           // "Y" = Group, "N" = Individual

        // Nếu groupTravel = "Y"
        groupName: "Tour Group ABC",

        // Nếu groupTravel = "N" → thêm bao nhiêu người cũng được
        companions: [
            {
                surname: "Nguyen",
                givenName: "Anh",
                relationship: "F"       // F=FRIEND, P=PARENT, S=SPOUSE, C=CHILD, R=OTHER RELATIVE, B=BUSINESS, O=OTHER
            }
            // Thêm người thứ 2:
            , { surname: "Tran", givenName: "Binh", relationship: "S" }
            // , { surname: "Le", givenName: "Minh", relationship: "C" }
        ]
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

    function triggerRadio(radioId) {
        const radio = document.getElementById(radioId);
        if (radio) {
            radio.checked = true;
            radio.click();
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU AUTO FILL TRAVEL COMPANIONS (v7.1)", "color:#0066cc;font-weight:bold");

        // 1. Câu hỏi đầu: Other persons traveling with you?
        triggerRadio(`ctl00_SiteContentPlaceHolder_FormView1_rblOtherPersonsTravelingWithYou_${config.otherPersons === "Y" ? "0" : "1"}`);

        if (config.otherPersons === "N") {
            alert("✅ Đã điền xong (chọn No - không đi cùng ai)!");
            return;
        }

        // Chờ câu hỏi thứ 2 hiện ra
        await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_rblGroupTravel_0");

        // 2. Câu hỏi thứ 2: Group or organization?
        triggerRadio(`ctl00_SiteContentPlaceHolder_FormView1_rblGroupTravel_${config.groupTravel === "Y" ? "0" : "1"}`);

        // Chờ form load sau postback
        await waitForElement(config.groupTravel === "Y"
            ? "#ctl00_SiteContentPlaceHolder_FormView1_tbxGroupName"
            : "#ctl00_SiteContentPlaceHolder_FormView1_dlTravelCompanions_ctl00_tbxSurname", 8000);

        if (config.groupTravel === "Y") {
            // ================== ĐI NHÓM ==================
            const groupInput = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxGroupName");
            if (groupInput) groupInput.value = config.groupName;
            console.log("✅ Group Name:", config.groupName);
        } else {
            // ================== ĐI CÙNG NGƯỜI (Individual) - HỖ TRỢ NHIỀU NGƯỜI ==================
            for (let i = 0; i < config.companions.length; i++) {
                const person = config.companions[i];

                // Nếu không phải người đầu tiên → click Add Another
                if (i > 0) {
                    const addBtn = document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_dlTravelCompanions_ctl0" + (i-1) + "_InsertButtonPrincipalPOT") ||
                                   document.querySelector(".addone a"); // fallback
                    if (addBtn) {
                        addBtn.click();
                        await sleep(800); // chờ dòng mới hiện ra
                    }
                }

                const prefix = i === 0 ? "ctl00" : `ctl0${i}`;
                const surname = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dlTravelCompanions_${prefix}_tbxSurname`);
                const given   = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dlTravelCompanions_${prefix}_tbxGivenName`);
                const rel     = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dlTravelCompanions_${prefix}_ddlTCRelationship`);

                if (surname) surname.value = person.surname;
                if (given)   given.value   = person.givenName;
                if (rel) {
                    rel.value = person.relationship;
                    rel.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
            console.log(`✅ Đã điền ${config.companions.length} người đi cùng`);
        }

        alert("✅ ĐÃ ĐIỀN XONG PHẦN TRAVEL COMPANIONS (v7.1 - hỗ trợ nhiều Add Another)!\nKiểm tra lại rồi Next nhé Paul!");
    }

    // ================== THÊM NÚT AUTO FILL ==================
    function addFillButton() {
        if (document.getElementById("autoFillCompanionsBtn")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillCompanionsBtn";
        btn.innerHTML = "🛠 AUTO FILL COMPANIONS";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:12px 20px;background:#0066cc;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:bold;box-shadow:0 4px 12px rgba(0,0,0,0.3);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addFillButton, 1500));
})();