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

async function loadCameras() {
  try {
    const cameras = await authFetch("/cameras/", "GET");
    renderCameraGrid(cameras);
  } catch (err) {
    console.error("Failed to load cameras:", err);
  }
}

function renderCameraGrid(cameras) {
  const grid = document.getElementById("camera-grid");
  grid.innerHTML = "";

  if (!cameras.length) {
    document.getElementById("cameras-empty").classList.remove("hidden");
    return;
  }
  document.getElementById("cameras-empty").classList.add("hidden");
  document.getElementById("hero-subtitle").textContent =
    `Managing ${cameras.length} registered camera${cameras.length === 1 ? "" : "s"} across your active sites.`;

  cameras.forEach((cam) => {
    const isActive = cam.status === "active";
    const dotColor = isActive ? "bg-primary" : "bg-gray-400";
    const badgeColor = cam.source_type === "drone" ? "bg-tertiary" : "bg-primary";
    const photo = getPhotoForSite(`${cam.camera_name}-${cam.location}`);

    const card = document.createElement("div");
    card.className = "bg-white rounded-xl overflow-hidden shadow-sm border border-outline-variant/10 hover:-translate-y-1 transition-all duration-300";
    card.innerHTML = `
      <div class="relative h-48">
        <img class="w-full h-full object-cover ${isActive ? '' : 'grayscale opacity-70'}" src="${photo}" alt="${cam.camera_name}">
        <div class="absolute top-4 left-4 flex items-center gap-2 px-2 py-1 bg-black/60 backdrop-blur-md rounded-md">
          <div class="w-2 h-2 rounded-full ${dotColor}"></div>
          <span class="text-[10px] font-bold text-white uppercase tracking-widest">${isActive ? "Live Stream" : "Offline"}</span>
        </div>
        <div class="absolute top-4 right-4 ${badgeColor} text-white text-[10px] font-bold px-2 py-1 rounded uppercase">${cam.source_type}</div>
      </div>
      <div class="p-5">
        <div class="flex justify-between items-start mb-4">
          <div>
            <h4 class="font-headline font-bold text-on-surface">${cam.camera_name}</h4>
            <p class="text-xs text-outline flex items-center gap-1 mt-1">📍 ${cam.location}</p>
          </div>
        </div>
        <div class="flex gap-2">
          <button onclick='openCameraFeedModal(${JSON.stringify(cam).replace(/'/g, "&apos;")})' class="flex-1 py-2 bg-[#f2f4f7] hover:bg-primary/10 hover:text-primary rounded-lg text-xs font-bold transition-colors">View Feed</button>
          <button onclick="deleteCamera(${cam.id})" class="w-10 h-10 flex items-center justify-center border border-outline-variant rounded-lg hover:border-error hover:text-error transition-colors">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-4 h-4"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14z"/></svg>
          </button>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });
}

function openCameraFeedModal(cam) {
  const photo = getPhotoForSite(`${cam.camera_name}-${cam.location}`);
  document.getElementById("camera-feed-modal").querySelector("img").src = photo;
  document.getElementById("feed-camera-name").textContent = cam.camera_name;
  document.getElementById("feed-camera-id").textContent = `CAM-${String(cam.id).padStart(3, "0")}`;
  document.getElementById("feed-camera-location").textContent = cam.location;
  document.getElementById("feed-camera-type").textContent = cam.source_type.toUpperCase();
  document.getElementById("feed-camera-status-dot").className =
    `w-2 h-2 rounded-full ${cam.status === 'active' ? 'bg-primary animate-pulse' : 'bg-gray-400'}`;
  document.getElementById("feed-camera-status-text").textContent = cam.status === 'active' ? 'STREAMING' : 'OFFLINE';
  document.getElementById("feed-timestamp").textContent = new Date().toLocaleString("en-US", {
    weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit"
  });
  document.getElementById("camera-feed-modal").classList.add("open");
}

function closeCameraFeedModal() {
  document.getElementById("camera-feed-modal").classList.remove("open");
}

async function submitNewCamera(event) {
  event.preventDefault();
  const name = document.getElementById("new-camera-name").value.trim();
  const location = document.getElementById("new-camera-location").value.trim();
  const sourceType = document.getElementById("new-camera-source").value;
  if (!name || !location) return;

  try {
    const params = new URLSearchParams({ camera_name: name, location, source_type: sourceType });
    await authFetch(`/cameras/?${params.toString()}`, "POST");
    document.getElementById("new-camera-name").value = "";
    document.getElementById("new-camera-location").value = "";
    loadCameras();
  } catch (err) {
    console.error("Failed to create camera:", err);
  }
}

async function deleteCamera(id) {
  if (!confirm("Delete this camera?")) return;
  try {
    await authFetch(`/cameras/${id}`, "DELETE");
    loadCameras();
  } catch (err) {
    console.error("Failed to delete camera:", err);
  }
}

document.addEventListener("DOMContentLoaded", loadCameras);