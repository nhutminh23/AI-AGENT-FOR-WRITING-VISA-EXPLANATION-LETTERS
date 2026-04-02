// ==================== AUSTRALIA AUTOFILL IMMI HUB ====================

// DOM Elements
const auCopyGrokPromptBtn = document.getElementById("auCopyGrokPromptBtn");
const auCopyStatus = document.getElementById("auCopyStatus");
const auJsonInput = document.getElementById("auJsonInput");
const auSaveProfileBtn = document.getElementById("auSaveProfileBtn");
const auSaveStatus = document.getElementById("auSaveStatus");
const auActiveProfile = document.getElementById("auActiveProfile");
const auProfileList = document.getElementById("auProfileList");

// ==================== STEP 1: Copy Grok Prompt ====================
if (auCopyGrokPromptBtn) {
  auCopyGrokPromptBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/australia/api/grok-prompt-immi");
      const data = await res.json();
      if (!res.ok) {
        auCopyStatus.textContent = `❌ ${data.error}`;
        auCopyStatus.style.color = "#f87171";
        return;
      }
      await navigator.clipboard.writeText(data.prompt);
      auCopyStatus.textContent = "✅ Đã copy prompt! Sang grok.com dán vào nhé.";
      auCopyStatus.style.color = "#4ade80";
      setTimeout(() => { auCopyStatus.textContent = ""; }, 5000);
    } catch (e) {
      auCopyStatus.textContent = `❌ Lỗi: ${e.message}`;
      auCopyStatus.style.color = "#f87171";
    }
  });
}

// ==================== STEP 2: Save Profile ====================
if (auSaveProfileBtn) {
  auSaveProfileBtn.addEventListener("click", async () => {
    const raw = (auJsonInput?.value || "").trim();
    if (!raw) {
      auSaveStatus.textContent = "⚠️ Chưa có JSON. Dán output từ Grok vào.";
      auSaveStatus.style.color = "#fbbf24";
      return;
    }

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      auSaveStatus.textContent = `❌ JSON không hợp lệ: ${e.message}`;
      auSaveStatus.style.color = "#f87171";
      return;
    }

    auSaveProfileBtn.disabled = true;
    auSaveProfileBtn.textContent = "⏳ Đang lưu...";
    auSaveStatus.textContent = "";

    try {
      const res = await fetch("/australia/api/active-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      const data = await res.json();
      if (!res.ok) {
        auSaveStatus.textContent = `❌ ${data.error}`;
        auSaveStatus.style.color = "#f87171";
        return;
      }

      auSaveStatus.textContent = `✅ Đã lưu ${data.total_saved} người. Active: ${data.active}`;
      auSaveStatus.style.color = "#4ade80";
      loadAuProfiles();
    } catch (e) {
      auSaveStatus.textContent = `❌ Lỗi: ${e.message}`;
      auSaveStatus.style.color = "#f87171";
    } finally {
      auSaveProfileBtn.disabled = false;
      auSaveProfileBtn.textContent = "✅ Lưu & Kích hoạt";
    }
  });
}

// ==================== STEP 3: Profile Management ====================
window.loadAuProfiles = async function() {
  try {
    const res = await fetch("/australia/api/profiles");
    const data = await res.json();

    // Update active display
    if (data.active) {
      auActiveProfile.innerHTML = `
        <div style="display:flex; align-items:center; gap:12px;">
          <span style="font-size:24px;">🟢</span>
          <div>
            <div style="font-weight:600; font-size:16px; color:#4ade80;">${data.active}</div>
            <div style="font-size:12px; color:#94a3b8;">Extension sẽ điền data cho người này trên IMMI</div>
          </div>
        </div>`;
    } else {
      auActiveProfile.innerHTML = `<strong>Chưa có ai.</strong> Dán JSON ở bước 2 để bắt đầu.`;
    }

    // Render profile buttons
    if (auProfileList && data.profiles && data.profiles.length > 0) {
      auProfileList.innerHTML = data.profiles.map(p => `
        <button class="btn" onclick="switchAuProfile('${p.name}')" 
          style="padding:8px 16px; border-radius:8px; font-size:13px; cursor:pointer;
            background:${p.is_active ? '#16a34a' : '#334155'}; 
            color:${p.is_active ? 'white' : '#e2e8f0'}; 
            border:${p.is_active ? '2px solid #4ade80' : '1px solid #475569'};">
          ${p.is_active ? '🟢' : '⚪'} ${p.name}
        </button>
      `).join("");
    } else if (auProfileList) {
      auProfileList.innerHTML = "";
    }
  } catch (e) {
    console.warn("loadAuProfiles error:", e);
  }
}

window.switchAuProfile = async function(name) {
  try {
    const res = await fetch(`/australia/api/set-active/${encodeURIComponent(name)}`, {
      method: "POST",
    });
    const data = await res.json();
    if (res.ok) {
      loadAuProfiles();
    } else {
      alert(`Lỗi chuyển profile: ${data.error}`);
    }
  } catch (e) {
    alert(`Lỗi: ${e.message}`);
  }
}
