"""Pydantic models of the (undocumented) GVH Árfigyelő JSON API, and pure parse functions.

Shapes come from BUILD-BRIEF §4.1 and research/gvh-location (notes.md §1-2, verify.md). Every assumption is
listed in ``ASSUMPTIONS.md`` next to this file so it can be checked against real samples
(``server/tests/fixtures/gvh/raw/``).

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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

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


class GvhModel(BaseModel):
    """Strict, immutable, extra fields allowed (and reported as drift)."""

    model_config = ConfigDict(extra="allow", strict=True, frozen=True)


# ───────────────────────────── reference endpoints ─────────────────────────────


class CategoryNode(GvhModel):
    """``GET /categories``: the root is a JSON array of top-level nodes."""

    id: int
    name: str
    path: str
    categoryNodes: list[CategoryNode] | None = None  # absent, null or [] on leaves


class ChainStore(GvhModel):
    """``GET /chain-stores``: one retail chain. ``imageUrl`` (a logo) is never stored or shown."""

    uuid: str
    name: str
    imageUrl: str | None = None


class ShopLocation(GvhModel):
    latitude: JsonDecimal
    longitude: JsonDecimal


class Shop(GvhModel):
    """``GET /shops``: one store. ``openingTime`` is filled in almost only for Lidl."""

    uuid: str
    chainStoreUuid: str
    postalCode: str | None
    city: str | None
    address: str | None
    location: ShopLocation | None
    openingTime: str | None = None


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
    unitTitle: str | None  # "kg" = sold by weight (lédig/counter), "csomag" = fixed pack
    packaging: JsonDecimal | None  # pack size in `unit`
    bulk: bool | None = None  # unreliable (differs between listing and detail)
    imageUrl: str | None = None  # never used (retailer IP, BUILD-BRIEF §8.3)
    categoryPath: object = None  # documented, unused; its type is not known
    minUnitPrice: JsonDecimal | None = None  # documented, unused
    pricesOfChainStores: list[ListingChainPrices]


class ProductPage(GvhModel):
    """``GET /products-by-category/{id}?limit=48&offset=N[&shopIds=...]``."""

    products: list[ListingProduct]
    count: int


class DetailChain(GvhModel):
    """One chain in ``GET /product/{id}``: every chain selling the product (no 3-chain cap)."""

    id: str
    name: str | None = None
    prices: list[PriceEntry] | None = None
    pricesMax: list[PriceEntry] | None = None
    priceSameEverywhere: bool | None = None  # literal in the detail (trap 3)
    productMinAmount: JsonDecimal | None = None
    availableInShops: list[str]  # store uuids that report a price for the product


class ProductDetail(GvhModel):
    """``GET /product/{id}``. research/gvh-location/notes.md §1 calls the chain list ``chainStores``; the
    listing's name ``pricesOfChainStores`` is accepted too (see ASSUMPTIONS.md)."""

    id: str
    chainStores: list[DetailChain] = Field(
        validation_alias=AliasChoices("chainStores", "pricesOfChainStores")
    )
    name: str | None = None
    unit: str | None = None
    unitTitle: str | None = None
    packaging: JsonDecimal | None = None
    bulk: bool | None = None
    imageUrl: str | None = None
    categoryPath: object = None
    minUnitPrice: JsonDecimal | None = None


class ShopPrice(GvhModel):
    shopUuid: str
    prices: list[PriceEntry]


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


def validate_list[M: GvhModel](model: type[M], data: object, *, what: str) -> Parsed[tuple[M, ...]]:
    """The root must be a JSON array of ``model`` objects."""
    if not isinstance(data, list):
        raise GvhSchemaError(f"{what}: expected a JSON array at the root, got {type(data).__name__}")
    items: list[M] = []
    for index, element in enumerate(data):
        try:
            items.append(model.model_validate(element))
        except ValidationError as exc:
            raise _schema_error(what, exc, prefix=str(index)) from None
    return Parsed(tuple(items), tuple(sorted(collect_drift(items))))


def parse_categories(content: bytes, *, content_type: str | None = None) -> Parsed[tuple[CategoryNode, ...]]:
    what = "categories"
    return validate_list(CategoryNode, parse_json(content, what=what, content_type=content_type), what=what)


def parse_chain_stores(content: bytes, *, content_type: str | None = None) -> Parsed[tuple[ChainStore, ...]]:
    what = "chain-stores"
    return validate_list(ChainStore, parse_json(content, what=what, content_type=content_type), what=what)


def parse_shops(content: bytes, *, content_type: str | None = None) -> Parsed[tuple[Shop, ...]]:
    what = "shops"
    return validate_list(Shop, parse_json(content, what=what, content_type=content_type), what=what)


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
