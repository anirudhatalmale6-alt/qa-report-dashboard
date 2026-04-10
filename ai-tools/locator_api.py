"""
Flask API server for the AI Locator Fixer.
Provides REST endpoints for the QA Dashboard web UI.

Run: python locator_api.py
Endpoint: http://localhost:5001

Requires:
    pip install flask requests
    Ollama running: ollama serve
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import tempfile

from locator_parser import parse_locator_file, parse_all_locator_files
from locator_fixer import fix_locators_batch, fix_locator_single, query_ollama, generate_updated_file

app = Flask(__name__)
CORS(app)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


@app.route("/api/ai/status", methods=["GET"])
def status():
    """Check if Ollama is running and which models are available."""
    try:
        import requests as req
        resp = req.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return jsonify({"status": "connected", "models": models})
        return jsonify({"status": "error", "message": f"Ollama returned {resp.status_code}"})
    except Exception as e:
        return jsonify({"status": "offline", "message": str(e)})


@app.route("/api/ai/parse-locators", methods=["POST"])
def parse_locators():
    """Parse locators from uploaded Python file content."""
    data = request.json
    code = data.get("code", "")
    filename = data.get("filename", "locators.py")

    # Write to temp file for parsing
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmppath = f.name

    try:
        locators = parse_locator_file(tmppath)
        return jsonify({"locators": locators, "count": len(locators)})
    finally:
        os.unlink(tmppath)


@app.route("/api/ai/fix-locators", methods=["POST"])
def fix_locators():
    """Fix broken locators using AI."""
    data = request.json
    locators = data.get("locators", [])
    page_html = data.get("html", "")
    model = data.get("model", "llama3.1")
    batch_size = data.get("batch_size", 5)

    if not locators:
        return jsonify({"error": "No locators provided"}), 400
    if not page_html:
        return jsonify({"error": "No HTML provided"}), 400

    results = fix_locators_batch(locators, page_html, model=model, batch_size=batch_size)
    return jsonify({"fixes": results})


@app.route("/api/ai/fix-single", methods=["POST"])
def fix_single():
    """Fix a single locator."""
    data = request.json
    name = data.get("name", "")
    value = data.get("value", "")
    html = data.get("html", "")
    model = data.get("model", "llama3.1")

    if not value or not html:
        return jsonify({"error": "Missing locator value or HTML"}), 400

    result = fix_locator_single(name, value, html, model=model)
    return jsonify(result)


@app.route("/api/ai/generate-file", methods=["POST"])
def generate_file():
    """Generate updated locator file with fixes applied."""
    data = request.json
    original_code = data.get("original_code", "")
    fixes = data.get("fixes", [])

    # Write original to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(original_code)
        tmppath = f.name

    try:
        updated = generate_updated_file(tmppath, fixes)
        return jsonify({"updated_code": updated})
    finally:
        os.unlink(tmppath)


@app.route("/api/ai/generate-script", methods=["POST"])
def generate_script():
    """Generate a new Playwright test script from natural language description."""
    data = request.json
    description = data.get("description", "")
    framework_context = data.get("framework_context", "")
    model = data.get("model", "llama3.1")

    if not description:
        return jsonify({"error": "No description provided"}), 400

    prompt = f"""You are an expert Playwright + pytest test automation engineer.
Generate a complete, ready-to-run Playwright test script based on the description below.

FRAMEWORK CONTEXT (existing patterns to follow):
{framework_context[:6000]}

USER DESCRIPTION:
{description}

Generate a complete Python test script that:
1. Follows the existing framework patterns (imports, page objects, Application class)
2. Uses proper Playwright selectors (prefer accessible selectors: aria-label, role, data-testid)
3. Includes allure decorations (@allure.story, @allure.description, allure.step)
4. Has proper assertions with expect()
5. Handles waits and timeouts appropriately

Respond with ONLY the Python code, no markdown fences or explanations."""

    response = query_ollama(prompt, model=model, temperature=0.2)
    # Clean up code fences if present
    code = response.strip()
    if code.startswith("```"):
        code = code.split("```")[1]
        if code.startswith("python"):
            code = code[6:]
        code = code.strip()

    return jsonify({"script": code})


if __name__ == "__main__":
    print("AI Locator Fixer API starting on http://localhost:5001")
    print("Make sure Ollama is running: ollama serve")
    print("Recommended model: ollama pull llama3.1")
    app.run(host="0.0.0.0", port=5001, debug=True)
