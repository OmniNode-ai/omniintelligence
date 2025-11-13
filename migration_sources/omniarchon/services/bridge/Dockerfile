# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy Poetry configuration files
COPY services/bridge/pyproject.toml ./

# Configure Poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --only=main

# Copy shared models first
COPY shared/models /app/shared/models

# Copy config directory for timeout configuration
COPY config /app/config

# Copy python library directory for config_validator
COPY python/ /app/python/

# Copy application source code
COPY services/bridge/ .

# Set PYTHONPATH to ensure module imports work
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8054

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8054/health || exit 1

# Run the application
CMD ["python", "app.py"]
