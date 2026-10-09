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
# Base image supplies Cube envd on 49983 and code interpreter/probe on 49999.
# OpenCode V2 server is started on demand via Cube SDK, not at image boot.
EXPOSE 49983 49999 4096
