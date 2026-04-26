"""
QA Framework Documentation Publisher - Azure DevOps Wiki
---------------------------------------------------------
Publishes framework documentation pages to Azure DevOps Wiki:
  1. Pre-Requisite Installations
  2. Playwright Framework Architecture & User Guide
  3. Locust Framework Architecture & User Guide

Usage:
    python publish_wiki_docs.py --org https://dev.azure.com/SOM-DTMB --project ASSR-Development --pat YOUR_PAT

    # Preview without publishing:
    python publish_wiki_docs.py --preview

    # Publish specific page only:
    python publish_wiki_docs.py --page prereqs --org ... --project ... --pat ...
    python publish_wiki_docs.py --page playwright --org ... --project ... --pat ...
    python publish_wiki_docs.py --page locust --org ... --project ... --pat ...

Environment variables (alternative to CLI args):
    set AZURE_DEVOPS_ORG=https://dev.azure.com/SOM-DTMB
    set AZURE_DEVOPS_PROJECT=ASSR-Development
    set AZURE_DEVOPS_PAT=your_pat_token
"""
import os
import sys
import json
import argparse
import base64
from datetime import datetime

import requests


# ============================================================
# Wiki Page Paths (under Testing Standards)
# ============================================================
WIKI_PREFIX = "/Atlas Modernization/Testings Standards"

PAGES = {
    "prereqs": {
        "path": f"{WIKI_PREFIX}/Pre-Requisite Installations",
        "title": "Pre-Requisite Installations",
    },
    "playwright": {
        "path": f"{WIKI_PREFIX}/Playwright Framework Guide",
        "title": "Playwright Framework Architecture & User Guide",
    },
    "locust": {
        "path": f"{WIKI_PREFIX}/Locust Framework Guide",
        "title": "Locust Framework Architecture & User Guide",
    },
}


# ============================================================
# Page Content Generators
# ============================================================

def generate_prereqs_page() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# Pre-Requisite Installations
_Last updated: {now}_

## General Information

| Revision Date | Author | Section(s) | Summary |
|---------------|--------|------------|---------|
| {datetime.now().strftime("%m/%d/%Y")} | QA Automation Team | All | Document created |

::: {{.privacy}}
**Privacy Information**
This document contains information of a sensitive nature. This information should not be given to persons other than those who are involved with this system/project or who will become involved during its lifecycle.
:::

## 1. Introduction

This page describes the software prerequisites and installation steps required to set up the QA Automation Framework on a new workstation. Follow these steps before running any Playwright, Locust, or Allure tests.

## 2. Software Requirements

| Software | Version | Required | Download Link |
|----------|---------|----------|---------------|
| Python | 3.10 or higher | Yes | https://www.python.org/downloads/ |
| Node.js | 18 LTS or higher | Yes | https://nodejs.org/ |
| Git | Latest | Yes | https://git-scm.com/download/win |
| Visual Studio Code | Latest | Recommended | https://code.visualstudio.com/ |
| Microsoft Edge | Latest | Yes (default browser) | Pre-installed on Windows |

> **Important:** When installing Python, check **"Add Python to PATH"** during installation.

## 3. Automated Setup (Recommended)

A PowerShell script is provided that installs everything automatically:

```powershell
# Clone the repository
git clone <repo-url>
cd setup

# Run the setup script
.\\setup-qa-env.ps1

# Optional: Skip desktop automation packages
.\\setup-qa-env.ps1 -SkipDesktop

# Optional: Specify dashboard path
.\\setup-qa-env.ps1 -DashboardPath "C:\\QA_Reports_Dashboard\\qa-report-dashboard"
```

The script performs these steps automatically:
1. Checks Python, Node.js, Git are installed
2. Installs all Python packages from `requirements.txt`
3. Installs Playwright browsers (Chromium, Firefox, WebKit)
4. Installs Allure 3 CLI via npm
5. Sets up QA Dashboard dependencies
6. Verifies all installations

## 4. Manual Installation Steps

If you prefer manual installation or the script encounters issues:

### Step 1: Python Packages

```powershell
pip install -r setup/requirements.txt
```

**Core packages installed:**

