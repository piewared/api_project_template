# FastAPI Application Production Dockerfile
# Multi-stage build for optimal security and performance

# =============================================================================
# Stage 1: Build environment
# =============================================================================
FROM python:3.13-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    cargo \
    git

# Create and set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Install dependencies to a virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies using uv sync
RUN uv sync --frozen --no-dev

# =============================================================================
# Stage 2: Production environment
# =============================================================================
FROM python:3.13-alpine AS production

# Install runtime dependencies only
RUN apk add --no-cache \
    ca-certificates \
    tzdata \
    tini \
    && rm -rf /var/cache/apk/*

# Create app user for security
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set PATH to use virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appgroup src/ src/
COPY --chown=appuser:appgroup src_main.py ./

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Environment variables for production
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Use tini as init process for proper signal handling
ENTRYPOINT ["/sbin/tini", "--"]

# Start application
CMD ["uvicorn", "src_main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]