#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import solutionscope_workflow as workflow  # noqa: E402
from schema_gate import validate_instance  # noqa: E402


def write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def base_config() -> dict:
    return {
        "contract": "SolutionScope-v1.5-workflow-config",
        "config_id": "test-config",
        "allowed_states": ["current", "planned", "candidate", "normative", "unknown", "conflicted"],
        "state_rules": [
            {"state": "planned", "phrases": ["后续将"]},
            {"state": "candidate", "phrases": ["可建设"]},
            {"state": "normative", "phrases": ["应记录"]},
            {"state": "current", "phrases": ["当前平台支持", "通过统一时间轴完成"]},
        ],
        "focus_terms": ["统一时间轴"],
        "promotion_source_states": ["planned", "candidate", "normative"],
        "conflict_against_current_states": ["planned", "candidate"],
        "question_groups": [
            {
                "group_id": "G1",
                "questions": [
                    {
                        "question_id": "QA",
                        "question": "区分现状和规划。",
                        "instruction_components": ["current", "planned"],
                    }
                ],
            },
            {
                "group_id": "G2",
                "questions": [
                    {
                        "question_id": "QB",
                        "question": "列出候选能力和待确认项。",
                        "instruction_components": ["candidate", "question"],
                    }
                ],
            },
        ],
    }


def valid_ledger() -> dict:
    empty = {"dependencies": [], "quantitative_metrics": [], "acceptance_method": None, "information_gaps": []}
    return {
        "contract": "SolutionScope-v1.5-capability-ledger",
        "entries": [
            {
                "capability_id": "cap-current",
                "module": "采集",
                "normalized_capability": "当前采集能力",
                "language_state": "current",
                "evidence_locators": [
                    {
                        "page_number": 1,
                        "section": "范围",
                        "paragraph_id": "P001-001",
                        "quote": "当前平台支持数据采集，并通过统一时间轴完成多源对齐。",
                    }
                ],
                **empty,
            },
            {
                "capability_id": "cap-conflict",
                "module": "对齐",
                "normalized_capability": "统一时间轴",
                "language_state": "conflicted",
                "evidence_locators": [
                    {
                        "page_number": 1,
                        "section": "范围",
                        "paragraph_id": "P001-001",
                        "quote": "通过统一时间轴完成多源对齐",
                    },
                    {
                        "page_number": 1,
                        "section": "范围",
                        "paragraph_id": "P001-002",
                        "quote": "后续将完善统一时间轴的精度校准。",
                    },
                ],
                **empty,
            },
            {
                "capability_id": "cap-candidate",
                "module": "标定",
                "normalized_capability": "自动标定",
                "language_state": "candidate",
                "evidence_locators": [
                    {
                        "page_number": 1,
                        "section": "范围",
                        "paragraph_id": "P001-003",
                        "quote": "可建设自动标定能力。",
                    }
                ],
                **empty,
            },
        ],
    }


