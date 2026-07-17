from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
SESSION_SCRIPTS_ROOT = PROJECT_ROOT / "Semantic-Communication" / "session_bootstrap" / "scripts"
if str(SESSION_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SESSION_SCRIPTS_ROOT))

from artifact_guard import verify_artifact
from output_shape_utils import analyze_shape_pair
from replay_guard import E_DUPLICATE_JOB, ReplayGuard


def test_sfit03_artifact_guard_rejects_tampered_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "model.so"
    artifact.write_bytes(b"trusted-model")
    trusted_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.write_bytes(b"tampered-model")

    result = verify_artifact(str(artifact), trusted_sha)

    assert result["status"] == "deny"
    assert result["error_code"] == "E_ARTIFACT_SHA_MISMATCH"


def test_sfit04_missing_trusted_kem_backend_rejects_session() -> None:
    from mlkem_link import kem

    with (
        mock.patch.object(kem, "TongsuoBackend", side_effect=RuntimeError("disabled")),
        mock.patch.object(kem, "LibOQSBackend", side_effect=RuntimeError("disabled")),
        mock.patch.object(kem, "_detect_oqs_install_path", return_value=""),
        pytest.raises(RuntimeError, match="拒绝建立不安全会话"),
    ):
        kem.get_backend("768")


def test_sfit07_replay_guard_rejects_duplicate_job_sequence(tmp_path: Path) -> None:
    with mock.patch.dict(os.environ, {"ARTIFACT_GUARD_LOG_DIR": str(tmp_path)}):
        guard = ReplayGuard(window_size=16)
        try:
            assert guard.check_and_record("job-001", 7) == ("allow", None)
            assert guard.check_and_record("job-001", 7) == ("deny", E_DUPLICATE_JOB)
        finally:
            guard.close()


def test_sfit06_abnormal_output_is_detected_and_auditable(tmp_path: Path) -> None:
    result = analyze_shape_pair(
        [1, 3, 249, 249],
        [1, 3, 256, 256],
        left_label="expected",
        right_label="actual",
    )
    evidence = tmp_path / "output_shape_audit.json"
    evidence.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")

    persisted = json.loads(evidence.read_text(encoding="utf-8"))
    assert persisted["shapes_match"] is False
    assert persisted["relation"] == "spatial_mismatch"
    assert persisted["common_shape"] == [1, 3, 249, 249]
