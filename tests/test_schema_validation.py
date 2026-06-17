import json
from pathlib import Path

from jsonschema.validators import validator_for

from fme_packager.schema_validation import (
    format_schema_validation_errors,
    load_schema_validator,
)

CWD = Path(__file__).parent.resolve()


# A simple, non-FMXJ schema to show the helper is schema-agnostic.
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "count": {"type": "integer"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "count"],
}


def _errors(instance):
    cls = validator_for(SCHEMA)
    return list(cls(SCHEMA).iter_errors(instance))


def test_load_schema_validator_is_usable_and_cached():
    validator = load_schema_validator("fmxj.schema.min.json")
    # Returns a working validator: a known-good FMXJ fixture yields no errors.
    fixture = CWD / "fixtures" / "fmxj_package" / "transformers" / "DemoGreeter.fmxj"
    assert list(validator.iter_errors(json.loads(fixture.read_text()))) == []
    # Cached per (filename, package): repeated calls return the same instance.
    assert load_schema_validator("fmxj.schema.min.json") is validator


def test_single_error():
    errors = _errors({"name": "x", "count": "not-an-int"})
    message = format_schema_validation_errors(errors, subject="config.json")
    assert message == (
        "config.json failed schema validation:\n"
        "  - at $.count: 'not-an-int' is not of type 'integer'"
    )


def test_multiple_errors_are_listed():
    errors = _errors({"count": "nope", "tags": [1]})
    message = format_schema_validation_errors(errors, subject="config.json")
    assert message.startswith("config.json failed schema validation:")
    assert "  - at $: 'name' is a required property" in message
    assert "  - at $.count: 'nope' is not of type 'integer'" in message
    assert "  - at $.tags[0]: 1 is not of type 'string'" in message


def test_default_subject_and_overflow():
    # 12 invalid array items -> 12 distinct errors; only max_errors are shown.
    errors = _errors({"name": "x", "count": 1, "tags": list(range(12))})
    message = format_schema_validation_errors(errors, max_errors=10)
    assert message.startswith("instance failed schema validation:")
    assert "  (and 2 other schema error(s))" in message
    # 1 header + 10 shown + 1 overflow note
    assert len(message.splitlines()) == 12
