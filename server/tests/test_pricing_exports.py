"""``bpf.pricing`` re-exports every model type and exactly the ENGINE.md functions with their signatures,
and the engine is pure (no I/O, clock or randomness imports)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import bpf.pricing
from bpf.pricing import model

ENGINE_FUNCTIONS = {
    "fold_name": "(name: 'str') -> 'str'",
    "candidate_products": "(ing: 'Ingredient', cat: 'Catalogue') -> 'tuple[Product, ...]'",
    "to_canonical": "(qty: 'Decimal', product_unit: 'str', ing: 'Ingredient') -> 'Decimal | None'",
    "resolve_price": (
        "(product: 'Product', store: 'Store', cat: 'Catalogue', *, include_loyalty: 'bool' = False)"
        " -> 'ResolvedPrice | None'"
    ),
    "pack_options": (
        "(ing: 'Ingredient', store: 'Store', cat: 'Catalogue', *, include_loyalty: 'bool' = False)"
        " -> 'tuple[PackOption, ...]'"
    ),
    "optimise_packs": "(qty: 'Decimal', options: 'Sequence[PackOption]') -> 'tuple[LinePick, ...] | None'",
    "quote_store": (
        "(lines: 'Sequence[tuple[str, Decimal]]', store: 'Store', cat: 'Catalogue', *,"
        " include_loyalty: 'bool' = False) -> 'StoreQuote'"
    ),
    "rank_stores": "(quotes: 'Sequence[StoreQuote]') -> 'tuple[StoreRank, ...]'",
    "suggest_split": (
        "(quotes: 'Sequence[StoreQuote]', *, threshold: 'Decimal' = Decimal('1500'))"
        " -> 'SplitSuggestion | None'"
    ),
    "recipe_chain_costs": "(recipe: 'Recipe', cat: 'Catalogue') -> 'tuple[ChainRecipeCost, ...]'",
    "build_list": (
        "(items: 'Sequence[tuple[Recipe, Decimal]]', ingredients: 'Mapping[str, Ingredient]', *,"
        " on_hand: 'Mapping[str, Decimal] | None' = None, include_optional: 'bool' = True)"
        " -> 'tuple[ListLine, ...]'"
    ),
    "ingredient_history": (
        "(ing: 'Ingredient', cat: 'Catalogue', rows: 'Iterable[tuple[date, str, str, Decimal | None]]')"
        " -> 'dict[str, tuple[tuple[date, Decimal], ...]]'"
    ),
    "nutrition_per_serving": "(recipe: 'Recipe', cat: 'Catalogue') -> 'NutritionPerServing | None'",
}


def test_every_engine_function_is_exported_with_the_contract_signature() -> None:
    for name, signature in ENGINE_FUNCTIONS.items():
        assert name in bpf.pricing.__all__, name
        assert str(inspect.signature(getattr(bpf.pricing, name))) == signature, name


def _model_public_names() -> set[str]:
    """Every public top-level name defined in model.py (classes, functions, type aliases, constants)."""
    tree = ast.parse(Path(model.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {name for name in names if not name.startswith("_")}


def test_every_model_type_is_re_exported() -> None:
    names = _model_public_names()
    assert {"Catalogue", "PackOption", "LineStatus", "SLOTS_5", "fold_name", "NutritionPerServing"} <= names
    for name in names:
        assert name in bpf.pricing.__all__, name
        assert getattr(bpf.pricing, name) is getattr(model, name), name


def test_all_names_resolve() -> None:
    for name in bpf.pricing.__all__:
        assert hasattr(bpf.pricing, name), name
    assert len(set(bpf.pricing.__all__)) == len(bpf.pricing.__all__)


def test_engine_imports_no_io_clock_or_randomness() -> None:
    forbidden = {
        "os",
        "io",
        "sys",
        "time",
        "datetime.datetime",
        "random",
        "socket",
        "subprocess",
        "pathlib",
        "psycopg",
        "httpx",
        "requests",
        "urllib",
        "sqlite3",
        "shutil",
        "tempfile",
        "secrets",
        "uuid",
    }
    package_dir = Path(bpf.pricing.__file__).parent
    for path in sorted(package_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""} | {f"{node.module}.{alias.name}" for alias in node.names}
            else:
                continue
            assert not names & forbidden, (path.name, names & forbidden)
