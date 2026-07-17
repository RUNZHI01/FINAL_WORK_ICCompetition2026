#!/usr/bin/env python3
"""Small threaded TCP forwarder used by Docker-hosted hardware services."""

from __future__ import annotations

import argparse
import socket
import socketserver
import struct
import threading
from pathlib import Path


def resolve_target_host(host: str, *, route_path: Path = Path("/proc/net/route")) -> str:
    if host != "docker-gateway":
        return host
    for line in route_path.read_text(encoding="ascii").splitlines()[1:]:
        fields = line.split()
        if len(fields) < 4 or fields[1] != "00000000":
            continue
        flags = int(fields[3], 16)
        if flags & 0x2:
            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    raise RuntimeError(f"default Docker gateway not found in {route_path}")


class ForwardHandler(socketserver.BaseRequestHandler):
    target: tuple[str, int]

    @staticmethod
    def _pump(source: socket.socket, destination: socket.socket) -> None:
        try:
            while data := source.recv(65536):
                destination.sendall(data)
        except OSError:
            pass
        finally:
            try:
                destination.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def handle(self) -> None:
        with socket.create_connection(self.target, timeout=10.0) as upstream:
            request_pump = threading.Thread(
                target=self._pump,
                args=(self.request, upstream),
                daemon=True,
            )
            request_pump.start()
            self._pump(upstream, self.request)
            request_pump.join(timeout=1.0)


class ForwardServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--target-host", required=True)
    parser.add_argument("--target-port", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = (resolve_target_host(args.target_host), args.target_port)
    handler = type("ConfiguredForwardHandler", (ForwardHandler,), {"target": target})
    with ForwardServer((args.listen_host, args.listen_port), handler) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
