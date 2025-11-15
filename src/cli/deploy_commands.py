"""Deployment CLI commands for dev, prod, and k8s environments."""

import os
import subprocess
import time
from enum import Enum

import requests
import typer
from dotenv.main import load_dotenv
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.dev.dev_utils import (
    check_container_running,
    check_docker_running,
    check_postgres_status,
    check_redis_status,
    check_temporal_status,
    run_keycloak_setup,
    wait_for_keycloak,
)

from .utils import console, get_project_root, run_command

# Create the deploy command group
deploy_app = typer.Typer(help="🚀 Deployment commands for different environments")


class Environment(str, Enum):
    """Deployment environment options."""

    DEV = "dev"
    PROD = "prod"
    K8S = "k8s"


@deploy_app.command()
def up(
    env: Environment = typer.Argument(
        ..., help="Environment to deploy (dev, prod, or k8s)"
    ),
    force: bool = typer.Option(
        False, "--force", help="Force restart even if services are running (dev only)"
    ),
    no_wait: bool = typer.Option(
        False, "--no-wait", help="Don't wait for services to be ready"
    ),
    namespace: str = typer.Option(
        "api-forge-prod", "--namespace", "-n", help="Kubernetes namespace (k8s only)"
    ),
) -> None:
    """
    🚀 Deploy the application to the specified environment.

    Environments:
    - dev: Development environment with hot reload
    - prod: Production-like Docker Compose environment
    - k8s: Kubernetes cluster deployment
    """
    if env == Environment.DEV:
        deploy_dev(force=force, no_wait=no_wait)
    elif env == Environment.PROD:
        deploy_prod(no_wait=no_wait)
    elif env == Environment.K8S:
        deploy_k8s(namespace=namespace, no_wait=no_wait)


