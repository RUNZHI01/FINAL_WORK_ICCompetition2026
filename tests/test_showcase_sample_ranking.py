from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from scripts.image_quality_metrics import measure_rgb_quality
from scripts.rank_showcase_samples import (
    QualityRow,
    UsrpEvidence,
    aggregate_quality_runs,
    load_quality_rows,
    rank_showcase_samples,
    write_ranking_outputs,
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


def test_load_quality_rows_reads_multiple_pytorch_manifests(tmp_path: Path) -> None:
    original_dir = tmp_path / "originals"
    original_dir.mkdir()
    original = original_dir / "00000001.jpg"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(original)
    manifests = []
    for seed, color in ((0, (10, 20, 30)), (1, (12, 22, 32))):
        output = tmp_path / f"seed-{seed}.png"
        Image.new("RGB", (8, 8), color).save(output)
        manifest = tmp_path / f"seed-{seed}.json"
        manifest.write_text(
            __import__("json").dumps(
                {
                    "seed": seed,
                    "records": [
                        {
                            "source_name": original.name,
                            "source_path": str(original),
                            "output_path": str(output),
                            "run_seed": seed,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        manifests.append(manifest)

    rows = load_quality_rows(original_dir, manifests)

    assert len(rows) == 2
    assert {row.run_seed for row in rows} == {0, 1}
    assert {row.source_name for row in rows} == {"00000001.jpg"}


def test_write_ranking_outputs_keeps_final_manifest_for_usrp_evidence(tmp_path: Path) -> None:
    rows = [_quality(f"{index:08d}.jpg", 0, 40.0 - index) for index in range(1, 5)]

    paths = write_ranking_outputs(
        quality_rows=rows,
        usrp_rows=[],
        output_dir=tmp_path,
        candidate_limit=3,
        final_limit=2,
    )

    assert paths["ranking_json"].is_file()
    assert paths["ranking_csv"].is_file()
    assert paths["candidates_json"].is_file()
    assert paths["selected_manifest"] is None
    candidates = __import__("json").loads(paths["candidates_json"].read_text())
    assert [row["source_name"] for row in candidates["samples"]] == [
        "00000001.jpg",
        "00000002.jpg",
        "00000003.jpg",
    ]
