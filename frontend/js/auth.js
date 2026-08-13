function saveSession(token, username, role) {
  localStorage.setItem("aeroinspect_token", token);
  localStorage.setItem("aeroinspect_username", username);
  localStorage.setItem("aeroinspect_role", role);
}

function getToken() { return localStorage.getItem("aeroinspect_token"); }
function getUsername() { return localStorage.getItem("aeroinspect_username"); }
function getRole() { return localStorage.getItem("aeroinspect_role"); }

function clearSession() {
  localStorage.removeItem("aeroinspect_token");
  localStorage.removeItem("aeroinspect_username");
  localStorage.removeItem("aeroinspect_role");
}

function logout() {
  clearSession();
  window.location.href = "login.html";
}

function getPageName() {
  // Cloudflare Pages serves clean URLs (login.html -> /login), so pathname
  // won't always carry the .html suffix -- normalize before comparing.
  let name = window.location.pathname.split("/").pop() || "index";
  return name.replace(/\.html$/, "");
}

function isLoginPage() {
  return getPageName() === "login";
}

function requireAuth() {
  if (isLoginPage()) return;
  if (!getToken()) window.location.href = "login.html";
}

async function loginUser(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Invalid username or password");
  const data = await res.json();
  saveSession(data.access_token, data.username, data.role);
  return data;
}

async function authFetch(path, method, body) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 || res.status === 403) {
    clearSession();
    window.location.href = "login.html";
    return;
  }
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status}`);
  return res.json();
}

function getInitials(name) {
  return name.slice(0, 2).toUpperCase();
}

function renderUserBadge() {
  const badge = document.getElementById("user-badge");
  if (badge) {
    const role = getRole();
    badge.innerHTML = `
      <span class="px-3 py-1 bg-primary/10 text-primary font-semibold text-xs rounded-full uppercase tracking-widest">${role}</span>
      <button onclick="logout()" title="Log out" class="w-9 h-9 rounded-full bg-red-50 text-red-600 flex items-center justify-center hover:bg-red-100 transition-colors">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-4 h-4"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      </button>
    `;
  }

  const sidebarUser = document.getElementById("sidebar-user") || document.getElementById("user-badge-sidebar");
  if (sidebarUser) {
    const username = getUsername();
    const role = getRole();
    sidebarUser.innerHTML = `
      <div class="w-9 h-9 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-xs flex-shrink-0">${getInitials(username)}</div>
      <div class="overflow-hidden">
        <p class="text-white text-sm font-semibold truncate">${username}</p>
        <p class="text-white/50 text-xs truncate capitalize">${role}</p>
      </div>
    `;
  }
}

function applyRoleVisibility() {
  if (isLoginPage()) return;
  const role = getRole();
  if (role === "admin") return;

  document.querySelectorAll('[data-admin-only="true"]').forEach(el => {
    el.style.display = "none";
  });

  const adminOnlyPages = ["settings", "users", "safety-management"];
  if (adminOnlyPages.includes(getPageName())) {
    window.location.href = "index.html";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  requireAuth();
  renderUserBadge();
  applyRoleVisibility();
});