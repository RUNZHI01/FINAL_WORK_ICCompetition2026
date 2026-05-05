#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TVM_SRC = PROJECT_ROOT / "tvm-src"
if not TVM_SRC.exists():
    TVM_SRC = PROJECT_ROOT.parent / "tvm-src"
SCRIPT_DIR = PROJECT_ROOT / "session_bootstrap" / "scripts"
TMP_ROOT = PROJECT_ROOT / "session_bootstrap" / "tmp"
REPORT_ROOT = PROJECT_ROOT / "session_bootstrap" / "reports"
DEFAULT_ENV = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "reports"
    / "daily_20260404_openamp_3core_big_little_followup"
    / "acl_big_little_compare.env"
)


REMOTE_TVM_BENCH_SCRIPT = textwrap.dedent(
    """
    #!/usr/bin/env python3
    import json
    import sys
    import time

    import numpy as np

    sys.path.insert(0, "/home/user/tvm_samegen_20260307/python")
    sys.path.insert(0, "/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages")
    sys.path.insert(0, "/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages")

    import tvm

    so_path, func_name, input_shape_s, weight_shape_s, bias_shape_s, output_shape_s, label = sys.argv[1:8]

    def parse_shape(value):
        return tuple(int(part) for part in value.split(","))

    def make_tensor(arr, dev):
        runtime = getattr(tvm, "runtime", None)
        if runtime is not None and hasattr(runtime, "tensor"):
            return runtime.tensor(arr, dev)
        if runtime is not None and hasattr(runtime, "ndarray"):
            return runtime.ndarray.array(arr, dev)
        return tvm.nd.array(arr, dev)

    input_shape = parse_shape(input_shape_s)
    weight_shape = parse_shape(weight_shape_s)
    bias_shape = parse_shape(bias_shape_s)
    output_shape = parse_shape(output_shape_s)

    np.random.seed(42)
    input_np = np.random.randn(*input_shape).astype("float32")
    weight_np = np.random.randn(*weight_shape).astype("float32")
    bias_np = np.random.randn(*bias_shape).astype("float32")
    output_np = np.zeros(output_shape, dtype="float32")

    dev = tvm.cpu(0)
    lib = tvm.runtime.load_module(so_path)
    func = lib[func_name]

    input_t = make_tensor(input_np, dev)
    weight_t = make_tensor(weight_np, dev)
    bias_t = make_tensor(bias_np, dev)
    output_t = make_tensor(output_np, dev)

    for _ in range(5):
        func(input_t, weight_t, bias_t, output_t)

    times_us = []
    for _ in range(30):
        t0 = time.perf_counter()
        func(input_t, weight_t, bias_t, output_t)
        t1 = time.perf_counter()
        times_us.append((t1 - t0) * 1e6)

    payload = {
        "label": label,
        "so_path": so_path,
        "func_name": func_name,
        "median_us": float(np.median(times_us)),
        "mean_us": float(np.mean(times_us)),
        "min_us": float(np.min(times_us)),
        "max_us": float(np.max(times_us)),
        "std_us": float(np.std(times_us)),
        "samples": 30,
        "input_shape": list(input_shape),
        "weight_shape": list(weight_shape),
        "bias_shape": list(bias_shape),
        "output_shape": list(output_shape),
    }
    print(json.dumps(payload))
    """
).strip()

