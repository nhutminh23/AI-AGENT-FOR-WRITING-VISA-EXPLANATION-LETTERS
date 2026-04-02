document.addEventListener('DOMContentLoaded', async () => {
  await loadScriptList();
  await loadGlobalToggle();
  setupTabs();
  setupToolbar();
  setupSearch();
  setupTrash();
  setupImportExport();
});

async function loadGlobalToggle() {
  const toggle = document.getElementById('globalToggle');
  toggle.checked = await getGlobalEnabled();
  toggle.addEventListener('change', async () => {
    await setGlobalEnabled(toggle.checked);
  });
}

function setupTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById('tab-' + tab.dataset.tab);
      if (target) target.classList.add('active');
    });
  });
}

function setupToolbar() {
  document.getElementById('addNew').addEventListener('click', openNewEditor);

  const addNewEmpty = document.getElementById('addNewEmpty');
  if (addNewEmpty) addNewEmpty.addEventListener('click', openNewEditor);

  document.getElementById('settingsBtn').addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="settings"]').classList.add('active');
    document.getElementById('tab-settings').classList.add('active');
  });
}

function openNewEditor() {
  chrome.tabs.create({ url: chrome.runtime.getURL('editor.html?new=true') });
}

function setupSearch() {
  const input = document.getElementById('searchInput');
  input.addEventListener('input', () => {
    const query = input.value.toLowerCase();
    document.querySelectorAll('#scriptList tr').forEach(row => {
      const name = row.querySelector('.script-name')?.textContent?.toLowerCase() || '';
      row.style.display = name.includes(query) ? '' : 'none';
    });
  });
}

function setupTrash() {
  document.getElementById('trashBtn').addEventListener('click', async () => {
    await renderTrash();
    document.getElementById('trashModal').style.display = 'flex';
  });

  document.getElementById('closeTrash').addEventListener('click', () => {
    document.getElementById('trashModal').style.display = 'none';
  });

  document.getElementById('trashModal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('trashModal')) {
      document.getElementById('trashModal').style.display = 'none';
    }
  });

  document.getElementById('emptyTrashBtn').addEventListener('click', async () => {
    if (confirm('Xóa vĩnh viễn tất cả script trong thùng rác?')) {
      await emptyTrash();
      await renderTrash();
    }
  });
}

async function renderTrash() {
  const trash = await getTrash();
  const container = document.getElementById('trashList');

  if (trash.length === 0) {
    container.innerHTML = '<div class="trash-empty">Thùng rác trống</div>';
    return;
  }

  container.innerHTML = trash.map(s => `
    <div class="trash-item">
      <span class="trash-item-name">${escapeHtml(s.meta?.name || s.name)}</span>
      <button class="toolbar-btn" data-id="${s.id}" data-action="restore">↩ Khôi phục</button>
    </div>
  `).join('');

  container.querySelectorAll('[data-action="restore"]').forEach(btn => {
    btn.addEventListener('click', async () => {
      await restoreFromTrash(btn.dataset.id);
      chrome.runtime.sendMessage({ action: 'reloadScripts' });
      await renderTrash();
      await loadScriptList();
    });
  });
}

function setupImportExport() {
  document.getElementById('exportBtn').addEventListener('click', async () => {
    const scripts = await getAllScripts();
    const blob = new Blob([JSON.stringify(scripts, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'autofill-uc-scripts.json';
    a.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById('importBtn').addEventListener('click', () => {
    document.getElementById('importFile').click();
  });

  document.getElementById('importFile').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const imported = JSON.parse(text);
      if (!Array.isArray(imported)) throw new Error('Invalid format');

      const existing = await getAllScripts();
      for (const script of imported) {
        if (!script.id) script.id = generateId();
        if (!existing.find(s => s.id === script.id)) {
          script.meta = parseMetadata(script.code || '');
          existing.push(script);
        }
      }
      await chrome.storage.local.set({ [STORAGE_KEY]: existing });
      chrome.runtime.sendMessage({ action: 'reloadScripts' });
      await loadScriptList();
      alert('Nhập thành công ' + imported.length + ' script!');
    } catch (err) {
      alert('Lỗi nhập file: ' + err.message);
    }
    e.target.value = '';
  });
}

async function loadScriptList() {
  const scripts = await getAllScripts();
  const tbody = document.getElementById('scriptList');
  const emptyState = document.getElementById('emptyState');

  if (scripts.length === 0) {
    tbody.innerHTML = '';
    emptyState.style.display = 'block';
    return;
  }

  emptyState.style.display = 'none';

  tbody.innerHTML = scripts.map((script, index) => `
    <tr>
      <td class="col-num">${index + 1}</td>
      <td class="col-toggle">
        <label class="toggle">
          <input type="checkbox" ${script.enabled ? 'checked' : ''} data-id="${script.id}">
          <span class="toggle-slider"></span>
        </label>
      </td>
      <td>
        <span class="script-name" data-id="${script.id}">${escapeHtml(script.meta?.name || script.name)}</span>
      </td>
      <td>${escapeHtml(script.meta?.version || '-')}</td>
      <td>${formatSize(script.code)}</td>
      <td>${formatDateRelative(script.lastUpdate)}</td>
      <td>
        <div class="actions-cell">
          <button class="btn-action btn-edit" data-id="${script.id}" title="Chỉnh sửa">✏️</button>
          <button class="btn-action btn-delete" data-id="${script.id}" title="Xóa">🗑️</button>
        </div>
      </td>
    </tr>
  `).join('');

  tbody.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', async () => {
      await toggleScript(cb.dataset.id);
      chrome.runtime.sendMessage({ action: 'reloadScripts' });
    });
  });

  tbody.querySelectorAll('.script-name, .btn-edit').forEach(el => {
    el.addEventListener('click', () => {
      chrome.tabs.create({ url: chrome.runtime.getURL(`editor.html?id=${el.dataset.id}`) });
    });
  });

  tbody.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', async () => {
      const name = btn.closest('tr').querySelector('.script-name')?.textContent || 'script';
      if (confirm(`Xóa "${name}"?`)) {
        await deleteScript(btn.dataset.id);
        chrome.runtime.sendMessage({ action: 'reloadScripts' });
        await loadScriptList();
      }
    });
  });
}
