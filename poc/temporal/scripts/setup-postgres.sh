#!/bin/sh
# One-time official Temporal SQL schema bootstrap for an isolated POC DB.
# Based on temporalio/samples-server/compose/scripts/setup-postgres.sh.
set -eu
: "${POSTGRES_SEEDS:?}"
: "${POSTGRES_USER:?}"
: "${SQL_PASSWORD:?}"
port="${DB_PORT:-5432}"
common="--plugin postgres12 --ep ${POSTGRES_SEEDS} -u ${POSTGRES_USER} -p ${port}"

temporal-sql-tool ${common} --db temporal create
temporal-sql-tool ${common} --db temporal setup-schema -v 0.0
temporal-sql-tool ${common} --db temporal update-schema -d /etc/temporal/schema/postgresql/v12/temporal/versioned

temporal-sql-tool ${common} --db temporal_visibility create
temporal-sql-tool ${common} --db temporal_visibility setup-schema -v 0.0
temporal-sql-tool ${common} --db temporal_visibility update-schema -d /etc/temporal/schema/postgresql/v12/visibility/versioned

echo TEMPORAL_OSSSQL_SCHEMA_READY
