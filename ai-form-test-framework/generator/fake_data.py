"""
Generates realistic, randomized field values using Faker instead of
static hardcoded strings. Used by:
  - the generated Locust load test (realistic concurrent traffic, not the
    same payload replayed thousands of times)
  - the generated pytest contract tests (varied valid inputs per run,
    not the exact same fixed values every time)

Per-field-NAME generators take priority (semantic match on the field's
name/label); a per-TYPE fallback covers anything unrecognised.
"""
from faker import Faker
import random

fake = Faker()

NAME_GENERATORS = {
    "full_name": lambda: fake.name(),
    "email": lambda: fake.unique.email(),
    "age": lambda: str(random.randint(18, 100)),
    "password": lambda: fake.password(length=12, special_chars=True, digits=True,
                                        upper_case=True, lower_case=True),
    "phone": lambda: "".join(c for c in fake.msisdn())[:10],
}

TYPE_GENERATORS = {
    "email": lambda: fake.unique.email(),
    "number": lambda: str(random.randint(1, 100)),
    "password": lambda: fake.password(length=12),
    "text": lambda: fake.word().capitalize(),
}


def fake_value_for(field_name: str, field_type: str = "text") -> str:
    if field_name in NAME_GENERATORS:
        return NAME_GENERATORS[field_name]()
    if field_type in TYPE_GENERATORS:
        return TYPE_GENERATORS[field_type]()
    return fake.word()


def fake_payload(fields: list) -> dict:
    """fields: list of {"name": ..., "type": ...} dicts from the feature model."""
    return {f["name"]: fake_value_for(f["name"], f.get("type", "text")) for f in fields}
