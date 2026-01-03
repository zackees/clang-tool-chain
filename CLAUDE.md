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
| macOS    | x86_64      | 19.1.7            | -                    |
| macOS    | arm64       | 19.1.7            | -                    |
| Windows  | x86_64      | 21.1.5            | MinGW-w64 (integrated) |
| Linux    | x86_64      | 21.1.5            | -                    |
| Linux    | arm64       | 21.1.5            | -                    |

*Version information as of November 11, 2025*

**Note:** The LLVM versions listed above are for the main clang-tool-chain toolchain. Emscripten uses its own bundled LLVM (LLVM 22 for Emscripten 4.0.19), which is installed separately and does not share binaries with the main toolchain.

### Emscripten WebAssembly Support

| Platform | Architecture | Emscripten Version | Status |
|----------|-------------|-------------------|--------|
| macOS    | x86_64      | 4.0.19            | ✅ Available |
| macOS    | arm64       | 4.0.19            | ✅ Available |
| Windows  | x86_64      | 4.0.19            | ✅ Available |
| Linux    | x86_64      | 4.0.21            | ✅ Available |
| Linux    | arm64       | 4.0.21            | ✅ Available |

*Emscripten support added November 2025*

**Key Features:**
- Pre-built Clang/LLVM binaries (~50-400 MB per platform)
- Cross-platform support (Windows x64, macOS x64/ARM64, Linux x64/ARM64)
- Automatic toolchain download and installation on first use
- **Parallel downloads with HTTP range requests (3-5x faster)**
- Manifest-based distribution system with checksum verification
- Python wrapper commands for all essential tools
- Ultra-compressed archives using zstd level 22 (~94% size reduction)
- **Windows GNU ABI support with integrated MinGW headers and sysroot** (no separate download)
- **Automatic MinGW DLL deployment for Windows executables** (GNU ABI only)
- Emscripten WebAssembly compilation
- Bundled Node.js runtime

## Documentation

Detailed documentation is organized into focused sub-documents:

- **[Clang/LLVM Toolchain](docs/CLANG_LLVM.md)** - Clang/LLVM compiler wrappers, macOS SDK detection, Windows GNU/MSVC ABI, sccache integration
- **[DLL Deployment](docs/DLL_DEPLOYMENT.md)** - Windows MinGW DLL automatic deployment (detailed guide)
- **[Emscripten](docs/EMSCRIPTEN.md)** - WebAssembly compilation with Emscripten
- **[Node.js Integration](docs/NODEJS.md)** - Bundled Node.js runtime for WebAssembly
- **[Parallel Downloads](docs/PARALLEL_DOWNLOADS.md)** - High-speed downloads with multi-threaded range requests
- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture, manifest system, multi-part archives
- **[Maintainer Tools](docs/MAINTAINER.md)** - Binary packaging, archive creation, troubleshooting
- **[Testing Guide](docs/TESTING.md)** - Test infrastructure, running tests, CI/CD

## Windows MinGW DLL Deployment

**Automatic DLL Deployment for Windows Executables (GNU ABI)**

When compiling Windows executables with the GNU ABI (default on Windows), clang-tool-chain automatically copies required MinGW runtime DLLs to the executable directory. This ensures your executables run immediately in `cmd.exe` without PATH modifications.

### How It Works

1. **Automatic Detection**: After successful linking, clang-tool-chain uses `llvm-objdump` to detect required MinGW DLLs
2. **Smart Copying**: DLLs are copied from the MinGW sysroot to the executable directory
3. **Timestamp Checking**: DLLs are only copied if source is newer (prevents unnecessary copies)
4. **Non-Fatal**: DLL deployment never fails your build - warnings only

### Environment Variables

- **`CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1`** - Disable automatic DLL deployment
- **`CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1`** - Enable verbose logging (DEBUG level)

### Example Usage

```bash
# Default behavior - DLLs automatically deployed
clang-tool-chain-cpp main.cpp -o program.exe
# Output: Deployed 3 MinGW DLL(s) for program.exe

# Run without PATH setup required
.\program.exe  # Works in cmd.exe immediately!

# Disable DLL deployment
set CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1
clang-tool-chain-cpp main.cpp -o program.exe
# No DLLs copied

# Verbose logging
set CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program.exe
# Output: Detailed DLL detection and copy logs
```

