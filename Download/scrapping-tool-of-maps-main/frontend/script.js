const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const downloadBtn = document.getElementById("downloadBtn");
const statusEl = document.getElementById("status");
const bodyEl = document.getElementById("resultsBody");
const statsPanel = document.getElementById("statsPanel");
const modeDescription = document.getElementById("modeDescription");
const extractionModeSelect = document.getElementById("extractionMode");
const historyInfo = document.getElementById("historyInfo");
const historyCount = document.getElementById("historyCount");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");
const historyFilesList = document.getElementById("historyFilesList");
const refreshHistoryFilesBtn = document.getElementById("refreshHistoryFilesBtn");
const selectAllHistoryFilesBtn = document.getElementById("selectAllHistoryFilesBtn");
const clearSelectedHistoryFilesBtn = document.getElementById("clearSelectedHistoryFilesBtn");
const locationSuggestions = document.getElementById("locationSuggestions");
const resultSearch = document.getElementById("resultSearch");
const resultCountEl = document.getElementById("resultCount");

// Progress bar elements
const progressPanel = document.getElementById("progressPanel");
const progressFill = document.getElementById("progressFill");
const progressPercent = document.getElementById("progressPercent");
const progressCounts = document.getElementById("progressCounts");
const progressElapsed = document.getElementById("progressElapsed");
const progressPhase = document.getElementById("progressPhase");
const progressMessage = document.getElementById("progressMessage");
const progressTrack = document.getElementById("progressTrack");

const MAX_RESULTS_LIMIT = 500;
const LOCATION_SUGGESTION_LIMIT = 8;

let pollingId = null;
let outputHistoryFiles = [];
const selectedHistoryFiles = new Set();
let activeScrapeController = null;
let stopRequestedByUser = false;
let lastRenderedCount = 0;
let backendCooldownUntil = 0;
let locationSuggestController = null;
let locationSuggestTimer = null;

// Progress state
let currentRows = [];
let progressTarget = 50;
let scrapeStartTime = 0;
let elapsedTimerId = null;
let displayedPercent = 0;

function canCallBackend() {
  return Date.now() >= backendCooldownUntil;
}

function markBackendUnavailable(message = "Backend is offline. Start the server (see run.txt / setup_and_run.sh).") {
  backendCooldownUntil = Date.now() + 5000;
  setStatus(message);
}

// ============================================================================
// MODE DESCRIPTIONS
// ============================================================================
const modeDescriptions = {
  ultra: `<small><strong>Ultra Deep:</strong> Uses ALL extraction engines (business_extractor, email_extractor, enhanced_scraper, deep_scraper) in parallel with cross-verification. Highest accuracy, slowest speed. Best for important lead generation.</small>`,
  maximum: `<small><strong>💎 Maximum:</strong> The ultimate mode — Google Maps + DuckDuckGo/Bing web search + ALL analysis engines + full cross-verification. Finds businesses NOT on Google Maps. Highest data completeness.</small>`,
  deep: `<small><strong>Deep:</strong> Multi-source extraction - Google Maps → Website analysis → Google Search cross-verification. Finds Instagram, Facebook, WhatsApp and emails from multiple sources.</small>`,
  enhanced: `<small><strong>Enhanced:</strong> Google Maps + comprehensive website analysis. Extracts tech stack, chatbots, analytics. Good balance of speed and data quality.</small>`,
  basic: `<small><strong>Basic:</strong> Fast Maps-only extraction. Gets name, phone, address, rating, website from Google Maps only. Fastest option when you need quick results.</small>`
};

function updateModeDescription() {
  const mode = extractionModeSelect.value;
  if (modeDescription && modeDescriptions[mode]) {
    modeDescription.innerHTML = modeDescriptions[mode];
  }
}

if (extractionModeSelect) {
  extractionModeSelect.addEventListener("change", updateModeDescription);
  updateModeDescription();
}

