# QA Reports Dashboard

Centralized dashboard for viewing Allure test reports across all QA projects.

## Architecture

```
Test Machine (Windows)           Dashboard Server
+-------------------------+     +-------------------------+
| pytest runs tests       |     | Node.js + Express       |
| allure-results/ created |     | Serves reports at :3000 |
| allure.ps1 generates    |---->| reports/ directory      |
|   allure-report/        |     | /dashboard - main UI    |
| allure-publish.ps1      |     | /api/reports - REST API |
|   copies to server      |     +-------------------------+
+-------------------------+
```

## Prerequisites

- Node.js 18+ (https://nodejs.org/)
- Docker + Docker Compose (optional, for containerized deployment)


## Deployment - Option 1: Docker (Recommended)

1. Clone the repo:
   ```
   git clone <repo-url>
   cd qa-report-dashboard
   ```

2. Start the container:
   ```
   docker-compose up -d
   ```

3. Dashboard is live at:
   ```
   http://<server-ip>:3000/dashboard
   ```

4. To stop:
   ```
   docker-compose down
   ```

Notes:
- Reports persist in ./reports/ via Docker volume mount
- Container auto-restarts on failure (restart: unless-stopped)
- Port 3000 must be open in the firewall


## Deployment - Option 2: Manual (without Docker)

1. Clone the repo:
   ```
   git clone <repo-url>
   cd qa-report-dashboard
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the server:
   ```
   node server.js
   ```
   Or to run in background (Linux):
   ```
   nohup node server.js > dashboard.log 2>&1 &
   ```
   Or as a Windows service, use pm2:
   ```
   npm install -g pm2
   pm2 start server.js --name qa-dashboard
   pm2 save
   pm2 startup
   ```

4. Dashboard is live at:
   ```
   http://<server-ip>:3000/dashboard
   ```


## Test Machine Configuration

After the dashboard server is running, each test machine needs two things configured:

### 1. Update allure.ps1

In the Playwright test repo (testing/playwright/allure.ps1), update the DashboardPath:

```powershell
$DashboardPath = "\\<server-ip>\QA_Reports_Dashboard\qa-report-dashboard"
```

Or if reports are published via HTTP/network share, update the path accordingly.

### 2. Verify allure-publish.ps1

The allure-publish.ps1 script must be accessible at:
```
<DashboardPath>\allure-publish.ps1
```

This script is called automatically after each test run by allure.ps1.
It copies the generated Allure report into reports/<project>/<timestamp>/ on the server.


## How Reports Get Published

1. pytest finishes -> conftest.py pytest_sessionfinish() runs
2. conftest.py writes metadata files (environment.properties, executor.json, categories.json)
3. conftest.py generates runmanager.json (total scripts, executed, did not run)
4. conftest.py calls allure.ps1 via subprocess
5. allure.ps1 runs "allure generate allure-results -o allure-report"
6. allure.ps1 calls allure-publish.ps1 which copies the report to the dashboard server

Reports folder structure on the server:
```
reports/
  ESS/
    App_Migration/
      20260409_142722/
        index.html        (Allure report)
        summary.json      (stats: total, passed, failed)
        runmanager.json   (total scripts, executed, did not run)
        csv-results/      (test result CSVs)
    ADA/
      20260409_100000/
        ...
  Clarety/
    Maintenance/
      20260408_160000/
        ...
```


## Firewall / Network Requirements

- Port 3000: Open for dashboard web access (HTTP)
- Test machines need network access to the reports/ folder on the server
  - Option A: UNC path (Windows file share) \\server\reports
  - Option B: Mapped network drive
  - Option C: SCP/rsync from test machine to server


## Environment Setup (Test Machines)

For setting up a new test machine with all QA tools, run the setup script:
```
cd setup
.\setup-qa-env.ps1
```

This installs: Python packages, Playwright browsers, Allure 3 CLI, and Node.js dependencies.

See setup/setup-qa-env.ps1 for details and options.


## Files Overview

```
server.js              - Express server (main application)
package.json           - Node.js dependencies
docker-compose.yml     - Docker deployment config
Dockerfile             - Container build instructions
public/                - Frontend assets (HTML, CSS, JS)
  app.js               - Dashboard frontend logic
  style.css            - Dashboard styles
setup/                 - Environment setup scripts
  setup-qa-env.ps1     - One-click setup for test machines
  requirements.txt     - Python package list
allure-publish.ps1     - Report publishing script (called by allure.ps1)
reports/               - Report storage (created at runtime, not in repo)
```


## Troubleshooting

Dashboard not showing reports:
- Check that reports/ folder exists and has content
- Check that allure-publish.ps1 ran without errors (check pytest console output)
- Verify the DashboardPath in allure.ps1 points to the correct server location

Reports not publishing after test runs:
- Check pytest console for "allure-publish" related messages
- Verify allure CLI is installed: allure --version
- Verify allure-results/ directory has content after test run
- Check for PermissionError on allure-results/ or test-results/ folders
  (Windows antivirus/indexer can lock these - add exclusions)

Container won't start:
- Check logs: docker-compose logs
- Verify port 3000 is not already in use
- Verify Docker is running: docker info
