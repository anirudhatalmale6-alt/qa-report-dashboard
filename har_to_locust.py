"""
HAR to Locust Converter
-----------------------
Converts a HAR file into a Locust script matching the WSS/ESS framework pattern.
Filters out static assets and generates clean Locust requests with:
- Cookie handling (JSESSIONID, SECONDARYSESSIONID)
- Struts TOKEN extraction
- catch_response pattern
- Sequential task naming

Usage:
    python har_to_locust.py recording.har
    python har_to_locust.py recording.har --output my_script.py --name MyTestScript
    python har_to_locust.py recording.har --base-url https://ors-uat42.state.mi.us
"""
import json
import sys
import os
import argparse
from urllib.parse import urlparse, parse_qs, unquote


# Static asset extensions to skip
SKIP_EXTENSIONS = {
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.map', '.webp', '.bmp'
}

# Domains to skip entirely
SKIP_DOMAINS = {
    'www.google-analytics.com', 'analytics.google.com',
    'www.googletagmanager.com', 'fonts.googleapis.com',
    'fonts.gstatic.com', 'cdn.jsdelivr.net',
    'www.gstatic.com', 'accounts.google.com',
}


def parse_har(har_path: str) -> list[dict]:
    """Parse HAR file and extract relevant HTTP requests."""
    with open(har_path, 'r', encoding='utf-8', errors='ignore') as f:
        har = json.load(f)

    requests = []
    for entry in har['log']['entries']:
        req = entry['request']
        resp = entry['response']
        url = req['url']
        parsed = urlparse(url)

        # Skip static assets
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext in SKIP_EXTENSIONS:
            continue

        # Skip tracking/analytics domains
        if parsed.hostname in SKIP_DOMAINS:
            continue

        # Skip non-document resource types
        resource_type = entry.get('_resourceType', '')
        if resource_type in ('image', 'stylesheet', 'script', 'font', 'media'):
            continue

        method = req['method']
        status = resp['status']

        # Extract path (relative to base)
        path = parsed.path
        if path.startswith('/'):
            path = path[1:]

        # Extract query params
        query_params = parse_qs(parsed.query)
        # Flatten single-value params
        query_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

        # Extract POST data
        post_data = {}
        if method == 'POST' and req.get('postData'):
            pd = req['postData']
            if pd.get('params'):
                post_data = {p['name']: p.get('value', '') for p in pd['params']}
            elif pd.get('text'):
                # Try to parse as form data
                for pair in pd['text'].split('&'):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        post_data[unquote(k)] = unquote(v)

        # Extract cookies
        cookies = {}
        for cookie in req.get('cookies', []):
            cookies[cookie['name']] = cookie['value']

        # Check response for useful text (first 500 chars)
        resp_text = ''
        if resp.get('content', {}).get('text'):
            resp_text = resp['content']['text'][:2000]

        requests.append({
            'method': method,
            'url': url,
            'path': path,
            'query_params': query_params,
            'post_data': post_data,
            'cookies': cookies,
            'status': status,
            'response_preview': resp_text,
            'base_url': f"{parsed.scheme}://{parsed.hostname}",
            'resource_type': resource_type,
        })

    return requests


def detect_page_markers(resp_text: str) -> str:
    """Try to find a page title or identifier in the response."""
    import re
    # Look for <title> tag
    title = re.search(r'<title>(.*?)</title>', resp_text, re.IGNORECASE)
    if title:
        return title.group(1).strip()
    # Look for common heading patterns
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', resp_text, re.IGNORECASE)
    if h1:
        return h1.group(1).strip()[:50]
    return ""


def has_struts_token(post_data: dict) -> bool:
    """Check if request contains a Struts token."""
    return any('TOKEN' in k for k in post_data.keys())


