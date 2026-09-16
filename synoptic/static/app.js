"use strict";

/* ==========================================================================
   Synoptic frontend
   Vanilla JS, no framework, no build step — open index.html's <script src>
   and it just runs. Talks to the local Python server's JSON API.
   ========================================================================== */

// ---- Map projection (must match src/dashboard.py's constants) ----
const MAP_LON_RANGE = [-125.0, -66.0];
const MAP_LAT_RANGE = [24.0, 49.5];
const MAP_W = 720, MAP_H = 420;
const DEFAULT_VIEWBOX = [0, 0, MAP_W, MAP_H];

function project(lon, lat) {
  const [lon0, lon1] = MAP_LON_RANGE;
  const [lat0, lat1] = MAP_LAT_RANGE;
  const x = ((lon - lon0) / (lon1 - lon0)) * MAP_W;
  const y = (1 - (lat - lat0) / (lat1 - lat0)) * MAP_H;
  return [x, y];
}

const SEVERITY_RANK = { Extreme: 4, Severe: 3, Moderate: 2, Minor: 1, Unknown: 0 };
const SEVERITY_LABEL = { Extreme: "Warning", Severe: "Warning", Moderate: "Watch", Minor: "Advisory", Unknown: "Statement" };
const STATUS_WORD = { Extreme: "WARNING", Severe: "WARNING", Moderate: "WATCH", Minor: "ADVISORY" };

const HAZARD_KEYWORDS = [
  ["Tornado", ["tornado"]],
  ["Flood", ["flood"]],
  ["Winter", ["winter", "snow", "ice", "blizzard", "freeze", "frost"]],
  ["Wind", ["wind"]],
  ["Thunderstorm", ["thunderstorm", "severe storm"]],
  ["Heat", ["heat"]],
  ["Fire", ["fire", "red flag"]],
  ["Hurricane", ["hurricane", "tropical"]],
];

function hazardCategory(eventName) {
  const lower = (eventName || "").toLowerCase();
  for (const [label, keywords] of HAZARD_KEYWORDS) {
    if (keywords.some((k) => lower.includes(k))) return label;
  }
  return "Other";
}

function timeAgo(iso) {
  if (!iso) return "unknown time";
  const then = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const prefersReducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------
const state = {
  alerts: [],
  lastUpdated: null,
  locations: [],
  selectedLocation: null,        // {label, state, lat, lon}
  activeHazard: "All",
  statePaths: {},                // stateName -> <path> element
  currentViewBox: DEFAULT_VIEWBOX.slice(),
  selectedAlertId: null,
  seenSevereIds: new Set(),
  notifyEnabled: false,
  deferredInstallPrompt: null,
};

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", init);

async function init() {
  registerServiceWorker();
  wireStaticControls();

  try {
    const [locRes, geoRes] = await Promise.all([
      fetch("/api/locations").then((r) => r.json()),
      fetch("/api/states-geojson").then((r) => r.json()),
    ]);
    state.locations = locRes.locations || [];
    state.selectedLocation = state.locations[0] || null;
    populateLocationOptions();
    renderMapShell(geoRes);
  } catch (e) {
    console.error("Failed to load base data", e);
    showBootFailure();
    return; // don't keep trying alerts/status if the server itself is unreachable
  }

  await refreshAlerts();
  hideBootBanner();
  updateHero();

  setInterval(pollStatus, 12000);
  setInterval(() => updateLiveBadge(), 5000);
}

function wireStaticControls() {
  document.getElementById("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("location-input");
    const match = state.locations.find(
      (l) => l.label.toLowerCase() === input.value.trim().toLowerCase()
    ) || state.locations.find((l) =>
      l.label.toLowerCase().includes(input.value.trim().toLowerCase())
    );
    if (match) {
      state.selectedLocation = match;
      updateHero();
      renderSidebar();
    }
  });

  document.getElementById("geo-btn").addEventListener("click", useMyLocation);
  document.getElementById("refresh-btn").addEventListener("click", () => {
    fetch("/api/refresh");
    setLiveText("Refreshing…");
    setTimeout(refreshAlerts, 1500);
  });

  document.getElementById("zoom-in").addEventListener("click", () => zoomByFactor(0.7));
  document.getElementById("zoom-out").addEventListener("click", () => zoomByFactor(1.4));
  document.getElementById("zoom-reset").addEventListener("click", () => animateViewBox(DEFAULT_VIEWBOX));
  document.getElementById("popover-close").addEventListener("click", hidePopover);

  document.getElementById("notify-btn").addEventListener("click", enableNotifications);

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    state.deferredInstallPrompt = e;
    const btn = document.getElementById("install-btn");
    btn.hidden = false;
    btn.addEventListener("click", async () => {
      btn.hidden = true;
      state.deferredInstallPrompt.prompt();
      await state.deferredInstallPrompt.userChoice;
      state.deferredInstallPrompt = null;
    });
  });
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

