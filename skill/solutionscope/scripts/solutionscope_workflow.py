#!/usr/bin/env python3
"""SolutionScope v1.5 configurable, offline, ledger-constrained workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema_gate import validate_instance


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.5"
CONFIG_SCHEMA_PATH = ROOT / "references" / "workflow-config.schema.json"
GAP_KINDS = {
    "metric_absent",
    "metric_statistical_definition_insufficient",
    "acceptance_method_insufficient",
    "condition_insufficient",
    "information_complete",
    "potential_conflict_or_term_drift",
    "unclear",
}
UNAVAILABLE = "unavailable"


class WorkflowRefusal(RuntimeError):
    """Fail closed after writing the available audit artifacts."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def load_record(run_dir: Path) -> dict[str, Any]:
    return read_json(run_dir / "workflow_run_record.json")


def save_record(run_dir: Path, record: dict[str, Any]) -> None:
    record["updated_at_utc"] = utc_now()
    write_json(run_dir / "workflow_run_record.json", record)


def add_stage(record: dict[str, Any], name: str, started: float, **details: Any) -> None:
    record["stages"].append(
        {
            "stage_id": f"{record['run_id']}:{len(record['stages']) + 1:02d}:{name}",
            "stage": name,
            "created_at_utc": utc_now(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            **details,
        }
    )


def config_semantic_errors(config: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    group_ids: set[str] = set()
    question_ids: set[str] = set()
    rule_states: set[str] = set()
    for index, rule in enumerate(config.get("state_rules", [])):
        state = rule.get("state")
        if state in rule_states:
            errors.append({"code": "config.duplicate_state_rule", "path": f"$.state_rules[{index}].state", "message": f"duplicate state rule: {state}"})
        rule_states.add(state)
    for group_index, group in enumerate(config.get("question_groups", [])):
        group_id = group.get("group_id")
        if group_id in group_ids:
            errors.append({"code": "config.duplicate_group_id", "path": f"$.question_groups[{group_index}].group_id", "message": f"duplicate group ID: {group_id}"})
        group_ids.add(group_id)
        for question_index, question in enumerate(group.get("questions", [])):
            question_id = question.get("question_id")
            if question_id in question_ids:
                errors.append({"code": "config.duplicate_question_id", "path": f"$.question_groups[{group_index}].questions[{question_index}].question_id", "message": f"duplicate question ID: {question_id}"})
            question_ids.add(question_id)
    return errors


def load_and_validate_config(path: Path) -> dict[str, Any]:
    config = read_json(path)
    schema = read_json(CONFIG_SCHEMA_PATH)
    errors = validate_instance(config, schema) + config_semantic_errors(config)
    if errors:
        raise WorkflowRefusal(f"workflow config rejected: {json.dumps(errors, ensure_ascii=False)}")
    return config


def import_markdown(path: Path) -> dict[str, Any]:
    if path.suffix.lower() not in {".md", ".markdown"}:
        raise WorkflowRefusal("input must be Markdown")
    section = "root"
    paragraphs: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip() or "root"
            continue
        if line.startswith("> "):
            continue
        paragraphs.append(
            {
                "page_number": 1,
                "section": section,
                "paragraph_id": f"P001-{len(paragraphs) + 1:03d}",
                "text": line,
            }
        )
    if not paragraphs:
        raise WorkflowRefusal("input Markdown contains no reviewable paragraphs")
    return {
        "contract": "SolutionScope-v1.5-markdown-import",
        "document_id": f"DOC-{sha256(path)[:12]}",
        "source_sha256": sha256(path),
        "pagination": "markdown_continuous_page_1",
        "paragraphs": paragraphs,
    }


def locator_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["page_number", "section", "paragraph_id", "quote"],
        "properties": {
            "page_number": {"type": "integer"},
            "section": {"type": "string", "minLength": 1},
            "paragraph_id": {"type": "string", "minLength": 1},
            "quote": {"type": "string", "minLength": 1},
        },
    }


def ledger_schema(config: dict[str, Any]) -> dict[str, Any]:
    metric = {
        "type": "object",
        "additionalProperties": False,
        "required": ["metric", "comparator", "value", "unit", "condition", "raw_text"],
        "properties": {
            key: {"type": ["string", "null"]}
            for key in ("metric", "comparator", "value", "unit", "condition", "raw_text")
        },
    }
    gap = {
        "type": "object",
        "additionalProperties": False,
        "required": ["gap_kind", "description", "clarification_question", "evidence_locators"],
        "properties": {
            "gap_kind": {"enum": sorted(GAP_KINDS)},
            "description": {"type": "string", "minLength": 1},
            "clarification_question": {"type": "string"},
            "evidence_locators": {"type": "array", "items": {"$ref": "#/$defs/locator"}},
        },
    }
    entry = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "capability_id",
            "module",
            "normalized_capability",
            "language_state",
            "evidence_locators",
            "dependencies",
            "quantitative_metrics",
            "acceptance_method",
            "information_gaps",
        ],
        "properties": {
            "capability_id": {"type": "string", "minLength": 1, "pattern": "^[A-Za-z0-9_-]+$"},
            "module": {"type": "string", "minLength": 1},
            "normalized_capability": {"type": "string", "minLength": 1},
            "language_state": {"enum": config["allowed_states"]},
            "evidence_locators": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/locator"}},
            "dependencies": {"type": "array", "uniqueItems": True, "items": {"type": "string", "minLength": 1}},
            "quantitative_metrics": {"type": "array", "items": metric},
            "acceptance_method": {"type": ["string", "null"]},
            "information_gaps": {"type": "array", "items": gap},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["contract", "entries"],
        "properties": {
            "contract": {"const": "SolutionScope-v1.5-capability-ledger"},
            "entries": {"type": "array", "minItems": 1, "items": entry},
        },
        "$defs": {"locator": locator_schema()},
    }


