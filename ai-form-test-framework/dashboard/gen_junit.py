"""
Converts playwright_results.json into a JUnit-style XML file so this
framework's functional-test results can be consumed by any CI system
(GitHub Actions, Jenkins, GitLab CI, Azure Pipelines) that understands
the JUnit format -- the same format pytest's own --junitxml produces,
which this project also emits directly for the contract tests.

This closes the "no CI/CD integration story" gap: a pipeline can run
run_all.py headlessly and point its test-reporting step at
results/junit/*.xml with zero framework-specific plugins.
"""
import json
import os
from xml.sax.saxutils import escape

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
JUNIT_DIR = os.path.join(RESULTS_DIR, "junit")


def build_junit_xml(results: list, suite_name: str = "playwright_functional") -> str:
    total = len(results)
    failures = sum(1 for r in results if not r["passed"])
    cases = []
    for r in results:
        name = escape(r["test"])
        if r["passed"]:
            cases.append(f'  <testcase classname="{suite_name}" name="{name}" />')
        else:
            detail = escape(r.get("detail", "") or "assertion failed")
            shot = f' (screenshot: {escape(r["screenshot"])})' if r.get("screenshot") else ""
            cases.append(
                f'  <testcase classname="{suite_name}" name="{name}">\n'
                f'    <failure message="{detail}{shot}"></failure>\n'
                f'  </testcase>'
            )
    body = "\n".join(cases)
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="{suite_name}" tests="{total}" failures="{failures}">\n'
        f'{body}\n'
        f'</testsuite>\n'
    )


def write_playwright_junit():
    src = os.path.join(RESULTS_DIR, "playwright_results.json")
    if not os.path.exists(src):
        print("[gen_junit] No playwright_results.json found; skipping.")
        return
    with open(src, encoding="utf-8") as f:
        results = json.load(f)

    os.makedirs(JUNIT_DIR, exist_ok=True)
    out_path = os.path.join(JUNIT_DIR, "playwright.xml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_junit_xml(results))
    print(f"Wrote JUnit XML -> {out_path}")


if __name__ == "__main__":
    write_playwright_junit()