| Package | Purpose |
|---------|---------|
| pytest | Test runner |
| pytest-playwright | Playwright integration for pytest |
| playwright | Browser automation library |
| pytest-xdist | Parallel test execution |
| allure-pytest | Allure reporting integration |
| locust | Performance/load testing |
| pandas, openpyxl | Excel data handling |
| requests | HTTP/API testing |
| assertpy | Fluent assertion library |
| Faker | Test data generation |
| pyodbc | SQL Server database connectivity |
| pyyaml | YAML configuration parsing |
| jsonpath-ng | JSON path expressions |

### Step 2: Playwright Browsers

```powershell
python -m playwright install
```

This installs Chromium, Firefox, and WebKit browsers. For systems requiring dependencies:

```powershell
python -m playwright install --with-deps
```

### Step 3: Allure 3 CLI

```powershell
npm install -g allure@3
```

Verify installation:
```powershell
allure --version
```

### Step 4: QA Dashboard

```powershell
cd <dashboard-folder>
npm install
```

### Step 5: Desktop Automation (Optional)

Only needed if running desktop automation tests:

```powershell
pip install pyautoit pyautogui
```

## 5. Verification

Run these commands to verify everything is installed correctly:

```powershell
python -m pytest --version        # Should show pytest 8.x
python -m playwright --version    # Should show playwright version
python -m locust --version        # Should show locust 2.x
allure --version                  # Should show allure 3.x
node --version                    # Should show v18.x or higher
```

## 6. Environment Configuration

After installation, configure the test environment:

1. **Environment config**: Update `config/env_config.txt` with target environment URLs
2. **Test data**: Place test data Excel files in `test_data/` folder
3. **RunManager**: Configure `RunManager.xlsx` with test plan and data references

## 7. Quick Start Commands

| Action | Command |
|--------|---------|
| Run Playwright tests | `pytest tests/ --alluredir=allure-results` |
| Run with parallel execution | `pytest tests/ -n 6 --alluredir=allure-results` |
| Run specific test | `pytest tests/miors/test_miors_ui.py -k "test_name"` |
| Run Locust load test | `python -m locust -f wss/WSS_Retiredmem.py --headless -u 10 -r 2` |
| Generate Allure report | `.\\allure.ps1` |
| Start QA Dashboard | `node server.js` |
| View dashboard | Open http://localhost:3000/dashboard |

## 8. Troubleshooting

| Issue | Solution |
|-------|----------|
| `python` not recognized | Add Python to PATH: System Properties > Environment Variables |
| Playwright browsers fail to install | Run as Administrator: `python -m playwright install --with-deps` |
| `locust` command not found | Use `python -m locust` instead of `locust` directly |
| Allure not on PATH | Restart terminal after npm install, or use full path |
| pyodbc install fails | Install ODBC Driver 17 for SQL Server from Microsoft |
| npm permission error | Run PowerShell as Administrator |

