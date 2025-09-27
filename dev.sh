#!/bin/bash

# Development script for the API template project
# This allows you to work on the template code and run tests during development

set -e

case "${1:-help}" in
    "test")
        echo "Running infrastructure unit tests..."
        uv run pytest tests/ -v
        ;;
    "test-all")
        echo "Running all tests..."
        uv run pytest tests/ -v
        ;;
    "lint")
        echo "Running code quality checks..."
        uv run ruff check src/
        ;;
    "format")
        echo "Formatting code..."
        uv run ruff format src/
        ;;
    "serve")
        echo "Starting infrastructure development server..."
        PYTHONPATH=src uv run uvicorn src.app.api.http.app:app --reload
        ;;
    "serve-dev")
        echo "Starting legacy development server..."
        uv run uvicorn main:app --reload
        ;;
    "init-db")
        echo "Initializing database..."
        PYTHONPATH=src uv run python -c "from src.app.runtime.init_db import init_db; init_db()"
        ;;
    "help"|*)
        echo "Development commands for API Template:"
        echo ""
        echo "🏗️  Infrastructure Development:"
        echo "  test           Run all tests (infrastructure + template)"
        echo "  test-template  Run template generation tests only"
        echo "  serve          Start infrastructure development server"
        echo "  init-db        Initialize database for infrastructure"
        echo ""
        echo "🔧 Code Quality:"
        echo "  lint           Check code quality"
        echo "  format         Format code"
        echo ""
        echo "🚀 Legacy Development:"
        echo "  serve-dev      Start legacy development server"
        echo ""
        echo "Examples:"
        echo "  ./dev.sh test         # Run all tests"
        echo "  ./dev.sh test-template # Template tests only"
        echo "  ./dev.sh serve        # Run infrastructure server"
        ;;
esac