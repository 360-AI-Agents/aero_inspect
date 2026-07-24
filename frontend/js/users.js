let allUsersCache = [];

async function loadUsers() {
  try {
    const users = await authFetch("/users/", "GET");
    allUsersCache = users;
    renderUsers(users);
    const capacity = Math.min(100, Math.round((users.length / 25) * 100));
    document.getElementById("team-capacity-text").textContent = `You are currently using ${users.length} of 25 enterprise seats.`;
    document.getElementById("capacity-bar").style.width = `${capacity}%`;
  } catch (err) {
    console.error("Failed to load users:", err);
  }
}

const ROLE_COLORS = { admin: "bg-primary/10 text-primary", inspector: "bg-blue-50 text-blue-700" };
const AVATAR_COLORS = ["bg-primary/20 text-primary", "bg-amber-100 text-amber-700", "bg-blue-100 text-blue-700", "bg-purple-100 text-purple-700"];

function renderUsers(users) {
  const tbody = document.getElementById("users-body");
  tbody.innerHTML = "";
  if (!users.length) { document.getElementById("users-empty").classList.remove("hidden"); return; }
  document.getElementById("users-empty").classList.add("hidden");

  const currentUsername = getUsername();

  users.forEach((u, idx) => {
    const initials = u.username.slice(0, 2).toUpperCase();
    const avatarColor = AVATAR_COLORS[idx % AVATAR_COLORS.length];
    const isSelf = u.username === currentUsername;

    const row = document.createElement("tr");
    row.className = "hover:bg-[#f2f4f7]";
    row.innerHTML = `
      <td class="px-8 py-5"><div class="flex items-center gap-4"><div class="w-10 h-10 rounded-full ${avatarColor} flex items-center justify-center font-bold text-sm">${initials}</div><p class="font-semibold text-sm">${u.username}${isSelf ? ' <span class="text-[10px] text-outline">(You)</span>' : ''}</p></div></td>
      <td class="px-8 py-5 font-mono text-xs text-outline">${u.email}</td>
      <td class="px-8 py-5"><span class="px-3 py-1 rounded-full text-[11px] font-bold uppercase ${ROLE_COLORS[u.role]||'bg-gray-100'}">${u.role}</span></td>
      <td class="px-8 py-5"><span class="px-3 py-1 rounded-full text-[11px] font-bold uppercase ${u.is_active ? 'bg-primary/10 text-primary' : 'bg-gray-100 text-gray-600'}">${u.is_active ? "Active" : "Disabled"}</span></td>
      <td class="px-8 py-5 text-right">
        ${isSelf
          ? `<span class="text-xs text-outline italic">—</span>`
          : `
            <button onclick="toggleUserStatus(${u.id})" title="${u.is_active ? 'Disable user' : 'Enable user'}" class="px-3 py-1 border ${u.is_active ? 'border-outline-variant text-outline hover:border-tertiary hover:text-tertiary' : 'border-primary text-primary hover:bg-primary hover:text-white'} font-bold text-xs rounded transition-all mr-2">${u.is_active ? 'Disable' : 'Enable'}</button>
            <button onclick="deleteUser(${u.id}, '${u.username}')" title="Remove user" class="text-outline hover:text-error transition-colors">🗑</button>
          `
        }
      </td>
    `;
    tbody.appendChild(row);
  });
}

async function submitNewUser(event) {
  event.preventDefault();
  const payload = {
    username: document.getElementById("new-user-username").value.trim(),
    email: document.getElementById("new-user-email").value.trim(),
    password: document.getElementById("new-user-password").value,
    role: document.getElementById("new-user-role").value,
  };
  try {
    await authFetch("/users/", "POST", payload);
    event.target.reset();
    loadUsers();
  } catch (err) {
    console.error("Failed to create user:", err);
    alert("Failed to create user — admin access required, or username already exists.");
  }
}

async function toggleUserStatus(id) {
  try {
    await authFetch(`/users/${id}/status`, "PATCH");
    loadUsers();
  } catch (err) {
    console.error("Failed to toggle user status:", err);
    alert("Failed to update user status.");
  }
}

