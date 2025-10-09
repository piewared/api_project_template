"""Keycloak user management CLI commands."""

import typer
from rich.panel import Panel
from rich.table import Table

from ..setup_keycloak import KeycloakSetup
from .utils import console

# Create the users command group
users_app = typer.Typer(help="👥 Keycloak user management commands")


def get_keycloak_setup() -> KeycloakSetup:
    """Get a configured KeycloakSetup instance."""
    setup = KeycloakSetup()
    try:
        setup.get_admin_token()
        return setup
    except Exception as e:
        console.print(f"[red]❌ Failed to connect to Keycloak: {e}[/red]")
        console.print("[yellow]Make sure Keycloak is running: uv run cli dev start-env[/yellow]")
        raise typer.Exit(1) from None


@users_app.command("list")
def list_users(
    realm: str = typer.Option("test-realm", help="Keycloak realm to list users from"),
    limit: int = typer.Option(10, help="Maximum number of users to show"),
) -> None:
    """
    📋 List users in a Keycloak realm.

    Shows a table of users with their basic information including username,
    email, name, and enabled status.
    """
    console.print(
        Panel.fit(
            f"[bold cyan]Users in Realm: {realm}[/bold cyan]",
            border_style="cyan",
        )
    )

    setup = get_keycloak_setup()

    try:
        users = setup.list_users(realm, limit)

        if not users:
            console.print(f"[yellow]No users found in realm '{realm}'[/yellow]")
            return

        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Username", style="cyan")
        table.add_column("Email", style="green")
        table.add_column("First Name", style="blue")
        table.add_column("Last Name", style="blue")
        table.add_column("Enabled", style="yellow")
        table.add_column("Email Verified", style="yellow")

        for user in users:
            enabled = "✅" if user.get("enabled", False) else "❌"
            email_verified = "✅" if user.get("emailVerified", False) else "❌"
            table.add_row(
                user.get("username", ""),
                user.get("email", ""),
                user.get("firstName", ""),
                user.get("lastName", ""),
                enabled,
                email_verified,
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(users)} users[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Failed to list users: {e}[/red]")
        raise typer.Exit(1) from None


@users_app.command("add")
def add_user(
    username: str = typer.Argument(..., help="Username for the new user"),
    email: str = typer.Argument(..., help="Email address for the new user"),
    password: str = typer.Option(
        "password123", "--password", "-p", help="Password for the new user"
    ),
    first_name: str | None = typer.Option(None, "--first-name", help="First name"),
    last_name: str | None = typer.Option(None, "--last-name", help="Last name"),
    realm: str = typer.Option("test-realm", help="Keycloak realm to add user to"),
    enabled: bool = typer.Option(True, help="Whether the user should be enabled"),
    email_verified: bool = typer.Option(True, help="Whether the email should be marked as verified"),
    temporary_password: bool = typer.Option(False, help="Whether the password is temporary"),
) -> None:
    """
    ➕ Add a new user to a Keycloak realm.

    Creates a new user with the specified credentials and attributes.
    The user will be created with basic profile information and a password.
    """
    console.print(
        Panel.fit(
            f"[bold green]Adding User: {username}[/bold green]",
            border_style="green",
        )
    )

    setup = get_keycloak_setup()

    # Prepare user data
    user_data = {
        "username": username,
        "email": email,
        "enabled": enabled,
        "emailVerified": email_verified,
        "credentials": [
            {
                "type": "password",
                "value": password,
                "temporary": temporary_password,
            }
        ],
    }

    if first_name:
        user_data["firstName"] = first_name
    if last_name:
        user_data["lastName"] = last_name

    try:
        success = setup.create_user(realm, user_data)

        if success:
            console.print(f"[green]✅ User '{username}' created successfully![/green]")
            console.print(f"[blue]Realm:[/blue] {realm}")
            console.print(f"[blue]Email:[/blue] {email}")
            console.print(f"[blue]Password:[/blue] {password}")
            if temporary_password:
                console.print("[yellow]⚠️  Password is temporary - user must change it on first login[/yellow]")
        else:
            console.print(f"[red]❌ Failed to create user '{username}'[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Failed to create user: {e}[/red]")
        raise typer.Exit(1) from None


@users_app.command("delete")
def delete_user(
    username: str = typer.Argument(..., help="Username of the user to delete"),
    realm: str = typer.Option("test-realm", help="Keycloak realm to delete user from"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """
    🗑️  Delete a user from a Keycloak realm.

    Permanently removes a user from the specified realm. This action cannot be undone.
    """
    setup = get_keycloak_setup()

    # Get user info first
    try:
        user = setup.get_user_by_username(realm, username)
        if not user:
            console.print(f"[red]❌ User '{username}' not found in realm '{realm}'[/red]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ Failed to find user: {e}[/red]")
        raise typer.Exit(1) from None

    # Show user info
    console.print(
        Panel.fit(
            f"[bold red]Delete User: {username}[/bold red]",
            border_style="red",
        )
    )

    console.print(f"[blue]Username:[/blue] {user.get('username', '')}")
    console.print(f"[blue]Email:[/blue] {user.get('email', '')}")
    console.print(f"[blue]Name:[/blue] {user.get('firstName', '')} {user.get('lastName', '')}")
    console.print(f"[blue]Realm:[/blue] {realm}")

    # Confirmation
    if not force:
        confirm = typer.confirm(
            f"\nAre you sure you want to delete user '{username}'? This cannot be undone."
        )
        if not confirm:
            console.print("[yellow]Operation cancelled[/yellow]")
            raise typer.Exit(0)

    try:
        success = setup.delete_user(realm, user["id"])

        if success:
            console.print(f"[green]✅ User '{username}' deleted successfully![/green]")
        else:
            console.print(f"[red]❌ Failed to delete user '{username}'[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Failed to delete user: {e}[/red]")
        raise typer.Exit(1) from None


@users_app.command("info")
def user_info(
    username: str = typer.Argument(..., help="Username to get information for"),
    realm: str = typer.Option("test-realm", help="Keycloak realm to search in"),
) -> None:
    """
    ℹ️  Show detailed information about a user.

    Displays comprehensive user information including profile, roles, and status.
    """
    console.print(
        Panel.fit(
            f"[bold cyan]User Information: {username}[/bold cyan]",
            border_style="cyan",
        )
    )

    setup = get_keycloak_setup()

    try:
        user = setup.get_user_by_username(realm, username)
        if not user:
            console.print(f"[red]❌ User '{username}' not found in realm '{realm}'[/red]")
            raise typer.Exit(1)

        # Basic information
        console.print("[bold]Basic Information:[/bold]")
        console.print(f"  Username: {user.get('username', 'N/A')}")
        console.print(f"  Email: {user.get('email', 'N/A')}")
        console.print(f"  First Name: {user.get('firstName', 'N/A')}")
        console.print(f"  Last Name: {user.get('lastName', 'N/A')}")
        console.print(f"  User ID: {user.get('id', 'N/A')}")

        # Status
        console.print("\n[bold]Status:[/bold]")
        enabled = "✅ Enabled" if user.get("enabled", False) else "❌ Disabled"
        email_verified = "✅ Verified" if user.get("emailVerified", False) else "❌ Not verified"
        console.print(f"  Account: {enabled}")
        console.print(f"  Email: {email_verified}")

        # Timestamps
        console.print("\n[bold]Timestamps:[/bold]")
        created_timestamp = user.get("createdTimestamp")
        if created_timestamp:
            import datetime
            created_date = datetime.datetime.fromtimestamp(created_timestamp / 1000)
            console.print(f"  Created: {created_date.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            console.print("  Created: N/A")

        # Attributes
        attributes = user.get("attributes", {})
        if attributes:
            console.print("\n[bold]Custom Attributes:[/bold]")
            for key, value in attributes.items():
                if isinstance(value, list):
                    value = ", ".join(value)
                console.print(f"  {key}: {value}")

        # Required actions
        required_actions = user.get("requiredActions", [])
        if required_actions:
            console.print("\n[bold]Required Actions:[/bold]")
            for action in required_actions:
                console.print(f"  • {action}")

    except Exception as e:
        console.print(f"[red]❌ Failed to get user information: {e}[/red]")
        raise typer.Exit(1) from None


@users_app.command("reset-password")
def reset_password(
    username: str = typer.Argument(..., help="Username to reset password for"),
    new_password: str = typer.Argument(..., help="New password for the user"),
    realm: str = typer.Option("test-realm", help="Keycloak realm"),
    temporary: bool = typer.Option(False, help="Whether the password is temporary"),
) -> None:
    """
    🔑 Reset a user's password.

    Changes the password for an existing user. Can be set as temporary to force
    the user to change it on next login.
    """
    console.print(
        Panel.fit(
            f"[bold yellow]Reset Password: {username}[/bold yellow]",
            border_style="yellow",
        )
    )

    setup = get_keycloak_setup()

    try:
        # Verify user exists first
        user = setup.get_user_by_username(realm, username)
        if not user:
            console.print(f"[red]❌ User '{username}' not found in realm '{realm}'[/red]")
            raise typer.Exit(1)

        success = setup.reset_user_password(realm, user["id"], new_password, temporary)

        if success:
            console.print(f"[green]✅ Password reset successfully for user '{username}'![/green]")
            if temporary:
                console.print("[yellow]⚠️  Password is temporary - user must change it on next login[/yellow]")
        else:
            console.print(f"[red]❌ Failed to reset password for user '{username}'[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]❌ Failed to reset password: {e}[/red]")
        raise typer.Exit(1) from None
