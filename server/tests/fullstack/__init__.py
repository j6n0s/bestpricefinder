"""Full-stack end-to-end harness: the REAL system on localhost (docs/E2E.md).

:class:`tests.fullstack.stack.FullStack` brings up a throwaway PostgreSQL cluster (the real
``deploy/local/db-init.sh``), the fake GVH Árfigyelő over HTTP (REAL store list, SYNTHETIC products and
prices), the real ingest CLI, the real content loader and the real API (optionally serving
``web/build``), and tears everything down again. ``python -m tests.fullstack`` runs it as a long-lived
launcher for the Playwright suite in ``web/tests/fullstack/``.
"""

from tests.fullstack.stack import FullStack, StackError, StepResult

__all__ = ["FullStack", "StackError", "StepResult"]
