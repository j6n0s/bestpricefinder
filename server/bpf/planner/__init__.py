"""Pure meal planner (docs/ENGINE.md "bpf.planner"): no I/O, no DB, no clock; randomness only from
``random.Random(req.seed)``.

* ``suggest_plan(recipes, ingredients, req) -> Plan``: seeded constraint search; see ``bpf.planner.search``
  for the algorithm and the warning codes.
* ``check_plan(days, recipes, ingredients, *, people, ...) -> tuple[RuleCheck, ...]``: the weekly rules; see
  ``bpf.planner.rules`` for their exact definitions.
"""

from .rules import check_plan
from .search import suggest_plan

__all__ = ["check_plan", "suggest_plan"]
