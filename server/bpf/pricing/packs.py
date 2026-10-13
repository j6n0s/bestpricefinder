"""Buyable options of an ingredient at a store, and exact pack optimisation (ENGINE.md ``pack_options``,
``optimise_packs``; BUILD-BRIEF §6.1).

Pack options
------------
A product is sold by weight ("variable weight") when its folded ``unit_title`` is ``kg`` (GVH's marker for
loose / counter goods priced per kg) or when a ``kg``/``l`` product has no ``packaging`` (a ``db`` product
without packaging is one piece). Its option has ``size`` None and its
price is per canonical unit. Every other product is a fixed pack of ``packaging`` product units. Unit prices
are always recomputed as amount / canonical size; GVH's own ``unitAmount`` is never trusted.

Pack optimisation
-----------------
Given a required quantity ``qty`` and options, choose whole packs (any mix of options, any counts) plus,
optionally, an exact weight of one variable-weight option, covering at least ``qty``. Among all such
purchases the result minimises, in this order:

1. checkout cost;
2. leftover (quantity bought beyond ``qty``);
3. number of picks (packs; a variable-weight purchase counts as one);
4. product id: the purchase that buys more of the option whose product id sorts first wins (options with
   the same product id are ordered by their input position).

The search is exact. Every quantity and price is converted to a scaled integer (no rounding), then:

* only the cheapest variable-weight option can be part of an optimum, and a fixed pack dearer than that
  weight of it is never used;
* Pareto pruning: a pack is dropped when another pack is at least as large and strictly cheaper, or is an
  identical (size, price) duplicate with a later product id;
* ``b`` = the pack with the best unit price (ties: the largest). Exchange arguments bound every other
  pack's count: ``c_i <= ceil(qty / s_i)``; ``c_i < s_b / gcd(s_i, s_b)`` (that many copies of ``i`` can be
  swapped for whole ``b`` packs, strictly better); and their total count ``< s_b / gcd(all sizes)``
  (pigeonhole on partial sums modulo ``s_b``);
* a depth-first search over the other packs' counts with a linear-relaxation lower bound, where ``b``'s
  count and the variable weight are computed in closed form at each leaf.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from bpf.pricing._num import ONE, decimals, div, exact, from_scaled_int, is_positive, to_scaled_int
from bpf.pricing.matching import candidate_products, folded_name
from bpf.pricing.model import Catalogue, Ingredient, LinePick, PackOption, Product, ResolvedPrice, Store
from bpf.pricing.prices import resolve_price
from bpf.pricing.units import convert_units

# ───────────────────────────── pack options ─────────────────────────────


def is_variable_weight(product: Product) -> bool:
    """Sold by weight: GVH unitTitle ``kg`` (loose/counter goods), or a ``kg``/``l`` product without a usable
    ``packaging``. A ``db`` product without packaging is one piece (e.g. "Karfiol db"), never fractional."""
    if product.unit_title is not None and folded_name(product.unit_title) == "kg":
        return True
    if not is_positive(product.packaging):
        return product.unit in ("kg", "l")
    return False


@functools.lru_cache(maxsize=65_536)
@exact
def _basis(
    unit: str,
    variable: bool,
    packaging: Decimal | None,
    ing_unit: str,
    piece_weight: Decimal | None,
    density: Decimal | None,
) -> Decimal | None:
    """Canonical quantity a product's amount is for: one product unit (sold by weight) or one pack."""
    base = ONE if variable or packaging is None else packaging
    qty = convert_units(base, unit, ing_unit, piece_weight, density)
    return qty if is_positive(qty) else None


def canonical_basis(product: Product, ing: Ingredient) -> tuple[bool, Decimal] | None:
    """``(variable_weight, canonical quantity the price amount is for)``; None when not convertible."""
    variable = is_variable_weight(product)
    qty = _basis(
        product.unit, variable, product.packaging, ing.unit, ing.piece_weight_kg, ing.density_kg_per_l
    )
    return None if qty is None else (variable, qty)


def canonical_unit_price(product: Product, amount: Decimal, ing: Ingredient) -> Decimal | None:
    """Price per canonical unit of ``ing``; ``amount`` is per pack, or per product unit if sold by weight."""
    basis = canonical_basis(product, ing)
    if basis is None:
        return None
    qty = basis[1]
    return amount if qty == ONE else div(amount, qty)


def make_option(product: Product, price: ResolvedPrice, ing: Ingredient) -> PackOption | None:
    """The ``PackOption`` for a priced product, in ``ing``'s canonical unit (None when not convertible)."""
    basis = canonical_basis(product, ing)
    if basis is None:
        return None
    variable, qty = basis
    unit_price = price.amount if qty == ONE else div(price.amount, qty)
    return PackOption(
        product_id=product.id,
        product_name=product.name,
        size=None if variable else qty,
        price=unit_price if variable else price.amount,
        unit_price=unit_price,
        price_type=price.price_type,
        scope=price.scope,
        availability=price.availability,
    )