---
_Generated automatically by publish_wiki_docs.py_
"""


def generate_playwright_page() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# Playwright Framework Architecture & User Guide
_Last updated: {now}_

## General Information

| Revision Date | Author | Section(s) | Summary |
|---------------|--------|------------|---------|
| {datetime.now().strftime("%m/%d/%Y")} | QA Automation Team | All | Document created |

::: {{.privacy}}
**Privacy Information**
This document contains information of a sensitive nature. This information should not be given to persons other than those who are involved with this system/project or who will become involved during its lifecycle.
:::

## 1. Introduction

The QA Automation Framework uses **Microsoft Playwright** for browser-based UI testing. It follows a **Page Object Model (POM)** pattern with Excel-driven test data management and Allure reporting integration. Tests are written in Python using the `pytest` framework.

## 2. Architecture Overview

```
+------------------+     +-----------------+     +------------------+
|   RunManager     |     |   conftest.py   |     |   Allure Report  |
|   (Excel)        +---->+   (Fixtures &   +---->+   (HTML Report   |
|   Test Plan &    |     |    Hooks)       |     |    + Dashboard)  |
|   Data Sheets    |     +---------+-------+     +------------------+
+------------------+               |
                                   v
                    +-----------------------------+
                    |      Application Layer      |
                    |   application/application.py|
                    +------+--------+------+------+
                           |        |      |
                    +------v--+ +---v---+ +v--------+
                    |   UI    | |  API  | |   DB    |
                    |  Layer  | | Layer | |  Layer  |
                    +---------+ +-------+ +---------+
                         |
              +----------+----------+
              |          |          |
         +----v----+ +--v---+ +---v------+
         |  Page   | | Page | |   Page   |
         | Objects | | Objs | |  Objects |
         | (MIORS) | | (WSS)| | (CLT,..) |
         +---------+ +------+ +----------+
```

### Layer Responsibilities

| Layer | Purpose | Key Files |
|-------|---------|-----------|
| **Test Layer** | Test definitions, pytest parametrization | `tests/*.py` |
| **Application Layer** | Routes actions to UI/API/DB layers | `application/application.py` |
| **UI Layer** | Page Objects with Playwright actions | `application/ui/*.py` |
| **API Layer** | REST API test methods | `application/api/*.py` |
| **DB Layer** | SQL Server database queries | `application/db/*.py` |
| **Lib Layer** | Shared utilities (logging, data, config) | `lib/*.py` |

## 3. Folder Structure

```
SOM_2.0/
|-- conftest.py                    # Session setup, fixtures, hooks
|-- pytest.ini                     # Pytest configuration
|-- application/
|   |-- application.py             # Main Application class (router)
|   |-- ui/
|   |   |-- ui_application.py      # UI Application (page object manager)
|   |   |-- login_page.py          # Login page object
|   |   |-- miors_login_page.py    # MIORS login & navigation
|   |   |-- miors_product_admin.py # MIORS product administration
|   |   |-- clt_home_page.py       # Clarety home page
|   |   |-- wss_login_page.py      # WSS login
|   |   +-- ...                    # Other page objects
|   |-- api/                       # API test layer
|   +-- db/                        # Database query layer
|-- lib/
|   |-- constants.py               # URLs, credentials, file paths
|   |-- logger.py                  # Logging configuration
|   |-- test_data_manager.py       # Excel read/write operations
|   |-- config.py                  # Environment config parser
|   +-- test_registry.py           # Test name registry
|-- tests/
|   |-- test_run_manager.py        # Main entry point (parametrized)
|   |-- miors/test_miors_ui.py     # MIORS test scripts
|   |-- wss/test_wss_ui.py         # WSS test scripts
|   |-- ess/test_ess_ui.py         # ESS test scripts
|   |-- clarety/test_clarety_ui.py # Clarety test scripts
|   +-- api/test_apitests.py       # API test scripts
|-- test_data/
|   +-- SERS_RAP.xlsx              # RunManager + data sheets
+-- config/
    +-- env_config.txt             # Environment URLs & credentials
```

## 4. Key Components

### 4.1 conftest.py (Test Configuration)

The `conftest.py` file is the heart of the framework. It provides:

**Fixtures:**
- `prod_browser` (session scope) - Single browser for production mode with manual OTP login
- `test_context` (function scope) - Fresh browser per test for UAT parallel execution
- `app` - The `Application` object injected into every test

**Dynamic Test Generation:**
- `pytest_generate_tests()` reads the RunManager Excel sheet
- Expands data references (supports `ALL`, ranges like `1-4000`, lists like `1,45,62`)
- Generates unique test IDs for Allure trend tracking

**Result Reporting Hooks:**
- `pytest_runtest_makereport()` writes FinalStatus and StackTrace back to Excel
- `pytest_sessionfinish()` generates Allure report and copies history for trends

### 4.2 Application Class (Router)

```python
# application/application.py
class Application:
    def __init__(self, test_context):
        self.ui = UIApplication(test_context.page)
        self.api = APIApplication()
        self.db = DBApplication()
        self.data = test_context.data      # Test data from Excel
        self.env = test_context.env        # Environment config
        self.sheet_name = test_context.sheet_name
```

Every test receives an `app` object with access to all layers.

### 4.3 Page Objects

Each page object encapsulates:
- **Locators** (XPath/CSS selectors in a separate `*_Locators` class)
- **Actions** (click, fill, select, wait)
- **Verifications** (assertions on page state)

Example pattern:
```python
class MIORSLoginPage:
    def __init__(self, page):
        self.page = page
        self.loc = MIORSLoginLocators()

    def loginToMiORS(self, data, sheet_name):
        self.page.fill(self.loc.username_field, data["Username"])
        self.page.fill(self.loc.password_field, data["Password"])
        self.page.click(self.loc.login_button)
```

### 4.4 Test Data Manager

- Reads test data from Excel sheets using `openpyxl`
- Supports multiple data references per test
- Writes results (Pass/Fail/Timestamp) back to Excel after execution

## 5. Execution Modes

### 5.1 UAT Mode (Default - Parallel)

```powershell
# Run all tests with 6 parallel workers
pytest tests/ -n 6 --alluredir=allure-results

# Run specific application tests
pytest tests/miors/ --alluredir=allure-results

# Run single test by name
pytest tests/ -k "test_miors_ChangeInsurancePremiums" --alluredir=allure-results
```

- Fresh browser per test (function-scoped fixture)
- Supports `pytest-xdist` parallel execution
- Headless by default (use `--headed` for visible browser)

### 5.2 Production Mode (Sequential)

```powershell
# Production mode with Edge browser
pytest tests/ --mode prod --browser msedge --alluredir=allure-results
```

- Single browser session (session-scoped fixture)
- Pauses for manual MiLogin OTP entry
- Uses persistent browser context for SSO
- Sequential execution (no parallelism)

### 5.3 Headless Mode

```powershell
# Run headless (faster, no UI)
pytest tests/ --headless --alluredir=allure-results
```

## 6. RunManager Excel Structure

### TestPlan Sheet

| Column | Description |
|--------|-------------|
| TestName | Display name for the test |
| TestMethod | Python test function name (e.g., `test_miors_ChangeInsurancePremiums`) |
| TestType | Category (Smoke, Regression, etc.) |
| DataReference | Sheet name + row references (e.g., `Sheet1!ALL` or `Sheet1!1,2,3`) |
| Browser | Target browser (chromium, firefox, msedge) |
| Execute | Yes/No flag to include in run |

### Data Sheets

Each data sheet contains test data with columns specific to the test:
- Row 1: Column headers
- Row 2+: Test data (one row = one test iteration)

## 7. Allure Reporting

### Generate Report

```powershell
# After test execution
.\\allure.ps1
```

### Publish to Dashboard

```powershell
# Publish report to QA Dashboard
.\\allure-publish.ps1 -App ESS -Project App_Migration
```

### Report Features
- Test results with pass/fail/broken status
- Screenshots on failure (auto-captured)
- Test execution timeline
- Trend charts (when history is maintained)
- Environment details
- Categories (UI Bugs, API Bugs, Assertion Failures)

## 8. Writing New Tests

### Step 1: Create Page Object (if needed)

```python
# application/ui/new_page.py
class NewPage:
    def __init__(self, page):
        self.page = page

    def perform_action(self, data):
        self.page.fill("input#field", data["value"])
        self.page.click("button#submit")
```

### Step 2: Register in UIApplication

```python
# application/ui/ui_application.py
from application.ui.new_page import NewPage

class UIApplication:
    @property
    def new_page(self):
        if not hasattr(self, '_new_page'):
            self._new_page = NewPage(self.page)
        return self._new_page
```

### Step 3: Write Test Function

```python
# tests/new/test_new_feature.py
from lib.test_registry import register_test

@register_test("test_new_feature_action")
def test_new_feature_action(app: Application):
    app.ui.gotoMIORS(app.env["base_url"])
    app.ui.miors_login_page.loginToMiORS(app.data, app.sheet_name)
    app.ui.new_page.perform_action(app.data)
```

### Step 4: Add to RunManager Excel

Add a row to the TestPlan sheet with TestMethod = `test_new_feature_action` and configure data references.

## 9. Best Practices

1. **Use Page Object Model** - Never put locators directly in test files
2. **Data-Driven Tests** - Use Excel for test data, not hardcoded values
3. **Wait Strategies** - Use `page.wait_for_selector()` or `expect()` instead of `time.sleep()`
4. **Screenshots** - Capture on failure using Allure attachments
5. **Meaningful Names** - Test names should describe the business action
6. **Keep Tests Independent** - Each test should be runnable in isolation
7. **Allure Annotations** - Add `allure.dynamic.story()` and `allure.dynamic.description()` for traceability

---
_Generated automatically by publish_wiki_docs.py_
"""