async function deleteUser(id, username) {
  if (!confirm(`Remove user "${username}" from the system? This cannot be undone.`)) return;
  try {
    await authFetch(`/users/${id}`, "DELETE");
    loadUsers();
  } catch (err) {
    console.error("Failed to delete user:", err);
    alert("Failed to delete user.");
  }
}

async function loadAssignments() {
  try {
    const assignments = await authFetch("/site-assignments/", "GET");
    renderAssignments(assignments);
  } catch (err) {
    console.error("Failed to load site assignments:", err);
  }
}

function renderAssignments(assignments) {
  const tbody = document.getElementById("assignments-body");
  tbody.innerHTML = "";
  if (!assignments.length) { document.getElementById("assignments-empty").classList.remove("hidden"); return; }
  document.getElementById("assignments-empty").classList.add("hidden");

  assignments.forEach(a => {
    const row = document.createElement("tr");
    row.className = "hover:bg-[#f2f4f7]";
    row.innerHTML = `
      <td class="px-8 py-4 font-semibold text-sm">${a.username || "Unknown"}</td>
      <td class="px-8 py-4 text-sm">📍 ${a.location}</td>
      <td class="px-8 py-4 font-mono text-xs text-outline">${a.alert_email || "—"}</td>
      <td class="px-8 py-4 text-right"><button onclick="removeAssignment(${a.id})" class="text-outline hover:text-error transition-colors">🗑</button></td>
    `;
    tbody.appendChild(row);
  });
}

async function openAssignModal() {
  const userSelect = document.getElementById("assign-user-select");
  const locationSelect = document.getElementById("assign-location-select");

  userSelect.innerHTML = "";
  const inspectors = allUsersCache.filter(u => u.role === "inspector");
  if (!inspectors.length) {
    userSelect.innerHTML = `<option value="">No inspectors yet — add one above first</option>`;
  } else {
    inspectors.forEach(u => {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = `${u.username} (${u.email})`;
      userSelect.appendChild(opt);
    });
  }

  try {
    const cameras = await authFetch("/cameras/", "GET");
    const locations = [...new Set(cameras.map(c => c.location))];
    locationSelect.innerHTML = "";
    if (!locations.length) {
      locationSelect.innerHTML = `<option value="">No sites yet — register a camera first</option>`;
    } else {
      locations.forEach(loc => {
        const opt = document.createElement("option");
        opt.value = loc;
        opt.textContent = loc;
        locationSelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.error("Failed to load locations:", err);
  }

  document.getElementById("assign-modal").classList.add("open");
}

function closeAssignModal() {
  document.getElementById("assign-modal").classList.remove("open");
}

async function submitAssignment(event) {
  event.preventDefault();
  const userId = document.getElementById("assign-user-select").value;
  const location = document.getElementById("assign-location-select").value;
  const email = document.getElementById("assign-email-input").value.trim();

  if (!userId || !location) return;

  try {
    await authFetch("/site-assignments/", "POST", {
      user_id: Number(userId),
      location: location,
      alert_email: email || null,
    });
    closeAssignModal();
    document.getElementById("assign-email-input").value = "";
    loadAssignments();
  } catch (err) {
    console.error("Failed to create assignment:", err);
    alert("Failed to assign site — this inspector may already be assigned to this location.");
  }
}

async function removeAssignment(id) {
  if (!confirm("Remove this site assignment?")) return;
  try {
    await authFetch(`/site-assignments/${id}`, "DELETE");
    loadAssignments();
  } catch (err) {
    console.error("Failed to remove assignment:", err);
  }
}

async function exportUsersList() {
  const btn = document.getElementById("export-users-btn");
  const originalText = btn.textContent;
  btn.textContent = "Exporting…";
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/export/users`, {
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
    a.download = "aeroinspect_users.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Export failed:", err);
    alert("Failed to export users list.");
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}
document.addEventListener("DOMContentLoaded", () => {
  loadUsers().then(loadAssignments);
});