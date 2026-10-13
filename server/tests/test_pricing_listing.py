"""Aggregated shopping list (ENGINE.md ``build_list``; docs/API.md ``POST /api/list``). Synthetic data."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bpf.pricing import build_list
from tests.fixtures.pricing.builders import ingredient, recipe

D = Decimal

INGREDIENTS = {
    i.id: i
    for i in [
        ingredient("alma", list_group="zoldseg_gyumolcs", name_hu="alma"),
        ingredient("anizs", list_group="fuszer_olaj", name_hu="ánizs", pantry=True),
        ingredient("olaj", unit="l", list_group="fuszer_olaj", name_hu="napraforgó olaj", pantry=True),
        ingredient("tojas", unit="db", list_group="tejtermek_tojas", name_hu="tojás", piece_weight="0.06"),
        ingredient("tejfol", list_group="tejtermek_tojas", name_hu="tejföl"),
        ingredient("csirke", list_group="hus_hal", name_hu="csirkemell"),
        ingredient("uborka", list_group="zoldseg_gyumolcs", name_hu="uborka"),
        ingredient("egyedi", list_group="sajat_csoport", name_hu="egyedi dolog"),
        ingredient("zeller", list_group="zoldseg_gyumolcs", name_hu="zeller"),
        ingredient("eper", list_group="zoldseg_gyumolcs", name_hu="Eper"),
    ]
}

PAPRIKAS = recipe("paprikas", 4, [("csirke", "0.6"), ("tejfol", "0.2"), ("olaj", "0.02"), ("anizs", "0.001")])
SALATA = recipe("salata", 2, [("uborka", "0.4"), ("tejfol", "0.1"), ("alma", "0.15", True)])
RANTOTTA = recipe("rantotta", 1, [("tojas", "3"), ("olaj", "0.01")])


def _lines(**kwargs: object) -> dict[str, tuple[Decimal, tuple[str, ...]]]:
    items = kwargs.pop("items")
    result = build_list(items, INGREDIENTS, **kwargs)  # type: ignore[arg-type]
    return {line.ingredient_id: (line.qty, line.recipe_ids) for line in result}


def test_scaling_summing_and_recipe_ids() -> None:
    lines = _lines(items=[(PAPRIKAS, D(2)), (SALATA, D(3)), (RANTOTTA, D(2))])
    assert lines["csirke"] == (D("0.3"), ("paprikas",))  # 0.6 x 2/4
    assert lines["tejfol"] == (D("0.25"), ("paprikas", "salata"))  # 0.2 x 2/4 + 0.1 x 3/2
    assert lines["uborka"] == (D("0.6"), ("salata",))
    assert lines["alma"] == (D("0.225"), ("salata",))  # optional, included by default
    assert lines["tojas"] == (D(6), ("rantotta",))
    assert lines["olaj"] == (D("0.03"), ("paprikas", "rantotta"))  # 0.02 x 2/4 + 0.01 x 2


def test_same_recipe_twice_is_summed_and_listed_once() -> None:
    lines = _lines(items=[(RANTOTTA, D(1)), (RANTOTTA, D("1.5"))])
    assert lines["tojas"] == (D("7.5"), ("rantotta",))


def test_include_optional_false_drops_optional_lines() -> None:
    assert "alma" not in _lines(items=[(SALATA, D(2))], include_optional=False)


def test_on_hand_is_subtracted_and_lines_at_or_below_zero_are_dropped() -> None:
    lines = _lines(
        items=[(PAPRIKAS, D(4)), (RANTOTTA, D(1))],
        on_hand={"tojas": D(3), "csirke": D("0.25"), "tejfol": D("0.5"), "nincs_listan": D(1)},
    )
    assert "tojas" not in lines  # exactly zero
    assert "tejfol" not in lines  # negative
    assert lines["csirke"] == (D("0.35"), ("paprikas",))


def test_exact_arithmetic_then_half_up_rounding_to_the_api_grid() -> None:
    thirds = recipe("harmad", 3, [("csirke", "0.1"), ("tejfol", "0.001")])
    lines = _lines(items=[(thirds, D(1)), (thirds, D(1)), (thirds, D(1))], on_hand={"csirke": D("0.0995")})
    # 3 x 0.1/3 = 0.1 exactly; minus 0.0995 = 0.0005 -> rounds half-up to 0.001 (not lost to 28-digit noise)
    assert lines["csirke"][0] == D("0.001")
    # 3 x 0.001/3 = 0.001
    assert lines["tejfol"][0] == D("0.001")
    tiny = _lines(items=[(thirds, D(1))], on_hand={"csirke": D("0.0333")})
    assert "csirke" not in tiny  # 0.1/3 - 0.0333 = 0.0000333... rounds to 0 -> dropped


def test_sort_order_by_list_group_then_folded_name() -> None:
    every = recipe(
        "minden",
        1,
        [
            (ing_id, "1")
            for ing_id in ["egyedi", "olaj", "anizs", "csirke", "tejfol", "tojas", "uborka", "alma"]
        ]
        + [("zeller", "1"), ("eper", "1")],
    )
    result = build_list([(every, D(1))], INGREDIENTS)
    assert [line.ingredient_id for line in result] == [
        "alma",  # zoldseg_gyumolcs: alma < Eper < uborka < zeller (case- and accent-insensitive)
        "eper",
        "uborka",
        "zeller",
        "tejfol",  # tejtermek_tojas: tejföl < tojás
        "tojas",
        "csirke",  # hus_hal
        "anizs",  # fuszer_olaj: ánizs sorts with the a's
        "olaj",
        "egyedi",  # unknown group last
    ]


def test_line_fields_and_pantry_flag() -> None:
    (line,) = build_list([(recipe("r", 1, [("olaj", "0.5")]), D(1))], INGREDIENTS)
    assert (line.unit, line.list_group, line.pantry) == ("l", "fuszer_olaj", True)


def test_unknown_ingredient_raises_key_error() -> None:
    with pytest.raises(KeyError):
        build_list([(recipe("r", 1, [("nincs", "1")]), D(1))], INGREDIENTS)


@pytest.mark.parametrize("servings", ["0", "-1", "NaN"])
def test_invalid_servings_raise(servings: str) -> None:
    with pytest.raises(ValueError, match="servings|finite"):
        build_list([(RANTOTTA, D(servings))], INGREDIENTS)


def test_empty_items() -> None:
    assert build_list([], INGREDIENTS) == ()
