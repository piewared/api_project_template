"""Base deployer class with shared functionality."""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn


class BaseDeployer(ABC):
    """Abstract base class for all deployers."""

    def __init__(self, console: Console, project_root: Path):
        """Initialize the deployer.

        Args:
            console: Rich console for output
            project_root: Path to the project root directory
        """
        self.console = console
        self.project_root = project_root

    @abstractmethod
    def deploy(self, **kwargs: Any) -> None:
        """Deploy the environment.

        Args:
            **kwargs: Environment-specific deployment options
        """
        pass

    @abstractmethod
    def teardown(self, **kwargs: Any) -> None:
        """Tear down the environment.

        Args:
            **kwargs: Environment-specific teardown options
        """
        pass

    @abstractmethod
    def show_status(self) -> None:
        """Display the current status of the deployment."""
        pass

    def run_command(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        capture_output: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Run a shell command.

        Args:
            cmd: Command and arguments as a list
            cwd: Working directory (defaults to project root)
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise exception on non-zero exit code

        Returns:
            CompletedProcess instance
        """
        return subprocess.run(
            cmd,
            cwd=cwd or self.project_root,
            capture_output=capture_output,
            text=True,
            check=check,
        )

    def check_env_file(self) -> bool:
        """Check if .env file exists and provide helpful guidance if not.

        Returns:
            True if .env file exists, False otherwise
        """
        env_file = self.project_root / ".env"
        env_example = self.project_root / ".env.example"

        if not env_file.exists():
            self.error("❌ .env file not found!")
            self.console.print()
            self.console.print("[bold yellow]📝 Setup Required:[/bold yellow]")
            self.console.print()

            if env_example.exists():
                self.console.print(
                    "  1. Copy the example environment file:\n"
                    f"     [cyan]cp .env.example .env[/cyan]\n"
                )
            else:
                self.console.print(
                    "  1. Create a .env file in the project root:\n"
                    f"     [cyan]touch .env[/cyan]\n"
                )

            self.console.print(
                "  2. Edit .env and configure the following:\n"
                "     • Database credentials (if using PostgreSQL)\n"
                "     • Redis settings (if using Redis)\n"
                "     • OIDC provider secrets (Keycloak/Google/Microsoft)\n"
                "     • Session signing secrets\n"
                "     • CSRF signing secret\n"
            )
            self.console.print()
            self.console.print(
                "[dim]💡 Tip: For development, you can use the defaults from .env.example[/dim]"
            )
            self.console.print()
            return False

        return True

    def create_progress(self, transient: bool = True) -> Progress:
        """Create a progress indicator.

        Args:
            transient: Whether the progress indicator should disappear after completion

        Returns:
            Progress instance
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=transient,
        )

    def success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: The message to print
        """
        self.console.print(f"[green]✅ {message}[/green]")

    def error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: The message to print
        """
        self.console.print(f"[red]❌ {message}[/red]")

    def warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: The message to print
        """
        self.console.print(f"[yellow]⚠️  {message}[/yellow]")

    def info(self, message: str) -> None:
        """Print an info message.

        Args:
            message: The message to print
        """
        self.console.print(f"[blue]ℹ {message}[/blue]")
