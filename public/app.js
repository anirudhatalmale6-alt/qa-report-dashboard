let allRuns = [];
let currentProject = null;

document.addEventListener("DOMContentLoaded", loadProjects);

async function loadProjects() {
  try {
    const res = await fetch("/api/projects");
    const projects = await res.json();
    renderProjects(projects);
  } catch (err) {
    console.error("Failed to load projects:", err);
  }
}

function renderProjects(projects) {
  const container = document.getElementById("projectCards");
  const emptyState = document.getElementById("emptyState");
  const headerMeta = document.getElementById("headerMeta");

  if (projects.length === 0) {
    container.style.display = "none";
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";
  container.style.display = "grid";

  const totalRuns = projects.reduce((s, p) => s + p.totalRuns, 0);
  headerMeta.textContent = `${projects.length} project${projects.length !== 1 ? "s" : ""} \u00b7 ${totalRuns} total runs`;

  container.innerHTML = projects
    .map(
      (p) => `
    <div class="project-card" onclick="showRuns('${p.name}')">
      <div class="project-name">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        ${escapeHtml(p.name)}
      </div>
      <div class="project-stats">
        <div class="stat">
          <div class="stat-value value-blue">${p.totalRuns}</div>
          <div class="stat-label">Runs</div>
        </div>
        ${
          p.latestRun
            ? `
          <div class="stat">
            <div class="stat-value value-green">${p.latestRun.passed}</div>
            <div class="stat-label">Passed</div>
          </div>
          <div class="stat">
            <div class="stat-value value-red">${p.latestRun.failed}</div>
            <div class="stat-label">Failed</div>
          </div>
          <div class="stat">
            <div class="stat-value">${p.latestRun.total}</div>
            <div class="stat-label">Total</div>
          </div>
        `
            : ""
        }
      </div>
      <div class="project-latest">
        ${
          p.latestRun
            ? `
          <span>Latest: ${formatDate(p.latestRun.date)}</span>
          <span class="status-badge status-${p.latestRun.status}">
            ${p.latestRun.status === "passed" ? "\u2713" : "\u2717"} ${p.latestRun.status}
          </span>
        `
            : "<span>No runs yet</span>"
        }
      </div>
    </div>
  `
    )
    .join("");
}

async function showRuns(projectName) {
  currentProject = projectName;
  document.getElementById("projectsView").style.display = "none";
  document.getElementById("runsView").style.display = "block";
  document.getElementById("runsTitle").textContent = projectName;

  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(projectName)}/runs`);
    allRuns = await res.json();
    renderRunsSummary(allRuns);
    renderRuns(allRuns);
  } catch (err) {
    console.error("Failed to load runs:", err);
  }
}

function showProjects() {
  document.getElementById("projectsView").style.display = "block";
  document.getElementById("runsView").style.display = "none";
  currentProject = null;
  loadProjects();
}

function renderRunsSummary(runs) {
  const totalRuns = runs.length;
  const totalPassed = runs.reduce((s, r) => s + r.passed, 0);
  const totalFailed = runs.reduce((s, r) => s + r.failed, 0);
  const totalTests = runs.reduce((s, r) => s + r.total, 0);
  const passRate =
    totalTests > 0 ? ((totalPassed / totalTests) * 100).toFixed(1) : 0;

  document.getElementById("runsSummary").innerHTML = `
    <div class="summary-card">
      <div class="value value-blue">${totalRuns}</div>
      <div class="label">Total Runs</div>
    </div>
    <div class="summary-card">
      <div class="value value-green">${totalPassed}</div>
      <div class="label">Tests Passed</div>
    </div>
    <div class="summary-card">
      <div class="value value-red">${totalFailed}</div>
      <div class="label">Tests Failed</div>
    </div>
    <div class="summary-card">
      <div class="value" style="color: ${Number(passRate) >= 90 ? "#3fb950" : Number(passRate) >= 70 ? "#d29922" : "#f85149"}">${passRate}%</div>
      <div class="label">Pass Rate</div>
    </div>
  `;
}

function filterRuns() {
  const status = document.getElementById("statusFilter").value;
  const search = document.getElementById("searchBox").value.toLowerCase();

  let filtered = allRuns;
  if (status !== "all") {
    filtered = filtered.filter((r) => r.status === status);
  }
  if (search) {
    filtered = filtered.filter(
      (r) =>
        r.id.toLowerCase().includes(search) ||
        r.date.toLowerCase().includes(search)
    );
  }
  renderRuns(filtered);
}

function renderRuns(runs) {
  const container = document.getElementById("runsList");

  if (runs.length === 0) {
    container.innerHTML =
      '<div class="empty-state"><p>No runs match your filters.</p></div>';
    return;
  }

  container.innerHTML = runs
    .map(
      (r) => `
    <div class="run-row" onclick="openReport('${escapeHtml(r.reportUrl)}')">
      <div class="run-status-icon ${r.status}">
        ${r.status === "passed"
          ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>'
          : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
        }
      </div>
      <div class="run-info">
        <div class="run-date">${formatDate(r.date)}</div>
        <div class="run-id">${escapeHtml(r.id)}</div>
        <div class="progress-bar">
          ${r.total > 0 ? `
            <div class="segment passed-seg" style="width:${(r.passed / r.total) * 100}%"></div>
            <div class="segment failed-seg" style="width:${(r.failed / r.total) * 100}%"></div>
            <div class="segment broken-seg" style="width:${(r.broken / r.total) * 100}%"></div>
            <div class="segment skipped-seg" style="width:${(r.skipped / r.total) * 100}%"></div>
          ` : ""}
        </div>
      </div>
      <div class="run-metrics">
        <div class="run-metric">
          <div class="num value-green">${r.passed}</div>
          <div class="lbl">Passed</div>
        </div>
        <div class="run-metric">
          <div class="num value-red">${r.failed}</div>
          <div class="lbl">Failed</div>
        </div>
        <div class="run-metric">
          <div class="num">${r.total}</div>
          <div class="lbl">Total</div>
        </div>
      </div>
      <div class="run-duration">${formatDuration(r.duration)}</div>
      <button class="run-open-btn" onclick="event.stopPropagation(); openReport('${escapeHtml(r.reportUrl)}')">
        Open Report
      </button>
    </div>
  `
    )
    .join("");
}

function openReport(url) {
  window.open(url, "_blank");
}

function formatDate(isoStr) {
  if (!isoStr) return "Unknown";
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return isoStr;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(ms) {
  if (!ms || ms === 0) return "-";
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes < 60) return `${minutes}m ${secs}s`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
