-- A29: platform cancellation of a pending Approval is not rejection.
-- Preserve the historical request with a distinct CANCELLED state.
-- Idempotent POC migration (003 creates the original constraints on each init).
ALTER TABLE poc_approvals DROP CONSTRAINT IF EXISTS poc_approvals_state_check;
ALTER TABLE poc_approvals ADD CONSTRAINT poc_approvals_state_check
  CHECK (state IN ('PENDING','APPROVED','REJECTED','CANCELLED'));
ALTER TABLE poc_approvals DROP CONSTRAINT IF EXISTS poc_approvals_check;
ALTER TABLE poc_approvals ADD CONSTRAINT poc_approvals_check
  CHECK ((state IN ('PENDING','CANCELLED') AND decided_by_principal_id IS NULL
          AND decided_at IS NULL)
      OR (state IN ('APPROVED','REJECTED') AND decided_by_principal_id IS NOT NULL
          AND decided_at IS NOT NULL));
