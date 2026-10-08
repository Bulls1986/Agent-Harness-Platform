-- G6 POC only: immutable intent and externally observed non-idempotent tool receipt.
-- Never store tool payload, credentials or provider-private internals here.
CREATE TABLE IF NOT EXISTS poc_tool_dispatch_intents (
  execution_id text PRIMARY KEY REFERENCES poc_executions(execution_id),
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  attempt_id text NOT NULL REFERENCES poc_attempts(attempt_id),
  adapter_id text NOT NULL,
  operation_id text NOT NULL,
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (adapter_id,operation_id)
);
CREATE TABLE IF NOT EXISTS poc_side_effect_receipts (
  execution_id text PRIMARY KEY REFERENCES poc_tool_dispatch_intents(execution_id),
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  adapter_id text NOT NULL,
  operation_id text NOT NULL,
  external_receipt_id text NOT NULL,
  result_sha256 text NOT NULL CHECK (result_sha256 ~ '^[0-9a-f]{64}$'),
  result_kind text NOT NULL CHECK (result_kind='COMMITTED'),
  observed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (adapter_id,external_receipt_id)
);
-- An observed receipt is immutable evidence. Repeated identically verified
-- observations return ALREADY_RECONCILED without changing these facts.
CREATE OR REPLACE FUNCTION poc_reject_tool_receipt_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'tool receipt is immutable';
END;
$$;
DROP TRIGGER IF EXISTS poc_tool_receipt_immutable ON poc_side_effect_receipts;
CREATE TRIGGER poc_tool_receipt_immutable BEFORE UPDATE OR DELETE ON poc_side_effect_receipts
FOR EACH ROW EXECUTE FUNCTION poc_reject_tool_receipt_mutation();
CREATE OR REPLACE FUNCTION poc_reject_tool_intent_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'tool dispatch intent is immutable';
END;
$$;
DROP TRIGGER IF EXISTS poc_tool_intent_immutable ON poc_tool_dispatch_intents;
CREATE TRIGGER poc_tool_intent_immutable BEFORE UPDATE OR DELETE ON poc_tool_dispatch_intents
FOR EACH ROW EXECUTE FUNCTION poc_reject_tool_intent_mutation();
