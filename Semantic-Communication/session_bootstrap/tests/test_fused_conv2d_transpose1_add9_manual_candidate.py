from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "handwritten"
    / "fused_conv2d_transpose1_add9"
    / "fused_conv2d_transpose1_add9_manual_candidate.py"
)

spec = importlib.util.spec_from_file_location(
    "fused_conv2d_transpose1_add9_manual_candidate",
    MODULE_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {MODULE_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

RPC_TUNE_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "rpc_tune.py"
)
RPC_TUNE_DIR = RPC_TUNE_PATH.parent
if str(RPC_TUNE_DIR) not in sys.path:
    sys.path.insert(0, str(RPC_TUNE_DIR))
rpc_spec = importlib.util.spec_from_file_location("rpc_tune_manual_candidate_test", RPC_TUNE_PATH)
if rpc_spec is None or rpc_spec.loader is None:
    raise RuntimeError(f"unable to load module from {RPC_TUNE_PATH}")
rpc_tune = importlib.util.module_from_spec(rpc_spec)
rpc_spec.loader.exec_module(rpc_tune)


class FakeGlobalVar:
    def __init__(self, name_hint: str) -> None:
        self.name_hint = name_hint


class FakeIRModule:
    def __init__(self, mapping: dict[str, object]) -> None:
        self.mapping = dict(mapping)

    def get_global_var(self, name: str) -> FakeGlobalVar:
        if name not in self.mapping:
            raise KeyError(name)
        return FakeGlobalVar(name)

    def __getitem__(self, key: object) -> object:
        name = getattr(key, "name_hint", key)
        if not isinstance(name, str) or name not in self.mapping:
            raise KeyError(name)
        return self.mapping[name]

    def __setitem__(self, key: object, value: object) -> None:
        name = getattr(key, "name_hint", key)
        if not isinstance(name, str):
            raise KeyError(name)
        self.mapping[name] = value


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FusedConv2dTranspose1Add9ManualCandidateTest(unittest.TestCase):
    def test_candidate_reports_checked_in_v0_override_honestly(self) -> None:
        metadata = module.describe_placeholder()
        self.assertEqual(metadata["operator"], "fused_conv2d_transpose1_add9")
        self.assertEqual(metadata["candidate_version"], "v0")
        self.assertFalse(metadata["placeholder_only"])
        self.assertFalse(metadata["manual_override_applied"])
        self.assertTrue(metadata["manual_override_available"])
        self.assertEqual(
            metadata["validation_scope"],
            "local_staging_only_pre_compile_override",
        )
        self.assertEqual(
            metadata["evaluation_contract"]["path_kind"],
            "diagnostic_raw_pre_compile_replacement",
        )
        self.assertEqual(
            metadata["evaluation_contract"]["comparison_semantics"],
            "non_comparable_diagnostic_only",
        )
        self.assertFalse(metadata["evaluation_contract"]["performance_evaluable"])
        self.assertEqual(
            metadata["evaluation_contract"]["schedule_context_guarantee"],
            "not_guaranteed",
        )
        self.assertEqual(
            metadata["evaluation_contract"]["future_path_kind"],
            "schedule_context_preserving_evaluation",
        )
        self.assertTrue(Path(metadata["candidate_tir"]).is_file())
        self.assertTrue(Path(metadata["editable_tir"]).is_file())
        self.assertTrue(Path(metadata["candidate_metadata"]).is_file())
        self.assertTrue(Path(metadata["seed_manifest"]).is_file())

        result = module.build_manual_impl(
            {
                "phase": "pre_compile",
                "task_stages": {
                    "legalized_fused_tir": {
                        "tasks": [
                            {
                                "rank": 16,
                                "task_name": "fused_conv2d_transpose1_add9",
                                "prim_funcs": ["fused_conv2d_transpose1_add9"],
                            }
                        ]
                    }
                },
            }
        )
        self.assertEqual(result["phase"], "pre_compile")
        self.assertEqual(
            result["validation_scope"],
            "local_staging_only_pre_compile_override",
        )
        self.assertEqual(result["task_row"]["stage_name"], "legalized_fused_tir")
        self.assertEqual(result["override"]["kind"], "replace_prim_func_from_source")
        self.assertEqual(result["override"]["candidate_version"], "v0")
        self.assertEqual(
            result["evaluation_contract"]["path_kind"],
            "diagnostic_raw_pre_compile_replacement",
        )
        self.assertEqual(
            result["evaluation_contract"]["comparison_semantics"],
            "non_comparable_diagnostic_only",
        )
        self.assertFalse(result["evaluation_contract"]["performance_evaluable"])
        self.assertEqual(
            result["evaluation_contract"]["schedule_context_guarantee"],
            "not_guaranteed",
        )
        self.assertEqual(
            result["override"]["target_global_vars"],
            ["fused_conv2d_transpose1_add9"],
        )
        self.assertEqual(
            result["override"]["evaluation_contract"]["path_kind"],
            "diagnostic_raw_pre_compile_replacement",
        )
        self.assertEqual(result["override"]["source_path"], result["candidate_tir"])

    def test_candidate_v0_override_descriptor_can_be_applied_locally(self) -> None:
        result = module.build_manual_impl(
            {
                "phase": "pre_compile",
                "task_stages": {
                    "legalized_fused_tir": {
                        "tasks": [
                            {
                                "rank": 16,
                                "task_name": "fused_conv2d_transpose1_add9",
                                "prim_funcs": ["fused_conv2d_transpose1_add9"],
                            }
                        ]
                    }
                },
            }
        )
        fake_mod = FakeIRModule({"fused_conv2d_transpose1_add9": "seed"})

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
            updated_mod, summary = rpc_tune._apply_handwritten_override(
                fake_mod,
                "fused_conv2d_transpose1_add9",
                result["override"],
            )

        self.assertIs(updated_mod, fake_mod)
        self.assertEqual(summary["candidate_version"], "v0")
        self.assertEqual(summary["target_global_var"], "fused_conv2d_transpose1_add9")
        self.assertEqual(
            summary["evaluation_contract"]["path_kind"],
            "diagnostic_raw_pre_compile_replacement",
        )
        self.assertEqual(
            summary["evaluation_contract"]["comparison_semantics"],
            "non_comparable_diagnostic_only",
        )
        self.assertFalse(summary["evaluation_contract"]["performance_evaluable"])
        self.assertFalse(summary["evaluation_contract"]["performance_comparable"])
        self.assertEqual(
            summary["evaluation_contract"]["schedule_context_guarantee"],
            "not_guaranteed",
        )
        self.assertTrue(callable(fake_mod.mapping["fused_conv2d_transpose1_add9"]))
        self.assertEqual(
            fake_mod.mapping["fused_conv2d_transpose1_add9"].__name__,
            "main",
        )


if __name__ == "__main__":
    unittest.main()