def options_at(
    ing: Ingredient, store: Store, cat: Catalogue, include_loyalty: bool
) -> tuple[PackOption, ...]:
    """Engine-internal :func:`pack_options` without the context switch: call it inside ``exact``."""
    options: list[PackOption] = []
    for product in candidate_products(ing, cat):
        price = resolve_price(product, store, cat, include_loyalty=include_loyalty)
        if price is None:
            continue
        option = make_option(product, price, ing)
        if option is not None:
            options.append(option)
    return tuple(options)


@exact
def pack_options(
    ing: Ingredient, store: Store, cat: Catalogue, *, include_loyalty: bool = False
) -> tuple[PackOption, ...]:
    """Every priced candidate product of ``ing`` at ``store`` as a ``PackOption``, ordered by product id."""
    return options_at(ing, store, cat, include_loyalty)


# ───────────────────────────── pack optimisation ─────────────────────────────


@dataclass(slots=True)
class _Pack:
    rank: int  # position in product-id order (the final tie-break)
    option: PackOption
    size: int = 0  # scaled quantity units
    cost: int = 0  # scaled money units
    bound: int = 0  # max count in an optimum (packs other than b)


@dataclass(slots=True)
class _Var:
    rank: int
    option: PackOption
    price: int = 0  # scaled money units per scaled quantity unit


@dataclass(slots=True)
class _Best:
    cost: int
    leftover: int
    picks: int
    counts: tuple[int, ...]  # per non-b pack
    b_count: int
    weight: int  # variable weight, scaled quantity units


class _Problem:
    """One optimisation problem in scaled integers, searched exactly (see the module docstring)."""

    def __init__(self, qty: int, b: _Pack, others: list[_Pack], var: _Var | None, total_bound: int) -> None:
        self.qty = qty
        self.b = b
        self.others = others
        self.var = var
        self.total_bound = total_bound
        self.counts = [0] * len(others)
        self.best: _Best | None = None

    def solve(self) -> _Best:
        self._dfs(0, 0, 0, 0, self.total_bound)
        if self.best is None:  # pragma: no cover - the all-zero leaf always yields a solution
            raise AssertionError("no solution found")
        return self.best

    def _dfs(self, level: int, covered: int, cost: int, picks: int, budget: int) -> None:
        if level == len(self.others):
            self._leaf(covered, cost, picks)
            return
        pack = self.others[level]
        b = self.b
        for count in range(min(pack.bound, budget) + 1):
            new_covered = covered + count * pack.size
            new_cost = cost + count * pack.cost
            best = self.best
            if best is not None:
                # Lower bound for the whole subtree: the rest at b's unit price (the best one available;
                # the variable weight is never cheaper per unit than b, or b would have been pruned).
                rest = self.qty - new_covered
                bound = new_cost * b.size + (rest * b.cost if rest > 0 else 0)
                if bound > best.cost * b.size:
                    break  # the bound only grows with count
            self.counts[level] = count
            self._dfs(level + 1, new_covered, new_cost, picks + count, budget - count)
        self.counts[level] = 0

    def _leaf(self, covered: int, cost: int, picks: int) -> None:
        rest = self.qty - covered
        b = self.b
        if rest <= 0:
            self._consider(cost, -rest, picks, 0, 0)
            return
        full, part = divmod(rest, b.size)
        ceil_count = full + (1 if part else 0)
        leftover = ceil_count * b.size - rest
        self._consider(cost + ceil_count * b.cost, leftover, picks + ceil_count, ceil_count, 0)
        var = self.var
        if var is None:
            return
        # With a variable-weight option the cost is linear in b's count up to `full`; only 0 and `full`
        # (plus the ceiling above) can be optimal.
        for count in (0, full) if full else (0,):
            weight = rest - count * b.size
            if weight > 0:
                total = cost + count * b.cost + weight * var.price
                self._consider(total, 0, picks + count + 1, count, weight)

    def _consider(self, cost: int, leftover: int, picks: int, b_count: int, weight: int) -> None:
        best = self.best
        if best is not None:
            mine = (cost, leftover, picks)
            theirs = (best.cost, best.leftover, best.picks)
            if mine > theirs:
                return
            if mine == theirs and self._rank_key(tuple(self.counts), b_count, weight) >= self._rank_key(
                best.counts, best.b_count, best.weight
            ):
                return
        self.best = _Best(cost, leftover, picks, tuple(self.counts), b_count, weight)

    def _rank_key(self, counts: tuple[int, ...], b_count: int, weight: int) -> tuple[tuple[int, int], ...]:
        """Final tie-break: more of the lower-ranked (product id) options first."""
        pairs = [(pack.rank, -count) for pack, count in zip(self.others, counts, strict=True) if count]
        if b_count:
            pairs.append((self.b.rank, -b_count))
        if weight and self.var is not None:
            pairs.append((self.var.rank, -1))
        return tuple(sorted(pairs))


