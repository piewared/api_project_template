#!/usr/bin/env python3
"""Post-generation hook to merge infrastructure with business logic."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def copy_infrastructure():
    """Copy infrastructure code from template's src/ to the generated project."""
    project_root = Path(".").absolute()
    package_name = "{{cookiecutter.package_name}}"
    project_slug = "{{cookiecutter.project_slug}}"
    template_path_str = "{{cookiecutter._template}}"

    print("🔧 Merging infrastructure with business logic...")
    print(f"📁 Template path: {template_path_str}")
    print(f"📁 Current directory: {project_root}")
    print(f"📁 Package name: {package_name}")

    # Key insight: When cookiecutter runs, the hook executes from within the temp directory
    # where the template was cloned. So the template's src should be accessible as ../src
    src_dir = None
    search_paths = []

    # Strategy 1: Check if this is a local template (direct path)
    if not template_path_str.startswith(("git@", "https://", "http://")):
        local_template = Path(template_path_str).resolve()
        if local_template.exists():
            potential_src = local_template / "src"
            if potential_src.exists():
                search_paths.append(potential_src)

    # Strategy 2: The most reliable approach for remote templates
    # When cookiecutter clones a remote template, it runs the hook from within the template directory
    # So ../src should be the template's src directory
    current_working_dir = Path(".").absolute()
    potential_locations = [
        # Direct parent (most common for cookiecutter)
        current_working_dir.parent / "src",
        # Sometimes cookiecutter creates nested structure
        current_working_dir.parent.parent / "src",
        # Check if we're already in a template-like structure
        current_working_dir / ".." / "src",
    ]

    for potential_src in potential_locations:
        try:
            resolved_path = potential_src.resolve()
            if resolved_path.exists() and resolved_path.is_dir():
                search_paths.append(resolved_path)
        except (OSError, RuntimeError):
            continue

    # Strategy 3: Look in parent directories systematically
    current = current_working_dir
    for level in range(4):  # Don't search too far up
        if level > 0:
            current = current.parent

        # Look for src directory directly
        potential_src = current / "src"
        if potential_src.exists():
            search_paths.append(potential_src)

        # Look for template-like directories that contain src
        try:
            for item in current.iterdir():
                if item.is_dir():
                    potential_src = item / "src"
                    if potential_src.exists():
                        search_paths.append(potential_src)
        except (PermissionError, OSError):
            continue

    print(f"🔍 Searching for template src directory...")
    print(f"   Found {len(search_paths)} potential locations")

    # Validate each potential src directory
    for i, potential_src in enumerate(search_paths):
        print(f"   [{i + 1}] Checking: {potential_src}")

        if not potential_src.exists() or not potential_src.is_dir():
            print("       ❌ Not a directory")
            continue

        # Verify this looks like our template by checking for required structure
        # Check for new src/app/ structure first
        app_dir = potential_src / "app"
        if app_dir.exists():
            required_dirs = ["api", "core", "runtime"]
            missing_dirs = [d for d in required_dirs if not (app_dir / d).exists()]
            
            if not missing_dirs:
                print("       ✅ Found new src/app/ structure")
                # Keep the src directory as our source to preserve folder structure
                # potential_src stays as the src directory
            else:
                print(f"       ❌ Missing required directories in app/: {missing_dirs}")
                continue
        else:
            # Fallback: check for old flat structure under src/
            required_dirs = ["api", "core", "runtime"]
            missing_dirs = [d for d in required_dirs if not (potential_src / d).exists()]
            
            if missing_dirs:
                print(f"       ❌ Missing required directories: {missing_dirs}")
                continue

        # Additional validation: check for key files
        if app_dir.exists():
            # New structure: files are under app/
            key_files = ["app/api/http/app.py", "app/runtime/db.py", "app/entities/__init__.py"]
        else:
            # Old structure: files are directly under src/
            key_files = ["api/http/app.py", "runtime/db.py", "entities/__init__.py"]
        
        missing_files = [f for f in key_files if not (potential_src / f).exists()]

        if missing_files:
            print(f"       ❌ Missing key files: {missing_files}")
            continue

        print("       ✅ Valid template src directory found!")
        src_dir = potential_src
        break

    if src_dir is None:
        print("❌ Infrastructure source directory not found!")
        print(
            "❌ This means the generated project will be missing core infrastructure."
        )
        print("❌ The project may not work correctly without manual setup.")
        print("⚠️  Possible solutions:")
        print("   1. Use a local template: cruft create /path/to/local/template")
        print("   2. Manual setup may be required")
        print("   3. Check cookiecutter/cruft version compatibility")
        print("   4. Ensure the template repository has the correct structure")
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

    # Copy and process configuration files from source
    # Get template path from the src directory we found
    template_root = src_dir.parent if src_dir else None
    if template_root:
        copy_config_files(template_root, project_root, package_name, project_slug)
    else:
        print("⚠️  Warning: Could not locate template root for config file copying")

    return True


def copy_config_files(template_path: Path, project_root: Path, package_name: str, project_slug: str):
    """Copy and process configuration files from the source project."""
    config_files = {
        "pyproject.toml": process_pyproject_toml,
        "README.md": process_readme,
        ".env.example": lambda content, **kwargs: content,  # Copy as-is
        ".gitignore": lambda content, **kwargs: content,    # Copy as-is
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
                    content, 
                    package_name=package_name, 
                    project_slug=project_slug
                )
                
                with open(target_file, "w") as f:
                    f.write(processed_content)
                
                print(f"🔧 Copied and processed {filename}")
            except Exception as e:
                print(f"⚠️  Warning: Could not process {filename}: {e}")
        else:
            print(f"⚠️  Warning: Source {filename} not found")


def process_pyproject_toml(content: str, package_name: str, project_slug: str, **kwargs) -> str:
    """Process pyproject.toml to replace project-specific placeholders."""
    # Replace the project name and dependencies
    processed = content.replace("api_project_template3", project_slug)
    processed = processed.replace('"src"', f'"{package_name}"')
    
    # Update entry points to use the generated package name
    # Handle both hatch build config and scripts
    processed = processed.replace("src.app.runtime.init_db:init_db", f"{package_name}.app.runtime.init_db:init_db")
    processed = processed.replace("src.dev.cli:main", f"{package_name}.dev.cli:main")
    processed = processed.replace("api-dev", f"{project_slug}-dev")
    
    # Also handle any remaining src. references in entry points
    import re
    # Replace patterns like "src.something = "package_name.something"
    processed = re.sub(r'([\"\']?)src\.', f'\\1{package_name}.', processed)
    
    return processed


def process_readme(content: str, package_name: str, project_slug: str, **kwargs) -> str:
    """Process README.md to replace project-specific placeholders."""
    # Replace project name references
    processed = content.replace("API Project Template", project_slug.replace("_", " ").title())
    processed = processed.replace("api_project_template3", project_slug)
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
            # Set environment to suppress UV warnings
            env = os.environ.copy()
            env.pop('VIRTUAL_ENV', None)  # Remove VIRTUAL_ENV to avoid mismatch warning
            env['UV_LINK_MODE'] = 'copy'  # Use copy mode to suppress hardlink warning
            
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
    print(f"   - Domain entities: {package_name}/app/entities/service/__init__.py")
    print(f"   - Business services: {package_name}/app/service/__init__.py")
    print(f"   - API routes: {package_name}/app/api/routers/business.py")
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