// ============================================================================
// PROGRESS BAR
// ============================================================================
function formatElapsed(ms) {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function phaseFromMessage(message) {
  const msg = (message || "").toLowerCase();
  if (msg.includes("web") && msg.includes("search")) return "🌐 Searching the web…";
  if (msg.includes("enrich")) return "✉️ Enriching contacts…";
  if (msg.includes("merg")) return "🔀 Merging sources…";
  if (msg.includes("verif")) return "✅ Cross-verifying…";
  if (msg.includes("captcha")) return "🛑 Captcha — solve in browser";
  if (msg.includes("stopping")) return "⏹ Stopping…";
  if (msg.includes("scraping") || msg.includes("running")) return "🗺️ Extracting leads…";
  return "⚡ Working…";
}

function resetProgressUI() {
  progressPanel.classList.remove("active", "done", "stopped", "error");
  progressTrack.classList.remove("indeterminate");
  progressPanel.setAttribute("aria-hidden", "true");
  progressFill.style.width = "0%";
  progressPercent.textContent = "0%";
  progressCounts.textContent = "0 / 0";
  progressElapsed.textContent = "0s";
  displayedPercent = 0;
}

function startProgress(target) {
  progressTarget = Math.max(1, Number(target) || 50);
  scrapeStartTime = Date.now();
  displayedPercent = 0;
  progressPanel.classList.remove("done", "stopped", "error");
  progressPanel.classList.add("active");
  progressTrack.classList.add("indeterminate"); // until first count arrives
  progressPanel.setAttribute("aria-hidden", "false");
  progressPhase.textContent = "⚡ Starting engines…";
  progressMessage.textContent = "Launching parallel workers…";
  progressCounts.textContent = `0 / ${progressTarget}`;
  progressPercent.textContent = "0%";
  progressFill.style.width = "0%";

  clearInterval(elapsedTimerId);
  elapsedTimerId = setInterval(() => {
    progressElapsed.textContent = formatElapsed(Date.now() - scrapeStartTime);
  }, 1000);
}

function updateProgress(count, message) {
  if (!progressPanel.classList.contains("active")) return;

  const n = Number(count) || 0;
  if (n > 0) progressTrack.classList.remove("indeterminate");

  // Cap at 99% while running; only completion sets 100%.
  let pct = Math.min(99, Math.round((n / progressTarget) * 100));
  if (n === 0) pct = displayedPercent; // keep indeterminate look
  displayedPercent = Math.max(displayedPercent, pct);

  progressTrack.setAttribute("aria-valuenow", String(displayedPercent));
  if (!progressTrack.classList.contains("indeterminate")) {
    progressFill.style.width = `${displayedPercent}%`;
    progressPercent.textContent = `${displayedPercent}%`;
  } else {
    progressPercent.textContent = "…";
  }

  progressCounts.textContent = `${n} / ${progressTarget}`;
  progressPhase.textContent = phaseFromMessage(message);
  if (message) progressMessage.textContent = message;
}

function finishProgress(state, count, message) {
  clearInterval(elapsedTimerId);
  progressTrack.classList.remove("indeterminate");
  progressPanel.classList.remove("done", "stopped", "error");

  const n = Number(count) || 0;
  let pct = 100;
  if (state === "stopped" || state === "error") {
    pct = Math.min(100, Math.round((n / progressTarget) * 100)) || 0;
  }

  progressPanel.classList.add(state === "completed" ? "done" : state === "stopped" ? "stopped" : "error");
  progressFill.style.width = `${pct}%`;
  progressPercent.textContent = `${pct}%`;
  progressTrack.setAttribute("aria-valuenow", String(pct));
  progressCounts.textContent = `${n} / ${progressTarget}`;
  progressElapsed.textContent = formatElapsed(Date.now() - scrapeStartTime);

  if (state === "completed") progressPhase.textContent = "✅ Completed";
  else if (state === "stopped") progressPhase.textContent = "⏹ Stopped";
  else progressPhase.textContent = "⚠️ Finished with errors";

  if (message) progressMessage.textContent = message;
}

// ============================================================================
// HISTORY MANAGEMENT
// ============================================================================
async function fetchHistoryStats() {
  if (!canCallBackend()) return;
  const keyword = document.getElementById("keyword").value.trim();
  const location = document.getElementById("location").value.trim();
  if (!keyword || !location) { historyInfo.style.display = "none"; return; }
  try {
    const res = await fetch(`/history/stats?keyword=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}`);
    const data = await res.json();
    if (data.search_total > 0) {
      historyCount.textContent = data.search_total;
      historyInfo.style.display = "block";
    } else {
      historyInfo.style.display = "none";
    }
  } catch {
    markBackendUnavailable();
    historyInfo.style.display = "none";
  }
}

async function clearHistory() {
  if (!canCallBackend()) { markBackendUnavailable(); return; }
  const keyword = document.getElementById("keyword").value.trim();
  const location = document.getElementById("location").value.trim();
  if (!keyword || !location) { alert("Please enter keyword and location first."); return; }
  if (!confirm(`Clear history for "${keyword}" in "${location}"?\n\nThis will allow you to scrape the same businesses again.`)) return;
  try {
    const res = await fetch("/history/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword, location }),
    });
    const data = await res.json();
    if (data.ok) { setStatus(`✓ ${data.message}`); historyInfo.style.display = "none"; }
    else { setStatus(`Error: ${data.error || "Failed to clear history"}`); }
  } catch {
    markBackendUnavailable();
    setStatus("Error clearing history.");
  }
}

