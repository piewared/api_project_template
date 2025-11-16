"""Production environment deployer."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .base import BaseDeployer
from .health_checks import HealthChecker
from .status_display import StatusDisplay


class ProdDeployer(BaseDeployer):
    """Deployer for production environment using Docker Compose."""

    COMPOSE_FILE = "docker-compose.prod.yml"

    # Service monitoring configuration
    SERVICES = [
        ("api-forge-postgres", "PostgreSQL"),
        ("api-forge-redis", "Redis"),
        ("api-forge-temporal", "Temporal"),
        ("api-forge-temporal-web", "Temporal Web"),
        ("api-forge-app", "FastAPI App"),
        ("api-forge-worker", "Temporal Worker"),
    ]

    def __init__(self, console: Console, project_root: Path):
        """Initialize the production deployer.

        Args:
            console: Rich console for output
            project_root: Path to the project root directory
        """
        super().__init__(console, project_root)
        self.status_display = StatusDisplay(console)
        self.health_checker = HealthChecker()

    def deploy(self, **kwargs) -> None:
        """Deploy the production environment.

        Args:
            **kwargs: Deployment options (skip_build, no_wait)
        """
        # Check for .env file first
        if not self.check_env_file():
            raise typer.Exit(1)

        skip_build = kwargs.get("skip_build", False)
        no_wait = kwargs.get("no_wait", False)
        # Build app image if needed
        if not skip_build:
            self._build_app_image()

        # Start services
        self._start_services()

        # Wait for health checks
        if not no_wait:
            self._monitor_health_checks()

        # Display final status
        self.console.print("\n[bold green]🎉 Production deployment complete![/bold green]")
        self.status_display.show_prod_status()

    def teardown(self, **kwargs) -> None:
        """Stop the production environment.

        Args:
            **kwargs: Teardown options (volumes)
        """
        volumes = kwargs.get("volumes", False)
        cmd = ["docker", "compose", "-f", self.COMPOSE_FILE, "down", "--remove-orphans"]
        if volumes:
            cmd.append("-v")

        with self.console.status("[bold red]Stopping containers..."):
            self.run_command(cmd)

        if volumes:
            self.success("Production services stopped and volumes removed")
        else:
            self.success("Production services stopped (volumes preserved)")

    def show_status(self) -> None:
        """Display the current status of the production deployment."""
        self.status_display.show_prod_status()

    def _build_app_image(self) -> None:
        """Build the application Docker image using Docker layer caching."""
        with self.create_progress() as progress:
            task = progress.add_task("Building application image...", total=1)
            self.run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    self.COMPOSE_FILE,
                    "build",
                    "app",
                ]
            )
            progress.update(task, completed=1)
        self.success("Application image built (using cached layers)")

    def _start_services(self) -> None:
        """Start all production services."""
        with self.create_progress() as progress:
            task = progress.add_task("Starting production services...", total=1)
            self.run_command(
                ["docker", "compose", "-f", self.COMPOSE_FILE, "up", "-d", "--remove-orphans"]
            )
            progress.update(task, completed=1)
        self.success("Production services started")

    def _monitor_health_checks(self) -> None:
        """Monitor health checks for all services."""
        self.console.print("\n[bold cyan]🔍 Monitoring service health checks...[/bold cyan]")
        self.console.print("[dim]This may take up to 90 seconds per service...[/dim]\n")

        # Create status table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan", width=20)
        table.add_column("Status", width=15)
        table.add_column("Details", style="dim")

        all_healthy = True

        # Check each service with retries
        for container_name, service_name in self.SERVICES:
            # Wait for container to become healthy (with timeout)
            def check_health(name: str = container_name) -> bool:
                is_healthy, _ = self.health_checker.check_container_health(name)
                return is_healthy

            is_healthy = self.health_checker.wait_for_condition(
                check_health, timeout=90, interval=3, service_name=service_name
            )

            # Get final status for display
            _, status = self.health_checker.check_container_health(container_name)

            if is_healthy:
                table.add_row(
                    service_name, "[bold green]✓ Healthy[/bold green]", status or "Running"
                )
            elif status == "starting":
                table.add_row(
                    service_name, "[bold yellow]⚡ Starting[/bold yellow]", "Still starting up..."
                )
                all_healthy = False
            elif status == "no-healthcheck":
                # For containers without health checks, just verify they're running
                result = self.run_command(
                    [
                        "docker",
                        "inspect",
                        "-f",
                        "{{.State.Running}}",
                        container_name,
                    ],
                    capture_output=True,
                )
                if result.stdout and result.stdout.strip().lower() == "true":
                    table.add_row(
                        service_name,
                        "[bold blue]● Running[/bold blue]",
                        "No health check configured",
                    )
                else:
                    table.add_row(
                        service_name, "[bold red]✗ Not Running[/bold red]", "Container stopped"
                    )
                    all_healthy = False
            else:
                table.add_row(
                    service_name, "[bold red]✗ Unhealthy[/bold red]", status or "Health check failed"
                )
                all_healthy = False

        # Display results
        self.console.print(Panel(table, title="Service Health Status", border_style="green"))

        if not all_healthy:
            self.warning(
                "Some services may need more time to become healthy. "
                "Check logs with: docker compose -f docker-compose.prod.yml logs [service]"
            )
