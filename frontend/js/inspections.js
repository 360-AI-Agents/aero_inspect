let currentInspections = [];
let currentEvidenceRecords = [];
let evidencePage = 0;
const EVIDENCE_PAGE_SIZE = 6;
let hlsPlayer = null;

async function loadInspections() {
  try {
    currentInspections = await authFetch("/inspections/?limit=100", "GET");
    renderInspectionTable(currentInspections);
  } catch (err) {
    console.error("Failed to load inspections:", err);
  }
}

function renderInspectionTable(inspections) {
  const tbody = document.getElementById("inspections-body");
  tbody.innerHTML = "";

  if (!inspections.length) {
    document.getElementById("inspections-empty").classList.remove("hidden");
    return;
  }
  document.getElementById("inspections-empty").classList.add("hidden");

  inspections.forEach((insp) => {
    const row = document.createElement("tr");
    row.className = "hover:bg-[#f2f4f7] cursor-pointer transition-colors";
    row.onclick = () => openInspectionDetail(insp.id);
    row.innerHTML = `
      <td class="px-6 py-4 font-semibold text-sm">${insp.inspection_name}</td>
      <td class="px-6 py-4 font-mono text-sm">${insp.workers_detected}</td>
      <td class="px-6 py-4 font-mono text-sm text-error">${insp.total_violations}</td>
      <td class="px-6 py-4 font-mono text-sm">${insp.compliance_score}%</td>
      <td class="px-6 py-4"><span class="px-2.5 py-1 rounded-full text-[11px] font-bold uppercase ${statusBadgeClasses(insp.inspection_status)}">${insp.inspection_status}</span></td>
      <td class="px-6 py-4 font-mono text-xs text-outline text-right">${formatDate(insp.created_at)}</td>
    `;
    tbody.appendChild(row);
  });
}

async function openInspectionDetail(id) {
  try {
    const insp = await authFetch(`/inspections/${id}`, "GET");
    document.getElementById("detail-empty").style.display = "none";
    document.getElementById("detail-panel").style.display = "block";

    document.getElementById("detail-title").textContent = insp.inspection_name;
    document.getElementById("detail-meta").textContent = `Inspection #${insp.id} · ${formatDate(insp.created_at)}`;
    document.getElementById("detail-workers").textContent = insp.workers_detected;
    document.getElementById("detail-violations").textContent = insp.total_violations;
    document.getElementById("detail-compliance").textContent = `${insp.compliance_score}%`;

    const list = document.getElementById("violation-list");
    list.innerHTML = "";

    if (!insp.violations || insp.violations.length === 0) {
      list.innerHTML = `<div class="text-sm text-outline text-center py-4">No violations recorded.</div>`;
    } else {
      insp.violations.forEach((v) => {
        const sevColor = v.severity === "critical" ? "bg-red-50 text-error" :
                          v.severity === "high" ? "bg-orange-50 text-orange-700" :
                          "bg-amber-50 text-amber-700";
        const item = document.createElement("div");
        item.className = "bg-white/60 p-3 rounded-lg border border-white/70 flex justify-between items-start";
        item.innerHTML = `
          <div>
            <p class="font-bold text-sm">${v.violation_name}</p>
            <p class="text-xs text-outline">×${v.count} occurrence(s)</p>
          </div>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase ${sevColor}">${v.severity}</span>
        `;
        list.appendChild(item);
      });
    }

    await loadLiveStream(insp.camera_id);

    evidencePage = 0;
    await loadWorkerEvidence(id, insp.inspection_name);
    document.getElementById("worker-evidence-section").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    console.error("Failed to load inspection detail:", err);
  }
}

