const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 3000;
const REPORTS_DIR = path.join(__dirname, "reports");

app.use("/dashboard", express.static(path.join(__dirname, "public")));
app.use("/reports", express.static(REPORTS_DIR));

// API: list runs for app/project (2-level)
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

// API: get CSV results for a specific run
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
