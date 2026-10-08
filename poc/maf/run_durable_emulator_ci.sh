#!/usr/bin/env bash
# Development-only DTS emulator crash/handoff probe. No hosted Durable evidence.
set -euo pipefail
export POC_DTS_ENDPOINT="${POC_DTS_ENDPOINT:-http://127.0.0.1:18080}"
export POC_DTS_TASKHUB="${POC_DTS_TASKHUB:-pocmaf}"
export POC_DTS_MARKERS="${POC_DTS_MARKERS:-/tmp/maf-dts-markers}"
finish() {
  docker compose -f poc/maf/compose-durable-emulator.yml logs --no-color --tail 60 || true
  docker compose -f poc/maf/compose-durable-emulator.yml down --remove-orphans || true
}
trap finish EXIT
docker compose -f poc/maf/compose-durable-emulator.yml up -d
docker image inspect mcr.microsoft.com/dts/dts-emulator:latest --format '{{.Id}}' > dts-emulator-image-id.txt
docker image inspect mcr.microsoft.com/dts/dts-emulator:latest --format '{{json .RepoDigests}}' > dts-emulator-image-digests.txt
python - <<'PY'
import socket,time
deadline=time.monotonic()+120
while time.monotonic()<deadline:
    try:
        with socket.create_connection(("127.0.0.1",18080),timeout=1):
            print("DTS emulator port ready",flush=True)
            break
    except OSError:
        time.sleep(2)
else:
    raise SystemExit("DTS emulator gRPC port not reachable")
PY
set -euo pipefail
mkdir -p "$POC_DTS_MARKERS"
python poc/maf/durable_emulator_probe.py worker > /tmp/maf-dts-worker-a.log 2>&1 &
worker_a=$!
for i in $(seq 1 60); do
  if grep -q '"worker_ready": true' /tmp/maf-dts-worker-a.log; then break; fi
  if ! kill -0 "$worker_a" 2>/dev/null; then cat /tmp/maf-dts-worker-a.log; exit 1; fi
  sleep 1
done
grep -q '"worker_ready": true' /tmp/maf-dts-worker-a.log
python poc/maf/durable_emulator_probe.py start --case approved-fixture > /tmp/maf-dts-start-approved.json
python poc/maf/durable_emulator_probe.py start --case rejected-fixture > /tmp/maf-dts-start-rejected.json
approved_id=$(python -c "import json;print(json.load(open('/tmp/maf-dts-start-approved.json'))['instance_id'])")
rejected_id=$(python -c "import json;print(json.load(open('/tmp/maf-dts-start-rejected.json'))['instance_id'])")
timeout 90s python poc/maf/durable_emulator_probe.py pending --instance "$approved_id" > /tmp/maf-dts-pending-approved.json
timeout 90s python poc/maf/durable_emulator_probe.py pending --instance "$rejected_id" > /tmp/maf-dts-pending-rejected.json
test "$(wc -l < "$POC_DTS_MARKERS/approved-fixture.prepare")" -eq 1
test "$(wc -l < "$POC_DTS_MARKERS/rejected-fixture.prepare")" -eq 1
test ! -f "$POC_DTS_MARKERS/approved-fixture.action"
test ! -f "$POC_DTS_MARKERS/rejected-fixture.action"
kill -9 "$worker_a"
wait "$worker_a" || true
python poc/maf/durable_emulator_probe.py worker > /tmp/maf-dts-worker-b.log 2>&1 &
worker_b=$!
for i in $(seq 1 60); do
  if grep -q '"worker_ready": true' /tmp/maf-dts-worker-b.log; then break; fi
  if ! kill -0 "$worker_b" 2>/dev/null; then cat /tmp/maf-dts-worker-b.log; exit 1; fi
  sleep 1
done
grep -q '"worker_ready": true' /tmp/maf-dts-worker-b.log
approved_req=$(python -c "import json;print(json.load(open('/tmp/maf-dts-pending-approved.json'))['request_id'])")
rejected_req=$(python -c "import json;print(json.load(open('/tmp/maf-dts-pending-rejected.json'))['request_id'])")
python poc/maf/durable_emulator_probe.py respond --instance "$approved_id" --request "$approved_req" --decision APPROVED
python poc/maf/durable_emulator_probe.py respond --instance "$rejected_id" --request "$rejected_req" --decision REJECTED
timeout 90s python poc/maf/durable_emulator_probe.py output --instance "$approved_id" > /tmp/maf-dts-output-approved.json
timeout 90s python poc/maf/durable_emulator_probe.py output --instance "$rejected_id" > /tmp/maf-dts-output-rejected.json
python - <<'PY'
import json
a=json.load(open("/tmp/maf-dts-output-approved.json"))["output"]
b=json.load(open("/tmp/maf-dts-output-rejected.json"))["output"]
assert "SIMULATED_EXECUTION:approved-fixture" in a,a
assert "DENIED_NO_EXECUTION" in b,b
print("Native Durable workflow output survived worker handoff")
PY
test "$(wc -l < "$POC_DTS_MARKERS/approved-fixture.prepare")" -eq 1
test "$(wc -l < "$POC_DTS_MARKERS/rejected-fixture.prepare")" -eq 1
test "$(wc -l < "$POC_DTS_MARKERS/approved-fixture.action")" -eq 1
test ! -f "$POC_DTS_MARKERS/rejected-fixture.action"
echo 'MAF native Durable DTS-Emulator worker-handoff and HITL fixtures PASS'
kill "$worker_b" || true
