#!/usr/bin/env python3
"""
conftest.py — pytest 共享配置与后端可用性检测

为 scripts/ 下的 FIT 测试提供后端可用性检测和条件跳过逻辑。
当 Tongsuo 和 liboqs 均不可用时，需要后端的测试自动标记为 SKIP
而不是硬失败（ImportError / RuntimeError）。
"""

import os
import sys

import pytest

# 确保 mlkem_link 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════
# 后端可用性检测
# ══════════════════════════════════════════════


def _check_backend_available():
    """尝试加载 KEM 后端，返回 (可用与否, 后端名称)"""
    try:
        from mlkem_link.kem import get_backend
        backend = get_backend("768")
        return True, backend.name
    except (ImportError, RuntimeError, OSError, AttributeError):
        return False, ""


_backend_ok, _backend_name = _check_backend_available()

require_backend = pytest.mark.skipif(
    not _backend_ok,
    reason=f"KEM 后端不可用（Tongsuo/liboqs 均未编译），跳过后端依赖测试"
)

require_root = pytest.mark.skipif(
    os.geteuid() != 0,
    reason="需要 root 权限（tc netem）"
)
