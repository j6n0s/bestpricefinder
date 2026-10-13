"""Ingredient -> candidate GVH products (ENGINE.md ``candidate_products``).

Pipeline: leaf membership -> include regexes (ANY must match, when there are any) and exclude regexes
(NONE may match) on ``fold_name(product.name)`` -> ``product.unit`` allowed by ``ing.product_units`` (when
non-empty) -> ``product.unit`` convertible to ``ing.unit``. Deterministic order: product id.

Patterns are applied with ``re.search`` exactly as written (lower-case ASCII, per docs/DATA.md); they are
not folded themselves, because folding would turn escapes such as ``\\B`` or ``\\D`` into ``\\b``/``\\d``.

Matching results are memoised per ingredient rule set and per (name, unit) pair. The memo is keyed by
values only (never by object identity), so it can never serve a stale result for a different catalogue.
"""

from __future__ import annotations

import functools
import re
from operator import attrgetter

from bpf.pricing.model import Catalogue, Ingredient, Product, fold_name
from bpf.pricing.units import is_convertible

_MEMO_LIMIT = 200_000  # per rule set; far above the ~4,300 food SKUs, only a guard against unbounded growth


@functools.lru_cache(maxsize=65_536)
def _folded(name: str) -> str:
    return fold_name(name)


class _Matcher:
    """Compiled name and unit rules of one ingredient, with a (name, unit) -> bool memo."""

    __slots__ = ("_exclude", "_include", "_ing", "_memo", "_units")

    def __init__(self, ing: Ingredient) -> None:
        self._ing = ing
        self._include = tuple(re.compile(p) for p in ing.include_patterns)
        self._exclude = tuple(re.compile(p) for p in ing.exclude_patterns)
        self._units = frozenset(ing.product_units)
        self._memo: dict[tuple[str, str], bool] = {}

    def accepts(self, product: Product) -> bool:
        key = (product.name, product.unit)
        hit = self._memo.get(key)
        if hit is None:
            hit = self._evaluate(product.name, product.unit)
            if len(self._memo) < _MEMO_LIMIT:
                self._memo[key] = hit
        return hit

    def _evaluate(self, name: str, unit: str) -> bool:
        if self._units and unit not in self._units:
            return False
        if not is_convertible(unit, self._ing):
            return False
        folded = _folded(name)
        if self._include and not any(p.search(folded) for p in self._include):
            return False
        return not any(p.search(folded) for p in self._exclude)


def _rules_key(ing: Ingredient) -> tuple[object, ...]:
    """Everything a match depends on (and nothing else, so equal rule sets share one matcher)."""
    return (
        tuple(ing.include_patterns),
        tuple(ing.exclude_patterns),
        tuple(ing.product_units),
        ing.unit,
        ing.piece_weight_kg,
        ing.density_kg_per_l,
    )


_MATCHER_LIMIT = 4_096
_matchers: dict[tuple[object, ...], _Matcher] = {}


def _matcher(ing: Ingredient) -> _Matcher:
    """The (shared, memoised) matcher for the ingredient's rule set."""
    key = _rules_key(ing)
    try:
        matcher = _matchers.get(key)
    except TypeError:  # an unhashable rule value: still correct, just not memoised
        return _Matcher(ing)
    if matcher is None:
        if len(_matchers) >= _MATCHER_LIMIT:
            _matchers.clear()
        matcher = _Matcher(ing)
        _matchers[key] = matcher
    return matcher


def product_matches(ing: Ingredient, product: Product) -> bool:
    """True when ``product`` passes the ingredient's name and unit rules (leaf membership not checked)."""
    return _matcher(ing).accepts(product)


def candidate_products(ing: Ingredient, cat: Catalogue) -> tuple[Product, ...]:
    """Products in the ingredient's GVH leaves that pass its name and unit rules, sorted by product id."""
    matcher = _matcher(ing)
    seen: set[str] = set()
    found: list[Product] = []
    for leaf in ing.leaf_ids:
        for product_id in cat.products_by_leaf.get(leaf, ()):
            if product_id in seen:
                continue
            seen.add(product_id)
            product = cat.products.get(product_id)
            if product is not None and matcher.accepts(product):
                found.append(product)
    found.sort(key=attrgetter("id"))
    return tuple(found)
