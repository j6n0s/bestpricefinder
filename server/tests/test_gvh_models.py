"""Strict pydantic models of the GVH JSON (bpf.gvh.models): required fields, exact types, drift reporting."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from bpf.gvh import GvhSchemaError
from bpf.gvh.models import (
    SHOP_PRICES_NOT_FOUND,
    is_shop_prices_not_found,
    min_prices,
    parse_categories,
    parse_chain_stores,
    parse_json,
    parse_product_detail,
    parse_product_page,
    parse_shop_prices,
    parse_shops,
)

# Key order and JSON types as in the real listing samples of 2026-10-14 (tests/fixtures/gvh/raw/pbc-*.json).
CHAIN = {
    "id": "c1",
    "name": "Spar",
    "priceSameEverywhere": True,
    "productMinAmount": 699.0,
    "prices": [
        {"type": "NORMAL", "amount": 294.0, "unitAmount": 588.0, "sameAmountEverywhere": False},
        {"type": "DISCOUNTED", "amount": 279.0, "unitAmount": 558.0, "sameAmountEverywhere": True},
    ],
}
PRODUCT = {
    "id": "5997490112823",
    "name": "Próbakert spagetti 500 g",
    "imageUrl": "https://cdn.example.invalid/p.png",
    "unit": "kg",
    "unitTitle": "csomag",
    "bulk": False,
    "returnType": None,
    "returnFee": 0,
    "packaging": "0.5",
    "categoryPath": "tartos_elelmiszer_ital/teszta/szarazteszta",
    "minUnitPrice": 1398.0,
    "pricesOfChainStores": [CHAIN],
}


def page(**changes: Any) -> bytes:
    return json.dumps({"products": [{**PRODUCT, **changes}], "count": 1}).encode()


def chain(**changes: Any) -> bytes:
    return page(pricesOfChainStores=[{**CHAIN, **changes}])


def test_listing_page_parses_with_exact_decimals() -> None:
    parsed = parse_product_page(page(packaging="0.285", minUnitPrice=1031.579))
    product = parsed.value.products[0]
    assert parsed.drift == ()
    assert product.packaging == Decimal("0.285")
    assert product.minUnitPrice == Decimal("1031.579")  # parsed from the JSON text, never through float
    entry = product.pricesOfChainStores[0]
    assert entry.productMinAmount == Decimal(699)
    assert [p.type for p in entry.prices] == ["NORMAL", "DISCOUNTED"]


@pytest.mark.parametrize(
    ("body", "location"),
    [
        (chain(productMinAmount="699"), "productMinAmount"),
        (chain(productMinAmount=True), "productMinAmount"),
        (chain(prices=[{"type": "NORMAL", "amount": "294", "unitAmount": 1}]), "amount"),
        (chain(prices=[{"type": "SPECIAL", "amount": 294, "unitAmount": 1}]), "type"),
        (chain(prices=[{"type": "NORMAL", "amount": 294}]), "unitAmount"),
        (chain(priceSameEverywhere="true"), "priceSameEverywhere"),
        (chain(id=12), "id"),
        (page(id=5997490112823), "id"),
        (page(unit=None), "unit"),
        (page(packaging="0,5"), "packaging"),
        (page(packaging=0.5), "packaging"),  # GVH sends packaging as a string; a number is a shape change
        (page(packaging=""), "packaging"),
        (page(packaging=" 0.5"), "packaging"),
        (page(packaging="-1"), "packaging"),
        (page(packaging="1e3"), "packaging"),
        (page(packaging="NaN"), "packaging"),
        (page(packaging=True), "packaging"),
        (page(returnFee="0"), "returnFee"),
    ],
)
def test_wrong_types_fail_loudly(body: bytes, location: str) -> None:
    with pytest.raises(GvhSchemaError, match=location):
        parse_product_page(body)


@pytest.mark.parametrize("field", ["id", "name", "unit", "unitTitle", "packaging", "pricesOfChainStores"])
def test_missing_required_product_fields_fail_loudly(field: str) -> None:
    product = {k: v for k, v in PRODUCT.items() if k != field}
    with pytest.raises(GvhSchemaError, match=f"{field}: missing"):
        parse_product_page(json.dumps({"products": [product], "count": 1}).encode())


@pytest.mark.parametrize("field", ["id", "name", "priceSameEverywhere", "productMinAmount", "prices"])
def test_missing_required_chain_fields_fail_loudly(field: str) -> None:
    entry = {k: v for k, v in CHAIN.items() if k != field}
    with pytest.raises(GvhSchemaError, match=f"{field}: missing"):
        parse_product_page(page(pricesOfChainStores=[entry]))


@pytest.mark.parametrize(
    ("text", "value"), [("1", "1"), ("0.5", "0.5"), ("0.175", "0.175"), ("12.25", "12.25")]
)
def test_packaging_strings_parse_exactly(text: str, value: str) -> None:
    assert parse_product_page(page(packaging=text)).value.products[0].packaging == Decimal(value)


def test_documented_but_unused_fields_are_optional() -> None:
    unused = {"imageUrl", "bulk", "categoryPath", "minUnitPrice", "returnType", "returnFee"}
    product = {k: v for k, v in PRODUCT.items() if k not in unused}
    parsed = parse_product_page(json.dumps({"products": [product], "count": 1}).encode())
    assert parsed.drift == ()


def test_nullable_values() -> None:
    parsed = parse_product_page(chain(productMinAmount=None, priceSameEverywhere=None))
    entry = parsed.value.products[0].pricesOfChainStores[0]
    assert entry.productMinAmount is None
    assert entry.priceSameEverywhere is None


def test_extra_fields_are_reported_as_drift_with_their_model() -> None:
    body = json.dumps(
        {
            "products": [{**PRODUCT, "brand": "x", "pricesOfChainStores": [{**CHAIN, "storeCount": 3}]}],
            "count": 1,
            "page": 0,
        }
    ).encode()
    parsed = parse_product_page(body)
    assert parsed.drift == ("ListingChainPrices.storeCount", "ListingProduct.brand", "ProductPage.page")


def test_errors_never_echo_input_values() -> None:
    secretish = "do-not-echo-this-value"
    with pytest.raises(GvhSchemaError) as err:
        parse_product_page(chain(productMinAmount=secretish))
    assert secretish not in str(err.value)


@pytest.mark.parametrize(
    "body", [b"<!doctype html>", b"", b'{"products": [], "count": NaN}', b'{"a": Infinity}', b"\xff\xfe\x00"]
)
def test_not_json_fails_loudly(body: bytes) -> None:
    with pytest.raises(GvhSchemaError, match="not valid JSON"):
        parse_json(body, what="x")


@pytest.mark.parametrize(
    ("parse", "key"),
    [(parse_categories, "categories"), (parse_chain_stores, "chainStores"), (parse_shops, "shops")],
)
def test_reference_bodies_are_wrapped_objects(parse: Any, key: str) -> None:
    """Real samples (2026-10-14): ``{"categories": [...]}``, ``{"chainStores": [...]}``, ``{"shops": []}``."""
    assert parse(json.dumps({key: []}).encode()).value == ()
    with pytest.raises(GvhSchemaError, match=f"expected a JSON object with '{key}'"):
        parse(b"[]")
    with pytest.raises(GvhSchemaError, match=f"{key}: missing"):
        parse(b'{"items": []}')
    assert parse(json.dumps({key: [], "total": 0}).encode()).drift[0].endswith(".total")


def test_listing_root_must_be_an_object() -> None:
    with pytest.raises(GvhSchemaError, match="products"):
        parse_product_page(b"[]")


def test_categories_accept_every_leaf_terminator() -> None:
    body = json.dumps(
        {
            "categories": [
                {
                    "id": 1001,
                    "name": "Tejtermék, sajt, tojás",
                    "path": "tejtermek_sajt_tojas",
                    "icon": None,
                    "categoryNodes": [
                        {"id": 1, "name": "a", "path": "t/a", "icon": None, "categoryNodes": []},
                        {"id": 2, "name": "b", "path": "t/b", "categoryNodes": None},
                        {"id": 3, "name": "c", "path": "t/c"},
                    ],
                }
            ]
        }
    ).encode()
    parsed = parse_categories(body)
    (top,) = parsed.value
    assert [n.id for n in top.categoryNodes or []] == [1, 2, 3]
    assert parsed.drift == ()


def test_category_ids_must_be_integers() -> None:
    with pytest.raises(GvhSchemaError, match="categories.0.id"):
        parse_categories(b'{"categories": [{"id": "1001", "name": "x", "path": "x"}]}')


def test_chain_stores_and_shops() -> None:
    chains = parse_chain_stores(
        b'{"chainStores": [{"uuid": "u1", "name": "M\\u00fcller", "imageUrl": "mueller"}]}'
    )
    assert chains.value[0].name == "Müller"
    shop = {
        "uuid": "lidl-316",
        "postalCode": "1027",
        "city": "BUDAPEST",
        "address": "Csalogány u. 43",
        "chainStoreUuid": "u1",
        "location": {"latitude": 47.50813, "longitude": 19.03156},
        "openingTime": "Nyitvatartás: 06:30-21:30",
    }

    def shops(*items: dict[str, Any]) -> bytes:
        return json.dumps({"shops": list(items)}).encode()

    (parsed,) = parse_shops(shops(shop)).value
    assert parsed.location is not None
    assert parsed.location.latitude == Decimal("47.50813")
    no_hours = {k: v for k, v in shop.items() if k != "openingTime"}
    assert parse_shops(shops(no_hours, {**shop, "location": None, "openingTime": ""})).drift == ()
    with pytest.raises(GvhSchemaError, match="shops.0.postalCode"):
        parse_shops(shops({**shop, "postalCode": 1027}))
    with pytest.raises(GvhSchemaError, match="chainStoreUuid: missing"):
        parse_shops(shops({k: v for k, v in shop.items() if k != "chainStoreUuid"}))


# The real detail (tests/fixtures/gvh/raw/product-*.json): chain entries carry "uuid", not "id".
DETAIL_CHAIN = {
    "uuid": "c1",
    "name": "Spar",
    "imageUrl": "spar",
    "prices": [{"type": "NORMAL", "amount": 294.0, "unitAmount": 588.0}],
    "pricesMax": [],
    "priceSameEverywhere": False,
    "availableInShops": ["spar-110"],
}


def test_detail_chain_entries_use_uuid() -> None:
    body = {
        "id": "1",
        "name": "x",
        "imageUrl": "https://cdn.example.invalid/p.jpg",
        "unit": "kg",
        "unitTitle": "csomag",
        "bulk": False,
        "returnType": None,
        "returnFee": 0,
        "packaging": "0.5",
        "categoryId": "50",
        "categoryPath": "a/b/c",
        "chainStores": [DETAIL_CHAIN],
    }
    parsed = parse_product_detail(json.dumps(body).encode())
    assert parsed.drift == ()
    assert parsed.value.chainStores[0].uuid == "c1"
    assert parsed.value.chainStores[0].availableInShops == ["spar-110"]
    listing_style = {"id": "c1", **{k: v for k, v in DETAIL_CHAIN.items() if k != "uuid"}}
    with pytest.raises(GvhSchemaError, match="uuid: missing"):
        parse_product_detail(json.dumps({"id": "1", "chainStores": [listing_style]}).encode())
    with pytest.raises(GvhSchemaError, match="availableInShops: missing"):
        parse_product_detail(json.dumps({"id": "1", "chainStores": [{"uuid": "c1"}]}).encode())
    with pytest.raises(GvhSchemaError, match="chainStores: missing"):
        parse_product_detail(json.dumps({"id": "1", "pricesOfChainStores": [DETAIL_CHAIN]}).encode())
    with pytest.raises(GvhSchemaError, match="chainStores: missing"):
        parse_product_detail(b'{"id": "1"}')


def test_shop_prices_and_not_found() -> None:
    ok = parse_shop_prices(
        b'{"shops": [{"shopUuid": "tesco-4062", "prices": [{"type": "NORMAL", '
        b'"amount": 2101, "unitAmount": 2101}]}]}'
    )
    assert ok is not None
    assert ok.value.shops[0].prices[0].amount == Decimal(2101)
    assert ok.drift == ()
    # The real 2xx answer (first seen on the VM on 2026-10-15) carries `uuid` next to `shopUuid`: declared,
    # so it is not drift; a missing one is still fine.
    with_uuid = parse_shop_prices(
        b'{"shops": [{"uuid": "9b6c2d0e-0000-4000-8000-000000000001", "shopUuid": "tesco-4062", '
        b'"prices": [{"type": "NORMAL", "amount": 2101, "unitAmount": 2101}]}]}'
    )
    assert with_uuid is not None
    assert with_uuid.value.shops[0].uuid == "9b6c2d0e-0000-4000-8000-000000000001"
    assert with_uuid.drift == ()
    body = json.dumps(
        {"code": SHOP_PRICES_NOT_FOUND, "message": "Not found prices by product and shops uuid!"}
    )
    body = body.encode()  # the real 404 body (tests/fixtures/gvh/raw/product-shop-notfound.json)
    assert is_shop_prices_not_found(404, body)
    assert is_shop_prices_not_found(400, body)
    assert is_shop_prices_not_found(500, body)  # the status is undocumented: the code decides
    assert not is_shop_prices_not_found(200, body)  # a 2xx body goes through parse_shop_prices
    assert not is_shop_prices_not_found(404, b'{"message": "OTHER"}')
    assert parse_shop_prices(json.dumps({"error": SHOP_PRICES_NOT_FOUND}).encode()) is None
    with pytest.raises(GvhSchemaError, match="shops: missing"):
        parse_shop_prices(b'{"error": "SOMETHING"}')


def test_min_prices_keeps_the_lowest_entry_per_type() -> None:
    entries = (
        parse_product_page(
            chain(
                prices=[
                    {"type": "NORMAL", "amount": 300, "unitAmount": 600},
                    {"type": "NORMAL", "amount": 294, "unitAmount": 588},
                    {"type": "LOYALTY", "amount": 250, "unitAmount": None},
                ]
            )
        )
        .value.products[0]
        .pricesOfChainStores[0]
        .prices
    )
    best = min_prices(entries)
    assert best["NORMAL"].amount == Decimal(294)
    assert best["NORMAL"].unitAmount == Decimal(588)
    assert best["LOYALTY"].unitAmount is None
    assert "DISCOUNTED" not in best
