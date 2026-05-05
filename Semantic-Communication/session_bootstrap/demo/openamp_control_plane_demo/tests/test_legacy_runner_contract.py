from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from threading import Lock
import textwrap
import unittest
from unittest.mock import Mock


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DEMO_ROOT.parents[2]
LEGACY_RUNNER = REPO_ROOT / "session_bootstrap" / "scripts" / "run_remote_legacy_tvm_compat.sh"
CURRENT_RUNNER = REPO_ROOT / "session_bootstrap" / "scripts" / "run_remote_current_real_reconstruction.sh"

if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

import inference_runner  # noqa: E402
from inference_runner import LiveRemoteReconstructionJob, PROJECT_ROOT  # noqa: E402


def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


class LegacyCompatRunnerContractTest(unittest.TestCase):
    def test_local_runner_emits_json_summary_after_legacy_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            fake_python_root = temp_dir / "fake_pythonpath"
            fake_tvm_dir = fake_python_root / "tvm"
            fake_tvm_dir.mkdir(parents=True)

            write_file(
                fake_tvm_dir / "__init__.py",
                textwrap.dedent(
                    """\
                    from . import relax, runtime


                    def cpu(index=0):
                        return ("cpu", index)
                    """
                ),
            )
            write_file(
                fake_tvm_dir / "runtime.py",
                textwrap.dedent(
                    """\
                    class _Module:
                        type_key = "library"


                    def load_module(path):
                        return _Module()
                    """
                ),
            )
            write_file(
                fake_tvm_dir / "relax.py",
                textwrap.dedent(
                    """\
                    class VirtualMachine:
                        def __init__(self, lib, dev):
                            self.lib = lib
                            self.dev = dev
                    """
                ),
            )

            fake_python = temp_dir / "fake_python.sh"
            write_executable(
                fake_python,
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    export PYTHONPATH="{fake_python_root}${{PYTHONPATH:+:${{PYTHONPATH}}}}"
                    exec python3 "$@"
                    """
                ),
            )

            jscc_dir = temp_dir / "jscc"
            jscc_dir.mkdir()
            artifact_dir = jscc_dir / "tvm_tune_logs"
            artifact_dir.mkdir()
            artifact_path = artifact_dir / "optimized_model.so"
            artifact_bytes = b"legacy-openamp-artifact"
            artifact_path.write_bytes(artifact_bytes)
            expected_sha = hashlib.sha256(artifact_bytes).hexdigest()

            write_file(
                jscc_dir / "tvm_002.py",
                textwrap.dedent(
                    """\
                    import argparse
                    from pathlib import Path


                    parser = argparse.ArgumentParser()
                    parser.add_argument("--input_dir", required=True)
                    parser.add_argument("--output_dir", required=True)
                    parser.add_argument("--snr", required=True)
                    parser.add_argument("--batch_size", required=True)
                    args = parser.parse_args()

                    input_files = sorted(path for path in Path(args.input_dir).iterdir() if path.is_file())
                    recon_dir = Path(args.output_dir) / "reconstructions"
                    recon_dir.mkdir(parents=True, exist_ok=True)
                    for input_path in input_files:
                        save_path = recon_dir / f"{input_path.stem}_recon.png"
                        save_path.write_bytes(b"fake-png")
                        print("批量推理时间（1 个样本）: 0.012 秒")
                        print(f"重构图像保存至: {save_path}")
                    print("处理完成")
                    """
                ),
            )

            input_dir = temp_dir / "inputs"
            input_dir.mkdir()
            (input_dir / "sample_000.pt").write_bytes(b"latent-000")
            (input_dir / "sample_001.npy").write_bytes(b"latent-001")
            output_base = temp_dir / "outputs"
            output_base.mkdir()

            env = os.environ.copy()
            env.update(
                {
                    "REMOTE_MODE": "local",
                    "REMOTE_TVM_PYTHON": str(fake_python),
                    "REMOTE_JSCC_DIR": str(jscc_dir),
                    "REMOTE_INPUT_DIR": str(input_dir),
                    "REMOTE_OUTPUT_BASE": str(output_base),
                    "REMOTE_SNR_BASELINE": "10",
                    "REMOTE_BATCH_BASELINE": "1",
                    "REMOTE_BASELINE_ARTIFACT": str(artifact_path),
                    "INFERENCE_BASELINE_EXPECTED_SHA256": expected_sha,
                }
            )

            result = subprocess.run(
                ["bash", str(LEGACY_RUNNER), "--variant", "baseline", "--max-inputs", "1"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 3)
            self.assertIn("批量推理时间（1 个样本）", result.stdout)

            summary = json.loads(lines[-1])
            self.assertEqual(summary["variant"], "baseline")
            self.assertEqual(summary["artifact_path"], str(artifact_path))
            self.assertEqual(summary["artifact_sha256"], expected_sha)
            self.assertEqual(summary["artifact_sha256_expected"], expected_sha)
            self.assertTrue(summary["artifact_sha256_match"])
            self.assertEqual(summary["output_count"], 1)
            self.assertEqual(summary["processed_count"], 1)
            self.assertEqual(summary["input_count"], 1)
            self.assertEqual(summary["available_input_count"], 2)
            self.assertEqual(summary["run_count"], 1)
            self.assertEqual(summary["run_samples_ms"], [12.0])
            self.assertEqual(summary["run_median_ms"], 12.0)
            self.assertEqual(summary["run_mean_ms"], 12.0)
            self.assertEqual(summary["load_ms"], 0.0)
            self.assertEqual(summary["vm_init_ms"], 0.0)
            self.assertEqual(summary["max_inputs"], 1)
            self.assertEqual(summary["parser"], "legacy_latency_lines")
            self.assertEqual(summary["save_format"], "png")
            self.assertTrue(summary["output_dir"].endswith("/reconstructions"))

    def test_local_runner_respects_100_image_cap_and_ignores_stale_outputs_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            fake_python_root = temp_dir / "fake_pythonpath"
            fake_tvm_dir = fake_python_root / "tvm"
            fake_tvm_dir.mkdir(parents=True)

            write_file(
                fake_tvm_dir / "__init__.py",
                textwrap.dedent(
                    """\
                    from . import relax, runtime


                    def cpu(index=0):
                        return ("cpu", index)
                    """
                ),
            )
            write_file(
                fake_tvm_dir / "runtime.py",
                textwrap.dedent(
                    """\
                    class _Module:
                        type_key = "library"


                    def load_module(path):
                        return _Module()
                    """
                ),
            )
            write_file(
                fake_tvm_dir / "relax.py",
                textwrap.dedent(
                    """\
                    class VirtualMachine:
                        def __init__(self, lib, dev):
                            self.lib = lib
                            self.dev = dev
                    """
                ),
            )

            fake_python = temp_dir / "fake_python.sh"
            write_executable(
                fake_python,
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    export PYTHONPATH="{fake_python_root}${{PYTHONPATH:+:${{PYTHONPATH}}}}"
                    exec python3 "$@"
                    """
                ),
            )

            jscc_dir = temp_dir / "jscc"
            jscc_dir.mkdir()
            artifact_dir = jscc_dir / "tvm_tune_logs"
            artifact_dir.mkdir()
            artifact_path = artifact_dir / "optimized_model.so"
            artifact_bytes = b"legacy-openamp-artifact"
            artifact_path.write_bytes(artifact_bytes)
            expected_sha = hashlib.sha256(artifact_bytes).hexdigest()

            write_file(
                jscc_dir / "tvm_002.py",
                textwrap.dedent(
                    """\
                    import argparse
                    from pathlib import Path


                    parser = argparse.ArgumentParser()
                    parser.add_argument("--input_dir", required=True)
                    parser.add_argument("--output_dir", required=True)
                    parser.add_argument("--snr", required=True)
                    parser.add_argument("--batch_size", required=True)
                    args = parser.parse_args()

                    input_files = sorted(path for path in Path(args.input_dir).iterdir() if path.is_file())
                    recon_dir = Path(args.output_dir) / "reconstructions"
                    recon_dir.mkdir(parents=True, exist_ok=True)
                    for input_path in input_files:
                        save_path = recon_dir / f"{input_path.stem}_recon.png"
                        save_path.write_bytes(b"fake-png")
                        print("批量推理时间（1 个样本）: 0.012 秒")
                    print("处理完成")
                    """
                ),
            )

            input_dir = temp_dir / "inputs"
            input_dir.mkdir()
            for index in range(105):
                suffix = ".pt" if index % 2 == 0 else ".npy"
                (input_dir / f"sample_{index:03d}{suffix}").write_bytes(f"latent-{index:03d}".encode("utf-8"))
            output_base = temp_dir / "outputs"
            output_base.mkdir()
            stale_recon_dir = output_base / "inference_benchmark_baseline" / "reconstructions"
            stale_recon_dir.mkdir(parents=True)
            stale_output = stale_recon_dir / "stale_extra.png"
            stale_output.write_bytes(b"stale-png")
            os.utime(stale_output, (1, 1))

            env = os.environ.copy()
            env.update(
                {
                    "REMOTE_MODE": "local",
                    "REMOTE_TVM_PYTHON": str(fake_python),
                    "REMOTE_JSCC_DIR": str(jscc_dir),
                    "REMOTE_INPUT_DIR": str(input_dir),
                    "REMOTE_OUTPUT_BASE": str(output_base),
                    "REMOTE_SNR_BASELINE": "10",
                    "REMOTE_BATCH_BASELINE": "1",
                    "REMOTE_BASELINE_ARTIFACT": str(artifact_path),
                    "INFERENCE_BASELINE_EXPECTED_SHA256": expected_sha,
                }
            )

            result = subprocess.run(
                ["bash", str(LEGACY_RUNNER), "--variant", "baseline", "--max-inputs", "300"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads([line.strip() for line in result.stdout.splitlines() if line.strip()][-1])
            self.assertEqual(summary["variant"], "baseline")
            self.assertEqual(summary["artifact_path"], str(artifact_path))
            self.assertEqual(summary["artifact_sha256"], expected_sha)
            self.assertEqual(summary["artifact_sha256_expected"], expected_sha)
            self.assertTrue(summary["artifact_sha256_match"])
            self.assertEqual(summary["available_input_count"], 105)
            self.assertEqual(summary["input_count"], 105)
            self.assertEqual(summary["processed_count"], 105)
            self.assertEqual(summary["run_count"], 105)
            self.assertEqual(len(summary["run_samples_ms"]), 105)
            self.assertEqual(summary["output_count"], 105)
            self.assertEqual(summary["max_inputs"], 300)
            self.assertEqual(summary["save_format"], "png")
            self.assertTrue(summary["output_dir"].endswith("/reconstructions"))

    def test_legacy_runner_defaults_to_demo_100_image_cap_without_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            fake_python_root = temp_dir / "fake_pythonpath"
            fake_tvm_dir = fake_python_root / "tvm"
            fake_tvm_dir.mkdir(parents=True)

            write_file(
                fake_tvm_dir / "__init__.py",
                textwrap.dedent(
                    """\
                    from . import relax, runtime


                    def cpu(index=0):
                        return ("cpu", index)
                    """
                ),
            )
            write_file(
                fake_tvm_dir / "runtime.py",
                textwrap.dedent(
                    """\
                    class _Module:
                        type_key = "library"


                    def load_module(path):
                        return _Module()
                    """
                ),
            )
            write_file(
                fake_tvm_dir / "relax.py",
                textwrap.dedent(
                    """\
                    class VirtualMachine:
                        def __init__(self, lib, dev):
                            self.lib = lib
                            self.dev = dev
                    """
                ),
            )

            fake_python = temp_dir / "fake_python.sh"
            write_executable(
                fake_python,
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    export PYTHONPATH="{fake_python_root}${{PYTHONPATH:+:${{PYTHONPATH}}}}"
                    exec python3 "$@"
                    """
                ),
            )

            jscc_dir = temp_dir / "jscc"
            jscc_dir.mkdir()
            artifact_dir = jscc_dir / "tvm_tune_logs"
            artifact_dir.mkdir()
            artifact_path = artifact_dir / "optimized_model.so"
            artifact_bytes = b"legacy-openamp-artifact"
            artifact_path.write_bytes(artifact_bytes)
            expected_sha = hashlib.sha256(artifact_bytes).hexdigest()

            write_file(
                jscc_dir / "tvm_002.py",
                textwrap.dedent(
                    """\
                    import argparse
                    from pathlib import Path


                    parser = argparse.ArgumentParser()
                    parser.add_argument("--input_dir", required=True)
                    parser.add_argument("--output_dir", required=True)
                    parser.add_argument("--snr", required=True)
                    parser.add_argument("--batch_size", required=True)
                    args = parser.parse_args()

                    input_files = sorted(path for path in Path(args.input_dir).iterdir() if path.is_file())
                    recon_dir = Path(args.output_dir) / "reconstructions"
                    recon_dir.mkdir(parents=True, exist_ok=True)
                    for input_path in input_files:
                        (recon_dir / f"{input_path.stem}_recon.png").write_bytes(b"fake-png")
                        print("批量推理时间（1 个样本）: 0.010 秒")
                    """
                ),
            )

            input_dir = temp_dir / "inputs"
            input_dir.mkdir()
            for index in range(105):
                suffix = ".pt" if index % 2 == 0 else ".npy"
                (input_dir / f"sample_{index:03d}{suffix}").write_bytes(f"latent-{index:03d}".encode("utf-8"))
            output_base = temp_dir / "outputs"
            output_base.mkdir()

            env = os.environ.copy()
            env.update(
                {
                    "REMOTE_MODE": "local",
                    "REMOTE_TVM_PYTHON": str(fake_python),
                    "REMOTE_JSCC_DIR": str(jscc_dir),
                    "REMOTE_INPUT_DIR": str(input_dir),
                    "REMOTE_OUTPUT_BASE": str(output_base),
                    "REMOTE_SNR_BASELINE": "10",
                    "REMOTE_BATCH_BASELINE": "1",
                    "REMOTE_BASELINE_ARTIFACT": str(artifact_path),
                    "INFERENCE_BASELINE_EXPECTED_SHA256": expected_sha,
                    "OPENAMP_DEMO_MODE": "1",
                    "OPENAMP_DEMO_MAX_INPUTS": "300",
                }
            )

            result = subprocess.run(
                ["bash", str(LEGACY_RUNNER), "--variant", "baseline"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads([line.strip() for line in result.stdout.splitlines() if line.strip()][-1])
            self.assertEqual(summary["max_inputs"], 300)
            self.assertEqual(summary["input_count"], 105)
            self.assertEqual(summary["processed_count"], 105)
            self.assertEqual(summary["output_count"], 105)
            self.assertEqual(summary["available_input_count"], 105)


class CurrentReconstructionRunnerContractTest(unittest.TestCase):
    def test_local_runner_defaults_to_demo_300_image_cap_and_clears_stale_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            fake_python = temp_dir / "fake_python.sh"
            write_executable(
                fake_python,
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    cat >/dev/null

                    artifact_path=""
                    input_dir=""
                    output_dir=""
                    variant=""
                    expected_sha256=""
                    max_inputs="0"

                    while [[ $# -gt 0 ]]; do
                      case "$1" in
                        --artifact-path)
                          artifact_path="$2"
                          shift 2
                          ;;
                        --input-dir)
                          input_dir="$2"
                          shift 2
                          ;;
                        --output-dir)
                          output_dir="$2"
                          shift 2
                          ;;
                        --variant)
                          variant="$2"
                          shift 2
                          ;;
                        --expected-sha256)
                          expected_sha256="$2"
                          shift 2
                          ;;
                        --max-inputs)
                          max_inputs="$2"
                          shift 2
                          ;;
                        *)
                          shift
                          ;;
                      esac
                    done

                    mapfile -t input_files < <(find "$input_dir" -maxdepth 1 -type f -name '*.npy' | LC_ALL=C sort)
                    available_input_count="${#input_files[@]}"
                    selected_input_count="$available_input_count"
                    if [[ "$max_inputs" != "0" && "$available_input_count" -gt "$max_inputs" ]]; then
                      selected_input_count="$max_inputs"
                    fi

                    recon_dir="$output_dir/reconstructions"
                    mkdir -p "$recon_dir"
                    for ((index = 0; index < selected_input_count; index++)); do
                      input_path="${input_files[$index]}"
                      stem="$(basename "${input_path%.*}")"
                      printf 'fake-recon' > "$recon_dir/${stem}_recon.npy"
                    done

                    python3 - "$artifact_path" "$expected_sha256" "$input_dir" "$recon_dir" "$variant" "$available_input_count" "$selected_input_count" "$max_inputs" <<'PY'
import json
import sys

(
    artifact_path,
    expected_sha256,
    input_dir,
    recon_dir,
    variant,
    available_input_count,
    selected_input_count,
    max_inputs,
) = sys.argv[1:]

selected_input_count = int(selected_input_count)
available_input_count = int(available_input_count)
max_inputs = int(max_inputs)

summary = {
    "variant": variant,
    "artifact_path": artifact_path,
    "artifact_sha256": expected_sha256,
    "artifact_sha256_expected": expected_sha256,
    "artifact_sha256_match": True,
    "input_dir": input_dir,
    "output_dir": recon_dir,
    "output_count": selected_input_count,
    "processed_count": selected_input_count,
    "input_count": selected_input_count,
    "available_input_count": available_input_count,
    "load_ms": 0.0,
    "vm_init_ms": 0.0,
    "run_count": selected_input_count,
    "run_samples_ms": [12.0] * selected_input_count,
    "run_median_ms": 12.0,
    "run_mean_ms": 12.0,
    "run_min_ms": 12.0,
    "run_max_ms": 12.0,
    "run_variance_ms2": 0.0,
    "output_shape": [1, 1, 2, 2],
    "output_dtype": "float32",
    "snr": 12.0,
    "batch_size": 1,
    "save_format": "npy",
    "seed": None,
    "max_inputs": max_inputs,
}
print(json.dumps(summary, ensure_ascii=False))
PY
                    """
                ),
            )

            artifact_path = temp_dir / "optimized_model.so"
            artifact_bytes = b"current-openamp-artifact"
            artifact_path.write_bytes(artifact_bytes)
            expected_sha = hashlib.sha256(artifact_bytes).hexdigest()

            input_dir = temp_dir / "inputs"
            input_dir.mkdir()
            for index in range(305):
                (input_dir / f"sample_{index:03d}.npy").write_bytes(f"latent-{index:03d}".encode("utf-8"))

            output_base = temp_dir / "outputs"
            output_base.mkdir()
            stale_recon_dir = output_base / "inference_real_reconstruction_current" / "reconstructions"
            stale_recon_dir.mkdir(parents=True)
            stale_output = stale_recon_dir / "stale_single_image.npy"
            stale_output.write_bytes(b"stale")
            os.utime(stale_output, (1, 1))

            env = os.environ.copy()
            env.update(
                {
                    "REMOTE_MODE": "local",
                    "REMOTE_TVM_PYTHON": str(fake_python),
                    "REMOTE_INPUT_DIR": str(input_dir),
                    "REMOTE_OUTPUT_BASE": str(output_base),
                    "REMOTE_SNR_CURRENT": "12",
                    "REMOTE_BATCH_CURRENT": "1",
                    "REMOTE_CURRENT_ARTIFACT": str(artifact_path),
                    "INFERENCE_CURRENT_EXPECTED_SHA256": expected_sha,
                    "OPENAMP_DEMO_MODE": "1",
                    "OPENAMP_DEMO_MAX_INPUTS": "300",
                }
            )

            result = subprocess.run(
                ["bash", str(CURRENT_RUNNER), "--variant", "current"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads([line.strip() for line in result.stdout.splitlines() if line.strip()][-1])
            self.assertEqual(summary["variant"], "current")
            self.assertEqual(summary["artifact_path"], str(artifact_path))
            self.assertEqual(summary["artifact_sha256"], expected_sha)
            self.assertEqual(summary["artifact_sha256_expected"], expected_sha)
            self.assertTrue(summary["artifact_sha256_match"])
            self.assertEqual(summary["max_inputs"], 300)
            self.assertEqual(summary["available_input_count"], 305)
            self.assertEqual(summary["input_count"], 300)
            self.assertEqual(summary["processed_count"], 300)
            self.assertEqual(summary["run_count"], 300)
            self.assertEqual(len(summary["run_samples_ms"]), 300)
            self.assertEqual(summary["output_count"], 300)
            self.assertFalse(stale_output.exists())

    def test_ssh_runner_stages_trusted_local_current_artifact_and_uses_it_instead_of_mutable_remote_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            runner_dir = temp_dir / "runner"
            runner_dir.mkdir()
            staged_runner = runner_dir / "run_remote_current_real_reconstruction.sh"
            staged_runner.write_text(CURRENT_RUNNER.read_text(encoding="utf-8"), encoding="utf-8")
            staged_runner.chmod(
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH
            )
            write_file(
                runner_dir / "current_real_reconstruction.py",
                "print('placeholder runner source')\n",
            )
            write_executable(
                runner_dir / "ssh_with_password.sh",
                (REPO_ROOT / "session_bootstrap" / "scripts" / "ssh_with_password.sh").read_text(encoding="utf-8"),
            )
            fake_ssh = temp_dir / "ssh"
            write_executable(
                fake_ssh,
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    while [[ $# -gt 0 ]]; do
                      case "$1" in
                        -p|-o)
                          shift 2
                          ;;
                        -*)
                          shift
                          ;;
                        *@*)
                          shift
                          break
                          ;;
                        *)
                          break
                          ;;
                      esac
                    done

                    if [[ $# -eq 0 ]]; then
                      echo "missing remote command" >&2
                      exit 1
                    fi

                    remote_command="$1"
                    shift
                    for arg in "$@"; do
                      remote_command+=" $arg"
                    done

                    exec bash -lc "$remote_command"
                    """
                ),
            )

            fake_python = temp_dir / "fake_python.sh"
            write_executable(
                fake_python,
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    cat >/dev/null

                    artifact_path=""
                    input_dir=""
                    output_dir=""
                    variant=""
                    expected_sha256=""
                    max_inputs="0"

                    while [[ $# -gt 0 ]]; do
                      case "$1" in
                        --artifact-path)
                          artifact_path="$2"
                          shift 2
                          ;;
                        --input-dir)
                          input_dir="$2"
                          shift 2
                          ;;
                        --output-dir)
                          output_dir="$2"
                          shift 2
                          ;;
                        --variant)
                          variant="$2"
                          shift 2
                          ;;
                        --expected-sha256)
                          expected_sha256="$2"
                          shift 2
                          ;;
                        --max-inputs)
                          max_inputs="$2"
                          shift 2
                          ;;
                        *)
                          shift
                          ;;
                      esac
                    done

                    mapfile -t input_files < <(find "$input_dir" -maxdepth 1 -type f -name '*.npy' | LC_ALL=C sort)
                    available_input_count="${#input_files[@]}"
                    selected_input_count="$available_input_count"
                    if [[ "$max_inputs" != "0" && "$available_input_count" -gt "$max_inputs" ]]; then
                      selected_input_count="$max_inputs"
                    fi

                    recon_dir="$output_dir/reconstructions"
                    mkdir -p "$recon_dir"
                    for ((index = 0; index < selected_input_count; index++)); do
                      input_path="${input_files[$index]}"
                      stem="$(basename "${input_path%.*}")"
                      printf 'fake-recon' > "$recon_dir/${stem}_recon.npy"
                    done

                    python3 - "$artifact_path" "$expected_sha256" "$input_dir" "$recon_dir" "$variant" "$available_input_count" "$selected_input_count" "$max_inputs" <<'PY'
import json
import sys

(
    artifact_path,
    expected_sha256,
    input_dir,
    recon_dir,
    variant,
    available_input_count,
    selected_input_count,
    max_inputs,
) = sys.argv[1:]

selected_input_count = int(selected_input_count)
available_input_count = int(available_input_count)
max_inputs = int(max_inputs)

summary = {
    "variant": variant,
    "artifact_path": artifact_path,
    "artifact_sha256": expected_sha256,
    "artifact_sha256_expected": expected_sha256,
    "artifact_sha256_match": True,
    "input_dir": input_dir,
    "output_dir": recon_dir,
    "output_count": selected_input_count,
    "processed_count": selected_input_count,
    "input_count": selected_input_count,
    "available_input_count": available_input_count,
    "load_ms": 0.0,
    "vm_init_ms": 0.0,
    "run_count": selected_input_count,
    "run_samples_ms": [12.0] * selected_input_count,
    "run_median_ms": 12.0,
    "run_mean_ms": 12.0,
    "run_min_ms": 12.0,
    "run_max_ms": 12.0,
    "run_variance_ms2": 0.0,
    "output_shape": [1, 1, 2, 2],
    "output_dtype": "float32",
    "snr": 12.0,
    "batch_size": 1,
    "save_format": "npy",
    "seed": None,
    "max_inputs": max_inputs,
}
print(json.dumps(summary, ensure_ascii=False))
PY
                    """
                ),
            )

            trusted_source = temp_dir / "trusted_current.so"
            trusted_bytes = b"trusted-current-artifact"
            trusted_source.write_bytes(trusted_bytes)
            expected_sha = hashlib.sha256(trusted_bytes).hexdigest()

            mutable_remote_dir = temp_dir / "mutable_remote" / "tvm_tune_logs"
            mutable_remote_dir.mkdir(parents=True)
            mutable_remote_artifact = mutable_remote_dir / "optimized_model.so"
            mutable_remote_artifact.write_bytes(b"baseline-artifact")

            input_dir = temp_dir / "inputs"
            input_dir.mkdir()
            (input_dir / "sample_000.npy").write_bytes(b"latent-000")
            output_base = temp_dir / "outputs"
            output_base.mkdir()
            remote_stage_root = temp_dir / "remote_stage_root"

            env = os.environ.copy()
            env.update(
                {
                    "REMOTE_MODE": "ssh",
                    "REMOTE_HOST": "demo-board",
                    "REMOTE_USER": "demo-user",
                    "REMOTE_PASS": "demo-pass",
                    "REMOTE_SSH_PORT": "22",
                    "REMOTE_TVM_PYTHON": str(fake_python),
                    "REMOTE_INPUT_DIR": str(input_dir),
                    "REMOTE_OUTPUT_BASE": str(output_base),
                    "REMOTE_SNR_CURRENT": "12",
                    "REMOTE_BATCH_CURRENT": "1",
                    "REMOTE_CURRENT_ARTIFACT": str(mutable_remote_artifact),
                    "REMOTE_CURRENT_ARTIFACT_STAGE_DIR": str(remote_stage_root),
                    "LOCAL_CURRENT_ARTIFACT_SOURCE": str(trusted_source),
                    "INFERENCE_CURRENT_EXPECTED_SHA256": expected_sha,
                }
            )
            env["PATH"] = f"{temp_dir}:{env.get('PATH', '')}"

            result = subprocess.run(
                ["bash", str(staged_runner), "--variant", "current", "--max-inputs", "1"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads([line.strip() for line in result.stdout.splitlines() if line.strip()][-1])
            staged_remote_artifact = remote_stage_root / ".openamp_demo_current" / expected_sha / "optimized_model.so"
            self.assertIn("staged trusted current artifact source", result.stdout)
            self.assertEqual(summary["variant"], "current")
            self.assertEqual(summary["artifact_path"], str(staged_remote_artifact))
            self.assertEqual(summary["artifact_sha256"], expected_sha)
            self.assertEqual(summary["artifact_sha256_expected"], expected_sha)
            self.assertTrue(summary["artifact_sha256_match"])
            self.assertNotEqual(summary["artifact_path"], str(mutable_remote_artifact))
            self.assertEqual(staged_remote_artifact.read_bytes(), trusted_bytes)
            self.assertEqual(mutable_remote_artifact.read_bytes(), b"baseline-artifact")

    def test_ssh_runner_exports_torch_sidecar_env_when_remote_python_overrides_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            runner_dir = temp_dir / "runner"
            runner_dir.mkdir()
            staged_runner = runner_dir / "run_remote_current_real_reconstruction.sh"
            staged_runner.write_text(CURRENT_RUNNER.read_text(encoding="utf-8"), encoding="utf-8")
            staged_runner.chmod(
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH
            )
            write_file(
                runner_dir / "current_real_reconstruction.py",
                textwrap.dedent(
                    """\
                    import argparse
                    import json
                    import os
                    from pathlib import Path
                    import sys


                    def import_torch():
                        extra_pythonpath = (
                            os.environ.get("REMOTE_TORCH_PYTHONPATH")
                            or os.environ.get("REMOTE_REAL_EXTRA_PYTHONPATH")
                            or os.environ.get("DEMO_EXTRA_PYTHONPATH")
                            or ""
                        )
                        for entry in reversed([value for value in extra_pythonpath.split(":") if value]):
                            if entry not in sys.path:
                                sys.path.insert(0, entry)
                        import torch

                        return torch, extra_pythonpath


                    parser = argparse.ArgumentParser()
                    parser.add_argument("--artifact-path", required=True)
                    parser.add_argument("--input-dir", required=True)
                    parser.add_argument("--output-dir", required=True)
                    parser.add_argument("--variant", required=True)
                    parser.add_argument("--expected-sha256", default="")
                    parser.add_argument("--max-inputs", type=int, default=0)
                    parser.add_argument("--snr")
                    parser.add_argument("--batch-size")
                    args = parser.parse_args()

                    torch, extra_pythonpath = import_torch()
                    pt_inputs = sorted(Path(args.input_dir).glob("*.pt"))
                    if not pt_inputs:
                        raise SystemExit("missing pt input")
                    payload = torch.load(pt_inputs[0], map_location="cpu", weights_only=True)
                    recon_dir = Path(args.output_dir) / "reconstructions"
                    recon_dir.mkdir(parents=True, exist_ok=True)
                    (recon_dir / f"{pt_inputs[0].stem}_recon.npy").write_text("ok", encoding="utf-8")
                    print(
                        json.dumps(
                            {
                                "variant": args.variant,
                                "artifact_path": args.artifact_path,
                                "artifact_sha256": args.expected_sha256,
                                "artifact_sha256_expected": args.expected_sha256,
                                "artifact_sha256_match": True,
                                "input_dir": args.input_dir,
                                "output_dir": str(recon_dir),
                                "output_count": 1,
                                "processed_count": 1,
                                "input_count": 1,
                                "available_input_count": 1,
                                "load_ms": 0.0,
                                "vm_init_ms": 0.0,
                                "run_count": 1,
                                "run_samples_ms": [1.0],
                                "run_median_ms": 1.0,
                                "run_mean_ms": 1.0,
                                "run_min_ms": 1.0,
                                "run_max_ms": 1.0,
                                "run_variance_ms2": 0.0,
                                "output_shape": [1, 1, 1, 1],
                                "output_dtype": "float32",
                                "snr": 12.0,
                                "batch_size": 1,
                                "save_format": "npy",
                                "seed": None,
                                "max_inputs": args.max_inputs,
                                "torch_sidecar_pythonpath": extra_pythonpath,
                                "torch_payload_keys": sorted(payload),
                            },
                            ensure_ascii=False,
                        )
                    )
                    """
                ),
            )
            write_executable(
                runner_dir / "ssh_with_password.sh",
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    while [[ $# -gt 0 ]]; do
                      case "$1" in
                        --host|--user|--pass|--port)
                          shift 2
                          ;;
                        --)
                          shift
                          break
                          ;;
                        *)
                          shift
                          ;;
                      esac
                    done

                    exec env -i PATH="$PATH" "$@"
                    """
                ),
            )

            fake_torch_root = temp_dir / "fake_torch"
            (fake_torch_root / "torch").mkdir(parents=True)
            write_file(
                fake_torch_root / "torch" / "__init__.py",
                textwrap.dedent(
                    """\
                    import json


                    def load(path, map_location=None, weights_only=None):
                        with open(path, "r", encoding="utf-8") as infile:
                            return json.load(infile)
                    """
                ),
            )

            fake_python = temp_dir / "fake_python.sh"
            write_executable(
                fake_python,
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    exec python3 "$@"
                    """
                ),
            )

            artifact_path = temp_dir / "optimized_model.so"
            artifact_bytes = b"current-openamp-artifact"
            artifact_path.write_bytes(artifact_bytes)
            expected_sha = hashlib.sha256(artifact_bytes).hexdigest()

            input_dir = temp_dir / "inputs"
            input_dir.mkdir()
            write_file(
                input_dir / "sample_000.pt",
                '{"quant": [[[1.0]]], "scale": [[[1.0]]], "zero_point": [[[0.0]]]}',
            )

            output_base = temp_dir / "outputs"
            output_base.mkdir()

            env = os.environ.copy()
            env.update(
                {
                    "REMOTE_MODE": "ssh",
                    "REMOTE_HOST": "demo-host",
                    "REMOTE_USER": "demo-user",
                    "REMOTE_PASS": "demo-pass",
                    "REMOTE_TVM_PYTHON": f"env PYTHONPATH=/tmp/tvm_only {fake_python}",
                    "REMOTE_INPUT_DIR": str(input_dir),
                    "REMOTE_OUTPUT_BASE": str(output_base),
                    "REMOTE_SNR_CURRENT": "12",
                    "REMOTE_BATCH_CURRENT": "1",
                    "REMOTE_CURRENT_ARTIFACT": str(artifact_path),
                    "REMOTE_TORCH_PYTHONPATH": str(fake_torch_root),
                    "INFERENCE_CURRENT_EXPECTED_SHA256": expected_sha,
                }
            )

            result = subprocess.run(
                ["bash", str(staged_runner), "--variant", "current", "--max-inputs", "1"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads([line.strip() for line in result.stdout.splitlines() if line.strip()][-1])
            self.assertEqual(summary["processed_count"], 1)
            self.assertEqual(summary["output_count"], 1)
            self.assertEqual(summary["torch_sidecar_pythonpath"], str(fake_torch_root))
            self.assertEqual(summary["torch_payload_keys"], ["quant", "scale", "zero_point"])


class LegacyBaselineLiveConsumptionTest(unittest.TestCase):
    def test_live_job_accepts_legacy_summary_json_as_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_name:
            output_dir = Path(temp_dir_name)
            trace_path = output_dir / "control_trace.jsonl"
            summary_path = output_dir / "wrapper_summary.json"
            runner_log_path = output_dir / "runner.log"

            trace_events = [
                {
                    "at": "2026-03-15T21:00:00+0800",
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 4242},
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                            "rx_frame": {
                                "status_resp": {
                                    "guard_state_name": "READY",
                                    "last_fault_name": "NONE",
                                }
                            },
                        },
                    },
                },
                {
                    "at": "2026-03-15T21:00:01+0800",
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 4242, "expected_sha256": "b" * 64},
                    "hook_result": {
                        "returncode": 0,
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "ALLOW",
                            "guard_state_name": "JOB_ACTIVE",
                            "fault_name": "NONE",
                            "transport_status": "job_ack_received",
                            "protocol_semantics": "implemented",
                        },
                    },
                },
                {
                    "at": "2026-03-15T21:00:01+0800",
                    "phase": "JOB_ACK",
                    "payload": {
                        "job_id": 4242,
                        "decision": "ALLOW",
                        "guard_state_name": "JOB_ACTIVE",
                        "fault_name": "NONE",
                    },
                },
                {
                    "at": "2026-03-15T21:00:03+0800",
                    "phase": "JOB_DONE",
                    "payload": {
                        "job_id": 4242,
                        "elapsed_ms": 2000,
                        "result_code": 0,
                        "runner_exit_code": 0,
                        "timed_out": False,
                    },
                },
            ]
            trace_path.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in trace_events) + "\n",
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps({"result": "success"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            runner_summary = {
                "variant": "baseline",
                "artifact_path": "/tmp/baseline/optimized_model.so",
                "artifact_sha256": "b" * 64,
                "artifact_sha256_expected": "b" * 64,
                "artifact_sha256_match": True,
                "output_dir": "/tmp/openamp_demo_hook/4242/inference_benchmark_baseline/reconstructions",
                "output_count": 1,
                "processed_count": 1,
                "input_count": 1,
                "available_input_count": 1,
                "load_ms": 0.0,
                "vm_init_ms": 0.0,
                "run_count": 1,
                "run_samples_ms": [12.0],
                "run_median_ms": 12.0,
                "run_mean_ms": 12.0,
                "run_min_ms": 12.0,
                "run_max_ms": 12.0,
                "run_variance_ms2": 0.0,
                "output_shape": None,
                "output_dtype": None,
                "snr": 10.0,
                "batch_size": 1,
                "save_format": "png",
                "seed": None,
                "max_inputs": 1,
                "parser": "legacy_latency_lines",
            }
            runner_log_path.write_text(
                "[2026-03-15T21:00:00+0800] openamp wrapper start\n"
                "runner_cmd=bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline --max-inputs 1\n"
                "[legacy-compat] variant=baseline script=tvm_002.py output_dir=/tmp/out snr=10 batch_size=1 max_inputs=1\n"
                "批量推理时间（1 个样本）: 0.012 秒\n"
                + json.dumps(runner_summary, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            job = LiveRemoteReconstructionJob.__new__(LiveRemoteReconstructionJob)
            job.job_id = "4242"
            job.variant = "baseline"
            job._timeout_sec = 10.0
            job._output_dir = output_dir
            job._trace_path = trace_path
            job._summary_path = summary_path
            job._runner_log_path = runner_log_path
            job._lock = Lock()
            job._final_snapshot = None

            fake_process = Mock()
            fake_process.communicate.return_value = ("", "")
            fake_process.returncode = 0
            job._process = fake_process

            job._wait_for_completion()

            snapshot = job._final_snapshot
            assert snapshot is not None
            self.assertEqual(snapshot["status"], "success")
            self.assertEqual(snapshot["execution_mode"], "live")
            self.assertEqual(snapshot["status_category"], "success")
            self.assertEqual(snapshot["runner_summary"]["parser"], "legacy_latency_lines")
            self.assertEqual(snapshot["runner_summary"]["run_median_ms"], 12.0)
            self.assertEqual(snapshot["runner_summary"]["artifact_sha256"], "b" * 64)
            self.assertEqual(snapshot["progress"]["completed_count"], 1)
            self.assertEqual(snapshot["progress"]["expected_count"], 1)
            self.assertEqual(snapshot["progress"]["count_source"], "runner_summary.processed_count")
            self.assertEqual(snapshot["progress"]["stages"][3]["status"], "done")


if __name__ == "__main__":
    unittest.main()