async function fetchOutputHistoryFiles() {
  if (!canCallBackend()) return;
  if (!historyFilesList) return;
  try {
    const res = await fetch("/history/output-files");
    const data = await res.json();
    outputHistoryFiles = Array.isArray(data.files) ? data.files : [];
    const availableNames = new Set(outputHistoryFiles.map((file) => file.name));
    for (const selected of [...selectedHistoryFiles]) {
      if (!availableNames.has(selected)) selectedHistoryFiles.delete(selected);
    }
    renderOutputHistoryFiles();
  } catch {
    markBackendUnavailable();
    historyFilesList.innerHTML = "Could not load output history files.";
  }
}

function renderOutputHistoryFiles() {
  if (!historyFilesList) return;
  historyFilesList.innerHTML = "";
  if (!outputHistoryFiles.length) {
    historyFilesList.textContent = "No output CSV files found yet.";
    return;
  }
  const fragment = document.createDocumentFragment();
  outputHistoryFiles.forEach((file) => {
    const row = document.createElement("label");
    row.className = "history-file-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selectedHistoryFiles.has(file.name);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedHistoryFiles.add(file.name);
      else selectedHistoryFiles.delete(file.name);
    });
    const nameEl = document.createElement("span");
    nameEl.className = "history-file-name";
    nameEl.textContent = file.name;
    const metaEl = document.createElement("small");
    metaEl.className = "history-file-meta";
    metaEl.textContent = `${file.rows || 0} rows | ${file.modified || "unknown"}`;
    row.appendChild(checkbox);
    row.appendChild(nameEl);
    row.appendChild(metaEl);
    fragment.appendChild(row);
  });
  historyFilesList.appendChild(fragment);
}

function getSelectedHistoryFiles() {
  return [...selectedHistoryFiles];
}

if (clearHistoryBtn) clearHistoryBtn.addEventListener("click", clearHistory);
if (refreshHistoryFilesBtn) refreshHistoryFilesBtn.addEventListener("click", fetchOutputHistoryFiles);
if (selectAllHistoryFilesBtn) {
  selectAllHistoryFilesBtn.addEventListener("click", () => {
    outputHistoryFiles.forEach((file) => selectedHistoryFiles.add(file.name));
    renderOutputHistoryFiles();
  });
}
if (clearSelectedHistoryFilesBtn) {
  clearSelectedHistoryFilesBtn.addEventListener("click", () => {
    selectedHistoryFiles.clear();
    renderOutputHistoryFiles();
  });
}

// ============================================================================
// LOCATION SUGGESTIONS
// ============================================================================
const keywordInput = document.getElementById("keyword");
const locationInput = document.getElementById("location");

