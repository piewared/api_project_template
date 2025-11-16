#!/bin/bash
# scripts/sync_to_template.sh
# Syncs infrastructure files from project root to template directory
# This keeps the bundled infrastructure up-to-date for remote template users

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$PROJECT_ROOT/{{cookiecutter.project_slug}}/_infrastructure"

echo "🔄 Syncing infrastructure to template..."
echo "   From: $PROJECT_ROOT"
echo "   To:   $INFRA_DIR"

# Create infrastructure directory
mkdir -p "$INFRA_DIR"

# Files and directories to sync
ITEMS=(
    "src"
    "k8s"
    "infra"
    "examples"
    "docs"
    "tests"
    ".env.example"
    ".gitignore"
    "config.yaml"
    "docker-compose.dev.yml"
    "docker-compose.prod.yml"
    "Dockerfile"
    "pyproject.toml"
    "uv.lock"
    "src_main.py"
    "README.md"
)

# Check if rsync is available
if ! command -v rsync &> /dev/null; then
    echo "⚠️  rsync not found, using cp instead (slower)"
    USE_CP=true
else
    USE_CP=false
fi

for item in "${ITEMS[@]}"; do
    if [ -e "$PROJECT_ROOT/$item" ]; then
        echo "  ✓ Syncing $item"
        
        if [ "$USE_CP" = true ]; then
            # Fallback to cp if rsync not available
            if [ -d "$PROJECT_ROOT/$item" ]; then
                rm -rf "$INFRA_DIR/$item"
                cp -r "$PROJECT_ROOT/$item" "$INFRA_DIR/"
            else
                cp "$PROJECT_ROOT/$item" "$INFRA_DIR/"
            fi
        else
            # Use rsync for efficient syncing (only copies changed files)
            rsync -a --delete \
                --exclude='__pycache__' \
                --exclude='*.pyc' \
                --exclude='.pytest_cache' \
                --exclude='*.egg-info' \
                --exclude='.mypy_cache' \
                --exclude='.ruff_cache' \
                --exclude='node_modules' \
                --exclude='.venv' \
                --exclude='venv' \
                --exclude='*.db' \
                --exclude='*.sqlite' \
                --exclude='*.sqlite3' \
                "$PROJECT_ROOT/$item" "$INFRA_DIR/"
        fi
    else
        echo "  ⚠ Skipping $item (not found)"
    fi
done

echo ""
echo "✅ Infrastructure synced to {{cookiecutter.project_slug}}/_infrastructure/"
echo "   This directory should be committed to git for remote template users."
echo ""
echo "📝 Next steps:"
echo "   1. Review changes: git status {{cookiecutter.project_slug}}/_infrastructure/"
echo "   2. Stage changes:  git add {{cookiecutter.project_slug}}/_infrastructure/"
echo "   3. Commit:         git commit -m 'bundle: update infrastructure'"
echo "   4. Push:           git push"
