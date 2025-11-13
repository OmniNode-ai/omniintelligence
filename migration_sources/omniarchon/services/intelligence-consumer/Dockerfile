# Intelligence Consumer Service Dockerfile
FROM python:3.12-slim

LABEL maintainer="Archon Team"
LABEL description="Intelligence consumer service for asynchronous document enrichment"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY services/intelligence-consumer/pyproject.toml services/intelligence-consumer/poetry.lock* ./

# Configure Poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies (skip project installation)
RUN poetry install --no-root --only main --no-interaction --no-ansi

# Copy application code
COPY services/intelligence-consumer/src/ ./src/
COPY python/ ./python/

# Create non-root user
RUN useradd -m -u 1000 consumer && \
    chown -R consumer:consumer /app

# Switch to non-root user
USER consumer

# Expose health check port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run consumer service directly with Python
CMD ["python", "-m", "src.main"]
