"""``python -m bpf.api``: serve the API (and the SPA build) with uvicorn.

Binds 127.0.0.1:8000 by default (put Caddy in front to expose it). ``X-Forwarded-*`` headers are honoured
only when ``BPF_TRUST_PROXY_HEADERS=true`` (and then only from ``FORWARDED_ALLOW_IPS``, uvicorn's default
127.0.0.1). The ``Server`` header is not sent. The access log is off by default (it would record client IP
addresses); ``--access-log`` turns it on.
"""

from __future__ import annotations

import argparse

import uvicorn

from bpf.config import get_settings

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bpf.api", description="Serve the bestpricefinder API.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"bind address (default {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default {DEFAULT_PORT})")
    parser.add_argument(
        "--log-level", default="info", choices=("critical", "error", "warning", "info", "debug")
    )
    parser.add_argument("--access-log", action="store_true", help="log every request (includes client IPs)")
    args = parser.parse_args(argv)
    settings = get_settings()
    uvicorn.run(
        "bpf.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        proxy_headers=settings.trust_proxy_headers,
        server_header=False,
        access_log=args.access_log,
        log_level=args.log_level,
        lifespan="on",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