REMOTE_TVM_BUILD_SCRIPT = textwrap.dedent(
    """
    #!/usr/bin/env python3
    import hashlib
    import json
    import pathlib
    import sys

    import tvm

    tir_path_s, func_name, out_so_s, target_json = sys.argv[1:5]
    tir_path = pathlib.Path(tir_path_s)
    out_so = pathlib.Path(out_so_s)

    module_name = f"_remote_build_{func_name}"
    namespace = {"__file__": str(tir_path), "__name__": module_name}
    module_stub = type(sys)(module_name)
    module_stub.__file__ = str(tir_path)
    sys.modules[module_name] = module_stub
    exec(compile(tir_path.read_text(encoding="utf-8"), str(tir_path), "exec"), namespace)
    ir_mod = namespace["Module"]
    func = ir_mod[func_name]
    target = tvm.target.Target(json.loads(target_json))
    runtime_module = tvm.build(func, target=target)
    out_so.parent.mkdir(parents=True, exist_ok=True)
    runtime_module.export_library(str(out_so))

    digest = hashlib.sha256()
    with out_so.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)

    print(
        json.dumps(
            {
                "func_name": func_name,
                "tir_path": str(tir_path),
                "artifact_path": str(out_so),
                "artifact_sha256": digest.hexdigest(),
                "artifact_size_bytes": out_so.stat().st_size,
                "target": str(target),
            }
        )
    )
    """
).strip()


@dataclass(frozen=True)
class HotspotSpec:
    name: str
    func_name: str
    tir_path: Path
    input_shape: tuple[int, ...]
    weight_shape: tuple[int, ...]
    bias_shape: tuple[int, ...]
    output_shape: tuple[int, ...]
    acl_case: str


