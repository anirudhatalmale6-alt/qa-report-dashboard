"""
AI-powered Playwright locator fixer using Ollama (local LLM).

Takes broken locators + new page HTML, uses LLM to suggest updated locators.

Usage:
    # CLI mode:
    python locator_fixer.py --locator-file wss_page_locators.py --html new_page.html

    # Python API:
    from locator_fixer import fix_locators
    results = fix_locators(locators, page_html, model="llama3.1")

Requirements:
    pip install requests
    Ollama running locally: ollama serve
    Model pulled: ollama pull llama3.1
"""

import json
import requests
import argparse
import os
import sys
import time
from locator_parser import parse_locator_file, format_locators_for_llm


# Ollama API endpoint
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")


def query_ollama(prompt, model=DEFAULT_MODEL, temperature=0.1):
    """Send a prompt to Ollama and return the response."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 4096,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except requests.exceptions.ConnectionError:
        return "ERROR: Cannot connect to Ollama. Make sure 'ollama serve' is running."
    except Exception as e:
        return f"ERROR: {str(e)}"


def fix_locators_batch(locators, page_html, model=DEFAULT_MODEL, batch_size=5):
    """
    Fix a batch of locators by comparing against new page HTML.

    Args:
        locators: List of locator dicts from locator_parser
        page_html: HTML string of the updated page
        model: Ollama model name
        batch_size: How many locators to fix per LLM call

    Returns:
        List of dicts with original + suggested fix for each locator
    """
    results = []

    # Truncate HTML if too long (keep structure, remove inline styles/scripts)
    clean_html = _clean_html(page_html)

    for i in range(0, len(locators), batch_size):
        batch = locators[i : i + batch_size]
        batch_text = "\n".join(
            f'{j+1}. {loc["name"]} = "{loc["value"]}" (type: {loc["type"]})'
            for j, loc in enumerate(batch)
        )

        prompt = f"""You are an expert Playwright test automation engineer. The web application was updated for ADA WCAG 2.1 accessibility compliance. This changed HTML structure, added aria-labels, aria-roles, and modified class names.

Below are Playwright locators that are NOW BROKEN because of these changes. I also provide the NEW HTML of the page.

Your task: For each broken locator, analyze the new HTML and suggest an UPDATED locator that:
1. Targets the same element as the original
2. Uses the most robust selector strategy (prefer aria-label, role, data-testid, id over XPath position)
3. Is ADA-compliant friendly (uses accessible attributes when available)
4. Keeps the same type (XPath or CSS) unless a better option exists

BROKEN LOCATORS:
{batch_text}

NEW PAGE HTML (relevant section):
```html
{clean_html[:8000]}
```

Respond in this exact JSON format (no markdown, no explanation, just JSON):
[
  {{
    "name": "LOCATOR_NAME",
    "old": "old locator value",
    "new": "suggested new locator value",
    "type": "xpath or css",
    "confidence": "high/medium/low",
    "reason": "brief explanation of what changed"
  }}
]

If you cannot determine a fix, set confidence to "low" and new to the old value with a comment.
Respond ONLY with the JSON array, nothing else."""

        print(f"  Fixing locators {i+1}-{min(i+batch_size, len(locators))} of {len(locators)}...")
        response = query_ollama(prompt, model=model)

        # Parse JSON from response
        try:
            # Try to extract JSON from response (handle markdown code blocks)
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()
            fixes = json.loads(json_str)
            results.extend(fixes)
        except (json.JSONDecodeError, IndexError):
            # If JSON parsing fails, create placeholder results
            for loc in batch:
                results.append({
                    "name": loc["name"],
                    "old": loc["value"],
                    "new": loc["value"],
                    "type": loc["type"],
                    "confidence": "low",
                    "reason": f"LLM response could not be parsed. Raw: {response[:200]}",
                })

    return results


def fix_locator_single(locator_name, locator_value, page_html, model=DEFAULT_MODEL):
    """Fix a single locator. Returns suggested new locator."""
    clean_html = _clean_html(page_html)

    prompt = f"""You are an expert Playwright test automation engineer. A web app was updated for ADA WCAG 2.1 compliance, breaking this locator.

BROKEN LOCATOR:
  Name: {locator_name}
  Value: "{locator_value}"

NEW PAGE HTML:
```html
{clean_html[:12000]}
```

