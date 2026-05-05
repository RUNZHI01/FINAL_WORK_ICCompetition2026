#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TVM_SRC = PROJECT_ROOT / "tvm-src"
TIR_PATH = PROJECT_ROOT / "session_bootstrap/handwritten/fused_conv2d_transpose_add6/fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py"
OUT_DIR = PROJECT_ROOT / "session_bootstrap/tmp" / f"transpose_add6_standalone_v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(TVM_SRC / "python"))
os.environ.setdefault("TVM_LIBRARY_PATH", str(TVM_SRC / "build"))
os.environ["LD_LIBRARY_PATH"] = f"{TVM_SRC / 'build'}:{os.environ.get('LD_LIBRARY_PATH','')}"

import tvm  # type: ignore


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

module_name = "_transpose_add6_v1_standalone"
ns = {"__file__": str(TIR_PATH), "__name__": module_name}
mod_stub = type(sys)(module_name)
mod_stub.__file__ = str(TIR_PATH)
sys.modules[module_name] = mod_stub
exec(compile(TIR_PATH.read_text(encoding='utf-8'), str(TIR_PATH), 'exec'), ns)
mod = ns["Module"]
func = mod["fused_conv2d_transpose_add6"]

target = tvm.target.Target({
    "kind": "llvm",
    "mtriple": "aarch64-linux-gnu",
    "mcpu": "cortex-a72",
    "mattr": ["+neon"],
    "num-cores": 4,
})

rt_mod = tvm.build(func, target=target)
out_so = OUT_DIR / "fused_conv2d_transpose_add6_v1_standalone.so"
rt_mod.export_library(str(out_so))
report = {
    "status": "built",
    "tir_path": str(TIR_PATH),
    "artifact_path": str(out_so),
    "artifact_sha256": sha256(out_so),
    "artifact_size_bytes": out_so.stat().st_size,
    "target": str(target),
}
(OUT_DIR / "build_report.json").write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
