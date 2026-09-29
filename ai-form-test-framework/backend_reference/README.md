# backend_reference/

Drop whatever backend reference material you have here, then point
`config.json` -> `backend_reference_path` at it. This is the ONLY place
you need to touch to switch between Case A (backend/spec available) and
Case B (black-box only) -- if the path is missing, empty, or unreadable,
the framework automatically falls back to Case B fuzzing/inference and
tells you it did so.

## Supported formats (auto-detected by file extension/content)

1. **Python file with a `VALIDATION_RULES` dict** (see `validation_rules.py`
   in this folder for the exact convention/keys expected). Use this when
   you have backend source code and can express its validators as a plain
   dict -- either by hand, or by writing a small adapter that imports your
   real Django/Flask/Spring validators and re-exports them in this shape.

2. **JSON Schema / OpenAPI-style file** with `properties` + `required`
   (see `validation_schema.example.json`). Use this when you have an
   OpenAPI spec, a Joi/Zod schema, or any SRS/API-doc already expressed as
   JSON Schema -- no Python needed.

3. **Nothing / file not found** -> the framework logs a warning and runs
   the Case B black-box fuzzing pipeline instead, treating the form as if
   no backend reference exists.

## What NOT to do

Don't edit `extraction/parse_backend.py` itself per-project -- it's a
generic loader for the two formats above. If your reference material is
in some other shape (e.g. a free-text SRS document), convert the relevant
constraints into one of the two formats above first; that conversion is
intentionally a manual/one-off step for this project's scope (see the
project report's discussion of SRS parsing).
