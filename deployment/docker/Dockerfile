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
COPY pyproject.toml .
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

# Expose health check port
EXPOSE 8000

# Run reducer
CMD ["python", "-m", "omniintelligence.nodes.intelligence_reducer.v1_0_0.reducer"]

# ============================================================================
# Stage 3: Orchestrator
# ============================================================================

FROM base as orchestrator

ENV PYTHONPATH=/app/src
ENV NODE_TYPE=orchestrator

# Expose health check port
EXPOSE 8000

# Run orchestrator
CMD ["python", "-m", "omniintelligence.nodes.intelligence_orchestrator.v1_0_0.orchestrator"]

# ============================================================================
# Stage 4: Compute Node (generic)
# ============================================================================

FROM base as compute

ARG NODE_NAME
ENV PYTHONPATH=/app/src
ENV NODE_TYPE=compute
ENV NODE_NAME=${NODE_NAME}

# Expose health check port
EXPOSE 8000

# Run compute node
CMD python -m omniintelligence.nodes.${NODE_NAME}.v1_0_0.compute

# ============================================================================
# Stage 5: Effect Node (generic)
# ============================================================================

FROM base as effect

ARG NODE_NAME
ENV PYTHONPATH=/app/src
ENV NODE_TYPE=effect
ENV NODE_NAME=${NODE_NAME}

# Expose health check port
EXPOSE 8000

# Run effect node
CMD python -m omniintelligence.nodes.${NODE_NAME}.v1_0_0.effect

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
