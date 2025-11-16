#!/usr/bin/env python3
"""Post-generation hook to merge infrastructure with business logic."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def copy_infrastructure():
    """Copy infrastructure files from bundled _infrastructure directory."""
    project_root = Path.cwd()
    package_name = "{{cookiecutter.package_name}}"
    project_slug = "{{cookiecutter.project_slug}}"
    infra_dir = project_root / "_infrastructure"

    print("🔧 Copying infrastructure files to project root...")
    print(f"📁 Project directory: {project_root}")
    print(f"📁 Package name: {package_name}")

    # Check if bundled infrastructure exists
    if not infra_dir.exists():
        print("❌ Bundled infrastructure directory not found!")
        print("❌ This means the template was not properly synced.")
        print("❌ Template maintainers: Please run ./scripts/sync_to_template.sh")
        return False

    print(f"📦 Found bundled infrastructure at: {infra_dir}")

    # Items to copy from _infrastructure to project root (directories and non-config files)
    directory_items = ["k8s", "infra", "examples", "docs", "tests"]
    other_files = [
        "docker-compose.dev.yml",
        "docker-compose.prod.yml",
        "Dockerfile",
        "dev.sh",
    ]

    copied_count = 0
    
    # Copy directories
    for item_name in directory_items:
        source = infra_dir / item_name
        target = project_root / item_name

        if not source.exists():
            print(f"⚠️  Skipping {item_name} (not found in bundled infrastructure)")
            continue

        try:
            print(f"📁 Copying {item_name}/")
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
            copied_count += 1
        except Exception as e:
            print(f"❌ Failed to copy {item_name}: {e}")
    
    # Copy src directory to package_name
    src_source = infra_dir / "src"
    if src_source.exists():
        try:
            target = project_root / package_name
            print(f"📁 Copying src/ → {package_name}/")
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src_source, target)
            copied_count += 1
            
            # Fix imports in the package directory
            fix_imports_in_directory(target, package_name)
            print(f"✅ Fixed imports in {package_name}/")
        except Exception as e:
            print(f"❌ Failed to copy src: {e}")
    
    # Copy other files (non-config)
    for item_name in other_files:
        source = infra_dir / item_name
        target = project_root / item_name

        if not source.exists():
            continue

        try:
            print(f"📄 Copying {item_name}")
            if target.exists():
                target.unlink()
            shutil.copy2(source, target)
            copied_count += 1
        except Exception as e:
            print(f"❌ Failed to copy {item_name}: {e}")

    print(f"✅ Copied {copied_count} infrastructure items")

    # Process configuration files with template variables (before cleaning up infra_dir)
    copy_config_files(infra_dir, project_root, package_name, project_slug)

    # Clean up the bundled infrastructure directory
    print("🧹 Cleaning up bundled infrastructure...")
    try:
        shutil.rmtree(infra_dir)
        print("✅ Removed _infrastructure/ directory")
    except Exception as e:
        print(f"⚠️  Warning: Could not remove _infrastructure/: {e}")

    return True


def copy_config_files(
    template_path: Path, project_root: Path, package_name: str, project_slug: str
):
    """Copy and process configuration files from the source project."""
    config_files = {
        "pyproject.toml": process_pyproject_toml,
        "README.md": process_readme,
        "config.yaml": lambda content, **kwargs: content,  # Copy as-is
        ".env.example": lambda content, **kwargs: content,  # Copy as-is
        ".gitignore": lambda content, **kwargs: content,  # Copy as-is
    }

    for filename, processor in config_files.items():
        source_file = template_path / filename
        target_file = project_root / filename

        if source_file.exists():
            try:
                with open(source_file) as f:
                    content = f.read()

                # Process the content with placeholders
                processed_content = processor(
                    content, package_name=package_name, project_slug=project_slug
                )

                with open(target_file, "w") as f:
                    f.write(processed_content)

                print(f"🔧 Copied and processed {filename}")
            except Exception as e:
                print(f"⚠️  Warning: Could not process {filename}: {e}")
        else:
            print(f"⚠️  Warning: Source {filename} not found")


def process_pyproject_toml(
    content: str, package_name: str, project_slug: str, **kwargs
) -> str:
    """Process pyproject.toml to replace project-specific placeholders."""
    # Replace the project name and dependencies
    processed = content.replace("api-forge", project_slug)
    processed = processed.replace('"src"', f'"{package_name}"')

    # Update entry points to use the generated package name
    # Handle both hatch build config and scripts
    processed = processed.replace(
        "src.app.runtime.init_db:init_db", f"{package_name}.app.runtime.init_db:init_db"
    )
    processed = processed.replace("src.dev.cli:main", f"{package_name}.dev.cli:main")
    processed = processed.replace("api-dev", f"{project_slug}-dev")

    # Also handle any remaining src. references in entry points
    import re

    # Replace patterns like "src.something = "package_name.something"
    processed = re.sub(r"([\"\']?)src\.", f"\\1{package_name}.", processed)

    return processed


def process_readme(content: str, package_name: str, project_slug: str, **kwargs) -> str:
    """Process README.md to replace project-specific placeholders."""
    # Replace project name references
    processed = content.replace(
        "API Project Template", project_slug.replace("_", " ").title()
    )
    processed = processed.replace("api-forge", project_slug)
    processed = processed.replace("src/", f"{package_name}/")
    processed = processed.replace("api-dev", f"{project_slug}-dev")
    processed = processed.replace("uv run api-dev", f"uv run {project_slug}-dev")

    return processed


def fix_imports_in_directory(directory: Path, package_name: str):
    """Fix src. imports to use the actual package name."""
    for py_file in directory.rglob("*.py"):
        with open(py_file) as f:
            content = f.read()

        # Replace src.app. imports with the actual package name (new structure)
        updated_content = content.replace("from src.app.", f"from {package_name}.app.")
        updated_content = updated_content.replace(
            "import src.app.", f"import {package_name}.app."
        )

        # Also handle any remaining old-style src. imports for backward compatibility
        updated_content = updated_content.replace("from src.", f"from {package_name}.")
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
    python_version = "{{cookiecutter.python_version}}"

    print(f"🐍 Setting up Python {python_version} environment...")

    # Check if uv is available (preferred)
    try:
        subprocess.run(["uv", "--version"], check=True, capture_output=True)
        print("📦 Using uv for dependency management")
        try:
            # Set environment to suppress UV warnings
            env = os.environ.copy()
            env.pop("VIRTUAL_ENV", None)  # Remove VIRTUAL_ENV to avoid mismatch warning
            env["UV_LINK_MODE"] = "copy"  # Use copy mode to suppress hardlink warning

            subprocess.run(["uv", "sync"], check=True, env=env)
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


def copy_development_environment():
    """Copy development environment configuration and setup Keycloak."""
    project_root = Path(".").absolute()

    # Get the template root directory
    template_path_str = "{{cookiecutter._template}}"

    # Find the template dev_env directory
    dev_env_src = None
    search_paths = []

    # Strategy 1: Check if this is a local template (direct path)
    if not template_path_str.startswith(("git@", "https://", "http://")):
        local_template = Path(template_path_str).resolve()
        if local_template.exists():
            potential_dev_env = local_template / "dev_env"
            if potential_dev_env.exists():
                search_paths.append(potential_dev_env)

    # Strategy 2: Look in parent directories (most common for cookiecutter)
    current_working_dir = Path(".").absolute()
    potential_locations = [
        current_working_dir.parent / "dev_env",
        current_working_dir.parent.parent / "dev_env",
        current_working_dir / ".." / "dev_env",
    ]

    for potential_dev_env in potential_locations:
        try:
            resolved_path = potential_dev_env.resolve()
            if resolved_path.exists() and resolved_path.is_dir():
                search_paths.append(resolved_path)
        except (OSError, RuntimeError):
            continue

    print("🔍 Looking for development environment configuration...")

    # Validate each potential dev_env directory
    for potential_dev_env in search_paths:
        if not potential_dev_env.exists():
            continue

        # Check for required dev environment files
        required_files = ["keycloak/docker-compose.yml", "setup_dev.sh"]
        missing_files = [
            f for f in required_files if not (potential_dev_env / f).exists()
        ]

        if not missing_files:
            print(f"   ✅ Found development environment at: {potential_dev_env}")
            dev_env_src = potential_dev_env
            break

    if dev_env_src is None:
        print("⚠️  Development environment configuration not found")
        print("   You'll need to set up Keycloak manually for OIDC testing")
        return False

    # Copy development environment to the project
    dev_env_target = project_root / "dev_env"
    if dev_env_target.exists():
        shutil.rmtree(dev_env_target)

    shutil.copytree(dev_env_src, dev_env_target)
    print("✅ Copied development environment configuration")

    # Also copy the setup_keycloak.py script to make it accessible
    setup_keycloak_src = dev_env_src.parent / "src" / "dev" / "setup_keycloak.py"
    if setup_keycloak_src.exists():
        # Create src/dev directory in generated project if it doesn't exist
        dev_dir = project_root / "src" / "dev"
        dev_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(setup_keycloak_src, dev_dir / "setup_keycloak.py")
        print("✅ Copied Keycloak setup script")

    return True


def setup_keycloak_development():
    """Set up Keycloak for development if the environment configuration exists."""
    project_root = Path(".").absolute()
    dev_env_dir = project_root / "dev_env"

    if not dev_env_dir.exists():
        print("⚠️  Development environment not set up, skipping Keycloak configuration")
        return

    print("🔐 Setting up Keycloak development environment...")

    try:
        # Check if Docker is available
        subprocess.run(["docker", "--version"], check=True, capture_output=True)

        # Run the development environment setup
        setup_script = dev_env_dir / "setup_dev.sh"
        if setup_script.exists():
            # Make the script executable
            setup_script.chmod(0o755)

            print("🚀 Starting Keycloak and configuring OIDC...")
            result = subprocess.run(
                [str(setup_script)],
                cwd=str(dev_env_dir),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            if result.returncode == 0:
                print("✅ Keycloak development environment ready!")
                print("   Access Keycloak Admin: http://localhost:8080 (admin/admin)")
            else:
                print("⚠️  Keycloak setup completed with warnings:")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)

        else:
            print("⚠️  Development setup script not found")
            print("   You can manually run: cd dev_env && ./setup_dev.sh")

    except subprocess.TimeoutExpired:
        print("⏰ Keycloak setup timed out (this can happen on slower systems)")
        print("   The setup may still be running in the background")
        print("   Check with: docker ps")

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Keycloak setup failed: {e}")
        print("   You can manually run: cd dev_env && ./setup_dev.sh")

    except FileNotFoundError:
        print("⚠️  Docker not found. Keycloak setup requires Docker")
        print("   Install Docker and run: cd dev_env && ./setup_dev.sh")


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

    print("\n🚀 Next steps:")
    print(f"   1. cd {project_slug}")
    print("   2. Copy .env.example to .env and configure your settings")
    print("   3. Run 'uv run init-db' to initialize the database")
    print("   4. Start development server: 'uvicorn main:app --reload'")

    print("\n🔐 OIDC/Keycloak Development:")
    print("   - Keycloak Admin: http://localhost:8080 (admin/admin)")
    print("   - If Keycloak setup failed, run: cd dev_env && ./setup_dev.sh")
    print("   - Test users: testuser1/password123, testuser2/password123")

    if use_redis:
        print("\n🔧 Redis configuration:")
        print("   - Install Redis locally or use a cloud service")
        print("   - Update REDIS_URL in your .env file")
        print("   - Without Redis, the app will use in-memory rate limiting")

    print("\n📚 Development commands:")
    print("   - Run tests: pytest")
    print("   - Type checking: mypy .")
    print("   - Linting: ruff check .")
    print("   - Format code: ruff format .")

    print("\n🏗️  Add your domain logic:")
    print(f"   - Domain entities: {package_name}/app/entities/service/__init__.py")
    print(f"   - Business services: {package_name}/app/service/__init__.py")
    print(f"   - API routes: {package_name}/app/api/routers/business.py")
    print("   - Tests: tests/")

    print("\n📖 Template updates:")
    print("   - Check for updates: cruft check")
    print("   - Apply updates: cruft update")
    print("   - More info: https://cruft.github.io/cruft/")

    print("\n📖 Documentation: Check README.md for detailed usage")
    print("=" * 60)


def main():
    """Run post-generation setup."""
    print("🔧 Setting up your new project...")
    print("🎯 MARKER: Using updated post_gen_project.py file!")

    try:
        # Copy infrastructure and merge with business logic
        print("📦 Step 1: Copying infrastructure...")
        if not copy_infrastructure():
            print("❌ Failed to copy infrastructure")
            sys.exit(1)

        # Update main app to include business routes
        print("📝 Step 2: Updating main app...")
        update_main_app()

        # Clean up conditional files
        print("🧹 Step 3: Cleaning up conditional files...")
        remove_conditional_files()

        # Set up Cruft tracking
        print("📌 Step 4: Setting up Cruft tracking...")
        setup_cruft_tracking()

        # Set up git repository
        print("🎯 Step 5: Setting up git repository...")
        setup_git_repository()

        # Set up Python environment
        print("🐍 Step 6: Setting up Python environment...")
        create_virtual_environment()

        # Copy development environment configuration
        print("🔧 Step 7: Copying development environment...")
        copy_development_environment()

        # Print next steps
        print_next_steps()

    except Exception as e:
        import traceback
        print(f"❌ Setup error: {e}")
        print("Traceback:")
        traceback.print_exc()
        print("The project was created but some setup steps failed.")
        print("Check the README.md for manual setup instructions.")
        sys.exit(1)


if __name__ == "__main__":
    main()
