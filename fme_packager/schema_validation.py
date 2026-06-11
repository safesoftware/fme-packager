"""
Reusable helpers for JSON-schema validation.
"""

import json
from functools import cache
from importlib.resources import open_text

from jsonschema.exceptions import best_match
from jsonschema.validators import validator_for


@cache
def load_schema_validator(schema_filename: str):
    """
    Load a JSON schema bundled in the package and return a cached validator for it.

    :param schema_filename: Name of the schema file bundled in fme_packager.
    :return: A jsonschema validator instance bound to the loaded schema.
    """
    with open_text("fme_packager", schema_filename) as f:
        schema = json.load(f)
    cls = validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def format_schema_validation_errors(errors, subject: str = "instance", max_errors: int = 10) -> str:
    """
    Build a concise, agent-actionable message from jsonschema validation errors.

    Renders a header line followed by up to ``max_errors`` bulleted errors, each as
    "  - at <json_path>: <reason>". The single most-relevant error (per best_match)
    is surfaced first, since nested anyOf/oneOf constructs can otherwise bury it.
    When more than ``max_errors`` exist, the remainder is noted as
    "(and N other schema error(s))" so nothing is silently hidden.

    :param errors: Iterable of jsonschema ValidationError, e.g. from
        ``validator.iter_errors(instance)``.
    :param subject: Name of the thing being validated, used as the message subject
        (e.g. a filename like "DemoGreeter.fmxj" or "package.yml").
    :param max_errors: Maximum number of distinct errors to list.
    :return: A formatted and readable message.
    """
    errors = list(errors)
    primary = best_match(errors)
    # Most-relevant error first, then the rest; dedupe by (json_path, message).
    ordered = [primary] + [error for error in errors if error is not primary]
    seen = set()
    formatted = []
    for error in ordered:
        # error.json_path -> e.g. "$.versions[0].version"
        key = (error.json_path, error.message)
        if key in seen:
            continue
        seen.add(key)
        formatted.append(f"at {error.json_path}: {error.message}")

    total = len(formatted)
    shown = formatted[:max_errors]
    prefix = f"{subject} failed schema validation"

    lines = [f"{prefix}:"]
    lines += [f"  - {entry}" for entry in shown]
    if total > len(shown):
        lines.append(f"  (and {total - len(shown)} other schema error(s))")
    return "\n".join(lines)
