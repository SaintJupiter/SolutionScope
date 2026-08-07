#!/usr/bin/env python3
"""SolutionScope: deterministic ledger-constrained answer assembly."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.4-public"
STATES = {"current", "planned", "candidate", "normative", "unknown", "conflicted"}
GAPS = {"metric_absent", "metric_statistical_definition_insufficient", "acceptance_method_insufficient", "condition_insufficient", "information_complete", "potential_conflict_or_term_drift", "unclear"}
QUESTIONS = [
    ("Q1", "区分材料中的当前能力、后续规划、候选构想和规范性要求。", ["current_capabilities", "planned_capabilities", "candidate_capabilities", "normative_requirements"]),
    ("Q2", "梳理核心业务链路、模块依赖以及缺失环节。", ["workflow_steps", "module_dependencies", "missing_links"]),
    ("Q3", "找出阻碍测试验收或复现的关键缺口，并按影响排序。", ["ranked_gaps", "acceptance_blockers", "clarification_questions"]),
    ("Q4", "识别重复描述、状态漂移和潜在冲突，保留需要人工确认的内容。", ["duplicates", "state_drift", "potential_conflicts", "human_confirmation"]),
    ("Q5", "若首轮 PoC 只能选择三项能力，给出选择、依赖和取舍，并区分材料事实与业务假设。", ["three_choices", "dependencies", "tradeoffs", "fact_vs_business_assumption"]),
    ("Q6", "列出形成可执行验收仍需确认的信息，不得编造材料中不存在的阈值。", ["acceptance_information_gaps", "no_threshold_invention"]),
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save(run: Path, record: dict[str, Any]) -> None:
    record["updated_at_utc"] = now(); write(run / "workflow_run_record.json", record)


def load(run: Path) -> dict[str, Any]:
    return read(run / "workflow_run_record.json")


def stage(record: dict[str, Any], name: str, **detail: Any) -> None:
    record["stages"].append({"stage_id": f"{record['run_id']}:{len(record['stages']) + 1:02d}:{name}", "stage": name, "created_at_utc": now(), **detail})


def state_for_quote(quote: str) -> str:
    """Classify proposition-level lifecycle wording in Chinese or English."""
    text = quote or ""
    lowered = text.lower()
    if any(x in text for x in ("后续将", "还将", "将增强", "未来将", "下一阶段将")) or any(x in lowered for x in ("will add", "will support", "planned for", "next version")):
        return "planned"
    if any(x in text for x in ("可建设", "可结合", "可建立", "可考虑")) or any(x in lowered for x in ("could add", "may introduce", "can be considered")):
        return "candidate"
    if any(x in text for x in ("应记录", "应当", "必须", "需满足")) or any(x in lowered for x in ("must", "shall", "is required to")):
        return "normative"
    if any(x in text for x in ("当前支持", "当前平台支持", "平台支持", "平台已具备", "系统已支持", "现已支持")) or any(x in lowered for x in ("currently supports", "already supports", "is available")):
        return "current"
    return "unknown"


def question_rows(record: dict[str, Any]) -> list[tuple[str, str, list[str]]]:
    data = read(Path(record["questions_path"]))
    rows = data.get("questions", [])
    parsed: list[tuple[str, str, list[str]]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("question rows must be objects")
        qid = row.get("question_id")
        question = row.get("question")
        components = row.get("instruction_components")
        if not isinstance(qid, str) or not qid or not isinstance(question, str) or not question or not isinstance(components, list) or not components or any(not isinstance(x, str) or not x for x in components):
            raise ValueError("invalid question contract")
        parsed.append((qid, question, components))
    if not parsed or len({row[0] for row in parsed}) != len(parsed):
        raise ValueError("questions must contain unique IDs")
    return parsed


def import_markdown(path: Path) -> dict[str, Any]:
    section = "root"; rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith("#"):
            section = line.lstrip("#").strip() or "root"; continue
        if line.startswith("> "): continue
        rows.append({"page_number": 1, "section": section, "paragraph_id": f"P001-{len(rows) + 1:03d}", "text": line})
    if not rows: raise ValueError("no document paragraphs")
    return {"contract": "SolutionScope-v1.4-local-markdown-import", "document_id": f"DOC-{sha(path)[:12]}", "source_path": str(path), "source_sha256": sha(path), "pagination": "markdown_continuous_page_1", "paragraphs": rows}


def locator_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": ["page_number", "section", "paragraph_id", "quote"], "properties": {"page_number": {"type": "integer"}, "section": {"type": "string"}, "paragraph_id": {"type": "string"}, "quote": {"type": "string"}}}


def ledger_schema() -> dict[str, Any]:
    gap = {"type": "object", "additionalProperties": False, "required": ["gap_kind", "description", "clarification_question", "evidence_locators"], "properties": {"gap_kind": {"enum": sorted(GAPS)}, "description": {"type": "string"}, "clarification_question": {"type": "string"}, "evidence_locators": {"type": "array", "items": {"$ref": "#/$defs/locator"}}}}
    metric = {"type": "object", "additionalProperties": False, "required": ["metric", "comparator", "value", "unit", "condition", "raw_text"], "properties": {k: {"type": ["string", "null"]} for k in ("metric", "comparator", "value", "unit", "condition", "raw_text")}}
    entry = {"type": "object", "additionalProperties": False, "required": ["capability_id", "module", "normalized_capability", "language_state", "evidence_locators", "dependencies", "quantitative_metrics", "acceptance_method", "information_gaps"], "properties": {"capability_id": {"type": "string"}, "module": {"type": "string"}, "normalized_capability": {"type": "string"}, "language_state": {"enum": sorted(STATES)}, "evidence_locators": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/locator"}}, "dependencies": {"type": "array", "items": {"type": "string"}}, "quantitative_metrics": {"type": "array", "items": metric}, "acceptance_method": {"type": ["string", "null"]}, "information_gaps": {"type": "array", "items": gap}}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["contract", "entries"], "properties": {"contract": {"const": "SolutionScope-v1.4-capability-ledger"}, "entries": {"type": "array", "minItems": 1, "items": entry}}, "$defs": {"locator": locator_schema()}}


def fragment_schema(qids: list[str]) -> dict[str, Any]:
    ref = {"type": "array", "minItems": 1, "items": {"type": "string"}}
    finding = {"type": "object", "additionalProperties": False, "required": ["claim", "capability_ids"], "properties": {"claim": {"type": "string"}, "capability_ids": ref}}
    gap = {"type": "object", "additionalProperties": False, "required": ["gap_kind", "description", "clarification_question", "capability_ids"], "properties": {"gap_kind": {"enum": sorted(GAPS)}, "description": {"type": "string"}, "clarification_question": {"type": "string"}, "capability_ids": ref}}
    conflict = {"type": "object", "additionalProperties": False, "required": ["classification", "description", "capability_ids"], "properties": {"classification": {"const": "potential_conflict_or_term_drift"}, "description": {"type": "string"}, "capability_ids": ref}}
    coverage = {"type": "object", "additionalProperties": False, "required": ["component_id", "status", "note"], "properties": {"component_id": {"type": "string"}, "status": {"enum": ["covered", "not_covered", "not_applicable"]}, "note": {"type": ["string", "null"]}}}
    answer = {"type": "object", "additionalProperties": False, "required": ["question_id", "answer_summary", "findings", "information_gaps", "potential_conflicts", "assumptions", "recommendations", "instruction_coverage"], "properties": {"question_id": {"enum": qids}, "answer_summary": {"type": "string"}, "findings": {"type": "array", "items": finding}, "information_gaps": {"type": "array", "items": gap}, "potential_conflicts": {"type": "array", "items": conflict}, "assumptions": {"type": "array", "items": {"type": "string"}}, "recommendations": {"type": "array", "items": {"type": "string"}}, "instruction_coverage": {"type": "array", "items": coverage}}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["contract", "fragments"], "properties": {"contract": {"const": "SolutionScope-v1.4-ledger-constrained-fragments"}, "fragments": {"type": "array", "minItems": len(qids), "maxItems": len(qids), "items": answer}}}


def rows_and_lookup(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[tuple[int, str], dict[str, Any]]]:
    rows = read(Path(record["input_document_path"]))["paragraphs"]
    return rows, {(r["page_number"], r["paragraph_id"]): r for r in rows}


def locator_error(value: Any, rows: list[dict[str, Any]], lookup: dict[tuple[int, str], dict[str, Any]]) -> str | None:
    if not isinstance(value, dict) or set(value) != {"page_number", "section", "paragraph_id", "quote"}: return "locator_format_mismatch"
    target = lookup.get((value.get("page_number"), value.get("paragraph_id")))
    if not target: return "evidence_not_found"
    if value.get("section") != target["section"]: return "locator_misbound"
    quote = re.sub(r"\s+", "", value.get("quote", "")); text = re.sub(r"\s+", "", target["text"])
    return None if quote and quote in text else "locator_misbound"


def validation(kind: str, artifact: Path, record: dict[str, Any], errors: list[dict[str, Any]], risks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"contract": "SolutionScope-v1.4-validation-report", "kind": kind, "artifact_path": str(artifact), "artifact_sha256": sha(artifact) if artifact.is_file() else None, "input_document_sha256": record["input_document_sha256"], "structural_status": "passed" if not errors else "failed", "structural_errors": len(errors), "structural_error_categories": dict(Counter(x["code"] for x in errors)), "structural_findings": errors, "semantic_risk_count": len(risks), "semantic_risk_categories": dict(Counter(x["code"] for x in risks)), "semantic_risks": risks, "human_review_required": bool(risks), "boundary": "Source-bound deterministic validation; not expert review, accuracy, or semantic correctness."}


def validate_ledger(record: dict[str, Any], path: Path) -> dict[str, Any]:
    rows, lookup = rows_and_lookup(record); errors: list[dict[str, Any]] = []; risks: list[dict[str, Any]] = []
    data = read(path); entries = data.get("entries", []) if data.get("contract") == "SolutionScope-v1.4-capability-ledger" else []
    if not entries: errors.append({"code": "ledger_envelope", "path": "root", "message": "v1.4 ledger contract and entries required"})
    ids: set[str] = set(); required = {"capability_id", "module", "normalized_capability", "language_state", "evidence_locators", "dependencies", "quantitative_metrics", "acceptance_method", "information_gaps"}
    for i, entry in enumerate(entries):
        p = f"entries[{i}]"
        if not isinstance(entry, dict) or set(entry) != required or not all(isinstance(entry.get(k), str) and entry[k] for k in ("capability_id", "module", "normalized_capability")) or entry.get("capability_id") in ids or entry.get("language_state") not in STATES:
            errors.append({"code": "ledger_entry_shape", "path": p, "message": "ledger fields, state, and capability ID must be valid"}); continue
        ids.add(entry["capability_id"])
        locs = entry.get("evidence_locators", [])
        if not isinstance(locs, list) or not locs: errors.append({"code": "evidence_locator_missing", "path": p, "message": "ledger entry needs exact source anchor"}); continue
        valid = []
        for j, loc in enumerate(locs):
            code = locator_error(loc, rows, lookup)
            if code: errors.append({"code": code, "path": f"{p}.evidence_locators[{j}]", "message": "exact ledger anchor invalid"})
            else: valid.append(loc)
        states = {state_for_quote(loc["quote"]) for loc in valid}
        if entry["language_state"] == "current" and states and states <= {"planned", "candidate", "normative"}:
            risks.append({"code": "future_or_candidate_promoted_to_current", "severity": "high", "path": p, "message": "current ledger state has only explicit non-current propositions"})
        if entry["language_state"] == "conflicted" and not ({"current", "planned"} <= states or {"current", "candidate"} <= states):
            risks.append({"code": "conflict_state_not_evidenced", "severity": "high", "path": p, "message": "conflicted ledger entry lacks localized opposing propositions"})
    risks.extend(ledger_drifts(entries))
    return validation("ledger", path, record, errors, risks)


def ledger_drifts(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect lifecycle drift without domain-specific keywords."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("normalized_capability"), str):
            key = re.sub(r"\s+", "", entry["normalized_capability"]).lower()
            grouped.setdefault(key, []).append(entry)
    risks: list[dict[str, Any]] = []
    for key, group in grouped.items():
        states = {entry.get("language_state") for entry in group}
        if "current" in states and ("planned" in states or "candidate" in states):
            risks.append({
                "code": "document_state_drift_requires_confirmation",
                "severity": "high",
                "path": f"ledger.normalized_capability:{key}",
                "message": "the same normalized capability has current and future/candidate wording",
                "capability_ids": [entry.get("capability_id") for entry in group],
            })
    return risks


def check_ids(values: Any, ids: set[str], errors: list[dict[str, Any]], path: str) -> None:
    if not isinstance(values, list) or not values or any(not isinstance(x, str) or x not in ids for x in values): errors.append({"code": "unknown_or_missing_capability_id", "path": path, "message": "only known ledger capability IDs are allowed"})


def validate_fragment(record: dict[str, Any], path: Path, qids: list[str]) -> dict[str, Any]:
    ledger = read(Path(record["ledger_path"])); ids = {x["capability_id"] for x in ledger["entries"]}; data = read(path); errors: list[dict[str, Any]] = []; risks: list[dict[str, Any]] = []
    fragments = data.get("fragments", []) if data.get("contract") == "SolutionScope-v1.4-ledger-constrained-fragments" else []
    if [x.get("question_id") for x in fragments if isinstance(x, dict)] != qids: errors.append({"code": "question_order", "path": "fragments", "message": "requested question order required"}); fragments = []
    base_keys = {"question_id", "answer_summary", "findings", "information_gaps", "potential_conflicts", "assumptions", "recommendations", "instruction_coverage"}
    for answer in fragments:
        qid = answer.get("question_id", "?"); base = f"answers.{qid}"
        if not isinstance(answer, dict) or set(answer) != base_keys or not isinstance(answer.get("answer_summary"), str) or not answer["answer_summary"].strip(): errors.append({"code": "answer_shape", "path": base, "message": "fragment answer contract mismatch"}); continue
        for i, item in enumerate(answer.get("findings", [])):
            if not isinstance(item, dict) or set(item) != {"claim", "capability_ids"} or not isinstance(item.get("claim"), str) or not item["claim"].strip(): errors.append({"code": "finding_shape", "path": f"{base}.findings[{i}]", "message": "only claim and capability IDs allowed"})
            else: check_ids(item.get("capability_ids"), ids, errors, f"{base}.findings[{i}].capability_ids")
        for field, keys in (("information_gaps", {"gap_kind", "description", "clarification_question", "capability_ids"}), ("potential_conflicts", {"classification", "description", "capability_ids"})):
            for i, item in enumerate(answer.get(field, [])):
                if not isinstance(item, dict) or set(item) != keys or not isinstance(item.get("description"), str) or not item["description"].strip(): errors.append({"code": f"{field}_shape", "path": f"{base}.{field}[{i}]", "message": "ledger-only source binding required"}); continue
                if field == "information_gaps" and item.get("gap_kind") not in GAPS: errors.append({"code": "gap_shape", "path": f"{base}.{field}[{i}]", "message": "gap kind invalid"})
                elif field == "potential_conflicts" and item.get("classification") != "potential_conflict_or_term_drift": errors.append({"code": "conflict_shape", "path": f"{base}.{field}[{i}]", "message": "conflict classification invalid"})
                else: check_ids(item.get("capability_ids"), ids, errors, f"{base}.{field}[{i}].capability_ids")
        expected = next((parts for q, _, parts in QUESTIONS if q == qid), [])
        rows = answer.get("instruction_coverage", []); actual = [x.get("component_id") for x in rows if isinstance(x, dict)]
        if actual != expected or any(x.get("status") == "not_covered" for x in rows if isinstance(x, dict)): risks.append({"code": "instruction_component_missing", "severity": "high", "path": f"{base}.instruction_coverage", "message": "required component missing, malformed, or explicitly not covered"})
    return validation("fragment", path, record, errors, risks)


def inherited(ids: list[str], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"capability_id": cap, "language_state": ledger[cap]["language_state"], "evidence_locators": ledger[cap]["evidence_locators"]} for cap in ids]


def assemble_answer(answer: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    out = {k: answer[k] for k in ("question_id", "answer_summary", "assumptions", "recommendations", "instruction_coverage")}
    out["findings"] = [{"claim": x["claim"], "capability_ids": x["capability_ids"], "inherited_capabilities": inherited(x["capability_ids"], ledger)} for x in answer["findings"]]
    out["information_gaps"] = [{"gap_kind": x["gap_kind"], "description": x["description"], "clarification_question": x["clarification_question"], "capability_ids": x["capability_ids"], "inherited_capabilities": inherited(x["capability_ids"], ledger)} for x in answer["information_gaps"]]
    out["potential_conflicts"] = [{"classification": x["classification"], "description": x["description"], "capability_ids": x["capability_ids"], "inherited_capabilities": inherited(x["capability_ids"], ledger)} for x in answer["potential_conflicts"]]
    return out


def init(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); src = args.input.resolve()
    if (run / "workflow_run_record.json").exists(): raise ValueError("new run directory required")
    if not src.is_file() or src.suffix.lower() not in {".md", ".markdown"}: raise ValueError("a permitted Markdown input file is required")
    doc = import_markdown(src); doc_path = run / "document_import.json"; write(doc_path, doc)
    if args.questions:
        supplied = read(args.questions.resolve())
        questions = supplied.get("questions", []) if isinstance(supplied, dict) else []
    else:
        questions = [{"question_id": q, "question": text, "instruction_components": parts} for q, text, parts in QUESTIONS]
    qpath = run / "questions.json"; write(qpath, {"contract": "SolutionScope-v1.4-review-questions", "questions": questions})
    record = {"contract": "SolutionScope-v1.4-ledger-constrained-workflow", "workflow_version": VERSION, "run_id": args.run_id, "model": args.model, "reasoning_effort": args.reasoning_effort, "input_document_path": str(doc_path), "input_document_sha256": sha(doc_path), "source_input_path": str(src), "source_input_sha256": sha(src), "questions_path": str(qpath), "questions_sha256": sha(qpath), "skill_invoked": True, "actual_skill_invocation": True, "skill_path": str(ROOT), "skill_md_sha256": sha(ROOT / "SKILL.md"), "entry_script_path": str(Path(__file__).resolve()), "entry_script_sha256": sha(Path(__file__).resolve()), "model_calls": [], "stages": [], "retry_count": 0, "run_status": "initialized", "authorization": "caller_confirmed_permitted_input"}
    rows = question_rows(record)
    stage(record, "init", source_copy_public=False, question_count=len(rows)); save(run, record); print(json.dumps({"run_dir": str(run)}, ensure_ascii=False))


def prepare_ledger(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); schema = run / "schemas" / "ledger.schema.json"; write(schema, ledger_schema())
    doc = read(Path(record["input_document_path"])); doc.pop("source_path", None)
    request = {"request_contract": "SolutionScope-v1.4-ledger-request", "instruction": "Return exactly one JSON object matching output_schema. Build the only capability-state and evidence source for later answers. Every capability needs exact source anchors. Use language_state current/planned/candidate/normative/unknown/conflicted. Classify the cited proposition rather than an isolated modal word. Use conflicted for localized current-versus-planned/candidate tension. Do not answer review questions or use external/reference material.", "output_schema_path": str(schema), "output_schema_sha256": sha(schema), "document": doc, "output_artifact_path": str(run / "ledger_raw.json")}
    path = run / "ledger_request.json"; write(path, request); record.update({"ledger_request_path": str(path), "ledger_raw_path": request["output_artifact_path"], "ledger_schema_path": str(schema), "ledger_schema_sha256": sha(schema)}); stage(record, "prepare_ledger", schema_sha256=sha(schema)); record["run_status"] = "ledger_prepared"; save(run, record); print(json.dumps({"request_path": str(path), "schema_path": str(schema)}, ensure_ascii=False))


def register_ledger(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); artifact = args.artifact.resolve(); declared = Path(record["ledger_raw_path"]).resolve()
    if not artifact.is_file() or record["model_calls"] or artifact != declared: raise ValueError("one model output at the declared ledger path is required")
    call = {"model_call_id": args.model_call_id, "stage": "ledger", "artifact_path": str(artifact), "artifact_sha256": sha(artifact), "registered_at_utc": now(), "skill_invoked": True, "call_source": "caller-provided model call"}
    record["model_calls"].append(call); stage(record, "register_ledger", **call); save(run, record)


def validate_ledger_command(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); result = validate_ledger(record, Path(record["ledger_raw_path"])); path = run / "validation" / "ledger.json"; write(path, result); record.update({"ledger_path": record["ledger_raw_path"], "ledger_sha256": sha(Path(record["ledger_raw_path"])), "ledger_validation_path": str(path), "ledger_structural_errors": result["structural_errors"]}); stage(record, "validate_ledger", structural_errors=result["structural_errors"], semantic_risk_count=result["semantic_risk_count"]); save(run, record); print(json.dumps({"structural_errors": result["structural_errors"], "semantic_risks": result["semantic_risk_categories"]}, ensure_ascii=False))


def prepare_fragment(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); qids = args.question_ids.split(","); slug = "-".join(qids)
    all_questions = question_rows(record)
    if record.get("ledger_structural_errors") != 0 or any(q not in [x[0] for x in all_questions] for q in qids): raise ValueError("validated ledger and known questions required")
    schema = run / "schemas" / f"fragment-{slug}.schema.json"; write(schema, fragment_schema(qids)); ledger = read(Path(record["ledger_path"])); doc = read(Path(record["input_document_path"])); doc.pop("source_path", None)
    selected = [x for x in all_questions if x[0] in qids]; skeleton = {q: [{"component_id": c, "status": "not_covered", "note": None} for c in parts] for q, _, parts in selected}
    request = {"request_contract": "SolutionScope-v1.4-ledger-constrained-fragment-request", "instruction": "Return only the assigned answer fragments as JSON. The ledger is the exclusive source for capability state and exact evidence. Select only ledger capability_id values. Do not output lifecycle states, page/section/paragraph fields, locator quotes, or invented capability IDs. Write only question-specific judgments, gaps, conflicts, assumptions, recommendations, and the fixed coverage skeleton. Do not use external/reference material.", "output_schema_path": str(schema), "output_schema_sha256": sha(schema), "assigned_questions": [{"question_id": q, "question": text, "instruction_components": parts} for q, text, parts in selected], "coverage_skeletons": skeleton, "global_ledger": ledger, "full_document": doc, "output_artifact_path": str(run / "fragment_raw" / f"{slug}.json")}
    path = run / "fragment_requests" / f"{slug}.json"; write(path, request); record.setdefault("fragment_packages", {})[slug] = {"question_ids": qids, "request_path": str(path), "schema_path": str(schema), "schema_sha256": sha(schema), "output_path": request["output_artifact_path"]}; stage(record, "prepare_ledger_constrained_fragment", question_ids=qids, schema_sha256=sha(schema)); save(run, record); print(json.dumps({"request_path": str(path), "schema_path": str(schema)}, ensure_ascii=False))


def register_fragment(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); slug = args.question_ids.replace(",", "-"); package = record["fragment_packages"][slug]; artifact = args.artifact.resolve(); declared = Path(package["output_path"]).resolve()
    if not artifact.is_file() or artifact != declared or any(c["stage"] == f"fragment:{slug}" for c in record["model_calls"]): raise ValueError("one model output at the declared fragment path is required")
    call = {"model_call_id": args.model_call_id, "stage": f"fragment:{slug}", "artifact_path": str(artifact), "artifact_sha256": sha(artifact), "registered_at_utc": now(), "skill_invoked": True, "call_source": "caller-provided model call"}; record["model_calls"].append(call); stage(record, "register_fragment", **call); save(run, record)


def validate_fragment_command(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); slug = args.question_ids.replace(",", "-"); package = record["fragment_packages"][slug]; result = validate_fragment(record, Path(package["output_path"]), package["question_ids"]); path = run / "validation" / f"fragment-{slug}.json"; write(path, result); package.update({"validation_path": str(path), "structural_errors": result["structural_errors"]}); stage(record, "validate_fragment", question_ids=package["question_ids"], structural_errors=result["structural_errors"]); save(run, record); print(json.dumps({"structural_errors": result["structural_errors"]}, ensure_ascii=False))


def assemble(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); packages = record.get("fragment_packages", {}); expected = [q for q, _, _ in question_rows(record)]
    if any(p.get("structural_errors") != 0 for p in packages.values()): raise ValueError("fragment structural gate failed; one retry may be prepared externally")
    ledger = {x["capability_id"]: x for x in read(Path(record["ledger_path"]))["entries"]}; by_q = {}
    for package in packages.values():
        for answer in read(Path(package["output_path"]))["fragments"]: by_q[answer["question_id"]] = assemble_answer(answer, ledger)
    if list(by_q) != expected: raise ValueError("all configured questions are required")
    final = {"contract": "SolutionScope-v1.4-ledger-constrained-review-draft", "artifact_class": "ai_review_draft", "input_document_sha256": record["input_document_sha256"], "method": "ledger_constrained_generation", "capability_ledger": list(ledger.values()), "answers": [by_q[q] for q in expected], "provenance": {"model": record["model"], "reasoning_effort": record["reasoning_effort"], "skill_invoked": True, "skill_path": record["skill_path"], "skill_md_sha256": record["skill_md_sha256"], "entry_script_sha256": record["entry_script_sha256"], "ledger_sha256": record["ledger_sha256"], "retry_count": record["retry_count"]}}
    path = run / "B-v1.4-assembled.json"; write(path, final); record.update({"assembled_path": str(path), "assembled_sha256": sha(path)}); stage(record, "deterministic_ledger_injection_and_assembly", artifact_sha256=sha(path)); save(run, record); print(json.dumps({"artifact_path": str(path)}, ensure_ascii=False))


def validate_final(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); path = Path(record["assembled_path"]); data = read(path); errors: list[dict[str, Any]] = []; risks: list[dict[str, Any]] = []; ledger = {x["capability_id"]: x for x in data.get("capability_ledger", [])}; configured = question_rows(record)
    if data.get("contract") != "SolutionScope-v1.4-ledger-constrained-review-draft" or not ledger: errors.append({"code": "final_envelope", "path": "root", "message": "v1.4 final envelope/ledger required"})
    answer_ids = [x.get("question_id") for x in data.get("answers", []) if isinstance(x, dict)]
    if answer_ids != [q for q, _, _ in configured]: errors.append({"code": "question_order", "path": "answers", "message": "configured question order required"})
    conflicted_used = False
    for answer in data.get("answers", []):
        qid = answer.get("question_id", "?"); expected = next((c for q, _, c in configured if q == qid), []); coverage = answer.get("instruction_coverage", []); actual = [x.get("component_id") for x in coverage if isinstance(x, dict)]
        if actual != expected or any(x.get("status") == "not_covered" for x in coverage if isinstance(x, dict)): risks.append({"code": "instruction_component_missing", "severity": "high", "path": f"answers.{qid}.instruction_coverage", "message": "required instruction component not covered"})
        for field in ("findings", "information_gaps", "potential_conflicts"):
            for i, item in enumerate(answer.get(field, [])):
                ids = item.get("capability_ids", []); injected = item.get("inherited_capabilities", [])
                expected_injected = inherited(ids, ledger) if isinstance(ids, list) and all(x in ledger for x in ids) else None
                if expected_injected is None or injected != expected_injected: errors.append({"code": "ledger_injection_mismatch", "path": f"answers.{qid}.{field}[{i}]", "message": "states and anchors must be injected exactly from ledger"})
                if any(x.get("language_state") == "conflicted" for x in injected if isinstance(x, dict)): conflicted_used = True
    if any(x.get("language_state") == "conflicted" for x in ledger.values()) and not conflicted_used: risks.append({"code": "material_conflict_not_retained", "severity": "high", "path": "answers", "message": "conflicted ledger capability not retained in answers"})
    risks.extend(ledger_drifts(list(ledger.values()))); result = validation("final_skill", path, record, errors, risks); report_path = run / "validation" / "final-skill.json"; write(report_path, result); record["final_validation"] = {"report_path": str(report_path), "structural_errors": result["structural_errors"], "semantic_risk_count": result["semantic_risk_count"]}; stage(record, "validate_final", structural_errors=result["structural_errors"], semantic_risk_count=result["semantic_risk_count"]); record["run_status"] = "review_ready_structural_with_semantic_human_review_required" if not errors else "structural_gate_failed_manual_review_required"; save(run, record); print(json.dumps({"structural_errors": result["structural_errors"], "semantic_risks": result["semantic_risk_categories"]}, ensure_ascii=False))


def source_reference(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); ledger = read(Path(record["ledger_path"]))["entries"]; rows = []
    for x in ledger: rows.append({"capability_id": x["capability_id"], "ledger_language_state": x["language_state"], "source_proposition_states": sorted({state_for_quote(loc["quote"]) for loc in x["evidence_locators"]}), "evidence_locators": x["evidence_locators"]})
    path = run / "source_text_lifecycle_reference.json"; write(path, {"contract": "SolutionScope-v1.4-source-text-lifecycle-reference", "entries": rows, "boundary": "Deterministic wording reference, not expert gold or semantic truth."}); stage(record, "export_source_text_lifecycle_reference", path=str(path), sha256=sha(path)); save(run, record); print(json.dumps({"path": str(path)}, ensure_ascii=False))


def compare_baseline(args: argparse.Namespace) -> None:
    run = args.run_dir.resolve(); record = load(run); a = read(Path(args.a_report)); b = read(Path(record["final_validation"]["report_path"])); shared = ("future_or_candidate_promoted_to_current", "document_state_drift_requires_confirmation", "instruction_component_missing")
    counts = lambda report: {key: report["semantic_risk_categories"].get(key, 0) for key in shared}
    result = {"contract": "SolutionScope-v1.4-descriptive-comparison", "scope": "development material only unless a separate holdout is supplied", "baseline": {"calls": args.baseline_calls, "structural_errors": a["structural_errors"], "shared_source_text_risks": counts(a)}, "ledger_constrained": {"calls": len(record["model_calls"]), "structural_errors": b["structural_errors"], "shared_source_text_risks": counts(b), "ledger_only_observable_risks": {k: v for k, v in b["semantic_risk_categories"].items() if k not in shared}}, "boundary": "Risk flags are source-bound diagnostics, not proven errors, accuracy, or expert labels."}; path = run / "baseline-comparison.json"; write(path, result); stage(record, "compare_with_baseline_shared_risk_scope", path=str(path)); save(run, record); print(json.dumps({"path": str(path)}, ensure_ascii=False))


def main() -> int:
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("init"); x.add_argument("--input", type=Path, required=True); x.add_argument("--questions", type=Path); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--run-id", required=True); x.add_argument("--model", default="unspecified"); x.add_argument("--reasoning-effort", default="unspecified"); x.set_defaults(fn=init)
    for name, fn in (("prepare-ledger", prepare_ledger), ("validate-ledger", validate_ledger_command), ("assemble", assemble), ("validate-final", validate_final), ("source-reference", source_reference)):
        x = sub.add_parser(name); x.add_argument("--run-dir", type=Path, required=True); x.set_defaults(fn=fn)
    x = sub.add_parser("register-ledger"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--artifact", type=Path, required=True); x.add_argument("--model-call-id", required=True); x.set_defaults(fn=register_ledger)
    for name, fn in (("prepare-fragment", prepare_fragment), ("register-fragment", register_fragment), ("validate-fragment", validate_fragment_command)):
        x = sub.add_parser(name); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--question-ids", required=True); x.set_defaults(fn=fn)
        if name == "register-fragment": x.add_argument("--artifact", type=Path, required=True); x.add_argument("--model-call-id", required=True)
    x = sub.add_parser("compare-baseline"); x.add_argument("--run-dir", type=Path, required=True); x.add_argument("--a-report", type=Path, required=True); x.add_argument("--baseline-calls", type=int, default=1); x.set_defaults(fn=compare_baseline)
    args = p.parse_args(); args.fn(args); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc: raise SystemExit(f"SOLUTION SCOPE V1.4 REFUSED/FAILED: {exc}")
