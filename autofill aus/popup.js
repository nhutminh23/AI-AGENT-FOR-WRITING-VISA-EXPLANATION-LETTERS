document.addEventListener('DOMContentLoaded', async () => {
  const globalEnabled = await getGlobalEnabled();
  updateToggle(globalEnabled);

  chrome.runtime.sendMessage({ action: 'getRunningScripts' }, (scripts) => {
    updateRunningScripts(scripts || []);
  });

  document.getElementById('globalToggle').addEventListener('click', async () => {
    const current = await getGlobalEnabled();
    await setGlobalEnabled(!current);
    updateToggle(!current);
  });

  document.getElementById('createScript').addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('editor.html?new=true') });
    window.close();
  });

  document.getElementById('dashboard').addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('dashboard.html') });
    window.close();
  });

  document.getElementById('searchScripts').addEventListener('click', () => {
    chrome.tabs.create({ url: 'https://www.userscript.zone/' });
    window.close();
  });

  document.getElementById('utilities').addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('dashboard.html') });
    window.close();
  });
});

function updateToggle(enabled) {
  const el = document.getElementById('globalToggle');
  const icon = el.querySelector('.toggle-icon');
  const label = el.querySelector('.label');

  if (enabled) {
    el.className = 'menu-item toggle-item enabled';
    icon.textContent = '✓';
    label.textContent = 'Đã bật';
  } else {
    el.className = 'menu-item toggle-item disabled-state';
    icon.textContent = '✗';
    label.textContent = 'Đã tắt';
  }
}

function updateRunningScripts(scripts) {
  const el = document.getElementById('runningScripts');
  const icon = el.querySelector('.rs-icon');
  const label = el.querySelector('.label');

  if (!scripts || scripts.length === 0) {
    icon.textContent = '🔗';
    label.textContent = 'Không có tập lệnh nào đang chạy';
    el.classList.add('disabled');
  } else {
    icon.textContent = scripts.length.toString();
    el.classList.remove('disabled');
    label.innerHTML = scripts
      .map(s => `<div class="running-script-item">▸ ${escapeHtml(s)}</div>`)
      .join('');
  }
}
