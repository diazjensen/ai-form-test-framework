"""
API-level contract tests (unit/contract layer). These bypass the UI and hit
the backend endpoints directly, asserting the backend's own validation.
"""
import pytest
from data_factory import register_payload, checkout_payload


@pytest.mark.description(
    intent="A fully valid registration is accepted",
    fields=["full_name", "email", "age", "password", "phone"],
    expected="HTTP 201 with status 'ok'",
)
def test_register_valid_payload_created(api):
    """Register with realistic Faker data; the server should create the account."""
    r = api.post("/api/register", json=register_payload())
    assert r.status_code == 201
    assert r.json()["status"] == "ok"


@pytest.mark.parametrize("field", ["full_name", "email", "age", "password"])
@pytest.mark.description(
    intent="Every required registration field must be enforced by the backend",
    fields=["full_name", "email", "age", "password"],
    expected="HTTP 400 with an error keyed to the blank field",
)
def test_register_required_field_rejected(api, field):
    """Blank out one required field at a time and expect a field-level error."""
    r = api.post("/api/register", json=register_payload(**{field: ""}))
    assert r.status_code == 400
    assert field in r.json()["errors"]


@pytest.mark.parametrize("age,expected_status", [
    ("17", 400), ("18", 201), ("100", 201), ("101", 400),
])
@pytest.mark.description(
    intent="Age boundary values (18 and 100 inclusive) are enforced",
    fields=["age"],
    expected="17 and 101 rejected with 400; 18 and 100 accepted with 201",
)
def test_register_age_boundaries(api, age, expected_status):
    """Boundary-value analysis on the age field."""
    r = api.post("/api/register", json=register_payload(age=age))
    assert r.status_code == expected_status


@pytest.mark.description(
    intent="Malformed email addresses are rejected",
    fields=["email"],
    expected="HTTP 400 with an email error",
)
def test_register_bad_email_rejected(api):
    """An email without a domain must not pass server-side validation."""
    r = api.post("/api/register", json=register_payload(email="not-an-email"))
    assert r.status_code == 400
    assert "email" in r.json()["errors"]


@pytest.mark.description(
    intent="A valid checkout order is accepted",
    fields=["address", "country", "state", "card_number"],
    expected="HTTP 201 with 'Order placed.'",
)
def test_checkout_valid_payload_created(api):
    """Checkout with Faker data and a consistent country/state pair."""
    r = api.post("/api/checkout", json=checkout_payload(coupon=""))
    assert r.status_code == 201


@pytest.mark.description(
    intent="Dependent dropdown consistency is enforced server-side",
    fields=["country", "state"],
    expected="HTTP 400 with a state error when the state belongs to another country",
)
def test_checkout_state_must_match_country(api):
    """Kerala is not a US state; the backend must not trust the UI's dropdown."""
    r = api.post("/api/checkout", json=checkout_payload(country="US", state="Kerala"))
    assert r.status_code == 400
    assert "state" in r.json()["errors"]


@pytest.mark.description(
    intent="Card numbers must be exactly 16 digits",
    fields=["card_number"],
    expected="HTTP 400 with a card_number error",
)
def test_checkout_short_card_rejected(api):
    """A 15-digit card number is invalid."""
    r = api.post("/api/checkout", json=checkout_payload(card_number="123456789012345"))
    assert r.status_code == 400
    assert "card_number" in r.json()["errors"]
