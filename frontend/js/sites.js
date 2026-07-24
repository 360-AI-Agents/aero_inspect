let allSitesData = {};
let siteCriticalCounts = {};
let currentFilter = "all";
let currentView = "grid";

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

async function loadSites() {
  try {
    const cameras = await authFetch("/cameras/", "GET");
    const alertsData = await authFetch("/alerts/", "GET");

    const grouped = {};
    cameras.forEach((cam) => {
      if (!grouped[cam.location]) grouped[cam.location] = [];
      grouped[cam.location].push(cam);
    });
    allSitesData = grouped;

    siteCriticalCounts = {};
    (alertsData.critical || []).forEach((alert) => {
      const loc = alert.location;
      if (!loc) return;
      siteCriticalCounts[loc] = (siteCriticalCounts[loc] || 0) + 1;
    });

    updateSystemHealth(cameras);
    updateFilterButtons();
    renderSites();
  } catch (err) {
    console.error("Failed to load sites:", err);
  }
}

function updateSystemHealth(cameras) {
  if (!cameras.length) {
    document.getElementById("system-health").textContent = "No data";
    return;
  }
  const activeCount = cameras.filter(c => c.status === "active").length;
  const pct = ((activeCount / cameras.length) * 100).toFixed(1);
  document.getElementById("system-health").textContent = `${pct}% Uptime`;
}

function setFilter(filter) {
  currentFilter = filter;
  updateFilterButtons();
  renderSites();
}

function updateFilterButtons() {
  const allBtn = document.getElementById("filter-all");
  const attnBtn = document.getElementById("filter-attention");
  const critBtn = document.getElementById("filter-critical");

  const totalSites = Object.keys(allSitesData).length;
  const attentionCount = Object.values(allSitesData).filter(cams => cams.some(c => c.status !== "active")).length;
  const criticalCount = Object.keys(siteCriticalCounts).length;

  allBtn.textContent = `All Sites (${totalSites})`;
  attnBtn.textContent = `📡 Connection Lost (${attentionCount})`;
  critBtn.textContent = `🔴 Critical Sites (${criticalCount})`;

  const activeClass = "px-4 py-2 rounded-full text-sm font-semibold border border-primary/30 bg-primary/10 text-primary";
  const inactiveClass = "px-4 py-2 rounded-full text-sm font-semibold border border-outline-variant/30 text-outline hover:bg-gray-50";
  const criticalActiveClass = "px-4 py-2 rounded-full text-sm font-semibold border border-error/30 bg-error/10 text-error";

  allBtn.className = currentFilter === "all" ? activeClass : inactiveClass;
  attnBtn.className = currentFilter === "attention" ? activeClass : inactiveClass;
  critBtn.className = currentFilter === "critical" ? criticalActiveClass : inactiveClass;
}

function setView(view) {
  currentView = view;
  const gridBtn = document.getElementById("view-grid-btn");
  const listBtn = document.getElementById("view-list-btn");
  gridBtn.className = view === "grid" ? "p-1.5 bg-white shadow-sm rounded-md text-primary" : "p-1.5 text-outline hover:text-on-surface";
  listBtn.className = view === "list" ? "p-1.5 bg-white shadow-sm rounded-md text-primary" : "p-1.5 text-outline hover:text-on-surface";
  renderSites();
}

function getFilteredLocations() {
  const locations = Object.keys(allSitesData);
  if (currentFilter === "attention") {
    return locations.filter(loc => allSitesData[loc].some(c => c.status !== "active"));
  }
  if (currentFilter === "critical") {
    return locations.filter(loc => siteCriticalCounts[loc] > 0);
  }
  return locations;
}

