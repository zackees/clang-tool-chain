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

## Version Information

| Platform | Architecture | Clang/LLVM Version | Linker Used | Additional Components |
|----------|-------------|-------------------|-------------|----------------------|
| macOS    | x86_64      | 21.1.6            | ld64.lld    | -                    |
| macOS    | arm64       | 21.1.6            | ld64.lld    | -                    |
| Windows  | x86_64      | 21.1.5            | lld         | MinGW-w64 (integrated) |
| Linux    | x86_64      | 21.1.5            | lld         | libunwind (bundled)  |
| Linux    | arm64       | 21.1.5            | lld         | libunwind (bundled)  |

*Version information as of January 17, 2026*

**Linker Notes:**
- **macOS**: Uses `-fuse-ld=ld64.lld` on LLVM 21.x+ (explicit Mach-O linker). On older LLVM versions, automatically falls back to `-fuse-ld=lld` with a compatibility notice to stderr. GNU-style flags are automatically translated to ld64 equivalents: `--no-undefined` → `-undefined error`, `--fatal-warnings` → `-fatal_warnings`. Flags with no equivalent (like `--allow-shlib-undefined`) are removed with a warning. Set `CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1` to suppress the warning.
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
- **Bundled libunwind for Linux** (headers + shared library, no system packages required)

## Bundled libunwind (Linux)

On Linux, clang-tool-chain bundles libunwind headers and shared libraries, providing a complete self-contained solution for stack unwinding without requiring system packages.

### What's Bundled

| Component | Files | Size |
|-----------|-------|------|
| Headers | `libunwind.h`, `libunwind-common.h`, `libunwind-x86_64.h`/`libunwind-aarch64.h`, `libunwind-dynamic.h`, `libunwind-ptrace.h`, `unwind.h` | ~20 KB |
| Libraries | `libunwind.so.*`, `libunwind-x86_64.so.*` (or `aarch64`) | ~300 KB |

### How It Works

When compiling on Linux, clang-tool-chain automatically:
1. Adds `-I<clang_root>/include` for bundled libunwind headers
2. Adds `-L<clang_root>/lib` for bundled libunwind libraries
3. Adds `-Wl,-rpath,<clang_root>/lib` so executables find libunwind at runtime

This means `#include <libunwind.h>` and `-lunwind` work out of the box without installing `libunwind-dev`.

### Usage Example

```c
// test_unwind.c
#include <stdio.h>
#include <libunwind.h>

void print_backtrace() {
    unw_cursor_t cursor;
    unw_context_t context;
    unw_getcontext(&context);
    unw_init_local(&cursor, &context);

    while (unw_step(&cursor) > 0) {
        char name[256];
        unw_word_t offset;
        unw_get_proc_name(&cursor, name, sizeof(name), &offset);
        printf("  %s+0x%lx\n", name, (unsigned long)offset);
    }
}

int main() {
    print_backtrace();
    return 0;
}
```

```bash
# Compile and link with bundled libunwind
clang-tool-chain-c test_unwind.c -lunwind -o test_unwind

# Run without LD_LIBRARY_PATH - works due to embedded rpath
./test_unwind
```

### Environment Variables

- **`CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND=1`** - Disable bundled libunwind (use system libunwind instead)

### Platform Support

| Platform | libunwind.h | libunwind.so | Test Workflow |
|----------|-------------|--------------|---------------|
| Linux x86_64 | ✅ Bundled | ✅ Bundled | `test-libunwind-linux-x86.yml` |
| Linux ARM64 | ✅ Bundled | ✅ Bundled | `test-libunwind-linux-arm.yml` |
| Windows x64 | ✅ MinGW sysroot | ✅ MinGW sysroot | `test-libunwind-win.yml` |
| macOS x86_64 | ✅ System | ✅ System | `test-libunwind-macos-x86.yml` |
| macOS ARM64 | ✅ System | ✅ System | `test-libunwind-macos-arm.yml` |

