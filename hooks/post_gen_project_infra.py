#!/usr/bin/env python3
"""Post-generation hook to merge infrastructure code with business templates."""

import shutil
from pathlib import Path


def copy_infrastructure():
    """Copy infrastructure code from src/ to the generated project."""
    template_root = Path(__file__).parent.parent
    src_dir = template_root / "src"
    project_root = Path(".")
    package_name = "{{cookiecutter.package_name}}"

    print("🔧 Merging infrastructure with business logic...")

    # Copy infrastructure code
    for item in src_dir.iterdir():
        if item.is_dir():
            target = project_root / package_name / item.name
            if target.exists():
                # Merge directories
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                # Copy new directory
                shutil.copytree(item, target)
        else:
            # Copy files
            shutil.copy2(item, project_root / package_name / item.name)

    # Copy business templates to the right location
    business_template_dir = template_root / "business_template" / package_name
    if business_template_dir.exists():
        shutil.copytree(
            business_template_dir, project_root / package_name, dirs_exist_ok=True
        )

    print("✅ Infrastructure and business logic merged successfully!")


def update_main_app():
    """Update the main app to include business routes."""
    main_app_path = Path("{{cookiecutter.package_name}}") / "api" / "http" / "app.py"

    if main_app_path.exists():
        # Read the current app.py
        with open(main_app_path) as f:
            content = f.read()

        # Add business router import and inclusion
        business_import = (
            "from {{cookiecutter.package_name}}.api.routers import business"
        )
        business_include = "app.include_router(business.router)"

        # Insert import after other imports
        if business_import not in content:
            # Find the last import line
            lines = content.split("\n")
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip().startswith("from ") or line.strip().startswith(
                    "import "
                ):
                    import_end = i

            # Insert the business import
            lines.insert(import_end + 1, business_import)

            # Find where to add the router (after app creation)
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
                lines.insert(app_creation_line + 1, "")
                lines.insert(app_creation_line + 2, "# Include business routers")
                lines.insert(app_creation_line + 3, business_include)

            # Write back
            with open(main_app_path, "w") as f:
                f.write("\n".join(lines))

        print("✅ Business routes integrated into main app!")


if __name__ == "__main__":
    copy_infrastructure()
    update_main_app()
    print("🎉 Template setup complete!")
