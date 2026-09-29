"""
CASE A: Backend reference available.

Generic loader for whatever the developer placed at
config.json -> backend_reference_path. Supports two conventions
(see backend_reference/README.md):

  1. A Python file exporting a VALIDATION_RULES dict.
  2. A JSON Schema / OpenAPI-style file with "properties" + "required".

Returns None (rather than raising) when no usable reference is found, so
callers (run_all.py) can decide to fall back to Case B automatically.
"""
import json
import os
import re
import importlib.util

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_config() -> dict:
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _load_python_rules(path: str) -> dict:
    spec = importlib.util.spec_from_file_location("backend_reference_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "VALIDATION_RULES"):
        raise ValueError(
            f"{path} does not define a VALIDATION_RULES dict "
            "(see backend_reference/README.md for the expected convention)."
        )
    return dict(module.VALIDATION_RULES)


def _json_schema_field_to_rule(name: str, schema: dict, required_names: set) -> dict:
    """Translate one JSON-Schema 'properties' entry into our internal rule shape."""
    json_type = schema.get("type", "string")
    fmt = schema.get("format", "")

    if json_type in ("integer", "number"):
        internal_type = "number"
    elif fmt == "email" or "email" in name.lower():
        internal_type = "email"
    elif "password" in name.lower():
        internal_type = "password"
    else:
        internal_type = "text"

    rule = {"type": internal_type, "required": name in required_names}
    if json_type in ("integer", "number"):
        if "minimum" in schema:
            rule["min"] = schema["minimum"]
        if "maximum" in schema:
            rule["max"] = schema["maximum"]
    else:
        if "minLength" in schema:
            rule["min_len"] = schema["minLength"]
        if "maxLength" in schema:
            rule["max_len"] = schema["maxLength"]
    if "pattern" in schema:
        rule["pattern"] = schema["pattern"]
    return rule


def _load_json_schema_rules(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)
    properties = schema.get("properties")
    if not properties:
        raise ValueError(
            f"{path} has no top-level 'properties' object "
            "(see backend_reference/README.md for the expected JSON Schema shape)."
        )
    required_names = set(schema.get("required", []))
    return {
        name: _json_schema_field_to_rule(name, field_schema, required_names)
        for name, field_schema in properties.items()
    }


def get_backend_rules():
    """Returns {"source": ..., "rules": {...}} or None if unavailable/invalid."""
    config = load_config()
    ref = config.get("backend_reference_path")
    if not ref:
        print("[parse_backend] No backend_reference_path set in config.json.")
        return None

    ref_path = os.path.join(ROOT, ref) if not os.path.isabs(ref) else ref
    if not os.path.exists(ref_path):
        print(f"[parse_backend] Reference file not found: {ref_path}")
        return None

    try:
        if ref_path.endswith(".py"):
            rules = _load_python_rules(ref_path)
        elif ref_path.endswith(".json"):
            rules = _load_json_schema_rules(ref_path)
        else:
            print(f"[parse_backend] Unsupported reference file type: {ref_path} "
                  "(expected .py or .json -- see backend_reference/README.md).")
            return None
    except Exception as e:
        print(f"[parse_backend] Failed to parse {ref_path}: {e}")
        return None

    return {"source": "backend_reference", "reference_path": ref, "rules": rules}


if __name__ == "__main__":
    data = get_backend_rules()
    out_path = os.path.join(ROOT, "results", "backend_rules.json")
    if data is None:
        print("[parse_backend] No usable backend reference -- caller should fall back to Case B.")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Parsed {len(data['rules'])} rules from {data['reference_path']} -> {out_path}")
