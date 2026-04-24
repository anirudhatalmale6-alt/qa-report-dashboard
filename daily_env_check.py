"""
Daily Environment Check Automation
===================================
Replaces the manual workflow:
  1. Run 3 Locust scripts (Clarety, ESS, WSS)
  2. Run SQL queries for Business Dates (replaces VBS)
  3. Read all results + Assignment data
  4. Build HTML email table
  5. Send via Outlook

Usage:
  python daily_env_check.py
  python daily_env_check.py --skip-locust     (skip Locust, use existing .txt files)
  python daily_env_check.py --skip-sql        (skip SQL, use existing sql_output.txt)
  python daily_env_check.py --dry-run         (build email but don't send, save as HTML)

Schedule with Windows Task Scheduler to run every morning.
"""

import subprocess
import sys
import os
import time
import argparse
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION - Update these paths to match your environment
# =============================================================================

# Base directory where the scripts and output files live
BASE_DIR = r"\\hcs084islnpa020\orsfileshare\asttestteam\m-drive\Get_Env_Dates"

# Locust script paths (same folder as BASE_DIR)
LOCUST_SCRIPTS_DIR = BASE_DIR

# Output file paths (on network share)
MIOR_STATUS_FILE = os.path.join(BASE_DIR, "MIORStatus.txt")
ESS_STATUS_FILE = os.path.join(BASE_DIR, "ESSStatus.txt")
WSS_STATUS_FILE = os.path.join(BASE_DIR, "WSSStatus.txt")

# SQL connection info (from sql_input.txt)
SQL_INPUT_FILE = os.path.join(BASE_DIR, "sql_input.txt")

# Rules Engine DB config
RULES_ENGINE_SERVER = "orsuatdtda03.state.mi.us"
RULES_ENGINE_DB = "mipers_45"
RULES_ENGINE_QUERY = "select format(busn_dt,'MM/dd/yyyy') 'businessDate' from {db}.dbo.be_busn_dt"

# Assignment data for each environment (from Environments sheet)
ASSIGNMENTS = {
    "UAT11": "ES Testing US 241355 (Sudhakar)",
    "UAT25": "Siebel Break/fix - SD20 Performance Testing (Sudhakar) (see note about refreshes)",
    "UAT26": "CS Development for Sprints",
    "UAT27": "CS Peer Testing for Sprints",
    "UAT28": "CS Business Sprint Testing",
    "UAT35": "Security Vulnerabilities - Dev/Peer Testing",
    "UAT36": "ES Development for Sprints",
    "UAT37": "ES Peer Testing for Sprints",
    "UAT38": "ES Business Sprint Testing",
    "UAT45": "Daily Refresh Post Batch  |  PRD Mirror",
    "UAT46": "Testing Templates (Ben)/Test Team Testing",
    "UAT47": "US 231671 (UFT Testing - Pooja)",
    "UAT48": "ES ADA Testing - eMichigan, Business Testing, QA Testing",
    "UAT55": "26.04.16-025 SIT Testing",
    "UAT65": "Sprint Testing - 241155 and 243909 (Shana and Jamin)",
    "UAT75": "26.04.09-E002 SIT Testing",
    "UAT85": "26.04.16-025 Release Testing",
    "TT":    "26.04.16-025 Release Testing",
}

# Environment display order
ENV_ORDER = [
    "UAT11", "UAT25", "UAT26", "UAT27", "UAT28",
    "UAT35", "UAT36", "UAT37", "UAT38",
    "UAT45", "UAT46", "UAT47", "UAT48",
    "UAT55", "UAT65", "UAT75",
    "TT"
]

# Email recipients
EMAIL_TO = "DTMB-AST-ORS-Communications"
EMAIL_CC = "DTMB-AST-Test-Team; Meyers, Amber (DTMB); Potter, Joshua (DTMB); Wilson, Jason (DTMB)"

# =============================================================================
# STEP 1: Run Locust Scripts
# =============================================================================

