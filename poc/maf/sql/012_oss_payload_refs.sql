-- POC-A15: platform-owned small Artifact/Evidence/Workspace metadata only.
-- All bytes are in an external S3-compatible provider. This is not an OSS engine.
CREATE TABLE IF NOT EXISTS poc_payload_refs (
  payload_id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  step_id text NOT NULL REFERENCES poc_steps(step_id),
  attempt_id text NOT NULL REFERENCES poc_attempts(attempt_id),
  execution_id text NOT NULL REFERENCES poc_executions(execution_id),
  kind text NOT NULL CHECK (kind IN ('ARTIFACT','EVIDENCE','WORKSPACE')),
  media_type text NOT NULL,
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  byte_size bigint NOT NULL CHECK (byte_size>=0),
  object_key text,
  retention_policy_ref text NOT NULL,
  payload_status text NOT NULL DEFAULT 'AVAILABLE'
    CHECK (payload_status IN ('AVAILABLE','PURGE_PENDING','PURGED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  purged_at timestamptz,
  CHECK ((payload_status='PURGED' AND object_key IS NULL AND purged_at IS NOT NULL)
    OR (payload_status IN ('AVAILABLE','PURGE_PENDING') AND object_key IS NOT NULL
        AND purged_at IS NULL))
);
CREATE INDEX IF NOT EXISTS poc_payload_refs_run_idx ON poc_payload_refs(run_id,kind);
CREATE TABLE IF NOT EXISTS poc_payload_recovery_pins (
  payload_id text NOT NULL REFERENCES poc_payload_refs(payload_id),
  recovery_point_id text NOT NULL REFERENCES poc_recovery_points(recovery_point_id),
  PRIMARY KEY(payload_id,recovery_point_id)
);
