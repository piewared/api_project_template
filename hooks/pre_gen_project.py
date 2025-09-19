#!/usr/bin/env python3
"""Pre-generation hook for cookiecutter template validation."""

import re
import sys


def validate_project_name(project_name: str) -> None:
    """Validate that the project name is reasonable."""
    if not project_name:
        print("ERROR: project_name cannot be empty!")
        sys.exit(1)
    
    if len(project_name) > 100:
        print("ERROR: project_name is too long (max 100 characters)")
        sys.exit(1)


def validate_project_slug(project_slug: str) -> None:
    """Validate that the project slug is a valid Python package name."""
    if not re.match(r'^[a-z][a-z0-9_]*$', project_slug):
        print(f"ERROR: '{project_slug}' is not a valid Python package name!")
        print("Project slug must:")
        print("- Start with a lowercase letter")
        print("- Contain only lowercase letters, numbers, and underscores")
        print("- Not start with a number")
        sys.exit(1)
    
    # Check for Python reserved words
    reserved_words = {
        'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 
        'elif', 'else', 'except', 'exec', 'finally', 'for', 'from', 'global', 
        'if', 'import', 'in', 'is', 'lambda', 'not', 'or', 'pass', 'print', 
        'raise', 'return', 'try', 'while', 'with', 'yield', 'async', 'await',
        'True', 'False', 'None'
    }
    
    if project_slug in reserved_words:
        print(f"ERROR: '{project_slug}' is a Python reserved word!")
        sys.exit(1)


def validate_package_name(package_name: str) -> None:
    """Validate that the package name is a valid Python package name."""
    if package_name != package_name.lower():
        print(f"ERROR: package_name '{package_name}' must be lowercase!")
        sys.exit(1)
    
    validate_project_slug(package_name)


def validate_python_version(python_version: str) -> None:
    """Validate that the Python version is supported."""
    if not re.match(r'^\d+\.\d+$', python_version):
        print(f"ERROR: Invalid Python version format '{python_version}'")
        print("Use format like '3.11' or '3.12'")
        sys.exit(1)
    
    major, minor = map(int, python_version.split('.'))
    if major != 3 or minor < 10:
        print(f"ERROR: Python {python_version} is not supported!")
        print("Minimum supported version is Python 3.10")
        sys.exit(1)


def validate_email(email: str) -> None:
    """Validate email format."""
    if not email:
        return  # Email is optional
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        print(f"ERROR: Invalid email format '{email}'")
        sys.exit(1)


def main():
    """Run all validations."""
    # Import cookiecutter context
    project_name = "{{cookiecutter.project_name}}"
    project_slug = "{{cookiecutter.project_slug}}"
    package_name = "{{cookiecutter.package_name}}"
    python_version = "{{cookiecutter.python_version}}"
    author_email = "{{cookiecutter.author_email}}"
    
    print(f"🔍 Validating cookiecutter inputs...")
    print(f"   Project: {project_name}")
    print(f"   Slug: {project_slug}")
    print(f"   Package: {package_name}")
    print(f"   Python: {python_version}")
    
    try:
        validate_project_name(project_name)
        validate_project_slug(project_slug)
        validate_package_name(package_name)
        validate_python_version(python_version)
        validate_email(author_email)
        
        print("✅ All validations passed!")
        
    except Exception as e:
        print(f"❌ Validation error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()