function populateLocationOptions() {
  const list = document.getElementById("location-options");
  list.innerHTML = "";
  for (const loc of state.locations) {
    const opt = document.createElement("option");
    opt.value = loc.label;
    list.appendChild(opt);
  }
  if (state.selectedLocation) {
    document.getElementById("location-input").placeholder = state.selectedLocation.label;
  }
}

function useMyLocation() {
  if (!navigator.geolocation) {
    alert("Your browser doesn't support location lookup. Try searching by city instead.");
    return;
  }
  const btn = document.getElementById("geo-btn");
  btn.textContent = "…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;
      let best = null, bestDist = Infinity;
      for (const loc of state.locations) {
        const d = haversine(latitude, longitude, loc.lat, loc.lon);
        if (d < bestDist) { bestDist = d; best = loc; }
      }
      if (best) {
        state.selectedLocation = best;
        updateHero();
        renderSidebar();
      }
      btn.textContent = "📍";
    },
    () => {
      btn.textContent = "📍";
      alert("Couldn't get your location. Try searching by city instead.");
    },
    { timeout: 8000 }
  );
}

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ---------------------------------------------------------------------------
// Data fetching / polling
// ---------------------------------------------------------------------------
function hideBootBanner() {
  const banner = document.getElementById("boot-banner");
  if (banner) banner.classList.add("hidden");
}

function showBootFailure() {
  const banner = document.getElementById("boot-banner");
  if (!banner) return;
  banner.classList.remove("hidden");
  banner.style.borderLeftColor = "var(--extreme)";
  document.getElementById("boot-banner-detail").innerHTML =
    "Couldn't reach the local server. Make sure you started it (not just opened this file) — " +
    "open a terminal in the <code>synoptic</code> folder and run:";
}

async function refreshAlerts() {
  try {
    const res = await fetch("/api/alerts");
    const data = await res.json();
    state.alerts = data.alerts || [];
    state.lastUpdated = data.last_updated;
    renderChips();
    renderSidebar();
    updateMapColors();
    updateHero();
    updateLiveBadge();
  } catch (e) {
    console.error("Failed to fetch alerts", e);
    setLiveText("Offline — retrying…");
  }
}

async function pollStatus() {
  try {
    const res = await fetch("/api/status");
    const status = await res.json();
    if (status.newly_severe_ids && status.newly_severe_ids.length) {
      const freshIds = status.newly_severe_ids.filter((id) => !state.seenSevereIds.has(id));
      if (freshIds.length) {
        await refreshAlerts();
        for (const id of freshIds) {
          state.seenSevereIds.add(id);
          const alert = state.alerts.find((a) => a.id === id);
          if (alert) notifyNewAlert(alert);
        }
        return;
      }
    }
    if (status.last_updated && status.last_updated !== state.lastUpdated) {
      await refreshAlerts();
    }
  } catch (e) {
    setLiveText("Offline — retrying…");
  }
}

function setLiveText(text) {
  document.getElementById("live-text").textContent = text;
}

