#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = PROJECT_ROOT / "session_bootstrap" / "reports"
EXPECTED_MODULES = [
    "remoteproc",
    "rpmsg",
    "rpmsg_char",
    "rpmsg_ctrl",
    "virtio_rpmsg_bus",
    "rpmsg_ns",
    "mailbox",
]
EXPECTED_CONFIG_KEYS = [
    "CONFIG_REMOTEPROC",
    "CONFIG_RPMSG",
    "CONFIG_RPMSG_CHAR",
    "CONFIG_RPMSG_CTRL",
    "CONFIG_RPMSG_NS",
    "CONFIG_RPMSG_VIRTIO",
    "CONFIG_MAILBOX",
]
DEV_GLOBS = {
    "rpmsg_ctrl": "/dev/rpmsg_ctrl*",
    "rpmsg_endpoints": "/dev/rpmsg[0-9]*",
    "tty_rpmsg": "/dev/ttyRPMSG*",
}
SYSFS_PATHS = [
    "/sys/class/remoteproc",
    "/sys/bus/rpmsg",
    "/sys/class/rpmsg",
    "/sys/kernel/config",
    "/sys/module/remoteproc",
    "/sys/module/rpmsg",
    "/sys/module/rpmsg_char",
    "/sys/module/virtio_rpmsg_bus",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Linux-side OpenAMP/RPMsg/remoteproc readiness and optionally write "
            "JSON + Markdown evidence for the current host."
        )
    )
    parser.add_argument(
        "--label",
        default="local_probe",
        help="A short label written into the report, for example local_wsl or phytium_remote.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional JSON output path. Relative paths are resolved from the repo root.",
    )
    parser.add_argument(
        "--output-md",
        default="",
        help="Optional Markdown output path. Relative paths are resolved from the repo root.",
    )
    parser.add_argument(
        "--max-dmesg-lines",
        type=int,
        default=80,
        help="How many filtered dmesg lines to keep when access is allowed.",
    )
    parser.add_argument(
        "--max-path-samples",
        type=int,
        default=24,
        help="How many device/module path samples to keep per category.",
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the full JSON payload to stdout after collection.",
    )
    return parser.parse_args()


def resolve_output_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def read_text(path: Path, *, strip: bool = True) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text.strip() if strip else text


def sample_paths(pattern: str, *, limit: int) -> list[str]:
    import glob

    matches = sorted(glob.glob(pattern, recursive=True))
    return matches[:limit]


def run_command(command: list[str], *, timeout: int = 10) -> dict[str, Any]:
    if not command:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "empty command"}
    if shutil.which(command[0]) is None:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"command not found: {command[0]}",
        }
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout after {timeout}s",
        }
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def parse_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    return data


def parse_loaded_modules() -> list[str]:
    path = Path("/proc/modules")
    if not path.exists():
        return []
    modules = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if parts:
            modules.append(parts[0])
    return modules


def collect_module_inventory(limit: int) -> dict[str, Any]:
    loaded = parse_loaded_modules()
    loaded_set = set(loaded)
    matched_loaded = [name for name in loaded if any(token in name for token in EXPECTED_MODULES)]
    release = platform.release()
    module_root = Path("/lib/modules") / release
    module_globs = [
        str(module_root / "**" / "rpmsg*.ko*"),
        str(module_root / "**" / "*remoteproc*.ko*"),
        str(module_root / "**" / "*mailbox*.ko*"),
    ]
    available_paths: list[str] = []
    for pattern in module_globs:
        for path in sample_paths(pattern, limit=limit):
            if path not in available_paths:
                available_paths.append(path)
            if len(available_paths) >= limit:
                break
        if len(available_paths) >= limit:
            break
    return {
        "loaded_modules": matched_loaded,
        "expected_loaded": {name: (name in loaded_set) for name in EXPECTED_MODULES},
        "module_root_exists": module_root.exists(),
        "module_root": str(module_root),
        "available_module_paths": available_paths,
    }


