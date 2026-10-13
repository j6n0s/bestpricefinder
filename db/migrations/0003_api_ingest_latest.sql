-- 0003_api_ingest_latest.sql — let the API see when each kind of ingest last finished successfully.
-- Applied by bpf.migrate as bpf_migrator after `SET LOCAL ROLE bpf_owner` (see 0001 header).
--
-- The API role cannot read ops.ingest_run. It needs the latest finished availability run to apply the
-- Store.has_data rule exactly (docs/ENGINE.md): while no availability run finished within 8 days, every
-- store counts as having data. The view exposes only kind, data date and finish time — no warnings,
-- stats or error text.

CREATE VIEW api.ingest_latest AS
SELECT kind, max(data_date) AS data_date, max(finished_at) AS finished_at
FROM ops.ingest_run
WHERE status IN ('ok', 'partial') AND finished_at IS NOT NULL
GROUP BY kind;

REVOKE ALL ON api.ingest_latest FROM PUBLIC;
GRANT SELECT ON api.ingest_latest TO bpf_api;
