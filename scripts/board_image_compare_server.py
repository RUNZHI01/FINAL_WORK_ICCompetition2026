#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__:
    from .board_image_compare.service import ComparisonServiceState, create_http_server
else:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scripts.board_image_compare.service import ComparisonServiceState, create_http_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Host-side board reconstruction comparison service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8786)
    parser.add_argument("--cache-root", type=Path, default=Path("artifacts/board_image_cache"))
    args = parser.parse_args()

    state = ComparisonServiceState(cache_root=args.cache_root.resolve())
    server = create_http_server(args.host, args.port, state)
    print(f"board reconstruction comparison service: http://{args.host}:{server.server_port}/", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        state.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
