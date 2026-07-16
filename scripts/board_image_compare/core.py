from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from statistics import median
from typing import Iterable, Mapping, Sequence

import numpy as np
from PIL import Image


RECONSTRUCTION_INDEX_PATTERN = re.compile(r"^(\d+)(?:_recon)?\.[^.]+$", re.IGNORECASE)


def natural_key(value: str) -> tuple[object, ...]:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", value)
    )


@dataclass(frozen=True)
class ImagePair:
    index: int
    original: Path | None
    reconstruction: PurePosixPath | None
    original_name: str = ""


def _reconstruction_index(path: PurePosixPath) -> int | None:
    match = RECONSTRUCTION_INDEX_PATTERN.match(path.name)
    return int(match.group(1)) if match else None


def pair_images(
    originals: Iterable[Path],
    reconstructions: Iterable[PurePosixPath],
    manifest_names: Mapping[int, str] | None = None,
) -> list[ImagePair]:
    ordered_originals = sorted((Path(path) for path in originals), key=lambda path: natural_key(path.name))
    original_by_stem = {path.stem.casefold(): path for path in ordered_originals}
    reconstruction_by_index: dict[int, PurePosixPath] = {}
    for value in reconstructions:
        path = PurePosixPath(value)
        index = _reconstruction_index(path)
        if index is not None:
            reconstruction_by_index.setdefault(index, path)

    names = manifest_names or {}
    task_last_index = max(
        max(reconstruction_by_index, default=-1),
        max(names, default=-1),
    )
    pair_count = task_last_index + 1 if task_last_index >= 0 else len(ordered_originals)
    pairs: list[ImagePair] = []
    for index in range(pair_count):
        manifest_name = str(names.get(index, "")).strip()
        if manifest_name:
            original = original_by_stem.get(Path(manifest_name).stem.casefold())
        else:
            original = ordered_originals[index] if index < len(ordered_originals) else None
        pairs.append(
            ImagePair(
                index=index,
                original=original,
                reconstruction=reconstruction_by_index.get(index),
                original_name=manifest_name,
            )
        )
    return pairs


@dataclass(frozen=True)
class QualityMetrics:
    psnr_db: float | None
    ssim: float | None
    chroma_mae: float | None
    shape_match: bool


@dataclass(frozen=True)
class QualityVerdict:
    suspected: bool
    reason: str


def _global_ssim(original: np.ndarray, reconstruction: np.ndarray) -> float:
    max_value = 255.0
    c1 = (0.01 * max_value) ** 2
    c2 = (0.03 * max_value) ** 2
    mu_original = float(original.mean())
    mu_reconstruction = float(reconstruction.mean())
    var_original = float(original.var())
    var_reconstruction = float(reconstruction.var())
    covariance = float(((original - mu_original) * (reconstruction - mu_reconstruction)).mean())
    numerator = (2.0 * mu_original * mu_reconstruction + c1) * (2.0 * covariance + c2)
    denominator = (
        (mu_original**2 + mu_reconstruction**2 + c1)
        * (var_original + var_reconstruction + c2)
    )
    if denominator == 0.0:
        return 1.0 if np.array_equal(original, reconstruction) else 0.0
    return numerator / denominator


def measure_quality(original_path: Path, reconstruction_path: Path) -> QualityMetrics:
    with Image.open(original_path) as original_image:
        original = np.asarray(original_image.convert("RGB"), dtype=np.float32)
    with Image.open(reconstruction_path) as reconstruction_image:
        reconstruction = np.asarray(reconstruction_image.convert("RGB"), dtype=np.float32)
    if original.shape != reconstruction.shape:
        return QualityMetrics(None, None, None, False)

    difference = reconstruction - original
    mse = float(np.mean(np.square(difference)))
    psnr_db = math.inf if mse == 0.0 else 20.0 * math.log10(255.0) - 10.0 * math.log10(mse)
    channel_spread = np.max(difference, axis=2) - np.min(difference, axis=2)
    return QualityMetrics(
        psnr_db=psnr_db,
        ssim=float(_global_ssim(original, reconstruction)),
        chroma_mae=float(np.mean(np.abs(channel_spread))),
        shape_match=True,
    )


def _complete_history(history: Sequence[QualityMetrics]) -> list[QualityMetrics]:
    return [
        item
        for item in history
        if item.shape_match
        and item.psnr_db is not None
        and item.ssim is not None
        and math.isfinite(item.psnr_db)
    ]


def is_color_noise(
    metrics: QualityMetrics,
    job_history: Sequence[QualityMetrics],
) -> QualityVerdict:
    if (
        not metrics.shape_match
        or metrics.psnr_db is None
        or metrics.ssim is None
        or metrics.chroma_mae is None
    ):
        return QualityVerdict(False, "insufficient_data")
    if metrics.psnr_db < 14.0 and metrics.ssim < 0.35 and metrics.chroma_mae > 25.0:
        return QualityVerdict(True, "absolute_threshold")

    history = _complete_history(job_history)
    if len(history) >= 10 and metrics.chroma_mae > 20.0:
        median_psnr = median(item.psnr_db for item in history if item.psnr_db is not None)
        median_ssim = median(item.ssim for item in history if item.ssim is not None)
        if metrics.psnr_db <= median_psnr - 5.0 and metrics.ssim <= median_ssim - 0.20:
            return QualityVerdict(True, "job_outlier")
    return QualityVerdict(False, "within_expected_range")


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu_percent: float
    memory_percent: float


@dataclass(frozen=True)
class GateDecision:
    action: str
    reason: str


class ResourceGate:
    def __init__(
        self,
        *,
        paused: bool = False,
        pause_percent: float = 85.0,
        abort_percent: float = 90.0,
        resume_below_percent: float = 80.0,
    ) -> None:
        self.paused = paused
        self.pause_percent = pause_percent
        self.abort_percent = abort_percent
        self.resume_below_percent = resume_below_percent

    def evaluate(self, snapshot: ResourceSnapshot) -> GateDecision:
        peak = max(snapshot.cpu_percent, snapshot.memory_percent)
        if peak >= self.abort_percent:
            self.paused = True
            return GateDecision("abort", "board_resource_hard_limit")
        if self.paused:
            if peak >= self.resume_below_percent:
                return GateDecision("pause", "board_resource_recovery_wait")
            self.paused = False
            return GateDecision("allow", "board_resource_recovered")
        if peak >= self.pause_percent:
            self.paused = True
            return GateDecision("pause", "board_resource_soft_limit")
        return GateDecision("allow", "board_resource_available")
