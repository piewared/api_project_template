"""Main CLI application module."""

import typer

from .deploy_commands import deploy_app
from .dev_commands import dev_app
from .entity_commands import entity_app

# Create the main CLI application
app = typer.Typer(
    help="🛠️  API Forge CLI - Development and Deployment Tool",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register command groups
app.add_typer(deploy_app, name="deploy")
app.add_typer(entity_app, name="entity")
app.add_typer(dev_app, name="dev")  # Keep for backward compatibility


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
