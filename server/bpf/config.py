"""Application settings, read from the environment and the repo-root ``.env.local``.

Every field maps to an environment variable with the ``BPF_`` prefix (``db_port`` -> ``BPF_DB_PORT``).
Precedence (highest first): explicit keyword arguments, real environment variables, the env file, defaults.

The env file defaults to ``<repo>/.env.local`` (written by ``deploy/local/db-init.sh``); point
``BPF_ENV_FILE`` at another file to use that instead. ``.env.example`` documents every variable.

Passwords are ``SecretStr``: they print as ``**********`` in ``repr()``, ``str()``, logs and tracebacks.
Call ``.get_secret_value()`` only at the point where a connection is opened (see ``bpf.db``).

Usage::

    from bpf.config import get_settings
    settings = get_settings()          # cached; call get_settings.cache_clear() after changing the env
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Repository root: server/bpf/config.py -> parents[2].
REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE: Path = REPO_ROOT / ".env.local"


def env_file_path() -> Path:
    """The env file to read: ``$BPF_ENV_FILE`` if set, else ``<repo>/.env.local``."""
    override = os.environ.get("BPF_ENV_FILE")
    return Path(override).expanduser() if override else DEFAULT_ENV_FILE


class Settings(BaseSettings):
    """All runtime configuration. Construct via :func:`get_settings` (or directly in tests)."""

    model_config = SettingsConfigDict(
        env_prefix="BPF_",
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,  # validation errors must never echo a secret back
    )

    # ── database (deploy/local/db-init.sh writes these) ──
    db_host: str = Field(
        default="localhost", description="Unix socket directory (preferred) or host name of the cluster."
    )
    db_port: int = Field(default=5544, ge=1, le=65535)
    db_name: str = Field(default="bpf", pattern=r"^[a-z_][a-z0-9_]{0,62}$")
    migrator_password: SecretStr | None = None
    ingest_password: SecretStr | None = None
    api_password: SecretStr | None = None

    # ── GVH Árfigyelő client (ingest) ──
    gvh_base_url: str = "https://arfigyelo.gvh.hu/api"
    gvh_xlsx_url: str = "https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx"
    gvh_user_agent: str = Field(default="bestpricefinder/0.1 (+contact: set BPF_CONTACT_EMAIL)", min_length=1)
    contact_email: str | None = None
    # Politeness floor from BUILD-BRIEF: at most one request per second.
    gvh_min_interval_s: float = Field(default=1.0, ge=1.0)

    # ── public API ──
    api_rate_limit_per_minute: int = Field(default=120, gt=0)
    api_max_body_bytes: int = Field(default=65536, gt=0)
    web_build_dir: Path = REPO_ROOT / "web" / "build"
    # Comma-separated in the environment (BPF_ALLOWED_ORIGINS=https://a.example,https://b.example) or a
    # JSON list. Empty = same origin only.
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trust_proxy_headers: bool = False
    # Send Strict-Transport-Security on every response. Only behind TLS (e.g. Caddy): browsers then refuse
    # plain HTTP to this host for a year.
    hsts: bool = False
    # Serve the interactive OpenAPI docs at /api/docs, /api/redoc and /api/openapi.json, with a
    # development-only CSP that loads Swagger UI / ReDoc from a CDN. Off in production.
    enable_docs: bool = False

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [part.strip() for part in text.split(",") if part.strip()]
        return value

    def password_for(self, role: str) -> SecretStr | None:
        """The password for app role ``role`` ('api', 'ingest' or 'migrator')."""
        match role:
            case "api":
                return self.api_password
            case "ingest":
                return self.ingest_password
            case "migrator":
                return self.migrator_password
        raise ValueError(f"unknown database role {role!r}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, read once from the environment and :func:`env_file_path`."""
    return Settings(_env_file=env_file_path())
