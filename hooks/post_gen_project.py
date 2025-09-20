#!/usr/bin/env python3
"""Post-generation hook to merge infrastructure with business logic."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def copy_infrastructure():
    """Copy infrastructure code from template's src/ to the generated project."""
    # When cookiecutter runs, it sets the template path in an environment variable
    # or we can use the _template variable from cookiecutter context
    template_root = Path("{{cookiecutter._template}}").resolve()
    src_dir = template_root / "src"
    project_root = Path(".").absolute()
    package_name = "{{cookiecutter.package_name}}"

    print("🔧 Merging infrastructure with business logic...")
    print(f"📁 Template root: {template_root}")
    print(f"📁 Looking for src at: {src_dir}")

    if not src_dir.exists():
        print("❌ Infrastructure source directory not found!")
        print(f"❌ Expected location: {src_dir}")
        return False

    # Copy all infrastructure code to the package
    package_dir = project_root / package_name
    package_dir.mkdir(exist_ok=True)

    for item in src_dir.iterdir():
        target = package_dir / item.name
        if item.is_dir():
            if target.exists():
                # Merge directories (business logic takes precedence)
                merge_directories(item, target)
            else:
                # Copy new directory
                shutil.copytree(item, target)
        else:
            if not target.exists():  # Don't overwrite business files
                shutil.copy2(item, target)

    # Fix imports in the copied files
    fix_imports_in_directory(package_dir, package_name)

    print("✅ Infrastructure and business logic merged successfully!")
    return True


def fix_imports_in_directory(directory: Path, package_name: str):
    """Fix src. imports to use the actual package name."""
    for py_file in directory.rglob("*.py"):
        with open(py_file, "r") as f:
            content = f.read()

        # Replace src. imports with the actual package name
        updated_content = content.replace("from src.", f"from {package_name}.")
        updated_content = updated_content.replace(
            "import src.", f"import {package_name}."
        )

        if content != updated_content:
            with open(py_file, "w") as f:
                f.write(updated_content)
            print(f"🔧 Fixed imports in {py_file.relative_to(directory)}")


def merge_directories(src_dir, target_dir):
    """Recursively merge directories, with target taking precedence."""
    for item in src_dir.iterdir():
        target_item = target_dir / item.name
        if item.is_dir():
            if target_item.exists():
                merge_directories(item, target_item)
            else:
                shutil.copytree(item, target_item)
        else:
            if not target_item.exists():  # Don't overwrite existing files
                shutil.copy2(item, target_item)


def update_main_app():
    """Update the main app to include business routes."""
    package_name = "{{cookiecutter.package_name}}"
    main_app_path = Path(package_name) / "api" / "http" / "app.py"

    if not main_app_path.exists():
        print("⚠️  Main app file not found, skipping router integration")
        return

    # Read the current app.py
    with open(main_app_path, "r") as f:
        content = f.read()

    # Add business router import and inclusion
    business_import = f"from {package_name}.api.routers import business"
    business_include = "app.include_router(business.router)"

    # Insert import and router inclusion if not already present
    if business_import not in content:
        lines = content.split("\n")

        # Find the last import line that's not inside a function
        import_line_idx = 0
        in_function = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Track if we're inside a function
            if stripped.startswith("def ") or stripped.startswith("async def "):
                in_function = True
            elif stripped == "" and not in_function:
                # Empty line outside function could mark end of imports
                continue
            elif not in_function and (
                stripped.startswith("from ") or stripped.startswith("import ")
            ):
                import_line_idx = i
            elif stripped and not stripped.startswith("#") and not in_function:
                # Found non-import, non-comment line outside function
                break

        # Insert the business import after the last import
        lines.insert(import_line_idx + 1, business_import)

        # Find where to add the router (after app creation but before any endpoint definitions)
        app_creation_line = None
        for i, line in enumerate(lines):
            if "app = FastAPI(" in line:
                # Find the end of the FastAPI constructor
                bracket_count = 0
                for j in range(i, len(lines)):
                    bracket_count += lines[j].count("(") - lines[j].count(")")
                    if bracket_count == 0:
                        app_creation_line = j
                        break
                break

        if app_creation_line:
            # Look for an appropriate place to insert the router
            insert_line = app_creation_line + 1

            # Skip any immediate configuration or middleware setup
            for j in range(app_creation_line + 1, len(lines)):
                line = lines[j].strip()
                if line == "" or line.startswith("#"):
                    continue
                elif (
                    "app.add_middleware" in line
                    or "app.state" in line
                    or "@app." in line
                ):
                    insert_line = j + 1
                else:
                    break

            lines.insert(insert_line, "")
            lines.insert(insert_line + 1, "# Include business routers")
            lines.insert(insert_line + 2, business_include)

        # Write back
        with open(main_app_path, "w") as f:
            f.write("\n".join(lines))

        print("✅ Business routes integrated into main app!")


def remove_conditional_files():
    """Remove files based on cookiecutter options."""
    use_redis = "{{cookiecutter.use_redis}}" == "y"
    use_postgres = "{{cookiecutter.use_postgres}}" == "y"
    include_examples = "{{cookiecutter.include_example_routes}}" == "y"

    # Remove Redis-related files if not using Redis
    if not use_redis:
        files_to_remove = [
            # Add any Redis-specific files here if they exist
        ]
        for file_path in files_to_remove:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️  Removed {file_path} (Redis not selected)")

    # Remove PostgreSQL-related files if not using PostgreSQL
    if not use_postgres:
        files_to_remove = [
            # Add any PostgreSQL-specific files here if they exist
        ]
        for file_path in files_to_remove:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️  Removed {file_path} (PostgreSQL not selected)")

    # Remove example routes if not wanted
    if not include_examples:
        package_name = "{{cookiecutter.package_name}}"
        example_files = [f"{package_name}/api/routers/business.py"]
        for file_path in example_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️  Removed {file_path} (example routes not selected)")


