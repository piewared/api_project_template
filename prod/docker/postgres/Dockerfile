# PostgreSQL Production Dockerfile
# Hardened PostgreSQL with backup capabilities and performance tuning

FROM postgres:16-alpine

# Install additional utilities for production
RUN apk add --no-cache \
    bash \
    curl \
    openssl \
    postgresql-contrib \
    && rm -rf /var/cache/apk/*

# Create backup user and directories
RUN adduser -D -s /bin/bash backup && \
    mkdir -p /var/lib/postgresql/backups && \
    chown backup:backup /var/lib/postgresql/backups

# Copy custom PostgreSQL configuration
COPY postgresql.conf /tmp/postgresql.conf
COPY pg_hba.conf /tmp/pg_hba.conf

# Copy initialization and backup scripts
COPY init-scripts/ /docker-entrypoint-initdb.d/
COPY backup-scripts/ /usr/local/bin/

# Make scripts executable
RUN chmod +x /usr/local/bin/*.sh

# Environment variables for production
ENV POSTGRES_DB=appdb \
    POSTGRES_USER=appuser \
    POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password \
    POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256 --data-checksums" \
    POSTGRES_HOST_AUTH_METHOD=scram-sha-256

# Expose PostgreSQL port
EXPOSE 5432

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pg_isready -U $POSTGRES_USER -d $POSTGRES_DB || exit 1

# Data volume
VOLUME ["/var/lib/postgresql/data", "/var/lib/postgresql/backups"]

# Use the standard PostgreSQL entrypoint
CMD ["postgres"]