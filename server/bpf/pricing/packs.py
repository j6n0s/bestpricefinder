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
* a search over multisets ``X`` of the other packs (labels), where ``b``'s count and the variable weight
  are computed in closed form for each label, described below.

Search
------
The purchase order (cost, leftover, picks, product id) is the lexicographic order of an additive vector:
``W = (cost, quantity bought, picks, -count of each option in product-id rank order)`` (with equal picks,
"more of the lower-ranked option" is exactly "larger count at the first differing rank"; the variable
weight counts as one pick of its option). Labels are taken from a priority queue in increasing ``covered``
(the quantity of ``X``), so every label with less ``covered`` has been taken before, and are extended by
one more pack of any kind within the bounds. A label is dropped when:

* a lexicographic lower bound of (cost, leftover, picks) over every purchase that contains it is above the
  best purchase found: the rest of ``qty`` at ``b``'s unit price (no option is cheaper per unit), at least
  one more pick while ``qty`` is not covered, and the leftover it already has;
* ``covered >= qty + s_b``: such a purchase is always beaten by ``b`` alone (cheaper, or as cheap with
  less leftover);
* dominance. Completing ``X`` with ``k`` packs of ``b`` changes ``W`` by ``k * W(b)``. Take two labels in
  the same residue class of ``covered`` modulo ``s_b`` with ``covered_1 <= covered_2``, and any further
  packs ``Z``. Every completion of ``X_2 + Z`` that can be optimal (it covers less than ``qty + s_b``, see
  above; loose weight beside fewer than the most whole ``b`` packs that fit is dearer) has a counterpart
  for ``X_1 + Z`` with the same variable weight and ``(covered_2 - covered_1) / s_b`` more packs of ``b``,
  and the two compare as the reduced keys ``N(X) = s_b * W(X) - covered(X) * W(b)`` (additive; the
  quantity component is 0): premium ``cost * s_b - covered * c_b``, pick excess ``picks * s_b - covered``,
  then the rank vector. A label whose ``N`` is not below the lowest ``N`` already taken in its residue
  class can therefore never be part of the optimum (equal ``N`` means the same multiset). One exception:
  when the loose option costs exactly ``b``'s unit price (then so does every pack), a "loose weight only"
  completion can be optimal and does not follow ``N``, so only exact duplicates are dropped; the bound
  above then ends the search almost at once.

