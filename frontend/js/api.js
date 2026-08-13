const API_BASE = "https://aeroinspect-backend.orange-tree-069a.workers.dev";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

function formatDate(isoString) {
  if (!isoString) return "—";
  const d = new Date(isoString);
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function statusBadgeClasses(status) {
  const map = {
    Safe: "bg-primary/10 text-primary",
    flagged: "bg-amber-50 text-amber-700",
    unsafe: "bg-red-50 text-red-700",
  };
  return map[status] || "bg-gray-100 text-gray-600";
}