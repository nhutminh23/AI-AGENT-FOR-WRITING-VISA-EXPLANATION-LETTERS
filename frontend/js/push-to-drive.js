// Push-to-Drive: Upload processed files back to Google Drive
// Extracted as separate file to avoid bloating precheck.js

// --------------- Push to Drive Logic ---------------

/**
 * Check if the current input directory was downloaded from Drive
 * by querying /api/processor/drive-folders.
 * If so, show the Push to Drive button.
 */
async function checkDriveFolderStatus() {
  const pushBtn = document.getElementById("pushToDriveBtn");
  if (!pushBtn) return;

  try {
    const res = await fetch("/api/processor/drive-folders");
    const data = await res.json();
    const folders = data.folders || [];

    // Get current input dir
    const inputDir = (document.getElementById("precheckInputDir")?.value || "input").trim();

    // Check if ANY subfolder in current input dir has _meta.json
    const hasDriveFolder = folders.length > 0;

    pushBtn.style.display = hasDriveFolder ? "inline-block" : "none";

    // Store folders data for later use
    window._driveFolders = folders;
  } catch (e) {
    console.warn("Could not check drive folder status:", e);
    pushBtn.style.display = "none";
  }
}

/**
 * Push all processed files from a local input folder back to Google Drive.
 * Shows a folder selection dialog if multiple Drive-sourced folders exist.
 */
async function pushPipelineToDrive() {
  const pushBtn = document.getElementById("pushToDriveBtn");
  const folders = window._driveFolders || [];

  if (folders.length === 0) {
    alert("❌ Không tìm thấy folder nào có _meta.json.\nFolder phải được download từ Drive trước.");
    return;
  }

  // If multiple folders, show selection dialog
  let selectedFolder;
  if (folders.length === 1) {
    selectedFolder = folders[0];
  } else {
    // Build a selection dialog
    const options = folders.map((f, i) =>
      `${i + 1}. ${f.base_name} (${f.file_count} files)`
    ).join("\n");
    const choice = prompt(
      `Có ${folders.length} folder từ Drive. Chọn folder để gửi lên:\n\n${options}\n\nNhập số (1-${folders.length}):`
    );
    if (!choice) return;
    const idx = parseInt(choice, 10) - 1;
    if (isNaN(idx) || idx < 0 || idx >= folders.length) {
      alert("❌ Lựa chọn không hợp lệ.");
      return;
    }
    selectedFolder = folders[idx];
  }

  // Confirm
  const confirmMsg = `📤 Gửi lên Drive:\n\n` +
    `📁 Folder: ${selectedFolder.base_name}\n` +
    `📄 Số file: ${selectedFolder.file_count}\n` +
    `🆔 Drive ID: ${selectedFolder.drive_folder_id}\n\n` +
    `Hệ thống sẽ:\n` +
    `1. Tạo thư mục "Final" trong folder gốc trên Drive\n` +
    `2. Upload tất cả file vào Final/\n` +
    `3. Đổi tên folder thành "... - CHECK"\n` +
    `4. Bot tự động kiểm tra hồ sơ đã đủ chưa\n\n` +
    `Tiếp tục?`;

  if (!confirm(confirmMsg)) return;

  // Disable button and show progress
  pushBtn.disabled = true;
  pushBtn.textContent = "⏳ Đang upload lên Drive...";

  const renameProgress = document.getElementById("renameProgress");
  const renameStatus = document.getElementById("renameStatusText");
  if (renameProgress) renameProgress.style.display = "block";
  if (renameStatus) renameStatus.textContent = "Đang upload file lên Google Drive...";

  try {
    const res = await fetch("/api/processor/push-to-drive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ local_folder: selectedFolder.local_path }),
    });
    const data = await res.json();

    if (!res.ok) {
      const errMsg = data.detail || data.error || "Unknown error";
      alert(`❌ Lỗi: ${errMsg}`);
      if (renameStatus) renameStatus.textContent = `Lỗi: ${errMsg}`;
      return;
    }

    // Success!
    const msg =
      `✅ Đã upload ${data.uploaded_count} file lên Drive thành công!\n\n` +
      `📁 Folder: ${data.base_name}\n` +
      (data.error_count > 0 ? `⚠️ ${data.error_count} file lỗi.\n` : "") +
      `\n🤖 Bot sẽ tự động kiểm tra hồ sơ (trigger -CHECK).`;
    alert(msg);

    if (renameProgress) renameProgress.style.display = "none";

    // Update button state
    pushBtn.textContent = "✅ Đã gửi lên Drive!";
    pushBtn.style.background = "#6b7280";
    pushBtn.disabled = true;

    // Refresh drive folders list
    checkDriveFolderStatus();

  } catch (e) {
    alert(`❌ Lỗi kết nối: ${e.message}`);
    if (renameStatus) renameStatus.textContent = `Lỗi: ${e.message}`;
  } finally {
    if (pushBtn.textContent.includes("⏳")) {
      pushBtn.disabled = false;
      pushBtn.textContent = "📤 Gửi lên Drive";
    }
  }
}