def fragment_schema(group: dict[str, Any]) -> dict[str, Any]:
    question_ids = [question["question_id"] for question in group["questions"]]
    id_list = {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}}
    finding = {
        "type": "object",
        "additionalProperties": False,
        "required": ["claim", "capability_ids"],
        "properties": {"claim": {"type": "string", "minLength": 1}, "capability_ids": id_list},
    }
    gap = {
        "type": "object",
        "additionalProperties": False,
        "required": ["gap_kind", "description", "clarification_question", "capability_ids"],
        "properties": {
            "gap_kind": {"enum": sorted(GAP_KINDS)},
            "description": {"type": "string", "minLength": 1},
            "clarification_question": {"type": "string"},
            "capability_ids": id_list,
        },
    }
    conflict = {
        "type": "object",
        "additionalProperties": False,
        "required": ["classification", "description", "capability_ids"],
        "properties": {
            "classification": {"const": "potential_conflict_or_term_drift"},
            "description": {"type": "string", "minLength": 1},
            "capability_ids": id_list,
        },
    }
    coverage = {
        "type": "object",
        "additionalProperties": False,
        "required": ["component_id", "status", "note"],
        "properties": {
            "component_id": {"type": "string", "minLength": 1},
            "status": {"enum": ["covered", "not_covered", "not_applicable"]},
            "note": {"type": ["string", "null"]},
        },
    }
    answer = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "question_id",
            "answer_summary",
            "findings",
            "information_gaps",
            "potential_conflicts",
            "assumptions",
            "recommendations",
            "instruction_coverage",
        ],
        "properties": {
            "question_id": {"enum": question_ids},
            "answer_summary": {"type": "string", "minLength": 1},
            "findings": {"type": "array", "items": finding},
            "information_gaps": {"type": "array", "items": gap},
            "potential_conflicts": {"type": "array", "items": conflict},
            "assumptions": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "recommendations": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "instruction_coverage": {"type": "array", "minItems": 1, "items": coverage},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["contract", "group_id", "fragments"],
        "properties": {
            "contract": {"const": "SolutionScope-v1.5-ledger-constrained-fragments"},
            "group_id": {"const": group["group_id"]},
            "fragments": {
                "type": "array",
                "minItems": len(question_ids),
                "maxItems": len(question_ids),
                "items": answer,
            },
        },
    }


def final_schema(config: dict[str, Any]) -> dict[str, Any]:
    ledger_entry = ledger_schema(config)["properties"]["entries"]["items"]
    inherited = {
        "type": "object",
        "additionalProperties": False,
        "required": ["capability_id", "language_state", "evidence_locators"],
        "properties": {
            "capability_id": {"type": "string", "minLength": 1},
            "language_state": {"enum": config["allowed_states"]},
            "evidence_locators": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/locator"}},
        },
    }
    bound_finding = {
        "type": "object",
        "additionalProperties": False,
        "required": ["claim", "capability_ids", "inherited_capabilities"],
        "properties": {
            "claim": {"type": "string", "minLength": 1},
            "capability_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "inherited_capabilities": {"type": "array", "minItems": 1, "items": inherited},
        },
    }
    bound_gap = {
        "type": "object",
        "additionalProperties": False,
        "required": ["gap_kind", "description", "clarification_question", "capability_ids", "inherited_capabilities"],
        "properties": {
            "gap_kind": {"enum": sorted(GAP_KINDS)},
            "description": {"type": "string", "minLength": 1},
            "clarification_question": {"type": "string"},
            "capability_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "inherited_capabilities": {"type": "array", "minItems": 1, "items": inherited},
        },
    }
    bound_conflict = {
        "type": "object",
        "additionalProperties": False,
        "required": ["classification", "description", "capability_ids", "inherited_capabilities"],
        "properties": {
            "classification": {"const": "potential_conflict_or_term_drift"},
            "description": {"type": "string", "minLength": 1},
            "capability_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "inherited_capabilities": {"type": "array", "minItems": 1, "items": inherited},
        },
    }
    coverage = {
        "type": "object",
        "additionalProperties": False,
        "required": ["component_id", "status", "note"],
        "properties": {
            "component_id": {"type": "string"},
            "status": {"enum": ["covered", "not_covered", "not_applicable"]},
            "note": {"type": ["string", "null"]},
        },
    }
    risk = {
        "type": "object",
        "additionalProperties": False,
        "required": ["code", "severity", "path", "message"],
        "properties": {
            "code": {"type": "string", "minLength": 1},
            "severity": {"enum": ["low", "medium", "high"]},
            "path": {"type": "string", "minLength": 1},
            "message": {"type": "string", "minLength": 1},
            "evidence_locators": {"type": "array", "items": {"$ref": "#/$defs/locator"}},
        },
    }
    review_gate = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "human_review_required", "semantic_risk_count", "semantic_risks", "boundary"],
        "properties": {
            "status": {"enum": ["no_deterministic_block", "blocked_pending_human_review"]},
            "human_review_required": {"type": "boolean"},
            "semantic_risk_count": {"type": "integer"},
            "semantic_risks": {"type": "array", "items": risk},
            "boundary": {"type": "string", "minLength": 1},
        },
    }
    answer = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "question_id",
            "answer_summary",
            "findings",
            "information_gaps",
            "potential_conflicts",
            "assumptions",
            "recommendations",
            "instruction_coverage",
        ],
        "properties": {
            "question_id": {"type": "string"},
            "answer_summary": {"type": "string", "minLength": 1},
            "findings": {"type": "array", "items": bound_finding},
            "information_gaps": {"type": "array", "items": bound_gap},
            "potential_conflicts": {"type": "array", "items": bound_conflict},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "recommendations": {"type": "array", "items": {"type": "string"}},
            "instruction_coverage": {"type": "array", "items": coverage},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["contract", "artifact_class", "source_sha256", "source_config_sha256", "config_sha256", "capability_ledger", "answers", "review_gate", "provenance"],
        "properties": {
            "contract": {"const": "SolutionScope-v1.5-ledger-constrained-review-draft"},
            "artifact_class": {"enum": ["local_restricted_ai_draft", "public_authorized_ai_draft"]},
            "source_sha256": {"type": "string"},
            "source_config_sha256": {"type": "string"},
            "config_sha256": {"type": "string"},
            "capability_ledger": {"type": "array", "minItems": 1, "items": ledger_entry},
            "answers": {"type": "array", "minItems": 1, "items": answer},
            "review_gate": review_gate,
            "provenance": {"type": "object"},
        },
        "$defs": {"locator": locator_schema()},
    }


