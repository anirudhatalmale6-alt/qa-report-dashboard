# conftest.py
import os
import re
import pytest
import configparser
import pandas as pd
from typing import Dict, Any
from playwright.sync_api import sync_playwright
from lib.logger import logger
from lib.test_data_manager import load_test_data, write_to_cell, init_results_csv
from lib.constants import CONF_PATH, TEST_PLAN_PATH
from lib.test_data_manager import check_file_writable
import shutil
import subprocess
from application.application import Application
import logging
from logging.handlers import RotatingFileHandler

# Configure rotating logger
LOG_FILE = "test_execution.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3  # Keep 3 backup files

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Create a rotating file handler
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)



#######################
# CLI Options
#######################
def pytest_addoption(parser):
    logger.info("Adding custom command line options for pytest")
    parser.addoption("--env", action="store", default="prod", help="Environment to run tests against")
    parser.addoption("--ui", action="store_true", help="Run all UI tests, ignoring Execute flag")
    parser.addoption("--api", action="store_true", help="Run all API tests, ignoring Execute flag")
    parser.addoption("--all", action="store_true", help="Run all tests, ignoring Execute flag")
    parser.addoption("--project", default="default", help="Project name for dashboard")
    parser.addoption("--mode", default="uat", help="Run mode: 'prod' for production (single browser, manual login) or 'uat' for UAT (parallel, auto login)")
    parser.addoption("--headless", action="store_true", default=False, help="Run browsers in headless mode (no visible window)")

#######################
# Environment Config
#######################
@pytest.fixture(scope="session")
def env_config(request) -> Dict[str, str]:
    env = request.config.getoption("--env")
    logger.info(f"Loading configuration for environment: {env}")
    config = configparser.ConfigParser()
    if not os.path.exists(CONF_PATH):
        raise FileNotFoundError("Config file not found.")
    config.read(CONF_PATH)
    if env not in config:
        raise ValueError(f"Environment '{env}' not found in config file.")
    logger.info(f"Execution Started in {env}")
    return dict(config[env])


def pytest_configure(config):
    project = config.getoption("--project", default="default")
    with open("allure-project.txt", "w") as f:
        f.write(project)


#######################
# Helper: Expand DataReference ranges
#######################
def expand_data_references(data_ref, sheet_name, file_path):
    """
    Expand DataReference value into a list of actual DataReference strings.

    Supports:
      - "ALL"       -> reads all DataReference values from the sheet
      - "1-4000"    -> expands to DataRef1, DataRef2, ..., DataRef4000
      - "500-1000"  -> expands to DataRef500, DataRef501, ..., DataRef1000
      - "DataRef5"  -> single value, returned as-is (existing behavior)
    """
    data_ref_str = str(data_ref).strip()

    # Case 1: ALL - read every DataReference from the data sheet
    if data_ref_str.upper() == "ALL":
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        if 'DataReference' not in df.columns:
            raise KeyError(f"'DataReference' column missing in sheet '{sheet_name}'")
        refs = df['DataReference'].dropna().astype(str).str.strip().tolist()
        logger.info(f"Expanded ALL -> {len(refs)} DataReferences from sheet '{sheet_name}'")
        return refs

    # Case 2: Numeric range like "1-4000" or "500-1000"
    range_match = re.match(r'^(\d+)\s*-\s*(\d+)$', data_ref_str)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if start > end:
            start, end = end, start
        refs = [f"DataRef{i}" for i in range(start, end + 1)]
        logger.info(f"Expanded range {data_ref_str} -> {len(refs)} DataReferences (DataRef{start} to DataRef{end})")
        return refs

    # Case 3: Single specific DataReference (existing behavior)
    return [data_ref_str]


