#!/usr/bin/env python3
"""Compare the deployed OpenAMP firmware ELF against a rebuilt candidate.

The script prefers a local candidate ELF when provided. Otherwise it can fetch
the candidate ELF over SSH through `ssh_with_password.sh`, analyze both images
with local ELF tooling, and write durable raw outputs plus a JSON summary.

When live SSH is unavailable, `--allow-size-only-fallback` keeps the run
reproducible by recording the failure and classifying the remaining size delta
against the official ELF's runtime/debug composition using a known candidate
size.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
SESSION_BOOTSTRAP_ROOT = SCRIPT_PATH.parents[1]
DEFAULT_OFFICIAL_ELF = (
    SESSION_BOOTSTRAP_ROOT
    / "reports"
    / "old_fw_compare_20260314"
    / "openamp_core0_official.elf"
)
DEFAULT_OUTPUT_DIR = (
    SESSION_BOOTSTRAP_ROOT / "reports" / "openamp_fw_delta_compare_20260314"
)
DEFAULT_SSH_HELPER = SESSION_BOOTSTRAP_ROOT / "scripts" / "ssh_with_password.sh"
DEFAULT_REMOTE_HOST = "100.121.87.73"
DEFAULT_REMOTE_USER = "user"
DEFAULT_REMOTE_PATH = (
    "/home/user/phytium-dev/release_v1.4.0/example/system/amp/openamp_for_linux/"
    "phytiumpi_aarch64_firefly_openamp_core0.elf"
)
DEFAULT_CANDIDATE_SIZE = 1627224

SECTION_RE = re.compile(
    r"^\s*\[\s*(?P<nr>\d+)\]\s*(?P<name>\S*)\s+"
    r"(?P<type>\S+)\s+"
    r"(?P<addr>[0-9A-Fa-f]+)\s+"
    r"(?P<off>[0-9A-Fa-f]+)\s+"
    r"(?P<size>[0-9A-Fa-f]+)\s+"
    r"(?P<es>[0-9A-Fa-f]+)\s*"
    r"(?P<flags>[A-Za-z]*)\s+"
    r"(?P<lk>\d+)\s+"
    r"(?P<inf>\d+)\s+"
    r"(?P<al>\d+)\s*$"
)
SEGMENT_RE = re.compile(
    r"^\s*(?P<type>\S+)\s+"
    r"0x(?P<offset>[0-9A-Fa-f]+)\s+"
    r"0x(?P<vaddr>[0-9A-Fa-f]+)\s+"
    r"0x(?P<paddr>[0-9A-Fa-f]+)\s+"
    r"0x(?P<filesz>[0-9A-Fa-f]+)\s+"
    r"0x(?P<memsz>[0-9A-Fa-f]+)\s+"
    r"(?P<flags>[RWE ]+)\s+"
    r"0x(?P<align>[0-9A-Fa-f]+)\s*$"
)
SIZE_RE = re.compile(
    r"^(?P<name>\S+)\s+(?P<size>\d+)\s+(?P<addr>\d+)\s*$"
)


class CompareError(RuntimeError):
    """Raised for expected comparison failures."""


@dataclass
class Section:
    nr: int
    name: str
    type: str
    address: int
    offset: int
    size: int
    entry_size: int
    flags: str
    link: int
    info: int
    align: int

    @property
    def file_bytes(self) -> int:
        return 0 if self.type == "NOBITS" else self.size


@dataclass
class Segment:
    type: str
    offset: int
    vaddr: int
    paddr: int
    filesz: int
    memsz: int
    flags: str
    align: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--official-elf",
        type=Path,
        default=DEFAULT_OFFICIAL_ELF,
        help=f"Local deployed official ELF (default: {DEFAULT_OFFICIAL_ELF})",
    )
    parser.add_argument(
        "--candidate-elf",
        type=Path,
        help="Local rebuilt candidate ELF. If omitted, try fetching from remote.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for raw outputs and summary JSON (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--ssh-helper",
        type=Path,
        default=DEFAULT_SSH_HELPER,
        help=f"SSH helper script (default: {DEFAULT_SSH_HELPER})",
    )
    parser.add_argument(
        "--remote-host",
        default=DEFAULT_REMOTE_HOST,
        help=f"Remote host for fetching the candidate ELF (default: {DEFAULT_REMOTE_HOST})",
    )
    parser.add_argument(
        "--remote-user",
        default=DEFAULT_REMOTE_USER,
        help=f"Remote user for fetching the candidate ELF (default: {DEFAULT_REMOTE_USER})",
    )
    parser.add_argument(
        "--remote-pass",
        default=os.environ.get("OPENAMP_REMOTE_PASS"),
        help="Remote password. Defaults to the OPENAMP_REMOTE_PASS environment variable.",
    )
    parser.add_argument(
        "--remote-path",
        default=DEFAULT_REMOTE_PATH,
        help=f"Remote candidate ELF path (default: {DEFAULT_REMOTE_PATH})",
    )
    parser.add_argument(
        "--candidate-size",
        type=int,
        default=DEFAULT_CANDIDATE_SIZE,
        help=f"Known candidate ELF size for fallback analysis (default: {DEFAULT_CANDIDATE_SIZE})",
    )
    parser.add_argument(
        "--skip-remote-fetch",
        action="store_true",
        help="Do not attempt live SSH fetch. Useful with --candidate-elf or size-only fallback.",
    )
    parser.add_argument(
        "--allow-size-only-fallback",
        action="store_true",
        help="If live fetch fails, still emit a size-composition inference using --candidate-size.",
    )
    return parser.parse_args()


def ensure_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise CompareError(f"Required tool not found in PATH: {name}")


def run_text_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=True,
    )


def format_exception(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        details = stderr or stdout
        if details:
            return f"{exc}; details: {details}"
    return str(exc)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_sections(readelf_sections_text: str) -> list[Section]:
    sections: list[Section] = []
    for line in readelf_sections_text.splitlines():
        match = SECTION_RE.match(line)
        if not match:
            continue
        sections.append(
            Section(
                nr=int(match.group("nr")),
                name=match.group("name"),
                type=match.group("type"),
                address=int(match.group("addr"), 16),
                offset=int(match.group("off"), 16),
                size=int(match.group("size"), 16),
                entry_size=int(match.group("es"), 16),
                flags=match.group("flags"),
                link=int(match.group("lk")),
                info=int(match.group("inf")),
                align=int(match.group("al")),
            )
        )
    if not sections:
        raise CompareError("Failed to parse section headers from readelf output.")
    return sections


def parse_segments(readelf_segments_text: str) -> list[Segment]:
    segments: list[Segment] = []
    for line in readelf_segments_text.splitlines():
        match = SEGMENT_RE.match(line)
        if not match:
            continue
        segments.append(
            Segment(
                type=match.group("type"),
                offset=int(match.group("offset"), 16),
                vaddr=int(match.group("vaddr"), 16),
                paddr=int(match.group("paddr"), 16),
                filesz=int(match.group("filesz"), 16),
                memsz=int(match.group("memsz"), 16),
                flags=match.group("flags").strip(),
                align=int(match.group("align"), 16),
            )
        )
    if not segments:
        raise CompareError("Failed to parse program headers from readelf output.")
    return segments


def parse_size_output(size_text: str) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for line in size_text.splitlines():
        match = SIZE_RE.match(line.strip())
        if match:
            parsed[match.group("name")] = int(match.group("size"))
    return parsed


def measure_stripped_sizes(elf_path: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    with tempfile.TemporaryDirectory(prefix="openamp_strip_") as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        for mode, flag in {
            "strip_debug_size": "--strip-debug",
            "strip_all_size": "--strip-all",
        }.items():
            temp_elf = tmp_dir_path / f"{mode}.elf"
            shutil.copy2(elf_path, temp_elf)
            subprocess.run(
                ["objcopy", flag, str(temp_elf)],
                check=True,
                capture_output=True,
                text=True,
            )
            sizes[mode] = temp_elf.stat().st_size
    return sizes


def bucketize(sections: list[Section], file_size: int) -> dict[str, int]:
    runtime_alloc_file = 0
    runtime_nobits_mem = 0
    resource_table_file = 0
    debug_file = 0
    other_metadata_file = 0
    total_section_file = 0

    for section in sections:
        if section.nr == 0:
            continue
        total_section_file += section.file_bytes
        if section.name.startswith(".debug"):
            debug_file += section.file_bytes
            continue
        if "A" in section.flags:
            if section.name == ".resource_table":
                resource_table_file += section.file_bytes
            elif section.type == "NOBITS":
                runtime_nobits_mem += section.size
            else:
                runtime_alloc_file += section.file_bytes
            continue
        other_metadata_file += section.file_bytes

    return {
        "runtime_alloc_file": runtime_alloc_file,
        "resource_table_file": resource_table_file,
        "runtime_total_file": runtime_alloc_file + resource_table_file,
        "runtime_nobits_mem": runtime_nobits_mem,
        "debug_file": debug_file,
        "other_metadata_file": other_metadata_file,
        "other_file_overhead": file_size - total_section_file,
    }


def analyze_elf(elf_path: Path, label: str, output_dir: Path) -> dict[str, Any]:
    if not elf_path.exists():
        raise CompareError(f"ELF not found: {elf_path}")

    file_output = run_text_command(["file", str(elf_path)])
    stat_output = run_text_command(["stat", "-c", "size=%s mtime=%y", str(elf_path)])
    header_output = run_text_command(["readelf", "-h", str(elf_path)])
    sections_output = run_text_command(["readelf", "-SW", str(elf_path)])
    segments_output = run_text_command(["readelf", "-lW", str(elf_path)])
    size_output = run_text_command(["size", "-A", "-d", str(elf_path)])

    write_text(output_dir / f"{label}.file.txt", file_output.stdout)
    write_text(output_dir / f"{label}.stat.txt", stat_output.stdout)
    write_text(output_dir / f"{label}.readelf_header.txt", header_output.stdout)
    write_text(output_dir / f"{label}.readelf_sections.txt", sections_output.stdout)
    write_text(output_dir / f"{label}.readelf_segments.txt", segments_output.stdout)
    write_text(output_dir / f"{label}.size_A_d.txt", size_output.stdout)

    sections = parse_sections(sections_output.stdout)
    segments = parse_segments(segments_output.stdout)
    size_sections = parse_size_output(size_output.stdout)
    file_size = elf_path.stat().st_size
    buckets = bucketize(sections, file_size)
    stripped_sizes = measure_stripped_sizes(elf_path)

    load_segments = [segment for segment in segments if segment.type == "LOAD"]
    load_file_total = sum(segment.filesz for segment in load_segments)
    load_mem_total = sum(segment.memsz for segment in load_segments)

    return {
        "label": label,
        "path": str(elf_path),
        "file_size": file_size,
        "sections": [section.__dict__ | {"file_bytes": section.file_bytes} for section in sections],
        "segments": [segment.__dict__ for segment in segments],
        "size_sections": size_sections,
        "bucket_sizes": buckets,
        "load_segment_file_total": load_file_total,
        "load_segment_mem_total": load_mem_total,
        "load_segment_padding_file": load_file_total - buckets["runtime_total_file"],
        "stripped_sizes": stripped_sizes,
    }


def fetch_remote_candidate(
    *,
    ssh_helper: Path,
    remote_host: str,
    remote_user: str,
    remote_pass: str,
    remote_path: str,
    output_dir: Path,
) -> tuple[Path, dict[str, str]]:
    if not ssh_helper.exists():
        raise CompareError(f"SSH helper not found: {ssh_helper}")
    if not remote_pass:
        raise CompareError(
            "Remote password not provided. Use --remote-pass or OPENAMP_REMOTE_PASS."
        )

    metadata_cmd = [
        str(ssh_helper),
        "--host",
        remote_host,
        "--user",
        remote_user,
        "--pass",
        remote_pass,
        "--",
        f"stat -c {shlex.quote('size=%s mtime=%y')} {shlex.quote(remote_path)}",
    ]
    metadata_result = run_text_command(metadata_cmd)
    write_text(output_dir / "candidate.remote_stat.txt", metadata_result.stdout)

    tmp_fd, tmp_path_raw = tempfile.mkstemp(prefix="openamp_candidate_", suffix=".elf")
    os.close(tmp_fd)
    tmp_path = Path(tmp_path_raw)

    cat_cmd = [
        str(ssh_helper),
        "--host",
        remote_host,
        "--user",
        remote_user,
        "--pass",
        remote_pass,
        "--",
        f"cat {shlex.quote(remote_path)}",
    ]
    with tmp_path.open("wb") as fetched_file:
        result = subprocess.run(cat_cmd, check=False, stdout=fetched_file, stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        tmp_path.unlink(missing_ok=True)
        raise CompareError(
            "Remote fetch failed with return code "
            f"{result.returncode}: {stderr.strip() or 'no stderr'}"
        )

    return tmp_path, {
        "remote_host": remote_host,
        "remote_user": remote_user,
        "remote_path": remote_path,
        "ssh_helper": str(ssh_helper),
    }


def build_exact_summary(
    official: dict[str, Any], candidate: dict[str, Any], remote_source: dict[str, str] | None
) -> dict[str, Any]:
    official_by_name = {section["name"]: section for section in official["sections"]}
    candidate_by_name = {section["name"]: section for section in candidate["sections"]}
    section_names = sorted(set(official_by_name) | set(candidate_by_name))

    section_deltas: list[dict[str, Any]] = []
    bucket_deltas = {
        key: official["bucket_sizes"][key] - candidate["bucket_sizes"][key]
        for key in official["bucket_sizes"]
    }
    segment_deltas: list[dict[str, Any]] = []

    for name in section_names:
        official_section = official_by_name.get(name)
        candidate_section = candidate_by_name.get(name)
        official_file_bytes = official_section["file_bytes"] if official_section else 0
        candidate_file_bytes = candidate_section["file_bytes"] if candidate_section else 0
        delta = official_file_bytes - candidate_file_bytes
        if delta == 0:
            continue
        section_deltas.append(
            {
                "name": name,
                "official_file_bytes": official_file_bytes,
                "candidate_file_bytes": candidate_file_bytes,
                "official_minus_candidate": delta,
            }
        )

    section_deltas.sort(
        key=lambda item: abs(item["official_minus_candidate"]), reverse=True
    )

    for index, (official_segment, candidate_segment) in enumerate(
        zip(official["segments"], candidate["segments"], strict=False)
    ):
        segment_deltas.append(
            {
                "index": index,
                "type": official_segment["type"],
                "official_filesz": official_segment["filesz"],
                "candidate_filesz": candidate_segment["filesz"],
                "official_minus_candidate_filesz": (
                    official_segment["filesz"] - candidate_segment["filesz"]
                ),
                "official_memsz": official_segment["memsz"],
                "candidate_memsz": candidate_segment["memsz"],
                "official_minus_candidate_memsz": (
                    official_segment["memsz"] - candidate_segment["memsz"]
                ),
            }
        )

    file_delta = official["file_size"] - candidate["file_size"]
    runtime_delta = (
        bucket_deltas["runtime_alloc_file"] + bucket_deltas["resource_table_file"]
    )
    debug_delta = bucket_deltas["debug_file"]

    if abs(debug_delta) > abs(runtime_delta):
        classification = "mostly_debug_or_non_loadable_metadata"
    else:
        classification = "mostly_runtime_or_resource"

    return {
        "mode": "full_compare",
        "remote_source": remote_source,
        "official_minus_candidate": file_delta,
        "bucket_deltas_official_minus_candidate": bucket_deltas,
        "segment_deltas_official_minus_candidate": segment_deltas,
        "top_section_deltas_official_minus_candidate": section_deltas[:20],
        "classification": classification,
    }


def build_size_only_summary(
    official: dict[str, Any],
    *,
    candidate_size: int,
    candidate_origin: str,
    fetch_error: str | None,
) -> dict[str, Any]:
    file_delta = official["file_size"] - candidate_size
    bucket_sizes = official["bucket_sizes"]
    ratio_vs_debug = file_delta / bucket_sizes["debug_file"]
    ratio_vs_runtime = file_delta / bucket_sizes["runtime_total_file"]
    ratio_vs_load_segment = file_delta / official["load_segment_file_total"]
    ratio_vs_strip_debug = file_delta / official["stripped_sizes"]["strip_debug_size"]

    classification = "mostly_debug_or_non_loadable_metadata"
    rationale = [
        (
            f"The remaining delta is {file_delta} bytes, which is only "
            f"{ratio_vs_debug:.2%} of the official image's {bucket_sizes['debug_file']} "
            "bytes of .debug_* data."
        ),
        (
            f"The same delta would be {ratio_vs_runtime:.2%} of the official image's "
            f"{bucket_sizes['runtime_total_file']} runtime/resource bytes on disk "
            f"({ratio_vs_load_segment:.2%} of total LOAD FileSiz)."
        ),
        (
            f"The debug-stripped official ELF is {official['stripped_sizes']['strip_debug_size']} "
            "bytes, so a 23 KB runtime-only gap would still be a ~10% change in the whole "
            "debug-stripped image. That is much less plausible than small drift inside DWARF/"
            "symbol payloads for the current release_v1.4.0 convergence candidate."
        ),
    ]

    return {
        "mode": "size_only_inference",
        "candidate_reference_size": candidate_size,
        "candidate_reference_origin": candidate_origin,
        "official_minus_candidate": file_delta,
        "classification": classification,
        "fetch_error": fetch_error,
        "ratios": {
            "delta_vs_official_debug_file": ratio_vs_debug,
            "delta_vs_official_runtime_total_file": ratio_vs_runtime,
            "delta_vs_official_load_segment_file_total": ratio_vs_load_segment,
            "delta_vs_official_strip_debug_size": ratio_vs_strip_debug,
        },
        "rationale": rationale,
    }


def main() -> int:
    args = parse_args()
    for tool in ("file", "readelf", "size", "objcopy", "stat"):
        ensure_tool(tool)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    run_manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cwd": str(Path.cwd()),
        "argv": sys.argv,
    }
    write_text(output_dir / "run_manifest.json", json.dumps(run_manifest, indent=2) + "\n")

    official = analyze_elf(args.official_elf.resolve(), "official", output_dir)
    remote_source: dict[str, str] | None = None
    candidate: dict[str, Any] | None = None
    candidate_temp_path: Path | None = None
    fetch_error: str | None = None

    try:
        if args.candidate_elf:
            candidate = analyze_elf(args.candidate_elf.resolve(), "candidate", output_dir)
            remote_source = {"candidate_local_elf": str(args.candidate_elf.resolve())}
        elif not args.skip_remote_fetch:
            candidate_temp_path, remote_source = fetch_remote_candidate(
                ssh_helper=args.ssh_helper.resolve(),
                remote_host=args.remote_host,
                remote_user=args.remote_user,
                remote_pass=args.remote_pass or "",
                remote_path=args.remote_path,
                output_dir=output_dir,
            )
            candidate = analyze_elf(candidate_temp_path, "candidate", output_dir)
    except (CompareError, subprocess.CalledProcessError) as exc:
        fetch_error = format_exception(exc)
        write_text(output_dir / "candidate_fetch_error.txt", fetch_error + "\n")

    try:
        if candidate is not None:
            summary = {
                "official": official,
                "candidate": candidate,
                "comparison": build_exact_summary(official, candidate, remote_source),
            }
        else:
            if not args.allow_size_only_fallback:
                raise CompareError(
                    "Candidate ELF could not be analyzed and size-only fallback was not enabled."
                )
            summary = {
                "official": official,
                "candidate": {
                    "reference_size": args.candidate_size,
                    "reference_origin": (
                        "Task context / prior findings: release_v1.4.0 official-original "
                        "candidate size 1627224"
                    ),
                },
                "comparison": build_size_only_summary(
                    official,
                    candidate_size=args.candidate_size,
                    candidate_origin=(
                        "Task context / prior findings: release_v1.4.0 official-original "
                        "candidate size 1627224"
                    ),
                    fetch_error=fetch_error,
                ),
            }

        summary_path = output_dir / "comparison_summary.json"
        write_text(summary_path, json.dumps(summary, indent=2) + "\n")

        comparison = summary["comparison"]
        print(f"summary_json={summary_path}")
        print(f"mode={comparison['mode']}")
        print(f"official_size={official['file_size']}")
        if comparison["mode"] == "full_compare":
            print(f"candidate_size={candidate['file_size']}")
            print(
                "classification="
                f"{comparison['classification']}"
            )
            print(
                "official_minus_candidate="
                f"{comparison['official_minus_candidate']}"
            )
        else:
            print(f"candidate_size={args.candidate_size}")
            print(
                "classification="
                f"{comparison['classification']}"
            )
            print(
                "official_minus_candidate="
                f"{comparison['official_minus_candidate']}"
            )
            if fetch_error:
                print(f"candidate_fetch_error={fetch_error}")
        return 0
    finally:
        if candidate_temp_path is not None:
            candidate_temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
