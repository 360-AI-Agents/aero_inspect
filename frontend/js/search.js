let searchDebounceTimer = null;

function initSearch() {
  const input = document.getElementById("global-search");
  const resultsBox = document.getElementById("search-results");
  if (!input || !resultsBox) return;

  input.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    const query = input.value.trim();

    if (query.length < 2) {
      resultsBox.classList.add("hidden");
      resultsBox.innerHTML = "";
      return;
    }
    searchDebounceTimer = setTimeout(() => runSearch(query), 300);
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#global-search") && !e.target.closest("#search-results")) {
      resultsBox.classList.add("hidden");
    }
  });

  checkForDeepLinkedInspection();
}

async function runSearch(query) {
  try {
    const data = await apiGet(`/search/?q=${encodeURIComponent(query)}`);
    renderSearchResults(data.results);
  } catch (err) {
    console.error("Search failed:", err);
  }
}

function renderSearchResults(results) {
  const resultsBox = document.getElementById("search-results");
  resultsBox.innerHTML = "";

  if (!results.length) {
    resultsBox.innerHTML = `<div class="p-4 text-sm text-outline text-center">No matches found.</div>`;
    resultsBox.classList.remove("hidden");
    return;
  }

  results.forEach((item) => {
    const el = document.createElement("div");
    el.className = "flex flex-col gap-0.5 px-4 py-3 cursor-pointer hover:bg-[#f2f4f7] border-b border-outline-variant/10 last:border-0";
    el.innerHTML = `
      <span class="text-[10px] text-primary uppercase tracking-wide font-semibold">${item.type}</span>
      <span class="text-sm font-semibold">${item.title}</span>
      <span class="text-xs text-outline">${item.subtitle}</span>
    `;
    el.onclick = () => handleSearchResultClick(item);
    resultsBox.appendChild(el);
  });
  resultsBox.classList.remove("hidden");
}

function handleSearchResultClick(item) {
  const resultsBox = document.getElementById("search-results");
  const searchInput = document.getElementById("global-search");
  resultsBox.classList.add("hidden");
  searchInput.value = "";

  if (item.type === "inspection") {
    const currentPage = window.location.pathname.split("/").pop();
    if (currentPage === "inspections.html" && typeof openInspectionDetail === "function") {
      const detailPanel = document.getElementById("detail-panel");
      const detailEmpty = document.getElementById("detail-empty");
      if (detailPanel) detailPanel.style.display = "none";
      if (detailEmpty) detailEmpty.style.display = "block";
      openInspectionDetail(item.id);
    } else {
      window.location.href = `inspections.html?open=${item.id}`;
    }
  } else {
    window.location.href = item.link;
  }
}

function checkForDeepLinkedInspection() {
  const params = new URLSearchParams(window.location.search);
  const openId = params.get("open");
  if (openId && typeof openInspectionDetail === "function") {
    setTimeout(() => openInspectionDetail(Number(openId)), 400);
  }
}

document.addEventListener("DOMContentLoaded", initSearch);