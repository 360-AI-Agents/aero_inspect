async function loadSettings() {
  try {
    const data = await apiGet("/settings/");
    document.getElementById("flagged-threshold").value = data.flagged_threshold;
    document.getElementById("unsafe-threshold").value = data.unsafe_threshold;
    document.getElementById("alert-email").value = data.alert_email || "";
  } catch (err) {
    console.error("Failed to load settings:", err);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const payload = {
    flagged_threshold: Number(document.getElementById("flagged-threshold").value),
    unsafe_threshold: Number(document.getElementById("unsafe-threshold").value),
    alert_email: document.getElementById("alert-email").value.trim(),
  };
  try {
    await authFetch("/settings/", "PUT", payload);
    const status = document.getElementById("save-status");
    status.classList.remove("hidden");
    setTimeout(() => status.classList.add("hidden"), 2000);
  } catch (err) {
    console.error("Failed to save settings:", err);
    alert("Failed to save — admin access required.");
  }
}

document.addEventListener("DOMContentLoaded", loadSettings);