"""
Visual regression testing.

Python Playwright has no expect(page).to_have_screenshot() (that API exists
only in the JS @playwright/test runner), so this implements the same
workflow directly:

  * first run  -> saves a baseline PNG in quality_suite/baselines/
  * later runs -> screenshots the page, diffs it against the baseline with
                  Pillow, and fails if more than MAX_DIFF_RATIO of pixels differ
  * on failure -> writes a highlighted diff image to results/visual_diffs/

To approve an intentional UI change, delete the old baseline and re-run.
"""
import io
import os

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import Page

BASELINE_DIR = os.path.join(os.path.dirname(__file__), "baselines")
DIFF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results", "visual_diffs"))
MAX_DIFF_RATIO = 0.005  # 0.5% of pixels may differ (anti-aliasing tolerance)
PIXEL_TOLERANCE = 12    # per-channel difference ignored as noise


def assert_matches_baseline(page: Page, name: str):
    os.makedirs(BASELINE_DIR, exist_ok=True)
    os.makedirs(DIFF_DIR, exist_ok=True)

    page.add_style_tag(content="*{animation:none!important;transition:none!important;caret-color:transparent!important}")
    current = Image.open(io.BytesIO(page.screenshot(full_page=True))).convert("RGB")
    baseline_path = os.path.join(BASELINE_DIR, f"{name}.png")

    if not os.path.exists(baseline_path):
        current.save(baseline_path)
        pytest.skip(f"Baseline '{name}' did not exist and was created; re-run to compare.")

    baseline = Image.open(baseline_path).convert("RGB")
    if baseline.size != current.size:
        current.save(os.path.join(DIFF_DIR, f"{name}_actual.png"))
        raise AssertionError(
            f"Visual differs: '{name}' size changed from {baseline.size} to {current.size}"
        )

    diff = ImageChops.difference(baseline, current)
    mask = diff.convert("L").point(lambda v: 255 if v > PIXEL_TOLERANCE else 0)
    changed = mask.histogram()[255]
    ratio = changed / (mask.width * mask.height)

    if ratio > MAX_DIFF_RATIO:
        highlighted = current.copy()
        highlighted.paste(Image.new("RGB", mask.size, (255, 0, 0)), mask=mask)
        highlighted.save(os.path.join(DIFF_DIR, f"{name}_diff.png"))
        current.save(os.path.join(DIFF_DIR, f"{name}_actual.png"))
        raise AssertionError(
            f"Visual differs: '{name}' has {ratio:.2%} changed pixels (limit {MAX_DIFF_RATIO:.2%})"
        )


@pytest.mark.description(
    intent="Registration form looks the same as the approved baseline",
    fields=["full_name", "email", "age", "password", "phone"],
    expected="Pixel difference under 0.5% of the approved screenshot",
)
def test_visual_registration_form(page: Page, base_url):
    """Full-page visual regression of the registration form."""
    page.goto(base_url)
    assert_matches_baseline(page, "registration_form")


@pytest.mark.description(
    intent="Checkout wizard step 1 looks the same as the approved baseline",
    fields=["address", "country", "state"],
    expected="Pixel difference under 0.5% of the approved screenshot",
)
def test_visual_checkout_step1(page: Page, base_url):
    """Full-page visual regression of the wizard's first step."""
    page.goto(base_url + "/checkout")
    assert_matches_baseline(page, "checkout_step1")


@pytest.mark.description(
    intent="Checkout wizard with a populated dependent dropdown looks correct",
    fields=["country", "state"],
    expected="Pixel difference under 0.5% of the approved screenshot",
)
def test_visual_checkout_dropdown_selected(page: Page, base_url):
    """Visual state after choosing India, which enables and fills the state list."""
    page.goto(base_url + "/checkout")
    page.select_option("#country", "IN")
    page.wait_for_selector("#state:not([disabled])")
    assert_matches_baseline(page, "checkout_country_selected")