function normalizeLocationText(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9,\s-]+/g, " ").replace(/\s+/g, " ").trim();
}

function buildLocationFormatSuggestions(rawValue) {
  const cleaned = String(rawValue || "").replace(/\s+/g, " ").trim();
  if (!cleaned) return [];
  const options = [`${cleaned}, State/Region, Country`, `${cleaned}, Country`, `${cleaned} metro area, Country`];
  if (cleaned.includes(",")) return options.slice(0, 1);
  return options;
}

function hideLocationSuggestions() {
  if (!locationSuggestions) return;
  locationSuggestions.innerHTML = "";
  locationSuggestions.style.display = "none";
}

function showLocationSuggestions(inputValue, options) {
  if (!locationSuggestions || !locationInput || !Array.isArray(options) || options.length === 0) {
    hideLocationSuggestions();
    return;
  }
  locationSuggestions.innerHTML = "";
  const title = document.createElement("small");
  title.className = "location-suggestions-title";
  title.textContent = `Select exact location for "${inputValue}" (city/state/country):`;
  const list = document.createElement("div");
  list.className = "location-suggestions-list";
  options.forEach((option) => {
    const optionLabel = typeof option === "string" ? option : (option.label || option.value || "");
    const optionValue = typeof option === "string" ? option : (option.value || option.label || "");
    const optionHint = typeof option === "string" ? "" : (option.display_name || "");
    if (!optionValue) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "location-suggestion-btn";
    btn.textContent = optionLabel;
    if (optionHint) btn.title = optionHint;
    btn.addEventListener("click", () => {
      locationInput.value = optionValue;
      hideLocationSuggestions();
      locationInput.dispatchEvent(new Event("input", { bubbles: true }));
      setStatus(`Location selected: ${optionLabel}`);
    });
    list.appendChild(btn);
  });
  locationSuggestions.appendChild(title);
  locationSuggestions.appendChild(list);
  locationSuggestions.style.display = "block";
}

async function fetchLocationSuggestions(raw) {
  if (!canCallBackend()) return [];
  if (locationSuggestController) { try { locationSuggestController.abort(); } catch {} }
  locationSuggestController = new AbortController();
  try {
    const res = await fetch(`/location/suggest?q=${encodeURIComponent(raw)}&limit=${LOCATION_SUGGESTION_LIMIT}`, { signal: locationSuggestController.signal });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data?.suggestions) ? data.suggestions : [];
  } catch (err) {
    return [];
  } finally {
    locationSuggestController = null;
  }
}

async function updateLocationDisambiguation() {
  if (!locationInput) return;
  const raw = locationInput.value.trim();
  if (!raw) { hideLocationSuggestions(); return; }
  const fallbackSuggestions = buildLocationFormatSuggestions(raw);
  const normalizedRaw = normalizeLocationText(raw);
  const backendSuggestions = raw.length >= 2 ? await fetchLocationSuggestions(raw) : [];
  const combined = [];
  const seen = new Set();
  backendSuggestions.forEach((item) => {
    const value = normalizeLocationText(item?.value || item?.label || "");
    if (!value || seen.has(value)) return;
    seen.add(value);
    combined.push(item);
  });
  fallbackSuggestions.forEach((value) => {
    const key = normalizeLocationText(value);
    if (!key || seen.has(key)) return;
    seen.add(key);
    combined.push(value);
  });
  if (!combined || combined.length === 0) { hideLocationSuggestions(); return; }
  const alreadySelected = combined.some((item) => {
    if (typeof item === "string") return normalizeLocationText(item) === normalizedRaw;
    return normalizeLocationText(item.value || item.label || "") === normalizedRaw;
  });
  if (alreadySelected) { hideLocationSuggestions(); return; }
  showLocationSuggestions(raw, combined.slice(0, LOCATION_SUGGESTION_LIMIT));
}