#######################
# Load Test Plan
#######################
def load_test_plan(config) -> pd.DataFrame:
    if not os.path.exists(TEST_PLAN_PATH):
        raise FileNotFoundError(f"Test plan not found at {TEST_PLAN_PATH}")
    df = pd.read_excel(TEST_PLAN_PATH)
    if 'TestType' not in df.columns:
        raise KeyError("'TestType' column is missing in RunManager.xlsx")

    df['TestType'] = df['TestType'].str.strip().str.upper()
    run_all_ui = config.getoption("--ui")
    run_all_api = config.getoption("--api")
    run_all = config.getoption("--all")

    if run_all:
        return df
    elif run_all_ui:
        return df[df['TestType'] == 'UI']
    elif run_all_api:
        return df[df['TestType'] == 'API']
    else:
        # Default behavior: only run tests marked Execute='Yes'
        return df[df['Execute'].str.lower() == 'yes']


# Load test plan once for parametrization
def pytest_generate_tests(metafunc):
    if 'test_context' in metafunc.fixturenames:
        test_plan_df = load_test_plan(metafunc.config)

        # Expand ranges: each TestPlan row may produce multiple test cases
        expanded_records = []
        for _, row in test_plan_df.iterrows():
            row_dict = row.to_dict()
            data_ref = row_dict.get('DataReference', '')
            sheet_name = row_dict.get('SheetName', '')

            # Expand the DataReference (ALL, range, or single)
            refs = expand_data_references(data_ref, sheet_name, TEST_PLAN_PATH)

            for ref in refs:
                expanded = row_dict.copy()
                expanded['DataReference'] = ref
                expanded_records.append(expanded)

        logger.info(f"Total parametrized tests after expansion: {len(expanded_records)}")

        # Build stable records for consistent Allure historyId
        stable_fields = ['TestName', 'TestMethod', 'DataReference', 'SheetName', 'TestType', 'Browser', 'Execute']
        stable_records = [{k: r.get(k) for k in stable_fields if k in r} for r in expanded_records]
        metafunc.parametrize("test_context", stable_records, indirect=True)


#######################
# Pytest Session Scope
#######################
def pytest_sessionstart(session):
    try:
        check_file_writable(TEST_PLAN_PATH)
    except PermissionError as e:
        # Stop the session before test collection
        pytest.exit(f"\n[ERROR] {e}\n", returncode=1)

    results_dir = "allure-results"
    if os.path.exists(results_dir):
        shutil.rmtree(results_dir)
    os.makedirs(results_dir)

    # Initialize results CSVs from Excel (read-only copy for writing results)
    # Only includes rows flagged with Execute='Yes' in TestPlan
    try:
        df = pd.read_excel(TEST_PLAN_PATH, sheet_name='TestPlan')
        # Filter to only Execute='Yes' rows
        exec_df = df[df['Execute'].str.strip().str.lower() == 'yes']

        # Build per-sheet DataReference lists from Execute='Yes' rows
        sheet_data_refs = {}
        for _, row in exec_df.iterrows():
            sn = str(row['SheetName']).strip()
            dr = str(row['DataReference']).strip()
            sheet_data_refs.setdefault(sn, []).append(dr)

        # Initialize CSV for each data sheet (filtered by DataReference)
        for sn, refs in sheet_data_refs.items():
            init_results_csv(sn, TEST_PLAN_PATH, data_refs=refs)

        # Initialize TestPlan CSV (filtered to Execute='Yes' rows only)
        yes_test_refs = [str(r).strip() for r in exec_df['DataReference'].dropna().tolist()]
        init_results_csv('TestPlan', TEST_PLAN_PATH, data_refs=yes_test_refs)

        logger.info(f"Initialized results CSVs for sheets: {list(sheet_data_refs.keys())} (Execute=Yes only)")
    except Exception as e:
        logger.warning(f"Could not initialize results CSVs: {e}")


#######################
# Playwright Session Scope
#######################
@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