def run_locust_scripts():
    """Run the 3 Locust environment check scripts."""
    scripts = [
        ("EnvChecks_Clarety.py", "30m"),
        ("EnvChecks_ESS.py", "30m"),
        ("EnvChecks_WSS.py", "30m"),
    ]

    processes = []
    for script, timeout in scripts:
        script_path = os.path.join(LOCUST_SCRIPTS_DIR, script)
        if not os.path.exists(script_path):
            print(f"WARNING: {script_path} not found, skipping")
            continue

        print(f"Starting {script}...")
        cmd = f'"{sys.executable}" -m locust -f "{script_path}" -u 1 -r 1 --only-summary --headless -t {timeout}'
        proc = subprocess.Popen(cmd, shell=True)
        processes.append((script, proc))
        time.sleep(10)  # stagger starts like Run_Locust.ps1

    print("Waiting for Locust scripts to finish (max 35 min)...")
    max_wait = 35 * 60  # 35 minutes safety timeout
    for script, proc in processes:
        try:
            proc.wait(timeout=max_wait)
            print(f"  {script} finished (exit code: {proc.returncode})")
        except subprocess.TimeoutExpired:
            print(f"  {script} timed out after 35 min - killing process")
            proc.kill()
            proc.wait()

    print("All Locust scripts completed.\n")


# =============================================================================
# STEP 2: Run SQL Queries (replaces Run_SQL_Extract_Dates.vbs)
# =============================================================================

def run_sql_queries():
    """Query business dates from SQL Server databases using pyodbc."""
    try:
        import pyodbc
    except ImportError:
        print("ERROR: pyodbc not installed. Run: pip install pyodbc")
        sys.exit(1)

    results = {}

    # Read sql_input.txt for server/db config
    if not os.path.exists(SQL_INPUT_FILE):
        print(f"WARNING: {SQL_INPUT_FILE} not found, skipping SQL queries")
        return results

    with open(SQL_INPUT_FILE, 'r') as f:
        lines = f.readlines()

    current_server = None
    conn = None

    for line in lines[1:]:  # skip header
        line = line.strip()
        if not line:
            continue

        parts = line.split(',')
        if len(parts) < 3:
            continue

        env = parts[0].strip()
        db = parts[-1].strip()
        server = ','.join(parts[1:-1]).strip()

        # Reconnect if server changed
        if server != current_server:
            if conn:
                conn.close()
            current_server = server
            try:
                conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};Server={server};Trusted_Connection=yes;"
                conn = pyodbc.connect(conn_str, timeout=10)
                print(f"  Connected to {server}")
            except Exception as e:
                print(f"  ERROR connecting to {server}: {e}")
                conn = None

        # Query business date
        if conn:
            try:
                cursor = conn.cursor()
                sql = f"select format(busn_dt,'MM/dd/yyyy') 'businessDate' from {db}.dbo.be_busn_dt"
                cursor.execute(sql)
                row = cursor.fetchone()
                if row:
                    results[env] = row[0].strip()
                else:
                    results[env] = "N/A"
            except Exception as e:
                print(f"  ERROR querying {env} ({db}): {e}")
                results[env] = "N/A"
        else:
            results[env] = "N/A"

    if conn:
        conn.close()

    print(f"SQL queries complete. Got dates for {len(results)} environments.\n")
    return results


def get_rules_engine_date():
    """Query the Rules Engine business date."""
    try:
        import pyodbc
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};Server={RULES_ENGINE_SERVER};Trusted_Connection=yes;"
        conn = pyodbc.connect(conn_str, timeout=10)
        cursor = conn.cursor()
        sql = RULES_ENGINE_QUERY.format(db=RULES_ENGINE_DB)
        cursor.execute(sql)
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0].strip()
    except Exception as e:
        print(f"  ERROR querying Rules Engine: {e}")
    return "N/A"


# =============================================================================
# STEP 3: Read Locust Output Files
# =============================================================================

def read_status_file(filepath):
    """Read a status .txt file and return dict of {env: value}."""
    results = {}
    if not os.path.exists(filepath):
        print(f"WARNING: {filepath} not found")
        return results

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 1)
            if len(parts) == 2:
                env = parts[0].strip()
                val = parts[1].strip()
                if env:
                    results[env] = val

    return results


# =============================================================================
# STEP 4: Build HTML Email
# =============================================================================

