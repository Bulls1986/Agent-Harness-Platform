"""Fail-closed *reporting* contract for the DEV-M5-B03 live scenario.

This validates correlations in a proof observed by the trusted live verifier.
It is not, by itself, evidence that Hatchet, PostgreSQL or Cube actually ran.
"""


def validate_joint_evidence(evidence: dict) -> None:
    required_ids = (
        "run_id", "execution_id", "workflow_run_id", "a_cube_id", "b_cube_id",
    )
    if not isinstance(evidence, dict) or any(
        not isinstance(evidence.get(key), str) or not evidence[key]
        for key in required_ids
    ):
        raise ValueError("Missing correlated physical/Cube execution identity")
    if (type(evidence.get("worker_a_pid")) is not int
            or type(evidence.get("worker_b_pid")) is not int
            or evidence["worker_a_pid"] <= 0
            or evidence["worker_b_pid"] <= 0
            or evidence["worker_a_pid"] == evidence["worker_b_pid"]):
        raise ValueError("Independent OS workers not established")
    if (evidence.get("worker_a_exit_code") != -9
            or evidence.get("b_worker_role") != "worker-B"
            or type(evidence.get("native_retry_count")) is not int
            or evidence["native_retry_count"] < 1):
        raise ValueError("Real A SIGKILL -> B native retry not established")
    if (evidence.get("initial_epoch") != 7
            or evidence.get("new_epoch") != 8
            or evidence["a_cube_id"] != evidence["b_cube_id"]):
        raise ValueError("PG fencing or persistent provider identity differs")
    if (not isinstance(evidence.get("guest_original"), str)
            or not evidence["guest_original"]
            or evidence.get("guest_after_reconnect") != evidence["guest_original"]):
        raise ValueError("Original Guest data continuity not verified")
    if (evidence.get("old_epoch_rejected") is not True
            or evidence.get("wrong_scope_rejected") is not True
            or evidence.get("destroy_ack") != "RELEASED"):
        raise ValueError("Unsafe authorization or unknown Cube cleanup outcome")
