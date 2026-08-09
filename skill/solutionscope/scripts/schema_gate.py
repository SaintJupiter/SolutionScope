#!/usr/bin/env python3
"""Dependency-free validator for the declared SolutionScope JSON Schema subset."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SUPPORTED_KEYWORDS = {
    "$schema",
    "$ref",
    "$defs",
    "type",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "pattern",
}


def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"only local JSON Schema references are supported: {ref}")
    current: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"unresolvable JSON Schema reference: {ref}")
        current = current[token]
    if not isinstance(current, dict):
        raise ValueError(f"JSON Schema reference does not target an object: {ref}")
    return current


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError(f"unsupported JSON Schema type: {expected}")


def _check_schema_keywords(schema: Any, path: str = "schema") -> list[dict[str, str]]:
    if not isinstance(schema, dict):
        return [_issue("schema.invalid", path, "schema node must be an object")]
    issues: list[dict[str, str]] = []
    for key, value in schema.items():
        if key not in SUPPORTED_KEYWORDS:
            issues.append(_issue("schema.unsupported_keyword", f"{path}.{key}", f"unsupported keyword: {key}"))
        if key in {"properties", "$defs"} and isinstance(value, dict):
            for child_key, child in value.items():
                issues.extend(_check_schema_keywords(child, f"{path}.{key}.{child_key}"))
        elif key == "items" and isinstance(value, dict):
            issues.extend(_check_schema_keywords(value, f"{path}.items"))
    return issues


def validate_instance(instance: Any, schema: dict[str, Any]) -> list[dict[str, str]]:
    """Return deterministic validation findings; an empty list means pass."""
    schema_issues = _check_schema_keywords(schema)
    if schema_issues:
        return schema_issues
    issues: list[dict[str, str]] = []

    def walk(value: Any, rule: dict[str, Any], path: str) -> None:
        if "$ref" in rule:
            walk(value, _resolve_ref(schema, rule["$ref"]), path)
            return

        if "const" in rule and value != rule["const"]:
            issues.append(_issue("schema.const", path, f"expected constant {rule['const']!r}"))
        if "enum" in rule and value not in rule["enum"]:
            issues.append(_issue("schema.enum", path, "value is outside the allowed enum"))

        expected = rule.get("type")
        if expected is not None:
            choices = expected if isinstance(expected, list) else [expected]
            if not any(_type_matches(value, choice) for choice in choices):
                issues.append(_issue("schema.type", path, f"expected type {choices}"))
                return

        if isinstance(value, str):
            if len(value) < int(rule.get("minLength", 0)):
                issues.append(_issue("schema.minLength", path, "string is shorter than minLength"))
            if "pattern" in rule and re.search(rule["pattern"], value) is None:
                issues.append(_issue("schema.pattern", path, "string does not match pattern"))

        if isinstance(value, list):
            if len(value) < int(rule.get("minItems", 0)):
                issues.append(_issue("schema.minItems", path, "array is shorter than minItems"))
            if "maxItems" in rule and len(value) > int(rule["maxItems"]):
                issues.append(_issue("schema.maxItems", path, "array is longer than maxItems"))
            if rule.get("uniqueItems"):
                encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
                if len(encoded) != len(set(encoded)):
                    issues.append(_issue("schema.uniqueItems", path, "array items must be unique"))
            if isinstance(rule.get("items"), dict):
                for index, item in enumerate(value):
                    walk(item, rule["items"], f"{path}[{index}]")

        if isinstance(value, dict):
            properties = rule.get("properties", {})
            for key in rule.get("required", []):
                if key not in value:
                    issues.append(_issue("schema.required", f"{path}.{key}", "required property is missing"))
            if rule.get("additionalProperties") is False:
                for key in value:
                    if key not in properties:
                        issues.append(_issue("schema.additionalProperties", f"{path}.{key}", "unexpected property"))
            for key, child_rule in properties.items():
                if key in value:
                    walk(value[key], child_rule, f"{path}.{key}")

    walk(instance, schema, "$")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--instance", type=Path, required=True)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    instance = json.loads(args.instance.read_text(encoding="utf-8"))
    issues = validate_instance(instance, schema)
    print(json.dumps({"status": "passed" if not issues else "failed", "errors": issues}, ensure_ascii=False, indent=2))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
