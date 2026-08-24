#!/usr/bin/env python3
"""SolutionScope v2.2: source-bound requirements coverage workflow.

The script never calls a model. It prepares constrained requests, preserves raw
outputs, performs deterministic retrieval and validation, and assembles an
auditable requirement -> solution -> verification coverage matrix.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


VERSION = "2.2"
ATOM_CONTRACT = "SolutionScope-v2.2-requirement-atoms"
COVERAGE_CONTRACT = "SolutionScope-v2.2-coverage-decisions"
CHANGE_CONTRACT = "SolutionScope-v2.2-requirement-change-alignment"
BASELINE_CONTRACT = "SolutionScope-v2.2-direct-rag-review"
ROLES = {"requirement": "REQ", "solution": "SOL", "verification": "VER"}
STRENGTHS = {"must", "should", "may", "informational"}
LIFECYCLES = {"current", "planned", "candidate", "unknown"}
REVIEW_STAGES = {"proposal_review", "acceptance_review"}
SOLUTION_STATUSES = {"full", "partial", "absent", "conflicting", "unverifiable", "not_applicable"}
VERIFICATION_STATUSES = {"executable", "partial", "missing", "conflicting", "not_applicable"}
RELEASE_DECISIONS = {
    "pass_with_evidence", "block_missing_solution", "block_missing_verification",
    "block_conflict", "block_invariant_failure", "human_review",
}
COMPONENT_STATUSES = {"covered", "partial", "absent", "conflicting", "unverifiable"}
VERIFICATION_COMPONENT_STATUSES = {"supported", "partial", "missing", "conflicting", "unverifiable"}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*|[\u4e00-\u9fff]")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?:\s*%|\s*[A-Za-z]+)?")
STATE_TERMS = {
    "current": {"current", "existing", "implemented", "supported", "已", "现有", "当前", "具备", "支持"},
    "planned": {"planned", "future", "candidate", "proposed", "后续", "规划", "计划", "拟", "将", "候选"},
}

UNIT_ALIASES = {
    "%": ("percent", Decimal("1")), "percent": ("percent", Decimal("1")),
    "ms": ("time_ms", Decimal("1")), "millisecond": ("time_ms", Decimal("1")),
    "milliseconds": ("time_ms", Decimal("1")), "毫秒": ("time_ms", Decimal("1")),
    "s": ("time_ms", Decimal("1000")), "sec": ("time_ms", Decimal("1000")),
    "second": ("time_ms", Decimal("1000")), "seconds": ("time_ms", Decimal("1000")),
    "秒": ("time_ms", Decimal("1000")),
    "m": ("distance_m", Decimal("1")), "meter": ("distance_m", Decimal("1")),
    "meters": ("distance_m", Decimal("1")), "米": ("distance_m", Decimal("1")),
    "km": ("distance_m", Decimal("1000")), "kilometer": ("distance_m", Decimal("1000")),
    "kilometers": ("distance_m", Decimal("1000")), "公里": ("distance_m", Decimal("1000")),
}


class Refusal(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalized_metric(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", (value or "").lower())


def normalize_quantity(threshold: str, unit: str) -> tuple[str, Decimal] | None:
    """Normalize a numeric threshold without guessing unknown units."""
    try:
        number = Decimal(str(threshold).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    normalized_unit = re.sub(r"\s+", "", (unit or "").strip().lower())
    if normalized_unit not in UNIT_ALIASES:
        return None
    family, factor = UNIT_ALIASES[normalized_unit]
    return family, number * factor


def criterion_invariant(
    requirement: dict[str, str], observed: dict[str, str] | None, source: str, component_id: str,
) -> list[dict[str, str]]:
    """Check whether an observed commitment is at least as strong as the requirement."""
    failures: list[dict[str, str]] = []
    if not observed:
        return [{
            "code": f"{source}_criterion_not_observed", "component_id": component_id,
            "message": f"{source}未给出可复核的量化口径。",
        }]
    if normalized_metric(requirement.get("metric", "")) != normalized_metric(observed.get("metric", "")):
        failures.append({
            "code": f"{source}_metric_mismatch", "component_id": component_id,
            "message": f"{source}指标名称与需求指标不一致。",
        })
        return failures
    required_value = normalize_quantity(requirement.get("threshold", ""), requirement.get("unit", ""))
    observed_value = normalize_quantity(observed.get("threshold", ""), observed.get("unit", ""))
    if required_value is None or observed_value is None or required_value[0] != observed_value[0]:
        failures.append({
            "code": f"{source}_unit_incompatible", "component_id": component_id,
            "message": f"{source}量化单位无法与需求口径进行确定性换算。",
        })
        return failures
    req_op, obs_op = requirement.get("operator"), observed.get("operator")
    req_num, obs_num = required_value[1], observed_value[1]
    satisfies = False
    if req_op in {">=", ">"} and obs_op in {">=", ">"}:
        satisfies = obs_num > req_num or (obs_num == req_num and (req_op == ">=" or obs_op == ">"))
    elif req_op in {"<=", "<"} and obs_op in {"<=", "<"}:
        satisfies = obs_num < req_num or (obs_num == req_num and (req_op == "<=" or obs_op == "<"))
    elif req_op in {"=", "=="} and obs_op in {"=", "=="}:
        satisfies = obs_num == req_num
    if not satisfies:
        failures.append({
            "code": f"{source}_threshold_not_satisfied", "component_id": component_id,
            "message": (
                f"{source}口径 {observed.get('operator')} {observed.get('threshold')} {observed.get('unit')} "
                f"不能满足需求 {requirement.get('operator')} {requirement.get('threshold')} {requirement.get('unit')}。"
            ),
        })
    return failures


def tokens(text: str) -> list[str]:
    return [x.lower() for x in TOKEN_RE.findall(text or "")]


def char_ngrams(text: str, n: int = 2) -> set[str]:
    compact = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff%]", "", (text or "").lower())
    return {compact[i:i+n] for i in range(max(0, len(compact) - n + 1))}


def number_terms(text: str) -> set[str]:
    return {re.sub(r"\s+", "", x.lower()) for x in NUMBER_RE.findall(text or "")}


def state_terms(text: str) -> set[str]:
    lowered = (text or "").lower()
    return {state for state, words in STATE_TERMS.items() if any(word in lowered for word in words)}


def import_markdown(path: Path, role: str) -> dict[str, Any]:
    if role not in ROLES:
        raise Refusal(f"unknown role: {role}")
    page, section, counters, rows = 1, "root", {}, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        marker = re.fullmatch(r"<!--\s*source_page:\s*(\d+)\s*-->", line)
        if marker:
            page = int(marker.group(1)); section = f"Page {page}"; continue
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip() or section; continue
        counters[page] = counters.get(page, 0) + 1
        pid = f"P{page:03d}-{counters[page]:03d}"
        rows.append({
            "evidence_id": f"{ROLES[role]}-{pid}", "role": role,
            "page_number": page, "section": section, "paragraph_id": pid,
            "quote": line,
        })
    if not rows:
        raise Refusal(f"{role} input contains no reviewable paragraphs")
    return {
        "contract": "SolutionScope-v2-evidence-registry", "role": role,
        "document_id": f"{ROLES[role]}-{sha256(path)[:12]}",
        "source_path": str(path.resolve()), "source_sha256": sha256(path),
        "entries": rows,
    }


def id_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["evidence_id"]: row for row in registry["entries"]}


def bm25(query: str, rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    q = tokens(query)
    docs = [tokens(f"{r['section']} {r['quote']}") for r in rows]
    if not q or not docs:
        return []
    df = Counter()
    for d in docs:
        df.update(set(d))
    avgdl = sum(map(len, docs)) / len(docs)
    scored = []
    for row, d in zip(rows, docs):
        tf, score = Counter(d), 0.0
        for term in q:
            n = df.get(term, 0)
            idf = math.log(1 + (len(docs) - n + 0.5) / (n + 0.5))
            freq = tf.get(term, 0)
            if freq:
                score += idf * (freq * 2.2) / (freq + 1.2 * (1 - 0.75 + 0.75 * len(d) / max(avgdl, 1)))
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], x[1]["evidence_id"]))
    return [{**row, "retrieval_score": round(score, 6)} for score, row in scored[:top_k]]


def hybrid_retrieve(query: str, rows: list[dict[str, Any]], top_k: int, adjacent: int = 1) -> list[dict[str, Any]]:
    """Retrieve lexical matches, then preserve metric/state signals and nearby context."""
    base = {row["evidence_id"]: row for row in bm25(query, rows, max(top_k * 4, top_k))}
    q_numbers, q_states, q_grams = number_terms(query), state_terms(query), char_ngrams(query)
    scored = []
    for row in rows:
        text = f"{row['section']} {row['quote']}"
        lexical = float(base.get(row["evidence_id"], {}).get("retrieval_score", 0.0))
        r_numbers, r_states, r_grams = number_terms(text), state_terms(text), char_ngrams(text)
        numeric_hits = len(q_numbers & r_numbers)
        state_hits = len(q_states & r_states)
        overlap = len(q_grams & r_grams) / max(1, len(q_grams | r_grams))
        score = lexical + numeric_hits * 3.0 + state_hits * 1.25 + overlap * 4.0
        if score <= 0:
            continue
        reasons = []
        if lexical: reasons.append("lexical_bm25")
        if numeric_hits: reasons.append("metric_overlap")
        if state_hits: reasons.append("lifecycle_overlap")
        if overlap >= .08: reasons.append("phrase_overlap")
        scored.append((score, row, reasons))
    scored.sort(key=lambda item: (-item[0], item[1]["evidence_id"]))
    seeds = scored[:top_k]
    by_id = {row["evidence_id"]: i for i, row in enumerate(rows)}
    selected: dict[str, dict[str, Any]] = {}
    for score, row, reasons in seeds:
        selected[row["evidence_id"]] = {
            **row, "retrieval_score": round(score, 6),
            "retrieval_reasons": reasons, "context_expansion": False,
        }
        index = by_id[row["evidence_id"]]
        for offset in range(-adjacent, adjacent + 1):
            if not offset or not (0 <= index + offset < len(rows)):
                continue
            neighbour = rows[index + offset]
            if abs(neighbour["page_number"] - row["page_number"]) > 1:
                continue
            selected.setdefault(neighbour["evidence_id"], {
                **neighbour, "retrieval_score": round(max(score - abs(offset) * .001, 0), 6),
                "retrieval_reasons": ["adjacent_context"], "context_expansion": True,
            })
    return sorted(selected.values(), key=lambda row: (-row["retrieval_score"], row["evidence_id"]))


def atom_query(atom: dict[str, Any]) -> str:
    criteria = " ".join(
        f"{c.get('metric', '')} {c.get('operator', '')} {c.get('threshold', '')} {c.get('unit', '')}"
        for c in atom.get("quantitative_criteria", [])
    )
    return " ".join([
        atom.get("requirement_object", ""), atom.get("required_action", ""),
        " ".join(atom.get("conditions", [])), criteria,
        " ".join(atom.get("verification_expectations", [])),
    ])


def solution_components(atom: dict[str, Any]) -> list[dict[str, str]]:
    rid = atom["requirement_id"]
    rows = [{"component_id": f"{rid}::ACTION", "component_type": "action", "text": atom["required_action"]}]
    rows.extend({"component_id": f"{rid}::COND-{i:02d}", "component_type": "condition", "text": text}
                for i, text in enumerate(atom.get("conditions", []), 1))
    rows.extend({
        "component_id": f"{rid}::CRIT-{i:02d}", "component_type": "quantitative_criterion",
        "text": norm(f"{row.get('metric', '')} {row.get('operator', '')} {row.get('threshold', '')} {row.get('unit', '')}"),
    } for i, row in enumerate(atom.get("quantitative_criteria", []), 1))
    return rows


def verification_components(atom: dict[str, Any]) -> list[dict[str, str]]:
    rid = atom["requirement_id"]
    rows = [{"component_id": f"{rid}::VER-METHOD", "component_type": "verification_method", "text": "executable verification method"}]
    criteria = atom.get("quantitative_criteria", [])
    if criteria:
        rows.extend({
            "component_id": f"{rid}::VER-CRIT-{i:02d}", "component_type": "acceptance_criterion",
            "text": norm(f"{criterion.get('metric', '')} {criterion.get('operator', '')} {criterion.get('threshold', '')} {criterion.get('unit', '')}"),
        } for i, criterion in enumerate(criteria, 1))
    else:
        rows.append({"component_id": f"{rid}::VER-CRITERION", "component_type": "acceptance_criterion", "text": "explicit acceptance criterion"})
    rows.extend({"component_id": f"{rid}::VER-COND-{i:02d}", "component_type": "verification_condition", "text": text}
                for i, text in enumerate(atom.get("conditions", []), 1))
    return rows


def atom_schema(requirement_ids: list[str]) -> dict[str, Any]:
    evidence = {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"enum": requirement_ids}}
    criterion = {
        "type": "object", "additionalProperties": False,
        "required": ["metric", "operator", "threshold", "unit"],
        "properties": {k: {"type": "string"} for k in ["metric", "operator", "threshold", "unit"]},
    }
    atom = {
        "type": "object", "additionalProperties": False,
        "required": ["requirement_id", "requirement_object", "required_action", "normative_strength",
                     "lifecycle_state", "conditions", "quantitative_criteria", "verification_expectations",
                     "requirement_evidence_ids", "ambiguities"],
        "properties": {
            "requirement_id": {"type": "string", "pattern": "^R-[0-9]{3}$"},
            "requirement_object": {"type": "string", "minLength": 1},
            "required_action": {"type": "string", "minLength": 1},
            "normative_strength": {"enum": sorted(STRENGTHS)},
            "lifecycle_state": {"enum": sorted(LIFECYCLES)},
            "conditions": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "quantitative_criteria": {"type": "array", "items": criterion},
            "verification_expectations": {"type": "array", "items": {"type": "string", "minLength": 1}},
            "requirement_evidence_ids": evidence,
            "ambiguities": {"type": "array", "items": {"type": "string", "minLength": 1}},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
        "additionalProperties": False, "required": ["contract", "requirements"],
        "properties": {"contract": {"const": ATOM_CONTRACT}, "requirements": {"type": "array", "minItems": 1, "items": atom}},
    }


def coverage_schema(atoms: list[dict[str, Any]], candidates: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    observed_criterion = {
        "oneOf": [
            {"type": "object", "additionalProperties": False,
             "required": ["metric", "operator", "threshold", "unit"],
             "properties": {
                 "metric": {"type": "string", "minLength": 1},
                 "operator": {"enum": [">=", ">", "<=", "<", "=", "=="]},
                 "threshold": {"type": "string", "minLength": 1},
                 "unit": {"type": "string", "minLength": 1},
             }},
            {"type": "null"},
        ]
    }
    variants = []
    for atom in atoms:
        rid = atom["requirement_id"]
        sol_ids = [x["evidence_id"] for x in candidates[rid]["solution"]]
        ver_ids = [x["evidence_id"] for x in candidates[rid]["verification"]]
        sol_components = solution_components(atom)
        ver_components = verification_components(atom)
        sol_variants = [{
            "type": "object", "additionalProperties": False,
            "required": ["component_id", "status", "claim_lifecycle_state", "evidence_ids", "rationale"]
                        + (["observed_criterion"] if component["component_type"] == "quantitative_criterion" else []),
            "properties": {
                "component_id": {"const": component["component_id"]},
                "status": {"enum": sorted(COMPONENT_STATUSES)},
                "claim_lifecycle_state": {"enum": sorted(LIFECYCLES)},
                "evidence_ids": {"type": "array", "uniqueItems": True, "items": {"enum": sol_ids}},
                "rationale": {"type": "string", "minLength": 1},
                **({"observed_criterion": observed_criterion} if component["component_type"] == "quantitative_criterion" else {}),
            },
        } for component in sol_components]
        ver_variants = [{
            "type": "object", "additionalProperties": False,
            "required": ["component_id", "status", "evidence_ids", "rationale"]
                        + (["observed_criterion"] if component["component_type"] == "acceptance_criterion" else []),
            "properties": {
                "component_id": {"const": component["component_id"]},
                "status": {"enum": sorted(VERIFICATION_COMPONENT_STATUSES)},
                "evidence_ids": {"type": "array", "uniqueItems": True, "items": {"enum": ver_ids}},
                "rationale": {"type": "string", "minLength": 1},
                **({"observed_criterion": observed_criterion} if component["component_type"] == "acceptance_criterion" else {}),
            },
        } for component in ver_components]
        variants.append({
            "type": "object", "additionalProperties": False,
            "required": ["requirement_id", "solution_components", "verification_components", "unresolved_gaps", "conflicts"],
            "properties": {
                "requirement_id": {"const": rid},
                "solution_components": {"type": "array", "minItems": len(sol_components), "maxItems": len(sol_components), "items": {"oneOf": sol_variants}},
                "verification_components": {"type": "array", "minItems": len(ver_components), "maxItems": len(ver_components), "items": {"oneOf": ver_variants}},
                "unresolved_gaps": {"type": "array", "items": {"type": "string", "minLength": 1}},
                "conflicts": {"type": "array", "items": {"type": "string", "minLength": 1}},
            },
        })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
        "additionalProperties": False, "required": ["contract", "decisions"],
        "properties": {"contract": {"const": COVERAGE_CONTRACT}, "decisions": {"type": "array", "minItems": len(atoms), "maxItems": len(atoms), "items": {"oneOf": variants}}},
    }


def validate_atoms(raw: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    errors, seen, valid = [], set(), set(id_map(registry))
    if raw.get("contract") != ATOM_CONTRACT:
        errors.append("contract_mismatch")
    atoms = raw.get("requirements")
    if not isinstance(atoms, list) or not atoms:
        return errors + ["requirements_missing"]
    required = {"requirement_id", "requirement_object", "required_action", "normative_strength", "lifecycle_state",
                "conditions", "quantitative_criteria", "verification_expectations", "requirement_evidence_ids", "ambiguities"}
    for i, atom in enumerate(atoms):
        p = f"requirements[{i}]"
        if not isinstance(atom, dict): errors.append(f"{p}:not_object"); continue
        missing = required - set(atom)
        errors.extend(f"{p}:missing:{x}" for x in sorted(missing))
        rid = atom.get("requirement_id")
        if not isinstance(rid, str) or not re.fullmatch(r"R-\d{3}", rid): errors.append(f"{p}:bad_requirement_id")
        elif rid in seen: errors.append(f"{p}:duplicate_requirement_id")
        else: seen.add(rid)
        if atom.get("normative_strength") not in STRENGTHS: errors.append(f"{p}:bad_normative_strength")
        if atom.get("lifecycle_state") not in LIFECYCLES: errors.append(f"{p}:bad_lifecycle_state")
        ids = atom.get("requirement_evidence_ids", [])
        if not ids: errors.append(f"{p}:missing_requirement_evidence")
        for eid in ids:
            if eid not in valid: errors.append(f"{p}:unknown_requirement_evidence:{eid}")
    return errors


def derive_invariants(atom: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    """Derive deterministic requirement/solution/test consistency failures."""
    failures: list[dict[str, str]] = []
    sol_map = {x["component_id"]: x for x in row["solution_components"]}
    ver_map = {x["component_id"]: x for x in row["verification_components"]}
    rid = atom["requirement_id"]
    for i, requirement in enumerate(atom.get("quantitative_criteria", []), 1):
        sol_id, ver_id = f"{rid}::CRIT-{i:02d}", f"{rid}::VER-CRIT-{i:02d}"
        sol = sol_map.get(sol_id, {})
        ver = ver_map.get(ver_id, {})
        failures.extend(criterion_invariant(requirement, sol.get("observed_criterion"), "solution", sol_id))
        failures.extend(criterion_invariant(requirement, ver.get("observed_criterion"), "verification", ver_id))
    return failures


def expected_release(strength: str, solution: str, verification: str, ambiguous: bool,
                     invariant_failures: list[dict[str, str]]) -> tuple[str, bool]:
    if invariant_failures: return "block_invariant_failure", True
    if solution == "conflicting" or verification == "conflicting": return "block_conflict", True
    if strength == "must" and solution != "full": return "block_missing_solution", True
    if strength == "must" and verification != "executable": return "block_missing_verification", True
    if solution == "absent": return "block_missing_solution", True
    if verification == "missing" or (solution == "full" and verification != "executable"): return "block_missing_verification", True
    if solution == "full" and verification == "executable" and not ambiguous: return "pass_with_evidence", False
    return "human_review", True


def derive_statuses(atom: dict[str, Any], row: dict[str, Any], review_stage: str) -> dict[str, Any]:
    sol_statuses = []
    lifecycle_mismatches = []
    for component in row["solution_components"]:
        status = component["status"]
        lifecycle = component["claim_lifecycle_state"]
        if review_stage == "acceptance_review" and status in {"covered", "partial"} and lifecycle != "current":
            lifecycle_mismatches.append(component["component_id"])
            status = "unverifiable"
        sol_statuses.append(status)
    ver_statuses = [x["status"] for x in row["verification_components"]]
    if "conflicting" in sol_statuses:
        solution = "conflicting"
    elif "unverifiable" in sol_statuses:
        solution = "unverifiable"
    elif sol_statuses and all(x == "covered" for x in sol_statuses):
        solution = "full"
    elif sol_statuses and all(x == "absent" for x in sol_statuses):
        solution = "absent"
    else:
        solution = "partial"
    if "conflicting" in ver_statuses:
        verification = "conflicting"
    elif "unverifiable" in ver_statuses:
        verification = "partial"
    elif ver_statuses and all(x == "supported" for x in ver_statuses):
        verification = "executable"
    elif ver_statuses and all(x == "missing" for x in ver_statuses):
        verification = "missing"
    else:
        verification = "partial"
    invariant_failures = derive_invariants(atom, row)
    ambiguous = bool(atom.get("ambiguities") or row.get("unresolved_gaps") or row.get("conflicts"))
    release, human = expected_release(
        atom.get("normative_strength", "must"), solution, verification, ambiguous, invariant_failures,
    )
    reason_codes = []
    if solution != "full": reason_codes.append(f"solution_{solution}")
    if verification != "executable": reason_codes.append(f"verification_{verification}")
    if atom.get("ambiguities"): reason_codes.append("source_ambiguity")
    if row.get("unresolved_gaps"): reason_codes.append("unresolved_gap")
    if row.get("conflicts"): reason_codes.append("source_or_claim_conflict")
    if lifecycle_mismatches: reason_codes.append("lifecycle_mismatch")
    reason_codes.extend(x["code"] for x in invariant_failures)
    required_actions = []
    for failure in invariant_failures:
        if failure["code"].startswith("solution_") and "recheck_solution_commitment" not in required_actions:
            required_actions.append("recheck_solution_commitment")
        if failure["code"].startswith("verification_") and "recheck_acceptance_criterion" not in required_actions:
            required_actions.append("recheck_acceptance_criterion")
    if lifecycle_mismatches: required_actions.append("confirm_capability_lifecycle")
    if ambiguous: required_actions.append("human_confirm_source_gap")
    return {
        "solution_coverage": solution,
        "verification_readiness": verification,
        "release_decision": release,
        "human_review_required": human,
        "lifecycle_mismatch_component_ids": lifecycle_mismatches,
        "review_reason_codes": reason_codes,
        "failed_invariants": invariant_failures,
        "required_actions": required_actions,
    }


def validate_coverage(raw: dict[str, Any], atoms: list[dict[str, Any]], candidates: dict[str, Any]) -> list[str]:
    errors, seen = [], set()
    if raw.get("contract") != COVERAGE_CONTRACT: errors.append("contract_mismatch")
    decisions = raw.get("decisions")
    if not isinstance(decisions, list): return errors + ["decisions_missing"]
    atom_map = {a["requirement_id"]: a for a in atoms}
    for i, row in enumerate(decisions):
        p, rid = f"decisions[{i}]", row.get("requirement_id") if isinstance(row, dict) else None
        if rid not in atom_map: errors.append(f"{p}:unknown_requirement_id:{rid}"); continue
        if rid in seen: errors.append(f"{p}:duplicate_requirement_id:{rid}")
        seen.add(rid)
        allowed_sol = {x["evidence_id"] for x in candidates[rid]["solution"]}
        allowed_ver = {x["evidence_id"] for x in candidates[rid]["verification"]}
        expected_sol = {x["component_id"] for x in solution_components(atom_map[rid])}
        expected_ver = {x["component_id"] for x in verification_components(atom_map[rid])}
        for field, expected_ids, allowed_ids, status_set, evidence_statuses in [
            ("solution_components", expected_sol, allowed_sol, COMPONENT_STATUSES, {"covered", "partial", "conflicting", "unverifiable"}),
            ("verification_components", expected_ver, allowed_ver, VERIFICATION_COMPONENT_STATUSES, {"supported", "partial", "conflicting", "unverifiable"}),
        ]:
            components = row.get(field, [])
            if not isinstance(components, list): errors.append(f"{p}:{field}_missing"); continue
            actual_ids = [x.get("component_id") for x in components if isinstance(x, dict)]
            if len(actual_ids) != len(set(actual_ids)): errors.append(f"{p}:{field}_duplicate_component")
            for cid in sorted(expected_ids - set(actual_ids)): errors.append(f"{p}:{field}_missing:{cid}")
            for cid in sorted(set(actual_ids) - expected_ids): errors.append(f"{p}:{field}_unknown:{cid}")
            for j, component in enumerate(components):
                cp = f"{p}:{field}[{j}]"
                status = component.get("status")
                ids = component.get("evidence_ids", [])
                if status not in status_set: errors.append(f"{cp}:bad_status")
                for eid in ids:
                    if eid not in allowed_ids: errors.append(f"{cp}:evidence_out_of_scope:{eid}")
                if status in evidence_statuses and not ids: errors.append(f"{cp}:status_without_evidence")
                if status in {"absent", "missing"} and ids: errors.append(f"{cp}:absence_with_evidence")
                if field == "solution_components" and component.get("claim_lifecycle_state") not in LIFECYCLES:
                    errors.append(f"{cp}:bad_claim_lifecycle_state")
                is_criterion = (
                    field == "solution_components" and isinstance(component.get("component_id"), str)
                    and "::CRIT-" in component["component_id"]
                ) or (
                    field == "verification_components" and (
                        "::VER-CRIT-" in component.get("component_id", "")
                        or component.get("component_id", "").endswith("::VER-CRITERION")
                    )
                )
                if is_criterion:
                    observed = component.get("observed_criterion")
                    if "observed_criterion" not in component:
                        errors.append(f"{cp}:observed_criterion_missing")
                    elif status in evidence_statuses and observed is None:
                        errors.append(f"{cp}:supported_criterion_without_value")
                    elif status in {"absent", "missing"} and observed is not None:
                        errors.append(f"{cp}:absent_criterion_with_value")
                    elif observed is not None:
                        required_keys = {"metric", "operator", "threshold", "unit"}
                        if not isinstance(observed, dict) or set(observed) != required_keys:
                            errors.append(f"{cp}:bad_observed_criterion_shape")
        if not isinstance(row.get("unresolved_gaps"), list): errors.append(f"{p}:unresolved_gaps_missing")
        if not isinstance(row.get("conflicts"), list): errors.append(f"{p}:conflicts_missing")
    missing = set(atom_map) - seen
    errors.extend(f"missing_decision:{rid}" for rid in sorted(missing))
    return errors


def freeze_raw(src: Path, dst: Path) -> None:
    if dst.exists(): raise Refusal(f"raw artifact already exists: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def prepare(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve()
    if run.exists() and any(run.iterdir()): raise Refusal("prepare requires an empty run directory")
    run.mkdir(parents=True, exist_ok=True)
    regs = {
        "requirement": import_markdown(args.requirements.resolve(), "requirement"),
        "solution": import_markdown(args.solution.resolve(), "solution"),
        "verification": import_markdown(args.verification.resolve(), "verification"),
    }
    for role, reg in regs.items(): write_json(run / "frozen" / f"{role}-registry.json", reg)
    ids = [x["evidence_id"] for x in regs["requirement"]["entries"]]
    schema = atom_schema(ids); write_json(run / "schemas" / "requirement-atoms.schema.json", schema)
    request = {
        "request_contract": "SolutionScope-v2.2-requirement-atomization-request",
        "instruction": "Return one JSON object matching output_schema. Split compound source clauses into independently auditable obligations. Preserve shared conditions. Use only supplied requirement evidence. Do not inspect or assess the solution or verification plan.",
        "output_schema_path": str((run / "schemas" / "requirement-atoms.schema.json").resolve()),
        "requirement_registry": regs["requirement"],
        "declared_output_name": "requirement-atoms.json",
    }
    write_json(run / "requests" / "requirement-atomization.json", request)
    write_json(run / "run-record.json", {"version": VERSION, "status": "requirement_atomization_prepared", "top_k": args.top_k, "review_stage": args.review_stage, "raw_outputs": []})


def register_requirements(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = read_json(run / "run-record.json")
    if record["status"] != "requirement_atomization_prepared": raise Refusal("run is not ready for requirement registration")
    req_reg = read_json(run / "frozen" / "requirement-registry.json")
    raw = read_json(args.raw.resolve()); errors = validate_atoms(raw, req_reg)
    write_json(run / "validation" / "requirement-atoms.json", {"errors": errors, "error_count": len(errors)})
    if errors: raise Refusal(f"requirement atom gate failed with {len(errors)} errors")
    dst = run / "raw" / "requirement-atoms.json"; freeze_raw(args.raw.resolve(), dst)
    atoms = raw["requirements"]
    sol = read_json(run / "frozen" / "solution-registry.json")
    ver = read_json(run / "frozen" / "verification-registry.json")
    candidates = {}
    for atom in atoms:
        q = atom_query(atom)
        candidates[atom["requirement_id"]] = {
            "solution": hybrid_retrieve(q, sol["entries"], int(record["top_k"])),
            "verification": hybrid_retrieve(q, ver["entries"], int(record["top_k"])),
        }
    write_json(run / "derived" / "coverage-candidates.json", candidates)
    schema = coverage_schema(atoms, candidates); write_json(run / "schemas" / "coverage-decisions.schema.json", schema)
    request = {
        "request_contract": "SolutionScope-v2.2-coverage-adjudication-request",
        "instruction": f"Return one JSON object matching output_schema. Review stage is {record['review_stage']}. For every atomic requirement, judge every listed solution and verification component separately. For each quantitative solution or acceptance component, copy the metric, operator, threshold, and unit actually stated in role-specific evidence into observed_criterion; use null when absent. Never copy the requirement value merely because it is expected. Preserve each solution claim's lifecycle state. Cite only the supplied role-specific candidates for that requirement. A requirement source never proves implementation. Do not emit aggregate coverage or release decisions; deterministic code derives them. Do not fill missing facts. Use absent/missing and unresolved_gaps when evidence is not present.",
        "review_stage": record["review_stage"],
        "output_schema_path": str((run / "schemas" / "coverage-decisions.schema.json").resolve()),
        "requirements": atoms, "candidate_evidence_by_requirement": candidates,
        "declared_output_name": "coverage-decisions.json",
    }
    write_json(run / "requests" / "coverage-adjudication.json", request)
    record.update({"status": "coverage_adjudication_prepared", "requirement_count": len(atoms), "raw_outputs": [str(dst)]})
    write_json(run / "run-record.json", record)


def complete(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = read_json(run / "run-record.json")
    if record["status"] != "coverage_adjudication_prepared": raise Refusal("run is not ready for coverage completion")
    atoms_raw = read_json(run / "raw" / "requirement-atoms.json")
    candidates = read_json(run / "derived" / "coverage-candidates.json")
    raw = read_json(args.raw.resolve()); errors = validate_coverage(raw, atoms_raw["requirements"], candidates)
    write_json(run / "validation" / "coverage-decisions.json", {"errors": errors, "error_count": len(errors)})
    if errors: raise Refusal(f"coverage gate failed with {len(errors)} errors")
    dst = run / "raw" / "coverage-decisions.json"; freeze_raw(args.raw.resolve(), dst)
    regs = {}
    for role in ROLES: regs.update(id_map(read_json(run / "frozen" / f"{role}-registry.json")))
    decision_map = {x["requirement_id"]: x for x in raw["decisions"]}
    rows = []
    for atom in atoms_raw["requirements"]:
        adjudication = decision_map[atom["requirement_id"]]
        derived = derive_statuses(atom, adjudication, record["review_stage"])
        evidence = list(atom["requirement_evidence_ids"])
        for component in adjudication["solution_components"] + adjudication["verification_components"]:
            evidence.extend(component["evidence_ids"])
        evidence = list(dict.fromkeys(evidence))
        rows.append({"requirement": atom, "adjudication": adjudication, "decision": derived, "evidence": [regs[eid] for eid in evidence]})
    summary = Counter(r["decision"]["release_decision"] for r in rows)
    matrix = {"contract": "SolutionScope-v2.2-auditable-coverage-matrix", "version": VERSION, "review_stage": record["review_stage"], "rows": rows,
              "summary": dict(sorted(summary.items())), "release_ready": all(r["decision"]["release_decision"] == "pass_with_evidence" for r in rows)}
    write_json(run / "final" / "coverage-matrix.json", matrix)
    ui_rows = [{
        "requirement_id": row["requirement"]["requirement_id"],
        "requirement": norm(f"{row['requirement']['requirement_object']} · {row['requirement']['required_action']}"),
        "solution_coverage": row["decision"]["solution_coverage"],
        "verification_readiness": row["decision"]["verification_readiness"],
        "release_decision": row["decision"]["release_decision"],
        "reason_codes": row["decision"]["review_reason_codes"],
        "failed_invariants": row["decision"]["failed_invariants"],
        "required_actions": row["decision"]["required_actions"],
        "requirement_evidence_count": len(row["requirement"]["requirement_evidence_ids"]),
        "solution_evidence_count": sum(len(x["evidence_ids"]) for x in row["adjudication"]["solution_components"]),
        "verification_evidence_count": sum(len(x["evidence_ids"]) for x in row["adjudication"]["verification_components"]),
    } for row in rows]
    write_json(run / "final" / "ui-coverage-payload.json", {
        "contract": "SolutionScope-v2.2-ui-coverage-payload", "review_stage": record["review_stage"],
        "release_ready": matrix["release_ready"], "summary": matrix["summary"], "rows": ui_rows,
    })
    record.update({"status": "complete", "raw_outputs": record["raw_outputs"] + [str(dst)], "release_ready": matrix["release_ready"]})
    write_json(run / "run-record.json", record)


def change_schema(old_ids: list[str], new_ids: list[str]) -> dict[str, Any]:
    row = {
        "type": "object", "additionalProperties": False,
        "required": ["change_id", "change_type", "old_requirement_ids", "new_requirement_ids", "rationale"],
        "properties": {
            "change_id": {"type": "string", "pattern": "^C-[0-9]{3}$"},
            "change_type": {"enum": ["unchanged", "modified", "added", "removed", "split", "merged"]},
            "old_requirement_ids": {"type": "array", "uniqueItems": True, "items": {"enum": old_ids}},
            "new_requirement_ids": {"type": "array", "uniqueItems": True, "items": {"enum": new_ids}},
            "rationale": {"type": "string", "minLength": 1},
        },
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False,
            "required": ["contract", "changes"], "properties": {"contract": {"const": CHANGE_CONTRACT},
            "changes": {"type": "array", "minItems": 1, "items": row}}}


def prepare_change_impact(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve()
    if run.exists() and any(run.iterdir()): raise Refusal("prepare-change-impact requires an empty run directory")
    run.mkdir(parents=True, exist_ok=True)
    old, new, prior = read_json(args.old_atoms.resolve()), read_json(args.new_atoms.resolve()), read_json(args.prior_matrix.resolve())
    if old.get("contract") != ATOM_CONTRACT or new.get("contract") != ATOM_CONTRACT:
        raise Refusal("old and new atoms must use the v2.2 atom contract")
    old_ids = [x["requirement_id"] for x in old["requirements"]]
    new_ids = [x["requirement_id"] for x in new["requirements"]]
    schema = change_schema(old_ids, new_ids)
    write_json(run / "frozen" / "old-atoms.json", old); write_json(run / "frozen" / "new-atoms.json", new)
    write_json(run / "frozen" / "prior-matrix.json", prior); write_json(run / "schemas" / "change-alignment.schema.json", schema)
    write_json(run / "requests" / "change-alignment.json", {
        "request_contract": "SolutionScope-v2.2-change-impact-request",
        "instruction": "Align old and new atomic requirements by meaning, not by ID. Account for every old and new requirement. Use split or merged when one-to-many or many-to-one. Do not assess implementation or verification here.",
        "output_schema_path": str((run / "schemas" / "change-alignment.schema.json").resolve()),
        "old_requirements": old["requirements"], "new_requirements": new["requirements"],
    })
    write_json(run / "run-record.json", {"version": VERSION, "status": "change_alignment_prepared", "raw_outputs": []})


def validate_changes(raw: dict[str, Any], old_ids: set[str], new_ids: set[str]) -> list[str]:
    errors, seen_change, covered_old, covered_new = [], set(), [], []
    if raw.get("contract") != CHANGE_CONTRACT: errors.append("contract_mismatch")
    rows = raw.get("changes")
    if not isinstance(rows, list): return errors + ["changes_missing"]
    for i, row in enumerate(rows):
        p = f"changes[{i}]"; cid = row.get("change_id") if isinstance(row, dict) else None
        if cid in seen_change: errors.append(f"{p}:duplicate_change_id")
        seen_change.add(cid)
        kind = row.get("change_type")
        old = row.get("old_requirement_ids", []); new = row.get("new_requirement_ids", [])
        if any(x not in old_ids for x in old): errors.append(f"{p}:unknown_old_requirement")
        if any(x not in new_ids for x in new): errors.append(f"{p}:unknown_new_requirement")
        expected = {
            "added": lambda old_count, new_count: old_count == 0 and new_count >= 1,
            "removed": lambda old_count, new_count: old_count >= 1 and new_count == 0,
            "unchanged": lambda old_count, new_count: old_count == 1 and new_count == 1,
            "modified": lambda old_count, new_count: old_count == 1 and new_count == 1,
            "split": lambda old_count, new_count: old_count == 1 and new_count >= 2,
            "merged": lambda old_count, new_count: old_count >= 2 and new_count == 1,
        }
        if kind not in expected: errors.append(f"{p}:bad_change_type")
        elif not expected[kind](len(old), len(new)):
            errors.append(f"{p}:bad_change_shape:{kind}")
        covered_old.extend(old); covered_new.extend(new)
    for rid in sorted(old_ids - set(covered_old)): errors.append(f"old_requirement_unmapped:{rid}")
    for rid in sorted(new_ids - set(covered_new)): errors.append(f"new_requirement_unmapped:{rid}")
    if len(covered_old) != len(set(covered_old)): errors.append("old_requirement_mapped_multiple_times")
    if len(covered_new) != len(set(covered_new)): errors.append("new_requirement_mapped_multiple_times")
    return errors


def complete_change_impact(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = read_json(run / "run-record.json")
    if record["status"] != "change_alignment_prepared": raise Refusal("change-impact run is not ready")
    old, new = read_json(run / "frozen" / "old-atoms.json"), read_json(run / "frozen" / "new-atoms.json")
    prior = read_json(run / "frozen" / "prior-matrix.json"); raw = read_json(args.raw.resolve())
    errors = validate_changes(raw, {x["requirement_id"] for x in old["requirements"]}, {x["requirement_id"] for x in new["requirements"]})
    write_json(run / "validation" / "change-alignment.json", {"errors": errors, "error_count": len(errors)})
    if errors: raise Refusal(f"change alignment gate failed with {len(errors)} errors")
    dst = run / "raw" / "change-alignment.json"; freeze_raw(args.raw.resolve(), dst)
    prior_rows = {x["requirement"]["requirement_id"]: x for x in prior.get("rows", [])}
    worklist = []
    for change in raw["changes"]:
        kind = change["change_type"]; old_rows = [prior_rows[x] for x in change["old_requirement_ids"] if x in prior_rows]
        worklist.append({
            **change,
            "release_held": kind != "unchanged",
            "required_actions": [] if kind == "unchanged" else ["recheck_solution_coverage", "recheck_verification_plan", "human_confirm_change"],
            "previous_release_decisions": [x["decision"]["release_decision"] for x in old_rows],
            "previous_evidence_ids": sorted({e["evidence_id"] for x in old_rows for e in x.get("evidence", [])}),
        })
    write_json(run / "final" / "change-impact-worklist.json", {"contract": "SolutionScope-v2.2-change-impact-worklist", "version": VERSION,
               "release_held": any(x["release_held"] for x in worklist), "changes": worklist})
    record.update({"status": "complete", "raw_outputs": [str(dst)]}); write_json(run / "run-record.json", record)


def prepare_baseline(args: argparse.Namespace) -> None:
    """Prepare a fair one-pass direct-RAG comparator using the same registries."""
    run = args.run_dir.resolve()
    if run.exists() and any(run.iterdir()): raise Refusal("prepare-baseline requires an empty run directory")
    run.mkdir(parents=True, exist_ok=True)
    regs = {role: import_markdown(getattr(args, role).resolve(), role) for role in ROLES}
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False,
              "required": ["contract", "review"], "properties": {"contract": {"const": BASELINE_CONTRACT},
              "review": {"type": "array", "items": {"type": "object", "additionalProperties": False,
              "required": ["requirement", "answer", "recommendation", "evidence_ids"], "properties": {
              "requirement": {"type": "string"}, "answer": {"type": "string"},
              "recommendation": {"enum": ["pass", "needs_review", "block"]},
              "evidence_ids": {"type": "array", "uniqueItems": True, "items": {"enum": sorted(e for reg in regs.values() for e in id_map(reg))}}}}}}}
    write_json(run / "schemas" / "direct-rag-review.schema.json", schema)
    write_json(run / "requests" / "direct-rag-review.json", {"request_contract": "SolutionScope-v2.2-fair-direct-rag-baseline",
        "instruction": "In one pass, compare the requirements with the proposed solution and verification plan. Answer whether each requirement is covered and cite evidence. Do not use SolutionScope atomization, component routing, lifecycle gate, or deterministic release logic.",
        "output_schema_path": str((run / "schemas" / "direct-rag-review.schema.json").resolve()), "registries": regs})
    write_json(run / "run-record.json", {"version": VERSION, "status": "direct_rag_baseline_prepared", "raw_outputs": []})


def self_test(_: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="solutionscope-v2-2-") as tmp:
        root = Path(tmp); run = root / "run"
        req = root / "requirements.md"; sol = root / "solution.md"; ver = root / "verification.md"
        req.write_text("<!-- source_page: 1 -->\n# Requirements\nThe system shall detect vessels at 4 km with recognition rate >= 92%.\n", encoding="utf-8")
        sol.write_text("<!-- source_page: 2 -->\n# Solution\nThe perception module detects vessels using fused camera and radar inputs at 4 km with recognition rate >= 90%.\n", encoding="utf-8")
        ver.write_text("<!-- source_page: 3 -->\n# Test\nMeasure recognition rate over 100 labelled vessel encounters; pass when recognition rate is >= 92%.\n", encoding="utf-8")
        prepare(argparse.Namespace(run_dir=run, requirements=req, solution=sol, verification=ver, top_k=5, review_stage="acceptance_review"))
        req_id = read_json(run / "frozen" / "requirement-registry.json")["entries"][0]["evidence_id"]
        atoms = {"contract": ATOM_CONTRACT, "requirements": [{"requirement_id": "R-001", "requirement_object": "vessel perception", "required_action": "detect vessels", "normative_strength": "must", "lifecycle_state": "current", "conditions": ["at 4 km"], "quantitative_criteria": [{"metric": "recognition rate", "operator": ">=", "threshold": "92", "unit": "%"}], "verification_expectations": ["labelled vessel encounters"], "requirement_evidence_ids": [req_id], "ambiguities": []}]}
        atom_path = root / "atoms.json"; write_json(atom_path, atoms)
        register_requirements(argparse.Namespace(run_dir=run, raw=atom_path))
        cands = read_json(run / "derived" / "coverage-candidates.json")["R-001"]
        if not cands["solution"] or not cands["verification"]: raise AssertionError("retrieval produced no candidates")
        sol_id, ver_id = cands["solution"][0]["evidence_id"], cands["verification"][0]["evidence_id"]
        decisions = {"contract": COVERAGE_CONTRACT, "decisions": [{
            "requirement_id": "R-001",
            "solution_components": [
                {"component_id": "R-001::ACTION", "status": "covered", "claim_lifecycle_state": "current", "evidence_ids": [sol_id], "rationale": "Detection is specified."},
                {"component_id": "R-001::COND-01", "status": "covered", "claim_lifecycle_state": "current", "evidence_ids": [sol_id], "rationale": "The 4 km condition is specified."},
                {"component_id": "R-001::CRIT-01", "status": "covered", "claim_lifecycle_state": "current", "evidence_ids": [sol_id], "rationale": "The solution states a weaker 90 percent threshold.",
                 "observed_criterion": {"metric": "recognition rate", "operator": ">=", "threshold": "90", "unit": "%"}},
            ],
            "verification_components": [
                {"component_id": "R-001::VER-METHOD", "status": "supported", "evidence_ids": [ver_id], "rationale": "A labelled encounter test is defined."},
                {"component_id": "R-001::VER-CRIT-01", "status": "supported", "evidence_ids": [ver_id], "rationale": "A 92 percent threshold is defined.",
                 "observed_criterion": {"metric": "recognition rate", "operator": ">=", "threshold": "92", "unit": "%"}},
                {"component_id": "R-001::VER-COND-01", "status": "partial", "evidence_ids": [ver_id], "rationale": "The test does not explicitly restate the 4 km condition."},
            ],
            "unresolved_gaps": ["The solution threshold is weaker than the requirement and the test does not bind the 4 km condition."],
            "conflicts": [],
        }]}
        coverage_path = root / "coverage.json"; write_json(coverage_path, decisions)
        complete(argparse.Namespace(run_dir=run, raw=coverage_path))
        final = read_json(run / "final" / "coverage-matrix.json")
        assert final["release_ready"] is False and len(final["rows"]) == 1
        assert final["rows"][0]["decision"]["solution_coverage"] == "full"
        assert final["rows"][0]["decision"]["verification_readiness"] == "partial"
        assert final["rows"][0]["decision"]["release_decision"] == "block_invariant_failure"
        assert final["rows"][0]["decision"]["failed_invariants"][0]["code"] == "solution_threshold_not_satisfied"
        invalid = json.loads(json.dumps(decisions))
        invalid["decisions"][0]["solution_components"][0]["evidence_ids"] = [ver_id]
        invalid_errors = validate_coverage(invalid, atoms["requirements"], {"R-001": cands})
        assert any("evidence_out_of_scope" in error for error in invalid_errors)
        incomplete = json.loads(json.dumps(decisions))
        incomplete["decisions"][0]["verification_components"].pop()
        incomplete_errors = validate_coverage(incomplete, atoms["requirements"], {"R-001": cands})
        assert any("verification_components_missing" in error for error in incomplete_errors)
        ranked = hybrid_retrieve("recognition rate >= 92% current", read_json(run / "frozen" / "verification-registry.json")["entries"], 3)
        assert ranked and "metric_overlap" in ranked[0]["retrieval_reasons"]
        assert criterion_invariant(
            {"metric": "latency", "operator": "<=", "threshold": "600", "unit": "ms"},
            {"metric": "latency", "operator": "<=", "threshold": "0.6", "unit": "s"},
            "verification", "R-UNIT::VER-CRIT-01",
        ) == []
        assert criterion_invariant(
            {"metric": "recognition rate", "operator": ">=", "threshold": "92", "unit": "%"},
            {"metric": "recognition rate", "operator": ">=", "threshold": "90", "unit": "%"},
            "solution", "R-WEAK::CRIT-01",
        )[0]["code"] == "solution_threshold_not_satisfied"

        new_atoms = json.loads(json.dumps(atoms)); new_atoms["requirements"][0]["quantitative_criteria"][0]["threshold"] = "95"
        change_run = root / "change"; new_path = root / "new-atoms.json"; write_json(new_path, new_atoms)
        prepare_change_impact(argparse.Namespace(run_dir=change_run, old_atoms=atom_path, new_atoms=new_path,
                                                 prior_matrix=run / "final" / "coverage-matrix.json"))
        changes = {"contract": CHANGE_CONTRACT, "changes": [{"change_id": "C-001", "change_type": "modified",
                   "old_requirement_ids": ["R-001"], "new_requirement_ids": ["R-001"],
                   "rationale": "The recognition threshold changed from 92 to 95 percent."}]}
        change_path = root / "changes.json"; write_json(change_path, changes)
        complete_change_impact(argparse.Namespace(run_dir=change_run, raw=change_path))
        impact = read_json(change_run / "final" / "change-impact-worklist.json")
        assert impact["release_held"] is True
        assert impact["changes"][0]["required_actions"] == ["recheck_solution_coverage", "recheck_verification_plan", "human_confirm_change"]
        invalid_change = json.loads(json.dumps(changes))
        invalid_change["changes"][0]["change_type"] = "split"
        invalid_change_errors = validate_changes(invalid_change, {"R-001"}, {"R-001"})
        assert any("bad_change_shape:split" in error for error in invalid_change_errors)
    print("SolutionScope v2.2 self-test: PASS")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("prepare"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--requirements", type=Path, required=True); x.add_argument("--solution", type=Path, required=True); x.add_argument("--verification", type=Path, required=True); x.add_argument("--top-k", type=int, default=8); x.add_argument("--review-stage", choices=sorted(REVIEW_STAGES), default="acceptance_review"); x.set_defaults(func=prepare)
    x = sub.add_parser("register-requirements"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--raw", type=Path, required=True); x.set_defaults(func=register_requirements)
    x = sub.add_parser("complete"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--raw", type=Path, required=True); x.set_defaults(func=complete)
    x = sub.add_parser("prepare-change-impact"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--old-atoms", type=Path, required=True); x.add_argument("--new-atoms", type=Path, required=True); x.add_argument("--prior-matrix", type=Path, required=True); x.set_defaults(func=prepare_change_impact)
    x = sub.add_parser("complete-change-impact"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--raw", type=Path, required=True); x.set_defaults(func=complete_change_impact)
    x = sub.add_parser("prepare-baseline"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--requirement", type=Path, required=True); x.add_argument("--solution", type=Path, required=True); x.add_argument("--verification", type=Path, required=True); x.set_defaults(func=prepare_baseline)
    x = sub.add_parser("self-test"); x.set_defaults(func=self_test)
    return p


def main() -> None:
    args = parser().parse_args()
    try: args.func(args)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr); raise SystemExit(2)


if __name__ == "__main__": main()
