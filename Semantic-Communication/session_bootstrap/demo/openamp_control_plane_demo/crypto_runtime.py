from __future__ import annotations

import io
import json
import os
import queue
import select
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from shlex import quote as shlex_quote
import shutil
import stat
import tempfile
from typing import Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CRYPTO_PORT = 9527
DEFAULT_STATUS_PORT = 8080
DEFAULT_OUTPUT_DIR = "/tmp/mlkem_recv"
DEFAULT_LOG_PATH = "/tmp/tcp_server.log"
DEFAULT_CIPHER_SUITE = "SM4_GCM"

LOCAL_REPO_ROOT_KEYS = ("MLKEM_LOCAL_REPO_ROOT", "MLKEM_REPO_ROOT", "COCKPIT_REPO_ROOT")
LOCAL_SCRIPT_ROOT_KEYS = ("MLKEM_SCRIPT_ROOT",)
LOCAL_CLIENT_SCRIPT_KEYS = ("MLKEM_CLIENT_SCRIPT", "MLKEM_TCP_CLIENT_SCRIPT")
LOCAL_SERVER_SCRIPT_KEYS = ("MLKEM_SERVER_SCRIPT", "MLKEM_TCP_SERVER_SCRIPT")
OQS_INSTALL_KEYS = ("OQS_INSTALL_PATH", "MLKEM_OQS_INSTALL_PATH", "MLKEM_LIBOQS_ROOT")
LOCAL_TONGSUO_BRIDGE_KEYS = ("MLKEM_LOCAL_TONGSUO_KEM_BRIDGE", "TONGSUO_KEM_BRIDGE")
LOCAL_TONGSUO_SIG_BRIDGE_KEYS = ("MLKEM_LOCAL_TONGSUO_SIG_BRIDGE", "TONGSUO_SIG_BRIDGE")
LOCAL_LD_LIBRARY_KEYS = ("MLKEM_LOCAL_LD_LIBRARY_PATH",)

REMOTE_PROJECT_ROOT_KEYS = ("MLKEM_REMOTE_PROJECT_ROOT", "OPENAMP_REMOTE_PROJECT_ROOT")
LEGACY_REMOTE_PROJECT_ROOT_KEYS = ("REMOTE_PROJECT_ROOT",)
REMOTE_SERVER_SCRIPT_KEYS = ("MLKEM_REMOTE_SERVER_SCRIPT", "MLKEM_REMOTE_TCP_SERVER_SCRIPT")
REMOTE_STARTUP_CMD_KEYS = ("MLKEM_REMOTE_STARTUP_CMD",)
REMOTE_ACTIVATE_KEYS = ("MLKEM_REMOTE_ACTIVATE",)
REMOTE_CONDA_SH_KEYS = ("MLKEM_REMOTE_CONDA_SH",)
REMOTE_CONDA_ENV_KEYS = ("MLKEM_REMOTE_CONDA_ENV",)
REMOTE_LD_LIBRARY_KEYS = ("MLKEM_REMOTE_LD_LIBRARY_PATH",)
REMOTE_OQS_INSTALL_KEYS = ("MLKEM_REMOTE_OQS_INSTALL_PATH",)
REMOTE_TONGSUO_BRIDGE_KEYS = ("MLKEM_REMOTE_TONGSUO_KEM_BRIDGE",)
REMOTE_TONGSUO_SIG_BRIDGE_KEYS = ("MLKEM_REMOTE_TONGSUO_SIG_BRIDGE",)
REMOTE_PRELUDE_KEYS = ("MLKEM_REMOTE_PRELUDE", "MLKEM_REMOTE_EXTRA_ENV")
REMOTE_PYTHON_KEYS = ("MLKEM_REMOTE_PYTHON",)
REMOTE_ARTIFACT_KEYS = ("REMOTE_CURRENT_ARTIFACT",)
REMOTE_TVM_PYTHON_KEYS = ("REMOTE_TVM_PYTHON", "REMOTE_TVM310_PYTHON")
REMOTE_TVM_ENABLE_KEYS = ("MLKEM_ENABLE_TVM", "MLKEM_REMOTE_ENABLE_TVM")
REMOTE_PORT_KEYS = ("MLKEM_PORT", "MLKEM_SERVER_PORT", "MLKEM_DATA_PORT", "MLKEM_TCP_PORT")
STATUS_PORT_KEYS = ("MLKEM_STATUS_PORT", "MLKEM_REMOTE_STATUS_PORT")
SUITE_KEYS = ("MLKEM_CIPHER_SUITE", "MLKEM_SUITE")
TRANSPORT_MODE_KEYS = ("MLKEM_TRANSPORT_MODE", "MLKEM_DATA_TRANSPORT", "MLKEM_TRANSPORT")
REMOTE_OUTPUT_DIR_KEYS = ("MLKEM_OUTPUT_DIR",)
REMOTE_LOG_PATH_KEYS = ("MLKEM_REMOTE_LOG_PATH",)
REMOTE_RUN_LOGGER_DIR_KEYS = ("MLKEM_REMOTE_RUN_LOGGER_DIR", "RUN_LOGGER_DIR")
REMOTE_SNR_KEYS = ("MLKEM_SNR", "REMOTE_SNR_CURRENT")

