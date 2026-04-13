"""
HTML Page Capture Script
========================
Logs into WSS on UAT75 and saves HTML from every page your tests navigate to.
Run this behind VPN. The saved HTML files are used by validate_locators.py.

Usage:
    python capture_html.py --env-name UAT75 --username <user> --password <pass>

Output:
    html_pages/ folder with one .html file per page
"""

import os
import sys
import time
import argparse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright is required. Install with: pip install playwright && python -m playwright install")
    sys.exit(1)


# ===========================
# CONFIGURATION
# ===========================

# WSS Environment URLs (from your environment.py)
ENVIRONMENTS = {
    "UAT42": "https://ors-uat42.state.mi.us",
    "UAT45": "https://orsuatext.state.mi.us:1145",
    "UAT75": "https://orsuatint.state.mi.us:1175",
}

# Pages to capture after login
# Format: (page_name, navigation_action)
# navigation_action can be:
#   - "url:/path" to navigate directly
#   - "click:selector" to click a link
#   - "current" to capture current page after login
WSS_PAGES = [
    # Login page (before login)
    ("login_page", "url:/wss/security/login.do?method=showLogin"),

    # After login - home/dashboard
    ("home_page", "current"),

    # Account Summary (clicking on a member from home)
    ("account_summary", "click://a[contains(@href,'accountSummary')]"),

    # Contact Information
    ("contact_info", "click://a[contains(.,'Contact Information')]"),

    # Member Statement
    ("member_statement", "click://a[contains(.,'Member Statement')]"),

    # Beneficiary - Pension
    ("pension_beneficiary", "click://a[contains(.,'Pension') and contains(.,'Beneficiar')]"),

    # Beneficiary - Refund
    ("refund_beneficiary", "click://a[contains(.,'Refund') and contains(.,'Beneficiar')]"),

    # Dependents
    ("dependents", "click://a[contains(.,'Dependent')]"),

    # Direct Deposit
    ("direct_deposit", "click://a[contains(.,'Direct Deposit')]"),

    # Tax Withholding
    ("tax_withholding", "click://a[contains(.,'Tax Withholding')]"),

    # Pension Payments
    ("pension_payments", "click://a[contains(.,'Pension Payment')]"),

    # Pension Payment History
    ("pension_payment_history", "click://a[contains(.,'Pension Payment History')]"),

    # Healthcare Coverage
    ("healthcare_coverage", "click://a[contains(.,'Healthcare Coverage')]"),

    # Insurance Coverage
    ("insurance_coverage", "click://a[contains(.,'Insurance Coverage')]"),

    # Message Board
    ("message_board", "click://a[contains(.,'Message Board')]"),

    # Federal 1099R
    ("federal_1099r", "click://a[contains(.,'Federal 1099R')]"),

    # Proof of Income
    ("proof_of_income", "click://a[contains(.,'Proof of Income')]"),

    # Update Address & Phone
    ("update_address", "click://a[contains(.,'Change Address')]"),

    # Estimates
    ("estimates", "click://a[contains(.,'Estimate')]"),

    # Survivor Benefits
    ("survivor_benefits", "click://a[contains(.,'survivor benefit')]"),
]


def capture_pages(env_name, username, password, member_id=None, output_dir="html_pages"):
    """Capture HTML from all WSS pages."""
    base_url = ENVIRONMENTS.get(env_name)
    if not base_url:
        print(f"ERROR: Unknown environment: {env_name}")
        print(f"Available: {', '.join(ENVIRONMENTS.keys())}")
        sys.exit(1)

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print(f"Capturing HTML pages from {env_name} ({base_url})")
    print(f"Output: {output_path.absolute()}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False so you can see what's happening
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        page = context.new_page()

        # Step 1: Navigate to login page and capture it
        login_url = f"{base_url}/wss/security/login.do?method=showLogin"
        print(f"[1] Navigating to login page: {login_url}")
        page.goto(login_url, wait_until="networkidle", timeout=30000)
        save_html(page, output_path / "login_page.html")

        # Step 2: Login
        print(f"[2] Logging in as {username}...")
        page.locator("input[name='userName']").fill(username)
        page.locator("input[name='password']").fill(password)
        page.locator("input[name='login']").click()
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        save_html(page, output_path / "home_page.html")
        print(f"    Saved: home_page.html")

        # Step 3: If member_id provided, search for the member
        if member_id:
            print(f"[3] Searching for member: {member_id}")
            # Try common search patterns - adjust selectors as needed
            search_input = page.locator("input[name='ss_nr'], input[name='searchSsn'], input[name='ssn']").first
            if search_input.is_visible():
                search_input.fill(member_id)
                page.locator("input[name='search'], input[type='submit']").first.click()
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                save_html(page, output_path / "search_results.html")

                # Click first member link
                member_link = page.locator("table a").first
                if member_link.is_visible():
                    member_link.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    save_html(page, output_path / "account_summary.html")

        # Step 4: Navigate to each page and capture HTML
        page_num = 4
        captured = 0
        failed_pages = []

        for page_name, action in WSS_PAGES:
            if page_name in ("login_page", "home_page"):
                continue  # Already captured

            try:
                if action.startswith("url:"):
                    url_path = action[4:]
                    full_url = f"{base_url}{url_path}"
                    print(f"[{page_num}] Navigating to: {page_name} ({full_url})")
                    page.goto(full_url, wait_until="networkidle", timeout=15000)

                elif action.startswith("click:"):
                    selector = action[6:]
                    print(f"[{page_num}] Clicking: {page_name} ({selector})")
                    link = page.locator(selector).first
                    if link.is_visible(timeout=5000):
                        link.click()
                        page.wait_for_load_state("networkidle")
                    else:
                        print(f"    SKIP: Link not visible on current page")
                        failed_pages.append(page_name)
                        page_num += 1
                        continue

                elif action == "current":
                    print(f"[{page_num}] Capturing current page: {page_name}")

                time.sleep(1)
                save_html(page, output_path / f"{page_name}.html")
                captured += 1
                print(f"    Saved: {page_name}.html")

                # Go back to account summary/home for next navigation
                page.go_back()
                page.wait_for_load_state("networkidle")
                time.sleep(1)

            except Exception as e:
                print(f"    ERROR: {page_name} - {e}")
                failed_pages.append(page_name)

            page_num += 1

        browser.close()

    # Summary
    print()
    print("=" * 50)
    print(f"  Captured: {captured} pages")
    if failed_pages:
        print(f"  Failed: {len(failed_pages)} pages: {', '.join(failed_pages)}")
    print(f"  Output: {output_path.absolute()}")
    print("=" * 50)
    print()
    print("Next step: Run the validator:")
    print(f"  python validate_locators.py --locator-file wss_page_locators.py --html-dir {output_dir}")


def save_html(page, filepath):
    """Save page HTML content to file."""
    html_content = page.content()
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture HTML pages from WSS for locator validation")
    parser.add_argument("--env-name", default="UAT75", help="Environment name (default: UAT75)")
    parser.add_argument("--username", required=True, help="WSS login username")
    parser.add_argument("--password", required=True, help="WSS login password")
    parser.add_argument("--member-id", help="Optional: Member SSN/ID to search and navigate to")
    parser.add_argument("--output-dir", default="html_pages", help="Output directory for HTML files")
    args = parser.parse_args()

    capture_pages(args.env_name, args.username, args.password, args.member_id, args.output_dir)
