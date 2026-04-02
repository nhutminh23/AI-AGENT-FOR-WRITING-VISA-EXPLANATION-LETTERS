importScripts('shared/metadata.js', 'shared/storage.js', 'shared/utils.js');

let cachedScripts = [];

async function loadScripts() {
  cachedScripts = await getAllScripts();
}

loadScripts();

chrome.storage.onChanged.addListener(async (changes, namespace) => {
  if (namespace === 'local' && changes[STORAGE_KEY]) {
    const oldScripts = changes[STORAGE_KEY].oldValue || [];
    const newScripts = changes[STORAGE_KEY].newValue || [];
    cachedScripts = newScripts;

    for (const ns of newScripts) {
      const os = oldScripts.find(s => s.id === ns.id);
      if (ns.enabled && (!os || !os.enabled)) {
        injectIntoMatchingTabs(ns);
      }
    }
  }
});

async function injectIntoMatchingTabs(script) {
  try {
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      if (tab.url && scriptMatchesUrl(script, tab.url)) {
        injectSingle(tab.id, script);
      }
    }
  } catch (e) {
    console.error('injectIntoMatchingTabs error:', e);
  }
}

async function injectSingle(tabId, script) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (code) => {
        // Chạy trực tiếp code user script trong MAIN world.
        // Cách này ổn định hơn việc chèn inline <script> trên một số site có CSP chặt.
        (0, eval)(code);
      },
      args: [script.code],
      world: 'MAIN'
    });
  } catch (e) {
    console.warn(`Inject failed for tab ${tabId}:`, e.message);
  }
}

async function injectMatchingScripts(tabId, url) {
  const globalEnabled = await getGlobalEnabled();
  if (!globalEnabled) return;

  await loadScripts();

  for (const script of cachedScripts) {
    if (!script.enabled) continue;
    if (scriptMatchesUrl(script, url)) {
      await injectSingle(tabId, script);
    }
  }
}

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if ((changeInfo.status === 'loading' || changeInfo.status === 'complete') && tab.url && /^https?:/i.test(tab.url)) {
    await injectMatchingScripts(tabId, tab.url);
  }
});

chrome.webNavigation.onCommitted.addListener(async (details) => {
  if (details.frameId !== 0) return;
  if (!details.url || !/^https?:/i.test(details.url)) return;
  await injectMatchingScripts(details.tabId, details.url);
});

chrome.webNavigation.onHistoryStateUpdated.addListener(async (details) => {
  if (details.frameId !== 0) return;
  if (!details.url || !/^https?:/i.test(details.url)) return;
  await injectMatchingScripts(details.tabId, details.url);
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !tab.url || !/^https?:/i.test(tab.url)) return;
    await injectMatchingScripts(tabId, tab.url);
  } catch (e) {
    console.warn('onActivated inject error:', e.message);
  }
});

async function findTargetTabForRun(matchPatterns) {
  const tabs = await chrome.tabs.query({});
  const webTabs = tabs.filter(t => t.id && t.url && /^https?:/i.test(t.url));
  if (webTabs.length === 0) return null;

  if (Array.isArray(matchPatterns) && matchPatterns.length > 0) {
    for (const tab of webTabs) {
      const fakeScript = { meta: { match: matchPatterns } };
      if (scriptMatchesUrl(fakeScript, tab.url)) return tab;
    }
  }

  const activeTabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const active = activeTabs[0];
  if (active && active.url && /^https?:/i.test(active.url)) return active;

  return webTabs[0];
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'getRunningScripts') {
    (async () => {
      try {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tabs[0] || !tabs[0].url) { sendResponse([]); return; }

        const url = tabs[0].url;
        const globalEnabled = await getGlobalEnabled();
        if (!globalEnabled) { sendResponse([]); return; }

        await loadScripts();
        const running = [];
        for (const script of cachedScripts) {
          if (!script.enabled) continue;
          if (scriptMatchesUrl(script, url)) {
            running.push(script.meta?.name || script.name);
          }
        }
        sendResponse(running);
      } catch (e) {
        console.error('getRunningScripts error:', e);
        sendResponse([]);
      }
    })();
    return true;
  }

  if (msg.action === 'runScript') {
    (async () => {
      try {
        const targetTab = await findTargetTabForRun(msg.matchPatterns || []);
        if (!targetTab) {
          sendResponse({ ok: false, error: 'Không tìm thấy tab web để chạy script' });
          return;
        }

        await chrome.scripting.executeScript({
          target: { tabId: targetTab.id },
          func: (code) => {
            (0, eval)(code);
          },
          args: [msg.code],
          world: 'MAIN'
        });
        sendResponse({ ok: true, tabUrl: targetTab.url });
      } catch (e) {
        sendResponse({ ok: false, error: e.message });
      }
    })();
    return true;
  }

  if (msg.action === 'reloadScripts') {
    loadScripts().then(() => sendResponse({ ok: true }));
    return true;
  }
});
