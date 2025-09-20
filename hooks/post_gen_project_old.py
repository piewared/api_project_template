#!/usr/bin/env python3
"""Post-generation hook for cookiecutter template setup."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


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
        example_files = [
            # Add paths to example files that should be removed
        ]
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
            cwd=".."  # Go up one directory to the template root
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
            ["git", "commit", "-m", commit_message], 
            check=True, 
            capture_output=True
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
    
    print("\n" + "="*60)
    print(f"🎉 {project_name} has been created successfully!")
    print("="*60)
    
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
    print(f"   - Core entities: {package_name}/core/entities/")
    print(f"   - Repository interfaces: {package_name}/core/repositories/")
    print(f"   - API routes: {package_name}/api/http/routers/")
    print(f"   - Database models: {package_name}/application/rows/")
    
    print(f"\n📖 Template updates:")
    print("   - Check for updates: cruft check")
    print("   - Apply updates: cruft update")
    print("   - More info: https://cruft.github.io/cruft/")
    
    print(f"\n📖 Documentation: Check README.md for detailed usage")
    print("="*60)


def main():
    """Run post-generation setup."""
    print("🔧 Setting up your new project...")
    
    try:
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