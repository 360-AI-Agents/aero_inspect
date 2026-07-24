const SEV_CONFIG = {
  critical: { color: "bg-error", label: "Critical Severity Alerts", dot: "🔴" },
  high: { color: "bg-tertiary", label: "High Severity Alerts", dot: "🟠" },
  medium: { color: "bg-amber-500", label: "Medium Severity Alerts", dot: "🟡" },
  low: { color: "bg-primary", label: "Low Severity Alerts", dot: "🟢" },
};

const PIN_POSITIONS = [
  { top: "30%", left: "35%" }, { top: "62%", left: "70%" },
  { top: "45%", left: "18%" }, { top: "18%", left: "62%" },
  { top: "70%", left: "40%" },
];

async function loadAlerts() {
  try {
    const data = await authFetch("/alerts/", "GET");
    document.getElementById("count-critical").textContent = data.summary.critical;
    document.getElementById("count-high").textContent = data.summary.high;
    document.getElementById("count-medium").textContent = data.summary.medium;
    document.getElementById("count-low").textContent = data.summary.low;

    const total = data.summary.critical + data.summary.high + data.summary.medium + data.summary.low;
    renderTrends(data.summary, total);
    renderMapPins(data);
    renderHazardTags(data);
    renderSections(data, total);
  } catch (err) {
    console.error("Failed to load alerts:", err);
  }
}

function renderTrends(summary, total) {
  const critPct = total ? Math.round((summary.critical / total) * 100) : 0;
  const highPct = total ? Math.round((summary.high / total) * 100) : 0;
  const safePct = total ? Math.round((summary.low / total) * 100) : 0;
  document.getElementById("trend-critical-pct").textContent = `${critPct}%`;
  document.getElementById("trend-critical-bar").style.width = `${critPct}%`;
  document.getElementById("trend-high-pct").textContent = `${highPct}%`;
  document.getElementById("trend-high-bar").style.width = `${highPct}%`;
  document.getElementById("trend-safe-pct").textContent = `${safePct}%`;
  document.getElementById("trend-safe-bar").style.width = `${safePct}%`;
}

function renderMapPins(data) {
  const glowContainer = document.getElementById("heat-glows");
  const pinContainer = document.getElementById("map-pins");
  glowContainer.innerHTML = "";
  pinContainer.innerHTML = "";

  const topAlerts = [...(data.critical || []).slice(0, 3), ...(data.high || []).slice(0, 2)];

  topAlerts.forEach((a, i) => {
    const pos = PIN_POSITIONS[i % PIN_POSITIONS.length];
    const isCritical = a.severity === "critical" || (data.critical || []).includes(a);
    const color = isCritical ? "bg-error" : "bg-tertiary";
    const icon = isCritical ? "❗" : "⚠️";

    const glow = document.createElement("div");
    glow.className = `absolute w-32 h-32 ${isCritical ? "bg-error/20" : "bg-tertiary/20"} rounded-full blur-2xl`;
    glow.style.top = pos.top; glow.style.left = pos.left;
    glowContainer.appendChild(glow);

    const pin = document.createElement("div");
    pin.className = "absolute map-pin group";
    pin.style.top = pos.top; pin.style.left = pos.left;
    pin.innerHTML = `
      <div class="w-6 h-6 ${color} text-white rounded-full flex items-center justify-center border-2 border-white cursor-pointer hover:scale-125 transition-transform text-[10px]">${icon}</div>
      <div class="map-pin-tooltip absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 p-2 bg-[#191c1e] text-white text-xs rounded shadow-xl z-10">
        <p class="font-bold border-b border-white/20 pb-1 mb-1">${a.inspection_name}</p>
        <p>${a.violation_name} — ${a.location || "Unknown location"}</p>
      </div>
    `;
    pinContainer.appendChild(pin);
  });
}