def generate_locust_page() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""# Locust Framework Architecture & User Guide
_Last updated: {now}_

## General Information

| Revision Date | Author | Section(s) | Summary |
|---------------|--------|------------|---------|
| {datetime.now().strftime("%m/%d/%Y")} | QA Automation Team | All | Document created |

::: {{.privacy}}
**Privacy Information**
This document contains information of a sensitive nature. This information should not be given to persons other than those who are involved with this system/project or who will become involved during its lifecycle.
:::

## 1. Introduction

The QA Automation Framework uses **Locust** for performance and load testing. Locust is a Python-based load testing tool that simulates user behavior by running concurrent virtual users. Our framework extends Locust with custom utilities for thread-safe data distribution, session management, and integration with the QA Reports Dashboard.

## 2. Architecture Overview

```
+------------------+     +------------------+     +------------------+
|  Locust Script   |     |   DataPool       |     |   CSV Results    |
|  (User Behavior) +---->+  (Thread-safe    +---->+  (Stats &        |
|                  |     |   Data Queue)    |     |   Dashboard)     |
+--------+---------+     +------------------+     +------------------+
         |
         v
+------------------+     +------------------+
|  BaseTaskSet     |     |   Session        |
|  (Sequential     +---->+   Manager        |
|   Task Runner)   |     |  (Auth/Cookies)  |
+------------------+     +------------------+
```

