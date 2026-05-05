#!/usr/bin/env python3
"""daemon 模式 300 张批量测试"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RESULT_FILE = "/tmp/daemon_300_result.txt"

def log(msg: str) -> None:
    with open(RESULT_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()

PORT = 19532
N = 260


def main():
    # ── 1. 启动 tcp_server ──
    server = subprocess.Popen(
        [sys.executable, "scripts/tcp_server.py",
         "--host", "127.0.0.1", "--port", str(PORT),
         "--output-dir", "/tmp/mlkem_300test", "--status-port", "0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={**os.environ, "OQS_INSTALL_PATH": "./liboqs-dist"},
    )
    time.sleep(2)
    if server.poll() is not None:
        log(f"Server 启动失败 (exit code {server.returncode})")
        sys.exit(1)
    log(f"Server pid={server.pid} 端口={PORT}")

    # ── 2. 创建测试文件 ──
    tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    tmp.write(b"\0" * (1 * 32 * 32 * 32 * 4))
    tmp.close()
    tmp_path = tmp.name

    # ── 3. 启动 daemon ──
    daemon = subprocess.Popen(
        [sys.executable, "scripts/tcp_client.py",
         "--host", "127.0.0.1", "--port", str(PORT), "--daemon"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env={**os.environ, "OQS_INSTALL_PATH": "./liboqs-dist",
             "PYTHONUNBUFFERED": "1"},
    )

    ready_line = daemon.stdout.readline()
    if not ready_line:
        log("Daemon 启动超时 (EOF on stdout)")
        cleanup(server, daemon, tmp_path)
        return
    ready = json.loads(ready_line.strip())
    if not ready_line:
        log("Daemon 启动超时")
        cleanup(server, daemon, tmp_path)
        return
    ready = json.loads(ready_line)
    hs_ms = ready["handshake_ms"]
    log(f"Daemon ready: handshake={hs_ms}ms, suite={ready['suite']}")

    # ── 4. 发送 300 张 ──
    ok = 0
    fail = 0
    t0 = time.monotonic()

    for i in range(N):
        cmd = json.dumps({
            "action": "send",
            "input": tmp_path,
            "job_id": f"batch_{i:04d}",
        }) + "\n"
        daemon.stdin.write(cmd)
        daemon.stdin.flush()
        # 用 select 加 5s 超时，防止卡死
        import select as _sel
        ready_fds, _, _ = _sel.select([daemon.stdout], [], [], 5.0)
        if not ready_fds:
            log(f"  TIMEOUT [{i}] — daemon 未在 5s 内响应")
            fail += 1
            if fail > 5:
                log("连续超时过多，终止")
                break
            continue
        line = daemon.stdout.readline()
        if not line:
            log(f"\nDaemon 连接断开于第 {i} 张")
            break
        r = json.loads(line.strip())
        if r.get("status") == "ok":
            ok += 1
        else:
            fail += 1
            if fail <= 3:
                log(f"  FAIL [{i}]: {r}")

        if (i + 1) % 10 == 0:
            elapsed = (time.monotonic() - t0) * 1000
            log(f"  [{i+1}/{N}] ok={ok} fail={fail} "
                  f"elapsed={elapsed:.0f}ms avg={elapsed/(i+1):.1f}ms")

    total_ms = (time.monotonic() - t0) * 1000

    log(f"\n{'='*50}")
    log(f"总计:  {ok}/{N} 成功 ({fail} 失败)")
    log(f"总耗时: {total_ms:.0f}ms ({total_ms/1000:.1f}s)")
    log(f"平均:  {total_ms/max(ok,1):.2f}ms/张")
    log(f"握手:  {hs_ms}ms (一次性, 摊到每张 +{hs_ms/max(ok,1):.3f}ms)")
    log(f"{'='*50}")

    # ── 5. 关闭 ──
    cleanup(server, daemon, tmp_path)


def cleanup(server, daemon, tmp_path):
    try:
        daemon.stdin.write(json.dumps({"action": "quit"}) + "\n")
        daemon.stdin.flush()
        daemon.stdout.readline()
        daemon.wait(timeout=5)
    except Exception:
        daemon.kill()
    try:
        server.terminate()
        server.wait(timeout=5)
    except Exception:
        server.kill()
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


if __name__ == "__main__":
    main()
