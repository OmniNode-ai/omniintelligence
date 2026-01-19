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
COPY pyproject.toml uv.lock* ./
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
# Stage 6: Development/Testing
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
