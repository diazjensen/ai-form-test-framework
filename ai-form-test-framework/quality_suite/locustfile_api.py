"""
API-level load test. Bypasses the UI and hits the backend form endpoints
directly, with fresh Faker-generated data per request.

    POST /api/register   (weight 3)
    POST /api/checkout   (weight 2)

~15% of requests are deliberately invalid; the server is EXPECTED to reject
those with 400, so they are reported as successes only when it does. That
makes the run measure validation-path performance too, and a wrongly
accepted invalid payload (or a 5xx) shows up as a failure.
"""
import os
import random
import sys

from faker import Faker
from locust import HttpUser, task, between

sys.path.insert(0, os.path.dirname(__file__))
from data_factory import register_payload, checkout_payload  # noqa: E402


class FormApiUser(HttpUser):
    wait_time = between(0.2, 0.8)
    host = "http://127.0.0.1:5000"

    def on_start(self):
        self.fake = Faker()

    def _post(self, path, payload, expect_invalid):
        with self.client.post(path, json=payload, catch_response=True, name=path) as resp:
            ok_status = 400 if expect_invalid else 201
            if resp.status_code == ok_status:
                resp.success()
            else:
                resp.failure(f"expected {ok_status}, got {resp.status_code}")

    @task(3)
    def register(self):
        invalid = random.random() < 0.15
        payload = register_payload(self.fake, **({"age": "5"} if invalid else {}))
        self._post("/api/register", payload, invalid)

    @task(2)
    def checkout(self):
        invalid = random.random() < 0.15
        payload = checkout_payload(self.fake, **({"card_number": "123"} if invalid else {}))
        self._post("/api/checkout", payload, invalid)
