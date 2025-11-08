# clang-tool-chain

C/C++ compilation toolchain utilities using Clang.

[![Linting](../../actions/workflows/lint.yml/badge.svg)](../../actions/workflows/lint.yml)
[![MacOS_Tests](../../actions/workflows/push_macos.yml/badge.svg)](../../actions/workflows/push_macos.yml)
[![Ubuntu_Tests](../../actions/workflows/push_ubuntu.yml/badge.svg)](../../actions/workflows/push_ubuntu.yml)
[![Win_Tests](../../actions/workflows/push_win.yml/badge.svg)](../../actions/workflows/push_win.yml)

## Installation

```bash
pip install clang-tool-chain
```

## Development Setup

This project uses modern Python tooling with `pyproject.toml` and `uv` (or `pip`).

### Using uv (recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Using pip

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Usage

```bash
clang-tool-chain
```

## Development

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run tests in parallel
pytest -n auto

# Run specific test file
pytest tests/test_cli.py
```

### Code Quality

```bash
# Format code
black src tests
isort src tests

# Lint code
ruff check src tests

# Type check
mypy src tests
pyright
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. They run automatically on `git commit`, or you can run them manually:

```bash
pre-commit run --all-files
```

## Building

```bash
# Build package
pip install build
python -m build

# The built package will be in dist/
```

## License

BSD 3-Clause License
