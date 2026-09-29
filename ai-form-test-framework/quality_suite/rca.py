"""
AI-driven root cause analysis.

diagnose(ctx) takes the raw failure context captured by the pytest hook
(error text, stack tail, HTTP trace, browser console, test intent) and
returns a 2-sentence, human-readable diagnostic.

If an LLM is available (see llm_client.py) the context is sent as a prompt.
Otherwise a rule-based heuristic produces the same 2-sentence shape, so the
dashboard always has a diagnosis -- the provider name is stored alongside
it ("ollama" / "openai" / "heuristic") so it is always clear which one wrote it.
"""
import re
from llm_client import complete

SYSTEM = (
    "You are a senior QA engineer. Given a failed automated test, reply with "
    "EXACTLY two sentences: the first states the most likely root cause, the "
    "second states the most useful next step to fix or investigate it. "
    "No preamble, no bullet points, no code blocks."
)


def _tail(text, n):
    lines = (text or "").strip().splitlines()
    return "\n".join(lines[-n:])


def build_prompt(ctx: dict) -> str:
    return (
        f"Test: {ctx.get('name')}\n"
        f"Intent: {ctx.get('intent') or 'n/a'}\n"
        f"Expected outcome: {ctx.get('expected') or 'n/a'}\n"
        f"Target fields: {ctx.get('target_fields') or 'n/a'}\n"
        f"Error: {ctx.get('error')}\n"
        f"Stack (tail):\n{_tail(ctx.get('stack'), 12)}\n"
        f"HTTP trace: {ctx.get('http_trace') or 'none'}\n"
        f"Browser console (tail):\n{_tail(ctx.get('console_logs'), 6) or 'none'}\n"
    )


def _heuristic(ctx: dict) -> str:
    err = (ctx.get("error") or "")
    http = ctx.get("http_trace") or ""
    console = ctx.get("console_logs") or ""
    status = ctx.get("http_status")
    fields = ctx.get("target_fields") or "the target field(s)"
    expected = ctx.get("expected") or "the documented behaviour"

    if "Timeout" in err and ("locator" in err.lower() or "expect" in err.lower() or "waiting" in err.lower()):
        return (f"The page never reached the state the test waited for, which usually means a selector "
                f"changed, an element is hidden, or the request behind it failed. "
                f"Open the failure screenshot and confirm the element for {fields} is present and visible.")
    if status and status >= 500:
        return (f"The server answered with HTTP {status}, which points to an unhandled backend error "
                f"rather than a validation rule. Check the server logs for the stack trace at that request.")
    if status and 400 <= status < 500 and "AssertionError" in err:
        m = re.search(r"assert (\d+) == (\d+)", err)
        detail = f" (got {m.group(1)}, wanted {m.group(2)})" if m else ""
        return (f"The backend's validation for {fields} disagrees with the test's expectation{detail}. "
                f"Compare the rule in the backend reference with the test data, and update whichever is out of date.")
    if "pageerror" in console or "[error]" in console:
        return ("A JavaScript error was logged in the browser during the test, so the form's client-side "
                "logic likely broke before the expected result appeared. Read the console output above "
                "and fix the failing script.")
    if "differs" in err.lower() or "visual" in err.lower():
        return ("The rendered page no longer matches the approved baseline, indicating an intentional or "
                "accidental UI change. Review the diff image and either fix the regression or approve a new baseline.")
    if "AssertionError" in err:
        return (f"The observed behaviour did not match the expected outcome ({expected}). "
                f"Re-run the scenario manually with the same inputs to see which value differs.")
    return ("The test raised an unexpected error before it could verify its expected outcome. "
            "Inspect the stack trace and HTTP trace to find the first failing step.")


def diagnose(ctx: dict):
    """Returns (diagnosis_text, provider)."""
    text, provider = complete(build_prompt(ctx), system=SYSTEM, max_tokens=120)
    if text:
        return text.strip(), provider
    return _heuristic(ctx), "heuristic"
