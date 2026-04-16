"""
ADA Tab-Focus Validator
-----------------------
Tests that when a required field is left empty and Tab is pressed:
1. An error message appears
2. Focus stays on the same field (doesn't jump to next)
3. Proper aria attributes exist (aria-describedby, aria-invalid, role="alert")

Can run against:
  - Live pages (with Playwright, needs login)
  - Saved HTML files (static aria/attribute check only, no focus test)

Usage (live testing):
    python ada_focus_validator.py --mode live --url https://orsuatext7.state.mi.us:1175/wss/

Usage (HTML file check):
    python ada_focus_validator.py --mode html --folder saved_html_pages/

Usage (from list of URLs):
    python ada_focus_validator.py --mode live --url-file page_urls.txt
"""
import os
import sys
import csv
import json
import logging
import argparse
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@dataclass
class FieldResult:
    page: str
    field_id: str
    field_name: str
    field_label: str
    field_type: str
    is_required: bool
    has_error_span: bool
    has_aria_describedby: bool
    aria_describedby_target: str
    has_aria_invalid: bool
    error_has_role_alert: bool
    focus_stayed: str  # "PASS", "FAIL", "N/A" (for HTML-only mode)
    error_message: str
    status: str  # "PASS", "FAIL", "WARN", "SKIP"
    notes: str


# ============================================================
# HTML-only validation (static analysis of saved HTML files)
# ============================================================
def validate_html_file(html_path: str) -> list[FieldResult]:
    """Validate ADA attributes in a saved HTML file."""
    from lxml import html as lxml_html

    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    tree = lxml_html.fromstring(content)
    page_name = os.path.basename(html_path)
    results = []

    # Find all form input fields
    fields = tree.xpath(
        '//input[@type="text" or @type="password" or @type="email" or @type="tel" or not(@type)]'
        ' | //select | //textarea'
    )

    for field in fields:
        field_id = field.get("id", "")
        field_name = field.get("name", "")
        field_type = field.tag if field.tag != "input" else field.get("type", "text")

        if not field_id and not field_name:
            continue

        # Skip hidden fields
        if field.get("type") == "hidden":
            continue

        # Find label
        label_text = ""
        if field_id:
            labels = tree.xpath(f'//label[@for="{field_id}"]')
            if labels:
                label_text = labels[0].text_content().strip()

        # Check if required (by label * or attribute)
        is_required = (
            "required" in (field.get("required", "") or field.get("aria-required", "")).lower()
            or label_text.startswith("*")
        )

        # Check aria-describedby
        aria_describedby = field.get("aria-describedby", "").strip()
        has_aria_describedby = bool(aria_describedby)
        describedby_target = ""
        error_message = ""
        error_has_role_alert = False

        if aria_describedby:
            target_el = tree.xpath(f'//*[@id="{aria_describedby}"]')
            if target_el:
                describedby_target = aria_describedby
                error_message = target_el[0].text_content().strip()[:200]
                error_has_role_alert = target_el[0].get("role", "") == "alert"

        # Check aria-invalid
        has_aria_invalid = field.get("aria-invalid", "").lower() == "true"

        # Check for error span near the field
        has_error_span = False
        # Look for error-{id} pattern
        if field_id:
            error_els = tree.xpath(f'//*[@id="error-{field_id}"]')
            if error_els:
                has_error_span = True
                if not error_message:
                    error_message = error_els[0].text_content().strip()[:200]
                if not error_has_role_alert:
                    error_has_role_alert = error_els[0].get("role", "") == "alert"

        # Determine status
        notes = []
        status = "PASS"

        if is_required:
            if not has_aria_describedby:
                notes.append("Missing aria-describedby for required field")
                status = "FAIL"
            if has_error_span and not error_has_role_alert:
                notes.append("Error span missing role='alert' (screen reader won't announce)")
                status = "FAIL" if status != "FAIL" else status
        else:
            status = "SKIP"
            notes.append("Optional field")

        results.append(FieldResult(
            page=page_name,
            field_id=field_id,
            field_name=field_name,
            field_label=label_text,
            field_type=field_type,
            is_required=is_required,
            has_error_span=has_error_span,
            has_aria_describedby=has_aria_describedby,
            aria_describedby_target=describedby_target,
            has_aria_invalid=has_aria_invalid,
            error_has_role_alert=error_has_role_alert,
            focus_stayed="N/A",
            error_message=error_message,
            status=status,
            notes="; ".join(notes),
        ))

    return results


