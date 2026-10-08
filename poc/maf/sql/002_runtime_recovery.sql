-- POC-A24/A27 small extension. Applies after 001_task_facts.sql.
-- Runtime-private serialized native session state, NOT a platform task fact,
-- checkpoint, or general object/Artifact storage implementation.
CREATE TABLE IF NOT EXISTS poc_maf_sessions (
  run_id text PRIMARY KEY REFERENCES poc_runs(run_id),
  session_ref text NOT NULL UNIQUE,
  provider_fingerprint text NOT NULL,
  revision integer NOT NULL CHECK (revision > 0),
  native_payload jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Reconciliation is an explicit persisted task state after an UNKNOWN
-- non-PURE execution. Re-running the same Attempt is not allowed.
CREATE TABLE IF NOT EXISTS poc_reconciliations (
  execution_id text PRIMARY KEY REFERENCES poc_executions(execution_id),
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  state text NOT NULL CHECK (state IN ('PENDING','RESOLVED','HUMAN_REQUIRED')),
  failure_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS poc_reconciliation_run_idx ON poc_reconciliations(run_id);
