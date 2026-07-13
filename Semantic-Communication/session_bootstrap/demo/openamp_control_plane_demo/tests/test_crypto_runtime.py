from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import types
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

import crypto_runtime  # noqa: E402


class CryptoRuntimeTest(unittest.TestCase):
    def _load_repo_tcp_client_module(self):
        script_path = DEMO_ROOT.parents[2] / "scripts" / "tcp_client.py"
        package = types.ModuleType("mlkem_link")
        package.__path__ = []  # type: ignore[attr-defined]
        crypto_mod = types.ModuleType("mlkem_link.crypto")
        crypto_mod.CipherSuite = {"AES_256_GCM": object(), "SM4_GCM": object()}
        kem_mod = types.ModuleType("mlkem_link.kem")
        kem_mod.get_backend = lambda *_args, **_kwargs: SimpleNamespace(name="mock-backend")
        secure_channel_mod = types.ModuleType("mlkem_link.secure_channel")
        secure_channel_mod.SecureChannel = object
        session_mod = types.ModuleType("mlkem_link.session")
        session_mod.SessionRole = object
        auth_mod = types.ModuleType("mlkem_link.auth")
        auth_mod.IdentityConfig = object
        auth_mod.SigPolicy = SimpleNamespace(
            DUAL_REQUIRED=SimpleNamespace(value="DUAL_REQUIRED"),
            SM2_ONLY=SimpleNamespace(value="SM2_ONLY"),
            MLDSA_ONLY=SimpleNamespace(value="MLDSA_ONLY"),
        )

        injected_modules = {
            "mlkem_link": package,
            "mlkem_link.crypto": crypto_mod,
            "mlkem_link.kem": kem_mod,
            "mlkem_link.secure_channel": secure_channel_mod,
            "mlkem_link.session": session_mod,
            "mlkem_link.auth": auth_mod,
        }
        previous = {name: sys.modules.get(name) for name in injected_modules}
        try:
            sys.modules.update(injected_modules)
            spec = importlib.util.spec_from_file_location("_demo_test_tcp_client", script_path)
            self.assertIsNotNone(spec)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            for name, original in previous.items():
                if original is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original

    def test_resolve_local_crypto_client_discovers_sibling_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            current_repo = temp_root / "Semantic-Communication"
            sibling_repo = temp_root / "ICCompetition2026"
            (current_repo / "session_bootstrap").mkdir(parents=True)
            (sibling_repo / "scripts").mkdir(parents=True)
            client_script = sibling_repo / "scripts" / "tcp_client.py"
            client_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            with (
                patch.object(crypto_runtime, "PROJECT_ROOT", current_repo),
                patch.object(crypto_runtime.Path, "cwd", return_value=current_repo),
            ):
                resolved, searched = crypto_runtime.resolve_local_crypto_client({})

        self.assertEqual(resolved, client_script.resolve())
        self.assertIn(client_script.resolve(), searched)

    def test_resolve_local_crypto_client_prefers_runtime_repo_over_legacy_current_repo_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            current_repo = temp_root / "Semantic-Communication"
            sibling_repo = temp_root / "ICCompetition2026"
            (current_repo / "scripts").mkdir(parents=True)
            (current_repo / "session_bootstrap").mkdir(parents=True)
            (sibling_repo / "scripts").mkdir(parents=True)
            (sibling_repo / "mlkem_link").mkdir(parents=True)

            legacy_client = current_repo / "scripts" / "tcp_client.py"
            legacy_client.write_text("# legacy client without auth\n", encoding="utf-8")
            runtime_client = sibling_repo / "scripts" / "tcp_client.py"
            runtime_client.write_text(
                "#!/usr/bin/env python3\n"
                "parser.add_argument('--daemon')\n"
                "parser.add_argument('--count')\n"
                "parser.add_argument('--json-summary')\n",
                encoding="utf-8",
            )

            with (
                patch.object(crypto_runtime, "PROJECT_ROOT", current_repo),
                patch.object(crypto_runtime.Path, "cwd", return_value=current_repo),
            ):
                resolved, searched = crypto_runtime.resolve_local_crypto_client({})

        self.assertEqual(resolved, runtime_client.resolve())
        self.assertIn(runtime_client.resolve(), searched)

    def test_resolve_local_crypto_client_prefers_current_repo_modern_client_over_sibling_legacy_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            current_repo = temp_root / "Semantic-Communication"
            sibling_repo = temp_root / "ICCompetition2026"
            (current_repo / "scripts").mkdir(parents=True)
            (current_repo / "session_bootstrap").mkdir(parents=True)
            (sibling_repo / "scripts").mkdir(parents=True)
            (sibling_repo / "mlkem_link").mkdir(parents=True)

            modern_client = current_repo / "scripts" / "tcp_client.py"
            modern_client.write_text(
                "#!/usr/bin/env python3\n"
                "parser.add_argument('--daemon')\n"
                "parser.add_argument('--count')\n"
                "parser.add_argument('--json-summary')\n"
                "parser.add_argument('--expect-result')\n",
                encoding="utf-8",
            )
            legacy_runtime_client = sibling_repo / "scripts" / "tcp_client.py"
            legacy_runtime_client.write_text(
                "#!/usr/bin/env python3\n"
                "parser.add_argument('--input')\n",
                encoding="utf-8",
            )

            with (
                patch.object(crypto_runtime, "PROJECT_ROOT", current_repo),
                patch.object(crypto_runtime.Path, "cwd", return_value=current_repo),
            ):
                resolved, searched = crypto_runtime.resolve_local_crypto_client({})

        self.assertEqual(resolved, modern_client.resolve())
        self.assertIn(modern_client.resolve(), searched)

    def test_build_remote_crypto_server_command_uses_env_overrides(self) -> None:
        env_values = {
            "MLKEM_REMOTE_PROJECT_ROOT": "/opt/semantic",
            "MLKEM_REMOTE_PYTHON": "/opt/mlkem/bin/python",
            "REMOTE_TVM310_PYTHON": "/opt/tvm-compat/bin/python",
            "REMOTE_TVM_PYTHON": "env FOO=1 /opt/tvm/bin/python",
            "REMOTE_CURRENT_ARTIFACT": "/models/current.so",
            "MLKEM_PORT": "9540",
            "MLKEM_STATUS_PORT": "18080",
            "MLKEM_REMOTE_LOG_PATH": "/tmp/mlkem-server.log",
            "MLKEM_REMOTE_PRELUDE": "export EXTRA_FLAG=1",
            "MLKEM_CIPHER_SUITE": "SM4_GCM",
        }

        command = crypto_runtime.build_remote_crypto_server_command(
            env_values,
            local_server_script=Path("/tmp/local/scripts/tcp_server.py"),
        )

        self.assertIn("/opt/mlkem/bin/python", command)
        self.assertIn("/opt/semantic/scripts/tcp_server.py", command)
        self.assertIn("--port 9540", command)
        self.assertIn("--status-port 18080", command)
        self.assertIn("--artifact-path /models/current.so", command)
        self.assertIn("--tvm-python /opt/tvm/bin/python", command)
        self.assertNotIn("--tvm-python /opt/tvm-compat/bin/python", command)
        self.assertNotIn("--tvm-python env FOO=1 /opt/tvm/bin/python", command)
        self.assertIn("--suite SM4_GCM", command)
        self.assertIn("nohup", command)
        self.assertIn("export EXTRA_FLAG=1", command)

    def test_build_remote_crypto_server_command_exports_auth_env(self) -> None:
        command = crypto_runtime.build_remote_crypto_server_command(
            {
                "MLKEM_REMOTE_SERVER_SCRIPT": "/home/user/tcp_server.py",
                "MLKEM_AUTH_ENABLED": "1",
                "MLKEM_AUTH_SERVER_ID": "phytium-board",
                "MLKEM_AUTH_SIG_POLICY": "DUAL_REQUIRED",
                "MLKEM_AUTH_SERVER_SM2_KEY": "/home/user/keys/server_sm2_identity.key",
                "MLKEM_AUTH_SERVER_SM2_PUB": "/home/user/keys/server_sm2_identity.pub",
                "MLKEM_AUTH_SERVER_MLDSA_KEY": "/home/user/keys/server_mldsa_identity.key",
                "MLKEM_AUTH_SERVER_MLDSA_PUB": "/home/user/keys/server_mldsa_identity.pub",
                "MLKEM_REMOTE_TONGSUO_SIG_BRIDGE": "/home/user/libtongsuo_sig_bridge.so",
                "MLKEM_REMOTE_OQS_INSTALL_PATH": "/home/user/liboqs-dist",
            },
            local_server_script=Path("/tmp/local/scripts/tcp_server.py"),
        )

        self.assertIn("export MLKEM_AUTH_ENABLED=1", command)
        self.assertIn("export MLKEM_AUTH_SERVER_ID=phytium-board", command)
        self.assertIn("export MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED", command)
        self.assertIn("export MLKEM_AUTH_SERVER_SM2_KEY=/home/user/keys/server_sm2_identity.key", command)
        self.assertIn("export MLKEM_AUTH_SERVER_MLDSA_PUB=/home/user/keys/server_mldsa_identity.pub", command)
        self.assertIn("export TONGSUO_SIG_BRIDGE=/home/user/libtongsuo_sig_bridge.so", command)
        self.assertIn("export OQS_INSTALL_PATH=/home/user/liboqs-dist", command)
        self.assertIn("export LD_LIBRARY_PATH=/home/user/liboqs-dist/lib", command)

    def test_local_control_transport_mode_stays_tcp_when_data_transport_is_usrp(self) -> None:
        env_values = {"MLKEM_TRANSPORT_MODE": "usrp"}

        self.assertEqual(crypto_runtime.local_crypto_transport_mode(env_values), "usrp")
        self.assertEqual(crypto_runtime.local_control_transport_mode(env_values), "tcp")

    def test_build_remote_crypto_server_command_omits_status_port_when_server_script_lacks_support(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server_script = Path(temp_dir) / "tcp_server.py"
            server_script.write_text(
                "#!/usr/bin/env python3\n"
                "import argparse\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--port')\n",
                encoding="utf-8",
            )

            command = crypto_runtime.build_remote_crypto_server_command(
                {
                    "MLKEM_REMOTE_SERVER_SCRIPT": "/home/user/tcp_server.py",
                    "MLKEM_STATUS_PORT": "18080",
                },
                local_server_script=server_script,
            )

        self.assertNotIn("--status-port", command)

    def test_build_remote_crypto_server_command_ignores_generic_openamp_root_for_sibling_mlkem_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            current_repo = temp_root / "Semantic-Communication"
            sibling_repo = temp_root / "ICCompetition2026"
            (current_repo / "session_bootstrap").mkdir(parents=True)
            (sibling_repo / "scripts").mkdir(parents=True)
            local_server_script = sibling_repo / "scripts" / "tcp_server.py"
            local_server_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            with patch.object(crypto_runtime, "PROJECT_ROOT", current_repo):
                command = crypto_runtime.build_remote_crypto_server_command(
                    {"REMOTE_PROJECT_ROOT": "/home/user/tvm_metaschedule_execution_project"},
                    local_server_script=local_server_script,
                )

        self.assertIn("/home/user/tcp_server.py", command)
        self.assertNotIn("/home/user/tvm_metaschedule_execution_project/scripts/tcp_server.py", command)

    def test_run_ssh_command_falls_back_to_askpass_when_sshpass_missing(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            command = args[0]
            env = kwargs["env"]
            captured["command"] = command
            captured["env"] = env
            askpass_path = Path(str(env["SSH_ASKPASS"]))
            captured["askpass_exists_during_run"] = askpass_path.exists()
            captured["askpass_body"] = askpass_path.read_text(encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

        with (
            patch(
                "crypto_runtime.shutil.which",
                side_effect=lambda name: None if name == "sshpass" else "/usr/bin/setsid",
            ),
            patch("crypto_runtime.subprocess.run", side_effect=fake_run),
        ):
            result = crypto_runtime.run_ssh_command(
                host="demo-board",
                user="demo-user",
                password="demo-pass",
                port="22",
                remote_command="echo ready",
                timeout=5,
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(captured["command"][:2], ["setsid", "-w"])
        self.assertEqual(captured["command"][2], "ssh")
        self.assertTrue(captured["askpass_exists_during_run"])
        self.assertIn("demo-pass", str(captured["askpass_body"]))
        self.assertEqual(captured["env"]["SSH_ASKPASS_REQUIRE"], "force")
        self.assertFalse(Path(str(captured["env"]["SSH_ASKPASS"])).exists())

    def test_run_ssh_command_uses_utf8_replacement_decoding(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured.update(kwargs)
            return subprocess.CompletedProcess(args[0], 0, stdout="ok\n", stderr="")

        with patch("crypto_runtime.subprocess.run", side_effect=fake_run):
            crypto_runtime.run_ssh_command(
                host="demo-board",
                user="demo-user",
                password="",
                port="22",
                remote_command="echo ready",
                timeout=5,
            )

        self.assertIs(captured["text"], True)
        self.assertEqual(captured["encoding"], "utf-8")
        self.assertEqual(captured["errors"], "replace")
        self.assertEqual(captured["env"]["MSYS2_ARG_CONV_EXCL"], "*")

    def test_run_ssh_command_uses_docker_runner_when_requested(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured["command"] = args[0]
            captured["env"] = kwargs["env"]
            return subprocess.CompletedProcess(args[0], 0, stdout="ok\n", stderr="")

        with (
            patch.dict(
                os.environ,
                {
                    "OPENAMP_SSH_RUNNER": "docker",
                    "OPENAMP_SSH_DOCKER_IMAGE": "demo-ssh-image:latest",
                },
            ),
            patch("crypto_runtime.shutil.which", return_value="/usr/bin/docker"),
            patch("crypto_runtime.subprocess.run", side_effect=fake_run),
        ):
            crypto_runtime.run_ssh_command(
                host="demo-board",
                user="demo-user",
                password="demo-pass",
                port="22",
                remote_command="echo ready",
                timeout=5,
            )

        command = captured["command"]
        self.assertEqual(command[:5], ["docker", "run", "--rm", "-e", "SSHPASS"])
        self.assertIn("demo-ssh-image:latest", command)
        self.assertIn("sshpass", command)
        self.assertIn("ssh", command)
        self.assertEqual(captured["env"]["SSHPASS"], "demo-pass")

    def test_run_scp_file_uses_docker_runner_when_requested(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured["command"] = args[0]
            captured["env"] = kwargs["env"]
            return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            local_file = Path(temp_dir) / "payload.txt"
            local_file.write_text("payload", encoding="utf-8")
            with (
                patch.dict(
                    os.environ,
                    {
                        "OPENAMP_SSH_RUNNER": "docker",
                        "OPENAMP_SSH_DOCKER_IMAGE": "demo-ssh-image:latest",
                    },
                ),
                patch("crypto_runtime.shutil.which", return_value="/usr/bin/docker"),
                patch("crypto_runtime.subprocess.run", side_effect=fake_run),
            ):
                crypto_runtime.run_scp_file(
                    host="demo-board",
                    user="demo-user",
                    password="demo-pass",
                    port="22",
                    local_path=local_file,
                    remote_path="/tmp/payload.txt",
                    timeout=5,
                )

        command = captured["command"]
        self.assertEqual(command[:5], ["docker", "run", "--rm", "-e", "SSHPASS"])
        self.assertIn("demo-ssh-image:latest", command)
        self.assertIn("scp", command)
        self.assertIn("/upload/payload.txt", command)
        self.assertIn("/tmp/payload.txt", command[-1])
        self.assertEqual(captured["env"]["SSHPASS"], "demo-pass")

    def test_resolve_local_oqs_install_discovers_nested_liboqs_dist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            current_repo = temp_root / "Semantic-Communication"
            nested_oqs = current_repo / "liboqs" / "liboqs-dist"
            (current_repo / "session_bootstrap").mkdir(parents=True)
            nested_oqs.mkdir(parents=True)

            with (
                patch.object(crypto_runtime, "PROJECT_ROOT", current_repo),
                patch.object(crypto_runtime.Path, "cwd", return_value=current_repo),
            ):
                resolved, searched = crypto_runtime.resolve_local_oqs_install({})

        self.assertEqual(resolved, nested_oqs.resolve())
        self.assertIn(nested_oqs.resolve(), searched)

    def test_build_local_crypto_client_command_uses_detected_oqs_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            current_repo = temp_root / "Semantic-Communication"
            sibling_repo = temp_root / "ICCompetition2026"
            current_repo.mkdir()
            (sibling_repo / "scripts").mkdir(parents=True)
            (sibling_repo / "liboqs-dist").mkdir(parents=True)
            client_script = sibling_repo / "scripts" / "tcp_client.py"
            client_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            input_path = temp_root / "sample.bin"
            input_path.write_bytes(b"\0" * 32)

            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(crypto_runtime, "PROJECT_ROOT", current_repo),
                patch.object(crypto_runtime.Path, "cwd", return_value=current_repo),
            ):
                command, env = crypto_runtime.build_local_crypto_client_command(
                    {},
                    host="127.0.0.1",
                    input_path=input_path,
                    client_script=client_script,
                )

        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[1], str(client_script))
        self.assertEqual(env["OQS_INSTALL_PATH"], str((sibling_repo / "liboqs-dist").resolve()))

    def test_build_local_crypto_client_command_prefers_mlkem_runtime_venv_and_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            current_repo = temp_root / "Semantic-Communication"
            sibling_repo = temp_root / "ICCompetition2026"
            (current_repo / "scripts").mkdir(parents=True)
            (sibling_repo / "mlkem_link").mkdir(parents=True)
            (sibling_repo / ".venv" / "bin").mkdir(parents=True)
            (sibling_repo / "tongsuo-dist" / "tongsuo" / "lib").mkdir(parents=True)
            client_script = current_repo / "scripts" / "tcp_client.py"
            client_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            detected_python = sibling_repo / ".venv" / "bin" / "python"
            detected_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            bridge_path = sibling_repo / "tongsuo-dist" / "tongsuo" / "lib" / "libtongsuo_kem_bridge.so"
            bridge_path.write_bytes(b"\0")
            input_path = temp_root / "sample.bin"
            input_path.write_bytes(b"\0" * 32)

            with (
                patch.object(crypto_runtime, "PROJECT_ROOT", current_repo),
                patch.object(crypto_runtime.Path, "cwd", return_value=current_repo),
            ):
                command, env = crypto_runtime.build_local_crypto_client_command(
                    {},
                    host="127.0.0.1",
                    input_path=input_path,
                    client_script=client_script,
                )

        self.assertEqual(command[0], str(detected_python.resolve()))
        self.assertEqual(command[1], str(client_script))
        self.assertEqual(env["TONGSUO_KEM_BRIDGE"], str(bridge_path.resolve()))
        self.assertTrue(env["LD_LIBRARY_PATH"].startswith(str(bridge_path.parent.resolve())))
        self.assertEqual(env["PYTHONPATH"].split(os.pathsep)[0], str(sibling_repo.resolve()))

    def test_build_local_crypto_client_command_uses_docker_runner_and_maps_paths(self) -> None:
        env_values = {
            "MLKEM_LOCAL_CLIENT_RUNNER": "docker",
            "MLKEM_LOCAL_CLIENT_DOCKER_IMAGE": "demo-crypto-image:latest",
            "MLKEM_AUTH_ENABLED": "1",
            "MLKEM_AUTH_SIG_POLICY": "DUAL_REQUIRED",
            "MLKEM_AUTH_PEER_SM2_PUB": r"E:\repo\keys\server_sm2_identity.pub",
            "MLKEM_AUTH_PEER_MLDSA_PUB": r"E:\repo\keys\server_mldsa_identity.pub",
            "MLKEM_PORT": "9527",
        }

        with patch("crypto_runtime.shutil.which", return_value="/usr/bin/docker"):
            command, env = crypto_runtime.build_local_crypto_client_command(
                env_values,
                host="100.121.87.73",
                input_path=Path(r"C:\Users\demo\AppData\Local\Temp\sample.bin"),
                client_script=Path(r"E:\repo\Semantic-Communication\scripts\tcp_client.py"),
            )

        self.assertEqual(command[:3], ["docker", "run", "--rm"])
        self.assertIn(r"C:\:/host/c", command)
        self.assertIn(r"E:\:/host/e", command)
        self.assertIn("demo-crypto-image:latest", command)
        self.assertIn("/opt/iccomp-venv/bin/python", command)
        self.assertIn("/workspace/Semantic-Communication/scripts/tcp_client.py", command)
        self.assertIn("/host/c/Users/demo/AppData/Local/Temp/sample.bin", command)
        self.assertIn("MLKEM_AUTH_PEER_SM2_PUB=/host/e/repo/keys/server_sm2_identity.pub", command)
        self.assertIn("MLKEM_AUTH_PEER_MLDSA_PUB=/host/e/repo/keys/server_mldsa_identity.pub", command)
        self.assertIn("OQS_INSTALL_PATH=/workspace/liboqs-dist", command)
        self.assertIn("TONGSUO_SIG_BRIDGE=/workspace/artifacts/crypto/libtongsuo_sig_bridge.so", command)
        self.assertIn("LD_LIBRARY_PATH=/workspace/liboqs-dist/lib:/workspace/artifacts/crypto", command)
        self.assertIn("PATH=/opt/iccomp-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", command)
        self.assertIn("PYTHONUNBUFFERED=1", command)
        self.assertIn("PYTHONIOENCODING=utf-8", command)
        self.assertIn("PYTHONUTF8=1", command)
        self.assertIn("--port", command)
        self.assertIn("9527", command)
        self.assertIsInstance(env, dict)

    def test_build_local_crypto_daemon_command_uses_docker_runner_and_mounts_temp_drive(self) -> None:
        env_values = {
            "MLKEM_LOCAL_CLIENT_RUNNER": "docker",
            "MLKEM_LOCAL_CLIENT_DOCKER_IMAGE": "demo-crypto-image:latest",
        }

        with (
            patch.dict(os.environ, {"TEMP": r"C:\Users\demo\AppData\Local\Temp"}, clear=False),
            patch("crypto_runtime.shutil.which", return_value="/usr/bin/docker"),
        ):
            command, _env = crypto_runtime.build_local_crypto_daemon_command(
                env_values,
                host="100.121.87.73",
                client_script=Path(r"E:\repo\Semantic-Communication\scripts\tcp_client.py"),
            )

        self.assertEqual(command[:4], ["docker", "run", "--rm", "-i"])
        self.assertIn(r"C:\:/host/c", command)
        self.assertIn(r"E:\:/host/e", command)
        self.assertIn("demo-crypto-image:latest", command)
        self.assertIn("--daemon", command)

    def test_mlkem_session_manager_maps_input_path_for_docker_daemon(self) -> None:
        manager = crypto_runtime.MlkemSessionManager(
            {"MLKEM_LOCAL_CLIENT_RUNNER": "docker"},
            "100.121.87.73",
            Path(r"E:\repo\Semantic-Communication\scripts\tcp_client.py"),
        )
        manager._proc = SimpleNamespace(poll=lambda: None)
        manager._alive = True
        captured: list[dict[str, object]] = []

        def fake_stdin_write(data: str) -> None:
            captured.append(json.loads(data))

        manager._stdin_write = fake_stdin_write  # type: ignore[method-assign]
        manager._read_line = lambda timeout: '{"status":"ok","encrypt_ms":0.5}'  # type: ignore[method-assign]

        result = manager.send_image(Path(r"C:\Users\demo\AppData\Local\Temp\sample.bin"), "job-001")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(captured[0]["input"], "/host/c/Users/demo/AppData/Local/Temp/sample.bin")

    def test_mlkem_session_manager_reads_daemon_ready_from_non_selectable_pipe(self) -> None:
        manager = crypto_runtime.MlkemSessionManager({}, "127.0.0.1", Path("/tmp/tcp_client.py"))

        class FakeStdout:
            def __init__(self) -> None:
                self._lines = iter(['{"status":"ready","handshake_ms":12.5}\n', ""])

            def readline(self) -> str:
                return next(self._lines)

        class FakeProc:
            def __init__(self) -> None:
                self.stdin = io.StringIO()
                self.stdout = FakeStdout()
                self.stderr = io.StringIO()

            def poll(self) -> None:
                return None

        with (
            patch(
                "crypto_runtime.build_local_crypto_daemon_command",
                return_value=(["fake-python", "tcp_client.py", "--daemon"], {}),
            ),
            patch("crypto_runtime.subprocess.Popen", return_value=FakeProc()),
        ):
            manager.ensure_alive()

        self.assertTrue(manager.is_alive)
        self.assertEqual(manager._handshake_ms, 12.5)

    def test_repo_tcp_client_supports_batch_summary_mode(self) -> None:
        client_script = DEMO_ROOT.parents[2] / "scripts" / "tcp_client.py"
        capabilities = crypto_runtime.inspect_local_crypto_client_capabilities(client_script)

        self.assertTrue(capabilities["supports_daemon"])
        self.assertTrue(capabilities["supports_count"])
        self.assertTrue(capabilities["supports_json_summary"])
        self.assertTrue(capabilities["supports_batch_summary"])
        self.assertTrue(capabilities["supports_expect_result"])
        self.assertFalse(capabilities["legacy_single_input_only"])

    def test_repo_tcp_client_infers_modern_bin_shape_from_size(self) -> None:
        tcp_client = self._load_repo_tcp_client_module()
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp.write(b"\0" * (1 * 32 * 32 * 32 * 4))
            tmp.flush()
            tmp_path = tmp.name
        try:
            raw, info = tcp_client.load_latent(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertEqual(len(raw), 1 * 32 * 32 * 32 * 4)
        self.assertEqual(info["shape"], [1, 32, 32, 32])
        self.assertEqual(info["dtype"], "float32")

    def test_repo_tcp_client_infers_legacy_bin_shape_from_size(self) -> None:
        tcp_client = self._load_repo_tcp_client_module()
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp.write(b"\0" * (1 * 3 * 64 * 64 * 4))
            tmp.flush()
            tmp_path = tmp.name
        try:
            raw, info = tcp_client.load_latent(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        self.assertEqual(len(raw), 1 * 3 * 64 * 64 * 4)
        self.assertEqual(info["shape"], [1, 3, 64, 64])
        self.assertEqual(info["dtype"], "float32")

    def test_mlkem_session_manager_restarts_and_retries_on_eof(self) -> None:
        manager = crypto_runtime.MlkemSessionManager({}, "127.0.0.1", Path("/tmp/tcp_client.py"))
        manager._proc = SimpleNamespace(poll=lambda: None)
        manager._alive = True

        send_attempts = {"count": 0}
        restart_count = {"count": 0}

        def fake_stdin_write(data: str) -> None:
            send_attempts["count"] += 1

        def fake_read_line(*, timeout: float) -> str:
            if send_attempts["count"] == 1:
                manager._alive = False
                raise RuntimeError("连接关闭: 期望 4 字节，已读 0 字节")
            return '{"status":"ok","encrypt_ms":0.5,"total_ms":1.2}'

        def fake_start_daemon() -> None:
            restart_count["count"] += 1
            manager._proc = SimpleNamespace(poll=lambda: None)
            manager._alive = True

        with (
            patch.object(manager, "_stdin_write", side_effect=fake_stdin_write),
            patch.object(manager, "_read_line", side_effect=fake_read_line),
            patch.object(manager, "_start_daemon", side_effect=fake_start_daemon),
            patch.object(manager, "_kill_proc"),
        ):
            response = manager.send_image("/tmp/input.bin", "job-1")

        self.assertEqual(response["status"], "ok")
        self.assertEqual(send_attempts["count"], 2)
        self.assertEqual(restart_count["count"], 1)
        self.assertEqual(manager._images_sent, 1)

    def test_mlkem_session_manager_forwards_expect_result_to_daemon(self) -> None:
        manager = crypto_runtime.MlkemSessionManager({}, "127.0.0.1", Path("/tmp/tcp_client.py"))
        manager._proc = SimpleNamespace(poll=lambda: None)
        manager._alive = True

        captured: dict[str, object] = {}

        def fake_stdin_write(data: str) -> None:
            captured["payload"] = json.loads(data)

        with (
            patch.object(manager, "_stdin_write", side_effect=fake_stdin_write),
            patch.object(
                manager,
                "_read_line",
                return_value='{"status":"ok","result_received":true,"encrypt_ms":0.5,"total_ms":1.2}',
            ),
        ):
            response = manager.send_image("/tmp/input.bin", "job-3", expect_result=True)

        self.assertEqual(response["status"], "ok")
        self.assertEqual(captured["payload"]["action"], "send")
        self.assertTrue(captured["payload"]["expect_result"])

    def test_mlkem_session_manager_retries_on_retryable_error_response(self) -> None:
        manager = crypto_runtime.MlkemSessionManager({}, "127.0.0.1", Path("/tmp/tcp_client.py"))
        manager._proc = SimpleNamespace(poll=lambda: None)
        manager._alive = True

        send_attempts = {"count": 0}
        restart_count = {"count": 0}

        def fake_stdin_write(data: str) -> None:
            send_attempts["count"] += 1

        def fake_read_line(*, timeout: float) -> str:
            if send_attempts["count"] == 1:
                return '{"status":"error","message":"连接关闭: 期望 4 字节，已读 0 字节"}'
            return '{"status":"ok","encrypt_ms":0.5,"total_ms":1.2}'

        def fake_start_daemon() -> None:
            restart_count["count"] += 1
            manager._proc = SimpleNamespace(poll=lambda: None)
            manager._alive = True

        with (
            patch.object(manager, "_stdin_write", side_effect=fake_stdin_write),
            patch.object(manager, "_read_line", side_effect=fake_read_line),
            patch.object(manager, "_start_daemon", side_effect=fake_start_daemon),
            patch.object(manager, "_kill_proc"),
        ):
            response = manager.send_image("/tmp/input.bin", "job-2")

        self.assertEqual(response["status"], "ok")
        self.assertEqual(send_attempts["count"], 2)
        self.assertEqual(restart_count["count"], 1)
        self.assertEqual(manager._images_sent, 1)

    def test_build_local_crypto_daemon_fingerprint_changes_with_suite_and_port(self) -> None:
        client = Path("/tmp/tcp_client.py")
        fp_a = crypto_runtime.build_local_crypto_daemon_fingerprint(
            {"MLKEM_CIPHER_SUITE": "SM4_GCM", "MLKEM_PORT": "9527"},
            host="127.0.0.1",
            client_script=client,
        )
        fp_b = crypto_runtime.build_local_crypto_daemon_fingerprint(
            {"MLKEM_CIPHER_SUITE": "AES_256_GCM", "MLKEM_PORT": "9527"},
            host="127.0.0.1",
            client_script=client,
        )
        fp_c = crypto_runtime.build_local_crypto_daemon_fingerprint(
            {"MLKEM_CIPHER_SUITE": "SM4_GCM", "MLKEM_PORT": "9530"},
            host="127.0.0.1",
            client_script=client,
        )

        self.assertNotEqual(fp_a, fp_b)
        self.assertNotEqual(fp_a, fp_c)

    def test_build_local_crypto_daemon_fingerprint_tolerates_missing_runtime_root(self) -> None:
        with patch.object(
            crypto_runtime,
            "resolve_local_mlkem_runtime_root",
            return_value=(None, []),
        ):
            fingerprint = crypto_runtime.build_local_crypto_daemon_fingerprint(
                {"MLKEM_CIPHER_SUITE": "SM4_GCM"},
                host="127.0.0.1",
                client_script=Path("/tmp/tcp_client.py"),
            )

        self.assertIn("SM4_GCM", fingerprint)

    def test_mlkem_session_manager_retryable_send_error_matches_frame_too_large(self) -> None:
        self.assertTrue(crypto_runtime.MlkemSessionManager._is_retryable_send_error("frame too large"))
        self.assertTrue(crypto_runtime.MlkemSessionManager._is_retryable_send_error("帧过大"))
        self.assertTrue(crypto_runtime.MlkemSessionManager._is_retryable_send_error("invalid json"))


if __name__ == "__main__":
    unittest.main()
