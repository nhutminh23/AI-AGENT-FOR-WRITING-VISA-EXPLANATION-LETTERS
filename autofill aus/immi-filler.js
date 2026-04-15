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

    // Basic passport fields
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

    // ==================== NATIONAL IDENTITY CARD (CCCD) ====================
    const hasNationalID = d.has_national_id === "Yes" 
                       || (d.national_id_number && d.national_id_number.trim() !== "");

    if (hasNationalID) {
        clickRadioByText("Does this applicant have a national identity card?", "Yes");
        await delay(1500);

        // Check if inline CCCD form is showing (has Cancel/Confirm buttons)
        const cccdConfirmBtn = document.querySelector('button[title="Save the current entry"]');
        if (cccdConfirmBtn) {
            // Inline form is showing — use specific IDs to avoid label conflicts with passport
            // Family name (CCCD)
            const cccdFamilyName = document.getElementById('_2a0b0a0a0e0b0a0d1a1a0_input');
            if (cccdFamilyName) {
                cccdFamilyName.value = d.national_id_family_name || d.family_name || '';
                cccdFamilyName.dispatchEvent(new Event('input', {bubbles: true}));
                cccdFamilyName.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Given names (CCCD)
            const cccdGivenNames = document.getElementById('_2a0b0a0a0e0b0a0d2a1a0_input');
            if (cccdGivenNames) {
                cccdGivenNames.value = d.national_id_given_names || d.given_names || '';
                cccdGivenNames.dispatchEvent(new Event('input', {bubbles: true}));
                cccdGivenNames.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Identification number
            const cccdNumber = document.getElementById('_2a0b0a0a0e0b0a0e0b0_input');
            if (cccdNumber) {
                cccdNumber.value = d.national_id_number || '';
                cccdNumber.dispatchEvent(new Event('input', {bubbles: true}));
                cccdNumber.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Country of issue (select)
            const cccdCountry = document.getElementById('_2a0b0a0a0e0b0a0f0b0_input');
            if (cccdCountry) {
                cccdCountry.value = d.national_id_country || 'VIET';
                cccdCountry.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Date of issue (CCCD) — ONLY fill if we have CCCD-specific date, NOT passport date
            const cccdIssueDate = document.getElementById('_2a0b0a0a0e0b0a0h0b0_input');
            if (cccdIssueDate && d.national_id_issue_date) {
                cccdIssueDate.value = d.national_id_issue_date;
                cccdIssueDate.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Date of expiry (CCCD) — ONLY fill if we have CCCD-specific date
            const cccdExpiryDate = document.getElementById('_2a0b0a0a0e0b0a0i0b0_input');
            if (cccdExpiryDate && d.national_id_expiry_date) {
                cccdExpiryDate.value = d.national_id_expiry_date;
                cccdExpiryDate.dispatchEvent(new Event('change', {bubbles: true}));
            }
            console.log('[IMMI MAIN] ✅ National ID (CCCD) inline form filled via IDs');
        } else {
            // Fallback: label-based (when not in inline form)
            setTextInput("Identification number", d.national_id_number || "");
            setSelect("Country of issue", d.national_id_country || "VIET");
            if (d.national_id_issue_date) setTextInput("Date of issue", d.national_id_issue_date);
            if (d.national_id_expiry_date) setTextInput("Date of expiry", d.national_id_expiry_date);
            console.log('[IMMI MAIN] ✅ National ID fields filled via labels (no inline form)');
        }

        console.log('[IMMI MAIN] National ID: Yes');

    } else {
        // === KHÔNG CÓ CCCD (thường là trẻ em) ===
        clickRadioByText("Does this applicant have a national identity card?", "No");
        await delay(1200);   // chờ phần "Give the reason" hiện ra

        // Tự động điền lý do vào textarea "Give the reason..."
        const reasonTextarea = Array.from(document.querySelectorAll('textarea'))
            .find(ta => {
                const label = ta.closest('.wc-row') || ta.parentElement;
                return label && label.textContent.includes('Give the reason the applicant cannot provide details');
            });

        if (reasonTextarea) {
            const reasonText = d.national_id_reason || 
                "The applicant is under the age required to be issued a national identity card (CCCD) in Vietnam. Birth certificate has been provided as an other identity document.";

            reasonTextarea.value = reasonText;
            reasonTextarea.dispatchEvent(new Event('input', { bubbles: true }));
            reasonTextarea.dispatchEvent(new Event('change', { bubbles: true }));

            console.log('[IMMI MAIN] Filled reason for no national ID: ' + reasonText.substring(0, 80) + '...');
        } else {
            console.warn('[IMMI MAIN] Could not find "Give the reason" textarea');
        }

        sendInfo(`🔹 Không có CCCD → Chọn "No"\n📝 Đã điền lý do: "The applicant is a minor..."`);
    }

    // ==================== OTHER IDENTITY DOCUMENTS ====================
    // Buộc Yes nếu không có CCCD
    const shouldHaveOtherID = !hasNationalID || d.other_identity_docs === "Yes";

    if (shouldHaveOtherID) {
        clickRadioByText("Does this applicant have other identity documents?", "Yes");
        await delay(1500);

        // Auto-fill Birth Certificate inline form using direct IDs
        const otherDocConfirmBtn = document.getElementById('_2a0b0a0a0e0e3d');
        if (otherDocConfirmBtn) {
            // Family name
            const otherFamilyName = document.getElementById('_2a0b0a0a0e0e0a0e1a1a0_input');
            if (otherFamilyName) {
                otherFamilyName.value = d.family_name || '';
                otherFamilyName.dispatchEvent(new Event('input', {bubbles: true}));
                otherFamilyName.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Given names
            const otherGivenNames = document.getElementById('_2a0b0a0a0e0e0a0e2a1a0_input');
            if (otherGivenNames) {
                otherGivenNames.value = d.given_names || '';
                otherGivenNames.dispatchEvent(new Event('input', {bubbles: true}));
                otherGivenNames.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Type of document → Birth certificate
            const otherDocType = document.getElementById('_2a0b0a0a0e0e0a0f0b0_input');
            if (otherDocType) {
                otherDocType.value = 'BRT_CRT';
                otherDocType.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Identification number (số giấy khai sinh hoặc mặc định)
            const otherIdNumber = document.getElementById('_2a0b0a0a0e0e0a0g0b0_input');
            if (otherIdNumber) {
                const birthCertNumber = d.other_id_number || d.birth_certificate_number || 'Birth Certificate';
                otherIdNumber.value = birthCertNumber;
                otherIdNumber.dispatchEvent(new Event('input', {bubbles: true}));
                otherIdNumber.dispatchEvent(new Event('change', {bubbles: true}));
            }
            // Country of issue → VIETNAM
            const otherCountry = document.getElementById('_2a0b0a0a0e0e0a0h0b0_input');
            if (otherCountry) {
                otherCountry.value = 'VIET';
                otherCountry.dispatchEvent(new Event('change', {bubbles: true}));
            }

            await delay(500);

            // Click Confirm to save the entry
            otherDocConfirmBtn.click();
            console.log('[IMMI MAIN] ✅ Other ID: Birth Certificate filled & Confirmed');
            sendInfo(`📋 Đã tự động điền Birth Certificate:\n- Họ: ${d.family_name}\n- Tên: ${d.given_names}\n- Loại: Birth certificate\n- Quốc gia: VIETNAM\n✅ Đã nhấn Confirm`);

        } else {
            // Fallback: form chưa hiện, nhắc user thủ công
            sendInfo(`📋 Đã chọn "Yes" cho Other identity documents.\n⚠️ Không tìm thấy inline form. Vui lòng nhấn Add và thêm Birth Certificate thủ công.`);
            console.warn('[IMMI MAIN] ⚠️ Other ID inline form not found');
        }
    } else {
        clickRadioByText("Does this applicant have other identity documents?", "No");
    }

    // ==================== Các trường còn lại ====================
    clickRadioByText("Is the applicant a Pacific-Australia Card holder?", 
        d.pacific_australia_card === "Yes" ? "Yes" : "No");

    setTextInput("Town / City", d.place_of_birth_city || "");
    if (d.place_of_birth_state) setTextInput("State / Province", d.place_of_birth_state);
    setSelect("Country of birth", d.place_of_birth_country || "VIET");
    if (d.relationship_status) setSelect("Relationship status", d.relationship_status);

    clickRadioByText("Is this applicant currently, or have they ever been known by any other names?", 
        d.other_names_used === "Yes" ? "Yes" : "No");
    clickRadioByText("Is this applicant a citizen of the selected country of passport", 
        d.citizen_of_passport_country === "Yes" ? "Yes" : "No");
    clickRadioByText("Is this applicant a citizen of any other country?", 
        d.citizen_of_other_country === "Yes" ? "Yes" : "No");
    clickRadioByText("Has this applicant previously travelled to Australia?", 
        d.previously_travelled_to_australia === "Yes" ? "Yes" : "No");
    clickRadioByText("Has this applicant previously applied for a visa to Australia?", 
        d.previously_applied_visa === "Yes" ? "Yes" : "No");
    clickRadioByText("Does this applicant have an Australian visa grant number?", 
        d.has_grant_number === "Yes" ? "Yes" : "No");
    if (d.has_grant_number === "Yes" && d.grant_number) {
        await delay(800);
        const grantInput = Array.from(document.querySelectorAll('input[type="text"]'))
            .find(inp => {
                const label = document.querySelector(`label[for="${inp.id}"]`);
                return label && label.textContent.includes('Australian visa grant number');
            });
        if (grantInput) {
            grantInput.value = d.grant_number;
            grantInput.dispatchEvent(new Event('input', {bubbles: true}));
            grantInput.dispatchEvent(new Event('change', {bubbles: true}));
            console.log('[IMMI MAIN] ✅ Filled grant_number:', d.grant_number);
        } else {
            console.warn('[IMMI MAIN] ❌ Could not find grant number input');
        }
    }
    clickRadioByText("Does this applicant have any other passports or documents for travel?", 
        d.other_passports === "Yes" ? "Yes" : "No");
    clickRadioByText("Has this applicant undertaken a health examination for an Australian visa in the last 12 months?", 
        d.health_examination === "Yes" ? "Yes" : "No");

    console.log('[IMMI MAIN] fillPage3 DONE ✅');
}

    // ==================== HELPER: Read already-added members from table ====================
    function getAlreadyAddedFromTable() {
        const added = [];
        const tables = document.querySelectorAll('table');
        for (const table of tables) {
            const rows = table.querySelectorAll('tr');
            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {
                    const familyName = cells[0]?.textContent?.trim().toUpperCase() || '';
                    const givenNames = cells[1]?.textContent?.trim().toUpperCase() || '';
                    if (familyName && givenNames && familyName !== 'FAMILY NAME') {
                        added.push({ family_name: familyName, given_names: givenNames });
                    }
                }
            }
        }
        return added;
    }

    // Read entries from a SPECIFIC table by index (0-based)
    // Minor page 5: table[0] = guardian table, table[1] = companion table
    function getAddedFromTableByIndex(tableIndex) {
        const added = [];
        const tables = document.querySelectorAll('table');
        if (tableIndex >= tables.length) return added;
        const table = tables[tableIndex];
        const rows = table.querySelectorAll('tr');
        for (const row of rows) {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                const familyName = cells[0]?.textContent?.trim().toUpperCase() || '';
                const givenNames = cells[1]?.textContent?.trim().toUpperCase() || '';
                if (familyName && givenNames && familyName !== 'FAMILY NAME') {
                    added.push({ family_name: familyName, given_names: givenNames });
                }
            }
        }
        return added;
    }

    function saveAddedToStorage(pageKey, added) {
        try { sessionStorage.setItem(`immi_added_${pageKey}`, JSON.stringify(added)); }
        catch(e) { console.warn('[IMMI] sessionStorage error:', e); }
    }

    function loadAddedFromStorage(pageKey) {
        try {
            const raw = sessionStorage.getItem(`immi_added_${pageKey}`);
            return raw ? JSON.parse(raw) : [];
        } catch(e) { return []; }
    }

    function findNextUnadded(members, alreadyAdded) {
        for (let i = 0; i < members.length; i++) {
            const m = members[i];
            const mFamily = (m.family_name || '').toUpperCase();
            const mGiven = (m.given_names || '').toUpperCase();
            const isAlreadyAdded = alreadyAdded.some(a =>
                a.family_name === mFamily && a.given_names === mGiven
            );
            if (!isAlreadyAdded) {
                return { index: i, member: m };
            }
        }
        return null;
    }

    function sendInfo(msg) {
        window.postMessage({ type: 'IMMI_FILL_INFO', message: msg }, '*');
        console.log(`[IMMI MAIN] INFO: ${msg}`);
    }

    // ==================== PAGE 5: Travelling companion ====================
    async function fillPage5(d) {
        console.log('[IMMI MAIN] fillPage5 START — Travelling companion');

        const hasCompanions = d.companions && d.companions.length > 0;
        const isMinor = d.is_minor === "Yes";
        const STORAGE_KEY = 'page5';
        const GUARDIAN_STORAGE_KEY = 'page5_guardians';

        // Check if the inline companion form is already showing (user clicked Add)
        const hasConfirmBtn = !!document.querySelector('button[title="Save the current entry"]');
        const hasRelationshipLabel = Array.from(document.querySelectorAll('label.wc-label'))
            .some(l => l.textContent.includes('Relationship to the applicant'));
        const inlineForm = hasConfirmBtn && hasRelationshipLabel;

        // ==================== MINOR SECTION (under 18) ====================
        if (isMinor && !inlineForm) {
            console.log('[IMMI MAIN] Minor detected — handling parent/guardian section');

            // Q1: "Is the applicant travelling with a parent or legal guardian?"
            const travelWithParentRadioName = '_2a0b0a0a0e0a0a4a3b1b0';
            if (d.travelling_with_parent === "Yes") {
                const yesR = document.querySelector(`input[type="radio"][name="${travelWithParentRadioName}"][value="1"]`);
                if (yesR && !yesR.checked) yesR.click();
                console.log('[IMMI MAIN] ✅ Travelling with parent: Yes');
            } else if (d.travelling_with_parent === "No") {
                const noR = document.querySelector(`input[type="radio"][name="${travelWithParentRadioName}"][value="2"]`);
                if (noR && !noR.checked) noR.click();
                await delay(800);

                // Reason not with parent
                if (d.not_with_parent_reason) {
                    const reasonRadioName = '_2a0b0a0a0e0a0a4a3c1b0';
                    const reasonR = document.querySelector(`input[type="radio"][name="${reasonRadioName}"][value="${d.not_with_parent_reason}"]`);
                    if (reasonR) {
                        reasonR.click();
                        console.log('[IMMI MAIN] ✅ Not-with-parent reason:', d.not_with_parent_reason);
                        await delay(600);
                    }

                    // "Give details" textarea (appears for reason "5" = Other)
                    if (d.not_with_parent_reason === "5" && d.not_with_parent_details) {
                        const detailsTA = document.getElementById('_2a0b0a0a0e0a0a4a3d0b0_input');
                        if (detailsTA) {
                            detailsTA.value = d.not_with_parent_details;
                            detailsTA.dispatchEvent(new Event('input', {bubbles: true}));
                            detailsTA.dispatchEvent(new Event('change', {bubbles: true}));
                            console.log('[IMMI MAIN] ✅ Filled not-with-parent details');
                        }
                    }
                }
                console.log('[IMMI MAIN] ✅ Travelling with parent: No');
            }
            await delay(600);

            // Parents/guardians table — check if any need to be added
            const parents = d.parents_guardians || [];
            if (parents.length > 0) {
                // Read ONLY the FIRST table (guardian table) — table[0]
                const guardianTableAdded = getAddedFromTableByIndex(0);
                saveAddedToStorage(GUARDIAN_STORAGE_KEY, guardianTableAdded);
                const remaining = parents.length - guardianTableAdded.length;
                if (remaining > 0) {
                    const nextP = findNextUnadded(parents, guardianTableAdded);
                    const name = nextP ? `${nextP.member.family_name} ${nextP.member.given_names}` : '';
                    sendInfo(`👶 Minor detected! Còn ${remaining} cha/mẹ cần thêm vào bảng Guardian.\n👉 Ấn [Add] ở bảng "parents or legal guardians" → [Auto-Fill] để điền: ${name}`);
                } else {
                    sendInfo(`✅ Tất cả ${parents.length} cha/mẹ/guardian đã được thêm.`);
                }
            }
        }

        // ==================== MINOR: Fill guardian inline form ====================
        // Detect "Responsible person details" form (guardian form has different IDs than companion form)
        const isGuardianForm = !!document.getElementById('_2a0b0a0a0e0be0a0c0b0a_input') ||
            Array.from(document.querySelectorAll('h2.wc-heading')).some(h => h.textContent.includes('Responsible person details'));

        if (isMinor && isGuardianForm) {
            const parents = d.parents_guardians || [];
            if (parents.length > 0) {
                const guardianAdded = loadAddedFromStorage(GUARDIAN_STORAGE_KEY);
                const nextGuardian = findNextUnadded(parents, guardianAdded);

                if (nextGuardian) {
                    const g = nextGuardian.member;
                    const fillingNum = guardianAdded.length + 1;
                    sendInfo(`📝 Đang điền Guardian ${fillingNum}/${parents.length}: ${g.family_name} ${g.given_names}`);

                    // Helper: set value by element ID
                    function setById(id, value) {
                        if (!value) return false;
                        const el = document.getElementById(id);
                        if (!el) { console.log(`[IMMI P5] ❌ ID not found: ${id}`); return false; }
                        el.value = value;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        console.log(`[IMMI P5] ✅ ${id} = "${value}"`);
                        return true;
                    }

                    // 1. Relationship (select: 2=Parent, 14=Step Parent, 87=Legal guardian)
                    setById('_2a0b0a0a0e0be0a0c0b0a_input', g.relationship || '2');
                    await delay(600);

                    // 2. Family name
                    setById('_2a0b0a0a0e0be0a0g1b0b0a_input', g.family_name || '');
                    // 3. Given names
                    setById('_2a0b0a0a0e0be0a0g1c0b0a_input', g.given_names || '');
                    // 4. Sex (radio)
                    if (g.sex) {
                        const sexRadio = document.querySelector(`input[type="radio"][name="_2a0b0a0a0e0be0a0g2a1a"][value="${g.sex}"]`);
                        if (sexRadio) sexRadio.click();
                    }
                    // 5. Date of birth
                    setById('_2a0b0a0a0e0be0a0g3a1a_input', g.date_of_birth || '');

                    // 6. Passport number
                    setById('_2a0b0a0a0e0be0a0h1a1a_input', g.passport_number || '');
                    // 7. Country of passport
                    setById('_2a0b0a0a0e0be0a0h2a1a_input', g.passport_country || 'VNM');
                    // 8. Nationality of passport holder
                    setById('_2a0b0a0a0e0be0a0h3a1a_input', g.passport_nationality || 'VNM');
                    // 9. Date of issue (passport)
                    if (g.passport_issue_date) setById('_2a0b0a0a0e0be0a0h4a1a_input', g.passport_issue_date);
                    // 10. Date of expiry (passport)
                    if (g.passport_expiry_date) setById('_2a0b0a0a0e0be0a0h5a1a_input', g.passport_expiry_date);
                    // 11. Place of issue / issuing authority
                    setById('_2a0b0a0a0e0be0a0h7a1a_input', g.passport_issuing_authority || 'IMMIGRATION DEPARTMENT OF VIETNAM');

                    await delay(400);

                    // 12. Related application: "Has this responsible person submitted a Visitor visa application?"
                    if (g.has_submitted_visa === "Yes") {
                        const yesVisaR = document.querySelector('input[type="radio"][name="_2a0b0a0a0e0be0a0j1b0"][value="1"]');
                        if (yesVisaR) yesVisaR.click();
                        await delay(800);

                        // Reference number type
                        if (g.ref_number_type) {
                            setById('_2a0b0a0a0e0be0a0bc0b0_input', g.ref_number_type);
                            await delay(600);
                        }

                        // Fill the appropriate reference number field based on type
                        if (g.ref_number) {
                            if (g.ref_number_type === '1') {
                                // TRN
                                setById('_2a0b0a0a0e0be0a0bd0b0_input', g.ref_number);
                            } else if (g.ref_number_type === '10') {
                                // Application ID
                                setById('_2a0b0a0a0e0be0a0be0b0_input', g.ref_number);
                            } else if (g.ref_number_type === '3') {
                                // Visa grant number
                                setById('_2a0b0a0a0e0be0a0bf0b0a_input', g.ref_number);
                            }
                        }
                        console.log('[IMMI P5] ✅ Related application: Yes + ref filled');
                    } else {
                        const noVisaR = document.querySelector('input[type="radio"][name="_2a0b0a0a0e0be0a0j1b0"][value="2"]');
                        if (noVisaR) noVisaR.click();
                        console.log('[IMMI P5] ✅ Related application: No');
                    }

                    const remaining = parents.length - fillingNum;
                    if (remaining > 0) {
                        sendInfo(`✅ Đã điền Guardian ${g.family_name} ${g.given_names} (${fillingNum}/${parents.length})\n📌 Bao gồm passport + related application\n📌 Còn ${remaining} guardian. Ấn [Confirm] → [Add] → [Auto-Fill]`);
                    } else {
                        sendInfo(`✅ Đã điền Guardian ${g.family_name} ${g.given_names} — hoàn tất!\n📌 Bao gồm passport + related application\n👉 Ấn [Confirm] để lưu.`);
                    }
                    console.log('[IMMI MAIN] fillPage5 guardian (full passport) DONE ✅');
                    return;
                }
            }
            // If all guardians done, fall through to companion logic below
        }

        // ==================== COMPANION SECTION (shared for adult & minor) ====================
        if (!inlineForm) {
            // Phase 1: Click Yes/No + read table + save to storage
            // For minor: companion table is table[1] (2nd table), for adult: read all tables
            const tableAdded = isMinor ? getAddedFromTableByIndex(1) : getAlreadyAddedFromTable();
            saveAddedToStorage(STORAGE_KEY, tableAdded);

            const yesRadio = document.querySelector('input[type="radio"][name="_2a0b0a0a0e0a0a4a4b1a0"][value="1"]');
            const noRadio = document.querySelector('input[type="radio"][name="_2a0b0a0a0e0a0a4a4b1a0"][value="2"]');

            if (hasCompanions) {
                if (yesRadio) { yesRadio.click(); }
                const remaining = hasCompanions ? d.companions.length - tableAdded.length : 0;
                if (remaining > 0) {
                    const nextPerson = findNextUnadded(d.companions, tableAdded);
                    const name = nextPerson ? `${nextPerson.member.family_name} ${nextPerson.member.given_names}` : '';
                    sendInfo(`✅ Đã chọn Yes. Còn ${remaining} người cần thêm.\n👉 Ấn [Add] rồi [Auto-Fill] để điền: ${name}`);
                } else {
                    sendInfo(`✅ Tất cả ${d.companions.length} người đã được thêm!`);
                }
            } else {
                if (noRadio) { noRadio.click(); }
                sendInfo('✅ Không có người đi cùng → No');
            }
            return;
        }

        // Phase 2: Fill the NEXT unadded companion (read from storage)
        // Detect companion form specifically (heading "Travelling companion" or ID prefix _2a0b0a0a0e0bf)
        const isCompanionForm = !!document.getElementById('_2a0b0a0a0e0bf0a0c0b0a_input') ||
            Array.from(document.querySelectorAll('h2.wc-heading')).some(h => h.textContent.includes('Travelling companion'));

        if (!hasCompanions || !isCompanionForm) return;

        const alreadyAdded = loadAddedFromStorage(STORAGE_KEY);
        const next = findNextUnadded(d.companions, alreadyAdded);

        if (!next) {
            sendInfo(`⚠️ Tất cả ${d.companions.length} người đã được thêm! Không cần thêm nữa.`);
            return;
        }

        const comp = next.member;
        const fillingNum = alreadyAdded.length + 1;
        sendInfo(`📝 Đang điền companion ${fillingNum}/${d.companions.length}: ${comp.family_name} ${comp.given_names}`);

        // Try direct IDs first (minor page 5 companion form), fallback to label-based
        const compRelSelect = document.getElementById('_2a0b0a0a0e0bf0a0c0b0a_input');
        if (compRelSelect) {
            // Direct ID approach (minor page 5)
            compRelSelect.value = comp.relationship || '33';
            compRelSelect.dispatchEvent(new Event('change', {bubbles: true}));
            await delay(600);

            const compFamilyName = document.getElementById('_2a0b0a0a0e0bf0a0d1b0b0a_input');
            if (compFamilyName) { compFamilyName.value = comp.family_name || ''; compFamilyName.dispatchEvent(new Event('input', {bubbles: true})); compFamilyName.dispatchEvent(new Event('change', {bubbles: true})); }

            const compGivenNames = document.getElementById('_2a0b0a0a0e0bf0a0d1c0b0a_input');
            if (compGivenNames) { compGivenNames.value = comp.given_names || ''; compGivenNames.dispatchEvent(new Event('input', {bubbles: true})); compGivenNames.dispatchEvent(new Event('change', {bubbles: true})); }

            if (comp.sex) {
                const sexRadio = document.querySelector(`input[type="radio"][name="_2a0b0a0a0e0bf0a0d2a1a"][value="${comp.sex}"]`);
                if (sexRadio) sexRadio.click();
            }

            const compDob = document.getElementById('_2a0b0a0a0e0bf0a0d3a1a_input');
            if (compDob) { compDob.value = comp.date_of_birth || ''; compDob.dispatchEvent(new Event('input', {bubbles: true})); compDob.dispatchEvent(new Event('change', {bubbles: true})); }

            console.log('[IMMI P5] ✅ Companion filled via direct IDs (_2a0b0a0a0e0bf)');
        } else {
            // Fallback: label-based (adult page 5 or different form version)
            setSelect("Relationship to the applicant", comp.relationship || "33");
            await delay(600);
            setTextInput("Family name", comp.family_name || "");
            setTextInput("Given names", comp.given_names || "");
            if (comp.sex) clickRadioInFieldset("Sex", comp.sex);
            setTextInput("Date of birth", comp.date_of_birth || "");
            console.log('[IMMI P5] ✅ Companion filled via labels (fallback)');
        }
        await delay(300);

        const remaining = d.companions.length - fillingNum;
        if (remaining > 0) {
            sendInfo(`✅ Đã điền ${comp.family_name} ${comp.given_names} (${fillingNum}/${d.companions.length})\n📌 Còn ${remaining} người. Ấn [Confirm] → [Add] → [Auto-Fill]`);
        } else {
            sendInfo(`✅ Đã điền ${comp.family_name} ${comp.given_names} — người cuối cùng! Ấn [Confirm] để hoàn tất.`);
        }
        console.log('[IMMI MAIN] fillPage5 DONE ✅');
    }

    // ==================== PAGE 8: Non-accompanying family members ====================
    async function fillPage8(d) {
        console.log('[IMMI MAIN] fillPage8 START — Non-accompanying family members');

        const hasMembers = d.non_accompanying_members && d.non_accompanying_members.length > 0;
        const STORAGE_KEY = 'page8';

        // Check if the inline form is already showing (user clicked Add)
        const inlineForm = Array.from(document.querySelectorAll('label.wc-label'))
            .some(l => l.textContent.includes('Relationship to the applicant'));

        if (!inlineForm) {
            // Phase 1: Click Yes/No + read table + save to storage
            const tableAdded = getAlreadyAddedFromTable();
            saveAddedToStorage(STORAGE_KEY, tableAdded);

            const yesRadio = document.querySelector('input[type="radio"][name="_2a0b0a0a0e0a0a7a2b1a0"][value="1"]');
            const noRadio = document.querySelector('input[type="radio"][name="_2a0b0a0a0e0a0a7a2b1a0"][value="2"]');

            if (hasMembers) {
                if (yesRadio) { yesRadio.click(); }
                const remaining = d.non_accompanying_members.length - tableAdded.length;
                if (remaining > 0) {
                    const nextPerson = findNextUnadded(d.non_accompanying_members, tableAdded);
                    const name = nextPerson ? `${nextPerson.member.family_name} ${nextPerson.member.given_names}` : '';
                    sendInfo(`✅ Đã chọn Yes. Còn ${remaining} người cần thêm.\n👉 Ấn [Add] rồi [Auto-Fill] để điền: ${name}`);
                } else {
                    sendInfo(`✅ Tất cả ${d.non_accompanying_members.length} người đã được thêm!`);
                }
            } else {
                if (noRadio) { noRadio.click(); }
                sendInfo('✅ Không có thành viên không đi cùng → No');
            }
            return;
        }

        // Phase 2: Fill the NEXT unadded member (read from storage)
        if (!hasMembers) return;

        const alreadyAdded = loadAddedFromStorage(STORAGE_KEY);
        const next = findNextUnadded(d.non_accompanying_members, alreadyAdded);

        if (!next) {
            sendInfo(`⚠️ Tất cả ${d.non_accompanying_members.length} người đã được thêm! Không cần thêm nữa.`);
            return;
        }

        const m = next.member;
        const fillingNum = alreadyAdded.length + 1;
        sendInfo(`📝 Đang điền người ${fillingNum}/${d.non_accompanying_members.length}: ${m.family_name} ${m.given_names}`);

        setSelect("Relationship to the applicant", m.relationship || "3");
        await delay(600);
        setTextInput("Family name", m.family_name || "");
        setTextInput("Given names", m.given_names || "");
        if (m.sex) clickRadioInFieldset("Sex", m.sex);
        setTextInput("Date of birth", m.date_of_birth || "");
        if (m.country_of_birth) setSelect("Country of birth", m.country_of_birth);
        await delay(300);

        const remaining = d.non_accompanying_members.length - fillingNum;
        if (remaining > 0) {
            sendInfo(`✅ Đã điền ${m.family_name} ${m.given_names} (${fillingNum}/${d.non_accompanying_members.length})\n📌 Còn ${remaining} người. Ấn [Confirm] → [Add] → [Auto-Fill]`);
        } else {
            sendInfo(`✅ Đã điền ${m.family_name} ${m.given_names} — người cuối cùng! Ấn [Confirm] để hoàn tất.`);
        }
        console.log('[IMMI MAIN] fillPage8 DONE ✅');
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

        // Helper: set value by element ID
        function setById(id, value) {
            if (!value) return false;
            const el = document.getElementById(id);
            if (!el) { console.log(`[IMMI MAIN] ❌ ID not found: ${id}`); return false; }
            el.value = value;
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('input', {bubbles: true}));
            console.log(`[IMMI MAIN] ✅ ${id} = "${value}"`);
            return true;
        }

        // 1. Country of residence
        setById('_2a0b0a0a0e0a0a5a2c0b0a_input', d.usual_country || 'VIET');
        await delay(500);

        // 2. Department office (combobox — type text then click suggestion)
        if (d.closest_office) {
            const officeInput = document.getElementById('_2a0b0a0a0e0a0a5a3e0b0a_input');
            if (officeInput) {
                officeInput.value = d.closest_office;
                officeInput.dispatchEvent(new Event('input', {bubbles: true}));
                officeInput.dispatchEvent(new Event('change', {bubbles: true}));
                await delay(500);
                const suggestion = document.querySelector(`span[data-wc-value="${d.closest_office}"]`);
                if (suggestion) suggestion.click();
                console.log(`[IMMI MAIN] ✅ Office = "${d.closest_office}"`);
            }
        }

        // 3. Residential address — Country
        // ⚠️ WComponents needs a FULL event chain to trigger State field transformation
        if (d.residential_country) {
            const countrySelect = document.getElementById('_2a0b0a0a0e0a0a5a4d0b0_input');
            if (countrySelect) {
                // Simulate realistic user interaction for WComponents
                countrySelect.focus();
                countrySelect.dispatchEvent(new Event('focus', {bubbles: true}));
                await delay(100);
                
                countrySelect.value = d.residential_country;
                
                // Fire full event chain that WComponents expects
                countrySelect.dispatchEvent(new Event('change', {bubbles: true}));
                countrySelect.dispatchEvent(new Event('input', {bubbles: true}));
                countrySelect.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                countrySelect.blur();
                countrySelect.dispatchEvent(new Event('blur', {bubbles: true}));
                
                console.log(`[IMMI MAIN] ✅ Residential Country = "${d.residential_country}"`);
                
                // Wait for WComponents to process the country change and transform State field
                // This is critical — the framework needs time to AJAX-load province list
                await delay(2500);
                
                // Double-check: if State selectbox still hasn't appeared, trigger change again
                const stateSelectCheck = document.getElementById('_2a0b0a0a0e0a0a5a4h2b0b0_input');
                if (!stateSelectCheck || stateSelectCheck.closest('[hidden]')) {
                    console.log('[IMMI MAIN] ⏳ State selectbox not ready, re-triggering country change...');
                    countrySelect.dispatchEvent(new Event('change', {bubbles: true}));
                    await delay(2500);
                }
            }
        }

        // Address line 1 (max 40)
        setById('_2a0b0a0a0e0a0a5a4e0b0a_input', d.residential_address1 || '');

        // Address line 2 (max 40)
        if (d.residential_address2) {
            setById('_2a0b0a0a0e0a0a5a4f0b0_input', d.residential_address2);
        }

        // Suburb / Town (international section)
        setById('_2a0b0a0a0e0a0a5a4h1a1a_input', d.residential_suburb || '');

        // State / Province — wait for the correct field type to appear
        if (d.residential_state) {
            let stateSet = false;

            // Strategy 1: Try VN province selectbox (most common case for VIET)
            const vnDrop = document.getElementById('_2a0b0a0a0e0a0a5a4h2b0b0_input');
            if (vnDrop && !vnDrop.closest('[hidden]')) {
                // This is the selectbox with VN provinces (AN GIANG, BA RIA-VUNG TAU, etc.)
                const opts = Array.from(vnDrop.options);
                // Try exact value match first (e.g., "VN18" for NINH BINH)
                const exactMatch = opts.find(o => o.value === d.residential_state);
                // Try text match (e.g., "NINH BINH")
                const textMatch = opts.find(o => o.textContent.trim().toUpperCase().includes(d.residential_state.toUpperCase()));

                if (exactMatch) {
                    vnDrop.value = exactMatch.value;
                } else if (textMatch) {
                    vnDrop.value = textMatch.value;
                } else {
                    vnDrop.value = d.residential_state;
                }
                vnDrop.dispatchEvent(new Event('change', {bubbles: true}));
                stateSet = true;
                console.log(`[IMMI MAIN] ✅ VN Province (selectbox) = "${d.residential_state}"`);
            }

            // Strategy 2: Generic State labels (fallback for non-VN countries)
            if (!stateSet) {
                const stateLabel = Array.from(document.querySelectorAll('label.wc-label'))
                    .find(l => l.textContent.includes('State or Province') || l.textContent.includes('State / Province'));
                if (stateLabel) {
                    const row = stateLabel.closest('.wc-row') || stateLabel.closest('.wc-panel');
                    const sel = row?.querySelector('select:not([hidden])');
                    const txtInp = row?.querySelector('input[type="text"]:not([hidden])');

                    if (sel && !sel.closest('[hidden]')) {
                        const opts = Array.from(sel.options);
                        const exactMatch = opts.find(o => o.value === d.residential_state);
                        const textMatch = opts.find(o => o.textContent.trim().toUpperCase().includes(d.residential_state.toUpperCase()));
                        sel.value = exactMatch ? exactMatch.value : (textMatch ? textMatch.value : d.residential_state);
                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                        stateSet = true;
                        console.log(`[IMMI MAIN] ✅ State/Province (select by label) = "${d.residential_state}"`);
                    } else if (txtInp && !txtInp.closest('[hidden]')) {
                        txtInp.value = d.residential_state;
                        txtInp.dispatchEvent(new Event('input', {bubbles: true}));
                        txtInp.dispatchEvent(new Event('change', {bubbles: true}));
                        stateSet = true;
                        console.log(`[IMMI MAIN] ✅ State/Province (text by label) = "${d.residential_state}"`);
                    }
                }
            }

            // Strategy 3: Absolute fallback — text input by ID
            if (!stateSet) {
                setById('_2a0b0a0a0e0a0a5a4h2a0b0_input', d.residential_state);
                console.log(`[IMMI MAIN] ✅ State/Province (text ID fallback) = "${d.residential_state}"`);
            }
        }

        // Postal code (international)
        setById('_2a0b0a0a0e0a0a5a4h3a1a_input', d.residential_postcode || '');

        // 4. Phone numbers
        setById('_2a0b0a0a0e0a0a5a5d0b0_input', d.phone_home || '');
        setById('_2a0b0a0a0e0a0a5a5e0b0_input', d.phone_business || '');
        setById('_2a0b0a0a0e0a0a5a5f0b0_input', d.phone_mobile || '');

        // 5. Postal address same as residential? → default Yes
        const postalRadioVal = d.postal_same_as_residential === 'No' ? '2' : '1';
        const postalRadio = document.querySelector(`input[type="radio"][name="_2a0b0a0a0e0a0a5a6c1b0a"][value="${postalRadioVal}"]`);
        if (postalRadio && !postalRadio.checked) {
            postalRadio.click();
            console.log(`[IMMI MAIN] ✅ Postal same = ${postalRadioVal === '1' ? 'Yes' : 'No'}`);
        }

        // 6. Email (may be on this page in some form variants)
        if (d.email) setEmailInput('Email address', d.email);

        console.log('[IMMI MAIN] fillPage6 DONE ✅');
    }

    // ==================== PAGE 9: Planned travel ====================
    async function fillPage9(d) {
        console.log('[IMMI MAIN] fillPage9 START — Planned travel');

        // Check if the Contact in Australia inline form is already showing
        const contactInlineForm = Array.from(document.querySelectorAll('label.wc-label'))
            .some(l => l.textContent.includes('Relationship to the applicant'));

        if (contactInlineForm && d.contact_in_australia) {
            // Phase 2: Fill Contact in Australia details
            const c = d.contact_in_australia;
            console.log('[IMMI MAIN] fillPage9 Phase 2 — Contact in Australia');

            setSelect("Relationship to the applicant", c.relationship || "33");
            await delay(600);
            setTextInput("Family name", c.family_name || "");
            setTextInput("Given names", c.given_names || "");
            if (c.sex) clickRadioInFieldset("Sex", c.sex);
            setTextInput("Date of birth", c.date_of_birth || "");

            // Address in Australia
            if (c.address1) setTextInput("Address", c.address1);
            if (c.address2) setTextInput("Address 2", c.address2);
            if (c.suburb) setTextInput("Suburb / Town", c.suburb);
            if (c.state) setSelect("State / Territory", c.state);
            if (c.postcode) setTextInput("Postcode", c.postcode);

            // Phone & Email
            if (c.phone_home) setTextInput("Home phone", c.phone_home);
            if (c.phone_business) setTextInput("Business phone", c.phone_business);
            if (c.phone_mobile) setTextInput("Mobile / Cell phone", c.phone_mobile);
            if (c.email) setEmailInput("Email address", c.email);

            // Residency status
            if (c.residency_status) setSelect("Australian residency status", c.residency_status);

            console.log('[IMMI MAIN] fillPage9 Phase 2 DONE ✅ — Contact in Australia filled');
            return;
        }

        // Phase 1: Fill main planned travel fields
        clickRadioByText("Does the applicant intend to enter Australia on more than one occasion?", d.multiple_entry === "Yes" ? "Yes" : "No");
        await delay(800);

        if (d.length_of_stay) setSelect("Length of stay in Australia", d.length_of_stay);
        if (d.planned_arrival) setTextInput("Planned arrival date", d.planned_arrival);
        if (d.planned_departure) setTextInput("Planned final departure date", d.planned_departure);

        // "Does the applicant know the dates of entry for each occasion after first entry?"
        // This field appears when applicant has previous Aus visa or selected multiple entry
        if (d.know_dates_of_entry !== undefined) {
            clickRadioByText("Does the applicant know the dates of entry for each occasion after first entry to Australia?",
                d.know_dates_of_entry === "Yes" ? "Yes" : "No");
            await delay(800);

            // If "No" → fill the "Give reason" textarea
            if (d.know_dates_of_entry === "No" && d.dates_of_entry_reason) {
                const reasonTA = Array.from(document.querySelectorAll('textarea'))
                    .find(t => {
                        const label = document.querySelector(`label[for="${t.id}"]`);
                        return label && label.textContent.includes('Give reason');
                    });
                if (reasonTA) {
                    reasonTA.value = d.dates_of_entry_reason;
                    reasonTA.dispatchEvent(new Event('input', {bubbles: true}));
                    reasonTA.dispatchEvent(new Event('change', {bubbles: true}));
                    console.log('[IMMI MAIN] ✅ Filled dates_of_entry_reason');
                } else {
                    console.warn('[IMMI MAIN] ❌ Could not find "Give reason" textarea');
                }
            }
        }

        clickRadioByText("Is the applicant a parent or step-parent of an Australian citizen", d.is_parent_of_australian === "Yes" ? "Yes" : "No");
        clickRadioByText("Will the applicant undertake a course of study in Australia?", d.undertake_study === "Yes" ? "Yes" : "No");
        clickRadioByText("Will the applicant visit any relatives, friends or contacts while in Australia?", d.visit_relatives === "Yes" ? "Yes" : "No");

        if (d.visit_relatives === "Yes" && d.contact_in_australia) {
            console.log('[IMMI MAIN] fillPage9 Phase 1 DONE — click Add rồi ấn điền lại để fill Contact');
        } else {
            console.log('[IMMI MAIN] fillPage9 DONE ✅');
        }
    }

    // ==================== PAGE 11: Current employment ====================
    async function fillPage11(d) {
        console.log('[IMMI MAIN] fillPage11 START — Employment');

        if (d.employment_status) {
            setSelect("Employment status", d.employment_status);
            await delay(1200);
        }

        // Fields for Employed (1) and Self-employed (2)
        if (d.employment_status === "1" || d.employment_status === "2") {
            if (d.occupation_grouping) {
                setSelect("Occupation grouping", d.occupation_grouping);
                await delay(600);
            }
            if (d.occupation) setTextInput("Occupation", d.occupation);
            if (d.organisation) setTextInput("Organisation", d.organisation);
            if (d.start_date) setTextInput("Start date with current employer", d.start_date);
        }

        // Self-employed (2) — extra organisation details
        if (d.employment_status === "2") {
            await delay(600);
            if (d.legal_registered_name) setTextInput("Legal registered name", d.legal_registered_name);
            if (d.trading_name) setTextInput("Trading name", d.trading_name);
            if (d.industry_type) setSelect("Industry type", d.industry_type);
            if (d.business_structure) setSelect("Business structure", d.business_structure);
            if (d.business_reg_type) setTextInput("Business registration type", d.business_reg_type);
            if (d.business_reg_id) setTextInput("Business registration ID", d.business_reg_id);
            if (d.org_website) setTextInput("Organisation website", d.org_website);
        }

        // Unemployed (3)
        if (d.employment_status === "3") {
            if (d.unemployment_date_from) setTextInput("Date from", d.unemployment_date_from);
            if (d.last_employment_position) setTextInput("Last employment position", d.last_employment_position);
        }

        // Retired (4)
        if (d.employment_status === "4") {
            if (d.retirement_date) setTextInput("Retirement date", d.retirement_date);
        }

        // Student (5)
        if (d.employment_status === "5") {
            if (d.course_name) setTextInput("Course name", d.course_name);
            if (d.institution_name) setTextInput("Institution name", d.institution_name);
            if (d.course_date_from) setTextInput("Date from", d.course_date_from);
            if (d.course_date_to) setTextInput("Date to", d.course_date_to);
        }

        // Other (99)
        if (d.employment_status === "99" || d.employment_status === "3") {
            if (d.give_details) {
                const ta = Array.from(document.querySelectorAll('textarea'))
                    .find(t => !t.closest('[hidden]'));
                if (ta) {
                    ta.value = d.give_details;
                    ta.dispatchEvent(new Event('change', {bubbles: true}));
                    console.log('[IMMI MAIN] Set Give details textarea');
                }
            }
        }

        // Organisation address (for Employed & Self-employed)
        if (d.employment_status === "1" || d.employment_status === "2") {
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
        }

        console.log('[IMMI MAIN] fillPage11 DONE ✅');
    }

    // ==================== PAGE 12: Financial support ====================
    async function fillPage12(d) {
        console.log('[IMMI MAIN] fillPage12 START — Financial support');

        // Funding source radio: 1=Self, 2=Employer, 3=Other Org, 4=Other Person
        if (d.funding_source) {
            const clicked = clickRadioInFieldset("how the applicant's stay in Australia will be funded", d.funding_source);
            if (!clicked) {
                // Fallback: try by fieldset name attribute
                const radio = document.querySelector(`input[type="radio"][name="_2a0b0a0a0e0a0a11a2e1b0"][value="${d.funding_source}"]`);
                if (radio) { radio.click(); console.log('[IMMI MAIN] Clicked funding_source via name fallback'); }
                else { console.warn('[IMMI MAIN] ❌ Could not find funding_source radio for value:', d.funding_source); }
            } else {
                console.log('[IMMI MAIN] ✅ Clicked funding_source =', d.funding_source);
            }
            await delay(1200);
        }

        // Available funds textarea (always visible)
        if (d.available_funds) {
            const ta = document.querySelector('textarea[id$="2g0b0a_input"]') ||
                       Array.from(document.querySelectorAll('textarea'))
                           .find(t => {
                               const label = document.querySelector(`label[for="${t.id}"]`);
                               return label && label.textContent.includes('funds will the applicant have');
                           });
            if (ta) {
                ta.value = d.available_funds;
                ta.dispatchEvent(new Event('change', {bubbles: true}));
                console.log('[IMMI MAIN] Set available_funds');
            }
        }

        // Type of support (for employer/org/person funded)
        if (d.funding_source !== "1" && d.support_type) {
            setSelect("Type of support", d.support_type);
            await delay(600);
        }

        // Supported by other person (4) — relationship + name + address
        if (d.funding_source === "4") {
            if (d.supporter_relationship) setSelect("Relationship to the applicant", d.supporter_relationship);
            if (d.supporter_family_name) setTextInput("Family name", d.supporter_family_name);
            if (d.supporter_given_names) setTextInput("Given names", d.supporter_given_names);

            // Supporter address — Country
            if (d.supporter_country) {
                const countrySelect = document.getElementById('_2a0b0a0a0e0a0a11a8b0b0_input');
                if (countrySelect) {
                    // ⚠️ WComponents needs FULL event chain to trigger State field transformation
                    countrySelect.focus();
                    countrySelect.dispatchEvent(new Event('focus', {bubbles: true}));
                    await delay(100);

                    countrySelect.value = d.supporter_country;

                    countrySelect.dispatchEvent(new Event('change', {bubbles: true}));
                    countrySelect.dispatchEvent(new Event('input', {bubbles: true}));
                    countrySelect.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                    countrySelect.blur();
                    countrySelect.dispatchEvent(new Event('blur', {bubbles: true}));

                    console.log(`[IMMI MAIN] ✅ Supporter Country = "${d.supporter_country}"`);
                    await delay(2500);
                }
            }

            // Address line 1
            if (d.supporter_address1) {
                const addr1 = document.getElementById('_2a0b0a0a0e0a0a11a8c0b0a_input');
                if (addr1) {
                    addr1.value = d.supporter_address1;
                    addr1.dispatchEvent(new Event('input', {bubbles: true}));
                    addr1.dispatchEvent(new Event('change', {bubbles: true}));
                    console.log(`[IMMI MAIN] ✅ Supporter Address1 = "${d.supporter_address1}"`);
                }
            }

            // Address line 2
            if (d.supporter_address2) {
                const addr2 = document.getElementById('_2a0b0a0a0e0a0a11a8d0b0_input');
                if (addr2) {
                    addr2.value = d.supporter_address2;
                    addr2.dispatchEvent(new Event('input', {bubbles: true}));
                    addr2.dispatchEvent(new Event('change', {bubbles: true}));
                    console.log(`[IMMI MAIN] ✅ Supporter Address2 = "${d.supporter_address2}"`);
                }
            }

            // Suburb/Town + State + Postcode — depends on Country
            if (d.supporter_country === 'A') {
                // ===== AUSTRALIAN ADDRESS =====
                // Suburb/Town (Australian section)
                if (d.supporter_suburb) {
                    const suburb = document.getElementById('_2a0b0a0a0e0a0a11a8e0a1a_input');
                    if (suburb) {
                        suburb.value = d.supporter_suburb;
                        suburb.dispatchEvent(new Event('input', {bubbles: true}));
                        suburb.dispatchEvent(new Event('change', {bubbles: true}));
                        console.log(`[IMMI MAIN] ✅ Supporter Suburb (AU) = "${d.supporter_suburb}"`);
                    }
                }

                // State/Territory (Australian select: ACT, NSW, etc.)
                if (d.supporter_state) {
                    const stateSelect = document.getElementById('_2a0b0a0a0e0a0a11a8e1a1a_input');
                    if (stateSelect && !stateSelect.closest('[hidden]')) {
                        stateSelect.value = d.supporter_state;
                        stateSelect.dispatchEvent(new Event('change', {bubbles: true}));
                        console.log(`[IMMI MAIN] ✅ Supporter State (AU) = "${d.supporter_state}"`);
                    }
                }

                // Postcode (Australian)
                if (d.supporter_postcode) {
                    const postcode = document.getElementById('_2a0b0a0a0e0a0a11a8e2a1a_input');
                    if (postcode) {
                        postcode.value = d.supporter_postcode;
                        postcode.dispatchEvent(new Event('input', {bubbles: true}));
                        postcode.dispatchEvent(new Event('change', {bubbles: true}));
                        console.log(`[IMMI MAIN] ✅ Supporter Postcode (AU) = "${d.supporter_postcode}"`);
                    }
                }
            } else {
                // ===== INTERNATIONAL ADDRESS =====
                // Suburb/Town (International section)
                if (d.supporter_suburb) {
                    const suburb = document.getElementById('_2a0b0a0a0e0a0a11a8f1a1a_input');
                    if (suburb) {
                        suburb.value = d.supporter_suburb;
                        suburb.dispatchEvent(new Event('input', {bubbles: true}));
                        suburb.dispatchEvent(new Event('change', {bubbles: true}));
                        console.log(`[IMMI MAIN] ✅ Supporter Suburb (intl) = "${d.supporter_suburb}"`);
                    }
                }

                // State/Province (International — text or select depending on country)
                if (d.supporter_state) {
                    // Try select first (VN provinces etc.)
                    const stateDropdown = document.getElementById('_2a0b0a0a0e0a0a11a8f2b0b0_input');
                    if (stateDropdown && !stateDropdown.closest('[hidden]')) {
                        const opts = Array.from(stateDropdown.options);
                        const textMatch = opts.find(o => o.textContent.trim().toUpperCase().includes(d.supporter_state.toUpperCase()));
                        const exactMatch = opts.find(o => o.value === d.supporter_state);
                        stateDropdown.value = exactMatch ? exactMatch.value : (textMatch ? textMatch.value : d.supporter_state);
                        stateDropdown.dispatchEvent(new Event('change', {bubbles: true}));
                        console.log(`[IMMI MAIN] ✅ Supporter State (intl select) = "${d.supporter_state}"`);
                    } else {
                        // Fallback to text input
                        const stateText = document.getElementById('_2a0b0a0a0e0a0a11a8f2a0b0_input');
                        if (stateText && !stateText.closest('[hidden]')) {
                            stateText.value = d.supporter_state;
                            stateText.dispatchEvent(new Event('input', {bubbles: true}));
                            stateText.dispatchEvent(new Event('change', {bubbles: true}));
                            console.log(`[IMMI MAIN] ✅ Supporter State (intl text) = "${d.supporter_state}"`);
                        }
                    }
                }
            }
        }

        // Supported by employer/org (2/3) — organisation details
        if (d.funding_source === "2" || d.funding_source === "3") {
            if (d.paying_org) setSelect("Organisation", d.paying_org);
            await delay(800);

            // Business / organisation details (shown for employer/org)
            if (d.org_legal_name) setTextInput("Legal registered name", d.org_legal_name);
            if (d.org_trading_name) setTextInput("Trading name", d.org_trading_name);
            if (d.org_industry_type) setSelect("Industry type", d.org_industry_type);
            if (d.org_business_structure) setSelect("Business structure", d.org_business_structure);

            // Organisation address 
            if (d.org_country) { setSelect("Country", d.org_country); await delay(800); }
            if (d.org_address1) setTextInput("Address", d.org_address1);
            if (d.org_suburb) setTextInput("Suburb / Town", d.org_suburb);
            if (d.org_state) {
                const stateSelect = Array.from(document.querySelectorAll('select'))
                    .find(s => !s.closest('[hidden]') && s.querySelector('option[value="NSW"]'));
                if (stateSelect) {
                    stateSelect.value = d.org_state;
                    stateSelect.dispatchEvent(new Event('change', {bubbles: true}));
                } else {
                    setTextInput("State or Province", d.org_state);
                }
            }
            if (d.org_postcode) setTextInput("Postcode", d.org_postcode);
        }

        console.log('[IMMI MAIN] fillPage12 DONE ✅');
    }

    // ==================== PAGE 16: Health declarations ====================
    async function fillPage16(d) {
        console.log('[IMMI MAIN] fillPage16 START — Health declarations');

        // Map field keys to unique substrings of the radio name attributes
        const radioMap = [
            { key: 'lived_outside_3months',  name: '_2a0b0a0a0e0a0a15a2b1a' },
            { key: 'enter_hospital',         name: '_2a0b0a0a0e0a0a15a4b1a' },
            { key: 'healthcare_worker',      name: '_2a0b0a0a0e0a0a15a6b1a' },
            { key: 'aged_disability_care',   name: '_2a0b0a0a0e0a0a15a8b1a' },
            { key: 'child_care_centre',      name: '_2a0b0a0a0e0a0a15a10b1a' },
            { key: 'classroom_3months',      name: '_2a0b0a0a0e0a0a15a12b1a' },
            { key: 'tuberculosis',           name: '_2a0b0a0a0e0a0a15a15a1a' },
            { key: 'medical_conditions',     name: '_2a0b0a0a0e0a0a15a18a1a' },
            { key: 'ongoing_medical_care',   name: '_2a0b0a0a0e0a0a15a20b1a0' }
        ];

        for (const item of radioMap) {
            const val = d[item.key] === 'Yes' ? '1' : '2'; // Default to No
            const radio = document.querySelector(`input[type="radio"][name="${item.name}"][value="${val}"]`);
            if (radio && !radio.checked) {
                radio.click();
                console.log(`[IMMI MAIN] Clicked ${item.key} = ${val === '1' ? 'Yes' : 'No'}`);
                await delay(400);
            }
        }

        console.log('[IMMI MAIN] fillPage16 DONE ✅');
    }

    // ==================== PAGE 17: Character declarations ====================
    async function fillPage17(d) {
        console.log('[IMMI MAIN] fillPage17 START — Character declarations');

        const radioMap = [
            { key: 'charged_offence',         name: '_2a0b0a0a0e0a0a16a4b1a' },
            { key: 'convicted_offence',        name: '_2a0b0a0a0e0a0a16a6b1a' },
            { key: 'domestic_violence_order',   name: '_2a0b0a0a0e0a0a16a8b1a0' },
            { key: 'arrest_warrant_interpol',   name: '_2a0b0a0a0e0a0a16a10b1b0' },
            { key: 'sexual_offence_child',      name: '_2a0b0a0a0e0a0a16a11b1b0' },
            { key: 'sex_offender_register',     name: '_2a0b0a0a0e0a0a16a12b1b0' },
            { key: 'acquitted_unsound_mind',    name: '_2a0b0a0a0e0a0a16a13b1b0' },
            { key: 'not_fit_to_plead',          name: '_2a0b0a0a0e0a0a16a14b1b0' },
            { key: 'risk_national_security',    name: '_2a0b0a0a0e0a0a16a15b1b0' },
            { key: 'genocide_war_crimes',       name: '_2a0b0a0a0e0a0a16a16b1b0' },
            { key: 'associated_criminal',       name: '_2a0b0a0a0e0a0a16a17b1b0' },
            { key: 'associated_violence',       name: '_2a0b0a0a0e0a0a16a18b1b0' },
            { key: 'military_service',          name: '_2a0b0a0a0e0a0a16a19b1a' },
            { key: 'military_training',         name: '_2a0b0a0a0e0a0a16a21b1a' },
            { key: 'people_smuggling',          name: '_2a0b0a0a0e0a0a16a23b1b0' },
            { key: 'removed_deported',          name: '_2a0b0a0a0e0a0a16a24b1b0' },
            { key: 'overstayed_visa',           name: '_2a0b0a0a0e0a0a16a25b1b0' },
            { key: 'outstanding_debts',         name: '_2a0b0a0a0e0a0a16a26b1b0' }
        ];

        for (const item of radioMap) {
            const val = d[item.key] === 'Yes' ? '1' : '2'; // Default to No
            const radio = document.querySelector(`input[type="radio"][name="${item.name}"][value="${val}"]`);
            if (radio && !radio.checked) {
                radio.click();
                console.log(`[IMMI MAIN] Clicked ${item.key} = ${val === '1' ? 'Yes' : 'No'}`);
                await delay(300);
            }
        }

        console.log('[IMMI MAIN] fillPage17 DONE ✅');
    }

    // ==================== PAGE 18: Visa history ====================
    async function fillPage18(d) {
        console.log('[IMMI MAIN] fillPage18 START — Visa history');

        const questions = [
            {
                key: 'held_visa',
                detailKey: 'held_visa_details',
                radioName: '_2a0b0a0a0e0a0a17a1b1a',
                textareaId: '_2a0b0a0a0e0a0a17a2a1a_input'
            },
            {
                key: 'not_complied',
                detailKey: 'not_complied_details',
                radioName: '_2a0b0a0a0e0a0a17a3b1a',
                textareaId: '_2a0b0a0a0e0a0a17a4a1a_input'
            },
            {
                key: 'visa_refused',
                detailKey: 'visa_refused_details',
                radioName: '_2a0b0a0a0e0a0a17a5b1a',
                textareaId: '_2a0b0a0a0e0a0a17a6a1a_input'
            }
        ];

        for (const q of questions) {
            const val = d[q.key] === 'Yes' ? '1' : '2';
            const radio = document.querySelector(`input[type="radio"][name="${q.radioName}"][value="${val}"]`);
            if (radio && !radio.checked) {
                radio.click();
                console.log(`[IMMI MAIN] Clicked ${q.key} = ${val === '1' ? 'Yes' : 'No'}`);
                await delay(800);
            }

            // If Yes, fill the details textarea
            if (d[q.key] === 'Yes' && d[q.detailKey]) {
                const ta = document.getElementById(q.textareaId);
                if (ta) {
                    ta.value = d[q.detailKey].substring(0, 300);
                    ta.dispatchEvent(new Event('change', {bubbles: true}));
                    console.log(`[IMMI MAIN] Filled ${q.detailKey}`);
                }
            }
        }

        console.log('[IMMI MAIN] fillPage18 DONE ✅');
    }

    // ==================== PAGE 20: Declarations ====================
    async function fillPage20(d) {
        console.log('[IMMI MAIN] fillPage20 START — Declarations (ALL YES)');

        // All declaration radio buttons — ALL must be Yes (value=1)
        const radioNames = [
            '_2a0b0a0a0e0a0a19a1f1b0',  // Read and understood
            '_2a0b0a0a0e0a0a19a1g1b0',  // Complete and correct info
            '_2a0b0a0a0e0a0a19a1h1b0',  // Understand fraudulent docs consequences
            '_2a0b0a0a0e0a0a19a1i1b0',  // Understand visa cancellation
            '_2a0b0a0a0e0a0a19a1j1b0',  // Persons not included (may be hidden)
            '_2a0b0a0a0e0a0a19a1ba1b0', // Will inform changes
            '_2a0b0a0a0e0a0a19a1bb1b0', // Will notify changes - student (may be hidden)
            '_2a0b0a0a0e0a0a19a1bd0b0', // Read privacy notice
            '_2a0b0a0a0e0a0a19a1bf0b0', // Understand collect personal info
            '_2a0b0a0a0e0a0a19a2a1b0',  // Understand 8503 no further stay
            '_2a0b0a0a0e0a0a19a3a1b0',  // Agree no study >3 months
            '_2a0b0a0a0e0a0a19a4a1b0',  // Agree to leave AU
            '_2a0b0a0a0e0a0a19a5a1b0',  // Consent fingerprints
            '_2a0b0a0a0e0a0a19a6b1b0',  // Understand fingerprints to law enforcement
            '_2a0b0a0a0e0a0a19a7a1b0',  // Consent law enforcement disclosure
            '_2a0b0a0a0e0a0a19a8b1a',   // Understand no work permit
            '_2a0b0a0a0e0a0a19a9a1b0',  // Consent biometric Migration Act
            '_2a0b0a0a0e0a0a19a10c1b0'  // Understand visa ceases
        ];

        let clicked = 0;
        for (const name of radioNames) {
            const radio = document.querySelector(`input[type="radio"][name="${name}"][value="1"]`);
            if (radio && !radio.checked) {
                radio.click();
                clicked++;
                await delay(250);
            }
        }

        console.log(`[IMMI MAIN] fillPage20 DONE ✅ — Clicked ${clicked} Yes buttons`);
    }

    // ==================== MESSAGE LISTENER ====================
    const FILLERS = {
        2: fillPage2,
        3: fillPage3,
        5: fillPage5,
        6: fillPage6,
        8: fillPage8,
        9: fillPage9,
        11: fillPage11,
        12: fillPage12,
        16: fillPage16,
        17: fillPage17,
        18: fillPage18,
        20: fillPage20
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