def parse_kernel_config() -> dict[str, str]:
    candidates = [
        Path("/proc/config.gz"),
        Path("/boot") / f"config-{platform.release()}",
    ]
    raw = ""
    source = None
    for candidate in candidates:
        if not candidate.exists():
            continue
        source = candidate
        if candidate.suffix == ".gz":
            try:
                with gzip.open(candidate, "rt", encoding="utf-8", errors="replace") as infile:
                    raw = infile.read()
            except OSError:
                raw = ""
        else:
            raw = candidate.read_text(encoding="utf-8", errors="replace")
        if raw:
            break
    if not raw:
        return {}
    values: dict[str, str] = {"_source": str(source) if source is not None else ""}
    for key in EXPECTED_CONFIG_KEYS:
        values[key] = "missing"
    for line in raw.splitlines():
        for key in EXPECTED_CONFIG_KEYS:
            if line.startswith(f"{key}="):
                values[key] = line.split("=", 1)[1].strip()
    return values


def collect_remoteproc() -> list[dict[str, Any]]:
    base = Path("/sys/class/remoteproc")
    if not base.exists():
        return []
    entries = []
    for node in sorted(base.glob("remoteproc*")):
        entry = {
            "path": str(node),
            "name": read_text(node / "name"),
            "state": read_text(node / "state"),
            "firmware": read_text(node / "firmware"),
            "recovery": read_text(node / "recovery"),
            "coredump": read_text(node / "coredump"),
        }
        driver_link = node / "device" / "driver"
        if driver_link.exists():
            try:
                entry["driver"] = os.path.realpath(driver_link)
            except OSError:
                entry["driver"] = None
        entries.append(entry)
    return entries


def collect_rpmsg_bus(limit: int) -> list[dict[str, Any]]:
    base = Path("/sys/bus/rpmsg/devices")
    if not base.exists():
        return []
    entries = []
    for node in sorted(base.iterdir()):
        if node.name in {"drivers", "drivers_autoprobe", "uevent"}:
            continue
        if len(entries) >= limit:
            break
        entry = {
            "path": str(node),
            "name": read_text(node / "name"),
            "src": read_text(node / "src"),
            "dst": read_text(node / "dst"),
            "modalias": read_text(node / "modalias"),
        }
        driver_link = node / "driver"
        if driver_link.exists():
            try:
                entry["driver"] = os.path.realpath(driver_link)
            except OSError:
                entry["driver"] = None
        entries.append(entry)
    return entries


def collect_sysfs_summary() -> dict[str, Any]:
    summary = {}
    for raw in SYSFS_PATHS:
        path = Path(raw)
        summary[raw] = {
            "exists": path.exists(),
            "is_dir": path.is_dir(),
            "sample_children": [child.name for child in sorted(path.iterdir())[:12]] if path.is_dir() else [],
        }
    return summary


def collect_command_outputs(max_dmesg_lines: int) -> dict[str, Any]:
    command_specs = {
        "uname_a": ["uname", "-a"],
        "lsmod_filtered": ["sh", "-lc", "lsmod 2>/dev/null | grep -E 'rpmsg|remoteproc|virtio_rpmsg|mailbox|openamp' || true"],
        "dmesg_filtered": [
            "sh",
            "-lc",
            "dmesg 2>&1 | grep -Ei 'rpmsg|remoteproc|virtio_rpmsg|mailbox|openamp|virtio' | tail -n "
            + str(max_dmesg_lines),
        ],
    }
    outputs = {}
    for name, command in command_specs.items():
        outputs[name] = run_command(command)
    return outputs


