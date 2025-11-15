"""Kubernetes environment deployer."""

from pathlib import Path

from rich.console import Console

from .base import BaseDeployer
from .health_checks import HealthChecker
from .status_display import StatusDisplay


class K8sDeployer(BaseDeployer):
    """Deployer for Kubernetes environment."""

    DEFAULT_NAMESPACE = "api-forge-prod"

    def __init__(self, console: Console, project_root: Path):
        """Initialize the Kubernetes deployer.

        Args:
            console: Rich console for output
            project_root: Path to the project root directory
        """
        super().__init__(console, project_root)
        self.status_display = StatusDisplay(console)
        self.health_checker = HealthChecker()
        self.k8s_scripts = project_root / "k8s" / "scripts"

    def deploy(self, **kwargs) -> None:
        """Deploy to Kubernetes cluster.

        Args:
            **kwargs: Additional deployment options
        """
        namespace = kwargs.get("namespace", self.DEFAULT_NAMESPACE)

        # Build images
        self._build_images()

        # Create secrets
        self._create_secrets(namespace)

        # Deploy resources
        self._deploy_resources(namespace)

        # Wait for pods to be ready
        self._wait_for_pods(namespace)

        # Display status
        self.console.print("\n[bold green]🎉 Kubernetes deployment complete![/bold green]")
        self.status_display.show_k8s_status(namespace)

    def teardown(self, **kwargs) -> None:
        """Remove Kubernetes deployment.

        Args:
            **kwargs: Additional teardown options
        """
        namespace = kwargs.get("namespace", self.DEFAULT_NAMESPACE)

        with self.console.status(f"[bold red]Deleting namespace {namespace}..."):
            self.run_command(["kubectl", "delete", "namespace", namespace])

        self.success(f"Namespace {namespace} deleted")

    def show_status(self, namespace: str | None = None) -> None:
        """Display the current status of the Kubernetes deployment.

        Args:
            namespace: Kubernetes namespace to check (default: api-forge)
        """
        if namespace is None:
            namespace = self.DEFAULT_NAMESPACE
        self.status_display.show_k8s_status(namespace)

    def _build_images(self) -> None:
        """Build Docker images for Kubernetes deployment."""
        self.console.print("[bold cyan]🔨 Building Docker images...[/bold cyan]")

        script_path = self.k8s_scripts / "build-images.sh"
        with self.create_progress() as progress:
            task = progress.add_task("Building images...", total=1)
            self.run_command(["bash", str(script_path)])
            progress.update(task, completed=1)

        self.success("Docker images built")

    def _create_secrets(self, namespace: str) -> None:
        """Create Kubernetes secrets.

        Args:
            namespace: Target namespace
        """
        self.console.print("[bold cyan]🔐 Creating secrets...[/bold cyan]")

        script_path = self.k8s_scripts / "create-secrets.sh"
        with self.create_progress() as progress:
            task = progress.add_task("Creating secrets...", total=1)
            self.run_command(["bash", str(script_path), namespace])
            progress.update(task, completed=1)

        self.success(f"Secrets created in namespace {namespace}")

    def _deploy_resources(self, namespace: str) -> None:
        """Deploy Kubernetes resources.

        Args:
            namespace: Target namespace
        """
        self.console.print("[bold cyan]🚀 Deploying resources...[/bold cyan]")

        script_path = self.k8s_scripts / "deploy-resources.sh"
        with self.create_progress() as progress:
            task = progress.add_task("Deploying resources...", total=1)
            self.run_command(["bash", str(script_path), namespace])
            progress.update(task, completed=1)

        self.success(f"Resources deployed to namespace {namespace}")

    def _wait_for_pods(self, namespace: str) -> None:
        """Wait for all pods to be ready.

        Args:
            namespace: Target namespace
        """
        self.console.print("\n[bold cyan]⏳ Waiting for pods to be ready...[/bold cyan]")
        self.console.print("[dim]This may take 2-3 minutes...[/dim]\n")

        # Get list of pods
        pods_result = self.run_command(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                namespace,
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ],
            capture_output=True,
        )

        if not pods_result.stdout:
            self.warning("No pods found in namespace")
            return

        pod_names = pods_result.stdout.strip().split()

        # Check each pod
        all_ready = True
        for pod_name in pod_names:
            is_ready = self.health_checker.check_k8s_pod_ready(
                pod_name, namespace, timeout=180
            )
            if is_ready:
                self.success(f"Pod {pod_name} is ready")
            else:
                self.warning(f"Pod {pod_name} may not be fully ready yet")
                all_ready = False

        if not all_ready:
            self.console.print(
                "\n[yellow]💡 Tip: Check pod status with: "
                f"kubectl get pods -n {namespace}[/yellow]"
            )
