from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import fmean, pstdev
from typing import Iterable, Sequence


@dataclass(frozen=True)
class QualityRow:
    source_name: str
    run_seed: int
    psnr_db: float
    ssim: float
    chroma_mae: float


@dataclass(frozen=True)
class AggregatedQualityRow:
    source_name: str
    run_count: int
    psnr_mean: float
    psnr_std: float
    ssim_mean: float
    ssim_std: float
    chroma_mae_mean: float
    chroma_mae_std: float


@dataclass(frozen=True)
class UsrpEvidence:
    source_name: str
    retry_count: int
    job_id: str


@dataclass(frozen=True)
class RankedSample:
    rank: int
    source_name: str
    has_usrp_evidence: bool
    retry_count: int | None
    usrp_job_id: str | None
    run_count: int
    psnr_mean: float
    psnr_std: float
    ssim_mean: float
    ssim_std: float
    chroma_mae_mean: float
    chroma_mae_std: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def aggregate_quality_runs(
    rows: Sequence[QualityRow],
) -> list[AggregatedQualityRow]:
    grouped: dict[str, list[QualityRow]] = {}
    for row in rows:
        grouped.setdefault(row.source_name, []).append(row)

    result: list[AggregatedQualityRow] = []
    for source_name in sorted(grouped):
        samples = grouped[source_name]
        psnr_values = [row.psnr_db for row in samples]
        ssim_values = [row.ssim for row in samples]
        chroma_values = [row.chroma_mae for row in samples]
        result.append(
            AggregatedQualityRow(
                source_name=source_name,
                run_count=len(samples),
                psnr_mean=fmean(psnr_values),
                psnr_std=pstdev(psnr_values),
                ssim_mean=fmean(ssim_values),
                ssim_std=pstdev(ssim_values),
                chroma_mae_mean=fmean(chroma_values),
                chroma_mae_std=pstdev(chroma_values),
            )
        )
    return result


def _best_usrp_evidence(rows: Iterable[UsrpEvidence]) -> dict[str, UsrpEvidence]:
    selected: dict[str, UsrpEvidence] = {}
    for row in rows:
        current = selected.get(row.source_name)
        if current is None or (row.retry_count, row.job_id) < (
            current.retry_count,
            current.job_id,
        ):
            selected[row.source_name] = row
    return selected


def rank_showcase_samples(
    quality_rows: Sequence[QualityRow],
    usrp_rows: Sequence[UsrpEvidence],
    limit: int,
) -> list[RankedSample]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    evidence_by_source = _best_usrp_evidence(usrp_rows)
    candidates: list[tuple[tuple[object, ...], AggregatedQualityRow, UsrpEvidence | None]] = []
    for quality in aggregate_quality_runs(quality_rows):
        evidence = evidence_by_source.get(quality.source_name)
        sort_key: tuple[object, ...] = (
            evidence is None,
            evidence.retry_count if evidence is not None else math.inf,
            -quality.psnr_mean,
            -quality.ssim_mean,
            quality.chroma_mae_mean,
            quality.source_name,
        )
        candidates.append((sort_key, quality, evidence))

    ranked: list[RankedSample] = []
    for rank, (_, quality, evidence) in enumerate(sorted(candidates)[:limit], start=1):
        ranked.append(
            RankedSample(
                rank=rank,
                source_name=quality.source_name,
                has_usrp_evidence=evidence is not None,
                retry_count=evidence.retry_count if evidence is not None else None,
                usrp_job_id=evidence.job_id if evidence is not None else None,
                run_count=quality.run_count,
                psnr_mean=quality.psnr_mean,
                psnr_std=quality.psnr_std,
                ssim_mean=quality.ssim_mean,
                ssim_std=quality.ssim_std,
                chroma_mae_mean=quality.chroma_mae_mean,
                chroma_mae_std=quality.chroma_mae_std,
            )
        )
    return ranked