#######################
# Production Mode: Session-scoped browser (single browser for all tests)
#######################
@pytest.fixture(scope="session")
def prod_browser(request, playwright_instance, env_config):
    """
    Session-scoped browser for production runs.
    Opens once, pauses for manual OTP login, then reused for all 4000 tests.
    """
    mode = request.config.getoption("--mode")
    if mode != "prod":
        yield None
        return

    is_headless = request.config.getoption("--headless")
    slow = 0 if is_headless else 2000
    launch_args = [] if is_headless else ["--start-maximized"]

    # Read browser from TestPlan Excel Browser column (first row)
    browser_name = "msedge"  # default
    try:
        df = pd.read_excel(TEST_PLAN_PATH, sheet_name='TestPlan')
        excel_browser = str(df['Browser'].dropna().iloc[0]).strip().lower()
        if excel_browser:
            browser_name = excel_browser
    except Exception:
        pass
    logger.info(f"Production mode: Browser from Excel -> '{browser_name}', headless={is_headless}")

    if browser_name == "msedge":
        browser = playwright_instance.chromium.launch(
            channel="msedge",
            headless=is_headless,
            slow_mo=slow,
            args=launch_args
        )
    elif browser_name == "chrome":
        browser = playwright_instance.chromium.launch(
            channel="chrome",
            headless=is_headless,
            slow_mo=slow,
            args=launch_args
        )
    elif browser_name in ("chromium", "firefox", "webkit"):
        browser = getattr(playwright_instance, browser_name).launch(
            headless=is_headless,
            slow_mo=slow,
            args=launch_args if browser_name == "chromium" else []
        )
    else:
        # Default to Edge
        browser = playwright_instance.chromium.launch(
            channel="msedge",
            headless=is_headless,
            slow_mo=slow,
            args=launch_args
        )
        browser_name = "msedge"
    context = browser.new_context(accept_downloads=True)
    context.set_default_timeout(120000)
    context.set_default_navigation_timeout(120000)
    page = context.new_page()

    # Navigate to base URL so user can login
    base_url = env_config.get("base_url", "")
    if base_url:
        page.goto(base_url)

    # Pause for manual OTP login
    print("\n" + "=" * 60)
    print("PRODUCTION MODE - Manual Login Required")
    print("=" * 60)
    print("The browser is open. Please:")
    print("  1. Complete the OTP login manually")
    print("  2. Wait until the page is fully loaded")
    print("  3. Press ENTER here to continue execution")
    print("=" * 60)
    input("Press ENTER after login is complete...")
    print("Resuming test execution...\n")

    logger.info("Production mode: Browser session started, manual login complete")

    yield {
        "browser": browser,
        "context": context,
        "page": page,
        "browser_name": browser_name,
        "playwright_instance": playwright_instance
    }

    # Cleanup at end of session
    try:
        browser.close()
    except Exception:
        pass


#######################
# Main Test Context Fixture
#######################
@pytest.fixture(scope='function')
def test_context(request, env_config, playwright_instance, prod_browser):
    mode = request.config.getoption("--mode")
    row = request.param
    test_type = row.get('TestType', 'API').strip().upper()
    test_info = {
        "test_name": row.get("TestName"),
        "test_method": row.get("TestMethod"),
        "data_ref": row.get("DataReference"),
        "sheet_name": row.get("SheetName"),
        "browser": row.get("Browser"),
        "test_type": test_type,
        "env": env_config
    }
    print(test_info["env"])
    print(test_info["browser"])
    logger.info(f"Running test: {test_type} : {test_info['test_name']} ({test_info['test_method']}) - DataRef: {test_info['data_ref']}")
    test_data = {}
    try:
        test_data = load_test_data(row["SheetName"], row["DataReference"], TEST_PLAN_PATH)
        test_data['BR'] = test_info["browser"]
    except Exception as e:
        logger.error(f"Could not load test data: {e}")

    logger.info(f"[{test_info['test_name']}] Loaded Test data: {row['DataReference']} from sheet {row['SheetName']}")
    test_info["test_data"] = test_data

    # Write TestMethod to results CSV so you can filter results by method
    try:
        write_to_cell(row["DataReference"], 'TestMethod', row.get("TestMethod", ""), row["SheetName"])
        write_to_cell(row["DataReference"], 'TestName', row.get("TestName", ""), row["SheetName"])
    except Exception:
        pass

    if test_type == "UI":
        if mode == "prod" and prod_browser is not None:
            # PRODUCTION MODE: Reuse session-scoped browser
            test_info["playwright_instance"] = prod_browser["playwright_instance"]
            test_info["browser_name"] = prod_browser["browser_name"]
            test_info["browser"] = prod_browser["browser"]
            test_info["context"] = prod_browser["context"]
            test_info["page"] = prod_browser["page"]
            request.node.test_info = test_info
            yield test_info
            # Do NOT close browser - it's session-scoped
        else:
            # UAT MODE: New browser per test (supports parallel execution)
            is_headless = request.config.getoption("--headless")
            slow = 0 if is_headless else 2000
            launch_args = [] if is_headless else ["--start-maximized"]
            browser_name = row.get("Browser", "chromium").lower()
            browser = None
            try:
                if browser_name == "msedge":
                    browser = playwright_instance.chromium.launch(
                        channel="msedge",
                        headless=is_headless,
                        slow_mo=slow,
                        args=launch_args
                    )
                else:
                    browser = getattr(playwright_instance, browser_name).launch(headless=is_headless, slow_mo=slow, args=launch_args)
                context = browser.new_context(accept_downloads=True)
                context.set_default_timeout(60000)
                context.set_default_navigation_timeout(60000)
                page = context.new_page()
                test_info["playwright_instance"] = playwright_instance
                test_info["browser_name"] = browser_name
                test_info["browser"] = browser
                test_info["context"] = context
                test_info["page"] = page
                request.node.test_info = test_info
                yield test_info
            finally:
                if browser:
                    browser.close()
    else:
        request.node.test_info = test_info
        yield test_info


