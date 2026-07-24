let allWorkersCache = [];
let selectedWorkerPhoto = null;
let cameraStream = null;
let currentPhotoMode = "camera";

async function loadWorkers() {
  try {
    const workers = await authFetch("/workers/", "GET");
    allWorkersCache = workers;
    renderWorkers(workers);
    renderStats(workers);
    await populateSiteDropdown();
  } catch (err) {
    console.error("Failed to load workers:", err);
  }
}

function renderStats(workers) {
  document.getElementById("stat-total").textContent = workers.length;
  document.getElementById("stat-linked").textContent = workers.filter(w => w.tracked_worker_id != null).length;
  document.getElementById("stat-unlinked").textContent = workers.filter(w => w.tracked_worker_id == null).length;
  document.getElementById("stat-sites").textContent = new Set(workers.map(w => w.assigned_site)).size;
}

function renderWorkers(workers) {
  const grid = document.getElementById("workers-grid");
  grid.innerHTML = "";

  if (!workers.length) {
    document.getElementById("workers-empty").classList.remove("hidden");
    return;
  }
  document.getElementById("workers-empty").classList.add("hidden");

  workers.forEach((w) => {
    const isLinked = w.tracked_worker_id != null;
    const card = document.createElement("div");
    card.className = "bg-white rounded-xl overflow-hidden shadow-sm border border-outline-variant/10 hover:-translate-y-1 transition-all duration-300";
    card.innerHTML = `
      <div class="relative h-40 bg-gray-100 cursor-pointer" onclick="openHistoryModal(${w.id})">
        ${w.reference_photo_url
          ? `<img class="w-full h-full object-cover" src="${API_BASE}${w.reference_photo_url}">`
          : `<div class="w-full h-full flex items-center justify-center text-outline text-xs">No photo</div>`
        }
        <div class="absolute top-3 right-3 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase ${isLinked ? 'bg-primary/90 text-white' : 'bg-tertiary/90 text-white'}">
          ${isLinked ? `✓ Linked #${w.tracked_worker_id}` : "Not Linked"}
        </div>
      </div>
      <div class="p-5">
        <div class="flex justify-between items-start mb-1 cursor-pointer" onclick="openHistoryModal(${w.id})">
          <h4 class="font-headline font-bold hover:text-primary transition-colors">${w.name}</h4>
          <span class="font-mono text-xs text-outline">${w.employee_id}</span>
        </div>
        <p class="text-xs text-outline mb-1">${w.role || "—"} · ${w.company || "—"}</p>
        ${w.email ? `<p class="text-xs text-outline mb-1">✉️ ${w.email}</p>` : `<p class="text-xs text-tertiary mb-1">⚠ No email on file</p>`}
        <p class="text-xs text-outline mb-3">📍 ${w.assigned_site}</p>
        ${w.shift_start && w.shift_end ? `<p class="text-xs text-outline mb-3">⏰ ${w.shift_start} – ${w.shift_end}${w.weekly_off_day ? ` · Off: ${w.weekly_off_day}` : ""}</p>` : ""}
        <div class="flex gap-2">
          <button onclick="openLinkModal('${w.employee_id}')" class="flex-1 py-2 bg-[#f2f4f7] hover:bg-primary/10 hover:text-primary rounded-lg text-xs font-bold transition-colors">${isLinked ? "Re-link" : "Link Tracking ID"}</button>
          <button onclick="deleteWorker(${w.id})" class="w-9 h-9 flex items-center justify-center border border-outline-variant rounded-lg hover:border-error hover:text-error transition-colors">🗑</button>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });
}

async function populateSiteDropdown() {
  try {
    const cameras = await authFetch("/cameras/", "GET");
    const locations = [...new Set(cameras.map(c => c.location))];
    const select = document.getElementById("worker-site");
    select.innerHTML = locations.length
      ? locations.map(l => `<option value="${l}">${l}</option>`).join("")
      : `<option value="">No sites yet — register a camera first</option>`;
  } catch (err) {
    console.error("Failed to load sites for dropdown:", err);
  }
}

function openWorkerModal() {
  document.getElementById("worker-modal-title").textContent = "Register Worker";
  document.getElementById("worker-edit-id").value = "";
  document.getElementById("worker-employee-id").value = "";
  document.getElementById("worker-name").value = "";
  document.getElementById("worker-email").value = "";
  document.getElementById("worker-phone").value = "";
  document.getElementById("worker-company").value = "";
  document.getElementById("worker-role").value = "";
  document.getElementById("worker-shift-start").value = "";
  document.getElementById("worker-shift-end").value = "";
  document.getElementById("worker-weekly-off").value = "";
  switchPhotoMode("camera");
  resetCameraCapture();
  document.getElementById("worker-modal").classList.add("open");
}

function closeWorkerModal() {
  stopCameraStream();
  document.getElementById("worker-modal").classList.remove("open");
}

