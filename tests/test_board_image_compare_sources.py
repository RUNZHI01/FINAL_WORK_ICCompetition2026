import json
from pathlib import Path

import pytest

from scripts.board_image_compare.sources import (
    classify_usrp_summary,
    default_reconstruction_sources,
    extract_usrp_token,
    plan_usrp_migration,
)


def test_prerecorded_filters_keep_existing_layout():
    sources = default_reconstruction_sources("/home/user/Downloads/jscc-test-usrp")

    assert sources["prerecorded-pytorch"].accepts("pytorch_reference_reconstruction_20260715")
    assert not sources["prerecorded-tvm"].accepts("pytorch_reference_reconstruction_20260715")
    assert sources["prerecorded-tvm"].remote_root.endswith("/jscc/infer_outputs")
    assert sources["prerecorded-mnn"].remote_root.endswith("/mnn_benchmark_outputs")
    assert set(sources) == {
        "prerecorded-pytorch",
        "prerecorded-tvm",
        "prerecorded-mnn",
        "usrp-qpsk",
        "usrp-iq-direct",
    }


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"phy": "analog-latent-iq"}, "usrp-iq-direct"),
        ({"images": [{"round_records": [{"remote_received_latent_npz": "/rx/0.npz"}]}]}, "usrp-iq-direct"),
        ({"max_arq_rounds": 2, "chunk_bytes": 4096}, "usrp-qpsk"),
        ({"target_count": 1, "all_pass": True}, None),
    ],
)
def test_classify_usrp_summary_requires_evidence(payload, expected):
    assert classify_usrp_summary(payload) == expected


def test_extract_usrp_token_accepts_only_current_usrp_jobs():
    assert extract_usrp_token("openamp3_usrp_1784203435_current") == "1784203435"
    assert extract_usrp_token("openamp3_usrp_1784203435_recovery_current") == "1784203435_recovery"
    assert extract_usrp_token("openamp3_usrp_1784203435_retry_current") == "1784203435_retry"
    assert extract_usrp_token("openamp3_usrp_1784203435") is None
    assert extract_usrp_token("unrelated_job") is None


def _write_summary(root: Path, job_name: str, payload: dict) -> None:
    job_root = root / job_name
    job_root.mkdir(parents=True)
    (job_root / "batch_spool_summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_plan_usrp_migration_uses_exact_then_base_run_and_never_guesses(tmp_path: Path):
    run_root = tmp_path / "runs"
    legacy_root = tmp_path / "legacy"
    output_root = tmp_path / "outputs"
    _write_summary(run_root, "openamp3_usrp_123_recovery_current", {"phy": "analog-latent-iq"})
    _write_summary(run_root, "openamp3_usrp_456_current", {"max_arq_rounds": 2, "chunk_bytes": 4096})
    _write_summary(legacy_root, "openamp3_usrp_789_current", {"max_arq_rounds": 2, "chunk_bytes": 4096})

    decisions = plan_usrp_migration(
        [
            "openamp3_usrp_123_recovery_current",
            "openamp3_usrp_456_retry_current",
            "openamp3_usrp_789_current",
            "openamp3_usrp_000_current",
        ],
        run_root,
        legacy_root,
        output_root,
    )

    assert decisions == [
        {
            "source": str(run_root / "openamp3_usrp_123_recovery_current"),
            "destination": str(output_root / "iq-direct" / "tvm" / "openamp3_usrp_123_recovery_current"),
            "mode": "usrp-iq-direct",
            "reason": "classified from batch_spool_summary.json",
        },
        {
            "source": str(run_root / "openamp3_usrp_456_current"),
            "destination": str(output_root / "qpsk" / "tvm" / "openamp3_usrp_456_retry_current"),
            "mode": "usrp-qpsk",
            "reason": "classified from batch_spool_summary.json",
        },
        {
            "source": str(legacy_root / "openamp3_usrp_789_current"),
            "destination": str(output_root / "qpsk" / "tvm" / "openamp3_usrp_789_current"),
            "mode": "usrp-qpsk",
            "reason": "classified from batch_spool_summary.json",
        },
        {
            "source": str(run_root / "openamp3_usrp_000_current"),
            "destination": None,
            "mode": None,
            "reason": "batch_spool_summary.json not found",
        },
    ]


def test_plan_usrp_migration_does_not_read_other_files(tmp_path: Path):
    run_root = tmp_path / "runs"
    legacy_root = tmp_path / "legacy"
    output_root = tmp_path / "outputs"
    job_root = run_root / "openamp3_usrp_123_current"
    job_root.mkdir(parents=True)
    (job_root / "summary.json").write_text(json.dumps({"phy": "analog-latent-iq"}), encoding="utf-8")

    decisions = plan_usrp_migration([job_root.name], run_root, legacy_root, output_root)

    assert decisions[0]["destination"] is None
    assert decisions[0]["reason"] == "batch_spool_summary.json not found"
