from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


HANDWRITTEN_DIR = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "handwritten"
    / "fused_variance4_add13_tir_sqrt4"
)
MODULE_PATH = (
    HANDWRITTEN_DIR
    / "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v24_working_copy_tir.py"
)
MANIFEST_PATH = HANDWRITTEN_DIR / "scheduled_form_candidate_v24_working_copy_manifest.json"


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FusedVariance4Add13TirSqrt4ScheduledFormCandidateV24WorkingCopyTest(
    unittest.TestCase
):
    def test_working_copy_combines_scalar_mean_with_flattened_reductions(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("New candidate goal", text)
        self.assertIn(
            'lv335_red = T.alloc_buffer((T.int64(12),), "float32", scope="local")',
            text,
        )
        self.assertIn(
            'lv335_mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")',
            text,
        )
        self.assertIn(
            'T_multiply_red = T.alloc_buffer((T.int64(12),), "float32", scope="local")',
            text,
        )
        self.assertIn(
            'T_subtract_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")',
            text,
        )
        self.assertIn('T.attr(T_multiply_local.data, "volatile_scope", 1)', text)
        self.assertIn("T.writes(lv335_red[v_ax1])", text)
        self.assertIn("T.writes(lv335_mean_local[0])", text)
        self.assertIn("for k2, k3 in T.grid(T.int64(256), T.int64(256)):", text)
        self.assertIn("lv335[v_ax0, v_ax1, v_k2, v_k3] - lv335_mean_local[0]", text)
        self.assertIn("T.writes(T_multiply_red[v_ax1])", text)
        self.assertIn("T.reads(T_multiply_red[v_i1])", text)
        self.assertIn("+ T.float32(9.9999997473787516e-06)", text)

        script_module = types.ModuleType("tvm.script")
        script_module.ir = DummyTVMScriptNamespace()
        script_module.tir = DummyTVMScriptNamespace()
        tvm_module = types.ModuleType("tvm")
        tvm_module.script = script_module

        spec = importlib.util.spec_from_file_location(
            "scheduled_form_candidate_v24_working_copy_tir",
            MODULE_PATH,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"unable to load module from {MODULE_PATH}")
        loaded = importlib.util.module_from_spec(spec)
        with mock.patch.dict(
            sys.modules,
            {
                "tvm": tvm_module,
                "tvm.script": script_module,
            },
            clear=False,
        ):
            spec.loader.exec_module(loaded)

        self.assertTrue(hasattr(loaded, "Module"))

    def test_manifest_records_the_combined_branch(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["operator"], "fused_variance4_add13_tir_sqrt4")
        self.assertEqual(
            payload["working_copy_contract"]["path_kind"],
            "diagnostic_scheduled_form_candidate_v24_working_copy",
        )
        self.assertFalse(payload["working_copy_contract"]["performance_claims"])
        self.assertEqual(
            payload["accepted_baseline"]["status"],
            "seed_synced_unedited",
        )
        self.assertEqual(
            payload["current_edit_state"]["status"],
            "v24_scalar_mean_plus_flattened_reductions",
        )
        self.assertIn(
            "flatten the tiny reduction buffers lv335_red and T_multiply_red",
            payload["current_edit_state"]["concrete_change"],
        )
        self.assertEqual(
            payload["current_edit_state"]["working_copy_tir_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
