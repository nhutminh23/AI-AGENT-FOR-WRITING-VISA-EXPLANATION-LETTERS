// ==================== LETTER GEN V3 — Frontend Logic ====================
// Replaces V1/V2 pipeline with: Copy Prompt → Paste JSON → AI Generate → Download DOCX

// ---- State ----
let letterGenCurrentStep = 1;
let letterGenProfile = null;
let letterGenResult = null;

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

// ---- Step 2: Parse & Validate JSON ----
function letterGenParseJson(raw) {
  let text = raw.trim();
  // Strip markdown code block if present
  const jsonBlockMatch = text.match(/```(?:json)?\s*\n?([\s\S]*?)\n?\s*```/);
  if (jsonBlockMatch) {
    text = jsonBlockMatch[1].trim();
  }
  return JSON.parse(text);
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
  try {
    letterGenProfile = letterGenParseJson(input.value);
  } catch(e) {
    status.innerHTML = `<span style="color:#dc2626;">❌ JSON không hợp lệ: ${e.message}</span>`;
    return;
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

  try {
    const res = await fetch('/api/letter-gen/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile: letterGenProfile, additional_context: additionalContext }),
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
        `✅ Đã sinh <strong>2 thư</strong> cho <strong>${data.applicant_name}</strong>: Thư giải trình + Thư giải thích từ chối.`;
    } else {
      getLetterGenEl('letterGenTabs').style.display = 'none';
      getLetterGenEl('letterGenDownloadRefusalBtn').style.display = 'none';
      getLetterGenEl('letterGenResultInfo').innerHTML = 
        `✅ Đã sinh <strong>1 thư</strong> cho <strong>${data.applicant_name}</strong>: Thư giải trình.`;
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
    const data = await res.json();

    if (!res.ok) {
      status.innerHTML = `<span style="color:#dc2626;">❌ ${data.error}</span>`;
      return;
    }

    // Trigger download
    const link = document.createElement('a');
    link.href = data.download_url;
    link.download = data.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    status.innerHTML = `<span style="color:#16a34a;">✅ Đã tải: ${data.filename}</span>`;
    
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
  getLetterGenEl('letterGenJsonInput').value = '';
  getLetterGenEl('letterGenAdditionalContext').value = '';
  getLetterGenEl('letterGenMainText').value = '';
  getLetterGenEl('letterGenRefusalText').value = '';
  getLetterGenEl('letterGenJsonStatus').innerHTML = '';
  getLetterGenEl('letterGenDownloadStatus').innerHTML = '';
  getLetterGenEl('letterGenResultInfo').innerHTML = '';
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
