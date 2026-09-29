"""Generated skeleton -- review before trusting.
Prompt  : check that the api rejects an email without a domain on the register endpoint
Written by: template (no LLM available)
"""
import pytest
from data_factory import register_payload, checkout_payload


@pytest.mark.description(
    intent='check that the api rejects an email without a domain on the register endpoint',
    fields=['email'],
    expected="TODO: describe the expected outcome",
)
def test_check_that_the_api_rejects_an_email_with(api):
    """check that the api rejects an email without a domain on the register endpoint"""
    r = api.post("/api/register", json=register_payload())  # TODO: choose endpoint / mutate payload
    assert r.status_code == 201  # TODO: set the expected status

