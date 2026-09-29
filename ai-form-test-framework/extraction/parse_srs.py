"""
Lightweight SRS parser. Scans Software Requirements Specification documents
(.txt or .md) for form field constraints and translates them into the unified
feature model format.

Supports:
- Section-based field definitions (e.g. `### Full Name (full_name)` followed by constraints)
- Inline field definitions (e.g. `The full_name field is required...`)
- Markdown tables (e.g. `| full_name | text | Yes | 2 chars | 50 chars |`)
- Natural language constraint phrasing:
    * Required: "required", "mandatory", "must provide"
    * Length bounds: "between X and Y characters", "at least X characters", "at most Y characters"
    * Number bounds: "between X and Y", "minimum of X", "maximum of Y"
    * Formats: "email", "password", "numeric/number", regex patterns, phone
"""
import re
import os

REQUIRED_PATTERNS = [r"\brequired\b", r"\bmust\s+(?:be\s+)?provid", r"\bmandatory\b"]
EMAIL_PATTERNS = [r"\bvalid\s+email\b", r"\bemail\s+format\b", r"\be-?mail\s+address\b"]
LEN_RANGE = re.compile(r"between\s+(\d+)\s+and\s+(\d+)\s+characters", re.I)
MIN_LEN = re.compile(r"at\s+least\s+(\d+)\s+characters", re.I)
MAX_LEN = re.compile(r"at\s+most\s+(\d+)\s+characters|no\s+more\s+than\s+(\d+)\s+characters", re.I)
NUM_RANGE = re.compile(r"between\s+(\d+)\s+and\s+(\d+)\b(?!\s+characters)", re.I)
MIN_NUM = re.compile(r"(?:at\s+least|minimum(?:\s+of)?)\s+(\d+)\b(?!\s+characters)", re.I)
MAX_NUM = re.compile(r"(?:at\s+most|maximum(?:\s+of)?)\s+(\d+)\b(?!\s+characters)", re.I)


def _matches_any(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)


def parse_srs_rules(srs_path: str, known_field_names: list) -> dict:
    """Scans srs_path; recognizes headings, paragraphs, and markdown tables
    mentioning known fields and extracts constraint rules."""
    with open(srs_path, encoding="utf-8", errors="ignore") as f:
        text = f.read()

    rules = {f: {"type": "text", "required": False} for f in known_field_names}
    current_field = None

    for line in text.splitlines():
        line_clean = line.strip()
        line_lower = line_clean.lower()
        if not line_clean:
            continue

        # Check for section header switching active field: e.g. "### 2.1 Full Name (full_name)"
        if line_clean.startswith("#"):
            current_field = None
            for field in known_field_names:
                loose = field.replace("_", " ")
                if field.lower() in line_lower or loose.lower() in line_lower:
                    current_field = field
                    break
            continue

        # Check for markdown table row: e.g. "| full_name | text | Yes | 2 characters | 50 characters |"
        if line_clean.startswith("|") and not line_clean.startswith("|-"):
            cells = [c.strip() for c in line_clean.strip("|").split("|")]
            for field in known_field_names:
                if any(field.lower() == c.lower() or field.replace("_", " ").lower() == c.lower() for c in cells):
                    rule = rules[field]
                    row_text = " ".join(cells).lower()
                    if any(req in row_text for req in ["yes", "true", "required", "mandatory"]):
                        rule["required"] = True
                    elif any(no_val in row_text for no_val in ["no", "false", "optional"]):
                        rule["required"] = False
                    if "email" in row_text:
                        rule["type"] = "email"
                    elif "number" in row_text or "integer" in row_text or "numeric" in row_text or "age" in field.lower():
                        rule["type"] = "number"
                    elif "password" in row_text:
                        rule["type"] = "password"

                    # Numeric bounds in table
                    nums = re.findall(r"\b\d+\b", row_text)
                    if len(nums) >= 2:
                        if rule["type"] == "number":
                            rule["min"] = int(nums[0])
                            rule["max"] = int(nums[1])
                        else:
                            rule["min_len"] = int(nums[0])
                            rule["max_len"] = int(nums[1])
                    continue

        # Determine target field for this line: current_field or line-specific mention
        target_fields = []
        for field in known_field_names:
            loose = field.replace("_", " ")
            if field.lower() in line_lower or loose.lower() in line_lower:
                target_fields.append(field)

        # If no explicit field on this line, use current section's field
        if not target_fields and current_field:
            target_fields = [current_field]

        for field in target_fields:
            rule = rules[field]

            if "optional" in line_lower:
                rule["required"] = False
            elif _matches_any(REQUIRED_PATTERNS, line_clean) and "optional" not in line_lower:
                rule["required"] = True

            if _matches_any(EMAIL_PATTERNS, line_clean):
                rule["type"] = "email"
            elif "password" in field.lower():
                rule["type"] = "password"
            elif "data type: text" in line_lower or "data type: string" in line_lower:
                rule["type"] = "text"
            elif ("data type: number" in line_lower or "data type: numeric" in line_lower or "integer" in line_lower) and "disallow" not in line_lower:
                rule["type"] = "number"

            m = LEN_RANGE.search(line_clean)
            if m:
                rule["min_len"], rule["max_len"] = int(m.group(1)), int(m.group(2))
            else:
                m = MIN_LEN.search(line_clean)
                if m:
                    rule["min_len"] = int(m.group(1))
                m = MAX_LEN.search(line_clean)
                if m:
                    rule["max_len"] = int(m.group(1) or m.group(2))

            m = NUM_RANGE.search(line_clean)
            if m and rule.get("type") == "number":
                rule["min"], rule["max"] = int(m.group(1)), int(m.group(2))
            else:
                m = MIN_NUM.search(line_clean)
                if m and rule.get("type") == "number":
                    rule["min"] = int(m.group(1))
                m = MAX_NUM.search(line_clean)
                if m and rule.get("type") == "number":
                    rule["max"] = int(m.group(1))

    return rules


def get_srs_rules(srs_path: str, known_field_names: list):
    """Returns {"source": "srs_document", "reference_path": srs_path, "rules": rules}
    or None if the file is missing/empty."""
    if not srs_path or not os.path.exists(srs_path):
        return None
    if not srs_path.lower().endswith((".txt", ".md")):
        print(f"[parse_srs] Unsupported SRS file type: {srs_path} (expected .txt or .md).")
        return None

    rules = parse_srs_rules(srs_path, known_field_names)
    if not rules:
        print(f"[parse_srs] No recognisable field constraints found in {srs_path}.")
        return None

    for f in known_field_names:
        rules.setdefault(f, {"type": "text", "required": False})

    return {"source": "srs_document", "reference_path": srs_path, "rules": rules}


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "srs/registration_srs.md"
    fields = ["full_name", "email", "age", "password", "phone"]
    res = get_srs_rules(path, fields)
    print("Parsed SRS Rules:", res)
