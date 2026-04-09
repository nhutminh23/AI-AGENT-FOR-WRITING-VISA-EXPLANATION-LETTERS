// ==================== LETTER GEN V3 — Frontend Logic ====================
// Workflow: Copy Prompt → Paste JSON → AI Generate → Download DOCX
// With Group Application detection for ≥2 applicants

// ---- State ----
let letterGenCurrentStep = 1;
let letterGenProfile = null;
let letterGenResult = null;
let letterGenAllProfiles = null;   // Keep original multi-profile data
let letterGenGroupParticipants = null; // Detected group participants

// ---- Elements ----
function getLetterGenEl(id) { return document.getElementById(id); }

// ---- Step Navigation ----
function letterGenSetStep(step) {
  letterGenCurrentStep = step;
  // Hide all steps
  document.querySelectorAll('.letter-gen-step').forEach(el => el.style.display = 'none');
  const stepEl = getLetterGenEl(`letterGenStep${step}`);
  if (stepEl) stepEl.style.display = '';

  // Update steps bar
  document.querySelectorAll('.letter-step').forEach(el => {
    const s = parseInt(el.dataset.letterStep);
    if (s === step) {
      el.style.background = '#4f46e5';
      el.style.color = '#fff';
      el.classList.add('active');
    } else if (s < step) {
      el.style.background = '#1e3a5f';
      el.style.color = '#93c5fd';
      el.classList.remove('active');
    } else {
      el.style.background = '';
      el.style.color = '#94a3b8';
      el.classList.remove('active');
    }
  });
}

// ---- Step 1: Load & Show Prompt ----
async function letterGenLoadPrompt() {
  const display = getLetterGenEl('letterGenPromptDisplay');
  try {
    const res = await fetch('/api/letter-gen/prompt-template');
    const data = await res.json();
    if (data.prompt) {
      display.textContent = data.prompt;
    } else {
      display.textContent = '❌ Không tải được prompt: ' + (data.error || 'unknown');
    }
  } catch(e) {
    display.textContent = '❌ Lỗi kết nối: ' + e.message;
  }
}

function letterGenCopyPrompt() {
  const display = getLetterGenEl('letterGenPromptDisplay');
  const status = getLetterGenEl('letterGenCopyStatus');
  navigator.clipboard.writeText(display.textContent).then(() => {
    status.innerHTML = '<span style="color:#16a34a;">✅ Đã copy prompt! Paste vào Grok cùng các file hồ sơ.</span>';
    setTimeout(() => { status.innerHTML = ''; }, 5000);
  }).catch(() => {
    // Fallback for older browsers
    const ta = document.createElement('textarea');
    ta.value = display.textContent;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    status.innerHTML = '<span style="color:#16a34a;">✅ Đã copy prompt!</span>';
    setTimeout(() => { status.innerHTML = ''; }, 5000);
  });
}

