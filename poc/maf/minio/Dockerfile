# POC-only S3-compatible MinIO image, assembled from an official pinned release.
# Avoid third-party binary mirrors (upstream Docker Hub and Quay images unavailable).
FROM debian:bookworm-slim
ARG TARGETARCH=amd64
ARG MINIO_RELEASE=RELEASE.2025-09-07T16-13-09Z
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && set -eux; \
       base="https://dl.min.io/community/server/minio/release/linux-${TARGETARCH}/minio.${MINIO_RELEASE}"; \
       curl -fsSL "${base}" -o /usr/local/bin/minio; \
       curl -fsSL "${base}.sha256sum" -o /tmp/minio.sha256sum; \
       expected="$(awk '{print $1}' /tmp/minio.sha256sum)"; \
       actual="$(sha256sum /usr/local/bin/minio | awk '{print $1}')"; \
       test -n "${expected}" && test "${actual}" = "${expected}"; \
       chmod 755 /usr/local/bin/minio; \
       rm -f /tmp/minio.sha256sum; \
       mkdir -p /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 9000 9001
ENTRYPOINT ["/usr/local/bin/minio"]
