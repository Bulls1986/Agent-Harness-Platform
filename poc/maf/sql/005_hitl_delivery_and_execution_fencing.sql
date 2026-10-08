-- A26 crash-window recovery and A29 platform-owned Execution fencing only.
-- Not a replacement for MAF / DurableTask / Sandbox internal ownership.
CREATE TABLE IF NOT EXISTS poc_maf_hitl_deliveries (
  approval_id text PRIMARY KEY REFERENCES poc_approvals(approval_id),
  delivery_token text NOT NULL UNIQUE,
  state text NOT NULL CHECK (state IN ('IN_FLIGHT','APPLIED','UNKNOWN')),
  output_kind text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  CHECK ((state = 'APPLIED' AND output_kind IS NOT NULL AND completed_at IS NOT NULL)
      OR (state <> 'APPLIED' AND output_kind IS NULL AND completed_at IS NULL))
);

CREATE TABLE IF NOT EXISTS poc_execution_ownership (
  execution_id text PRIMARY KEY REFERENCES poc_executions(execution_id),
  owner_id text,
  fencing_token bigint NOT NULL CHECK (fencing_token > 0),
  lease_expires_at timestamptz NOT NULL,
  last_heartbeat_at timestamptz NOT NULL DEFAULT now(),
  dispatched_at timestamptz,
  revoked_at timestamptz,
  CHECK (owner_id IS NOT NULL OR revoked_at IS NOT NULL)
);