function updateLiveBadge() {
  const dot = document.getElementById("live-dot");
  if (!state.lastUpdated) {
    setLiveText("Connecting…");
    return;
  }
  const ageMs = Date.now() - new Date(state.lastUpdated).getTime();
  setLiveText(`Updated ${timeAgo(state.lastUpdated)}`);
  dot.classList.toggle("stale", ageMs > 3 * 60 * 1000);
}

// ---------------------------------------------------------------------------
// Hero status band
// ---------------------------------------------------------------------------
function updateHero() {
  const hero = document.getElementById("hero");
  const placeEl = document.getElementById("hero-place");
  const statusEl = document.getElementById("hero-status");
  const subEl = document.getElementById("hero-sub");

  const loc = state.selectedLocation;
  placeEl.textContent = loc ? loc.label : "your area";

  const relevant = loc
    ? state.alerts.filter((a) => (a.states || []).includes(loc.state))
    : [];

  let worst = null;
  for (const a of relevant) {
    if (!worst || SEVERITY_RANK[a.severity] > SEVERITY_RANK[worst.severity]) worst = a;
  }

  hero.className = "hero";
  if (!worst) {
    hero.classList.add("status-safe");
    statusEl.className = "hero-status safe";
    statusEl.textContent = "ALL CLEAR";
    subEl.textContent = "No active National Weather Service alerts for this area right now.";
  } else {
    const rank = SEVERITY_RANK[worst.severity];
    const bucket = rank >= 3 ? "warning" : rank === 2 ? "watch" : "advisory";
    hero.classList.add(`status-${bucket}`);
    statusEl.className = `hero-status ${bucket}`;
    statusEl.textContent = STATUS_WORD[worst.severity] || "ADVISORY";
    subEl.textContent = `${worst.event} — ${worst.headline || worst.area_desc || ""}`.slice(0, 160);
  }
}

// ---------------------------------------------------------------------------
// Filter chips
// ---------------------------------------------------------------------------
function renderChips() {
  const row = document.getElementById("chip-row");
  const counts = {};
  for (const a of state.alerts) {
    const cat = hazardCategory(a.event);
    counts[cat] = (counts[cat] || 0) + 1;
  }
  const categories = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);

  row.innerHTML = "";
  const allChip = makeChip("All", state.alerts.length, state.activeHazard === "All");
  row.appendChild(allChip);
  for (const cat of categories) {
    row.appendChild(makeChip(cat, counts[cat], state.activeHazard === cat));
  }
}

function makeChip(label, count, active) {
  const btn = document.createElement("button");
  btn.className = "chip";
  btn.setAttribute("aria-pressed", active ? "true" : "false");
  btn.innerHTML = `${label}<span class="count">${count}</span>`;
  btn.addEventListener("click", () => {
    state.activeHazard = label;
    renderChips();
    renderSidebar();
  });
  return btn;
}