def parse_miors_date(raw_value):
    """Parse MIORS date from various formats to MM/dd/yyyy.

    Input formats:
      - "Tue Apr 21 2026 07:22:59 AM"  (from Clarety login page)
      - "04/21/2026 07:22:59"          (alternative format)
      - "Bad Login"                     (login failed)
    """
    if not raw_value or raw_value == "N/A":
        return "#N/A"
    if "Bad Login" in str(raw_value):
        return "#N/A"

    raw = str(raw_value).strip()
    # Try parsing "Tue Apr 21 2026 07:22:59 AM"
    for fmt in ["%a %b %d %Y %I:%M:%S %p", "%a %b %d %Y %H:%M:%S %p",
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue

    # If it already looks like a date (contains /), return as-is
    if '/' in raw:
        return raw.split(' ')[0]

    return raw


def build_html_email(business_dates, mior_status, wss_status, ess_status, rules_engine_date):
    """Build the HTML email matching the existing format."""
    today = datetime.now().strftime("%m/%d/%Y")

    def date_cell_style(val):
        if not val or val in ("N/A", "#N/A") or "1900" in str(val) or "1/0/" in str(val):
            return 'background-color:#FFC7CE;color:#9C0006;'
        return 'background-color:#C6EFCE;color:#006100;'

    def status_cell_style(val):
        val_lower = str(val).lower().strip()
        if val_lower == 'ok':
            return 'background-color:#C6EFCE;color:#006100;'
        elif val_lower in ('down', 'n/a', '') or not val:
            return 'background-color:#FFC7CE;color:#9C0006;'
        elif 'milogin' in val_lower:
            return 'background-color:#FFEB9C;color:#9C6500;'
        return 'background-color:#C6EFCE;color:#006100;'

    def env_row(env, biz_date, miors_date, wss, ess, assignment, rules_col=""):
        rules_td = ""
        if rules_col == "SPACER":
            rules_td = (
                '<td style="border:none;padding:4px 8px;">&nbsp;</td>'
                f'<td style="border:1px solid #999;padding:4px 8px;text-align:center;">{rules_engine_date}</td>'
            )
        return f"""        <tr>
            <td style="border:1px solid #999;padding:4px 8px;font-weight:bold;">{env}</td>
            <td style="border:1px solid #999;padding:4px 8px;{date_cell_style(biz_date)}">{biz_date}</td>
            <td style="border:1px solid #999;padding:4px 8px;{date_cell_style(miors_date)}">{miors_date}</td>
            <td style="border:1px solid #999;padding:4px 8px;{status_cell_style(wss)}">{wss}</td>
            <td style="border:1px solid #999;padding:4px 8px;{status_cell_style(ess)}">{ess}</td>
            <td style="border:1px solid #999;padding:4px 8px;">{assignment}</td>
            {rules_td}
        </tr>
"""

    html = f"""<html>
<body style="font-family:Calibri,Arial,sans-serif;font-size:11pt;">
<h2 style="font-family:Calibri,Arial,sans-serif;margin-bottom:10px;">Environment Dates -{today}</h2>
<table style="border-collapse:collapse;font-family:Calibri,Arial,sans-serif;font-size:10pt;">
    <thead>
        <tr style="background-color:#4472C4;color:white;font-weight:bold;">
            <th style="border:1px solid #999;padding:6px 10px;">Environment</th>
            <th style="border:1px solid #999;padding:6px 10px;">Business Date</th>
            <th style="border:1px solid #999;padding:6px 10px;">MIORS Date</th>
            <th style="border:1px solid #999;padding:6px 10px;">WSS Status</th>
            <th style="border:1px solid #999;padding:6px 10px;">ESS Status</th>
            <th style="border:1px solid #999;padding:6px 10px;">Assignment</th>
            <th style="border:none;padding:6px 10px;">&nbsp;</th>
            <th style="border:1px solid #999;padding:6px 10px;background-color:#4472C4;color:white;">Rules Engine</th>
        </tr>
    </thead>
    <tbody>
"""

    for i, env in enumerate(ENV_ORDER):
        biz_date = business_dates.get(env, "N/A")
        miors_date = parse_miors_date(mior_status.get(env, ""))
        wss = wss_status.get(env, "N/A")
        ess = ess_status.get(env, "N/A")
        assignment = ASSIGNMENTS.get(env, "")
        rules = "SPACER" if i == 0 else ""
        html += env_row(env, biz_date, miors_date, wss, ess, assignment, rules)

    html += """    </tbody>
</table>
</body>
</html>"""

    return html


# =============================================================================
# STEP 5: Send Email via Outlook
# =============================================================================

def send_outlook_email(html_body, dry_run=False):
    """Send the HTML email via Outlook COM."""
    today = datetime.now().strftime("%m/%d/%Y")
    subject = f"Environment Dates -{today}"

    if dry_run:
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env_dates_email.html")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_body)
        print(f"Dry run - email saved to: {output_file}")
        print(f"Subject: {subject}")
        print(f"To: {EMAIL_TO}")
        print(f"CC: {EMAIL_CC}")
        return

    try:
        import win32com.client
    except ImportError:
        print("ERROR: pywin32 not installed. Run: pip install pywin32")
        print("Saving email as HTML file instead...")
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env_dates_email.html")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_body)
        print(f"Email HTML saved to: {output_file}")
        return

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = MailItem
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.To = EMAIL_TO
        mail.CC = EMAIL_CC
        mail.Send()
        print(f"Email sent successfully!")
        print(f"  Subject: {subject}")
        print(f"  To: {EMAIL_TO}")
        print(f"  CC: {EMAIL_CC}")
    except Exception as e:
        print(f"ERROR sending email: {e}")
        # Save as fallback
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env_dates_email.html")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_body)
        print(f"Email HTML saved to: {output_file}")


# =============================================================================
# STEP 6 (Optional): Publish to Dashboard
# =============================================================================

def publish_to_dashboard(dashboard_reports_dir, business_dates, mior_status,
                         wss_status, ess_status, rules_engine_date):
    """Save env_dates.json to the dashboard reports directory."""
    import json

    env_dates_dir = os.path.join(dashboard_reports_dir, "EnvDates")
    os.makedirs(env_dates_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    environments = []
    for env in ENV_ORDER:
        environments.append({
            "env": env,
            "businessDate": business_dates.get(env, "N/A"),
            "miorsDate": parse_miors_date(mior_status.get(env, "")),
            "wssStatus": wss_status.get(env, "N/A"),
            "essStatus": ess_status.get(env, "N/A"),
            "assignment": ASSIGNMENTS.get(env, ""),
        })

    data = {
        "date": today,
        "timestamp": timestamp,
        "rulesEngineDate": rules_engine_date,
        "environments": environments,
    }

    # Save as latest (always overwritten)
    latest_path = os.path.join(env_dates_dir, "latest.json")
    with open(latest_path, 'w') as f:
        json.dump(data, f, indent=2)

    # Save dated copy for history
    dated_path = os.path.join(env_dates_dir, f"env_dates_{today}.json")
    with open(dated_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Published to dashboard: {latest_path}")
    print(f"History saved: {dated_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Daily Environment Check Automation")
    parser.add_argument("--skip-locust", action="store_true", help="Skip running Locust scripts, use existing .txt files")
    parser.add_argument("--skip-sql", action="store_true", help="Skip SQL queries, use existing sql_output.txt")
    parser.add_argument("--dry-run", action="store_true", help="Build email but don't send (save as HTML)")
    parser.add_argument("--publish-dashboard", action="store", metavar="DIR",
                        help="Save env_dates.json to the dashboard reports directory for web display")
    args = parser.parse_args()

    print("=" * 60)
    print(f"Daily Environment Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: Run Locust scripts
    if not args.skip_locust:
        print("\n[Step 1/5] Running Locust environment checks...")
        run_locust_scripts()
    else:
        print("\n[Step 1/5] Skipping Locust scripts (--skip-locust)")

    # Step 2: Run SQL queries
    if not args.skip_sql:
        print("[Step 2/5] Querying business dates from SQL Server...")
        business_dates = run_sql_queries()
        rules_engine_date = get_rules_engine_date()
    else:
        print("[Step 2/5] Skipping SQL queries (--skip-sql)")
        # Read from existing sql_output.txt
        business_dates = {}
        sql_output = os.path.join(BASE_DIR, "sql_output.txt")
        if os.path.exists(sql_output):
            with open(sql_output, 'r') as f:
                for line in f.readlines()[1:]:  # skip header
                    parts = line.strip().split(',', 1)
                    if len(parts) == 2:
                        business_dates[parts[0].strip()] = parts[1].strip()
        rules_engine_date = business_dates.get("UAT45", "N/A")  # fallback

    # Step 3: Read Locust output files
    print("[Step 3/5] Reading status files...")
    mior_status = read_status_file(MIOR_STATUS_FILE)
    wss_status = read_status_file(WSS_STATUS_FILE)
    ess_status = read_status_file(ESS_STATUS_FILE)
    print(f"  MIORS: {len(mior_status)} envs, WSS: {len(wss_status)} envs, ESS: {len(ess_status)} envs")

    # Step 4: Build HTML email
    print("[Step 4/5] Building HTML email...")
    html = build_html_email(business_dates, mior_status, wss_status, ess_status, rules_engine_date)

    # Step 5: Send email
    print("[Step 5/5] Sending email...")
    send_outlook_email(html, dry_run=args.dry_run)

    # Optional: Publish to dashboard
    if args.publish_dashboard:
        publish_to_dashboard(args.publish_dashboard, business_dates, mior_status,
                             wss_status, ess_status, rules_engine_date)

    print("\nDone!")


if __name__ == "__main__":
    main()
