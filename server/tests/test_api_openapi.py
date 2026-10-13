"""The OpenAPI export (``python -m bpf.api.openapi`` -> docs/openapi.json): deterministic, independent of the
environment, complete, and the committed file is up to date."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bpf.api import openapi
from bpf.config import REPO_ROOT

PATHS = {
    "/api/health": {"get"},
    "/api/meta": {"get"},
    "/api/stores": {"get"},
    "/api/ingredients": {"get"},
    "/api/ingredients/{id}/history": {"get"},
    "/api/recipes": {"get"},
    "/api/recipes/{id}": {"get"},
    "/api/list": {"post"},
    "/api/quote": {"post"},
    "/api/plan/suggest": {"post"},
    "/api/plan/check": {"post"},
}
REQUESTS = {
    "/api/list": "ListRequest",
    "/api/quote": "QuoteRequest",
    "/api/plan/suggest": "PlanSuggestRequest",
    "/api/plan/check": "PlanCheckRequest",
}


def test_render_is_deterministic_and_canonical() -> None:
    first = openapi.render()
    assert first == openapi.render()
    assert first.endswith("}\n")
    document = json.loads(first)
    assert json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n" == first


def test_render_ignores_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    baseline = openapi.render()
    env_file = tmp_path / "env"
    env_file.write_text("BPF_ENABLE_DOCS=true\nBPF_HSTS=true\nBPF_ALLOWED_ORIGINS=https://a.example\n")
    monkeypatch.setenv("BPF_ENV_FILE", str(env_file))
    monkeypatch.setenv("BPF_ENABLE_DOCS", "true")
    monkeypatch.setenv("BPF_API_MAX_BODY_BYTES", "10")
    monkeypatch.setenv("BPF_DB_PORT", "not-a-port")  # even invalid settings do not matter
    monkeypatch.setenv("BPF_WEB_BUILD_DIR", str(tmp_path))
    assert openapi.render() == baseline


def test_document_covers_the_contract() -> None:
    document = openapi.openapi_document()
    assert {path: set(ops) for path, ops in document["paths"].items()} == PATHS
    schemas = document["components"]["schemas"]
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    for path, model in REQUESTS.items():
        operation = document["paths"][path]["post"]
        body = operation["requestBody"]["content"]["application/json"]["schema"]
        assert body == {"$ref": f"#/components/schemas/{model}"}
        for status in ("413", "415", "422", "429", "500"):
            error = operation["responses"][status]["content"]["application/json"]["schema"]
            assert error == {"$ref": "#/components/schemas/ErrorResponse"}, (path, status)
    quote = document["paths"]["/api/quote"]["post"]["responses"]["200"]["content"]["application/json"]
    assert quote["schema"] == {"$ref": "#/components/schemas/QuoteResponse"}
    assert schemas["ErrorResponse"]["properties"]["error"]["enum"] == [
        "invalid_request",
        "not_found",
        "payload_too_large",
        "unsupported_media_type",
        "rate_limited",
        "no_data",
        "internal",
        "method_not_allowed",
    ]
    assert schemas["QuoteRequest"]["additionalProperties"] is False
    params = {p["name"] for p in document["paths"]["/api/recipes"]["get"]["parameters"]}
    assert params == {"slot", "tag", "q"}


def test_cli_writes_and_checks(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    assert openapi.main(["--check", "-o", str(target)]) == 1  # missing
    assert openapi.main(["-o", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == openapi.render()
    assert openapi.main(["--check", "-o", str(target)]) == 0
    target.write_text("{}\n", encoding="utf-8")
    assert openapi.main(["--check", "-o", str(target)]) == 1


def test_committed_document_is_up_to_date() -> None:
    committed = REPO_ROOT / "docs" / "openapi.json"
    assert committed.read_text(encoding="utf-8") == openapi.render(), "run: python -m bpf.api.openapi"


def test_module_entry_point_in_a_fresh_interpreter(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    result = subprocess.run(
        [sys.executable, "-m", "bpf.api.openapi", "-o", str(target)],
        cwd=REPO_ROOT / "server",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert target.read_text(encoding="utf-8") == openapi.render()
