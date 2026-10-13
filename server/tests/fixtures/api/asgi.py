"""Call an ASGI app with an exact scope (no client-side URL normalisation) and raw body chunks."""

from __future__ import annotations

import asyncio
from typing import Any

JSON_HEADERS = [(b"host", b"testserver"), (b"content-type", b"application/json")]


async def _call(app: Any, scope: dict[str, Any], chunks: list[bytes]) -> tuple[int, dict[str, str], bytes]:
    queue = [
        {"type": "http.request", "body": c, "more_body": i < len(chunks) - 1} for i, c in enumerate(chunks)
    ]
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        if queue:
            return queue.pop(0)
        await asyncio.sleep(3600)  # never disconnect while the app is still answering
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await app(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], headers, body


def raw_request(
    app: Any,
    path: str,
    *,
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
    chunks: list[bytes] | None = None,
    client: tuple[str, int] = ("198.51.100.7", 40000),
) -> tuple[int, dict[str, str], bytes]:
    """Call the ASGI app with an exact, already-decoded ``path`` (no client-side URL normalisation)."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8", "surrogateescape"),
        "root_path": "",
        "query_string": b"",
        "headers": headers or [(b"host", b"testserver")],
        "client": client,
        "server": ("testserver", 80),
        "state": {},
    }
    return asyncio.run(_call(app, scope, chunks or [b""]))
