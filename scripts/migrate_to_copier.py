#!/usr/bin/env python3
"""
Script to migrate from Cookiecutter to Copier template structure.

This handles:
1. Moving files from {{cookiecutter.project_slug}}/ to template root
2. Renaming {{cookiecutter.*}} to {{ * }} in files
3. Updating file/directory names
"""

import os
import shutil
from pathlib import Path
import re

def migrate_template_syntax(content: str) -> str:
    """Convert cookiecutter syntax to copier syntax."""
    # Replace {{cookiecutter.variable}} with {{ variable }}
    content = re.sub(
        r'\{\{\s*cookiecutter\.([a-z_]+)\s*\}\}',
        r'{{ \1 }}',
        content,
        flags=re.IGNORECASE
    )
    
    # Replace {%cookiecutter.variable%} with {% variable %}  
    content = re.sub(
        r'\{%\s*cookiecutter\.([a-z_]+)\s*%\}',
        r'{% \1 %}',
        content,
        flags=re.IGNORECASE
    )
    
    return content

def should_process_file(filepath: Path) -> bool:
    """Check if file should be processed for syntax migration."""
    # Skip binary files and certain directories
    skip_patterns = [
        '.git', '__pycache__', '.pytest_cache', '.mypy_cache',
        '.ruff_cache', 'node_modules', '.venv', 'venv',
        '.db', '.pyc', '.pyo', '.so', '.dylib', '.dll',
        'uv.lock', '.png', '.jpg', '.jpeg', '.gif', '.pdf',
        '_infrastructure'  # We'll handle this separately
    ]
    
    filepath_str = str(filepath)
    for pattern in skip_patterns:
        if pattern in filepath_str:
            return False
    
    # Only process text files
    text_extensions = {
        '.py', '.md', '.txt', '.yml', '.yaml', '.json', '.toml',
        '.sh', '.bash', '.env', '.example', '.j2', '.jinja',
        '.html', '.css', '.js', '.ts', '.jsx', '.tsx'
    }
    
    return filepath.suffix in text_extensions or filepath.name in [
        'Dockerfile', 'Makefile', 'README', 'LICENSE', '.gitignore'
    ]

def migrate_file(src, dest):
    """Migrate a single file from cookiecutter to copier syntax."""
    # Convert to Path objects if strings
    src_path = Path(src) if isinstance(src, str) else src
    dest_path = Path(dest) if isinstance(dest, str) else dest
    
    if not should_process_file(src_path):
        # Just copy binary/non-text files
        shutil.copy2(src, dest)
        return
    
    try:
        with open(src, encoding='utf-8') as f:
            content = f.read()
        
        # Migrate syntax
        content = migrate_template_syntax(content)
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Preserve permissions
        shutil.copystat(src, dest)
        
    except UnicodeDecodeError:
        # Fall back to binary copy if not actually a text file
        shutil.copy2(src, dest)

def main():
    template_root = Path(__file__).parent.parent
    source_dir = template_root / "{{cookiecutter.project_slug}}"
    
    if not source_dir.exists():
        print("✅ Migration already completed or source directory not found")
        return
    
    print(f"🔄 Migrating template from {source_dir} to {template_root}")
    print(f"   This will update Cookiecutter syntax to Copier syntax")
    
    # Get list of items to migrate (excluding _infrastructure which stays bundled)
    items_to_migrate = []
    for item in source_dir.iterdir():
        if item.name == '_infrastructure':
            print(f"   ⏭️  Skipping _infrastructure (stays bundled)")
            continue
        items_to_migrate.append(item)
    
    # Migrate each item
    for item in items_to_migrate:
        dest = template_root / item.name
        
        # Handle template variable names in paths
        dest_name = migrate_template_syntax(item.name)
        dest = template_root / dest_name
        
        if item.is_dir():
            print(f"   📁 Migrating directory: {item.name}")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest, copy_function=migrate_file)
        else:
            print(f"   📄 Migrating file: {item.name}")
            if dest.exists():
                dest.unlink()
            migrate_file(item, dest)
    
    print(f"\n✅ Migration complete!")
    print(f"   Files migrated to template root")
    print(f"   {{{{cookiecutter.*}}}} → {{{{ * }}}}")
    print(f"\n⚠️  Note: Review the migrated files for any issues")
    print(f"   Especially check files with complex Jinja2 logic")

if __name__ == "__main__":
    main()
