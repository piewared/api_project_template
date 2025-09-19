"""Tests for the template generation process itself."""

import tempfile
import subprocess
import pytest
from pathlib import Path


def test_template_generation():
    """Test that the template generates successfully."""
    template_path = Path(__file__).parent.parent
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Generate a project
        result = subprocess.run([
            "cookiecutter", 
            str(template_path),
            "--no-input",
            "--output-dir", temp_dir
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Template generation failed: {result.stderr}"
        
        # Check that expected files exist
        project_dir = Path(temp_dir) / "my_api_project"
        assert project_dir.exists()
        assert (project_dir / "main.py").exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "tests").exists()


def test_generated_project_tests():
    """Test that generated project tests pass."""
    template_path = Path(__file__).parent.parent
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Generate a project
        subprocess.run([
            "cookiecutter", 
            str(template_path),
            "--no-input", 
            "--output-dir", temp_dir
        ], check=True)
        
        project_dir = Path(temp_dir) / "my_api_project"
        
        # Run tests in the generated project
        result = subprocess.run([
            "uv", "run", "pytest", "-v"
        ], cwd=project_dir, capture_output=True, text=True)
        
        assert result.returncode == 0, f"Generated project tests failed: {result.stdout}\n{result.stderr}"


def test_template_variables_replaced():
    """Test that template variables are properly replaced."""
    template_path = Path(__file__).parent.parent
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Generate with custom values
        subprocess.run([
            "cookiecutter", 
            str(template_path),
            "--no-input",
            "--output-dir", temp_dir,
            "project_name=Test Project",
            "package_name=test_project"
        ], check=True)
        
        project_dir = Path(temp_dir) / "test_project"
        main_py = (project_dir / "main.py").read_text()
        
        # Check that variables were replaced
        assert "test_project.api.http.app" in main_py
        assert "{{cookiecutter" not in main_py