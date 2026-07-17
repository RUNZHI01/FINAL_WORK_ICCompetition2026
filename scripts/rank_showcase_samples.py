from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import fmean, pstdev
from typing import Iterable, Mapping, Sequence


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


@dataclass(frozen=True)
class StabilityReport:
    stable: bool
    full_run_count: int
    rankings_identical: bool
    minimum_spearman: float
    minimum_top_overlap: float


def _spearman(reference: Sequence[str], candidate: Sequence[str]) -> float:
    if len(reference) != len(candidate) or set(reference) != set(candidate):
        return 0.0
    if len(reference) < 2:
        return 1.0
    candidate_positions = {name: index for index, name in enumerate(candidate)}
    squared_difference = sum(
        (index - candidate_positions[name]) ** 2
        for index, name in enumerate(reference)
    )
    count = len(reference)
    return 1.0 - (6.0 * squared_difference) / (count * (count**2 - 1))


def assess_ranking_stability(
    *,
    same_seed_hash_runs: Sequence[Mapping[str, str]],
    cross_seed_rankings: Sequence[Sequence[str]],
    minimum_spearman: float = 0.98,
    minimum_top_overlap: float = 0.90,
) -> StabilityReport:
    if len(same_seed_hash_runs) < 2:
        raise ValueError("at least two same-seed hash runs are required")
    baseline_hashes = dict(same_seed_hash_runs[0])
    if any(dict(run) != baseline_hashes for run in same_seed_hash_runs[1:]):
        raise ValueError("same-seed output mismatch")
    if len(cross_seed_rankings) < 2:
        raise ValueError("at least two cross-seed rankings are required")

    reference = list(cross_seed_rankings[0])
    top_count = max(1, math.ceil(len(reference) * 0.20))
    reference_top = set(reference[:top_count])
    correlations: list[float] = []
    overlaps: list[float] = []
    for candidate in cross_seed_rankings[1:]:
        candidate_list = list(candidate)
        correlations.append(_spearman(reference, candidate_list))
        overlaps.append(len(reference_top & set(candidate_list[:top_count])) / top_count)

    lowest_correlation = min(correlations)
    lowest_overlap = min(overlaps)
    rankings_identical = all(list(candidate) == reference for candidate in cross_seed_rankings[1:])
    stable = (
        rankings_identical
        and
        lowest_correlation >= minimum_spearman
        and lowest_overlap >= minimum_top_overlap
    )
    return StabilityReport(
        stable=stable,
        full_run_count=1 if stable else 3,
        rankings_identical=rankings_identical,
        minimum_spearman=lowest_correlation,
        minimum_top_overlap=lowest_overlap,
    )


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
