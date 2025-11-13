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
COPY ./services/search/pyproject.toml ./

# Configure Poetry to not create virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --only=main

# Copy shared models (must come before application source)
COPY ./shared ./shared

# Copy config directory for timeout configuration
COPY ./config ./config

# Copy python lib for config validator
COPY ./python ./python

# Copy application source code
COPY ./services/search .

# Expose port
EXPOSE 8055

# Health check (90s timeout for slow dependency checks)
HEALTHCHECK --interval=30s --timeout=90s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8055/health || exit 1

# Run the application
CMD ["python", "app.py"]
