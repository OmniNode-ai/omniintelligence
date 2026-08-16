# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# ============================================================================
# OmniIntelligence - Base Dockerfile
# ============================================================================
# Multi-stage build for ONEX 4.0 nodes
# Supports: Reducer, Orchestrator, Compute nodes, Effect nodes
# ============================================================================

# ============================================================================
# Stage 1: Base Python environment
# ============================================================================

FROM python:3.12-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv==0.5.0

# Set working directory
WORKDIR /app

# Copy project files
# Note: uv.lock* uses wildcard to make lock file optional. When present, it ensures
# reproducible builds with exact dependency versions. When absent (e.g., during
# development or CI without lock file), uv resolves dependencies from pyproject.toml.
# README.md is required too -- pyproject.toml declares readme = "README.md" and
# hatchling's build_editable validates that field exists on disk; without this
# COPY, `uv pip install -e .` fails on EVERY stage before this PR's api target
# was even added (OSError: Readme file does not exist: README.md, verified by
# building this Dockerfile locally against the unmodified base stage). This was
# a pre-existing, fully dormant bug: no CI workflow ever built this multi-stage
# Dockerfile before build-and-push-app-image.yml (OMN-15922).
COPY pyproject.toml uv.lock* README.md ./
COPY src/ src/
COPY deployment/ deployment/
COPY scripts/ scripts/

# Install dependencies
RUN uv pip install --system --no-cache -e .

# ============================================================================
# Entrypoint Setup (shared by all node stages)
# ============================================================================
# Copy entrypoint script to root and make executable once in base stage.
# This avoids repetition in derived stages and ensures consistent signal handling.
COPY deployment/docker/entrypoint-node.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ============================================================================
# Stage 2: Reducer
# ============================================================================

FROM base as reducer

ENV PYTHONPATH=/app/src
ENV NODE_TYPE=reducer
# Allow default Kafka config for container startup
ENV OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA=true

# Expose health check port
EXPOSE 8000

# Health check - verifies the node's HTTP health endpoint is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run reducer (canonical module path - no v1_0_0 versioning)
# Note: Entrypoint script already copied in base stage for proper signal handling
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
ENTRYPOINT ["/entrypoint.sh"]
CMD ["reducer"]

# ============================================================================
# Stage 3: Orchestrator
# ============================================================================

FROM base as orchestrator

ENV PYTHONPATH=/app/src
ENV NODE_TYPE=orchestrator
# Allow default Kafka config for container startup
ENV OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA=true

# Expose health check port
EXPOSE 8000

# Health check - verifies the node's HTTP health endpoint is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run orchestrator (canonical module path - no v1_0_0 versioning)
# Note: Entrypoint script already copied in base stage for proper signal handling
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
ENTRYPOINT ["/entrypoint.sh"]
CMD ["orchestrator"]

# ============================================================================
# Stage 4: Compute Node (generic)
# ============================================================================

FROM base as compute

ARG NODE_NAME
ENV PYTHONPATH=/app/src
ENV NODE_TYPE=compute
ENV NODE_NAME=${NODE_NAME}
# Allow default Kafka config for container startup
ENV OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA=true

# Expose health check port
EXPOSE 8000

# Health check - verifies the node's HTTP health endpoint is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run compute node (canonical module path - no v1_0_0 versioning)
# Note: Entrypoint script already copied in base stage for proper signal handling
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
ENTRYPOINT ["/entrypoint.sh"]
CMD ["compute"]

# ============================================================================
# Stage 5: Effect Node (generic)
# ============================================================================

FROM base as effect

ARG NODE_NAME
ENV PYTHONPATH=/app/src
ENV NODE_TYPE=effect
ENV NODE_NAME=${NODE_NAME}
# Allow default Kafka config for container startup
ENV OMNIINTELLIGENCE_ALLOW_DEFAULT_KAFKA=true

# Expose health check port
EXPOSE 8000

# Health check - verifies the node's HTTP health endpoint is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run effect node (canonical module path - no v1_0_0 versioning)
# Note: Entrypoint script already copied in base stage for proper signal handling
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
ENTRYPOINT ["/entrypoint.sh"]
CMD ["effect"]

# ============================================================================
# Stage 6: API (FastAPI pattern-query service -- OMN-15922 r2)
# ============================================================================
# This is the stage k8s/onex-dev/omniintelligence/deployment.yaml and
# k8s/onex-prod/omniintelligence/deployment.yaml actually run: containerPort
# 8053, readinessProbe GET /health, no command/args override (the Deployment
# relies entirely on this stage's own CMD). None of the reducer/orchestrator/
# compute/effect stages above serve HTTP on 8053 -- they are stub-mode
# NODE_TYPE launchers on :8000 dispatched by entrypoint-node.sh, matching
# this Dockerfile's own "stub mode" comments on each of those stages. Before
# this stage existed, no build target in this Dockerfile served the contract
# those two Deployments already assumed.
#
# The real server is src/omniintelligence/api/app.py::create_app(), whose own
# docstring names its serving command:
#   uvicorn omniintelligence.api.app:create_app --factory
#
# The base stage's `uv pip install -e .` installs only [project.dependencies]
# -- fastapi/uvicorn/asyncpg live in the "core" dependency-group instead (see
# `uv sync --group core` in .github/workflows/ci.yml), so this stage installs
# that trio explicitly by version-matching pyproject.toml's [dependency-groups]
# core entries, rather than the whole "core" group, which also pulls
# aiokafka/qdrant-client/neo4j and other deps this HTTP-only server never
# imports (verified: grepped every module app.py's import graph reaches).

FROM base as api

RUN uv pip install --system --no-cache \
    "fastapi>=0.104.0" \
    "uvicorn>=0.24.0" \
    "asyncpg>=0.29.0"

ENV PYTHONPATH=/app/src

EXPOSE 8053

# Health check matches api/app.py's GET /health and the k8s readinessProbe in
# k8s/onex-dev|onex-prod/omniintelligence/deployment.yaml.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8053/health || exit 1

CMD ["uvicorn", "omniintelligence.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8053"]

# ============================================================================
# Stage 7: Development/Testing
# ============================================================================

FROM base as dev

# Install development dependencies
RUN uv pip install --system --no-cache \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    ruff \
    mypy

ENV PYTHONPATH=/app/src

# Run tests by default
CMD ["pytest", "tests/", "-v", "--cov=src"]
