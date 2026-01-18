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

# Copy project files (include lock file for reproducible builds)
COPY pyproject.toml uv.lock* ./
COPY src/ src/
COPY deployment/ deployment/
COPY scripts/ scripts/

# Install dependencies
RUN uv pip install --system --no-cache -e .

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

# Run reducer (canonical module path - no v1_0_0 versioning)
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
CMD ["python", "-m", "omniintelligence.nodes.intelligence_reducer"]

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

# Run orchestrator (canonical module path - no v1_0_0 versioning)
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
CMD ["python", "-m", "omniintelligence.nodes.intelligence_orchestrator"]

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

# Run compute node (canonical module path - no v1_0_0 versioning)
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
CMD ["sh", "-c", "python -m omniintelligence.nodes.${NODE_NAME}"]

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

# Run effect node (canonical module path - no v1_0_0 versioning)
# Note: Runs in stub mode with health checks; full functionality requires
# ONEX container injection via RuntimeHostProcess
CMD ["sh", "-c", "python -m omniintelligence.nodes.${NODE_NAME}"]

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
