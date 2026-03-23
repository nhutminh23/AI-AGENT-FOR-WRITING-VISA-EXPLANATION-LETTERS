// ==UserScript==
// @name         13. DS 160 Security Part 1
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.3
// @description  Fix mạnh nhất: Click 1 lần điền No hết (delay 1300ms + trigger siêu mạnh)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_securityandbackground1.aspx?node=SecurityandBackground1
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const config = {
        disease:   { answer: "N", explain: "" },
        disorder:  { answer: "N", explain: "" },
        druguser:  { answer: "N", explain: "" }
    };

    const mapping = {
        disease:   { radio: "Disease",   explainField: "tbxDisease" },
        disorder:  { radio: "Disorder",  explainField: "tbxDisorder" },
        druguser:  { radio: "Druguser",  explainField: "tbxDruguser" }
    };

    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function triggerRadio(radioName, answer) {
        const suffix = answer === "Y" ? "_0" : "_1";
        let radio = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${radioName}${suffix}`);

        // Fallback selector (phòng trường hợp ID thay đổi)
        if (!radio) {
            radio = document.querySelector(`input[name*="rbl${radioName}"][value="${answer}"]`);
        }

        if (radio) {
            console.log(`→ Trigger ${radioName} = ${answer}`);
            radio.checked = true;
            radio.click();
            radio.dispatchEvent(new Event('click', { bubbles: true }));
            radio.dispatchEvent(new Event('change', { bubbles: true }));
            radio.dispatchEvent(new Event('blur', { bubbles: true }));
        } else {
            console.error(`❌ Không tìm thấy radio cho ${radioName}`);
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU SECURITY PART 1 (v7.3 - Fix No mạnh nhất)", "color:#0066cc;font-weight:bold");

        for (let key in config) {
            const item = config[key];
            const map = mapping[key];

            await triggerRadio(map.radio, item.answer);

            // Delay dài để ShowHideDiv + postback chạy xong (đây là chìa khóa)
            await sleep(1300);

            if (item.answer === "Y" && item.explain) {
                await sleep(700);
                const tbx = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_${map.explainField}`);
                if (tbx) tbx.value = item.explain;
            }
        }

        console.log("%c✅ HOÀN TẤT SECURITY PART 1 v7.3!", "color:green;font-weight:bold");
        alert("✅ ĐÃ ĐIỀN XONG SECURITY PART 1 (v7.3)!\n• Click 1 lần điền No hết\n• Delay đã tăng tối đa\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillSec1")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillSec1";
        btn.innerHTML = "🛠 AUTO FILL SECURITY PART 1 v7.3";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:12px 20px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 4px 12px rgba(0,0,0,0.3);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();