let currentReportInspectionId = null;

const DONUT_COLORS = ["#059669", "#545f73", "#b15f00", "#6d7a72", "#ba1a1a", "#3378D8", "#D8492B", "#7C8A99", "#402C08"];

async function populateInspectionSelect() {
  try {
    const inspections = await authFetch("/inspections/?limit=100", "GET");
    const select = document.getElementById("report-inspection-select");
    select.innerHTML = `<option value="">Select an inspection...</option>`;
    inspections.forEach((insp) => {
      const opt = document.createElement("option");
      opt.value = insp.id;
      opt.textContent = `${insp.inspection_name} — ${formatDate(insp.created_at)}`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to load inspections:", err);
  }
}

async function generateReport() {
  const id = document.getElementById("report-inspection-select").value;
  if (!id) return;
  currentReportInspectionId = id;

  try {
    const report = await authFetch(`/reports/${id}`, "GET");
    document.getElementById("report-title").textContent = report.report_title;
    document.getElementById("report-generated-at").textContent = `Generated ${formatDate(report.generated_at)}`;
    document.getElementById("report-id").textContent = `#AI-${String(id).padStart(4, "0")}`;
    document.getElementById("report-summary").textContent = report.summary;

    const entries = Object.entries(report.violation_breakdown).filter(([_, v]) => v > 0);
    const total = entries.reduce((s, [_, v]) => s + v, 0);
    document.getElementById("report-donut-total").textContent = total;

    renderDonutSVG(entries, total);
    renderBreakdownList(entries, total);

    const inspection = await authFetch(`/inspections/${id}`, "GET");
    const isCompliant = inspection.compliance_score >= 90;
    document.getElementById("report-status").textContent = isCompliant ? "COMPLIANT" : inspection.inspection_status.toUpperCase();
    document.getElementById("report-confidence").textContent = `${inspection.compliance_score}%`;

    document.getElementById("report-body").classList.remove("hidden");
    document.getElementById("report-body").classList.add("flex");
    document.getElementById("report-empty").classList.add("hidden");
  } catch (err) {
    console.error("Failed to generate report:", err);
  }
}

function renderDonutSVG(entries, total) {
  const svg = document.getElementById("report-donut");
  svg.innerHTML = `<circle cx="50" cy="50" fill="transparent" r="40" stroke="#e6e8eb" stroke-width="12"></circle>`;

  if (total === 0) return;

  const circumference = 2 * Math.PI * 40;
  let offsetAccum = 0;

  entries.forEach(([cat, count], i) => {
    const pct = count / total;
    const dash = pct * circumference;
    const gap = circumference - dash;
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", "50");
    circle.setAttribute("cy", "50");
    circle.setAttribute("r", "40");
    circle.setAttribute("fill", "transparent");
    circle.setAttribute("stroke", DONUT_COLORS[i % DONUT_COLORS.length]);
    circle.setAttribute("stroke-width", "12");
    circle.setAttribute("stroke-linecap", "round");
    circle.setAttribute("stroke-dasharray", `${dash}, ${gap}`);
    circle.setAttribute("stroke-dashoffset", `${-offsetAccum}`);
    svg.appendChild(circle);
    offsetAccum += dash;
  });
}

function renderBreakdownList(entries, total) {
  const list = document.getElementById("report-breakdown");
  list.innerHTML = "";

  if (!entries.length) {
    list.innerHTML = `<li class="text-sm text-outline text-center py-4">No violations recorded for this inspection.</li>`;
    return;
  }

  entries.forEach(([cat, count], i) => {
    const pct = Math.round((count / total) * 100);
    const li = document.createElement("li");
    li.className = "flex items-center justify-between";
    li.innerHTML = `
      <div class="flex items-center gap-3">
        <span class="w-3 h-3 rounded-full" style="background:${DONUT_COLORS[i % DONUT_COLORS.length]}"></span>
        <span class="text-sm capitalize">${cat.replace(/_/g, " ")}</span>
      </div>
      <span class="font-mono font-bold text-sm">${String(count).padStart(2,"0")} (${String(pct).padStart(2,"0")}%)</span>
    `;
    list.appendChild(li);
  });
}

async function downloadReportPdf(event) {
  if (!currentReportInspectionId) return;

  const btn = event ? event.target : null;
  const originalText = btn ? btn.textContent : null;
  if (btn) { btn.textContent = "Opening PDF…"; btn.disabled = true; }

  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/reports/${currentReportInspectionId}/pdf`, {
      headers: { "Authorization": `Bearer ${token}` },
    });

    if (res.status === 401 || res.status === 403) {
      clearSession();
      window.location.href = "login.html";
      return;
    }
    if (!res.ok) throw new Error(`PDF fetch failed: ${res.status}`);

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, "_blank");

    setTimeout(() => window.URL.revokeObjectURL(url), 60000);
  } catch (err) {
    console.error("Failed to open PDF:", err);
    alert("Failed to open the report PDF. Please try again.");
  } finally {
    if (btn) { btn.textContent = originalText; btn.disabled = false; }
  }
}

async function exportReportsList() {
  const btn = document.getElementById("export-reports-btn");
  const originalText = btn.textContent;
  btn.textContent = "Exporting…";
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/export/reports`, {
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
    a.download = "aeroinspect_reports.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Export failed:", err);
    alert("Failed to export reports list.");
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", populateInspectionSelect);