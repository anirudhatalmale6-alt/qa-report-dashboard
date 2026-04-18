const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 3000;
const REPORTS_DIR = path.join(__dirname, "reports");

app.use("/dashboard", express.static(path.join(__dirname, "public")));
app.use("/reports", express.static(REPORTS_DIR));

// ===========================
// PERFORMANCE TEST API ENDPOINTS (must be before generic :app/:project routes)
// ===========================

// API: list scripts for a performance app/project
// e.g. /api/performance/ESS/App_Migration/scripts
app.get("/api/performance/:app/:project/scripts", (req, res) => {
  const { app: appName, project } = req.params;
  const projDir = path.join(REPORTS_DIR, "Performance", appName, project);
  console.log(`[DEBUG] GET /api/performance/${appName}/${project}/scripts`);
  console.log(`[DEBUG]   Looking in: ${projDir}`);
  console.log(`[DEBUG]   Directory exists: ${fs.existsSync(projDir)}`);
  if (!fs.existsSync(projDir)) {
    console.log(`[DEBUG]   => Returning empty [] (directory not found)`);
    return res.json([]);
  }
  const scripts = fs
    .readdirSync(projDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);
  console.log(`[DEBUG]   => Found scripts: ${JSON.stringify(scripts)}`);
  res.json(scripts);
});

// API: list runs for a performance script
// e.g. /api/performance/ESS/App_Migration/WSS_Retiredmem/runs
app.get("/api/performance/:app/:project/:script/runs", (req, res) => {
  const { app: appName, project, script } = req.params;
  const scriptDir = path.join(REPORTS_DIR, "Performance", appName, project, script);
  console.log(`[DEBUG] GET /api/performance/${appName}/${project}/${script}/runs`);
  console.log(`[DEBUG]   Looking in: ${scriptDir}`);
  console.log(`[DEBUG]   Directory exists: ${fs.existsSync(scriptDir)}`);
  if (!fs.existsSync(scriptDir)) {
    console.log(`[DEBUG]   => Returning empty [] (directory not found)`);
    return res.json([]);
  }

  const runs = [];
  const entries = fs
    .readdirSync(scriptDir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && /^\d{8}/.test(d.name));

  for (const entry of entries) {
    const runPath = path.join(scriptDir, entry.name);
    const summaryPath = path.join(runPath, "summary.json");

    let summary = {};
    if (fs.existsSync(summaryPath)) {
      try {
        let raw = fs.readFileSync(summaryPath, "utf-8");
        if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1);
        summary = JSON.parse(raw);
      } catch (e) {
        console.error(`[Performance] Failed to parse ${summaryPath}:`, e.message);
      }
    }

    runs.push({
      id: entry.name,
      date: summary.date || parseRunDate(entry.name),
      scriptName: summary.scriptName || script,
      envName: summary.envName || "unknown",
      totalRequests: summary.totalRequests || 0,
      totalFailures: summary.totalFailures || 0,
      avgResponseTime: summary.avgResponseTime || 0,
      passRate: summary.passRate || 0,
      status: (summary.totalFailures || 0) > 0 ? "failed" : "passed",
    });
  }

  runs.sort((a, b) => new Date(b.date) - new Date(a.date));
  res.json(runs);
});

// API: get performance stats CSV data for a specific run
// e.g. /api/performance/ESS/App_Migration/WSS_Retiredmem/20260410_120000/stats
app.get("/api/performance/:app/:project/:script/:runId/stats", (req, res) => {
  const { app: appName, project, script, runId } = req.params;
  const runDir = path.join(REPORTS_DIR, "Performance", appName, project, script, runId);
  console.log(`[DEBUG] GET /api/performance/${appName}/${project}/${script}/${runId}/stats`);
  console.log(`[DEBUG]   Looking in: ${runDir}`);
  console.log(`[DEBUG]   Directory exists: ${fs.existsSync(runDir)}`);
  if (!fs.existsSync(runDir)) {
    console.log(`[DEBUG]   => Returning empty (directory not found)`);
    return res.json({ files: [] });
  }

  const csvFiles = fs.readdirSync(runDir).filter(f => f.endsWith(".csv"));
  const files = [];

  for (const file of csvFiles) {
    const content = fs.readFileSync(path.join(runDir, file), "utf-8");
    const lines = content.split("\n").filter(l => l.trim());
    if (lines.length === 0) continue;

    const headers = parseCSVLine(lines[0]);
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const values = parseCSVLine(lines[i]);
      const row = {};
      headers.forEach((h, idx) => { row[h] = values[idx] || ""; });
      rows.push(row);
    }

    let fileType = "other";
    if (file.includes("_stats_history")) fileType = "history";
    else if (file.includes("_stats")) fileType = "stats";
    else if (file.includes("_failures")) fileType = "failures";
    else if (file.includes("_exceptions")) fileType = "exceptions";

    files.push({ name: file, type: fileType, headers, rows });
  }

  const logPath = path.join(runDir, "script.log");
  let logContent = null;
  if (fs.existsSync(logPath)) {
    logContent = fs.readFileSync(logPath, "utf-8").slice(-50000);
  }

  res.json({ files, log: logContent });
});

