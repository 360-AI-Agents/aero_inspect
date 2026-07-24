const SEVERITY_COLORS = {
  helmet: "#059669", vest: "#3378D8", scaffolding: "#D89A33",
  debris: "#8d4b00", restricted_zone: "#ba1a1a", fall_protection: "#D8492B",
  heavy_equipment: "#7C8A99", unsafe_behaviour: "#545f73", material_storage: "#6d7a72",
};

const SITE_PHOTOS = [
  "https://plus.unsplash.com/premium_photo-1681691912442-68c4179c530c?w=900&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=900&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1587582423116-ec07293f0395?w=900&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1508450859948-4e04fabaa4ea?w=900&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=900&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1599707254554-027aeb4deacd?w=900&auto=format&fit=crop&q=60",
  "https://media.istockphoto.com/id/187654276/photo/bridge-building.webp?a=1&b=1&s=612x612&w=0&k=20&c=SzIJLQh-HWFGcX2EnTaKtPYqeOciuPxnrCy9m44qzxQ=",
  "https://media.istockphoto.com/id/838476004/photo/silhouette-of-engineer-and-construction-team-working-safely-work-load-concrete-on-scaffolding.webp?a=1&b=1&s=612x612&w=0&k=20&c=xXLKeqSFDdox0mTueiK01FcN-GEQmycwYpIYhis0nBg=",
  "https://images.unsplash.com/photo-1589939705384-5185137a7f0f?w=900&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1529792083865-d23889753466?w=900&auto=format&fit=crop&q=60",
  "https://images.unsplash.com/photo-1527335988388-b40ee248d80c?w=900&auto=format&fit=crop&q=60",
];

function getPhotoForSite(name) {
  const normalized = name.trim().toLowerCase();
  let hash = 5381;
  for (let i = 0; i < normalized.length; i++) {
    hash = ((hash << 5) + hash + normalized.charCodeAt(i)) & 0xffffffff;
  }
  hash = Math.abs(hash);
  return SITE_PHOTOS[hash % SITE_PHOTOS.length];
}

let latestInspectionId = null;
let allCamerasCache = [];

async function loadDashboard() {
  try {
    const data = await authFetch("/dashboard/", "GET");
    await renderHero(data);
    renderDonut(data.violation_breakdown);
    renderHistory(data.inspection_history);
  } catch (err) {
    console.error("Failed to load dashboard:", err);
  }
  await loadCameraStrip();
}

async function renderHero(data) {
  const latest = data.latest_inspection;
  document.getElementById("hero-title").textContent = latest ? latest.inspection_name : "No active inspections yet";
  latestInspectionId = latest ? latest.id : null;
  document.getElementById("kpi-compliance").textContent = `${data.overview.compliance_score}%`;
  document.getElementById("kpi-violations").textContent = data.overview.total_violations;

  const heroSection = document.querySelector("section.relative.h-\\[420px\\]");
  if (heroSection && latest) {
    const bgDiv = heroSection.querySelector(".absolute.inset-0.bg-cover");
    if (bgDiv) {
      const photo = getPhotoForSite(latest.inspection_name);
      bgDiv.style.backgroundImage = `url('${photo}')`;
    }
  }

  if (latest) {
    try {
      const counts = await authFetch(`/api/live_detection/worker-counts/${latest.id}`, "GET");
      document.getElementById("kpi-workers-today").textContent = counts.today;
      document.getElementById("kpi-workers-total").textContent = counts.total;
    } catch (err) {
      console.error("Failed to load worker counts:", err);
      document.getElementById("kpi-workers-today").textContent = "—";
      document.getElementById("kpi-workers-total").textContent = "—";
    }
  } else {
    document.getElementById("kpi-workers-today").textContent = "0";
    document.getElementById("kpi-workers-total").textContent = "0";
  }
}

