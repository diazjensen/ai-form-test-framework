"""
Functional UI tests with Playwright: client-side validation rules,
multi-step wizard, dependent dropdowns and dynamic input fields.
"""
import pytest
from playwright.sync_api import Page, expect
from data_factory import register_payload, checkout_payload


def fill_registration(page: Page, data: dict):
    for name, value in data.items():
        page.fill(f"input[name='{name}']", value)


def validity(page: Page, selector: str, flag: str) -> bool:
    return page.eval_on_selector(selector, f"el => el.validity.{flag}")


# ---------------------------- client-side validation ----------------------
@pytest.mark.description(
    intent="Browser blocks submitting an empty registration form",
    fields=["full_name", "email", "age", "password"],
    expected="Required fields report valueMissing and no request is sent",
)
def test_client_required_fields_block_submit(page: Page, base_url):
    """Click submit with nothing filled in; native validation must stop it."""
    page.goto(base_url)
    page.click("button[type='submit']")
    assert validity(page, "#full_name", "valueMissing")
    assert validity(page, "#email", "valueMissing")
    expect(page.locator("#result")).to_have_text("")


@pytest.mark.description(
    intent="Age below the minimum is flagged in the browser",
    fields=["age"],
    expected="validity.rangeUnderflow is true for age=5",
)
def test_client_age_range_underflow(page: Page, base_url):
    """The age input declares min=18; 5 should underflow."""
    page.goto(base_url)
    page.fill("#age", "5")
    assert validity(page, "#age", "rangeUnderflow")


@pytest.mark.description(
    intent="Phone number pattern is enforced client-side",
    fields=["phone"],
    expected="validity.patternMismatch is true for 'abc'",
)
def test_client_phone_pattern_mismatch(page: Page, base_url):
    """Letters are not a valid phone number."""
    page.goto(base_url)
    page.fill("#phone", "abc")
    assert validity(page, "#phone", "patternMismatch")


@pytest.mark.description(
    intent="A valid registration succeeds end to end through the UI",
    fields=["full_name", "email", "age", "password", "phone"],
    expected="Success message 'Registration successful.' appears",
)
def test_registration_happy_path(page: Page, base_url):
    """Fill the form with Faker data, submit, and expect the success banner."""
    page.goto(base_url)
    fill_registration(page, register_payload())
    page.click("button[type='submit']")
    expect(page.locator("#result .ok")).to_have_text("Registration successful.")


@pytest.mark.description(
    intent="Server-side errors surface in the UI when client checks are bypassed",
    fields=["age"],
    expected="An error message is displayed for an out-of-range age",
)
def test_server_error_shown_when_client_validation_bypassed(page: Page, base_url):
    """Disable native validation so the request reaches the backend."""
    page.goto(base_url)
    page.evaluate("document.querySelector('#regForm').noValidate = true")
    fill_registration(page, register_payload(age="5"))
    page.click("button[type='submit']")
    expect(page.locator("#result .err")).to_contain_text("age")


# ------------------------------ multi-step wizard -------------------------
def complete_step1(page: Page, country="IN", state="Kerala", address="12 MG Road"):
    page.fill("#address", address)
    page.select_option("#country", country)
    page.select_option("#state", state)
    page.click("#next1")


@pytest.mark.description(
    intent="Wizard cannot advance from Shipping without an address",
    fields=["address"],
    expected="Step 1 stays active and shows 'Address is required.'",
)
def test_wizard_blocks_next_without_address(page: Page, base_url):
    """Press Next on an empty shipping step."""
    page.goto(base_url + "/checkout")
    page.click("#next1")
    expect(page.locator("#err_address")).to_have_text("Address is required.")
    expect(page.locator("#step1")).to_have_class("step active")


