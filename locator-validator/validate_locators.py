"""
Locator Validator Tool
=====================
Validates Playwright locators (XPath/CSS) against saved HTML pages.
Reports broken locators and suggests fixes.

Usage:
    1. Capture HTML pages: python capture_html.py (run behind VPN)
    2. Validate locators:  python validate_locators.py --html-dir html_pages/ --locator-file wss_page_locators.py

Output:
    - Console summary of PASS/FAIL for each locator
    - CSV report: locator_report.csv
    - Suggestions for broken locators
"""

import os
import re
import sys
import csv
import argparse
from pathlib import Path

try:
    from lxml import html as lxml_html
    from lxml import etree
except ImportError:
    print("ERROR: lxml is required. Install with: pip install lxml")
    sys.exit(1)


def parse_locator_file(filepath):
    """Extract all locator definitions from a Python locator class file."""
    locators = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, start=1):
        line = line.strip()
        # Skip comments, blank lines, class definition
        if not line or line.startswith("#") or line.startswith("class ") or line.startswith("pass"):
            continue
        # Match: LOCATOR_NAME = "selector" or LOCATOR_NAME = '...'
        match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*["\'](.+?)["\']$', line)
        if match:
            name = match.group(1)
            selector = match.group(2)
            locators.append({
                "name": name,
                "selector": selector,
                "line": i,
                "type": detect_selector_type(selector),
            })
    return locators


def detect_selector_type(selector):
    """Detect if selector is XPath, CSS ID, CSS class, or other CSS."""
    if selector.startswith("//") or selector.startswith("(//"):
        return "xpath"
    elif selector.startswith("#"):
        return "css_id"
    elif selector.startswith("."):
        return "css_class"
    else:
        return "css"


def load_html_files(html_dir):
    """Load all HTML files from directory, return list of (filename, parsed_tree)."""
    pages = []
    html_path = Path(html_dir)
    if not html_path.exists():
        print(f"ERROR: HTML directory not found: {html_dir}")
        sys.exit(1)

    for html_file in sorted(html_path.glob("*.html")):
        try:
            content = html_file.read_text(encoding="utf-8", errors="replace")
            tree = lxml_html.fromstring(content)
            pages.append({"name": html_file.stem, "tree": tree, "content": content})
        except Exception as e:
            print(f"WARNING: Could not parse {html_file.name}: {e}")
    return pages


def test_xpath(tree, xpath_selector):
    """Test if XPath selector matches anything in the HTML tree."""
    try:
        results = tree.xpath(xpath_selector)
        return len(results) > 0, len(results)
    except etree.XPathEvalError:
        return False, 0


def test_css(tree, css_selector):
    """Test if CSS selector matches anything in the HTML tree."""
    try:
        results = tree.cssselect(css_selector)
        return len(results) > 0, len(results)
    except Exception:
        return False, 0


def test_locator(pages, locator):
    """Test a locator against all loaded HTML pages."""
    selector = locator["selector"]
    sel_type = locator["type"]
    matches = []

    for page in pages:
        if sel_type == "xpath":
            # Handle dynamic placeholders (e.g., 'rettype', 'fullname') - skip these
            found, count = test_xpath(page["tree"], selector)
        elif sel_type in ("css_id", "css_class", "css"):
            found, count = test_css(page["tree"], selector)
        else:
            found, count = False, 0

        if found:
            matches.append({"page": page["name"], "count": count})

    return matches


def has_dynamic_placeholder(selector):
    """Check if selector contains dynamic values that get replaced at runtime."""
    # Locators like: normalize-space()='fullname' or normalize-space()='rettype'
    # These are template values replaced at runtime
    placeholders = ["fullname", "rettype", "replacevalue", "replacename"]
    for ph in placeholders:
        if ph in selector.lower():
            return True
    return False


def suggest_fix_for_xpath(pages, broken_selector):
    """Analyze HTML and suggest alternatives for a broken XPath locator."""
    suggestions = []

    # Extract key attributes from the broken selector
    name_match = re.search(r"@name='([^']+)'", broken_selector)
    id_match = re.search(r"@id='([^']+)'", broken_selector)
    class_match = re.search(r"@class='([^']+)'", broken_selector)
    contains_text = re.search(r"contains\(\.,\s*'([^']+)'\)", broken_selector)
    contains_name = re.search(r"contains\(@name,\s*'([^']+)'\)", broken_selector)
    tag_match = re.search(r"//(\w+)\[", broken_selector)

    for page in pages:
        tree = page["tree"]

        # Try to find elements with the same @name attribute
        if name_match:
            name_val = name_match.group(1)
            try:
                elements = tree.xpath(f"//*[@name='{name_val}']")
                for el in elements:
                    new_xpath = build_xpath_for_element(el)
                    if new_xpath:
                        suggestions.append({
                            "page": page["name"],
                            "reason": f"Found element with name='{name_val}'",
                            "suggestion": new_xpath,
                        })
            except Exception:
                pass

        # Try to find elements with the same @id
        if id_match:
            id_val = id_match.group(1)
            try:
                elements = tree.xpath(f"//*[@id='{id_val}']")
                for el in elements:
                    new_xpath = build_xpath_for_element(el)
                    if new_xpath:
                        suggestions.append({
                            "page": page["name"],
                            "reason": f"Found element with id='{id_val}'",
                            "suggestion": new_xpath,
                        })
            except Exception:
                pass

        # Try to find elements with text content
        if contains_text:
            text_val = contains_text.group(1)
            try:
                elements = tree.xpath(f"//*[contains(text(),'{text_val}')]")
                for el in elements[:3]:  # Limit suggestions
                    new_xpath = build_xpath_for_element(el)
                    if new_xpath:
                        suggestions.append({
                            "page": page["name"],
                            "reason": f"Found element containing text '{text_val}'",
                            "suggestion": new_xpath,
                        })
            except Exception:
                pass

        # Look for aria-label attributes (common ADA additions)
        if contains_text:
            text_val = contains_text.group(1)
            try:
                elements = tree.xpath(f"//*[@aria-label and contains(@aria-label,'{text_val}')]")
                for el in elements[:3]:
                    new_xpath = build_xpath_for_element(el)
                    if new_xpath:
                        suggestions.append({
                            "page": page["name"],
                            "reason": f"ADA: Found element with aria-label containing '{text_val}'",
                            "suggestion": new_xpath,
                        })
            except Exception:
                pass

    return suggestions[:5]  # Return top 5 suggestions


