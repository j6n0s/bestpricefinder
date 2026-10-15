"""Pydantic models of the (undocumented) GVH Árfigyelő JSON API, and pure parse functions.

Shapes come from BUILD-BRIEF §4.1 and research/gvh-location (notes.md §1-2, verify.md), corrected against
the real samples captured on 2026-10-14 (``server/tests/fixtures/gvh/raw/``). Every assumption, and what the
samples showed, is listed in ``ASSUMPTIONS.md`` next to this file.

Validation policy ("fail loudly", BUILD-BRIEF §4.1 trap 11):

* **Required** = the fields the ingest uses. A missing required field, a wrong JSON type (a string where a
  number is expected, a number where a string is expected, ``true`` for a number...), an unknown price type,
  NaN/Infinity, or a body that is not JSON (e.g. the SPA's ``index.html``) raises :class:`GvhSchemaError`.
  Models are strict: nothing is coerced.
* Documented fields we do not use are declared as optional so their presence is not reported.
* **Unknown extra fields are accepted** but reported as *drift* (``Model.field`` paths) so the ingest can
  record them as warnings in ``ops.ingest_run``.
* JSON numbers are parsed straight to :class:`~decimal.Decimal` (``parse_float=Decimal``): money never
  passes through ``float``.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, ValidationError

from bpf.gvh.errors import GvhSchemaError

PriceType = Literal["NORMAL", "DISCOUNTED", "LOYALTY"]

#: GVH error code returned by ``/product/{id}/shop/{ids}`` when none of the stores sells the product.
SHOP_PRICES_NOT_FOUND = "PRODUCT-SHOP-PRICES-NOT-FOUND"

_MAX_REPORTED_ERRORS = 5


def _json_decimal(value: object) -> Decimal:
    """A JSON number as Decimal. Rejects booleans, strings, NaN and Infinity (no coercion)."""
    if isinstance(value, bool):
        raise ValueError("expected a JSON number, got a boolean")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("expected a finite number")
        return value
    if isinstance(value, float):  # only when a caller bypasses parse_json (tests); never on the wire path
        if not math.isfinite(value):
            raise ValueError("expected a finite number")
        return Decimal(repr(value))
    raise ValueError(f"expected a JSON number, got {type(value).__name__}")


JsonDecimal = Annotated[Decimal, BeforeValidator(_json_decimal)]

_DECIMAL_STRING_RE = re.compile(r"\d{1,9}(?:\.\d{1,9})?")


def _decimal_string(value: object) -> Decimal:
    """A JSON *string* holding a plain non-negative decimal (``"1"``, ``"0.5"``, ``"0.175"``): how GVH sends
    ``packaging``. Rejects JSON numbers, booleans, empty strings, commas, signs, exponents and spaces."""
    if not isinstance(value, str):
        raise ValueError(f"expected a decimal string, got {type(value).__name__}")
    if not _DECIMAL_STRING_RE.fullmatch(value):
        raise ValueError("expected a decimal string such as '0.5'")
    return Decimal(value)


DecimalString = Annotated[Decimal, BeforeValidator(_decimal_string)]


class GvhModel(BaseModel):
    """Strict, immutable, extra fields allowed (and reported as drift)."""

    model_config = ConfigDict(extra="allow", strict=True, frozen=True)


# ───────────────────────────── reference endpoints ─────────────────────────────


class CategoryNode(GvhModel):
    """One node of ``GET /categories`` (the body is ``{"categories": [top-level nodes]}``)."""

    id: int
    name: str
    path: str
    icon: str | None = None  # null in every real node seen; never used
    categoryNodes: list[CategoryNode] | None = None  # absent, null or [] on leaves


class CategoriesResponse(GvhModel):
    categories: list[CategoryNode]


class ChainStore(GvhModel):
    """One chain of ``GET /chain-stores`` (the body is ``{"chainStores": [...]}``). ``imageUrl`` is a logo key
    such as ``"spar"``; it is never stored or shown."""

    uuid: str
    name: str
    imageUrl: str | None = None


class ChainStoresResponse(GvhModel):
    chainStores: list[ChainStore]


class ShopLocation(GvhModel):
    latitude: JsonDecimal
    longitude: JsonDecimal


class Shop(GvhModel):
    """One store of ``GET /shops`` (the body is ``{"shops": [...]}``). ``openingTime`` is filled in almost
    only for Lidl (``""`` elsewhere)."""

    uuid: str
    chainStoreUuid: str
    postalCode: str | None
    city: str | None
    address: str | None
    location: ShopLocation | None
    openingTime: str | None = None


class ShopsResponse(GvhModel):
    shops: list[Shop]


# ───────────────────────────── prices and products ─────────────────────────────


class PriceEntry(GvhModel):
    """One price of one type. In the listing/detail it is the MINIMUM across the chain's stores for that type
    (BUILD-BRIEF §4.1 trap 1); in ``/product/{id}/shop/{ids}`` it is the real store price."""

    type: PriceType
    amount: JsonDecimal
    unitAmount: JsonDecimal | None
    sameAmountEverywhere: bool | None = None  # listing only


class ListingChainPrices(GvhModel):
    """``pricesOfChainStores[]`` in a listing product. The listing shows at most 3 chains (trap 2)."""

    id: str  # chain uuid (= ChainStore.uuid)
    name: str
    priceSameEverywhere: bool | None  # listing flag follows the 80 % notion (trap 3)
    productMinAmount: JsonDecimal | None  # the daily price charged by >=80 % of carrying stores (trap 1)
    prices: list[PriceEntry]


class ListingProduct(GvhModel):
    id: str
    name: str
    unit: str  # kg | l | db (others are skipped by the ingest)
    unitTitle: str | None  # "kg" = sold by weight (lédig/counter); "csomag" or "db" = fixed pack
    packaging: DecimalString | None  # pack size in `unit`, sent as a string ("0.175")
    bulk: bool | None = None  # unreliable (differs between listing and detail)
    imageUrl: str | None = None  # never used (retailer IP, BUILD-BRIEF §8.3)
    categoryPath: str | None = None  # e.g. "hus_hal_felvagott/szarnyas/csirkemell"; unused
    minUnitPrice: JsonDecimal | None = None  # documented, unused
    returnType: str | None = None  # deposit-return scheme marker (null in every sample); unused
    returnFee: JsonDecimal | None = None  # deposit in Ft, refundable, not part of the price; unused
    pricesOfChainStores: list[ListingChainPrices]


class ProductPage(GvhModel):
    """``GET /products-by-category/{id}?limit=48&offset=N[&shopIds=...]``."""

    products: list[ListingProduct]
    count: int


class DetailChain(GvhModel):
    """One chain in ``GET /product/{id}``: every chain selling the product (no 3-chain cap). Unlike the
    listing, the chain is ``uuid`` (not ``id``) and there is no ``productMinAmount``."""

    uuid: str  # chain uuid (= ChainStore.uuid)
    name: str | None = None
    imageUrl: str | None = None  # logo key such as "spar"; never used
    prices: list[PriceEntry] | None = None
    pricesMax: list[PriceEntry] | None = None
    priceSameEverywhere: bool | None = None  # literal in the detail (trap 3)
    availableInShops: list[str]  # store uuids that report a price for the product


class ProductDetail(GvhModel):
    """``GET /product/{id}``."""

    id: str
    chainStores: list[DetailChain]
    name: str | None = None
    unit: str | None = None
    unitTitle: str | None = None
    packaging: DecimalString | None = None
    bulk: bool | None = None
    imageUrl: str | None = None
    categoryId: str | None = None  # the leaf id as a string ("18"); unused
    categoryPath: str | None = None
    returnType: str | None = None
    returnFee: JsonDecimal | None = None


class ShopPrice(GvhModel):
    shopUuid: str
    prices: list[PriceEntry]
    # The row's own id, next to the store's: seen on 2026-10-15 in the first real 2xx answer of the per-store
    # endpoint (the VM's drift log: "unknown field ShopPrice.uuid"). Unused; declared so it is no longer
    # drift. The raw sample `product-shop-ok` is still to be captured (ASSUMPTIONS.md X3).
    uuid: str | None = None


class ShopPricesResponse(GvhModel):
    """``GET /product/{id}/shop/{uuid1,uuid2,...}``."""

    shops: list[ShopPrice]


# ───────────────────────────── parsing ─────────────────────────────


@dataclass(frozen=True, slots=True)
class Parsed[T]:
    """A parsed response plus the unknown-field paths found in it (``"Model.field"``)."""

    value: T
    drift: tuple[str, ...] = ()


def _reject_constant(name: str) -> object:
    raise ValueError(f"non-finite JSON constant {name}")


def parse_json(content: bytes, *, what: str, content_type: str | None = None) -> object:
    """Decode a JSON body with exact decimals. Not JSON (e.g. the SPA's index.html) -> GvhSchemaError."""
    try:
        return json.loads(content, parse_float=Decimal, parse_constant=_reject_constant)
    except ValueError, UnicodeDecodeError, RecursionError:
        kind = f" (content-type {content_type!r})" if content_type else ""
        raise GvhSchemaError(f"{what}: response is not valid JSON{kind}") from None


def _schema_error(what: str, exc: ValidationError, *, prefix: str = "") -> GvhSchemaError:
    details = []
    for err in exc.errors(include_url=False, include_input=False, include_context=False):
        loc = ".".join(str(part) for part in (prefix, *err["loc"]) if part != "")
        details.append(f"{loc or '<root>'}: {err['type']}")
    shown = "; ".join(details[:_MAX_REPORTED_ERRORS])
    more = f" (+{len(details) - _MAX_REPORTED_ERRORS} more)" if len(details) > _MAX_REPORTED_ERRORS else ""
    return GvhSchemaError(f"{what}: {len(details)} schema error(s): {shown}{more}")


def collect_drift(value: object, found: set[str] | None = None) -> set[str]:
    """Paths (``"Model.field"``) of unknown fields anywhere inside ``value`` (models, lists, tuples)."""
    found = set() if found is None else found
    if isinstance(value, BaseModel):
        for key in value.model_extra or {}:
            found.add(f"{type(value).__name__}.{key}")
        for name in type(value).model_fields:
            collect_drift(getattr(value, name), found)
    elif isinstance(value, list | tuple):
        for item in value:
            collect_drift(item, found)
    return found


def validate_model[M: GvhModel](model: type[M], data: object, *, what: str) -> Parsed[M]:
    try:
        obj = model.model_validate(data)
    except ValidationError as exc:
        raise _schema_error(what, exc) from None
    return Parsed(obj, tuple(sorted(collect_drift(obj))))


def _validate_wrapped(model: type[GvhModel], key: str, data: object, *, what: str) -> Parsed[tuple]:
    """A reference body ``{"<key>": [...]}``: the list's items, and the drift of the wrapper and items."""
    if not isinstance(data, dict):
        raise GvhSchemaError(
            f"{what}: expected a JSON object with {key!r} at the root, got {type(data).__name__}"
        )
    parsed = validate_model(model, data, what=what)
    return Parsed(tuple(getattr(parsed.value, key)), parsed.drift)


def parse_categories(content: bytes, *, content_type: str | None = None) -> Parsed[tuple[CategoryNode, ...]]:
    what = "categories"
    data = parse_json(content, what=what, content_type=content_type)
    return _validate_wrapped(CategoriesResponse, "categories", data, what=what)


def parse_chain_stores(content: bytes, *, content_type: str | None = None) -> Parsed[tuple[ChainStore, ...]]:
    what = "chain-stores"
    data = parse_json(content, what=what, content_type=content_type)
    return _validate_wrapped(ChainStoresResponse, "chainStores", data, what=what)


def parse_shops(content: bytes, *, content_type: str | None = None) -> Parsed[tuple[Shop, ...]]:
    what = "shops"
    data = parse_json(content, what=what, content_type=content_type)
    return _validate_wrapped(ShopsResponse, "shops", data, what=what)


def parse_product_page(
    content: bytes, *, what: str = "products-by-category", content_type: str | None = None
) -> Parsed[ProductPage]:
    return validate_model(ProductPage, parse_json(content, what=what, content_type=content_type), what=what)


def parse_product_detail(
    content: bytes, *, what: str = "product", content_type: str | None = None
) -> Parsed[ProductDetail]:
    return validate_model(ProductDetail, parse_json(content, what=what, content_type=content_type), what=what)


def body_mentions(content: bytes, code: str, *, limit: int = 8192) -> bool:
    """True if the first ``limit`` bytes of a body contain the GVH error code ``code``."""
    return code in content[:limit].decode("utf-8", errors="replace")


def is_shop_prices_not_found(status: int, content: bytes) -> bool:
    """An error status (4xx, or even 5xx: the status is not documented) whose body names
    ``PRODUCT-SHOP-PRICES-NOT-FOUND``: none of the requested stores sells the product."""
    return status >= 400 and body_mentions(content, SHOP_PRICES_NOT_FOUND)


def parse_shop_prices(
    content: bytes, *, what: str = "product-shop", content_type: str | None = None
) -> Parsed[ShopPricesResponse] | None:
    """Parse a 2xx per-store price body. None when the body names ``PRODUCT-SHOP-PRICES-NOT-FOUND`` instead
    of carrying ``shops`` (the error may also arrive as a 4xx: see :func:`is_shop_prices_not_found`)."""
    data = parse_json(content, what=what, content_type=content_type)
    if not (isinstance(data, dict) and "shops" in data) and body_mentions(content, SHOP_PRICES_NOT_FOUND):
        return None
    return validate_model(ShopPricesResponse, data, what=what)


def min_prices(entries: Iterable[PriceEntry]) -> dict[str, PriceEntry]:
    """Per price type, the entry with the lowest amount (ties: the first one)."""
    best: dict[str, PriceEntry] = {}
    for entry in entries:
        current = best.get(entry.type)
        if current is None or entry.amount < current.amount:
            best[entry.type] = entry
    return best


def iter_category_nodes(nodes: Sequence[CategoryNode]) -> Iterable[tuple[CategoryNode, int, CategoryNode]]:
    """Depth-first ``(node, level, top_node)`` over a category tree (level 1 = top)."""
    stack: list[tuple[CategoryNode, int, CategoryNode]] = [(node, 1, node) for node in reversed(nodes)]
    while stack:
        node, level, top = stack.pop()
        yield node, level, top
        for child in reversed(node.categoryNodes or []):
            stack.append((child, level + 1, top))
