#!/usr/bin/env sh
set -eu

# Application user and group IDs (must match Dockerfile)
APP_UID=1001
APP_GID=1001

echo "Starting entrypoint script..."

# Create secure tmpfs directory for secrets with proper ownership
echo "Setting up secure secrets directory..."
install -d -m 0700 -o "$APP_UID" -g "$APP_GID" /run/secrets

# Copy all mounted host secrets to tmpfs with proper ownership and permissions
echo "Copying secrets with proper permissions..."
for secret_file in /mnt/host_secrets/*; do
    if [ -f "$secret_file" ]; then
        secret_name=$(basename "$secret_file")
        # Remove .txt extension if present to match config expectations
        target_name="${secret_name%.txt}"
        echo "Installing secret: $secret_name -> $target_name"
        install -m 0400 -o "$APP_UID" -g "$APP_GID" "$secret_file" "/run/secrets/$target_name"
    fi
done

echo "Secrets setup complete. Starting application as appuser..."

# Drop privileges and start the application
exec su-exec "$APP_UID:$APP_GID" "$@"