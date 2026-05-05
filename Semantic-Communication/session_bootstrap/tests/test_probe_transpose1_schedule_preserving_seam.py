from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "probe_transpose1_schedule_preserving_seam.py"
)
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
probe_spec = importlib.util.spec_from_file_location(
    "probe_transpose1_schedule_preserving_seam",
    SCRIPT_PATH,
)
if probe_spec is None or probe_spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(probe_spec)
probe_spec.loader.exec_module(module)


class DummyTVMScriptNamespace:
    def __getattr__(self, name: str):
        if name in {"ir_module", "prim_func"}:
            return lambda obj: obj
        return self

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return self


class FakeGlobalVar:
    def __init__(self, name_hint: str) -> None:
        self.name_hint = name_hint


class FakeFunc:
    def __init__(
        self,
        tag: str,
        *,
        param_count: int = 2,
        attrs: dict[str, object] | None = None,
    ) -> None:
        self.tag = tag
        self.params = [object() for _ in range(param_count)]
        self.attrs: dict[str, object] = dict(attrs or {})

    def with_attr(self, key: str, value: object):
        cloned = FakeFunc(self.tag, param_count=len(self.params), attrs=self.attrs)
        cloned.attrs[key] = value
        return cloned


class FakeIRModule:
    def __init__(
        self,
        mapping: dict[str, object],
        *,
        attrs: dict[str, object] | None = None,
    ) -> None:
        self.mapping = dict(mapping)
        self.attrs = dict(attrs or {})

    def get_global_var(self, name: str) -> FakeGlobalVar:
        if name not in self.mapping:
            raise KeyError(name)
        return FakeGlobalVar(name)

    def get_global_vars(self) -> list[FakeGlobalVar]:
        return [FakeGlobalVar(name) for name in self.mapping]

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

    def script(self, show_meta: bool = False) -> str:
        del show_meta
        func_name = next(iter(self.mapping))
        return (
            "# from tvm.script import ir as I\n"
            "# from tvm.script import tir as T\n\n"
            "@I.ir_module\n"
            "class Module:\n"
            "    @T.prim_func\n"
            f"    def {func_name}():\n"
            "        T.evaluate(0)\n"
        )