if (keywordInput && locationInput) {
  let historyTimeout;
  const checkHistory = () => {
    clearTimeout(historyTimeout);
    historyTimeout = setTimeout(fetchHistoryStats, 500);
  };
  keywordInput.addEventListener("input", checkHistory);
  locationInput.addEventListener("input", () => {
    checkHistory();
    clearTimeout(locationSuggestTimer);
    locationSuggestTimer = setTimeout(() => { updateLocationDisambiguation(); }, 250);
  });
  locationInput.addEventListener("focus", () => {
    clearTimeout(locationSuggestTimer);
    locationSuggestTimer = setTimeout(() => { updateLocationDisambiguation(); }, 120);
  });
  locationInput.addEventListener("blur", () => { setTimeout(hideLocationSuggestions, 150); });
}

document.addEventListener("click", (event) => {
  if (!locationSuggestions || !locationInput) return;
  const target = event.target;
  if (locationSuggestions.contains(target) || locationInput.contains(target)) return;
  hideLocationSuggestions();
});

// ============================================================================
// STATUS + STATS + RENDERING
// ============================================================================
function setStatus(message) {
  statusEl.textContent = message;
}

function setRunningState(isRunning) {
  startBtn.disabled = isRunning;
  stopBtn.disabled = !isRunning;
}

function updateStats(rows) {
  if (!rows || rows.length === 0) { statsPanel.style.display = "none"; return; }
  statsPanel.style.display = "block";
  document.getElementById("statTotal").textContent = rows.length;
  document.getElementById("statWithEmail").textContent = rows.filter(r => r.email).length;
  document.getElementById("statWithWhatsapp").textContent = rows.filter(r => r.whatsapp).length;
  document.getElementById("statWithInstagram").textContent = rows.filter(r => r.instagram).length;
  document.getElementById("statWithFacebook").textContent = rows.filter(r => r.facebook).length;
  document.getElementById("statWithWebsite").textContent = rows.filter(r => r.has_website === "Yes").length;
  const verifiedEl = document.getElementById("statVerified");
  if (verifiedEl) {
    const verifiedCount = rows.filter(r => r.verified === true || r.verification_score > 50).length;
    verifiedEl.textContent = verifiedCount;
  }
}

