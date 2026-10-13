"""Seeded fuzz test: 2,000 random and mutated JSON bodies against every POST endpoint of an app on a real
cluster (SYNTHETIC catalogue, tests/fixtures/api/seed.py).

Mutations: wrong types, huge and tiny numbers, NaN/Infinity literals, deep nesting, long strings, unicode
(NUL, lone surrogates, RTL, emoji), duplicate keys, extra fields, missing fields, oversized lists, truncated
and random bytes. Every injected string carries a unique marker ``ZQnnnnnnQ``.

Asserted for every request: no 500 (only 200, 413 and 422), a well-formed JSON body, the security headers, and
the marker never appears in the response (no echo of input, in any status).
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from bpf.api.repo import CatalogueProvider
from tests.fixtures.api import seed
from tests.fixtures.api.seed import TestClient
from tests.pgcluster import PgCluster

pytestmark = pytest.mark.db

SEED = 20261013
TOTAL = 2000
MARKER_RE = re.compile(r"zq\d{6}q", re.IGNORECASE)
DEEP = "__deep_nesting_placeholder__"
FIELD_RE = re.compile(r"^(body|query|path|[a-z_]+)(\.[a-z0-9_]+)*$")

TEMPLATES: dict[str, dict[str, Any]] = {
    "/api/quote": {
        "lines": [{"ingredient_id": "csirkemell", "qty": 1.2}, {"ingredient_id": "tojas", "qty": 12}],
        "store_ids": ["alfa-1", "beta-1", "gamma-1"],
        "include_loyalty": False,
    },
    "/api/list": {
        "items": [
            {"recipe_id": "zz-csirkes-rizs", "servings": 2},
            {"recipe_id": "zz-rizs-koret", "servings": 4},
        ],
        "on_hand": [{"ingredient_id": "rizs", "qty": 0.1}],
        "include_optional": True,
    },
    "/api/plan/suggest": {
        "days": 7,
        "slots": 3,
        "people": 2,
        "seed": 1,
        "exclude_tags": ["sertes"],
        "exclude_ingredients": ["fahej"],
        "red_meat_g_per_person_week": 600,
        "no_repeat_days": 5,
        "weekly_budget": 20000,
    },
    "/api/plan/check": {
        "days": [{"index": 0, "meals": {"ebed": "zz-porkolt", "vacsora": None}}, {"index": 1, "meals": {}}],
        "people": 2,
        "red_meat_g_per_person_week": 600,
        "no_repeat_days": 5,
        "weekly_budget": None,
    },
}


class Fuzzer:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.counter = 0

    def marker(self) -> str:
        self.counter += 1
        return f"ZQ{self.counter:06d}Q"

    def evil_string(self) -> str:
        m = self.marker()
        choices = [
            m,
            m.lower(),
            f"{m}-" + "x" * self.rng.randint(1, 2000),
            m * self.rng.randint(1, 50),
            f"‮{m}‭",
            f"{m}\u0000",
            f"{m}\ud800",
            f"{m}🥕🥚",
            f"<script>{m}</script>",
            f"'; DROP TABLE x; -- {m}",
            f"../../{m}",
            f"{m}%00",
            " " + m + " ",
            f"é{m}ő",
        ]
        return self.rng.choice(choices)

    def evil_value(self, depth: int = 0) -> Any:
        options: list[Callable[[], Any]] = [
            self.evil_string,
            lambda: self.rng.choice(
                [0, -1, 1, 2, 7, 31, 32, 100, 1000, 1001, 2**31, 2**63, -(2**63), 10**30]
            ),
            lambda: self.rng.choice(
                [0.0, -0.0, 1e-30, 1e308, -1e308, 0.0005, 0.0004999, 1000.0004, 1000.0005]
            ),
            lambda: self.rng.choice([True, False, None]),
            lambda: [self.evil_value(depth + 1) for _ in range(self.rng.randint(0, 3))] if depth < 3 else [],
            lambda: {self.evil_string(): self.evil_value(depth + 1)} if depth < 3 else {},
            lambda: str(self.rng.choice([1, 0.5, -3, 1e400])),
        ]
        return self.rng.choice(options)()

    def paths(self, value: Any, prefix: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
        yield prefix
        if len(prefix) >= 8:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                yield from self.paths(item, (*prefix, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from self.paths(item, (*prefix, index))

    @staticmethod
    def get_parent(doc: Any, path: tuple[Any, ...]) -> Any:
        for part in path[:-1]:
            doc = doc[part]
        return doc

    def mutate_doc(self, doc: Any) -> Any:
        """One structural mutation of a JSON-like document (in place where possible)."""
        paths = [p for p in self.paths(doc) if p]
        op = self.rng.randrange(7)
        if not paths or op == 0:
            return self.evil_value()
        path = self.rng.choice(paths)
        parent = self.get_parent(doc, path)
        key = path[-1]
        if op == 1:  # wrong value
            parent[key] = self.evil_value()
        elif op == 2:  # delete
            del parent[key]
        elif op == 3 and isinstance(parent, dict):  # extra field
            parent[self.evil_string()] = self.evil_value()
        elif op == 4:  # deep nesting, expanded in the serialised text (see body())
            parent[key] = DEEP
        elif op == 5:  # oversized list
            parent[key] = [parent[key]] * self.rng.choice([201, 300, 1000])
        else:  # swap in a structure of the wrong shape
            parent[key] = self.rng.choice([[], {}, "", self.evil_string(), [self.evil_value()]])
        return doc

    def body(self, template: dict[str, Any]) -> bytes:
        doc: Any = json.loads(json.dumps(template))
        for _ in range(self.rng.randint(1, 3)):
            doc = self.mutate_doc(doc)
        text = json.dumps(doc, ensure_ascii=self.rng.random() < 0.5)
        placeholder = f'"{DEEP}"'
        if placeholder in text:  # the first placeholder becomes deep nesting, any copies a short string
            depth = self.rng.choice([5, 50, 500, 3000, 20000])
            opener, closer = ("[", "]") if self.rng.random() < 0.5 else ('{"a":', "}")
            inner = json.dumps(self.evil_string())
            text = text.replace(placeholder, opener * depth + inner + closer * depth, 1)
            text = text.replace(placeholder, json.dumps(self.marker()))
        raw = self.rng.random()
        if raw < 0.06:  # NaN / Infinity literals
            text = re.sub(
                r"\d+(\.\d+)?", lambda _: self.rng.choice(["NaN", "Infinity", "-Infinity"]), text, count=1
            )
        elif raw < 0.12 and text.startswith("{") and len(text) > 2:  # duplicate key
            text = '{"' + self.marker() + '": 1, ' + text[1:]
            first_key = re.search(r'"([^"]+)":', text[20:])
            if first_key:
                text = text[:-1] + f', "{first_key.group(1)}": {json.dumps(self.evil_value())}' + "}"
        elif raw < 0.16:  # truncated
            text = text[: self.rng.randint(0, max(0, len(text) - 1))]
        elif raw < 0.18:  # random bytes
            return self.rng.randbytes(self.rng.randint(1, 200))
        return text.encode("utf-8", "surrogatepass")


@pytest.fixture(scope="module")
def api(pg_factory: Callable[..., PgCluster]) -> Iterator[tuple[TestClient, CatalogueProvider]]:
    cluster = pg_factory()
    with cluster.connect("ingest") as conn:
        seed.seed_all(conn)
    with seed.client_for(seed.api_settings(cluster.settings())) as pair:
        yield pair


def test_fuzz_post_endpoints(api: tuple[TestClient, CatalogueProvider]) -> None:
    client, _ = api
    rng = random.Random(SEED)  # noqa: S311 - a reproducible test corpus, not security
    fuzzer = Fuzzer(rng)
    statuses: dict[int, int] = {}
    paths = list(TEMPLATES)
    for i in range(TOTAL):
        path = paths[i % len(paths)]
        body = fuzzer.body(TEMPLATES[path])
        response = client.post(path, content=body, headers={"Content-Type": "application/json"})
        statuses[response.status_code] = statuses.get(response.status_code, 0) + 1
        context = f"request {i} to {path}: {body[:300]!r}"
        assert response.status_code in (200, 413, 422), context
        assert response.headers["content-type"] == "application/json; charset=utf-8", context
        assert response.headers["x-content-type-options"] == "nosniff", context
        assert response.headers["cache-control"] == "no-store", context
        assert MARKER_RE.search(response.text) is None, context
        payload = response.json()
        if response.status_code != 200:
            assert set(payload) == {"error", "fields"}, context
            assert all(FIELD_RE.fullmatch(f) for f in payload["fields"]), context
    # the corpus really exercises both outcomes (it is seeded, so these counts are stable)
    assert statuses.get(422, 0) > TOTAL // 2
    assert statuses.get(200, 0) > 50
    assert statuses.get(500, 0) == 0


def test_valid_templates_succeed(api: tuple[TestClient, CatalogueProvider]) -> None:
    client, _ = api
    for path, body in TEMPLATES.items():
        assert client.post(path, json=body).status_code == 200, path
