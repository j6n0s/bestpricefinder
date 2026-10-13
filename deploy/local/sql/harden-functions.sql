-- harden-functions.sql — close database-level escape hatches that table GRANTs do not cover.
-- Run as the cluster superuser IN THE APP DATABASE (function privileges are per-database catalog objects),
-- with the psql variable dbname set. Idempotent. Used by db-init.sh (new clusters) and db-harden.sh
-- (existing clusters).
--
-- 1. Large objects are writes no table GRANT controls (a bpf_api session could fill the disk with
--    lo_from_bytea). The app never uses them, so no app role may create, import or write one.
REVOKE EXECUTE ON FUNCTION
    pg_catalog.lo_creat(integer), pg_catalog.lo_create(oid), pg_catalog.lo_from_bytea(oid, bytea),
    pg_catalog.lo_import(text), pg_catalog.lo_import(text, oid), pg_catalog.lo_put(oid, bigint, bytea),
    pg_catalog.lowrite(integer, bytea)
FROM PUBLIC;

-- 2. Advisory locks: a bpf_api session holding the ingest's lock would block every daily ingest. Revoke
--    every advisory-lock function from PUBLIC, then grant back exactly what the code uses:
--    bpf.migrate (bpf_migrator): pg_advisory_lock(bigint), released with pg_advisory_unlock(bigint);
--    bpf.ingest (bpf_ingest): pg_try_advisory_lock(int, int) / pg_advisory_unlock(int, int);
--    bpf.content (bpf_ingest): pg_advisory_xact_lock(bigint).
DO $$
DECLARE
    fn regprocedure;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure FROM pg_catalog.pg_proc p
        WHERE p.pronamespace = 'pg_catalog'::regnamespace AND p.proname ~ '^pg_(try_)?advisory_'
    LOOP
        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', fn);
    END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_advisory_lock(bigint), pg_catalog.pg_advisory_unlock(bigint)
    TO bpf_migrator;
GRANT EXECUTE ON FUNCTION pg_catalog.pg_try_advisory_lock(integer, integer),
    pg_catalog.pg_advisory_unlock(integer, integer), pg_catalog.pg_advisory_xact_lock(bigint)
    TO bpf_ingest;

-- 3. temp_file_limit can only be changed by a superuser, so this cap holds even if a bpf_api session
--    overrides its (user-settable) statement_timeout and default_transaction_read_only defaults.
ALTER ROLE bpf_api IN DATABASE :"dbname" SET temp_file_limit = '64MB';

DO $$
BEGIN
    IF has_function_privilege('bpf_api', 'pg_catalog.lo_from_bytea(oid, bytea)', 'EXECUTE')
       OR has_function_privilege('bpf_ingest', 'pg_catalog.lo_creat(integer)', 'EXECUTE')
       OR has_function_privilege('bpf_migrator', 'pg_catalog.lo_from_bytea(oid, bytea)', 'EXECUTE') THEN
        RAISE EXCEPTION 'an app role can still create large objects';
    END IF;
    IF has_function_privilege('bpf_api', 'pg_catalog.pg_try_advisory_lock(integer, integer)', 'EXECUTE')
       OR has_function_privilege('bpf_api', 'pg_catalog.pg_advisory_lock(bigint)', 'EXECUTE') THEN
        RAISE EXCEPTION 'bpf_api can still take advisory locks';
    END IF;
    IF NOT has_function_privilege('bpf_ingest', 'pg_catalog.pg_try_advisory_lock(integer, integer)', 'EXECUTE')
       OR NOT has_function_privilege('bpf_migrator', 'pg_catalog.pg_advisory_lock(bigint)', 'EXECUTE') THEN
        RAISE EXCEPTION 'the ingest or the migrator lost the advisory lock it needs';
    END IF;
END $$;
