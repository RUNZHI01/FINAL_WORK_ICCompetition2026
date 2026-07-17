import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.migrate_usrp_output_layout import (
    apply_migration,
    build_remote_migration_plan,
    collect_remote_job_names,
    parse_args,
    rollback_migration,
    write_report_atomic,
)
from scripts.board_image_compare.sources import (
    classify_usrp_summary,
    default_reconstruction_sources,
    extract_usrp_token,
    plan_usrp_migration,
)


class FakeSFTP:
    def __init__(self, existing_paths=(), directory_entries=None):
        self.paths = set(existing_paths)
        self.directory_entries = dict(directory_entries or {})
        self.mkdir_calls = []
        self.rename_calls = []

    def stat(self, path):
        if path not in self.paths:
            raise FileNotFoundError(2, "not found", path)
        return object()

    def mkdir(self, path):
        self.mkdir_calls.append(path)
        self.paths.add(path)

    def rename(self, source, destination):
        self.rename_calls.append((source, destination))
        self.paths.remove(source)
        self.paths.add(destination)

    def listdir(self, path):
        if path not in self.directory_entries:
            raise FileNotFoundError(2, "not found", path)
        return list(self.directory_entries[path])


@pytest.fixture
def migration_plan():
    return [
        {
            "source": "/legacy/openamp3_usrp_123_current",
            "destination": "/outputs/qpsk/tvm/openamp3_usrp_123_current",
            "mode": "usrp-qpsk",
            "reason": "classified from batch_spool_summary.json",
        }
    ]


@pytest.fixture
def fake_sftp(migration_plan):
    return FakeSFTP({migration_plan[0]["source"]})


def test_dry_run_never_renames(fake_sftp, migration_plan):
    result = apply_migration(fake_sftp, migration_plan, apply=False)

    assert fake_sftp.rename_calls == []
    assert result["moved"] == []
    assert result["classified"] == migration_plan


def test_empty_migration_plan_is_not_safe():
    result = apply_migration(FakeSFTP(), [], apply=False)

    assert result["safe"] is False


def test_apply_creates_parent_directories_and_renames_once(fake_sftp, migration_plan):
    result = apply_migration(fake_sftp, migration_plan, apply=True)

    assert fake_sftp.mkdir_calls == ["/outputs", "/outputs/qpsk", "/outputs/qpsk/tvm"]
    assert fake_sftp.rename_calls == [
        (
            "/legacy/openamp3_usrp_123_current",
            "/outputs/qpsk/tvm/openamp3_usrp_123_current",
        )
    ]
    assert result["moved"] == migration_plan


def test_existing_destination_collision_is_reported_without_overwrite(migration_plan):
    entry = migration_plan[0]
    fake_sftp = FakeSFTP({entry["source"], entry["destination"]})

    result = apply_migration(fake_sftp, migration_plan, apply=True)

    assert fake_sftp.rename_calls == []
    assert result["moved"] == []
    assert result["collisions"] == migration_plan


def test_dry_run_reports_already_moved_when_only_destination_exists(migration_plan):
    entry = migration_plan[0]
    fake_sftp = FakeSFTP({entry["destination"]})

    result = apply_migration(fake_sftp, migration_plan, apply=False)

    assert fake_sftp.rename_calls == []
    assert result["already_moved"] == migration_plan
    assert result["safe"] is True


def test_rollback_swaps_only_entries_whose_destination_exists(migration_plan):
    present = migration_plan[0]
    missing = {
        **present,
        "source": "/legacy/openamp3_usrp_456_current",
        "destination": "/outputs/qpsk/tvm/openamp3_usrp_456_current",
    }
    fake_sftp = FakeSFTP({present["destination"]})

    result = rollback_migration(
        fake_sftp,
        {"classified": [present, missing]},
        apply=True,
    )

    assert fake_sftp.rename_calls == [(present["destination"], present["source"])]
    assert result["moved"] == [
        {
            **present,
            "source": present["destination"],
            "destination": present["source"],
        }
    ]


def test_prerecorded_filters_keep_existing_layout():
    sources = default_reconstruction_sources("/home/user/Downloads/jscc-test-usrp")

    assert sources["prerecorded-pytorch"].accepts("pytorch_reference_reconstruction_20260715")
    assert not sources["prerecorded-tvm"].accepts("pytorch_reference_reconstruction_20260715")
    assert sources["prerecorded-pytorch"].remote_root == "/home/user/Downloads/jscc-test/jscc/infer_outputs"
    assert sources["prerecorded-tvm"].remote_root == "/home/user/Downloads/jscc-test/jscc/infer_outputs"
    assert sources["prerecorded-mnn"].remote_root == "/home/user/Downloads/jscc-test/mnn_benchmark_outputs"
    assert sources["usrp-qpsk"].remote_root == "/home/user/Downloads/jscc-test-usrp/qpsk/tvm"
    assert sources["usrp-iq-direct"].remote_root == "/home/user/Downloads/jscc-test-usrp/iq-direct/tvm"
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


