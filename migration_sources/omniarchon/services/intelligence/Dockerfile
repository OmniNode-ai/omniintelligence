# ============================================================================
# Base Stage: Production image with minimal dependencies
# ============================================================================
FROM python:3.12-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Configure Poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Copy Poetry files (omnibase_core now fetched from GitHub)
# Build context is /Volumes/PRO-G40/Code/omniarchon (project root)
COPY services/intelligence/pyproject.toml services/intelligence/poetry.lock* ./

# Regenerate lock file with GitHub dependency
RUN poetry lock

# Install production dependencies only (no pytest, pytest-asyncio, pytest-cov)
RUN poetry install --only=main

# Copy application code
# Build context is /Volumes/PRO-G40/Code/omniarchon (project root)
# Note: timeout_config.py is already included in services/intelligence/config/
COPY services/intelligence/ .

# Copy langextract code for CodeRelationshipDetector
# This enables file import extraction functionality
COPY services/langextract/ /app/langextract/

# Expose port
EXPOSE 8053

# Set PYTHONPATH to ensure module imports work
ENV PYTHONPATH=/app

# Health check (120s start period for slow startup, 5 retries for resilience)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8053/health || exit 1

# Run the application using uvicorn module (more reliable than app.py main block)
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8053"]

# ============================================================================
# Test Stage: Includes dev dependencies for testing
# ============================================================================
FROM base AS test

# Install dev dependencies (pytest, pytest-asyncio, pytest-cov)
# omnibase_core already copied in base stage
RUN poetry install --with=dev

# Override CMD for test stage (can be overridden at runtime)
CMD ["pytest", "tests/", "-v", "--cov=src", "--cov-report=term-missing"]