// ---- Step 2: Parse & Validate JSON + Group Detection ----
function letterGenParseJson(raw) {
  let text = raw.trim();
  // Strip markdown code block if present
  const jsonBlockMatch = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?\s*```/);
  if (jsonBlockMatch) {
    text = jsonBlockMatch[1].trim();
  }
  return JSON.parse(text);
}

/**
 * Detect group participants from parsed JSON data.
 * Works with:
 *  - Array of profiles: [{applicant: {...}}, {applicant: {...}}]
 *  - Dict of profiles: {person_1: {applicant: {...}}, person_2: {applicant: {...}}}
 *  - Single profile with accompanying_persons/group_members/co_applicants
 */
function letterGenDetectGroup(parsed) {
  const participants = [];

  if (Array.isArray(parsed)) {
    for (const p of parsed) {
      if (p && typeof p === 'object' && p.applicant) {
        participants.push(_extractParticipant(p.applicant));
      }
    }
  } else if (parsed && typeof parsed === 'object') {
    if (parsed.applicant) {
      // Single profile — check for group-related keys
      participants.push(_extractParticipant(parsed.applicant));
      for (const key of ['accompanying_persons', 'group_members', 'co_applicants']) {
        const extras = parsed[key];
        if (Array.isArray(extras)) {
          for (const person of extras) {
            if (person && typeof person === 'object') {
              participants.push(_extractParticipant(person));
            }
          }
        }
      }
    } else {
      // Dict of profiles
      const values = Object.values(parsed);
      for (const v of values) {
        if (v && typeof v === 'object' && v.applicant) {
          participants.push(_extractParticipant(v.applicant));
        }
      }
    }
  }

  return participants.length >= 2 ? participants : [];
}

function _extractParticipant(person) {
  return {
    full_name: person.full_name || '',
    passport_no: person.passport_no || '',
    dob: person.dob || '',
    sex: person.sex || person.gender || '',
    passport_expiry: person.passport_expiry || person.date_of_expiry || '',
  };
}

/**
 * Show group panel with participants table.
 */
function letterGenShowGroupPanel(participants) {
  const panel = getLetterGenEl('letterGenGroupPanel');
  const info = getLetterGenEl('letterGenGroupInfo');
  const tableDiv = getLetterGenEl('letterGenGroupTable');

  if (!panel || participants.length < 2) {
    if (panel) panel.style.display = 'none';
    return;
  }

  info.innerHTML = `Phát hiện <strong>${participants.length}</strong> người trong hồ sơ. Nhập Group ID rồi bấm tạo thư.`;

  // Build HTML table
  let html = `<table style="width:100%; border-collapse:collapse; font-size:0.85em; background:#0f172a; border-radius:8px; overflow:hidden;">
    <thead><tr style="background:#312e81; color:#c4b5fd;">
      <th style="padding:6px 8px; text-align:center;">#</th>
      <th style="padding:6px 8px; text-align:left;">Full Name</th>
      <th style="padding:6px 8px; text-align:center;">Passport No.</th>
      <th style="padding:6px 8px; text-align:center;">Date of Birth</th>
      <th style="padding:6px 8px; text-align:center;">Sex</th>
      <th style="padding:6px 8px; text-align:center;">Passport Expiry</th>
    </tr></thead><tbody>`;

  participants.forEach((p, i) => {
    html += `<tr style="border-top:1px solid #334155;">
      <td style="padding:6px 8px; text-align:center; color:#94a3b8;">${i + 1}</td>
      <td style="padding:6px 8px; color:#e2e8f0; font-weight:600;">${p.full_name}</td>
      <td style="padding:6px 8px; text-align:center; color:#e2e8f0;">${p.passport_no}</td>
      <td style="padding:6px 8px; text-align:center; color:#94a3b8;">${p.dob}</td>
      <td style="padding:6px 8px; text-align:center; color:#94a3b8;">${p.sex}</td>
      <td style="padding:6px 8px; text-align:center; color:#94a3b8;">${p.passport_expiry}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  tableDiv.innerHTML = html;

  panel.style.display = '';
}

function letterGenHideGroupPanel() {
  const panel = getLetterGenEl('letterGenGroupPanel');
  if (panel) panel.style.display = 'none';
  letterGenGroupParticipants = null;
}

/**
 * Download Group Participant List as DOCX.
 */