**Notes:**
- **Linux**: Bundled libunwind (headers + shared libraries) extracted from Debian packages. Building Linux archives requires Docker (`docker run ubuntu:22.04`).
- **Windows**: libunwind provided via MinGW sysroot (part of the Windows toolchain). No additional installation required. Native symbol resolution is provided via `unwind_windows.c` implementation.
- **macOS**: Uses system libunwind from macOS SDK. No additional installation required.
- **Testing**: All platforms have comprehensive test suites (`tests/test_libunwind_headers.py`) that verify header compilation, library linking, runtime execution, and backtrace functionality.
- **CI/CD**: All five platform variants have dedicated GitHub Actions workflows ensuring libunwind works correctly on every supported platform.

**Symbol Resolution on Windows:**
clang-tool-chain provides native symbol resolution for Windows through a C implementation that makes `unw_get_proc_name()` work automatically.

**Using Native Symbol Resolution** (recommended):
```bash
# Compile your program with unwind_windows.c to enable symbol resolution
clang-tool-chain-c unwind_windows.c your_program.c -lunwind -o program.exe

# Or include the header and link with the pre-built DLL
clang-tool-chain-c your_program.c -lunwind -lunwind_proc_name -o program.exe
```

**How it works:**
1. Parses COFF symbol table embedded in the PE executable
2. Builds sorted symbol map at initialization
3. Handles ASLR automatically by calculating runtime addresses
4. Returns function names and offsets from function start
5. Works in-process with no external tool dependencies

**Example stack trace output:**
```c
#include <stdio.h>
#define UNW_LOCAL_ONLY
#include <libunwind.h>

void print_backtrace(void) {
    unw_cursor_t cursor;
    unw_context_t context;
    unw_getcontext(&context);
    unw_init_local(&cursor, &context);

    while (unw_step(&cursor) > 0) {
        char name[256];
        unw_word_t offset;
        if (unw_get_proc_name(&cursor, name, sizeof(name), &offset) == 0) {
            printf("%s+0x%lx\n", name, offset);
        }
    }
}
```

**Output:**
```
test_func_beta+0x9
test_func_alpha+0x9
main+0x1b
```

**Source Location Information:**
The native implementation provides function names and offsets. For detailed source locations (file:line:column), use LLDB debugger:
```bash
clang-tool-chain-lldb --print program.exe  # Print crash stack trace with source locations
clang-tool-chain-lldb program.exe          # Interactive debugging
```

**Implementation Files:**
- `src/clang_tool_chain/symbolizer/unwind_windows.c` - C implementation
- `src/clang_tool_chain/symbolizer/unwind_windows.h` - Header file
- `src/clang_tool_chain/symbolizer/libunwind_proc_name.dll` - Pre-built DLL (optional)

**Advanced: Manual Symbol Resolution with llvm-symbolizer:**
If you need source locations without LLDB, you can manually use llvm-symbolizer:
```bash
# Compile with debug symbols
clang-tool-chain-c program.c -o program.exe -g

# Get symbols from binary
llvm-nm program.exe | grep main
# Output: 1400014d0 T main

# Resolve static address to source location
llvm-symbolizer -e program.exe -f -C 0x1400014d0
# Output: main
#         C:\path\to\program.c:10:0
```

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
- **[Binary Archive Building](downloads-bins/CLAUDE.md)** - Building IWYU/Clang/LLVM archives for distribution (submodule)
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

- **`CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1`** - Disable automatic library deployment for all outputs (cross-platform)
- **`CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1`** - Disable library deployment for shared library outputs only (.dll, .so, .dylib)
- **`CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1`** - Enable verbose logging (DEBUG level)

### Example Usage

```bash
# Default behavior - DLLs automatically deployed
clang-tool-chain-cpp main.cpp -o program.exe
# Output: Deployed 3 MinGW DLL(s) for program.exe

# Run without PATH setup required
.\program.exe  # Works in cmd.exe immediately!

# Disable library deployment
set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp main.cpp -o program.exe
# No DLLs copied

# Verbose logging
set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
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
- **Environment variable**: `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` set
- **DLL outputs with opt-out**: `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1` set (for .dll only)

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

clang-tool-chain uses unified cross-platform environment variables for library deployment:

| Variable | Platform | Purpose |
|----------|----------|---------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` | All platforms | Disable library deployment for all outputs |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB` | All platforms | Disable library deployment for shared library outputs only (.dll, .so, .dylib) |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` | All platforms | Enable verbose deployment logging |

See [Environment Variables Documentation](docs/ENVIRONMENT_VARIABLES.md) for complete reference.

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

