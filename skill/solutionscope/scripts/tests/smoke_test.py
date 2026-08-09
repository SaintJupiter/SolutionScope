#!/usr/bin/env python3
"""Run the public synthetic fixture through the CLI in a fresh temp directory."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "solutionscope_workflow.py"
sys.path.insert(0, str(HERE))

from test_workflow import base_config, valid_fragment, valid_ledger, write_json  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="solutionscope-v15-smoke-") as directory:
        root = Path(directory)
        source = root / "source.md"
        config = write_json(root / "config.json", base_config())
        ledger = write_json(root / "ledger.json", valid_ledger())
        g1 = write_json(root / "G1.json", valid_fragment("G1"))
        g2 = write_json(root / "G2.json", valid_fragment("G2"))
        run_dir = root / "fresh-run"
        source.write_text(
            "# 范围\n\n当前平台支持数据采集，并通过统一时间轴完成多源对齐。\n\n后续将完善统一时间轴的精度校准。\n\n可建设自动标定能力。\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            str(SCRIPT),
            "run-offline",
            "--input",
            str(source),
            "--config",
            str(config),
            "--run-dir",
            str(run_dir),
            "--run-id",
            "SMOKE-V15",
            "--model",
            "smoke-model",
            "--reasoning-effort",
            "unavailable",
            "--permission-class",
            "public_authorized",
            "--ledger-output",
            str(ledger),
            "--fragment-output",
            f"G1={g1}",
            "--fragment-output",
            f"G2={g2}",
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode
        report_path = run_dir / "report" / "run_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assertions = {
            "fresh_run_directory": run_dir.is_dir(),
            "structural_errors_zero": report["structural_errors"] == 0,
            "three_model_outputs_registered": report["telemetry"]["model_call_count"] == 3,
            "missing_telemetry_is_unavailable": report["telemetry"]["total_tokens"] == "unavailable",
            "final_artifact_exists": Path(report["final_artifact_path"]).is_file(),
            "human_review_boundary_retained": (
                report["status"] == "review_ready_human_gate_blocked"
                and report["release_gate"]["status"] == "blocked_pending_human_review"
            ),
        }
        print(json.dumps({"status": "passed" if all(assertions.values()) else "failed", "assertions": assertions, "report": report}, ensure_ascii=False, indent=2))
        return 0 if all(assertions.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