def setup_cruft_tracking():
    """Set up Cruft tracking with the current template commit."""
    template_url = "{{cookiecutter._template}}"

    # Try to get the current git commit SHA from the template
    try:
        # This assumes the template is in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd="..",  # Go up one directory to the template root
        )
        commit_sha = result.stdout.strip()

        # Update .cruft.json with the actual commit SHA
        cruft_file = Path(".cruft.json")
        if cruft_file.exists():
            content = cruft_file.read_text()
            content = content.replace("TEMPLATE_COMMIT_SHA", commit_sha)
            cruft_file.write_text(content)
            print(f"✅ Set up Cruft tracking (commit: {commit_sha[:8]})")

    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Could not determine template commit SHA")
        print("You may need to manually update .cruft.json with the correct commit")


def setup_git_repository():
    """Initialize git repository and make initial commit."""
    try:
        # Initialize git repository
        subprocess.run(["git", "init"], check=True, capture_output=True)
        print("📦 Initialized git repository")

        # Add all files
        subprocess.run(["git", "add", "."], check=True, capture_output=True)

        # Make initial commit
        commit_message = "Initial commit from FastAPI Hexagonal Template"
        subprocess.run(
            ["git", "commit", "-m", commit_message], check=True, capture_output=True
        )
        print("✅ Made initial git commit")

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Git setup failed: {e}")
        print("You can initialize git manually later with:")
        print("  git init")
        print("  git add .")
        print("  git commit -m 'Initial commit'")
    except FileNotFoundError:
        print("⚠️  Git not found. Skipping git repository setup.")
        print("Install git to enable automatic repository initialization.")


def create_virtual_environment():
    """Create Python virtual environment and install dependencies."""
    project_slug = "{{cookiecutter.project_slug}}"
    python_version = "{{cookiecutter.python_version}}"

    print(f"🐍 Setting up Python {python_version} environment...")

    # Check if uv is available (preferred)
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        print("📦 Using uv for dependency management")
        try:
            subprocess.run(["uv", "sync"], check=True)
            print("✅ Dependencies installed with uv")
            return
        except subprocess.CalledProcessError as e:
            print(f"⚠️  uv sync failed: {e}")
            print("You can install dependencies later with: uv sync")

    except (subprocess.CalledProcessError, FileNotFoundError):
        print("📦 uv not found, using standard Python tools")

    # Fallback to standard Python virtual environment
    try:
        venv_path = Path(".venv")
        if not venv_path.exists():
            subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
            print("✅ Created virtual environment")

        # Determine pip path
        if sys.platform == "win32":
            pip_path = venv_path / "Scripts" / "pip"
        else:
            pip_path = venv_path / "bin" / "pip"

        # Install dependencies
        subprocess.run([str(pip_path), "install", "-e", "."], check=True)
        print("✅ Dependencies installed")

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Virtual environment setup failed: {e}")
        print("You can set up the environment manually:")
        print("  python -m venv .venv")
        print("  source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate")
        print("  pip install -e .")


def print_next_steps():
    """Print helpful next steps for the user."""
    project_name = "{{cookiecutter.project_name}}"
    project_slug = "{{cookiecutter.project_slug}}"
    package_name = "{{cookiecutter.package_name}}"
    use_redis = "{{cookiecutter.use_redis}}" == "y"

    print("\n" + "=" * 60)
    print(f"🎉 {project_name} has been created successfully!")
    print("=" * 60)

    print(f"\n📁 Project location: ./{project_slug}")

    print(f"\n🚀 Next steps:")
    print(f"   1. cd {project_slug}")
    print("   2. Copy .env.example to .env and configure your settings")
    print("   3. Run 'uv run init-db' to initialize the database")
    print("   4. Start development server: 'uvicorn main:app --reload'")

    if use_redis:
        print("\n🔧 Redis configuration:")
        print("   - Install Redis locally or use a cloud service")
        print("   - Update REDIS_URL in your .env file")
        print("   - Without Redis, the app will use in-memory rate limiting")

    print(f"\n📚 Development commands:")
    print("   - Run tests: pytest")
    print("   - Type checking: mypy .")
    print("   - Linting: ruff check .")
    print("   - Format code: ruff format .")

    print(f"\n🏗️  Add your domain logic:")
    print(f"   - Business entities: {package_name}/business/entities.py")
    print(f"   - Business services: {package_name}/business/services.py")
    print(f"   - API routes: {package_name}/api/routers/business.py")
    print(f"   - Tests: tests/")

    print("\n📖 Template updates:")
    print("   - Check for updates: cruft check")
    print("   - Apply updates: cruft update")
    print("   - More info: https://cruft.github.io/cruft/")

    print("\n📖 Documentation: Check README.md for detailed usage")
    print("=" * 60)


def main():
    """Run post-generation setup."""
    print("🔧 Setting up your new project...")

    try:
        # Copy infrastructure and merge with business logic
        if not copy_infrastructure():
            print("❌ Failed to copy infrastructure")
            sys.exit(1)

        # Update main app to include business routes
        update_main_app()

        # Clean up conditional files
        remove_conditional_files()

        # Set up Cruft tracking
        setup_cruft_tracking()

        # Set up git repository
        setup_git_repository()

        # Set up Python environment
        create_virtual_environment()

        # Print next steps
        print_next_steps()

    except Exception as e:
        print(f"❌ Setup error: {e}")
        print("The project was created but some setup steps failed.")
        print("Check the README.md for manual setup instructions.")
        sys.exit(1)


if __name__ == "__main__":
    main()
