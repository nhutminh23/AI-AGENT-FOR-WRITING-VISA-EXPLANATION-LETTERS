/**
 * app-5257.js — IMM5257E Visitor Visa Auto-Fill logic
 * Handles: prompt display, JSON parsing, review form, PDF fill
 */
(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Field definitions for the review form — ALL fields
    // -----------------------------------------------------------------------
    const PERSONAL_FIELDS = [
        { key: 'family_name', label: 'Family Name (Họ)', placeholder: 'DINH' },
        { key: 'given_name', label: 'Given Name (Tên)', placeholder: 'THI LAN ANH' },
        { key: 'has_alias', label: 'Has Alias?', type: 'select', options: ['N', 'Y'] },
        { key: 'alias_family_name', label: 'Alias Family Name', placeholder: '', showWhen: { key: 'has_alias', value: 'Y' } },
        { key: 'alias_given_name', label: 'Alias Given Name', placeholder: '', showWhen: { key: 'has_alias', value: 'Y' } },
        { key: 'sex', label: 'Sex', type: 'select', options: [['', '—'], ['Male', 'Male'], ['Female', 'Female']] },
        { key: 'dob', label: 'Date of Birth', placeholder: 'YYYY-MM-DD' },
        { key: 'birth_city', label: 'City of Birth', placeholder: 'HA TINH' },
        { key: 'birth_country', label: 'Country of Birth (code)', placeholder: '270' },
        { key: 'citizenship', label: 'Citizenship (code)', placeholder: '270' },
        { key: 'cor_country', label: 'Country of Residence (code)', placeholder: '270' },
        { key: 'cor_status', label: 'COR Status', placeholder: '01' },
        { key: 'has_prev_cor', label: 'Previous Country of Residence?', type: 'select', options: ['N', 'Y'] },
        { key: 'same_as_cor', label: 'Applying from same country?', type: 'select', options: ['Y', 'N'] },
        { key: 'marital_status', label: 'Marital Status', type: 'select',
            options: [['', '—Select—'], ['01','Married'], ['02','Single'], ['03','Common-law'],
                      ['04','Divorced'], ['05','Separated'], ['06','Widowed'], ['07','Annulled']] },
        { key: 'date_of_marriage', label: 'Date of Marriage', placeholder: 'YYYY-MM-DD' },
        { key: 'spouse_family_name', label: 'Spouse Family Name', placeholder: '' },
        { key: 'spouse_given_name', label: 'Spouse Given Name', placeholder: '' },
        { key: 'prev_married', label: 'Previously Married?', type: 'select', options: ['N', 'Y'] },
        { key: 'pm_family_name', label: 'Prev Spouse Family Name', placeholder: '', showWhen: { key: 'prev_married', value: 'Y' } },
        { key: 'pm_given_name', label: 'Prev Spouse Given Name', placeholder: '', showWhen: { key: 'prev_married', value: 'Y' } },
        { key: 'pm_dob', label: 'Prev Spouse DOB', placeholder: 'YYYY-MM-DD', showWhen: { key: 'prev_married', value: 'Y' } },
        { key: 'pm_relationship', label: 'Prev Relationship Type', placeholder: '', showWhen: { key: 'prev_married', value: 'Y' } },
        { key: 'pm_from', label: 'Prev Marriage From', placeholder: 'YYYY-MM-DD', showWhen: { key: 'prev_married', value: 'Y' } },
        { key: 'pm_to', label: 'Prev Marriage To', placeholder: 'YYYY-MM-DD', showWhen: { key: 'prev_married', value: 'Y' } },
    ];

    const PASSPORT_FIELDS = [
        { key: 'passport_number', label: 'Passport Number', placeholder: 'E01370203' },
        { key: 'passport_country', label: 'Passport Country (code)', placeholder: '270' },
        { key: 'passport_issue_date', label: 'Issue Date', placeholder: 'YYYY-MM-DD' },
        { key: 'passport_expiry_date', label: 'Expiry Date', placeholder: 'YYYY-MM-DD' },
        { key: 'native_language', label: 'Native Language', placeholder: 'Vietnamese' },
        { key: 'can_communicate', label: 'Can Communicate', type: 'select',
            options: [['', '—'], ['English', 'English'], ['French', 'French'], ['Both', 'Both'], ['Neither', 'Neither']] },
        { key: 'has_language_test', label: 'Language Test Taken?', type: 'select', options: ['N', 'Y'] },
        { key: 'has_national_id', label: 'Has National ID?', type: 'select', options: ['N', 'Y'] },
        { key: 'national_id_number', label: 'National ID Number', placeholder: '', showWhen: { key: 'has_national_id', value: 'Y' } },
        { key: 'national_id_country', label: 'National ID Country', placeholder: '270', showWhen: { key: 'has_national_id', value: 'Y' } },
        { key: 'national_id_issue', label: 'National ID Issue Date', placeholder: 'YYYY-MM-DD', showWhen: { key: 'has_national_id', value: 'Y' } },
        { key: 'national_id_expiry', label: 'National ID Expiry Date', placeholder: 'YYYY-MM-DD', showWhen: { key: 'has_national_id', value: 'Y' } },
        { key: 'has_us_card', label: 'Has US PR Card?', type: 'select', options: ['N', 'Y'] },
        { key: 'us_card_number', label: 'US Card Number', placeholder: '', showWhen: { key: 'has_us_card', value: 'Y' } },
        { key: 'us_card_expiry', label: 'US Card Expiry', placeholder: 'YYYY-MM-DD', showWhen: { key: 'has_us_card', value: 'Y' } },
    ];

    const CONTACT_FIELDS = [
        { key: 'address_pobox', label: 'PO Box', placeholder: '' },
        { key: 'address_apt', label: 'Apt / Unit', placeholder: '39' },
        { key: 'address_street_num', label: 'Street Number', placeholder: '' },
        { key: 'address_street_name', label: 'Street Name', placeholder: 'NGUYEN THI MINH KHAI 1' },
        { key: 'address_city', label: 'City', placeholder: 'BAC GIANG CITY' },
        { key: 'address_country', label: 'Address Country', placeholder: '270' },
        { key: 'address_province', label: 'Province / State', placeholder: '' },
        { key: 'address_postal_code', label: 'Postal Code', placeholder: '' },
        { key: 'address_district', label: 'District', placeholder: '' },
        { key: 'same_mailing_address', label: 'Same Mailing Address?', type: 'select', options: ['Y', 'N'] },
        { key: 'phone_type', label: 'Phone Type', type: 'select',
            options: [['01', 'Residence'], ['02', 'Cellular'], ['03', 'Business']] },
        { key: 'phone_number', label: 'Phone Number', placeholder: '+84372226878' },
        { key: 'alt_phone', label: 'Alt Phone', placeholder: '' },
        { key: 'email', label: 'Email', placeholder: '' },
    ];

    const VISIT_FIELDS = [
        { key: 'purpose', label: 'Purpose of Visit', type: 'select',
            options: [['', '—Select—'], ['01','Business'], ['02','Tourism'],
                      ['03','Short-Term Studies'], ['04','Returning Student'],
                      ['05','Returning Worker'], ['06','Super Visa'],
                      ['07','Other'], ['08','Family Visit'], ['13','Visit']] },
        { key: 'purpose_other', label: 'Purpose Details', placeholder: 'TOURISM' },
        { key: 'travel_from', label: 'Travel From', placeholder: 'YYYY-MM-DD' },
        { key: 'travel_to', label: 'Travel To', placeholder: 'YYYY-MM-DD' },
        { key: 'funds', label: 'Funds Available (CAD)', placeholder: '7000' },
        { key: 'contact1_name', label: 'Contact in Canada (Name)', placeholder: '' },
        { key: 'contact1_relationship', label: 'Contact 1 Relationship', placeholder: '' },
        { key: 'contact1_address', label: 'Contact 1 Address', placeholder: '' },
        { key: 'contact2_name', label: 'Contact 2 Name', placeholder: '' },
        { key: 'contact2_relationship', label: 'Contact 2 Relationship', placeholder: '' },
        { key: 'contact2_address', label: 'Contact 2 Address', placeholder: '' },
        { key: 'has_education', label: 'Has Post-secondary Education?', type: 'select', options: ['N', 'Y'] },
    ];

    const BACKGROUND_FIELDS = [
        { key: 'bg_medical', label: 'Q1a) Tuberculosis/close contact?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_medical_b', label: 'Q1b) Physical/mental disorder?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_medical_details', label: 'Q1c) Medical Details', placeholder: 'Provide details if Yes above',
          showWhen: { key: 'bg_medical', value: 'Y' }, type: 'textarea' },
        { key: 'bg_overstayed', label: 'Q2a) Overstayed/worked without auth?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_refused_visa', label: 'Q2b) Refused visa/entry to any country?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_refused_details', label: 'Q2b) Refused Details', placeholder: 'Details of refusal',
          showWhen: { key: 'bg_refused_visa', value: 'Y' }, type: 'textarea' },
        { key: 'bg_applied_before', label: 'Q2c) Previously applied to Canada?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_crime', label: 'Q3) Arrested/convicted of crime?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_crime_details', label: 'Q3) Crime Details', placeholder: 'Details',
          showWhen: { key: 'bg_crime', value: 'Y' }, type: 'textarea' },
        { key: 'bg_military', label: 'Q4) Military/militia service?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_military_details', label: 'Q4) Military Details', placeholder: 'Details of service',
          showWhen: { key: 'bg_military', value: 'Y' }, type: 'textarea' },
        { key: 'bg_political', label: 'Q5) Political/violent organization?', type: 'select', options: ['N', 'Y'] },
        { key: 'bg_witnessed', label: 'Q6) Witnessed ill treatment?', type: 'select', options: ['N', 'Y'] },
    ];

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------
    let currentStep = 's1';
    let promptText = '';
    let formData = {};

    // -----------------------------------------------------------------------
    // Step navigation
    // -----------------------------------------------------------------------
    function goToStep(step) {
        currentStep = step;
        const container = document.getElementById('form-imm5257');
        container.querySelectorAll('.step-content').forEach(s => s.classList.remove('active'));
        const target = document.getElementById(step);
        if (target) target.classList.add('active');

        const stepNum = { s1: 1, s2: 2, s3: 3, s4: 4 }[step] || 1;
        container.querySelectorAll('.steps-bar .step').forEach(s => {
            const sn = parseInt(s.dataset.step?.replace('s', '') || '0');
            s.classList.toggle('active', sn <= stepNum);
        });
    }

    // -----------------------------------------------------------------------
    // Step 1: Load & copy prompt
    // -----------------------------------------------------------------------
    async function loadPrompt() {
        try {
            const res = await fetch('/canada/api/prompt-template-5257');
            const data = await res.json();
            if (data.prompt) {
                promptText = data.prompt;
                const display = document.getElementById('promptDisplay5257');
                display.innerHTML = `<pre style="white-space:pre-wrap;font-size:13px;max-height:400px;overflow-y:auto">${escapeHtml(promptText)}</pre>`;
                document.getElementById('copyPromptBtn5257').disabled = false;
            }
        } catch (e) {
            document.getElementById('promptDisplay5257').innerHTML =
                '<div class="prompt-loading" style="color:#dc2626">Failed to load prompt template</div>';
        }
    }

    function copyPrompt() {
        navigator.clipboard.writeText(promptText).then(() => {
            const btn = document.getElementById('copyPromptBtn5257');
            btn.textContent = '✅ Copied!';
            setTimeout(() => { btn.textContent = '📋 Copy Prompt'; }, 2000);
        });
    }

    // -----------------------------------------------------------------------
    // Step 2: Parse JSON
    // -----------------------------------------------------------------------
    function applyJson() {
        const raw = document.getElementById('jsonInput5257').value.trim();
        const statusEl = document.getElementById('jsonStatus5257');
        if (!raw) {
            statusEl.innerHTML = '<span style="color:#dc2626">Please paste JSON data</span>';
            return;
        }

        try {
            let cleaned = raw;
            const codeBlockMatch = cleaned.match(/```(?:json)?\s*([\s\S]*?)```/);
            if (codeBlockMatch) cleaned = codeBlockMatch[1].trim();

            formData = JSON.parse(cleaned);
            statusEl.innerHTML = '<span style="color:#16a34a">✅ JSON valid!</span>';
            buildReviewForm();
            goToStep('s3');
        } catch (e) {
            statusEl.innerHTML = `<span style="color:#dc2626">Invalid JSON: ${e.message}</span>`;
        }
    }

    // -----------------------------------------------------------------------
    // Step 3: Build review form with ALL fields
    // -----------------------------------------------------------------------
    function buildReviewForm() {
        buildFieldGroup('f5257_personal', PERSONAL_FIELDS, '👤 Personal Details');
        buildFieldGroup('f5257_passport', PASSPORT_FIELDS, '📘 Passport / ID / Language');
        buildFieldGroup('f5257_contact', CONTACT_FIELDS, '📍 Contact Information');
        buildFieldGroup('f5257_visit', VISIT_FIELDS, '✈️ Visit Details');
        buildFieldGroup('f5257_background', BACKGROUND_FIELDS, '🔍 Background Questions');

        // Add occupation section
        buildOccupationSection();

        // Add education section if visible
        buildEducationSection();
    }

    function buildFieldGroup(containerId, fields, headerText) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '';

        if (headerText) {
            const header = document.createElement('h3');
            header.style.cssText = 'grid-column: 1 / -1; margin: 0 0 4px 0; font-size: 15px; color: var(--primary, #6366f1);';
            header.textContent = headerText;
            container.appendChild(header);
        }

        fields.forEach(f => {
            const value = getNestedValue(formData, f.key) ?? '';
            const div = document.createElement('div');
            div.className = 'form-field';
            div.dataset.fieldKey = f.key;

            // Handle conditional visibility
            if (f.showWhen) {
                const parentVal = getNestedValue(formData, f.showWhen.key) ?? '';
                if (String(parentVal) !== f.showWhen.value) {
                    div.style.display = 'none';
                }
                div.dataset.showWhenKey = f.showWhen.key;
                div.dataset.showWhenValue = f.showWhen.value;
            }

            if (f.type === 'textarea') {
                div.style.gridColumn = '1 / -1';
                div.innerHTML = `
                    <label>${f.label}</label>
                    <textarea data-key="${f.key}" rows="3" placeholder="${f.placeholder || ''}"
                              style="width:100%;padding:8px;border-radius:6px;border:1px solid #d1d5db;font-size:13px;resize:vertical;">${escapeHtml(String(value))}</textarea>
                `;
            } else if (f.type === 'select') {
                const options = f.options.map(o => {
                    if (Array.isArray(o)) {
                        const selected = o[0] === String(value) ? 'selected' : '';
                        return `<option value="${o[0]}" ${selected}>${o[1]}</option>`;
                    }
                    const selected = o === String(value) ? 'selected' : '';
                    return `<option value="${o}" ${selected}>${o || '—'}</option>`;
                }).join('');
                div.innerHTML = `
                    <label>${f.label}</label>
                    <select data-key="${f.key}">${options}</select>
                `;

                // Add change listener for conditional fields
                if (['has_alias','prev_married','has_national_id','has_us_card','bg_medical','bg_refused_visa','bg_crime','bg_military'].includes(f.key)) {
                    setTimeout(() => {
                        const sel = div.querySelector('select');
                        sel?.addEventListener('change', () => handleConditionalVisibility(containerId, f.key, sel.value));
                    }, 0);
                }
            } else {
                div.innerHTML = `
                    <label>${f.label}</label>
                    <input type="text" data-key="${f.key}" value="${escapeAttr(String(value))}"
                           placeholder="${f.placeholder || ''}">
                `;
            }
            container.appendChild(div);
        });
    }

    function handleConditionalVisibility(containerId, parentKey, parentValue) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.querySelectorAll(`[data-show-when-key="${parentKey}"]`).forEach(el => {
            el.style.display = el.dataset.showWhenValue === parentValue ? '' : 'none';
        });
    }

    function buildOccupationSection() {
        const container = document.getElementById('f5257_visit');
        if (!container) return;

        // Build up to 3 occupation rows
        for (let i = 0; i < 3; i++) {
            let occ = formData[`occupation_${i}`];
            if (!occ && i === 0) occ = formData.current_occupation;
            if (!occ && i > 0) occ = {};

            const label = i === 0 ? '💼 Current Occupation' : `💼 Previous Occupation ${i}`;
            const bg = i === 0 ? '#f0f9ff' : '#f8fafc';

            const html = `
                <div class="form-field" style="grid-column: 1 / -1; background: ${bg}; padding: 12px; border-radius: 8px; margin-top: 8px;">
                    <h4 style="margin:0 0 8px 0; font-size: 14px;">${label}</h4>
                    <div class="form-grid">
                        ${makeInput(`occ${i}_title`, 'Job Title', occ?.title || '')}
                        ${makeInput(`occ${i}_employer`, 'Employer', occ?.employer || '')}
                        ${makeInput(`occ${i}_city`, 'City', occ?.city || '')}
                        ${makeInput(`occ${i}_country`, 'Country (code)', occ?.country || '')}
                        ${makeInput(`occ${i}_province`, 'Province', occ?.province || '')}
                        ${makeInput(`occ${i}_from_year`, 'From Year', occ?.from_year || '')}
                        ${makeInput(`occ${i}_from_month`, 'From Month', occ?.from_month || '')}
                        ${makeInput(`occ${i}_to_year`, 'To Year', occ?.to_year || '')}
                        ${makeInput(`occ${i}_to_month`, 'To Month', occ?.to_month || '')}
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        }
    }

    function buildEducationSection() {
        const container = document.getElementById('f5257_visit');
        if (!container) return;
        const edu = formData.education || {};

        const html = `
            <div class="form-field" id="edu-section" style="grid-column: 1 / -1; background: #fdf4ff; padding: 12px; border-radius: 8px; margin-top: 8px; ${formData.has_education !== 'Y' ? 'display:none;' : ''}">
                <h4 style="margin:0 0 8px 0; font-size: 14px;">🎓 Education</h4>
                <div class="form-grid">
                    ${makeInput('edu_field', 'Field of Study', edu.field || '')}
                    ${makeInput('edu_school', 'School', edu.school || '')}
                    ${makeInput('edu_city', 'City', edu.city || '')}
                    ${makeInput('edu_country', 'Country (code)', edu.country || '')}
                    ${makeInput('edu_province', 'Province', edu.province || '')}
                    ${makeInput('edu_from_year', 'From Year', edu.from_year || '')}
                    ${makeInput('edu_from_month', 'From Month', edu.from_month || '')}
                    ${makeInput('edu_to_year', 'To Year', edu.to_year || '')}
                    ${makeInput('edu_to_month', 'To Month', edu.to_month || '')}
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);

        // Listen for has_education change
        setTimeout(() => {
            const sel = container.querySelector('[data-key="has_education"]');
            sel?.addEventListener('change', () => {
                const sec = document.getElementById('edu-section');
                if (sec) sec.style.display = sel.value === 'Y' ? '' : 'none';
            });
        }, 0);
    }

    function makeInput(key, label, value) {
        return `<div class="form-field">
            <label>${label}</label>
            <input type="text" data-key="${key}" value="${escapeAttr(String(value || ''))}">
        </div>`;
    }

    function getNestedValue(obj, key) {
        return obj?.[key];
    }

    // -----------------------------------------------------------------------
    // Step 3→4: Collect form data & fill PDF
    // -----------------------------------------------------------------------
    function collectFormData() {
        const container = document.getElementById('form-imm5257');
        container.querySelectorAll('[data-key]').forEach(el => {
            const key = el.dataset.key;
            formData[key] = el.value;
        });

        // Rebuild occupation objects
        for (let i = 0; i < 3; i++) {
            const prefix = `occ${i}_`;
            const title = formData[prefix + 'title'] || '';
            const employer = formData[prefix + 'employer'] || '';
            if (title || employer) {
                const occ = {
                    title,
                    employer,
                    city: formData[prefix + 'city'] || '',
                    country: formData[prefix + 'country'] || '',
                    province: formData[prefix + 'province'] || '',
                    from_year: formData[prefix + 'from_year'] || '',
                    from_month: formData[prefix + 'from_month'] || '',
                    to_year: formData[prefix + 'to_year'] || '',
                    to_month: formData[prefix + 'to_month'] || '',
                };
                if (i === 0) formData.current_occupation = occ;
                else formData[`occupation_${i}`] = occ;
            }
        }

        // Rebuild education object
        if (formData.has_education === 'Y') {
            formData.education = {
                field: formData.edu_field || '',
                school: formData.edu_school || '',
                city: formData.edu_city || '',
                country: formData.edu_country || '',
                province: formData.edu_province || '',
                from_year: formData.edu_from_year || '',
                from_month: formData.edu_from_month || '',
                to_year: formData.edu_to_year || '',
                to_month: formData.edu_to_month || '',
            };
        }

        return formData;
    }

    async function fillPdf() {
        const statusEl = document.getElementById('fillStatus5257');
        const fillBtn = document.getElementById('fillBtn5257');
        statusEl.innerHTML = '<span style="color:#2563eb">⏳ Creating PDF...</span>';
        if (fillBtn) { fillBtn.disabled = true; fillBtn.textContent = '⏳ Creating...'; }

        const data = collectFormData();

        try {
            const res = await fetch('/canada/api/fill-5257', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ form_fields: data }),
            });
            const result = await res.json();

            if (result.success) {
                document.getElementById('downloadLink5257').href = result.download_url;
                goToStep('s4');
            } else {
                statusEl.innerHTML = `<span style="color:#dc2626">Error: ${result.error}</span>`;
            }
        } catch (e) {
            statusEl.innerHTML = `<span style="color:#dc2626">Error: ${e.message}</span>`;
        }
        if (fillBtn) { fillBtn.disabled = false; fillBtn.textContent = '✍️ Fill PDF & Download'; }
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------
    function escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    function escapeAttr(str) {
        return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // -----------------------------------------------------------------------
    // Event binding
    // -----------------------------------------------------------------------
    function init5257() {
        loadPrompt();

        // Check template
        fetch('/canada/api/check-template').then(r => r.json()).then(data => {
            const badge = document.getElementById('badge5257');
            if (data.imm5257_available) {
                badge.className = 'tab-badge ok';
                badge.textContent = '✅ Template OK';
            } else {
                badge.className = 'tab-badge missing';
                badge.textContent = '❌ Missing';
            }
            const badge5645 = document.getElementById('badge5645');
            if (data.imm5645_available) {
                badge5645.className = 'tab-badge ok';
                badge5645.textContent = '✅ Family Info';
            }
        });

        // Step 1 buttons
        document.getElementById('copyPromptBtn5257')?.addEventListener('click', copyPrompt);
        document.getElementById('goToS2Btn')?.addEventListener('click', () => goToStep('s2'));

        // Step 2 buttons
        document.getElementById('applyJsonBtn5257')?.addEventListener('click', applyJson);
        document.getElementById('backToS1Btn')?.addEventListener('click', () => goToStep('s1'));

        // Step 3 buttons
        document.getElementById('fillBtn5257')?.addEventListener('click', fillPdf);
        document.getElementById('backToS2Btn')?.addEventListener('click', () => goToStep('s2'));

        // Step 4 buttons
        document.getElementById('startOverBtn5257')?.addEventListener('click', () => {
            formData = {};
            document.getElementById('jsonInput5257').value = '';
            goToStep('s1');
        });
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init5257);
    } else {
        init5257();
    }
})();
