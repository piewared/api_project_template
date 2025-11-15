"""Health check utilities for various services."""

import subprocess
import time
from collections.abc import Callable


class HealthChecker:
    """Utility class for checking service health."""

    @staticmethod
    def wait_for_condition(
        check_fn: Callable[[], bool],
        timeout: int = 60,
        interval: int = 2,
        service_name: str = "service",
    ) -> bool:
        """Wait for a condition to become true.

        Args:
            check_fn: Function that returns True when condition is met
            timeout: Maximum time to wait in seconds
            interval: Time between checks in seconds
            service_name: Name of the service for logging

        Returns:
            True if condition met within timeout, False otherwise
        """
        elapsed = 0
        while elapsed < timeout:
            if check_fn():
                return True
            time.sleep(interval)
            elapsed += interval
        return False

    @staticmethod
    def check_container_health(container_name: str) -> tuple[bool, str]:
        """Check if a Docker container is healthy.

        Args:
            container_name: Name of the container to check

        Returns:
            Tuple of (is_healthy, status_message)
        """
        # First check if container is running
        check_result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name=^/{container_name}$",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
        )

        if check_result.returncode != 0 or container_name not in check_result.stdout:
            return False, "not running"

        # Check health status
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format={{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}",
                container_name,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return True, "running"  # Container exists but no health check

        health = result.stdout.strip()
        if health == "healthy":
            return True, "healthy"
        elif health == "no-healthcheck" or health == "":
            return True, "running"
        else:
            return False, health

    @staticmethod
    def check_k8s_pod_ready(
        pod_selector: str, namespace: str = "default", timeout: int = 180
    ) -> bool:
        """Check if Kubernetes pods matching selector are ready.

        Args:
            pod_selector: Label selector or pod name
            namespace: Kubernetes namespace
            timeout: Maximum time to wait in seconds

        Returns:
            True if all matching pods are ready, False otherwise
        """
        # Wait for pod to be ready
        elapsed = 0
        interval = 5

        while elapsed < timeout:
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "pod",
                    pod_selector,
                    "-n",
                    namespace,
                    "-o",
                    "jsonpath={.status.conditions[?(@.type=='Ready')].status}",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip() == "True":
                return True

            time.sleep(interval)
            elapsed += interval

        return False