def deploy_dev(force: bool = False, no_wait: bool = False) -> None:
    """Deploy development environment with Docker Compose."""
    console.print(
        Panel.fit(
            "[bold blue]Deploying Development Environment[/bold blue]",
            border_style="blue",
        )
    )

    # Check Docker
    if not check_docker_running():
        console.print(
            "[red]❌ Docker is not running. Please start Docker and try again.[/red]"
        )
        raise typer.Exit(1)

    console.print("[green]✅ Docker is running[/green]")

    # Check if services are already running
    keycloak_running = check_container_running("api-forge-keycloak-dev")
    postgres_running = check_container_running("api-forge-postgres-dev")
    redis_running = check_container_running("api-forge-redis-dev")
    temporal_running = check_container_running("api-forge-temporal-dev")

    # Count running services
    running_services = []
    if keycloak_running:
        running_services.append("Keycloak")
    if postgres_running:
        running_services.append("PostgreSQL")
    if redis_running:
        running_services.append("Redis")
    if temporal_running:
        running_services.append("Temporal")

    project_root_dir = get_project_root()

    # Check if ALL services are running
    all_services_running = (
        keycloak_running and postgres_running and redis_running and temporal_running
    )

    # If ALL services are running and --force is NOT used, just skip
    if all_services_running and not force:
        console.print(
            "[green]✅ All services are already running and healthy![/green]"
        )
        console.print(
            "[bold yellow]💡 Tip: Use --force to restart all services (will stop and recreate containers)[/bold yellow]"
        )
        console.print("\n[bold green]🎉 Development environment is ready![/bold green]")
        _display_dev_status()
        console.print(
            "\n[dim]Use 'api-forge-cli deploy down dev' to stop the development services[/dim]"
        )
        return

    # If services are running and --force is used, restart everything
    if running_services and force:
        console.print(
            f"[yellow]⚠️  Found running services: {', '.join(running_services)}[/yellow]"
        )
        console.print("[yellow]🔄 Restarting all services with --force flag...[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task1 = progress.add_task("Stopping existing containers...", total=1)
            run_command(
                [
                    "docker",
                    "compose",
                    "-f",
                    "docker-compose.dev.yml",
                    "down",
                    "--remove-orphans",
                ],
                cwd=project_root_dir,
            )
            progress.update(task1, completed=1)

    # If SOME services are running but --force is NOT used, show warning and stop
    elif running_services:
        console.print(
            f"[yellow]⚠️  Some services are already running: {', '.join(running_services)}[/yellow]"
        )
        console.print(
            "[bold yellow]💡 To avoid conflicts, please use --force to restart all services[/bold yellow]"
        )
        console.print(
            "[dim]This ensures containers are properly recreated with the correct configuration.[/dim]"
        )
        raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # Start containers
        task1 = progress.add_task("Starting Docker containers...", total=1)

        run_command(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.dev.yml",
                "up",
                "-d",
                "--remove-orphans",
            ],
            cwd=project_root_dir,
        )
        progress.update(task1, completed=1)

        if not no_wait:
            # Wait for PostgreSQL
            task2 = progress.add_task("Waiting for PostgreSQL to be ready...", total=1)
            postgres_ready = False
            max_postgres_wait = 30
            postgres_wait_time = 0

            while postgres_wait_time < max_postgres_wait and not postgres_ready:
                postgres_ready = check_postgres_status()
                if not postgres_ready:
                    time.sleep(2)
                    postgres_wait_time += 2

            if postgres_ready:
                progress.update(task2, completed=1)
                console.print("[green]✅ PostgreSQL is ready[/green]")
            else:
                console.print(
                    "[yellow]⚠️  PostgreSQL may not be fully ready yet[/yellow]"
                )

            # Wait for Keycloak
            task3 = progress.add_task("Waiting for Keycloak to be ready...", total=1)

            if wait_for_keycloak():
                progress.update(task3, completed=1)
                console.print("[green]✅ Keycloak is ready[/green]")

                # Run Keycloak setup automatically
                task4 = progress.add_task("Configuring Keycloak...", total=1)
                if run_keycloak_setup():
                    progress.update(task4, completed=1)
                    console.print("[green]✅ Keycloak configured[/green]")
                else:
                    console.print(
                        "[yellow]⚠️  Keycloak setup failed - you may need to run it manually[/yellow]"
                    )
            else:
                console.print("[red]❌ Keycloak failed to start within timeout[/red]")
                raise typer.Exit(1)

            # Wait for Redis
            task5 = progress.add_task("Waiting for Redis to be ready...", total=1)
            redis_ready = False
            max_redis_wait = 20
            redis_wait_time = 0

            while redis_wait_time < max_redis_wait and not redis_ready:
                redis_ready = check_redis_status()
                if not redis_ready:
                    time.sleep(2)
                    redis_wait_time += 2

            if redis_ready:
                progress.update(task5, completed=1)
                console.print("[green]✅ Redis is ready[/green]")
            else:
                console.print("[yellow]⚠️  Redis may not be fully ready yet[/yellow]")

            # Wait for Temporal
            task6 = progress.add_task("Waiting for Temporal to be ready...", total=1)
            temporal_ready = False
            max_temporal_wait = 60
            temporal_wait_time = 0

            while temporal_wait_time < max_temporal_wait and not temporal_ready:
                temporal_ready = check_temporal_status()
                if not temporal_ready:
                    time.sleep(5)
                    temporal_wait_time += 5

            if temporal_ready:
                progress.update(task6, completed=1)
                console.print("[green]✅ Temporal is ready[/green]")
            else:
                console.print("[yellow]⚠️  Temporal may not be fully ready yet[/yellow]")

    console.print("\n[bold green]🎉 Development environment is ready![/bold green]")
    _display_dev_status()

    # Start the development server
    console.print(
        "\n[bold cyan]🚀 Starting FastAPI Development Server...[/bold cyan]"
    )
    console.print(
        "[dim]The server will run with hot reload enabled. Press Ctrl+C to stop.[/dim]\n"
    )

    try:
        run_command(
            [
                "uv",
                "run",
                "uvicorn",
                "src.app.api.http.app:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
                "--reload-dir",
                "src",
                "--log-level",
                "info",
            ],
            cwd=project_root_dir,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
    except typer.Exit:
        console.print("[red]Failed to start development server[/red]")
        raise


def deploy_prod(no_wait: bool = False) -> None:
    """Deploy production environment with Docker Compose."""
    console.print(
        Panel.fit(
            "[bold green]Deploying Production Environment[/bold green]",
            border_style="green",
        )
    )

    # Check Docker
    if not check_docker_running():
        console.print(
            "[red]❌ Docker is not running. Please start Docker and try again.[/red]"
        )
        raise typer.Exit(1)

    console.print("[green]✅ Docker is running[/green]")

    project_root_dir = get_project_root()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # Build the app image
        task1 = progress.add_task("Building application image...", total=1)
        run_command(
            ["docker", "compose", "-f", "docker-compose.prod.yml", "build", "app"],
            cwd=project_root_dir,
        )
        progress.update(task1, completed=1)
        console.print("[green]✅ Application image built[/green]")

        # Start all services
        task2 = progress.add_task("Starting all services...", total=1)
        run_command(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.prod.yml",
                "up",
                "-d",
                "--remove-orphans",
            ],
            cwd=project_root_dir,
        )
        progress.update(task2, completed=1)

        if not no_wait:
            # Wait for PostgreSQL
            task3 = progress.add_task("Waiting for PostgreSQL...", total=1)
            max_wait = 60
            wait_time = 0
            postgres_healthy = False

            while wait_time < max_wait and not postgres_healthy:
                result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format={{.State.Health.Status}}",
                        "api-forge-postgres",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=project_root_dir,
                )
                if result.returncode == 0 and "healthy" in result.stdout:
                    postgres_healthy = True
                else:
                    time.sleep(2)
                    wait_time += 2

            if postgres_healthy:
                progress.update(task3, completed=1)
                console.print("[green]✅ PostgreSQL is healthy[/green]")
            else:
                console.print(
                    "[yellow]⚠️  PostgreSQL health check timeout[/yellow]"
                )

            # Wait for Redis
            task4 = progress.add_task("Waiting for Redis...", total=1)
            wait_time = 0
            redis_healthy = False

            while wait_time < max_wait and not redis_healthy:
                result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format={{.State.Health.Status}}",
                        "api-forge-redis",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=project_root_dir,
                )
                if result.returncode == 0 and "healthy" in result.stdout:
                    redis_healthy = True
                else:
                    time.sleep(2)
                    wait_time += 2

            if redis_healthy:
                progress.update(task4, completed=1)
                console.print("[green]✅ Redis is healthy[/green]")
            else:
                console.print("[yellow]⚠️  Redis health check timeout[/yellow]")

            # Wait for Temporal
            task5 = progress.add_task("Waiting for Temporal...", total=1)
            wait_time = 0
            temporal_healthy = False

            while wait_time < max_wait and not temporal_healthy:
                result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format={{.State.Health.Status}}",
                        "api-forge-temporal",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=project_root_dir,
                )
                if result.returncode == 0 and "healthy" in result.stdout:
                    temporal_healthy = True
                else:
                    time.sleep(2)
                    wait_time += 2

            if temporal_healthy:
                progress.update(task5, completed=1)
                console.print("[green]✅ Temporal is healthy[/green]")
            else:
                console.print("[yellow]⚠️  Temporal health check timeout[/yellow]")

            # Wait for Application
            task6 = progress.add_task("Waiting for Application...", total=1)
            wait_time = 0
            app_healthy = False

            while wait_time < max_wait and not app_healthy:
                result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format={{.State.Health.Status}}",
                        "api-forge-app",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=project_root_dir,
                )
                if result.returncode == 0 and "healthy" in result.stdout:
                    app_healthy = True
                else:
                    time.sleep(2)
                    wait_time += 2

            if app_healthy:
                progress.update(task6, completed=1)
                console.print("[green]✅ Application is healthy[/green]")
            else:
                console.print("[yellow]⚠️  Application health check timeout[/yellow]")

            # Wait for Worker
            task7 = progress.add_task("Waiting for Worker...", total=1)
            wait_time = 0
            worker_healthy = False

            while wait_time < max_wait and not worker_healthy:
                result = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format={{.State.Health.Status}}",
                        "api-forge-worker",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=project_root_dir,
                )
                if result.returncode == 0 and "healthy" in result.stdout:
                    worker_healthy = True
                else:
                    time.sleep(2)
                    wait_time += 2

            if worker_healthy:
                progress.update(task7, completed=1)
                console.print("[green]✅ Worker is healthy[/green]")
            else:
                console.print("[yellow]⚠️  Worker health check timeout[/yellow]")

    console.print("\n[bold green]🎉 Production environment is ready![/bold green]")
    _display_prod_status()