// ---------------------------------------------------------------------------
// Sidebar alert list
// ---------------------------------------------------------------------------
function renderSidebar() {
  const list = document.getElementById("alert-list");
  const heading = document.getElementById("sidebar-heading");
  list.innerHTML = "";

  let alerts = state.alerts;
  if (state.activeHazard !== "All") {
    alerts = alerts.filter((a) => hazardCategory(a.event) === state.activeHazard);
  }

  const loc = state.selectedLocation;
  heading.textContent = loc ? `ALERTS · ${alerts.length} ACTIVE` : `ALERTS · ${alerts.length} ACTIVE`;

  if (!alerts.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No alerts match this filter right now. That's good news.";
    list.appendChild(empty);
    return;
  }

  for (const alert of alerts) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = `alert-item sev-${alert.severity}`;
    btn.setAttribute("aria-selected", alert.id === state.selectedAlertId ? "true" : "false");
    btn.innerHTML = `
      <p class="event">${escapeHtml(alert.event || "Weather Alert")}</p>
      <p class="area">${escapeHtml(alert.area_desc || "")}</p>
      <div class="meta">
        <span>${SEVERITY_LABEL[alert.severity] || "Statement"}</span>
        <span>${timeAgo(alert.sent)}</span>
      </div>
    `;
    btn.addEventListener("click", () => selectAlert(alert));
    li.appendChild(btn);
    list.appendChild(li);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

// ---------------------------------------------------------------------------
// Map: build state paths once from GeoJSON, recolor on every refresh
// ---------------------------------------------------------------------------
function renderMapShell(geojson) {
  const svg = document.getElementById("us-map");
  svg.innerHTML = "";
  for (const feature of geojson.features || []) {
    const name = feature.properties.name;
    const d = geometryToPathD(feature.geometry);
    if (!d) continue;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("class", "state-path");
    path.setAttribute("fill-rule", "evenodd");
    path.setAttribute("data-name", name);
    path.addEventListener("click", () => zoomToStateName(name));
    svg.appendChild(path);
    state.statePaths[name] = path;
  }
}

function ringToPathD(ring) {
  return ring
    .map(([lon, lat], i) => {
      const [x, y] = project(lon, lat);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ") + " Z";
}

function geometryToPathD(geometry) {
  if (!geometry) return "";
  if (geometry.type === "Polygon") {
    return geometry.coordinates.map(ringToPathD).join(" ");
  }
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.map((poly) => poly.map(ringToPathD).join(" ")).join(" ");
  }
  return "";
}

function updateMapColors() {
  // highest severity per state, from currently loaded alerts (not filtered
  // by chip — the map always shows the full national picture)
  const bestByState = {};
  for (const a of state.alerts) {
    for (const abbr of a.state_names || []) {
      const current = bestByState[abbr];
      if (!current || SEVERITY_RANK[a.severity] > SEVERITY_RANK[current]) {
        bestByState[abbr] = a.severity;
      }
    }
  }
  for (const [name, path] of Object.entries(state.statePaths)) {
    path.classList.remove("sev-Extreme", "sev-Severe", "sev-Moderate", "sev-Minor", "has-alert");
    const sev = bestByState[name];
    if (sev) {
      path.classList.add(`sev-${sev}`, "has-alert");
    }
  }
}

// ---------------------------------------------------------------------------
// Map interaction: select alert -> zoom + popover
// ---------------------------------------------------------------------------
function selectAlert(alert) {
  state.selectedAlertId = alert.id;
  renderSidebar();

  for (const path of Object.values(state.statePaths)) path.classList.remove("selected");
  for (const name of alert.state_names || []) {
    const path = state.statePaths[name];
    if (path) path.classList.add("selected");
  }

  const bbox = bboxForAlert(alert);
  if (bbox) animateViewBox(bbox);

  showPopover(alert, bbox);
  document.querySelector(".map-panel").scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "nearest" });
}

function zoomToStateName(name) {
  const path = state.statePaths[name];
  if (!path) return;
  const box = path.getBBox();
  const pad = Math.max(box.width, box.height) * 0.25 + 10;
  animateViewBox([box.x - pad, box.y - pad, box.width + pad * 2, box.height + pad * 2]);
  hidePopover();
}

function bboxForAlert(alert) {
  let points = [];
  if (alert.geometry) {
    collectPoints(alert.geometry, points);
  } else if (alert.state_names && alert.state_names.length) {
    for (const name of alert.state_names) {
      const path = state.statePaths[name];
      if (path) {
        const b = path.getBBox();
        points.push([b.x, b.y], [b.x + b.width, b.y + b.height]);
      }
    }
  } else if (alert.centroid) {
    const [x, y] = project(alert.centroid.lon, alert.centroid.lat);
    points.push([x - 40, y - 40], [x + 40, y + 40]);
  }
  if (!points.length) return null;

  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = Math.max(maxX - minX, maxY - minY) * 0.3 + 15;
  return [minX - pad, minY - pad, (maxX - minX) + pad * 2, (maxY - minY) + pad * 2];
}

function collectPoints(geometry, out) {
  const walkRing = (ring) => {
    for (const [lon, lat] of ring) out.push(project(lon, lat));
  };
  if (geometry.type === "Polygon") {
    geometry.coordinates.forEach(walkRing);
  } else if (geometry.type === "MultiPolygon") {
    geometry.coordinates.forEach((poly) => poly.forEach(walkRing));
  }
}