async function letterGenDownloadGroupDocx() {
  if (!letterGenGroupParticipants || letterGenGroupParticipants.length < 2) return;

  const groupId = (getLetterGenEl('letterGenGroupId')?.value || '').trim();
  const statusEl = getLetterGenEl('letterGenGroupStatus');
  statusEl.innerHTML = '<span style="color:#f59e0b;">⏳ Đang tạo DOCX...</span>';

  try {
    const res = await fetch('/api/letter-gen/build-group-docx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        participants: letterGenGroupParticipants,
        group_id: groupId,
      }),
    });

    if (!res.ok) {
      const data = await res.json();
      statusEl.innerHTML = `<span style="color:#dc2626;">❌ ${data.error || 'Lỗi server'}</span>`;
      return;
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const cd = res.headers.get('content-disposition');
    let filename = 'Group_Participant_List.docx';
    if (cd && cd.includes('filename=')) {
      filename = cd.split('filename=')[1].replace(/["']/g, '');
    }

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);

    statusEl.innerHTML = '<span style="color:#16a34a;">✅ Đã tải Group List DOCX!</span>';
    setTimeout(() => { statusEl.innerHTML = ''; }, 5000);
  } catch(e) {
    statusEl.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${e.message}</span>`;
  }
}

async function letterGenApplyJson() {
  const input = getLetterGenEl('letterGenJsonInput');
  const status = getLetterGenEl('letterGenJsonStatus');
  const additionalContext = getLetterGenEl('letterGenAdditionalContext')?.value || '';

  if (!input.value.trim()) {
    status.innerHTML = '<span style="color:#dc2626;">❌ Vui lòng paste JSON từ Grok.</span>';
    return;
  }

  // Parse JSON
  let parsed;
  try {
    parsed = letterGenParseJson(input.value);
  } catch(e) {
    status.innerHTML = `<span style="color:#dc2626;">❌ JSON không hợp lệ: ${e.message}</span>`;
    return;
  }

  // Save original for group detection
  letterGenAllProfiles = parsed;

  // --- Group Detection ---
  letterGenGroupParticipants = letterGenDetectGroup(parsed);
  if (letterGenGroupParticipants.length >= 2) {
    letterGenShowGroupPanel(letterGenGroupParticipants);
  } else {
    letterGenHideGroupPanel();
  }

  // --- Select single profile for letter generation ---
  // Check if it's a dictionary of profiles (e.g. {"applicant_1": {...}, "applicant_2": {...}})
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) && !parsed.applicant) {
    const values = Object.values(parsed);
    if (values.length > 0 && values[0] && typeof values[0] === 'object' && values[0].applicant) {
      parsed = values;
    }
  }

  // Handle array of multiple applicants
  if (Array.isArray(parsed)) {
    if (parsed.length === 0) {
      status.innerHTML = '<span style="color:#dc2626;">❌ JSON mảng rỗng, không có dữ liệu.</span>';
      return;
    }
    if (parsed.length === 1) {
      letterGenProfile = parsed[0];
    } else {
      // Multiple applicants — show picker
      const names = parsed.map((p, i) => 
        `${i + 1}. ${p.applicant?.full_name || 'Applicant ' + (i + 1)}`
      ).join('\n');
      const choice = prompt(
        `JSON có ${parsed.length} người:\n${names}\n\nNhập số thứ tự (1-${parsed.length}) để chọn người tạo thư:`,
        '1'
      );
      const idx = parseInt(choice) - 1;
      if (isNaN(idx) || idx < 0 || idx >= parsed.length) {
        status.innerHTML = '<span style="color:#dc2626;">❌ Lựa chọn không hợp lệ. Vui lòng thử lại.</span>';
        return;
      }
      letterGenProfile = parsed[idx];
    }
  } else {
    letterGenProfile = parsed;
  }

  // Validate required fields
  if (!letterGenProfile.applicant || !letterGenProfile.applicant.full_name) {
    status.innerHTML = '<span style="color:#dc2626;">❌ JSON thiếu trường applicant.full_name</span>';
    return;
  }

  // Start generation
  status.innerHTML = '<span style="color:#f59e0b;">⏳ Đang gọi AI sinh thư... (có thể mất 30-60 giây)</span>';
  const btn = getLetterGenEl('letterGenApplyJsonBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Đang sinh thư...';

  // Build group_info if group detected
  let groupInfo = null;
  if (letterGenGroupParticipants && letterGenGroupParticipants.length >= 2) {
    groupInfo = {
      participants: letterGenGroupParticipants,
      group_id: (getLetterGenEl('letterGenGroupId')?.value || '').trim(),
      group_label: (getLetterGenEl('letterGenGroupLabel')?.value || '').trim(),
    };
  }

  try {
    const res = await fetch('/api/letter-gen/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: letterGenProfile,
        additional_context: additionalContext,
        group_info: groupInfo,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      status.innerHTML = `<span style="color:#dc2626;">❌ ${data.error || 'Lỗi server'}</span>`;
      return;
    }

    letterGenResult = data;

    // Fill step 3
    getLetterGenEl('letterGenMainText').value = data.explanation_letter || '';

    const hasRefusal = data.has_refusal && data.refusal_letter;
    if (hasRefusal) {
      getLetterGenEl('letterGenRefusalText').value = data.refusal_letter;
      getLetterGenEl('letterGenTabs').style.display = '';
      getLetterGenEl('letterGenDownloadRefusalBtn').style.display = '';
      getLetterGenEl('letterGenResultInfo').innerHTML = 
        `✅ Đã sinh <strong>2 thư</strong> cho <strong>${data.applicant_name}</strong>: Thư giải trình + Thư giải thích từ chối.` +
        (data.is_group ? ` <span style="color:#c4b5fd;">👥 Group Application</span>` : '');
    } else {
      getLetterGenEl('letterGenTabs').style.display = 'none';
      getLetterGenEl('letterGenDownloadRefusalBtn').style.display = 'none';
      getLetterGenEl('letterGenResultInfo').innerHTML = 
        `✅ Đã sinh <strong>1 thư</strong> cho <strong>${data.applicant_name}</strong>: Thư giải trình.` +
        (data.is_group ? ` <span style="color:#c4b5fd;">👥 Group Application</span>` : '');
    }

    // Show tabs correctly
    letterGenShowMainTab();

    // Go to step 3
    letterGenSetStep(3);
    status.innerHTML = '';
  } catch(e) {
    status.innerHTML = `<span style="color:#dc2626;">❌ Lỗi kết nối: ${e.message}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Tạo Thư Giải Trình';
  }
}

