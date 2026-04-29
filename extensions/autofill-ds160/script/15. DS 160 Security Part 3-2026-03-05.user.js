// ==UserScript==
// @name         15. DS 160 Security Part 3
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.2
// @description  Fix hoàn toàn + bổ sung ExViolence (extrajudicial killings)
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_securityandbackground3.aspx?node=SecurityandBackground3
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const config = {
        illegalActivity:         { answer: "N", explain: "" },
        terroristActivity:       { answer: "N", explain: "" },
        terroristSupport:        { answer: "N", explain: "" },
        terroristOrg:            { answer: "N", explain: "" },
        terroristRel:            { answer: "N", explain: "" },
        genocide:                { answer: "N", explain: "" },
        torture:                 { answer: "N", explain: "" },
        childSoldier:            { answer: "N", explain: "" },
        religiousFreedom:        { answer: "N", explain: "" },
        populationControls:      { answer: "N", explain: "" },
        transplant:              { answer: "N", explain: "" },
        exViolence:              { answer: "N", explain: "" }   // ← ĐÃ BỔ SUNG
    };

    const mapping = {
        illegalActivity:         { radio: "IllegalActivity",         explainField: "tbxIllegalActivity" },
        terroristActivity:       { radio: "TerroristActivity",       explainField: "tbxTerroristActivity" },
        terroristSupport:        { radio: "TerroristSupport",        explainField: "tbxTerroristSupport" },
        terroristOrg:            { radio: "TerroristOrg",            explainField: "tbxTerroristOrg" },
        terroristRel:            { radio: "TerroristRel",            explainField: "tbxTerroristRel" },
        genocide:                { radio: "Genocide",                explainField: "tbxGenocide" },
        torture:                 { radio: "Torture",                 explainField: "tbxTorture" },
        childSoldier:            { radio: "ChildSoldier",            explainField: "tbxChildSoldier" },
        religiousFreedom:        { radio: "ReligiousFreedom",        explainField: "tbxReligiousFreedom" },
        populationControls:      { radio: "PopulationControls",      explainField: "tbxPopulationControls" },
        transplant:              { radio: "Transplant",              explainField: "tbxTransplant" },
        exViolence:              { radio: "ExViolence",              explainField: "tbxExViolence" }   // ← ĐÃ BỔ SUNG
    };

    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function triggerRadio(radioName, answer) {
        const suffix = answer === "Y" ? "_0" : "_1";
        let radio = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${radioName}${suffix}`);

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
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU SECURITY PART 3 (v7.2)", "color:#0066cc;font-weight:bold");

        for (let key in config) {
            const item = config[key];
            const map = mapping[key];

            await triggerRadio(map.radio, item.answer);
            await sleep(1300);   // delay đủ để No hoạt động ổn định

            if (item.answer === "Y" && item.explain) {
                await sleep(700);
                const tbx = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_${map.explainField}`);
                if (tbx) tbx.value = item.explain;
            }
        }

        console.log("%c✅ HOÀN TẤT SECURITY PART 3 v7.2!", "color:green;font-weight:bold");
        alert("✅ ĐÃ ĐIỀN XONG SECURITY PART 3 (v7.2)!\n• Đã bổ sung đầy đủ extrajudicial killings\n• Click 1 lần điền No hết\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillSec3")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillSec3";
        btn.innerHTML = "🛠 AUTO FILL SECURITY PART 3 v7.2";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:12px 20px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;box-shadow:0 4px 12px rgba(0,0,0,0.3);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();