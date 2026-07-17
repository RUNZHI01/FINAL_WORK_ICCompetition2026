#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch


def latent_original_name(path: Path) -> str:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        return ""
    return Path(str(payload.get("original_filename") or "")).stem


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a ranked USRP latent input manifest")
    parser.add_argument("--selection-report", type=Path, required=True)
    parser.add_argument("--image-dir", type=Path, required=True)
    parser.add_argument("--latent-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.selection_report.read_text(encoding="utf-8"))
    ranks = {
        Path(str(record.get("source_name") or "")).stem: int(record["rank"])
        for record in report.get("samples", [])
        if record.get("source_name") and record.get("rank") is not None
    }
    final_names = {path.stem for path in args.image_dir.iterdir() if path.is_file()}
    latent_records = []
    for path in args.latent_dir.glob("*.pt"):
        original = latent_original_name(path)
        if original in final_names:
            latent_records.append((ranks.get(original, 1_000_000), original, path.name))
    latent_records.sort()
    if len(latent_records) != len(final_names):
        raise RuntimeError(
            f"image/latent mapping mismatch: images={len(final_names)} latents={len(latent_records)}"
        )

    lines = ["# latent_filename\toriginal_filename\tquality_rank"]
    lines.extend(f"{latent}\t{original}.jpg\t{rank}" for rank, original, latent in latent_records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"order_manifest={args.output} count={len(latent_records)} top100={min(100, len(latent_records))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
