// ==UserScript==
// @name         IMMI Smart AutoFill (Hub & Inject)
// @namespace    https://tampermonkey.net/
// @version      2.0
// @description  Unified autofill for Australian IMMI Visitor 600 form. Fetches data from local Hub (localhost:8000).
// @author       Visa AI Agent
// @match        https://online.immi.gov.au/elp/app*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // ===== GUARD: Prevent multiple injections from background.js =====
    if (window.__immiHubRunning) return;
    window.__immiHubRunning = true;

    const HUB_URL = "http://127.0.0.1:8000/australia/api/active-profile";
    let applicantData = null;
    let currentPage = null;
    let panelEl = null;

    // ==================== DETECT CURRENT PAGE ====================
    function detectPage() {
        // Method 1: Look for the specific IMMI page indicator element (e.g. "2/20")
        const pageLabel = document.querySelector('#_2a0b0a0a0c0');
        if (pageLabel) {
            const m = pageLabel.textContent.trim().match(/^(\d+)\s*\/\s*\d+$/);
            if (m) return parseInt(m[1]);
        }

        // Method 2: Scan all wc-label spans for "X/Y" pattern
        const labels = document.querySelectorAll('span.wc-label, .wc-label');
        for (const lbl of labels) {
            const txt = lbl.textContent.trim();
            const m = txt.match(/^(\d+)\s*\/\s*\d+$/);
            if (m) return parseInt(m[1]);
        }

        // Method 3: Fallback - search body text for "Page X of Y"
        const pageText = document.body.innerText;
        const match = pageText.match(/Page\s+(\d+)\s+of\s+(\d+)/i);
        if (match) return parseInt(match[1]);

        // Method 4: Check headings
        const heading = document.querySelector("h1, h2, .wc-heading");
        if (heading) {
            const hText = heading.textContent;
            const hMatch = hText.match(/(\d+)\s*(?:of|\/)\s*(\d+)/i);
            if (hMatch) return parseInt(hMatch[1]);
        }
        return null;
    }

    // ==================== FETCH DATA FROM HUB (via Extension Bridge) ====================
    async function fetchProfile() {
        // Use window.postMessage to ask bridge.js (ISOLATED world) to fetch via background.js
        // This bypasses Chrome's Mixed Content block (HTTPS page → HTTP localhost)
        return new Promise((resolve) => {
            const requestId = 'req_' + Date.now() + '_' + Math.random().toString(36).slice(2);

            function onResponse(event) {
                if (event.source !== window) return;
                if (!event.data || event.data.type !== 'IMMI_HUB_RESPONSE') return;
                if (event.data.requestId !== requestId) return;

                window.removeEventListener('message', onResponse);

                if (event.data.error || !event.data.data) {
                    console.warn('Hub fetch error:', event.data.error);
                    resolve(null);
                } else {
                    resolve(event.data.data);
                }
            }

            window.addEventListener('message', onResponse);

            window.postMessage({
                type: 'IMMI_HUB_FETCH',
                url: HUB_URL,
                requestId: requestId
            }, '*');

            // Timeout after 5 seconds
            setTimeout(() => {
                window.removeEventListener('message', onResponse);
                resolve(null);
            }, 5000);
        });
    }

    // ==================== DOM HELPERS ====================
    function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

    function findRadio(question, option) {
        return Array.from(document.querySelectorAll('label.wc-option'))
            .find(l => l.textContent.trim() === option &&
                  l.closest('fieldset') &&
                  l.closest('fieldset').textContent.includes(question))
            ?.querySelector('input[type="radio"]');
    }

    function setSelect(labelText, value) {
        const label = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes(labelText));
        if (!label) return false;
        const select = label.closest('.wc-row')?.querySelector('select') ||
                       label.parentElement?.parentElement?.querySelector('select');
        if (select) {
            select.value = value;
            select.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }
        return false;
    }

    function setInput(labelText, value) {
        const label = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes(labelText));
        if (!label) return false;
        const forId = label.getAttribute('for');
        const input = forId ? document.getElementById(forId) :
            label.closest('.wc-row')?.querySelector('input, textarea');
        if (input) {
            input.value = value;
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }
        return false;
    }

    function setTextarea(labelText, value) {
        const label = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.toLowerCase().includes(labelText.toLowerCase()));
        if (!label) return false;
        const forId = label.getAttribute('for');
        const ta = forId ? document.getElementById(forId) : null;
        if (ta) {
            ta.value = value;
            ta.dispatchEvent(new Event('input', {bubbles: true}));
            ta.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }
        return false;
    }

    function clickRadioByValue(value) {
        const radio = document.querySelector(`input[type="radio"][value="${value}"]`);
        if (radio) { radio.click(); return true; }
        return false;
    }

    // ==================== PAGE FILLERS ====================
    async function fillPage2(d) {
        console.log('[IMMI AutoFill] fillPage2 START', d);

        // 1. Outside Australia = Yes
        const yesRadio = findRadio("Is the applicant currently outside Australia?", "Yes");
        console.log('[IMMI] Step 1 - Outside Australia radio:', yesRadio);
        if (yesRadio) yesRadio.click();
        await delay(1500);

        // 2. Current location & Legal status
        console.log('[IMMI] Step 2 - Current location:', d.current_location);
        setSelect("Current location", d.current_location || "VIET");
        setSelect("Legal status", d.legal_status || "1");
        await delay(800);

        // 3. Purpose stream (radio by value)
        console.log('[IMMI] Step 3 - Purpose stream:', d.purpose_stream);
        clickRadioByValue(d.purpose_stream || "29");
        await delay(900);

        // 4. Frequent Traveller → initial purpose
        if (d.purpose_stream === "61" && d.initial_purpose) {
            clickRadioByValue(d.initial_purpose);
        }

        // 5. List all reasons - use findMultiSelect (proven working method)
        console.log('[IMMI] Step 5 - Visit reason:', d.visit_reason);
        const reasonLabel = Array.from(document.querySelectorAll('.wc-label'))
            .find(l => l.textContent.includes('List all reasons'));
        if (reasonLabel) {
            const reasonSelect = reasonLabel.closest('.wc-panel')?.querySelector('select');
            if (reasonSelect) {
                reasonSelect.value = d.visit_reason || "4";
                reasonSelect.dispatchEvent(new Event('change', {bubbles: true}));
                const plusBtn = document.querySelector('.wc_btn_icon.wc-invite');
                if (plusBtn) plusBtn.click();
                console.log('[IMMI] ✅ Visit reason set');
            } else {
                console.warn('[IMMI] ⚠️ Visit reason select not found');
            }
        }

        // 6. Significant dates - find label → get "for" attr → getElementById (proven working method)
        console.log('[IMMI] Step 6 - Significant dates');
        const datesLabel = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes('significant dates') ||
                      l.textContent.includes('Give details of any significant dates'));
        if (datesLabel) {
            const textareaId = datesLabel.getAttribute('for');
            const datesTA = textareaId ? document.getElementById(textareaId) : null;
            if (datesTA) {
                datesTA.value = d.significant_dates || "";
                datesTA.dispatchEvent(new Event('input', { bubbles: true }));
                datesTA.dispatchEvent(new Event('change', { bubbles: true }));
                console.log('[IMMI] ✅ Significant dates filled');
            } else {
                console.warn('[IMMI] ⚠️ Significant dates textarea not found');
            }
        }

        // 7. Group processing (JSON: "1"=Yes, "2"=No)
        if (d.group_processing === "1") {
            findRadio("Is this application being lodged as part of a group", "Yes")?.click();
        } else {
            findRadio("Is this application being lodged as part of a group", "No")?.click();
        }
        await delay(600);

        // 8. Special category = No (JSON: "2"=No)
        findRadio("Is the applicant travelling as a representative of a foreign government", "No")?.click();

        console.log('[IMMI AutoFill] fillPage2 DONE ✅');
    }

    async function fillPage3(d) {
        setInput("Family name", d.family_name || "");
        setInput("Given names", d.given_names || "");
        await delay(500);

        if (d.sex) findRadio("Sex", d.sex);
        setInput("Date of birth", d.date_of_birth || "");
        setInput("Town / City", d.place_of_birth_city || "");
        setSelect("Country of birth", d.place_of_birth_country || "VIET");
        await delay(500);

        if (d.relationship_status) {
            setSelect("Relationship status", d.relationship_status);
        }

        setInput("Passport number", d.passport_number || "");
        setSelect("Country of passport", d.passport_country || "VIET");
        setSelect("Nationality of passport holder", d.passport_nationality || "VNM");
        setInput("Date of issue", d.passport_issue_date || "");
        setInput("Date of expiry", d.passport_expiry_date || "");
        setInput("Place of issue / issuing authority", d.passport_issuing_authority || "");
        setInput("National identity card number", d.national_id_number || "");
    }

    async function fillPage5(d) {
        if (d.other_names_used === "No") {
            findRadio("Has the applicant been known by any other names", "No")?.click();
        }
        await delay(500);
        if (d.other_passports === "No") {
            findRadio("Does the applicant hold, or has the applicant previously held, any passports", "No")?.click();
        }
        if (d.other_citizenships === "No") {
            findRadio("Is the applicant a citizen of any other country", "No")?.click();
        }
        if (d.citizen_of_birth_country === "Yes") {
            findRadio("Is the applicant a citizen of their country of birth", "Yes")?.click();
        }
    }

    async function fillPage6(d) {
        setInput("Proposed date of arrival", d.proposed_arrival_date || "");
        setInput("Proposed date of departure", d.proposed_departure_date || "");
        await delay(500);
        if (d.proposed_duration_months) setInput("Months", d.proposed_duration_months);
        if (d.proposed_duration_days) setInput("Days", d.proposed_duration_days);
        if (d.previous_australian_visa === "No") {
            findRadio("Has the applicant previously held a visa for Australia", "No")?.click();
        }
    }

    async function fillPage8(d) {
        setInput("Address line 1", d.residential_address_line1 || "");
        if (d.residential_address_line2) setInput("Address line 2", d.residential_address_line2);
        setInput("Town / City", d.residential_city || "");
        if (d.residential_state) setInput("State / Province", d.residential_state);
        setInput("Postal code", d.residential_postcode || "");
        setSelect("Country", d.residential_country || "VIET");
        await delay(500);

        if (d.postal_same_as_residential === "Yes") {
            findRadio("Is the applicant's postal address the same", "Yes")?.click();
        }

        setInput("Home", d.phone_home || "");
        setInput("Mobile / Cell", d.phone_mobile || "");
        setInput("Email", d.email || "");

        if (d.address_in_australia) {
            setInput("Address in Australia", d.address_in_australia);
        }
    }

    async function fillPage9(d) {
        if (d.employment_status) {
            setSelect("Employment status", d.employment_status);
            await delay(500);
        }
        setInput("Employer name", d.employer_name || "");
        setInput("Employer address", d.employer_address || "");
        setInput("Job title", d.job_title || "");
        setInput("Date of employment", d.employment_start_date || "");
        if (d.annual_income_aud) setInput("Annual personal income", d.annual_income_aud);
        if (d.highest_qualification) setSelect("Highest qualification", d.highest_qualification);
        if (d.qualification_field) setInput("field of study", d.qualification_field);
    }

    async function fillPage11(d) {
        if (d.travelling_with_others === "Yes") {
            findRadio("Is the applicant travelling with any other applicants", "Yes")?.click();
            await delay(500);
            if (d.companion_names) setTextarea("names of applicants", d.companion_names);
        } else {
            findRadio("Is the applicant travelling with any other applicants", "No")?.click();
        }
        await delay(500);

        if (d.sponsor_name) {
            setInput("Family name", d.sponsor_name.split(" ").pop() || "");
            setInput("Address", d.sponsor_address || "");
            if (d.sponsor_phone) setInput("Telephone", d.sponsor_phone);
            if (d.sponsor_relationship) setInput("Relationship", d.sponsor_relationship);
        }
    }

    // Page-to-filler mapping
    const PAGE_FILLERS = {
        2: fillPage2,
        3: fillPage3,
        5: fillPage5,
        6: fillPage6,
        8: fillPage8,
        9: fillPage9,
        11: fillPage11,
    };

    // ==================== FLOATING PANEL ====================
    function createPanel() {
        if (document.getElementById('immi-hub-panel')) return;

        panelEl = document.createElement('div');
        panelEl.id = 'immi-hub-panel';
        panelEl.style.cssText = `
            position: fixed; top: 20px; left: 20px; z-index: 999999;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 2px solid #f59e0b; border-radius: 12px;
            padding: 16px; min-width: 280px; max-width: 350px;
            font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
            color: #e2e8f0; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        `;
        panelEl.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div style="font-weight:700; font-size:14px; color:#f59e0b;">🇦🇺 IMMI AutoFill</div>
                <button id="immi-hub-minimize" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:16px;">—</button>
            </div>
            <div id="immi-hub-body">
                <div id="immi-hub-profile" style="font-size:13px; margin-bottom:10px; color:#94a3b8;">⏳ Đang kết nối Hub...</div>
                <div id="immi-hub-page" style="font-size:12px; margin-bottom:12px; color:#64748b;"></div>
                <button id="immi-hub-fill" style="width:100%; padding:12px; background:#f59e0b; color:#000; border:none; border-radius:8px; font-weight:700; font-size:14px; cursor:pointer;">
                    🚀 Auto-Fill Trang Này
                </button>
                <div id="immi-hub-status" style="font-size:12px; margin-top:8px; color:#94a3b8;"></div>
            </div>
        `;
        document.body.appendChild(panelEl);

        // Minimize toggle
        const body = document.getElementById('immi-hub-body');
        document.getElementById('immi-hub-minimize').addEventListener('click', () => {
            body.style.display = body.style.display === 'none' ? 'block' : 'none';
        });

        // Fill button
        document.getElementById('immi-hub-fill').addEventListener('click', runAutoFill);
    }

    async function updatePanel() {
        const profileEl = document.getElementById('immi-hub-profile');
        const pageEl = document.getElementById('immi-hub-page');
        const statusEl = document.getElementById('immi-hub-status');
        const fillBtn = document.getElementById('immi-hub-fill');

        // Fetch profile
        applicantData = await fetchProfile();
        currentPage = detectPage();

        if (applicantData && applicantData.applicant_name) {
            profileEl.innerHTML = `🟢 <strong style="color:#4ade80;">${applicantData.applicant_name}</strong>`;
        } else {
            profileEl.innerHTML = `🔴 <span style="color:#f87171;">Chưa có data. Dán JSON ở localhost:8000</span>`;
        }

        if (currentPage) {
            const hasData = applicantData && applicantData[`page_${currentPage}`];
            pageEl.textContent = `📄 Trang ${currentPage} ${hasData ? '✅ Có data' : '⚠️ Không có data cho trang này'}`;
            fillBtn.disabled = !hasData;
            fillBtn.textContent = hasData ? `🚀 Auto-Fill Trang ${currentPage}` : `⚪ Không có data trang ${currentPage}`;
        } else {
            pageEl.textContent = `📄 Không detect được trang số mấy`;
        }
    }

    async function runAutoFill() {
        const statusEl = document.getElementById('immi-hub-status');
        const fillBtn = document.getElementById('immi-hub-fill');

        if (!applicantData) {
            statusEl.textContent = "❌ Không có data. Dán JSON trên localhost:8000 trước!";
            statusEl.style.color = "#f87171";
            return;
        }

        if (!currentPage) {
            statusEl.textContent = "❌ Không detect được trang.";
            statusEl.style.color = "#f87171";
            return;
        }

        const pageKey = `page_${currentPage}`;
        const pageData = applicantData[pageKey];
        if (!pageData) {
            statusEl.textContent = `⚠️ Không có data cho ${pageKey}`;
            statusEl.style.color = "#fbbf24";
            return;
        }

        const filler = PAGE_FILLERS[currentPage];
        if (!filler) {
            statusEl.textContent = `⚠️ Chưa hỗ trợ trang ${currentPage}`;
            statusEl.style.color = "#fbbf24";
            return;
        }

        fillBtn.disabled = true;
        fillBtn.textContent = "⏳ Đang điền...";
        statusEl.textContent = "";

        try {
            await filler(pageData);
            statusEl.textContent = `✅ Đã điền xong trang ${currentPage}! Kiểm tra lại trước khi Next.`;
            statusEl.style.color = "#4ade80";
        } catch (e) {
            statusEl.textContent = `❌ Lỗi: ${e.message}`;
            statusEl.style.color = "#f87171";
        } finally {
            fillBtn.disabled = false;
            fillBtn.textContent = `🚀 Auto-Fill Trang ${currentPage}`;
        }
    }

    // ==================== INIT ====================
    async function init() {
        createPanel();
        await updatePanel();

        // Re-check every 3 seconds (page navigation in IMMI is SPA-like)
        setInterval(async () => {
            const newPage = detectPage();
            if (newPage !== currentPage) {
                currentPage = newPage;
                await updatePanel();
            }
        }, 3000);
    }

    // Wait for page to fully render
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(init, 1500));
    } else {
        setTimeout(init, 1500);
    }
})();
