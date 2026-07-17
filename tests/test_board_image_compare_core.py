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


def test_reconstruction_batch_does_not_include_trailing_source_images(tmp_path: Path) -> None:
    originals = [tmp_path / f"{index:08d}.jpg" for index in range(5)]
    reconstructions = [
        PurePosixPath("/remote/00000000_recon.png"),
        PurePosixPath("/remote/00000001_recon.png"),
    ]

    pairs = pair_images(originals, reconstructions)

    assert len(pairs) == 2
    assert [pair.original for pair in pairs] == originals[:2]


def test_hash_named_reconstruction_pairs_with_matching_original(tmp_path: Path) -> None:
    source_hash = "b8a2ee65a3f1e97a3447a3c13900f19a121c2c87a537a8cf3fb77fd45a8f49f2"
    original = tmp_path / f"{source_hash}.jpg"
    reconstruction = PurePosixPath(f"/remote/{source_hash}_recon.png")

    pairs = pair_images([original], [reconstruction])

    assert len(pairs) == 1
    assert pairs[0].original == original
    assert pairs[0].reconstruction == reconstruction


def test_hash_only_reconstructions_exclude_unrelated_trailing_originals(tmp_path: Path) -> None:
    source_hash = "b8a2ee65a3f1e97a3447a3c13900f19a121c2c87a537a8cf3fb77fd45a8f49f2"
    original = tmp_path / f"{source_hash}.jpg"
    unrelated = tmp_path / "zz_unrelated.jpg"
    reconstruction = PurePosixPath(f"/remote/{source_hash}_recon.png")

    pairs = pair_images([original, unrelated], [reconstruction])

    assert len(pairs) == 1
    assert pairs[0].index == 0
    assert pairs[0].original == original
    assert pairs[0].reconstruction == reconstruction


def test_mixed_numeric_and_hash_reconstructions_preserve_numeric_range(tmp_path: Path) -> None:
    source_hash = "b8a2ee65a3f1e97a3447a3c13900f19a121c2c87a537a8cf3fb77fd45a8f49f2"
    numeric_original = tmp_path / "00000000.jpg"
    hash_original = tmp_path / f"{source_hash}.jpg"
    unrelated = tmp_path / "zz_unrelated.jpg"
    numeric_reconstruction = PurePosixPath("/remote/00000000_recon.png")
    hash_reconstruction = PurePosixPath(f"/remote/{source_hash}_recon.png")

    pairs = pair_images(
        [numeric_original, hash_original, unrelated],
        [numeric_reconstruction, hash_reconstruction],
    )

    assert len(pairs) == 2
    assert [(pair.index, pair.original, pair.reconstruction) for pair in pairs] == [
        (0, numeric_original, numeric_reconstruction),
        (1, hash_original, hash_reconstruction),
    ]


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