function switchPhotoMode(mode) {
  currentPhotoMode = mode;
  selectedWorkerPhoto = null;

  const cameraBtn = document.getElementById("photo-mode-camera-btn");
  const uploadBtn = document.getElementById("photo-mode-upload-btn");
  const cameraContainer = document.getElementById("camera-capture-container");
  const uploadContainer = document.getElementById("upload-container");

  if (mode === "camera") {
    cameraBtn.className = "flex-1 py-2 rounded-lg text-sm font-bold border-2 border-primary bg-primary/10 text-primary transition-all";
    uploadBtn.className = "flex-1 py-2 rounded-lg text-sm font-bold border-2 border-outline-variant text-outline hover:border-primary hover:text-primary transition-all";
    cameraContainer.style.display = "block";
    uploadContainer.style.display = "none";
    stopCameraStream();
    resetCameraCapture();
  } else {
    uploadBtn.className = "flex-1 py-2 rounded-lg text-sm font-bold border-2 border-primary bg-primary/10 text-primary transition-all";
    cameraBtn.className = "flex-1 py-2 rounded-lg text-sm font-bold border-2 border-outline-variant text-outline hover:border-primary hover:text-primary transition-all";
    uploadContainer.style.display = "block";
    cameraContainer.style.display = "none";
    stopCameraStream();
    document.getElementById("upload-file-label").textContent = "Click to upload a photo file";
  }
}

function resetCameraCapture() {
  document.getElementById("camera-idle-view").style.display = "flex";
  document.getElementById("camera-live-view").style.display = "none";
  document.getElementById("camera-captured-view").style.display = "none";
  document.getElementById("worker-photo-label").textContent = "No photo captured yet";
}

async function startCameraCapture() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    const video = document.getElementById("worker-camera-video");
    video.srcObject = cameraStream;

    document.getElementById("camera-idle-view").style.display = "none";
    document.getElementById("camera-live-view").style.display = "block";
  } catch (err) {
    console.error("Camera access failed:", err);
    alert("Couldn't access the camera. Please check your browser's camera permissions and try again.");
  }
}

function captureWorkerPhoto() {
  const video = document.getElementById("worker-camera-video");
  const canvas = document.getElementById("worker-camera-canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob((blob) => {
    selectedWorkerPhoto = new File([blob], `worker_capture_${Date.now()}.jpg`, { type: "image/jpeg" });

    const previewUrl = URL.createObjectURL(blob);
    document.getElementById("worker-captured-preview").src = previewUrl;

    stopCameraStream();
    document.getElementById("camera-live-view").style.display = "none";
    document.getElementById("camera-captured-view").style.display = "block";
    document.getElementById("worker-photo-label").textContent = "Photo captured ✓";
  }, "image/jpeg", 0.92);
}

function retakeWorkerPhoto() {
  document.getElementById("camera-captured-view").style.display = "none";
  startCameraCapture();
}

function stopCameraStream() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
}

function handleWorkerPhotoUpload(input) {
  const file = input.files[0];
  if (!file) return;
  selectedWorkerPhoto = file;
  document.getElementById("upload-file-label").textContent = `Selected: ${file.name}`;
}

