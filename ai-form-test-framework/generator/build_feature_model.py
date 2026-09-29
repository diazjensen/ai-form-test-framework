"""
Merges DOM features with:
  - Case A (SRS document or backend reference provided): specification-driven ground truth (confidence=1.0)
  - Case B (No SRS document provided): black-box testing conducted using the accessibility tree,
    DOM features, and response-pattern probing (with calculated confidence scores).

Outputs a unified intermediate feature model (results/feature_model_case<A|B>.json).
"""
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def load(name):
    path = os.path.join(RESULTS_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _match_ax_node(field_name: str, ax_nodes: list) -> dict:
    """Matches a form field name to its corresponding accessibility node."""
    if not ax_nodes:
        return {}
    clean_field = field_name.lower().replace("_", " ")
    for node in ax_nodes:
        name = (node.get("name") or "").lower()
        if clean_field in name or name in clean_field:
            return node
    return {}


def build(case: str) -> dict:
    dom = load("dom_features.json")
    if not dom:
        raise FileNotFoundError("dom_features.json not found in results directory.")

    model = {
        "case": case,
        "source_url": dom.get("source_url", "http://127.0.0.1:5000/"),
        "submit_endpoint": dom.get("submit_endpoint", "/submit"),
        "method": dom.get("method", "POST"),
        "fields": [],
    }

    if case == "A":
        backend_meta = load("backend_rules.json") or {}
        backend = backend_meta.get("rules", {})
        spec_source = backend_meta.get("source", "srs_specification")
        model["specification_source"] = spec_source
        model["reference_path"] = backend_meta.get("reference_path", "SRS document")

        for f in dom["fields"]:
            rule = backend.get(f["name"], {})
            model["fields"].append({
                "name": f["name"],
                "label": f.get("label"),
                "type": rule.get("type", f["type"]),
                "required": rule.get("required", f["required"]),
                "min": rule.get("min"),
                "max": rule.get("max"),
                "min_len": rule.get("min_len"),
                "max_len": rule.get("max_len"),
                "pattern": rule.get("pattern") or f.get("pattern"),
                "source": spec_source,
                "confidence": 1.0,
            })
    else:  # Case B: Black Box Testing using Accessibility Tree + DOM + Probing
        inferred_meta = load("inferred_rules.json") or {}
        inferred = inferred_meta.get("fields", {})
        ax_meta = load("accessibility_tree.json") or {}
        ax_nodes = ax_meta.get("nodes", [])

        model["specification_source"] = "black_box_accessibility_and_dom"
        model["accessibility_snapshot"] = ax_meta.get("aria_snapshot", "")

        for f in dom["fields"]:
            fname = f["name"]
            inf = inferred.get(fname, {})
            confs = inf.get("confidence", {})
            ax_node = _match_ax_node(fname, ax_nodes)

            # Cross-reference DOM, accessibility tree, and probing confidence
            ax_required = ax_node.get("required") if "required" in ax_node else None
            dom_required = f.get("required", False)
            inferred_required = inf.get("required", dom_required)
            final_required = (ax_required if ax_required is not None else (dom_required or inferred_required))

            ax_role = ax_node.get("role")
            suspected_type = inf.get("type_suspected")
            if ax_role == "spinbutton":
                resolved_type = "number"
            elif suspected_type:
                resolved_type = suspected_type
            else:
                resolved_type = f.get("type", "text")

            avg_conf = round(sum(confs.values()) / len(confs), 2) if confs else 0.5
            if ax_node:
                avg_conf = min(1.0, round(avg_conf + 0.15, 2))

            notes = inf.get("notes", [])
            if ax_node:
                notes.append(f"Mapped to accessibility role '{ax_role}' (accessible name: '{ax_node.get('name')}')")

            model["fields"].append({
                "name": fname,
                "label": f.get("label") or ax_node.get("name"),
                "accessible_role": ax_role,
                "accessible_name": ax_node.get("name"),
                "type": resolved_type,
                "required": bool(final_required),
                "min": None,
                "max": None,
                "min_len": None,
                "max_len": None,
                "pattern": f.get("pattern"),
                "source": "black_box_accessibility_tree_and_dom",
                "confidence": avg_conf,
                "notes": notes,
            })

    out_path = os.path.join(RESULTS_DIR, f"feature_model_case{case}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2)
    print(f"Built unified feature model (Case {case}, source: {model.get('specification_source')}) -> {out_path}")
    return model


if __name__ == "__main__":
    import sys
    build(sys.argv[1] if len(sys.argv) > 1 else "A")
