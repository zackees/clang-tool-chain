# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Version Management Policy

**CRITICAL: DO NOT change the package version number in `pyproject.toml` unless explicitly instructed by the repository owner.**

The version number is carefully managed and coordinated with binary distributions, manifests, and PyPI releases. Unauthorized version changes can break the distribution system and user installations.

### Files to Update When Bumping Version

When the repository owner requests a version bump, update these files **in order**:

1. **`pyproject.toml`** (line ~7) - Primary source of truth
   ```toml
   version = "X.Y.Z"
   ```

2. **`src/clang_tool_chain/__version__.py`** (line 3) - Python module version
   ```python
   __version__ = "X.Y.Z"
   ```

3. **`uv.lock`** - Auto-generated; run `uv sync` or `uv pip install -e .` to update

**Verification:** Run `uv run pytest tests/test_version.py -v` to ensure versions are consistent.

## Project Overview

This is a Python package that distributes pre-built Clang/LLVM binaries for Windows, macOS, and Linux with Python wrapper executables. The package provides automatic downloading, installation, and execution of LLVM/Clang toolchain binaries with minimal configuration required.

**Platforms:** Windows x64, macOS x64/ARM64, Linux x64/ARM64.

## Quick Version Reference

| Component | Version | Platforms | Details |
|-----------|---------|-----------|---------|
| Clang/LLVM | 21.1.5 (Linux/Win), 21.1.6 (macOS) | All 5 | [docs/CLANG_LLVM.md](docs/CLANG_LLVM.md) |
| Emscripten | 4.0.19 (Mac/Win), 4.0.21 (Linux) | All 5 | [docs/EMSCRIPTEN.md](docs/EMSCRIPTEN.md) |
| LLDB | 21.1.5-6 | Win/Linux (pending builds) | [docs/LLDB.md](docs/LLDB.md) |
| Cosmopolitan | 4.0.2 | All 5 | [docs/COSMOCC.md](docs/COSMOCC.md) |
| Valgrind | 3.24.0 | Linux x64/ARM64 (via Docker) | [docs/VALGRIND.md](docs/VALGRIND.md) |

**Linker:** Uses `ld64.lld` on macOS, `ld.lld` on Linux/Windows. Opt-out: `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1`. GNU-style flags auto-translated on macOS. See [docs/CLANG_LLVM.md](docs/CLANG_LLVM.md) for details.

**Key Features:**
- Pre-built Clang/LLVM binaries (~50-400 MB per platform)
- Cross-platform support (Windows x64, macOS x64/ARM64, Linux x64/ARM64)
- Automatic toolchain download and installation on first use
- **Parallel downloads with HTTP range requests (3-5x faster)**
- Manifest-based distribution system with checksum verification
- Python wrapper commands for all essential tools
- Ultra-compressed archives using zstd level 22 (~94% size reduction)
- **Consistent LLD linker across all platforms** (ld64.lld on macOS, ld.lld on Linux/Windows)
- **Windows GNU ABI support with integrated MinGW headers and sysroot** (no separate download)
- **Automatic MinGW DLL deployment for Windows executables** (GNU ABI only)
- Emscripten WebAssembly compilation
- Bundled Node.js runtime
- **Cosmopolitan Libc support for Actually Portable Executables (APE)**
- **Inlined Build Directives for self-contained source files**
- **Bundled libunwind for Linux** (headers + shared library, no system packages required)
- **Valgrind memory error detector** (runs via Docker from any host platform)

## Documentation Index

All detailed documentation lives in `docs/`. Read the file matching your task.

### Core Toolchain

| Document | Read when... |
|----------|-------------|
| **[Clang/LLVM](docs/CLANG_LLVM.md)** | Working on compiler wrappers, sanitizers (ASAN/UBSAN), LLD linker, macOS SDK, Windows GNU/MSVC ABI, sccache |
| **[Inlined Directives](docs/DIRECTIVES.md)** | Working on `@link`, `@std`, `@cflags`, `@platform` directives in source files |
| **[Library Deployment](docs/SHARED_LIBRARY_DEPLOYMENT.md)** | Working on DLL/SO/dylib deployment, `--deploy-dependencies` flag |
| **[Bundled libunwind](docs/LIBUNWIND.md)** | Working on stack unwinding, backtraces, Windows symbol resolution |

### Additional Toolchains

| Document | Read when... |
|----------|-------------|
| **[Emscripten](docs/EMSCRIPTEN.md)** | Working on WebAssembly compilation (emcc, em++) |
| **[LLDB Debugger](docs/LLDB.md)** | Working on crash analysis, stack traces, Python bundling |
| **[Cosmopolitan](docs/COSMOCC.md)** | Working on Actually Portable Executables (cosmocc) |
| **[Valgrind](docs/VALGRIND.md)** | Working on memory leak detection, Valgrind Docker execution |
| **[Callgrind](docs/CALLGRIND.md)** | Working on call graph profiling, performance analysis |
| **[Node.js](docs/NODEJS.md)** | Working on bundled Node.js runtime |

