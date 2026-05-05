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
    / "fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v5_working_copy_tir.py"
)
MANIFEST_PATH = HANDWRITTEN_DIR / "scheduled_form_candidate_v5_working_copy_manifest.json"


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FusedMean4Subtract4Divide4Multiply4Add14Relu3ScheduledFormCandidateV5WorkingCopyTest(
    unittest.TestCase
):
    def test_working_copy_precomputes_affine_epilogue(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("New candidate goal", text)
        self.assertIn('mean_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")', text)
        self.assertIn('scale_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")', text)
        self.assertIn('shift_local = T.alloc_buffer((T.int64(1),), "float32", scope="local")', text)
        self.assertIn('with T.sblock("scale_local")', text)
        self.assertIn('with T.sblock("shift_local")', text)
        self.assertIn('with T.sblock("affine_relu_compute")', text)
        self.assertIn('scale_local[0] = lv342[v_ax1, v_ax2, v_ax3] / lv340[v_ax0, v_ax1, v_ax2, v_ax3]', text)
        self.assertIn('shift_local[0] = lv344[v_ax1, v_ax2, v_ax3] - mean_local[0] * scale_local[0]', text)
        self.assertIn('lv335[v_ax0, v_ax1, v_k2, v_k3] * scale_local[0] + shift_local[0]', text)
        self.assertIn('"SSSSSS"', text)

        script_module = types.ModuleType("tvm.script")
        script_module.ir = DummyTVMScriptNamespace()
        script_module.tir = DummyTVMScriptNamespace()
        tvm_module = types.ModuleType("tvm")
        tvm_module.script = script_module

        spec = importlib.util.spec_from_file_location(
            "scheduled_form_candidate_v5_working_copy_tir",
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

    def test_manifest_records_the_affine_branch(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["operator"],
            "fused_mean4_subtract4_divide4_multiply4_add14_relu3",
        )
        self.assertEqual(
            payload["working_copy_contract"]["path_kind"],
            "diagnostic_scheduled_form_candidate_v5_working_copy",
        )
        self.assertFalse(payload["working_copy_contract"]["performance_claims"])
        self.assertEqual(
            payload["accepted_baseline"]["status"],
            "board_proven_positive_branch_baked_into_handwritten_final",
        )
        self.assertEqual(
            payload["current_edit_state"]["status"],
            "v5_channel_affine_precompute_applied",
        )
        self.assertIn(
            "collapse the channel-wise epilogue parameters into an affine pair",
            payload["current_edit_state"]["concrete_change"],
        )
        self.assertEqual(
            payload["current_edit_state"]["working_copy_tir_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
