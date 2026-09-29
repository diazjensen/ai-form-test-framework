"""
Case-agnostic feature extraction: uses Playwright to load the live form and
pull every field's DOM attributes and client-side validation hints.
This is the shared first stage for BOTH Case A (backend available) and
Case B (backend unavailable) pipelines.
"""
import json
import os
from html.parser import HTMLParser
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _load_target_url() -> str:
    try:
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            return json.load(f).get("target_url", "http://127.0.0.1:5000/")
    except FileNotFoundError:
        return "http://127.0.0.1:5000/"


TARGET_URL = _load_target_url()



class _FormParser(HTMLParser):
    """Fallback extractor used when Playwright's browser binary is not available.
    Parses the raw HTML to extract form action, method, and interactive inputs."""

    def __init__(self):
        super().__init__()
        self.fields = []
        self.labels = {}
        self.action = None
        self.method = "POST"
        self._current_label_for = None
        self._label_buffer = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            if not self.action or attrs.get("action"):
                self.action = attrs.get("action")
                if attrs.get("method"):
                    self.method = attrs.get("method").upper()
        elif tag in ("input", "textarea", "select") and attrs.get("name"):
            self.fields.append({
                "name": attrs.get("name"),
                "tag": tag,
                "type": attrs.get("type", "text" if tag != "select" else "select"),
                "required": "required" in attrs or attrs.get("aria-required") == "true",
                "min": attrs.get("min"),
                "max": attrs.get("max"),
                "minlength": attrs.get("minlength"),
                "maxlength": attrs.get("maxlength"),
                "pattern": attrs.get("pattern"),
                "placeholder": attrs.get("placeholder"),
                "label": None,
            })
        elif tag == "label" and attrs.get("for"):
            self._current_label_for = attrs["for"]
            self._label_buffer = ""

    def handle_data(self, data):
        if self._current_label_for:
            self._label_buffer += data

    def handle_endtag(self, tag):
        if tag == "label" and self._current_label_for:
            self.labels[self._current_label_for] = self._label_buffer.strip()
            self._current_label_for = None


def _extract_via_html_fallback(url: str):
    import urllib.parse
    import requests

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        html = r.text
        final_url = r.url or url
    except Exception as e:
        # Retry with SSL verification disabled if cert bundle issue on macOS
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True, verify=False)
        html = r.text
        final_url = r.url or url

    parser = _FormParser()
    parser.feed(html)
    for field in parser.fields:
        field["label"] = parser.labels.get(field["name"])

    if parser.action and parser.action.strip():
        submit_endpoint = urllib.parse.urljoin(final_url, parser.action.strip())
    else:
        import re
        m = re.search(r"""fetch\(['"]([^'"]+)['"]|axios\.(?:post|get)\(['"]([^'"]+)['"]""", html)
        if m:
            submit_endpoint = urllib.parse.urljoin(final_url, (m.group(1) or m.group(2)).strip())
        else:
            submit_endpoint = final_url

    return parser.fields, submit_endpoint, parser.method, final_url


def extract_form_features(url: str = TARGET_URL) -> dict:
    try:
        data = _extract_form_features_playwright(url)
        if data.get("fields"):
            return data
        print("[extract_dom] Playwright returned 0 fields, falling back to HTML parser.")
    except Exception as e:
        print(f"[extract_dom] Playwright extraction issue ({e}); falling back to no-browser HTML parsing.")

    fields, submit_endpoint, method, final_url = _extract_via_html_fallback(url)
    return {
        "source_url": final_url,
        "original_url": url,
        "submit_endpoint": submit_endpoint,
        "method": method,
        "extraction_mode": "html_fallback_no_browser",
        "fields": fields,
    }


def _extract_form_features_playwright(url: str) -> dict:
    import urllib.parse
    from playwright.sync_api import sync_playwright
    fields = []
    submit_endpoint = "/submit"
    method = "POST"
    final_url = url

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)

        page = browser.new_page()
        resp = page.goto(url, timeout=20000, wait_until="domcontentloaded")
        http_status = resp.status if resp else 200
        final_url = page.url

        # Detect the primary form under test (prioritize forms with the most inputs)
        forms = page.query_selector_all("form")
        best_form = None
        best_inputs = []

        for f in forms:
            inps = f.query_selector_all("input:not([type='hidden']), select, textarea")
            if len(inps) > len(best_inputs):
                best_form = f
                best_inputs = inps

        # If no form tag has inputs, search the whole page for form controls
        if not best_inputs:
            inputs_to_process = page.query_selector_all("input:not([type='hidden']), select, textarea")
            form_el = forms[0] if forms else None
        else:
            inputs_to_process = best_inputs
            form_el = best_form

        if not inputs_to_process:
            browser.close()
            raise ValueError(f"No interactive form inputs found on {url}")

        for el in inputs_to_process:
            name = el.get_attribute("name") or el.get_attribute("id")
            if not name:
                continue
            field = {
                "name": name,
                "tag": el.evaluate("e => e.tagName.toLowerCase()"),
                "type": el.get_attribute("type") or "text",
                "required": el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true",
                "min": el.get_attribute("min"),
                "max": el.get_attribute("max"),
                "minlength": el.get_attribute("minlength"),
                "maxlength": el.get_attribute("maxlength"),
                "pattern": el.get_attribute("pattern"),
                "placeholder": el.get_attribute("placeholder"),
            }
            el_id = el.get_attribute("id")
            label_text = None
            if el_id:
                label = page.query_selector(f"label[for='{el_id}']")
                if label:
                    label_text = label.inner_text().strip()
            if not label_text:
                label_text = el.get_attribute("aria-label") or el.get_attribute("placeholder")
            field["label"] = label_text
            fields.append(field)

        if form_el:
            action = form_el.get_attribute("action")
            raw_method = form_el.get_attribute("method")
            method = raw_method.upper() if raw_method else "POST"
            if action and action.strip():
                submit_endpoint = urllib.parse.urljoin(final_url, action.strip())
            else:
                try:
                    ep = page.evaluate("""() => {
                        const scripts = Array.from(document.querySelectorAll('script')).map(s => s.innerText).join('\\n');
                        const m = scripts.match(/fetch\\(['"]([^'"]+)['"]|axios\\.(?:post|get)\\(['"]([^'"]+)['"]/);
                        return m ? (m[1] || m[2]) : null;
                    }""")
                    submit_endpoint = urllib.parse.urljoin(final_url, ep.strip()) if ep else final_url
                except Exception:
                    submit_endpoint = final_url
        else:
            submit_endpoint = final_url

        browser.close()

    return {
        "source_url": final_url,
        "original_url": url,
        "submit_endpoint": submit_endpoint,
        "method": method,
        "http_status": http_status,
        "fields": fields,
    }


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else TARGET_URL
    data = extract_form_features(target)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    out_path = os.path.join(ROOT, "results", "dom_features.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Extracted {len(data['fields'])} fields from {target} -> {out_path}")
