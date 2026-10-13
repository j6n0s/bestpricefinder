"""GVH Árfigyelő client (docs/ENGINE.md ``bpf.gvh``): the only package that talks to GVH.

The API is undocumented; the shapes this package assumes are listed in ``ASSUMPTIONS.md`` next to this file.
"""

from bpf.gvh.client import (
    LISTING_LIMIT,
    SHOP_IDS_PER_CALL,
    CategoryListing,
    GvhClient,
    RequestStats,
    build_user_agent,
    random_buster_suffix,
    xlsx_cache_buster,
)
from bpf.gvh.errors import (
    GvhBudgetExceeded,
    GvhConfigError,
    GvhError,
    GvhHttpError,
    GvhSchemaError,
    StaleXlsxError,
)
from bpf.gvh.models import (
    SHOP_PRICES_NOT_FOUND,
    CategoryNode,
    ChainStore,
    DetailChain,
    ListingChainPrices,
    ListingProduct,
    PriceEntry,
    ProductDetail,
    ProductPage,
    Shop,
    ShopLocation,
    ShopPricesResponse,
)
from bpf.gvh.xlsx import HEADERS as XLSX_HEADERS
from bpf.gvh.xlsx import DailyXlsx, XlsxRow, parse_daily_xlsx

__all__ = [
    "LISTING_LIMIT",
    "SHOP_IDS_PER_CALL",
    "SHOP_PRICES_NOT_FOUND",
    "XLSX_HEADERS",
    "CategoryListing",
    "CategoryNode",
    "ChainStore",
    "DailyXlsx",
    "DetailChain",
    "GvhBudgetExceeded",
    "GvhClient",
    "GvhConfigError",
    "GvhError",
    "GvhHttpError",
    "GvhSchemaError",
    "ListingChainPrices",
    "ListingProduct",
    "PriceEntry",
    "ProductDetail",
    "ProductPage",
    "RequestStats",
    "Shop",
    "ShopLocation",
    "ShopPricesResponse",
    "StaleXlsxError",
    "XlsxRow",
    "build_user_agent",
    "parse_daily_xlsx",
    "random_buster_suffix",
    "xlsx_cache_buster",
]
