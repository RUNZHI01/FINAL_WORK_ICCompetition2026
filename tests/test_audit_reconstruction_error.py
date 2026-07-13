import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_reconstruction_error import audit_reconstructions, main


def write_rgb(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(np.asarray(pixels, dtype=np.uint8), mode="RGB").save(path)


def test_audit_reconstructions_reports_pixel_error_metrics(tmp_path: Path) -> None:
    originals = tmp_path / "originals"
    recons = tmp_path / "recons"
    originals.mkdir()
    recons.mkdir()

    base = np.zeros((2, 2, 3), dtype=np.uint8)
    changed = base.copy()
    changed[0, 0, :] = 10

    write_rgb(originals / "frame_0001.png", base)
    write_rgb(recons / "frame_0001_recon.png", changed)
    write_rgb(originals / "frame_0002.jpg", base)
    write_rgb(recons / "frame_0002_recon.png", base)

    result = audit_reconstructions(
        original_dir=originals,
        recon_dir=recons,
        sample_size=10,
        seed=0,
    )

    assert result["candidate_count"] == 2
    assert result["audited_count"] == 2
    records = {record["stem"]: record for record in result["records"]}

    changed_record = records["frame_0001"]
    assert changed_record["status"] == "ok"
    assert changed_record["shape_match"] is True
    assert changed_record["mse"] == pytest.approx(25.0)
    assert changed_record["rmse"] == pytest.approx(5.0)
    assert changed_record["mae"] == pytest.approx(2.5)
    assert changed_record["max_abs_diff"] == pytest.approx(10.0)
    assert changed_record["p95_abs_diff"] == pytest.approx(10.0)
    assert changed_record["pixel_equal_ratio"] == pytest.approx(0.75)
    assert changed_record["psnr_db"] == pytest.approx(34.1514, rel=1e-4)
    assert changed_record["ssim"] < 1.0

    identical_record = records["frame_0002"]
    assert identical_record["mse"] == pytest.approx(0.0)
    assert math.isinf(identical_record["psnr_db"])
    assert identical_record["ssim"] == pytest.approx(1.0)
    assert identical_record["pixel_equal_ratio"] == pytest.approx(1.0)

    aggregate = result["aggregate"]
    assert aggregate["mean_mse"] == pytest.approx(12.5)
    assert aggregate["mean_pixel_equal_ratio"] == pytest.approx(0.875)


def test_cli_samples_deterministically_and_writes_json_csv(tmp_path: Path) -> None:
    originals = tmp_path / "originals"
    recons = tmp_path / "recons"
    originals.mkdir()
    recons.mkdir()

    for index in range(5):
        pixels = np.full((2, 2, 3), index, dtype=np.uint8)
        write_rgb(originals / f"image_{index:04d}.png", pixels)
        write_rgb(recons / f"image_{index:04d}_recon.png", pixels)

    output_json = tmp_path / "audit.json"
    output_csv = tmp_path / "audit.csv"

    rc = main(
        [
            "--original-dir",
            str(originals),
            "--recon-dir",
            str(recons),
            "--sample-size",
            "2",
            "--seed",
            "11",
            "--output-json",
            str(output_json),
            "--output-csv",
            str(output_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    json.dumps(payload, allow_nan=False)
    assert payload["candidate_count"] == 5
    assert payload["audited_count"] == 2
    assert all(record["psnr_db"] == "Infinity" for record in payload["records"])
    first_stems = [record["stem"] for record in payload["records"]]

    rc = main(
        [
            "--original-dir",
            str(originals),
            "--recon-dir",
            str(recons),
            "--sample-size",
            "2",
            "--seed",
            "11",
            "--output-json",
            str(output_json),
        ]
    )
    assert rc == 0
    repeated = json.loads(output_json.read_text(encoding="utf-8"))
    assert [record["stem"] for record in repeated["records"]] == first_stems

    with output_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["stem"] for row in rows] == first_stems
    assert all(row["status"] == "ok" for row in rows)