function truncate(str, maxLen) {
  if (!str) return "";
  return str.length > maxLen ? str.substring(0, maxLen) + "..." : str;
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function getFilteredRows() {
  const term = (resultSearch?.value || "").trim().toLowerCase();
  if (!term) return currentRows;
  return currentRows.filter((r) => {
    const hay = [r.name, r.address, r.phone, r.whatsapp, r.email, r.website, r.instagram, r.facebook, r.category]
      .map((v) => String(v || "").toLowerCase()).join(" ");
    return hay.includes(term);
  });
}

function renderRows(rows) {
  currentRows = Array.isArray(rows) ? rows : [];
  updateStats(currentRows);
  renderTableBody(getFilteredRows());
  lastRenderedCount = currentRows.length;
}

function renderTableBody(rows) {
  bodyEl.innerHTML = "";

  if (!rows || rows.length === 0) {
    const tr = document.createElement("tr");
    const msg = currentRows.length === 0 ? "No results yet." : "No results match your filter.";
    tr.innerHTML = `<td colspan='11' style="text-align:center; padding:24px; color:var(--muted);">${msg}</td>`;
    bodyEl.appendChild(tr);
    if (resultCountEl) resultCountEl.textContent = `${rows.length} shown`;
    return;
  }

  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const addressCell = row.address ? `<span title="${escapeHtml(row.address)}">${escapeHtml(truncate(row.address, 30))}</span>` : "—";
    const websiteCell = row.website
      ? `<a href="${escapeHtml(row.website)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(row.website)}">🔗 Visit</a>`
      : "❌";
    const instagramCell = row.instagram
      ? `<a href="${escapeHtml(row.instagram)}" target="_blank" rel="noopener noreferrer" title="Instagram">📸 View</a>` : "—";
    const facebookCell = row.facebook
      ? `<a href="${escapeHtml(row.facebook)}" target="_blank" rel="noopener noreferrer" title="Facebook">👤 View</a>` : "—";
    const ratingCell = row.rating ? `⭐ ${escapeHtml(row.rating)}` : "—";
    const qualityClass = row.quality_score === "high" ? "quality-high" : row.quality_score === "medium" ? "quality-medium" : "quality-low";
    const qualityCell = `<span class="quality ${qualityClass}">${escapeHtml((row.quality_score || "?").toUpperCase())}</span>`;
    const whatsappCell = row.whatsapp ? escapeHtml(row.whatsapp) : "—";

    const waMeLinks = (row.whatsapp_wa_me_links || "").split(";").map((entry) => entry.trim()).filter(Boolean);
    const whatsappLinkCell = waMeLinks.length > 0
      ? waMeLinks.map((link) => `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" title="Open WhatsApp">Open</a>`).join(" | ")
      : (row.whatsapp
          ? `<a href="https://wa.me/${String(row.whatsapp).replace(/[^0-9]/g, "")}" target="_blank" rel="noopener noreferrer" title="Open WhatsApp">Open</a>`
          : "—");

    tr.innerHTML = `
      <td title="${escapeHtml(row.name || '')}">${escapeHtml(truncate(row.name, 25)) || "—"}</td>
      <td>${addressCell}</td>
      <td>${escapeHtml(row.phone) || "—"}</td>
      <td>${whatsappCell}</td>
      <td>${whatsappLinkCell}</td>
      <td>${escapeHtml(row.email) || "—"}</td>
      <td>${websiteCell}</td>
      <td>${instagramCell}</td>
      <td>${facebookCell}</td>
      <td>${ratingCell}</td>
      <td>${qualityCell}</td>
    `;
    fragment.appendChild(tr);
  });
  bodyEl.appendChild(fragment);
  if (resultCountEl) {
    resultCountEl.textContent = rows.length === currentRows.length
      ? `${rows.length} shown`
      : `${rows.length} of ${currentRows.length} shown`;
  }
}

if (resultSearch) {
  resultSearch.addEventListener("input", () => renderTableBody(getFilteredRows()));
}

function normalizeMaxResults(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 50;
  return Math.min(MAX_RESULTS_LIMIT, Math.max(1, Math.trunc(numeric)));
}

// ============================================================================
// POLLING
// ============================================================================
async function fetchStatus() {
  if (!canCallBackend()) return;
  try {
    const res = await fetch("/status");
    const data = await res.json();

    if (Array.isArray(data?.results) && data.results.length !== lastRenderedCount) {
      renderRows(data.results);
      downloadBtn.disabled = !(data.results.length > 0);
    }

    if (data?.message) setStatus(data.message);

    if (data?.running) {
      updateProgress(data.count ?? (data.results ? data.results.length : 0), data.message);
    }

    if (data && data.running === false && pollingId) {
      setRunningState(false);
      stopPolling();
      stopRequestedByUser = false;
      activeScrapeController = null;
      downloadBtn.disabled = !(data.count > 0);
      const state = (data.status === "stopped") ? "stopped" : (data.status === "error" || data.status === "captcha") ? "error" : "completed";
      finishProgress(state, data.count ?? 0, data.message);
      fetchHistoryStats();
      fetchOutputHistoryFiles();
    }
  } catch {
    markBackendUnavailable("Backend connection lost. Please restart server.");
    setRunningState(false);
    stopPolling();
    stopRequestedByUser = false;
    activeScrapeController = null;
    finishProgress("error", currentRows.length, "Connection lost.");
  }
}

function startPolling() {
  stopPolling();
  pollingId = setInterval(fetchStatus, 1500);
}

function stopPolling() {
  if (pollingId) { clearInterval(pollingId); pollingId = null; }
}