function showPopover(alert, bbox) {
  const pop = document.getElementById("map-popover");
  document.getElementById("popover-title").textContent = alert.event || "Weather Alert";
  document.getElementById("popover-area").textContent = alert.area_desc || "";
  document.getElementById("popover-time").textContent =
    `${SEVERITY_LABEL[alert.severity] || "Statement"} · issued ${timeAgo(alert.sent)}`;
  const outageText = alert.simulated_customers_out
    ? `Simulated outage risk: ~${alert.simulated_customers_out.toLocaleString()} customers`
    : "";
  document.getElementById("popover-outage").textContent = outageText;
  document.getElementById("popover-outage").style.display = outageText ? "block" : "none";

  const frame = document.querySelector(".map-frame");
  const frameBox = frame.getBoundingClientRect();
  let left = 20, top = 20;
  if (alert.centroid) {
    const [x, y] = project(alert.centroid.lon, alert.centroid.lat);
    const scaleX = frameBox.width / MAP_W;
    const scaleY = frameBox.height / MAP_H;
    left = Math.min(Math.max(x * scaleX - 100, 10), frameBox.width - 310);
    top = Math.min(Math.max(y * scaleY - 20, 10), frameBox.height - 140);
  }
  pop.style.left = `${left}px`;
  pop.style.top = `${top}px`;
  pop.classList.add("visible");
}

function hidePopover() {
  document.getElementById("map-popover").classList.remove("visible");
}

// ---------------------------------------------------------------------------
// viewBox pan/zoom animation
// ---------------------------------------------------------------------------
function animateViewBox(target) {
  const svg = document.getElementById("us-map");
  const start = state.currentViewBox.slice();
  if (prefersReducedMotion) {
    svg.setAttribute("viewBox", target.join(" "));
    state.currentViewBox = target.slice();
    return;
  }
  const duration = 450;
  const startTime = performance.now();

  function step(now) {
    const t = Math.min(1, (now - startTime) / duration);
    const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
    const current = start.map((v, i) => v + (target[i] - v) * eased);
    svg.setAttribute("viewBox", current.join(" "));
    if (t < 1) {
      requestAnimationFrame(step);
    } else {
      state.currentViewBox = target.slice();
    }
  }
  requestAnimationFrame(step);
}

function zoomByFactor(factor) {
  const [x, y, w, h] = state.currentViewBox;
  const cx = x + w / 2, cy = y + h / 2;
  const newW = Math.min(MAP_W * 1.2, Math.max(40, w * factor));
  const newH = Math.min(MAP_H * 1.2, Math.max(24, h * factor));
  animateViewBox([cx - newW / 2, cy - newH / 2, newW, newH]);
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------
function enableNotifications() {
  const btn = document.getElementById("notify-btn");
  if (!("Notification" in window)) {
    btn.textContent = "Notifications not supported here";
    btn.disabled = true;
    return;
  }
  Notification.requestPermission().then((perm) => {
    if (perm === "granted") {
      state.notifyEnabled = true;
      btn.textContent = "🔔 Alert notifications on";
    } else {
      btn.textContent = "🔕 Notifications blocked";
    }
  });
}

function notifyNewAlert(alert) {
  showToast(alert);
  if (state.notifyEnabled && "Notification" in window && Notification.permission === "granted") {
    new Notification(`New ${SEVERITY_LABEL[alert.severity] || "Alert"}: ${alert.event}`, {
      body: alert.area_desc || alert.headline || "",
      icon: "/icon.svg",
    });
  }
}

function showToast(alert) {
  const region = document.getElementById("toast-region");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <strong>New ${escapeHtml(SEVERITY_LABEL[alert.severity] || "Alert")}: ${escapeHtml(alert.event)}</strong>
    ${escapeHtml(alert.area_desc || "")}
    <div><button type="button">View on map</button></div>
  `;
  toast.querySelector("button").addEventListener("click", () => {
    selectAlert(alert);
    toast.remove();
  });
  region.appendChild(toast);
  setTimeout(() => toast.remove(), 15000);
}
