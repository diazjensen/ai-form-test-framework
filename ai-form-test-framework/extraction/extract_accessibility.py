"""
Accessibility-tree extraction, used as part of black-box testing (no SRS document
provided) alongside plain DOM extraction.

Uses the Chromium accessibility tree (CDP Accessibility.getFullAXTree + aria_snapshot),
which reflects how assistive technologies and accessibility standards "see" the form:
roles, accessible names, values, and required/invalid states -- independent of raw
HTML markup, catching ARIA-only fields, semantic roles, and accessibility constraints.
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")


def extract_accessibility_tree(url: str = "http://127.0.0.1:5000/") -> dict:
    from playwright.sync_api import sync_playwright

    form_roles = {"textbox", "combobox", "checkbox", "radio", "spinbutton",
                  "searchbox", "button", "listbox"}
    nodes = []
    aria_text = ""

    with sync_playwright() as p:
        # Launch with system chrome or chromium
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)

        page = browser.new_page()
        try:
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
        except Exception:
            pass

        # 1. High-level aria snapshot if available
        try:
            if hasattr(page.locator("body"), "aria_snapshot"):
                aria_text = page.locator("body").aria_snapshot()
        except Exception:
            pass

        # 2. Rich accessibility nodes from CDP or accessibility API
        try:
            client = page.context.new_cdp_session(page)
            ax = client.send("Accessibility.getFullAXTree")
            for n in ax.get("nodes", []):
                role = (n.get("role") or {}).get("value")
                if role in form_roles:
                    props = {p.get("name"): p.get("value", {}).get("value") for p in n.get("properties", [])}
                    name = (n.get("name") or {}).get("value")
                    val = (n.get("value") or {}).get("value")
                    is_req = props.get("required", False)
                    if isinstance(is_req, str):
                        is_req = is_req.lower() == "true"
                    nodes.append({
                        "role": role,
                        "name": name,
                        "value": val,
                        "required": bool(is_req),
                        "invalid": props.get("invalid", False),
                        "description": props.get("description"),
                    })
        except Exception as e:
            # Fallback: query interactive form controls via DOM ARIA evaluation
            print(f"[extract_accessibility] CDP accessibility tree error ({e}), using DOM evaluator fallback")
            elements = page.query_selector_all("input, select, textarea, button")
            for el in elements:
                name = el.get_attribute("name") or el.get_attribute("id") or el.get_attribute("aria-label")
                role = el.get_attribute("role") or el.evaluate("e => e.type || e.tagName.toLowerCase()")
                req = el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true"
                nodes.append({
                    "role": role,
                    "name": name,
                    "value": el.get_attribute("value"),
                    "required": req,
                    "invalid": el.get_attribute("aria-invalid") or False,
                    "description": el.get_attribute("aria-describedby"),
                })

        browser.close()

    return {
        "source": "accessibility_tree",
        "url": url,
        "aria_snapshot": aria_text,
        "nodes": nodes,
    }


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000/"
    data = extract_accessibility_tree(url)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    out_path = os.path.join(ROOT, "results", "accessibility_tree.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Extracted {len(data['nodes'])} accessible form nodes -> {out_path}")
