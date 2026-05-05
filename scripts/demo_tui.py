#!/usr/bin/env python3
"""
ML-KEM 安全语义通信 — TUI 演示界面

展示 ML-KEM 后量子密钥交换 + AEAD 加密传输的完整流程。
支持模拟模式（本地线程 server）和真机模式（连接飞腾派）。

用法:
  source ../.venv/bin/activate
  OQS_INSTALL_PATH=../liboqs-dist python demo_tui.py           # 模拟模式
  OQS_INSTALL_PATH=../liboqs-dist python demo_tui.py --host 100.121.87.73  # 真机
"""

import argparse
import base64
import errno
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Iterator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LIBOQS_DIST = _PROJECT_ROOT / "liboqs-dist"
if "OQS_INSTALL_PATH" not in os.environ and _LIBOQS_DIST.is_dir():
    os.environ["OQS_INSTALL_PATH"] = str(_LIBOQS_DIST)

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Footer, Header, Input, Label, RadioButton, RadioSet,
    RichLog, Static,
)
from rich.text import Text
from rich.panel import Panel

import mlkem_link.secure_channel as secure_channel_module
from mlkem_link.auth import (
    IdentityConfig,
    SigPolicy,
    get_mldsa_backend,
    get_sm2_backend,
)
from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite
from mlkem_link.session import SessionRole
from mlkem_link.secure_channel import SecureChannel


# ── 工具函数 ──

def ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def age_text(monotonic_ts: float | None) -> str:
    if not monotonic_ts:
        return "未更新"
    age = max(0.0, time.monotonic() - monotonic_ts)
    if age < 1.0:
        return f"{age * 1000:.0f} ms前"
    if age < 60.0:
        return f"{age:.1f} s前"
    return f"{age / 60.0:.1f} min前"


def strip_markup(message: str) -> str:
    return re.sub(r"\[/?[^\]]+\]", "", str(message or ""))


ADDR_IN_USE_ERRNOS = {errno.EADDRINUSE}
if hasattr(errno, "WSAEADDRINUSE"):
    ADDR_IN_USE_ERRNOS.add(errno.WSAEADDRINUSE)


def simulate_latent(shape=(1, 3, 64, 64)) -> bytes:
    size = 1
    for d in shape:
        size *= d
    return os.urandom(size * 4)


CONTROL_JOB_REQ_AAD = b"control/job_req"
CONTROL_JOB_ACK_AAD = b"control/job_ack"
CONTROL_HEARTBEAT_AAD = b"control/heartbeat"
CONTROL_HEARTBEAT_ACK_AAD = b"control/heartbeat_ack"
CONTROL_SAFE_STOP_AAD = b"control/safe_stop"
CONTROL_SAFE_STOP_ACK_AAD = b"control/safe_stop_ack"
SIM_SERVER_ID = "sim-board-01"
LOCAL_LOOPBACK_DEFAULT = "127.0.0.1:9527"
TAILSCALE_DEFAULT_HOST = "100.121.87.73"
TAILSCALE_DEFAULT_USER = "user"
TAILSCALE_DEFAULT_PASSWORD = "user"
TAILSCALE_DEFAULT_PORT = 9527
REMOTE_DEMO_SERVER_ID = "phytium-board"
REMOTE_OUTPUT_DIR = "/tmp/mlkem_tui_recv"
REMOTE_LOG_PATH = "/tmp/mlkem_tui_tcp_server.log"
REMOTE_PID_PATH = "/tmp/mlkem_tui_tcp_server.pid"
REMOTE_PORT_PATH = "/tmp/mlkem_tui_tcp_server.port"
REMOTE_TUI_SERVER_PATH = "/tmp/mlkem_tui_tcp_server.py"
LOCAL_TUI_REMOTE_SERVER_PATH = _PROJECT_ROOT / "scripts" / "tui_remote_tcp_server.py"
REMOTE_PYTHON_CANDIDATES = (
    "/home/user/anaconda3/envs/mlkem/bin/python",
    "/home/user/anaconda3/envs/tvm310_safe/bin/python",
    "/usr/bin/python3",
    "python3",
)
REMOTE_SM2_PUB_PATH = "/home/user/keys/server_sm2_identity.pub"
REMOTE_MLDSA_PUB_PATH = "/home/user/keys/server_mldsa_identity.pub"
REMOTE_SM2_KEY_PATH = "/home/user/keys/server_sm2_identity.key"
REMOTE_MLDSA_KEY_PATH = "/home/user/keys/server_mldsa_identity.key"
REMOTE_SIG_BRIDGE_CANDIDATES = (
    "/home/user/libtongsuo_sig_bridge.so",
    "/usr/local/tongsuo/lib/libtongsuo_sig_bridge.so",
    "/usr/local/tongsuo/lib64/libtongsuo_sig_bridge.so",
)
REMOTE_OQS_ROOT_CANDIDATES = (
    "/home/user/liboqs-dist",
    "/home/user/liboqs/build",
    "/usr/local",
)

KEM_PARAM_OPTIONS = ("512", "768", "1024")
CONNECTION_MODE_OPTIONS = ("local", "tailscale", "usrp")
AUTH_MODE_OPTIONS = (
    ("关闭认证", "off", None),
    ("SM2 + ML-DSA", "real", SigPolicy.DUAL_REQUIRED),
    ("SM2_ONLY", "real", SigPolicy.SM2_ONLY),
    ("MLDSA_ONLY", "real", SigPolicy.MLDSA_ONLY),
)


DEMO_HELP_TEXT = dedent(
    """
    ML-KEM 控制/认证 TUI 帮助

    推荐顺序
    1. 先在左侧选择连接模式、本机/Tailscale 参数、KEM、AEAD、认证模式。
    2. 按 `c` 建立连接；如果是 Tailscale 且派端服务未起，可先按 `b` 拉起派端。
    3. 按 `s` 运行控制/认证测试。
    4. 按 `e` 导出当前会话与日志。

    快捷键
    h / F1: 打开帮助
    c: 连接
    d: 断开
    b: 拉起派端
    s: 发送测试
    e: 导出会话
    q: 退出

    连接模式
    本机回环: 在本机起一个模拟 server，适合演示控制/认证流程
    Tailscale连接: 通过 SSH / TCP 连接到飞腾派
    USRP连接: 当前 UI 里仍回退到本机回环，不是正式入口

    左侧配置项
    本机回环参数: 本地 IP:端口，例如 127.0.0.1:9527
    Tailscale 参数: 板端 SSH 地址、用户名、密码
    KEM 参数: ML-KEM-512 / 768 / 1024
    AEAD 套件: AES-256-GCM 或 SM4-128-GCM
    认证模式:
      关闭认证
      SM2 + ML-DSA
      SM2_ONLY
      MLDSA_ONLY

    面板说明
    Sequence Diagram: 展示握手/测试步骤
    Preflight Panel: 展示运行前自检结果
    Control/Auth Panel: 展示当前密钥交换与认证状态
    History Panel: 展示最近的会话/动作摘要
    Log Panel: 最详细的运行日志

    备注
    这是控制面/认证面 demo，不是当前 USRP292x 数据面入口。
    如果要跑无线数据面，请用 `./tui_start.sh --usrp`。
    """
).strip()


