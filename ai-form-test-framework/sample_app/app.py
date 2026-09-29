"""
Sample target application for the AI-based Web-Form Testing Framework.

Pages
  /            registration form (server-validated, rules in backend_reference/)
  /checkout    3-step checkout wizard with dependent dropdowns + dynamic fields

JSON APIs (hit directly by Locust, bypassing the UI)
  POST /api/register
  POST /api/checkout
  GET  /api/states?country=XX
"""
from flask import Flask, request, render_template, jsonify
import re
import sys
import os

# Single source of truth: the same file a developer would hand to the
# framework as their "backend reference".
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend_reference"))
from validation_rules import VALIDATION_RULES  # noqa: E402

app = Flask(__name__)

STATES = {
    "IN": ["Kerala", "Karnataka", "Tamil Nadu"],
    "US": ["California", "Texas", "New York"],
    "GB": ["England", "Scotland", "Wales"],
}


def validate(payload: dict):
    errors = {}
    for field, rule in VALIDATION_RULES.items():
        value = str(payload.get(field) or "").strip()

        if rule["required"] and not value:
            errors[field] = f"{field} is required."
            continue
        if not value:
            continue

        if rule["type"] == "number":
            if not value.isdigit():
                errors[field] = f"{field} must be a number."
                continue
            num = int(value)
            if "min" in rule and num < rule["min"]:
                errors[field] = f"{field} must be >= {rule['min']}."
            elif "max" in rule and num > rule["max"]:
                errors[field] = f"{field} must be <= {rule['max']}."
            continue

        if "min_len" in rule and len(value) < rule["min_len"]:
            errors[field] = f"{field} must be at least {rule['min_len']} characters."
            continue
        if "max_len" in rule and len(value) > rule["max_len"]:
            errors[field] = f"{field} must be at most {rule['max_len']} characters."
            continue
        if "pattern" in rule and not re.match(rule["pattern"], value):
            errors[field] = f"{field} format is invalid."
            continue

    return errors


def validate_checkout(p: dict):
    errors = {}
    if not str(p.get("address") or "").strip():
        errors["address"] = "address is required."
    country = p.get("country")
    if country not in STATES:
        errors["country"] = "country is invalid."
    elif p.get("state") not in STATES[country]:
        errors["state"] = "state does not belong to the selected country."
    card = re.sub(r"\s+", "", str(p.get("card_number") or ""))
    if not re.fullmatch(r"\d{16}", card):
        errors["card_number"] = "card_number must be 16 digits."
    coupon = str(p.get("coupon") or "").strip()
    if coupon and not re.fullmatch(r"[A-Z0-9]{4,10}", coupon):
        errors["coupon"] = "coupon format is invalid."
    return errors


@app.route("/", methods=["GET"])
def index():
    return render_template("form.html")


@app.route("/checkout", methods=["GET"])
def checkout_page():
    return render_template("checkout.html")


@app.route("/api/states")
def api_states():
    return jsonify({"states": STATES.get(request.args.get("country"), [])})


@app.route("/submit", methods=["POST"])
def submit():
    payload = request.form.to_dict()
    errors = validate(payload)
    if errors:
        return jsonify({"status": "error", "errors": errors}), 400
    return jsonify({"status": "ok", "message": "Registration successful."}), 200


@app.route("/api/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or request.form.to_dict()
    errors = validate(payload)
    if errors:
        return jsonify({"status": "error", "errors": errors}), 400
    return jsonify({"status": "ok", "message": "Registration successful."}), 201


@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    payload = request.get_json(silent=True) or request.form.to_dict()
    errors = validate_checkout(payload)
    if errors:
        return jsonify({"status": "error", "errors": errors}), 400
    return jsonify({"status": "ok", "message": "Order placed."}), 201


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
