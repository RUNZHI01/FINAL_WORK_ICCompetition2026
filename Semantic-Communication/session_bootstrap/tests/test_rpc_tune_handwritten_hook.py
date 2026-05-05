from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import types
from types import SimpleNamespace
import unittest
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "rpc_tune.py"
)
SCRIPT_DIR = SCRIPT.parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

spec = importlib.util.spec_from_file_location("rpc_tune", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_task_stages(operator_name: str) -> dict[str, object]:
    row = {
        "rank": 1,
        "task_name": operator_name,
        "weight": 1,
        "dispatched_count": 1,
        "prim_funcs": [operator_name],
        "target": "llvm",
    }
    return {
        module.RAW_STAGE_NAME: {
            "stage_name": module.RAW_STAGE_NAME,
            "pipeline": None,
            "total_tasks": 1,
            "tasks": [row],
        },
        module.TUNED_STAGE_NAME: {
            "stage_name": module.TUNED_STAGE_NAME,
            "pipeline": "FuseTIR",
            "total_tasks": 1,
            "tasks": [row],
        },
    }


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


class RpcTuneHandwrittenHookTest(unittest.TestCase):
    def test_disabled_when_impl_path_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            with mock.patch.dict(os.environ, {}, clear=True):
                report = module.maybe_apply_handwritten_hook(
                    mod="fake-mod",
                    target="llvm",
                    database="fake-db",
                    output_dir=str(temp_dir),
                    task_stages=make_task_stages("fused_conv2d_transpose1_add9"),
                )

        self.assertIsNone(report)

    def test_placeholder_module_is_traced_and_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            impl_path = temp_dir / "manual_impl.py"
            state_json = temp_dir / "state.json"
            bookkeeping_json = temp_dir / "bookkeeping.json"
            write_text(bookkeeping_json, "{}\n")
            write_text(
                impl_path,
                textwrap.dedent(
                    f"""\
                    import json
                    from pathlib import Path

                    STATE_JSON = Path({str(state_json)!r})


                    def describe_placeholder(context):
                        STATE_JSON.write_text(
                            json.dumps(
                                {{
                                    "metadata_phase": context["phase"],
                                    "metadata_operator": context["operator"],
                                }}
                            ),
                            encoding="utf-8",
                        )
                        return {{
                            "operator": "fused_conv2d_transpose1_add9",
                            "placeholder_only": True,
                            "tag": "placeholder",
                        }}


                    def build_manual_impl(context):
                        payload = json.loads(STATE_JSON.read_text(encoding="utf-8"))
                        payload["entrypoint_phase"] = context["phase"]
                        STATE_JSON.write_text(json.dumps(payload), encoding="utf-8")
                        raise NotImplementedError("placeholder only")
                    """
                ),
            )

            env = {
                "TVM_HANDWRITTEN_IMPL_PATH": str(impl_path),
                "TVM_HANDWRITTEN_OP": "fused_conv2d_transpose1_add9",
                "TVM_HANDWRITTEN_IMPL_ENTRYPOINT": "build_manual_impl",
                "TVM_HANDWRITTEN_IMPL_METADATA_FN": "describe_placeholder",
                "TVM_HANDWRITTEN_BOOKKEEPING_JSON": str(bookkeeping_json),
            }
            with mock.patch.dict(os.environ, env, clear=True):
                report = module.maybe_apply_handwritten_hook(
                    mod="fake-mod",
                    target="llvm",
                    database="fake-db",
                    output_dir=str(temp_dir),
                    task_stages=make_task_stages("fused_conv2d_transpose1_add9"),
                )

            state = json.loads(state_json.read_text(encoding="utf-8"))

        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "placeholder_only")
        self.assertTrue(report["placeholder_only"])
        self.assertEqual(report["metadata"]["tag"], "placeholder")
        self.assertEqual(report["metadata_operator"], "fused_conv2d_transpose1_add9")
        self.assertEqual(report["bookkeeping_json"], str(bookkeeping_json))
        self.assertEqual(
            report["task_stage_matches"][module.TUNED_STAGE_NAME],
            True,
        )
        self.assertEqual(report["entrypoint_notice"], "placeholder only")
        self.assertEqual(state["metadata_phase"], "pre_compile")
        self.assertEqual(state["metadata_operator"], "fused_conv2d_transpose1_add9")
        self.assertEqual(state["entrypoint_phase"], "pre_compile")

    def test_compile_and_export_applies_manual_override_before_compile_relax(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            impl_path = temp_dir / "manual_impl.py"
            override_source = temp_dir / "override_source.py"
            write_text(
                override_source,
                textwrap.dedent(
                    """\
                    class OverrideModule:
                        manual_v0 = {"tag": "manual_v0"}
                    """
                ),
            )
            write_text(
                impl_path,
                textwrap.dedent(
                    f"""\
                    def describe_placeholder(context):
                        return {{
                            "operator": "fused_conv2d_transpose1_add9",
                            "placeholder_only": False,
                            "tag": "manual_override",
                        }}


                    def build_manual_impl(context):
                        return {{
                            "operator": "fused_conv2d_transpose1_add9",
                            "override": {{
                                "kind": "replace_prim_func_from_source",
                                "source_path": {str(override_source)!r},
                                "source_module_attr": "OverrideModule",
                                "source_func_name": "manual_v0",
                                "target_global_vars": ["fused_conv2d_transpose1_add9"],
                                "candidate_version": "v0",
                                "staging_only": True,
                            }},
                        }}
                    """
                ),
            )

            compile_calls: dict[str, object] = {}

            class FakeExecutable:
                def export_library(self, path: str) -> None:
                    Path(path).write_text("fake-so\n", encoding="utf-8")

            def fake_compile_relax(**kwargs):
                compile_calls.update(kwargs)
                return FakeExecutable()

            relax_integration_module = types.ModuleType(
                "tvm.s_tir.meta_schedule.relax_integration"
            )
            relax_integration_module.compile_relax = fake_compile_relax
            meta_schedule_module = types.ModuleType("tvm.s_tir.meta_schedule")
            meta_schedule_module.relax_integration = relax_integration_module
            s_tir_module = types.ModuleType("tvm.s_tir")
            s_tir_module.meta_schedule = meta_schedule_module
            tvm_module = types.ModuleType("tvm")
            tvm_module.s_tir = s_tir_module

            fake_mod = FakeIRModule({"fused_conv2d_transpose1_add9": {"tag": "seed"}})
            env = {
                "TVM_HANDWRITTEN_IMPL_PATH": str(impl_path),
                "TVM_HANDWRITTEN_OP": "fused_conv2d_transpose1_add9",
                "TVM_HANDWRITTEN_IMPL_ENTRYPOINT": "build_manual_impl",
                "TVM_HANDWRITTEN_IMPL_METADATA_FN": "describe_placeholder",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.dict(
                    sys.modules,
                    {
                        "tvm": tvm_module,
                        "tvm.s_tir": s_tir_module,
                        "tvm.s_tir.meta_schedule": meta_schedule_module,
                        "tvm.s_tir.meta_schedule.relax_integration": relax_integration_module,
                    },
                    clear=False,
                ):
                    lib_path, handwritten_hook = module.compile_and_export(
                        mod=fake_mod,
                        target="llvm",
                        database="fake-db",
                        output_dir=str(temp_dir),
                        task_stages=make_task_stages("fused_conv2d_transpose1_add9"),
                    )
                    self.assertEqual(
                        Path(lib_path).read_text(encoding="utf-8"), "fake-so\n"
                    )
                    self.assertIsNotNone(handwritten_hook)
                    self.assertEqual(
                        handwritten_hook["status"],
                        "manual_override_applied_diagnostic_only",
                    )
                    self.assertTrue(handwritten_hook["manual_override_applied"])
                    self.assertEqual(
                        handwritten_hook["applied_override"]["target_global_var"],
                        "fused_conv2d_transpose1_add9",
                    )
                    self.assertEqual(
                        handwritten_hook["evaluation_contract"]["path_kind"],
                        "diagnostic_raw_pre_compile_replacement",
                    )
                    self.assertEqual(
                        handwritten_hook["comparison_semantics"],
                        "non_comparable_diagnostic_only",
                    )
                    self.assertFalse(handwritten_hook["performance_evaluable"])
                    self.assertEqual(
                        handwritten_hook["evaluation_contract"]["schedule_context_guarantee"],
                        "not_guaranteed",
                    )
                    self.assertEqual(
                        handwritten_hook["evaluation_contract"]["future_path_kind"],
                        "schedule_context_preserving_evaluation",
                    )
                    self.assertFalse(
                        handwritten_hook["evaluation_contract"]["performance_comparable"]
                    )
                    self.assertEqual(
                        compile_calls["mod"].mapping["fused_conv2d_transpose1_add9"],
                        {"tag": "manual_v0"},
                    )
                    self.assertEqual(compile_calls["database"], "fake-db")
                    self.assertEqual(compile_calls["target"], "llvm")

    def test_metadata_operator_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            impl_path = temp_dir / "manual_impl.py"
            write_text(
                impl_path,
                textwrap.dedent(
                    """\
                    def describe_placeholder():
                        return {
                            "operator": "wrong_operator",
                            "placeholder_only": True,
                        }


                    def build_manual_impl():
                        return None
                    """
                ),
            )

            env = {
                "TVM_HANDWRITTEN_IMPL_PATH": str(impl_path),
                "TVM_HANDWRITTEN_OP": "fused_conv2d_transpose1_add9",
                "TVM_HANDWRITTEN_IMPL_ENTRYPOINT": "build_manual_impl",
                "TVM_HANDWRITTEN_IMPL_METADATA_FN": "describe_placeholder",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(
                    ValueError,
                    "Handwritten metadata operator mismatch",
                ):
                    module.maybe_apply_handwritten_hook(
                        mod="fake-mod",
                        target="llvm",
                        database="fake-db",
                        output_dir=str(temp_dir),
                        task_stages=make_task_stages("fused_conv2d_transpose1_add9"),
                    )

    def test_operator_must_exist_in_task_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            impl_path = temp_dir / "manual_impl.py"
            write_text(
                impl_path,
                textwrap.dedent(
                    """\
                    def describe_placeholder():
                        return {
                            "operator": "fused_conv2d_transpose1_add9",
                            "placeholder_only": True,
                        }


                    def build_manual_impl():
                        return None
                    """
                ),
            )

            env = {
                "TVM_HANDWRITTEN_IMPL_PATH": str(impl_path),
                "TVM_HANDWRITTEN_OP": "fused_conv2d_transpose1_add9",
                "TVM_HANDWRITTEN_IMPL_ENTRYPOINT": "build_manual_impl",
                "TVM_HANDWRITTEN_IMPL_METADATA_FN": "describe_placeholder",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(
                    ValueError,
                    "is not present in the extracted task stages",
                ):
                    module.maybe_apply_handwritten_hook(
                        mod="fake-mod",
                        target="llvm",
                        database="fake-db",
                        output_dir=str(temp_dir),
                        task_stages=make_task_stages("different_operator"),
                    )

    def test_report_writers_include_handwritten_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            args = SimpleNamespace(
                onnx_path="/tmp/model.onnx",
                target="llvm",
                input_shape="1,32,32,32",
                op_names="fused_conv2d_transpose1_add9",
                total_trials=0,
                runner="local",
                tracker_host="127.0.0.1",
                tracker_port=9190,
                device_key="armv8",
                existing_db="",
            )
            task_stages = make_task_stages("fused_conv2d_transpose1_add9")
            handwritten_hook = {
                "enabled": True,
                "status": "placeholder_only",
                "operator": "fused_conv2d_transpose1_add9",
            }

            task_summary_path = module.write_task_summary(
                str(temp_dir),
                task_stages,
                args,
                handwritten_hook=handwritten_hook,
            )
            report_path = module.write_tune_report(
                str(temp_dir),
                args,
                elapsed_sec=0.5,
                lib_path=str(temp_dir / "optimized_model.so"),
                work_dir=str(temp_dir / "tuning_logs"),
                task_summary_path=task_summary_path,
                task_stages=task_stages,
                handwritten_hook=handwritten_hook,
            )

            task_summary = json.loads(Path(task_summary_path).read_text(encoding="utf-8"))
            report = json.loads(Path(report_path).read_text(encoding="utf-8"))

        self.assertEqual(task_summary["handwritten_hook"], handwritten_hook)
        self.assertEqual(report["handwritten_hook"], handwritten_hook)


if __name__ == "__main__":
    unittest.main()
