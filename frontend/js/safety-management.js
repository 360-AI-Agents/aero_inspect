let selectedFile = null;

function handleFileSelect(input) {
  selectedFile = input.files[0] || null;
  const dropZone = document.getElementById("file-drop");
  if (selectedFile) {
    dropZone.querySelector("p.font-semibold").textContent = `Selected: ${selectedFile.name}`;
    dropZone.classList.add("drag-active");
  }
}

async function submitManual(event) {
  event.preventDefault();
  if (!selectedFile) { alert("Please select a file first."); return; }

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("manual_name", document.getElementById("manual-name").value.trim());
  formData.append("organization", document.getElementById("manual-org").value.trim());
  formData.append("region", document.getElementById("manual-region").value.trim());
  formData.append("version", document.getElementById("manual-version").value.trim());

  try {
    const res = await fetch(`${API_BASE}/safety-manuals/`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${getToken()}` },
      body: formData,
    });
    if (res.status === 401 || res.status === 403) { clearSession(); window.location.href = "login.html"; return; }
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);

    document.getElementById("upload-form").reset();
    selectedFile = null;
    loadManuals();
  } catch (err) {
    console.error("Failed to upload manual:", err);
    alert("Upload failed. Check console for details.");
  }
}

async function loadManuals() {
  try {
    const manuals = await authFetch("/safety-manuals/", "GET");
    renderManuals(manuals);
    loadActiveRules();
  } catch (err) {
    console.error("Failed to load manuals:", err);
  }
}

function renderManuals(manuals) {
  const tbody = document.getElementById("manuals-body");
  tbody.innerHTML = "";
  if (!manuals.length) { document.getElementById("manuals-empty").classList.remove("hidden"); return; }
  document.getElementById("manuals-empty").classList.add("hidden");

  const statusColors = { active: "bg-primary/10 text-primary", uploaded: "bg-blue-50 text-blue-700", processing: "bg-amber-50 text-amber-700", inactive: "bg-gray-100 text-gray-600" };

  manuals.forEach(m => {
    const row = document.createElement("tr");
    row.className = m.status === "active" ? "bg-primary/5" : "hover:bg-[#f2f4f7]";
    const isPdf = m.file_path && m.file_path.toLowerCase().endsWith(".pdf");
    const isProcessing = m.status === "processing";

    row.innerHTML = `
      <td class="px-6 py-4"><p class="font-bold text-sm">${m.manual_name}</p><p class="text-xs text-outline">${m.organization||"—"} · ${m.region||"—"} · v${m.version||"1.0"}</p></td>
      <td class="px-6 py-4"><span class="px-3 py-1 rounded-full text-[11px] font-bold uppercase ${statusColors[m.status]||'bg-gray-100'}">${isProcessing ? "🤖 Extracting..." : m.status}</span></td>
      <td class="px-6 py-4 font-mono text-xs text-outline">${formatDate(m.uploaded_at)}</td>
      <td class="px-6 py-4 text-right whitespace-nowrap">
        ${isPdf ? `<button onclick="extractRulesAI(${m.id})" ${isProcessing ? "disabled" : ""} class="px-3 py-1 border border-tertiary text-tertiary font-bold text-xs rounded hover:bg-tertiary hover:text-white transition-all mr-2 ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}">${isProcessing ? "Working..." : "🤖 Extract Rules"}</button>` : ""}
        ${m.status !== "active" ? `<button onclick="activateManual(${m.id})" class="px-3 py-1 border border-primary text-primary font-bold text-xs rounded hover:bg-primary hover:text-white transition-all">Activate</button>` : `<span class="text-primary text-xs font-bold">● Active</span>`}
        <button onclick="deleteManual(${m.id})" class="ml-2 text-outline hover:text-error transition-colors">🗑</button>
      </td>
    `;
    tbody.appendChild(row);
  });
}

async function loadActiveRules() {
  try {
    const rules = await authFetch("/safety-rules/active", "GET");
    renderActiveRules(rules);
  } catch (err) {
    console.error("Failed to load rules:", err);
  }
}

function renderActiveRules(rules) {
  const tbody = document.getElementById("rules-body");
  tbody.innerHTML = "";

  document.getElementById("rules-count-badge").textContent = `${rules.length} rule${rules.length === 1 ? "" : "s"}`;

  if (!rules.length) {
    document.getElementById("rules-empty").classList.remove("hidden");
    return;
  }
  document.getElementById("rules-empty").classList.add("hidden");

  const severityColors = {
    critical: "bg-red-50 text-error",
    high: "bg-orange-50 text-orange-700",
    medium: "bg-amber-50 text-amber-700",
    low: "bg-primary/10 text-primary",
  };

  rules.forEach(rule => {
    let condition;
    try {
      condition = JSON.parse(rule.condition);
    } catch {
      condition = { type: "unknown" };
    }

    const row = document.createElement("tr");
    row.className = "hover:bg-[#f2f4f7]";
    row.innerHTML = `
      <td class="px-6 py-4"><span class="px-2.5 py-1 bg-[#f2f4f7] text-xs font-bold rounded capitalize">${rule.category.replace(/_/g, " ")}</span></td>
      <td class="px-6 py-4 text-sm">${rule.rule_text}</td>
      <td class="px-6 py-4"><span class="px-2.5 py-1 rounded-full text-[11px] font-bold uppercase ${severityColors[rule.severity] || 'bg-gray-100'}">${rule.severity}</span></td>
      <td class="px-6 py-4 font-mono text-xs text-outline capitalize">${condition.type || "—"}</td>
    `;
    tbody.appendChild(row);
  });
}

async function activateManual(id) {
  try { await authFetch(`/safety-manuals/${id}/activate`, "PATCH"); loadManuals(); }
  catch (err) { console.error("Failed to activate:", err); }
}

async function deleteManual(id) {
  if (!confirm("Delete this manual?")) return;
  try { await authFetch(`/safety-manuals/${id}`, "DELETE"); loadManuals(); }
  catch (err) { console.error("Failed to delete:", err); }
}

async function extractRulesAI(manualId) {
  if (!confirm("Use AI to extract safety rules from this manual? This may take up to a minute.")) return;

  await loadManuals();

  try {
    const result = await authFetch(`/safety-manuals/${manualId}/extract-rules`, "POST");
    alert(`✓ ${result.message}\n\nFound: ${result.rules_found} rule(s)\nSaved: ${result.rules_saved} rule(s)`);
    loadManuals();
  } catch (err) {
    console.error("AI extraction failed:", err);
    alert("AI rule extraction failed. Check the console/backend logs for details.");
    loadManuals();
  }
}

document.addEventListener("DOMContentLoaded", loadManuals);