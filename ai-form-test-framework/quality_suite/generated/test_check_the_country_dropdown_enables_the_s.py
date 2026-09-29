"""Generated skeleton -- review before trusting.
Prompt  : check the country dropdown enables the state list
Written by: template (no LLM available)
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.description(
    intent='check the country dropdown enables the state list',
    fields=['country', 'state'],
    expected="TODO: describe the expected outcome",
)
def test_check_the_country_dropdown_enables_the_s(page: Page, base_url):
    """check the country dropdown enables the state list"""
    page.goto(base_url + "/checkout")
    page.select_option("#country", "IN")
    expect(page.locator("#state")).to_be_enabled()  # TODO: assert the behaviour you care about