def generate_locust_script(requests: list[dict], script_name: str, base_url: str = "") -> str:
    """Generate a Locust script from parsed HAR requests."""

    if not base_url and requests:
        base_url = requests[0]['base_url']

    lines = []

    # Header
    lines.append(f"'''")
    lines.append(f"Script: {script_name}.py")
    lines.append(f"Generated from HAR file using har_to_locust.py")
    lines.append(f"Base URL: {base_url}")
    lines.append(f"Total requests captured: {len(requests)}")
    lines.append(f"'''")
    lines.append("")

    # Imports
    lines.append("from locust import HttpUser, task, between, SequentialTaskSet")
    lines.append("import urllib3, re, time, logging")
    lines.append("import libs.lib_ResponseCheck as rc")
    lines.append("from libs.constants import *")
    lines.append("from data.{data_module} import {data_variable}  # UPDATE: your test data import")
    lines.append("from core.data_pool import DataPool")
    lines.append("")

    # Logging
    lines.append(f"logger = logging.getLogger('{script_name}')")
    lines.append("logger.setLevel(logging.INFO)")
    lines.append(f"fh = logging.FileHandler('logs/{script_name}.log', mode='a')")
    lines.append("fh.setLevel(logging.INFO)")
    lines.append("logger.addHandler(fh)")
    lines.append("")

    # Class
    lines.append(f"class {script_name}_TaskSet(SequentialTaskSet):")
    lines.append("")
    lines.append("    def __init__(self, parent):")
    lines.append("        super().__init__(parent)")
    lines.append('        self.jsessionid = ""')
    lines.append('        self.secondary_sessionid = ""')
    lines.append('        self.TOKEN = ""')
    lines.append("")
    lines.append("    def on_start(self):")
    lines.append('        self.userId = ""')
    lines.append("        self.password = WSSPASSWORD")
    lines.append("")

    # Task method
    lines.append("    @task")
    lines.append("    def run_flow(self):")
    lines.append("        # UPDATE: Add your user data iteration logic here")
    lines.append("        launchURL(self)")
    lines.append("        login(self)")
    lines.append(f"        main_flow(self)")
    lines.append("        logout(self)")
    lines.append("")

    # launchURL
    lines.append("")
    lines.append("def launchURL(self):")
    lines.append("    self.client.cookies.clear()")
    lines.append('    resp = self.client.get("wss/security/login.do?method=showLogin", name="0_Launch")')
    lines.append('    self.jsessionid = resp.cookies["JSESSIONID"]')
    lines.append("")

    # login
    lines.append("")
    lines.append("def login(self):")
    lines.append('    with self.client.post(')
    lines.append('            "wss/security/submitLogin.do?method=memberLogin&menuId=default&linkId=default",')
    lines.append('            name="0_Login",')
    lines.append('            data={"userId": self.userId, "password": self.password},')
    lines.append('            cookies={"JSESSIONID": self.jsessionid},')
    lines.append('            catch_response=True) as resp:')
    lines.append('        if rc.StatusCode200(resp):')
    lines.append('            if "Account Summary" in resp.text:')
    lines.append('                resp.success()')
    lines.append('            else:')
    lines.append('                resp.failure(f"{self.userId} login failed")')
    lines.append('                self.interrupt(reschedule=False)')
    lines.append('            self.secondary_sessionid = resp.cookies.get("SECONDARYSESSIONID", "")')
    lines.append(r"            re1 = re.search(r'org\.apache\.struts\.taglib\.html\.TOKEN\"\s*value=\"(.*?)\">', resp.text)")
    lines.append('            if re1:')
    lines.append('                self.TOKEN = re1.group(1)')
    lines.append("")

    # Main flow from HAR
    lines.append("")
    lines.append("def main_flow(self):")

    # Filter to only document/XHR requests, skip login/launch/logout
    flow_requests = []
    for req in requests:
        path_lower = req['path'].lower()
        # Skip login, logout, and static
        if any(skip in path_lower for skip in ['login.do', 'submitlogin.do', 'logout.do', 'showlogin']):
            continue
        if req['resource_type'] in ('xhr', 'fetch') and 'google' in req['url']:
            continue
        if req['method'] in ('GET', 'POST') and '.do' in req['path']:
            flow_requests.append(req)

    for idx, req in enumerate(flow_requests, 1):
        method = req['method'].lower()
        path = req['path']

        # Build a readable name from the path
        path_parts = path.split('/')
        action = path_parts[-1].replace('.do', '') if path_parts else f"step{idx}"
        # Extract method param if present
        method_param = req['query_params'].get('method', '')
        if method_param:
            request_name = f"{idx}_{action}_{method_param}"
        else:
            request_name = f"{idx}_{action}"

        # Detect page marker from response
        page_marker = detect_page_markers(req.get('response_preview', ''))

        # Build URL with query params for GET, or separate data for POST
        if req['method'] == 'GET':
            # For GET: put params in URL
            query_str = '&'.join(f"{k}={v}" for k, v in req['query_params'].items()
                                 if k != 'org.apache.struts.taglib.html.TOKEN')
            has_token_in_url = 'org.apache.struts.taglib.html.TOKEN' in req['query_params']

            if has_token_in_url:
                if query_str:
                    url_str = f'f"{path}?{query_str}&org.apache.struts.taglib.html.TOKEN={{self.TOKEN}}"'
                else:
                    url_str = f'f"{path}?org.apache.struts.taglib.html.TOKEN={{self.TOKEN}}"'
            elif query_str:
                url_str = f'"{path}?{query_str}"'
            else:
                url_str = f'"{path}"'

            lines.append(f"    # Request {idx}: {req['method']} {action}")
            lines.append(f"    with self.client.get(")
            lines.append(f"            {url_str},")
            lines.append(f'            name="{request_name}",')
            lines.append(f'            cookies={{"JSESSIONID": self.jsessionid, "SECONDARYSESSIONID": self.secondary_sessionid}},')
            lines.append(f"            catch_response=True) as resp:")

        else:
            # POST: data goes in body
            post_items = {}
            for k, v in req['post_data'].items():
                if k == 'org.apache.struts.taglib.html.TOKEN':
                    post_items[k] = 'self.TOKEN'
                else:
                    post_items[k] = v

            # Build query string for URL
            query_str = '&'.join(f"{k}={v}" for k, v in req['query_params'].items())
            if query_str:
                url_str = f'"{path}?{query_str}"'
            else:
                url_str = f'"{path}"'

            lines.append(f"    # Request {idx}: {req['method']} {action}")
            lines.append(f"    with self.client.post(")
            lines.append(f"            {url_str},")
            lines.append(f'            name="{request_name}",')
            lines.append(f'            cookies={{"JSESSIONID": self.jsessionid, "SECONDARYSESSIONID": self.secondary_sessionid}},')

            # Format post data
            lines.append(f"            data={{")
            for k, v in post_items.items():
                if v == 'self.TOKEN':
                    lines.append(f'                "{k}": self.TOKEN,')
                else:
                    lines.append(f'                "{k}": "{v}",')
            lines.append(f"            }},")
            lines.append(f"            catch_response=True) as resp:")

        # Response handling
        lines.append(f"        if rc.StatusCode200(resp):")
        if page_marker:
            safe_marker = page_marker.replace("'", "\\'")[:40]
            lines.append(f"            if '{safe_marker}' in resp.text:")
            lines.append(f"                resp.success()")
            lines.append(f"            else:")
            lines.append(f'                resp.failure("{request_name} - expected page not found")')
            lines.append(f"                self.interrupt()")
        else:
            lines.append(f"            resp.success()")

        # Token extraction
        lines.append(r"        re1 = re.search(r'org\.apache\.struts\.taglib\.html\.TOKEN\"\s*value=\"(.*?)\">', resp.text)")
        lines.append(f"        if re1:")
        lines.append(f"            self.TOKEN = re1.group(1)")
        lines.append("")

    # Logout
    lines.append("")
    lines.append("def logout(self):")
    lines.append('    with self.client.post(')
    lines.append('            "wss/security/logout.do?method=showLogout&menuId=default&linkId=default",')
    lines.append('            name="99_Logout",')
    lines.append('            cookies={"JSESSIONID": self.jsessionid},')
    lines.append('            catch_response=True) as resp:')
    lines.append('        if rc.StatusCode200(resp):')
    lines.append('            resp.success()')
    lines.append("")

    # HttpUser class
    lines.append("")
    lines.append(f"class {script_name}_User(HttpUser):")
    lines.append("    urllib3.disable_warnings()")
    lines.append("    wait_time = between(1, 3)")
    lines.append("")
    lines.append("    def on_start(self):")
    lines.append("        self.client.verify = False")
    lines.append("")
    lines.append(f"    tasks = [{script_name}_TaskSet]")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Convert HAR file to Locust script")
    parser.add_argument("har_file", help="Path to HAR file")
    parser.add_argument("--output", "-o", help="Output script path (default: <name>.py)")
    parser.add_argument("--name", "-n", default="", help="Script/class name (default: derived from HAR filename)")
    parser.add_argument("--base-url", default="", help="Base URL override")
    args = parser.parse_args()

    if not os.path.exists(args.har_file):
        print(f"Error: HAR file not found: {args.har_file}")
        sys.exit(1)

    # Derive name from filename
    name = args.name or os.path.splitext(os.path.basename(args.har_file))[0]
    name = name.replace('-', '_').replace(' ', '_')

    print(f"Parsing HAR file: {args.har_file}")
    requests = parse_har(args.har_file)
    print(f"Found {len(requests)} requests (after filtering static assets)")

    # Show summary of requests
    for i, req in enumerate(requests, 1):
        marker = detect_page_markers(req.get('response_preview', ''))
        marker_str = f" -> {marker}" if marker else ""
        print(f"  {i}. {req['method']} {req['path'][:80]}{marker_str}")

    script = generate_locust_script(requests, name, args.base_url)

    output_path = args.output or f"{name}.py"
    with open(output_path, 'w') as f:
        f.write(script)

    print(f"\nLocust script generated: {output_path}")
    print(f"\nIMPORTANT - Review and update:")
    print(f"  1. Data import line (from data.xxx import yyy)")
    print(f"  2. User iteration logic in run_flow()")
    print(f"  3. Page validation text in each request")
    print(f"  4. Any dynamic values that need extraction from responses")


if __name__ == "__main__":
    main()
