const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 3000;
const REPORTS_DIR = path.join(__dirname, "reports");

app.use("/dashboard", express.static(path.join(__dirname, "public")));
app.use("/reports", express.static(REPORTS_DIR));

// API: list runs for system/app/project (3-level)
// e.g. /api/ES/ESS/App_Migration/runs
app.get("/api/:system/:app/:project/runs", (req, res) => {
  const { system, app: appName, project } = req.params;
  const projectPath = path.join(REPORTS_DIR, system, appName, project);
  if (!fs.existsSync(projectPath)) {
    return res.json([]);
  }
  const reportBase = system + "/" + appName + "/" + project;
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