LOCAL_PYTHON_KEYS = ("COCKPIT_PYTHON", "PYTHON")
AUTH_COMMON_KEYS = ("MLKEM_AUTH_ENABLED", "MLKEM_AUTH_SERVER_ID", "MLKEM_AUTH_SIG_POLICY")
LOCAL_AUTH_CLIENT_KEYS = ("MLKEM_AUTH_PEER_SM2_PUB", "MLKEM_AUTH_PEER_MLDSA_PUB")
REMOTE_AUTH_SERVER_KEYS = (
    "MLKEM_AUTH_SERVER_SM2_KEY",
    "MLKEM_AUTH_SERVER_SM2_PUB",
    "MLKEM_AUTH_SERVER_MLDSA_KEY",
    "MLKEM_AUTH_SERVER_MLDSA_PUB",
)

_LOCAL_CRYPTO_CLIENT_CAP_CACHE: dict[Path, dict[str, bool]] = {}
_LOCAL_CRYPTO_SERVER_CAP_CACHE: dict[Path, dict[str, bool]] = {}


def _sources(env_values: Mapping[str, str] | None) -> tuple[Mapping[str, str], Mapping[str, str]]:
    return env_values or {}, os.environ


def first_config_value(
    env_values: Mapping[str, str] | None,
    *,
    keys: Sequence[str],
    default: str = "",
) -> str:
    for mapping in _sources(env_values):
        for key in keys:
            value = str(mapping.get(key, "")).strip()
            if value:
                return value
    return default