def all_questions(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [question for group in config["question_groups"] for question in group["questions"]]


def states_for_text(text: str, config: dict[str, Any]) -> set[str]:
    return {
        rule["state"]
        for rule in config["state_rules"]
        if any(phrase in text for phrase in rule["phrases"])
    }


def rows_and_lookup(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[tuple[int, str], dict[str, Any]]]:
    rows = read_json(Path(record["document_import_path"]))["paragraphs"]
    return rows, {(row["page_number"], row["paragraph_id"]): row for row in rows}


def locator_issue(locator: Any, lookup: dict[tuple[int, str], dict[str, Any]]) -> str | None:
    if not isinstance(locator, dict):
        return "locator_format_mismatch"
    target = lookup.get((locator.get("page_number"), locator.get("paragraph_id")))
    if target is None:
        return "evidence_not_found"
    if locator.get("section") != target["section"]:
        return "locator_misbound"
    quote = re.sub(r"\s+", "", locator.get("quote", ""))
    source = re.sub(r"\s+", "", target["text"])
    return None if quote and quote in source else "locator_misbound"


def source_drift_risks(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    against = set(config["conflict_against_current_states"])
    for term in config["focus_terms"]:
        hits = [row for row in rows if term in row["text"]]
        states = set().union(*(states_for_text(row["text"], config) for row in hits)) if hits else set()
        if "current" in states and states.intersection(against):
            risks.append(
                {
                    "code": "document_state_drift_requires_confirmation",
                    "severity": "high",
                    "path": f"document.focus_term:{term}",
                    "message": "source contains current and planned/candidate wording for a configured focus term",
                    "evidence_locators": [
                        {
                            "page_number": row["page_number"],
                            "section": row["section"],
                            "paragraph_id": row["paragraph_id"],
                            "quote": row["text"],
                        }
                        for row in hits
                    ],
                }
            )
    return risks


def validation_report(kind: str, artifact: Path, errors: list[dict[str, Any]], risks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "contract": "SolutionScope-v1.5-validation-report",
        "kind": kind,
        "artifact_path": str(artifact),
        "artifact_sha256": sha256(artifact),
        "structural_status": "passed" if not errors else "failed",
        "structural_errors": len(errors),
        "structural_error_categories": dict(Counter(error["code"] for error in errors)),
        "structural_findings": errors,
        "semantic_risk_count": len(risks),
        "semantic_risk_categories": dict(Counter(risk["code"] for risk in risks)),
        "semantic_risks": risks,
        "human_review_required": bool(risks),
        "boundary": "Deterministic structure and source-risk gates; not expert review, accuracy, or semantic correctness.",
    }


def validate_ledger(record: dict[str, Any], artifact: Path) -> dict[str, Any]:
    config = read_json(Path(record["config_path"]))
    schema = read_json(Path(record["ledger_schema_path"]))
    data = read_json(artifact)
    errors: list[dict[str, Any]] = validate_instance(data, schema)
    risks: list[dict[str, Any]] = []
    rows, lookup = rows_and_lookup(record)
    entries = data.get("entries", []) if isinstance(data, dict) else []
    capability_ids = [entry.get("capability_id") for entry in entries if isinstance(entry, dict)]
    if len(capability_ids) != len(set(capability_ids)):
        errors.append({"code": "duplicate_capability_id", "path": "$.entries", "message": "capability IDs must be unique"})
    known = set(capability_ids)
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        path = f"$.entries[{index}]"
        valid_locators: list[dict[str, Any]] = []
        for locator_index, locator in enumerate(entry.get("evidence_locators", [])):
            code = locator_issue(locator, lookup)
            if code:
                errors.append({"code": code, "path": f"{path}.evidence_locators[{locator_index}]", "message": "source anchor is not exact"})
            else:
                valid_locators.append(locator)
        unknown_dependencies = [dependency for dependency in entry.get("dependencies", []) if dependency not in known]
        if unknown_dependencies:
            errors.append({"code": "unknown_dependency_id", "path": f"{path}.dependencies", "message": f"unknown capability IDs: {unknown_dependencies}"})
        source_states = set().union(*(states_for_text(locator["quote"], config) for locator in valid_locators)) if valid_locators else set()
        if entry.get("language_state") == "current" and "current" not in source_states and source_states.intersection(config["promotion_source_states"]):
            risks.append({"code": "future_or_candidate_promoted_to_current", "severity": "high", "path": path, "message": "current ledger state is anchored only to explicit non-current wording"})
        if entry.get("language_state") == "conflicted":
            if "current" not in source_states or not source_states.intersection(config["conflict_against_current_states"]):
                risks.append({"code": "conflict_state_not_evidenced", "severity": "high", "path": path, "message": "conflicted state lacks localized opposing source propositions"})

    drift_risks = source_drift_risks(rows, config)
    risks.extend(drift_risks)
    for drift in drift_risks:
        term = drift["path"].split(":", 1)[1]
        represented = any(
            entry.get("language_state") == "conflicted"
            and any(term in locator.get("quote", "") for locator in entry.get("evidence_locators", []))
            for entry in entries
            if isinstance(entry, dict)
        )
        if not represented:
            risks.append({"code": "source_conflict_not_ledgered", "severity": "high", "path": drift["path"], "message": "configured source drift is not represented by a conflicted ledger capability"})
    return validation_report("ledger", artifact, errors, risks)


def validate_fragment(record: dict[str, Any], group: dict[str, Any], artifact: Path) -> dict[str, Any]:
    schema = read_json(Path(record["fragment_packages"][group["group_id"]]["schema_path"]))
    data = read_json(artifact)
    errors: list[dict[str, Any]] = validate_instance(data, schema)
    risks: list[dict[str, Any]] = []
    ledger = read_json(Path(record["ledger_artifact_path"]))
    known_ids = {entry["capability_id"] for entry in ledger["entries"]}
    expected_question_ids = [question["question_id"] for question in group["questions"]]
    fragments = data.get("fragments", []) if isinstance(data, dict) else []
    actual_question_ids = [fragment.get("question_id") for fragment in fragments if isinstance(fragment, dict)]
    if actual_question_ids != expected_question_ids:
        errors.append({"code": "question_order", "path": "$.fragments", "message": "fragment questions must match configured order"})
    question_by_id = {question["question_id"]: question for question in group["questions"]}
    for fragment in fragments:
        if not isinstance(fragment, dict):
            continue
        question_id = fragment.get("question_id", "?")
        for field in ("findings", "information_gaps", "potential_conflicts"):
            for index, item in enumerate(fragment.get(field, [])):
                unknown = [capability_id for capability_id in item.get("capability_ids", []) if capability_id not in known_ids]
                if unknown:
                    errors.append({"code": "unknown_capability_id", "path": f"$.answers.{question_id}.{field}[{index}].capability_ids", "message": f"unknown capability IDs: {unknown}"})
        expected_components = question_by_id.get(question_id, {}).get("instruction_components", [])
        coverage = fragment.get("instruction_coverage", [])
        actual_components = [item.get("component_id") for item in coverage if isinstance(item, dict)]
        if actual_components != expected_components or any(item.get("status") == "not_covered" for item in coverage if isinstance(item, dict)):
            risks.append({"code": "instruction_component_missing", "severity": "high", "path": f"$.answers.{question_id}.instruction_coverage", "message": "configured instruction component is absent, reordered, or explicitly not covered"})
    return validation_report(f"fragment:{group['group_id']}", artifact, errors, risks)


def inherited(capability_ids: list[str], ledger: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "capability_id": capability_id,
            "language_state": ledger[capability_id]["language_state"],
            "evidence_locators": ledger[capability_id]["evidence_locators"],
        }
        for capability_id in capability_ids
    ]


def assemble_fragment(fragment: dict[str, Any], ledger: dict[str, dict[str, Any]]) -> dict[str, Any]:
    output = {
        key: fragment[key]
        for key in ("question_id", "answer_summary", "assumptions", "recommendations", "instruction_coverage")
    }
    output["findings"] = [
        {**item, "inherited_capabilities": inherited(item["capability_ids"], ledger)}
        for item in fragment["findings"]
    ]
    output["information_gaps"] = [
        {**item, "inherited_capabilities": inherited(item["capability_ids"], ledger)}
        for item in fragment["information_gaps"]
    ]
    output["potential_conflicts"] = [
        {**item, "inherited_capabilities": inherited(item["capability_ids"], ledger)}
        for item in fragment["potential_conflicts"]
    ]
    return output


def unique_strings(values: list[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def answer_locators(answer: dict[str, Any]) -> list[dict[str, Any]]:
    locators: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field in ("findings", "information_gaps", "potential_conflicts"):
        for item in answer.get(field, []):
            for capability in item.get("inherited_capabilities", []):
                for locator in capability.get("evidence_locators", []):
                    key = json.dumps(locator, ensure_ascii=False, sort_keys=True)
                    if key not in seen:
                        seen.add(key)
                        locators.append(locator)
    return locators


def ui_locator(locator: dict[str, Any]) -> str:
    return f"p.{locator['page_number']} / {locator['section']} / {locator['paragraph_id']}"


def build_ui_review_payload(
    final: dict[str, Any],
    config: dict[str, Any],
    document: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    """Create a deterministic browser view model without changing model output."""
    questions = {question["question_id"]: question for question in all_questions(config)}
    ledger = {entry["capability_id"]: entry for entry in final["capability_ledger"]}
    items: list[dict[str, Any]] = []
    origin = (
        "本地受限材料的精确来源锚点（仅在当前浏览器本地审核）"
        if final["artifact_class"] == "local_restricted_ai_draft"
        else "已授权公开材料的精确来源锚点"
    )
    gap_to_fields = {
        "metric_absent": ["quantitative_target"],
        "metric_statistical_definition_insufficient": ["quantitative_target"],
        "acceptance_method_insufficient": ["test_or_acceptance_method"],
        "condition_insufficient": ["preconditions"],
        "unclear": ["scope_boundary"],
        "potential_conflict_or_term_drift": ["scope_boundary"],
    }

    for answer in final["answers"]:
        question = questions[answer["question_id"]]
        locators = answer_locators(answer)
        primary = locators[0] if locators else None
        capability_ids = unique_strings(
            [
                capability_id
                for field in ("findings", "information_gaps", "potential_conflicts")
                for item in answer.get(field, [])
                for capability_id in item.get("capability_ids", [])
            ]
        )
        capabilities = [ledger[capability_id] for capability_id in capability_ids if capability_id in ledger]
        states = unique_strings([capability.get("language_state") for capability in capabilities])
        metrics = unique_strings(
            [
                metric.get("raw_text")
                or " ".join(str(metric.get(key) or "") for key in ("metric", "comparator", "value", "unit")).strip()
                for capability in capabilities
                for metric in capability.get("quantitative_metrics", [])
            ]
        )
        acceptance = unique_strings([capability.get("acceptance_method") for capability in capabilities])
        gap_questions = unique_strings(
            [gap.get("clarification_question") for gap in answer["information_gaps"]]
            + [f"请确认：{conflict['description']}" for conflict in answer["potential_conflicts"]]
        )
        suggested_missing = unique_strings(
            [
                field
                for gap in answer["information_gaps"]
                for field in gap_to_fields.get(gap["gap_kind"], [])
            ]
        )
        review_hints = unique_strings(
            [gap["description"] for gap in answer["information_gaps"]]
            + [conflict["description"] for conflict in answer["potential_conflicts"]]
        )
        has_open_issue = bool(answer["information_gaps"] or answer["potential_conflicts"])
        items.append(
            {
                "id": answer["question_id"],
                "topic": question["question"],
                "risk": "high" if has_open_issue else "normal",
                "evidence": {
                    "status": "bound" if primary else "missing",
                    "sourceId": document["document_id"],
                    "locator": ui_locator(primary) if primary else "未绑定",
                    "origin": origin,
                    "excerpt": primary["quote"] if primary else "该回答没有可展示的来源锚点，必须人工核对。",
                    "relatedLocators": [
                        {**locator, "display": ui_locator(locator)} for locator in locators
                    ],
                },
                "aiDraft": {
                    "requirement_object": question["question"],
                    "preconditions": "、".join(states) if states else None,
                    "required_action": "；".join(item["claim"] for item in answer["findings"]) or None,
                    "expected_result": answer["answer_summary"],
                    "quantitative_target": "；".join(metrics) if metrics else None,
                    "test_or_acceptance_method": "；".join(acceptance) if acceptance else None,
                    "clarification_questions": gap_questions,
                },
                "aiCompleteness": "partial" if has_open_issue or not primary else "complete",
                "reviewHints": review_hints,
                "suggestedMissingFields": suggested_missing,
            }
        )

    return {
        "contract": "SolutionScope-ui-review-payload-v1",
        "fixtureId": f"SS-{record['run_id']}",
        "fixtureType": final["artifact_class"],
        "title": "技术材料要求抽取与审核",
        "subtitle": f"{record['run_id']} · 本地导入 · 页面不调用模型",
        "boundary": [
            "该文件是确定性生成的审核视图，不改写模型原始输出。",
            "页面只在当前浏览器会话中读取审核包，不上传材料。",
            "结构和来源门禁通过不代表语义正确、专家批准或生产可用。",
        ],
        "fieldLabels": {
            "requirement_object": "审核问题",
            "preconditions": "涉及的材料状态",
            "required_action": "关键发现",
            "expected_result": "回答摘要",
            "quantitative_target": "量化信息",
            "test_or_acceptance_method": "验收信息",
            "scope_boundary": "适用范围",
            "audit_requirement": "审计要求",
        },
        "items": items,
        "source": {
            "sourceSha256": final["source_sha256"],
            "configSha256": final["config_sha256"],
            "reviewDraftSha256": sha256(Path(record["final_artifact_path"])),
            "generatedAtUtc": utc_now(),
        },
        "claimBoundary": "Local review view model only; no accuracy, expert correctness, production readiness, user value, or ROI claim.",
    }


def validate_final(record: dict[str, Any], artifact: Path) -> dict[str, Any]:
    config = read_json(Path(record["config_path"]))
    schema = read_json(Path(record["final_schema_path"]))
    data = read_json(artifact)
    errors: list[dict[str, Any]] = validate_instance(data, schema)
    risks: list[dict[str, Any]] = []
    expected_preassembly_risks = collect_preassembly_risks(record)
    review_gate = data.get("review_gate", {}) if isinstance(data, dict) else {}
    if review_gate.get("semantic_risks") != expected_preassembly_risks:
        errors.append({"code": "review_gate_mismatch", "path": "$.review_gate.semantic_risks", "message": "final review gate must retain all deterministic preassembly risks exactly"})
    else:
        risks.extend(expected_preassembly_risks)
    ledger = {entry["capability_id"]: entry for entry in data.get("capability_ledger", [])}
    expected_questions = [question["question_id"] for question in all_questions(config)]
    actual_questions = [answer.get("question_id") for answer in data.get("answers", []) if isinstance(answer, dict)]
    if actual_questions != expected_questions:
        errors.append({"code": "question_order", "path": "$.answers", "message": "final answers must match configured question order"})
    used_ids: set[str] = set()
    for answer_index, answer in enumerate(data.get("answers", [])):
        if not isinstance(answer, dict):
            continue
        for field in ("findings", "information_gaps", "potential_conflicts"):
            for item_index, item in enumerate(answer.get(field, [])):
                capability_ids = item.get("capability_ids", [])
                used_ids.update(capability_ids)
                expected = inherited(capability_ids, ledger) if all(capability_id in ledger for capability_id in capability_ids) else None
                if expected is None or item.get("inherited_capabilities") != expected:
                    errors.append({"code": "ledger_injection_mismatch", "path": f"$.answers[{answer_index}].{field}[{item_index}]", "message": "states and source anchors must be injected exactly from the ledger"})
    missing_conflicts = [capability_id for capability_id, entry in ledger.items() if entry["language_state"] == "conflicted" and capability_id not in used_ids]
    if missing_conflicts:
        risks.append({"code": "material_conflict_not_retained", "severity": "high", "path": "$.answers", "message": f"conflicted ledger capabilities were not retained: {missing_conflicts}"})
    return validation_report("final", artifact, errors, risks)


def collect_preassembly_risks(record: dict[str, Any]) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if record.get("ledger_validation_path"):
        paths.append(Path(record["ledger_validation_path"]))
    for package in record.get("fragment_packages", {}).values():
        if package.get("validation_path"):
            paths.append(Path(package["validation_path"]))
    reports = [read_json(path) for path in paths if path.is_file()]
    return deduplicate_findings([risk for report in reports for risk in report.get("semantic_risks", [])])


def metadata_for_stage(metadata: dict[str, Any], stage_key: str, artifact: Path, record: dict[str, Any]) -> dict[str, Any]:
    supplied = metadata.get(stage_key, {}) if isinstance(metadata, dict) else {}
    duration = supplied.get("duration_ms", UNAVAILABLE)
    input_tokens = supplied.get("input_tokens", UNAVAILABLE)
    output_tokens = supplied.get("output_tokens", UNAVAILABLE)
    total_tokens = supplied.get("total_tokens", UNAVAILABLE)
    if total_tokens == UNAVAILABLE and isinstance(input_tokens, int) and isinstance(output_tokens, int):
        total_tokens = input_tokens + output_tokens
    cost_value = supplied.get("cost_value", UNAVAILABLE)
    currency = supplied.get("currency", UNAVAILABLE if cost_value == UNAVAILABLE else "USD")
    return {
        "model_call_id": supplied.get("model_call_id", f"import:{stage_key}:{sha256(artifact)[:12]}"),
        "stage": stage_key,
        "model": supplied.get("model", record["model"]),
        "reasoning_effort": supplied.get("reasoning_effort", record["reasoning_effort"]),
        "duration_ms": duration,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": {"value": cost_value, "currency": currency},
        "call_source": "existing_model_raw_output_import",
    }


def load_metadata(path: Path | None) -> dict[str, Any]:
    return read_json(path) if path is not None else {}


def register_raw(run_dir: Path, record: dict[str, Any], source: Path, stage_key: str, metadata: dict[str, Any]) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise WorkflowRefusal(f"model output does not exist: {source}")
    read_json(source)
    destination = run_dir / "raw_outputs" / f"{stage_key}.json"
    if destination.exists():
        raise WorkflowRefusal(f"raw model output already registered: {stage_key}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    call = metadata_for_stage(metadata, stage_key, destination, record)
    call.update({"artifact_path": str(destination), "artifact_sha256": sha256(destination), "registered_at_utc": utc_now()})
    record["model_calls"].append(call)
    return destination


def question_manifest(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": "SolutionScope-v1.5-question-manifest",
        "config_id": config["config_id"],
        "groups": config["question_groups"],
    }


def prepare_run(
    input_path: Path,
    config_path: Path,
    run_dir: Path,
    run_id: str,
    model: str,
    reasoning_effort: str,
    permission_class: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    input_path = input_path.resolve()
    config_path = config_path.resolve()
    run_dir = run_dir.resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise WorkflowRefusal("prepare requires a new or empty run directory")
    run_dir.mkdir(parents=True, exist_ok=True)
    config = load_and_validate_config(config_path)
    imported = import_markdown(input_path)
    config_copy = run_dir / "workflow_config.json"
    document_path = run_dir / "document_import.json"
    questions_path = run_dir / "questions.json"
    ledger_schema_path = run_dir / "schemas" / "ledger.schema.json"
    final_schema_path = run_dir / "schemas" / "final.schema.json"
    write_json(config_copy, config)
    write_json(document_path, imported)
    write_json(questions_path, question_manifest(config))
    write_json(ledger_schema_path, ledger_schema(config))
    write_json(final_schema_path, final_schema(config))
    fragment_packages: dict[str, Any] = {}
    for group in config["question_groups"]:
        schema_path = run_dir / "schemas" / f"fragment-{group['group_id']}.schema.json"
        write_json(schema_path, fragment_schema(group))
        fragment_packages[group["group_id"]] = {
            "question_ids": [question["question_id"] for question in group["questions"]],
            "schema_path": str(schema_path),
            "schema_sha256": sha256(schema_path),
            "status": "awaiting_validated_ledger",
        }
    ledger_request = {
        "request_contract": "SolutionScope-v1.5-capability-ledger-request",
        "instruction": "Return exactly one JSON object matching output_schema. Build the sole capability-state and source-anchor ledger. Use only the imported document and configured states. Keep localized current-versus-planned/candidate tension as conflicted. Do not answer the questions or use external/reference outputs.",
        "output_schema_path": str(ledger_schema_path),
        "output_schema_sha256": sha256(ledger_schema_path),
        "workflow_config": config,
        "document": imported,
        "declared_output_name": "ledger.json",
    }
    ledger_request_path = run_dir / "requests" / "ledger_request.json"
    write_json(ledger_request_path, ledger_request)
    record = {
        "contract": "SolutionScope-v1.5-offline-workflow-run",
        "workflow_version": VERSION,
        "run_id": run_id,
        "run_status": "ledger_request_prepared",
        "model": model,
        "reasoning_effort": reasoning_effort,
        "permission_class": permission_class,
        "source_input_path": str(input_path),
        "source_input_sha256": sha256(input_path),
        "source_config_path": str(config_path),
        "source_config_sha256": sha256(config_path),
        "config_path": str(config_copy),
        "config_sha256": sha256(config_copy),
        "config_sha256_kind": "normalized_runtime_copy",
        "document_import_path": str(document_path),
        "document_import_sha256": sha256(document_path),
        "questions_path": str(questions_path),
        "questions_sha256": sha256(questions_path),
        "ledger_schema_path": str(ledger_schema_path),
        "ledger_schema_sha256": sha256(ledger_schema_path),
        "final_schema_path": str(final_schema_path),
        "final_schema_sha256": sha256(final_schema_path),
        "ledger_request_path": str(ledger_request_path),
        "ledger_request_sha256": sha256(ledger_request_path),
        "fragment_packages": fragment_packages,
        "model_calls": [],
        "stages": [],
        "claim_boundary": "Offline auditable workflow; no external model is called by this script. Structural/source-risk gates are not accuracy or expert review.",
    }
    add_stage(record, "prepare", started, question_count=len(all_questions(config)), group_count=len(config["question_groups"]))
    save_record(run_dir, record)
    return record


def advance_run(run_dir: Path, ledger_output: Path, metadata_path: Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    run_dir = run_dir.resolve()
    record = load_record(run_dir)
    if record["run_status"] != "ledger_request_prepared":
        raise WorkflowRefusal("advance requires ledger_request_prepared status")
    metadata = load_metadata(metadata_path)
    ledger_artifact = register_raw(run_dir, record, ledger_output, "ledger", metadata)
    report = validate_ledger(record, ledger_artifact)
    report_path = run_dir / "validation" / "ledger.json"
    write_json(report_path, report)
    record.update(
        {
            "ledger_artifact_path": str(ledger_artifact),
            "ledger_artifact_sha256": sha256(ledger_artifact),
            "ledger_validation_path": str(report_path),
            "ledger_validation_sha256": sha256(report_path),
        }
    )
    add_stage(record, "register_and_validate_ledger", started, structural_errors=report["structural_errors"], semantic_risks=report["semantic_risk_count"])
    if report["structural_errors"]:
        record["run_status"] = "failed_ledger_structural_gate"
        save_record(run_dir, record)
        write_overall_report(run_dir, record)
        raise WorkflowRefusal("ledger failed structural gate")

    config = read_json(Path(record["config_path"]))
    document = read_json(Path(record["document_import_path"]))
    ledger = read_json(ledger_artifact)
    for group in config["question_groups"]:
        group_id = group["group_id"]
        skeletons = {
            question["question_id"]: [
                {"component_id": component, "status": "not_covered", "note": None}
                for component in question["instruction_components"]
            ]
            for question in group["questions"]
        }
        request = {
            "request_contract": "SolutionScope-v1.5-ledger-constrained-fragment-request",
            "instruction": "Return exactly one JSON object matching output_schema. Select only capability_id values from the ledger. Do not output source locators or lifecycle states. Write question-specific findings, gaps, conflicts, assumptions, recommendations, and the fixed instruction coverage. Use no external/reference outputs.",
            "output_schema_path": record["fragment_packages"][group_id]["schema_path"],
            "output_schema_sha256": record["fragment_packages"][group_id]["schema_sha256"],
            "assigned_group": group,
            "coverage_skeletons": skeletons,
            "capability_ledger": ledger,
            "document": document,
            "declared_output_name": f"fragment-{group_id}.json",
        }
        request_path = run_dir / "requests" / f"fragment-{group_id}.json"
        write_json(request_path, request)
        record["fragment_packages"][group_id].update(
            {"request_path": str(request_path), "request_sha256": sha256(request_path), "status": "request_prepared"}
        )
    record["run_status"] = "fragment_requests_prepared"
    save_record(run_dir, record)
    return record


def parse_fragment_outputs(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise WorkflowRefusal("fragment output must use GROUP_ID=PATH")
        group_id, raw_path = value.split("=", 1)
        if not group_id or group_id in parsed:
            raise WorkflowRefusal(f"duplicate or empty fragment group: {group_id}")
        parsed[group_id] = Path(raw_path)
    return parsed


def complete_run(run_dir: Path, fragment_outputs: dict[str, Path], metadata_path: Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    run_dir = run_dir.resolve()
    record = load_record(run_dir)
    if record["run_status"] != "fragment_requests_prepared":
        raise WorkflowRefusal("complete requires fragment_requests_prepared status")
    config = read_json(Path(record["config_path"]))
    groups = {group["group_id"]: group for group in config["question_groups"]}
    if set(fragment_outputs) != set(groups):
        raise WorkflowRefusal(f"fragment groups must match exactly: expected {sorted(groups)}, got {sorted(fragment_outputs)}")
    metadata = load_metadata(metadata_path)
    structural_errors = 0
    for group_id, group in groups.items():
        artifact = register_raw(run_dir, record, fragment_outputs[group_id], group_id, metadata)
        report = validate_fragment(record, group, artifact)
        report_path = run_dir / "validation" / f"fragment-{group_id}.json"
        write_json(report_path, report)
        record["fragment_packages"][group_id].update(
            {
                "artifact_path": str(artifact),
                "artifact_sha256": sha256(artifact),
                "validation_path": str(report_path),
                "validation_sha256": sha256(report_path),
                "structural_errors": report["structural_errors"],
                "status": "validated" if not report["structural_errors"] else "failed_structural_gate",
            }
        )
        structural_errors += report["structural_errors"]
    add_stage(record, "register_and_validate_fragments", started, structural_errors=structural_errors)
    if structural_errors:
        record["run_status"] = "failed_fragment_structural_gate"
        save_record(run_dir, record)
        write_overall_report(run_dir, record)
        raise WorkflowRefusal("one or more fragments failed structural gate")

    assembly_started = time.perf_counter()
    ledger_list = read_json(Path(record["ledger_artifact_path"]))["entries"]
    ledger = {entry["capability_id"]: entry for entry in ledger_list}
    fragments_by_question: dict[str, dict[str, Any]] = {}
    for group_id in groups:
        artifact = read_json(Path(record["fragment_packages"][group_id]["artifact_path"]))
        for fragment in artifact["fragments"]:
            fragments_by_question[fragment["question_id"]] = fragment
    ordered_questions = [question["question_id"] for question in all_questions(config)]
    if set(fragments_by_question) != set(ordered_questions):
        raise WorkflowRefusal("validated fragments do not cover every configured question")
    final = {
        "contract": "SolutionScope-v1.5-ledger-constrained-review-draft",
        "artifact_class": "local_restricted_ai_draft" if record["permission_class"] == "local_restricted" else "public_authorized_ai_draft",
        "source_sha256": record["source_input_sha256"],
        "source_config_sha256": record["source_config_sha256"],
        "config_sha256": record["config_sha256"],
        "capability_ledger": ledger_list,
        "answers": [assemble_fragment(fragments_by_question[question_id], ledger) for question_id in ordered_questions],
        "review_gate": {
            "status": "blocked_pending_human_review" if collect_preassembly_risks(record) else "no_deterministic_block",
            "human_review_required": bool(collect_preassembly_risks(record)),
            "semantic_risk_count": len(collect_preassembly_risks(record)),
            "semantic_risks": collect_preassembly_risks(record),
            "boundary": "A deterministic risk gate controls human review; it is not expert correctness or release approval.",
        },
        "provenance": {
            "workflow_version": VERSION,
            "run_id": record["run_id"],
            "model": record["model"],
            "reasoning_effort": record["reasoning_effort"],
            "model_calls": record["model_calls"],
            "boundary": record["claim_boundary"],
        },
    }
    final_path = run_dir / "final" / "review_draft.json"
    write_json(final_path, final)
    final_report = validate_final(record, final_path)
    final_validation_path = run_dir / "validation" / "final.json"
    write_json(final_validation_path, final_report)
    record.update(
        {
            "final_artifact_path": str(final_path),
            "final_artifact_sha256": sha256(final_path),
            "final_validation_path": str(final_validation_path),
            "final_validation_sha256": sha256(final_validation_path),
        }
    )
    if not final_report["structural_errors"]:
        ui_payload = build_ui_review_payload(
            final,
            config,
            read_json(Path(record["document_import_path"])),
            record,
        )
        ui_payload_path = run_dir / "final" / "ui_review_payload.json"
        write_json(ui_payload_path, ui_payload)
        record.update(
            {
                "ui_review_payload_path": str(ui_payload_path),
                "ui_review_payload_sha256": sha256(ui_payload_path),
            }
        )
    add_stage(record, "deterministic_assembly_and_final_validation", assembly_started, structural_errors=final_report["structural_errors"], semantic_risks=final_report["semantic_risk_count"])
    record["run_status"] = "failed_final_structural_gate" if final_report["structural_errors"] else "report_ready"
    save_record(run_dir, record)
    summary = write_overall_report(run_dir, record)
    if final_report["structural_errors"]:
        raise WorkflowRefusal("final artifact failed structural gate")
    return summary


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        key = json.dumps(
            {key: finding.get(key) for key in ("code", "path", "message")},
            ensure_ascii=False,
            sort_keys=True,
        )
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


def aggregate_telemetry(model_calls: list[dict[str, Any]]) -> dict[str, Any]:
    def sum_if_complete(field: str) -> int | float | str:
        values = [call[field] for call in model_calls]
        return sum(values) if values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values) else UNAVAILABLE

    costs = [call["cost"]["value"] for call in model_calls]
    currencies = {call["cost"]["currency"] for call in model_calls}
    cost_value: int | float | str = sum(costs) if costs and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in costs) else UNAVAILABLE
    currency = next(iter(currencies)) if len(currencies) == 1 and cost_value != UNAVAILABLE else UNAVAILABLE
    return {
        "model_call_count": len(model_calls),
        "duration_ms": sum_if_complete("duration_ms"),
        "input_tokens": sum_if_complete("input_tokens"),
        "output_tokens": sum_if_complete("output_tokens"),
        "total_tokens": sum_if_complete("total_tokens"),
        "cost": {"value": cost_value, "currency": currency},
    }


def write_overall_report(run_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    validation_paths: list[Path] = []
    if record.get("ledger_validation_path"):
        validation_paths.append(Path(record["ledger_validation_path"]))
    for package in record.get("fragment_packages", {}).values():
        if package.get("validation_path"):
            validation_paths.append(Path(package["validation_path"]))
    if record.get("final_validation_path"):
        validation_paths.append(Path(record["final_validation_path"]))
    validations = [read_json(path) for path in validation_paths if path.is_file()]
    errors = deduplicate_findings([finding for report in validations for finding in report["structural_findings"]])
    risks = deduplicate_findings([finding for report in validations for finding in report["semantic_risks"]])
    status = "failed_structural_gate" if errors else "review_ready_human_gate_blocked" if risks else "review_ready_source_bound"
    release_gate = "blocked_structural_error" if errors else "blocked_pending_human_review" if risks else "no_deterministic_block"
    summary = {
        "contract": "SolutionScope-v1.5-run-report",
        "run_id": record["run_id"],
        "workflow_version": VERSION,
        "status": status,
        "source_sha256": record["source_input_sha256"],
        "source_config_sha256": record["source_config_sha256"],
        "config_sha256": record["config_sha256"],
        "config_sha256_kind": record.get("config_sha256_kind", "normalized_runtime_copy"),
        "question_count": sum(len(package["question_ids"]) for package in record["fragment_packages"].values()),
        "group_count": len(record["fragment_packages"]),
        "stage_count": len(record["stages"]),
        "telemetry": aggregate_telemetry(record["model_calls"]),
        "structural_errors": len(errors),
        "structural_error_categories": dict(Counter(error["code"] for error in errors)),
        "semantic_risks": len(risks),
        "semantic_risk_categories": dict(Counter(risk["code"] for risk in risks)),
        "structural_findings": errors,
        "semantic_findings": risks,
        "release_gate": {
            "status": release_gate,
            "human_review_required": bool(errors or risks),
            "meaning": "Process exit code 0 means an auditable review artifact was generated; it never means approved for release.",
        },
        "final_artifact_path": record.get("final_artifact_path"),
        "boundary": "Source-bound deterministic report. It is not accuracy, expert correctness, generalization, production readiness, user value, or ROI.",
    }
    report_json = run_dir / "report" / "run_report.json"
    write_json(report_json, summary)
    lines = [
        "# SolutionScope v1.5 offline run report",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Questions/groups: {summary['question_count']} / {summary['group_count']}",
        f"- Recorded stages/model calls: {summary['stage_count']} / {summary['telemetry']['model_call_count']}",
        f"- Structural errors: {summary['structural_errors']}",
        f"- Deterministic semantic risks: {summary['semantic_risks']}",
        f"- Human release gate: `{summary['release_gate']['status']}`",
        f"- Duration/tokens/cost: `{summary['telemetry']['duration_ms']}` / `{summary['telemetry']['total_tokens']}` / `{summary['telemetry']['cost']['value']}`",
        "",
        "## Boundaries",
        "",
        summary["boundary"],
    ]
    if summary["semantic_risk_categories"]:
        lines.extend(["", "## Source-risk categories", ""])
        lines.extend(f"- `{code}`: {count}" for code, count in sorted(summary["semantic_risk_categories"].items()))
    write_text(run_dir / "report" / "run_report.md", "\n".join(lines) + "\n")
    record["report_path"] = str(report_json)
    record["report_sha256"] = sha256(report_json)
    record["run_status"] = status
    save_record(run_dir, record)
    return summary


def handle_prepare(args: argparse.Namespace) -> None:
    record = prepare_run(args.input, args.config, args.run_dir, args.run_id, args.model, args.reasoning_effort, args.permission_class)
    print(json.dumps({"run_dir": str(args.run_dir.resolve()), "status": record["run_status"], "ledger_request": record["ledger_request_path"]}, ensure_ascii=False, indent=2))


def handle_advance(args: argparse.Namespace) -> None:
    record = advance_run(args.run_dir, args.ledger_output, args.call_metadata)
    print(json.dumps({"status": record["run_status"], "fragment_requests": {group: package["request_path"] for group, package in record["fragment_packages"].items()}}, ensure_ascii=False, indent=2))


def handle_complete(args: argparse.Namespace) -> None:
    summary = complete_run(args.run_dir, parse_fragment_outputs(args.fragment_output), args.call_metadata)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def handle_offline(args: argparse.Namespace) -> None:
    prepare_run(args.input, args.config, args.run_dir, args.run_id, args.model, args.reasoning_effort, args.permission_class)
    advance_run(args.run_dir, args.ledger_output, args.call_metadata)
    summary = complete_run(args.run_dir, parse_fragment_outputs(args.fragment_output), args.call_metadata)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def add_prepare_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default=UNAVAILABLE)
    parser.add_argument("--reasoning-effort", default=UNAVAILABLE)
    parser.add_argument("--permission-class", choices=["local_restricted", "public_authorized"], default="local_restricted")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    add_prepare_arguments(prepare_parser)
    prepare_parser.set_defaults(handler=handle_prepare)

    advance_parser = subparsers.add_parser("advance")
    advance_parser.add_argument("--run-dir", type=Path, required=True)
    advance_parser.add_argument("--ledger-output", type=Path, required=True)
    advance_parser.add_argument("--call-metadata", type=Path)
    advance_parser.set_defaults(handler=handle_advance)

    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--run-dir", type=Path, required=True)
    complete_parser.add_argument("--fragment-output", action="append", default=[], required=True)
    complete_parser.add_argument("--call-metadata", type=Path)
    complete_parser.set_defaults(handler=handle_complete)

    offline_parser = subparsers.add_parser("run-offline")
    add_prepare_arguments(offline_parser)
    offline_parser.add_argument("--ledger-output", type=Path, required=True)
    offline_parser.add_argument("--fragment-output", action="append", default=[], required=True)
    offline_parser.add_argument("--call-metadata", type=Path)
    offline_parser.set_defaults(handler=handle_offline)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.handler(args)
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, WorkflowRefusal) as error:
        print(f"SOLUTION SCOPE V1.5 REFUSED/FAILED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