def valid_fragment(group_id: str) -> dict:
    if group_id == "G1":
        return {
            "contract": "SolutionScope-v1.5-ledger-constrained-fragments",
            "group_id": "G1",
            "fragments": [
                {
                    "question_id": "QA",
                    "answer_summary": "当前能力与规划存在时间轴范围张力。",
                    "findings": [{"claim": "平台当前支持采集。", "capability_ids": ["cap-current"]}],
                    "information_gaps": [],
                    "potential_conflicts": [
                        {
                            "classification": "potential_conflict_or_term_drift",
                            "description": "统一时间轴的当前范围仍需确认。",
                            "capability_ids": ["cap-conflict"],
                        }
                    ],
                    "assumptions": [],
                    "recommendations": ["由材料负责人确认边界。"],
                    "instruction_coverage": [
                        {"component_id": "current", "status": "covered", "note": None},
                        {"component_id": "planned", "status": "covered", "note": None},
                    ],
                }
            ],
        }
    return {
        "contract": "SolutionScope-v1.5-ledger-constrained-fragments",
        "group_id": "G2",
        "fragments": [
            {
                "question_id": "QB",
                "answer_summary": "自动标定仍是候选能力。",
                "findings": [{"claim": "材料提出自动标定候选。", "capability_ids": ["cap-candidate"]}],
                "information_gaps": [
                    {
                        "gap_kind": "acceptance_method_insufficient",
                        "description": "尚无验收方法。",
                        "clarification_question": "如何验收自动标定？",
                        "capability_ids": ["cap-candidate"],
                    }
                ],
                "potential_conflicts": [],
                "assumptions": [],
                "recommendations": [],
                "instruction_coverage": [
                    {"component_id": "candidate", "status": "covered", "note": None},
                    {"component_id": "question", "status": "covered", "note": None},
                ],
            }
        ],
    }


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.input_path = root / "source.md"
        self.config_path = root / "config.json"
        self.run_dir = root / "run"
        self.input_path.write_text(
            "# 范围\n\n当前平台支持数据采集，并通过统一时间轴完成多源对齐。\n\n后续将完善统一时间轴的精度校准。\n\n可建设自动标定能力。\n",
            encoding="utf-8",
        )
        write_json(self.config_path, base_config())
        workflow.prepare_run(
            self.input_path,
            self.config_path,
            self.run_dir,
            "TEST-RUN",
            "test-model",
            "test-effort",
            "public_authorized",
        )

    def ledger_path(self, value: dict | None = None) -> Path:
        return write_json(self.root / "model" / "ledger.json", value or valid_ledger())

    def fragment_paths(self) -> dict[str, Path]:
        return {
            group: write_json(self.root / "model" / f"{group}.json", valid_fragment(group))
            for group in ("G1", "G2")
        }

    def complete(self, metadata: Path | None = None) -> dict:
        workflow.advance_run(self.run_dir, self.ledger_path(), metadata)
        return workflow.complete_run(self.run_dir, self.fragment_paths(), metadata)


class SchemaGateTests(unittest.TestCase):
    def test_rejects_missing_required_property(self) -> None:
        schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "string"}}}
        self.assertIn("schema.required", {issue["code"] for issue in validate_instance({}, schema)})

    def test_rejects_additional_property(self) -> None:
        schema = {"type": "object", "additionalProperties": False, "properties": {}}
        self.assertIn("schema.additionalProperties", {issue["code"] for issue in validate_instance({"x": 1}, schema)})

    def test_rejects_wrong_type(self) -> None:
        self.assertIn("schema.type", {issue["code"] for issue in validate_instance("1", {"type": "integer"})})

    def test_rejects_duplicate_unique_items(self) -> None:
        schema = {"type": "array", "uniqueItems": True, "items": {"type": "string"}}
        self.assertIn("schema.uniqueItems", {issue["code"] for issue in validate_instance(["x", "x"], schema)})


