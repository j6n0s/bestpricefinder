"""Content pipeline: the ingredient ontology, our recipes and the KSH fallback prices (docs/DATA.md).

``python -m bpf.content`` validates ``data/``, checks the recipe coverage rule and loads everything as
``bpf_ingest`` in one transaction (see :mod:`bpf.content.__main__`). The functions below are the public API
for other packages and tests; they return the domain types of :mod:`bpf.pricing.model`.
"""

from bpf.content.coverage import COVERAGE_THRESHOLD, RecipeCoverage, UnitPrice, compute_coverage
from bpf.content.errors import ContentError
from bpf.content.ksh import load_ksh
from bpf.content.ksh_convert import convert_ksh_file
from bpf.content.load import Content, load_content, load_ingredients
from bpf.content.paths import ContentPaths
from bpf.content.recipes import load_recipes

__all__ = [
    "COVERAGE_THRESHOLD",
    "Content",
    "ContentError",
    "ContentPaths",
    "RecipeCoverage",
    "UnitPrice",
    "compute_coverage",
    "convert_ksh_file",
    "load_content",
    "load_ingredients",
    "load_ksh",
    "load_recipes",
]
