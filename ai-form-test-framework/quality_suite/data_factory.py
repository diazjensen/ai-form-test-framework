"""
Dynamic, realistic form data via Faker -- shared by the pytest tests and
the Locust load tests so every virtual user / test submits unique,
plausible data instead of one hard-coded payload.
"""
import random
from faker import Faker

_fake = Faker()

COUNTRY_STATES = {
    "IN": ["Kerala", "Karnataka", "Tamil Nadu"],
    "US": ["California", "Texas", "New York"],
    "GB": ["England", "Scotland", "Wales"],
}


def register_payload(fake: Faker = None, **overrides) -> dict:
    f = fake or _fake
    payload = {
        "full_name": f.name()[:50],
        "email": f.unique.email() if fake is None else f.email(),
        "age": str(random.randint(18, 100)),
        "password": f.password(length=random.randint(8, 20)),
        "phone": "9" + "".join(random.choices("0123456789", k=9)),
    }
    payload.update(overrides)
    return payload


def checkout_payload(fake: Faker = None, **overrides) -> dict:
    f = fake or _fake
    country = random.choice(list(COUNTRY_STATES))
    payload = {
        "address": f.street_address(),
        "country": country,
        "state": random.choice(COUNTRY_STATES[country]),
        "card_number": "".join(random.choices("0123456789", k=16)),
        "coupon": random.choice(["", "", "SAVE10", "WELCOME5"]),
    }
    payload.update(overrides)
    return payload
