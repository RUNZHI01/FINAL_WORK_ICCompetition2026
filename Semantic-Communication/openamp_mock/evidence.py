from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .protocol import (
    FORMAL_BASELINE_E2E_MS,
    FORMAL_BASELINE_PAYLOAD_MS,
    FORMAL_CURRENT_E2E_MS,
    FORMAL_CURRENT_PAYLOAD_MS,
    FORMAL_TRUSTED_CURRENT_SHA,
)


def write_example_bundle(
    *,
    output_dir: str | Path,
    run_id: str,
    scenario_results: list[dict[str, Any]],
    template_dir: str | Path,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    template_path = Path(template_dir)

    summary_path = output_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "generated_at": _now(),
                "scenario_results": scenario_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    written_files = {"summary": str(summary_path)}
    coverage_rows: list[str] = []

    for result in scenario_results:
        scenario_name = result["scenario"]
        scenario_dir = output_path / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = scenario_dir / f"job_manifest_{result['job_id']}.json"
        fault_log_path = scenario_dir / "fault_log.jsonl"
        guard_state_log_path = scenario_dir / "guard_state_log.jsonl"

        manifest = {
            "run_id": run_id,
            "scenario": scenario_name,
            "job_id": result["job_id"],
            "flags": result["flags"],
            "trusted_current_sha": FORMAL_TRUSTED_CURRENT_SHA,
            "artifact_sha_expected": result["artifact_sha_expected"],
            "artifact_sha_actual": result["artifact_sha_actual"],
            "deadline_ms": result["deadline_ms"],
            "expected_outputs": result["expected_outputs"],
            "decision": result["decision"],
            "orchestrator_state": result["orchestrator_state"],
            "guard_state": result["guard_state"],
            "last_fault_code": result["last_fault_code"],
            "formal_metrics": {
                "payload_ms": {
                    "baseline": FORMAL_BASELINE_PAYLOAD_MS,
                    "current": FORMAL_CURRENT_PAYLOAD_MS,
                },
                "real_e2e_ms_per_image": {
                    "baseline": FORMAL_BASELINE_E2E_MS,
                    "current": FORMAL_CURRENT_E2E_MS,
                },
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_jsonl(fault_log_path, result["fault_log"])
        _write_jsonl(guard_state_log_path, result["guard_state_log"])

        written_files[f"{scenario_name}_manifest"] = str(manifest_path)
        written_files[f"{scenario_name}_fault_log"] = str(fault_log_path)
        written_files[f"{scenario_name}_guard_state_log"] = str(guard_state_log_path)

        coverage_rows.append(
            "| {tc_id} | {scenario} | {status} | {decision} | {orchestrator_state} | {guard_state} | {fault} | {evidence} |".format(
                tc_id=result["tc_id"],
                scenario=scenario_name,
                status="PASS" if result["passed"] else "FAIL",
                decision=result["decision"],
                orchestrator_state=result["orchestrator_state"],
                guard_state=result["guard_state"],
                fault=result["last_fault_code"],
                evidence=f"`{scenario_name}/job_manifest_{result['job_id']}.json`",
            )
        )

        if result["fit_id"] is not None:
            fit_path = scenario_dir / f"fit_report_{result['fit_id']}.md"
            fit_template = _read_template(template_path / "openamp_fit_report_template.md")
            fit_report = _render_template(
                fit_template,
                {
                    "generated_at": _now(),
                    "fit_id": result["fit_id"],
                    "run_id": run_id,
                    "scenario": scenario_name,
                    "tc_id": result["tc_id"],
                    "injected_fault": result["injected_fault"] or "N/A",
                    "expected_result": result["expected_result"],
                    "actual_result": result["actual_result"],
                    "risk_item": result["risk_item"] or "N/A",
                    "evidence_bundle": f"{scenario_name}/job_manifest_{result['job_id']}.json, {scenario_name}/fault_log.jsonl, {scenario_name}/guard_state_log.jsonl",
                },
            )
            fit_path.write_text(fit_report, encoding="utf-8")
            written_files[f"{scenario_name}_fit"] = str(fit_path)

    coverage_template = _read_template(template_path / "openamp_coverage_matrix_template.md")
    coverage_path = output_path / "coverage_matrix.md"
    covered = ", ".join(result["tc_id"] for result in scenario_results)
    coverage_markdown = _render_template(
        coverage_template,
        {
            "generated_at": _now(),
            "run_id": run_id,
            "trusted_current_sha": FORMAL_TRUSTED_CURRENT_SHA,
            "coverage_rows": "\n".join(coverage_rows),
            "covered_items": covered,
            "remaining_items": "TC-002, TC-005, TC-007, TC-008, TC-009, TC-010, TC-011, TC-012",
        },
    )
    coverage_path.write_text(coverage_markdown, encoding="utf-8")
    written_files["coverage_matrix"] = str(coverage_path)
    return written_files


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
