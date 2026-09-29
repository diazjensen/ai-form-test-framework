"""
DEVELOPER-SUPPLIED BACKEND REFERENCE (Python convention).

Drop a file like this into backend_reference/ to give the framework
ground-truth validation rules for Case A (backend available).

Convention the framework looks for: a module-level dict named
VALIDATION_RULES, keyed by form field name, where each value is a dict
describing that field's constraints. Recognised keys per field:

    type       : "text" | "email" | "number" | "password"
    required   : bool
    min_len/max_len : int   (string length bounds)
    min/max          : int  (numeric bounds)
    pattern          : str  (regex the value must match)

This is exactly what you'd extract from a real backend's validators
(Django forms.py, WTForms, Spring @Valid annotations, a Joi/Zod schema,
etc.) -- the point is to express those rules in this common shape once,
by hand or with a small adapter script, so the rest of the framework
doesn't need to know which backend framework you used.
"""

VALIDATION_RULES = {
    "full_name": {"type": "text", "required": True, "min_len": 2, "max_len": 50},
    "email": {"type": "email", "required": True,
              "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"},
    "age": {"type": "number", "required": True, "min": 18, "max": 100},
    "password": {"type": "password", "required": True, "min_len": 8, "max_len": 64},
    "phone": {"type": "text", "required": False, "pattern": r"^\+?\d{10,13}$"},
}
