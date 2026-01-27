# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ Version Management Policy

**CRITICAL: DO NOT change the package version number in `pyproject.toml` unless explicitly instructed by the repository owner.**

The version number is carefully managed and coordinated with binary distributions, manifests, and PyPI releases. Unauthorized version changes can break the distribution system and user installations.

## Project Overview

This is a Python package that distributes pre-built Clang/LLVM binaries for Windows, macOS, and Linux with Python wrapper executables. The package provides automatic downloading, installation, and execution of LLVM/Clang toolchain binaries with minimal configuration required.

## Version Information

| Platform | Architecture | Clang/LLVM Version | Linker Used | Additional Components |
|----------|-------------|-------------------|-------------|----------------------|
| macOS    | x86_64      | 21.1.6            | ld64.lld    | -                    |
| macOS    | arm64       | 21.1.6            | ld64.lld    | -                    |
| Windows  | x86_64      | 21.1.5            | lld         | MinGW-w64 (integrated) |
| Linux    | x86_64      | 21.1.5            | lld         | -                    |
| Linux    | arm64       | 21.1.5            | lld         | -                    |

*Version information as of January 17, 2026*

**Linker Notes:**
- **macOS**: Uses `-fuse-ld=ld64.lld` on LLVM 21.x+ (explicit Mach-O linker). On older LLVM versions, automatically falls back to `-fuse-ld=lld` with a compatibility notice to stderr. GNU-style flags like `--no-undefined` are automatically translated to ld64 equivalents (`-undefined error`).
- **Linux/Windows**: Uses LLVM lld for faster linking and cross-platform consistency
- **Opt-out**: Set `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` to use the system linker instead of bundled LLD

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

### LLDB Debugger Support

| Platform | Architecture | LLDB Version | Python Support | Status |
|----------|-------------|--------------|----------------|--------|
| Windows  | x86_64      | 21.1.5       | ✅ Ready (workflow available) | ⏳ Build Pending |
| Linux    | x86_64      | 21.1.5       | ✅ Full (Python 3.10 ready) | ⏳ Wrapper Ready, Archives Pending |
| Linux    | arm64       | 21.1.5       | ✅ Full (Python 3.10 ready) | ⏳ Wrapper Ready, Archives Pending |
| macOS    | x86_64      | 21.1.6       | ⏳ Planned            | ⏳ Pending |
| macOS    | arm64       | 21.1.6       | ⏳ Planned            | ⏳ Pending |

*LLDB support added January 2026 (wrapper integration complete for Windows/Linux, automated build workflows deployed)*

**Python 3.10 Bundling:**

*Windows x64 (Build Workflow Ready):*
- **Automated workflow available**: `.github/workflows/build-lldb-archives-windows.yml`
- **Code changes complete**: Scripts extract python310.dll + standard library + LLDB Python module
- **Expected archive size**: ~35 MB compressed (+5 MB from current ~30 MB)
- **Status**: Archive rebuild pending maintainer action (workflow ready to execute)
- **Expected features after rebuild**: Full "bt all" backtraces, Python scripting, advanced variable inspection, LLDB Python API
- **Current workaround**: Users experiencing python310.dll errors should wait for next archive rebuild
- **Technical details**: See [Iteration 5 Documentation](.agent_task/ITERATION_5.md)

*Linux x86_64/ARM64 (Wrapper Ready):*
- **Python 3.10 integration complete**: Wrapper configured with PYTHONPATH/PYTHONHOME
- **Expected download size**: ~10-11 MB compressed per platform
- **Python modules ready**: Extracted from Debian Jammy packages + minimized stdlib
- **Status**: Wrapper complete, archives pending GitHub Actions workflow execution
- **CI/CD**: Workflow ready at `.github/workflows/build-lldb-archives-linux.yml`

See [LLDB Documentation](docs/LLDB.md) for complete Python integration details

### Cosmopolitan Libc Support

