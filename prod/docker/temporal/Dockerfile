# Temporal Production Dockerfile
# Production-ready Temporal Server with PostgreSQL support

FROM temporalio/auto-setup:1.28.1

# Install additional utilities for production
USER root
RUN apk add --no-cache \
    bash \
    curl \
    postgresql-client \
    && rm -rf /var/cache/apk/*

# Create temporal user for production
RUN adduser -D -s /bin/bash temporal-user

# Copy configuration files
COPY config/ /etc/temporal/config/
COPY scripts/ /usr/local/bin/

# Make scripts executable
RUN chmod +x /usr/local/bin/*.sh

# Create directories with proper permissions
RUN mkdir -p /var/log/temporal && \
    chown -R temporal-user:temporal-user /var/log/temporal

# Environment variables for production
ENV TEMPORAL_ADDRESS=0.0.0.0:7233 \
    TEMPORAL_CLI_ADDRESS=0.0.0.0:7233 \
    DB=postgres12 \
    DB_PORT=5432 \
    POSTGRES_SEEDS=postgres \
    TEMPORAL_LOG_LEVEL=info \
    DYNAMIC_CONFIG_FILE_PATH=/etc/temporal/config/dynamicconfig/docker.yaml

# Expose Temporal ports
EXPOSE 7233 7234 7235 7239 6933 6934 6935 6939

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:7233/health || exit 1

# Switch to non-root user
USER temporal-user

# Custom entrypoint for production setup
ENTRYPOINT ["/usr/local/bin/temporal-entrypoint.sh"]
CMD ["temporal-server", "start"]