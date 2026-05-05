#!/usr/bin/env python3
"""
generate_fit_report.py — FIT 测试报告自动生成

运行所有 FIT 测试并生成统一的覆盖率矩阵 Markdown 报告。

用法:
  python scripts/generate_fit_report.py
  python scripts/generate_fit_report.py --output custom/path.md
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone


# ── 风险矩阵映射 ──

RISK_MATRIX = {
    "R1": {"desc": "未知 artifact 执行", "fit_ids": ["S-FIT-03"]},
    "R2": {"desc": "不安全降级", "fit_ids": ["S-FIT-04"]},
    "R3": {"desc": "数据链路窃听/篡改", "fit_ids": ["S-FIT-01", "S-FIT-02"]},
    "R4": {"desc": "输入契约违反", "fit_ids": ["S-FIT-02"]},
    "R5": {"desc": "主控核心无响应", "fit_ids": ["S-FIT-05"]},
    "R6": {"desc": "输出异常/不可追溯", "fit_ids": ["S-FIT-06"]},
    "R7": {"desc": "重放攻击", "fit_ids": ["S-FIT-07"]},
}

PROTOCOL_FIT = {
    "FIT-P04": {"desc": "控制帧 CRC 篡改"},
    "FIT-P05": {"desc": "不完整结果检测"},
    "FIT-P06": {"desc": "非法参数范围"},
}

EXTRA_FIT = {
    "S-FIT-WN": {"desc": "弱网络环境安全信道完整性"},
}


def _run_pytest(test_paths, extra_args=None):
    """运行 pytest 并返回 (exit_code, output)"""
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + test_paths
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode, result.stdout + result.stderr


def _parse_pytest_output(output):
    """解析 pytest -v 输出，返回 {test_id: result} 字典"""
    results = {}
    for line in output.split("\n"):
        line = line.strip()
        for status in ("PASSED", "FAILED", "SKIPPED", "ERROR"):
            if f" {status} " in line or line.endswith(f" {status}"):
                parts = line.split()
                for p in parts:
                    if "::" in p:
                        results[p] = status
                        break
    return results


def _generate_report(fit_results, extra_results=None):
    """生成 Markdown 覆盖率报告"""
    now = datetime.now(tz=timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M UTC")

    lines = []
    lines.append(f"# FIT 故障注入测试覆盖率报告")
    lines.append(f"\n> 生成时间: {date_str} {time_str}")
    lines.append(f"\n---")
    lines.append("")

    all_results = {**fit_results, **(extra_results or {})}
    total = len(all_results)
    passed = sum(1 for v in all_results.values() if v == "PASSED")
    failed = sum(1 for v in all_results.values() if v == "FAILED")
    skipped = sum(1 for v in all_results.values() if v == "SKIPPED")
    errored = sum(1 for v in all_results.values() if v == "ERROR")

    lines.append("## 总览")
    lines.append("")
    lines.append("| 指标 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| 总测试数 | {total} |")
    lines.append(f"| 通过 | {passed} |")
    lines.append(f"| 跳过（无后端） | {skipped} |")
    lines.append(f"| 失败 | {failed} |")
    lines.append(f"| 错误 | {errored} |")
    lines.append("")

    lines.append("## 风险矩阵覆盖率 (R1-R7)")
    lines.append("")
    lines.append("| 风险项 | 描述 | FIT 用例 | 状态 |")
    lines.append("|--------|------|----------|------|")
    for risk_id, info in RISK_MATRIX.items():
        fit_ids = info["fit_ids"]
        status_parts = []
        for fid in fit_ids:
            # 匹配类名中包含 FIT ID 的测试（如 TestSFIT01CiphertextTamperingInChannel）
            class_matches = []
            for k, v in all_results.items():
                parts = k.split("::")
                if len(parts) >= 2 and fid.replace("-", "").lower() in parts[1].lower():
                    class_matches.append(f"{v}")
            if class_matches:
                # 统计该类下所有测试的结果
                status_parts.append(f"{len(class_matches)} passed" if all(m == "PASSED" for m in class_matches) else f"mixed")
            else:
                status_parts.append("N/A")
        status_str = ", ".join(status_parts) if status_parts else "N/A"
        lines.append(f"| {risk_id} | {info['desc']} | {', '.join(fit_ids)} | {status_str} |")
    lines.append("")

    lines.append("## 协议级 FIT (OpenAMP)")
    lines.append("")
    lines.append("| FIT ID | 描述 | 状态 |")
    lines.append("|--------|------|------|")
    for fit_id, info in PROTOCOL_FIT.items():
        matching = [
            f"{v}"
            for k, v in all_results.items()
            if fit_id.lower().replace("-", "") in k.lower()
        ]
        status_str = ", ".join(matching) if matching else "N/A"
        lines.append(f"| {fit_id} | {info['desc']} | {status_str} |")
    lines.append("")

    lines.append("## 弱网环境 FIT")
    lines.append("")
    lines.append("| FIT ID | 描述 | 状态 |")
    lines.append("|--------|------|------|")
    for fit_id, info in EXTRA_FIT.items():
        matching = [
            f"{v}"
            for k, v in all_results.items()
            if fit_id.lower().replace("-", "") in k.lower()
        ]
        status_str = ", ".join(matching) if matching else "N/A"
        lines.append(f"| {fit_id} | {info['desc']} | {status_str} |")
    lines.append("")

    lines.append("## 详细结果")
    lines.append("")
    lines.append("| 测试 | 状态 |")
    lines.append("|------|------|")
    for test_id, status in sorted(all_results.items()):
        icon = {"PASSED": "PASS", "FAILED": "FAIL", "SKIPPED": "SKIP", "ERROR": "ERR"}.get(status, status)
        lines.append(f"| `{test_id}` | {icon} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="FIT 测试报告自动生成")
    parser.add_argument("--output", default="", help="输出文件路径")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("运行系统级 FIT 测试...")
    _, fit_output = _run_pytest([
        os.path.join(project_root, "scripts", "test_fit.py"),
        os.path.join(project_root, "scripts", "test_system_fit.py"),
    ])
    fit_results = _parse_pytest_output(fit_output)

    print("运行 OpenAMP 协议级 FIT...")
    _, proto_output = _run_pytest([
        os.path.join(project_root, "Semantic-Communication", "openamp_mock", "tests", "test_protocol_fit.py"),
    ])
    proto_results = _parse_pytest_output(proto_output)

    all_extra = {**proto_results}
    _, wn_output = _run_pytest([
        os.path.join(project_root, "scripts", "test_weak_network.py"),
        "-k", "test_weak_network_results_schema",
    ])
    wn_results = _parse_pytest_output(wn_output)
    all_extra.update(wn_results)

    report = _generate_report(fit_results, all_extra)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n报告已写入: {args.output}")
    else:
        print(report)

    return 0 if all(v in ("PASSED", "SKIPPED") for v in {**fit_results, **all_extra}.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
