"""
Parses Playwright *_locators.py files to extract all locator definitions.

Extracts:
- Class-level string constants (XPath, CSS selectors)
- Static/dynamic methods that return locators
- Groups them by class name

Usage:
    from locator_parser import parse_locator_file
    locators = parse_locator_file("wss_page_locators.py")
    # Returns: [{"name": "WSS_CONTACTINFO", "value": "//form[@name=...]", "line": 3, "type": "xpath"}, ...]
"""

import re
import os


def parse_locator_file(filepath):
    """Parse a *_locators.py file and extract all locator definitions."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    locators = []
    class_name = None

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect class declaration
        class_match = re.match(r"class\s+(\w+)", stripped)
        if class_match:
            class_name = class_match.group(1)
            continue

        # Detect string constant assignment: VAR_NAME = "locator_value"
        const_match = re.match(r"(\w+)\s*=\s*[\"'](.*?)[\"']\s*$", stripped)
        if const_match:
            name = const_match.group(1)
            value = const_match.group(2)
            loc_type = detect_locator_type(value)
            locators.append({
                "name": name,
                "value": value,
                "line": i,
                "type": loc_type,
                "class": class_name,
            })
            continue

        # Detect multi-line or concatenated locator
        # e.g. VAR = "part1" \
        #            "part2"
        concat_match = re.match(r"(\w+)\s*=\s*[\"'](.*?)\\?\s*$", stripped)
        if concat_match and stripped.endswith("\\"):
            name = concat_match.group(1)
            value = concat_match.group(2)
            # Read continuation lines
            j = i
            while j < len(lines) and lines[j - 1].strip().endswith("\\"):
                j += 1
                cont_match = re.match(r"\s*[\"'](.*?)[\"']\s*\\?\s*$", lines[j - 1])
                if cont_match:
                    value += cont_match.group(1)
            loc_type = detect_locator_type(value)
            locators.append({
                "name": name,
                "value": value,
                "line": i,
                "type": loc_type,
                "class": class_name,
            })
            continue

        # Detect f-string or concatenation patterns (dynamic locators)
        fstr_match = re.match(r"(\w+)\s*=\s*f[\"'](.*?)[\"']\s*$", stripped)
        if fstr_match:
            name = fstr_match.group(1)
            value = fstr_match.group(2)
            loc_type = detect_locator_type(value)
            locators.append({
                "name": name,
                "value": value,
                "line": i,
                "type": loc_type,
                "class": class_name,
                "dynamic": True,
            })

    return locators


def detect_locator_type(value):
    """Detect whether a locator is XPath, CSS, or other."""
    if value.startswith("//") or value.startswith("(//"):
        return "xpath"
    elif value.startswith("xpath="):
        return "xpath"
    elif re.match(r"^[#.\[]", value) or ":has-text" in value or ":nth" in value:
        return "css"
    elif "text=" in value:
        return "text"
    elif re.match(r"^[a-zA-Z]", value) and ("." in value or "#" in value or "[" in value):
        return "css"
    else:
        return "unknown"


def parse_all_locator_files(directory):
    """Parse all *_locators.py files in a directory."""
    all_locators = {}
    for filename in os.listdir(directory):
        if filename.endswith("_locators.py"):
            filepath = os.path.join(directory, filename)
            locators = parse_locator_file(filepath)
            all_locators[filename] = locators
    return all_locators


def format_locators_for_llm(locators, filename=""):
    """Format locators as a readable string for LLM context."""
    lines = []
    if filename:
        lines.append(f"File: {filename}")
        lines.append("=" * 60)
    for loc in locators:
        dynamic = " (DYNAMIC)" if loc.get("dynamic") else ""
        lines.append(f"  {loc['name']} [{loc['type']}]{dynamic} = \"{loc['value']}\"")
    return "\n".join(lines)
