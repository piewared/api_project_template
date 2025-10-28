FROM temporalio/server:1.29.0

# Switch to root to install grpc_health_probe
USER root

# Add grpc_health_probe (tiny static binary)
# Pick the latest release for your arch; this URL is an example for linux-amd64.
ADD --chmod=755 https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.28/grpc_health_probe-linux-amd64 /usr/local/bin/grpc_health_probe

# Switch back to the default temporal user
USER temporal