| Platform | Architecture | Cosmocc Version | Status |
|----------|-------------|-----------------|--------|
| Windows  | x86_64      | 4.0.2           | ✅ Available |
| Linux    | x86_64      | 4.0.2           | ✅ Available |
| Linux    | arm64       | 4.0.2           | ✅ Available |
| macOS    | x86_64      | 4.0.2           | ✅ Available |
| macOS    | arm64       | 4.0.2           | ✅ Available |

*Cosmopolitan support added January 2026*

**About Cosmopolitan Libc:**
Cosmopolitan Libc makes C a build-once run-anywhere language. Executables produced by cosmocc are called "Actually Portable Executables" (APE) and run natively on Windows, Linux, macOS, FreeBSD, NetBSD, and OpenBSD without any runtime dependencies or modifications.

**Usage:**
```bash
# Install cosmocc toolchain
clang-tool-chain install cosmocc

# Compile a portable executable
clang-tool-chain-cosmocc hello.c -o hello.com
clang-tool-chain-cosmocpp hello.cpp -o hello.com

# The .com file runs on any supported OS!
./hello.com  # Works on Linux, macOS, FreeBSD, etc.
# On Windows: hello.com
```

For more information: https://github.com/jart/cosmopolitan

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
- **Inlined Build Directives for self-contained source files** (NEW)

## Inlined Build Directives

clang-tool-chain supports embedding build configuration directly in source files using directive comments. This makes source files self-contained - they know how to build themselves.

### Quick Example

```cpp
// @link: pthread
// @std: c++17

#include <pthread.h>
#include <iostream>

int main() {
    // pthread code here
    return 0;
}
```

Compile without any extra flags:
```bash
clang-tool-chain-cpp pthread_hello.cpp -o pthread_hello
# Automatically adds -std=c++17 -lpthread
```

### Supported Directives

| Directive | Description | Example |
|-----------|-------------|---------|
| `@link` | Link libraries | `// @link: pthread` or `// @link: [pthread, m]` |
| `@std` | C/C++ standard | `// @std: c++17` |
| `@cflags` | Compiler flags | `// @cflags: -O2 -Wall` |
| `@ldflags` | Linker flags | `// @ldflags: -rpath /opt/lib` |
| `@include` | Include paths | `// @include: /usr/local/include` |
| `@platform` | Platform-specific | `// @platform: linux` (followed by indented directives) |

### Platform-Specific Example

```cpp
// @std: c++17

// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
// @platform: darwin
//   @link: pthread
```

### Commands with Directive Support

- `clang-tool-chain-cpp` / `clang-tool-chain-c`
- `clang-tool-chain-cpp-msvc` / `clang-tool-chain-c-msvc`
- `clang-tool-chain-build` / `clang-tool-chain-build-run`

### Environment Variables

- `CLANG_TOOL_CHAIN_NO_DIRECTIVES=1` - Disable directive parsing
- `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1` - Show parsed directives (debug)

See [Inlined Build Directives Documentation](docs/DIRECTIVES.md) for full details.

## Documentation

Detailed documentation is organized into focused sub-documents:

- **[Clang/LLVM Toolchain](docs/CLANG_LLVM.md)** - Clang/LLVM compiler wrappers, macOS SDK detection, Windows GNU/MSVC ABI, sccache integration
- **[Inlined Build Directives](docs/DIRECTIVES.md)** - Self-contained source files with embedded build configuration
- **[Library Deployment](docs/SHARED_LIBRARY_DEPLOYMENT.md)** - Cross-platform automatic library deployment (Windows DLL, Linux .so, macOS .dylib)
- **[Emscripten](docs/EMSCRIPTEN.md)** - WebAssembly compilation with Emscripten
- **[LLDB Debugger](docs/LLDB.md)** - LLVM debugger for interactive debugging and crash analysis
- **[Node.js Integration](docs/NODEJS.md)** - Bundled Node.js runtime for WebAssembly
- **[Parallel Downloads](docs/PARALLEL_DOWNLOADS.md)** - High-speed downloads with multi-threaded range requests
- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture, manifest system, multi-part archives
- **[Maintainer Tools](docs/MAINTAINER.md)** - Binary packaging, archive creation, troubleshooting
- **[Testing Guide](docs/TESTING.md)** - Test infrastructure, running tests, CI/CD

