"""POC-only official MSSQL Durable Worker crash plus SQLite receipt integration.

Uses existing local Docker test MSSQL/PostgreSQL containers and cached
MAF Functions image. Fixture DB secrets are retrieved from their own container
configuration, held only in process memory and a temporary restricted Compose
env file deleted on exit. Never runs against user enterprise services or
prints/commits secrets. It does not establish enterprise Tool trust/Exactly Once.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import verify_guarded_native_handoff as guarded

MSSQL_FIXTURE="maf-mssql-poc-mssql-1"


def container_env(name:str)->dict[str,str]:
    raw=subprocess.check_output(
        ["docker","inspect","-f","{{json .Config.Env}}",name],
        text=True,timeout=20,
    )
    values=json.loads(raw)
    return dict(item.split("=",1) for item in values if "=" in item)


def main()->None:
    config=container_env(MSSQL_FIXTURE)
    sql_key=config.get("MSSQL_SA_PASSWORD") or config.get("SA_PASSWORD")
    if not sql_key:
        raise RuntimeError("Local POC MSSQL credential unavailable; cannot run")
    with tempfile.TemporaryDirectory(prefix="maf-a34-compose-env-") as root:
        envfile=Path(root)/"poc-only.env"
        try:
            envfile.write_text("POC_MSSQL_SA_PASSWORD="+sql_key+"\n",encoding="utf-8")
            os.chmod(envfile,0o600)
            guarded.ENVFILE=envfile
            os.environ["POC_A34_G6_RECEIPT"]="1"
            guarded.main()
        finally:
            # File removed by TemporaryDirectory, and never copied to repo.
            os.environ.pop("POC_A34_G6_RECEIPT",None)


if __name__=="__main__":
    main()