def pytest_sessionfinish(session, exitstatus):
    import os
    import json
    import shutil
    import subprocess

    # Only run in the main process (not in xdist workers)
    if hasattr(session.config, "workerinput"):
        return

    results_dir = "allure-results"
    report_dir = "allure-report"

    # Ensure results exist
    if not os.path.exists(results_dir) or len(os.listdir(results_dir)) == 0:
        print("allure-results directory is missing or empty. No report will be generated.")
        return

    # ---------------------------------------------------------
    # 1. COPY HISTORY BEFORE GENERATING NEW REPORT
    # ---------------------------------------------------------
    history_src = os.path.join(report_dir, "history")
    history_dest = os.path.join(results_dir, "history")

    if os.path.exists(history_src):
        shutil.copytree(history_src, history_dest, dirs_exist_ok=True)
        print("✔ history copied for trend graph support")
    else:
        print("ℹ No previous history found (trend will appear from next run)")

    # ---------------------------------------------------------
    # 2. WRITE environment.properties
    # ---------------------------------------------------------
    env = session.config.getoption("--env") or "none"
    mode = session.config.getoption("--mode") or "uat"
    env_file = os.path.join(results_dir, "environment.properties")

    with open(env_file, "w") as f:
        f.write(f"Environment={env}\n")
        f.write(f"RunMode={mode}\n")
        f.write("Browser=Chromium\n")
        f.write("OS=Windows\n")
        f.write("Tester=Automation QA\n")

    print("✔ environment.properties added")

    # ---------------------------------------------------------
    # 3. WRITE executor.json
    # ---------------------------------------------------------
    executor_file = os.path.join(results_dir, "executor.json")
    executor_data = {
        "name": "Local Machine",
        "type": "local",
        "url": "http://localhost",
        "buildOrder": "1",
        "buildName": "Local Test Run",
        "buildUrl": "http://localhost/build"
    }

    with open(executor_file, "w") as f:
        json.dump(executor_data, f, indent=2)

    print("✔ executor.json added")

    # ---------------------------------------------------------
    # 4. WRITE categories.json
    # ---------------------------------------------------------
    categories_file = os.path.join(results_dir, "categories.json")
    categories_data = [
        {
            "name": "UI Bugs",
            "matchedStatuses": ["failed"],
            "messageRegex": "element|selector|not found"
        },
        {
            "name": "API Bugs",
            "matchedStatuses": ["failed"],
            "messageRegex": "API|timeout|500"
        },
        {
            "name": "Assertion Failures",
            "matchedStatuses": ["failed"],
            "traceRegex": "AssertionError"
        }
    ]

    with open(categories_file, "w") as f:
        json.dump(categories_data, f, indent=2)

    print("✔ categories.json added")

    # ---------------------------------------------------------
    # 5. GENERATE runmanager.json (for dashboard stats)
    # ---------------------------------------------------------
    try:
        df_full = pd.read_excel(TEST_PLAN_PATH, sheet_name='TestPlan')
        total_scripts = len(df_full)
        executed_df = df_full[df_full['Execute'].str.strip().str.lower() == 'yes']
        executed_count = len(executed_df)
        did_not_run = total_scripts - executed_count

        runmanager_data = {
            "totalScripts": total_scripts,
            "executed": executed_count,
            "didNotRun": did_not_run
        }

        # Save to current working directory (where pytest is run from)
        # NOT in allure-results/ (Allure tries to parse all JSON there)
        runmanager_path = os.path.join(os.getcwd(), "runmanager.json")
        with open(runmanager_path, "w") as f:
            json.dump(runmanager_data, f, indent=2)

        print(f"✔ runmanager.json added (Total: {total_scripts}, Executed: {executed_count}, Did Not Run: {did_not_run})")
    except Exception as e:
        print(f"⚠ Could not generate runmanager.json: {e}")

    # ---------------------------------------------------------
    # 6. RUN THE POWERSHELL SCRIPT TO GENERATE THE REPORT
    # ---------------------------------------------------------
    current_dir = os.path.dirname(os.path.abspath(__file__))
    allure_script_path = os.path.join(current_dir, 'allure.ps1')

    if not os.path.exists(allure_script_path):
        print(f"\nERROR: Allure PowerShell script not found at: {allure_script_path}")
        return

    try:
        subprocess.run([
            "powershell", "-ExecutionPolicy", "Bypass", "-File", allure_script_path
        ], check=True)
        print("\n✔ Allure report generated using allure.ps1")
    except Exception as e:
        print(f"\nFailed to generate Allure report using allure.ps1: {e}")



