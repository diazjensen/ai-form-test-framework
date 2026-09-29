"""
AI-driven root cause analysis for failed tests.

Given the raw failure context captured by conftest.py's
pytest_runtest_makereport hook (traceback text, HTTP status if any,
test description/target field), produces a short, human-readable
2-sentence diagnostic.

Tries the LLM wrapper first; if no LLM backend is reachable, falls back
to a rule-based diagnosis using simple pattern matching over the
traceback/status -- so the dashboard always has *something* useful to
show, even fully offline.
"""
from ai_wrapper.llm_client import complete

PROMPT_TEMPLATE = """You are a QA assistant. A test failed. Explain the likely
root cause in EXACTLY 2 short sentences, plain English, for a developer.

Test: {test_name}
Target field: {target_field}
Expected outcome: {expected_outcome}
HTTP status observed: {http_status}
Error/traceback (last part): {traceback_tail}

Answer in exactly 2 sentences, no preamble."""


def _rule_based_diagnosis(context: dict) -> str:
    tb = (context.get("traceback_tail") or "").lower()
    status = context.get("http_status")
    field = context.get("target_field") or "the field under test"

    if status == 500:
        return (f"The server returned a 500 error while testing {field}, indicating an "
                f"unhandled exception in the backend rather than a validation failure. "
                f"Check the server logs around the submission for a stack trace.")
    if status == 404:
        return (f"The submit endpoint returned 404, so the request never reached the "
                f"validation logic for {field}. Verify the endpoint path in config.json "
                f"matches the live route.")
    if "assert" in tb and "200" in tb and "400" in tb:
        return (f"The test expected a successful (200) response for {field} but the "
                f"server rejected the request as invalid (400). The inferred or "
                f"configured constraint for this field is likely stricter than intended, "
                f"or the test's sample value doesn't actually satisfy it.")
    if "assert" in tb and "400" in tb:
        return (f"The test expected the server to reject an invalid value for {field} "
                f"but it was accepted instead. This suggests the backend is missing or "
                f"has looser validation than the extracted/inferred rule assumed.")
    if "timeout" in tb or "timed out" in tb:
        return (f"The test timed out waiting for a response while exercising {field}. "
                f"This points to the target application being slow, unresponsive, or not "
                f"running at the configured URL.")
    if "connectionerror" in tb or "connection refused" in tb:
        return (f"The test could not connect to the target application at all while "
                f"testing {field}. Confirm the form's server is running and reachable at "
                f"the URL in config.json.")
    return (f"The test for {field} failed; see the captured traceback for the exact "
            f"assertion that did not hold. No specific failure pattern was recognised, "
            f"so a manual look at the response body is recommended.")


def generate_diagnostic(context: dict) -> dict:
    """context keys: test_name, target_field, expected_outcome,
    http_status, traceback_tail. Returns {"text": ..., "source": "llm"|"rule_based"}."""
    prompt = PROMPT_TEMPLATE.format(
        test_name=context.get("test_name", "unknown"),
        target_field=context.get("target_field", "unknown"),
        expected_outcome=context.get("expected_outcome", "unknown"),
        http_status=context.get("http_status", "n/a"),
        traceback_tail=(context.get("traceback_tail") or "")[-600:],
    )
    llm_result = complete(prompt)
    if llm_result:
        return {"text": llm_result, "source": "llm"}
    return {"text": _rule_based_diagnosis(context), "source": "rule_based"}
