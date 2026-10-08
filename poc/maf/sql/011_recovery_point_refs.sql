-- G2/G6: extend existing platform RecoveryPoint *references* only.
-- Opaque provider checkpoint contents, snapshots and OSS payload stay external.
ALTER TABLE poc_recovery_points
  ADD COLUMN IF NOT EXISTS runtime_type text;
ALTER TABLE poc_recovery_points
  ADD COLUMN IF NOT EXISTS repository_revision_set jsonb;
ALTER TABLE poc_recovery_points
  ADD COLUMN IF NOT EXISTS environment_fingerprint text;
ALTER TABLE poc_recovery_points
  ADD COLUMN IF NOT EXISTS sandbox_snapshot_ref text;
ALTER TABLE poc_recovery_points
  ADD COLUMN IF NOT EXISTS provider_fingerprint text;
CREATE INDEX IF NOT EXISTS poc_recovery_points_run_created_idx
ON poc_recovery_points(run_id,created_at DESC,recovery_point_id DESC);

CREATE OR REPLACE FUNCTION poc_reject_recovery_point_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'RecoveryPoint references are immutable';
END;
$$;
DROP TRIGGER IF EXISTS poc_recovery_point_immutable ON poc_recovery_points;
CREATE TRIGGER poc_recovery_point_immutable BEFORE UPDATE OR DELETE ON poc_recovery_points
FOR EACH ROW EXECUTE FUNCTION poc_reject_recovery_point_mutation();