def _validate(qty: Decimal, options: Sequence[PackOption]) -> None:
    if not qty.is_finite():
        raise ValueError(f"qty must be finite, got {qty!r}")
    for option in options:
        if option.size is not None and not is_positive(option.size):
            raise ValueError(f"pack size must be > 0: {option.product_id} {option.size!r}")
        if not option.price.is_finite() or option.price < 0:
            raise ValueError(f"price must be finite and >= 0: {option.product_id} {option.price!r}")


def _size(option: PackOption) -> Decimal:
    if option.size is None:  # pragma: no cover - fixed packs only
        raise AssertionError("fixed pack without size")
    return option.size


def _pareto(packs: list[_Pack]) -> list[_Pack]:
    """Drop packs with a strictly cheaper pack at least as large, and exact (size, price) duplicates."""
    kept: list[_Pack] = []
    cheapest_larger: Decimal | None = None  # min price among strictly larger sizes seen so far
    ordered = sorted(packs, key=lambda p: (-_size(p.option), p.option.price, p.rank))
    index = 0
    while index < len(ordered):
        size = ordered[index].option.size
        group_end = index
        while group_end < len(ordered) and ordered[group_end].option.size == size:
            group_end += 1
        head = ordered[index]  # cheapest of this size, lowest rank among equal prices
        if cheapest_larger is None or head.option.price <= cheapest_larger:
            kept.append(head)
        if cheapest_larger is None or head.option.price < cheapest_larger:
            cheapest_larger = head.option.price
        index = group_end
    return kept


def _picks(problem: _Problem, best: _Best, q_places: int) -> tuple[LinePick, ...]:
    picks: list[tuple[int, LinePick]] = []
    for pack, count in zip(problem.others, best.counts, strict=True):
        if count:
            picks.append((pack.rank, _pack_pick(pack.option, count)))
    if best.b_count:
        picks.append((problem.b.rank, _pack_pick(problem.b.option, best.b_count)))
    if best.weight and problem.var is not None:
        weight = from_scaled_int(best.weight, q_places)
        option = problem.var.option
        picks.append((problem.var.rank, LinePick(option, 1, weight, option.price * weight)))
    picks.sort(key=lambda item: item[0])
    return tuple(pick for _, pick in picks)


def _pack_pick(option: PackOption, count: int) -> LinePick:
    return LinePick(option, count, _size(option) * count, option.price * count)


@exact
def optimise_packs(qty: Decimal, options: Sequence[PackOption]) -> tuple[LinePick, ...] | None:
    """Cheapest exact purchase covering ``qty`` (see the module docstring); None if ``options`` is empty.

    A ``qty`` <= 0 needs nothing: the result is an empty tuple."""
    return optimise(qty, options)


def optimise(qty: Decimal, options: Sequence[PackOption]) -> tuple[LinePick, ...] | None:
    """Engine-internal :func:`optimise_packs` without the context switch: call it inside ``exact``."""
    if not options:
        return None
    _validate(qty, options)
    if qty <= 0:
        return ()
    ordered = sorted(options, key=lambda o: o.product_id)  # stable: equal ids keep input order
    fixed = [_Pack(rank, o) for rank, o in enumerate(ordered) if o.size is not None]
    variable = [_Var(rank, o) for rank, o in enumerate(ordered) if o.size is None]
    var = min(variable, key=lambda v: (v.option.price, v.rank)) if variable else None
    if var is not None:
        # A pack dearer than the same weight bought loose is never part of an optimum.
        fixed = [p for p in fixed if p.option.price <= var.option.price * _size(p.option)]
    fixed = _pareto(fixed)

    q_places = max([decimals(qty)] + [decimals(_size(p.option)) for p in fixed])
    p_places = max([0] + [decimals(p.option.price) for p in fixed])
    v_places = decimals(var.option.price) if var is not None else 0
    money_places = max(p_places, v_places + q_places)
    q = to_scaled_int(qty, q_places)
    for pack in fixed:
        pack.size = to_scaled_int(_size(pack.option), q_places)
        pack.cost = to_scaled_int(pack.option.price, money_places)
    if var is not None:
        # cost of w scaled quantity units = price * w * 10**-(v_places + q_places) money units
        var.price = to_scaled_int(var.option.price, v_places) * 10 ** (money_places - v_places - q_places)

    if not fixed:
        if var is None:  # pragma: no cover - options is non-empty and pruning keeps >= 1 pack
            raise AssertionError("no option left")
        weight = qty
        return (LinePick(var.option, 1, weight, var.option.price * weight),)

    # b: best unit price (cost/size), ties -> the largest size (unique after Pareto pruning).
    b = min(fixed, key=lambda p: (Fraction(p.cost, p.size), -p.size))
    others = [p for p in fixed if p is not b]
    others.sort(key=lambda p: (Fraction(p.cost, p.size), -p.size, p.rank))
    for pack in others:
        cover_bound = -(-q // pack.size)
        exchange_bound = b.size // math.gcd(pack.size, b.size) - 1
        pack.bound = min(cover_bound, exchange_bound)
    grid = math.gcd(*(p.size for p in fixed))
    total_bound = b.size // grid - 1
    problem = _Problem(q, b, others, var, total_bound)
    best = problem.solve()
    return _picks(problem, best, q_places)
