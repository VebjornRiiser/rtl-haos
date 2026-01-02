# Dual-purpose Dockerfile: Home Assistant Add-on + Standalone Docker

# ============================================================================
# Build arguments
# ============================================================================
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.21

# Optional internal build metadata (SemVer build metadata). Kept out of config.yaml.
# If not provided, we'll try to derive a short git SHA when building from a
# git checkout (e.g., HAOS pulling this add-on from a Git repository).
ARG RTL_HAOS_BUILD=""

# ============================================================================
# STAGE 1: Builder - Install Python dependencies with compilation support
# ============================================================================
FROM ${BUILD_FROM} as builder

# Re-declare ARG for this stage (Docker requires this to use it after FROM)
ARG RTL_HAOS_BUILD=""

# Install build dependencies needed for compiling Python packages
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    python3-dev \
    git

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /uvx /bin/

WORKDIR /app

# Copy dependency files and install into virtual environment
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source into a separate directory so we can safely derive
# build metadata without bloating the final runtime image.
WORKDIR /src
COPY . ./

# Bake an internal build id into /src/build.txt.
# - Prefer explicitly provided RTL_HAOS_BUILD.
# - Otherwise, if .git is present, derive short SHA (and mark dirty if needed).
# This file is later copied into the runtime image and loaded by run.sh.
RUN set -e; \
    BUILD=""; \
    if [ -n "${RTL_HAOS_BUILD}" ]; then \
      BUILD="${RTL_HAOS_BUILD}"; \
    elif [ -d ".git" ]; then \
      BUILD="$(git rev-parse --short HEAD 2>/dev/null || true)"; \
      if [ -n "${BUILD}" ] && ! git diff --quiet --no-ext-diff 2>/dev/null; then \
        BUILD="${BUILD}-dirty"; \
      fi; \
    fi; \
    if [ -n "${BUILD}" ]; then echo "${BUILD}" > /src/build.txt; fi; \
    rm -rf /src/.git

# ============================================================================
# STAGE 2: Runtime - Slim final image
# ============================================================================
FROM ${BUILD_FROM}

# Re-declare ARG for this stage (Docker requires this to use it after FROM)
ARG RTL_HAOS_BUILD=""

# Install only runtime dependencies
RUN apk add --no-cache \
    rtl-sdr \
    rtl_433 \
    libusb

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code (cleaned in builder stage; no .git in final image)
COPY --from=builder /src /app

# Entrypoint
COPY --from=builder /src/run.sh /

RUN chmod a+x /run.sh

# Use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV TERM=xterm-256color

# Optional internal build metadata (SemVer build metadata). Kept out of config.yaml.
# If you *do* provide RTL_HAOS_BUILD as a build arg or runtime env, it will
# override the baked /app/build.txt.
ENV RTL_HAOS_BUILD="${RTL_HAOS_BUILD}"

CMD [ "/run.sh" ]
