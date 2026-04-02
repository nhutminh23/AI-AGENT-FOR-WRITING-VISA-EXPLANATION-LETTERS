/**
 * IMMI Form Filler — MAIN WORLD content script
 * 
 * Page mapping (đúng theo IMMI form thật):
 *   Page 2/20 = Application context
 *   Page 3/20 = Passport and identity details
 *   Page 5/20 = Travelling companion
 *   Page 6/20 = Contact details (address, phone, email)
 *   Page 8/20 = Non-accompanying family member
 *   Page 9/20 = Planned travel + Contact in Australia
 *   Page 11/20 = Current overseas employment
 */

(function() {
    'use strict';

    if (window.__immiFillerReady) return;
    window.__immiFillerReady = true;

    console.log('[IMMI Filler] MAIN world script loaded');

    // ==================== DOM HELPERS ====================
    function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

    function setTextInput(labelText, value) {
        if (!value) return false;
        const lbl = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes(labelText));
        if (!lbl) {
            console.log(`[IMMI MAIN] ❌ Label not found: ${labelText}`);
            return false;
        }

        let input = null;
        // Try 'for' attribute first
        const forId = lbl.getAttribute('for');
        if (forId) {
            input = document.getElementById(forId) || document.getElementById(forId + '_input');
        }

        // Fallback to closest row/container
        if (!input) {
            input = lbl.closest('.wc-row, .wc-panel')?.querySelector('input[type="text"]');
        }

        if (input) {
            input.value = value;
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            console.log(`[IMMI MAIN] ✅ setTextInput: ${labelText} = "${value}"`);
            return true;
        }
        console.log(`[IMMI MAIN] ❌ Input element not found for label: ${labelText}`);
        return false;
    }

    function setSelect(labelText, value) {
        const label = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes(labelText));
        if (!label) return false;
        const forId = label.getAttribute('for');
        if (forId) {
            const sel = document.getElementById(forId) || document.getElementById(forId + '_input');
            if (sel && sel.tagName === 'SELECT') {
                sel.value = value;
                sel.dispatchEvent(new Event('change', {bubbles: true}));
                return true;
            }
        }
        const row = label.closest('.wc-row');
        if (row) {
            const sel = row.querySelector('select');
            if (sel) { sel.value = value; sel.dispatchEvent(new Event('change', {bubbles: true})); return true; }
        }
        let el = label.parentElement;
        for (let i = 0; i < 5 && el; i++) {
            const sel = el.querySelector('select');
            if (sel) { sel.value = value; sel.dispatchEvent(new Event('change', {bubbles: true})); return true; }
            el = el.parentElement;
        }
        return false;
    }

    function setInput(labelText, value) {
        if (!value) return false;
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

    function setEmailInput(labelText, value) {
        if (!value) return false;
        const label = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes(labelText));
        if (!label) return false;
        const row = label.closest('.wc-row') || label.closest('.wc-panel');
        const input = row?.querySelector('input[type="text"], input[type="email"]');
        if (input) {
            input.value = value;
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }
        return false;
    }

    function clickRadioByText(questionText, optionText) {
        for (const l of document.querySelectorAll('label.wc-option')) {
            if (l.textContent.trim() === optionText) {
                const fs = l.closest('fieldset');
                if (fs && fs.textContent.includes(questionText)) {
                    const input = l.querySelector('input[type="radio"]');
                    if (input) { input.click(); return true; }
                }
            }
        }
        return false;
    }

    function findRadio(question, option) {
        return Array.from(document.querySelectorAll('label.wc-option'))
            .find(l => l.textContent.trim() === option &&
                  l.closest('fieldset')?.textContent.includes(question))
            ?.querySelector('input[type="radio"]');
    }

    function clickRadioByValue(value) {
        const radio = document.querySelector(`input[type="radio"][value="${value}"]`);
        if (radio) { radio.click(); return true; }
        return false;
    }

    function clickRadioInFieldset(label, value) {
        for (const r of document.querySelectorAll('input[type="radio"]')) {
            if (r.value === value && r.closest('fieldset')?.textContent.includes(label)) {
                r.click(); return true;
            }
        }
        return false;
    }

    function setComboBox(labelText, value) {
        const label = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes(labelText));
        if (!label) return false;
        const input = label.closest('.wc-row')?.querySelector('input[type="text"]');
        if (input) {
            input.value = value;
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            setTimeout(() => {
                const suggestion = document.querySelector(`span[data-wc-value="${value}"]`);
                if (suggestion) suggestion.click();
            }, 300);
            return true;
        }
        return false;
    }

    // ==================== PAGE 2: Application context ====================
    async function fillPage2(d) {
        console.log('[IMMI MAIN] fillPage2 START — Application context');
        const yesRadio = findRadio("Is the applicant currently outside Australia?", "Yes");
        if (yesRadio) yesRadio.click();
        await delay(1500);

        setSelect("Current location", d.current_location || "VIET");
        setSelect("Legal status", d.legal_status || "1");
        await delay(800);

        clickRadioByValue(d.purpose_stream || "29");
        await delay(900);

        if (d.purpose_stream === "61" && d.initial_purpose) clickRadioByValue(d.initial_purpose);

        const reasonLabel = Array.from(document.querySelectorAll('.wc-label'))
            .find(l => l.textContent.includes('List all reasons'));
        if (reasonLabel) {
            const sel = reasonLabel.closest('.wc-panel')?.querySelector('select');
            if (sel) {
                sel.value = d.visit_reason || "4";
                sel.dispatchEvent(new Event('change', {bubbles: true}));
                const plusBtn = document.querySelector('.wc_btn_icon.wc-invite');
                if (plusBtn) plusBtn.click();
            }
        }

        const datesLabel = Array.from(document.querySelectorAll('label.wc-label'))
            .find(l => l.textContent.includes('significant dates') || l.textContent.includes('Give details of any significant dates'));
        if (datesLabel) {
            const taId = datesLabel.getAttribute('for');
            const ta = taId ? document.getElementById(taId) : null;
            if (ta) {
                ta.value = d.significant_dates || "";
                ta.dispatchEvent(new Event('input', {bubbles: true}));
                ta.dispatchEvent(new Event('change', {bubbles: true}));
            }
        }

        if (d.group_processing === "1") findRadio("Is this application being lodged as part of a group", "Yes")?.click();
        else findRadio("Is this application being lodged as part of a group", "No")?.click();
        await delay(600);

        findRadio("Is the applicant travelling as a representative of a foreign government", "No")?.click();
        console.log('[IMMI MAIN] fillPage2 DONE ✅');
    }

    // ==================== PAGE 3: Passport & Identity ====================
    async function fillPage3(d) {
        console.log('[IMMI MAIN] fillPage3 START — Passport details');
        setTextInput("Family name", d.family_name || "");
        setTextInput("Given names", d.given_names || "");
        if (d.sex) clickRadioInFieldset("Sex", d.sex);

        setTextInput("Date of birth", d.date_of_birth || "");
        setTextInput("Passport number", d.passport_number || "");
        setSelect("Country of passport", d.passport_country || "VNM");
        setSelect("Nationality of passport holder", d.passport_nationality || "VNM");
        setTextInput("Date of issue", d.passport_issue_date || "");
        setTextInput("Date of expiry", d.passport_expiry_date || "");
        setTextInput("Place of issue / issuing authority", d.passport_issuing_authority || "");

        if (d.has_national_id === "Yes") {
            clickRadioByText("Does this applicant have a national identity card?", "Yes");
            await delay(1500);
            setTextInput("Family name", d.national_id_family_name || d.family_name || "");
            setTextInput("Given names", d.national_id_given_names || d.given_names || "");
            setTextInput("Identification number", d.national_id_number || "");
            setSelect("Country of issue", d.national_id_country || "VIET");
            setTextInput("Date of issue", d.national_id_issue_date || "");
            setTextInput("Date of expiry", d.national_id_expiry_date || "");
        } else {
            clickRadioByText("Does this applicant have a national identity card?", "No");
        }

        clickRadioByText("Is the applicant a Pacific-Australia Card holder?", d.pacific_australia_card === "Yes" ? "Yes" : "No");

        setTextInput("Town / City", d.place_of_birth_city || "");
        if (d.place_of_birth_state) setTextInput("State / Province", d.place_of_birth_state);
        setSelect("Country of birth", d.place_of_birth_country || "VIET");
        if (d.relationship_status) setSelect("Relationship status", d.relationship_status);

        clickRadioByText("Is this applicant currently, or have they ever been known by any other names?", d.other_names_used === "Yes" ? "Yes" : "No");
        clickRadioByText("Is this applicant a citizen of the selected country of passport", d.citizen_of_passport_country === "Yes" ? "Yes" : "No");
        clickRadioByText("Is this applicant a citizen of any other country?", d.citizen_of_other_country === "Yes" ? "Yes" : "No");
        clickRadioByText("Has this applicant previously travelled to Australia?", d.previously_travelled_to_australia === "Yes" ? "Yes" : "No");
        clickRadioByText("Has this applicant previously applied for a visa to Australia?", d.previously_applied_visa === "Yes" ? "Yes" : "No");
        clickRadioByText("Does this applicant have an Australian visa grant number?", d.has_grant_number === "Yes" ? "Yes" : "No");
        clickRadioByText("Does this applicant have any other passports or documents for travel?", d.other_passports === "Yes" ? "Yes" : "No");
        clickRadioByText("Does this applicant have other identity documents?", d.other_identity_docs === "Yes" ? "Yes" : "No");
        clickRadioByText("Has this applicant undertaken a health examination for an Australian visa in the last 12 months?", d.health_examination === "Yes" ? "Yes" : "No");

        console.log('[IMMI MAIN] fillPage3 DONE ✅');
    }

    // ==================== PAGE 5: Travelling companion ====================
    async function fillPage5(d) {
        console.log('[IMMI MAIN] fillPage5 START — Travelling companion');
        if (!d.companions || d.companions.length === 0) return;

        for (let i = 0; i < d.companions.length; i++) {
            const comp = d.companions[i];
            console.log(`[IMMI MAIN] Companion ${i + 1}:`, comp.family_name, comp.given_names);

            setSelect("Relationship to the applicant", comp.relationship || "33");
            await delay(600);
            setTextInput("Family name", comp.family_name || "");
            setTextInput("Given names", comp.given_names || "");
            if (comp.sex) clickRadioInFieldset("Sex", comp.sex);
            setTextInput("Date of birth", comp.date_of_birth || "");
            await delay(300);

            if (i < d.companions.length - 1) {
                const saveBtn = document.querySelector('button[title="Save the current entry"]');
                if (saveBtn) { saveBtn.click(); await delay(1500); }
            }
        }
        console.log('[IMMI MAIN] fillPage5 DONE ✅');
    }

    // ==================== PAGE 6: Contact details (address/phone/email) ====================
    // Helper: Tìm select có options bắt đầu bằng "VN" (tỉnh Việt Nam)
    function setSelectVietnamProvince(value) {
        if (!value) return false;
        const selects = document.querySelectorAll('select');
        for (const sel of selects) {
            if (Array.from(sel.options).some(opt => opt.value.startsWith('VN'))) {
                sel.value = value;
                sel.dispatchEvent(new Event('change', {bubbles: true}));
                console.log('[IMMI MAIN] ✅ VN Province set:', value);
                return true;
            }
        }
        return false;
    }

    async function fillPage6(d) {
        console.log('[IMMI MAIN] fillPage6 START — Contact details');

        // 1. Country of residence
        if (d.usual_country) setSelect("Usual country of residence", d.usual_country);

        // 2. Department office (combobox)
        if (d.closest_office) setComboBox("Office", d.closest_office);

        // 3. Residential address
        if (d.residential_country) {
            setSelect("Country", d.residential_country);
            await delay(800); // Wait for State dropdown to load
        }
        setTextInput("Address", d.residential_address1 || "");
        if (d.residential_address2) setTextInput("Address 2", d.residential_address2);
        setTextInput("Suburb / Town", d.residential_suburb || "");

        // State/Province: Vietnam = SELECT (VNSG, VNHN...), others = text input
        if (d.residential_state) {
            if (!setSelectVietnamProvince(d.residential_state)) {
                // Fallback: try as text input (for non-VN countries)
                setTextInput("State or Province", d.residential_state) ||
                setTextInput("State / Province", d.residential_state);
            }
        }

        setTextInput("Postal code", d.residential_postcode || "");

        // 4. Phone numbers
        if (d.phone_home) setTextInput("Home phone", d.phone_home);
        if (d.phone_business) setTextInput("Business phone", d.phone_business);
        if (d.phone_mobile) setTextInput("Mobile / Cell phone", d.phone_mobile);

        // 5. Postal address
        if (d.postal_same_as_residential === "Yes") {
            clickRadioByText("postal address the same", "Yes");
        }

        // 6. Email
        if (d.email) setEmailInput("Email address", d.email);

        console.log('[IMMI MAIN] fillPage6 DONE ✅');
    }

    // ==================== PAGE 9: Planned travel ====================
    async function fillPage9(d) {
        console.log('[IMMI MAIN] fillPage9 START — Planned travel');

        clickRadioByText("Does the applicant intend to enter Australia on more than one occasion?", d.multiple_entry === "Yes" ? "Yes" : "No");
        await delay(800);

        if (d.length_of_stay) setSelect("Length of stay in Australia", d.length_of_stay);
        if (d.planned_arrival) setTextInput("Planned arrival date", d.planned_arrival);
        if (d.planned_departure) setTextInput("Planned final departure date", d.planned_departure);

        clickRadioByText("Is the applicant a parent or step-parent of an Australian citizen", d.is_parent_of_australian === "Yes" ? "Yes" : "No");
        clickRadioByText("Will the applicant undertake a course of study in Australia?", d.undertake_study === "Yes" ? "Yes" : "No");
        clickRadioByText("Will the applicant visit any relatives, friends or contacts while in Australia?", d.visit_relatives === "Yes" ? "Yes" : "No");

        console.log('[IMMI MAIN] fillPage9 DONE ✅');
    }

    // ==================== PAGE 11: Current employment ====================
    async function fillPage11(d) {
        console.log('[IMMI MAIN] fillPage11 START — Employment');

        if (d.employment_status) {
            setSelect("Employment status", d.employment_status);
            await delay(1200);
        }

        if (d.occupation_grouping) {
            setSelect("Occupation grouping", d.occupation_grouping);
            await delay(600);
        }

        if (d.organisation) setTextInput("Organisation", d.organisation);
        if (d.start_date) setTextInput("Start date with current employer", d.start_date);

        // Organisation address
        if (d.org_country) { setSelect("Country", d.org_country); await delay(800); }
        if (d.org_address1) setTextInput("Address", d.org_address1);
        if (d.org_address2) setTextInput("Address 2", d.org_address2);
        if (d.org_suburb) setTextInput("Suburb / Town", d.org_suburb);
        if (d.org_state) setTextInput("State or Province", d.org_state);
        if (d.org_postcode) setTextInput("Postal code", d.org_postcode);

        // Contact person
        if (d.contact_family_name) setTextInput("Family name", d.contact_family_name);
        if (d.contact_given_names) setTextInput("Given names", d.contact_given_names);
        if (d.contact_position) setTextInput("Position", d.contact_position);
        if (d.contact_business_phone) setTextInput("Business phone", d.contact_business_phone);
        if (d.contact_mobile) setTextInput("Mobile / Cell phone", d.contact_mobile);
        if (d.contact_email) setEmailInput("Email address", d.contact_email);

        console.log('[IMMI MAIN] fillPage11 DONE ✅');
    }

    // ==================== MESSAGE LISTENER ====================
    const FILLERS = {
        2: fillPage2,
        3: fillPage3,
        5: fillPage5,
        6: fillPage6,
        9: fillPage9,
        11: fillPage11
    };

    window.addEventListener('message', (event) => {
        if (event.data?.type !== 'IMMI_FILL_REQUEST') return;

        const { page, data } = event.data;
        console.log(`[IMMI Filler] Received fill request for page ${page}`);

        const filler = FILLERS[page];
        if (filler) {
            filler(data).then(() => {
                window.postMessage({type: 'IMMI_FILL_DONE', page, success: true}, '*');
            }).catch(e => {
                console.error('[IMMI Filler] Error:', e);
                window.postMessage({type: 'IMMI_FILL_DONE', page, success: false, error: e.message}, '*');
            });
        } else {
            window.postMessage({type: 'IMMI_FILL_DONE', page, success: false, error: `No filler for page ${page}`}, '*');
        }
    });
})();