function renderHazardTags(data) {
  const container = document.getElementById("hazard-tags");
  container.innerHTML = "";
  const allItems = [...(data.critical||[]), ...(data.high||[]), ...(data.medium||[]), ...(data.low||[])];
  const unique = [...new Set(allItems.map(a => a.violation_name))].slice(0, 4);

  if (!unique.length) { container.innerHTML = `<span class="text-xs text-outline">No data yet</span>`; return; }
  unique.forEach(v => {
    const tag = document.createElement("span");
    tag.className = "px-2 py-1 bg-[#f2f4f7] text-[10px] font-bold rounded uppercase tracking-tight";
    tag.textContent = v;
    container.appendChild(tag);
  });
}

function renderSections(data, total) {
  const container = document.getElementById("alert-sections");
  container.innerHTML = "";

  if (total === 0) { document.getElementById("alerts-empty").classList.remove("hidden"); return; }
  document.getElementById("alerts-empty").classList.add("hidden");

  ["critical", "high", "medium", "low"].forEach((sev, idx) => {
    const items = data[sev] || [];
    const cfg = SEV_CONFIG[sev];
    const section = document.createElement("div");
    section.className = `bg-white rounded-xl shadow-sm border border-outline-variant/10 overflow-hidden ${idx === 0 ? "collapse-open" : ""}`;
    section.innerHTML = `
      <button onclick="this.closest('.bg-white').classList.toggle('collapse-open')" class="w-full flex items-center justify-between p-4 hover:bg-[#f2f4f7] transition-colors text-left">
        <div class="flex items-center gap-4">
          <span class="w-2 h-8 ${cfg.color} rounded-full"></span>
          <h5 class="font-headline text-lg flex items-center gap-3">${cfg.dot} ${cfg.label} <span class="px-2 py-0.5 bg-[#f2f4f7] text-xs font-bold rounded-full">${items.length} Active</span></h5>
        </div>
        <svg class="chevron w-5 h-5 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
      </button>
      <div class="collapse-content px-4 pb-4 space-y-3">
        ${items.length === 0 ? `<p class="text-sm text-outline text-center py-4">No ${sev} alerts.</p>` :
          items.map(a => `
            <div class="flex gap-4 p-4 rounded-lg bg-[#f7f9fc] border border-outline-variant/20 hover:border-error/30 transition-all">
              <div class="w-32 h-20 rounded overflow-hidden flex-shrink-0 bg-gray-200">
                <img class="w-full h-full object-cover" src="https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=300&q=60">
              </div>
              <div class="flex-1 grid grid-cols-4 gap-4">
                <div>
                  <p class="text-[10px] text-outline uppercase tracking-tight">Inspection / Camera</p>
                  <p class="font-bold text-sm">${a.inspection_name}</p>
                  <p class="font-mono text-xs text-outline">${a.camera_name || "Unassigned"}</p>
                </div>
                <div>
                  <p class="text-[10px] text-outline uppercase tracking-tight">Violation Description</p>
                  <p class="text-sm font-semibold ${sev === 'critical' ? 'text-error' : sev === 'high' ? 'text-tertiary' : 'text-on-surface'}">${a.violation_name}</p>
                  <p class="text-xs text-outline">×${a.count} occurrence(s)</p>
                </div>
                <div>
                  <p class="text-[10px] text-outline uppercase tracking-tight">Status & Severity</p>
                  <span class="w-fit inline-block px-2 py-0.5 bg-white text-[10px] font-bold rounded-full border ${sev === 'critical' ? 'border-error/30 text-error' : 'border-outline-variant text-outline'} mt-1">${sev.toUpperCase()}</span>
                </div>
                <div class="text-right flex flex-col justify-between">
                  <p class="font-mono text-xs text-outline">${formatDate(a.created_at)}</p>
                </div>
              </div>
            </div>
          `).join("")}
      </div>
    `;
    container.appendChild(section);
  });
}

document.addEventListener("DOMContentLoaded", loadAlerts);