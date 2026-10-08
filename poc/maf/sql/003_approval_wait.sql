-- A26 platform-owned approval waiting facts; no secret material, no IAM replication.
-- The native MAF HITL request and checkpoint must be mapped separately.
CREATE TABLE IF NOT EXISTS poc_approvals (
  approval_id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  step_id text NOT NULL REFERENCES poc_steps(step_id),
  attempt_id text NOT NULL REFERENCES poc_attempts(attempt_id),
  action_ref text NOT NULL,
  resource_ref text NOT NULL,
  policy_ref text NOT NULL,
  requester_principal_id text NOT NULL,
  required_approver_principal_id text NOT NULL,
  state text NOT NULL CHECK (state IN ('PENDING','APPROVED','REJECTED')),
  decided_by_principal_id text,
  decided_at timestamptz,
  CHECK (
    (state='PENDING' AND decided_by_principal_id IS NULL AND decided_at IS NULL)
    OR
    (state IN ('APPROVED','REJECTED') AND decided_by_principal_id IS NOT NULL AND decided_at IS NOT NULL)
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS poc_one_pending_approval_per_run
  ON poc_approvals(run_id) WHERE state='PENDING';

CREATE OR REPLACE FUNCTION poc_approval_decision_immutable()
RETURNS trigger LANGUAGE plpgsql AS $approval_guard$
BEGIN
  IF OLD.state <> 'PENDING' THEN
    RAISE EXCEPTION 'approval decision is immutable: %', OLD.approval_id;
  END IF;
  RETURN NEW;
END;
$approval_guard$;
DROP TRIGGER IF EXISTS poc_approval_history_guard ON poc_approvals;
CREATE TRIGGER poc_approval_history_guard BEFORE UPDATE OR DELETE ON poc_approvals
FOR EACH ROW EXECUTE FUNCTION poc_approval_decision_immutable();