function renderDonut(breakdown) {
  const entries = Object.entries(breakdown).filter(([_, v]) => v > 0);
  const total = entries.reduce((sum, [_, v]) => sum + v, 0);
  document.getElementById("donut-total").textContent = total;

  const donut = document.getElementById("donut-chart");
  const legend = document.getElementById("breakdown-legend");
  legend.innerHTML = "";

  if (total === 0) {
    donut.style.background = "#e0e3e6";
    legend.innerHTML = `<p class="text-sm text-outline text-center">No violations recorded yet.</p>`;
    return;
  }

  let cumulative = 0;
  const stops = entries.map(([cat, count]) => {
    const pct = (count / total) * 100;
    const start = cumulative;
    cumulative += pct;
    return `${SEVERITY_COLORS[cat] || "#999"} ${start}% ${cumulative}%`;
  });
  donut.style.background = `conic-gradient(${stops.join(", ")})`;

  entries.forEach(([cat, count]) => {
    const pct = Math.round((count / total) * 100);
    const row = document.createElement("div");
    row.className = "flex items-center justify-between";
    row.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full" style="background:${SEVERITY_COLORS[cat] || '#999'}"></span>
        <span class="text-sm capitalize">${cat.replace(/_/g, " ")}</span>
      </div>
      <span class="font-mono text-sm font-bold">${count} (${pct}%)</span>
    `;
    legend.appendChild(row);
  });
}

function renderHistory(inspections) {
  const tbody = document.getElementById("history-body");
  tbody.innerHTML = "";
  if (!inspections.length) {
    document.getElementById("history-empty").classList.remove("hidden");
    return;
  }
  document.getElementById("history-empty").classList.add("hidden");

  inspections.forEach(insp => {
    const row = document.createElement("tr");
    row.className = "hover:bg-[#f2f4f7] transition-colors";
    if (insp.id === latestInspectionId) row.classList.add("bg-primary/5");
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

async function loadCameraStrip() {
  try {
    const cameras = await authFetch("/cameras/", "GET");
    allCamerasCache = cameras;
    const strip = document.getElementById("camera-story-strip");
    const mosaic = document.getElementById("camera-mosaic");
    strip.innerHTML = "";
    mosaic.innerHTML = "";

    if (!cameras.length) {
      strip.innerHTML = `<p class="text-sm text-outline">No cameras registered yet.</p>`;
      mosaic.innerHTML = `<p class="text-sm text-outline col-span-2">No cameras registered yet — add one on the Cameras page.</p>`;
      return;
    }

    cameras.slice(0, 6).forEach((cam) => {
      const photo = getPhotoForSite(`${cam.camera_name}-${cam.location}`);
      const el = document.createElement("div");
      el.className = "flex flex-col items-center gap-2 flex-shrink-0 cursor-pointer group";
      el.onclick = () => openCameraPreview(cam);
      el.innerHTML = `
        <div class="relative w-16 h-16 rounded-full border-2 ${cam.status === 'active' ? 'border-primary' : 'border-outline-variant'} p-1 bg-white transition-transform group-hover:scale-110">
          <div class="w-full h-full rounded-full bg-cover bg-center" style="background-image:url('${photo}')"></div>
          ${cam.status === 'active' ? '<span class="absolute top-0 right-0 w-3 h-3 rounded-full bg-red-500 border-2 border-white animate-pulse"></span>' : ''}
        </div>
        <span class="text-[10px] font-bold text-outline uppercase tracking-widest truncate max-w-[70px] group-hover:text-primary">${cam.camera_name}</span>
      `;
      strip.appendChild(el);
    });

   cameras.slice(0, 4).forEach(cam => {
      const el = document.createElement("div");
      el.className = "relative aspect-video rounded-xl overflow-hidden cursor-pointer";
      el.onclick = () => openCameraPreview(cam);

      if (cam.status === 'active') {
        const photo = getPhotoForSite(`${cam.camera_name}-${cam.location}`);
        el.classList.add("bg-gray-100");
        el.innerHTML = `
          <img class="w-full h-full object-cover" src="${photo}" alt="${cam.camera_name}">
          <div class="absolute top-3 left-3 flex items-center gap-2 bg-black/50 backdrop-blur-sm text-white px-3 py-1 rounded text-[10px] font-bold">
            <span class="live-dot"></span> ${cam.camera_name.toUpperCase()}
          </div>
          <div class="absolute top-3 right-3 bg-primary text-white text-[10px] font-bold px-2 py-1 rounded uppercase">${cam.source_type}</div>
        `;
      } else {
        el.classList.add("bg-[#1a1f24]");
        el.innerHTML = `
          <div class="w-full h-full flex flex-col items-center justify-center gap-2 opacity-70">
            <svg viewBox="0 0 24 24" fill="none" stroke="#6d7a72" stroke-width="1.5" class="w-10 h-10"><path d="M1 1l22 22M9.5 4H15a2 2 0 012 2v9.5M17 17.5V19a2 2 0 01-2 2H5a2 2 0 01-2-2V7c0-.5.2-1 .5-1.4"/><circle cx="12" cy="13" r="3.5"/></svg>
            <span class="text-[11px] font-bold text-outline uppercase tracking-widest">Connection Lost</span>
          </div>
          <div class="absolute top-3 left-3 flex items-center gap-2 bg-black/60 backdrop-blur-sm text-white/70 px-3 py-1 rounded text-[10px] font-bold">
            ${cam.camera_name.toUpperCase()}
          </div>
        `;
      }
      mosaic.appendChild(el);
    });

  } catch (err) {
    console.error("Failed to load cameras:", err);
  }
}

function openCameraPreview(cam) {
  const photo = getPhotoForSite(`${cam.camera_name}-${cam.location}`);
  const modal = document.getElementById("camera-preview-modal");
  modal.querySelector("img").src = photo;
  document.getElementById("preview-camera-name").textContent = cam.camera_name;
  document.getElementById("preview-camera-location").textContent = cam.location;
  document.getElementById("preview-camera-status").textContent = cam.status;
  document.getElementById("preview-camera-status").className =
    `px-2.5 py-1 rounded-full text-[11px] font-bold uppercase ${cam.status === 'active' ? 'bg-primary/10 text-primary' : 'bg-gray-100 text-gray-600'}`;
  document.getElementById("preview-camera-type").textContent = cam.source_type.toUpperCase();
  modal.classList.add("open");
}

function closeCameraPreview() {
  document.getElementById("camera-preview-modal").classList.remove("open");
}

async function simulateDetection() {
  const btn = document.getElementById("simulate-btn");
  btn.disabled = true;
  btn.textContent = "Simulating…";

  if (!allCamerasCache.length) {
    alert("No cameras available to simulate a detection on. Ask an admin to register a camera for your assigned site.");
    btn.textContent = "+ Simulate Live Detection";
    btn.disabled = false;
    return;
  }

  const violationPool = [
    { category: "helmet", violation_name: "No Helmet", severity: "high" },
    { category: "vest", violation_name: "No High-Vis Vest", severity: "high" },
    { category: "scaffolding", violation_name: "Unsecured Scaffold", severity: "high" },
    { category: "debris", violation_name: "Debris in Walkway", severity: "medium" },
    { category: "restricted_zone", violation_name: "Restricted Zone Entry", severity: "critical" },
    { category: "fall_protection", violation_name: "Missing Fall Protection", severity: "critical" },
    { category: "heavy_equipment", violation_name: "Worker Near Heavy Equipment", severity: "critical" },
  ];

  const chosenCamera = allCamerasCache[Math.floor(Math.random() * allCamerasCache.length)];

  try {
    const created = await authFetch("/inspections/", "POST", {
      inspection_name: `${chosenCamera.location} (${new Date().toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit"})})`,
      camera_id: chosenCamera.id,
    });

    const count = Math.floor(Math.random() * 2) + 1;
    const chosen = [...violationPool].sort(() => Math.random() - 0.5).slice(0, count);

    await authFetch(`/inspections/${created.id}/detections/raw`, "POST", {
      workers_detected: Math.floor(Math.random() * 12) + 3,
      helmet_missing: chosen.some(v => v.category === "helmet"),
      vest_missing: chosen.some(v => v.category === "vest"),
      in_restricted_zone: chosen.some(v => v.category === "restricted_zone"),
      near_heavy_equipment: chosen.some(v => v.category === "heavy_equipment"),
      unsecured_scaffolding: chosen.some(v => v.category === "scaffolding"),
      debris_present: chosen.some(v => v.category === "debris"),
      height_meters: chosen.some(v => v.category === "fall_protection") ? 3.5 : null,
      harness_worn: false,
      confidence: 0.9,
    });

    await loadDashboard();
    btn.textContent = "✓ Detection Simulated";
    document.getElementById("history-section").scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(() => { btn.textContent = "+ Simulate Live Detection"; btn.disabled = false; }, 1500);
  } catch (err) {
    console.error("Simulation failed:", err);
    btn.textContent = "+ Simulate Live Detection";
    btn.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadDashboard();
  setInterval(loadDashboard, 10000);
});