"""Development environment CLI commands."""

import os
import time

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

from .user_commands import users_app
from .utils import console, get_dev_dir, get_project_root, run_command

# Create the dev command group
dev_app = typer.Typer(help="🚀 Development environment commands")

# Add users subcommand
dev_app.add_typer(users_app, name="users")


@dev_app.command(name="start-server")
def start_server(
    host: str = typer.Option("0.0.0.0", help="Host to bind the server to"),
    port: int = typer.Option(8000, help="Port to bind the server to"),
    reload: bool = typer.Option(True, help="Enable auto-reload on code changes"),
    log_level: str = typer.Option(
        "info", help="Log level (debug, info, warning, error, critical)"
    ),
) -> None:
    """
    🚀 Start the FastAPI development server.

    This command starts the FastAPI application in development mode with hot reloading
    and detailed logging. Perfect for development and testing.
    """
    console.print(
        Panel.fit(
            "[bold green]Starting FastAPI Development Server[/bold green]",
            border_style="green",
        )
    )

    from .utils import get_project_root

    project_root = get_project_root()

    # Build the uvicorn command
    cmd = [
        "uv",
        "run",
        "uvicorn",
        "src.app.api.http.app:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        log_level,
    ]

    if reload:
        cmd.extend(["--reload", "--reload-dir", "src"])

    console.print(f"[blue]Running:[/blue] {' '.join(cmd)}")
    console.print(f"[blue]Server will be available at:[/blue] http://{host}:{port}")
    console.print("[dim]Press Ctrl+C to stop the server[/dim]")

    try:
        run_command(cmd, cwd=project_root)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
    except typer.Exit:
        console.print("[red]Failed to start development server[/red]")
        raise


