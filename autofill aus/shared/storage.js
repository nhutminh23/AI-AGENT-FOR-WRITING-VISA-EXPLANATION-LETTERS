const STORAGE_KEY = 'userscripts';
const GLOBAL_ENABLED_KEY = 'globalEnabled';
const TRASH_KEY = 'userscripts_trash';

async function getAllScripts() {
  const result = await chrome.storage.local.get(STORAGE_KEY);
  return result[STORAGE_KEY] || [];
}

async function getScript(id) {
  const scripts = await getAllScripts();
  return scripts.find(s => s.id === id) || null;
}

async function saveScript(script) {
  const scripts = await getAllScripts();
  const idx = scripts.findIndex(s => s.id === script.id);
  if (idx >= 0) {
    scripts[idx] = script;
  } else {
    scripts.push(script);
  }
  await chrome.storage.local.set({ [STORAGE_KEY]: scripts });
  return script;
}

async function deleteScript(id) {
  const scripts = await getAllScripts();
  const target = scripts.find(s => s.id === id);
  const remaining = scripts.filter(s => s.id !== id);
  await chrome.storage.local.set({ [STORAGE_KEY]: remaining });

  if (target) {
    const trashResult = await chrome.storage.local.get(TRASH_KEY);
    const trash = trashResult[TRASH_KEY] || [];
    target._deletedAt = new Date().toISOString();
    trash.push(target);
    await chrome.storage.local.set({ [TRASH_KEY]: trash });
  }
}

async function getTrash() {
  const result = await chrome.storage.local.get(TRASH_KEY);
  return result[TRASH_KEY] || [];
}

async function restoreFromTrash(id) {
  const trashResult = await chrome.storage.local.get(TRASH_KEY);
  const trash = trashResult[TRASH_KEY] || [];
  const target = trash.find(s => s.id === id);
  if (!target) return;

  const remaining = trash.filter(s => s.id !== id);
  await chrome.storage.local.set({ [TRASH_KEY]: remaining });

  delete target._deletedAt;
  await saveScript(target);
}

async function emptyTrash() {
  await chrome.storage.local.set({ [TRASH_KEY]: [] });
}

async function toggleScript(id) {
  const scripts = await getAllScripts();
  const script = scripts.find(s => s.id === id);
  if (script) {
    script.enabled = !script.enabled;
    await chrome.storage.local.set({ [STORAGE_KEY]: scripts });
    return script.enabled;
  }
  return null;
}

async function getGlobalEnabled() {
  const result = await chrome.storage.local.get(GLOBAL_ENABLED_KEY);
  return result[GLOBAL_ENABLED_KEY] !== false;
}

async function setGlobalEnabled(enabled) {
  await chrome.storage.local.set({ [GLOBAL_ENABLED_KEY]: enabled });
}
