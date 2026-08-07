from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "solutionscope" / "scripts" / "ledger_constrained_workflow.py"
SOURCE = ROOT / "examples" / "synthetic-platform.md"
QUESTIONS = ROOT / "examples" / "questions.json"


def run_cli(*args: str) -> None:
    subprocess.run([sys.executable, str(SCRIPT), *args], check=True, capture_output=True, text=True)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class WorkflowTest(unittest.TestCase):
    def test_synthetic_end_to_end_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            run_cli("init", "--input", str(SOURCE), "--questions", str(QUESTIONS), "--run-dir", str(run), "--run-id", "test-001")
            run_cli("prepare-ledger", "--run-dir", str(run))

            doc = json.loads((run / "document_import.json").read_text(encoding="utf-8"))
            rows = doc["paragraphs"]

            def locator(index: int) -> dict[str, object]:
                row = rows[index]
                return {
                    "page_number": row["page_number"],
                    "section": row["section"],
                    "paragraph_id": row["paragraph_id"],
                    "quote": row["text"],
                }

            empty_gap: list[object] = []
            ledger = {
                "contract": "SolutionScope-v1.4-capability-ledger",
                "entries": [
                    {
                        "capability_id": "CAP-001",
                        "module": "review",
                        "normalized_capability": "source-linked review",
                        "language_state": "current",
                        "evidence_locators": [locator(0)],
                        "dependencies": [],
                        "quantitative_metrics": [],
                        "acceptance_method": None,
                        "information_gaps": empty_gap,
                    },
                    {
                        "capability_id": "CAP-002",
                        "module": "analysis",
                        "normalized_capability": "cross-document conflict detection",
                        "language_state": "planned",
                        "evidence_locators": [locator(2)],
                        "dependencies": ["CAP-001"],
                        "quantitative_metrics": [],
                        "acceptance_method": None,
                        "information_gaps": empty_gap,
                    },
                    {
                        "capability_id": "CAP-003",
                        "module": "acceptance",
                        "normalized_capability": "source locator requirement",
                        "language_state": "normative",
                        "evidence_locators": [locator(4)],
                        "dependencies": [],
                        "quantitative_metrics": [],
                        "acceptance_method": "reviewer inspection",
                        "information_gaps": empty_gap,
                    },
                ],
            }
            write_json(run / "ledger_raw.json", ledger)
            run_cli("register-ledger", "--run-dir", str(run), "--artifact", str(run / "ledger_raw.json"), "--model-call-id", "test-ledger")
            run_cli("validate-ledger", "--run-dir", str(run))

            run_cli("prepare-fragment", "--run-dir", str(run), "--question-ids", "Q1,Q2,Q3")
            questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
            fragments = []
            for question in questions:
                qid = question["question_id"]
                fragments.append(
                    {
                        "question_id": qid,
                        "answer_summary": f"Synthetic answer for {qid}",
                        "findings": [{"claim": "Source-bound finding", "capability_ids": ["CAP-001"]}],
                        "information_gaps": [],
                        "potential_conflicts": [],
                        "assumptions": [],
                        "recommendations": [],
                        "instruction_coverage": [
                            {"component_id": component, "status": "covered", "note": None}
                            for component in question["instruction_components"]
                        ],
                    }
                )
            fragment_path = run / "fragment_raw" / "Q1-Q2-Q3.json"
            write_json(fragment_path, {"contract": "SolutionScope-v1.4-ledger-constrained-fragments", "fragments": fragments})
            run_cli("register-fragment", "--run-dir", str(run), "--question-ids", "Q1,Q2,Q3", "--artifact", str(fragment_path), "--model-call-id", "test-fragment")
            run_cli("validate-fragment", "--run-dir", str(run), "--question-ids", "Q1,Q2,Q3")
            run_cli("assemble", "--run-dir", str(run))
            run_cli("validate-final", "--run-dir", str(run))

            final_report = json.loads((run / "validation" / "final-skill.json").read_text(encoding="utf-8"))
            self.assertEqual(final_report["structural_errors"], 0)
            assembled = json.loads((run / "B-v1.4-assembled.json").read_text(encoding="utf-8"))
            inherited = assembled["answers"][0]["findings"][0]["inherited_capabilities"][0]
            self.assertEqual(inherited["language_state"], "current")
            self.assertEqual(inherited["capability_id"], "CAP-001")


if __name__ == "__main__":
    unittest.main()
