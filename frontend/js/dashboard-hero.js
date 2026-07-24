// ============================================================
// dashboard-hero.js — hero carousel, camera story strip,
// donut chart, and camera mosaic. Reads real camera data
// where available; uses labeled placeholder photography
// since no live video pipeline exists yet.
// ============================================================

const SITE_PHOTOS = [
  "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=1600&q=80",
  "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=1600&q=80",
  "https://images.unsplash.com/photo-1590496793907-7f8be6a7b0ad?w=1600&q=80",
];

let heroSlideIndex = 0;

function initHeroCarousel() {
  const slider = document.getElementById("hero-slider");
  if (!slider) return;

  slider.innerHTML = SITE_PHOTOS.map((url, i) =>
    `<div class="hero-slide ${i === 0 ? "active" : ""}" style="background-image:url('${url}')"></div>`
  ).join("");

  setInterval(() => {
    const slides = slider.querySelectorAll(".hero-slide");
    slides[heroSlideIndex].classList.remove("active");
    heroSlideIndex = (heroSlideIndex + 1) % slides.length;
    slides[heroSlideIndex].classList.add("active");
  }, 6000);
}

async function initCameraStoryStrip() {
  const strip = document.getElementById("command-strip");
  if (!strip) return;

  try {
    const cameras = await apiGet("/cameras/");
    strip.innerHTML = "";

    if (!cameras.length) {
      strip.innerHTML = `<div style="color:var(--text-muted); font-size:12.5px;">No cameras registered yet — add one from the Cameras page.</div>`;
      return;
    }

    cameras.slice(0, 8).forEach((cam, i) => {
      const photo = SITE_PHOTOS[i % SITE_PHOTOS.length];
      const isActive = cam.status === "active";
      const el = document.createElement("div");
      el.className = "story-item";
      el.onclick = () => { window.location.href = "cameras.html"; };
      el.innerHTML = `
        <div class="story-ring ${isActive ? "" : "story-ring-inactive"}">
          <div class="story-photo" style="background-image:url('${photo}')"></div>
        </div>
        <span class="story-label">${cam.camera_name}</span>
      `;
      strip.appendChild(el);
    });
  } catch (err) {
    console.error("Failed to load camera story strip:", err);
  }
}

async function initCameraMosaic() {
  const grid = document.getElementById("mosaic-grid");
  if (!grid) return;

  try {
    const cameras = await apiGet("/cameras/");
    grid.innerHTML = "";

    if (!cameras.length) {
      grid.innerHTML = `<div class="empty-state">No cameras registered yet.</div>`;
      return;
    }

    cameras.slice(0, 4).forEach((cam, i) => {
      const card = document.createElement("div");
      card.className = "mosaic-card";

      if (cam.status === "active") {
        const photo = SITE_PHOTOS[i % SITE_PHOTOS.length];
        card.innerHTML = `
          <img src="${photo}" alt="${cam.camera_name}">
          <div class="mosaic-tag"><span class="kpi-live-dot"></span> ${cam.camera_name.toUpperCase()}</div>
        `;
      } else {
        card.innerHTML = `
          <div class="mosaic-offline">
            <span>⌀</span>
            <span>${cam.camera_name.toUpperCase()} — OFFLINE</span>
          </div>
        `;
      }
      grid.appendChild(card);
    });
  } catch (err) {
    console.error("Failed to load camera mosaic:", err);
  }
}

function renderDonutChart(breakdown) {
  const donutEl = document.getElementById("donut-chart");
  const legendEl = document.getElementById("donut-legend");
  const holeValueEl = document.getElementById("donut-hole-value");
  if (!donutEl || !legendEl) return;

  const colors = ["#059669", "#F59E0B", "#DC2626", "#3378D8", "#8B5CF6", "#EC4899", "#64748B", "#0EA5E9", "#D8492B"];
  const entries = Object.entries(breakdown).filter(([, v]) => v > 0);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  holeValueEl.textContent = total;

  if (total === 0) {
    donutEl.style.background = "var(--border)";
    legendEl.innerHTML = `<div class="empty-state" style="padding:0;">No violations recorded yet.</div>`;
    return;
  }

  let gradientParts = [];
  let cursor = 0;
  entries.forEach(([, count], i) => {
    const pct = (count / total) * 100;
    gradientParts.push(`${colors[i % colors.length]} ${cursor}% ${cursor + pct}%`);
    cursor += pct;
  });
  donutEl.style.background = `conic-gradient(${gradientParts.join(", ")})`;

  legendEl.innerHTML = entries.map(([cat, count], i) => `
    <div class="donut-legend-row">
      <div class="donut-legend-left">
        <span class="donut-legend-dot" style="background:${colors[i % colors.length]}"></span>
        <span class="donut-legend-name">${cat.replace(/_/g, " ")}</span>
      </div>
      <span class="donut-legend-value">${count}</span>
    </div>
  `).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  initHeroCarousel();
  initCameraStoryStrip();
  initCameraMosaic();
});