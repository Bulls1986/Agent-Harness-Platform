-- A34 RUNNING-side durable metadata: PostgreSQL Harness facts only.
-- Authoritative Workflow checkpoint/history remains in official MSSQL TaskHub.
-- This mapping alone is NOT a same-attempt continuation guarantee.
CREATE TABLE IF NOT EXISTS poc_maf_durable_running_bindings (
  execution_id text PRIMARY KEY REFERENCES poc_executions(execution_id),
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  step_id text NOT NULL REFERENCES poc_steps(step_id),
  attempt_id text NOT NULL UNIQUE REFERENCES poc_attempts(attempt_id),
  native_instance_id text NOT NULL UNIQUE,
  native_workflow_name text NOT NULL,
  frozen_workflow_version text NOT NULL,
  frozen_runtime_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (length(native_instance_id) > 0),
  CHECK (length(native_workflow_name) > 0),
  CHECK (length(frozen_workflow_version) > 0),
  CHECK (length(frozen_runtime_version) > 0)
);

CREATE OR REPLACE FUNCTION poc_maf_running_binding_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'native running binding is immutable: %', OLD.execution_id;
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM poc_executions e
    JOIN poc_attempts a ON a.attempt_id=e.attempt_id
    JOIN poc_steps s ON s.step_id=a.step_id
    JOIN poc_plans p ON p.plan_id=s.plan_id
    JOIN poc_runs r ON r.run_id=p.run_id
    WHERE e.execution_id=NEW.execution_id AND e.attempt_id=NEW.attempt_id
      AND a.attempt_id=NEW.attempt_id AND a.step_id=NEW.step_id
      AND p.run_id=NEW.run_id AND r.runtime_type='maf'
      AND r.state='RUNNING' AND a.state='RUNNING' AND e.state='RUNNING'
      AND p.version=(SELECT MAX(version) FROM poc_plans WHERE run_id=NEW.run_id)
  ) THEN
    RAISE EXCEPTION 'invalid active RUNNING execution/native instance lineage';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS poc_maf_running_binding_lineage ON poc_maf_durable_running_bindings;
CREATE TRIGGER poc_maf_running_binding_lineage
  BEFORE INSERT OR UPDATE OR DELETE ON poc_maf_durable_running_bindings
  FOR EACH ROW EXECUTE FUNCTION poc_maf_running_binding_guard();