def classify_readiness(data: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    findings: list[str] = []
    gaps: list[str] = []

    remoteproc_entries = data["remoteproc_entries"]
    rpmsg_entries = data["rpmsg_bus_entries"]
    dev_nodes = data["device_nodes"]
    modules = data["modules"]
    sysfs = data["sysfs"]

    if not sysfs["/sys/class/remoteproc"]["exists"]:
        findings.append("缺少 /sys/class/remoteproc，说明当前宿主机没有暴露 remoteproc 用户态入口。")
        gaps.append("remoteproc sysfs 缺失")
    elif not remoteproc_entries:
        findings.append("/sys/class/remoteproc 存在，但没有 remoteprocX 实例。")
        gaps.append("remoteproc 实例缺失")

    if not sysfs["/sys/bus/rpmsg"]["exists"]:
        findings.append("缺少 /sys/bus/rpmsg，RPMsg 总线未暴露。")
        gaps.append("rpmsg bus 缺失")
    elif not rpmsg_entries:
        findings.append("/sys/bus/rpmsg 存在，但未发现已绑定的 channel/device。")
        gaps.append("rpmsg channel 缺失")

    if not any(dev_nodes.values()):
        findings.append("未发现 /dev/rpmsg_ctrl*、/dev/rpmsg* 或 /dev/ttyRPMSG* 设备节点。")
        gaps.append("rpmsg 设备节点缺失")

    expected_loaded = modules["expected_loaded"]
    if not any(expected_loaded.values()):
        findings.append("当前内核未加载 remoteproc/rpmsg 相关模块。")
        gaps.append("相关内核模块未加载")

    dmesg_result = data["commands"]["dmesg_filtered"]
    if not dmesg_result["ok"] and dmesg_result["stderr"]:
        findings.append(f"dmesg 过滤失败或受限：{dmesg_result['stderr'].strip()}")

    if remoteproc_entries and (rpmsg_entries or any(dev_nodes.values())) and any(expected_loaded.values()):
        readiness = "ready"
    elif remoteproc_entries or rpmsg_entries or any(dev_nodes.values()) or any(expected_loaded.values()):
        readiness = "partial"
    else:
        readiness = "absent"

    return readiness, findings, gaps


def build_remote_commands() -> list[str]:
    return [
        "STAMP=\"$(date +%Y%m%d_%H%M%S)\"",
        "python3 ./session_bootstrap/scripts/audit_openamp_linux_platform.py \\",
        "  --label phytium_remote \\",
        "  --output-json \"./session_bootstrap/reports/openamp_platform_audit_phytium_${STAMP}.json\" \\",
        "  --output-md \"./session_bootstrap/reports/openamp_platform_audit_phytium_${STAMP}.md\"",
        "ls -l /dev/rpmsg* /dev/ttyRPMSG* 2>/dev/null || true",
        "lsmod | grep -E 'rpmsg|remoteproc|virtio_rpmsg|mailbox|openamp' || true",
        "for p in /sys/class/remoteproc/remoteproc*; do [ -e \"$p\" ] || continue; echo \"== $p ==\"; "
        "for f in name state firmware recovery coredump; do [ -f \"$p/$f\" ] && printf '%s=%s\\n' \"$f\" \"$(cat \"$p/$f\")\"; done; done",
        "for p in /sys/bus/rpmsg/devices/*; do [ -e \"$p\" ] || continue; basename \"$p\"; "
        "for f in name src dst modalias; do [ -f \"$p/$f\" ] && printf '  %s=%s\\n' \"$f\" \"$(cat \"$p/$f\")\"; done; done",
        "dmesg | grep -Ei 'rpmsg|remoteproc|virtio_rpmsg|mailbox|openamp|virtio' | tail -n 80",
    ]


def build_minimum_path() -> list[str]:
    return [
        "先确认 remoteproc 实例存在，并能读取 name/state/firmware；若 state=offline，再确认从核固件装载路径和启动方式。",
        "确认 RPMsg 用户态入口至少具备一项：/dev/rpmsg_ctrl*、/dev/rpmsg* 或厂商封装的 /dev/ttyRPMSG*。",
        "确认内核侧至少暴露 remoteproc + rpmsg_char/virtio_rpmsg_bus，若未自动加载则补驱动或设备树绑定。",
        "先打通 STATUS_REQ/STATUS_RESP，验证 Linux -> 从核 -> Linux 的最短控制回环，再接 JOB_REQ/JOB_ACK。",
        "最后再用独立控制面 wrapper 包裹现有 trusted current runner，只在执行前后加控制消息与心跳，不改推理数据面。",
    ]


def build_checklist() -> list[dict[str, str]]:
    return [
        {"category": "用户态入口", "item": "/dev/rpmsg_ctrl*、/dev/rpmsg*、/dev/ttyRPMSG* 是否存在且权限可读写"},
        {"category": "sysfs", "item": "/sys/class/remoteproc/remoteprocX 的 name/state/firmware/recovery/coredump"},
        {"category": "sysfs", "item": "/sys/bus/rpmsg/devices/* 的 channel 名称、src/dst、绑定 driver"},
        {"category": "内核模块", "item": "remoteproc、rpmsg、rpmsg_char、virtio_rpmsg_bus、mailbox 是否已加载"},
        {"category": "内核配置", "item": "CONFIG_REMOTEPROC / CONFIG_RPMSG / CONFIG_RPMSG_CHAR / CONFIG_RPMSG_VIRTIO"},
        {"category": "日志证据", "item": "dmesg 中是否出现 remoteproc boot、virtio rpmsg、name service、mailbox 错误"},
        {"category": "联调前置", "item": "先 STATUS_REQ/RESP，再 JOB_REQ/JOB_ACK，再 heartbeat/deadline/safe-stop"},
    ]


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 飞腾平台 OpenAMP / RPMsg Linux 侧平台审计报告")
    lines.append("")
    lines.append(f"> 生成时间：{data['generated_at']}")
    lines.append(f"> 探测标签：`{data['label']}`")
    lines.append(f"> 宿主机：`{data['host']['hostname']}` / `{data['host']['kernel_release']}` / `{data['host']['machine']}`")
    lines.append("")
    lines.append("## 1. 本次结论")
    lines.append("")
    lines.append(f"- readiness: `{data['assessment']['readiness']}`")
    lines.append(f"- 本机是否飞腾目标板：`{data['host']['looks_like_phytium_board']}`")
    for finding in data["assessment"]["findings"]:
        lines.append(f"- {finding}")
    if not data["assessment"]["findings"]:
        lines.append("- 当前探测未发现显著缺口。")
    lines.append("")
    lines.append("## 2. Linux 侧必须检查项")
    lines.append("")
    for row in data["audit_checklist"]:
        lines.append(f"- `{row['category']}`: {row['item']}")
    lines.append("")
    lines.append("## 3. 本地已验证结果")
    lines.append("")
    lines.append("### 3.1 sysfs / dev 节点")
    lines.append("")
    for raw, payload in data["sysfs"].items():
        lines.append(f"- `{raw}`: exists=`{payload['exists']}` sample_children=`{payload['sample_children']}`")
    for name, nodes in data["device_nodes"].items():
        lines.append(f"- `{name}`: {nodes if nodes else '[]'}")
    lines.append("")
    lines.append("### 3.2 remoteproc / rpmsg 实例")
    lines.append("")
    if data["remoteproc_entries"]:
        for entry in data["remoteproc_entries"]:
            lines.append(
                f"- `{entry['path']}`: name=`{entry.get('name')}` state=`{entry.get('state')}` "
                f"firmware=`{entry.get('firmware')}` recovery=`{entry.get('recovery')}`"
            )
    else:
        lines.append("- 未发现 `remoteprocX` 实例。")
    if data["rpmsg_bus_entries"]:
        for entry in data["rpmsg_bus_entries"]:
            lines.append(
                f"- `{entry['path']}`: name=`{entry.get('name')}` src=`{entry.get('src')}` "
                f"dst=`{entry.get('dst')}` driver=`{entry.get('driver')}`"
            )
    else:
        lines.append("- 未发现 `rpmsg` channel/device 实例。")
    lines.append("")
    lines.append("### 3.3 模块 / 内核配置 / 日志")
    lines.append("")
    lines.append(f"- loaded module matches: `{data['modules']['loaded_modules']}`")
    lines.append(f"- expected_loaded: `{data['modules']['expected_loaded']}`")
    lines.append(f"- module_root: `{data['modules']['module_root']}` exists=`{data['modules']['module_root_exists']}`")
    lines.append(f"- module path samples: `{data['modules']['available_module_paths']}`")
    lines.append(f"- kernel config snapshot: `{data['kernel_config']}`")
    dmesg = data["commands"]["dmesg_filtered"]
    if dmesg["stdout"].strip():
        lines.append("- dmesg 过滤摘录：")
        lines.append("")
        lines.append("```text")
        lines.append(dmesg["stdout"].strip())
        lines.append("```")
    elif dmesg["stderr"].strip():
        lines.append(f"- dmesg 过滤结果：`{dmesg['stderr'].strip()}`")
    else:
        lines.append("- dmesg 过滤结果为空。")
    lines.append("")
    lines.append("## 4. 常见缺口")
    lines.append("")
    if data["assessment"]["common_gaps"]:
        for gap in data["assessment"]["common_gaps"]:
            lines.append(f"- {gap}")
    else:
        lines.append("- 当前未自动识别出通用缺口。")
    lines.append("- 典型缺口还包括：remoteproc 固件名不匹配、device tree 未绑定 mailbox/shared-memory、rpmsg_char 未启用、从核未拉起。")
    lines.append("")
    lines.append("## 5. 最小联调路径")
    lines.append("")
    for step in data["minimum_debug_path"]:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("## 6. 远端待执行命令与预期证据路径")
    lines.append("")
    lines.append("- 当前本机不是已确认的飞腾目标板时，不伪造 RPMsg/remoteproc 结果；下面命令应在真实飞腾 Linux 侧仓库根目录执行。")
    lines.append("- 预期证据路径：`session_bootstrap/reports/openamp_platform_audit_phytium_<timestamp>.json` 和对应 `.md`。")
    lines.append("")
    lines.append("```bash")
    lines.extend(data["remote_pending_commands"])
    lines.append("```")
    lines.append("")
    lines.append("## 7. 控制面包裹边界")
    lines.append("")
    lines.append("- OpenAMP 只包裹控制面：执行授权、状态查询、心跳、deadline、安全停止、故障上报。")
    lines.append("- 现有 trusted current 数据面继续走 `run_remote_current_real_reconstruction.sh` / `current_real_reconstruction.py` / `run_inference_benchmark.sh`。")
    lines.append("- 后续 wrapper 只在 runner 前后插入 `STATUS_REQ/JOB_REQ/HEARTBEAT/JOB_DONE`，不重写推理逻辑。")
    lines.append("")
    return "\n".join(lines)


def collect(args: argparse.Namespace) -> dict[str, Any]:
    host = {
        "hostname": platform.node(),
        "kernel_release": platform.release(),
        "kernel_version": platform.version(),
        "machine": platform.machine(),
        "system": platform.system(),
        "platform": platform.platform(),
        "looks_like_phytium_board": "yes"
        if "phytium" in platform.platform().lower() or "ft-" in platform.node().lower()
        else "no",
        "os_release": parse_os_release(),
    }
    data: dict[str, Any] = {
        "generated_at": now_iso(),
        "label": args.label,
        "host": host,
        "sysfs": collect_sysfs_summary(),
        "device_nodes": {
            name: sample_paths(pattern, limit=args.max_path_samples) for name, pattern in DEV_GLOBS.items()
        },
        "remoteproc_entries": collect_remoteproc(),
        "rpmsg_bus_entries": collect_rpmsg_bus(args.max_path_samples),
        "modules": collect_module_inventory(args.max_path_samples),
        "kernel_config": parse_kernel_config(),
        "commands": collect_command_outputs(args.max_dmesg_lines),
        "audit_checklist": build_checklist(),
        "minimum_debug_path": build_minimum_path(),
        "remote_pending_commands": build_remote_commands(),
    }
    readiness, findings, gaps = classify_readiness(data)
    data["assessment"] = {
        "readiness": readiness,
        "findings": findings,
        "common_gaps": gaps,
    }
    return data


def write_outputs(payload: dict[str, Any], *, output_json: Path | None, output_md: Path | None) -> None:
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(payload) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    payload = collect(args)
    output_json = resolve_output_path(args.output_json) if args.output_json else None
    output_md = resolve_output_path(args.output_md) if args.output_md else None
    write_outputs(payload, output_json=output_json, output_md=output_md)
    if args.stdout_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = {
            "label": payload["label"],
            "readiness": payload["assessment"]["readiness"],
            "remoteproc_count": len(payload["remoteproc_entries"]),
            "rpmsg_count": len(payload["rpmsg_bus_entries"]),
            "device_node_total": sum(len(v) for v in payload["device_nodes"].values()),
            "json": str(output_json) if output_json else "",
            "md": str(output_md) if output_md else "",
        }
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
