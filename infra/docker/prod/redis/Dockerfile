# Redis Production Dockerfile
# Hardened Redis with persistence and security configurations

FROM redis:7-alpine

# Install additional utilities
RUN apk add --no-cache \
    bash \
    curl \
    su-exec \
    && rm -rf /var/cache/apk/*

# Create redis user and directories
RUN adduser -D -s /bin/bash redis-backup && \
    mkdir -p /var/lib/redis/backups && \
    chown redis-backup:redis-backup /var/lib/redis/backups

# Copy Redis configuration and scripts
COPY redis.conf /usr/local/etc/redis/redis.conf
COPY backup-scripts/ /usr/local/bin/
COPY docker-entrypoint.sh /usr/local/bin/

# Make scripts executable
RUN chmod +x /usr/local/bin/*.sh

# Create data directory with proper permissions
RUN mkdir -p /data && \
    chown redis:redis /data

# Expose Redis port
EXPOSE 6379

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD redis-cli ping || exit 1

# Volume for data persistence
VOLUME ["/data", "/var/lib/redis/backups"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]