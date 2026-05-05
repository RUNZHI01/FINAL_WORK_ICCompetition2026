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
    / "fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py"
)
MANIFEST_PATH = HANDWRITTEN_DIR / "scheduled_form_candidate_v1_working_copy_manifest.json"


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FusedConv2dTranspose1Add9ScheduledFormCandidateV1WorkingCopyTest(
    unittest.TestCase
):
    def test_working_copy_keeps_the_first_v1_edit_local_and_narrow(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("First real scheduled-form v1 edit", text)
        self.assertIn("P4 local micro-tuning edit", text)
        self.assertNotIn("compute_intermediate = T.alloc_buffer", text)
        self.assertNotIn('with T.sblock("T_add")', text)
        self.assertIn('"pragma_auto_unroll_max_step": 64', text)
        self.assertIn(
            "T.reads(lv320[v_b, v_c, T.int64(0), T.int64(0)])",
            text,
        )
        self.assertIn(
            "T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])",
            text,
        )

        script_module = types.ModuleType("tvm.script")
        script_module.ir = DummyTVMScriptNamespace()
        script_module.tir = DummyTVMScriptNamespace()
        tvm_module = types.ModuleType("tvm")
        tvm_module.script = script_module

        spec = importlib.util.spec_from_file_location(
            "scheduled_form_candidate_v1_working_copy_tir",
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

    def test_manifest_records_the_current_checked_in_v1_edit(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["operator"], "fused_conv2d_transpose1_add9")
        self.assertEqual(
            payload["working_copy_contract"]["path_kind"],
            "diagnostic_scheduled_form_candidate_v1_working_copy",
        )
        self.assertFalse(payload["working_copy_contract"]["performance_claims"])
        self.assertEqual(
            payload["current_edit_state"]["status"],
            "p4_cortex_a72_auto_unroll64_on_p2_applied",
        )
        self.assertIn(
            "raise pragma_auto_unroll_max_step from 32 to 64",
            payload["current_edit_state"]["concrete_change"],
        )
        self.assertEqual(
            payload["current_edit_state"]["working_copy_tir_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
