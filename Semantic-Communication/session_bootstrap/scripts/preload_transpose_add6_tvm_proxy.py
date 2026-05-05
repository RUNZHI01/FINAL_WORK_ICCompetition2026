#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import tvm

REMOTE_SO = os.environ.get("TVM_TRANSPOSE_ADD6_PROXY_SO", "").strip()
FUNC_NAME = os.environ.get("TVM_TRANSPOSE_ADD6_PROXY_FUNC", "fused_conv2d_transpose_add6").strip()
REG_NAME = os.environ.get("TVM_TRANSPOSE_ADD6_PROXY_REG", "jscc.acl.transpose_add6").strip()

if not REMOTE_SO:
    raise SystemExit("ERROR: TVM_TRANSPOSE_ADD6_PROXY_SO is required for preload_transpose_add6_tvm_proxy.py")

so_path = Path(REMOTE_SO)
if not so_path.is_file():
    raise SystemExit(f"ERROR: proxy standalone .so not found: {so_path}")

lib = tvm.runtime.load_module(str(so_path))
fn = lib[FUNC_NAME]

@tvm.register_global_func(REG_NAME, override=True)
def _transpose_add6_proxy(inp, weight, bias, out):
    fn(inp, weight, bias, out)
    return 0

print(f"[preload] registered {REG_NAME} via {so_path}::{FUNC_NAME}")
