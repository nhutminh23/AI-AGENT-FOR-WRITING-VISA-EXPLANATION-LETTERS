/**
 * IMMI AutoFill — ISOLATED WORLD content script
 * 
 * Handles: data fetching (chrome.runtime.sendMessage), UI panel
 * Sends fill requests to immi-filler.js (MAIN world) via postMessage
 */

(function() {
    'use strict';

    if (window.__immiContentScriptV2) return;
    window.__immiContentScriptV2 = true;

    const HUB_URL = "http://127.0.0.1:8000/australia/api/active-profile";
    let applicantData = null;
    let currentPage = null;

    // ==================== DETECT PAGE ====================
    function detectPage() {
        const pageLabel = document.querySelector('#_2a0b0a0a0c0');
        if (pageLabel) {
            const m = pageLabel.textContent.trim().match(/^(\d+)\s*\/\s*\d+$/);
            if (m) return parseInt(m[1]);
        }
        const labels = document.querySelectorAll('span.wc-label, .wc-label');
        for (const lbl of labels) {
            const m = lbl.textContent.trim().match(/^(\d+)\s*\/\s*\d+$/);
            if (m) return parseInt(m[1]);
        }
        return null;
    }

    // ==================== FETCH DATA VIA BACKGROUND.JS ====================
    async function fetchProfile() {
        try {
            const response = await chrome.runtime.sendMessage({
                action: 'fetchHubData',
                url: HUB_URL
            });
            if (response && response.data) {
                console.log('[IMMI Hub] ✅ Profile loaded:', response.data.applicant_name);
                return response.data;
            } else {
                console.warn('[IMMI Hub] No data:', response?.error);
                return null;
            }
        } catch (e) {
            console.warn('[IMMI Hub] sendMessage failed:', e.message);
            return null;
        }
    }

    // ==================== FLOATING PANEL ====================
    function createPanel() {
        const oldPanel = document.getElementById('immi-hub-panel');
        if (oldPanel) oldPanel.remove();

        const panelEl = document.createElement('div');
        panelEl.id = 'immi-hub-panel';
        panelEl.style.cssText = `
            position: fixed; top: 20px; left: 20px; z-index: 999999;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 2px solid #f59e0b; border-radius: 12px;
            padding: 16px; min-width: 280px; max-width: 350px;
            font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
            color: #e2e8f0; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        `;
        panelEl.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div style="font-weight:700; font-size:14px; color:#f59e0b;">🇦🇺 IMMI AutoFill</div>
                <button id="immi-hub-minimize" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:16px;">—</button>
            </div>
            <div id="immi-hub-body">
                <div id="immi-hub-profile" style="font-size:13px; margin-bottom:10px; color:#94a3b8;">⏳ Đang kết nối Hub...</div>
                <div id="immi-hub-page" style="font-size:12px; margin-bottom:12px; color:#64748b;"></div>
                <button id="immi-hub-fill" style="width:100%; padding:12px; background:#f59e0b; color:#000; border:none; border-radius:8px; font-weight:700; font-size:14px; cursor:pointer;">
                    🚀 Auto-Fill Trang Này
                </button>
                <div id="immi-hub-status" style="font-size:12px; margin-top:8px; color:#94a3b8;"></div>
            </div>
        `;
        document.body.appendChild(panelEl);

        document.getElementById('immi-hub-minimize').addEventListener('click', () => {
            const body = document.getElementById('immi-hub-body');
            body.style.display = body.style.display === 'none' ? 'block' : 'none';
        });

        document.getElementById('immi-hub-fill').addEventListener('click', runAutoFill);
    }

    async function updatePanel() {
        const profileEl = document.getElementById('immi-hub-profile');
        const pageEl = document.getElementById('immi-hub-page');
        const fillBtn = document.getElementById('immi-hub-fill');

        applicantData = await fetchProfile();
        currentPage = detectPage();

        if (applicantData && applicantData.applicant_name) {
            profileEl.innerHTML = `🟢 <strong style="color:#4ade80;">${applicantData.applicant_name}</strong>`;
        } else {
            profileEl.innerHTML = `🔴 <span style="color:#f87171;">Chưa có data. Dán JSON ở localhost:8000</span>`;
        }

        if (currentPage) {
            const hasData = applicantData && applicantData[`page_${currentPage}`];
            pageEl.textContent = `📄 Trang ${currentPage} ${hasData ? '✅ Có data' : '⚠️ Không có data cho trang này'}`;
            fillBtn.disabled = !hasData;
            fillBtn.textContent = hasData ? `🚀 Auto-Fill Trang ${currentPage}` : `⚪ Không có data trang ${currentPage}`;
        } else {
            pageEl.textContent = `📄 Không detect được trang số mấy`;
        }
    }

    async function runAutoFill() {
        const statusEl = document.getElementById('immi-hub-status');
        const fillBtn = document.getElementById('immi-hub-fill');

        if (!applicantData || !currentPage) {
            statusEl.textContent = "❌ Không có data hoặc không detect được trang.";
            statusEl.style.color = "#f87171";
            return;
        }

        const pageKey = `page_${currentPage}`;
        const pageData = applicantData[pageKey];
        if (!pageData) {
            statusEl.textContent = `⚠️ Không có data cho ${pageKey}`;
            statusEl.style.color = "#fbbf24";
            return;
        }

        fillBtn.disabled = true;
        fillBtn.textContent = "⏳ Đang điền...";
        statusEl.textContent = "";

        // Listen for completion from MAIN world
        const doneHandler = (event) => {
            if (event.data?.type === 'IMMI_FILL_DONE' && event.data.page === currentPage) {
                window.removeEventListener('message', doneHandler);
                if (event.data.success) {
                    statusEl.textContent = `✅ Đã điền xong trang ${currentPage}! Kiểm tra lại trước khi Next.`;
                    statusEl.style.color = "#4ade80";
                } else {
                    statusEl.textContent = `❌ Lỗi: ${event.data.error}`;
                    statusEl.style.color = "#f87171";
                }
                fillBtn.disabled = false;
                fillBtn.textContent = `🚀 Auto-Fill Trang ${currentPage}`;
            }
        };
        window.addEventListener('message', doneHandler);

        // Send fill request to MAIN world (immi-filler.js)
        window.postMessage({
            type: 'IMMI_FILL_REQUEST',
            page: currentPage,
            data: pageData
        }, '*');

        // Timeout fallback (15 seconds)
        setTimeout(() => {
            window.removeEventListener('message', doneHandler);
            if (fillBtn.disabled) {
                fillBtn.disabled = false;
                fillBtn.textContent = `🚀 Auto-Fill Trang ${currentPage}`;
                if (!statusEl.textContent) {
                    statusEl.textContent = `⏱️ Timeout — kiểm tra Console xem đã fill chưa.`;
                    statusEl.style.color = "#fbbf24";
                }
            }
        }, 15000);
    }

    // ==================== INIT ====================
    async function init() {
        console.log('[IMMI Hub] ISOLATED world: panel + data fetch');
        createPanel();
        await updatePanel();

        setInterval(async () => {
            const newPage = detectPage();
            if (newPage !== currentPage) {
                currentPage = newPage;
                await updatePanel();
            }
        }, 3000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(init, 1500));
    } else {
        setTimeout(init, 1500);
    }
})();
