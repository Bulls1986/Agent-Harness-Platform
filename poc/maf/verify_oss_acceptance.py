"""One-command POC-A15 local OSS + PostgreSQL acceptance.

Requires locally available Docker and optional requirements-oss.txt dependencies.
Creates fresh isolated Postgres and S3-compatible SeaweedFS containers on random
127.0.0.1 ports; runs real S3/PG integration tests; removes both containers.
No shared enterprise/other-project object-store buckets are modified.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def docker(*args: str,env: dict | None = None,timeout=25)->str:
    r=subprocess.run(["docker",*args],env=env,capture_output=True,
                     encoding="utf-8",errors="replace",timeout=timeout)
    if r.returncode:
        raise RuntimeError("Isolated Docker provider operation failed")
    return r.stdout.strip()


def run()->int:
    if not (Path("poc")/"maf"/"tests"/"test_oss_payload_refs_pg.py").exists():
        print(json.dumps({"outcome":"SETUP_GAP","reason":"run_from_repository_root"}))
        return 2
    ident=secrets.token_hex(5)
    pg_name="maf-a15-pg-"+ident
    oss_name="maf-a15-oss-"+ident
    image=os.environ.get("POC_A15_OSS_IMAGE","chrislusf/seaweedfs:3.99")
    password=secrets.token_urlsafe(24)
    started=[]
    try:
        env=os.environ.copy()
        env["POSTGRES_PASSWORD"]=password
        docker("run","--rm","-d","--name",pg_name,
               "-e","POSTGRES_PASSWORD","-e","POSTGRES_DB=a15",
               "-e","POSTGRES_USER=poc",
               "-p","127.0.0.1::5432","postgres:16-alpine",env=env,timeout=45)
        started.append(pg_name)
        pgport=int(docker("port",pg_name,"5432/tcp").rsplit(":",1)[1])
        for _ in range(55):
            ready=subprocess.run(
                ["docker","exec",pg_name,"pg_isready","-U","poc","-d","a15"],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
            if ready.returncode==0:break
            time.sleep(.3)
        else:raise RuntimeError("Isolated PostgreSQL not ready")

        docker("run","--rm","-d","--name",oss_name,
               "-p","127.0.0.1::8333",
               image,"server","-dir=/data","-s3","-s3.port=8333",
               "-ip=127.0.0.1","-ip.bind=0.0.0.0",timeout=50)
        started.append(oss_name)
        ossport=int(docker("port",oss_name,"8333/tcp").rsplit(":",1)[1])
        for _ in range(100):
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{ossport}",timeout=1.5):
                    break
            except urllib.error.HTTPError as exc:
                if exc.code in (400,403,404):break
            except (OSError,TimeoutError):
                pass
            time.sleep(.45)
        else:raise RuntimeError("Isolated S3 endpoint not ready")

        child=os.environ.copy()
        child["POC_POSTGRES_DSN"]=(
            f"postgresql://poc:{password}@127.0.0.1:{pgport}/a15")
        child["POC_OSS_ENDPOINT"]=f"http://127.0.0.1:{ossport}"
        child["POC_OSS_BUCKET"]="maf-a15-"+ident
        r=subprocess.run(
            [sys.executable,"-m","unittest","discover",
             "-s","poc/maf/tests","-p","test_oss_payload_refs_pg.py","-v"],
            env=child,timeout=105,
        )
        print(json.dumps({"outcome":"PASS_REAL_S3_AND_POSTGRES" if r.returncode==0
                          else "FAIL_REAL_S3_AND_POSTGRES",
                          "successful":r.returncode==0,
                          "independent_providers":True,
                          "ephemeral_containers":True},sort_keys=True))
        return r.returncode
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({"outcome":"GAP","error_type":type(exc).__name__}))
        return 1
    finally:
        for name in reversed(started):
            try:
                docker("rm","-f",name,timeout=28)
            except (OSError,RuntimeError,subprocess.TimeoutExpired):
                print(json.dumps({"outcome":"CLEANUP_GAP","resource":name}))


if __name__=="__main__":
    raise SystemExit(run())