The project uses a comprehensive test matrix with 45+ GitHub Actions workflows covering all platform+tool combinations:

- **5 platforms:** Windows x64, Linux x86_64, Linux ARM64, macOS x86_64, macOS ARM64
- **9 tool categories:** clang, clang-sccache, emscripten, emscripten-sccache, iwyu, lldb, libunwind, format-lint, binary-utils

Each workflow runs platform-specific tests to ensure all tools work correctly on all platforms.

See the "Test Matrix" section in README.md for live status badges.

### Test Organization by Tool Category

- **tests/test_integration.py** - Basic clang compilation tests
- **tests/test_emscripten.py** - Emscripten WebAssembly compilation
- **tests/test_emscripten_full_pipeline.py** - Full Emscripten pipeline tests
- **tests/test_iwyu.py** - Include What You Use analyzer tests
- **tests/test_lldb.py** - LLDB debugger tests (crash analysis and stack traces)
- **tests/test_libunwind_headers.py** - libunwind stack unwinding tests (all platforms: Linux bundled, Windows MinGW sysroot, macOS system)
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

## Address Sanitizer (ASAN) Support

clang-tool-chain fully supports ASAN (Address Sanitizer) and other sanitizers on all platforms with automatic runtime library linking and deployment.

### Linux ASAN Configuration

On Linux, when using `-fsanitize=address`, clang-tool-chain automatically injects the following flags:
- `-shared-libasan` - Uses the shared ASAN runtime library (prevents undefined symbol errors during linking)
- `-Wl,--allow-shlib-undefined` - When building shared libraries (`-shared`), allows undefined symbols that will be provided by the sanitizer runtime at load time

Individual notes are printed to stderr when flags are automatically injected:
```
clang-tool-chain: note: automatically injected -shared-libasan for ASAN runtime linking (disable with CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE=1)
clang-tool-chain: note: automatically injected -Wl,--allow-shlib-undefined for shared library ASAN (disable with CLANG_TOOL_CHAIN_NO_ALLOW_SHLIB_UNDEFINED_NOTE=1)
```

**Example:**
```bash
# Compile with ASAN - runtime automatically linked
clang-tool-chain-cpp -fsanitize=address test.cpp -o test

# Build shared library with ASAN - allows undefined sanitizer symbols
clang-tool-chain-cpp -fsanitize=address -shared -fPIC mylib.cpp -o mylib.so

# Deploy ASAN shared library alongside executable (optional)
clang-tool-chain-cpp -fsanitize=address test.cpp -o test --deploy-dependencies

# Run with ASAN enabled
./test
```

**Environment Variables:**
- `CLANG_TOOL_CHAIN_NO_SHARED_ASAN=1` - Disable automatic `-shared-libasan` injection (use static ASAN)
- `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` - Disable automatic library deployment
- `CLANG_TOOL_CHAIN_NO_SANITIZER_ENV=1` - Disable automatic `ASAN_OPTIONS`/`LSAN_OPTIONS` injection at runtime

**Note Suppression (Hierarchical):**
Notes can be suppressed at different levels using a hierarchical system:

| Variable | Scope | What it suppresses |
|----------|-------|-------------------|
| `CLANG_TOOL_CHAIN_NO_AUTO=1` | Global | All automatic features and notes |
| `CLANG_TOOL_CHAIN_NO_SANITIZER_NOTE=1` | Category | All sanitizer-related notes |
| `CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE=1` | Specific | Only the -shared-libasan note |
| `CLANG_TOOL_CHAIN_NO_ALLOW_SHLIB_UNDEFINED_NOTE=1` | Specific | Only the --allow-shlib-undefined note |
| `CLANG_TOOL_CHAIN_NO_LINKER_NOTE=1` | Category | All linker-related notes |
| `CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1` | Specific | Only the removed GNU flags note |
| `CLANG_TOOL_CHAIN_NO_LD64_LLD_CONVERT_NOTE=1` | Specific | Only the ld64.lld conversion note |

Each note message includes its specific disable variable for easy discoverability.

### Runtime Environment (ASAN_OPTIONS Injection)

When running executables via `clang-tool-chain-build-run`, optimal sanitizer options are automatically injected to improve stack trace quality **only when the corresponding sanitizer was used during compilation**. This fixes `<unknown module>` entries in stack traces from `dlopen()`'d shared libraries.

