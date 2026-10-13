"""GVH ingest (docs/ENGINE.md ``bpf.ingest``): reference data, the daily price snapshot and availability.

CLI: ``python -m bpf.ingest {reference|daily|availability} [--date YYYY-MM-DD] [--budapest-only]
[--max-requests N]``. Every run is recorded in ``ops.ingest_run``; see each module's docstring for its rules.
"""

from bpf.ingest.availability import run_availability
from bpf.ingest.common import (
    IngestBusyError,
    IngestError,
    IngestOutcome,
    budapest_today,
)
from bpf.ingest.daily import run_daily
from bpf.ingest.reference import chain_slug, run_reference, store_format

__all__ = [
    "IngestBusyError",
    "IngestError",
    "IngestOutcome",
    "budapest_today",
    "chain_slug",
    "run_availability",
    "run_daily",
    "run_reference",
    "store_format",
]
