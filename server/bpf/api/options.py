"""API-only switches that ``bpf.config.Settings`` does not carry (yet).

docs/API.md names ``BPF_HSTS`` and the task names ``BPF_ENABLE_DOCS``; ``bpf.config`` belongs to the
skeleton, so they are read here with the same rules (``BPF_`` prefix, real environment over the env file,
``BPF_ENV_FILE`` or ``<repo>/.env.local``). Both default to off, which is the safe production setting.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from bpf.config import env_file_path


class ApiOptions(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BPF_", env_file_encoding="utf-8", extra="ignore", frozen=True, hide_input_in_errors=True
    )

    hsts: bool = False
    """Send ``Strict-Transport-Security`` (only behind TLS, e.g. Caddy)."""
    enable_docs: bool = False
    """Serve the interactive OpenAPI docs at /api/docs, /api/redoc and /api/openapi.json (development)."""


def load_options(env_file: Path | None = None) -> ApiOptions:
    """Options from the environment and the env file (``bpf.config.env_file_path()`` by default)."""
    path = env_file if env_file is not None else env_file_path()
    return ApiOptions(_env_file=path if path.is_file() else None)  # type: ignore[call-arg]