**Automatically injected based on compiler flags:**
- `ASAN_OPTIONS=fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1` (when `-fsanitize=address` is used)
- `LSAN_OPTIONS=fast_unwind_on_malloc=0:symbolize=1` (when `-fsanitize=address` or `-fsanitize=leak` is used)
- `ASAN_SYMBOLIZER_PATH=/path/to/llvm-symbolizer` (automatically detected from clang-tool-chain installation)

**What these options do:**
- `fast_unwind_on_malloc=0`: Use slow but accurate stack unwinding (fixes `<unknown module>` in dlopen'd libraries)
- `symbolize=1`: Enable symbolization for readable function names in stack traces
- `detect_leaks=1`: Enable leak detection (ASAN only)
- `ASAN_SYMBOLIZER_PATH`: Points to `llvm-symbolizer` binary for address-to-symbol resolution (function names, file paths, line numbers)

**Opt-out:** Set `CLANG_TOOL_CHAIN_NO_SANITIZER_ENV=1` to disable automatic injection.

**User options preserved:** If you set `ASAN_OPTIONS`, `LSAN_OPTIONS`, or `ASAN_SYMBOLIZER_PATH` yourself, your values are preserved (no automatic injection for that variable).

### Programmatic API for Sanitizer Environment

External callers can use the sanitizer environment API programmatically:

```python
from clang_tool_chain import prepare_sanitizer_environment, get_symbolizer_path

# Option A: Complete environment setup (recommended)
env = prepare_sanitizer_environment(
    base_env=os.environ.copy(),
    compiler_flags=["-fsanitize=address", "-O2"]
)
# env now contains ASAN_OPTIONS, LSAN_OPTIONS, and ASAN_SYMBOLIZER_PATH

# Option B: Get just the symbolizer path
symbolizer = get_symbolizer_path()
if symbolizer:
    os.environ["ASAN_SYMBOLIZER_PATH"] = symbolizer
```

**Functions:**
- `prepare_sanitizer_environment(base_env, compiler_flags)` - Returns environment dict with all sanitizer variables injected
- `get_symbolizer_path()` - Returns path to `llvm-symbolizer` or `None` if not found
- `detect_sanitizers_from_flags(flags)` - Returns `(asan_enabled, lsan_enabled)` tuple
- `get_asan_runtime_dll()` - Returns `Path` to the ASAN runtime DLL on Windows, or `None` (for Meson workaround)
- `get_all_sanitizer_runtime_dlls()` - Returns list of `Path` objects for all sanitizer DLLs on Windows
- `get_runtime_dll_paths()` - Returns list of directory paths containing runtime DLLs on Windows

**Note:** Options are only injected when the corresponding sanitizer is detected in the compiler flags. Regular builds without sanitizers are unaffected.

**Implementation Details:**
- **ASANRuntimeTransformer** (priority=250) automatically adds `-shared-libasan` when `-fsanitize=address` detected on Linux
- **ASANRuntimeTransformer** also adds `-Wl,--allow-shlib-undefined` when building shared libraries (`-shared`) with ASAN
- A warning is printed to stderr when sanitizer flags are automatically injected
- Shared library deployment now works on all platforms (previously Windows-only)
- The `execute_tool()` function now uses `subprocess.run()` on all platforms to enable post-link deployment
- ASAN runtime library (`libclang_rt.asan.so`) is automatically deployed when `--deploy-dependencies` flag is used
- **`get_symbolizer_path()`** finds `llvm-symbolizer` from clang-tool-chain installation, falls back to system PATH
- **`prepare_sanitizer_environment()`** automatically injects `ASAN_SYMBOLIZER_PATH` when sanitizers are detected

**Files Modified:**
- `src/clang_tool_chain/execution/arg_transformers.py` - Added ASANRuntimeTransformer
- `src/clang_tool_chain/execution/core.py` - Replaced `os.execv()` with `subprocess.run()` for Linux/macOS deployment support
- `src/clang_tool_chain/execution/sanitizer_env.py` - Added `get_symbolizer_path()` and `ASAN_SYMBOLIZER_PATH` injection
- `tests/test_asan_linking.py` - Comprehensive ASAN linking tests
- `tests/test_asan_options_injection.py` - Tests for sanitizer environment injection (43 tests)

### Windows ASAN Support

Windows ASAN support works with both GNU and MSVC ABIs. Runtime DLLs are automatically deployed for GNU ABI builds.

#### Meson Test Runner Workaround

When running ASAN-instrumented tests via Meson's test runner (`meson test`), Meson overrides PATH to only include build directory DLLs. This causes tests to fail with exit code 3 (DLL not found) because the ASAN runtime DLL (`libclang_rt.asan_dynamic-x86_64.dll`) is external to the build directory.

**Solution:** Copy the ASAN DLL to your build directory so Meson discovers it automatically:

```python
from clang_tool_chain import get_asan_runtime_dll
import shutil
from pathlib import Path

# Get the ASAN DLL path
dll_path = get_asan_runtime_dll()
if dll_path:
    build_dir = Path(".build/meson-debug/tests")  # Your build directory
    shutil.copy(dll_path, build_dir / dll_path.name)
    # Now `meson test` will find the ASAN DLL
```

Alternatively, copy all sanitizer DLLs:
```python
from clang_tool_chain import get_all_sanitizer_runtime_dlls
import shutil

for dll in get_all_sanitizer_runtime_dlls():
    shutil.copy(dll, build_dir / dll.name)
```

See `BUG_ASAN.md` for detailed analysis of this issue.

### macOS ASAN Support

macOS ASAN support uses the bundled LLVM ASAN runtime with automatic deployment via `--deploy-dependencies`.

### Dynamically Loaded Libraries

See README.md "Dynamically Loaded Libraries" section for user-facing documentation on fixing `<unknown module>` in ASAN stack traces (dlopen flags, dlclose handling).

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

## Maintainer: Building IWYU Archives

When rebuilding the Windows IWYU archive, runtime DLLs must be included in the `bin/` directory for the executable to run standalone.

**Required DLLs for Windows IWYU** (copy to `downloads-bins/assets/iwyu/win/x86_64/bin/`):

| DLL | Size | Source | Purpose |
|-----|------|--------|---------|
| `libclang-cpp.dll` | ~45-57 MB | llvm-mingw | Clang C++ library |
| `libLLVM-21.dll` | ~73-136 MB | llvm-mingw | LLVM core library |
| `libgcc_s_seh-1.dll` | ~143-150 KB | mingw64 | GCC support library |
| `libstdc++-6.dll` | ~2.3-2.5 MB | mingw64 | C++ standard library |
| `libwinpthread-1.dll` | ~65 KB | mingw64/llvm-mingw | POSIX threads |
| `libffi-8.dll` | ~34-87 KB | llvm-mingw | Foreign function interface |
| `libiconv-2.dll` | ~1.1 MB | MSYS2 | Character encoding |
| `liblzma-5.dll` | ~189 KB | MSYS2 | LZMA compression |
| `libxml2-16.dll` | ~1.3 MB | MSYS2 | XML parsing |
| `libzstd.dll` | ~1.2 MB | MSYS2 | Zstd compression |
| `zlib1.dll` | ~121 KB | MSYS2 | Zlib compression |

**DLL Source Locations** (in `downloads-bins/tools/work/x86_64/`):
- `llvm-mingw-*/bin/` - LLVM DLLs (libclang-cpp.dll, libLLVM-21.dll, libffi-8.dll)
- `mingw64/bin/` - MinGW GCC runtime DLLs (libgcc_s_seh-1.dll, libstdc++-6.dll)
- MSYS2 packages for additional dependencies

**Steps to rebuild Windows IWYU archive:**
```bash
cd downloads-bins

# 1. Copy DLLs to bin/ directory (see sources above)
cp tools/work/x86_64/llvm-mingw-*/bin/libclang-cpp.dll assets/iwyu/win/x86_64/bin/
cp tools/work/x86_64/llvm-mingw-*/bin/libLLVM-21.dll assets/iwyu/win/x86_64/bin/
# ... copy remaining DLLs

# 2. Create the archive
uv run create-iwyu-archives --platform win --arch x86_64

# 3. Commit changes (DLLs tracked via Git LFS)
git add assets/iwyu/win/x86_64/
git commit -m "feat: Update Windows IWYU archive with DLL dependencies"
```

See `downloads-bins/CLAUDE.md` for complete documentation.