async function submitWorker(event) {
  event.preventDefault();

  const payload = {
    employee_id: document.getElementById("worker-employee-id").value.trim(),
    name: document.getElementById("worker-name").value.trim(),
    email: document.getElementById("worker-email").value.trim() || null,
    phone: document.getElementById("worker-phone").value.trim() || null,
    company: document.getElementById("worker-company").value.trim() || null,
    role: document.getElementById("worker-role").value.trim() || null,
    assigned_site: document.getElementById("worker-site").value,
    shift_start: document.getElementById("worker-shift-start").value || null,
    shift_end: document.getElementById("worker-shift-end").value || null,
    weekly_off_day: document.getElementById("worker-weekly-off").value || null,
  };

  try {
    const worker = await authFetch("/workers/", "POST", payload);

    if (selectedWorkerPhoto) {
      const formData = new FormData();
      formData.append("file", selectedWorkerPhoto);
      const res = await fetch(`${API_BASE}/workers/${worker.id}/photo`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${getToken()}` },
        body: formData,
      });
      if (!res.ok) console.error("Photo upload failed:", res.status);
    }

    closeWorkerModal();
    loadWorkers();
  } catch (err) {
    console.error("Failed to register worker:", err);
    alert("Failed to register worker — employee ID may already exist.");
  }
}

async function deleteWorker(id) {
  if (!confirm("Remove this worker from the system?")) return;
  try {
    await authFetch(`/workers/${id}`, "DELETE");
    loadWorkers();
  } catch (err) {
    console.error("Failed to delete worker:", err);
  }
}

function openLinkModal(employeeId) {
  document.getElementById("link-employee-id").value = employeeId;
  document.getElementById("link-tracked-id").value = "";
  document.getElementById("link-modal").classList.add("open");
}

function closeLinkModal() {
  document.getElementById("link-modal").classList.remove("open");
}

async function submitLinkTracking(event) {
  event.preventDefault();
  const employeeId = document.getElementById("link-employee-id").value;
  const trackedId = Number(document.getElementById("link-tracked-id").value);

  try {
    const result = await authFetch("/workers/link-tracker", "POST", {
      tracked_worker_id: trackedId,
      employee_id: employeeId,
    });
    closeLinkModal();
    loadWorkers();
    alert(`Linked successfully. ${result.historical_violations_linked} past violation record(s) now attached to this worker.`);
  } catch (err) {
    console.error("Failed to link tracking ID:", err);
    alert("Failed to link — admin access required.");
  }
}

async function openHistoryModal(workerId) {
  try {
    const data = await authFetch(`/workers/${workerId}/history`, "GET");

    document.getElementById("history-worker-name").textContent = data.worker.name;
    document.getElementById("history-worker-meta").textContent =
      `${data.worker.employee_id} · ${data.worker.role || "—"} · ${data.worker.assigned_site}`;

    const photoContainer = document.getElementById("history-photo-container");
    photoContainer.innerHTML = data.worker.reference_photo_url
      ? `<img class="w-full h-full object-cover" src="${API_BASE}${data.worker.reference_photo_url}">`
      : `<div class="w-full h-full flex items-center justify-center text-outline text-xs">No photo</div>`;

    document.getElementById("history-total-events").textContent = data.summary.total_violation_events;

    const totalMin = Math.round(data.summary.total_duration_seconds / 60);
    document.getElementById("history-total-duration").textContent = totalMin > 0 ? `${totalMin} min` : "< 1 min";

    const typeCounts = data.summary.violation_type_counts;
    const mostCommon = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0];
    document.getElementById("history-most-common").textContent = mostCommon ? `${mostCommon[0]} (×${mostCommon[1]})` : "—";

    const timeline = document.getElementById("history-timeline");
    timeline.innerHTML = "";

    if (!data.records.length) {
      document.getElementById("history-empty").classList.remove("hidden");
    } else {
      document.getElementById("history-empty").classList.add("hidden");
      data.records.forEach((r) => {
        const statusColor = r.status === "open" ? "bg-red-50 text-error" :
                             r.status === "resolved" ? "bg-primary/10 text-primary" :
                             "bg-gray-100 text-gray-600";
        const durationMin = r.duration_seconds ? Math.round(r.duration_seconds / 60) : 0;
        const item = document.createElement("div");
        item.className = "flex gap-4 p-4 bg-[#f7f9fc] rounded-lg border border-outline-variant/20";
        item.innerHTML = `
          <div class="w-20 h-16 rounded-lg overflow-hidden flex-shrink-0 bg-gray-200">
            ${r.evidence_image_url
              ? `<img class="w-full h-full object-cover cursor-pointer" src="${API_BASE}${r.evidence_image_url}" onclick="window.open('${API_BASE}${r.evidence_image_url}', '_blank')">`
              : `<div class="w-full h-full flex items-center justify-center text-outline text-[10px]">No photo</div>`
            }
          </div>
          <div class="flex-1">
            <div class="flex justify-between items-start mb-1">
              <p class="font-bold text-sm">${r.violations || "—"}</p>
              <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase ${statusColor}">${r.status}</span>
            </div>
            <p class="text-xs text-outline">
              ${r.first_seen ? new Date(r.first_seen).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
              ${r.duration_seconds ? ` · ${durationMin > 0 ? durationMin + " min" : "< 1 min"}` : ""}
              ${r.repeat_offender ? ` · <span class="text-tertiary font-bold">⚠ Repeat Offender</span>` : ""}
            </p>
          </div>
        `;
        timeline.appendChild(item);
      });
    }

    document.getElementById("history-modal").classList.add("open");
  } catch (err) {
    console.error("Failed to load worker history:", err);
    alert("Failed to load worker history.");
  }
}

function closeHistoryModal() {
  document.getElementById("history-modal").classList.remove("open");
}

async function exportWorkersList() {
  const btn = document.getElementById("export-workers-btn");
  const originalText = btn.textContent;
  btn.textContent = "Exporting…";
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/export/workers`, {
      headers: { "Authorization": `Bearer ${getToken()}` },
    });

    if (res.status === 401 || res.status === 403) {
      clearSession();
      window.location.href = "login.html";
      return;
    }
    if (!res.ok) throw new Error(`Export failed: ${res.status}`);

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "aeroinspect_workers.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Export failed:", err);
    alert("Failed to export workers list.");
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

async function sendDigestNow() {
  if (!confirm("Send this hour's violation digest email to all workers who have violations recorded in the last hour?\n\nNote: this is mainly for testing/demo purposes. The system already sends this automatically every hour — using this button between automatic runs may result in a worker receiving two emails covering overlapping violations.")) return;
  const btn = document.getElementById("send-digest-btn");
  const originalText = btn.textContent;
  btn.textContent = "Sending…";
  btn.disabled = true;

  try {
    const result = await authFetch("/digest/send-now", "POST");
    alert(result.message);
  } catch (err) {
    console.error("Failed to send digest:", err);
    alert("Failed to send digest — admin access required.");
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", loadWorkers);