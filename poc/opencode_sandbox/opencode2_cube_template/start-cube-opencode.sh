#!/bin/sh
# Cube guest coding profile: envd + minimal health service; no Jupyter.
set -eu
mkdir -p /workspace /var/log
/usr/bin/envd -port "${ENVD_PORT:-49983}" >/var/log/envd.log 2>&1 &
exec python3 -u /opt/ahp/health_probe.py
