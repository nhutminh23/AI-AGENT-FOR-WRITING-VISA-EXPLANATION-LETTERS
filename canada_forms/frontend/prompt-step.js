/**
 * prompt-step.js — Step 1: Load and display Grok prompt template
 *
 * Fetches prompt text from /canada/api/prompt-template
 * and provides a Copy to Clipboard button.
 */

const PromptStep = (() => {
    let promptText = "";

    async function loadPrompt() {
        const display = document.getElementById("promptDisplay");
        const copyBtn = document.getElementById("copyPromptBtn");

        try {
            const res = await fetch("/canada/api/prompt-template");
            const data = await res.json();

            if (!res.ok) throw new Error(data.error || "Failed to load prompt");

            promptText = data.prompt;

            // Render prompt in a scrollable pre block
            display.innerHTML = `<pre class="prompt-text">${escapeHtml(promptText)}</pre>`;
            copyBtn.disabled = false;
        } catch (e) {
            display.innerHTML = `<div class="prompt-error">❌ Không tải được prompt: ${e.message}</div>`;
        }
    }

    function copyPrompt() {
        if (!promptText) return false;

        navigator.clipboard.writeText(promptText).then(() => {
            const status = document.getElementById("copyStatus");
            status.className = "status-msg success";
            status.textContent = "✅ Đã copy prompt! Paste vào Grok cùng file hồ sơ.";
            setTimeout(() => { status.textContent = ""; }, 3000);
        });
        return true;
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    return { loadPrompt, copyPrompt };
})();