class WorkflowGateTests(unittest.TestCase):
    def test_config_rejects_duplicate_question_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = base_config()
            config["question_groups"][1]["questions"][0]["question_id"] = "QA"
            path = write_json(Path(directory) / "config.json", config)
            with self.assertRaises(workflow.WorkflowRefusal):
                workflow.load_and_validate_config(path)

    def test_prepare_uses_configured_questions_without_python_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            manifest = workflow.read_json(fixture.run_dir / "questions.json")
            ids = [question["question_id"] for group in manifest["groups"] for question in group["questions"]]
            self.assertEqual(ids, ["QA", "QB"])

    def test_illegal_locator_is_structural_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            ledger = valid_ledger()
            ledger["entries"][0]["evidence_locators"][0]["quote"] = "不存在的原文"
            report = workflow.validate_ledger(workflow.load_record(fixture.run_dir), fixture.ledger_path(ledger))
            self.assertIn("locator_misbound", report["structural_error_categories"])

    def test_unknown_dependency_is_structural_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            ledger = valid_ledger()
            ledger["entries"][0]["dependencies"] = ["cap-missing"]
            report = workflow.validate_ledger(workflow.load_record(fixture.run_dir), fixture.ledger_path(ledger))
            self.assertIn("unknown_dependency_id", report["structural_error_categories"])

    def test_state_promotion_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            ledger = valid_ledger()
            ledger["entries"][2]["language_state"] = "current"
            report = workflow.validate_ledger(workflow.load_record(fixture.run_dir), fixture.ledger_path(ledger))
            self.assertIn("future_or_candidate_promoted_to_current", report["semantic_risk_categories"])

    def test_configured_source_drift_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            report = workflow.validate_ledger(workflow.load_record(fixture.run_dir), fixture.ledger_path())
            self.assertIn("document_state_drift_requires_confirmation", report["semantic_risk_categories"])

    def test_unledgered_source_conflict_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            ledger = valid_ledger()
            ledger["entries"] = [entry for entry in ledger["entries"] if entry["capability_id"] != "cap-conflict"]
            report = workflow.validate_ledger(workflow.load_record(fixture.run_dir), fixture.ledger_path(ledger))
            self.assertIn("source_conflict_not_ledgered", report["semantic_risk_categories"])

    def test_invalid_fragment_shape_fails_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            workflow.advance_run(fixture.run_dir, fixture.ledger_path())
            fragment = valid_fragment("G1")
            fragment["fragments"][0]["unexpected"] = True
            path = write_json(fixture.root / "bad-fragment.json", fragment)
            record = workflow.load_record(fixture.run_dir)
            group = base_config()["question_groups"][0]
            report = workflow.validate_fragment(record, group, path)
            self.assertIn("schema.additionalProperties", report["structural_error_categories"])

    def test_unknown_capability_id_fails_fragment_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            workflow.advance_run(fixture.run_dir, fixture.ledger_path())
            fragment = valid_fragment("G1")
            fragment["fragments"][0]["findings"][0]["capability_ids"] = ["cap-missing"]
            path = write_json(fixture.root / "bad-fragment.json", fragment)
            report = workflow.validate_fragment(workflow.load_record(fixture.run_dir), base_config()["question_groups"][0], path)
            self.assertIn("unknown_capability_id", report["structural_error_categories"])

    def test_missing_instruction_component_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            workflow.advance_run(fixture.run_dir, fixture.ledger_path())
            fragment = valid_fragment("G1")
            fragment["fragments"][0]["instruction_coverage"][1]["status"] = "not_covered"
            path = write_json(fixture.root / "risk-fragment.json", fragment)
            report = workflow.validate_fragment(workflow.load_record(fixture.run_dir), base_config()["question_groups"][0], path)
            self.assertIn("instruction_component_missing", report["semantic_risk_categories"])

    def test_conflict_lost_from_final_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.complete()
            record = workflow.load_record(fixture.run_dir)
            final = workflow.read_json(Path(record["final_artifact_path"]))
            final["answers"][0]["potential_conflicts"] = []
            altered = write_json(fixture.root / "altered-final.json", final)
            report = workflow.validate_final(record, altered)
            self.assertIn("material_conflict_not_retained", report["semantic_risk_categories"])

    def test_deterministic_injection_uses_ledger_state_and_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.complete()
            record = workflow.load_record(fixture.run_dir)
            final = workflow.read_json(Path(record["final_artifact_path"]))
            inherited = final["answers"][0]["findings"][0]["inherited_capabilities"][0]
            self.assertEqual(inherited["language_state"], "current")
            self.assertEqual(inherited["evidence_locators"][0]["paragraph_id"], "P001-001")

    def test_final_artifact_exposes_human_review_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.complete()
            record = workflow.load_record(fixture.run_dir)
            final = workflow.read_json(Path(record["final_artifact_path"]))
            self.assertEqual(final["review_gate"]["status"], "blocked_pending_human_review")
            self.assertGreater(final["review_gate"]["semantic_risk_count"], 0)
            self.assertEqual(final["source_config_sha256"], record["source_config_sha256"])

    def test_complete_writes_browser_review_payload_with_exact_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            fixture.complete()
            record = workflow.load_record(fixture.run_dir)
            payload_path = Path(record["ui_review_payload_path"])
            payload = workflow.read_json(payload_path)
            self.assertEqual(payload["contract"], "SolutionScope-ui-review-payload-v1")
            self.assertEqual([item["id"] for item in payload["items"]], ["QA", "QB"])
            self.assertEqual(payload["items"][0]["evidence"]["status"], "bound")
            self.assertEqual(payload["items"][0]["evidence"]["relatedLocators"][0]["paragraph_id"], "P001-001")
            self.assertEqual(payload["items"][1]["aiCompleteness"], "partial")
            self.assertIn("test_or_acceptance_method", payload["items"][1]["suggestedMissingFields"])
            self.assertEqual(workflow.sha256(payload_path), record["ui_review_payload_sha256"])

    def test_clean_source_has_no_deterministic_review_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            config = workflow.read_json(fixture.config_path)
            config["focus_terms"] = []
            clean_config = write_json(fixture.root / "clean-config.json", config)
            clean_run = fixture.root / "clean-run"
            workflow.prepare_run(fixture.input_path, clean_config, clean_run, "CLEAN", "model", "effort", "public_authorized")
            ledger = valid_ledger()
            ledger["entries"] = [entry for entry in ledger["entries"] if entry["capability_id"] != "cap-conflict"]
            ledger_path = write_json(fixture.root / "clean-ledger.json", ledger)
            workflow.advance_run(clean_run, ledger_path)
            g1 = valid_fragment("G1")
            g1["fragments"][0]["potential_conflicts"] = []
            g1["fragments"][0]["findings"][0]["capability_ids"] = ["cap-current"]
            fragments = {
                "G1": write_json(fixture.root / "clean-G1.json", g1),
                "G2": write_json(fixture.root / "clean-G2.json", valid_fragment("G2")),
            }
            summary = workflow.complete_run(clean_run, fragments)
            final = workflow.read_json(Path(workflow.load_record(clean_run)["final_artifact_path"]))
            self.assertEqual(summary["release_gate"]["status"], "no_deterministic_block")
            self.assertEqual(final["review_gate"]["status"], "no_deterministic_block")

    def test_missing_provider_telemetry_remains_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            summary = fixture.complete()
            self.assertEqual(summary["telemetry"]["duration_ms"], "unavailable")
            self.assertEqual(summary["telemetry"]["total_tokens"], "unavailable")
            self.assertEqual(summary["telemetry"]["cost"]["value"], "unavailable")

    def test_known_provider_telemetry_is_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Fixture(root)
            metadata = {
                stage: {
                    "model_call_id": f"call-{stage}",
                    "duration_ms": 10,
                    "input_tokens": 2,
                    "output_tokens": 3,
                    "cost_value": 1.0,
                    "currency": "USD",
                }
                for stage in ("ledger", "G1", "G2")
            }
            metadata_path = write_json(root / "metadata.json", metadata)
            summary = fixture.complete(metadata_path)
            self.assertEqual(summary["telemetry"]["duration_ms"], 30)
            self.assertEqual(summary["telemetry"]["total_tokens"], 15)
            self.assertEqual(summary["telemetry"]["cost"]["value"], 3.0)

    def test_fresh_directory_offline_flow_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            summary = fixture.complete()
            self.assertEqual(summary["structural_errors"], 0)
            self.assertTrue((fixture.run_dir / "report" / "run_report.json").is_file())
            self.assertTrue((fixture.run_dir / "report" / "run_report.md").is_file())

    def test_prepare_refuses_nonempty_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Fixture(root)
            with self.assertRaises(workflow.WorkflowRefusal):
                workflow.prepare_run(
                    fixture.input_path,
                    fixture.config_path,
                    fixture.run_dir,
                    "SECOND",
                    "model",
                    "effort",
                    "public_authorized",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
