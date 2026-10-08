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
