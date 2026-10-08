-- C11: Harness owns lineage, logical Artifact/Evidence identity and tombstones.
-- Actual bytes live ONLY in independent S3-compatible object storage.
CREATE TABLE IF NOT EXISTS poc_c11_runs (
 run_id text PRIMARY KEY REFERENCES poc_runs(run_id),
 native_workflow_id text NOT NULL UNIQUE,
 frozen_workflow_version text NOT NULL,
 frozen_image_digest text NOT NULL CHECK (frozen_image_digest LIKE 'sha256:%'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS poc_c11_sandbox_stages (
 attempt_id text PRIMARY KEY REFERENCES poc_attempts(attempt_id),
 run_id text NOT NULL REFERENCES poc_c11_runs(run_id),
 step_id text NOT NULL UNIQUE REFERENCES poc_steps(step_id),
 execution_id text NOT NULL UNIQUE REFERENCES poc_executions(execution_id),
 ordinal integer NOT NULL CHECK (ordinal IN (1,2)),
 provider text NOT NULL CHECK (provider IN ('docker-oneshot','docker-session')),
 UNIQUE(run_id,ordinal), UNIQUE(run_id,provider)
);
CREATE TABLE IF NOT EXISTS poc_c11_payload_metadata (
 payload_id text PRIMARY KEY,
 run_id text NOT NULL REFERENCES poc_c11_runs(run_id),
 step_id text NOT NULL REFERENCES poc_steps(step_id),
 attempt_id text NOT NULL REFERENCES poc_attempts(attempt_id),
 execution_id text NOT NULL REFERENCES poc_executions(execution_id),
 kind text NOT NULL CHECK (kind IN ('ARTIFACT','EVIDENCE')),
 media_type text NOT NULL,
 sha256_hex text NOT NULL CHECK (sha256_hex ~ '^[0-9a-f]{64}$'),
 size_bytes bigint NOT NULL CHECK (size_bytes > 0),
 storage_ref text,
 payload_status text NOT NULL DEFAULT 'AVAILABLE'
    CHECK (payload_status IN ('AVAILABLE','PURGED')),
 recovery_pinned boolean NOT NULL DEFAULT TRUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 purged_at timestamptz,
 UNIQUE(execution_id,kind),
 CHECK ((payload_status='AVAILABLE' AND storage_ref LIKE 's3://%' AND purged_at IS NULL)
    OR (payload_status='PURGED' AND storage_ref IS NULL AND purged_at IS NOT NULL))
);
CREATE OR REPLACE FUNCTION poc_c11_immutable_binding() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'immutable C11 frozen Sandbox binding'; END IF;
 IF TG_TABLE_NAME='poc_c11_runs' THEN
   IF NOT EXISTS (SELECT 1 FROM poc_runs r WHERE r.run_id=NEW.run_id
      AND r.runtime_type='temporal' AND r.state='RUNNING') THEN
     RAISE EXCEPTION 'C11 binding requires active Temporal Run';
   END IF;
 ELSE
   IF NOT EXISTS (
     SELECT 1 FROM poc_steps s
     JOIN poc_plans p ON p.plan_id=s.plan_id
     JOIN poc_attempts a ON a.step_id=s.step_id
     JOIN poc_executions e ON e.attempt_id=a.attempt_id
     WHERE a.attempt_id=NEW.attempt_id AND s.step_id=NEW.step_id
       AND e.execution_id=NEW.execution_id AND p.run_id=NEW.run_id
       AND s.ordinal=NEW.ordinal AND e.side_effect_class='IDEMPOTENT'
       AND a.state='RUNNING' AND e.state='RUNNING') THEN
     RAISE EXCEPTION 'C11 stage lineage/active state incorrect';
   END IF;
 END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_c11_run_guard ON poc_c11_runs;
CREATE TRIGGER poc_c11_run_guard BEFORE INSERT OR UPDATE OR DELETE ON poc_c11_runs
FOR EACH ROW EXECUTE FUNCTION poc_c11_immutable_binding();
DROP TRIGGER IF EXISTS poc_c11_stage_guard ON poc_c11_sandbox_stages;
CREATE TRIGGER poc_c11_stage_guard BEFORE INSERT OR UPDATE OR DELETE ON poc_c11_sandbox_stages
FOR EACH ROW EXECUTE FUNCTION poc_c11_immutable_binding();

CREATE OR REPLACE FUNCTION poc_c11_payload_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE run_state text;
BEGIN
 SELECT state INTO run_state FROM poc_runs WHERE run_id=COALESCE(NEW.run_id,OLD.run_id);
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Artifact/Evidence lineage cannot be deleted'; END IF;
 IF TG_OP='INSERT' THEN
   IF NOT EXISTS (
     SELECT 1 FROM poc_c11_sandbox_stages b
     JOIN poc_attempts a ON a.attempt_id=b.attempt_id
     JOIN poc_executions e ON e.execution_id=b.execution_id
     WHERE b.run_id=NEW.run_id AND b.step_id=NEW.step_id
       AND b.attempt_id=NEW.attempt_id AND b.execution_id=NEW.execution_id
       AND e.attempt_id=b.attempt_id AND a.step_id=b.step_id
   ) THEN RAISE EXCEPTION 'Artifact/Evidence lineage incorrect'; END IF;
   IF NEW.payload_status<>'AVAILABLE' OR NOT NEW.recovery_pinned THEN
     RAISE EXCEPTION 'New Artifact/Evidence must be pinned and available';
   END IF;
 ELSE
   IF (OLD.payload_id,OLD.run_id,OLD.step_id,OLD.attempt_id,OLD.execution_id,
       OLD.kind,OLD.media_type,OLD.sha256_hex,OLD.size_bytes,OLD.created_at)
      IS DISTINCT FROM
      (NEW.payload_id,NEW.run_id,NEW.step_id,NEW.attempt_id,NEW.execution_id,
       NEW.kind,NEW.media_type,NEW.sha256_hex,NEW.size_bytes,NEW.created_at) THEN
     RAISE EXCEPTION 'Artifact/Evidence immutable lineage/digest';
   END IF;
   IF run_state NOT IN ('COMPLETED','FAILED','ABORTED','CANCELLED') THEN
     RAISE EXCEPTION 'Recoverable active Run payload cannot be released or purged';
   END IF;
   IF OLD.recovery_pinned AND NOT NEW.recovery_pinned
      AND OLD.payload_status='AVAILABLE'
      AND NEW.payload_status='AVAILABLE'
      AND OLD.storage_ref IS NOT DISTINCT FROM NEW.storage_ref
      AND OLD.purged_at IS NOT DISTINCT FROM NEW.purged_at THEN
     RETURN NEW;
   END IF;
   IF NOT OLD.recovery_pinned AND NOT NEW.recovery_pinned
      AND OLD.payload_status='AVAILABLE' AND NEW.payload_status='PURGED'
      AND NEW.storage_ref IS NULL AND NEW.purged_at IS NOT NULL THEN
     RETURN NEW;
   END IF;
   RAISE EXCEPTION 'Forbidden Artifact/Evidence mutation or recovery pin violation';
 END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_c11_payload_lineage ON poc_c11_payload_metadata;
CREATE TRIGGER poc_c11_payload_lineage
BEFORE INSERT OR UPDATE OR DELETE ON poc_c11_payload_metadata
FOR EACH ROW EXECUTE FUNCTION poc_c11_payload_guard();