def deploy_k8s(namespace: str = "api-forge-prod", no_wait: bool = False) -> None:
    """Deploy to Kubernetes cluster."""
    console.print(
        Panel.fit(
            "[bold magenta]Deploying to Kubernetes[/bold magenta]",
            border_style="magenta",
        )
    )

    project_root_dir = get_project_root()

    # Check if kubectl is available
    try:
        subprocess.run(
            ["kubectl", "version", "--client"],
            capture_output=True,
            check=True,
            cwd=project_root_dir,
        )
        console.print("[green]✅ kubectl is available[/green]")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        console.print("[red]❌ kubectl is not available or not configured[/red]")
        raise typer.Exit(1) from e

    # Check cluster connectivity
    try:
        subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            check=True,
            cwd=project_root_dir,
        )
        console.print("[green]✅ Connected to Kubernetes cluster[/green]")
    except subprocess.CalledProcessError as e:
        console.print("[red]❌ Cannot connect to Kubernetes cluster[/red]")
        raise typer.Exit(1) from e

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        # Build images - run from project root
        task1 = progress.add_task("Building Docker images...", total=1)
        result = subprocess.run(
            ["bash", "k8s/scripts/build-images.sh"],
            cwd=project_root_dir,
            capture_output=False,
        )
        if result.returncode != 0:
            console.print("[red]❌ Failed to build images[/red]")
            raise typer.Exit(1)
        progress.update(task1, completed=1)
        console.print("[green]✅ Images built successfully[/green]")

        # Create secrets (if needed) - run from project root
        task2 = progress.add_task("Creating Kubernetes secrets...", total=1)
        result = subprocess.run(
            ["bash", "k8s/scripts/create-secrets.sh", namespace],
            cwd=project_root_dir,
            capture_output=False,
        )
        if result.returncode != 0:
            console.print("[yellow]⚠️  Secrets may already exist or creation failed[/yellow]")
        else:
            console.print("[green]✅ Secrets created[/green]")
        progress.update(task2, completed=1)

        # Deploy resources - run from project root
        task3 = progress.add_task("Deploying Kubernetes resources...", total=1)
        result = subprocess.run(
            ["bash", "k8s/scripts/deploy-resources.sh", namespace],
            cwd=project_root_dir,
            capture_output=False,
        )
        if result.returncode != 0:
            console.print("[red]❌ Failed to deploy resources[/red]")
            raise typer.Exit(1)
        progress.update(task3, completed=1)

    console.print("\n[bold green]🎉 Kubernetes deployment complete![/bold green]")
    _display_k8s_status(namespace)


