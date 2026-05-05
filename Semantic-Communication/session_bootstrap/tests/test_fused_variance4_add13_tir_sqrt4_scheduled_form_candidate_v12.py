from __future__ import annotations

import importlib.util
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
    HANDWRITTEN_DIR / "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12.py"
)
WORKING_COPY_TIR_PATH = (
    HANDWRITTEN_DIR
    / "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12_working_copy_tir.py"
)

spec = importlib.util.spec_from_file_location(
    "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v12",
    MODULE_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {MODULE_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SEAM_PROBE_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "probe_transpose1_schedule_preserving_seam.py"
)
SEAM_PROBE_DIR = SEAM_PROBE_PATH.parent
if str(SEAM_PROBE_DIR) not in sys.path:
    sys.path.insert(0, str(SEAM_PROBE_DIR))
seam_spec = importlib.util.spec_from_file_location(
    "probe_transpose1_schedule_preserving_seam_variance4_v12_test",
    SEAM_PROBE_PATH,
)
if seam_spec is None or seam_spec.loader is None:
    raise RuntimeError(f"unable to load module from {SEAM_PROBE_PATH}")
seam_probe = importlib.util.module_from_spec(seam_spec)
seam_spec.loader.exec_module(seam_probe)


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FusedVariance4Add13TirSqrt4ScheduledFormCandidateV12Test(unittest.TestCase):
    def test_wrapper_reports_local_only_post_db_contract(self) -> None:
        metadata = module.describe_placeholder()
        self.assertEqual(metadata["operator"], "fused_variance4_add13_tir_sqrt4")
        self.assertEqual(metadata["candidate_version"], "v12_working_copy")
        self.assertEqual(
            metadata["candidate_status"],
            "v12_remove_raw_allocate_handle_keep_decl_buffer_data_volatility",
        )
        self.assertFalse(metadata["placeholder_only"])
        self.assertFalse(metadata["hook_target"])
        self.assertTrue(metadata["schedule_preserving_override_available"])
        self.assertEqual(
            metadata["validation_scope"],
            "local_only_post_db_scheduled_swap",
        )
        self.assertEqual(
            metadata["accepted_baseline"]["status"],
            "seed_synced_unedited",
        )
        self.assertEqual(
            metadata["evaluation_contract"]["path_kind"],
            "diagnostic_post_db_scheduled_primfunc_swap",
        )
        self.assertFalse(metadata["evaluation_contract"]["performance_evaluable"])
        self.assertTrue(Path(metadata["working_copy_tir"]).is_file())
        self.assertTrue(Path(metadata["working_copy_manifest"]).is_file())

    def test_seam_probe_can_load_the_v12_wrapper(self) -> None:
        script_module = types.ModuleType("tvm.script")
        script_module.ir = DummyTVMScriptNamespace()
        script_module.tir = DummyTVMScriptNamespace()
        tvm_module = types.ModuleType("tvm")
        tvm_module.script = script_module

        with mock.patch.dict(
            sys.modules,
            {
                "tvm": tvm_module,
                "tvm.script": script_module,
            },
            clear=False,
        ):
            payload = seam_probe.load_candidate_override(
                MODULE_PATH,
                {
                    "legalized_fused_tir": {
                        "tasks": [
                            {
                                "rank": 26,
                                "task_name": "fused_variance4_add13_tir_sqrt4",
                                "prim_funcs": ["main"],
                            }
                        ]
                    }
                },
            )

        self.assertEqual(payload["metadata"]["operator"], "fused_variance4_add13_tir_sqrt4")
        self.assertEqual(payload["source_path"], WORKING_COPY_TIR_PATH.resolve())
        self.assertEqual(payload["source_func_name"], "fused_variance4_add13_tir_sqrt4")
        self.assertTrue(callable(payload["source_func"]))
        self.assertEqual(
            payload["result"]["evaluation_contract"]["path_kind"],
            "diagnostic_post_db_scheduled_primfunc_swap",
        )
        self.assertEqual(
            payload["override"]["target_global_vars"],
            ["fused_variance4_add13_tir_sqrt4"],
        )


if __name__ == "__main__":
    unittest.main()
