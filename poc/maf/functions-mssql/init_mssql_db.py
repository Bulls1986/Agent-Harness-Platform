"""Prepare isolated DurableDB with SQL Durable Functions required BIN2_UTF8 collation.

Never prints or accepts the SQL SA password on the host; uses trusted
container-internal MSSQL_SA_PASSWORD for isolated POC SQL Server only.
"""
from __future__ import annotations

import subprocess
import sys
import time

SQL_CONTAINER = "maf-mssql-poc-mssql-1"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
CREATE = (
    "IF DB_ID('DurableDB') IS NULL "
    "CREATE DATABASE DurableDB COLLATE Latin1_General_100_BIN2_UTF8;"
)
VERIFY = (
    "SET NOCOUNT ON; SELECT collation_name FROM sys.databases "
    "WHERE name='DurableDB';"
)


def run_sql(query: str) -> subprocess.CompletedProcess[str]:
    script = (
        f'{SQLCMD} -C -b -S localhost -U sa '
        f'-P "$MSSQL_SA_PASSWORD" -Q "{query}"'
    )
    return subprocess.run(
        ["docker", "exec", SQL_CONTAINER, "/bin/bash", "-lc", script],
        capture_output=True, text=True,
    )


def main() -> None:
    db = sys.argv[1] if len(sys.argv) == 2 else 'DurableDB'
    if db not in ('DurableDB', 'DurableA34', 'DurableA34Running', 'DurableA34Guarded'):
        raise ValueError('Only dedicated POC databases are allowed')
    create = CREATE.replace('DurableDB', db)
    verify = VERIFY.replace('DurableDB', db)
    for attempt in range(60):
        result = run_sql(create)
        if result.returncode == 0:
            break
        time.sleep(2)
    else:
        raise RuntimeError("Isolated MSSQL SQL Server not ready after retries")
    check = run_sql(verify)
    if check.returncode != 0 or "Latin1_General_100_BIN2_UTF8" not in check.stdout:
        raise RuntimeError("DurableDB collation missing or not BIN2_UTF8")
    print(db + " initialized with Latin1_General_100_BIN2_UTF8; SQL container only")


if __name__ == "__main__":
    main()