async function loadLiveStream(cameraId) {
  const video = document.getElementById("live-stream-video");
  const placeholder = document.getElementById("live-stream-placeholder");
  const badge = document.getElementById("live-stream-badge");

  if (hlsPlayer) {
    hlsPlayer.destroy();
    hlsPlayer = null;
  }
  video.classList.add("hidden");
  badge.classList.add("hidden");
  badge.classList.remove("flex");
  placeholder.classList.remove("hidden");
  placeholder.textContent = "No live stream available for this camera yet";

  if (!cameraId) return;

  try {
    const camera = await authFetch(`/cameras/${cameraId}`, "GET");
    const cameraName = camera.camera_name.replace(/\//g, "_").replace(/\\/g, "_");
    const streamUrl = `${API_BASE}/stream/${cameraName}/stream.m3u8`;

    const checkRes = await fetch(streamUrl, { method: "HEAD" });
    if (!checkRes.ok) {
      placeholder.textContent = "No live stream available for this camera yet";
      return;
    }

    if (Hls.isSupported()) {
      hlsPlayer = new Hls();
      hlsPlayer.loadSource(streamUrl);
      hlsPlayer.attachMedia(video);
      hlsPlayer.on(Hls.Events.MANIFEST_PARSED, () => {
        video.classList.remove("hidden");
        placeholder.classList.add("hidden");
        badge.classList.remove("hidden");
        badge.classList.add("flex");
        video.play().catch(() => {});
      });
      hlsPlayer.on(Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          console.error("HLS fatal error:", data);
          placeholder.textContent = "Live stream unavailable right now";
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = streamUrl;
      video.classList.remove("hidden");
      placeholder.classList.add("hidden");
      badge.classList.remove("hidden");
      badge.classList.add("flex");
      video.play().catch(() => {});
    } else {
      placeholder.textContent = "Live streaming isn't supported in this browser";
    }
  } catch (err) {
    console.error("Failed to load live stream:", err);
    placeholder.textContent = "No live stream available for this camera yet";
  }
}

async function loadWorkerEvidence(inspectionId, inspectionName) {
  const container = document.getElementById("worker-evidence-section");

  try {
    const records = await authFetch(`/api/live_detection/worker-violations/${inspectionId}`, "GET");

    const sorted = [...records].sort((a, b) => {
      const aTime = new Date(a.first_seen || a.created_at).getTime();
      const bTime = new Date(b.first_seen || b.created_at).getTime();
      return bTime - aTime;
    });

    currentEvidenceRecords = sorted;

    if (!sorted.length) {
      container.style.display = "none";
      return;
    }
    container.style.display = "block";
    renderEvidencePage(inspectionName);
  } catch (err) {
    console.error("Failed to load worker evidence:", err);
    container.style.display = "none";
  }
}

function renderEvidencePage(inspectionName) {
  const list = document.getElementById("worker-evidence-list");
  list.innerHTML = "";

  const total = currentEvidenceRecords.length;
  const withPhoto = currentEvidenceRecords.filter(r => r.evidence_image_url).length;
  const unauthorizedCount = currentEvidenceRecords.filter(r => r.alert_type === "unauthorized_presence").length;
  const totalPages = Math.ceil(total / EVIDENCE_PAGE_SIZE);
  const start = evidencePage * EVIDENCE_PAGE_SIZE;
  const end = Math.min(start + EVIDENCE_PAGE_SIZE, total);
  const pageItems = currentEvidenceRecords.slice(start, end);

  document.getElementById("evidence-inspection-label").textContent =
    `${inspectionName} · ${withPhoto}/${total} with photo evidence${unauthorizedCount > 0 ? ` · ${unauthorizedCount} unauthorized presence` : ""}`;

  pageItems.forEach((r) => {
    const globalIdx = currentEvidenceRecords.indexOf(r);
    const isUnauthorized = r.alert_type === "unauthorized_presence";

    const statusColor = r.status === "open" ? "bg-red-50 text-error" :
                         r.status === "resolved" ? "bg-primary/10 text-primary" :
                         "bg-gray-100 text-gray-600";
    const durationMin = r.duration_seconds ? Math.round(r.duration_seconds / 60) : 0;
    const durationText = durationMin > 0 ? `${durationMin} min` : "< 1 min";
    const hasPhoto = !!r.evidence_image_url;

    const card = document.createElement("div");
    card.className = `bg-[#f7f9fc] rounded-lg border overflow-hidden transition-all ${
      isUnauthorized ? "border-2 border-tertiary" :
      hasPhoto ? "border-outline-variant/20 hover:shadow-md cursor-pointer" :
      "border-dashed border-outline-variant/40 opacity-70"
    }`;
    if (hasPhoto) card.onclick = () => openEvidenceModal(globalIdx);

    card.innerHTML = `
      ${isUnauthorized ? `<div class="bg-tertiary text-white text-[10px] font-bold uppercase px-3 py-1.5 flex items-center gap-1.5">🚫 Unauthorized Presence</div>` : ""}
      <div class="relative h-32 bg-gray-200">
        ${hasPhoto
          ? `<img class="w-full h-full object-cover" src="${API_BASE}${r.evidence_image_url}">`
          : `<div class="w-full h-full flex flex-col items-center justify-center text-outline text-xs gap-1">
               <span>📷</span><span>Photo pending</span>
             </div>`
        }
        <span class="absolute top-2 right-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase ${statusColor}">${r.status}</span>
      </div>
      <div class="p-3">
        <div class="flex justify-between items-start mb-1">
          <p class="font-bold text-sm">Worker #${r.worker_id}${r.employee_id ? ` (${r.employee_id})` : ""}</p>
          ${r.repeat_offender ? `<span class="text-tertiary text-[10px] font-bold">⚠ Repeat</span>` : ""}
        </div>
        <p class="text-xs text-outline mb-1 truncate">${isUnauthorized ? "Detected outside registered shift hours" : (r.violations || "—")}</p>
        <p class="text-[11px] text-outline">⏱ ${durationText}</p>
      </div>
    `;
    list.appendChild(card);
  });

  const pagination = document.getElementById("evidence-pagination");
  if (totalPages <= 1) {
    pagination.innerHTML = "";
    return;
  }

  pagination.innerHTML = `
    <button onclick="changeEvidencePage(-1)" ${evidencePage === 0 ? "disabled" : ""} class="px-3 py-1.5 border border-outline-variant rounded-lg text-xs font-bold ${evidencePage === 0 ? "opacity-40 cursor-not-allowed" : "hover:bg-gray-50"}">← Newer</button>
    <span class="text-xs text-outline">Showing ${start + 1}–${end} of ${total}</span>
    <button onclick="changeEvidencePage(1)" ${evidencePage >= totalPages - 1 ? "disabled" : ""} class="px-3 py-1.5 border border-outline-variant rounded-lg text-xs font-bold ${evidencePage >= totalPages - 1 ? "opacity-40 cursor-not-allowed" : "hover:bg-gray-50"}">Older →</button>
  `;
}

function changeEvidencePage(direction) {
  evidencePage += direction;
  const label = document.getElementById("evidence-inspection-label").textContent.split(" · ")[0];
  renderEvidencePage(label);
}

function openEvidenceModal(idx) {
  const r = currentEvidenceRecords[idx];
  if (!r || !r.evidence_image_url) return;

  document.getElementById("evidence-photo-full").src = `${API_BASE}${r.evidence_image_url}`;
  document.getElementById("evidence-modal-worker").textContent = `Worker #${r.worker_id}${r.employee_id ? ` (${r.employee_id})` : ""}`;

  const statusColor = r.status === "open" ? "bg-red-50 text-error" :
                       r.status === "resolved" ? "bg-primary/10 text-primary" :
                       "bg-gray-100 text-gray-600";
  const statusEl = document.getElementById("evidence-modal-status");
  statusEl.textContent = r.status;
  statusEl.className = `px-2.5 py-1 rounded-full text-[11px] font-bold uppercase ${statusColor}`;

  document.getElementById("evidence-modal-violations").textContent =
    r.alert_type === "unauthorized_presence" ? "🚫 Unauthorized Presence — detected outside registered shift hours" : (r.violations || "No violation details");

  const durationMin = r.duration_seconds ? Math.round(r.duration_seconds / 60) : 0;
  document.getElementById("evidence-modal-duration").textContent = `⏱ Duration: ${durationMin > 0 ? durationMin + " min" : "< 1 min"}`;
  document.getElementById("evidence-modal-repeat").textContent = r.repeat_offender ? "⚠ Repeat Offender" : "";

  document.getElementById("evidence-photo-modal").classList.add("open");
}

function closeEvidenceModal() {
  document.getElementById("evidence-photo-modal").classList.remove("open");
}

function openCreateModal() {
  document.getElementById("create-modal").classList.add("open");
}
function closeCreateModal() {
  document.getElementById("create-modal").classList.remove("open");
}

async function submitNewInspection(event) {
  event.preventDefault();
  const name = document.getElementById("new-inspection-name").value.trim();
  const cameraId = document.getElementById("new-inspection-camera").value;
  if (!name) return;

  try {
    await authFetch("/inspections/", "POST", {
      inspection_name: name,
      camera_id: cameraId ? Number(cameraId) : null,
    });
    closeCreateModal();
    document.getElementById("new-inspection-name").value = "";
    document.getElementById("new-inspection-camera").value = "";
    loadInspections();
  } catch (err) {
    console.error("Failed to create inspection:", err);
  }
}

function checkDeepLink() {
  const params = new URLSearchParams(window.location.search);
  const openId = params.get("open");
  if (openId) setTimeout(() => openInspectionDetail(Number(openId)), 300);
}

document.addEventListener("DOMContentLoaded", () => {
  loadInspections();
  checkDeepLink();
});