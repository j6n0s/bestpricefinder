"""Capture small, unmodified samples of the real GVH Árfigyelő API, the daily XLSX and the KSH ara0044 file.

Run this on a machine that can reach arfigyelo.gvh.hu, the XLSX CDN and www.ksh.hu (the cloud build container
cannot). It writes exactly the files docs/QUESTIONS.md (2026-10-13) asks for, in the format the tests in
server/tests/test_gvh_fixtures.py read:

    server/tests/fixtures/gvh/raw/<name>.json        the response body, byte for byte (shops-head: first 40)
    server/tests/fixtures/gvh/raw/<name>.meta.json   {url, status, fetched_at_utc, content_type, headers, ...}
    server/tests/fixtures/gvh/raw/xlsx-sample.xlsx   header + first 150 rows, sheet name and cell types kept
    data/ksh/raw/<file> (+ .meta.json)               the KSH file exactly as downloaded

Politeness: at most one request per 1.2 s, a User-Agent with your contact e-mail, no retries, no redirects,
and a full stop at the first 403, 429 or 5xx. 18-33 requests in total.

Usage (from server/):
    uv run python tools/capture_gvh_samples.py --contact you@example.com
    uv run pytest tests/test_gvh_fixtures.py -v      # checks every parser against the new samples

Nothing here is used by the app; it is a one-off data-collection tool.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
import openpyxl

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = SERVER_DIR.parent
DEFAULT_OUT = SERVER_DIR / "tests" / "fixtures" / "gvh" / "raw"
DEFAULT_KSH_OUT = REPO_DIR / "data" / "ksh" / "raw"
DEFAULT_BASE = "https://arfigyelo.gvh.hu/api"
DEFAULT_XLSX = "https://cdnarfigyeloprodweu.azureedge.net/excel/arfigyelo_napi_termekadatok.xlsx"
DEFAULT_KSH = "https://www.ksh.hu/stadat_files/ara/hu/ara0044.csv"
KSH_PAGE = "https://www.ksh.hu/stadat_files/ara/hu/ara0044.html"
KEPT_HEADERS = (
    "content-type",
    "content-length",
    "cache-control",
    "last-modified",
    "etag",
    "content-encoding",
    "date",
    "x-cache",
)
XLSX_ROWS = 150
SHOPS_KEPT = 40
MULTICHAIN_TRIES = 15


class Stopped(Exception):
    """A source refused (403/429) or failed (5xx): stop at once, never retry."""


@dataclass
class Capture:
    base: str
    xlsx_url: str
    out: Path
    user_agent: str
    min_interval_s: float
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    client: httpx.Client | None = None
    report: list[dict[str, Any]] = field(default_factory=list)
    _last: float | None = None

    def get(self, url: str) -> httpx.Response:
        if self._last is not None:
            wait = self.min_interval_s - (self.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
        if self.client is None:
            raise RuntimeError("Capture.client is not set")
        try:
            response = self.client.get(url, headers={"User-Agent": self.user_agent})
        finally:
            self._last = self.monotonic()
        if response.status_code in (403, 429) or response.status_code >= 500:
            raise Stopped(f"{urlsplit(url).hostname} answered HTTP {response.status_code} for {url}")
        return response

    def save(self, name: str, url: str, response: httpx.Response, body: bytes, **extra: Any) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / f"{name}.json").write_bytes(body)
        meta = {
            "url": url,
            "status": response.status_code,
            "fetched_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "content_type": response.headers.get("content-type"),
            "headers": {k: v for k, v in response.headers.items() if k.lower() in KEPT_HEADERS},
            "synthetic": False,
            **extra,
        }
        (self.out / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        self.report.append({"name": name, "status": response.status_code, "bytes": len(body), **extra})
        print(f"  {name:<26} HTTP {response.status_code}  {len(body):>8} bytes")

    def api(self, name: str, path: str, params: dict[str, Any] | None = None) -> Any:
        url = self.base + path + (("?" + urlencode(params, safe=",")) if params else "")
        response = self.get(url)
        self.save(name, url, response, response.content)
        try:
            return response.json()
        except ValueError:
            return None


def _products(listing: Any) -> list[dict[str, Any]]:
    products = listing.get("products") if isinstance(listing, dict) else None
    return [p for p in products if isinstance(p, dict)] if isinstance(products, list) else []


def _chain_entries(detail: Any) -> list[dict[str, Any]]:
    """The per-chain list of a product detail, whatever it turns out to be called."""
    if not isinstance(detail, dict):
        return []
    for key in ("chainStores", "pricesOfChainStores"):
        value = detail.get(key)
        if isinstance(value, list):
            return [v for v in value if isinstance(v, dict)]
    return []


def _budapest_shops(shops: Any, chain_id: str | None) -> list[str]:
    if not isinstance(shops, list):
        return []
    found = []
    for shop in shops:
        if not isinstance(shop, dict):
            continue
        postal = str(shop.get("postalCode") or "")
        uuid = str(shop.get("uuid") or "")
        of_chain = shop.get("chainStoreUuid") == chain_id if chain_id else uuid.startswith("tesco-")
        if postal.startswith("1") and len(postal) == 4 and of_chain:
            found.append(uuid)
    return found


def capture_gvh(
    cap: Capture, *, product_a: str, product_b: str, notfound_product: str, notfound_store: str, shop_ids: str
) -> None:
    print(f"GVH API {cap.base}")
    cap.api("categories", "/categories")
    chains = cap.api("chain-stores", "/chain-stores")
    url = cap.base + "/shops"
    response = cap.get(url)
    try:
        shops = response.json() if response.status_code == 200 else None
    except ValueError:
        shops = None  # not JSON: saved as received, and the fixture test will say so
    head = shops[:SHOPS_KEPT] if isinstance(shops, list) else shops
    body = json.dumps(head, ensure_ascii=False).encode() if isinstance(shops, list) else response.content
    cap.save(
        "shops-head",
        url,
        response,
        body,
        full_count=len(shops) if isinstance(shops, list) else None,
        truncated_to=SHOPS_KEPT if isinstance(shops, list) else None,
    )

    first = cap.api("pbc-18-o0", "/products-by-category/18", {"limit": 48, "offset": 0})
    count = first.get("count") if isinstance(first, dict) else None
    if isinstance(count, int) and count > 48:
        cap.api("pbc-18-last", "/products-by-category/18", {"limit": 48, "offset": ((count - 1) // 48) * 48})
    cap.api("pbc-18-default", "/products-by-category/18")
    cap.api("pbc-18-shops", "/products-by-category/18", {"limit": 48, "offset": 0, "shopIds": shop_ids})
    onions = cap.api("pbc-40-o0", "/products-by-category/40", {"limit": 48, "offset": 0})
    yoghurts = cap.api("pbc-7-o0", "/products-by-category/7", {"limit": 48, "offset": 0})

    detail_a = cap.api(f"product-{product_a}", f"/product/{product_a}")
    cap.api(f"product-{product_b}", f"/product/{product_b}")

    # The listing shows at most 3 chains, so only the detail tells; products listed with 3 chains go first.
    listed = [p for listing in (first, yoghurts, onions) for p in _products(listing)]
    listed.sort(key=lambda p: -len(p.get("pricesOfChainStores") or []))
    candidates = [str(p["id"]) for p in listed if p.get("id") and str(p["id"]) not in (product_a, product_b)]
    for pid in list(dict.fromkeys(candidates))[:MULTICHAIN_TRIES]:
        url = f"{cap.base}/product/{pid}"
        response = cap.get(url)
        try:
            entries = _chain_entries(response.json())
        except ValueError:
            entries = []
        if len(entries) >= 4:
            cap.save(
                "product-multichain", url, response, response.content, product_id=pid, chains=len(entries)
            )
            break
    else:
        print(
            f"  product-multichain        none of {min(len(set(candidates)), MULTICHAIN_TRIES)} products "
            "tried is sold by >= 4 chains (skipped)"
        )

    chain_list = chains if isinstance(chains, list) else []
    tesco = next(
        (
            c.get("uuid")
            for c in chain_list
            if isinstance(c, dict) and str(c.get("name", "")).lower().startswith("tesco")
        ),
        None,
    )
    carried: set[str] = set()
    for entry in _chain_entries(detail_a):
        shops_of = entry.get("availableInShops")
        if isinstance(shops_of, list):
            carried.update(str(s) for s in shops_of)
    budapest_tesco = [s for s in _budapest_shops(shops, tesco) if not carried or s in carried][:5]
    if budapest_tesco:
        ids = ",".join(budapest_tesco)
        cap.api("product-shop-ok", f"/product/{product_a}/shop/{ids}")
    else:
        print("  product-shop-ok           no Budapest Tesco store found for the product (skipped)")
    cap.api("product-shop-notfound", f"/product/{notfound_product}/shop/{notfound_store}")
    cap.api("search-400", "/search", {"q": "so"})


def capture_xlsx(cap: Capture, today: str) -> None:
    url = f"{cap.xlsx_url}?{urlencode({'v': today.replace('-', '') + '-capture'})}"
    print(f"Daily XLSX {url}")
    response = cap.get(url)
    if response.status_code != 200:
        print(f"  xlsx-sample.xlsx          HTTP {response.status_code} (skipped)")
        cap.report.append({"name": "xlsx-sample.xlsx", "status": response.status_code})
        return
    source = openpyxl.load_workbook(io.BytesIO(response.content), read_only=True)
    sheet = source.worksheets[0]
    source_sheets = list(source.sheetnames)
    out = openpyxl.Workbook()
    target = out.active
    if target is None:
        raise RuntimeError("openpyxl created a workbook without a sheet")
    target.title = sheet.title
    total = 0
    for index, row in enumerate(sheet.iter_rows(values_only=True)):
        if index <= XLSX_ROWS:
            target.append(list(row))  # the values keep their type: text stays text (decimal commas)
        total += 1
    source.close()
    buffer = io.BytesIO()
    out.save(buffer)
    cap.out.mkdir(parents=True, exist_ok=True)
    (cap.out / "xlsx-sample.xlsx").write_bytes(buffer.getvalue())
    meta = {
        "url": url,
        "status": response.status_code,
        "fetched_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_modified": response.headers.get("last-modified"),
        "original_bytes": len(response.content),
        "original_data_rows": total - 1,
        "kept_data_rows": min(XLSX_ROWS, total - 1),
        "sheet_name": sheet.title,
        "all_sheet_names": source_sheets,
        "synthetic": False,
    }
    (cap.out / "xlsx-sample.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    cap.report.append({"name": "xlsx-sample.xlsx", "status": 200, **meta})
    kept = meta["kept_data_rows"]
    print(f"  xlsx-sample.xlsx          sheet {sheet.title!r}, kept {kept} of {total - 1} data rows")


def capture_ksh(cap: Capture, url: str, out: Path) -> None:
    print(f"KSH {url}")
    response = cap.get(url)
    name = Path(urlsplit(url).path).name or "ara0044"
    out.mkdir(parents=True, exist_ok=True)
    if response.status_code == 200:
        (out / name).write_bytes(response.content)
    meta = {
        "url": url,
        "status": response.status_code,
        "fetched_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
        "licence": "CC BY 4.0, Forrás: KSH",
    }
    (out / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    cap.report.append({"name": f"ksh/{name}", "status": response.status_code, "bytes": len(response.content)})
    print(f"  {name:<26} HTTP {response.status_code}  {len(response.content):>8} bytes")
    if response.status_code != 200 or "html" in (response.headers.get("content-type") or ""):
        print(
            f"  WARNING: not the data file. Open {KSH_PAGE}, download the table's CSV once by hand "
            f"and put it in {out}/ with a .meta.json like this one."
        )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--contact", required=True, help="your e-mail address, sent in the User-Agent")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ksh-out", type=Path, default=DEFAULT_KSH_OUT)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--xlsx-url", default=DEFAULT_XLSX)
    parser.add_argument("--ksh-url", default=DEFAULT_KSH)
    parser.add_argument("--no-ksh", action="store_true")
    parser.add_argument("--product-a", default="2804780000000", help="Tesco counter chicken breast")
    parser.add_argument("--product-b", default="5997490112823", help="Don Francesco spaghetti (Spar outlier)")
    parser.add_argument("--notfound-product", help="product for product-shop-notfound (default: --product-a)")
    parser.add_argument("--notfound-store", default="tesco-4062")
    parser.add_argument("--shop-ids", default="tesco-4030,lidl-274")
    parser.add_argument("--min-interval", type=float, default=1.2, help="seconds between requests (>= 1)")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if "@" not in args.contact:
        parser.error("--contact must be an e-mail address")
    urls = (args.base_url, args.xlsx_url) + (() if args.no_ksh else (args.ksh_url,))
    hosts = {urlsplit(u).hostname for u in urls}
    if args.min_interval < 1.0 and not hosts <= {"127.0.0.1", "localhost"}:
        parser.error("--min-interval below 1 s is only allowed against a local test server")
    today = datetime.now(UTC).date().isoformat()
    cap = Capture(
        base=args.base_url.rstrip("/"),
        xlsx_url=args.xlsx_url,
        out=args.out,
        user_agent=f"bestpricefinder/0.1 (+contact: {args.contact}; fixture capture)",
        min_interval_s=args.min_interval,
    )
    stopped: Stopped | None = None
    with httpx.Client(timeout=60.0, follow_redirects=False) as client:
        cap.client = client
        try:
            capture_gvh(
                cap,
                product_a=args.product_a,
                product_b=args.product_b,
                notfound_product=args.notfound_product or args.product_a,
                notfound_store=args.notfound_store,
                shop_ids=args.shop_ids,
            )
            capture_xlsx(cap, today)
            if not args.no_ksh:
                capture_ksh(cap, args.ksh_url, args.ksh_out)
        except Stopped as error:
            stopped = error
            cap.report.append({"name": "STOPPED", "reason": str(error)})
    args.out.mkdir(parents=True, exist_ok=True)
    report = args.out / "capture-report.txt"
    report.write_text("\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in cap.report) + "\n")
    if stopped is not None:
        print(f"\nSTOPPED: {stopped}. Not retried. Report it; do not run again today. Report: {report}")
        return 1
    print(f"\nDone: {len(cap.report)} items. Report: {report}")
    print("Next: cd server && uv run pytest tests/test_gvh_fixtures.py -v")
    return 0


if __name__ == "__main__":
    sys.exit(main())