HOTSPOTS: tuple[HotspotSpec, ...] = (
    HotspotSpec(
        name="fused_conv2d_transpose1_add9",
        func_name="fused_conv2d_transpose1_add9",
        tir_path=PROJECT_ROOT
        / "session_bootstrap"
        / "handwritten"
        / "fused_conv2d_transpose1_add9"
        / "fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py",
        input_shape=(1, 48, 64, 64),
        weight_shape=(48, 24, 3, 3),
        bias_shape=(1, 24, 1, 1),
        output_shape=(1, 24, 128, 128),
        acl_case="transpose1_asym",
    ),
    HotspotSpec(
        name="fused_conv2d_transpose2_add12",
        func_name="fused_conv2d_transpose2_add12",
        tir_path=PROJECT_ROOT
        / "session_bootstrap"
        / "handwritten"
        / "fused_conv2d_transpose2_add12"
        / "fused_conv2d_transpose2_add12_scheduled_form_candidate_v1_working_copy_tir.py",
        input_shape=(1, 24, 128, 128),
        weight_shape=(24, 12, 3, 3),
        bias_shape=(1, 12, 1, 1),
        output_shape=(1, 12, 256, 256),
        acl_case="transpose2_asym",
    ),
    HotspotSpec(
        name="fused_conv2d_transpose_add6",
        func_name="fused_conv2d_transpose_add6",
        tir_path=PROJECT_ROOT
        / "session_bootstrap"
        / "handwritten"
        / "fused_conv2d_transpose_add6"
        / "fused_conv2d_transpose_add6_scheduled_form_candidate_v1_working_copy_tir.py",
        input_shape=(1, 96, 32, 32),
        weight_shape=(96, 48, 3, 3),
        bias_shape=(1, 48, 1, 1),
        output_shape=(1, 48, 64, 64),
        acl_case="transpose_add6_asym",
    ),
)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_local(
    argv: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=PROJECT_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def load_env(env_path: Path) -> dict[str, str]:
    script = textwrap.dedent(
        f"""
        set -euo pipefail
        set -a
        source {shlex.quote(str(env_path))}
        set +a
        python3 - <<'PY'
        import json
        import os

        keys = [
            "REMOTE_HOST",
            "REMOTE_USER",
            "REMOTE_PASS",
            "REMOTE_SSH_PORT",
            "REMOTE_TVM_PYTHON",
            "TARGET",
        ]
        print(json.dumps({{key: os.environ.get(key, "") for key in keys}}))
        PY
        """
    )
    proc = run_local(["bash", "-lc", script])
    payload = json.loads(proc.stdout)
    missing = [key for key, value in payload.items() if key != "TARGET" and not value]
    if missing:
        raise SystemExit(f"ERROR: missing env values from {env_path}: {', '.join(missing)}")
    return {str(k): str(v) for k, v in payload.items()}


def ssh_exec(env: dict[str, str], remote_command: str, *, input_text: str | None = None) -> str:
    argv = [
        "bash",
        str(SCRIPT_DIR / "ssh_with_password.sh"),
        "--host",
        env["REMOTE_HOST"],
        "--user",
        env["REMOTE_USER"],
        "--pass",
        env["REMOTE_PASS"],
        "--port",
        env.get("REMOTE_SSH_PORT", "22") or "22",
        "--",
        remote_command,
    ]
    proc = run_local(argv, input_text=input_text)
    return proc.stdout


def remote_meta(env: dict[str, str], remote_path: str) -> dict[str, Any]:
    script = (
        "import hashlib, json, pathlib, sys\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "if not path.is_file():\n"
        "    raise SystemExit(f'ERROR: missing remote file: {path}')\n"
        "digest = hashlib.sha256()\n"
        "with path.open('rb') as infile:\n"
        "    for chunk in iter(lambda: infile.read(1024 * 1024), b''):\n"
        "        digest.update(chunk)\n"
        "print(json.dumps({'sha256': digest.hexdigest(), 'size_bytes': path.stat().st_size}))\n"
    )
    out = ssh_exec(env, f"python3 -c {shlex.quote(script)} {shlex.quote(remote_path)}")
    return json.loads(out.strip().splitlines()[-1])


def upload_text(env: dict[str, str], content: str, remote_path: str) -> dict[str, Any]:
    payload = base64.b64encode(content.encode("utf-8")).decode("ascii")
    writer = (
        "import base64, pathlib, sys\n"
        "data = base64.b64decode(sys.stdin.buffer.read())\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "path.parent.mkdir(parents=True, exist_ok=True)\n"
        "path.write_bytes(data)\n"
    )
    ssh_exec(env, f"python3 -c {shlex.quote(writer)} {shlex.quote(remote_path)}", input_text=payload)
    return remote_meta(env, remote_path)


def upload_file(env: dict[str, str], local_path: Path, remote_path: str) -> dict[str, Any]:
    payload = base64.b64encode(local_path.read_bytes()).decode("ascii")
    writer = (
        "import base64, pathlib, sys\n"
        "data = base64.b64decode(sys.stdin.buffer.read())\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "path.parent.mkdir(parents=True, exist_ok=True)\n"
        "path.write_bytes(data)\n"
    )
    ssh_exec(env, f"python3 -c {shlex.quote(writer)} {shlex.quote(remote_path)}", input_text=payload)
    meta = remote_meta(env, remote_path)
    local_sha = sha256_file(local_path)
    local_size = local_path.stat().st_size
    if meta["sha256"] != local_sha or int(meta["size_bytes"]) != local_size:
        raise SystemExit(
            f"ERROR: local/remote mismatch for {local_path}: "
            f"local_sha={local_sha} remote_sha={meta['sha256']} "
            f"local_size={local_size} remote_size={meta['size_bytes']}"
        )
    return {"local_sha256": local_sha, "local_size_bytes": local_size, **meta}


def build_standalone(
    env: dict[str, str],
    spec: HotspotSpec,
    *,
    target_config: dict[str, Any],
    remote_stage_dir: str,
) -> dict[str, Any]:
    remote_tir = f"{remote_stage_dir}/{spec.name}.tir.py"
    remote_so = f"{remote_stage_dir}/{spec.name}.so"
    remote_builder = f"{remote_stage_dir}/build_tvm_transpose_hotspot.py"
    upload_text(env, spec.tir_path.read_text(encoding="utf-8"), remote_tir)
    cmd = (
        f"cd {shlex.quote(remote_stage_dir)} && "
        f"{env['REMOTE_TVM_PYTHON']} {shlex.quote(remote_builder)} "
        f"{shlex.quote(remote_tir)} "
        f"{shlex.quote(spec.func_name)} "
        f"{shlex.quote(remote_so)} "
        f"{shlex.quote(json.dumps(target_config))}"
    )
    out = ssh_exec(env, cmd)
    payload = json.loads(out.strip().splitlines()[-1])
    payload["name"] = spec.name
    payload["local_tir_path"] = str(spec.tir_path)
    return payload


def run_remote_tvm_bench(
    env: dict[str, str],
    *,
    remote_stage_dir: str,
    remote_so: str,
    spec: HotspotSpec,
    replicates: int,
) -> dict[str, Any]:
    remote_helper = f"{remote_stage_dir}/bench_tvm_transpose_hotspot.py"
    results: list[dict[str, Any]] = []
    for idx in range(replicates):
        cmd = (
            f"cd {shlex.quote(remote_stage_dir)} && "
            f"{env['REMOTE_TVM_PYTHON']} {shlex.quote(remote_helper)} "
            f"{shlex.quote(remote_so)} "
            f"{shlex.quote(spec.func_name)} "
            f"{shlex.quote(','.join(str(v) for v in spec.input_shape))} "
            f"{shlex.quote(','.join(str(v) for v in spec.weight_shape))} "
            f"{shlex.quote(','.join(str(v) for v in spec.bias_shape))} "
            f"{shlex.quote(','.join(str(v) for v in spec.output_shape))} "
            f"{shlex.quote(f'{spec.name}_rep{idx + 1}')}"
        )
        out = ssh_exec(env, cmd)
        results.append(json.loads(out.strip().splitlines()[-1]))
    medians_ms = [entry["median_us"] / 1000.0 for entry in results]
    return {
        "replicates": results,
        "median_of_medians_ms": sorted(medians_ms)[len(medians_ms) // 2],
        "mean_of_medians_ms": sum(medians_ms) / len(medians_ms),
    }


ACL_LINE_RE = re.compile(
    r"^case=(?P<case>\S+)\s+output=(?P<output>\S+)\s+median_ms=(?P<median>[0-9.]+)\s+mean_ms=(?P<mean>[0-9.]+)"
)


def parse_acl_output(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        match = ACL_LINE_RE.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "case": match.group("case"),
                "output_shape": match.group("output"),
                "median_ms": float(match.group("median")),
                "mean_ms": float(match.group("mean")),
            }
        )
    return rows


def run_acl_bench(env: dict[str, str], *, replicates: int) -> dict[str, Any]:
    raw_runs: list[str] = []
    rows_by_case: dict[str, list[dict[str, Any]]] = {}
    for _ in range(replicates):
        raw = ssh_exec(
            env,
            "set -euo pipefail && export OMP_NUM_THREADS=3 && taskset -c 0-2 /tmp/acl_deconv_f32_bench_asym",
        )
        raw_runs.append(raw)
        for row in parse_acl_output(raw):
            rows_by_case.setdefault(row["case"], []).append(row)
    summary: dict[str, Any] = {}
    for case, rows in sorted(rows_by_case.items()):
        medians = [row["median_ms"] for row in rows]
        summary[case] = {
            "replicates": rows,
            "median_of_medians_ms": sorted(medians)[len(medians) // 2],
            "mean_of_medians_ms": sum(medians) / len(medians),
            "output_shape": rows[0]["output_shape"],
        }
    return {"raw_runs": raw_runs, "cases": summary}


def collect_board_state(env: dict[str, str]) -> dict[str, Any]:
    script = textwrap.dedent(
        """
        set -euo pipefail
        python3 - <<'PY'
        import json
        import pathlib
        import subprocess

        def read_text(path):
            p = pathlib.Path(path)
            return p.read_text(encoding="utf-8").strip() if p.exists() else None

        payload = {
            "hostname": read_text("/etc/hostname"),
            "remoteproc0_state": read_text("/sys/class/remoteproc/remoteproc0/state"),
            "cpu_online": read_text("/sys/devices/system/cpu/online"),
            "nproc": subprocess.check_output(["nproc"], text=True).strip(),
            "rpmsg0_exists": pathlib.Path("/dev/rpmsg0").exists(),
            "rpmsg_ctrl0_exists": pathlib.Path("/dev/rpmsg_ctrl0").exists(),
        }
        print(json.dumps(payload))
        PY
        """
    ).strip()
    out = ssh_exec(env, script)
    return json.loads(out.strip().splitlines()[-1])


def build_report(
    *,
    report_path: Path,
    env_path: Path,
    board_state: dict[str, Any],
    target_config: dict[str, Any],
    build_facts: dict[str, Any],
    tvm_results: dict[str, Any],
    acl_results: dict[str, Any],
) -> None:
    lines: list[str] = []
    lines.append("# OpenAMP 三核板态下 ACL vs TVM 热点单算子公平复测")
    lines.append("")
    lines.append(f"- date: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append("- scope: current graph 中 ACL 可比的三条 `conv2d_transpose` hotspot")
    lines.append(f"- env: `{env_path.relative_to(PROJECT_ROOT)}`")
    lines.append(f"- board: `{board_state.get('hostname')}`")
    lines.append(
        f"- board_state: `remoteproc0={board_state.get('remoteproc0_state')}`, "
        f"`cpu_online={board_state.get('cpu_online')}`, `nproc={board_state.get('nproc')}`"
    )
    lines.append(f"- target: `{json.dumps(target_config, ensure_ascii=False)}`")
    lines.append("- ACL bench: `/tmp/acl_deconv_f32_bench_asym` rerun on the same board state")
    lines.append("- TVM bench: accepted scheduled-form standalone `.so`, rebuilt with `num-cores=3`, remotely executed under `OMP_NUM_THREADS=3 TVM_NUM_THREADS=3`")
    lines.append("")
    lines.append("## Fairness Contract")
    lines.append("")
    lines.append("- fixed to the current OpenAMP three-core board state on `2026-04-04`")
    lines.append("- fixed to the current graph hotspot shapes `128/256/64` using ACL asymmetric padding branch")
    lines.append("- fixed TVM side to `num-cores=3` build target and three-thread runtime")
    lines.append("- repeated ACL and TVM runs three times each, then compared median-of-medians")
    lines.append("- kept the existing ACL semantic boundary explicit: current ACL binary is still `deconvolution` only, while TVM hotspot is fused `deconv + bias add`")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Hotspot | TVM standalone median-of-medians (ms) | ACL asym median-of-medians (ms) | ACL vs TVM | Current read |")
    lines.append("|---|---:|---:|---:|---|")
    for spec in HOTSPOTS:
        tvm_ms = tvm_results[spec.name]["median_of_medians_ms"]
        acl_case = acl_results["cases"][spec.acl_case]
        acl_ms = acl_case["median_of_medians_ms"]
        delta_pct = (acl_ms - tvm_ms) / tvm_ms * 100.0
        if acl_ms < tvm_ms:
            read = "ACL numerically faster"
        elif acl_ms > tvm_ms:
            read = "TVM numerically faster"
        else:
            read = "tie"
        lines.append(
            f"| `{spec.name}` | `{tvm_ms:.3f}` | `{acl_ms:.3f}` | `{delta_pct:+.2f}%` | {read} |"
        )
    lines.append("")
    lines.append("## TVM Build Facts")
    lines.append("")
    for spec in HOTSPOTS:
        fact = build_facts[spec.name]
        lines.append(
            f"- `{spec.name}`: remote `{fact['artifact_path']}`, sha256 `{fact['artifact_sha256']}`, size `{fact['artifact_size_bytes']}` bytes"
        )
    lines.append("")
    lines.append("## ACL Raw Case Medians")
    lines.append("")
    for case, summary in sorted(acl_results["cases"].items()):
        medians = [row["median_ms"] for row in summary["replicates"]]
        lines.append(
            f"- `{case}`: output `{summary['output_shape']}`, per-run medians `{', '.join(f'{value:.3f}' for value in medians)}`, "
            f"median-of-medians `{summary['median_of_medians_ms']:.3f} ms`"
        )
    lines.append("")
    lines.append("## Scope Boundary For Handwritten Final")
    lines.append("")
    lines.append("- 当前真正进入 `Handwritten final` 的 surviving handwritten 替换是 `fused_variance3_add10_tir_sqrt3` 与 `fused_mean4_subtract4_divide4_multiply4_add14_relu3`。")
    lines.append("- 这两条在当前 repo 内没有对应的 stock ACL single-op benchmark/harness，因此本次 ACL 公平单算子表不把它们硬塞成伪对等行。")
    lines.append("- 因而这份报告回答的是：在当前计算图里，ACL 真正声称可介入的三条 transpose hotspot，在三核板态下与 TVM/handwritten standalone 到底谁更快。")
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append("- `2026-04-04` 之前那句“ACL 在 `transpose_add6` standalone 上快约 `33.9%`”不再可作为正文结论直接使用，因为它混入了不同板态/线程条件。")
    lines.append("- 这一轮结果才是当前可写入口：OpenAMP 三核、当前图 shape、三线程 TVM runtime、同板状态 ACL asym branch。")
    lines.append("- 但 ACL 侧仍然保留 `deconvolution-only` 边界，所以正文里最稳的说法应该是“在公平化后的三核 hotspot A/B 下，ACL 与 TVM 的相对关系如何”，而不是直接把它写成对 fused hotspot 的最终胜负。")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    env_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_ENV
    stamp = now_stamp()
    env = load_env(env_path)
    target_config = json.loads(env.get("TARGET") or "")
    board_state = collect_board_state(env)
    remote_stage_dir = f"/home/user/Downloads/jscc-test/acl_ab/fair_acl_tvm_hotspot_ab_{stamp}"
    ssh_exec(env, f"mkdir -p {shlex.quote(remote_stage_dir)}")

    bench_helper_path = f"{remote_stage_dir}/bench_tvm_transpose_hotspot.py"
    build_helper_path = f"{remote_stage_dir}/build_tvm_transpose_hotspot.py"
    upload_text(env, REMOTE_TVM_BENCH_SCRIPT + "\n", bench_helper_path)
    upload_text(env, REMOTE_TVM_BUILD_SCRIPT + "\n", build_helper_path)

    build_facts: dict[str, Any] = {}
    tvm_results: dict[str, Any] = {}
    for spec in HOTSPOTS:
        fact = build_standalone(
            env,
            spec,
            target_config=target_config,
            remote_stage_dir=remote_stage_dir,
        )
        build_facts[spec.name] = fact
        tvm_results[spec.name] = run_remote_tvm_bench(
            env,
            remote_stage_dir=remote_stage_dir,
            remote_so=fact["artifact_path"],
            spec=spec,
            replicates=3,
        )

    acl_results = run_acl_bench(env, replicates=3)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "env_path": str(env_path),
        "board_state": board_state,
        "target": target_config,
        "remote_stage_dir": remote_stage_dir,
        "build_facts": build_facts,
        "tvm_results": tvm_results,
        "acl_results": acl_results,
    }
    json_path = REPORT_ROOT / f"fair_acl_tvm_hotspot_ab_openamp3_{stamp}.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = REPORT_ROOT / f"fair_acl_tvm_hotspot_ab_openamp3_{stamp}.md"
    build_report(
        report_path=md_path,
        env_path=env_path,
        board_state=board_state,
        target_config=target_config,
        build_facts=build_facts,
        tvm_results=tvm_results,
        acl_results=acl_results,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "json_report": str(json_path),
                "md_report": str(md_path),
                "remote_stage_dir": remote_stage_dir,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
