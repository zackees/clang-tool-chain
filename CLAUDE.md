# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Version Management Policy

**CRITICAL: DO NOT change the package version number in `pyproject.toml` unless explicitly instructed by the repository owner.**

The version number is carefully managed and coordinated with binary distributions, manifests, and PyPI releases. Unauthorized version changes can break the distribution system and user installations.

## Project Overview

This is a Python package that distributes pre-built Clang/LLVM binaries for Windows, macOS, and Linux with Python wrapper executables. The package provides automatic downloading, installation, and execution of LLVM/Clang toolchain binaries with minimal configuration required.

## Version Information

| Platform | Architecture | Clang/LLVM Version | Additional Components |
|----------|-------------|-------------------|----------------------|
| macOS    | x86_64      | 19.1.6            | -                    |
| macOS    | arm64       | 19.1.6            | -                    |
| Windows  | x86_64      | 21.1.5            | MinGW-w64 21.1.5 (GNU ABI) |
| Linux    | x86_64      | 21.1.5            | -                    |
| Linux    | arm64       | 21.1.5            | -                    |

*Version information as of November 9, 2025*

**Key Features:**
- Pre-built Clang/LLVM binaries (~200-400 MB per platform)
- Cross-platform support (Windows x64, macOS x64/ARM64, Linux x64/ARM64)
- Automatic toolchain download and installation on first use
- Manifest-based distribution system with checksum verification
- Python wrapper commands for all essential tools
- Ultra-compressed archives using zstd level 22 (~94% size reduction)
- Windows GNU ABI support with MinGW sysroot
- Emscripten WebAssembly compilation
- Bundled Node.js runtime

## Documentation

Detailed documentation is organized into focused sub-documents:

- **[Clang/LLVM Toolchain](docs/CLANG_LLVM.md)** - Clang/LLVM compiler wrappers, macOS SDK detection, Windows GNU/MSVC ABI, sccache integration
- **[Emscripten](docs/EMSCRIPTEN.md)** - WebAssembly compilation with Emscripten
- **[Node.js Integration](docs/NODEJS.md)** - Bundled Node.js runtime for WebAssembly
- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture, manifest system, multi-part archives
- **[Maintainer Tools](docs/MAINTAINER.md)** - Binary packaging, archive creation, troubleshooting
- **[Testing Guide](docs/TESTING.md)** - Test infrastructure, running tests, CI/CD

## Development Commands

### Initial Setup

```bash
# Install dependencies (preferred method using uv)
./install

# Or manually:
uv venv --python 3.11
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
pre-commit install

# Optional: Install with sccache support for compilation caching
uv pip install -e ".[sccache]"
```

### Removing Toolchains

```bash
# Remove all downloaded toolchains and cached data
clang-tool-chain purge          # Interactive confirmation
clang-tool-chain purge --yes    # Skip confirmation (for scripts)

# This removes ~/.clang-tool-chain/ directory which contains:
# - LLVM/Clang binaries (~200-400 MB per platform)
# - MinGW sysroot (~176 MB uncompressed, Windows only)
# - Emscripten SDK (~1.4 GB uncompressed)
# - Node.js runtime (~90-100 MB uncompressed)
# - IWYU binaries
# - Lock files

# Toolchains will be re-downloaded on next use
```

### Testing

```bash
# Quick diagnostic test of the toolchain installation
clang-tool-chain-test           # Runs 7 diagnostic tests
# Or via main CLI:
clang-tool-chain test          # Same as above

# Run all tests with coverage (parallel execution)
./test

# Or manually with pytest:
uv run pytest                    # Run with coverage reporting
uv run pytest -n auto            # Run in parallel
uv run pytest tests/test_cli.py  # Run specific test file
uv run pytest -m "not slow"      # Skip slow tests

# Run single test
uv run pytest tests/test_cli.py::MainTester::test_imports -v

# Windows-specific tests
uv run pytest tests/test_gnu_abi.py -v          # Windows GNU ABI tests
uv run pytest tests/test_msvc_compile.py -v     # Windows MSVC comprehensive tests
```

See [Testing Guide](docs/TESTING.md) for comprehensive testing documentation.

### Code Quality

```bash
# Run all linters and formatters
./lint

# Individual tools:
uv run ruff check --fix src tests  # Lint with auto-fix
uv run black src tests             # Format code
uv run isort --profile black src tests  # Sort imports
uv run pyright src tests           # Type checking
uv run mypy src tests              # Alternative type checking
```

### Pre-commit Hooks

```bash
pre-commit run --all-files  # Run all pre-commit checks manually
```

### Cleaning

```bash
./clean  # Remove build artifacts, cache files, and virtual environments
```

### Building and Publishing

```bash
# Build the package
uv run python -m build

# Upload to PyPI
./upload_package.sh
```

## Code Quality Standards

### Line Length
Maximum line length is 120 characters (configured in ruff, black, and isort).

### Python Version
- Minimum Python version: 3.10
- Development uses Python 3.11

### Test Coverage
- Coverage reports are generated automatically with pytest
- Reports in: terminal, HTML (htmlcov/), and XML formats
- Source coverage tracked for `src/` directory only

### Type Checking
- MyPy runs with `warn_return_any` and `warn_unused_configs`
- Untyped defs are allowed (`disallow_untyped_defs = false`)
- Missing imports are ignored
- Pyright uses "basic" type checking mode

### Import Handling
- F401 (unused imports) ignored in `__init__.py` files
- S101 (assert usage) ignored in test files
- Use isort with black profile for import organization

### Pre-commit Integration
Pre-commit hooks enforce:
- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON/TOML validation
- Large file detection
- Debug statement detection
- Mixed line ending checks
- Black formatting
- isort import sorting
- Ruff linting with auto-fix
- MyPy type checking

Hooks run automatically on `git commit` and will block commits if checks fail.

## Development Workflow

### Using uv for Commands
All development commands should be run through `uv run` to ensure correct virtual environment usage. The convenience scripts (`./test`, `./lint`, `./install`) handle this automatically.

### Testing Integration
```bash
# Test the complete workflow
uv run pytest tests/test_integration.py -v

# Test CLI commands
uv run pytest tests/test_cli.py -v

# Test downloader
uv run pytest tests/test_downloader.py -v

# Test Windows GNU ABI support (Windows only)
uv run pytest tests/test_gnu_abi.py -v

# Run all Windows-specific tests
uv run pytest -k "windows or gnu or msvc" -v
```
