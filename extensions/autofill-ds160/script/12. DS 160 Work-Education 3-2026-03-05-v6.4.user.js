// ==UserScript==
// @name         12. DS 160 Work/Education 3
// @namespace    http://tampermonkey.net/
// @version      2026-03-06-v7.0
// @description  Fix hoàn toàn: Tự động Add Another cho languages, countries, organizations, military
// @author       Mỹ
// @match        https://ceac.state.gov/GenNIV/General/complete/complete_workeducation3.aspx?node=WorkEducation3
// @icon         https://www.google.com/s2/favicons?sz=64&domain=state.gov
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ================== 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 ==================
    const config = {
        // 1. Clan or Tribe
        hasClan: "Y",
        clanName: "Kinh",
        // 2. Languages
        languages: ["English", "Vietnamese", "French"], // thêm bao nhiêu cũng được
        // 3. Countries visited
        hasCountriesVisited: "Y",
        visitedCountries: ["CHIN", "COL", "THAI"], // mã hoặc tên đầy đủ
        // 4. Organizations
        hasOrganizations: "Y",
        organizations: ["Vietnam Graphic Design Association", "Vietnam IT Association"],
        // 5. Specialized skills
        hasSpecializedSkills: "Y",
        specializedExplain: "test",
        // 6. Military service
        hasMilitary: "Y",
        military: [
            {
                country: "VTNM",
                branch: "Army",
                rank: "Sergeant",
                specialty: "Infantry",
                from: { day: "1", month: "6", year: "2018" },
                to: { day: "31", month: "10", year: "2020" }
            }
            // thêm quân ngũ thứ 2: , { ... }
        ],
        // 7. Paramilitary / Insurgent
        hasInsurgent: "Y",
        insurgentExplain: "test"
    };
    // =================================================================


    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function waitForElement(selector, timeout = 7000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            const el = document.querySelector(selector);
            if (el) return el;
            await sleep(200);
        }
        return null;
    }

    function triggerRadio(name, value) {
        const yes = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${name}_0`);
        const no = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_rbl${name}_1`);
        const target = value === "Y" ? yes : no;
        if (target) {
            target.checked = true;
            target.click();
            target.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function fillForm() {
        console.log("%c🚀 BẮT ĐẦU ONE-CLICK FULL v7.0 - Work/Education 3", "color:#0066cc;font-weight:bold");

        // 1. Clan or Tribe
        triggerRadio("CLAN_TRIBE_IND", config.hasClan);
        if (config.hasClan === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxCLAN_TRIBE_NAME");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxCLAN_TRIBE_NAME").value = config.clanName;
        }

        // 2. Languages
        triggerRadio("LANGUAGES_IND", config.languages.length > 0 ? "Y" : "N");
        if (config.languages.length > 0) {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlLANGUAGES_ctl00_tbxLANGUAGE_NAME");
            for (let i = 0; i < config.languages.length; i++) {
                if (i > 0) {
                    const addBtn = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlLANGUAGES_ctl0${i-1}_InsertButtonLANGUAGE`);
                    if (addBtn) {
                        addBtn.click();
                        await sleep(800);
                    }
                }
                const prefix = i === 0 ? "ctl00" : `ctl0${i}`;
                const input = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlLANGUAGES_${prefix}_tbxLANGUAGE_NAME`);
                if (input) input.value = config.languages[i];
            }
        }

        // 3. Countries visited
        triggerRadio("COUNTRIES_VISITED_IND", config.hasCountriesVisited);
        if (config.hasCountriesVisited === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlCountriesVisited_ctl00_ddlCOUNTRIES_VISITED");
            for (let i = 0; i < config.visitedCountries.length; i++) {
                if (i > 0) {
                    const addBtn = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlCountriesVisited_ctl0${i-1}_InsertButtonCountriesVisited`);
                    if (addBtn) {
                        addBtn.click();
                        await sleep(800);
                    }
                }
                const prefix = i === 0 ? "ctl00" : `ctl0${i}`;
                const sel = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlCountriesVisited_${prefix}_ddlCOUNTRIES_VISITED`);
                if (sel) sel.value =config.visitedCountries[i];
            }
        }

        // 4. Organizations
        triggerRadio("ORGANIZATION_IND", config.hasOrganizations);
        if (config.hasOrganizations === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlORGANIZATIONS_ctl00_tbxORGANIZATION_NAME");
            for (let i = 0; i < config.organizations.length; i++) {
                if (i > 0) {
                    const addBtn = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlORGANIZATIONS_ctl0${i-1}_InsertButtonORGANIZATION`);
                    if (addBtn) {
                        addBtn.click();
                        await sleep(800);
                    }
                }
                const prefix = i === 0 ? "ctl00" : `ctl0${i}`;
                const input = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlORGANIZATIONS_${prefix}_tbxORGANIZATION_NAME`);
                if (input) input.value = config.organizations[i];
            }
        }

        // 5. Specialized skills
        triggerRadio("SPECIALIZED_SKILLS_IND", config.hasSpecializedSkills);
        if (config.hasSpecializedSkills === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxSPECIALIZED_SKILLS_EXPL");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxSPECIALIZED_SKILLS_EXPL").value = config.specializedExplain;
        }

        // 6. Military service
        triggerRadio("MILITARY_SERVICE_IND", config.hasMilitary);
        if (config.hasMilitary === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl00_ddlMILITARY_SVC_CNTRY");
            for (let i = 0; i < config.military.length; i++) {
                if (i > 0) {
                    const addBtn = document.getElementById(`ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl0${i-1}_InsertButtonMILITARY_SERVICE`);
                    if (addBtn) {
                        addBtn.click();
                        await sleep(800);
                    }
                }
                const p = `ctl00_SiteContentPlaceHolder_FormView1_dtlMILITARY_SERVICE_ctl0${i}`;
                const countrySel = document.getElementById(p + "_ddlMILITARY_SVC_CNTRY");
                if (countrySel) countrySel.value =config.military[i].country;
                document.getElementById(p + "_tbxMILITARY_SVC_BRANCH").value = config.military[i].branch;
                document.getElementById(p + "_tbxMILITARY_SVC_RANK").value = config.military[i].rank;
                document.getElementById(p + "_tbxMILITARY_SVC_SPECIALTY").value = config.military[i].specialty;
                // From
                document.getElementById(p + "_ddlMILITARY_SVC_FROMDay").value = config.military[i].from.day;
                document.getElementById(p + "_ddlMILITARY_SVC_FROMMonth").value = config.military[i].from.month;
                document.getElementById(p + "_tbxMILITARY_SVC_FROMYear").value = config.military[i].from.year;
                // To
                document.getElementById(p + "_ddlMILITARY_SVC_TODay").value = config.military[i].to.day;
                document.getElementById(p + "_ddlMILITARY_SVC_TOMonth").value =config.military[i].to.month;
                document.getElementById(p + "_tbxMILITARY_SVC_TOYear").value = config.military[i].to.year;
            }
        }

        // 7. Paramilitary / Insurgent
        triggerRadio("INSURGENT_ORG_IND", config.hasInsurgent);
        if (config.hasInsurgent === "Y") {
            await waitForElement("#ctl00_SiteContentPlaceHolder_FormView1_tbxINSURGENT_ORG_EXPL");
            document.getElementById("ctl00_SiteContentPlaceHolder_FormView1_tbxINSURGENT_ORG_EXPL").value = config.insurgentExplain;
        }

        finish();
    }

    function finish() {
        console.log("%c🎉 HOÀN TẤT ONE-CLICK FULL v7.0 - Work/Education 3!", "color:green;font-weight:bold;font-size:16px");
        alert("✅ ĐÃ ĐIỀN XONG WORK/EDUCATION 3 (v7.0)!\n• Tự động Add Another cho tất cả mảng\nKiểm tra lại rồi Next nhé Paul!");
    }

    function addButton() {
        if (document.getElementById("autoFillWorkEdu3v70")) return;
        const btn = document.createElement("button");
        btn.id = "autoFillWorkEdu3v70";
        btn.textContent = "🛠 AUTO FILL WORK/EDUCATION 3 (1 CLICK v7.0)";
        btn.style.cssText = "position:fixed;top:15px;right:15px;z-index:99999;padding:14px 24px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:15px;box-shadow:0 6px 15px rgba(0,0,0,0.4);";
        document.body.appendChild(btn);
        btn.addEventListener("click", fillForm);
    }

    window.addEventListener("load", () => setTimeout(addButton, 1500));
})();