-- POC-A23 v1: platform task facts only. NOT MAF checkpoint/state backend.
-- Large Artifact/Evidence payload remains in OSS; only opaque refs belong here.
CREATE TABLE IF NOT EXISTS poc_conversations (
  conversation_id text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS poc_turns (
  turn_id text PRIMARY KEY,
  conversation_id text NOT NULL REFERENCES poc_conversations(conversation_id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS poc_runs (
  run_id text PRIMARY KEY,
  turn_id text NOT NULL REFERENCES poc_turns(turn_id),
  initiator_principal_id text NOT NULL,
  runtime_type text NOT NULL,
  recipe_version text NOT NULL,
  state text NOT NULL CHECK (state IN ('CREATED','RUNNING','WAITING_APPROVAL','WAITING_INPUT','CANCELLING','COMPLETED','FAILED','ABORTED','CANCELLED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  terminal_at timestamptz
);
CREATE TABLE IF NOT EXISTS poc_plans (
  plan_id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  version integer NOT NULL CHECK (version > 0),
  parent_plan_id text REFERENCES poc_plans(plan_id),
  reason text NOT NULL,
  UNIQUE (run_id, version)
);
CREATE TABLE IF NOT EXISTS poc_steps (
  step_id text PRIMARY KEY,
  plan_id text NOT NULL REFERENCES poc_plans(plan_id),
  ordinal integer NOT NULL CHECK (ordinal > 0),
  intent text NOT NULL,
  UNIQUE (plan_id, ordinal)
);
CREATE TABLE IF NOT EXISTS poc_attempts (
  attempt_id text PRIMARY KEY,
  step_id text NOT NULL REFERENCES poc_steps(step_id),
  ordinal integer NOT NULL CHECK (ordinal > 0),
  state text NOT NULL CHECK (state IN ('CREATED','QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED','UNKNOWN')),
  failure_type text,
  UNIQUE (step_id, ordinal)
);
CREATE TABLE IF NOT EXISTS poc_executions (
  execution_id text PRIMARY KEY,
  attempt_id text NOT NULL REFERENCES poc_attempts(attempt_id),
  side_effect_class text NOT NULL CHECK (side_effect_class IN ('PURE','IDEMPOTENT','DEDUPLICATED','VERIFY_BEFORE_RETRY','COMPENSATABLE','NON_RETRYABLE')),
  state text NOT NULL CHECK (state IN ('RUNNING','SUCCEEDED','FAILED','CANCELLED','UNKNOWN')),
  failure_type text
);
CREATE TABLE IF NOT EXISTS poc_verifications (
  verification_id text PRIMARY KEY,
  execution_id text NOT NULL UNIQUE REFERENCES poc_executions(execution_id),
  passed boolean NOT NULL,
  evidence_ref text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS poc_events (
  event_id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  seq integer NOT NULL CHECK (seq > 0),
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, seq)
);
CREATE TABLE IF NOT EXISTS poc_runtime_bindings (
  run_id text PRIMARY KEY REFERENCES poc_runs(run_id),
  runtime_type text NOT NULL,
  native_session_ref text,
  runtime_checkpoint_ref text
);
CREATE TABLE IF NOT EXISTS poc_recovery_points (
  recovery_point_id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES poc_runs(run_id),
  step_id text REFERENCES poc_steps(step_id),
  attempt_id text REFERENCES poc_attempts(attempt_id),
  runtime_checkpoint_ref text,
  workspace_state_ref text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Terminal Run cannot be reopened or rewritten (including metadata).
CREATE OR REPLACE FUNCTION poc_reject_terminal_run_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state IN ('COMPLETED','FAILED','ABORTED','CANCELLED') THEN
    RAISE EXCEPTION 'terminal Run cannot be changed: %', OLD.run_id;
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_terminal_run_guard ON poc_runs;
CREATE TRIGGER poc_terminal_run_guard BEFORE UPDATE OR DELETE ON poc_runs
FOR EACH ROW EXECUTE FUNCTION poc_reject_terminal_run_mutation();

-- A finalized Attempt is historical evidence, not a mutable scratchpad.
CREATE OR REPLACE FUNCTION poc_reject_final_attempt_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state IN ('SUCCEEDED','FAILED','CANCELLED','UNKNOWN') THEN
    RAISE EXCEPTION 'final Attempt cannot be changed: %', OLD.attempt_id;
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_final_attempt_guard ON poc_attempts;
CREATE TRIGGER poc_final_attempt_guard BEFORE UPDATE OR DELETE ON poc_attempts
FOR EACH ROW EXECUTE FUNCTION poc_reject_final_attempt_mutation();

-- Final Execution outcome is immutable, just like final Attempt outcome.
CREATE OR REPLACE FUNCTION poc_reject_final_execution_mutation()
RETURNS trigger LANGUAGE plpgsql AS $
BEGIN
  IF OLD.state IN ('SUCCEEDED','FAILED','CANCELLED','UNKNOWN') THEN
    RAISE EXCEPTION 'final Execution cannot be changed: %', OLD.execution_id;
  END IF;
  RETURN NEW;
END;
$;
DROP TRIGGER IF EXISTS poc_final_execution_guard ON poc_executions;
CREATE TRIGGER poc_final_execution_guard BEFORE UPDATE OR DELETE ON poc_executions
FOR EACH ROW EXECUTE FUNCTION poc_reject_final_execution_mutation();

-- Plan versions, events and verification records are append-only facts.
CREATE OR REPLACE FUNCTION poc_reject_fact_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'immutable task fact: %', TG_TABLE_NAME;
END;
$$;
DROP TRIGGER IF EXISTS poc_plan_immutable ON poc_plans;
CREATE TRIGGER poc_plan_immutable BEFORE UPDATE OR DELETE ON poc_plans
FOR EACH ROW EXECUTE FUNCTION poc_reject_fact_mutation();
DROP TRIGGER IF EXISTS poc_event_immutable ON poc_events;
CREATE TRIGGER poc_event_immutable BEFORE UPDATE OR DELETE ON poc_events
FOR EACH ROW EXECUTE FUNCTION poc_reject_fact_mutation();
DROP TRIGGER IF EXISTS poc_verification_immutable ON poc_verifications;
CREATE TRIGGER poc_verification_immutable BEFORE UPDATE OR DELETE ON poc_verifications
FOR EACH ROW EXECUTE FUNCTION poc_reject_fact_mutation();
