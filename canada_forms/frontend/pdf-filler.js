/**
 * pdf-filler.js — Step 4: Fill PDF and handle download
 *
 * Sends form data to /canada/api/fill
 * and manages the download link.
 */

const PdfFiller = (() => {

    /**
     * Fill the PDF and return result.
     * @param {Object} formFields - Flat form field data from FormBuilder.collectFormData()
     * @returns {Promise<{success: boolean, downloadUrl?: string, filename?: string, error?: string}>}
     */
    async function fillPdf(formFields) {
        const filledCount = Object.keys(formFields).length;

        if (filledCount < 3) {
            return { success: false, error: "Vui lòng điền ít nhất vài trường trước khi tạo PDF" };
        }

        try {
            const res = await fetch("/canada/api/fill", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ form_fields: formFields }),
            });
            const data = await res.json();

            if (!res.ok) {
                return { success: false, error: data.error || "Fill PDF thất bại" };
            }

            return {
                success: true,
                downloadUrl: data.download_url,
                filename: data.filename,
            };
        } catch (e) {
            return { success: false, error: `Lỗi kết nối: ${e.message}` };
        }
    }

    /**
     * Check if the PDF template is available on the server.
     * @returns {Promise<boolean>}
     */
    async function checkTemplate() {
        try {
            const res = await fetch("/canada/api/check-template");
            const data = await res.json();
            return data.available === true;
        } catch {
            return false;
        }
    }

    return { fillPdf, checkTemplate };
})();
