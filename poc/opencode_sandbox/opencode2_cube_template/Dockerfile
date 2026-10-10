# POC candidate: OpenCode 2 in Cube's existing sandbox-code guest image.
# Use this OCI image as an immutable Cube template. DO NOT run this Dockerfile
# as a replacement for the Cube control-plane or as an unrestricted host tool.
ARG OPENCODE_IMAGE=ghcr.io/anomalyco/opencode:2.0.24
ARG CUBE_BASE_IMAGE=cube-sandbox-int.tencentcloudcr.com/cube-sandbox/sandbox-code:latest
FROM ${OPENCODE_IMAGE} AS opencode
FROM ${CUBE_BASE_IMAGE}
# OpenCode 2.0.24 is a musl-linked executable from Alpine. The Cube guest
# base is Debian/glibc. Keep its musl loader and C++ dependencies private to
# OpenCode; do not replace Cube guest's glibc or globally alter LD_LIBRARY_PATH.
COPY --from=opencode /usr/local/bin/opencode /usr/local/bin/opencode-musl
COPY --from=opencode /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY --from=opencode /usr/lib/libstdc++.so.6* /opt/opencode-musl/
COPY --from=opencode /usr/lib/libgcc_s.so.1 /opt/opencode-musl/
RUN printf '#!/bin/sh\nLD_LIBRARY_PATH=/opt/opencode-musl exec /usr/local/bin/opencode-musl "$@"\n' > /usr/local/bin/opencode \
    && chmod 755 /usr/local/bin/opencode \
    && /usr/local/bin/opencode --version
# Coding-only guest: Cube envd stays on 49983, lightweight probe on 49999.
# Do not spawn a Jupyter server/kernel before the template readiness gate.
# OpenCode V2 Server on 4096 is started via leased Cube SDK Shell later.
COPY start-cube-opencode.sh /opt/ahp/start-cube-opencode.sh
COPY health_probe.py /opt/ahp/health_probe.py
RUN chmod 755 /opt/ahp/start-cube-opencode.sh \
    && python3 -m py_compile /opt/ahp/health_probe.py
# Coding template must carry a real Git CLI for repository operations.
# Bookworm package version is recorded by the build; no global host changes.
RUN apt-get update -qq -o Acquire::Retries=1 -o Acquire::http::Timeout=20 \
    && apt-get install -y -qq --no-install-recommends git \
    && git --version \
    && rm -rf /var/lib/apt/lists/*
CMD ["/opt/ahp/start-cube-opencode.sh"]
EXPOSE 49983 49999 4096
