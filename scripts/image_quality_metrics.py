from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class QualityMetrics:
    psnr_db: float | None
    ssim: float | None
    chroma_mae: float | None
    shape_match: bool


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float32)


def global_ssim(reference: np.ndarray, candidate: np.ndarray) -> float:
    max_value = 255.0
    c1 = (0.01 * max_value) ** 2
    c2 = (0.03 * max_value) ** 2
    reference_mean = float(reference.mean())
    candidate_mean = float(candidate.mean())
    reference_variance = float(reference.var())
    candidate_variance = float(candidate.var())
    covariance = float(
        ((reference - reference_mean) * (candidate - candidate_mean)).mean()
    )
    numerator = (
        (2.0 * reference_mean * candidate_mean + c1)
        * (2.0 * covariance + c2)
    )
    denominator = (
        (reference_mean**2 + candidate_mean**2 + c1)
        * (reference_variance + candidate_variance + c2)
    )
    if denominator == 0.0:
        return 1.0 if np.array_equal(reference, candidate) else 0.0
    return numerator / denominator


def measure_rgb_quality(reference_path: Path, candidate_path: Path) -> QualityMetrics:
    reference = _load_rgb(Path(reference_path))
    candidate = _load_rgb(Path(candidate_path))
    if reference.shape != candidate.shape:
        return QualityMetrics(None, None, None, False)

    difference = candidate - reference
    mse = float(np.mean(np.square(difference)))
    psnr_db = (
        math.inf
        if mse == 0.0
        else 20.0 * math.log10(255.0) - 10.0 * math.log10(mse)
    )
    channel_spread = np.max(difference, axis=2) - np.min(difference, axis=2)
    return QualityMetrics(
        psnr_db=psnr_db,
        ssim=float(global_ssim(reference, candidate)),
        chroma_mae=float(np.mean(np.abs(channel_spread))),
        shape_match=True,
    )