// ===========================
// ALLURE API ENDPOINTS
// ===========================

// API: list runs for app/project (2-level) - Allure reports
// e.g. /api/ESS/App_Migration/runs
app.get("/api/:app/:project/runs", (req, res) => {
  const { app: appName, project } = req.params;
  const projectPath = path.join(REPORTS_DIR, appName, project);
  if (!fs.existsSync(projectPath)) {
    return res.json([]);
  }
  const reportBase = appName + "/" + project;
  const runs = getRuns(projectPath, reportBase);
  res.json(runs);
});

function getRuns(dirPath, reportBase) {
  const runs = [];
  if (!fs.existsSync(dirPath)) return runs;

  const entries = fs
    .readdirSync(dirPath, { withFileTypes: true })
    .filter((d) => d.isDirectory() && /^\d{8}/.test(d.name));

  for (const entry of entries) {
    const runPath = path.join(dirPath, entry.name);
    const summaryPath = path.join(runPath, "summary.json");

    let summary = null;
    if (fs.existsSync(summaryPath)) {
      try {
        summary = JSON.parse(fs.readFileSync(summaryPath, "utf-8"));
      } catch (e) {}
    }

    const stats = summary?.stats || {};
    const passed = stats.passed || 0;
    const failed = stats.failed || 0;
    const broken = stats.broken || 0;
    const skipped = stats.skipped || 0;
    const unknown = stats.unknown || 0;
    const total = stats.total || 0;
    const duration = summary?.duration || 0;
    const date = parseRunDate(entry.name);

    runs.push({
      id: entry.name,
      date,
      passed,
      failed,
      broken,
      skipped,
      unknown,
      total,
      duration,
      status: failed > 0 || broken > 0 ? "failed" : "passed",
      reportUrl: "/reports/" + reportBase + "/" + entry.name + "/index.html",
    });
  }

  runs.sort((a, b) => new Date(b.date) - new Date(a.date));
  return runs;
}

function parseRunDate(folderName) {
  const match = folderName.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
  if (match) {
    const [, y, m, d, h, min, s] = match;
    return new Date(y, m - 1, d, h, min, s).toISOString();
  }
  return new Date().toISOString();
}

// API: get CSV results for a specific Allure run
// e.g. /api/ESS/App_Migration/20260409_120000/results
app.get("/api/:app/:project/:runId/results", (req, res) => {
  const { app: appName, project, runId } = req.params;
  const csvDir = path.join(REPORTS_DIR, appName, project, runId, "csv-results");
  if (!fs.existsSync(csvDir)) {
    return res.json({ sheets: [] });
  }

  const csvFiles = fs.readdirSync(csvDir).filter(f => f.endsWith(".csv") && f.startsWith("results_"));
  const sheets = [];

  for (const file of csvFiles) {
    const sheetName = file.replace("results_", "").replace(".csv", "");
    const content = fs.readFileSync(path.join(csvDir, file), "utf-8");
    const lines = content.split("\n").filter(l => l.trim());
    if (lines.length === 0) continue;

    const headers = parseCSVLine(lines[0]);
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const values = parseCSVLine(lines[i]);
      const row = {};
      headers.forEach((h, idx) => { row[h] = values[idx] || ""; });
      rows.push(row);
    }
    sheets.push({ name: sheetName, headers, rows });
  }

  res.json({ sheets });
});

// API: list CSV files for download
app.get("/api/:app/:project/:runId/csv-files", (req, res) => {
  const { app: appName, project, runId } = req.params;
  const csvDir = path.join(REPORTS_DIR, appName, project, runId, "csv-results");
  if (!fs.existsSync(csvDir)) {
    return res.json([]);
  }
  const files = fs.readdirSync(csvDir).filter(f => f.endsWith(".csv"));
  res.json(files.map(f => ({
    name: f,
    url: "/reports/" + appName + "/" + project + "/" + runId + "/csv-results/" + f
  })));
});

// Simple CSV line parser (handles quoted fields with commas)
function parseCSVLine(line) {
  const result = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current.trim());
  return result;
}

// Serve AI Tools page
app.use("/ai-tools", express.static(path.join(__dirname, "ai-tools")));
app.get("/ai", (req, res) => {
  res.sendFile(path.join(__dirname, "ai-tools", "ai-tools.html"));
});

app.get("/", (req, res) => {
  res.redirect("/dashboard");
});

if (!fs.existsSync(REPORTS_DIR)) {
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
}

app.listen(PORT, () => {
  console.log("QA Dashboard running at http://localhost:" + PORT);
  console.log("Reports directory: " + REPORTS_DIR);
});
