-- A34: Harness-owned opaque MAF Durable Function instance binding.
-- The runtime history / checkpoint stays inside the MSSQL Durable Provider.
-- A binding alone does not establish Same Attempt execution recovery.
CREATE TABLE IF NOT EXISTS poc_maf_durable_approval_bindings (
  approval_id text PRIMARY KEY REFERENCES poc_approvals(approval_id),
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  step_id text NOT NULL REFERENCES poc_steps(step_id),
  attempt_id text NOT NULL REFERENCES poc_attempts(attempt_id),
  native_instance_id text NOT NULL UNIQUE,
  native_request_id text NOT NULL UNIQUE,
  native_workflow_name text NOT NULL,
  frozen_workflow_version text NOT NULL,
  frozen_runtime_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (length(native_instance_id) > 0),
  CHECK (length(native_request_id) > 0),
  CHECK (length(native_workflow_name) > 0),
  CHECK (length(frozen_workflow_version) > 0),
  CHECK (length(frozen_runtime_version) > 0)
);
CREATE OR REPLACE FUNCTION poc_durable_binding_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'durable approval binding is immutable: %', OLD.approval_id;
END;
$$;
DROP TRIGGER IF EXISTS poc_durable_binding_guard ON poc_maf_durable_approval_bindings;
CREATE TRIGGER poc_durable_binding_guard BEFORE UPDATE OR DELETE
  ON poc_maf_durable_approval_bindings
  FOR EACH ROW EXECUTE FUNCTION poc_durable_binding_immutable();

-- Prevent direct SQL inserts from pairing approval with an unrelated Step,
-- Attempt, Plan, or Run. Separate FKs alone do not enforce this lineage.
CREATE OR REPLACE FUNCTION poc_durable_binding_lineage_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM poc_approvals a
    JOIN poc_runs r ON r.run_id=a.run_id
    JOIN poc_attempts t ON t.attempt_id=a.attempt_id
    JOIN poc_steps s ON s.step_id=t.step_id
    JOIN poc_plans p ON p.plan_id=s.plan_id
    WHERE a.approval_id=NEW.approval_id
      AND a.run_id=NEW.run_id
      AND a.step_id=NEW.step_id
      AND a.attempt_id=NEW.attempt_id
      AND r.state='WAITING_APPROVAL' AND a.state='PENDING'
      AND p.run_id=NEW.run_id
  ) THEN
    RAISE EXCEPTION 'durable approval binding lineage mismatch';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_durable_binding_lineage ON poc_maf_durable_approval_bindings;
CREATE TRIGGER poc_durable_binding_lineage BEFORE INSERT
  ON poc_maf_durable_approval_bindings
  FOR EACH ROW EXECUTE FUNCTION poc_durable_binding_lineage_guard();
