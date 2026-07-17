from __future__ import annotations

from pathlib import Path

from USRP292x.input_order import INPUT_ORDER_ENV, ordered_directory_inputs


def test_order_manifest_prioritizes_listed_inputs_and_appends_the_rest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for name in ("a_latent.pt", "b_latent.pt", "c_latent.pt"):
        (input_dir / name).write_bytes(name.encode("ascii"))
    order = tmp_path / "showcase_order.tsv"
    order.write_text(
        "# latent_filename\toriginal_filename\trank\n"
        "c_latent.pt\timage-c.jpg\t1\n"
        "a_latent.pt\timage-a.jpg\t2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(INPUT_ORDER_ENV, str(order))

    paths = ordered_directory_inputs(input_dir, "*.pt")

    assert [path.name for path in paths] == ["c_latent.pt", "a_latent.pt", "b_latent.pt"]


def test_missing_order_manifest_keeps_natural_file_order(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    (input_dir / "b.pt").write_bytes(b"b")
    (input_dir / "a.pt").write_bytes(b"a")
    monkeypatch.setenv(INPUT_ORDER_ENV, str(tmp_path / "missing.tsv"))

    assert [path.name for path in ordered_directory_inputs(input_dir, "*.pt")] == ["a.pt", "b.pt"]
