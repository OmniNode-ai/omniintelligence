# LangExtract Service Dockerfile
# Advanced Language-Aware Data Extraction Service

FROM python:3.12-slim

LABEL maintainer="Archon Team"
LABEL service="langextract"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    gcc \
    g++ \
    pkg-config \
    libicu-dev \
    libmagic1 \
    libmagic-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements-minimal.txt requirements.txt

# Install build dependencies first
RUN pip install --no-cache-dir setuptools wheel

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r langextract && useradd -r -g langextract langextract
RUN chown -R langextract:langextract /app
USER langextract

# Expose service port
EXPOSE 8156

# Health check (90s timeout for slow dependency checks)
HEALTHCHECK --interval=30s --timeout=90s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8156/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8156", "--reload"]
