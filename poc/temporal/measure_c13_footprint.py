"""C13 reproducible Docker Compose service footprint, not cost/SLO benchmark."""
import json
import os
import subprocess
from pathlib import Path

ROOT=Path(__file__).parent
SPECS={"temporal":"compose-oss-postgres.yml",
       "harness_pg":"compose-platform-pg.yml",
       "optional_s3":"compose-objectstore.yml"}
def measure():
    env=os.environ.copy()
    env.setdefault("POC_C_TEMPORAL_DB_PASSWORD","fixture-placeholder")
    env.setdefault("POC_C_HARNESS_PG_PASSWORD","fixture-placeholder")
    groups={}
    for kind,path in SPECS.items():
        res=subprocess.run(["docker","compose","-f",str(ROOT/path),"config",
                            "--services"],env=env,text=True,capture_output=True,
                           timeout=24,check=False)
        if res.returncode:raise RuntimeError("Compose manifest parse failed")
        groups[kind]=[x for x in res.stdout.splitlines() if x]
    all_services=[s for g in groups.values() for s in g]
    init={"temporal-schema","temporal-namespace"}
    optional={"c11-s3"}
    return {"status":"PASS_C13_COMPOSE_FOOTPRINT",
            "service_definitions":len(all_services),
            "steady_core_services":len(set(all_services)-init-optional),
            "one_time_init_services":len(set(all_services)&init),
            "optional_objectstore_services":len(set(all_services)&optional),
            "requires_separate_worker_process":True,
            "external_APM_not_built":True,
            "HA_benchmark_performed":False,
            "services":groups}
if __name__=="__main__":print(json.dumps(measure(),sort_keys=True))
