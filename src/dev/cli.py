#!/usr/bin/env python3
"""CLI interface for API development utilities.

This module provides a command-line interface for managing the development
environment, including starting services, managing containers, and entities.
"""

import subprocess
import requests
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import development utilities
from .dev_utils import (
    check_container_running,
    check_docker_running,
    check_postgres_status,
    check_redis_status,
    check_temporal_status,
    run_keycloak_setup,
    wait_for_keycloak,
)

# Initialize Rich console for colored output
console = Console()

# Initialize the main CLI app
app = typer.Typer(
    name="api-dev",
    help="API Development CLI - Manage development services and project entities",
    rich_markup_mode="rich",
)

# Create command groups
entity_app = typer.Typer(help="🏗️ Entity management commands")
dev_app = typer.Typer(help="🚀 Development environment commands")

# Add command groups to main app
app.add_typer(entity_app, name="entity")
app.add_typer(dev_app, name="dev")


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def get_dev_dir() -> Path:
    """Get the dev_env directory (infrastructure and Docker files)."""
    project_root = get_project_root()
    return project_root / "dev_env"


def run_command(
    command: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run a shell command with proper error handling."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd or get_project_root(),
            check=check,
            capture_output=capture_output,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Command failed: {' '.join(command)}[/red]")
        console.print(f"[red]Exit code: {e.returncode}[/red]")
        if e.stdout:
            console.print(f"[red]stdout: {e.stdout}[/red]")
        if e.stderr:
            console.print(f"[red]stderr: {e.stderr}[/red]")
        raise typer.Exit(1) from e


@dev_app.command(name="start-server")
def start_dev_server(
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


@dev_app.command(name="start-dev-env")
def setup_dev(
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
    keycloak_running = check_container_running("keycloak")
    postgres_running = check_container_running("postgres")
    redis_running = check_container_running("redis")
    temporal_running = check_container_running("temporal-server")

    if (
        keycloak_running or postgres_running or redis_running or temporal_running
    ) and not force:
        console.print(
            "[yellow]⚠️  Services are already running. Use --force to restart.[/yellow]"
        )
        return

    dev_dir = get_dev_dir()

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
            run_command(["docker-compose", "down"], cwd=dev_dir)

        run_command(["docker-compose", "up", "-d"], cwd=dev_dir)
        progress.update(task1, completed=1)

        if not no_wait:
            # Wait for PostgreSQL to be ready first
            task2 = progress.add_task("Waiting for PostgreSQL to be ready...", total=1)

            # Wait with timeout for PostgreSQL
            import time

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
    console.print("\n[blue]Available services:[/blue]")
    console.print("  • Keycloak: http://localhost:8080")
    console.print("    - Admin console: http://localhost:8080/admin")
    console.print("    - Username: admin, Password: admin")
    console.print("    - Test realm: http://localhost:8080/realms/test-realm")
    console.print("  • PostgreSQL: localhost:5432")
    console.print("    - Database: devdb (devuser/devpass)")
    console.print("    - Test DB: testdb (devuser/devpass)")
    console.print("  • Redis: localhost:6379")
    console.print("    - Connection: redis://localhost:6379")
    console.print("    - Persistence: AOF enabled")
    console.print("  • Temporal: localhost:7233")
    console.print("    - gRPC API: localhost:7233")
    console.print("    - Web UI: http://localhost:8088")

    console.print("\n[dim]Use 'api-dev dev start-server' to start the API server[/dim]")


# Entity Management Commands
@entity_app.command(name="add")
def entity_add(
    name: str = typer.Argument(..., help="Name of the entity to create"),
    fields: str = typer.Option(
        "", help="Comma-separated list of field:type pairs (e.g., 'name:str,age:int')"
    ),
) -> None:
    """
    ➕ Add a new entity to the project.

    Creates a new entity with the specified name and optional fields.
    This will generate the necessary entity files and update related modules.
    """
    console.print(
        Panel.fit(
            f"[bold green]Adding Entity: {name}[/bold green]", border_style="green"
        )
    )

    project_root = get_project_root()
    entities_dir = project_root / "src" / "app" / "entities"

    if not entities_dir.exists():
        console.print(f"[red]❌ Entities directory not found: {entities_dir}[/red]")
        raise typer.Exit(1)

    entity_dir = entities_dir / name.lower()
    if entity_dir.exists():
        console.print(f"[red]❌ Entity '{name}' already exists[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]📁 Creating entity directory: {entity_dir}[/blue]")
    entity_dir.mkdir(parents=True, exist_ok=True)

    # Create basic entity files
    init_file = entity_dir / "__init__.py"
    model_file = entity_dir / "model.py"

    # Create __init__.py
    init_content = (
        f'"""Entity: {name}"""\n\nfrom .model import {name}\n\n__all__ = ["{name}"]\n'
    )
    init_file.write_text(init_content)

    # Create basic model file
    model_content = f'''"""Entity model: {name}"""

from typing import Optional
from sqlmodel import SQLModel, Field


class {name}(SQLModel, table=True):
    """
    {name} entity model.
    """
    __tablename__ = "{name.lower()}s"

    id: Optional[int] = Field(default=None, primary_key=True)
'''

    # Add fields if provided
    if fields:
        field_pairs = [f.strip() for f in fields.split(",")]
        for field_pair in field_pairs:
            if ":" in field_pair:
                field_name, field_type = field_pair.split(":", 1)
                field_name = field_name.strip()
                field_type = field_type.strip()
                model_content += f"    {field_name}: Optional[{field_type}] = None\n"

    model_file.write_text(model_content)

    console.print(f"[green]✅ Entity '{name}' created successfully[/green]")
    console.print("[blue]📄 Files created:[/blue]")
    console.print(f"  - {init_file}")
    console.print(f"  - {model_file}")


@entity_app.command(name="rm")
def entity_remove(
    name: str = typer.Argument(..., help="Name of the entity to remove"),
    force: bool = typer.Option(
        False, "--force", help="Force removal without confirmation"
    ),
) -> None:
    """
    🗑️ Remove an entity from the project.

    Removes the entity directory and all associated files.
    Use --force to skip confirmation prompt.
    """
    console.print(
        Panel.fit(f"[bold red]Removing Entity: {name}[/bold red]", border_style="red")
    )

    project_root = get_project_root()
    entities_dir = project_root / "src" / "app" / "entities"
    entity_dir = entities_dir / name.lower()

    if not entity_dir.exists():
        console.print(f"[red]❌ Entity '{name}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirmed = typer.confirm(f"Are you sure you want to remove entity '{name}'?")
        if not confirmed:
            console.print("[yellow]❌ Operation cancelled[/yellow]")
            raise typer.Exit(0)

    # Remove entity directory
    import shutil

    shutil.rmtree(entity_dir)

    console.print(f"[green]✅ Entity '{name}' removed successfully[/green]")


@entity_app.command(name="ls")
def entity_list() -> None:
    """
    📋 List all entities in the project.

    Shows all existing entities and their basic information.
    """
    console.print(
        Panel.fit("[bold cyan]Project Entities[/bold cyan]", border_style="cyan")
    )

    project_root = get_project_root()
    entities_dir = project_root / "src" / "app" / "entities"

    if not entities_dir.exists():
        console.print(f"[red]❌ Entities directory not found: {entities_dir}[/red]")
        raise typer.Exit(1)

    entities = []
    for item in entities_dir.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            model_file = item / "model.py"
            has_model = "✅" if model_file.exists() else "❌"
            entities.append((item.name, has_model))

    if not entities:
        console.print("[yellow]📭 No entities found[/yellow]")
        return

    console.print(f"[blue]Found {len(entities)} entities:[/blue]\n")
    for entity_name, has_model in sorted(entities):
        console.print(f"  {has_model} [bold]{entity_name}[/bold]")

    console.print(f"\n[dim]Total: {len(entities)} entities[/dim]")


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

    # Check Docker
    docker_running = check_docker_running()
    docker_status = (
        "[green]✅ Running[/green]" if docker_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Docker: {docker_status}")

    if not docker_running:
        console.print("[yellow]⚠️  Docker is not running. Please start Docker first.[/yellow]")
        return

    # Check Keycloak
    keycloak_running = check_container_running("dev_env_keycloak_1")
    keycloak_status = (
        "[green]✅ Running[/green]" if keycloak_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Keycloak: {keycloak_status}")

    if keycloak_running:
        # Check Keycloak health using master realm endpoint
        try:
            response = requests.get("http://localhost:8080/realms/master", timeout=5)
            if response.status_code == 200:
                console.print("  [green]└─ Health: ✅ Ready[/green]")
                console.print("  [green]└─ Admin UI: http://localhost:8080/admin/master/console/[/green]")
            else:
                console.print("  [yellow]└─ Health: ⚠️  Not ready[/yellow]")
        except requests.exceptions.RequestException:
            console.print("  [yellow]└─ Health: ⚠️  Cannot reach Keycloak[/yellow]")

    # Check PostgreSQL
    postgres_running = check_container_running("dev_env_postgres_1")
    postgres_status = (
        "[green]✅ Running[/green]" if postgres_running else "[red]❌ Not running[/red]"
    )
    console.print(f"PostgreSQL: {postgres_status}")

    if postgres_running:
        # Check PostgreSQL connection using utility function
        if check_postgres_status():
            console.print("  [green]└─ Connection: ✅ Ready[/green]")
            console.print("  [green]└─ Databases: devdb, testdb[/green]")
        else:
            console.print("  [yellow]└─ Connection: ⚠️  Not ready[/yellow]")

    # Check Redis
    redis_running = check_container_running("dev_env_redis_1")
    redis_status = (
        "[green]✅ Running[/green]" if redis_running else "[red]❌ Not running[/red]"
    )
    console.print(f"Redis: {redis_status}")

    if redis_running:
        # Check Redis connection using utility function
        if check_redis_status():
            console.print("  [green]└─ Connection: ✅ Ready[/green]")
            console.print("  [green]└─ Server: localhost:6379[/green]")
        else:
            console.print("  [yellow]└─ Connection: ⚠️  Not ready[/yellow]")

    # Check Temporal
    temporal_server_running = check_container_running("api-template-temporal")
    temporal_web_running = check_container_running("api-template-temporal-ui")
    temporal_status = (
        "[green]✅ Running[/green]"
        if temporal_server_running
        else "[red]❌ Not running[/red]"
    )
    console.print(f"Temporal: {temporal_status}")

    if temporal_server_running:
        # Check Temporal health using the utility function
        if check_temporal_status():
            console.print("  [green]└─ Server: ✅ Healthy[/green]")
            console.print("  [green]└─ gRPC API: localhost:7233[/green]")
        else:
            console.print("  [yellow]└─ Server: ⚠️  Not ready[/yellow]")

        if temporal_web_running:
            console.print(
                "  [green]└─ Web UI: ✅ Running (http://localhost:8081)[/green]"
            )
        else:
            console.print("  [yellow]└─ Web UI: ⚠️  Not running[/yellow]")


if __name__ == "__main__":
    app()

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

    dev_dir = get_dev_dir()

    with console.status("[bold red]Stopping containers..."):
        run_command(["docker-compose", "down"], cwd=dev_dir)

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


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
