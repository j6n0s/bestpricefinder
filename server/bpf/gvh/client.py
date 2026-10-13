"""The GVH Árfigyelő HTTP client: the only code that talks to GVH (docs/ENGINE.md ``bpf.gvh``).

Politeness and robustness (BUILD-BRIEF §4.1 trap 11, research/legal):

* **Throttle:** at least ``settings.gvh_min_interval_s`` (>= 1 s) between the starts of any two requests,
  retries included. The clock and sleep functions are injectable for tests.
* **User-Agent:** descriptive, with the operator's contact e-mail; the client refuses to start without one.
* **Retries:** at most 3, with exponential backoff, on 5xx and connection/timeouts only. Never on 4xx
  (including 429) or 3xx: those raise :class:`GvhHttpError` immediately. 30 s timeout per request.
* **Budget:** an optional ``max_requests`` cap (CLI ``--max-requests``); every attempt counts.
* **Fail loudly:** every response is validated (``bpf.gvh.models``, ``bpf.gvh.xlsx``); unexpected shapes
  raise :class:`GvhSchemaError`; unknown extra fields are collected in :attr:`GvhClient.drift`.
* **Size cap:** bodies above 32 MB (JSON) / 64 MB (XLSX) are refused.
* Logs carry URL, status and size only: never bodies, never credentials.

Traps handled here: listing paging always sends ``limit=48`` and walks ``offset`` in steps of 48 until
``count`` (the server's default page is 12, so a page shorter than 48 before the end is an error, never a
silent gap); per-store prices are requested in chunks of at most 200 store ids and
``PRODUCT-SHOP-PRICES-NOT-FOUND`` maps to "no prices"; the XLSX URL gets the cache-buster ``?v=YYYYMMDD``
and its sheet date is checked against the expected data date.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from types import TracebackType
from typing import Self
from urllib.parse import quote

import httpx

from bpf.config import Settings
from bpf.gvh.errors import GvhBudgetExceeded, GvhConfigError, GvhHttpError, GvhSchemaError
from bpf.gvh.models import (
    SHOP_PRICES_NOT_FOUND,
    CategoryNode,
    ChainStore,
    ListingProduct,
    PriceEntry,
    ProductDetail,
    Shop,
    body_mentions,
    is_shop_prices_not_found,
    parse_categories,
    parse_chain_stores,
    parse_product_detail,
    parse_product_page,
    parse_shop_prices,
    parse_shops,
)
from bpf.gvh.xlsx import DailyXlsx, parse_daily_xlsx

log = logging.getLogger("bpf.gvh")

LISTING_LIMIT = 48  # server maximum; the default page size is 12 (BUILD-BRIEF §4.1, §11)
SHOP_IDS_PER_CALL = 200  # largest chunk verified to work (research/gvh-location/notes.md §1)
MAX_RETRIES = 3
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_BACKOFF_S = 2.0
API_MAX_BYTES = 32 * 1024 * 1024
XLSX_MAX_BYTES = 64 * 1024 * 1024
MAX_LISTING_PAGES = 500  # 24,000 products in one category: far above the real maximum (about 1,000)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_CONTACT_PLACEHOLDER_RE = re.compile(r"\s*\(\+contact: set BPF_CONTACT_EMAIL\)")
_ERROR_CODE_RE = re.compile(r"[A-Z]{2,}(?:-[A-Z]{2,}){1,8}")
_STORE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_PRODUCT_ID_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_LOG_URL_MAX = 160


def build_user_agent(settings: Settings) -> str:
    """The User-Agent: ``settings.gvh_user_agent`` with ``settings.contact_email`` filled in.

    Raises GvhConfigError when the result carries no contact e-mail address (BUILD-BRIEF §4.1 trap 11)."""
    agent = " ".join(settings.gvh_user_agent.split())  # also strips CR/LF
    email = (settings.contact_email or "").strip()
    if email:
        if not _EMAIL_RE.fullmatch(email):
            raise GvhConfigError("BPF_CONTACT_EMAIL is not a valid e-mail address")
        agent = _CONTACT_PLACEHOLDER_RE.sub("", agent).strip()
        if email not in agent:
            agent = f"{agent} (+contact: {email})"
    if not _EMAIL_RE.search(agent):
        raise GvhConfigError(
            "the GVH User-Agent must contain a contact e-mail address: set BPF_CONTACT_EMAIL"
        )
    return agent


@dataclass(slots=True)
class RequestStats:
    requests: int = 0  # attempts sent, retries included
    bytes: int = 0  # body bytes received (decoded)
    retries: int = 0


@dataclass(frozen=True, slots=True)
class _Response:
    status: int
    content: bytes
    content_type: str | None


@dataclass(frozen=True, slots=True)
class CategoryListing:
    """Every product of one category, collected over all pages."""

    category_id: int
    count: int  # the server's ``count`` (on the last page fetched)
    products: tuple[ListingProduct, ...]  # unique by id, in server order
    pages: int
    duplicates: int  # products seen on more than one page (order shifted between pages)
    count_changed: bool  # ``count`` differed between pages (data changed during paging)

    @property
    def missing(self) -> int:
        """How many of ``count`` products were not collected (0 when complete)."""
        return max(0, self.count - len(self.products))


def _short(url: str) -> str:
    return url if len(url) <= _LOG_URL_MAX else url[: _LOG_URL_MAX - 3] + "..."


def _error_code(content: bytes) -> str | None:
    match = _ERROR_CODE_RE.search(content[:4096].decode("utf-8", errors="replace"))
    return match.group(0) if match else None


def _chunks(items: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _check_product_id(product_id: str) -> None:
    if not _PRODUCT_ID_RE.fullmatch(product_id):
        raise ValueError(f"invalid GVH product id {product_id!r}")


class GvhClient:
    """Synchronous GVH client. Use as a context manager (or call :meth:`close`).

    ``transport`` replaces the network (``httpx.MockTransport`` in tests); ``clock``/``sleep`` drive the
    throttle and the retry backoff (monotonic seconds)."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        max_requests: int | None = None,
        max_retries: int = MAX_RETRIES,
        backoff_s: float = DEFAULT_BACKOFF_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        if max_requests is not None and max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if not 0 <= max_retries <= MAX_RETRIES:
            raise ValueError(f"max_retries must be between 0 and {MAX_RETRIES}")
        if settings.gvh_min_interval_s < 1.0:
            raise GvhConfigError("gvh_min_interval_s must be >= 1.0 (at most one request per second)")
        self.user_agent = build_user_agent(settings)
        self._base = settings.gvh_base_url.rstrip("/")
        self._xlsx_url = settings.gvh_xlsx_url
        self._min_interval = float(settings.gvh_min_interval_s)
        self._clock = clock
        self._sleep = sleep
        self._max_requests = max_requests
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._last_start: float | None = None
        self._http = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(timeout_s),
            headers={"User-Agent": self.user_agent},
            follow_redirects=False,
        )
        self.stats = RequestStats()
        self.drift: dict[str, int] = {}

    # ── lifecycle ──────────────────────────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    # ── transport, throttle, retries ───────────────────────────────────────────────────────────────

    def _before_request(self) -> None:
        if self._max_requests is not None and self.stats.requests >= self._max_requests:
            raise GvhBudgetExceeded(f"the request budget of {self._max_requests} is used up")
        now = self._clock()
        if self._last_start is not None:
            wait = self._last_start + self._min_interval - now
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
        self._last_start = now
        self.stats.requests += 1

    def _send_once(self, url: str, params: dict[str, str] | None, accept: str, max_bytes: int) -> _Response:
        with self._http.stream("GET", url, params=params, headers={"Accept": accept}) as response:
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    self.stats.bytes += size
                    raise GvhHttpError(
                        f"response larger than {max_bytes} bytes",
                        url=_short(str(response.request.url)),
                        status=response.status_code,
                    )
                chunks.append(chunk)
            self.stats.bytes += size
            log.debug(
                "GET %s -> %s (%d bytes)", _short(str(response.request.url)), response.status_code, size
            )
            return _Response(response.status_code, b"".join(chunks), response.headers.get("content-type"))

    def _get(
        self,
        url: str,
        *,
        what: str,
        params: dict[str, str] | None = None,
        accept: str = "application/json",
        xlsx: bool = False,
        final_codes: tuple[str, ...] = (),
    ) -> _Response:
        """One logical GET with throttle, budget and retries (5xx / connection errors only). A 5xx whose
        body names one of ``final_codes`` is a definitive answer and is returned without retrying."""
        max_bytes = XLSX_MAX_BYTES if xlsx else API_MAX_BYTES
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            self._before_request()
            try:
                response = self._send_once(url, params, accept, max_bytes)
            except httpx.DecodingError as exc:  # a corrupt (compressed) body: not a connection error
                raise GvhHttpError(f"{what}: undecodable response body", url=_short(url)) from exc
            except httpx.TransportError as exc:
                log.warning("%s: %s (attempt %d of %d)", what, type(exc).__name__, attempt + 1, attempts)
                if attempt + 1 >= attempts:
                    raise GvhHttpError(
                        f"{what}: connection failed after {attempts} attempt(s) ({type(exc).__name__})",
                        url=_short(url),
                    ) from exc
                self._backoff(attempt)
                continue
            if response.status >= 500 and not any(body_mentions(response.content, c) for c in final_codes):
                log.warning("%s: HTTP %d (attempt %d of %d)", what, response.status, attempt + 1, attempts)
                if attempt + 1 >= attempts:
                    raise GvhHttpError(
                        f"{what}: HTTP {response.status} after {attempts} attempt(s)",
                        url=_short(url),
                        status=response.status,
                    )
                self._backoff(attempt)
                continue
            return response
        raise AssertionError("unreachable")  # pragma: no cover

    def _backoff(self, attempt: int) -> None:
        self.stats.retries += 1
        self._sleep(self._backoff_s * (2**attempt))

    @staticmethod
    def _require_ok(response: _Response, *, what: str, url: str) -> None:
        if not 200 <= response.status < 300:
            code = _error_code(response.content)
            suffix = f" ({code})" if code else ""
            raise GvhHttpError(
                f"{what}: HTTP {response.status}{suffix}", url=_short(url), status=response.status, code=code
            )

    def _note_drift(self, paths: Sequence[str]) -> None:
        for path in paths:
            if path not in self.drift:
                log.warning("GVH schema drift: unknown field %s", path)
            self.drift[path] = self.drift.get(path, 0) + 1

    def _api(self, path: str) -> str:
        return f"{self._base}{path}"

    # ── endpoints ──────────────────────────────────────────────────────────────────────────────────

    def categories(self) -> tuple[CategoryNode, ...]:
        """``GET /categories``: the top-level category nodes (with nested ``categoryNodes``)."""
        url = self._api("/categories")
        response = self._get(url, what="categories")
        self._require_ok(response, what="categories", url=url)
        parsed = parse_categories(response.content, content_type=response.content_type)
        self._note_drift(parsed.drift)
        return parsed.value

    def chain_stores(self) -> tuple[ChainStore, ...]:
        """``GET /chain-stores``: the chains."""
        url = self._api("/chain-stores")
        response = self._get(url, what="chain-stores")
        self._require_ok(response, what="chain-stores", url=url)
        parsed = parse_chain_stores(response.content, content_type=response.content_type)
        self._note_drift(parsed.drift)
        return parsed.value

    def shops(self) -> tuple[Shop, ...]:
        """``GET /shops``: every store."""
        url = self._api("/shops")
        response = self._get(url, what="shops")
        self._require_ok(response, what="shops", url=url)
        parsed = parse_shops(response.content, content_type=response.content_type)
        self._note_drift(parsed.drift)
        return parsed.value

    def products_by_category(self, leaf_id: int, *, shop_ids: Sequence[str] | None = None) -> CategoryListing:
        """Every product of a category (a leaf; level-2 ids work too): ``limit=48`` on every page and
        ``offset`` += 48 until ``count``.

        A page shorter than 48 rows before ``count`` is reached, while ``count`` itself did not change, means
        the server ignored ``limit`` (its default page is 12): that raises GvhSchemaError instead of silently
        skipping rows. If ``count`` changes between pages (data updated while paging), paging follows the
        newest count and the listing is flagged ``count_changed``."""
        if isinstance(leaf_id, bool) or not isinstance(leaf_id, int) or leaf_id < 0:
            raise ValueError(f"invalid category id {leaf_id!r}")
        params_base: dict[str, str] = {"limit": str(LISTING_LIMIT)}
        if shop_ids is not None:
            ids = list(dict.fromkeys(shop_ids))
            for store_id in ids:
                if not _STORE_ID_RE.fullmatch(store_id):
                    raise ValueError(f"invalid store id {store_id!r}")
            params_base["shopIds"] = ",".join(ids)
        what = f"products-by-category/{leaf_id}"
        url = self._api(f"/products-by-category/{leaf_id}")
        products: dict[str, ListingProduct] = {}
        first_count: int | None = None
        count = 0
        count_changed = False
        duplicates = 0
        offset = 0
        pages = 0
        while True:
            if pages >= MAX_LISTING_PAGES:
                raise GvhSchemaError(f"{what}: more than {MAX_LISTING_PAGES} pages")
            params = {**params_base, "offset": str(offset)}
            response = self._get(url, what=what, params=params)
            self._require_ok(response, what=what, url=url)
            parsed = parse_product_page(response.content, what=what, content_type=response.content_type)
            self._note_drift(parsed.drift)
            page = parsed.value
            pages += 1
            if page.count < 0:
                raise GvhSchemaError(f"{what}: negative count")
            count = page.count
            first_count = count if first_count is None else first_count
            count_changed = count_changed or count != first_count
            if len(page.products) > LISTING_LIMIT:
                raise GvhSchemaError(
                    f"{what}: {len(page.products)} rows on a page with limit={LISTING_LIMIT}"
                )
            for product in page.products:
                if product.id in products:
                    duplicates += 1
                else:
                    products[product.id] = product
            offset += LISTING_LIMIT
            if offset >= count:
                break
            if len(page.products) < LISTING_LIMIT:
                if count_changed:
                    break  # the category changed while paging: not a paging fault (reported via the flag)
                raise GvhSchemaError(
                    f"{what}: page at offset {offset - LISTING_LIMIT} has {len(page.products)} rows before "
                    f"count={count}; the server did not honour limit={LISTING_LIMIT}"
                )
        return CategoryListing(
            category_id=leaf_id,
            count=count,
            products=tuple(products.values()),
            pages=pages,
            duplicates=duplicates,
            count_changed=count_changed,
        )

    def product(self, product_id: str) -> ProductDetail:
        """``GET /product/{id}``: every chain selling the product, with ``availableInShops``."""
        _check_product_id(product_id)
        what = "product"
        url = self._api(f"/product/{quote(product_id, safe='')}")
        response = self._get(url, what=what)
        self._require_ok(response, what=what, url=url)
        parsed = parse_product_detail(response.content, what=what, content_type=response.content_type)
        self._note_drift(parsed.drift)
        return parsed.value

    def product_shop_prices(
        self, product_id: str, store_ids: Sequence[str]
    ) -> dict[str, tuple[PriceEntry, ...]]:
        """Real per-store prices: ``GET /product/{id}/shop/{ids}`` in chunks of at most 200 store ids.

        Returns ``{store id: prices}`` for the stores that sell the product; stores that do not are simply
        absent, and a chunk answered with ``PRODUCT-SHOP-PRICES-NOT-FOUND`` contributes nothing."""
        _check_product_id(product_id)
        ids = list(dict.fromkeys(store_ids))
        for store_id in ids:
            if not _STORE_ID_RE.fullmatch(store_id):
                raise ValueError(f"invalid store id {store_id!r}")
        what = "product-shop"
        result: dict[str, list[PriceEntry]] = {}
        for chunk in _chunks(ids, SHOP_IDS_PER_CALL):
            joined = quote(",".join(chunk), safe="")
            url = self._api(f"/product/{quote(product_id, safe='')}/shop/{joined}")
            response = self._get(url, what=what, final_codes=(SHOP_PRICES_NOT_FOUND,))
            if is_shop_prices_not_found(response.status, response.content):
                continue
            self._require_ok(response, what=what, url=url)
            parsed = parse_shop_prices(response.content, what=what, content_type=response.content_type)
            if parsed is None:
                continue
            self._note_drift(parsed.drift)
            for shop in parsed.value.shops:
                result.setdefault(shop.shopUuid, []).extend(shop.prices)
        return {store_id: tuple(prices) for store_id, prices in result.items()}

    def daily_xlsx(self, expected_date: date) -> DailyXlsx:
        """The official daily XLSX, cache-busted with ``?v=YYYYMMDD`` and checked to be ``expected_date``'s
        file (StaleXlsxError otherwise)."""
        what = "daily-xlsx"
        params = {"v": expected_date.strftime("%Y%m%d")}
        response = self._get(self._xlsx_url, what=what, params=params, accept="*/*", xlsx=True)
        self._require_ok(response, what=what, url=self._xlsx_url)
        sheet = parse_daily_xlsx(response.content, expected_date)
        self._note_drift(sheet.drift)
        return sheet
