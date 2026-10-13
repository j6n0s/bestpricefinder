"""Write the OpenAPI document of the API to ``docs/openapi.json`` (the web client's types come from it).

``python -m bpf.api.openapi`` writes it; ``--check`` exits 1 when the file on disk is out of date; ``-o PATH``
writes elsewhere. The output is deterministic: no database, no web build, no environment is read, and the JSON
is written with sorted keys, two-space indentation and a trailing newline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from bpf.api.app import create_app
from bpf.api.options import ApiOptions
from bpf.config import REPO_ROOT, Settings

DEFAULT_OUTPUT = REPO_ROOT / "docs" / "openapi.json"


def openapi_document() -> dict[str, Any]:
    """The OpenAPI document, built from an app that has no environment, database or static site."""
    # model_construct: defaults only, nothing read from the environment or an env file
    settings = Settings.model_construct(web_build_dir=Path("/nonexistent/bpf-openapi"))
    options = ApiOptions.model_construct(hsts=False, enable_docs=False)
    return create_app(settings, options=options).openapi()


def render() -> str:
    return json.dumps(openapi_document(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bpf.api.openapi", description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help="file to write")
    parser.add_argument("--check", action="store_true", help="exit 1 if the file is missing or out of date")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        try:
            current = args.output.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != text:
            print(f"{args.output} is out of date; run python -m bpf.api.openapi", file=sys.stderr)
            return 1
        return 0
    args.output.write_text(text, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