### Component Responsibilities

| Component | Purpose |
|-----------|---------|
| **Locust Script** | Defines user behavior (HTTP requests, flow) |
| **BaseTaskSet** | Sequential task execution base class |
| **DataPool** | Thread-safe data distribution across virtual users |
| **SessionManager** | Handles authentication and session cookies |
| **run-locust.ps1** | Launcher script with environment configuration |

## 3. Folder Structure

```
allure-dashboard/
|-- locust-enhancements/
|   |-- base_taskset.py              # SequentialTaskSet base class
|   |-- data_pool.py                 # Thread-safe DataPool
|   |-- logger.py                    # Logging wrapper
|   +-- WSS_Retiredmem_example.py    # Example load test
|-- wss/
|   +-- WSS_Retiredmem.py            # WSS retired member load test
|-- ess/
|   +-- ESS_*.py                     # ESS load test scripts
|-- run-locust.ps1                   # Launcher script
+-- locust-publish.ps1               # Results publisher (to dashboard)
```

## 4. Key Components

### 4.1 DataPool (Thread-Safe Data Distribution)

The `DataPool` class ensures each virtual user gets unique test data without race conditions:

```python
from locust_enhancements.data_pool import DataPool

# Create pool with test data
member_data = [
    {{"member_id": "M001", "name": "John Doe"}},
    {{"member_id": "M002", "name": "Jane Smith"}},
    # ... more test data
]
pool = DataPool(member_data, reusable=False)
```

**Key Features:**
- **Thread-safe**: Uses Python `queue.Queue` internally
- **Reusable mode**: `reusable=True` recycles data (for sustained load)
- **One-time mode**: `reusable=False` each data item used once (for data migration)
- **Auto-interrupt**: Stops the Locust user when pool is exhausted

### 4.2 BaseTaskSet (Sequential Task Runner)

Extends Locust's `SequentialTaskSet` for ordered task execution:

```python
from locust_enhancements.base_taskset import BaseTaskSet

class MyTaskSet(BaseTaskSet):
    @task
    def step1_login(self):
        data = self.get_next_data(member_pool)
        self.client.post("/login", json=data)

    @task
    def step2_search(self):
        self.client.get(f"/search?id={{self.current_data['member_id']}}")

    @task
    def step3_verify(self):
        response = self.client.get(f"/details/{{self.current_data['member_id']}}")
        assert response.status_code == 200
```

### 4.3 Session Manager

Handles authenticated sessions for testing internal applications:

```python
class SessionManager:
    def __init__(self, client):
        self.client = client

    def login(self, username, password):
        resp = self.client.post("/auth/login", data={{
            "username": username,
            "password": password
        }})
        # Session cookies automatically maintained by Locust client
```

## 5. Writing a Locust Script

### Step 1: Define Test Data

```python
import csv
from locust_enhancements.data_pool import DataPool

def load_test_data():
    with open("test_data/members.csv") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]

member_pool = DataPool(load_test_data(), reusable=False)
```

### Step 2: Define User Behavior

```python
from locust import HttpUser, task, between
from locust_enhancements.base_taskset import BaseTaskSet

class MemberFlowTaskSet(BaseTaskSet):
    @task
    def login(self):
        self.data = self.get_next_data(member_pool)
        self.client.post("/api/login", json={{
            "user": self.data["username"],
            "pass": self.data["password"]
        }})

    @task
    def search_member(self):
        self.client.get(f"/api/members/{{self.data['member_id']}}")

    @task
    def update_record(self):
        self.client.put(f"/api/members/{{self.data['member_id']}}", json={{
            "status": "active"
        }})

class WebsiteUser(HttpUser):
    tasks = [MemberFlowTaskSet]
    wait_time = between(1, 3)  # 1-3 seconds between tasks
    host = "https://target-environment.michigan.gov"
```

