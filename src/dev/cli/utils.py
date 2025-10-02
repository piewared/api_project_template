"""Shared utilities for CLI commands."""

import subprocess
from pathlib import Path

import typer
from rich.console import Console

# Initialize Rich console for colored output
console = Console()


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


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
