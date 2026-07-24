async function loadAnalytics() {
  try {
    const data = await authFetch("/dashboard/", "GET");
    document.getElementById("an-total-inspections").textContent = data.inspection_history.length;
    document.getElementById("an-total-violations").textContent = data.overview.total_violations;
    document.getElementById("an-avg-compliance").textContent = `${data.overview.compliance_score}%`;

    renderDonut(data.violation_breakdown);
    renderBars(data.inspection_history);
    renderLogs(data.inspection_history);
  } catch (err) {
    console.error("Failed to load analytics:", err);
  }
}

const COLORS = { helmet:"#059669", vest:"#3378D8", scaffolding:"#D89A33", debris:"#8d4b00", restricted_zone:"#ba1a1a", fall_protection:"#D8492B", heavy_equipment:"#7C8A99", unsafe_behaviour:"#545f73", material_storage:"#6d7a72" };

function renderDonut(breakdown) {
  const entries = Object.entries(breakdown).filter(([_, v]) => v > 0);
  const total = entries.reduce((s, [_, v]) => s + v, 0);
  document.getElementById("an-donut-total").textContent = total;
  const donut = document.getElementById("an-donut");
  const legend = document.getElementById("an-legend");
  legend.innerHTML = "";

  if (total === 0) { donut.style.background = "#e0e3e6"; return; }

  let cum = 0;
  const stops = entries.map(([cat, c]) => {
    const pct = (c/total)*100; const start = cum; cum += pct;
    return `${COLORS[cat]||"#999"} ${start}% ${cum}%`;
  });
  donut.style.background = `conic-gradient(${stops.join(", ")})`;

  entries.forEach(([cat, c]) => {
    const row = document.createElement("div");
    row.className = "flex items-center justify-between text-sm";
    row.innerHTML = `<div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full" style="background:${COLORS[cat]||'#999'}"></span><span class="capitalize">${cat.replace(/_/g," ")}</span></div><span class="font-mono font-bold">${c}</span>`;
    legend.appendChild(row);
  });
}

function renderBars(inspections) {
  const bars = document.getElementById("an-bars");
  bars.innerHTML = "";
  const recent = inspections.slice(0, 6).reverse();
  if (!recent.length) { bars.innerHTML = `<p class="text-sm text-outline">No data yet.</p>`; return; }

  recent.forEach(insp => {
    const height = Math.max(insp.compliance_score, 5);
    const color = insp.compliance_score >= 90 ? "bg-primary" : insp.compliance_score >= 70 ? "bg-amber-400" : "bg-error";
    const col = document.createElement("div");
    col.className = "flex-1 flex flex-col items-center gap-2 h-full justify-end";
    col.innerHTML = `
      <span class="text-xs font-mono font-bold">${insp.compliance_score}%</span>
      <div class="w-8 ${color} rounded-t" style="height:${height}%"></div>
      <span class="text-[10px] text-outline truncate w-full text-center">${insp.inspection_name.slice(0,10)}</span>
    `;
    bars.appendChild(col);
  });
}

function renderLogs(inspections) {
  const tbody = document.getElementById("an-logs");
  tbody.innerHTML = "";
  inspections.slice(0, 8).forEach(insp => {
    const row = document.createElement("tr");
    row.className = "hover:bg-[#f2f4f7]";
    row.innerHTML = `
      <td class="px-6 py-4 font-semibold text-sm">${insp.inspection_name}</td>
      <td class="px-6 py-4 font-mono text-xs text-outline">${formatDate(insp.created_at)}</td>
      <td class="px-6 py-4 font-mono text-sm">${insp.compliance_score}</td>
      <td class="px-6 py-4"><span class="px-2.5 py-1 rounded-full text-[11px] font-bold uppercase ${statusBadgeClasses(insp.inspection_status)}">${insp.inspection_status}</span></td>
    `;
    tbody.appendChild(row);
  });
}

document.addEventListener("DOMContentLoaded", loadAnalytics);