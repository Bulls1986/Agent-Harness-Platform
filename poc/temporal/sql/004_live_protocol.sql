-- C15 G3 real-model self-host Responses stream; separate platform metadata only.
CREATE TABLE IF NOT EXISTS poc_c15_runs (
 run_id text PRIMARY KEY REFERENCES poc_runs(run_id),
 native_workflow_id text NOT NULL UNIQUE,
 model text NOT NULL,
 frozen_workflow_version text NOT NULL,
 prompt text NOT NULL CHECK (length(prompt) BETWEEN 1 AND 500),
 step_id text NOT NULL UNIQUE REFERENCES poc_steps(step_id),
 attempt_id text NOT NULL UNIQUE REFERENCES poc_attempts(attempt_id),
 execution_id text NOT NULL UNIQUE REFERENCES poc_executions(execution_id),
 start_state text NOT NULL DEFAULT 'PREPARED'
    CHECK (start_state IN ('PREPARED','ACKED','START_UNKNOWN')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION poc_c15_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'C15 binding cannot be deleted'; END IF;
 IF TG_OP='UPDATE' THEN
   IF (NEW.run_id,NEW.native_workflow_id,NEW.model,NEW.frozen_workflow_version,
       NEW.prompt,NEW.step_id,NEW.attempt_id,NEW.execution_id,NEW.created_at)
      IS DISTINCT FROM
      (OLD.run_id,OLD.native_workflow_id,OLD.model,OLD.frozen_workflow_version,
       OLD.prompt,OLD.step_id,OLD.attempt_id,OLD.execution_id,OLD.created_at)
     THEN RAISE EXCEPTION 'C15 frozen binding cannot change'; END IF;
   IF OLD.start_state='ACKED' AND NEW.start_state<>'ACKED'
      THEN RAISE EXCEPTION 'C15 acknowledged start cannot be downgraded'; END IF;
   RETURN NEW;
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM poc_executions e JOIN poc_attempts a ON a.attempt_id=e.attempt_id
   JOIN poc_steps s ON s.step_id=a.step_id JOIN poc_plans p ON p.plan_id=s.plan_id
   JOIN poc_runs r ON r.run_id=p.run_id
   WHERE e.execution_id=NEW.execution_id AND a.attempt_id=NEW.attempt_id
     AND s.step_id=NEW.step_id AND p.run_id=NEW.run_id
     AND r.runtime_type='temporal' AND r.state='RUNNING'
     AND e.side_effect_class='PURE')
 THEN RAISE EXCEPTION 'C15 invalid lineage'; END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_c15_binding_guard ON poc_c15_runs;
CREATE TRIGGER poc_c15_binding_guard BEFORE INSERT OR UPDATE OR DELETE
ON poc_c15_runs FOR EACH ROW EXECUTE FUNCTION poc_c15_guard();

-- C15 RecoveryPoint is an opaque immutable native reference, not a duplicate
-- Temporal checkpoint store or an independently schedulable task.
CREATE OR REPLACE FUNCTION poc_c15_recovery_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_run text;
BEGIN
 IF TG_OP='DELETE' THEN target_run=OLD.run_id;
 ELSE target_run=NEW.run_id; END IF;
 IF NOT EXISTS(SELECT 1 FROM poc_c15_runs WHERE run_id=target_run) THEN
   IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
 END IF;
 IF TG_OP='UPDATE' OR TG_OP='DELETE' THEN
   RAISE EXCEPTION 'C15 recovery reference immutable';
 END IF;
 IF EXISTS (SELECT 1 FROM poc_recovery_points WHERE run_id=target_run) THEN
   RAISE EXCEPTION 'C15 duplicate RecoveryPoint for same Run';
 END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS poc_c15_recovery_guard_trigger ON poc_recovery_points;
CREATE TRIGGER poc_c15_recovery_guard_trigger BEFORE INSERT OR UPDATE OR DELETE
ON poc_recovery_points FOR EACH ROW EXECUTE FUNCTION poc_c15_recovery_guard();
