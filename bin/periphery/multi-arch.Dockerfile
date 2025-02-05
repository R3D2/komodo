## Assumes the latest binaries for x86_64 and aarch64 are already built (by binaries.Dockerfile).
## Sets up the necessary runtime container dependencies for Komodo Periphery.
## Since theres no heavy build here, QEMU multi-arch builds are fine for this image.

ARG BINARIES_IMAGE=ghcr.io/mbecker20/komodo-binaries:latest
ARG X86_64_BINARIES=${BINARIES_IMAGE}-x86_64
ARG AARCH64_BINARIES=${BINARIES_IMAGE}-aarch64
ARG X86_64_MUSL_BINARIES=${BINARIES_IMAGE}-x86_64-musl
ARG AARCH64_MUSL_BINARIES=${BINARIES_IMAGE}-aarch64-musl

FROM ${X86_64_BINARIES} AS x86_64
FROM ${AARCH64_BINARIES} AS aarch64
FROM ${X86_64_MUSL_BINARIES} AS x86_64-musl
FROM ${AARCH64_MUSL_BINARIES} AS aarch64-musl

FROM alpine:3.19 AS musl-base
FROM debian:bullseye-slim AS glibc-base

FROM ${VARIANT:-glibc-base}

# Install deps based on base
RUN if [ -f /etc/alpine-release ]; then \
      apk add --no-cache ca-certificates tzdata; \
    else \
      sh ./debian-deps.sh && rm ./debian-deps.sh; \
    fi

WORKDIR /app

## Copy all binary variants initially, but only keep appropriate one for the TARGETPLATFORM and VARIANT
COPY --from=x86_64 /periphery /app/arch/linux/amd64/glibc
COPY --from=aarch64 /periphery /app/arch/linux/arm64/glibc
COPY --from=x86_64-musl /periphery /app/arch/linux/amd64/musl
COPY --from=aarch64-musl /periphery /app/arch/linux/arm64/musl

ARG TARGETPLATFORM
ARG VARIANT=glibc
RUN mv /app/arch/${TARGETPLATFORM}/${VARIANT} /usr/local/bin/periphery && rm -r /app/arch

EXPOSE 8120

LABEL org.opencontainers.image.source=https://github.com/mbecker20/komodo
LABEL org.opencontainers.image.description="Komodo Periphery"
LABEL org.opencontainers.image.licenses=GPL-3.0

CMD [ "periphery" ]