# ============================================================
# Live Playwright validation (tests actual tab behavior)
# ============================================================
def validate_live_page(page, page_url: str) -> list[FieldResult]:
    """Test tab-focus behavior on a live page using Playwright."""
    page_name = page_url.split("/")[-1].split("?")[0] or page_url
    results = []

    # Get all focusable input fields
    fields_info = page.evaluate("""() => {
        const fields = document.querySelectorAll(
            'input[type="text"], input[type="password"], input[type="email"], input[type="tel"], select, textarea'
        );
        return Array.from(fields).filter(f => {
            // Skip hidden fields
            const style = window.getComputedStyle(f);
            return f.type !== 'hidden' && style.display !== 'none' && style.visibility !== 'hidden';
        }).map(f => {
            // Find label
            let label = '';
            if (f.id) {
                const labelEl = document.querySelector(`label[for="${f.id}"]`);
                if (labelEl) label = labelEl.textContent.trim();
            }
            return {
                id: f.id,
                name: f.name,
                tagName: f.tagName.toLowerCase(),
                type: f.type || f.tagName.toLowerCase(),
                label: label,
                isRequired: label.startsWith('*') || f.required || f.getAttribute('aria-required') === 'true',
                ariaDescribedby: f.getAttribute('aria-describedby') || '',
                ariaInvalid: f.getAttribute('aria-invalid') || '',
            };
        });
    }""")

    for field_info in fields_info:
        field_id = field_info["id"]
        if not field_id:
            continue

        is_required = field_info["isRequired"]
        if not is_required:
            results.append(FieldResult(
                page=page_name,
                field_id=field_id,
                field_name=field_info["name"],
                field_label=field_info["label"],
                field_type=field_info["type"],
                is_required=False,
                has_error_span=False,
                has_aria_describedby=bool(field_info["ariaDescribedby"]),
                aria_describedby_target=field_info["ariaDescribedby"],
                has_aria_invalid=False,
                error_has_role_alert=False,
                focus_stayed="SKIP",
                error_message="",
                status="SKIP",
                notes="Optional field",
            ))
            continue

        # Clear the field and test tab behavior
        try:
            selector = f"#{field_id}"
            field_el = page.locator(selector)

            # Click to focus the field
            field_el.click()
            page.wait_for_timeout(500)

            # Clear any existing value
            if field_info["tagName"] == "select":
                # For selects: use keyboard to reset to first option ("-Select-")
                # Press Home to go to first option, or select empty value
                field_el.select_option(value="")
                page.wait_for_timeout(300)
                # Re-click to ensure focus is on the select
                field_el.click()
                page.wait_for_timeout(300)
            else:
                field_el.fill("")

            # Press Tab to leave the field (triggers blur validation)
            page.keyboard.press("Tab")

            # Wait for JS validation to fire
            page.wait_for_timeout(2000)

            # If no error found after first check, try clicking Save button
            # (some apps only validate on submit, not on blur)
            quick_check = page.evaluate(f"""() => {{
                const errorEl = document.getElementById('error-{field_id}');
                if (errorEl) {{
                    const style = window.getComputedStyle(errorEl);
                    return style.display !== 'none' && style.visibility !== 'hidden' && errorEl.offsetParent !== null;
                }}
                const field = document.getElementById('{field_id}');
                if (field) {{
                    const describedBy = field.getAttribute('aria-describedby');
                    if (describedBy) {{
                        const el = document.getElementById(describedBy);
                        if (el) {{
                            const st = window.getComputedStyle(el);
                            return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
                        }}
                    }}
                }}
                return false;
            }}""")

            # If still no error visible, the error might need the field to lose focus differently
            if not quick_check:
                # Try clicking somewhere neutral then check again
                try:
                    page.locator("body").click(position={"x": 1, "y": 1})
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            # Check what has focus now
            focused_id = page.evaluate("() => document.activeElement ? document.activeElement.id : ''")
            focus_stayed = focused_id == field_id

            # Check if error message appeared
            # Search multiple ways: error-{id}, aria-describedby target, nearby .error-message
            error_visible = page.evaluate(f"""() => {{
                // Method 1: Look for error-{field_id} by ID
                let errorEl = document.getElementById('error-{field_id}');

                // Method 2: Check aria-describedby target on the field
                if (!errorEl) {{
                    const field = document.getElementById('{field_id}');
                    if (field) {{
                        const describedBy = field.getAttribute('aria-describedby');
                        if (describedBy) {{
                            errorEl = document.getElementById(describedBy);
                        }}
                    }}
                }}

                // Method 3: Look for .error-message sibling/nearby
                if (!errorEl) {{
                    const field = document.getElementById('{field_id}');
                    if (field && field.parentElement) {{
                        errorEl = field.parentElement.querySelector('.error-message');
                    }}
                }}

                if (!errorEl) return {{ visible: false, text: '', hasRoleAlert: false }};
                const style = window.getComputedStyle(errorEl);
                const isVisible = style.display !== 'none' && style.visibility !== 'hidden' && errorEl.offsetParent !== null;
                return {{
                    visible: isVisible,
                    text: errorEl.textContent.trim().substring(0, 200),
                    hasRoleAlert: errorEl.getAttribute('role') === 'alert'
                }};
            }}""")

            # Check aria-invalid state after tab
            aria_state = page.evaluate(f"""() => {{
                const el = document.getElementById('{field_id}');
                return {{
                    ariaInvalid: el ? el.getAttribute('aria-invalid') : '',
                    ariaDescribedby: el ? el.getAttribute('aria-describedby') || '' : ''
                }};
            }}""")

            has_error = error_visible["visible"]
            error_msg = error_visible["text"]
            has_role_alert = error_visible["hasRoleAlert"]

            # Determine status
            notes = []
            status = "PASS"

            if has_error:
                if not focus_stayed:
                    notes.append(f"FOCUS MOVED to '{focused_id}' instead of staying on '{field_id}'")
                    status = "FAIL"
                if not has_role_alert:
                    notes.append("Error message missing role='alert'")
                    status = "FAIL"
                if aria_state["ariaInvalid"] != "true":
                    notes.append("aria-invalid not set to 'true' after validation error")
                    status = "WARN" if status == "PASS" else status
                if not aria_state["ariaDescribedby"]:
                    notes.append("Missing aria-describedby")
                    status = "FAIL"
            else:
                notes.append("No error message appeared after Tab on empty required field")
                status = "WARN"

            results.append(FieldResult(
                page=page_name,
                field_id=field_id,
                field_name=field_info["name"],
                field_label=field_info["label"],
                field_type=field_info["type"],
                is_required=True,
                has_error_span=has_error,
                has_aria_describedby=bool(aria_state["ariaDescribedby"]),
                aria_describedby_target=aria_state["ariaDescribedby"],
                has_aria_invalid=aria_state["ariaInvalid"] == "true",
                error_has_role_alert=has_role_alert,
                focus_stayed="PASS" if focus_stayed else "FAIL",
                error_message=error_msg,
                status=status,
                notes="; ".join(notes),
            ))

        except Exception as e:
            results.append(FieldResult(
                page=page_name,
                field_id=field_id,
                field_name=field_info["name"],
                field_label=field_info["label"],
                field_type=field_info["type"],
                is_required=True,
                has_error_span=False,
                has_aria_describedby=False,
                aria_describedby_target="",
                has_aria_invalid=False,
                error_has_role_alert=False,
                focus_stayed="ERROR",
                error_message="",
                status="ERROR",
                notes=str(e)[:200],
            ))

    return results


