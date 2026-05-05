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
    / "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v2_working_copy_tir.py"
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


class FusedVariance4Add13TirSqrt4ScheduledFormCandidateV2WorkingCopyTest(
    unittest.TestCase
):
    def test_working_copy_keeps_the_first_edit_local_and_isolated(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("New candidate goal", text)
        self.assertIn("T_divide_intermediate = T.alloc_buffer", text)
        self.assertNotIn("T_add_intermediate = T.alloc_buffer", text)
        self.assertNotIn('with T.sblock("T_add")', text)
        self.assertIn("compute_intermediate[v_i0, v_i1, v_i2, v_i3] = T.sqrt(", text)
        self.assertIn("+ T.float32(9.9999997473787516e-06)", text)

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

    def test_manifest_records_the_current_checked_in_v2_edit(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["operator"], "fused_variance4_add13_tir_sqrt4")
        self.assertEqual(
            payload["working_copy_contract"]["path_kind"],
            "diagnostic_scheduled_form_candidate_v2_working_copy",
        )
        self.assertFalse(payload["working_copy_contract"]["performance_claims"])
        self.assertEqual(
            payload["accepted_baseline"]["status"],
            "seed_synced_unedited",
        )
        self.assertEqual(
            payload["current_edit_state"]["status"],
            "v2_epsilon_add_fused_into_sqrt_on_top_of_v1_seed_applied",
        )
        self.assertIn(
            "remove the standalone T_add_intermediate buffer/stage",
            payload["current_edit_state"]["concrete_change"],
        )
        self.assertEqual(
            payload["current_edit_state"]["working_copy_tir_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