class ProbeTranspose1SchedulePreservingSeamTest(unittest.TestCase):
    def test_lookup_global_func_finds_named_entry(self) -> None:
        mod = FakeIRModule({"main": {"tag": "scheduled"}})
        self.assertEqual(module.lookup_global_func(mod, "main"), {"tag": "scheduled"})

    def test_replace_global_func_updates_named_entry(self) -> None:
        mod = FakeIRModule({"fused_conv2d_transpose1_add9": FakeFunc("scheduled")})
        updated = module.replace_global_func(
            mod,
            "fused_conv2d_transpose1_add9",
            FakeFunc("candidate"),
        )
        self.assertIs(updated, mod)
        replaced = mod.mapping["fused_conv2d_transpose1_add9"]
        self.assertIsInstance(replaced, FakeFunc)
        self.assertEqual(replaced.tag, "candidate")
        self.assertEqual(replaced.attrs.get("global_symbol"), "fused_conv2d_transpose1_add9")

    def test_load_candidate_override_recovers_checked_in_candidate_source(self) -> None:
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
            payload = module.load_candidate_override(
                module.DEFAULT_CANDIDATE_IMPL,
                {
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
            )

        self.assertEqual(payload["metadata"]["operator"], "fused_conv2d_transpose1_add9")
        self.assertEqual(payload["override"]["kind"], "replace_prim_func_from_source")
        self.assertEqual(payload["source_func_name"], "main")
        self.assertTrue(callable(payload["source_func"]))
        self.assertEqual(
            payload["result"]["evaluation_contract"]["path_kind"],
            "diagnostic_raw_pre_compile_replacement",
        )

    def test_main_exports_local_swapped_artifact_and_adjacent_report(self) -> None:
        operator = module.DEFAULT_OPERATOR

        class DummyContextManager:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeTarget(DummyContextManager):
            def __init__(self, raw: str) -> None:
                self.raw = raw

        class FakeTrace:
            def __init__(self, inst_count: int) -> None:
                self.insts = list(range(inst_count))

        class FakeRecord:
            def __init__(self) -> None:
                self.run_secs = [0.123, 0.456]
                self.trace = FakeTrace(3)

        class FakeSchedule:
            def __init__(self, mod: FakeIRModule) -> None:
                self.mod = mod
                self.trace = FakeTrace(5)

        class FakeJSONDatabase(DummyContextManager):
            def __init__(self, workload_path: str, record_path: str) -> None:
                self.workload_path = workload_path
                self.record_path = record_path

            def query_tuning_record(self, dispatched: object, target: object, task_name: str):
                return FakeRecord()

            def query_ir_module(self, dispatched: object, target: object, task_name: str):
                return scheduled_ir_module

            def query_schedule(self, dispatched: object, target: object, task_name: str):
                return FakeSchedule(scheduled_ir_module)

        class FakeExtractedTask:
            def __init__(self) -> None:
                self.task_name = operator
                self.weight = 7
                self.dispatched = [scheduled_ir_module]

        class FakeExecutable:
            def export_library(self, path: str) -> None:
                Path(path).write_bytes(b"fake-post-db-swap-artifact\n")

        class FakeApplyDatabase:
            def __init__(self, enable_warning: bool = False) -> None:
                self.enable_warning = enable_warning

            def __call__(self, mod: object) -> FakeIRModule:
                return applied_mod

        scheduled_ir_module = FakeIRModule(
            {"main": FakeFunc("scheduled_reference")},
            attrs={"tir.is_scheduled": True},
        )
        applied_mod = FakeIRModule(
            {
                operator: FakeFunc(
                    "scheduled_applied",
                    attrs={"tir.is_scheduled": True},
                )
            }
        )
        candidate_func = FakeFunc("candidate_manual")
        candidate_payload = {
            "module": object(),
            "metadata": {"operator": operator, "tag": "manual_candidate"},
            "result": {
                "evaluation_contract": {
                    "path_kind": "diagnostic_post_db_swap_build_export",
                }
            },
            "override": {
                "evaluation_contract": {
                    "path_kind": "diagnostic_post_db_swap_build_export",
                },
                "target_global_vars": [operator],
            },
            "source_path": SCRIPT_PATH,
            "source_owner": FakeIRModule({"main": candidate_func}),
            "source_func_name": "main",
            "source_func": candidate_func,
        }

        fake_relax_module = types.ModuleType("tvm.relax")
        fake_relax_module.build = lambda mod, target=None: FakeExecutable()
        fake_relax_transform_module = types.ModuleType("tvm.relax.transform")
        fake_relax_transform_module.MetaScheduleApplyDatabase = FakeApplyDatabase
        fake_database_module = types.ModuleType("tvm.s_tir.meta_schedule.database")
        fake_database_module.JSONDatabase = FakeJSONDatabase
        fake_relax_integration_module = types.ModuleType(
            "tvm.s_tir.meta_schedule.relax_integration"
        )
        fake_relax_integration_module.extract_tasks = lambda mod, target: [FakeExtractedTask()]
        fake_meta_schedule_module = types.ModuleType("tvm.s_tir.meta_schedule")
        fake_meta_schedule_module.database = fake_database_module
        fake_meta_schedule_module.relax_integration = fake_relax_integration_module
        fake_s_tir_module = types.ModuleType("tvm.s_tir")
        fake_s_tir_module.meta_schedule = fake_meta_schedule_module
        fake_tvm_module = types.ModuleType("tvm")
        fake_tvm_module.target = types.SimpleNamespace(Target=FakeTarget)
        fake_tvm_module.transform = types.SimpleNamespace(
            PassContext=lambda opt_level=3: DummyContextManager()
        )
        fake_tvm_module.relax = fake_relax_module
        fake_tvm_module.s_tir = fake_s_tir_module
        fake_tvm_module.build = lambda mod, target=None: object()
        fake_tvm_module.ir = types.SimpleNamespace(
            structural_equal=lambda lhs, rhs: (
                lhs is rhs or getattr(lhs, "tag", None) == getattr(rhs, "tag", None)
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            task_summary_path = temp_dir / "task_summary.json"
            onnx_path = temp_dir / "model.onnx"
            database_dir = temp_dir / "db"
            output_dir = temp_dir / "out"
            candidate_impl = temp_dir / "candidate_impl.py"
            onnx_path.write_bytes(b"fake-onnx")
            database_dir.mkdir()
            (database_dir / "database_workload.json").write_text("[]\n", encoding="utf-8")
            (database_dir / "database_tuning_record.json").write_text("[]\n", encoding="utf-8")
            candidate_impl.write_text("# fake candidate impl\n", encoding="utf-8")
            task_summary_path.write_text(
                json.dumps(
                    {
                        "onnx_path": str(onnx_path),
                        "input_shape": "1,48,64,64",
                        "input_name": "input",
                        "input_dtype": "float32",
                        "target": "llvm -mcpu=cortex-a72",
                        "stages": {
                            "legalized_fused_tir": {
                                "tasks": [{"task_name": operator, "rank": 3}]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with mock.patch.dict(
                sys.modules,
                {
                    "tvm": fake_tvm_module,
                    "tvm.relax": fake_relax_module,
                    "tvm.relax.transform": fake_relax_transform_module,
                    "tvm.s_tir": fake_s_tir_module,
                    "tvm.s_tir.meta_schedule": fake_meta_schedule_module,
                    "tvm.s_tir.meta_schedule.database": fake_database_module,
                    "tvm.s_tir.meta_schedule.relax_integration": fake_relax_integration_module,
                },
                clear=False,
            ):
                with mock.patch.object(
                    module,
                    "load_onnx_to_relax",
                    return_value=FakeIRModule({"main": FakeFunc("raw_relax")}),
                ):
                    with mock.patch.object(
                        module,
                        "summarize_task_stages",
                        return_value=(
                            FakeIRModule({"main": FakeFunc("tuned_relax")}),
                            {
                                "legalized_fused_tir": {
                                    "tasks": [{"task_name": operator, "rank": 3}]
                                }
                            },
                        ),
                    ):
                        with mock.patch.object(
                            module,
                            "load_candidate_override",
                            return_value=candidate_payload,
                        ):
                            with mock.patch.object(
                                sys,
                                "argv",
                                [
                                    str(SCRIPT_PATH),
                                    "--task-summary",
                                    str(task_summary_path),
                                    "--database-dir",
                                    str(database_dir),
                                    "--candidate-impl",
                                    str(candidate_impl),
                                    "--output-dir",
                                    str(output_dir),
                                ],
                            ):
                                with contextlib.redirect_stdout(stdout):
                                    module.main()

            payload = json.loads(stdout.getvalue())
            artifact_path = output_dir.resolve() / f"{operator}_post_db_swap.so"
            report_path = output_dir.resolve() / f"{operator}_post_db_swap_report.json"

            self.assertEqual(payload["post_db_scheduled_swap"]["build_status"], "built")
            self.assertEqual(payload["local_build_output"]["output_dir"], str(output_dir.resolve()))
            self.assertEqual(payload["local_build_output"]["artifact_path"], str(artifact_path))
            self.assertEqual(payload["local_build_output"]["report_path"], str(report_path))
            self.assertTrue(payload["local_build_output"]["export_attempted"])
            self.assertEqual(payload["local_build_output"]["export_status"], "exported")
            self.assertTrue(artifact_path.is_file())
            self.assertTrue(report_path.is_file())

            persisted = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(
                persisted["local_build_output"]["artifact_sha256"],
                payload["local_build_output"]["artifact_sha256"],
            )
            self.assertTrue(persisted["local_build_output"]["artifact_exists"])

    def test_probe_schedule_seam_writes_post_db_scheduled_seed_when_requested(self) -> None:
        operator = module.DEFAULT_OPERATOR

        class DummyContextManager:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeTarget(DummyContextManager):
            def __init__(self, raw: str) -> None:
                self.raw = raw

        class FakeTrace:
            def __init__(self, inst_count: int) -> None:
                self.insts = list(range(inst_count))

        class FakeRecord:
            def __init__(self) -> None:
                self.run_secs = [0.1, 0.2]
                self.trace = FakeTrace(4)

        class FakeSchedule:
            def __init__(self, mod: FakeIRModule) -> None:
                self.mod = mod
                self.trace = FakeTrace(6)

        class FakeJSONDatabase(DummyContextManager):
            def __init__(self, workload_path: str, record_path: str) -> None:
                self.workload_path = workload_path
                self.record_path = record_path

            def query_tuning_record(self, dispatched: object, target: object, task_name: str):
                return FakeRecord()

            def query_ir_module(self, dispatched: object, target: object, task_name: str):
                return scheduled_ir_module

            def query_schedule(self, dispatched: object, target: object, task_name: str):
                return FakeSchedule(scheduled_ir_module)

        class FakeExtractedTask:
            def __init__(self) -> None:
                self.task_name = operator
                self.weight = 1
                self.dispatched = [scheduled_ir_module]

        class FakeApplyDatabase:
            def __init__(self, enable_warning: bool = False) -> None:
                self.enable_warning = enable_warning

            def __call__(self, mod: object) -> FakeIRModule:
                return applied_mod

        scheduled_ir_module = FakeIRModule(
            {"main": FakeFunc("scheduled_reference")},
            attrs={"tir.is_scheduled": True},
        )
        applied_mod = FakeIRModule(
            {
                operator: FakeFunc(
                    "scheduled_reference",
                    attrs={"tir.is_scheduled": True},
                )
            }
        )
        candidate_func = FakeFunc("candidate_manual")
        candidate_payload = {
            "module": object(),
            "metadata": {"operator": operator},
            "result": {
                "evaluation_contract": {
                    "path_kind": "diagnostic_post_db_swap_build_export",
                }
            },
            "override": {
                "evaluation_contract": {
                    "path_kind": "diagnostic_post_db_swap_build_export",
                },
                "target_global_vars": [operator],
            },
            "source_path": SCRIPT_PATH,
            "source_owner": FakeIRModule({"main": candidate_func}),
            "source_func_name": "main",
            "source_func": candidate_func,
        }

        fake_relax_module = types.ModuleType("tvm.relax")
        fake_relax_module.build = lambda mod, target=None: object()
        fake_relax_transform_module = types.ModuleType("tvm.relax.transform")
        fake_relax_transform_module.MetaScheduleApplyDatabase = FakeApplyDatabase
        fake_database_module = types.ModuleType("tvm.s_tir.meta_schedule.database")
        fake_database_module.JSONDatabase = FakeJSONDatabase
        fake_relax_integration_module = types.ModuleType(
            "tvm.s_tir.meta_schedule.relax_integration"
        )
        fake_relax_integration_module.extract_tasks = lambda mod, target: [FakeExtractedTask()]
        fake_meta_schedule_module = types.ModuleType("tvm.s_tir.meta_schedule")
        fake_meta_schedule_module.database = fake_database_module
        fake_meta_schedule_module.relax_integration = fake_relax_integration_module
        fake_s_tir_module = types.ModuleType("tvm.s_tir")
        fake_s_tir_module.meta_schedule = fake_meta_schedule_module
        fake_tvm_module = types.ModuleType("tvm")
        fake_tvm_module.target = types.SimpleNamespace(Target=FakeTarget)
        fake_tvm_module.transform = types.SimpleNamespace(
            PassContext=lambda opt_level=3: DummyContextManager()
        )
        fake_tvm_module.relax = fake_relax_module
        fake_tvm_module.s_tir = fake_s_tir_module
        fake_tvm_module.build = lambda mod, target=None: object()
        fake_tvm_module.IRModule = lambda mapping: FakeIRModule(mapping)
        fake_tvm_module.ir = types.SimpleNamespace(
            structural_equal=lambda lhs, rhs: (
                lhs is rhs or getattr(lhs, "tag", None) == getattr(rhs, "tag", None)
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            task_summary_path = temp_dir / "task_summary.json"
            onnx_path = temp_dir / "model.onnx"
            database_dir = temp_dir / "db"
            scheduled_seed_dir = temp_dir / "checked_in"
            candidate_impl = temp_dir / "candidate_impl.py"
            onnx_path.write_bytes(b"fake-onnx")
            database_dir.mkdir()
            scheduled_seed_dir.mkdir()
            (database_dir / "database_workload.json").write_text("[]\n", encoding="utf-8")
            (database_dir / "database_tuning_record.json").write_text("[]\n", encoding="utf-8")
            candidate_impl.write_text("# fake candidate impl\n", encoding="utf-8")
            (scheduled_seed_dir / f"{operator}_editable_seed_tir.py").write_text(
                "# raw pre-compile seed\n",
                encoding="utf-8",
            )
            (scheduled_seed_dir / "seed_manifest.json").write_text(
                "{\"operator\": \"fused_conv2d_transpose1_add9\"}\n",
                encoding="utf-8",
            )
            task_summary_path.write_text(
                json.dumps(
                    {
                        "onnx_path": str(onnx_path),
                        "input_shape": "1,48,64,64",
                        "input_name": "input",
                        "input_dtype": "float32",
                        "target": "llvm -mcpu=cortex-a72",
                        "stages": {
                            "legalized_fused_tir": {
                                "tasks": [{"task_name": operator, "rank": 16}]
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.dict(
                sys.modules,
                {
                    "tvm": fake_tvm_module,
                    "tvm.relax": fake_relax_module,
                    "tvm.relax.transform": fake_relax_transform_module,
                    "tvm.s_tir": fake_s_tir_module,
                    "tvm.s_tir.meta_schedule": fake_meta_schedule_module,
                    "tvm.s_tir.meta_schedule.database": fake_database_module,
                    "tvm.s_tir.meta_schedule.relax_integration": fake_relax_integration_module,
                },
                clear=False,
            ):
                with mock.patch.object(
                    module,
                    "load_onnx_to_relax",
                    return_value=FakeIRModule({"main": FakeFunc("raw_relax")}),
                ):
                    with mock.patch.object(
                        module,
                        "summarize_task_stages",
                        return_value=(
                            FakeIRModule({"main": FakeFunc("tuned_relax")}),
                            {
                                "legalized_fused_tir": {
                                    "tasks": [{"task_name": operator, "rank": 16}]
                                }
                            },
                        ),
                    ):
                        with mock.patch.object(
                            module,
                            "load_candidate_override",
                            return_value=candidate_payload,
                        ):
                            report = module.probe_schedule_seam(
                                task_summary_path=task_summary_path,
                                database_dir=database_dir,
                                operator=operator,
                                candidate_impl=candidate_impl,
                                build_standalone_scheduled_task=True,
                                scheduled_seed_dir=scheduled_seed_dir,
                            )

            scheduled_seed = report["post_db_scheduled_seed"]
            self.assertTrue(scheduled_seed["requested"])
            self.assertEqual(scheduled_seed["status"], "written")
            self.assertTrue(scheduled_seed["post_db_operator_tir_is_scheduled"])
            self.assertTrue(
                scheduled_seed["structural_equal_to_database_query_ir_module_main"]
            )

            reference_tir_path = scheduled_seed_dir / (
                f"{operator}_post_db_scheduled_reference_seed_tir.py"
            )
            manifest_path = scheduled_seed_dir / "post_db_scheduled_reference_seed_manifest.json"
            self.assertTrue(reference_tir_path.is_file())
            self.assertTrue(manifest_path.is_file())

            reference_tir = reference_tir_path.read_text(encoding="utf-8")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("Schedule-preserving reference/edit seed", reference_tir)
            self.assertIn("distinct from the older raw pre-compile seed", reference_tir)
            self.assertIn("def fused_conv2d_transpose1_add9():", reference_tir)
            self.assertEqual(
                manifest["seed_capture_kind"],
                "post_db_schedule_preserving_reference_seed",
            )
            self.assertEqual(
                manifest["related_files"]["raw_precompile_edit_seed_tir"],
                str(scheduled_seed_dir / f"{operator}_editable_seed_tir.py"),
            )
            self.assertTrue(manifest["source"]["post_db_operator_tir_is_scheduled"])
            self.assertTrue(
                manifest["source"][
                    "structural_equal_to_database_query_ir_module_main"
                ]
            )


if __name__ == "__main__":
    unittest.main()
