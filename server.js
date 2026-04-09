const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 3000;
const REPORTS_DIR = path.join(__dirname, "reports");

// Serve static dashboard files
app.use("/dashboard", express.static(path.join(__dirname, "public")));

// Serve report files (each report is in its own subfolder)
app.use("/reports", express.static(REPORTS_DIR));

// API: list all projects with their systems
app.get("/api/projects", (req, res) => {
  if (!fs.existsSync(REPORTS_DIR)) {
    return res.json([]);
  }
  const projects = fs
    .readdirSync(REPORTS_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const projectPath = path.join(REPORTS_DIR, d.name);
      const systems = getProjectSystems(projectPath, d.name);
      const totalRuns = systems.reduce((sum, s) => sum + s.totalRuns, 0);
      return {
        name: d.name,
        systems: systems,
        totalRuns: totalRuns,
      };
    });
  res.json(projects);
});

// API: list runs for a category/subproject
app.get("/api/:category/:subproject/runs", (req, res) => {
  const { category, subproject } = req.params;
  const projectPath = path.join(REPORTS_DIR, category, subproject);
  if (!fs.existsSync(projectPath)) {
    return res.json([]);
  }
  const reportBase = `${category}/${subproject}`;
  const runs = getRuns(projectPath, reportBase);
  res.json(runs);
});

function getProjectSystems(projectPath, projectName) {
  const systems = [];
  const entries = fs
    .readdirSync(projectPath, { withFileTypes: true })
    .filter((d) => d.isDirectory());

  for (const entry of entries) {
    const entryPath = path.join(projectPath, entry.name);
    // Check if this is a system folder (contains timestamp folders)
    // or a direct run folder (is itself a timestamp folder)
    const isTimestamp = /^\d{8}/.test(entry.name);

    if (!isTimestamp) {
      // This is a system subfolder
      const reportBase = `${projectName}/${entry.name}`;
      const runs = getRuns(entryPath, reportBase);
      const latestRun = runs.length > 0 ? runs[0] : null;
      systems.push({
        name: entry.name,
        totalRuns: runs.length,
        latestRun: latestRun
          ? {
              date: latestRun.date,
              passed: latestRun.passed,
              failed: latestRun.failed,
              total: latestRun.total,
              status: latestRun.failed > 0 ? "failed" : "passed",
            }
          : null,
      });
    }
  }

  // If no system subfolders found, treat the project itself as having direct runs
  if (systems.length === 0) {
    const runs = getRuns(projectPath, projectName);
    if (runs.length > 0) {
      const latestRun = runs[0];
      systems.push({
        name: "_default",
        totalRuns: runs.length,
        latestRun: {
          date: latestRun.date,
          passed: latestRun.passed,
          failed: latestRun.failed,
          total: latestRun.total,
          status: latestRun.failed > 0 ? "failed" : "passed",
        },
      });
    }
  }

  return systems;
}

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
      } catch (e) {
        // skip invalid summary
      }
    }

    const stats = summary?.stats || {};
    const passed = stats.passed || 0;
    const failed = stats.failed || 0;
    const broken = stats.broken || 0;
    const skipped = stats.skipped || 0;
    const unknown = stats.unknown || 0;
    const total = stats.total || 0;
    const duration = summary?.duration || 0;

    let date = parseRunDate(entry.name);

    runs.push({
      id: entry.name,
      date: date,
      name: summary?.name || "Allure Report",
      passed,
      failed,
      broken,
      skipped,
      unknown,
      total,
      duration,
      status: failed > 0 || broken > 0 ? "failed" : "passed",
      reportUrl: `/reports/${reportBase}/${entry.name}/index.html`,
    });
  }

  runs.sort((a, b) => new Date(b.date) - new Date(a.date));
  return runs;
}

function parseRunDate(folderName) {
  const match = folderName.match(
    /(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/
  );
  if (match) {
    const [, y, m, d, h, min, s] = match;
    return new Date(y, m - 1, d, h, min, s).toISOString();
  }
  const isoMatch = folderName.match(
    /(\d{4})-(\d{2})-(\d{2})[T_](\d{2})-(\d{2})-(\d{2})/
  );
  if (isoMatch) {
    const [, y, m, d, h, min, s] = isoMatch;
    return new Date(y, m - 1, d, h, min, s).toISOString();
  }
  return new Date().toISOString();
}

// Redirect root to dashboard
app.get("/", (req, res) => {
  res.redirect("/dashboard");
});

// Ensure reports directory exists
if (!fs.existsSync(REPORTS_DIR)) {
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
}

app.listen(PORT, () => {
  console.log(`QA Report Dashboard running at http://localhost:${PORT}`);
  console.log(`Reports directory: ${REPORTS_DIR}`);
});
