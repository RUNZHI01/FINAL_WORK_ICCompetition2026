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
    / "fused_conv2d_transpose1_add9"
)
MODULE_PATH = (
    HANDWRITTEN_DIR
    / "fused_conv2d_transpose1_add9_scheduled_form_candidate_v4_working_copy_tir.py"
)
MANIFEST_PATH = HANDWRITTEN_DIR / "scheduled_form_candidate_v4_working_copy_manifest.json"


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FusedConv2dTranspose1Add9ScheduledFormCandidateV4WorkingCopyTest(
    unittest.TestCase
):
    def test_working_copy_keeps_the_v4_edit_local_and_isolated(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("Accepted baseline carried forward into this v4 scaffold", text)
        self.assertIn("First real v4 locality/schedule edit", text)
        self.assertIn("kernel_transform = T.alloc_buffer", text)
        self.assertIn("data_dilate = T.alloc_buffer", text)
        self.assertIn("data_pad = T.alloc_buffer", text)
        self.assertIn('with T.sblock("data_dilate")', text)
        self.assertIn('with T.sblock("data_pad")', text)
        self.assertNotIn("compute_intermediate = T.alloc_buffer", text)
        self.assertNotIn('with T.sblock("T_add")', text)
        self.assertIn('"pragma_auto_unroll_max_step": 64', text)
        self.assertLess(
            text.index("for ax0, ax1, ax2 in T.grid"),
            text.index("for b_1, c_1 in T.grid"),
        )
        self.assertIn(
            "reuse each staged data tile across all three output-channel groups",
            text,
        )

        script_module = types.ModuleType("tvm.script")
        script_module.ir = DummyTVMScriptNamespace()
        script_module.tir = DummyTVMScriptNamespace()
        tvm_module = types.ModuleType("tvm")
        tvm_module.script = script_module

        spec = importlib.util.spec_from_file_location(
            "scheduled_form_candidate_v4_working_copy_tir",
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

    def test_manifest_records_the_current_checked_in_v4_scaffold_state(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["operator"], "fused_conv2d_transpose1_add9")
        self.assertEqual(
            payload["working_copy_contract"]["path_kind"],
            "diagnostic_scheduled_form_candidate_v4_working_copy",
        )
        self.assertFalse(payload["working_copy_contract"]["performance_claims"])
        self.assertEqual(
            payload["current_edit_state"]["status"],
            "v4_data_staging_hoisted_outside_c1_applied",
        )
        self.assertIn(
            "hoist the materialized data_dilate/data_pad tile fill outside the c_1 loop",
            payload["current_edit_state"]["concrete_change"],
        )
        self.assertEqual(
            payload["current_edit_state"]["working_copy_tir_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(payload["accepted_baseline"]["remote_median_ms"], 159.356)


if __name__ == "__main__":
    unittest.main()