### Performance

- **DLL Detection**: <50ms per executable (llvm-objdump overhead)
- **DLL Copying**: <50ms total (2-3 small DLLs typically)
- **Total Overhead**: <100ms per executable build
- **Timestamp Check**: <5ms (skips copy if up-to-date)

### Typical DLLs Deployed

- `libwinpthread-1.dll` - Threading support
- `libgcc_s_seh-1.dll` - GCC runtime support
- `libstdc++-6.dll` - C++ standard library

### When It's Skipped

- **Non-Windows platforms**: Linux/macOS (no-op)
- **MSVC ABI**: `clang-tool-chain-cpp-msvc` (uses MSVC runtime)
- **Compile-only**: `-c` flag present (no executable produced)
- **Non-.exe outputs**: `.o`, `.obj`, `.a`, `.lib` files
- **Environment variable**: `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` set

### Logging Levels

- **INFO**: Summary of deployed DLLs (e.g., "Deployed 3 MinGW DLL(s) for program.exe")
- **DEBUG**: Individual DLL operations (detection, copy, skip reasons)
- **WARNING**: Missing DLLs, permission errors, detection failures

### See Also

- Implementation: `src/clang_tool_chain/deployment/dll_deployer.py`
- Tests: `tests/test_dll_deployment.py` (38 comprehensive tests)
- Integration: `src/clang_tool_chain/execution/core.py` (post-link hooks)

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

### Pre-installing the Toolchain

```bash
# Pre-download and install just the core Clang/LLVM toolchain
clang-tool-chain install clang

# This downloads ~71-91 MB and does NOT include:
# - IWYU (downloads on first use of clang-tool-chain-iwyu)
# - Emscripten (downloads on first use of clang-tool-chain-emcc)
# - Node.js (downloads with Emscripten)
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
# Also automatically removes any PATH entries (clang-env, iwyu-env, etc.)
```

### Installing Toolchain to System Environment

To make clang++ and related tools available globally (without the `clang-tool-chain-` prefix):

```bash
# Add Clang/LLVM toolchain binaries to system PATH
clang-tool-chain install clang-env

# Remove Clang/LLVM from PATH
clang-tool-chain uninstall clang-env
```

**Note:** This feature uses the `setenvironment` package (included as a dependency) and modifies system/user PATH persistently. Changes take effect in new terminal sessions.

**Future expansion:**
- `install iwyu` / `install iwyu-env` - IWYU analyzer (depends on clang)
- `install emscripten` / `install emscripten-env` - Emscripten SDK (includes its own LLVM, separate from main clang)
  - Note: Emscripten includes its own bundled LLVM, so `install emscripten-env` would add Emscripten's tools to PATH (emcc, em++, etc.), not the main clang toolchain.

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

## Test Matrix

The project uses a comprehensive test matrix with 35 GitHub Actions workflows covering all platform+tool combinations:

- **5 platforms:** Windows x64, Linux x86_64, Linux ARM64, macOS x86_64, macOS ARM64
- **7 tool categories:** clang, clang-sccache, emscripten, emscripten-sccache, iwyu, format-lint, binary-utils

Each workflow runs platform-specific tests to ensure all tools work correctly on all platforms.

See the "Test Matrix" section in README.md for live status badges.

### Test Organization by Tool Category

- **tests/test_integration.py** - Basic clang compilation tests
- **tests/test_emscripten.py** - Emscripten WebAssembly compilation
- **tests/test_emscripten_full_pipeline.py** - Full Emscripten pipeline tests
- **tests/test_iwyu.py** - Include What You Use analyzer tests
- **tests/test_format_lint.py** - clang-format and clang-tidy tests
- **tests/test_binary_utils.py** - LLVM binary utilities tests (ar, nm, objdump, strip, etc.)
- **tests/test_build_run_cached_integration.py** - sccache integration tests

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
