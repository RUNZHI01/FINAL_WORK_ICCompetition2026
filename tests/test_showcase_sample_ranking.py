from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from scripts.image_quality_metrics import measure_rgb_quality
from scripts.rank_showcase_samples import (
    QualityRow,
    UsrpEvidence,
    aggregate_quality_runs,
    rank_showcase_samples,
)


def _quality(
    source_name: str,
    run_seed: int,
    psnr_db: float,
    *,
    ssim: float = 0.9,
    chroma_mae: float = 3.0,
) -> QualityRow:
    return QualityRow(
        source_name=source_name,
        run_seed=run_seed,
        psnr_db=psnr_db,
        ssim=ssim,
        chroma_mae=chroma_mae,
    )


def test_measure_rgb_quality_rejects_shape_mismatch(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (8, 8), (20, 30, 40)).save(reference)
    Image.new("RGB", (7, 8), (20, 30, 40)).save(candidate)

    metrics = measure_rgb_quality(reference, candidate)

    assert metrics.shape_match is False
    assert metrics.psnr_db is None
    assert metrics.ssim is None
    assert metrics.chroma_mae is None


def test_aggregate_quality_runs_reports_population_mean_and_std() -> None:
    rows = [
        _quality("00000001.jpg", 0, 30.0, ssim=0.8, chroma_mae=4.0),
        _quality("00000001.jpg", 1, 34.0, ssim=1.0, chroma_mae=2.0),
    ]

    result = aggregate_quality_runs(rows)[0]

    assert result.source_name == "00000001.jpg"
    assert result.run_count == 2
    assert result.psnr_mean == pytest.approx(32.0)
    assert result.psnr_std == pytest.approx(2.0)
    assert result.ssim_mean == pytest.approx(0.9)
    assert result.ssim_std == pytest.approx(0.1)
    assert result.chroma_mae_mean == pytest.approx(3.0)
    assert result.chroma_mae_std == pytest.approx(1.0)


def test_rank_requires_usrp_evidence_before_retry_priority() -> None:
    quality_rows = [
        _quality("00000001.jpg", 0, 40.0),
        _quality("00000002.jpg", 0, 30.0),
        _quality("00000003.jpg", 0, 38.0),
    ]
    usrp_rows = [
        UsrpEvidence(source_name="00000002.jpg", retry_count=0, job_id="job-a"),
        UsrpEvidence(source_name="00000003.jpg", retry_count=2, job_id="job-a"),
    ]

    ranked = rank_showcase_samples(quality_rows, usrp_rows, limit=3)

    assert [row.source_name for row in ranked] == [
        "00000002.jpg",
        "00000003.jpg",
        "00000001.jpg",
    ]
    assert ranked[0].has_usrp_evidence is True
    assert ranked[-1].has_usrp_evidence is False


def test_quality_breakers_are_deterministic() -> None:
    quality_rows = [
        _quality("00000003.jpg", 0, 31.0, ssim=0.90, chroma_mae=2.0),
        _quality("00000002.jpg", 0, 31.0, ssim=0.95, chroma_mae=4.0),
        _quality("00000001.jpg", 0, 31.0, ssim=0.95, chroma_mae=3.0),
    ]
    usrp_rows = [
        UsrpEvidence(source_name=row.source_name, retry_count=0, job_id="job-a")
        for row in quality_rows
    ]

    ranked = rank_showcase_samples(quality_rows, usrp_rows, limit=3)

    assert [row.source_name for row in ranked] == [
        "00000001.jpg",
        "00000002.jpg",
        "00000003.jpg",
    ]
