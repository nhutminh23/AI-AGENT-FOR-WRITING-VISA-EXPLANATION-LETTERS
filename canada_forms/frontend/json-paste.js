/**
 * json-paste.js — Step 2: Parse and validate JSON from Grok
 *
 * Handles textarea input, strips markdown code blocks,
 * validates structure, and returns parsed data.
 */

const JsonPaste = (() => {

    /**
     * Parse JSON text, handling markdown code blocks.
     * @param {string} raw - Raw text from textarea
     * @returns {{ success: boolean, data?: object, error?: string }}
     */
    function parseJson(raw) {
        const trimmed = (raw || "").trim();
        if (!trimmed) {
            return { success: false, error: "Vui lòng paste JSON vào textarea" };
        }

        // Strip markdown code block wrappers: ```json ... ```
        let jsonText = trimmed;
        if (jsonText.startsWith("```")) {
            const lines = jsonText.split("\n");
            // Remove first line (```json or ```)
            if (lines[0].startsWith("```")) lines.shift();
            // Remove last line (```)
            if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
            jsonText = lines.join("\n");
        }

        // Try to parse
        let parsed;
        try {
            parsed = JSON.parse(jsonText);
        } catch (e) {
            return { success: false, error: `JSON không hợp lệ: ${e.message}` };
        }

        // Validate structure
        if (!parsed || typeof parsed !== "object") {
            return { success: false, error: "JSON phải là một object {}" };
        }

        if (!parsed.applicant) {
            return {
                success: false,
                error: 'JSON thiếu trường "applicant". Kiểm tra lại output từ Grok.',
            };
        }

        return { success: true, data: parsed };
    }

    return { parseJson };
})();