// ---- Step 3: Tab switching ----
function letterGenShowMainTab() {
  getLetterGenEl('letterGenMainPanel').style.display = '';
  getLetterGenEl('letterGenRefusalPanel').style.display = 'none';
  getLetterGenEl('letterGenTabMain').style.background = '#4f46e5';
  getLetterGenEl('letterGenTabMain').style.color = '#fff';
  getLetterGenEl('letterGenTabRefusal').style.background = '#334155';
  getLetterGenEl('letterGenTabRefusal').style.color = '#94a3b8';
}

function letterGenShowRefusalTab() {
  getLetterGenEl('letterGenMainPanel').style.display = 'none';
  getLetterGenEl('letterGenRefusalPanel').style.display = '';
  getLetterGenEl('letterGenTabMain').style.background = '#334155';
  getLetterGenEl('letterGenTabMain').style.color = '#94a3b8';
  getLetterGenEl('letterGenTabRefusal').style.background = '#4f46e5';
  getLetterGenEl('letterGenTabRefusal').style.color = '#fff';
}

// ---- Step 3/4: Download DOCX ----
async function letterGenDownloadDocx(type) {
  const status = getLetterGenEl('letterGenDownloadStatus');
  const isMain = (type === 'main');
  const letterText = isMain
    ? getLetterGenEl('letterGenMainText').value
    : getLetterGenEl('letterGenRefusalText').value;
  const applicantName = letterGenResult?.applicant_name || 'Applicant';
  const prefix = isMain ? 'Explanation_Letter' : 'Refusal_Explanation';

  if (!letterText.trim()) {
    status.innerHTML = '<span style="color:#dc2626;">❌ Không có nội dung thư để tải.</span>';
    return;
  }

  status.innerHTML = '<span style="color:#f59e0b;">⏳ Đang tạo DOCX...</span>';

  try {
    const res = await fetch('/api/letter-gen/build-docx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        letter_text: letterText,
        applicant_name: applicantName,
        filename_prefix: prefix,
      }),
    });
    if (!res.ok) {
      // If error, it returns JSON
      const data = await res.json();
      status.innerHTML = `<span style="color:#dc2626;">❌ ${data.error || 'Server error'}</span>`;
      return;
    }

    // Success -> it returns a Blob (DOCX file attachment)
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    
    // Get filename from Content-Disposition if possible, fallback to custom
    const cd = res.headers.get('content-disposition');
    let filename = `${prefix}_${applicantName}.docx`;
    if (cd && cd.includes('filename=')) {
        filename = cd.split('filename=')[1].replace(/["']/g, '');
    }

    // Trigger download via Blob URL (bypasses browser popup blockers completely)
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);

    status.innerHTML = `<span style="color:#16a34a;">✅ Đã tải thành công (Không lưu rác trên hệ thống!)</span>`;
    
    // Move to step 4
    letterGenSetStep(4);
  } catch(e) {
    status.innerHTML = `<span style="color:#dc2626;">❌ Lỗi: ${e.message}</span>`;
  }
}

