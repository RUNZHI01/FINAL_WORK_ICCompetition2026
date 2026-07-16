from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from scripts.board_image_compare.core import (
    QualityMetrics,
    ResourceGate,
    ResourceSnapshot,
    is_color_noise,
    pair_images,
)


def test_manifest_names_override_natural_sort(tmp_path: Path) -> None:
    originals = [tmp_path / "a.png", tmp_path / "b.png"]
    reconstructions = [
        PurePosixPath("/remote/00000000_recon.png"),
        PurePosixPath("/remote/00000001_recon.png"),
    ]

    pairs = pair_images(originals, reconstructions, {0: "b.jpg", 1: "a.png"})

    assert [pair.original.name if pair.original else None for pair in pairs] == ["b.png", "a.png"]
    assert [pair.original_name for pair in pairs] == ["b.jpg", "a.png"]


def test_missing_side_stays_at_same_index(tmp_path: Path) -> None:
    pairs = pair_images(
        [tmp_path / "a.png"],
        [PurePosixPath("/remote/00000001_recon.png")],
    )

    assert len(pairs) == 2
    assert pairs[0].original == tmp_path / "a.png"
    assert pairs[0].reconstruction is None
    assert pairs[1].original is None
    assert pairs[1].reconstruction == PurePosixPath("/remote/00000001_recon.png")


def test_color_noise_requires_low_similarity_and_chroma_error() -> None:
    noisy = QualityMetrics(
        psnr_db=9.0,
        ssim=0.05,
        chroma_mae=58.0,
        shape_match=True,
    )
    blurry_but_plausible = QualityMetrics(
        psnr_db=13.0,
        ssim=0.30,
        chroma_mae=12.0,
        shape_match=True,
    )

    assert is_color_noise(noisy, []).suspected is True
    assert is_color_noise(blurry_but_plausible, []).suspected is False


def test_job_outlier_rule_needs_ten_reference_samples() -> None:
    history = [
        QualityMetrics(psnr_db=25.0, ssim=0.82, chroma_mae=8.0, shape_match=True)
        for _ in range(10)
    ]
    outlier = QualityMetrics(psnr_db=18.0, ssim=0.50, chroma_mae=28.0, shape_match=True)

    verdict = is_color_noise(outlier, history)

    assert verdict.suspected is True
    assert verdict.reason == "job_outlier"


@pytest.mark.parametrize(
    ("cpu", "memory", "paused", "action"),
    [
        (84.9, 20.0, False, "allow"),
        (85.0, 20.0, False, "pause"),
        (20.0, 90.0, False, "abort"),
        (80.0, 20.0, True, "pause"),
        (79.9, 20.0, True, "allow"),
    ],
)
def test_resource_gate_hysteresis(
    cpu: float,
    memory: float,
    paused: bool,
    action: str,
) -> None:
    gate = ResourceGate(paused=paused)

    decision = gate.evaluate(ResourceSnapshot(cpu_percent=cpu, memory_percent=memory))

    assert decision.action == action
