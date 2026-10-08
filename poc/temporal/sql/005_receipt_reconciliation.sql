-- C16: trusted external business Receipt observed AFTER UNKNOWN quarantine.
CREATE TABLE IF NOT EXISTS poc_c16_reconciled_receipts(
  execution_id text PRIMARY KEY REFERENCES poc_executions(execution_id),
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  attempt_id text NOT NULL REFERENCES poc_attempts(attempt_id),
  receipt_id text NOT NULL UNIQUE,
  external_ref text NOT NULL,
  receipt_sha256 text NOT NULL CHECK(receipt_sha256 ~ '^[0-9a-f]{64}$'),
  external_effect_count integer NOT NULL CHECK(external_effect_count=1),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION poc_c16_immutable_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'C16 receipt proof immutable'; END IF;
 IF NOT EXISTS(SELECT 1 FROM poc_reconciliations r
    JOIN poc_executions e ON e.execution_id=r.execution_id
    JOIN poc_attempts a ON a.attempt_id=e.attempt_id
    JOIN poc_execution_ownership o ON o.execution_id=e.execution_id
    WHERE r.execution_id=NEW.execution_id AND r.run_id=NEW.run_id
      AND r.state='PENDING' AND e.state='UNKNOWN' AND a.state='UNKNOWN'
      AND a.attempt_id=NEW.attempt_id AND o.revoked_at IS NOT NULL)
 THEN RAISE EXCEPTION 'Receipt cannot apply to non-UNKNOWN/unfenced execution'; END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_c16_receipt_guard ON poc_c16_reconciled_receipts;
CREATE TRIGGER poc_c16_receipt_guard
BEFORE INSERT OR UPDATE OR DELETE ON poc_c16_reconciled_receipts
FOR EACH ROW EXECUTE FUNCTION poc_c16_immutable_receipt();
