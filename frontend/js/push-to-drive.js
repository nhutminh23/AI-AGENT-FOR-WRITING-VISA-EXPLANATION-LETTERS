// Push-to-Drive: Upload processed files back to Google Drive
// Extracted as separate file to avoid bloating precheck.js

// --------------- Push to Drive Logic ---------------

function _setPushButtonReady(pushBtn, folderCount) {
  if (!pushBtn) return;
  if (folderCount <= 0) {
    pushBtn.style.display = "none";
    return;
  }

  const suffix = folderCount === 1 ? "folder" : "folders";
  pushBtn.style.display = "inline-block";
  pushBtn.disabled = false;
  pushBtn.style.background = "#4f46e5";
  pushBtn.textContent = `📤 Gửi lên Drive (${folderCount} ${suffix})`;
  pushBtn.title = "Upload tất cả folder local có _meta.json lên đúng folder gốc trên Google Drive";
}

async function _fetchDriveFolders() {
  const res = await fetch("/api/processor/drive-folders");
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "Không lấy được danh sách folder từ Drive");
  }
  return data.folders || [];
}

async function _hasRealInputFiles(inputDir = "input") {
  const res = await fetch(`/api/files?input_dir=${encodeURIComponent(inputDir)}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "Không đọc được danh sách file input");
  }

  const files = Array.isArray(data.files) ? data.files : [];
  const realFiles = files.filter((f) => {
    const name = String(f?.name || "");
    return name && !name.startsWith(".") && !name.startsWith("_") && name !== "_meta.json";
  });
  return realFiles.length > 0;
}

/**
 * Check if the current input directory was downloaded from Drive
 * by querying /api/processor/drive-folders.
 * If so, show the Push to Drive button.
 */
async function checkDriveFolderStatus() {
  const pushBtn = document.getElementById("pushToDriveBtn");
  if (!pushBtn) return [];

  try {
    const folders = await _fetchDriveFolders();
    window._driveFolders = folders;

    // Avoid overriding loading state while an upload batch is running.
    if (pushBtn.dataset.uploading !== "true") {
      _setPushButtonReady(pushBtn, folders.length);
    }

    return folders;
  } catch (e) {
    console.warn("Could not check drive folder status:", e);
    const cachedFolders = Array.isArray(window._driveFolders) ? window._driveFolders : [];
    if (cachedFolders.length > 0 && pushBtn.dataset.uploading !== "true") {
      _setPushButtonReady(pushBtn, cachedFolders.length);
    } else {
      pushBtn.style.display = "none";
    }
    return cachedFolders;
  }
}

/**
 * Push all processed files from every Drive-linked local folder back to Google Drive.
 * No folder picker prompt: each local folder uploads to its own target by _meta.json.
 */
async function pushPipelineToDrive() {
  const pushBtn = document.getElementById("pushToDriveBtn");
  if (!pushBtn || pushBtn.dataset.uploading === "true") return;

  let folders = await checkDriveFolderStatus();
  if (folders.length === 0) {
    folders = window._driveFolders || [];
  }

  if (folders.length === 0) {
    alert("❌ Không tìm thấy folder nào có _meta.json.\nFolder phải được download từ Drive trước.");
    return;
  }

  const preview = folders
    .slice(0, 8)
    .map((f, i) => `${i + 1}. ${f.base_name} (${f.file_count} files)`)
    .join("\n");
  const more = folders.length > 8 ? `\n... và ${folders.length - 8} folder nữa` : "";

  const confirmMsg = `📤 Gửi lên Drive tất cả ${folders.length} folder:\n\n` +
    `${preview}${more}\n\n` +
    `Hệ thống sẽ:\n` +
    `1. Tự map từng folder local vào đúng folder gốc trên Drive bằng _meta.json\n` +
    `2. Tạo thư mục "Final" và upload toàn bộ file của từng folder\n` +
    `3. Đổi trạng thái folder trên Drive theo flow tương ứng\n\n` +
    `Tiếp tục?`;

  if (!confirm(confirmMsg)) return;

  pushBtn.dataset.uploading = "true";
  pushBtn.disabled = true;
  pushBtn.style.background = "#6366f1";
  pushBtn.textContent = `⏳ Đang upload 0/${folders.length}...`;

  const renameProgress = document.getElementById("renameProgress");
  const renameStatus = document.getElementById("renameStatusText");
  if (renameProgress) renameProgress.style.display = "block";
  if (renameStatus) renameStatus.textContent = `Đang upload 0/${folders.length} folder...`;

  const successes = [];
  const failures = [];
  let totalUploaded = 0;
  let totalUploadErrors = 0;

  for (let i = 0; i < folders.length; i++) {
    const folder = folders[i];
    pushBtn.textContent = `⏳ Đang upload ${i + 1}/${folders.length}...`;
    if (renameStatus) {
      renameStatus.textContent = `Đang upload ${i + 1}/${folders.length}: ${folder.base_name}`;
    }

    try {
      const res = await fetch("/api/processor/push-to-drive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ local_folder: folder.local_path }),
      });
      const data = await res.json();

      if (!res.ok) {
        const errMsg = data.detail || data.error || "Unknown error";
        failures.push({ base_name: folder.base_name, error: errMsg });
        continue;
      }

      successes.push({
        base_name: data.base_name || folder.base_name,
        uploaded_count: data.uploaded_count || 0,
        error_count: data.error_count || 0,
      });
      totalUploaded += data.uploaded_count || 0;
      totalUploadErrors += data.error_count || 0;
    } catch (e) {
      failures.push({ base_name: folder.base_name, error: e.message || "Network error" });
    }
  }

  if (renameProgress) renameProgress.style.display = "none";
  pushBtn.dataset.uploading = "false";

  const successCount = successes.length;
  const failCount = failures.length;

  if (failCount === 0) {
    const msg =
      `✅ Đã gửi thành công ${successCount}/${folders.length} folder lên Drive!\n\n` +
      `📄 Tổng file upload: ${totalUploaded}\n` +
      (totalUploadErrors > 0 ? `⚠️ Tổng lỗi file: ${totalUploadErrors}\n` : "") +
      `\n🤖 Bot sẽ tự động xử lý trạng thái tiếp theo.`;
    alert(msg);
    if (renameStatus) renameStatus.textContent = `✅ Hoàn tất upload ${successCount}/${folders.length} folder.`;
  } else {
    const topErrors = failures
      .slice(0, 5)
      .map((f, i) => `${i + 1}. ${f.base_name}: ${f.error}`)
      .join("\n");
    const msg =
      `⚠️ Upload hoàn tất với lỗi một phần.\n\n` +
      `✅ Thành công: ${successCount}/${folders.length} folder\n` +
      `❌ Thất bại: ${failCount} folder\n\n` +
      `${topErrors}` +
      (failures.length > 5 ? `\n... và ${failures.length - 5} lỗi khác` : "") +
      `\n\nBạn có thể bấm lại nút để gửi tiếp các folder còn lỗi.`;
    alert(msg);
    if (renameStatus) renameStatus.textContent = `⚠️ Còn ${failCount} folder lỗi. Bấm lại để retry.`;
  }

  const remainingFolders = await checkDriveFolderStatus();
  if (remainingFolders.length === 0) {
    // If upload is fully done and local input has no real files, clear precheck backup snapshot.
    if (failCount === 0 && typeof clearPrecheckSnapshot === "function") {
      try {
        const hasRealInputFiles = await _hasRealInputFiles("input");
        if (!hasRealInputFiles) {
          clearPrecheckSnapshot();
          window._precheckLastScanData = null;

          const resultsCard = document.getElementById("precheckResultsCard");
          const resultsDiv = document.getElementById("precheckResults");
          const summaryDiv = document.getElementById("precheckSummary");
          const statusText = document.getElementById("precheckStatusText");
          if (resultsDiv) resultsDiv.innerHTML = "";
          if (summaryDiv) summaryDiv.innerHTML = "";
          if (resultsCard) resultsCard.style.display = "none";
          if (statusText) {
            statusText.textContent = "✅ Đã gửi xong lên Drive và input hiện không còn file nào.";
          }
        }
      } catch (e) {
        console.warn("Could not verify input emptiness after push:", e);
      }
    }

    pushBtn.style.display = "inline-block";
    pushBtn.style.background = "#6b7280";
    pushBtn.textContent = "✅ Đã gửi lên Drive!";
    pushBtn.disabled = true;
  }
}