function renderSites() {
  const grid = document.getElementById("sites-grid");
  const list = document.getElementById("sites-list");
  const empty = document.getElementById("sites-empty");
  grid.innerHTML = "";
  list.innerHTML = "";

  const locations = getFilteredLocations();
  const totalCameras = Object.values(allSitesData).flat().length;

  document.getElementById("hero-subtitle").textContent =
    `Real-time AI monitoring across your enterprise portfolio. Currently analyzing ${Object.keys(allSitesData).length} sites with ${totalCameras} active sensor nodes.`;

  if (!locations.length) {
    empty.classList.remove("hidden");
    grid.classList.add("hidden");
    list.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");

  if (currentView === "grid") {
    grid.classList.remove("hidden");
    list.classList.add("hidden");
    locations.forEach(loc => grid.appendChild(buildSiteCard(loc)));
  } else {
    list.classList.remove("hidden");
    grid.classList.add("hidden");
    locations.forEach(loc => list.appendChild(buildSiteListRow(loc)));
  }
}

function buildSiteCard(loc) {
  const cams = allSitesData[loc];
  const activeCount = cams.filter(c => c.status === "active").length;
  const allSafe = activeCount === cams.length;
  const critCount = siteCriticalCounts[loc] || 0;
  const photo = getPhotoForSite(loc);

  let badgeText, badgeColor;
  if (critCount > 0) {
    badgeText = `${critCount} Critical`;
    badgeColor = "bg-error/90";
  } else if (allSafe) {
    badgeText = "Safe";
    badgeColor = "bg-primary/90";
  } else {
    badgeText = `${cams.length - activeCount} Offline`;
    badgeColor = "bg-tertiary/90";
  }

  const card = document.createElement("div");
  card.className = "bg-white rounded-xl overflow-hidden shadow-sm border border-outline-variant/10 hover:-translate-y-1 transition-all duration-300";
  card.innerHTML = `
    <div class="relative h-40">
      <img class="w-full h-full object-cover" src="${photo}" alt="${loc}">
      <div class="absolute top-3 right-3 ${badgeColor} backdrop-blur-sm px-3 py-1 rounded-full flex items-center gap-1.5">
        <span class="w-1.5 h-1.5 rounded-full bg-white live-dot"></span>
        <span class="text-[11px] text-white font-semibold">${badgeText}</span>
      </div>
    </div>
    <div class="p-6">
      <div class="flex justify-between items-start mb-2">
        <h3 class="font-headline text-lg font-bold">${loc}</h3>
        <span class="font-mono text-xs text-outline">${activeCount}/${cams.length}</span>
      </div>
      <p class="text-xs text-outline mb-4">${cams.length} camera(s) registered${critCount > 0 ? ` · ${critCount} critical alert(s)` : ""}</p>
      <div class="grid grid-cols-2 gap-2 mb-4">
        ${cams.map(c => `
          <div class="flex items-center gap-2 text-xs">
            <span class="w-1.5 h-1.5 rounded-full ${c.status === 'active' ? 'bg-primary' : 'bg-gray-300'}"></span>
            <span class="truncate">${c.camera_name}</span>
          </div>
        `).join("")}
      </div>
      <button onclick="window.location.href='cameras.html'" class="w-full py-2.5 bg-[#eceef1] hover:bg-primary hover:text-white rounded-lg font-bold text-sm transition-all">View Cameras</button>
    </div>
  `;
  return card;
}

function buildSiteListRow(loc) {
  const cams = allSitesData[loc];
  const activeCount = cams.filter(c => c.status === "active").length;
  const allSafe = activeCount === cams.length;
  const critCount = siteCriticalCounts[loc] || 0;
  const photo = getPhotoForSite(loc);

  let badgeText, badgeClass;
  if (critCount > 0) {
    badgeText = `${critCount} Critical`;
    badgeClass = "bg-red-50 text-error";
  } else if (allSafe) {
    badgeText = "Safe";
    badgeClass = "bg-primary/10 text-primary";
  } else {
    badgeText = "Connection Lost";
    badgeClass = "bg-amber-50 text-amber-700";
  }

  const row = document.createElement("div");
  row.className = "bg-white rounded-xl p-5 shadow-sm border border-outline-variant/10 flex items-center justify-between";
  row.innerHTML = `
    <div class="flex items-center gap-4">
      <div class="w-14 h-14 rounded-lg bg-cover bg-center flex-shrink-0" style="background-image:url('${photo}')"></div>
      <div>
        <h3 class="font-headline font-bold">${loc}</h3>
        <p class="text-xs text-outline">${cams.length} camera(s) · ${activeCount} active</p>
      </div>
    </div>
    <div class="flex items-center gap-4">
      <span class="px-3 py-1 rounded-full text-xs font-bold ${badgeClass}">${badgeText}</span>
      <button onclick="window.location.href='cameras.html'" class="px-4 py-2 bg-[#eceef1] hover:bg-primary hover:text-white rounded-lg font-bold text-xs transition-all">View Cameras</button>
    </div>
  `;
  return row;
}

function openRegisterModal() {
  document.getElementById("register-modal").classList.add("open");
}
function closeRegisterModal() {
  document.getElementById("register-modal").classList.remove("open");
}

async function submitNewSite(event) {
  event.preventDefault();
  const location = document.getElementById("new-site-location").value.trim();
  const cameraName = document.getElementById("new-site-camera-name").value.trim();
  const sourceType = document.getElementById("new-site-source").value;
  if (!location || !cameraName) return;

  try {
    const params = new URLSearchParams({ camera_name: cameraName, location, source_type: sourceType });
    await authFetch(`/cameras/?${params.toString()}`, "POST");
    closeRegisterModal();
    document.getElementById("new-site-location").value = "";
    document.getElementById("new-site-camera-name").value = "";
    loadSites();
  } catch (err) {
    console.error("Failed to register site:", err);
  }
}

document.addEventListener("DOMContentLoaded", loadSites);