Search cap
----------
The work is pseudo-polynomial in ``s_b / gcd(all sizes)`` (residue classes) and ``qty / s_b``: real
catalogues need at most a few thousand steps (labels taken plus labels queued), mostly far fewer. As a
safety net for pathological inputs (many packs of near-identical unit price with sizes on a very fine
common grid), one call stops after ``MAX_SEARCH_STEPS`` and returns the best purchase found so far. That
purchase is always a valid covering of ``qty`` and never worse than ``b`` alone (the first label is the
empty one), but it may not be the optimum.
"""

from __future__ import annotations

import functools
import heapq
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


# Safety cap on the work of one search (labels popped plus labels pushed). Real catalogues need a few thousand
# at most; the cap only bounds pathological inputs (module docstring, "Search cap").
MAX_SEARCH_STEPS = 200_000


@dataclass(slots=True)
class _Label:
    """A multiset of the packs other than b (module docstring, "Search")."""

    covered: int  # scaled quantity
    cost: int  # scaled money
    picks: int  # number of packs
    counts: tuple[int, ...]  # per non-b pack
    premium: int  # cost * s_b - covered * c_b (>= 0)
    excess: int  # picks * s_b - covered
    vector: tuple[int, ...] | None = None  # the rest of the reduced key, built on demand


class _Problem:
    """One optimisation problem in scaled integers, searched exactly (see the module docstring)."""

    def __init__(self, qty: int, b: _Pack, others: list[_Pack], var: _Var | None, total_bound: int) -> None:
        self.qty = qty
        self.b = b
        self.others = others
        self.var = var
        self.total_bound = total_bound
        self.best: _Best | None = None
        self.steps = 0
        self.capped = False
        # The reduced key orders labels only when the loose option costs more per unit than b; when it costs
        # exactly b's unit price (then every pack does), only exact duplicates are dropped.
        self.reduced = var is None or var.price * b.size != b.cost
        # The reduced key's rank vector: b (-1) and every other pack (its index), in product-id rank order.
        self.rank_order = sorted([-1, *range(len(others))], key=lambda i: b.rank if i < 0 else others[i].rank)

    def solve(self) -> _Best:
        b = self.b
        root = self._label(0, 0, 0, (0,) * len(self.others))
        heap: list[tuple[int, int, int, int, _Label]] = [(0, 0, 0, 0, root)]
        pushed = 1
        lowest: dict[int, _Label] = {}  # residue of covered modulo s_b -> lowest reduced key popped so far
        seen: set[tuple[int, ...]] = set()
        while heap:
            label = heapq.heappop(heap)[-1]
            self.steps += 1
            if self.steps > MAX_SEARCH_STEPS:
                self.capped = True
                break
            if self.reduced:
                residue = label.covered % b.size
                low = lowest.get(residue)
                if low is not None and not self._less(label, low):
                    continue  # dominated (or a duplicate): see the module docstring
                lowest[residue] = label
            elif label.counts in seen:
                continue
            else:
                seen.add(label.counts)
            if self._bound_exceeds_best(label.covered, label.cost, label.picks):
                continue
            self._leaf(label)
            for child in self._children(label):
                self.steps += 1
                pushed += 1
                heapq.heappush(heap, (child.covered, child.premium, child.excess, pushed, child))
        if self.best is None:  # pragma: no cover - the root (b alone) is the first label popped
            raise AssertionError("no solution found")
        return self.best

    def _label(self, covered: int, cost: int, picks: int, counts: tuple[int, ...]) -> _Label:
        b = self.b
        return _Label(
            covered, cost, picks, counts, cost * b.size - covered * b.cost, picks * b.size - covered
        )

    def _children(self, label: _Label) -> list[_Label]:
        """``label`` plus one more pack, for every pack still within its bounds."""
        if label.picks >= self.total_bound:
            return []
        limit = self.qty + self.b.size  # covering that much alone is always worse than b alone
        children: list[_Label] = []
        for index, pack in enumerate(self.others):
            if label.counts[index] >= pack.bound:
                continue
            covered = label.covered + pack.size
            cost = label.cost + pack.cost
            if covered >= limit or self._bound_exceeds_best(covered, cost, label.picks + 1):
                continue
            counts = label.counts[:index] + (label.counts[index] + 1,) + label.counts[index + 1 :]
            children.append(self._label(covered, cost, label.picks + 1, counts))
        return children

    def _bound_exceeds_best(self, covered: int, cost: int, picks: int) -> bool:
        """Whether a lexicographic lower bound of (cost, leftover, picks) over every purchase that contains
        these packs is above the best purchase found so far: the rest at b's unit price (the best one; the
        variable weight is never cheaper per unit than b, or b would have been pruned) and at least one more
        pick while qty is not covered, or the leftover already bought."""
        best = self.best
        if best is None:
            return False
        b = self.b
        target = (best.cost * b.size, best.leftover, best.picks)
        rest = self.qty - covered
        if rest > 0:
            return (cost * b.size + rest * b.cost, 0, picks + 1) > target
        return (cost * b.size, -rest, picks) > target

    def _less(self, x: _Label, y: _Label) -> bool:
        """Strict order of the reduced key (premium, pick excess, rank vector)."""
        if x.premium != y.premium:
            return x.premium < y.premium
        if x.excess != y.excess:
            return x.excess < y.excess
        return self._vector(x) < self._vector(y)

    def _vector(self, label: _Label) -> tuple[int, ...]:
        """Per option in rank order: ``covered`` for b, s_b * (minus the count) for every other pack."""
        if label.vector is None:
            size = self.b.size
            label.vector = tuple(label.covered if i < 0 else -size * label.counts[i] for i in self.rank_order)
        return label.vector

    def _leaf(self, label: _Label) -> None:
        """Complete ``label`` with b's count and the variable weight in closed form."""
        cost, picks, counts = label.cost, label.picks, label.counts
        rest = self.qty - label.covered
        b = self.b
        if rest <= 0:
            self._consider(cost, -rest, picks, counts, 0, 0)
            return
        full, part = divmod(rest, b.size)
        ceil_count = full + (1 if part else 0)
        leftover = ceil_count * b.size - rest
        self._consider(cost + ceil_count * b.cost, leftover, picks + ceil_count, counts, ceil_count, 0)
        var = self.var
        if var is None:
            return
        # With a variable-weight option the cost is linear in b's count up to `full`; only 0 and `full`
        # (plus the ceiling above) can be optimal.
        for count in (0, full) if full else (0,):
            weight = rest - count * b.size
            if weight > 0:
                total = cost + count * b.cost + weight * var.price
                self._consider(total, 0, picks + count + 1, counts, count, weight)

    def _consider(
        self, cost: int, leftover: int, picks: int, counts: tuple[int, ...], b_count: int, weight: int
    ) -> None:
        best = self.best
        if best is not None:
            mine = (cost, leftover, picks)
            theirs = (best.cost, best.leftover, best.picks)
            if mine > theirs:
                return
            if mine == theirs and self._rank_key(counts, b_count, weight) >= self._rank_key(
                best.counts, best.b_count, best.weight
            ):
                return
        self.best = _Best(cost, leftover, picks, counts, b_count, weight)

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
