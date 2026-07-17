from __future__ import annotations

import os
from pathlib import Path


INPUT_ORDER_ENV = "USRP_INPUT_ORDER_FILE"


def ordered_directory_inputs(input_dir: Path, pattern: str) -> list[Path]:
    paths = sorted(path for path in input_dir.rglob(pattern) if path.is_file())
    order_value = os.environ.get(INPUT_ORDER_ENV, "").strip()
    if not order_value:
        return paths

    order_path = Path(order_value).expanduser()
    if not order_path.is_file():
        return paths

    by_name = {path.name: path for path in paths}
    ordered: list[Path] = []
    seen: set[Path] = set()
    for raw_line in order_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("\t", 1)[0].strip()
        path = by_name.get(Path(name).name)
        if path is not None and path not in seen:
            ordered.append(path)
            seen.add(path)
    ordered.extend(path for path in paths if path not in seen)
    return ordered
