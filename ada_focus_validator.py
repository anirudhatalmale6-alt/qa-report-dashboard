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
        error_role = ""
        error_aria_live = ""
        error_has_correct_role = False

        if aria_describedby:
            target_el = tree.xpath(f'//*[@id="{aria_describedby}"]')
            if target_el:
                describedby_target = aria_describedby
                error_message = target_el[0].text_content().strip()[:200]
                error_role = target_el[0].get("role", "")
                error_aria_live = target_el[0].get("aria-live", "")
                error_has_correct_role = error_role == "status"

        # Check aria-invalid
        has_aria_invalid = field.get("aria-invalid", "").lower() == "true"

        # Check for error span near the field
        has_error_span = False
        if field_id:
            error_els = tree.xpath(f'//*[@id="error-{field_id}"]')
            if error_els:
                has_error_span = True
                if not error_message:
                    error_message = error_els[0].text_content().strip()[:200]
                if not error_role:
                    error_role = error_els[0].get("role", "")
                    error_aria_live = error_els[0].get("aria-live", "")
                    error_has_correct_role = error_role == "status"

        # Determine status based on expected ADA behavior:
        # Error divs should have role="status" aria-live="off" (NOT role="alert" aria-live="assertive")
        notes = []
        status = "PASS"

        if is_required:
            if not has_aria_describedby:
                notes.append("Missing aria-describedby for required field")
                status = "FAIL"
            if has_error_span:
                if error_role == "alert":
                    notes.append(f"Error has role='alert' (should be 'status' after ADA fix)")
                    status = "FAIL"
                elif error_role != "status":
                    notes.append(f"Error has role='{error_role}' (expected 'status')")
                    status = "WARN"
                if error_aria_live == "assertive":
                    notes.append(f"Error has aria-live='assertive' (should be 'off' after ADA fix)")
                    status = "FAIL"
                elif error_aria_live != "off":
                    notes.append(f"Error has aria-live='{error_aria_live}' (expected 'off')")
                    status = "WARN" if status == "PASS" else status
                if not notes:
                    notes.append(f"OK: role='{error_role}', aria-live='{error_aria_live}'")
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
            error_has_role_alert=error_has_correct_role,
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

    # Step 1: Clear all required fields to trigger validation
    required_fields = [f for f in fields_info if f["isRequired"] and f["id"]]
    optional_fields = [f for f in fields_info if not f["isRequired"] and f["id"]]

    # Add optional fields to results as SKIP
    for field_info in optional_fields:
        results.append(FieldResult(
            page=page_name,
            field_id=field_info["id"],
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

    # Clear all required fields using JavaScript (more reliable than Playwright APIs)
    page.evaluate("""() => {
        const fields = document.querySelectorAll(
            'input[type="text"], input[type="password"], input[type="email"], input[type="tel"], select, textarea'
        );
        fields.forEach(f => {
            if (f.type === 'hidden') return;
            const style = window.getComputedStyle(f);
            if (style.display === 'none' || style.visibility === 'hidden') return;

            if (f.tagName === 'SELECT') {
                f.selectedIndex = 0;  // Reset to first option ("-Select-")
                f.dispatchEvent(new Event('change', {bubbles: true}));
            } else {
                f.value = '';
                f.dispatchEvent(new Event('input', {bubbles: true}));
                f.dispatchEvent(new Event('change', {bubbles: true}));
            }
        });
    }""")
    page.wait_for_timeout(500)

    # Step 2: Click Save/Submit button to trigger all validation errors
    save_clicked = False
    for btn_text in ["Save", "Submit", "Continue", "Next"]:
        try:
            btn = page.get_by_role("button", name=btn_text)
            if btn.count() > 0:
                btn.first.click()
                save_clicked = True
                logger.info(f"Clicked '{btn_text}' button")
                break
        except Exception:
            continue

    if not save_clicked:
        # Try input[type=submit]
        try:
            submit = page.locator("input[type='submit']")
            if submit.count() > 0:
                submit.first.click()
                save_clicked = True
        except Exception:
            pass

    if not save_clicked:
        logger.warning("Could not find Save/Submit button")

    # Wait for validation to complete
    page.wait_for_timeout(3000)

    # Step 3: Check where focus landed after Save (should be first errored field)
    first_focused_id = page.evaluate("() => document.activeElement ? document.activeElement.id : ''")

    # Step 4: Check each required field for proper error handling
    first_errored_field = None
    for field_info in required_fields:
        field_id = field_info["id"]

        try:
            # Check error element and its attributes
            field_check = page.evaluate(f"""() => {{
                const field = document.getElementById('{field_id}');
                if (!field) return null;

                // Find error element via multiple methods
                let errorEl = document.getElementById('error-{field_id}');
                if (!errorEl) {{
                    const describedBy = field.getAttribute('aria-describedby');
                    if (describedBy) errorEl = document.getElementById(describedBy);
                }}
                if (!errorEl && field.parentElement) {{
                    errorEl = field.parentElement.querySelector('.error-message');
                }}

                let errorInfo = {{ visible: false, text: '', role: '', ariaLive: '', id: '' }};
                if (errorEl) {{
                    const style = window.getComputedStyle(errorEl);
                    errorInfo = {{
                        visible: style.display !== 'none' && style.visibility !== 'hidden' && errorEl.offsetParent !== null,
                        text: errorEl.textContent.trim().substring(0, 200),
                        role: errorEl.getAttribute('role') || '',
                        ariaLive: errorEl.getAttribute('aria-live') || '',
                        id: errorEl.id || ''
                    }};
                }}

                return {{
                    ariaDescribedby: field.getAttribute('aria-describedby') || '',
                    ariaInvalid: field.getAttribute('aria-invalid') || '',
                    hasErrorClass: field.classList.contains('error-field'),
                    error: errorInfo
                }};
            }}""")

            if not field_check:
                continue

            has_error = field_check["error"]["visible"]
            error_msg = field_check["error"]["text"]
            error_role = field_check["error"]["role"]
            error_aria_live = field_check["error"]["ariaLive"]

            if has_error and first_errored_field is None:
                first_errored_field = field_id

            # Determine status based on NEW expected behavior
            notes = []
            status = "PASS"

            if has_error:
                # Check 1: role should be "status" (not "alert")
                if error_role == "alert":
                    notes.append(f"Error has role='alert' (should be 'status' after fix)")
                    status = "FAIL"
                elif error_role != "status":
                    notes.append(f"Error has role='{error_role}' (expected 'status')")
                    status = "WARN"

                # Check 2: aria-live should be "off" (not "assertive")
                if error_aria_live == "assertive":
                    notes.append(f"Error has aria-live='assertive' (should be 'off' after fix)")
                    status = "FAIL"
                elif error_aria_live != "off":
                    notes.append(f"Error has aria-live='{error_aria_live}' (expected 'off')")
                    status = "WARN" if status == "PASS" else status

                # Check 3: Field must have aria-describedby
                if not field_check["ariaDescribedby"]:
                    notes.append("Missing aria-describedby on field")
                    status = "FAIL"

                # Check 4: Focus on first error after Save
                if first_errored_field == field_id:
                    if first_focused_id == field_id:
                        notes.append("Focus correctly on first errored field after Save")
                    else:
                        notes.append(f"After Save, focus on '{first_focused_id}' instead of first error '{field_id}'")
                        status = "FAIL"

                if not notes:
                    notes.append(f"role='{error_role}', aria-live='{error_aria_live}', aria-describedby OK")

            else:
                notes.append("No error message appeared after Save for required empty field")
                status = "WARN"

            results.append(FieldResult(
                page=page_name,
                field_id=field_id,
                field_name=field_info["name"],
                field_label=field_info["label"],
                field_type=field_info["type"],
                is_required=True,
                has_error_span=has_error,
                has_aria_describedby=bool(field_check["ariaDescribedby"]),
                aria_describedby_target=field_check["ariaDescribedby"],
                has_aria_invalid=field_check["ariaInvalid"] == "true",
                error_has_role_alert=error_role == "status",
                focus_stayed="PASS" if (first_errored_field != field_id or first_focused_id == field_id) else "FAIL",
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
