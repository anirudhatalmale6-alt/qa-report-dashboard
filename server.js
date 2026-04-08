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

// API: list all projects
app.get("/api/projects", (req, res) => {
  if (!fs.existsSync(REPORTS_DIR)) {
    return res.json([]);
  }
  const projects = fs
    .readdirSync(REPORTS_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const projectPath = path.join(REPORTS_DIR, d.name);
      const runs = getProjectRuns(projectPath);
      const latestRun = runs.length > 0 ? runs[0] : null;
      return {
        name: d.name,
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
      };
    });
  res.json(projects);
});

// API: list runs for a project
app.get("/api/projects/:project/runs", (req, res) => {
  const projectPath = path.join(REPORTS_DIR, req.params.project);
  if (!fs.existsSync(projectPath)) {
    return res.status(404).json({ error: "Project not found" });
  }
  const runs = getProjectRuns(projectPath);
  res.json(runs);
});

function getProjectRuns(projectPath) {
  const runs = [];
  if (!fs.existsSync(projectPath)) return runs;

  const entries = fs
    .readdirSync(projectPath, { withFileTypes: true })
    .filter((d) => d.isDirectory());

  for (const entry of entries) {
    const runPath = path.join(projectPath, entry.name);
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

    // Parse date from folder name (format: YYYYMMDD_HHmmss or similar)
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
      reportUrl: `/reports/${path.basename(projectPath)}/${entry.name}/index.html`,
    });
  }

  // Sort by date descending (newest first)
  runs.sort((a, b) => new Date(b.date) - new Date(a.date));
  return runs;
}

function parseRunDate(folderName) {
  // Try parsing YYYYMMDD_HHmmss format
  const match = folderName.match(
    /(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/
  );
  if (match) {
    const [, y, m, d, h, min, s] = match;
    return new Date(y, m - 1, d, h, min, s).toISOString();
  }
  // Try parsing ISO-like format
  const isoMatch = folderName.match(
    /(\d{4})-(\d{2})-(\d{2})[T_](\d{2})-(\d{2})-(\d{2})/
  );
  if (isoMatch) {
    const [, y, m, d, h, min, s] = isoMatch;
    return new Date(y, m - 1, d, h, min, s).toISOString();
  }
  // Fallback: use folder modification time
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