# ============================================================
# Report generation
# ============================================================
def write_report(results: list[FieldResult], output_path: str):
    """Write results to CSV."""
    if not results:
        print("No results to write.")
        return

    fieldnames = list(asdict(results[0]).keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    # Print summary
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    warned = sum(1 for r in results if r.status == "WARN")
    skipped = sum(1 for r in results if r.status == "SKIP")
    errors = sum(1 for r in results if r.status == "ERROR")

    print(f"\n{'=' * 50}")
    print(f"ADA Focus Validation Report")
    print(f"{'=' * 50}")
    print(f"Total fields checked: {total}")
    print(f"  PASS:    {passed}")
    print(f"  FAIL:    {failed}")
    print(f"  WARN:    {warned}")
    print(f"  SKIP:    {skipped} (optional fields)")
    print(f"  ERROR:   {errors}")
    print(f"\nReport saved: {output_path}")

    # Print failures
    if failed > 0:
        print(f"\n{'=' * 50}")
        print("FAILURES:")
        print(f"{'=' * 50}")
        for r in results:
            if r.status == "FAIL":
                print(f"  [{r.page}] {r.field_label or r.field_id}: {r.notes}")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="ADA Tab-Focus Validator")
    parser.add_argument("--mode", choices=["html", "live"], default="html",
                       help="'html' for saved HTML files, 'live' for Playwright testing")
    parser.add_argument("--folder", default="", help="Folder with saved HTML files (html mode)")
    parser.add_argument("--file", default="", help="Single HTML file to check (html mode)")
    parser.add_argument("--url", default="", help="Base URL for live testing")
    parser.add_argument("--url-file", default="", help="File with list of URLs to test (one per line)")
    parser.add_argument("--pages", type=int, default=0, help="Number of pages to test interactively (live mode)")
    parser.add_argument("--output", default="ada_focus_report.csv", help="Output CSV path")
    args = parser.parse_args()

    all_results = []

    if args.mode == "html":
        # Static HTML analysis
        if args.file:
            files = [args.file]
        elif args.folder:
            files = [os.path.join(args.folder, f) for f in os.listdir(args.folder)
                     if f.endswith(('.html', '.htm'))]
        else:
            print("Provide --file or --folder for html mode")
            sys.exit(1)

        print(f"Checking {len(files)} HTML file(s)...")
        for filepath in sorted(files):
            print(f"  Analyzing: {os.path.basename(filepath)}")
            results = validate_html_file(filepath)
            all_results.extend(results)
            for r in results:
                symbol = "PASS" if r.status == "PASS" else "FAIL" if r.status == "FAIL" else "SKIP"
                if r.status in ("PASS", "FAIL"):
                    print(f"    [{symbol}] {r.field_label or r.field_id}: {r.notes or 'OK'}")

    elif args.mode == "live":
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=500)
            context = browser.new_context()
            page = context.new_page()

            # Navigate to base URL for login
            base_url = args.url or "https://orsuatext7.state.mi.us:1175/wss/"
            if "/wss/" in base_url:
                login_url = base_url.split("/wss/")[0] + "/wss/"
            else:
                login_url = base_url
            page.goto(login_url)

            print("\n" + "=" * 60)
            print("  ADA FOCUS VALIDATOR - Interactive Mode")
            print("=" * 60)
            print("  1. Log in manually in the browser")
            print("  2. Navigate to the page you want to test")
            print("  3. Come back here and press ENTER")
            print("  4. Script will test all fields on that page")
            print("  5. Then navigate to next page and press ENTER again")
            print('  6. Type "done" and press ENTER when finished')
            print("=" * 60)

            page_count = 0
            num_pages = args.pages  # 0 means unlimited

            while True:
                user_input = input(f"\n>> Navigate to a page, then press ENTER to test (or type 'done' to finish): ").strip()

                if user_input.lower() == "done":
                    print("Finishing up...")
                    break

                page_count += 1
                current_url = page.url
                page_name = current_url.split("/")[-1].split("?")[0] or "unknown"
                print(f"\n  Page {page_count}: {page_name}")
                print(f"  URL: {current_url}")

                try:
                    # Wait a moment for page to be fully stable
                    page.wait_for_timeout(1000)
                    results = validate_live_page(page, current_url)
                    all_results.extend(results)

                    tested = [r for r in results if r.status in ("PASS", "FAIL", "WARN")]
                    skipped = [r for r in results if r.status == "SKIP"]
                    print(f"  Fields tested: {len(tested)}, Skipped: {len(skipped)}")

                    for r in results:
                        if r.status in ("PASS", "FAIL", "WARN"):
                            symbol = r.status
                            focus_info = f" | Focus: {r.focus_stayed}" if r.focus_stayed != "SKIP" else ""
                            print(f"    [{symbol}] {r.field_label or r.field_id}{focus_info} | {r.notes or 'OK'}")
                except Exception as e:
                    print(f"    ERROR: {e}")

                if num_pages > 0 and page_count >= num_pages:
                    print(f"\nReached {num_pages} pages. Finishing up...")
                    break

            browser.close()

    write_report(all_results, args.output)


if __name__ == "__main__":
    main()