@pytest.fixture(autouse=True)
def clear_status_and_stacktrace_fixture(request, test_context):
    """
    Automatically clear FinalStatus and StackTrace before each test.
    Uses test_context to get the needed data.
    """
    # Defensive: only clear if these fields exist
    app = getattr(request.node, "app", None)
    # If you have an Application object, use it; otherwise, use test_context directly
    if app is not None:
        data_ref = app.data.get('DataReference')
        sheet_name = app.sheet_name
    else:
        data_ref = test_context.get('test_data', {}).get('DataReference')
        sheet_name = test_context.get('sheet_name')
    if data_ref and sheet_name:
        write_to_cell(data_ref, 'FinalStatus', '', sheet_name)
        write_to_cell(data_ref, 'StackTrace', '', sheet_name)


@pytest.fixture(autouse=True)
def write_status_and_stacktrace_fixture(request, test_context):
    app = getattr(request.node, "app", None)
    if app is not None:
        data_ref = app.data.get('DataReference')
        sheet_name = app.sheet_name
    else:
        data_ref = test_context.get('test_data', {}).get('DataReference')
        sheet_name = test_context.get('sheet_name')

    # Store on the node for later access in the hook
    request.node._data_ref = data_ref
    request.node._sheet_name = sheet_name

    yield


def pytest_runtest_makereport(item, call):
    if call.when == 'call':  # Only after the test body, not setup/teardown
        data_ref = getattr(item, '_data_ref', None)
        sheet_name = getattr(item, '_sheet_name', None)
        if data_ref and sheet_name:
            outcome = 'Passed' if call.excinfo is None else 'Failed'
            stacktrace = ''
            if call.excinfo is not None:
                # Get the traceback object
                tb = call.excinfo.tb
                # Walk to the last frame of the traceback (where exception occurred)
                while tb.tb_next:
                    tb = tb.tb_next
                    fname = tb.tb_frame.f_code.co_filename
                    func = tb.tb_frame.f_code.co_name
                    line = tb.tb_lineno
                    stacktrace = f"{str(call.excinfo.value)} at {func}() ({fname}:{line})"
            write_to_cell(data_ref, 'FinalStatus', outcome, sheet_name)
            write_to_cell(data_ref, 'StackTrace', stacktrace, sheet_name)