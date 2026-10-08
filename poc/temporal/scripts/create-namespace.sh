#!/bin/sh
set -eu
: "${TEMPORAL_ADDRESS:?}"
# Namespace is Temporal provider configuration, NOT a multi-tenant Harness domain.
if temporal operator namespace describe --namespace default >/dev/null 2>&1; then
  echo TEMPORAL_DEFAULT_NAMESPACE_EXISTS
else
  temporal operator namespace create --namespace default --retention 1d
  echo TEMPORAL_DEFAULT_NAMESPACE_READY
fi