Suggest an updated locator that targets the same element. Prefer accessible selectors (aria-label, role, data-testid, id).

Respond in this exact format (nothing else):
LOCATOR: <the new locator value>
TYPE: <xpath or css>
CONFIDENCE: <high/medium/low>
REASON: <brief explanation>"""

    response = query_ollama(prompt, model=model)
    return _parse_single_response(response, locator_name, locator_value)


def _parse_single_response(response, name, old_value):
    """Parse a single locator fix response."""
    result = {
        "name": name,
        "old": old_value,
        "new": old_value,
        "type": "unknown",
        "confidence": "low",
        "reason": "Could not parse response",
    }
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("LOCATOR:"):
            result["new"] = line[8:].strip().strip('"').strip("'")
        elif line.startswith("TYPE:"):
            result["type"] = line[5:].strip().lower()
        elif line.startswith("CONFIDENCE:"):
            result["confidence"] = line[11:].strip().lower()
        elif line.startswith("REASON:"):
            result["reason"] = line[7:].strip()
    return result


def _clean_html(html):
    """Clean HTML for LLM consumption - remove noise, keep structure."""
    import re

    # Remove inline scripts
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    # Remove inline styles (keep class attributes)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    # Remove HTML comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # Collapse whitespace
    html = re.sub(r"\s+", " ", html)
    # Add newlines for readability
    html = re.sub(r">\s*<", ">\n<", html)

    return html


def generate_updated_file(original_file, fixes):
    """Generate an updated locator file with fixes applied."""
    with open(original_file, "r", encoding="utf-8") as f:
        content = f.read()

    fix_map = {fix["old"]: fix for fix in fixes if fix["confidence"] != "low"}

    for old_val, fix in fix_map.items():
        if fix["new"] != old_val:
            content = content.replace(
                f'"{old_val}"',
                f'"{fix["new"]}"  # AI-updated: {fix["reason"]}',
            )

    return content


def print_results(results):
    """Pretty-print fix results to console."""
    for r in results:
        status = "OK" if r["confidence"] == "high" else ("REVIEW" if r["confidence"] == "medium" else "SKIP")
        changed = "CHANGED" if r["old"] != r["new"] else "SAME"
        print(f"\n[{status}] {r['name']} ({changed})")
        if r["old"] != r["new"]:
            print(f"  OLD: {r['old']}")
            print(f"  NEW: {r['new']}")
        print(f"  Confidence: {r['confidence']} | {r['reason']}")


# ===========================
# CLI
# ===========================

def main():
    parser = argparse.ArgumentParser(description="AI-powered Playwright locator fixer")
    parser.add_argument("--locator-file", required=True, help="Path to *_locators.py file")
    parser.add_argument("--html", required=True, help="Path to new page HTML file")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--output", help="Output file for updated locators (optional)")
    parser.add_argument("--batch-size", type=int, default=5, help="Locators per LLM call (default: 5)")
    args = parser.parse_args()

    # Parse locators
    print(f"Parsing locators from: {args.locator_file}")
    locators = parse_locator_file(args.locator_file)
    print(f"Found {len(locators)} locators")

    # Read HTML
    print(f"Reading HTML from: {args.html}")
    with open(args.html, "r", encoding="utf-8") as f:
        page_html = f.read()

    # Fix locators
    print(f"\nUsing model: {args.model}")
    print(f"Fixing {len(locators)} locators in batches of {args.batch_size}...\n")
    start = time.time()
    results = fix_locators_batch(locators, page_html, model=args.model, batch_size=args.batch_size)
    elapsed = time.time() - start

    # Print results
    print_results(results)

    # Summary
    changed = sum(1 for r in results if r["old"] != r["new"])
    high = sum(1 for r in results if r["confidence"] == "high")
    medium = sum(1 for r in results if r["confidence"] == "medium")
    low = sum(1 for r in results if r["confidence"] == "low")
    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(results)} locators analyzed in {elapsed:.1f}s")
    print(f"  Changed: {changed} | High: {high} | Medium: {medium} | Low: {low}")

    # Write output
    if args.output:
        updated = generate_updated_file(args.locator_file, results)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"\nUpdated file written to: {args.output}")

    # Also write JSON results
    json_output = args.locator_file.replace(".py", "_fixes.json")
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Fix details saved to: {json_output}")


if __name__ == "__main__":
    main()
