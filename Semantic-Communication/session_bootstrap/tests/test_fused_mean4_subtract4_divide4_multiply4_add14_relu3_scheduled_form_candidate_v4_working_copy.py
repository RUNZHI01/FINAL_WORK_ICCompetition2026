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
    / "fused_mean4_subtract4_divide4_multiply4_add14_relu3"
)
MODULE_PATH = (
    HANDWRITTEN_DIR
    / "fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4_working_copy_tir.py"
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


class FusedMean4Subtract4Divide4Multiply4Add14Relu3ScheduledFormCandidateV4WorkingCopyTest(
    unittest.TestCase
):
    def test_working_copy_hoists_channel_params_and_fuses_epilogue(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("New candidate goal", text)
        self.assertIn('mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")', text)
        self.assertIn('std_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")', text)
        self.assertIn('weight_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")', text)
        self.assertIn('bias_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")', text)
        self.assertIn('with T.sblock("param_local")', text)
        self.assertIn('with T.sblock("fused_compute")', text)
        self.assertIn('for k2, k3 in T.grid(T.int64(256), T.int64(256)):', text)
        self.assertIn('mean_local[0] = T_divide_intermediate[v_ax0, v_ax1, v_ax2, v_ax3]', text)
        self.assertIn('compute_intermediate[v_ax0, v_ax1, v_k2, v_k3] = T.max(', text)
        self.assertIn('"SSSSSS"', text)

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

    def test_manifest_records_the_operator_specific_fused_branch(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["operator"],
            "fused_mean4_subtract4_divide4_multiply4_add14_relu3",
        )
        self.assertEqual(
            payload["working_copy_contract"]["path_kind"],
            "diagnostic_scheduled_form_candidate_v4_working_copy",
        )
        self.assertFalse(payload["working_copy_contract"]["performance_claims"])
        self.assertEqual(
            payload["accepted_baseline"]["status"],
            "local_ablation_only_not_board_validated",
        )
        self.assertEqual(
            payload["current_edit_state"]["status"],
            "v4_channel_param_hoist_fused_epilogue_applied",
        )
        self.assertIn(
            "hoist mean/std/weight/bias once per channel into local buffers",
            payload["current_edit_state"]["concrete_change"],
        )
        self.assertEqual(
            payload["current_edit_state"]["working_copy_tir_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
