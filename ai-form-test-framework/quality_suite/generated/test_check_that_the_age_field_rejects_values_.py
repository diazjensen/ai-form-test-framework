"""Generated skeleton -- review before trusting.
Prompt  : check that the age field rejects values under 18
Written by: template (no LLM available)
"""
import pytest
from playwright.sync_api import Page, expect
from data_factory import register_payload


@pytest.mark.description(
    intent='check that the age field rejects values under 18',
    fields=['age'],
    expected="TODO: describe the expected outcome",
)
def test_check_that_the_age_field_rejects_values_(page: Page, base_url):
    """check that the age field rejects values under 18"""
    page.goto(base_url)
    data = register_payload()  # TODO: override the field(s) under test
    for k, v in data.items():
        page.fill(f"input[name='{k}']", v)
    page.click("button[type='submit']")
    expect(page.locator("#result")).not_to_be_empty()  # TODO: replace with the real assertion

