function generateId() {
  return 'script_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function formatSize(code) {
  if (!code) return '0 B';
  const bytes = new Blob([code]).size;
  if (bytes < 1024) return bytes + ' B';
  return Math.round(bytes / 1024) + ' KB';
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toISOString().split('T')[0];
  } catch {
    return dateStr;
  }
}

function formatDateRelative(dateStr) {
  if (!dateStr) return '-';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const diff = now - d;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return 'Hôm nay';
    if (days === 1) return 'Hôm qua';
    if (days < 7) return days + ' ngày';
    if (days < 30) return Math.floor(days / 7) + ' tuần';
    return formatDate(dateStr);
  } catch {
    return dateStr;
  }
}

function matchUrlPattern(pattern, url) {
  if (!pattern || !url) return false;
  if (pattern === '<all_urls>') return true;

  try {
    let regex = pattern
      .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
      .replace(/\*/g, '.*');
    if (new RegExp('^' + regex + '$', 'i').test(url)) return true;

    // Linh hoạt hơn với URL có query mở rộng, ví dụ:
    // pattern ...?node=Personal1 sẽ vẫn match với ...?node=Personal1&foo=bar
    if (!pattern.includes('*') && pattern.includes('?')) {
      if (url.startsWith(pattern + '&') || url.startsWith(pattern + '#')) return true;
    }

    return false;
  } catch {
    return false;
  }
}

function scriptMatchesUrl(script, url) {
  if (!script) return false;

  // Fallback cho dữ liệu cũ chưa có meta.
  if (!script.meta && typeof parseMetadata === 'function' && script.code) {
    script.meta = parseMetadata(script.code);
  }

  if (!script.meta) return false;

  const matches = script.meta.match || [];
  const matchList = Array.isArray(matches) ? matches : [matches];
  for (const pattern of matchList) {
    if (matchUrlPattern(pattern, url)) return true;
  }
  return false;
}

function getDefaultTemplate() {
  const today = new Date().toISOString().split('T')[0];
  return `// ==UserScript==
// @name         New Script
// @namespace    http://tampermonkey.net/
// @version      ${today}-v1.0
// @description  Mô tả script ở đây
// @author       You
// @match        https://example.com/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=example.com
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ------------------- 🔥 CONFIG - CHỈNH SỬA Ở ĐÂY 🔥 -------------------
    const config = {
        "key1": "value1",
        "key2": "value2"
    };

    // ------------------- CODE CHẠY Ở ĐÂY -------------------
    console.log('Script is running!', config);
})();`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
