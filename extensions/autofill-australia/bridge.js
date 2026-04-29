/**
 * Bridge Content Script (ISOLATED world)
 * 
 * Runs in Chrome Extension's isolated world on immi.gov.au pages.
 * Relays fetch requests from the MAIN world script (smart-injector.js)
 * to the background service worker, bypassing Mixed Content restrictions.
 * 
 * Flow: MAIN world → window.postMessage → bridge.js → chrome.runtime.sendMessage → background.js → fetch localhost
 */

window.addEventListener('message', async (event) => {
  // Only accept messages from same window
  if (event.source !== window) return;
  if (!event.data || event.data.type !== 'IMMI_HUB_FETCH') return;

  try {
    const response = await chrome.runtime.sendMessage({
      action: 'fetchHubData',
      url: event.data.url
    });

    window.postMessage({
      type: 'IMMI_HUB_RESPONSE',
      requestId: event.data.requestId,
      data: response.data,
      error: response.error
    }, '*');
  } catch (err) {
    window.postMessage({
      type: 'IMMI_HUB_RESPONSE',
      requestId: event.data.requestId,
      data: null,
      error: err.message
    }, '*');
  }
});
