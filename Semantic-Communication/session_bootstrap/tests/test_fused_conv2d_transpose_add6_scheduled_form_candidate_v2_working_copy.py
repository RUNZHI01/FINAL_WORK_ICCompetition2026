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
    / "fused_conv2d_transpose_add6"
)
MODULE_PATH = (
    HANDWRITTEN_DIR
    / "fused_conv2d_transpose_add6_scheduled_form_candidate_v2_working_copy_tir.py"
)
MANIFEST_PATH = HANDWRITTEN_DIR / "scheduled_form_candidate_v2_working_copy_manifest.json"


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FusedConv2dTransposeAdd6ScheduledFormCandidateV2WorkingCopyTest(
    unittest.TestCase
):
    def test_working_copy_applies_the_first_locality_edit(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("First real v2 locality edit", text)
        self.assertIn("data_dilate = T.alloc_buffer", text)
        self.assertIn('with T.sblock("data_pad")', text)
        self.assertIn("kernel_transform = T.alloc_buffer", text)
        self.assertIn("for dc_0 in T.serial(T.int64(6))", text)
        self.assertIn(
            "for ax0, ax1, ax2 in T.grid(T.int64(1), T.int64(16), T.int64(6))",
            text,
        )
        self.assertNotIn("compute_intermediate = T.alloc_buffer", text)
        self.assertNotIn('with T.sblock("T_add")', text)
        self.assertIn('"pragma_auto_unroll_max_step": 32', text)

        script_module = types.ModuleType("tvm.script")
        script_module.ir = DummyTVMScriptNamespace()
        script_module.tir = DummyTVMScriptNamespace()
        tvm_module = types.ModuleType("tvm")
        tvm_module.script = script_module

        spec = importlib.util.spec_from_file_location(
            "scheduled_form_candidate_v2_working_copy_tir",
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

    def test_manifest_records_the_current_checked_in_v2_seed(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["operator"], "fused_conv2d_transpose_add6")
        self.assertEqual(
            payload["working_copy_contract"]["path_kind"],
            "diagnostic_scheduled_form_candidate_v2_working_copy",
        )
        self.assertFalse(payload["working_copy_contract"]["performance_claims"])
        self.assertEqual(
            payload["current_edit_state"]["status"],
            "v2_dc0_slice_data_pad_reuse_applied",
        )
        self.assertIn(
            "the tile-local data_pad patch is staged one dc_0 16-channel reduction slice at a time",
            payload["current_edit_state"]["concrete_change"],
        )
        self.assertEqual(
            payload["current_edit_state"]["working_copy_tir_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