## Automatic Library Dependency Deployment

**Cross-Platform Automatic Library Deployment for Executables and Shared Libraries**

clang-tool-chain automatically detects and deploys required runtime libraries to the output directory on all platforms:
- **Windows**: MinGW DLLs (`.dll`) for GNU ABI executables and shared libraries
- **Linux**: Shared objects (`.so`) for executables and shared libraries
- **macOS**: Dynamic libraries (`.dylib`) for executables and shared libraries

This ensures your executables and libraries run immediately without PATH/LD_LIBRARY_PATH/DYLD_LIBRARY_PATH modifications, and shared libraries have their transitive dependencies available.

### Windows MinGW DLL Deployment

When compiling Windows executables (`.exe`) or shared libraries (`.dll`) with the GNU ABI (default on Windows), clang-tool-chain automatically copies required MinGW runtime DLLs to the output directory.

### How It Works

1. **Automatic Detection**: After successful linking, clang-tool-chain uses `llvm-objdump` to detect required MinGW DLLs
2. **Smart Copying**: DLLs are copied from the MinGW sysroot to the executable directory
3. **Timestamp Checking**: DLLs are only copied if source is newer (prevents unnecessary copies)
4. **Non-Fatal**: DLL deployment never fails your build - warnings only

### Environment Variables

- **`CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1`** - Disable automatic DLL deployment for all outputs
- **`CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS=1`** - Disable DLL deployment for .dll outputs only (default: enabled)
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
- **Non-.exe/.dll outputs**: `.o`, `.obj`, `.a`, `.lib` files
- **Environment variable**: `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` set
- **DLL outputs with opt-out**: `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS=1` set (for .dll only)

### Logging Levels

- **INFO**: Summary of deployed DLLs (e.g., "Deployed 3 MinGW DLL(s) for program.exe")
- **DEBUG**: Individual DLL operations (detection, copy, skip reasons)
- **WARNING**: Missing DLLs, permission errors, detection failures

### See Also

- Implementation: `src/clang_tool_chain/deployment/dll_deployer.py`
- Tests: `tests/test_dll_deployment.py` (38 comprehensive tests)
- Integration: `src/clang_tool_chain/execution/core.py` (post-link hooks)

### Linux Shared Library Deployment

When compiling Linux executables or shared libraries (`.so`), clang-tool-chain can automatically detect and copy required shared libraries to the output directory using the `--deploy-dependencies` flag.

**How It Works**:
1. **Dependency Detection**: Uses `ldd` to detect required shared libraries
2. **Smart Copying**: Copies `.so` files to the executable directory
3. **Symlink Handling**: Preserves symlinks (e.g., `libunwind.so.8` → `libunwind.so.8.0.1`)
4. **Non-Fatal**: Library deployment never fails your build - warnings only

**Example Usage**:
```bash
# Build with automatic library deployment
clang-tool-chain-cpp -shared -fPIC mylib.cpp -o mylib.so --deploy-dependencies
# Output: Deployed 2 shared libraries for mylib.so

# Build executable with library deployment
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies -lunwind
# Output: Deployed 1 shared library for program

# Run without LD_LIBRARY_PATH setup required
./program  # Works immediately!
```

**Environment Variables**:
- **`CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1`** - Disable automatic library deployment
- **`CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1`** - Enable verbose logging

**Performance**:
- Dependency detection: ~50-200ms (ldd overhead)
- Library copying: ~50-100ms (2-3 libraries typically)
- Total overhead: ~100-300ms per build

**See Also**:
- Implementation: `src/clang_tool_chain/deployment/so_deployer.py`
- Tests: `tests/test_so_deployment.py` (43 comprehensive tests)
- Factory: `src/clang_tool_chain/deployment/factory.py`

### macOS Dynamic Library Deployment

