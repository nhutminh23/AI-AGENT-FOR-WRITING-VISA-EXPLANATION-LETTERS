let currentScript = null;
const editor = document.getElementById('codeEditor');
const lineNumbers = document.getElementById('lineNumbers');

document.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  const scriptId = params.get('id');
  const isNew = params.get('new') === 'true';

  if (isNew) {
    editor.value = getDefaultTemplate();
    document.getElementById('scriptInfo').textContent = 'New Script';
    document.title = 'Autofill úc - New Script';
  } else if (scriptId) {
    currentScript = await getScript(scriptId);
    if (currentScript) {
      editor.value = currentScript.code;
      const name = currentScript.meta?.name || currentScript.name;
      document.getElementById('scriptInfo').textContent = name;
      document.title = 'Autofill úc - ' + name;
    } else {
      editor.value = '// Script không tồn tại';
      document.getElementById('scriptInfo').textContent = 'Lỗi';
    }
  }

  updateLineNumbers();
  updateCursorPosition();
  updateCharCount();

  editor.addEventListener('input', () => {
    updateLineNumbers();
    updateCharCount();
  });
  editor.addEventListener('scroll', syncScroll);
  editor.addEventListener('keydown', handleKeydown);
  editor.addEventListener('click', updateCursorPosition);
  editor.addEventListener('keyup', updateCursorPosition);

  document.getElementById('saveBtn').addEventListener('click', saveCurrentScript);
  document.getElementById('runBtn').addEventListener('click', runCurrentScript);
  document.getElementById('deleteBtn').addEventListener('click', deleteCurrentScript);
});

function updateLineNumbers() {
  const lines = editor.value.split('\n').length;
  lineNumbers.textContent = Array.from({ length: lines }, (_, i) => i + 1).join('\n');
}

function syncScroll() {
  lineNumbers.scrollTop = editor.scrollTop;
}

function handleKeydown(e) {
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = editor.selectionStart;
    const end = editor.selectionEnd;

    if (e.shiftKey) {
      const lineStart = editor.value.lastIndexOf('\n', start - 1) + 1;
      const lineText = editor.value.substring(lineStart, start);
      const spaces = lineText.match(/^ {1,4}/);
      if (spaces) {
        editor.value = editor.value.substring(0, lineStart) + editor.value.substring(lineStart + spaces[0].length);
        editor.selectionStart = editor.selectionEnd = start - spaces[0].length;
      }
    } else {
      editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
      editor.selectionStart = editor.selectionEnd = start + 4;
    }
    updateLineNumbers();
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault();
    saveCurrentScript();
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    runCurrentScript();
  }
}

function updateCursorPosition() {
  const text = editor.value.substring(0, editor.selectionStart);
  const lines = text.split('\n');
  const line = lines.length;
  const col = lines[lines.length - 1].length + 1;
  document.getElementById('lineCol').textContent = `Ln ${line}, Col ${col}`;
}

function updateCharCount() {
  const len = editor.value.length;
  document.getElementById('charCount').textContent = len.toLocaleString() + ' ký tự';
}

async function saveCurrentScript() {
  const code = editor.value;
  const meta = parseMetadata(code);

  if (!currentScript) {
    currentScript = {
      id: generateId(),
      name: meta.name || 'Untitled Script',
      code,
      enabled: true,
      lastUpdate: new Date().toISOString(),
      meta
    };
  } else {
    currentScript.code = code;
    currentScript.meta = meta;
    currentScript.name = meta.name || currentScript.name;
    currentScript.lastUpdate = new Date().toISOString();
  }

  await saveScript(currentScript);
  chrome.runtime.sendMessage({ action: 'reloadScripts' });

  const name = currentScript.meta?.name || currentScript.name;
  document.getElementById('scriptInfo').textContent = name;
  document.title = 'Autofill úc - ' + name;

  showToast('Đã lưu thành công!');
}

async function runCurrentScript() {
  const code = editor.value;
  const meta = parseMetadata(code);
  const matchPatterns = Array.isArray(meta.match) ? meta.match : (meta.match ? [meta.match] : []);

  chrome.runtime.sendMessage({ action: 'runScript', code, matchPatterns }, (response) => {
    if (response?.ok) {
      const where = response.tabUrl ? ` (${response.tabUrl})` : '';
      showToast('Script đã được chạy' + where);
    } else {
      showToast('Lỗi: ' + (response?.error || 'Không thể chạy script'), true);
    }
  });
}

async function deleteCurrentScript() {
  if (!currentScript) {
    showToast('Không có script nào để xóa', true);
    return;
  }
  const name = currentScript.meta?.name || currentScript.name;
  if (confirm(`Xóa "${name}"?`)) {
    await deleteScript(currentScript.id);
    chrome.runtime.sendMessage({ action: 'reloadScripts' });
    showToast('Đã xóa script');
    setTimeout(() => window.close(), 600);
  }
}

function showToast(msg, isError = false) {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }

  toast.textContent = msg;
  toast.classList.toggle('error', isError);
  toast.classList.add('show');

  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 2500);

  document.getElementById('statusText').textContent = msg;
  clearTimeout(window._statusTimer);
  window._statusTimer = setTimeout(() => {
    document.getElementById('statusText').textContent = 'Ready';
  }, 4000);
}
