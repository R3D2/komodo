## Builds the Komodo Core and Periphery binaries
## for a specific architecture.

# glibc builder
FROM rust:1.82.0-bullseye AS glibc-builder

WORKDIR /builder
COPY Cargo.toml Cargo.lock ./
COPY ./lib ./lib
COPY ./client/core/rs ./client/core/rs
COPY ./client/periphery ./client/periphery
COPY ./bin/core ./bin/core
COPY ./bin/periphery ./bin/periphery

# Compile bin for glibc
RUN cargo build -p komodo_core --release && \
    cargo build -p komodo_periphery --release

# musl builder
FROM rust:1.82.0-alpine AS musl-builder

# Install musl build dependencies
RUN apk add --no-cache musl-dev build-base

# Add musl target
RUN rustup target add x86_64-unknown-linux-musl aarch64-unknown-linux-musl

WORKDIR /builder
COPY Cargo.toml Cargo.lock ./
COPY ./lib ./lib
COPY ./client/core/rs ./client/core/rs
COPY ./client/periphery ./client/periphery
COPY ./bin/core ./bin/core
COPY ./bin/periphery ./bin/periphery

# Compile bin for musl
RUN cargo build -p komodo_core --release --target $(case $(uname -m) in aarch64) echo "aarch64-unknown-linux-musl" ;; x86_64) echo "x86_64-unknown-linux-musl" ;; esac) && \
    cargo build -p komodo_periphery --release --target $(case $(uname -m) in aarch64) echo "aarch64-unknown-linux-musl" ;; x86_64) echo "x86_64-unknown-linux-musl" ;; esac)

# Final stage
FROM scratch

# Copy binaries based on VARIANT build arg
ARG VARIANT=glibc
COPY --from=glibc-builder /builder/target/release/core /glibc/core
COPY --from=glibc-builder /builder/target/release/periphery /glibc/periphery
COPY --from=musl-builder /builder/target/$(case $(uname -m) in aarch64) echo "aarch64-unknown-linux-musl" ;; x86_64) echo "x86_64-unknown-linux-musl" ;; esac)/release/core /musl/core
COPY --from=musl-builder /builder/target/$(case $(uname -m) in aarch64) echo "aarch64-unknown-linux-musl" ;; x86_64) echo "x86_64-unknown-linux-musl" ;; esac)/release/periphery /musl/periphery

RUN cp /${VARIANT}/core /core && \
    cp /${VARIANT}/periphery /periphery && \
    rm -r /glibc /musl

LABEL org.opencontainers.image.source=https://github.com/mbecker20/komodo
LABEL org.opencontainers.image.description="Komodo Periphery"
LABEL org.opencontainers.image.licenses=GPL-3.0