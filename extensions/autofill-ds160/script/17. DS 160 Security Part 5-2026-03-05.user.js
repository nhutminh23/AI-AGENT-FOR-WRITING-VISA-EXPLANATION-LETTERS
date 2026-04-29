// ==UserScript==
// @name         17. DS 160 Security Part 5
// @namespace    http://tampermonkey.net/
// @version      2026-03-05
// @description  Part 5: ChildCustody, VotingViolation...
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_securityandbackground5.aspx?node=SecurityandBackground5
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const config = {
        childCustody:    { answer: "Y", explain: "test" },
        votingViolation: { answer: "Y", explain: "test" },
        renounceExp:     { answer: "Y", explain: "test" },
        reimburseSchool: { answer: "Y", explain: "test" }   // không có explain
    };

    const mapping = {
        childCustody:    { radio: "ChildCustody",    explain: "tbxChildCustody" },
        votingViolation: { radio: "VotingViolation", explain: "tbxVotingViolation" },
        renounceExp:     { radio: "RenounceExp",     explain: "tbxRenounceExp" },
        reimburseSchool: { radio: "AttWoReimb",      explain: "" }
    };

    // (giữ nguyên các hàm sleep, waitForElement, triggerYes, fillForm, addButton như các script trước)

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

    function triggerYes(radioName) {
        const yes = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${radioName}_0`);
        if (yes) {
            yes.checked = true;
            yes.click();
            yes.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function fillForm() {
        for (let key in config) {
            const item = config[key];
            const map = mapping[key];
            if (item.answer !== "Y") continue;

            triggerYes(map.radio);

            if (map.explain) {
                await waitForElement(`#ctl00_SiteContentPlaceHolder_FormView1_${map.explain}`);
                const tbx = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_${map.explain}`);
                if (tbx) tbx.value = item.explain;
            }
        }
        alert("✅ ĐÃ ĐIỀN XONG PART 5!");
    }

    function addButton() {
        const btn = document.createElement("button");
        btn.textContent = "🛠 AUTO FILL SECURITY PART 5";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:12px 20px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1200));
})();