### Configuration & Environment

| Document | Read when... |
|----------|-------------|
| **[Environment Variables](docs/ENVIRONMENT_VARIABLES.md)** | Looking up `CLANG_TOOL_CHAIN_*` env vars, note suppression hierarchy |
| **[Parallel Downloads](docs/PARALLEL_DOWNLOADS.md)** | Working on download speed, chunk configuration |

### Infrastructure

| Document | Read when... |
|----------|-------------|
| **[Architecture](docs/ARCHITECTURE.md)** | Working on manifest system, multi-part archives, download infrastructure |
| **[Testing Guide](docs/TESTING.md)** | Adding/modifying tests, debugging CI, understanding test matrix (45+ workflows) |

### Maintainer & Distribution

| Document | Read when... |
|----------|-------------|
| **[Maintainer Tools](docs/MAINTAINER.md)** | Packaging binaries, building archives, IWYU DLL bundling |
| **[Binary Archive Building](downloads-bins/CLAUDE.md)** | Building IWYU/Clang/LLVM archives, updating LLVM versions |

## Development Commands

### Initial Setup

```bash
# Install dependencies (preferred method using uv)
./install

# Or manually:
uv venv --python 3.11
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Optional: Install with sccache support for compilation caching
uv pip install -e ".[sccache]"
```

### Pre-installing the Toolchain

```bash
# Pre-download and install just the core Clang/LLVM toolchain
clang-tool-chain install clang

# This downloads ~71-91 MB and does NOT include:
# - IWYU (downloads on first use of clang-tool-chain-iwyu)
# - LLDB (downloads on first use of clang-tool-chain-lldb)
# - Emscripten (downloads on first use of clang-tool-chain-emcc)
# - Node.js (downloads with Emscripten)
```

### Removing Toolchains

```bash
# Remove all downloaded toolchains and cached data
clang-tool-chain purge          # Interactive confirmation
clang-tool-chain purge --yes    # Skip confirmation (for scripts)

# This removes ~/.clang-tool-chain/ directory (~200 MB - 1.4 GB)
# Toolchains will be re-downloaded on next use
```

### Installing Toolchain to System Environment

```bash
# Add Clang/LLVM toolchain binaries to system PATH
clang-tool-chain install clang-env

# Remove Clang/LLVM from PATH
clang-tool-chain uninstall clang-env
```

### Testing

```bash
# Quick diagnostic test of the toolchain installation
clang-tool-chain-test           # Runs 7 diagnostic tests

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

See [Testing Guide](docs/TESTING.md) for comprehensive testing documentation including test organization and CI/CD workflows.

### Code Quality

```bash
# Run all linters and formatters
./lint

# Individual tools:
uv run ruff check --fix src tests  # Lint with auto-fix
uv run ruff format src tests       # Format code and sort imports
uv run pyright src tests           # Type checking
uv run mypy src tests              # Alternative type checking
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

## Code Quality Standards

### Line Length
Maximum line length is 120 characters (configured in ruff).

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

### Formatting and Linting
- Ruff handles all linting, formatting, and import sorting
- F401 (unused imports) ignored in `__init__.py` files
- S101 (assert usage) ignored in test files

## Development Workflow

### Using uv for Commands
All development commands should be run through `uv run` to ensure correct virtual environment usage. The convenience scripts (`./test`, `./lint`, `./install`) handle this automatically.

## Binary Distribution & Packaging

### Where to Push Binaries

Use the `downloads-bins` **submodule** to store and distribute binaries -- NOT the main repository. See [downloads-bins/CLAUDE.md](downloads-bins/CLAUDE.md) for complete documentation.

### LFS Policy

**Do NOT use Git LFS** -- it costs money for bandwidth. All archives should be stored directly in git. Archives larger than 99 MB must be split into parts (each <99 MB). New archives should NEVER be added to LFS.

### Manifest Verification Checklist

When updating manifests, verify:
1. **SHA256 checksum** matches the archive file: `sha256sum -c archive.tar.zst.sha256`
2. **URL format** uses correct GitHub path (check `href` field)
3. **Required fields** present: `version`, `href`, `sha256`
4. **Archive integrity**: decompress and verify binaries execute (`zstd -d archive.tar.zst && tar xf archive.tar`)

### Post-Build Verification

```bash
# Verify archive decompresses correctly
uv run expand-archive assets/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst ./test-install

# Verify checksum
sha256sum -c assets/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst.sha256

# Verify binary execution
./test-install/bin/clang --version
```