def parse_int_config(raw_value: str, default: int) -> int:
    value = str(raw_value or "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def parse_bool_config(raw_value: str, default: bool) -> bool:
    value = str(raw_value or "").strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def local_crypto_transport_mode(env_values: Mapping[str, str] | None) -> str:
    raw_value = first_config_value(env_values, keys=TRANSPORT_MODE_KEYS, default="tcp")
    normalized = str(raw_value or "").strip().lower()
    if normalized in {"usrp", "ota", "wireless"}:
        return "usrp"
    return "tcp"


def local_control_transport_mode(env_values: Mapping[str, str] | None) -> str:
    """控制/认证面当前固定走 TCP/Tailscale。"""
    del env_values
    return "tcp"


def _resolve_existing_path(raw_path: str, *, base_dir: Path | None = None) -> Path | None:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        seed_dir = base_dir or PROJECT_ROOT
        candidate = (seed_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()
    try:
        exists = candidate.exists()
    except OSError:
        exists = False
    if exists:
        return candidate
    return None


def _append_unique(paths: list[Path], seen: set[Path], candidate: Path | None) -> None:
    if candidate is None:
        return
    resolved = candidate.resolve()
    if resolved in seen:
        return
    seen.add(resolved)
    paths.append(resolved)


def _candidate_base_dirs(
    env_values: Mapping[str, str] | None,
    *,
    extra_roots: Sequence[Path | str] = (),
) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()

    for mapping in _sources(env_values):
        for key in (*LOCAL_REPO_ROOT_KEYS, *LOCAL_SCRIPT_ROOT_KEYS):
            raw_value = str(mapping.get(key, "")).strip()
            if not raw_value:
                continue
            _append_unique(paths, seen, _resolve_existing_path(raw_value))

    for raw_root in extra_roots:
        _append_unique(paths, seen, _resolve_existing_path(str(raw_root)))

    for default_root in (PROJECT_ROOT, Path.cwd(), PROJECT_ROOT.parent, Path.cwd().parent):
        try:
            exists = default_root.exists()
        except OSError:
            exists = False
        if exists:
            _append_unique(paths, seen, default_root)

    return paths


def resolve_local_asset(
    relative_path: str,
    *,
    env_values: Mapping[str, str] | None = None,
    explicit_path_keys: Sequence[str] = (),
    explicit_root_keys: Sequence[str] = (),
    extra_roots: Sequence[Path | str] = (),
) -> tuple[Path | None, list[Path]]:
    searched: list[Path] = []
    seen: set[Path] = set()
    relative = Path(relative_path)

    for mapping in _sources(env_values):
        for key in explicit_path_keys:
            raw_value = str(mapping.get(key, "")).strip()
            if not raw_value:
                continue
            candidate = _resolve_existing_path(raw_value)
            _append_unique(searched, seen, candidate or (PROJECT_ROOT / raw_value).resolve())
            if candidate is not None:
                return candidate, searched
        for key in explicit_root_keys:
            raw_value = str(mapping.get(key, "")).strip()
            if not raw_value:
                continue
            root = _resolve_existing_path(raw_value)
            if root is None:
                unresolved = (PROJECT_ROOT / raw_value).resolve()
                _append_unique(searched, seen, unresolved / relative)
                continue
            candidate = root / relative
            _append_unique(searched, seen, candidate)
            try:
                exists = candidate.exists()
            except OSError:
                exists = False
            if exists:
                return candidate.resolve(), searched

    base_dirs = _candidate_base_dirs(env_values, extra_roots=extra_roots)
    for root in base_dirs:
        candidate = root / relative
        _append_unique(searched, seen, candidate)
        try:
            exists = candidate.exists()
        except OSError:
            exists = False
        if exists:
            return candidate.resolve(), searched

    sibling_parents = [root.parent for root in base_dirs if root.parent.exists()]
    sibling_parent_seen: set[Path] = set()
    for sibling_parent in sibling_parents:
        resolved_parent = sibling_parent.resolve()
        if resolved_parent in sibling_parent_seen:
            continue
        sibling_parent_seen.add(resolved_parent)
        try:
            children = sorted(path for path in resolved_parent.iterdir() if path.is_dir())
        except OSError:
            continue
        for child in children:
            candidate = child / relative
            _append_unique(searched, seen, candidate)
            try:
                exists = candidate.exists()
            except OSError:
                exists = False
            if exists:
                return candidate.resolve(), searched

    return None, searched


def resolve_local_crypto_client(
    env_values: Mapping[str, str] | None = None,
    *,
    extra_roots: Sequence[Path | str] = (),
) -> tuple[Path | None, list[Path]]:
    explicit_locator = False
    for mapping in _sources(env_values):
        for key in (*LOCAL_CLIENT_SCRIPT_KEYS, *LOCAL_REPO_ROOT_KEYS, *LOCAL_SCRIPT_ROOT_KEYS):
            if str(mapping.get(key, "")).strip():
                explicit_locator = True
                break
        if explicit_locator:
            break

    runtime_root, _ = resolve_local_mlkem_runtime_root(env_values, extra_roots=extra_roots)
    prioritized_roots: tuple[Path | str, ...] = (
        ((runtime_root,) + tuple(extra_roots)) if runtime_root is not None else tuple(extra_roots)
    )
    if explicit_locator:
        return resolve_local_asset(
            "scripts/tcp_client.py",
            env_values=env_values,
            explicit_path_keys=LOCAL_CLIENT_SCRIPT_KEYS,
            explicit_root_keys=(*LOCAL_REPO_ROOT_KEYS, *LOCAL_SCRIPT_ROOT_KEYS),
            extra_roots=prioritized_roots,
        )

    searched: list[Path] = []
    seen: set[Path] = set()
    candidates: list[Path] = []

    for root in (
        PROJECT_ROOT,
        Path.cwd(),
        runtime_root,
        *tuple(extra_roots),
    ):
        if root is None:
            continue
        candidate = _resolve_existing_path(str(Path(root) / "scripts" / "tcp_client.py"))
        _append_unique(searched, seen, candidate)
        if candidate is not None:
            candidates.append(candidate.resolve())

    if candidates:
        project_root_resolved = PROJECT_ROOT.resolve()

        def _score(candidate: Path) -> tuple[int, int, int, int, int]:
            capabilities = inspect_local_crypto_client_capabilities(candidate)
            try:
                candidate_root = candidate.parents[1].resolve()
            except OSError:
                candidate_root = candidate.parents[1]
            return (
                1 if capabilities.get("supports_daemon") else 0,
                1 if capabilities.get("supports_batch_summary") else 0,
                1 if capabilities.get("supports_expect_result") else 0,
                1 if capabilities.get("supports_output") else 0,
                1 if candidate_root == project_root_resolved else 0,
            )

        best = max(candidates, key=_score)
        return best, searched

    return resolve_local_asset(
        "scripts/tcp_client.py",
        env_values=env_values,
        explicit_path_keys=LOCAL_CLIENT_SCRIPT_KEYS,
        explicit_root_keys=(*LOCAL_REPO_ROOT_KEYS, *LOCAL_SCRIPT_ROOT_KEYS),
        extra_roots=prioritized_roots,
    )


def resolve_local_crypto_server(
    env_values: Mapping[str, str] | None = None,
    *,
    extra_roots: Sequence[Path | str] = (),
) -> tuple[Path | None, list[Path]]:
    runtime_root, _ = resolve_local_mlkem_runtime_root(env_values, extra_roots=extra_roots)
    prioritized_roots: tuple[Path | str, ...] = (
        ((runtime_root,) + tuple(extra_roots)) if runtime_root is not None else tuple(extra_roots)
    )
    return resolve_local_asset(
        "scripts/tcp_server.py",
        env_values=env_values,
        explicit_path_keys=LOCAL_SERVER_SCRIPT_KEYS,
        explicit_root_keys=(*LOCAL_REPO_ROOT_KEYS, *LOCAL_SCRIPT_ROOT_KEYS),
        extra_roots=prioritized_roots,
    )


def inspect_local_crypto_client_capabilities(client_script: Path) -> dict[str, bool]:
    """Best-effort feature detection for locally discovered tcp_client.py.

    We may discover different client generations across machines. The newer demo
    path expects `--daemon`, `--count`, and `--json-summary`, while the older
    single-shot client only supports `--input` / `--output`. Detect features from
    the checked-in script text so we can choose a compatible execution path
    without assuming a specific external repo revision.
    """
    resolved = client_script.resolve()
    cached = _LOCAL_CRYPTO_CLIENT_CAP_CACHE.get(resolved)
    if cached is not None:
        return dict(cached)

    try:
        script_text = resolved.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        script_text = ""

    capabilities = {
        "supports_daemon": "--daemon" in script_text,
        "supports_count": "--count" in script_text,
        "supports_json_summary": "--json-summary" in script_text,
        "supports_output": "--output" in script_text,
        "supports_expect_result": "--expect-result" in script_text,
    }
    capabilities["supports_batch_summary"] = (
        capabilities["supports_count"] and capabilities["supports_json_summary"]
    )
    capabilities["legacy_single_input_only"] = not capabilities["supports_batch_summary"]

    _LOCAL_CRYPTO_CLIENT_CAP_CACHE[resolved] = dict(capabilities)
    return dict(capabilities)


def inspect_local_crypto_server_capabilities(server_script: Path) -> dict[str, bool]:
    resolved = server_script.resolve()
    cached = _LOCAL_CRYPTO_SERVER_CAP_CACHE.get(resolved)
    if cached is not None:
        return dict(cached)

    try:
        script_text = resolved.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        capabilities = {"supports_status_port": True}
        _LOCAL_CRYPTO_SERVER_CAP_CACHE[resolved] = dict(capabilities)
        return dict(capabilities)

    capabilities = {
        "supports_status_port": "--status-port" in script_text,
    }
    _LOCAL_CRYPTO_SERVER_CAP_CACHE[resolved] = dict(capabilities)
    return dict(capabilities)


def resolve_local_oqs_install(
    env_values: Mapping[str, str] | None = None,
    *,
    extra_roots: Sequence[Path | str] = (),
) -> tuple[Path | None, list[Path]]:
    resolved, searched = resolve_local_asset(
        "liboqs-dist",
        env_values=env_values,
        explicit_path_keys=OQS_INSTALL_KEYS,
        explicit_root_keys=(*LOCAL_REPO_ROOT_KEYS, *LOCAL_SCRIPT_ROOT_KEYS),
        extra_roots=extra_roots,
    )
    if resolved is not None:
        return resolved, searched

    for base_dir in _candidate_base_dirs(env_values, extra_roots=extra_roots):
        candidate = base_dir / "liboqs" / "liboqs-dist"
        searched.append(candidate)
        if _path_exists(candidate):
            return candidate.resolve(), searched
    return None, searched


def resolve_local_mlkem_runtime_root(
    env_values: Mapping[str, str] | None = None,
    *,
    extra_roots: Sequence[Path | str] = (),
) -> tuple[Path | None, list[Path]]:
    searched: list[Path] = []
    seen: set[Path] = set()

    for base_dir in _candidate_base_dirs(env_values, extra_roots=extra_roots):
        candidate_dirs: list[Path] = [base_dir]

        for sibling_name in ("ICCompetition2026", "mlkem_link", "mlkem"):
            candidate_dirs.append(base_dir / sibling_name)
            candidate_dirs.append(base_dir.parent / sibling_name)

        try:
            for child in base_dir.parent.iterdir():
                candidate_dirs.append(child)
        except OSError:
            pass

        for candidate_dir in candidate_dirs:
            resolved = _resolve_existing_path(str(candidate_dir))
            _append_unique(searched, seen, resolved)
            if resolved is None or not resolved.is_dir():
                continue
            try:
                has_runtime = (resolved / "mlkem_link").is_dir()
            except OSError:
                has_runtime = False
            if has_runtime:
                return resolved, searched

    return None, searched


def _prepend_env_path(env: dict[str, str], key: str, path_value: str) -> None:
    value = str(path_value or "").strip()
    if not value:
        return

    existing = [segment for segment in str(env.get(key, "")).split(os.pathsep) if segment]
    if value in existing:
        return
    env[key] = os.pathsep.join([value, *existing]) if existing else value


def _config_env_pairs(
    env_values: Mapping[str, str] | None,
    keys: Sequence[str],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for mapping in _sources(env_values):
        for key in keys:
            if key in seen or key not in mapping:
                continue
            value = str(mapping.get(key, "")).strip()
            if not value:
                continue
            pairs.append((key, value))
            seen.add(key)
    return pairs


def _detect_local_python_command(
    env_values: Mapping[str, str] | None,
    *,
    runtime_root: Path | None,
) -> str:
    explicit = first_config_value(env_values, keys=LOCAL_PYTHON_KEYS, default="")
    if explicit:
        return explicit

    if runtime_root is not None:
        detected = runtime_root / ".venv" / "bin" / "python"
        if detected.exists():
            return str(detected)

    return sys.executable or "python3"


def _detect_local_tongsuo_bridge(runtime_root: Path | None) -> Path | None:
    if runtime_root is None:
        return None

    candidates = (
        runtime_root / "tongsuo-dist" / "tongsuo" / "lib" / "libtongsuo_kem_bridge.so",
        runtime_root / "tongsuo-dist" / "lib64" / "libtongsuo_kem_bridge.so",
        runtime_root / "tongsuo-dist" / "lib" / "libtongsuo_kem_bridge.so",
    )
    for candidate in candidates:
        try:
            exists = candidate.exists()
        except OSError:
            exists = False
        if exists:
            return candidate.resolve()
    return None


def _detect_local_tongsuo_sig_bridge(runtime_root: Path | None) -> Path | None:
    if runtime_root is None:
        return None

    candidates = (
        runtime_root / "tongsuo-dist" / "tongsuo" / "lib" / "libtongsuo_sig_bridge.so",
        runtime_root / "tongsuo-dist" / "lib64" / "libtongsuo_sig_bridge.so",
        runtime_root / "tongsuo-dist" / "lib" / "libtongsuo_sig_bridge.so",
    )
    for candidate in candidates:
        try:
            exists = candidate.exists()
        except OSError:
            exists = False
        if exists:
            return candidate.resolve()
    return None


def _build_local_crypto_env(
    env_values: Mapping[str, str] | None,
    *,
    client_script: Path,
    runtime_root: Path | None,
) -> dict[str, str]:
    env = dict(os.environ)

    if runtime_root is not None and (runtime_root / "mlkem_link").is_dir():
        _prepend_env_path(env, "PYTHONPATH", str(runtime_root))

    oqs_install = first_config_value(env_values, keys=OQS_INSTALL_KEYS)
    if oqs_install:
        env["OQS_INSTALL_PATH"] = oqs_install
    else:
        extra_roots: list[Path] = [client_script.parent.parent]
        if runtime_root is not None:
            extra_roots.append(runtime_root)
        detected_oqs_root, _ = resolve_local_oqs_install(env_values, extra_roots=tuple(extra_roots))
        if detected_oqs_root is not None:
            env["OQS_INSTALL_PATH"] = str(detected_oqs_root)

    bridge_value = first_config_value(env_values, keys=LOCAL_TONGSUO_BRIDGE_KEYS, default="")
    bridge_path: Path | None = None
    if bridge_value:
        bridge_path = _resolve_existing_path(bridge_value)
    if bridge_path is None:
        bridge_path = _detect_local_tongsuo_bridge(runtime_root)
    if bridge_path is not None:
        env["TONGSUO_KEM_BRIDGE"] = str(bridge_path)

    sig_bridge_value = first_config_value(env_values, keys=LOCAL_TONGSUO_SIG_BRIDGE_KEYS, default="")
    sig_bridge_path: Path | None = None
    if sig_bridge_value:
        sig_bridge_path = _resolve_existing_path(sig_bridge_value)
    if sig_bridge_path is None:
        sig_bridge_path = _detect_local_tongsuo_sig_bridge(runtime_root)
    if sig_bridge_path is not None:
        env["TONGSUO_SIG_BRIDGE"] = str(sig_bridge_path)

    explicit_local_ld = first_config_value(env_values, keys=LOCAL_LD_LIBRARY_KEYS, default="")
    if explicit_local_ld:
        for segment in reversed([item for item in explicit_local_ld.split(os.pathsep) if item]):
            _prepend_env_path(env, "LD_LIBRARY_PATH", segment)
    elif bridge_path is not None:
        _prepend_env_path(env, "LD_LIBRARY_PATH", str(bridge_path.parent))
    elif sig_bridge_path is not None:
        _prepend_env_path(env, "LD_LIBRARY_PATH", str(sig_bridge_path.parent))

    for key, value in _config_env_pairs(env_values, (*AUTH_COMMON_KEYS, *LOCAL_AUTH_CLIENT_KEYS)):
        env[key] = value

    return env


def _normalize_remote_tvm_python(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return value

    try:
        parts = shlex.split(value)
    except ValueError:
        return value
    if not parts:
        return value
    if len(parts) == 1:
        return parts[0]
    if parts[0] == "env":
        for token in reversed(parts[1:]):
            if "=" not in token:
                return token
    return value


def build_local_crypto_client_command(
    env_values: Mapping[str, str] | None,
    *,
    host: str,
    input_path: Path,
    client_script: Path,
) -> tuple[list[str], dict[str, str]]:
    runtime_root, _ = resolve_local_mlkem_runtime_root(
        env_values,
        extra_roots=(client_script.parent.parent,),
    )
    python_command = _detect_local_python_command(env_values, runtime_root=runtime_root)
    suite = first_config_value(env_values, keys=SUITE_KEYS, default=DEFAULT_CIPHER_SUITE)
    crypto_port = parse_int_config(
        first_config_value(env_values, keys=REMOTE_PORT_KEYS),
        DEFAULT_CRYPTO_PORT,
    )

    env = _build_local_crypto_env(
        env_values,
        client_script=client_script,
        runtime_root=runtime_root,
    )

    command = [
        python_command,
        str(client_script),
        "--host",
        host,
        "--port",
        str(crypto_port),
        "--input",
        str(input_path),
        "--suite",
        suite,
    ]
    return command, env


def build_local_crypto_daemon_command(
    env_values: Mapping[str, str] | None,
    *,
    host: str,
    client_script: Path,
) -> tuple[list[str], dict[str, str]]:
    """构建 tcp_client.py --daemon 模式的启动命令

    daemon 模式下不需要 --input / --count / --json-summary，
    这些参数通过 stdin JSON 指令按需传入。
    """
    runtime_root, _ = resolve_local_mlkem_runtime_root(
        env_values,
        extra_roots=(client_script.parent.parent,),
    )
    python_command = _detect_local_python_command(env_values, runtime_root=runtime_root)
    suite = first_config_value(env_values, keys=SUITE_KEYS, default=DEFAULT_CIPHER_SUITE)
    crypto_port = parse_int_config(
        first_config_value(env_values, keys=REMOTE_PORT_KEYS),
        DEFAULT_CRYPTO_PORT,
    )

    env = _build_local_crypto_env(
        env_values,
        client_script=client_script,
        runtime_root=runtime_root,
    )

    command = [
        python_command,
        str(client_script),
        "--host", host,
        "--port", str(crypto_port),
        "--suite", suite,
        "--daemon",
    ]
    return command, env


def build_local_crypto_daemon_fingerprint(
    env_values: Mapping[str, str] | None,
    *,
    host: str,
    client_script: Path,
) -> tuple[str, ...]:
    """Build a daemon reuse fingerprint tied to the effective runtime config."""
    runtime_root, _ = resolve_local_mlkem_runtime_root(
        env_values,
        extra_roots=(client_script.parent.parent,),
    )
    transport_mode = local_crypto_transport_mode(env_values)
    suite = first_config_value(env_values, keys=SUITE_KEYS, default=DEFAULT_CIPHER_SUITE)
    crypto_port = parse_int_config(
        first_config_value(env_values, keys=REMOTE_PORT_KEYS),
        DEFAULT_CRYPTO_PORT,
    )
    try:
        resolved_client = str(client_script.resolve())
    except OSError:
        resolved_client = str(client_script)
    try:
        resolved_runtime_root = str(runtime_root.resolve()) if runtime_root is not None else ""
    except OSError:
        resolved_runtime_root = str(runtime_root) if runtime_root is not None else ""
    auth_parts = tuple(
        f"{key}={value}"
        for key, value in _config_env_pairs(env_values, (*AUTH_COMMON_KEYS, *LOCAL_AUTH_CLIENT_KEYS))
    )
    return (
        transport_mode,
        str(host).strip(),
        str(crypto_port),
        str(suite).strip().upper(),
        resolved_client,
        resolved_runtime_root,
        *auth_parts,
    )


class MlkemSessionManager:
    """管理持久化的 tcp_client.py --daemon 子进程

    一次启动 → 一次握手 → N 张图片复用同一 ML-KEM session。
    通过 stdin/stdout JSON 协议通信。

    Usage:
        mgr = MlkemSessionManager(env_values, host, client_script)
        mgr.ensure_alive()
        result = mgr.send_image("/tmp/latent.bin", "job-001")
        mgr.close()
    """

    def __init__(
        self,
        env_values: Mapping[str, str] | None,
        host: str,
        client_script: Path,
        *,
        startup_timeout: float = 30.0,
        io_timeout: float = 120.0,
    ) -> None:
        self._env_values = env_values
        self._host = host
        self._client_script = client_script
        self._config_fingerprint = build_local_crypto_daemon_fingerprint(
            env_values,
            host=host,
            client_script=client_script,
        )
        self._startup_timeout = startup_timeout
        self._io_timeout = io_timeout
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._handshake_ms: float = 0.0
        self._images_sent: int = 0
        self._alive: bool = False

    @property
    def is_alive(self) -> bool:
        return self._alive and self._proc is not None and self._proc.poll() is None

    def matches_config(
        self,
        env_values: Mapping[str, str] | None,
        *,
        host: str,
        client_script: Path,
    ) -> bool:
        return self._config_fingerprint == build_local_crypto_daemon_fingerprint(
            env_values,
            host=host,
            client_script=client_script,
        )

    def ensure_alive(self) -> None:
        """启动 daemon（如未运行）"""
        with self._lock:
            if self.is_alive:
                return
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    self._start_daemon()
                    return
                except Exception as exc:
                    last_error = exc
                    if attempt >= 2:
                        break
                    time.sleep(0.5)
            assert last_error is not None
            raise last_error

    def _start_daemon(self) -> None:
        """启动 daemon 子进程，等待 'ready' 响应"""
        cmd, env = build_local_crypto_daemon_command(
            self._env_values, host=self._host, client_script=self._client_script)
        env["PYTHONUNBUFFERED"] = "1"

        print(f"[MlkemSessionManager] 启动 daemon: {' '.join(cmd[:6])}...")
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=env, bufsize=1)
        assert self._proc.stdin is not None
        assert self._proc.stdout is not None

        try:
            ready_line = self._read_line(timeout=self._startup_timeout)
            ready = json.loads(ready_line)
            if ready.get("status") != "ready":
                raise RuntimeError(f"daemon 未就绪: {ready}")
            self._handshake_ms = ready.get("handshake_ms", 0.0)
            self._images_sent = 0
            self._alive = True
            print(f"[MlkemSessionManager] daemon 就绪 "
                  f"(握手={self._handshake_ms:.0f}ms)")
        except Exception as e:
            stderr_tail = ""
            if self._proc is not None and self._proc.poll() is not None and self._proc.stderr is not None:
                try:
                    stderr_tail = (self._proc.stderr.read() or "").strip()[-400:]
                except Exception:
                    stderr_tail = ""
            self._kill_proc()
            detail = f"{e}"
            if stderr_tail:
                detail = f"{detail}; stderr={stderr_tail}"
            raise RuntimeError(f"daemon 启动失败: {detail}") from e

    def send_image(
        self,
        input_path: str | Path,
        job_id: str,
        *,
        run_tvm: bool = False,
        expect_result: bool = False,
    ) -> dict:
        """通过 daemon 发送单张图片

        Returns:
            响应 dict（含 status, sha256_match, total_ms 等）
        Raises:
            RuntimeError: daemon 不可用
        """
        with self._lock:
            last_error: Exception | None = None
            for attempt in range(2):
                if not self.is_alive:
                    self._start_daemon()
                try:
                    self._stdin_write(json.dumps({
                        "action": "send",
                        "input": str(input_path),
                        "job_id": job_id,
                        "run_tvm": run_tvm,
                        "expect_result": expect_result,
                    }))
                    response_line = self._read_line(timeout=self._io_timeout)
                    response = json.loads(response_line)
                    if response.get("status") == "ok":
                        self._images_sent += 1
                        return response
                    message = str(
                        response.get("message")
                        or response.get("error")
                        or response.get("detail")
                        or ""
                    ).strip()
                    if self._is_retryable_send_error(message):
                        last_error = RuntimeError(message or "daemon link lost")
                        self._alive = False
                        self._kill_proc()
                        if attempt >= 1:
                            break
                        print(
                            f"[MlkemSessionManager] daemon 响应链路错误，正在重连重试 "
                            f"(job_id={job_id}): {message or 'daemon link lost'}"
                        )
                        continue
                    return response
                except Exception as exc:
                    last_error = exc
                    self._alive = False
                    self._kill_proc()
                    if attempt >= 1:
                        break
                    print(
                        f"[MlkemSessionManager] daemon 发送失败，正在重连重试 "
                        f"(job_id={job_id}): {exc}"
                    )
            assert last_error is not None
            raise RuntimeError(f"daemon 发送失败: {last_error}") from last_error

    @staticmethod
    def _is_retryable_send_error(message: str) -> bool:
        text = str(message or "").strip().lower()
        if not text:
            return False
        retry_tokens = (
            "连接关闭",
            "已读 0 字节",
            "connection closed",
            "connection reset",
            "reset by peer",
            "broken pipe",
            "eof",
            "timed out",
            "timeout",
            "daemon link lost",
            "帧过大",
            "frame too large",
            "invalid json",
        )
        return any(token in text for token in retry_tokens)

    def ping(self) -> dict:
        """检查 daemon 健康状态"""
        with self._lock:
            if not self.is_alive:
                raise RuntimeError("daemon 未运行")
            self._stdin_write(json.dumps({"action": "ping"}))
            response_line = self._read_line(timeout=self._io_timeout)
            return json.loads(response_line)

    def close(self) -> None:
        """优雅关闭 daemon"""
        with self._lock:
            if not self.is_alive:
                return
            try:
                self._stdin_write(json.dumps({"action": "quit"}))
                self._proc.wait(timeout=5.0)
            except Exception:
                self._kill_proc()
            finally:
                self._alive = False
                print(f"[MlkemSessionManager] 已关闭 "
                      f"(已发送 {self._images_sent} 张)")

    def _stdin_write(self, data: str) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(data + "\n")
        self._proc.stdin.flush()

    def _read_line(self, timeout: float) -> str:
        """从 daemon stdout 读取一行，带超时（O-2: select 替代线程 spawn）

        注意：必须用 os.read() 直接读 fd，绕过 TextIOWrapper 的内部缓冲区。
        BufferedReader 首次 read() 会预读整个 fd，导致后续 select 看不到数据。
        """
        assert self._proc is not None and self._proc.stdout is not None
        fd = self._proc.stdout.fileno()
        deadline = time.monotonic() + timeout
        buf: list[bytes] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._alive = False
                raise TimeoutError(f"daemon 读取超时 ({timeout}s)")
            ready, _, _ = select.select([fd], [], [], min(remaining, 0.5))
            if not ready:
                continue
            raw = os.read(fd, 1)
            if not raw:
                self._alive = False
                raise RuntimeError("daemon stdout 已关闭")
            if raw == b'\n':
                return b''.join(buf).decode('utf-8')
            buf.append(raw)

    def _kill_proc(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None
        self._alive = False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def _derive_remote_server_script(
    env_values: Mapping[str, str] | None,
    *,
    local_server_script: Path | None,
) -> str:
    explicit_remote_script = first_config_value(env_values, keys=REMOTE_SERVER_SCRIPT_KEYS)
    if explicit_remote_script:
        return explicit_remote_script

    remote_project_root = first_config_value(env_values, keys=REMOTE_PROJECT_ROOT_KEYS)
    if not remote_project_root and local_server_script is not None:
        try:
            local_server_script.resolve().relative_to(PROJECT_ROOT)
        except ValueError:
            # The ML-KEM helper was discovered from a sibling/external repo.
            # In that case, a generic REMOTE_PROJECT_ROOT usually refers to the
            # OpenAMP project on the board, not the ML-KEM helper location.
            pass
        else:
            remote_project_root = first_config_value(env_values, keys=LEGACY_REMOTE_PROJECT_ROOT_KEYS)
    if remote_project_root:
        if local_server_script is not None:
            try:
                relative_script = local_server_script.resolve().relative_to(local_server_script.resolve().parents[1])
            except ValueError:
                relative_script = Path("scripts/tcp_server.py")
        else:
            relative_script = Path("scripts/tcp_server.py")
        return f"{remote_project_root.rstrip('/')}/{relative_script.as_posix()}"

    return "~/tcp_server.py"


def build_remote_crypto_server_command(
    env_values: Mapping[str, str] | None,
    *,
    local_server_script: Path | None = None,
) -> str:
    explicit_command = first_config_value(env_values, keys=REMOTE_STARTUP_CMD_KEYS)
    if explicit_command:
        return explicit_command

    remote_python = first_config_value(
        env_values, keys=REMOTE_PYTHON_KEYS,
        default="/home/user/anaconda3/envs/mlkem/bin/python",
    )
    remote_server_script = _derive_remote_server_script(env_values, local_server_script=local_server_script)
    suite = first_config_value(env_values, keys=SUITE_KEYS, default=DEFAULT_CIPHER_SUITE)
    output_dir = first_config_value(env_values, keys=REMOTE_OUTPUT_DIR_KEYS, default=DEFAULT_OUTPUT_DIR)
    log_path = first_config_value(env_values, keys=REMOTE_LOG_PATH_KEYS, default=DEFAULT_LOG_PATH)
    crypto_port = parse_int_config(first_config_value(env_values, keys=REMOTE_PORT_KEYS), DEFAULT_CRYPTO_PORT)
    status_port_raw = first_config_value(env_values, keys=STATUS_PORT_KEYS)
    enable_tvm = parse_bool_config(first_config_value(env_values, keys=REMOTE_TVM_ENABLE_KEYS), True)
    server_caps = (
        inspect_local_crypto_server_capabilities(local_server_script)
        if local_server_script is not None
        else {"supports_status_port": True}
    )

    server_argv: list[str] = [
        remote_python,
        remote_server_script,
        "--host",
        "0.0.0.0",
        "--port",
        str(crypto_port),
        "--output-dir",
        output_dir,
        "--suite",
        suite,
    ]
    if server_caps.get("supports_status_port", True):
        if status_port_raw:
            server_argv.extend(["--status-port", str(parse_int_config(status_port_raw, DEFAULT_STATUS_PORT))])
        else:
            server_argv.extend(["--status-port", str(DEFAULT_STATUS_PORT)])
    if enable_tvm:
        server_argv.append("--tvm")
        remote_tvm_python = first_config_value(env_values, keys=REMOTE_TVM_PYTHON_KEYS)
        if remote_tvm_python:
            server_argv.extend(["--tvm-python", _normalize_remote_tvm_python(remote_tvm_python)])
        remote_artifact = first_config_value(env_values, keys=REMOTE_ARTIFACT_KEYS)
        if remote_artifact:
            server_argv.extend(["--artifact-path", remote_artifact])
        snr = first_config_value(env_values, keys=REMOTE_SNR_KEYS, default="10")
        server_argv.extend(["--snr", snr])

    command_steps: list[str] = []
    # 仅在 remote_python 不是绝对路径时才需要 conda activate（绝对路径已自带环境，无需激活）
    remote_python_is_abs = remote_python.startswith("/")
    activate_command = first_config_value(env_values, keys=REMOTE_ACTIVATE_KEYS)
    if activate_command and not remote_python_is_abs:
        command_steps.append(activate_command)
    elif not remote_python_is_abs:
        conda_env = first_config_value(env_values, keys=REMOTE_CONDA_ENV_KEYS)
        conda_sh = first_config_value(env_values, keys=REMOTE_CONDA_SH_KEYS)
        if conda_env and conda_sh:
            command_steps.append(
                f"if [ -f {shlex_quote(conda_sh)} ]; then . {shlex_quote(conda_sh)} && "
                f"conda activate {shlex_quote(conda_env)}; fi"
            )
        elif conda_env:
            command_steps.append(
                "if command -v conda >/dev/null 2>&1; then "
                f'eval "$(conda shell.bash hook)" >/dev/null 2>&1 && conda activate {shlex_quote(conda_env)}; fi'
            )

    remote_oqs_install = first_config_value(env_values, keys=REMOTE_OQS_INSTALL_KEYS)
    if remote_oqs_install:
        command_steps.append(f"export OQS_INSTALL_PATH={shlex_quote(remote_oqs_install)}")

    ld_library_path = first_config_value(env_values, keys=REMOTE_LD_LIBRARY_KEYS)
    if ld_library_path:
        command_steps.append(
            f"export LD_LIBRARY_PATH={shlex_quote(ld_library_path)}${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
        )
    elif remote_oqs_install:
        remote_oqs_lib = f"{remote_oqs_install.rstrip('/')}/lib"
        command_steps.append(
            f"export LD_LIBRARY_PATH={shlex_quote(remote_oqs_lib)}${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
        )

    tongsuo_bridge = first_config_value(env_values, keys=REMOTE_TONGSUO_BRIDGE_KEYS)
    if tongsuo_bridge:
        command_steps.append(f"export TONGSUO_KEM_BRIDGE={shlex_quote(tongsuo_bridge)}")

    tongsuo_sig_bridge = first_config_value(env_values, keys=REMOTE_TONGSUO_SIG_BRIDGE_KEYS)
    if tongsuo_sig_bridge:
        command_steps.append(f"export TONGSUO_SIG_BRIDGE={shlex_quote(tongsuo_sig_bridge)}")

    remote_prelude = first_config_value(env_values, keys=REMOTE_PRELUDE_KEYS)
    if remote_prelude:
        command_steps.append(remote_prelude)

    run_logger_dir = first_config_value(env_values, keys=REMOTE_RUN_LOGGER_DIR_KEYS)
    if run_logger_dir:
        command_steps.append(f"export RUN_LOGGER_DIR={shlex_quote(run_logger_dir)}")

    for key, value in _config_env_pairs(env_values, (*AUTH_COMMON_KEYS, *REMOTE_AUTH_SERVER_KEYS)):
        command_steps.append(f"export {key}={shlex_quote(value)}")

    server_command = " ".join(shlex_quote(str(arg)) for arg in server_argv)
    command_steps.append(f"nohup {server_command} </dev/null >> {shlex_quote(log_path)} 2>&1 &")
    return f"bash -c {shlex_quote('; '.join(command_steps))}"


def run_ssh_command(
    *,
    host: str,
    user: str,
    password: str,
    port: str | int,
    remote_command: str,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    ssh_command = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=no",
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-p",
        str(port),
        f"{user}@{host}",
        remote_command,
    ]
    env = dict(os.environ)
    askpass_path: Path | None = None

    if password and shutil.which("sshpass"):
        env["SSHPASS"] = password
        command = ["sshpass", "-e", *ssh_command]
    elif password:
        fd, raw_path = tempfile.mkstemp(prefix="mlkem-askpass-", suffix=".sh", text=True)
        askpass_path = Path(raw_path)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
            handle.write(f"printf '%s\\n' {shlex_quote(password)}\n")
        askpass_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        env["SSH_ASKPASS"] = str(askpass_path)
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env.setdefault("DISPLAY", "codex-askpass:0")
        if shutil.which("setsid"):
            command = ["setsid", "-w", *ssh_command]
        else:
            command = ssh_command
    else:
        command = ssh_command

    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    finally:
        if askpass_path is not None:
            try:
                askpass_path.unlink()
            except OSError:
                pass