// ============================================================================
// START / STOP / DOWNLOAD
// ============================================================================
startBtn.addEventListener("click", async () => {
  const keyword = document.getElementById("keyword").value.trim();
  const location = document.getElementById("location").value.trim();
  const maxResultsInput = document.getElementById("maxResults");
  const maxResults = normalizeMaxResults(maxResultsInput.value || 50);
  const websiteFilter = document.getElementById("websiteFilter").value || "all";
  const extractionMode = document.getElementById("extractionMode").value || "deep";
  const headless = document.getElementById("headless").checked;
  const deepSearch = document.getElementById("deepSearch").checked;
  const verifySocials = document.getElementById("verifySocials")?.checked ?? true;
  const skipDuplicates = document.getElementById("skipDuplicates")?.checked ?? true;
  const chosenHistoryFiles = getSelectedHistoryFiles();

  maxResultsInput.value = String(maxResults);

  if (!keyword || !location) {
    setStatus("Keyword and location are required.");
    return;
  }

  const modeNames = {
    ultra: "🚀 Ultra Deep: ALL engines + Cross-verification",
    maximum: "💎 Maximum: Maps + Web Search + ALL engines",
    deep: "🔍 Deep: Maps → Website → Google Search",
    enhanced: "⚙️ Enhanced: Maps + Website analysis",
    basic: "⚡ Basic: Maps only (fast)"
  };

  let statusMsg = modeNames[extractionMode] || "Scraping...";
  if (skipDuplicates) statusMsg += " (skipping previous results)";
  if (chosenHistoryFiles.length > 0) statusMsg += ` + ${chosenHistoryFiles.length} selected history file(s)`;

  setRunningState(true);
  downloadBtn.disabled = true;
  renderRows([]);
  if (resultSearch) resultSearch.value = "";
  stopRequestedByUser = false;
  activeScrapeController = new AbortController();
  setStatus(statusMsg);
  startProgress(maxResults);
  startPolling();

  try {
    const res = await fetch("/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: activeScrapeController.signal,
      body: JSON.stringify({
        keyword, location,
        max_results: maxResults,
        website_filter: websiteFilter,
        extraction_mode: extractionMode,
        deep_search: deepSearch,
        verify_socials: verifySocials,
        skip_duplicates: skipDuplicates,
        selected_history_files: chosenHistoryFiles,
        headless,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      setStatus(data.error || "Scraping failed.");
      finishProgress("error", currentRows.length, data.error || "Scraping failed.");
      stopRequestedByUser = false;
      return;
    }

    renderRows(data.results || []);
    setStatus(data.message || `Completed. ${data.count || 0} NEW leads collected.`);
    downloadBtn.disabled = !(data.count > 0);
    finishProgress("completed", data.count ?? (data.results ? data.results.length : 0), data.message);
    stopRequestedByUser = false;
    fetchHistoryStats();
    fetchOutputHistoryFiles();
  } catch (err) {
    if (err?.name === "AbortError" && stopRequestedByUser) {
      setStatus("Stopping... returning collected results.");
      startPolling();
    } else {
      markBackendUnavailable();
      setStatus("Network error while scraping. Check backend logs.");
      finishProgress("error", currentRows.length, "Network error.");
      stopRequestedByUser = false;
    }
  } finally {
    activeScrapeController = null;
    if (!stopRequestedByUser) {
      setRunningState(false);
      stopPolling();
    }
  }
});

stopBtn.addEventListener("click", async () => {
  if (!canCallBackend()) { markBackendUnavailable(); return; }
  stopRequestedByUser = true;
  progressPhase.textContent = "⏹ Stopping…";
  if (activeScrapeController) { try { activeScrapeController.abort(); } catch {} }
  startPolling();
  try {
    const res = await fetch("/stop", { method: "POST" });
    const data = await res.json();
    if (Array.isArray(data?.results)) {
      renderRows(data.results);
      downloadBtn.disabled = !(data.results.length > 0);
    }
    setStatus(data.message || "Stop requested.");
  } catch {
    markBackendUnavailable();
    setStatus("Could not send stop request.");
  }
});

downloadBtn.addEventListener("click", () => {
  window.location.href = "/download";
});

// ============================================================================
// INIT
// ============================================================================
resetProgressUI();
renderRows([]);
fetchOutputHistoryFiles();
