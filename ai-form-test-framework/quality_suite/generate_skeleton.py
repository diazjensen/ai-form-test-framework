"""
Prompt -> test skeleton generator.

    py generate_skeleton.py "check that the age field rejects values under 18"

With an LLM available (Ollama / OpenAI, see llm_client.py) the model writes
the test using this project's conventions. Without one, a deterministic
template picks the right layer (API / UI / dropdown / visual) from keywords
and fills in the description marker, so you still get a usable skeleton.

Output goes to quality_suite/generated/test_<slug>.py -- a starting point to
review and complete, NOT a finished, verified test. The generated header
says which provider wrote it.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from llm_client import complete  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "generated")

SYSTEM = """You write pytest test skeletons for a web-form testing framework.
Rules:
- Output ONLY Python code, no markdown fences, no explanation.
- Use pytest. For UI tests use the pytest-playwright `page` fixture and `base_url`, with `from playwright.sync_api import Page, expect`.
- For API tests use the `api` fixture: api.post("/api/register", json={...}) returns a requests.Response.
- Available endpoints: POST /api/register (fields full_name,email,age,password,phone), POST /api/checkout (address,country,state,card_number,coupon).
- Page selectors: registration form at "/" (#full_name,#email,#age,#password,#phone, button[type='submit'], #result); checkout wizard at "/checkout" (#address,#country,#state,#next1,#card_number,#next2,#placeOrder).
- Generate realistic data with `from data_factory import register_payload, checkout_payload`.
- Decorate every test with @pytest.mark.description(intent="...", fields=[...], expected="...") and give it a one-line docstring.
- Keep it to 1-3 tests. Leave `# TODO` comments where the developer must confirm details."""


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "generated"


def _fields_in(prompt):
    known = ["full_name", "name", "email", "age", "password", "phone", "address",
             "country", "state", "card", "coupon"]
    found = [k for k in known if k in prompt.lower()]
    return [("card_number" if f == "card" else "full_name" if f == "name" else f) for f in found] or ["TODO"]


def _fallback(prompt):
    p = prompt.lower()
    fields = _fields_in(prompt)
    marker = (f'@pytest.mark.description(\n    intent={prompt!r},\n    fields={fields!r},\n'
              f'    expected="TODO: describe the expected outcome",\n)')
    name = "test_" + _slug(prompt)

    if any(k in p for k in ("api", "endpoint", "payload", "status code", "backend")):
        body = ('import pytest\nfrom data_factory import register_payload, checkout_payload\n\n\n'
                f'{marker}\ndef {name}(api):\n    """{prompt}"""\n'
                '    r = api.post("/api/register", json=register_payload())  # TODO: choose endpoint / mutate payload\n'
                '    assert r.status_code == 201  # TODO: set the expected status\n')
    elif any(k in p for k in ("look", "visual", "layout", "screenshot", "appearance")):
        body = ('import pytest\nfrom playwright.sync_api import Page\nfrom test_visual import assert_matches_baseline\n\n\n'
                f'{marker}\ndef {name}(page: Page, base_url):\n    """{prompt}"""\n'
                '    page.goto(base_url)  # TODO: navigate to the page under test\n'
                f'    assert_matches_baseline(page, "{_slug(prompt)}")\n')
    elif any(k in p for k in ("dropdown", "select", "country", "state")):
        body = ('import pytest\nfrom playwright.sync_api import Page, expect\n\n\n'
                f'{marker}\ndef {name}(page: Page, base_url):\n    """{prompt}"""\n'
                '    page.goto(base_url + "/checkout")\n'
                '    page.select_option("#country", "IN")\n'
                '    expect(page.locator("#state")).to_be_enabled()  # TODO: assert the behaviour you care about\n')
    else:
        body = ('import pytest\nfrom playwright.sync_api import Page, expect\nfrom data_factory import register_payload\n\n\n'
                f'{marker}\ndef {name}(page: Page, base_url):\n    """{prompt}"""\n'
                '    page.goto(base_url)\n'
                '    data = register_payload()  # TODO: override the field(s) under test\n'
                '    for k, v in data.items():\n        page.fill(f"input[name=\'{k}\']", v)\n'
                '    page.click("button[type=\'submit\']")\n'
                '    expect(page.locator("#result")).not_to_be_empty()  # TODO: replace with the real assertion\n')
    return body


def _strip_fences(code):
    code = re.sub(r"^```(?:python)?\s*", "", code.strip())
    return re.sub(r"\s*```$", "", code)


def generate(prompt: str):
    text, provider = complete(prompt, system=SYSTEM, max_tokens=900)
    if text:
        code, provider_label = _strip_fences(text), provider
    else:
        code, provider_label = _fallback(prompt), "template (no LLM available)"

    header = (f'"""Generated skeleton -- review before trusting.\n'
              f'Prompt  : {prompt}\nWritten by: {provider_label}\n"""\n')
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"test_{_slug(prompt)}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + code + "\n")
    return path, provider_label, header + code + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: py generate_skeleton.py "describe the test you want"')
        sys.exit(1)
    out, prov, _ = generate(" ".join(sys.argv[1:]))
    print(f"Wrote {out}  (by {prov})")
