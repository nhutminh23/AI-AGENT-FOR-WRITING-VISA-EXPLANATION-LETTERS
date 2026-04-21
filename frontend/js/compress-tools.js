(function () {
  const STORAGE_KEY_ROOT = "compress.rootPath";

  let initialized = false;
  let lastScanData = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function el() {
    return {
      section: byId("compressSection"),
      rootPath: byId("compressRootPath"),
      maxMb: byId("compressMaxMb"),
      pickBtn: byId("compressPickFolderBtn"),
      scanBtn: byId("compressScanBtn"),
      scanStatus: byId("compressScanStatus"),
      resultsCard: byId("compressResultsCard"),
      summary: byId("compressSummary"),
      tableWrap: byId("compressResultsTableWrap"),
      actionStatus: byId("compressActionStatus"),
      compressAllBtn: byId("compressAllBtn"),
    };
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatBytes(bytes) {
    const n = Number(bytes || 0);
    if (!Number.isFinite(n) || n <= 0) return "0 B";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(2)} KB`;
    return `${(n / (1024 * 1024)).toFixed(2)} MB`;
  }

  function setScanStatus(message, color) {
    const dom = el();
    if (!dom.scanStatus) return;
    dom.scanStatus.style.color = color || "#94a3b8";
    dom.scanStatus.innerHTML = message;
  }

  function setActionStatus(message, color) {
    const dom = el();
    if (!dom.actionStatus) return;
    dom.actionStatus.style.color = color || "#94a3b8";
    dom.actionStatus.innerHTML = message;
  }

  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  function renderScanResults(data) {
    const dom = el();
    if (!dom.resultsCard || !dom.summary || !dom.tableWrap || !dom.compressAllBtn) return;

    const files = Array.isArray(data?.over_limit_files) ? data.over_limit_files : [];
    const maxMb = Number(data?.max_mb || dom.maxMb?.value || 5);

    dom.resultsCard.style.display = "";

    dom.summary.innerHTML = [
      `📂 Root: <strong>${escapeHtml(data?.root_path || "")}</strong>`,
      `• Tổng file đã quét: <strong>${Number(data?.scanned_total || 0)}</strong>`,
      `• File nằm trong thư mục Final: <strong>${Number(data?.scanned_in_final || 0)}</strong>`,
      `• File > ${maxMb}MB: <strong>${files.length}</strong>`,
    ].join(" ");

    if (files.length === 0) {
      dom.compressAllBtn.disabled = true;
      dom.tableWrap.innerHTML = `<div style="padding:12px; border:1px solid #334155; border-radius:8px; color:#22c55e;">✅ Không có file nào trong Final vượt ${maxMb}MB.</div>`;
      return;
    }

    dom.compressAllBtn.disabled = false;

    const rows = files.map((item, idx) => {
      const encodedPath = encodeURIComponent(item.abs_path || "");
      const supportTag = item.compress_supported
        ? '<span style="color:#22c55e;">Hỗ trợ</span>'
        : '<span style="color:#f59e0b;">Không hỗ trợ</span>';

      const actionBtn = item.compress_supported
        ? `<button class="compress-one-btn" data-file-path="${encodedPath}" style="padding:6px 10px; font-size:12px; background:#2563eb;">Nén file</button>`
        : `<button disabled style="padding:6px 10px; font-size:12px; background:#475569; cursor:not-allowed;">Không hỗ trợ</button>`;

      return `
        <tr>
          <td style="padding:8px; border-bottom:1px solid #1f2937; text-align:center;">${idx + 1}</td>
          <td style="padding:8px; border-bottom:1px solid #1f2937; white-space:nowrap;">${escapeHtml(item.rel_path || item.name || "")}</td>
          <td style="padding:8px; border-bottom:1px solid #1f2937; text-align:right;">${formatBytes(item.size_bytes)}</td>
          <td style="padding:8px; border-bottom:1px solid #1f2937; text-align:center;">${escapeHtml(item.ext || "")}</td>
          <td style="padding:8px; border-bottom:1px solid #1f2937; text-align:center;">${supportTag}</td>
          <td style="padding:8px; border-bottom:1px solid #1f2937; text-align:center;">${actionBtn}</td>
        </tr>
      `;
    }).join("");

    dom.tableWrap.innerHTML = `
      <table style="width:100%; border-collapse:collapse; font-size:13px; min-width:900px;">
        <thead>
          <tr style="background:#111827; color:#cbd5e1;">
            <th style="padding:8px; border-bottom:1px solid #334155; width:60px;">#</th>
            <th style="padding:8px; border-bottom:1px solid #334155; text-align:left;">Đường dẫn tương đối</th>
            <th style="padding:8px; border-bottom:1px solid #334155; text-align:right; width:130px;">Kích thước</th>
            <th style="padding:8px; border-bottom:1px solid #334155; width:90px;">Đuôi</th>
            <th style="padding:8px; border-bottom:1px solid #334155; width:120px;">Nén được</th>
            <th style="padding:8px; border-bottom:1px solid #334155; width:140px;">Thao tác</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  function getPayloadFromForm() {
    const dom = el();
    const rootPath = (dom.rootPath?.value || "").trim();
    const maxMbRaw = Number(dom.maxMb?.value || 5);
    const maxMb = Number.isFinite(maxMbRaw) && maxMbRaw > 0 ? maxMbRaw : 5;
    return { root_path: rootPath, max_mb: maxMb };
  }

  async function scanOverLimitFiles() {
    const dom = el();
    const payload = getPayloadFromForm();

    if (!payload.root_path) {
      setScanStatus("❌ Vui lòng chọn hoặc nhập thư mục gốc.", "#ef4444");
      return;
    }

    if (dom.scanBtn) {
      dom.scanBtn.disabled = true;
      dom.scanBtn.textContent = "⏳ Đang quét...";
    }

    setActionStatus("");
    setScanStatus("⏳ Đang quét đệ quy file trong các thư mục Final...", "#f59e0b");

    try {
      localStorage.setItem(STORAGE_KEY_ROOT, payload.root_path);
      const data = await postJson("/api/compress/scan", payload);
      lastScanData = data;
      renderScanResults(data);

      const overCount = Number(data?.over_limit_count || 0);
      if (overCount > 0) {
        setScanStatus(`⚠️ Tìm thấy <strong>${overCount}</strong> file vượt giới hạn trong Final.`, "#f59e0b");
      } else {
        setScanStatus("✅ Quét xong, không có file vượt giới hạn trong Final.", "#22c55e");
      }
    } catch (err) {
      setScanStatus(`❌ Lỗi quét: ${escapeHtml(err.message)}`, "#ef4444");
    } finally {
      if (dom.scanBtn) {
        dom.scanBtn.disabled = false;
        dom.scanBtn.textContent = "🔍 Quét file trong Final";
      }
    }
  }

  async function pickFolderNative() {
    const dom = el();
    if (dom.pickBtn) {
      dom.pickBtn.disabled = true;
      dom.pickBtn.textContent = "⏳ Đang mở...";
    }

    try {
      const data = await postJson("/api/compress/pick-folder", {});
      if (data.status === "cancelled") {
        setScanStatus("ℹ️ Bạn đã hủy chọn thư mục.", "#94a3b8");
        return;
      }
      if (dom.rootPath) {
        dom.rootPath.value = data.folder_path || "";
      }
      if (data.folder_path) {
        localStorage.setItem(STORAGE_KEY_ROOT, data.folder_path);
      }
      setScanStatus(`✅ Đã chọn thư mục: <strong>${escapeHtml(data.folder_path || "")}</strong>`, "#22c55e");
    } catch (err) {
      setScanStatus(`❌ Không mở được hộp thoại chọn thư mục: ${escapeHtml(err.message)}. Bạn có thể nhập đường dẫn thủ công.`, "#ef4444");
    } finally {
      if (dom.pickBtn) {
        dom.pickBtn.disabled = false;
        dom.pickBtn.textContent = "📁 Chọn thư mục";
      }
    }
  }

  async function compressOneFile(absPath, btn) {
    if (!absPath) return;
    const dom = el();
    const payloadBase = getPayloadFromForm();

    const originalLabel = btn?.textContent || "Nén file";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Đang nén...";
    }

    setActionStatus(`⏳ Đang nén file: ${escapeHtml(absPath)}`, "#f59e0b");

    try {
      const data = await postJson("/api/compress/file", {
        file_path: absPath,
        max_mb: payloadBase.max_mb,
      });

      if (data.status === "done") {
        setActionStatus(
          `✅ Nén thành công: <strong>${escapeHtml(data.rel_path || data.file_path || "")}</strong> · ${formatBytes(data.old_size_bytes)} → ${formatBytes(data.new_size_bytes)} · Method: ${escapeHtml(data.method || "")}`,
          "#22c55e",
        );
      } else if (data.status === "skipped") {
        setActionStatus(`ℹ️ Bỏ qua: ${escapeHtml(data.detail || "Không cần nén")}`, "#94a3b8");
      } else {
        setActionStatus(`❌ Không nén được: ${escapeHtml(data.detail || "Unknown error")}`, "#ef4444");
      }

      await scanOverLimitFiles();
    } catch (err) {
      setActionStatus(`❌ Lỗi nén file: ${escapeHtml(err.message)}`, "#ef4444");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = originalLabel;
      }
    }
  }

  async function compressAllFiles() {
    const dom = el();
    const payload = getPayloadFromForm();
    if (!payload.root_path) {
      setActionStatus("❌ Vui lòng chọn hoặc nhập thư mục gốc trước.", "#ef4444");
      return;
    }

    if (dom.compressAllBtn) {
      dom.compressAllBtn.disabled = true;
      dom.compressAllBtn.textContent = "⏳ Đang nén tất cả...";
    }

    setActionStatus("⏳ Đang nén tất cả file vượt giới hạn trong Final...", "#f59e0b");

    try {
      const data = await postJson("/api/compress/all", payload);
      const total = Number(data.total || 0);
      const ok = Number(data.success_count || 0);
      const fail = Number(data.failed_count || 0);
      const skipped = Number(data.skipped_count || 0);

      setActionStatus(
        `✅ Hoàn tất batch nén: tổng ${total} file · thành công ${ok} · thất bại ${fail} · bỏ qua ${skipped}`,
        fail > 0 ? "#f59e0b" : "#22c55e",
      );

      await scanOverLimitFiles();
    } catch (err) {
      setActionStatus(`❌ Lỗi nén batch: ${escapeHtml(err.message)}`, "#ef4444");
    } finally {
      if (dom.compressAllBtn) {
        dom.compressAllBtn.disabled = false;
        dom.compressAllBtn.textContent = "🗜️ Nén tất cả file > giới hạn";
      }
    }
  }

  function attachEventsOnce() {
    const dom = el();
    if (!dom.section) return;

    if (dom.pickBtn) {
      dom.pickBtn.addEventListener("click", pickFolderNative);
    }
    if (dom.scanBtn) {
      dom.scanBtn.addEventListener("click", scanOverLimitFiles);
    }
    if (dom.compressAllBtn) {
      dom.compressAllBtn.addEventListener("click", compressAllFiles);
    }

    if (dom.tableWrap && !dom.tableWrap.dataset.boundCompressActions) {
      dom.tableWrap.dataset.boundCompressActions = "1";
      dom.tableWrap.addEventListener("click", async (event) => {
        const btn = event.target.closest(".compress-one-btn");
        if (!btn) return;
        const encoded = btn.dataset.filePath || "";
        const absPath = decodeURIComponent(encoded);
        await compressOneFile(absPath, btn);
      });
    }
  }

  window.initCompressToolsSection = function initCompressToolsSection() {
    const dom = el();
    if (!dom.section) return;

    if (!initialized) {
      attachEventsOnce();
      initialized = true;
    }

    if (dom.rootPath && !dom.rootPath.value) {
      const cached = localStorage.getItem(STORAGE_KEY_ROOT) || "";
      if (cached) dom.rootPath.value = cached;
    }

    if (!lastScanData) {
      setScanStatus("Chưa quét. Chọn thư mục rồi bấm \"Quét file trong Final\".", "#94a3b8");
      setActionStatus("");
    }
  };
})();
