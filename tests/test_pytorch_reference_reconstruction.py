from __future__ import annotations

import importlib.util
import hashlib
import sys
from pathlib import Path

import pytest
import torch

from scripts.rank_showcase_samples import assess_ranking_stability


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / "Semantic-Communication"
    / "session_bootstrap"
    / "scripts"
    / "pytorch_reference_reconstruction.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("pytorch_reference_for_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_source_provenance_uses_latent_manifest_mapping(tmp_path: Path) -> None:
    module = _load_module()
    latent = tmp_path / "abc_latent.pt"
    source_index = {
        "abc_latent.pt": {
            "source_image": "E:/images/00000001.jpg",
            "source_image_rel": "00000001.jpg",
            "source_image_sha256": "a" * 64,
        }
    }

    provenance = module.source_provenance(
        latent,
        {"original_filename": "00000001"},
        source_index,
    )

    assert provenance == {
        "source_name": "00000001.jpg",
        "source_path": "E:/images/00000001.jpg",
        "source_sha256": "a" * 64,
    }


def test_source_provenance_falls_back_to_embedded_name(tmp_path: Path) -> None:
    module = _load_module()

    provenance = module.source_provenance(
        tmp_path / "abc_latent.pt",
        {"original_filename": "00000001"},
        {},
    )

    assert provenance["source_name"] == "00000001"
    assert provenance["source_path"] is None
    assert provenance["source_sha256"] is None


def test_load_pt_latent_validates_checksum_before_float_conversion(tmp_path: Path) -> None:
    module = _load_module()
    quant = torch.tensor([[[1, 2], [3, 4]]], dtype=torch.uint8)
    latent_path = tmp_path / "sample.pt"
    torch.save(
        {
            "quant": quant,
            "scale": torch.tensor(0.5),
            "zero_point": torch.tensor(2.0),
            "checksum": hashlib.md5(quant.numpy().tobytes()).hexdigest(),
        },
        latent_path,
    )

    latent, metadata = module.load_pt_latent(latent_path)

    assert tuple(latent.shape) == (1, 1, 2, 2)
    assert metadata["quant_checksum"] == hashlib.md5(quant.numpy().tobytes()).hexdigest()


def test_same_seed_hash_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="same-seed output mismatch"):
        assess_ranking_stability(
            same_seed_hash_runs=[{"a": "hash-1"}, {"a": "hash-2"}],
            cross_seed_rankings=[["a", "b"], ["a", "b"], ["a", "b"]],
        )


def test_stable_cross_seed_probe_requires_one_full_run() -> None:
    report = assess_ranking_stability(
        same_seed_hash_runs=[{"a": "hash-1"}, {"a": "hash-1"}],
        cross_seed_rankings=[
            ["a", "b", "c", "d", "e"],
            ["a", "b", "c", "d", "e"],
            ["a", "b", "c", "d", "e"],
        ],
    )

    assert report.full_run_count == 1
    assert report.stable is True


def test_unstable_cross_seed_probe_requires_three_full_runs() -> None:
    report = assess_ranking_stability(
        same_seed_hash_runs=[{"a": "hash-1"}, {"a": "hash-1"}],
        cross_seed_rankings=[
            ["a", "b", "c", "d", "e"],
            ["e", "d", "c", "b", "a"],
            ["b", "c", "d", "e", "a"],
        ],
    )

    assert report.full_run_count == 3
    assert report.stable is False


def test_correlated_but_different_rankings_stop_after_two_run_average() -> None:
    baseline = [f"sample-{index:03d}" for index in range(100)]
    changed = list(baseline)
    changed[-1], changed[-2] = changed[-2], changed[-1]

    report = assess_ranking_stability(
        same_seed_hash_runs=[{"a": "hash-1"}, {"a": "hash-1"}],
        cross_seed_rankings=[baseline, changed, baseline],
    )

    assert report.minimum_spearman >= 0.98
    assert report.minimum_top_overlap == 1.0
    assert report.full_run_count == 2
    assert report.stable is True