When compiling macOS executables or dynamic libraries (`.dylib`), clang-tool-chain can automatically detect and copy required dynamic libraries to the output directory using the `--deploy-dependencies` flag.

**How It Works**:
1. **Dependency Detection**: Uses `otool -L` to detect required dynamic libraries
2. **Smart Copying**: Copies `.dylib` files to the executable directory
3. **@rpath Handling**: Supports @rpath, @loader_path, and absolute paths
4. **Non-Fatal**: Library deployment never fails your build - warnings only

**Example Usage**:
```bash
# Build with automatic library deployment
clang-tool-chain-cpp -shared -fPIC mylib.cpp -o mylib.dylib --deploy-dependencies
# Output: Deployed 2 dynamic libraries for mylib.dylib

# Build executable with library deployment
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies -lunwind
# Output: Deployed 1 dynamic library for program

# Run without DYLD_LIBRARY_PATH setup required
./program  # Works immediately!
```

**Environment Variables**:
- **`CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1`** - Disable automatic library deployment
- **`CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1`** - Enable verbose logging

**Performance**:
- Dependency detection: ~50-200ms (otool overhead)
- Library copying: ~50-100ms (2-3 libraries typically)
- Total overhead: ~100-300ms per build

**See Also**:
- Implementation: `src/clang_tool_chain/deployment/dylib_deployer.py`
- Tests: `tests/test_dylib_deployment.py` (51 comprehensive tests)
- Factory: `src/clang_tool_chain/deployment/factory.py`

### Cross-Platform Environment Variables

For maximum compatibility, clang-tool-chain supports both legacy (Windows-specific) and modern (cross-platform) environment variables:

| Variable | Platform | Purpose | Status |
|----------|----------|---------|--------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS` | Windows (legacy) | Disable DLL deployment | ✅ Existing |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` | All platforms | Disable library deployment | ✅ New |
| `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE` | Windows (legacy) | Verbose logging | ✅ Existing |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` | All platforms | Verbose logging | ✅ New |

**Backward Compatibility**: All existing Windows-specific variables (`*_DLLS`, `*_DLL_*`) still work and will be honored alongside the modern cross-platform variables (`*_LIBS`, `*_LIB_*`).

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

# This removes ~/.clang-tool-chain/ directory which contains:
# - LLVM/Clang binaries (~200-400 MB per platform)
# - MinGW sysroot (~176 MB uncompressed, Windows only)
# - Emscripten SDK (~1.4 GB uncompressed)
# - Node.js runtime (~90-100 MB uncompressed)
# - IWYU binaries
# - LLDB binaries
# - Lock files

# Toolchains will be re-downloaded on next use
# Also automatically removes any PATH entries (clang-env, iwyu-env, lldb-env, etc.)
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
- `install lldb` / `install lldb-env` - LLDB debugger (depends on clang)
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

The project uses a comprehensive test matrix with 40 GitHub Actions workflows covering all platform+tool combinations:

- **5 platforms:** Windows x64, Linux x86_64, Linux ARM64, macOS x86_64, macOS ARM64
- **8 tool categories:** clang, clang-sccache, emscripten, emscripten-sccache, iwyu, lldb, format-lint, binary-utils

Each workflow runs platform-specific tests to ensure all tools work correctly on all platforms.

See the "Test Matrix" section in README.md for live status badges.

### Test Organization by Tool Category

- **tests/test_integration.py** - Basic clang compilation tests
- **tests/test_emscripten.py** - Emscripten WebAssembly compilation
- **tests/test_emscripten_full_pipeline.py** - Full Emscripten pipeline tests
- **tests/test_iwyu.py** - Include What You Use analyzer tests
- **tests/test_lldb.py** - LLDB debugger tests (crash analysis and stack traces)
- **tests/test_format_lint.py** - clang-format and clang-tidy tests
- **tests/test_binary_utils.py** - LLVM binary utilities tests (ar, nm, objdump, strip, etc.)
- **tests/test_build_run_cached_integration.py** - sccache integration tests

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