### Step 3: Configure and Run

```powershell
# Run with 10 users, spawn rate 2 users/second, for 5 minutes
python -m locust -f wss/WSS_Retiredmem.py --headless -u 10 -r 2 -t 5m

# Run with web UI (opens http://localhost:8089)
python -m locust -f wss/WSS_Retiredmem.py
```

## 6. Execution Methods

### 6.1 Headless Mode (Recommended for CI/CD)

```powershell
python -m locust -f <script.py> --headless -u <users> -r <spawn-rate> -t <duration>
```

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-f` | Script file path | `wss/WSS_Retiredmem.py` |
| `--headless` | No web UI | - |
| `-u` | Number of virtual users | `10` |
| `-r` | Spawn rate (users/second) | `2` |
| `-t` | Test duration | `5m`, `1h`, `30s` |
| `--csv` | Export results to CSV | `results/output` |
| `-H` | Target host override | `https://env.michigan.gov` |

### 6.2 Web UI Mode (Interactive)

```powershell
python -m locust -f wss/WSS_Retiredmem.py
# Open http://localhost:8089 in browser
```

The web UI provides:
- Real-time charts (requests/sec, response times, user count)
- Request statistics table
- Failure details
- Download CSV results

### 6.3 Using the Launcher Script

```powershell
# Uses pre-configured settings
.\\run-locust.ps1 -Script "wss/WSS_Retiredmem.py" -Users 10 -SpawnRate 2 -Duration "5m"
```

## 7. Results & Reporting

### 7.1 CSV Output

Locust generates CSV files with performance statistics:

| File | Contents |
|------|----------|
| `*_stats.csv` | Per-request statistics (avg, median, min, max response times) |
| `*_stats_history.csv` | Time-series data for trend analysis |
| `*_failures.csv` | Failed request details |
| `*_exceptions.csv` | Python exceptions during test |

### 7.2 Publishing to QA Dashboard

```powershell
# Publish results to the QA Reports Dashboard
.\\locust-publish.ps1 -App ESS -Project App_Migration -Script WSS_Retiredmem
```

This copies CSV results and creates a `summary.json` for the dashboard to display:
- Total requests & failures
- Average response time
- Pass rate
- Per-endpoint breakdown

### 7.3 Viewing in Dashboard

Navigate to: **Performance Test > [App] > [Project] > [Script]** in the QA Reports Dashboard to view:
- Run history with pass/fail status
- Response time trends (displayed in seconds)
- Detailed stats table per run
- CSV download

## 8. Performance Testing Scenarios

### Scenario Types

| Type | Users | Duration | Purpose |
|------|-------|----------|---------|
| **Smoke** | 1-2 | 1 min | Verify script works |
| **Load** | 10-50 | 10-30 min | Normal load behavior |
| **Stress** | 50-200 | 15-60 min | Find breaking point |
| **Soak** | 10-20 | 1-4 hours | Memory leaks, stability |

### Example: Smoke Test

```powershell
python -m locust -f wss/WSS_Retiredmem.py --headless -u 1 -r 1 -t 1m --csv results/smoke
```

### Example: Load Test

```powershell
python -m locust -f wss/WSS_Retiredmem.py --headless -u 20 -r 5 -t 30m --csv results/load
```

## 9. Best Practices

1. **Start Small** - Always run a smoke test (1 user) before scaling up
2. **Use DataPool** - Never share mutable state between users without DataPool
3. **Realistic Wait Times** - Use `between(1, 5)` to simulate real user think time
4. **Monitor Target** - Watch server CPU/memory during load tests
5. **Isolate Environment** - Run load tests against dedicated environments, not shared UAT
6. **Save Baselines** - Record baseline metrics before code changes for comparison
7. **Check Failures First** - A high failure rate invalidates all performance metrics
8. **Use CSV Export** - Always export CSV for historical tracking and dashboard integration

## 10. Troubleshooting