def build_xpath_for_element(element):
    """Build a robust XPath for a given lxml element."""
    tag = element.tag
    attrs = dict(element.attrib)

    # Priority: id > name > aria-label > class > text
    if "id" in attrs:
        return f"//{tag}[@id='{attrs['id']}']"
    if "name" in attrs:
        xpath = f"//{tag}[@name='{attrs['name']}'"
        if "type" in attrs:
            xpath += f" and @type='{attrs['type']}'"
        xpath += "]"
        return xpath
    if "aria-label" in attrs:
        return f"//{tag}[@aria-label='{attrs['aria-label']}']"
    if "class" in attrs and attrs["class"].strip():
        return f"//{tag}[@class='{attrs['class']}']"

    # Text-based
    text = element.text_content().strip()[:50] if element.text_content() else None
    if text:
        return f"//{tag}[contains(.,'{text}')]"

    return None


def run_validation(locator_file, html_dir, output_csv="locator_report.csv"):
    """Main validation function."""
    print("=" * 70)
    print("  Locator Validator Tool")
    print("=" * 70)
    print()

    # Parse locators
    print(f"Loading locators from: {locator_file}")
    locators = parse_locator_file(locator_file)
    print(f"  Found {len(locators)} locators")
    print()

    # Load HTML pages
    print(f"Loading HTML pages from: {html_dir}")
    pages = load_html_files(html_dir)
    print(f"  Loaded {len(pages)} pages: {', '.join(p['name'] for p in pages)}")
    print()

    if not pages:
        print("ERROR: No HTML pages found. Run capture_html.py first.")
        sys.exit(1)

    # Validate each locator
    results = []
    passed = 0
    failed = 0
    skipped = 0

    print("-" * 70)
    print(f"{'STATUS':<8} {'LOCATOR NAME':<45} {'MATCHES'}")
    print("-" * 70)

    for locator in locators:
        # Skip dynamic placeholders
        if has_dynamic_placeholder(locator["selector"]):
            status = "SKIP"
            skipped += 1
            match_info = "Dynamic placeholder (runtime value)"
            suggestions = []
        else:
            matches = test_locator(pages, locator)
            if matches:
                status = "PASS"
                passed += 1
                match_pages = [f"{m['page']}({m['count']})" for m in matches]
                match_info = ", ".join(match_pages)
                suggestions = []
            else:
                status = "FAIL"
                failed += 1
                match_info = "NOT FOUND in any page"
                suggestions = suggest_fix_for_xpath(pages, locator["selector"]) if locator["type"] == "xpath" else []

        color = "\033[92m" if status == "PASS" else "\033[91m" if status == "FAIL" else "\033[93m"
        reset = "\033[0m"
        print(f"{color}{status:<8}{reset} {locator['name']:<45} {match_info}")

        if suggestions:
            for s in suggestions[:2]:
                print(f"         -> {s['reason']}")
                print(f"            {s['suggestion']}")

        results.append({
            "name": locator["name"],
            "line": locator["line"],
            "type": locator["type"],
            "selector": locator["selector"],
            "status": status,
            "match_info": match_info,
            "suggestions": "; ".join(s["suggestion"] for s in suggestions) if suggestions else "",
        })

    # Summary
    print()
    print("=" * 70)
    print(f"  SUMMARY")
    print(f"  Total: {len(locators)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    if failed > 0:
        print(f"  {failed} locators need updating for ADA changes!")
    else:
        print(f"  All locators are valid!")
    print("=" * 70)

    # Write CSV report
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "line", "type", "selector", "status", "match_info", "suggestions"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nReport saved to: {output_csv}")

    # Write broken locators summary
    broken = [r for r in results if r["status"] == "FAIL"]
    if broken:
        broken_file = output_csv.replace(".csv", "_broken.csv")
        with open(broken_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "line", "type", "selector", "suggestions"])
            writer.writeheader()
            for r in broken:
                writer.writerow({k: r[k] for k in ["name", "line", "type", "selector", "suggestions"]})
        print(f"Broken locators saved to: {broken_file}")

    return passed, failed, skipped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Playwright locators against HTML pages")
    parser.add_argument("--locator-file", required=True, help="Path to locator Python file (e.g., wss_page_locators.py)")
    parser.add_argument("--html-dir", required=True, help="Directory containing saved HTML pages")
    parser.add_argument("--output", default="locator_report.csv", help="Output CSV report path")
    args = parser.parse_args()

    run_validation(args.locator_file, args.html_dir, args.output)