@dev_app.command(name="start-env")
def start_env(
    force: bool = typer.Option(
        False, "--force", help="Force restart even if services are running"
    ),
    no_wait: bool = typer.Option(
        False, "--no-wait", help="Don't wait for services to be ready"
    ),
) -> None:
    """
    🐳 Set up development environment with required services.

    This command starts Docker containers for development services:
    - Keycloak (OIDC provider for authentication testing)
    - PostgreSQL (Database for development and testing)
    - Redis (Caching and session storage)
    - Temporal (Workflow orchestration server)

    The services will be configured with test data and ready for development.
    """
    console.print(
        Panel.fit(
            "[bold blue]Setting Up Development Environment[/bold blue]",
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
    keycloak_running = check_container_running("api-template-keycloak-dev")
    postgres_running = check_container_running("api-template-postgres-dev")
    redis_running = check_container_running("api-template-redis-dev")
    temporal_running = check_container_running("api-template-temporal-dev")

    if (
        keycloak_running or postgres_running or redis_running or temporal_running
    ) and not force:
        console.print(
            "[yellow]⚠️  Services are already running. Use --force to restart.[/yellow]"
        )
        return

    project_root_dir = get_project_root()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # Start containers
        task1 = progress.add_task("Starting Docker containers...", total=1)

        if force and (
            keycloak_running or postgres_running or redis_running or temporal_running
        ):
            console.print("[yellow]Stopping existing containers...[/yellow]")
            run_command(
                ["docker", "compose", "-f", "docker-compose.dev.yml", "down"],
                cwd=project_root_dir,
            )

        run_command(
            ["docker", "compose", "-f", "docker-compose.dev.yml", "up", "-d"],
            cwd=project_root_dir,
        )
        progress.update(task1, completed=1)

        if not no_wait:
            # Wait for PostgreSQL to be ready first
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

            # Wait for Keycloak to be ready
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

            # Wait for Redis to be ready
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

            # Wait for Temporal to be ready
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
    status()
    console.print("\n[dim]Use 'cli dev start-server' to start the API server[/dim]")


def _check_docker_status() -> bool:
    """Check Docker daemon status."""
    docker_running = check_docker_running()
    status_text = (
        "[green]✅ Running[/green]" if docker_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Docker: {status_text}")

    if not docker_running:
        console.print(
            "[yellow]⚠️  Docker is not running. Please start Docker first.[/yellow]"
        )

    return docker_running


def _check_keycloak_status() -> None:
    """Check Keycloak container and health status."""
    keycloak_running = check_container_running("api-template-keycloak-dev")
    status_text = (
        "[green]✅ Running[/green]" if keycloak_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Keycloak: {status_text}")

    if not keycloak_running:
        return

    # Check Keycloak health using master realm endpoint
    try:
        response = requests.get("http://localhost:8080/realms/master", timeout=5)
        if response.status_code == 200:
            console.print("  └─ Health: ✅ Ready")
            console.print("  └─ Server: http://localhost:8080")
            console.print("  └─ Admin UI: http://localhost:8080/admin/master/console/")
        else:
            console.print("  └─ Health: ⚠️  Not ready")
            console.print("  └─ Server: http://localhost:8080")
    except requests.exceptions.RequestException:
        console.print("  └─ Health: ⚠️  Cannot connect")
        console.print("  └─ Server: http://localhost:8080")


def _check_postgres_status(
    app_db: str, app_user: str, app_password: str, app_db_url: str
) -> None:
    """Check PostgreSQL container and connection status."""
    postgres_running = check_container_running("api-template-postgres-dev")
    status_text = (
        "[green]✅ Running[/green]" if postgres_running else "[red]❌ Not running[/red]"
    )
    console.print(f"PostgreSQL: {status_text}")

    if not postgres_running:
        return

    if check_postgres_status():
        console.print("  └─ Health: ✅ Ready")
        console.print(f"  └─ Server: {app_db_url}")
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
    else:
        console.print("  └─ Health: ⚠️  Not ready")
        console.print(f"  └─ Server: {app_db_url}")


def _check_redis_status(redis_url: str) -> None:
    """Check Redis container and connection status."""
    redis_running = check_container_running("api-template-redis-dev")
    status_text = (
        "[green]✅ Running[/green]" if redis_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Redis: {status_text}")

    if not redis_running:
        return

    if check_redis_status():
        console.print("  └─ Health: ✅ Ready")
        console.print(f"  └─ Server: {redis_url}")
    else:
        console.print("  └─ Health: ⚠️  Not ready")
        console.print(f"  └─ Server: {redis_url}")


def _check_temporal_status(temporal_url: str) -> None:
    """Check Temporal server and UI status."""
    temporal_server_running = check_container_running("api-template-temporal-dev")
    temporal_web_running = check_container_running("api-template-temporal-ui-dev")

    status_text = (
        "[green]✅ Running[/green]"
        if temporal_server_running
        else "[red]❌ Not running[/red]"
    )
    console.print(f"Temporal: {status_text}")

    if not temporal_server_running:
        return

    if check_temporal_status():
        console.print("  └─ Health: ✅ Ready")
        console.print(f"  └─ Server: {temporal_url}")
        console.print("  └─ Protocol: gRPC")
    else:
        console.print("  └─ Health: ⚠️  Not ready")
        console.print(f"  └─ Server: {temporal_url}")

    if temporal_web_running:
        console.print("  └─ Web UI: ✅ http://localhost:8082")
    else:
        console.print("  └─ Web UI: ⚠️  Not running")


@dev_app.command()
def status() -> None:
    """
    📊 Check the status of development services.

    Shows which development services are running and their health status.
    """
    console.print(
        Panel.fit(
            "[bold cyan]Development Services Status[/bold cyan]", border_style="cyan"
        )
    )

    load_dotenv()

    # Load environment configuration
    app_db = os.getenv("APP_DB", "appdb")
    app_user = os.getenv("APP_DB_USER", "appuser")
    app_password = os.getenv("APP_DB_USER_PW", "devpass")
    app_db_url = os.getenv("DEVELOPMENT_DATABASE_URL", "localhost:5433")
    redis_url = os.getenv("DEVELOPMENT_REDIS_URL", "redis://localhost:6380")
    temporal_url = os.getenv("DEVELOPMENT_TEMPORAL_URL", "localhost:7234")

    # Check Docker first - exit early if not running
    if not _check_docker_status():
        return

    # Check all services
    _check_keycloak_status()
    _check_postgres_status(app_db, app_user, app_password, app_db_url)
    _check_redis_status(redis_url)
    _check_temporal_status(temporal_url)


@dev_app.command()
def stop() -> None:
    """
    ⏹️  Stop all development services.

    Stops and removes all Docker containers used for development.
    """
    console.print(
        Panel.fit(
            "[bold red]Stopping Development Services[/bold red]", border_style="red"
        )
    )

    project_root = get_project_root()

    with console.status("[bold red]Stopping containers..."):
        run_command(
            ["docker", "compose", "-f", "docker-compose.dev.yml", "down"],
            cwd=project_root,
        )

    console.print("[green]✅ All development services stopped[/green]")


@dev_app.command()
def logs(
    service: str = typer.Argument("keycloak", help="Service to show logs for"),
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow log output"),
    lines: int = typer.Option(50, "-n", "--lines", help="Number of lines to show"),
) -> None:
    """
    📋 Show logs from development services.

    Display logs from Docker containers. Use --follow to stream logs in real-time.
    """
    dev_dir = get_dev_dir()

    cmd = ["docker-compose", "logs"]

    if follow:
        cmd.append("--follow")

    cmd.extend(["--tail", str(lines), service])

    console.print(f"[blue]Showing logs for {service}...[/blue]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    try:
        run_command(cmd, cwd=dev_dir)
    except KeyboardInterrupt:
        console.print("\n[yellow]Log streaming stopped[/yellow]")