| Issue | Solution |
|-------|----------|
| `locust` command not found | Use `python -m locust` instead |
| Connection refused | Check target host URL and VPN connectivity |
| All requests failing | Verify authentication/session setup in the script |
| High response times on start | Normal - Locust spawns users gradually (controlled by `-r`) |
| Script hangs after completion | Set timeout: `proc.wait(timeout=1800)` in launcher |
| DataPool exhausted too fast | Increase test data or use `reusable=True` |
| Memory issues with many users | Use `--processes` flag to spread across CPU cores |

---
_Generated automatically by publish_wiki_docs.py_
"""


# ============================================================
# Publish to Azure DevOps Wiki (reused from publish_coverage_wiki.py)
# ============================================================
def publish_to_wiki(org_url: str, project: str, pat: str, wiki_page_path: str, content: str):
    auth = base64.b64encode(f":{pat}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }

    wiki_url = f"{org_url}/{project}/_apis/wiki/wikis?api-version=7.1"
    resp = requests.get(wiki_url, headers=headers)

    if resp.status_code != 200:
        print(f"  Failed to list wikis: {resp.status_code} {resp.text}")
        return False

    wikis = resp.json().get("value", [])
    if not wikis:
        print("  No wikis found in the project.")
        return False

    wiki_id = wikis[0]["id"]
    print(f"  Using wiki: {wikis[0]['name']}")

    page_url = f"{org_url}/{project}/_apis/wiki/wikis/{wiki_id}/pages?path={wiki_page_path}&api-version=7.1"

    get_resp = requests.get(page_url, headers=headers)

    if get_resp.status_code == 200:
        etag = get_resp.headers.get("ETag", "")
        update_headers = {**headers, "If-Match": etag}
        put_resp = requests.put(page_url, headers=update_headers, json={"content": content})
        if put_resp.status_code == 200:
            print(f"  Wiki page UPDATED: {wiki_page_path}")
            return True
        else:
            print(f"  Failed to update: {put_resp.status_code} {put_resp.text}")
            return False
    else:
        put_resp = requests.put(page_url, headers=headers, json={"content": content})
        if put_resp.status_code in (200, 201):
            print(f"  Wiki page CREATED: {wiki_page_path}")
            return True
        else:
            print(f"  Failed to create: {put_resp.status_code} {put_resp.text}")
            return False


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Publish QA framework docs to Azure DevOps Wiki")
    parser.add_argument("--org", default=os.environ.get("AZURE_DEVOPS_ORG", ""), help="Azure DevOps org URL")
    parser.add_argument("--project", default=os.environ.get("AZURE_DEVOPS_PROJECT", ""), help="Project name")
    parser.add_argument("--pat", default=os.environ.get("AZURE_DEVOPS_PAT", ""), help="Personal Access Token")
    parser.add_argument("--page", default="all", choices=["all", "prereqs", "playwright", "locust"],
                        help="Which page to publish (default: all)")
    parser.add_argument("--preview", action="store_true", help="Preview markdown without publishing")
    parser.add_argument("--wiki-prefix", default=WIKI_PREFIX, help="Wiki path prefix")
    args = parser.parse_args()

    generators = {
        "prereqs": generate_prereqs_page,
        "playwright": generate_playwright_page,
        "locust": generate_locust_page,
    }

    pages_to_publish = list(generators.keys()) if args.page == "all" else [args.page]

    for page_key in pages_to_publish:
        page_info = PAGES[page_key]
        wiki_path = page_info["path"]
        if args.wiki_prefix != WIKI_PREFIX:
            wiki_path = f"{args.wiki_prefix}/{page_info['title']}"

        print(f"\n{'='*60}")
        print(f"  {page_info['title']}")
        print(f"  Wiki path: {wiki_path}")
        print(f"{'='*60}")

        content = generators[page_key]()

        if args.preview:
            print(content)
            continue

        if not args.org or not args.project or not args.pat:
            local_file = f"wiki_{page_key}.md"
            with open(local_file, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  Saved locally: {local_file}")
            print(f"  (Provide --org, --project, --pat to publish to Azure DevOps)")
            continue

        success = publish_to_wiki(args.org, args.project, args.pat, wiki_path, content)
        if success:
            print(f"  View at: {args.org}/{args.project}/_wiki/wikis/{args.project}.wiki{wiki_path}")

        local_file = f"wiki_{page_key}.md"
        with open(local_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Also saved locally: {local_file}")

    if not args.preview:
        print(f"\nDone! {len(pages_to_publish)} page(s) processed.")


if __name__ == "__main__":
    main()
