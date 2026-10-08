-- A26: provider-native HITL request and opaque checkpoint binding only.
-- MAF owns checkpoint contents; platform owns Approval and Run lifecycle.
CREATE TABLE IF NOT EXISTS poc_maf_approval_bindings (
  approval_id text PRIMARY KEY REFERENCES poc_approvals(approval_id),
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  native_request_id text NOT NULL UNIQUE,
  native_checkpoint_ref text NOT NULL,
  native_workflow_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (native_request_id <> '' AND native_checkpoint_ref <> '' AND native_workflow_name <> '')
);
CREATE INDEX IF NOT EXISTS poc_maf_approval_bindings_run_idx ON poc_maf_approval_bindings(run_id);
DROP TRIGGER IF EXISTS poc_maf_approval_binding_immutable ON poc_maf_approval_bindings;
CREATE TRIGGER poc_maf_approval_binding_immutable BEFORE UPDATE OR DELETE ON poc_maf_approval_bindings
FOR EACH ROW EXECUTE FUNCTION poc_reject_fact_mutation();