// ---- Reset / Start Over ----
function letterGenStartOver() {
  letterGenProfile = null;
  letterGenResult = null;
  letterGenAllProfiles = null;
  letterGenGroupParticipants = null;
  getLetterGenEl('letterGenJsonInput').value = '';
  getLetterGenEl('letterGenAdditionalContext').value = '';
  getLetterGenEl('letterGenMainText').value = '';
  getLetterGenEl('letterGenRefusalText').value = '';
  getLetterGenEl('letterGenJsonStatus').innerHTML = '';
  getLetterGenEl('letterGenDownloadStatus').innerHTML = '';
  getLetterGenEl('letterGenResultInfo').innerHTML = '';
  // Reset group fields
  const groupIdEl = getLetterGenEl('letterGenGroupId');
  if (groupIdEl) groupIdEl.value = '';
  const groupLabelEl = getLetterGenEl('letterGenGroupLabel');
  if (groupLabelEl) groupLabelEl.value = '';
  letterGenHideGroupPanel();
  letterGenSetStep(1);
}

// ---- Init ----
function initLetterGen() {
  // Load prompt on init
  letterGenLoadPrompt();

  // Step 1 buttons
  const copyBtn = getLetterGenEl('letterGenCopyPromptBtn');
  if (copyBtn) copyBtn.addEventListener('click', letterGenCopyPrompt);

  const goStep2Btn = getLetterGenEl('letterGenGoStep2Btn');
  if (goStep2Btn) goStep2Btn.addEventListener('click', () => letterGenSetStep(2));

  // Step 2 buttons
  const applyBtn = getLetterGenEl('letterGenApplyJsonBtn');
  if (applyBtn) applyBtn.addEventListener('click', letterGenApplyJson);

  const backStep1Btn = getLetterGenEl('letterGenBackStep1Btn');
  if (backStep1Btn) backStep1Btn.addEventListener('click', () => letterGenSetStep(1));

  // Group DOCX download button
  const groupDocxBtn = getLetterGenEl('letterGenDownloadGroupDocxBtn');
  if (groupDocxBtn) groupDocxBtn.addEventListener('click', letterGenDownloadGroupDocx);

  // Step 3 tabs
  const tabMain = getLetterGenEl('letterGenTabMain');
  if (tabMain) tabMain.addEventListener('click', letterGenShowMainTab);

  const tabRefusal = getLetterGenEl('letterGenTabRefusal');
  if (tabRefusal) tabRefusal.addEventListener('click', letterGenShowRefusalTab);

  // Step 3 download buttons
  const dlMain = getLetterGenEl('letterGenDownloadMainBtn');
  if (dlMain) dlMain.addEventListener('click', () => letterGenDownloadDocx('main'));

  const dlRefusal = getLetterGenEl('letterGenDownloadRefusalBtn');
  if (dlRefusal) dlRefusal.addEventListener('click', () => letterGenDownloadDocx('refusal'));

  // Step 3 navigation
  const backStep2Btn = getLetterGenEl('letterGenBackStep2Btn');
  if (backStep2Btn) backStep2Btn.addEventListener('click', () => letterGenSetStep(2));

  const startOverBtn = getLetterGenEl('letterGenStartOverBtn');
  if (startOverBtn) startOverBtn.addEventListener('click', letterGenStartOver);

  // Steps bar click navigation
  document.querySelectorAll('.letter-step').forEach(el => {
    el.addEventListener('click', () => {
      const s = parseInt(el.dataset.letterStep);
      // Only allow going back, or forward if already visited
      if (s <= letterGenCurrentStep) {
        letterGenSetStep(s);
      }
    });
  });
}