@pytest.mark.description(
    intent="Wizard completes all three steps and places an order",
    fields=["address", "country", "state", "card_number"],
    expected="'Order placed.' is displayed after confirming",
)
def test_wizard_happy_path(page: Page, base_url):
    """Shipping -> Payment -> Confirm -> Place order."""
    page.goto(base_url + "/checkout")
    complete_step1(page)
    page.fill("#card_number", "4111111111111111")
    page.click("#next2")
    expect(page.locator("#summary")).to_contain_text("12 MG Road")
    page.click("#placeOrder")
    expect(page.locator("#result .ok")).to_have_text("Order placed.")


@pytest.mark.description(
    intent="Going back in the wizard preserves entered values",
    fields=["address"],
    expected="Address input still holds the previously typed value",
)
def test_wizard_back_preserves_values(page: Page, base_url):
    """Advance to payment, go back, and check state was retained."""
    page.goto(base_url + "/checkout")
    complete_step1(page, address="Preserved Street 9")
    page.click("#back2")
    expect(page.locator("#address")).to_have_value("Preserved Street 9")


@pytest.mark.description(
    intent="Payment step rejects a short card number",
    fields=["card_number"],
    expected="'Card number must be 16 digits.' and the wizard stays on step 2",
)
def test_wizard_rejects_short_card(page: Page, base_url):
    """Type 12 digits and try to continue."""
    page.goto(base_url + "/checkout")
    complete_step1(page)
    page.fill("#card_number", "123456789012")
    page.click("#next2")
    expect(page.locator("#err_card")).to_have_text("Card number must be 16 digits.")


# ---------------------------- dependent dropdowns -------------------------
@pytest.mark.description(
    intent="State options depend on the selected country",
    fields=["country", "state"],
    expected="India lists Kerala; switching to US replaces it with California",
)
def test_dependent_dropdown_updates_with_country(page: Page, base_url):
    """State list must be disabled first, then populated and refreshed."""
    page.goto(base_url + "/checkout")
    expect(page.locator("#state")).to_be_disabled()

    page.select_option("#country", "IN")
    expect(page.locator("#state")).to_be_enabled()
    expect(page.locator("#state option", has_text="Kerala")).to_have_count(1)

    page.select_option("#country", "US")
    expect(page.locator("#state option", has_text="California")).to_have_count(1)
    expect(page.locator("#state option", has_text="Kerala")).to_have_count(0)


@pytest.mark.description(
    intent="Clearing the country disables and resets the state dropdown",
    fields=["country", "state"],
    expected="State dropdown becomes disabled again",
)
def test_dependent_dropdown_resets(page: Page, base_url):
    """Select a country then unselect it."""
    page.goto(base_url + "/checkout")
    page.select_option("#country", "GB")
    expect(page.locator("#state")).to_be_enabled()
    page.select_option("#country", "")
    expect(page.locator("#state")).to_be_disabled()


# ------------------------------ dynamic fields ----------------------------
@pytest.mark.description(
    intent="Coupon field is hidden until requested",
    fields=["coupon"],
    expected="Hidden initially; visible after clicking '+ Add coupon'",
)
def test_dynamic_coupon_field_appears(page: Page, base_url):
    """Dynamic input revealed by a button click."""
    page.goto(base_url + "/checkout")
    complete_step1(page)
    expect(page.locator("#coupon")).to_be_hidden()
    page.click("#addCoupon")
    expect(page.locator("#coupon")).to_be_visible()


@pytest.mark.description(
    intent="Invalid coupon codes are rejected by the server",
    fields=["coupon"],
    expected="An error mentioning 'coupon' is displayed on order placement",
)
def test_invalid_coupon_rejected(page: Page, base_url):
    """Lower-case/symbol coupons violate the [A-Z0-9]{4,10} rule."""
    page.goto(base_url + "/checkout")
    complete_step1(page)
    page.click("#addCoupon")
    page.fill("#coupon", "bad!")
    page.fill("#card_number", "4111111111111111")
    page.click("#next2")
    page.click("#placeOrder")
    expect(page.locator("#result .err")).to_contain_text("coupon")