@deploy_app.command()
def down(
    env: Environment = typer.Argument(
        ..., help="Environment to stop (dev, prod, or k8s)"
    ),
    namespace: str = typer.Option(
        "api-forge-prod", "--namespace", "-n", help="Kubernetes namespace (k8s only)"
    ),
    volumes: bool = typer.Option(
        False, "--volumes", "-v", help="Remove volumes (Docker Compose only)"
    ),
) -> None:
    """
    ⏹️  Stop services in the specified environment.

    Environments:
    - dev: Stop development Docker Compose services
    - prod: Stop production Docker Compose services
    - k8s: Delete Kubernetes deployment
    """
    project_root_dir = get_project_root()

    if env == Environment.DEV:
        console.print(
            Panel.fit(
                "[bold red]Stopping Development Environment[/bold red]",
                border_style="red",
            )
        )

        cmd = ["docker", "compose", "-f", "docker-compose.dev.yml", "down", "--remove-orphans"]
        if volumes:
            cmd.append("-v")

        with console.status("[bold red]Stopping containers..."):
            run_command(cmd, cwd=project_root_dir)

        console.print("[green]✅ Development services stopped[/green]")

    elif env == Environment.PROD:
        console.print(
            Panel.fit(
                "[bold red]Stopping Production Environment[/bold red]",
                border_style="red",
            )
        )

        cmd = ["docker", "compose", "-f", "docker-compose.prod.yml", "down", "--remove-orphans"]
        if volumes:
            cmd.append("-v")

        with console.status("[bold red]Stopping containers..."):
            run_command(cmd, cwd=project_root_dir)

        console.print("[green]✅ Production services stopped[/green]")

    elif env == Environment.K8S:
        console.print(
            Panel.fit(
                "[bold red]Deleting Kubernetes Deployment[/bold red]",
                border_style="red",
            )
        )

        with console.status(f"[bold red]Deleting namespace {namespace}..."):
            result = subprocess.run(
                ["kubectl", "delete", "namespace", namespace],
                capture_output=True,
                text=True,
                cwd=project_root_dir,
            )

        if result.returncode == 0:
            console.print(f"[green]✅ Namespace {namespace} deleted[/green]")
        else:
            console.print(f"[yellow]⚠️  Failed to delete namespace: {result.stderr}[/yellow]")


