-- C09: frozen harness Run native binding and two real Agent Runtime stages.
-- Temporal only stores its native History, never the Harness domain facts.
CREATE TABLE IF NOT EXISTS poc_c09_run_bindings (
 run_id text PRIMARY KEY REFERENCES poc_runs(run_id),
 native_workflow_id text NOT NULL UNIQUE,
 frozen_workflow_version text NOT NULL,
 expected_marker text NOT NULL CHECK (expected_marker ~ '^C09-[0-9A-F]{8}$'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS poc_c09_runtime_stages (
 attempt_id text PRIMARY KEY REFERENCES poc_attempts(attempt_id),
 run_id text NOT NULL REFERENCES poc_c09_run_bindings(run_id),
 step_id text NOT NULL UNIQUE REFERENCES poc_steps(step_id),
 execution_id text NOT NULL UNIQUE REFERENCES poc_executions(execution_id),
 ordinal integer NOT NULL CHECK (ordinal IN (1,2)),
 adapter text NOT NULL CHECK (adapter IN ('maf-harness','openai-agents')),
 frozen_runtime_version text NOT NULL,
 UNIQUE (run_id,ordinal),
 UNIQUE (run_id,adapter)
);
CREATE OR REPLACE FUNCTION poc_c09_guard_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'C09 native/adapter binding immutable';
 END IF;
 IF TG_TABLE_NAME='poc_c09_run_bindings' THEN
   IF NOT EXISTS (SELECT 1 FROM poc_runs r WHERE r.run_id=NEW.run_id
      AND r.runtime_type='temporal' AND r.state='RUNNING') THEN
     RAISE EXCEPTION 'C09 Run binding requires active Temporal run';
   END IF;
 ELSE
   IF NOT EXISTS (
    SELECT 1 FROM poc_attempts a
    JOIN poc_steps s ON s.step_id=a.step_id
    JOIN poc_plans p ON p.plan_id=s.plan_id
    JOIN poc_executions e ON e.attempt_id=a.attempt_id
    WHERE a.attempt_id=NEW.attempt_id AND a.step_id=NEW.step_id
      AND e.execution_id=NEW.execution_id AND e.side_effect_class='PURE'
      AND a.state='RUNNING' AND e.state='RUNNING'
      AND p.run_id=NEW.run_id AND s.ordinal=NEW.ordinal
      AND p.version=1
   ) THEN RAISE EXCEPTION 'C09 stage lineage invalid'; END IF;
 END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_c09_run_guard ON poc_c09_run_bindings;
CREATE TRIGGER poc_c09_run_guard BEFORE INSERT OR UPDATE OR DELETE
ON poc_c09_run_bindings FOR EACH ROW EXECUTE FUNCTION poc_c09_guard_immutable();
DROP TRIGGER IF EXISTS poc_c09_stage_guard ON poc_c09_runtime_stages;
CREATE TRIGGER poc_c09_stage_guard BEFORE INSERT OR UPDATE OR DELETE
ON poc_c09_runtime_stages FOR EACH ROW EXECUTE FUNCTION poc_c09_guard_immutable();