def test_build_remote_plan_uses_local_evidence_and_reversible_remote_paths(tmp_path: Path):
    run_root = tmp_path / "runs"
    base_job = "openamp3_usrp_123_current"
    recovery_job = "openamp3_usrp_123_recovery_current"
    _write_summary(run_root, base_job, {"phy": "analog-latent-iq"})

    plan = build_remote_migration_plan(
        [recovery_job],
        run_root,
        "/home/user/Downloads/jscc-test/jscc/infer_outputs",
        "/home/user/Downloads/jscc-test-usrp",
    )

    assert plan == [
        {
            "source": f"/home/user/Downloads/jscc-test/jscc/infer_outputs/{recovery_job}",
            "destination": f"/home/user/Downloads/jscc-test-usrp/iq-direct/tvm/{recovery_job}",
            "mode": "usrp-iq-direct",
            "reason": "classified from batch_spool_summary.json",
            "classification": "inherited-base-summary",
            "evidence": base_job,
        }
    ]


def test_discovery_unions_legacy_and_destination_roots_for_idempotence(tmp_path: Path):
    run_root = tmp_path / "runs"
    legacy_root = "/home/user/Downloads/jscc-test-usrp/tvm"
    output_root = "/home/user/Downloads/jscc-test-usrp"
    legacy_job = "openamp3_usrp_100_current"
    qpsk_job = "openamp3_usrp_200_current"
    iq_job = "openamp3_usrp_300_current"
    _write_summary(run_root, legacy_job, {"max_arq_rounds": 2})
    _write_summary(run_root, qpsk_job, {"chunk_bytes": 4096})
    _write_summary(run_root, iq_job, {"phy": "analog-latent-iq"})
    qpsk_destination = f"{output_root}/qpsk/tvm/{qpsk_job}"
    iq_destination = f"{output_root}/iq-direct/tvm/{iq_job}"
    fake_sftp = FakeSFTP(
        {
            f"{legacy_root}/{legacy_job}",
            qpsk_destination,
            iq_destination,
        },
        {
            legacy_root: [legacy_job, "prerecorded_job"],
            f"{output_root}/qpsk/tvm": [qpsk_job],
            f"{output_root}/iq-direct/tvm": [iq_job],
        },
    )

    job_names = collect_remote_job_names(fake_sftp, legacy_root, output_root)
    plan = build_remote_migration_plan(job_names, run_root, legacy_root, output_root)
    result = apply_migration(fake_sftp, plan, apply=False)

    assert job_names == [legacy_job, qpsk_job, iq_job]
    assert len(result["classified"]) == 3
    assert {entry["destination"] for entry in result["already_moved"]} == {
        qpsk_destination,
        iq_destination,
    }


def test_write_report_atomic_is_deterministic(tmp_path: Path):
    report_path = tmp_path / "reports" / "migration.json"
    payload = {"moved": [], "classified": [{"source": "/legacy/job"}]}

    write_report_atomic(report_path, payload)

    assert report_path.read_text(encoding="utf-8") == (
        '{\n  "classified": [\n    {\n      "source": "/legacy/job"\n    }\n  ],\n'
        '  "moved": []\n}\n'
    )
    assert list(report_path.parent.iterdir()) == [report_path]


def test_migration_script_runs_as_a_direct_cli():
    repository_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [sys.executable, "scripts/migrate_usrp_output_layout.py", "--help"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_migration_cli_defaults_to_historical_usrp_legacy_root():
    args = parse_args(
        ["--host", "board", "--user", "user", "--password", "user"]
    )

    assert args.legacy_root == "/home/user/Downloads/jscc-test-usrp/tvm"


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


def test_plan_usrp_migration_checks_exact_recovery_across_all_roots_before_base(tmp_path: Path):
    run_root = tmp_path / "runs"
    legacy_root = tmp_path / "legacy"
    output_root = tmp_path / "outputs"
    _write_summary(run_root, "openamp3_usrp_123_current", {"max_arq_rounds": 2, "chunk_bytes": 4096})
    _write_summary(legacy_root, "openamp3_usrp_123_recovery_current", {"phy": "analog-latent-iq"})

    decisions = plan_usrp_migration(
        ["openamp3_usrp_123_recovery_current"], run_root, legacy_root, output_root
    )

    assert decisions[0]["source"] == str(legacy_root / "openamp3_usrp_123_recovery_current")
    assert decisions[0]["mode"] == "usrp-iq-direct"


def test_plan_usrp_migration_reports_existing_destination_collision(tmp_path: Path):
    run_root = tmp_path / "runs"
    legacy_root = tmp_path / "legacy"
    output_root = tmp_path / "outputs"
    job_name = "openamp3_usrp_123_current"
    _write_summary(run_root, job_name, {"max_arq_rounds": 2, "chunk_bytes": 4096})
    destination = output_root / "qpsk" / "tvm" / job_name

    decisions = plan_usrp_migration(
        [job_name],
        run_root,
        legacy_root,
        output_root,
        existing_destinations=[str(destination)],
    )

    assert decisions[0]["mode"] == "usrp-qpsk"
    assert decisions[0]["destination"] is None
    assert decisions[0]["reason"] == "destination already exists"
