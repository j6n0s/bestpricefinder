"""The FastAPI application (docs/API.md, docs/ENGINE.md ``bpf.api``).

Run with ``python -m bpf.api`` (127.0.0.1:8000) or ``uvicorn bpf.api.app:app``; ``app`` is created lazily on
first access (PEP 562), so importing this module never reads settings or touches the database.

``create_app`` wires:

* the routes (``bpf.api.routes``) with strict JSON bodies (``bpf.api.strictjson``);
* the error handlers (``bpf.api.errors``): every error is ``{"error", "fields"}``;
* the middlewares (``bpf.api.security``), outermost first: security headers (+ last-resort 500), CORS only
  when ``BPF_ALLOWED_ORIGINS`` is set, the per-client rate limit, the JSON content-type check, the body
  size limit;
* the SPA build (``bpf.api.static``) when ``web/build`` exists; otherwise only /api is served and every
  other path is a JSON 404;
* a lifespan that opens the ``bpf_api`` pool and the catalogue provider (unless one is injected, e.g. by
  tests) and closes them on shutdown.

FastAPI's OpenTelemetry integration is switched off: it can record validation failures with request bodies.
The interactive docs (``/api/docs``, ``/api/redoc``, ``/api/openapi.json``) exist only with
``BPF_ENABLE_DOCS=true``; ``python -m bpf.api.openapi`` writes the document to docs/openapi.json instead.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio.to_thread
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from bpf.api.errors import ApiError, api_error_handler, http_error_handler, validation_error_handler
from bpf.api.options import ApiOptions, load_options
from bpf.api.repo import CONNECTION_TIMEOUT_S, CatalogueProvider, DataUnavailable
from bpf.api.routes import register_routes
from bpf.api.security import (
    BodyLimitMiddleware,
    JsonContentTypeMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    TokenBucketLimiter,
)
from bpf.api.static import SpaRoute, StaticSite
from bpf.api.strictjson import StrictJsonRoute
from bpf.config import Settings, get_settings
from bpf.db import open_pool

log = logging.getLogger("bpf.api")

API_TITLE = "Heti kosár API"
API_VERSION = "1.1"
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 4
DOCS_URL = "/api/docs"
REDOC_URL = "/api/redoc"
OPENAPI_URL = "/api/openapi.json"
# The docs UI loads Swagger UI / ReDoc from jsdelivr and runs an inline bootstrap script (development only).
DOCS_CSP = (
    "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "connect-src 'self'; worker-src blob:; frame-ancestors 'none'"
)
TELEMETRY_OFF: dict[str, Any] = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}


def _lifespan(settings: Settings) -> Any:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        created: CatalogueProvider | None = None
        if getattr(app.state, "provider", None) is None:
            pool = open_pool(
                "api", POOL_MIN_SIZE, POOL_MAX_SIZE, settings=settings, timeout=CONNECTION_TIMEOUT_S
            )
            created = CatalogueProvider.from_pool(pool, owns_pool=True)
            app.state.provider = created
            try:  # warm the cache; a database that is down now is reported by /api/health
                await anyio.to_thread.run_sync(created.snapshot)
            except DataUnavailable:
                log.warning("catalogue not loaded at startup (database unavailable)")
        try:
            yield
        finally:
            if created is not None:
                app.state.provider = None
                await anyio.to_thread.run_sync(created.close)

    return lifespan


def create_app(
    settings: Settings | None = None,
    *,
    catalogue_provider: CatalogueProvider | None = None,
    options: ApiOptions | None = None,
) -> FastAPI:
    """Build the application. ``catalogue_provider`` replaces the database-backed one (tests); ``options``
    defaults to the environment (``BPF_HSTS``, ``BPF_ENABLE_DOCS``)."""
    settings = settings if settings is not None else get_settings()
    options = options if options is not None else load_options()
    docs = options.enable_docs
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description="Stateless, read-only API of the weekly meal planner. Contract: docs/API.md.",
        docs_url=DOCS_URL if docs else None,
        redoc_url=REDOC_URL if docs else None,
        openapi_url=OPENAPI_URL if docs else None,
        swagger_ui_oauth2_redirect_url=None,
        redirect_slashes=False,
        lifespan=_lifespan(settings),
        telemetry=TELEMETRY_OFF,  # type: ignore[arg-type]
    )
    app.state.settings = settings
    app.state.provider = catalogue_provider
    app.router.route_class = StrictJsonRoute
    register_routes(app)

    site = StaticSite.load(settings.web_build_dir)
    if site is not None:
        app.router.routes.append(SpaRoute(site))
    app.state.static_site = site

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)

    json_paths = {
        route.path for route in app.routes if isinstance(route, APIRoute) and "POST" in (route.methods or ())
    }
    # add_middleware puts each new middleware OUTSIDE the previous ones: innermost first.
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.api_max_body_bytes)
    app.add_middleware(JsonContentTypeMiddleware, json_paths=json_paths)
    limiter = TokenBucketLimiter(settings.api_rate_limit_per_minute)
    app.state.rate_limiter = limiter
    app.add_middleware(RateLimitMiddleware, limiter=limiter, trust_proxy_headers=settings.trust_proxy_headers)
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Accept", "If-None-Match"],
            expose_headers=["ETag", "Retry-After"],
            allow_credentials=False,
            max_age=600,
        )
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts=options.hsts,
        csp_overrides={DOCS_URL: DOCS_CSP, REDOC_URL: DOCS_CSP} if docs else None,
    )
    return app


_app: FastAPI | None = None
_app_lock = threading.Lock()


def __getattr__(name: str) -> Any:
    """``bpf.api.app.app``: the application built from the environment on first access."""
    if name != "app":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    global _app
    with _app_lock:
        if _app is None:
            _app = create_app()
        return _app