def _display_dev_status() -> None:
    """Display development environment status."""
    console.print(
        Panel.fit(
            "[bold cyan]Development Services Status[/bold cyan]", border_style="cyan"
        )
    )

    load_dotenv()

    app_db = os.getenv("APP_DB", "appdb")
    app_user = os.getenv("APP_DB_USER", "appuser")
    app_password = os.getenv("APP_DB_USER_PW", "devpass")

    # Check Docker
    docker_running = check_docker_running()
    status_text = (
        "[green]✅ Running[/green]" if docker_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Docker: {status_text}")

    # Check Keycloak
    keycloak_running = check_container_running("api-forge-keycloak-dev")
    status_text = (
        "[green]✅ Running[/green]" if keycloak_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Keycloak: {status_text}")

    if keycloak_running:
        try:
            response = requests.get("http://localhost:8080/realms/master", timeout=5)
            if response.status_code == 200:
                console.print("  └─ Health: [green]✅ Ready[/green]")
                console.print("  └─ Server: http://localhost:8080")
                console.print(
                    "  └─ Admin UI: http://localhost:8080/admin/master/console/"
                )
        except requests.exceptions.RequestException:
            console.print("  └─ Health: [yellow]⚠️  Cannot connect[/yellow]")

    # Check PostgreSQL
    postgres_running = check_container_running("api-forge-postgres-dev")
    status_text = (
        "[green]✅ Running[/green]" if postgres_running else "[red]❌ Not running[/red]"
    )
    console.print(f"PostgreSQL: {status_text}")

    if postgres_running and check_postgres_status():
        console.print("  └─ Health: [green]✅ Ready[/green]")
        console.print(
            "  └─ Server: postgresql://appuser:devpass@localhost:5433/appdb"
        )
        console.print(f"  └─ Database: {app_db}")
        console.print(f"  └─ Username: {app_user}")
        console.print(f"  └─ Password: {app_password}")
        console.print(
            f"  └─ Connection (localhost): "
            f"[cyan]postgresql://{app_user}:{app_password}@localhost:5433/{app_db}[/cyan]"
        )
        console.print(
            f"  └─ Connection (container): "
            f"[cyan]postgresql://{app_user}:{app_password}@app_dev_postgres_db:5432/{app_db}[/cyan]"
        )

    # Check Redis
    redis_running = check_container_running("api-forge-redis-dev")
    status_text = (
        "[green]✅ Running[/green]" if redis_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Redis: {status_text}")

    if redis_running and check_redis_status():
        console.print("  └─ Health: [green]✅ Ready[/green]")
        console.print("  └─ Server: redis://localhost:6380/0")

    # Check Temporal
    temporal_server_running = check_container_running("api-forge-temporal-dev")
    temporal_web_running = check_container_running("api-forge-temporal-ui-dev")

    status_text = (
        "[green]✅ Running[/green]"
        if temporal_server_running
        else "[red]❌ Not running[/red]"
    )
    console.print(f"Temporal: {status_text}")

    if temporal_server_running and check_temporal_status():
        console.print("  └─ Health: [green]✅ Ready[/green]")
        console.print("  └─ Server: localhost:7234")
        console.print("  └─ Protocol: gRPC")

        if temporal_web_running:
            console.print("  └─ Web UI: [green]✅ http://localhost:8082[/green]")


def _display_prod_status() -> None:
    """Display production environment status."""
    console.print(
        Panel.fit(
            "[bold green]Production Services Status[/bold green]", border_style="green"
        )
    )

    services = [
        ("PostgreSQL", "api-forge-postgres"),
        ("Redis", "api-forge-redis"),
        ("Temporal", "api-forge-temporal"),
        ("Temporal Web", "api-forge-temporal-web"),
        ("Application", "api-forge-app"),
        ("Worker", "api-forge-worker"),
    ]

    for service_name, container_name in services:
        # First check if container is running using exact name match
        check_result = subprocess.run(
            ["docker", "ps", "--filter", f"name=^/{container_name}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )

        container_found = check_result.returncode == 0 and container_name in check_result.stdout

        if not container_found:
            console.print(f"{service_name}: [red]❌ Not running[/red]")
            continue

        # Then check health status
        result = subprocess.run(
            ["docker", "inspect", "--format={{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}", container_name],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            health = result.stdout.strip()
            if health == "healthy":
                status = "[green]✅ Healthy[/green]"
            elif health == "no-healthcheck" or health == "":
                # No health check defined - container is running
                status = "[green]✅ Running[/green]"
            else:
                status = f"[yellow]⚠️  {health.capitalize()}[/yellow]"
            console.print(f"{service_name}: {status}")
        else:
            # Fallback - container is running but inspect failed
            console.print(f"{service_name}: [green]✅ Running[/green]")

    console.print("\n[bold cyan]Access URLs:[/bold cyan]")
    console.print("  └─ API: http://localhost:8000")
    console.print("  └─ Health: http://localhost:8000/health")
    console.print("  └─ API Docs: http://localhost:8000/docs")
    console.print("  └─ Temporal Web: http://localhost:8081")


def _display_k8s_status(namespace: str) -> None:
    """Display Kubernetes deployment status."""
    console.print(
        Panel.fit(
            "[bold magenta]Kubernetes Deployment Status[/bold magenta]",
            border_style="magenta",
        )
    )

    # Get pod status
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "wide"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print("\n[bold cyan]Pods:[/bold cyan]")
        console.print(result.stdout)

    # Get service status
    result = subprocess.run(
        ["kubectl", "get", "svc", "-n", namespace],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print("\n[bold cyan]Services:[/bold cyan]")
        console.print(result.stdout)

    console.print("\n[bold cyan]Access Instructions:[/bold cyan]")
    console.print(f"  └─ Port-forward to app: kubectl port-forward -n {namespace} svc/app 8000:8000")
    console.print(f"  └─ Port-forward to Temporal Web: kubectl port-forward -n {namespace} svc/temporal-web 8080:8080")
    console.print(f"  └─ View logs: kubectl logs -n {namespace} -l app.kubernetes.io/name=app -f")
