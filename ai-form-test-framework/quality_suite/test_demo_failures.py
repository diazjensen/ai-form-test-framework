"""
Intentionally failing tests used to demonstrate failure artifact capture and
AI root-cause analysis. They are NOT collected in normal runs -- set
QS_DEMO_FAILURES=1 to include them (see conftest.py collect_ignore).
"""
import pytest
from playwright.sync_api import Page, expect
from data_factory import register_payload


@pytest.mark.description(
    intent="DEMO: expects an under-age registration to succeed (it should not)",
    fields=["age"],
    expected="Registration successful (deliberately wrong expectation)",
)
def test_demo_ui_underage_should_succeed(page: Page, base_url):
    """Bypass client validation with age=5, then wrongly expect a success banner."""
    page.goto(base_url)
    page.evaluate("document.querySelector('#regForm').noValidate = true")
    for k, v in register_payload(age="5").items():
        page.fill(f"input[name='{k}']", v)
    page.click("button[type='submit']")
    expect(page.locator("#result .ok")).to_have_text("Registration successful.", timeout=2000)


@pytest.mark.description(
    intent="DEMO: expects age 17 to be accepted by the API (it is rejected)",
    fields=["age"],
    expected="HTTP 201 (deliberately wrong expectation)",
)
def test_demo_api_age_17_should_be_created(api):
    """The backend's minimum age is 18, so this assertion fails on purpose."""
    r = api.post("/api/register", json=register_payload(age="17"))
    assert r.status_code == 201