class DemoHelpScreen(ModalScreen[None]):
    CSS = """
    DemoHelpScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.72);
    }
    #demo-help-dialog {
        width: 96;
        max-width: 96%;
        height: 28;
        max-height: 92%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }
    #demo-help-title {
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    #demo-help-body {
        height: 1fr;
    }
    #demo-help-close {
        width: 1fr;
        margin-top: 1;
    }
    """
    BINDINGS = [
        Binding("escape", "close_help", "关闭", priority=True),
        Binding("h", "close_help", "关闭"),
        Binding("f1", "close_help", "关闭"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="demo-help-dialog"):
            yield Static("ML-KEM Demo Help", id="demo-help-title")
            with VerticalScroll(id="demo-help-body"):
                yield Static(DEMO_HELP_TEXT)
            yield Button("关闭帮助 (Esc / h / F1)", id="demo-help-close", variant="primary")

    def action_close_help(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "demo-help-close":
            self.dismiss(None)


@dataclass
class ConnectionConfig:
    mode: str
    host: str
    port: int
    board_host: str = ""
    board_user: str = TAILSCALE_DEFAULT_USER
    board_password: str = TAILSCALE_DEFAULT_PASSWORD
    label: str = ""


@dataclass
class AuthBundle:
    display_name: str
    enabled: bool
    backend_mode: str
    policy: SigPolicy | None = None
    sm2_backend: Any | None = None
    mldsa_backend: Any | None = None
    client_config: IdentityConfig | None = None
    server_config: IdentityConfig | None = None
    sm2_name: str = "off"
    mldsa_name: str = "off"
    fingerprint: str = "off"


def detect_auth_capabilities() -> dict[str, str]:
    capabilities: dict[str, str] = {}
    try:
        capabilities["sm2"] = get_sm2_backend().name
    except Exception as exc:
        capabilities["sm2"] = f"不可用: {exc}"
    try:
        capabilities["mldsa"] = get_mldsa_backend().name
    except Exception as exc:
        capabilities["mldsa"] = f"不可用: {exc}"
    return capabilities


@contextmanager
def patch_auth_backends(bundle: AuthBundle | None) -> Iterator[None]:
    original_sm2 = secure_channel_module.get_sm2_backend
    original_mldsa = secure_channel_module.get_mldsa_backend
    try:
        if bundle and bundle.enabled:
            if bundle.sm2_backend is not None:
                secure_channel_module.get_sm2_backend = lambda: bundle.sm2_backend
            if bundle.mldsa_backend is not None:
                secure_channel_module.get_mldsa_backend = lambda: bundle.mldsa_backend
        yield
    finally:
        secure_channel_module.get_sm2_backend = original_sm2
        secure_channel_module.get_mldsa_backend = original_mldsa


# ── 模拟 server ──

class SimServer:
    """后台线程模拟飞腾派 server"""

    def __init__(
        self,
        host="127.0.0.1",
        port=0,
        *,
        kem_param: str = "768",
        suite: CipherSuite = CipherSuite.SM4_GCM,
        auth_bundle: AuthBundle | None = None,
    ):
        self._kem_param = kem_param
        self._suite = suite
        self._auth_bundle = auth_bundle
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((host, port))
        self._server.listen(5)
        self.host, self.port = self._server.getsockname()
        self._running = False

    @property
    def config_key(self) -> tuple[str, str, str]:
        auth_key = "off"
        if self._auth_bundle and self._auth_bundle.enabled:
            auth_key = self._auth_bundle.fingerprint
        return (self._kem_param, self._suite.value, auth_key, self.host, str(self.port))

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False
        try:
            self._server.close()
        except OSError:
            pass

    def _run(self):
        backend = get_backend(self._kem_param)
        while self._running:
            self._server.settimeout(1.0)
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                ch = SecureChannel(conn, SessionRole.RESPONDER, backend, self._suite)
                with patch_auth_backends(self._auth_bundle):
                    if self._auth_bundle and self._auth_bundle.enabled:
                        ch.authenticated_handshake(self._auth_bundle.server_config)
                    else:
                        ch.handshake()

                control_state = {
                    "guard_state": "READY",
                    "last_fault_code": "NONE",
                    "active_job_id": "",
                    "job_req_count": 0,
                    "job_ack_allow": 0,
                    "job_ack_deny": 0,
                    "heartbeat_count": 0,
                    "heartbeat_ack_count": 0,
                    "safe_stop_count": 0,
                    "safe_stop_ack_count": 0,
                    "auth_enabled": bool(self._auth_bundle and self._auth_bundle.enabled),
                    "auth_policy": (
                        self._auth_bundle.policy.value
                        if self._auth_bundle and self._auth_bundle.policy
                        else "OFF"
                    ),
                    "server_id": SIM_SERVER_ID,
                }

                job_req_raw = ch.recv_encrypted(aad=CONTROL_JOB_REQ_AAD)
                job_req = json.loads(job_req_raw)
                control_state["job_req_count"] += 1
                control_state["job_ack_allow"] += 1
                control_state["guard_state"] = "JOB_ACTIVE"
                control_state["active_job_id"] = str(job_req.get("job_id") or "sim-job")
                job_ack = json.dumps({
                    "type": "JOB_ACK",
                    "decision": "ALLOW",
                    **control_state,
                }).encode()
                ch.send_encrypted(job_ack, aad=CONTROL_JOB_ACK_AAD)

                hb_raw = ch.recv_encrypted(aad=CONTROL_HEARTBEAT_AAD)
                hb = json.loads(hb_raw)
                control_state["heartbeat_count"] += 1
                control_state["heartbeat_ack_count"] += 1
                hb_ack = json.dumps({
                    "type": "HEARTBEAT_ACK",
                    "hb_seq": int(hb.get("hb_seq") or 0),
                    **control_state,
                }).encode()
                ch.send_encrypted(hb_ack, aad=CONTROL_HEARTBEAT_ACK_AAD)

                meta_raw = ch.recv_encrypted(aad=b"metadata")
                meta = json.loads(meta_raw)
                latent = ch.recv_encrypted(aad=meta_raw)
                recv_sha = hashlib.sha256(latent).hexdigest()
                sha_ok = recv_sha == meta.get("sha256", "")
                ack = json.dumps({
                    "status": "ok" if sha_ok else "sha256_mismatch",
                    "sha256_match": sha_ok,
                    "bytes_received": len(latent),
                    "guard_state": control_state["guard_state"],
                    "server_id": SIM_SERVER_ID,
                }).encode()
                ch.send_encrypted(ack, aad=b"ack")

                stop_raw = ch.recv_encrypted(aad=CONTROL_SAFE_STOP_AAD)
                stop_msg = json.loads(stop_raw)
                control_state["safe_stop_count"] += 1
                control_state["safe_stop_ack_count"] += 1
                control_state["guard_state"] = "READY"
                control_state["active_job_id"] = ""
                stop_ack = json.dumps({
                    "type": "SAFE_STOP_ACK",
                    "requested_by": stop_msg.get("requested_by") or "host",
                    **control_state,
                }).encode()
                ch.send_encrypted(stop_ack, aad=CONTROL_SAFE_STOP_ACK_AAD)
            except Exception:
                pass
            finally:
                conn.close()


# ── 时序图 ──

class SequenceDiagram(Static):
    """握手 + 认证 + 控制 + 传输时序图"""

    MIN_FLOW_WIDTH = 38

    phase: reactive[str] = reactive("idle")
    pk_sent: reactive[bool] = reactive(False)
    ct_received: reactive[bool] = reactive(False)
    auth_label: reactive[str] = reactive("")
    auth_done: reactive[bool] = reactive(False)
    job_ack: reactive[bool] = reactive(False)
    heartbeat_ack: reactive[bool] = reactive(False)
    data_sent: reactive[bool] = reactive(False)
    ack_received: reactive[bool] = reactive(False)
    safe_stop_ack: reactive[bool] = reactive(False)
    error_msg: reactive[str] = reactive("")

    def _flow_width(self) -> int:
        widget_width = getattr(self.size, "width", 0)
        if widget_width <= 0:
            return self.MIN_FLOW_WIDTH
        return max(self.MIN_FLOW_WIDTH, widget_width - 6)

    @staticmethod
    def _fit_text(text: str, width: int) -> str:
        if len(text) <= width:
            return text.ljust(width)
        if width <= 1:
            return text[:width]
        return text[: width - 1] + "…"

    def _flow_body(self, label: str, direction: str) -> str:
        flow_width = self._flow_width()
        label = self._fit_text(label, max(1, flow_width - 3)).strip()
        core = f" {label} "
        dash_count = max(0, flow_width - len(core) - 1)
        left = dash_count // 2
        right = dash_count - left
        if direction == "lr":
            return f"{'─' * left}{core}{'─' * right}>"
        return f"<{'─' * left}{core}{'─' * right}"

    def _append_flow(
        self,
        text: Text,
        *,
        label: str,
        direction: str,
        style: str,
        note: str = "",
        note_style: str | None = None,
    ) -> None:
        text.append("  │", style="cyan")
        text.append(self._flow_body(label, direction), style=style)
        text.append("│", style="green")
        if note:
            text.append("  ", style="green")
            text.append(note, style=note_style or style)
        text.append("\n")

    def _append_wait(self, text: Text, label: str) -> None:
        flow_width = self._flow_width()
        text.append("  │", style="dim")
        text.append(self._fit_text(f"  {label}", flow_width), style="dim italic")
        text.append("│\n", style="dim")

    def _append_blank(self, text: Text) -> None:
        flow_width = self._flow_width()
        text.append("  │", style="dim")
        text.append(" " * flow_width, style="dim")
        text.append("│\n", style="dim")

    def render(self) -> Text:
        flow_width = self._flow_width()
        header_width = flow_width + 2
        header_gap = max(1, header_width - len("上位机") - len("飞腾派"))
        t = Text()
        t.append("  时序图\n", style="bold white on #333366")

        # 列头
        t.append("  ")
        t.append("上位机", style="bold cyan")
        t.append(" " * header_gap)
        t.append("飞腾派", style="bold green")
        t.append("\n")
        t.append("  ")
        t.append("─" * header_width, style="dim")
        t.append("\n")

        if self.phase == "idle":
            t.append("\n  等待连接...\n\n", style="dim italic")
        else:
            t.append("\n")

            if self.auth_label:
                if self.pk_sent:
                    self._append_flow(
                        t,
                        label="ClientHello{suite,nonce,kem_pk}",
                        direction="lr",
                        style="bold yellow",
                    )
                else:
                    self._append_blank(t)
                if self.ct_received:
                    self._append_flow(
                        t,
                        label="ServerHelloAuth{id,policy,kem_ct,sigs}",
                        direction="rl",
                        style="bold yellow",
                    )
                elif self.pk_sent:
                    self._append_wait(t, "等待 ServerHelloAuth...")
                else:
                    self._append_blank(t)
                if self.auth_done:
                    self._append_flow(
                        t,
                        label="Finished(c2s)",
                        direction="lr",
                        style="bold blue",
                    )
                    self._append_flow(
                        t,
                        label="Finished(s2c)",
                        direction="rl",
                        style="bold blue",
                        note=f"{self.auth_label} 认证完成",
                    )
                elif self.ct_received:
                    self._append_wait(t, "验签 / Finished...")
                else:
                    self._append_blank(t)
            else:
                if self.pk_sent:
                    self._append_flow(
                        t,
                        label="ML-KEM public_key",
                        direction="lr",
                        style="bold yellow",
                    )
                else:
                    self._append_blank(t)
                if self.ct_received:
                    self._append_flow(
                        t,
                        label="ML-KEM ciphertext",
                        direction="rl",
                        style="bold yellow",
                        note="会话密钥就绪",
                        note_style="bold green",
                    )
                elif self.pk_sent:
                    self._append_wait(t, "等待 ciphertext...")
                else:
                    self._append_blank(t)

            if self.job_ack:
                self._append_flow(
                    t,
                    label="JOB_REQ",
                    direction="lr",
                    style="bold cyan",
                )
                self._append_flow(
                    t,
                    label="JOB_ACK",
                    direction="rl",
                    style="bold cyan",
                    note="控制面放行",
                )
            elif self.auth_done or self.ct_received:
                self._append_wait(t, "等待 JOB_ACK...")
            else:
                self._append_blank(t)

            if self.heartbeat_ack:
                self._append_flow(
                    t,
                    label="HEARTBEAT",
                    direction="lr",
                    style="bold white",
                )
                self._append_flow(
                    t,
                    label="HEARTBEAT_ACK",
                    direction="rl",
                    style="bold white",
                    note="保活确认",
                )
            elif self.job_ack:
                self._append_wait(t, "等待 HB_ACK...")
            else:
                self._append_blank(t)

            # Data
            if self.data_sent:
                self._append_flow(
                    t,
                    label="ENC_DATA (49KB)",
                    direction="lr",
                    style="bold magenta",
                    note="AEAD 加密传输",
                )
            else:
                self._append_blank(t)

            # ACK
            if self.ack_received:
                self._append_flow(
                    t,
                    label="DATA_ACK(INTEGRITY)",
                    direction="rl",
                    style="bold green",
                    note="完整性验证通过",
                )
            elif self.data_sent:
                self._append_wait(t, "等待 ACK...")

            if self.safe_stop_ack:
                self._append_flow(
                    t,
                    label="SAFE_STOP",
                    direction="lr",
                    style="bold yellow",
                )
                self._append_flow(
                    t,
                    label="SAFE_STOP_ACK",
                    direction="rl",
                    style="bold yellow",
                    note="收口回 READY",
                )
            elif self.ack_received:
                self._append_wait(t, "等待 STOP_ACK...")

            t.append("\n")

        if self.error_msg:
            t.append(f"  ✗ {self.error_msg}\n", style="bold red")

        return t

    def reset(self):
        self.phase = "idle"
        self.pk_sent = False
        self.ct_received = False
        self.auth_label = ""
        self.auth_done = False
        self.job_ack = False
        self.heartbeat_ack = False
        self.data_sent = False
        self.ack_received = False
        self.safe_stop_ack = False
        self.error_msg = ""

class ControlAuthPanel(Static):
    """认证状态 + 控制面状态面板"""

    state: reactive[dict] = reactive({})

    def on_mount(self) -> None:
        self.set_interval(4.0, self.refresh)

    def render(self) -> Text:
        t = Text()
        t.append("  认证 / 控制面\n", style="bold white on #333366")
        t.append("\n")

        if not self.state:
            t.append("  等待测试...\n", style="dim italic")
            return t

        auth_enabled = bool(self.state.get("auth_enabled"))
        policy = str(self.state.get("auth_policy") or "OFF")
        auth_mode = str(self.state.get("auth_mode") or "off")
        auth_label = str(self.state.get("auth_label") or auth_mode)
        server_id = str(self.state.get("server_id") or "-")
        finished_ok = bool(self.state.get("finished_ok"))
        snapshot_age = age_text(self.state.get("_snapshot_monotonic"))
        snapshot_at = str(self.state.get("_snapshot_at") or "-")

        t.append("  认证: ")
        t.append("ON" if auth_enabled else "OFF", style="bold green" if auth_enabled else "bold yellow")
        t.append(f"  选项={auth_label}  策略={policy}\n")
        t.append(f"  服务端: {server_id}\n")
        t.append(f"  SM2: {self.state.get('sm2_backend', 'off')}\n")
        t.append(f"  ML-DSA: {self.state.get('mldsa_backend', 'off')}\n")
        t.append("  Finished: ")
        t.append("✓\n" if finished_ok else "-\n", style="bold green" if finished_ok else "dim")
        t.append("  KDF: HKDF-SHA256\n")
        t.append("  Payload: AEAD + 指纹回执\n")
        t.append(f"  快照: {snapshot_age}  ({snapshot_at})\n", style="dim")

        t.append("\n  控制面:\n")
        t.append(f"  Guard={self.state.get('guard_state', 'UNKNOWN')}  Fault={self.state.get('last_fault_code', 'UNKNOWN')}\n")
        t.append(
            f"  JOB req={self.state.get('job_req_count', 0)} "
            f"allow={self.state.get('job_ack_allow', 0)} "
            f"deny={self.state.get('job_ack_deny', 0)}\n"
        )
        t.append(
            f"  HB tx={self.state.get('heartbeat_count', 0)} "
            f"ack={self.state.get('heartbeat_ack_count', 0)}\n"
        )
        t.append(
            f"  STOP tx={self.state.get('safe_stop_count', 0)} "
            f"ack={self.state.get('safe_stop_ack_count', 0)}\n"
        )
        active_job_id = str(self.state.get("active_job_id") or "-")
        t.append(f"  Active job: {active_job_id}\n")
        return t


class PreflightPanel(Static):
    """运行前自检 + 状态新鲜度摘要"""

    snapshot: reactive[dict] = reactive({})

    def on_mount(self) -> None:
        self.set_interval(4.0, self.refresh)

    def render(self) -> Text:
        t = Text()
        t.append("  自检 / 新鲜度\n", style="bold white on #333366")
        t.append("\n")

        snapshot = dict(self.snapshot or {})
        if not snapshot:
            t.append("  尚未执行自检\n", style="dim italic")
            t.append("  连接或测试前会自动检查依赖、端口和导出目录。\n", style="dim")
            return t

        overall = str(snapshot.get("overall") or "idle")
        overall_style = {
            "ok": "bold green",
            "warn": "bold yellow",
            "fail": "bold red",
        }.get(overall, "dim")
        t.append("  总体: ")
        t.append(overall.upper(), style=overall_style)
        t.append(f"  {snapshot.get('connection_label', '-')}\n")
        t.append(
            f"  上次自检: {age_text(snapshot.get('_checked_monotonic'))}  ({snapshot.get('checked_at', '-')})\n",
            style="dim",
        )

        checks = list(snapshot.get("checks") or [])
        if checks:
            t.append("\n")
            for item in checks[:6]:
                status = str(item.get("status") or "warn")
                badge = {"ok": "✓", "warn": "!", "fail": "✗"}.get(status, "?")
                style = {"ok": "green", "warn": "yellow", "fail": "red"}.get(status, "dim")
                t.append(f"  {badge} ", style=style)
                t.append(f"{item.get('label', '-')}: ", style="bold")
                t.append(f"{item.get('detail', '-')}\n", style=style)

        app = self.app
        if hasattr(app, "_preflight_aux_snapshot"):
            aux = app._preflight_aux_snapshot()
            t.append("\n")
            t.append(f"  派端探测: {aux.get('board_age', '未更新')}\n", style="dim")
            t.append(f"  控制快照: {aux.get('control_age', '未更新')}\n", style="dim")
            t.append(f"  最近导出: {aux.get('export_age', '未导出')}\n", style="dim")
            export_path = aux.get("export_path")
            if export_path:
                t.append(f"  导出文件: {export_path}\n", style="dim")

        return t


# ── 历史面板 ──

class HistoryPanel(Static):
    """多次传输历史对比"""

    records: reactive[list] = reactive([])

    @staticmethod
    def _total_ms(record: dict[str, Any]) -> float:
        return sum(
            float(record.get(key, 0) or 0)
            for key in ("handshake_ms", "control_ms", "encrypt_ms", "ack_ms")
        )

    def render(self) -> Text:
        t = Text()
        t.append("  传输历史 / 指标\n", style="bold white on #333366")
        t.append("\n")

        if not self.records:
            t.append("  暂无记录\n", style="dim italic")
            return t

        latest = self.records[-1]
        latest_total = self._total_ms(latest)
        latest_ok = bool(latest.get("sha_match"))
        t.append(
            "  本次: "
            f"总{latest_total:>6.1f} ms  "
            f"握手{latest.get('handshake_ms', 0):>5.1f}  "
            f"控制{latest.get('control_ms', 0):>5.1f}  "
            f"加密{latest.get('encrypt_ms', 0):>5.1f}  "
            f"ACK{latest.get('ack_ms', 0):>5.1f}\n"
        )
        t.append("  数据: ")
        t.append(f"{latest.get('data_bytes', 0):,} B", style="bold")
        t.append("  完整性: ")
        t.append(
            "payload 指纹 OK\n" if latest_ok else "payload 指纹 FAIL\n",
            style="bold green" if latest_ok else "bold red",
        )

        t.append("\n  #  总耗时  握手  控制  加密  ACK   数据(B)  完整性\n", style="bold")
        t.append("  " + "─" * 64 + "\n", style="dim")

        recent_records = self.records[-8:]
        start_index = max(1, len(self.records) - len(recent_records) + 1)

        for i, rec in enumerate(recent_records, start_index):
            total = self._total_ms(rec)
            hs = rec.get("handshake_ms", 0)
            ctrl = rec.get("control_ms", 0)
            enc = rec.get("encrypt_ms", 0)
            ack = rec.get("ack_ms", 0)
            data = rec.get("data_bytes", 0)
            sha = rec.get("sha_match", False)
            sha_str = "OK" if sha else "FAIL"
            sha_style = "bold green" if sha else "bold red"
            t.append(f"  {i:<3}")
            t.append(f"{total:>6.1f} ")
            t.append(f"{hs:>5.1f} ")
            t.append(f"{ctrl:>5.1f} ")
            t.append(f"{enc:>5.1f} ")
            t.append(f"{ack:>5.1f}   ")
            t.append(f"{data:>7,}   ")
            t.append(f"{sha_str}\n", style=sha_style)

        return t


# ── 板卡状态面板 ──

class BoardStatusPanel(Static):
    """飞腾派实时状态面板（SSH 轮询）"""

    board_status: reactive[dict] = reactive({})

    _SSH_CMD = (
        'echo "===RPROC==="; cat /sys/class/remoteproc/remoteproc0/state 2>&1;'
        'echo "===FIRMWARE==="; cat /sys/class/remoteproc/remoteproc0/firmware 2>&1;'
        'echo "===CPU_ON==="; cat /sys/devices/system/cpu/online;'
        'echo "===CPU_OFF==="; cat /sys/devices/system/cpu/offline;'
        'echo "===TVM==="; ps aux | grep -c "[t]vm";'
        'echo "===TCP==="; ps aux | grep -c "[t]cp_server";'
        'echo "===TONGSUO==="; test -f /usr/local/tongsuo/lib/libtongsuo_kem_bridge.so && echo ok || echo missing;'
        'echo "===MEM==="; free -m | head -2;'
        'echo "===TEMP==="; cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null;'
        'echo "===TSIP==="; ip -4 addr show tailscale0 2>/dev/null | grep -oP "inet \\K[\\d.]+";'
    )

    def __init__(
        self,
        board_host: str = None,
        *,
        board_user: str = TAILSCALE_DEFAULT_USER,
        board_password: str = TAILSCALE_DEFAULT_PASSWORD,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._board_host = board_host
        self._board_user = board_user
        self._board_password = board_password
        self._poll_interval = 12
        self._poll_timer = None

    def on_mount(self) -> None:
        if self._board_host:
            self._poll_timer = self.set_interval(self._poll_interval, self._poll_board)
            self._poll_board()

    def set_board_access(
        self,
        board_host: str | None,
        *,
        board_user: str = TAILSCALE_DEFAULT_USER,
        board_password: str = TAILSCALE_DEFAULT_PASSWORD,
    ) -> None:
        normalized = str(board_host or "").strip()
        self._board_host = normalized or None
        self._board_user = str(board_user or "").strip() or TAILSCALE_DEFAULT_USER
        self._board_password = str(board_password or "") or TAILSCALE_DEFAULT_PASSWORD
        self.board_status = {}
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        if self._board_host:
            self._poll_timer = self.set_interval(self._poll_interval, self._poll_board)
        if self._board_host:
            self._poll_board()

    def _poll_board(self) -> None:
        if not self._board_host:
            return
        threading.Thread(target=self._ssh_poll, daemon=True).start()

    def _ssh_poll(self) -> None:
        try:
            result = subprocess.run(
                ["sshpass", "-p", self._board_password, "ssh",
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=3",
                 f"{self._board_user}@{self._board_host}",
                 self._SSH_CMD],
                capture_output=True, text=True, timeout=8,
            )
            status = self._parse(result.stdout)
            self.app.call_from_thread(self._update, status)
        except Exception as e:
            self.app.call_from_thread(self._update, {"error": str(e)})

    def _update(self, status: dict) -> None:
        snapshot = dict(status)
        snapshot["_observed_at"] = now_iso()
        snapshot["_observed_monotonic"] = time.monotonic()
        self.board_status = snapshot

    @staticmethod
    def _parse(raw: str) -> dict:
        sections = {}
        key = None
        for line in raw.strip().splitlines():
            if line.startswith("===") and line.endswith("==="):
                key = line.strip("=")
                sections[key] = []
            elif key:
                sections[key].append(line.strip())
        d = {}
        d["rproc_state"] = sections.get("RPROC", ["?"])[0]
        d["firmware"] = sections.get("FIRMWARE", ["?"])[0]
        d["cpu_online"] = sections.get("CPU_ON", ["?"])[0]
        d["cpu_offline"] = sections.get("CPU_OFF", ["?"])[0]
        d["tvm_procs"] = sections.get("TVM", ["0"])[0]
        d["tcp_server"] = sections.get("TCP", ["0"])[0]
        d["tongsuo"] = sections.get("TONGSUO", ["?"])[0]
        mem_lines = sections.get("MEM", [])
        if len(mem_lines) >= 2:
            parts = mem_lines[1].split()
            d["mem_used"] = parts[2] if len(parts) > 2 else "?"
            d["mem_total"] = parts[1] if len(parts) > 1 else "?"
        temp_raw = sections.get("TEMP", [""])[0]
        if temp_raw and temp_raw.isdigit():
            d["temp_c"] = f"{int(temp_raw) / 1000:.0f}"
        else:
            d["temp_c"] = "?"
        d["ts_ip"] = sections.get("TSIP", [""])[0] or "?"
        return d

    def render(self) -> Text:
        t = Text()
        if not self._board_host:
            t.append(" 飞腾派\n", style="bold")
            t.append(" 本地模拟模式（无派端连接）", style="dim")
            return t

        s = self.board_status
        if not s:
            t.append(" 飞腾派\n", style="bold")
            t.append(" 正在连接...", style="yellow")
            return t

        if "error" in s:
            t.append(" 飞腾派\n", style="bold")
            t.append(f" 探测异常: {s['error'][:50]}\n", style="bold yellow")
            t.append(f" 最近探测: {age_text(s.get('_observed_monotonic'))}", style="dim")
            return t

        t.append(" 飞腾派\n", style="bold")
        t.append(
            f" 最近探测: {age_text(s.get('_observed_monotonic'))}  ({s.get('_observed_at', '-')})\n",
            style="dim",
        )
        state = s.get("rproc_state", "?")
        if state == "running":
            t.append(" RTOS: ", style="")
            t.append("● running\n", style="bold green")
        else:
            t.append(" RTOS: ", style="")
            t.append(f"○ {state}\n", style="bold red")
        t.append(
            f" CPU:{s.get('cpu_online', '?')}+{s.get('cpu_offline', '?')}  "
            f"TVM:{s.get('tvm_procs', '?')}\n"
        )
        tcp = s.get("tcp_server", "0")
        t.append(" TCP Server: ", style="")
        if tcp != "0":
            t.append("●", style="bold green")
        else:
            t.append("✗", style="bold red")
        tong = s.get("tongsuo", "?")
        t.append("  Tongsuo: ", style="")
        if tong == "ok":
            t.append("✓\n", style="bold green")
        else:
            t.append("✗\n", style="bold red")
        t.append(
            f" RAM:{s.get('mem_used', '?')}/{s.get('mem_total', '?')}M  "
            f"Temp:{s.get('temp_c', '?')}°C\n"
        )
        t.append(f" IP:{s.get('ts_ip', '?')}")

        return t


# ── 主应用 ──

class MLKEMDemoApp(App):
    """ML-KEM 安全语义通信 TUI 演示"""

    TITLE = "ML-KEM 后量子安全语义通信"
    SUB_TITLE = "集创赛 2026 · 飞腾派赛道"

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }
    #status-bar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 2;
    }
    #workspace {
        height: 1fr;
        margin: 0 1;
    }
    #sidebar {
        width: 34;
        height: 1fr;
    }
    #config-panel {
        height: 1fr;
        border: round $primary-background-darken-1;
        padding: 0 1;
    }
    #board-panel {
        height: 8;
        border: round $primary-background-darken-1;
        padding: 0 1;
        margin-top: 1;
    }
    #settings-actions {
        height: 10;
        border: round $primary-background-darken-1;
        padding: 1 1;
        margin-top: 1;
    }
    #main-content {
        width: 1fr;
        height: 1fr;
        margin-left: 1;
    }
    #cards-grid {
        height: 1fr;
    }
    #cards-row-top {
        height: 5fr;
    }
    #cards-row-bottom {
        height: 3fr;
        margin-top: 1;
    }
    #sequence-panel {
        width: 8fr;
        border: round $primary-background-darken-1;
        padding: 0 1;
    }
    #preflight-panel {
        width: 5fr;
        border: round $primary-background-darken-1;
        padding: 0 1;
        margin-left: 1;
    }
    #control-panel {
        width: 1fr;
        border: round $primary-background-darken-1;
        padding: 0 1;
    }
    #history-panel {
        width: 1fr;
        border: round $primary-background-darken-1;
        padding: 0 1;
        margin-left: 1;
    }
    #log-panel {
        border: round $primary-background-darken-1;
        margin-top: 1;
        padding: 0;
        height: 1fr;
    }
    #log-content {
        height: 1fr;
    }
    #button-bar {
        dock: bottom;
        height: 3;
        margin: 0 1;
        padding: 0;
    }
    .btn {
        margin: 0 1;
        min-width: 16;
    }
    .sidebar-btn {
        width: 1fr;
        margin: 0 0 1 0;
    }
    .label-dim {
        color: $text-disabled;
    }
    .config-group {
        margin-bottom: 1;
    }
    Input {
        width: 1fr;
        margin-bottom: 1;
    }
    RadioSet {
        width: 1fr;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出", priority=True),
        Binding("h", "show_help", "帮助"),
        Binding("f1", "show_help", "帮助"),
        Binding("s", "send_test", "发送测试"),
        Binding("c", "connect", "连接"),
        Binding("d", "disconnect", "断开"),
        Binding("b", "bringup_remote", "拉起派端"),
        Binding("e", "export_session", "导出"),
    ]

    connected = reactive(False)

    def __init__(self, target_host=None, target_port=9527, board_host=None, **kwargs):
        super().__init__(**kwargs)
        self._target_host = target_host
        self._target_port = target_port
        self._board_host = board_host or target_host
        self._sim_server = None
        self._backend = None
        self._auth_capabilities: dict[str, str] = {}
        self._records = []
        self._log_history: list[str] = []
        self._preflight_snapshot: dict[str, Any] = {}
        self._last_export_info: dict[str, Any] = {}
        self._last_connection: ConnectionConfig | None = None
        self._last_auth_bundle: AuthBundle | None = None
        self._last_suite: CipherSuite | None = None
        self._last_kem_param: str = "768"
        self._remote_runtime: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="workspace"):
            with Vertical(id="sidebar"):
                with VerticalScroll(id="config-panel"):
                    yield Label("连接配置", classes="label-dim")
                    initial_local = not self._target_host or self._target_host in {"127.0.0.1", "localhost"}
                    local_endpoint = (
                        f"{self._target_host}:{self._target_port}"
                        if initial_local and self._target_host
                        else LOCAL_LOOPBACK_DEFAULT
                    )
                    tailscale_host = (
                        self._target_host
                        if self._target_host and not initial_local
                        else (self._board_host or TAILSCALE_DEFAULT_HOST)
                    )
                    with RadioSet(id="connection-mode-select", classes="config-group"):
                        yield RadioButton("本机回环", value=initial_local)
                        yield RadioButton("Tailscale连接", value=not initial_local)
                        yield RadioButton("USRP连接")

                    with Container(id="local-config", classes="config-group"):
                        yield Label("本机回环参数", classes="label-dim")
                        yield Input(
                            value=local_endpoint,
                            placeholder="IP:端口，例如 127.0.0.1:9527",
                            id="input-loopback-endpoint",
                        )

                    with Container(id="tailscale-config", classes="config-group"):
                        yield Label("Tailscale 参数", classes="label-dim")
                        yield Input(
                            value=tailscale_host,
                            placeholder="SSH IP 地址",
                            id="input-ts-host",
                        )
                        yield Input(
                            value=TAILSCALE_DEFAULT_USER,
                            placeholder="用户名",
                            id="input-ts-user",
                        )
                        yield Input(
                            value=TAILSCALE_DEFAULT_PASSWORD,
                            placeholder="密码",
                            password=True,
                            id="input-ts-password",
                        )

                    yield Label("KEM 参数", classes="label-dim")
                    with RadioSet(id="kem-select", classes="config-group"):
                        yield RadioButton("ML-KEM-512")
                        yield RadioButton("ML-KEM-768", value=True)
                        yield RadioButton("ML-KEM-1024")
                    yield Label("AEAD 套件", classes="label-dim")
                    with RadioSet(id="suite-select", classes="config-group"):
                        yield RadioButton("AES-256-GCM")
                        yield RadioButton("SM4-128-GCM", value=True)
                    yield Label("认证模式", classes="label-dim")
                    with RadioSet(id="auth-select", classes="config-group"):
                        yield RadioButton("关闭认证", value=True)
                        yield RadioButton("SM2 + ML-DSA")
                        yield RadioButton("SM2_ONLY")
                        yield RadioButton("MLDSA_ONLY")

                with Container(id="board-panel"):
                    yield BoardStatusPanel(
                        board_host=(tailscale_host if not initial_local else None),
                        board_user=TAILSCALE_DEFAULT_USER,
                        board_password=TAILSCALE_DEFAULT_PASSWORD,
                    )

                with Vertical(id="settings-actions"):
                    yield Button("连接 (c)", id="btn-connect", variant="success", classes="sidebar-btn")
                    yield Button("拉起派端 (b)", id="btn-bringup", variant="primary", classes="sidebar-btn")
                    yield Button("断开 (d)", id="btn-disconnect", variant="error", classes="sidebar-btn")

            with Vertical(id="main-content"):
                with Vertical(id="cards-grid"):
                    with Horizontal(id="cards-row-top"):
                        with Container(id="sequence-panel"):
                            yield SequenceDiagram()
                        with Container(id="preflight-panel"):
                            yield PreflightPanel()
                    with Horizontal(id="cards-row-bottom"):
                        with Container(id="control-panel"):
                            yield ControlAuthPanel()
                        with Container(id="history-panel"):
                            yield HistoryPanel()

                with Vertical(id="log-panel"):
                    yield RichLog(id="log-content", highlight=True, markup=True)

        # 按钮栏
        with Horizontal(id="button-bar"):
            yield Button("运行控制/认证测试 (s)", id="btn-test",
                         variant="primary", classes="btn")
            yield Button("帮助 (h / F1)", id="btn-help",
                         variant="default", classes="btn")
            yield Button("清空日志", id="btn-clear",
                         variant="default", classes="btn")
            yield Button("退出 (q)", id="btn-quit",
                         variant="default", classes="btn")

        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log-content", RichLog)
        self._auth_capabilities = detect_auth_capabilities()
        self._sync_default_radio_highlights()
        self._sync_connection_mode_ui()
        try:
            self._backend = get_backend("768")
            self._write_log(f"[bold]KEM 后端:[/bold] {self._backend.name}")
        except Exception as exc:
            self._backend = None
            self._write_log(f"[bold red]KEM 初始化失败:[/bold red] {exc}")
        self._write_log(
            "[bold]认证能力:[/bold] "
            f"SM2={self._auth_capabilities.get('sm2', '?')} | "
            f"ML-DSA={self._auth_capabilities.get('mldsa', '?')}"
        )
        if self._target_host:
            self._write_log(f"[bold]目标:[/bold] {self._target_host}:{self._target_port}")
        else:
            self._write_log("[dim]模拟模式 — 按 c 启动本地控制/认证试验台[/dim]")
        self._write_log("")
        self.query_one("#log-content").focus()

    def _write_log(self, message: str, *, store: bool = True) -> None:
        self.query_one("#log-content", RichLog).write(message)
        if store:
            plain = strip_markup(message).strip()
            if plain:
                self._log_history.append(f"{ts()} {plain}")
                self._log_history = self._log_history[-120:]

    def _mask_secret(self, value: str) -> str:
        if not value:
            return ""
        return "*" * min(max(len(value), 4), 12)

    def _store_runtime_context(
        self,
        *,
        connection: ConnectionConfig,
        kem_param: str,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> None:
        self._last_connection = connection
        self._last_kem_param = kem_param
        self._last_suite = suite
        self._last_auth_bundle = auth_bundle

    def _session_export_root(self) -> Path:
        root = _PROJECT_ROOT / "artifacts" / "tui_sessions"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _probe_tcp(self, host: str, port: int, timeout_sec: float = 1.5) -> tuple[bool, str]:
        try:
            with socket.create_connection((host, port), timeout=timeout_sec):
                return True, f"{host}:{port} 可达"
        except Exception as exc:
            return False, f"{host}:{port} 不可达 ({exc})"

    def _ssh_base_command(self, connection: ConnectionConfig) -> list[str]:
        return [
            "sshpass", "-p", connection.board_password,
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=no",
            "-o", "PreferredAuthentications=password,keyboard-interactive",
            "-o", "ConnectTimeout=5",
            f"{connection.board_user}@{connection.board_host}",
        ]

    def _run_ssh(
        self,
        connection: ConnectionConfig,
        remote_cmd: str,
        *,
        timeout_sec: float = 15.0,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*self._ssh_base_command(connection), remote_cmd],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )

    def _run_scp_to_remote(
        self,
        connection: ConnectionConfig,
        local_path: Path,
        remote_path: str,
        *,
        timeout_sec: float = 15.0,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "sshpass", "-p", connection.board_password,
                "scp",
                "-O",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=5",
                str(local_path),
                f"{connection.board_user}@{connection.board_host}:{remote_path}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )

    def _remote_runtime_signature(
        self,
        connection: ConnectionConfig,
        kem_param: str,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> tuple[str, str, str, str, str]:
        return (
            connection.board_host,
            connection.board_user,
            kem_param,
            suite.value,
            auth_bundle.policy.value if auth_bundle.enabled and auth_bundle.policy is not None else "OFF",
        )

    def _sync_remote_tui_server(self, connection: ConnectionConfig) -> str:
        if not LOCAL_TUI_REMOTE_SERVER_PATH.is_file():
            raise RuntimeError(f"TUI 远端 helper 不存在: {LOCAL_TUI_REMOTE_SERVER_PATH}")
        result = self._run_scp_to_remote(
            connection,
            LOCAL_TUI_REMOTE_SERVER_PATH,
            REMOTE_TUI_SERVER_PATH,
            timeout_sec=20.0,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"同步远端 helper 失败: {detail or f'rc={result.returncode}'}")
        chmod_result = self._run_ssh(
            connection,
            f"chmod 755 {shlex.quote(REMOTE_TUI_SERVER_PATH)}",
            timeout_sec=8.0,
        )
        if chmod_result.returncode != 0:
            detail = (chmod_result.stderr or chmod_result.stdout or "").strip()
            raise RuntimeError(f"设置远端 helper 权限失败: {detail or f'rc={chmod_result.returncode}'}")
        self._write_log(f"[dim]已同步 TUI 远端 helper: {REMOTE_TUI_SERVER_PATH}[/dim]")
        return REMOTE_TUI_SERVER_PATH

    def _fetch_remote_bytes(
        self,
        connection: ConnectionConfig,
        remote_path: str,
    ) -> bytes:
        remote_python = "/usr/bin/env python3"
        payload = (
            "import base64\n"
            "from pathlib import Path\n"
            f"path = Path({remote_path!r}).expanduser()\n"
            "data = path.read_bytes()\n"
            "print(base64.b64encode(data).decode('ascii'))\n"
        )
        remote_cmd = f"{remote_python} -c {shlex.quote(payload)}"
        result = self._run_ssh(connection, remote_cmd, timeout_sec=12.0)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"读取远端文件失败: {remote_path} ({detail or f'rc={result.returncode}'})")
        try:
            return base64.b64decode(result.stdout.strip().encode("ascii"))
        except Exception as exc:
            raise RuntimeError(f"远端文件解码失败: {remote_path}") from exc

    def _ensure_remote_service(
        self,
        connection: ConnectionConfig,
        kem_param: str,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> tuple[str, int]:
        signature = self._remote_runtime_signature(connection, kem_param, suite, auth_bundle)
        if self._remote_runtime.get("signature") == signature:
            cached_port = int(self._remote_runtime.get("port") or 0)
            if cached_port > 0:
                reachable, _ = self._probe_tcp(connection.host, cached_port)
                if reachable:
                    self._write_log(
                        f"[dim]复用派端服务: {connection.host}:{cached_port}[/dim]"
                    )
                    return connection.host, cached_port

        suite_name = "AES_256_GCM" if suite == CipherSuite.AES_256_GCM else "SM4_GCM"
        auth_enabled = "1" if auth_bundle.enabled else "0"
        sig_policy = auth_bundle.policy.value if auth_bundle.enabled and auth_bundle.policy is not None else "OFF"
        remote_server_path = self._sync_remote_tui_server(connection)
        self._write_log(
            f"[dim]通过 SSH 拉起派端 tcp_server... suite={suite.value} auth={auth_bundle.display_name}[/dim]"
        )
        remote_cmd = f"""
set -e
PREFERRED_PORT={int(connection.port)}
SUITE={shlex.quote(suite_name)}
KEM_PARAM={shlex.quote(kem_param)}
AUTH_ENABLED={auth_enabled}
SIG_POLICY={shlex.quote(sig_policy)}
SERVER_ID={shlex.quote(REMOTE_DEMO_SERVER_ID)}
OUTPUT_DIR={shlex.quote(REMOTE_OUTPUT_DIR)}
LOG_PATH={shlex.quote(REMOTE_LOG_PATH)}
PID_PATH={shlex.quote(REMOTE_PID_PATH)}
PORT_PATH={shlex.quote(REMOTE_PORT_PATH)}
SCRIPT_PATH={shlex.quote(remote_server_path)}
if [ ! -f "$SCRIPT_PATH" ]; then
  echo "status=error"
  echo "detail=no_tui_remote_helper"
  exit 3
fi
PYTHON_BIN=""
for candidate in {' '.join(shlex.quote(path) for path in REMOTE_PYTHON_CANDIDATES)}; do
  if [ "$candidate" = "python3" ]; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3)"
      break
    fi
  elif [ -x "$candidate" ]; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  echo "status=error"
  echo "detail=no_python"
  exit 4
fi
PORT="$("$PYTHON_BIN" -c 'import socket, sys
preferred=int(sys.argv[1])
def reserve(port):
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError:
        sock.close()
        return None
    actual = sock.getsockname()[1]
    sock.close()
    return actual
port = reserve(preferred)
if port is None:
    port = reserve(0)
if port is None:
    raise SystemExit(2)
print(port)
' "$PREFERRED_PORT")"
mkdir -p "$OUTPUT_DIR"
: > "$LOG_PATH"
if [ -f "$PID_PATH" ]; then
  OLD_PID="$(cat "$PID_PATH" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    CMDLINE="$(tr '\\0' ' ' </proc/$OLD_PID/cmdline 2>/dev/null || true)"
    case "$CMDLINE" in
      *"$SCRIPT_PATH"*)
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
        ;;
    esac
  fi
fi
OQS_ROOT=""
for candidate in {' '.join(shlex.quote(path) for path in REMOTE_OQS_ROOT_CANDIDATES)}; do
  if [ -d "$candidate/lib" ] && [ -f "$candidate/lib/liboqs.so" ]; then
    OQS_ROOT="$candidate"
    break
  fi
done
export LD_LIBRARY_PATH="/usr/local/tongsuo/lib:/usr/local/tongsuo/lib64:${{LD_LIBRARY_PATH:-}}"
if [ -n "$OQS_ROOT" ]; then
  export OQS_INSTALL_PATH="$OQS_ROOT"
  export LD_LIBRARY_PATH="$OQS_ROOT/lib:$LD_LIBRARY_PATH"
fi
export TONGSUO_KEM_BRIDGE="${{TONGSUO_KEM_BRIDGE:-/usr/local/tongsuo/lib/libtongsuo_kem_bridge.so}}"
if [ -z "${{TONGSUO_SIG_BRIDGE:-}}" ]; then
  for candidate in {' '.join(shlex.quote(path) for path in REMOTE_SIG_BRIDGE_CANDIDATES)}; do
    if [ -f "$candidate" ]; then
      export TONGSUO_SIG_BRIDGE="$candidate"
      break
    fi
  done
fi
if [ "$AUTH_ENABLED" = "1" ]; then
  export MLKEM_AUTH_ENABLED=1
  export MLKEM_AUTH_SERVER_ID="$SERVER_ID"
  export MLKEM_AUTH_SIG_POLICY="$SIG_POLICY"
  export MLKEM_AUTH_SERVER_SM2_KEY={shlex.quote(REMOTE_SM2_KEY_PATH)}
  export MLKEM_AUTH_SERVER_SM2_PUB={shlex.quote(REMOTE_SM2_PUB_PATH)}
  export MLKEM_AUTH_SERVER_MLDSA_KEY={shlex.quote(REMOTE_MLDSA_KEY_PATH)}
  export MLKEM_AUTH_SERVER_MLDSA_PUB={shlex.quote(REMOTE_MLDSA_PUB_PATH)}
else
  unset MLKEM_AUTH_ENABLED MLKEM_AUTH_SIG_POLICY MLKEM_AUTH_SERVER_SM2_KEY MLKEM_AUTH_SERVER_SM2_PUB MLKEM_AUTH_SERVER_MLDSA_KEY MLKEM_AUTH_SERVER_MLDSA_PUB
fi
nohup "$PYTHON_BIN" "$SCRIPT_PATH" --host 0.0.0.0 --port "$PORT" --output-dir "$OUTPUT_DIR" --suite "$SUITE" --kem "$KEM_PARAM" >"$LOG_PATH" 2>&1 </dev/null &
PID=$!
echo "$PID" > "$PID_PATH"
echo "$PORT" > "$PORT_PATH"
sleep 1
if "$PYTHON_BIN" -c 'import socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket()
sock.settimeout(1.0)
sock.connect((host, port))
sock.close()
' 127.0.0.1 "$PORT" >/dev/null 2>&1; then
  echo "status=started"
  echo "port=$PORT"
  echo "pid=$PID"
  echo "script=$SCRIPT_PATH"
  echo "python=$PYTHON_BIN"
else
  echo "status=error"
  echo "detail=start_failed"
  echo "port=$PORT"
  echo "pid=$PID"
  tail -n 20 "$LOG_PATH" 2>/dev/null || true
  exit 5
fi
"""
        result = self._run_ssh(connection, remote_cmd, timeout_sec=20.0)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"派端服务拉起失败: {detail or f'rc={result.returncode}'}")

        metadata: dict[str, str] = {}
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            metadata[key.strip()] = value.strip()

        actual_port = int(metadata.get("port") or connection.port)
        self._remote_runtime = {
            "signature": signature,
            "host": connection.host,
            "port": actual_port,
            "pid": metadata.get("pid", ""),
            "script": metadata.get("script", ""),
            "python": metadata.get("python", ""),
        }
        self._write_log(
            f"[dim]派端服务: {connection.host}:{actual_port} "
            f"script={metadata.get('script', '?')}[/dim]"
        )
        return connection.host, actual_port

    def _update_preflight_panel(self, snapshot: dict[str, Any]) -> None:
        self._preflight_snapshot = dict(snapshot)
        panel = self.query_one(PreflightPanel)
        panel.snapshot = dict(snapshot)
        panel.refresh(layout=True)

    def _preflight_aux_snapshot(self) -> dict[str, str]:
        board_state = dict(self.query_one(BoardStatusPanel).board_status or {})
        control_state = dict(self.query_one(ControlAuthPanel).state or {})
        export_age = age_text(self._last_export_info.get("_export_monotonic")) if self._last_export_info else "未导出"
        export_path = self._last_export_info.get("json_path") if self._last_export_info else ""
        return {
            "board_age": age_text(board_state.get("_observed_monotonic")),
            "control_age": age_text(control_state.get("_snapshot_monotonic")),
            "export_age": export_age,
            "export_path": str(export_path or ""),
        }

    def _run_preflight(
        self,
        *,
        connection: ConnectionConfig,
        kem_param: str,
        backend: Any,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> dict[str, Any]:
        checks: list[dict[str, str]] = []

        def add(label: str, status: str, detail: str) -> None:
            checks.append({"label": label, "status": status, "detail": detail})

        export_root = self._session_export_root()
        add("Python", "ok", sys.executable)
        if backend is not None:
            add("KEM", "ok", f"{backend.name} / {kem_param}")
        else:
            add("KEM", "fail", f"ML-KEM-{kem_param} 后端不可用")

        oqs_path = os.environ.get("OQS_INSTALL_PATH", "")
        if oqs_path and Path(oqs_path).exists():
            add("OQS", "ok", oqs_path)
        else:
            add("OQS", "warn", "未显式设置 OQS_INSTALL_PATH，依赖当前运行环境")

        if os.access(export_root, os.W_OK):
            add("导出目录", "ok", str(export_root))
        else:
            add("导出目录", "fail", f"{export_root} 不可写")

        if auth_bundle.enabled:
            add(
                "认证",
                "ok",
                f"{auth_bundle.display_name} / SM2={auth_bundle.sm2_name} / ML-DSA={auth_bundle.mldsa_name}",
            )
        else:
            add("认证", "warn", "当前关闭认证，仅验证 KEM + AEAD")

        if connection.mode == "local":
            reachable, detail = self._probe_tcp(connection.host, connection.port)
            add("本机回环", "ok" if reachable else "fail", detail)
        elif connection.mode == "tailscale":
            sshpass_path = shutil.which("sshpass")
            add("sshpass", "ok" if sshpass_path else "fail", sshpass_path or "未安装 sshpass")
            ssh_ok, ssh_detail = self._probe_tcp(connection.board_host, 22)
            add("SSH", "ok" if ssh_ok else "warn", ssh_detail if ssh_ok else f"{ssh_detail}，当前仅表示派端暂未就绪")
            data_ok, data_detail = self._probe_tcp(connection.host, connection.port)
            add("数据端口", "ok" if data_ok else "warn", data_detail if data_ok else f"{data_detail}，当前仅表示远端服务暂未拉起")
            if not connection.board_password:
                add("派端口令", "warn", "密码为空，SSH 面板轮询会失败")
            else:
                add("派端口令", "ok", f"{connection.board_user}@{connection.board_host} / {self._mask_secret(connection.board_password)}")
        else:
            add("USRP", "warn", "当前未实现，已回退到本机回环")

        overall = "ok"
        if any(item["status"] == "fail" for item in checks):
            overall = "fail"
        elif any(item["status"] == "warn" for item in checks):
            overall = "warn"

        snapshot = {
            "overall": overall,
            "checked_at": now_iso(),
            "_checked_monotonic": time.monotonic(),
            "connection_label": connection.label,
            "suite": suite.value,
            "checks": checks,
        }
        self._update_preflight_panel(snapshot)
        return snapshot

    def _export_session(self, *, reason: str, error: str = "") -> dict[str, Any]:
        export_root = self._session_export_root()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = export_root / f"tui_session_{stamp}.json"
        md_path = export_root / f"tui_session_{stamp}.md"

        connection = self._last_connection
        auth_bundle = self._last_auth_bundle
        board_state = dict(self.query_one(BoardStatusPanel).board_status or {})
        control_state = dict(self.query_one(ControlAuthPanel).state or {})
        latest_record = dict(self._records[-1]) if self._records else {}
        payload = {
            "generated_at": now_iso(),
            "reason": reason,
            "error": error,
            "connection": {
                "mode": connection.mode if connection else "",
                "label": connection.label if connection else "",
                "host": connection.host if connection else "",
                "port": connection.port if connection else 0,
                "board_host": connection.board_host if connection else "",
                "board_user": connection.board_user if connection else "",
                "board_password": self._mask_secret(connection.board_password) if connection else "",
            },
            "crypto": {
                "kem_param": self._last_kem_param,
                "backend": getattr(self._backend, "name", "unknown"),
                "suite": self._last_suite.value if self._last_suite else "",
                "auth_display": auth_bundle.display_name if auth_bundle else "",
                "auth_enabled": bool(auth_bundle.enabled) if auth_bundle else False,
                "auth_policy": auth_bundle.policy.value if auth_bundle and auth_bundle.policy else "OFF",
            },
            "preflight": dict(self._preflight_snapshot),
            "board_status": board_state,
            "control_state": control_state,
            "latest_record": latest_record,
            "history": list(self._records[-8:]),
            "log_tail": list(self._log_history[-40:]),
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        preflight_lines = []
        for item in payload["preflight"].get("checks", []):
            preflight_lines.append(f"- [{item['status'].upper()}] {item['label']}: {item['detail']}")
        history_summary = (
            f"- latest: handshake={latest_record.get('handshake_ms', 0):.1f} ms, "
            f"control={latest_record.get('control_ms', 0):.1f} ms, "
            f"encrypt={latest_record.get('encrypt_ms', 0):.1f} ms, "
            f"ack={latest_record.get('ack_ms', 0):.1f} ms, "
            f"sha={'OK' if latest_record.get('sha_match') else 'FAIL'}"
            if latest_record
            else "- latest: n/a"
        )
        md_lines = [
            "# TUI 会话导出",
            "",
            f"- 时间: {payload['generated_at']}",
            f"- 原因: {reason}",
            f"- 连接: {payload['connection']['label'] or '-'}",
            f"- KEM: {payload['crypto']['backend']} / {payload['crypto']['kem_param']}",
            f"- 套件: {payload['crypto']['suite']}",
            f"- 认证: {payload['crypto']['auth_display'] or '关闭认证'}",
            f"- 错误: {error or '-'}",
            "",
            "## 自检",
            *preflight_lines,
            "",
            "## 最新指标",
            history_summary,
            "",
            "## 控制面",
            f"- Guard: {control_state.get('guard_state', 'UNKNOWN')}",
            f"- Fault: {control_state.get('last_fault_code', 'UNKNOWN')}",
            f"- 快照年龄: {age_text(control_state.get('_snapshot_monotonic'))}",
            "",
            "## 派端状态",
            f"- 最近探测: {age_text(board_state.get('_observed_monotonic'))}",
            f"- RTOS: {board_state.get('rproc_state', '?')}",
            f"- TCP Server: {board_state.get('tcp_server', '?')}",
            "",
            "## 日志摘录",
            "```text",
            *payload["log_tail"],
            "```",
            "",
        ]
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        self._last_export_info = {
            "json_path": str(json_path),
            "md_path": str(md_path),
            "reason": reason,
            "_export_monotonic": time.monotonic(),
            "exported_at": now_iso(),
        }
        self._update_preflight_panel(dict(self._preflight_snapshot or {}))
        return self._last_export_info

    # ── 按钮事件 ──

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-connect":
            self.action_connect()
        elif bid == "btn-bringup":
            self.action_bringup_remote()
        elif bid == "btn-disconnect":
            self.action_disconnect()
        elif bid == "btn-test":
            self.action_send_test()
        elif bid == "btn-help":
            self.action_show_help()
        elif bid == "btn-clear":
            self.query_one("#log-content", RichLog).clear()
        elif bid == "btn-quit":
            self.exit()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "connection-mode-select":
            return
        selected_mode = self._selected_connection_mode()
        if selected_mode == "usrp":
            self._write_log("[yellow]USRP 连接：敬请期待，当前回退到本机回环。[/yellow]")
            self._force_connection_mode("local")
            return
        self._sync_connection_mode_ui()

    # ── 选择与状态辅助 ──

    def _selected_connection_mode(self) -> str:
        index = self.query_one("#connection-mode-select", RadioSet).pressed_index
        if index is None or index < 0 or index >= len(CONNECTION_MODE_OPTIONS):
            return "local"
        return CONNECTION_MODE_OPTIONS[index]

    def _sync_default_radio_highlights(self) -> None:
        for radio_set in self.query(RadioSet):
            if radio_set.pressed_index >= 0:
                radio_set._selected = radio_set.pressed_index

    def _force_connection_mode(self, mode: str) -> None:
        radio_set = self.query_one("#connection-mode-select", RadioSet)
        buttons = list(radio_set.query(RadioButton))
        mode_index = CONNECTION_MODE_OPTIONS.index(mode)
        target_button = buttons[mode_index]
        with radio_set.prevent(RadioSet.Changed, RadioButton.Changed):
            if radio_set.pressed_button is not None and radio_set.pressed_button != target_button:
                radio_set.pressed_button.value = False
            target_button.value = True
        radio_set._pressed_button = target_button
        radio_set._selected = mode_index
        self._sync_connection_mode_ui()

    def _sync_connection_mode_ui(self) -> None:
        mode = self._selected_connection_mode()
        self.query_one("#local-config", Container).display = mode == "local"
        self.query_one("#tailscale-config", Container).display = mode == "tailscale"

    def _set_local_endpoint_input(self, host: str, port: int) -> None:
        self.query_one("#input-loopback-endpoint", Input).value = f"{host}:{port}"

    def _parse_host_port(self, raw_value: str) -> tuple[str, int]:
        value = str(raw_value or "").strip()
        if not value or ":" not in value:
            raise ValueError("本机回环请输入 IP:端口，例如 127.0.0.1:9527")
        host, port_text = value.rsplit(":", 1)
        host = host.strip()
        port = int(port_text.strip())
        if not host:
            raise ValueError("本机回环地址不能为空")
        if port <= 0 or port > 65535:
            raise ValueError("端口必须在 1-65535 之间")
        return host, port

    def _resolve_connection_config(self) -> ConnectionConfig:
        mode = self._selected_connection_mode()
        if mode == "local":
            host, port = self._parse_host_port(
                self.query_one("#input-loopback-endpoint", Input).value
            )
            return ConnectionConfig(
                mode="local",
                host=host,
                port=port,
                label=f"本机回环 {host}:{port}",
            )

        tailscale_host = self.query_one("#input-ts-host", Input).value.strip() or TAILSCALE_DEFAULT_HOST
        tailscale_user = self.query_one("#input-ts-user", Input).value.strip() or TAILSCALE_DEFAULT_USER
        tailscale_password = self.query_one("#input-ts-password", Input).value or TAILSCALE_DEFAULT_PASSWORD
        return ConnectionConfig(
            mode="tailscale",
            host=tailscale_host,
            port=TAILSCALE_DEFAULT_PORT,
            board_host=tailscale_host,
            board_user=tailscale_user,
            board_password=tailscale_password,
            label=f"Tailscale {tailscale_host}:{TAILSCALE_DEFAULT_PORT}",
        )

    def _selected_kem_param(self) -> str:
        index = self.query_one("#kem-select", RadioSet).pressed_index
        if index is None or index < 0 or index >= len(KEM_PARAM_OPTIONS):
            return "768"
        return KEM_PARAM_OPTIONS[index]

    def _selected_suite(self) -> CipherSuite:
        suite_idx = self.query_one("#suite-select", RadioSet).pressed_index
        return CipherSuite.AES_256_GCM if suite_idx == 0 else CipherSuite.SM4_GCM

    def _selected_auth_option(self) -> tuple[str, str, SigPolicy | None]:
        index = self.query_one("#auth-select", RadioSet).pressed_index
        if index is None or index < 0 or index >= len(AUTH_MODE_OPTIONS):
            return AUTH_MODE_OPTIONS[0]
        return AUTH_MODE_OPTIONS[index]

    def _build_auth_bundle(self, connection: ConnectionConfig) -> AuthBundle:
        label, backend_mode, policy = self._selected_auth_option()
        if backend_mode == "off" or policy is None:
            return AuthBundle(display_name=label, enabled=False, backend_mode="off")

        need_sm2 = policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY}
        need_mldsa = policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY}
        sm2_backend = get_sm2_backend() if need_sm2 else None
        mldsa_backend = get_mldsa_backend() if need_mldsa else None

        if connection.mode == "local":
            sm2_pk = sm2_sk = None
            mldsa_pk = mldsa_sk = None
            if sm2_backend is not None:
                sm2_pk, sm2_sk = sm2_backend.keygen()
            if mldsa_backend is not None:
                mldsa_pk, mldsa_sk = mldsa_backend.keygen()

            fingerprint = hashlib.sha256((sm2_pk or b"") + (mldsa_pk or b"")).hexdigest()[:12]

            return AuthBundle(
                display_name=label,
                enabled=True,
                backend_mode=backend_mode,
                policy=policy,
                sm2_backend=sm2_backend,
                mldsa_backend=mldsa_backend,
                client_config=IdentityConfig(
                    role=SessionRole.INITIATOR,
                    server_id=SIM_SERVER_ID,
                    peer_sm2_pk=sm2_pk,
                    peer_mldsa_pk=mldsa_pk,
                    sig_policy=policy,
                ),
                server_config=IdentityConfig(
                    role=SessionRole.RESPONDER,
                    server_id=SIM_SERVER_ID,
                    server_sm2_sk=sm2_sk,
                    server_sm2_pk=sm2_pk,
                    server_mldsa_sk=mldsa_sk,
                    server_mldsa_pk=mldsa_pk,
                    sig_policy=policy,
                ),
                sm2_name=(sm2_backend.name if sm2_backend is not None else "off"),
                mldsa_name=(mldsa_backend.name if mldsa_backend is not None else "off"),
                fingerprint=fingerprint,
            )

        peer_sm2_pk = self._fetch_remote_bytes(connection, REMOTE_SM2_PUB_PATH) if need_sm2 else None
        peer_mldsa_pk = self._fetch_remote_bytes(connection, REMOTE_MLDSA_PUB_PATH) if need_mldsa else None
        fingerprint = hashlib.sha256((peer_sm2_pk or b"") + (peer_mldsa_pk or b"")).hexdigest()[:12]
        return AuthBundle(
            display_name=label,
            enabled=True,
            backend_mode=backend_mode,
            policy=policy,
            sm2_backend=sm2_backend,
            mldsa_backend=mldsa_backend,
            client_config=IdentityConfig(
                role=SessionRole.INITIATOR,
                server_id=REMOTE_DEMO_SERVER_ID,
                peer_sm2_pk=peer_sm2_pk,
                peer_mldsa_pk=peer_mldsa_pk,
                sig_policy=policy,
            ),
            server_config=None,
            sm2_name=(sm2_backend.name if sm2_backend is not None else "off"),
            mldsa_name=(mldsa_backend.name if mldsa_backend is not None else "off"),
            fingerprint=fingerprint,
        )

    def _initial_control_auth_state(self, bundle: AuthBundle) -> dict[str, Any]:
        return {
            "auth_enabled": bundle.enabled,
            "auth_mode": bundle.backend_mode,
            "auth_label": bundle.display_name,
            "auth_policy": bundle.policy.value if bundle.policy is not None else "OFF",
            "server_id": (
                bundle.client_config.server_id
                if bundle.enabled and bundle.client_config is not None
                else (SIM_SERVER_ID if bundle.enabled else "-")
            ),
            "sm2_backend": bundle.sm2_name,
            "mldsa_backend": bundle.mldsa_name,
            "finished_ok": False,
            "guard_state": "READY",
            "last_fault_code": "NONE",
            "active_job_id": "",
            "job_req_count": 0,
            "job_ack_allow": 0,
            "job_ack_deny": 0,
            "heartbeat_count": 0,
            "heartbeat_ack_count": 0,
            "safe_stop_count": 0,
            "safe_stop_ack_count": 0,
            "_snapshot_at": now_iso(),
            "_snapshot_monotonic": time.monotonic(),
        }

    def _update_control_panel(self, payload: dict[str, Any]) -> None:
        panel = self.query_one(ControlAuthPanel)
        snapshot = dict(payload)
        snapshot["_snapshot_at"] = snapshot.get("_snapshot_at") or now_iso()
        snapshot["_snapshot_monotonic"] = snapshot.get("_snapshot_monotonic") or time.monotonic()
        panel.state = snapshot
        panel.refresh(layout=True)

    def _apply_control_update(self, state: dict[str, Any], payload: dict[str, Any]) -> None:
        for key in (
            "guard_state",
            "last_fault_code",
            "active_job_id",
            "job_req_count",
            "job_ack_allow",
            "job_ack_deny",
            "heartbeat_count",
            "heartbeat_ack_count",
            "safe_stop_count",
            "safe_stop_ack_count",
            "auth_enabled",
            "auth_policy",
            "server_id",
        ):
            if key in payload:
                state[key] = payload.get(key)

    def _ensure_local_sim_server(
        self,
        *,
        host: str,
        port: int,
        kem_param: str,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> tuple[str, int]:
        desired_key = (
            kem_param,
            suite.value,
            auth_bundle.fingerprint,
            host,
            str(port),
        )
        if self._sim_server is not None and self._sim_server.config_key == desired_key:
            return self._sim_server.host, self._sim_server.port
        if self._sim_server is not None:
            self._sim_server.stop()
            self._sim_server = None
        self._write_log(
            f"[dim]启动本地模拟 server... KEM={kem_param} suite={suite.value} "
            f"auth={auth_bundle.display_name} bind={host}:{port}[/dim]"
        )
        try:
            self._sim_server = SimServer(
                host=host,
                port=port,
                kem_param=kem_param,
                suite=suite,
                auth_bundle=auth_bundle,
            )
        except OSError as exc:
            if exc.errno not in ADDR_IN_USE_ERRNOS or port == 0:
                raise
            self._write_log(
                f"[yellow]本机回环端口 {host}:{port} 已被占用，自动切换到空闲端口。[/yellow]"
            )
            self._sim_server = SimServer(
                host=host,
                port=0,
                kem_param=kem_param,
                suite=suite,
                auth_bundle=auth_bundle,
            )
            self._set_local_endpoint_input(self._sim_server.host, self._sim_server.port)
            self._write_log(
                f"[dim]本机回环参数已更新为 {self._sim_server.host}:{self._sim_server.port}[/dim]"
            )
        self._sim_server.start()
        time.sleep(0.3)
        self._write_log(f"[dim]模拟 server: {self._sim_server.host}:{self._sim_server.port}[/dim]")
        return self._sim_server.host, self._sim_server.port

    def _prepare_runtime_context(
        self,
        log: RichLog,
    ) -> tuple[ConnectionConfig, str, Any, CipherSuite, AuthBundle] | None:
        try:
            connection = self._resolve_connection_config()
        except Exception as exc:
            self._write_log(f"[bold red]连接配置无效:[/bold red] {exc}")
            return None

        kem_param = self._selected_kem_param()
        suite = self._selected_suite()
        try:
            backend = get_backend(kem_param)
            self._backend = backend
        except Exception as exc:
            self._write_log(f"[bold red]KEM 后端不可用:[/bold red] {exc}")
            return None

        try:
            auth_bundle = self._build_auth_bundle(connection)
        except Exception as exc:
            self._write_log(f"[bold red]认证模式初始化失败:[/bold red] {exc}")
            return None

        self._store_runtime_context(
            connection=connection,
            kem_param=kem_param,
            suite=suite,
            auth_bundle=auth_bundle,
        )
        return connection, kem_param, backend, suite, auth_bundle

    def _apply_connection(
        self,
        *,
        log: RichLog,
        connection: ConnectionConfig,
        kem_param: str,
        backend: Any,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> None:
        if self.connected:
            self._write_log("[dim]重新应用当前配置...[/dim]")

        if connection.mode == "local":
            actual_host, actual_port = self._ensure_local_sim_server(
                host=connection.host,
                port=connection.port,
                kem_param=kem_param,
                suite=suite,
                auth_bundle=auth_bundle,
            )
            connection.host = actual_host
            connection.port = actual_port
            connection.label = f"本机回环 {actual_host}:{actual_port}"
        else:
            if self._sim_server is not None:
                self._sim_server.stop()
                self._sim_server = None
            actual_host, actual_port = self._ensure_remote_service(
                connection,
                kem_param,
                suite,
                auth_bundle,
            )
            connection.host = actual_host
            connection.port = actual_port
            connection.label = f"Tailscale {actual_host}:{actual_port}"
            if auth_bundle.enabled:
                self._write_log("[dim]远端模式已复用派端现有身份材料完成服务端鉴别。[/dim]")

        self.connected = True
        self._target_host = connection.host
        self._target_port = connection.port
        self._board_host = connection.board_host or None
        self.query_one(BoardStatusPanel).set_board_access(
            connection.board_host or None,
            board_user=connection.board_user,
            board_password=connection.board_password,
        )
        self._update_control_panel(self._initial_control_auth_state(auth_bundle))
        self._write_log(
            f"[bold green]就绪[/bold green] "
            f"conn={connection.label} backend={backend.name} suite={suite.value} auth={auth_bundle.display_name}"
        )
        if connection.board_host:
            self._write_log(f"[dim]飞腾派 SSH: {connection.board_user}@{connection.board_host}[/dim]")
        else:
            self._write_log("[dim]飞腾派 SSH: 未配置（本地模拟模式）[/dim]")

    # ── 连接 ──

    def action_connect(self):
        log = self.query_one("#log-content", RichLog)
        context = self._prepare_runtime_context(log)
        if context is None:
            return
        connection, kem_param, backend, suite, auth_bundle = context
        try:
            self._apply_connection(
                log=log,
                connection=connection,
                kem_param=kem_param,
                backend=backend,
                suite=suite,
                auth_bundle=auth_bundle,
            )
        except Exception as exc:
            self.connected = False
            self._write_log(f"[bold red]连接失败:[/bold red] {exc}")
            self._run_preflight(
                connection=connection,
                kem_param=kem_param,
                backend=backend,
                suite=suite,
                auth_bundle=auth_bundle,
            )
            return
        preflight = self._run_preflight(
            connection=connection,
            kem_param=kem_param,
            backend=backend,
            suite=suite,
            auth_bundle=auth_bundle,
        )
        self._write_log(f"[dim]自检完成: {preflight['overall'].upper()}[/dim]")

    def action_disconnect(self):
        self.connected = False
        if self._sim_server:
            self._sim_server.stop()
        self._sim_server = None
        self._board_host = None
        self._write_log("[yellow]已断开[/yellow]")
        self.query_one(SequenceDiagram).reset()
        self.query_one(ControlAuthPanel).state = {}
        self.query_one(BoardStatusPanel).set_board_access(None)

    def action_bringup_remote(self):
        log = self.query_one("#log-content", RichLog)
        context = self._prepare_runtime_context(log)
        if context is None:
            return
        connection, kem_param, backend, suite, auth_bundle = context
        if connection.mode != "tailscale":
            self._write_log("[yellow]当前不是 Tailscale 模式，无需拉起派端服务。[/yellow]")
            return
        try:
            host, port = self._ensure_remote_service(connection, kem_param, suite, auth_bundle)
        except Exception as exc:
            self._write_log(f"[bold red]派端服务拉起失败:[/bold red] {exc}")
            self._export_session(reason="remote_bringup_failure", error=str(exc))
            return
        connection.host = host
        connection.port = port
        connection.label = f"Tailscale {host}:{port}"
        self._store_runtime_context(
            connection=connection,
            kem_param=kem_param,
            suite=suite,
            auth_bundle=auth_bundle,
        )
        self.query_one(BoardStatusPanel).set_board_access(
            connection.board_host or None,
            board_user=connection.board_user,
            board_password=connection.board_password,
        )
        preflight = self._run_preflight(
            connection=connection,
            kem_param=kem_param,
            backend=backend,
            suite=suite,
            auth_bundle=auth_bundle,
        )
        self._write_log(
            f"[bold green]派端服务已就绪[/bold green] {connection.label}  自检={preflight['overall'].upper()}"
        )

    def action_export_session(self):
        export_info = self._export_session(reason="manual")
        self._write_log(
            f"[bold cyan]会话已导出[/bold cyan] json={export_info['json_path']} md={export_info['md_path']}"
        )

    def action_show_help(self):
        self.push_screen(DemoHelpScreen())

    # ── 发送 ──

    def action_send_test(self):
        log = self.query_one("#log-content", RichLog)
        context = self._prepare_runtime_context(log)
        if context is None:
            return
        connection, kem_param, backend, suite, auth_bundle = context
        try:
            self._apply_connection(
                log=log,
                connection=connection,
                kem_param=kem_param,
                backend=backend,
                suite=suite,
                auth_bundle=auth_bundle,
            )
        except Exception as exc:
            self.connected = False
            self._write_log(f"[bold red]连接失败:[/bold red] {exc}")
            self._export_session(reason="connect_failure", error=str(exc))
            return

        preflight = self._run_preflight(
            connection=connection,
            kem_param=kem_param,
            backend=backend,
            suite=suite,
            auth_bundle=auth_bundle,
        )
        self._write_log(f"[dim]运行前自检: {preflight['overall'].upper()}[/dim]")
        if preflight["overall"] == "fail":
            self._write_log("[bold red]阻断发送[/bold red] 自检未通过，请先处理失败项。")
            self._export_session(reason="preflight_fail", error="运行前自检未通过")
            return

        if connection.mode == "local":
            self._ensure_local_sim_server(
                host=connection.host,
                port=connection.port,
                kem_param=kem_param,
                suite=suite,
                auth_bundle=auth_bundle,
            )
            self._run_local_scripted_test(
                host=connection.host,
                port=self._sim_server.port if self._sim_server else connection.port,
                backend=backend,
                suite=suite,
                auth_bundle=auth_bundle,
            )
            return

        if auth_bundle.enabled:
            self._write_log("[yellow]远端模式当前只保留基础数据测试，控制/认证脚本不发送到派端。[/yellow]")
        self._run_basic_data_test(
            host=connection.host,
            port=connection.port,
            backend=backend,
            suite=suite,
            auth_bundle=auth_bundle,
        )

    def _run_local_scripted_test(
        self,
        *,
        host: str,
        port: int,
        backend: Any,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> None:
        seq = self.query_one(SequenceDiagram)
        latent = simulate_latent()
        latent_sha = hashlib.sha256(latent).hexdigest()
        job_id = f"test-{len(self._records) + 1}"
        meta = json.dumps({
            "job_id": job_id,
            "shape": [1, 3, 64, 64],
            "dtype": "float32",
            "sha256": latent_sha,
            "size": len(latent),
        }).encode()

        self._write_log(f"\n[bold]── 控制/认证试验 #{len(self._records) + 1} ──[/bold]")
        self._write_log(
            f"  KEM={backend.name}  suite={suite.value}  auth={auth_bundle.display_name}"
        )
        self._write_log(f"  生成 latent: [cyan]{len(latent):,}B[/cyan]  Payload 指纹(sha256)=[dim]{latent_sha[:16]}...[/dim]")

        metrics = {"data_bytes": len(latent), "control_ms": 0.0}
        panel_state = self._initial_control_auth_state(auth_bundle)
        self._update_control_panel(panel_state)
        seq.reset()
        seq.phase = "handshake"
        seq.auth_label = panel_state["auth_policy"] if auth_bundle.enabled else ""
        seq.refresh(layout=True)

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(15)
            sock.connect((host, port))
            channel = SecureChannel(sock, SessionRole.INITIATOR, backend, suite)

            with patch_auth_backends(auth_bundle):
                hs_ms = (
                    channel.authenticated_handshake(auth_bundle.client_config)
                    if auth_bundle.enabled
                    else channel.handshake()
                )
            metrics["handshake_ms"] = hs_ms
            seq.pk_sent = True
            seq.ct_received = True
            seq.auth_done = auth_bundle.enabled
            seq.refresh(layout=True)

            panel_state["finished_ok"] = auth_bundle.enabled
            panel_state["server_id"] = channel.peer_server_id or panel_state["server_id"]
            self._update_control_panel(panel_state)
            self._write_log(f"  握手: [yellow]{hs_ms:.1f} ms[/yellow]")
            if auth_bundle.enabled:
                self._write_log(
                    f"  认证: [blue]{auth_bundle.policy.value}[/blue] "
                    f"server_id={channel.peer_server_id or SIM_SERVER_ID}"
                )

            t_ctrl = time.perf_counter()
            job_req = json.dumps({
                "type": "JOB_REQ",
                "job_id": job_id,
                "requested_suite": suite.value,
                "auth_enabled": auth_bundle.enabled,
            }).encode()
            channel.send_encrypted(job_req, aad=CONTROL_JOB_REQ_AAD)
            job_ack = json.loads(channel.recv_encrypted(aad=CONTROL_JOB_ACK_AAD))
            metrics["control_ms"] += (time.perf_counter() - t_ctrl) * 1000
            seq.job_ack = True
            self._apply_control_update(panel_state, job_ack)
            self._update_control_panel(panel_state)
            seq.refresh(layout=True)
            self._write_log(
                f"  JOB_ACK: [cyan]{job_ack.get('decision', '?')}[/cyan] "
                f"guard={job_ack.get('guard_state', '?')}"
            )

            t_ctrl = time.perf_counter()
            hb_req = json.dumps({
                "type": "HEARTBEAT",
                "job_id": job_id,
                "hb_seq": 1,
            }).encode()
            channel.send_encrypted(hb_req, aad=CONTROL_HEARTBEAT_AAD)
            hb_ack = json.loads(channel.recv_encrypted(aad=CONTROL_HEARTBEAT_ACK_AAD))
            metrics["control_ms"] += (time.perf_counter() - t_ctrl) * 1000
            seq.heartbeat_ack = True
            self._apply_control_update(panel_state, hb_ack)
            self._update_control_panel(panel_state)
            seq.refresh(layout=True)
            self._write_log(
                f"  HEARTBEAT_ACK: hb_seq={hb_ack.get('hb_seq', '?')} "
                f"guard={hb_ack.get('guard_state', '?')}"
            )

            channel.send_encrypted(meta, aad=b"metadata")
            t_enc = time.perf_counter()
            channel.send_encrypted(latent, aad=meta)
            metrics["encrypt_ms"] = (time.perf_counter() - t_enc) * 1000
            metrics["overhead_bytes"] = 1 + 12 + 16
            seq.data_sent = True
            seq.refresh(layout=True)
            self._write_log(
                f"  加密发送: [magenta]{len(latent):,}B[/magenta] "
                f"耗时 [magenta]{metrics['encrypt_ms']:.1f} ms[/magenta]"
            )

            t_ack = time.perf_counter()
            ack = json.loads(channel.recv_encrypted(aad=b"ack"))
            metrics["ack_ms"] = (time.perf_counter() - t_ack) * 1000
            seq.ack_received = True
            seq.refresh(layout=True)
            metrics["sha_match"] = bool(ack.get("sha256_match"))
            if metrics["sha_match"]:
                self._write_log(
                    f"  ACK: [bold green]完整性 ✓[/bold green]  "
                    f"对端确认 {ack.get('bytes_received', '?'):,}B"
                )
            else:
                self._write_log("  ACK: [bold red]完整性 ✗[/bold red]")

            t_ctrl = time.perf_counter()
            stop_req = json.dumps({
                "type": "SAFE_STOP",
                "job_id": job_id,
                "requested_by": "tui-host",
            }).encode()
            channel.send_encrypted(stop_req, aad=CONTROL_SAFE_STOP_AAD)
            stop_ack = json.loads(channel.recv_encrypted(aad=CONTROL_SAFE_STOP_ACK_AAD))
            metrics["control_ms"] += (time.perf_counter() - t_ctrl) * 1000
            seq.safe_stop_ack = True
            self._apply_control_update(panel_state, stop_ack)
            self._update_control_panel(panel_state)
            seq.refresh(layout=True)
            self._write_log(
                f"  SAFE_STOP_ACK: guard={stop_ack.get('guard_state', '?')} "
                f"active_job_id={stop_ack.get('active_job_id', '-') or '-'}"
            )

            self._commit_metrics(metrics)
            export_info = self._export_session(reason="test_success")
            self._write_log(
                f"[dim]会话导出: {export_info['json_path']}[/dim]",
                store=False,
            )

        except Exception as exc:
            self._write_log(f"  [bold red]失败:[/bold red] {exc}")
            seq.reset()
            seq.error_msg = str(exc)[:60]
            seq.refresh(layout=True)
            export_info = self._export_session(reason="test_failure", error=str(exc))
            self._write_log(
                f"[dim]失败快照已导出: {export_info['json_path']}[/dim]",
                store=False,
            )
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    def _run_basic_data_test(
        self,
        *,
        host: str,
        port: int,
        backend: Any,
        suite: CipherSuite,
        auth_bundle: AuthBundle,
    ) -> None:
        seq = self.query_one(SequenceDiagram)
        panel_state = self._initial_control_auth_state(auth_bundle if auth_bundle.enabled else AuthBundle(display_name="关闭认证", enabled=False, backend_mode="off"))
        self._update_control_panel(panel_state)

        latent = simulate_latent()
        latent_sha = hashlib.sha256(latent).hexdigest()
        meta = json.dumps({
            "job_id": f"test-{len(self._records) + 1}",
            "shape": [1, 3, 64, 64],
            "dtype": "float32",
            "sha256": latent_sha,
            "size": len(latent),
        }).encode()

        self._write_log(f"\n[bold]── 基础数据测试 #{len(self._records) + 1} ──[/bold]")
        self._write_log(f"  KEM={backend.name}  suite={suite.value}  auth={auth_bundle.display_name}")
        metrics = {"data_bytes": len(latent), "control_ms": 0.0}
        seq.reset()
        seq.phase = "handshake"
        seq.auth_label = panel_state["auth_policy"] if auth_bundle.enabled else ""
        seq.refresh(layout=True)

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(15)
            sock.connect((host, port))
            channel = SecureChannel(sock, SessionRole.INITIATOR, backend, suite)

            with patch_auth_backends(auth_bundle):
                hs_ms = (
                    channel.authenticated_handshake(auth_bundle.client_config)
                    if auth_bundle.enabled and auth_bundle.client_config is not None
                    else channel.handshake()
                )
            metrics["handshake_ms"] = hs_ms
            seq.pk_sent = True
            seq.ct_received = True
            seq.auth_done = auth_bundle.enabled
            seq.refresh(layout=True)
            self._write_log(f"  握手: [yellow]{hs_ms:.1f} ms[/yellow]")
            if auth_bundle.enabled:
                panel_state["finished_ok"] = True
                panel_state["server_id"] = channel.peer_server_id or REMOTE_DEMO_SERVER_ID
                self._update_control_panel(panel_state)
                self._write_log(
                    f"  认证: [blue]{auth_bundle.policy.value}[/blue] "
                    f"server_id={channel.peer_server_id or REMOTE_DEMO_SERVER_ID}"
                )

            channel.send_encrypted(meta, aad=b"metadata")
            t_enc = time.perf_counter()
            channel.send_encrypted(latent, aad=meta)
            metrics["encrypt_ms"] = (time.perf_counter() - t_enc) * 1000
            metrics["overhead_bytes"] = 1 + 12 + 16
            seq.data_sent = True
            seq.refresh(layout=True)

            t_ack = time.perf_counter()
            ack = json.loads(channel.recv_encrypted(aad=b"ack"))
            metrics["ack_ms"] = (time.perf_counter() - t_ack) * 1000
            metrics["sha_match"] = bool(ack.get("sha256_match"))
            seq.ack_received = True
            seq.refresh(layout=True)

            if metrics["sha_match"]:
                self._write_log("  ACK: [bold green]完整性 ✓[/bold green]")
            else:
                self._write_log("  ACK: [bold red]完整性 ✗[/bold red]")

            self._commit_metrics(metrics)
            export_info = self._export_session(reason="test_success")
            self._write_log(
                f"[dim]会话导出: {export_info['json_path']}[/dim]",
                store=False,
            )

        except Exception as exc:
            self._write_log(f"  [bold red]失败:[/bold red] {exc}")
            seq.reset()
            seq.error_msg = str(exc)[:60]
            seq.refresh(layout=True)
            export_info = self._export_session(reason="test_failure", error=str(exc))
            self._write_log(
                f"[dim]失败快照已导出: {export_info['json_path']}[/dim]",
                store=False,
            )
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    def _commit_metrics(self, metrics: dict[str, Any]) -> None:
        self._records.append(dict(metrics))
        history_panel = self.query_one(HistoryPanel)
        history_panel.records = list(self._records)
        history_panel.refresh(layout=True)

    # ── 辅助 ──

    def _set_seq_error(self, msg: str):
        try:
            self.query_one(SequenceDiagram).error_msg = msg
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="ML-KEM 安全语义通信 TUI 演示")
    parser.add_argument("--host", default=None, help="目标地址 (省略则模拟模式)")
    parser.add_argument("--port", type=int, default=9527, help="目标端口")
    parser.add_argument("--board", default=None, help="飞腾派 SSH 地址 (默认同 --host)")
    args = parser.parse_args()

    app = MLKEMDemoApp(
        target_host=args.host,
        target_port=args.port,
        board_host=args.board,
    )
    app.run()


if __name__ == "__main__":
    main()
