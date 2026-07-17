from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable, Mapping, Sequence

try:
    from scripts.image_quality_metrics import measure_rgb_quality
except ModuleNotFoundError:
    from image_quality_metrics import measure_rgb_quality


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
        lowest_correlation >= minimum_spearman
        and lowest_overlap >= minimum_top_overlap
    )
    full_run_count = 1 if rankings_identical else (2 if stable else 3)
    return StabilityReport(
        stable=stable,
        full_run_count=full_run_count,
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


def _manifest_path(value: object, manifest_path: Path) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else (manifest_path.parent / path).resolve()


def load_quality_rows(
    original_dir: Path,
    manifest_paths: Sequence[Path],
) -> list[QualityRow]:
    original_root = Path(original_dir).resolve()
    originals_by_name = {
        path.name.casefold(): path
        for path in original_root.iterdir()
        if path.is_file()
    }
    originals_by_stem = {path.stem.casefold(): path for path in originals_by_name.values()}
    rows: list[QualityRow] = []
    for manifest_value in manifest_paths:
        manifest_path = Path(manifest_value).resolve()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise ValueError(f"manifest has no records list: {manifest_path}")
        default_seed = int(payload.get("seed", 0))
        for record in records:
            if not isinstance(record, dict):
                continue
            source_name = str(
                record.get("source_name")
                or (record.get("latent_metadata") or {}).get("original_filename")
                or ""
            ).strip()
            source_path_value = str(record.get("source_path") or "").strip()
            source_path = Path(source_path_value) if source_path_value else None
            if source_path is None or not source_path.is_file():
                source_path = originals_by_name.get(source_name.casefold())
                if source_path is None:
                    source_path = originals_by_stem.get(Path(source_name).stem.casefold())
            if source_path is None or not source_path.is_file():
                raise FileNotFoundError(f"original image unavailable for {source_name}")
            output_path = _manifest_path(record.get("output_path"), manifest_path)
            if not output_path.is_file():
                raise FileNotFoundError(f"PyTorch output unavailable: {output_path}")
            metrics = measure_rgb_quality(source_path, output_path)
            if (
                not metrics.shape_match
                or metrics.psnr_db is None
                or metrics.ssim is None
                or metrics.chroma_mae is None
            ):
                raise ValueError(f"shape mismatch for {source_name}: {output_path}")
            rows.append(
                QualityRow(
                    source_name=source_path.name,
                    run_seed=int(record.get("run_seed", default_seed)),
                    psnr_db=metrics.psnr_db,
                    ssim=metrics.ssim,
                    chroma_mae=metrics.chroma_mae,
                )
            )
    return rows


def write_ranking_outputs(
    *,
    quality_rows: Sequence[QualityRow],
    usrp_rows: Sequence[UsrpEvidence],
    output_dir: Path,
    candidate_limit: int,
    final_limit: int,
) -> dict[str, Path | None]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    ranked = rank_showcase_samples(
        quality_rows,
        usrp_rows,
        limit=len({row.source_name for row in quality_rows}),
    )
    ranking_json = output_root / "pytorch_quality_ranking.json"
    ranking_csv = output_root / "pytorch_quality_ranking.csv"
    candidates_json = output_root / "showcase_candidates.json"
    ranking_payload = {
        "sample_count": len(ranked),
        "quality_run_count": max((row.run_count for row in ranked), default=0),
        "samples": [row.to_dict() for row in ranked],
    }
    ranking_json.write_text(
        json.dumps(ranking_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fieldnames = list(RankedSample.__dataclass_fields__)
    with ranking_csv.open("w", encoding="utf-8-sig", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row.to_dict() for row in ranked)
    candidates = ranked[:candidate_limit]
    candidates_json.write_text(
        json.dumps(
            {
                "candidate_limit": candidate_limit,
                "samples": [row.to_dict() for row in candidates],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    qualified = [row for row in ranked if row.has_usrp_evidence]
    selected_manifest: Path | None = None
    if len(qualified) >= final_limit:
        selected_manifest = output_root / "selected_300_manifest.json"
        selected_manifest.write_text(
            json.dumps(
                {
                    "final_limit": final_limit,
                    "samples": [row.to_dict() for row in qualified[:final_limit]],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return {
        "ranking_json": ranking_json,
        "ranking_csv": ranking_csv,
        "candidates_json": candidates_json,
        "selected_manifest": selected_manifest,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank PyTorch and USRP showcase samples.")
    parser.add_argument("--original-dir", required=True, type=Path)
    parser.add_argument("--pytorch-manifest", required=True, type=Path, action="append")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--candidate-limit", type=int, default=600)
    parser.add_argument("--final-limit", type=int, default=300)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    quality_rows = load_quality_rows(args.original_dir, args.pytorch_manifest)
    paths = write_ranking_outputs(
        quality_rows=quality_rows,
        usrp_rows=[],
        output_dir=args.output_dir,
        candidate_limit=args.candidate_limit,
        final_limit=args.final_limit,
    )
    print(json.dumps({key: str(value) if value else None for key, value in paths.items()}))


if __name__ == "__main__":
    main()
