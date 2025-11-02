#!/bin/bash
# Custom entrypoint for Redis with security configurations

set -e

# Set Redis password from secret file or environment variable
if [ -f "$REDIS_PASSWORD_FILE" ]; then
    REDIS_PASSWORD=$(cat "$REDIS_PASSWORD_FILE")
    echo "" >> /usr/local/etc/redis/redis.conf
    echo "requirepass $REDIS_PASSWORD" >> /usr/local/etc/redis/redis.conf
    echo "Redis password configured from secret file: $REDIS_PASSWORD_FILE"
elif [ -n "$REDIS_PASSWORD" ]; then
    echo "" >> /usr/local/etc/redis/redis.conf
    echo "requirepass $REDIS_PASSWORD" >> /usr/local/etc/redis/redis.conf
    echo "Redis password configured from environment variable"
else
    echo "Warning: No Redis password configured"
fi

# Ensure proper permissions
chown -R redis:redis /data
chown -R redis:redis /usr/local/etc/redis

# Start Redis as redis user
exec su-exec redis "$@"