from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "prepare_fused_conv2d_transpose1_add9_manual_hook_overlay.py"
)

spec = importlib.util.spec_from_file_location(
    "prepare_fused_conv2d_transpose1_add9_manual_hook_overlay",
    SCRIPT,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class FakeGlobalVar:
    def __init__(self, name_hint: str) -> None:
        self.name_hint = name_hint


class FakePrimFunc:
    def __init__(self, script_text: str) -> None:
        self._script_text = script_text

    def script(self, show_meta: bool = False) -> str:
        del show_meta
        return self._script_text


class FakeIRModule:
    def __init__(self, mapping: dict[str, FakePrimFunc]) -> None:
        self._mapping = mapping

    def get_global_var(self, name: str) -> FakeGlobalVar:
        if name not in self._mapping:
            raise KeyError(name)
        return FakeGlobalVar(name)

    def __getitem__(self, key: object) -> FakePrimFunc:
        name = getattr(key, "name_hint", key)
        if not isinstance(name, str) or name not in self._mapping:
            raise KeyError(name)
        return self._mapping[name]


class PrepareFusedConv2dTranspose1Add9ManualHookOverlayTest(unittest.TestCase):
    def _write_scaffold_inputs(
        self,
        scaffold_dir: Path,
        *,
        include_preferred_local_build: bool = True,
    ) -> tuple[Path, Path]:
        rebuild_env = scaffold_dir / "manual_rebuild.env"
        bookkeeping_json = scaffold_dir / "bookkeeping.json"
        write_text(rebuild_env, "TUNE_TOTAL_TRIALS=0\n")
        bookkeeping = {
            "operator": "fused_conv2d_transpose1_add9",
            "current_best_staging": {
                "artifact_sha256": (
                    "5bd14b9f97d1d06f04a484cd8b1b3f57"
                    "a955d65711ed65a22f9925dcec44698d"
                )
            },
            "current_profile_json": "/tmp/current_profile.json",
            "remote_archive_dir": "/tmp/handwritten_archive",
            "operator_context": {
                "current_argument_shapes": (
                    "float32[1, 48, 64, 64], "
                    "float32[48, 24, 3, 3], "
                    "float32[1, 24, 1, 1], "
                    "float32[1, 24, 128, 128]"
                )
            },
        }
        if include_preferred_local_build:
            bookkeeping["preferred_local_post_db_build"] = {
                "command": (
                    "python3 ./session_bootstrap/scripts/"
                    "run_transpose1_post_db_local_build.py "
                    "--output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build"
                ),
                "output_dir": "./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
                "artifact_path": (
                    "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/"
                    "fused_conv2d_transpose1_add9_post_db_swap.so"
                ),
                "report_path": (
                    "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/"
                    "fused_conv2d_transpose1_add9_post_db_swap_report.json"
                ),
            }
        write_text(
            bookkeeping_json,
            json.dumps(bookkeeping, indent=2) + "\n",
        )
        return rebuild_env, bookkeeping_json

    def test_defaults_overlay_to_checked_in_candidate_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            scaffold_dir = temp_dir / "scaffold"
            rebuild_env, bookkeeping_json = self._write_scaffold_inputs(scaffold_dir)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = module.main(["--scaffold-dir", str(scaffold_dir)])
            self.assertEqual(rc, 0)
            result = json.loads(stdout.getvalue())

            overlay_env_path = scaffold_dir / "manual_hook_overlay.env"
            overlay_env = overlay_env_path.read_text(encoding="utf-8")
            self.assertIn(f"source {str(rebuild_env)}", overlay_env)
            self.assertIn(
                "TVM_HANDWRITTEN_IMPL_PATH=./session_bootstrap/handwritten/"
                "fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_manual_candidate.py",
                overlay_env,
            )
            self.assertIn("rpc_tune.py already consumes these variables", overlay_env)
            self.assertIn("This overlay is hook wiring only", overlay_env)
            self.assertIn(
                "run_transpose1_post_db_local_build.py --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
                overlay_env,
            )
            self.assertIn(
                "Preferred local build artifact: ./session_bootstrap/tmp/transpose1_post_db_swap_local_build/fused_conv2d_transpose1_add9_post_db_swap.so",
                overlay_env,
            )
            self.assertIn(
                "Preferred local build report: ./session_bootstrap/tmp/transpose1_post_db_swap_local_build/fused_conv2d_transpose1_add9_post_db_swap_report.json",
                overlay_env,
            )
            self.assertIn(
                f"TVM_HANDWRITTEN_BOOKKEEPING_JSON={bookkeeping_json}",
                overlay_env,
            )
            self.assertFalse(
                (scaffold_dir / "fused_conv2d_transpose1_add9_manual_impl.py").exists()
            )
            self.assertEqual(result["overlay_role"], "hook_wiring_only")
            self.assertTrue(result["overlay_is_hook_wiring_only"])
            self.assertEqual(
                result["preferred_local_build_command"],
                "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
            )
            self.assertEqual(
                result["preferred_local_build_output_dir"],
                "./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
            )
            self.assertEqual(
                result["preferred_local_build_artifact_path"],
                "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/fused_conv2d_transpose1_add9_post_db_swap.so",
            )
            self.assertEqual(
                result["preferred_local_build_report_path"],
                "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/fused_conv2d_transpose1_add9_post_db_swap_report.json",
            )

    def test_falls_back_to_default_local_build_references_for_older_bookkeeping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            scaffold_dir = temp_dir / "scaffold"
            self._write_scaffold_inputs(
                scaffold_dir,
                include_preferred_local_build=False,
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = module.main(["--scaffold-dir", str(scaffold_dir)])
            self.assertEqual(rc, 0)
            result = json.loads(stdout.getvalue())

            overlay_env = (scaffold_dir / "manual_hook_overlay.env").read_text(encoding="utf-8")
            self.assertIn("This overlay is hook wiring only", overlay_env)
            self.assertIn("local-only and diagnostic-only", overlay_env)
            self.assertIn(
                "run_transpose1_post_db_local_build.py --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
                overlay_env,
            )
            self.assertIn(
                "Preferred local build output dir: ./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
                overlay_env,
            )
            self.assertEqual(
                result["preferred_local_build_command"],
                "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
            )
            self.assertEqual(
                result["preferred_local_build_artifact_path"],
                "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/fused_conv2d_transpose1_add9_post_db_swap.so",
            )
            self.assertEqual(
                result["preferred_local_build_report_path"],
                "./session_bootstrap/tmp/transpose1_post_db_swap_local_build/fused_conv2d_transpose1_add9_post_db_swap_report.json",
            )

    def test_materializes_scaffold_local_manual_seed_when_path_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            scaffold_dir = temp_dir / "scaffold"
            rebuild_env, bookkeeping_json = self._write_scaffold_inputs(scaffold_dir)
            manual_impl_path = scaffold_dir / "fused_conv2d_transpose1_add9_manual_impl.py"

            rc = module.main(
                [
                    "--scaffold-dir",
                    str(scaffold_dir),
                    "--manual-impl-path",
                    str(manual_impl_path),
                ]
            )
            self.assertEqual(rc, 0)

            overlay_env_path = scaffold_dir / "manual_hook_overlay.env"
            overlay_env = overlay_env_path.read_text(encoding="utf-8")
            self.assertIn(f"source {str(rebuild_env)}", overlay_env)
            self.assertIn(
                f"TVM_HANDWRITTEN_IMPL_PATH={manual_impl_path}",
                overlay_env,
            )
            self.assertIn("TVM_HANDWRITTEN_IMPL_ENTRYPOINT=build_manual_impl", overlay_env)
            self.assertIn(
                f"TVM_HANDWRITTEN_BOOKKEEPING_JSON={bookkeeping_json}",
                overlay_env,
            )

            impl_spec = importlib.util.spec_from_file_location("manual_impl_placeholder", manual_impl_path)
            if impl_spec is None or impl_spec.loader is None:
                raise RuntimeError(f"unable to load generated module from {manual_impl_path}")
            impl_module = importlib.util.module_from_spec(impl_spec)
            impl_spec.loader.exec_module(impl_module)

            payload = impl_module.describe_placeholder()
            self.assertEqual(payload["operator"], "fused_conv2d_transpose1_add9")
            self.assertEqual(
                payload["reference_staging_sha256"],
                "5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d",
            )
            self.assertEqual(payload["bookkeeping_json"], str(bookkeeping_json))
            self.assertTrue(payload["placeholder_only"])
            self.assertEqual(
                payload["seed_json"],
                str(scaffold_dir / "fused_conv2d_transpose1_add9_manual_seed.json"),
            )
            self.assertEqual(
                payload["seed_tir"],
                str(scaffold_dir / "fused_conv2d_transpose1_add9_manual_seed_tir.py"),
            )

            context = {
                "phase": "pre_compile",
                "operator": "fused_conv2d_transpose1_add9",
                "module_path": str(manual_impl_path),
                "output_dir": str(temp_dir / "build_output"),
                "target": "llvm",
                "database": "fake-db",
                "bookkeeping_json": str(bookkeeping_json),
                "task_stages": {
                    "legalized_fused_tir": {
                        "tasks": [
                            {
                                "task_name": "fused_conv2d_transpose1_add9",
                                "prim_funcs": ["fused_conv2d_transpose1_add9"],
                                "weight": 1,
                            }
                        ]
                    }
                },
                "mod": FakeIRModule(
                    {
                        "fused_conv2d_transpose1_add9": FakePrimFunc(
                            "def fused_conv2d_transpose1_add9():\n    pass\n"
                        )
                    }
                ),
            }
            with self.assertRaises(NotImplementedError):
                impl_module.build_manual_impl(context)

            seed_json = json.loads(
                (scaffold_dir / "fused_conv2d_transpose1_add9_manual_seed.json").read_text(
                    encoding="utf-8"
                )
            )
            seed_tir = (
                scaffold_dir / "fused_conv2d_transpose1_add9_manual_seed_tir.py"
            ).read_text(encoding="utf-8")
            self.assertEqual(seed_json["operator"], "fused_conv2d_transpose1_add9")
            self.assertEqual(seed_json["phase"], "pre_compile")
            self.assertEqual(seed_json["task_row"]["stage_name"], "legalized_fused_tir")
            self.assertEqual(seed_json["prim_func_capture"][0]["name"], "fused_conv2d_transpose1_add9")
            self.assertIn("PrimFunc: fused_conv2d_transpose1_add9", seed_tir)
            self.assertIn("def fused_conv2d_transpose1_add9()", seed_tir)


if __name__ == "__main__":
    unittest.main()
