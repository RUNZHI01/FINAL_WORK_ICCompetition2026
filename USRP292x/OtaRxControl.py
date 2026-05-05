#!/usr/bin/env python3
"""Control client for OtaRxPersistentServer.

The control protocol is intentionally small so it can run over localhost or a
Tailscale TCP path without additional dependencies.
"""

from __future__ import annotations

import argparse
import socket
import sys


DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 29220


def send_command(host: str, port: int, line: str, timeout: float) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((line.rstrip() + '\n').encode('utf-8'))
            chunks: list[bytes] = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
                if b'\n' in data:
                    break
        return b''.join(chunks).decode('utf-8', errors='replace').strip()
    except ConnectionRefusedError:
        return f'ERR_CONNECTION_REFUSED host={host} port={port}'
    except (socket.timeout, OSError):
        return f'ERR_TIMEOUT host={host} port={port}'


def require_ok(response: str) -> int:
    print(response)
    return 0 if response.startswith('OK') else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='USRP292x persistent RX control client.')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--timeout', type=float, default=10.0)

    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('ping')
    sub.add_parser('status')
    sub.add_parser('stop')
    sub.add_parser('quit')

    capture = sub.add_parser('capture')
    capture.add_argument('--file', required=True)
    capture.add_argument('--duration', type=float, default=0.0)
    capture.add_argument('--nsamps', type=int, default=0)

    wait = sub.add_parser('wait')
    wait.add_argument('--wait-timeout', type=float, default=0.0)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.cmd == 'ping':
        line = 'PING'
    elif args.cmd == 'status':
        line = 'STATUS'
    elif args.cmd == 'stop':
        line = 'STOP'
    elif args.cmd == 'quit':
        line = 'QUIT'
    elif args.cmd == 'capture':
        if args.duration <= 0.0 and args.nsamps <= 0:
            raise RuntimeError('capture requires --duration > 0 or --nsamps > 0')
        line = f'CAPTURE file={args.file} duration={args.duration} nsamps={args.nsamps}'
    elif args.cmd == 'wait':
        line = f'WAIT timeout={args.wait_timeout}'
        args.timeout = max(args.timeout, args.wait_timeout + 5.0)
    else:
        raise RuntimeError(f'unknown command: {args.cmd}')

    response = send_command(args.host, args.port, line, args.timeout)
    return require_ok(response)


if __name__ == '__main__':
    raise SystemExit(main())
