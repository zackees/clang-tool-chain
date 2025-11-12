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

**Windows GNU ABI Support (v2.0.0+):**
- Windows defaults to GNU ABI (`x86_64-w64-windows-gnu`) for cross-platform consistency
- Includes MinGW-w64 sysroot (~12 MB compressed, 176 MB installed)
- Compatible with strict C++11 mode (no C++14 extensions in standard library headers)
- MSVC ABI available via `-msvc` command variants for Windows-specific projects

**Key Features:**
- Pre-built Clang/LLVM binaries (~200-400 MB per platform)
- Cross-platform support (Windows x64, macOS x64/ARM64, Linux x64/ARM64)
- Automatic toolchain download and installation on first use
- Manifest-based distribution system with checksum verification
- Python wrapper commands for all essential tools
- Ultra-compressed archives using zstd level 22 (~94% size reduction)

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

### sccache Integration (Optional)

The package provides optional sccache integration for faster compilation through caching:

**Installation:**
```bash
# Option 1: Install via pip (Python package)
pip install clang-tool-chain[sccache]

# Option 2: Install via cargo
cargo install sccache

# Option 3: System package manager
# Linux
apt install sccache        # Debian/Ubuntu
yum install sccache        # RHEL/CentOS

# macOS
brew install sccache

# Option 4: Download binary from GitHub
# https://github.com/mozilla/sccache/releases
```

**Usage:**
```bash
# Use sccache-wrapped compilers
clang-tool-chain-sccache-c main.c -o main
clang-tool-chain-sccache-cpp main.cpp -o main

# Direct sccache commands (passthrough)
clang-tool-chain-sccache --show-stats     # Check cache statistics
clang-tool-chain-sccache --zero-stats     # Clear statistics
clang-tool-chain-sccache --start-server   # Start sccache server
clang-tool-chain-sccache --stop-server    # Stop sccache server
clang-tool-chain-sccache --version        # Show sccache version
```

**How it works:**
- `clang-tool-chain-sccache` provides direct access to sccache for querying stats, managing the server, etc.
- `clang-tool-chain-sccache-c` and `clang-tool-chain-sccache-cpp` automatically invoke sccache with the clang-tool-chain compilers
- Compilation results are cached locally, speeding up repeated builds
- Requires sccache to be available in your PATH
- If sccache is not found, the commands will fail with clear installation instructions

### macOS SDK Detection (Automatic)

On macOS, system headers (like `stdio.h` and `iostream`) are NOT located in `/usr/include`. Since macOS 10.14 Mojave, Apple only provides headers through SDK bundles in Xcode or Command Line Tools. Standalone clang binaries cannot automatically find these headers without help.

**Automatic SDK Detection:**

This package implements LLVM's official three-tier SDK detection strategy (based on [LLVM patch D136315](https://reviews.llvm.org/D136315)):

1. **Explicit `-isysroot` flag**: User-provided SDK path takes priority
2. **`SDKROOT` environment variable**: Standard macOS/Xcode environment variable
3. **Automatic `xcrun --show-sdk-path`**: Fallback detection when nothing else specified

The wrapper automatically injects `-isysroot` when compiling on macOS, ensuring system headers are found without manual configuration.

**Environment Variables:**
```bash
# Disable automatic SDK detection (not recommended)
export CLANG_TOOL_CHAIN_NO_SYSROOT=1

# Use custom SDK path (standard macOS variable)
export SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk
```

**Requirements:**
- macOS users must have Xcode Command Line Tools installed: `xcode-select --install`
- SDK is automatically detected via `xcrun` - no manual configuration needed

**Behavior:**
- Automatic `-isysroot` injection is skipped when:
  - User explicitly provides `-isysroot` in arguments
  - `SDKROOT` environment variable is set
  - Freestanding compilation flags are used (`-nostdinc`, `-nostdinc++`, `-nostdlib`, `-ffreestanding`)
  - `CLANG_TOOL_CHAIN_NO_SYSROOT=1` is set

### Windows GNU ABI (Automatic, v2.0.0+)

On Windows, starting with v2.0.0, the default target is **GNU ABI** (`x86_64-w64-windows-gnu`) for cross-platform consistency.

**Automatic GNU ABI Injection:**

This package implements automatic GNU target selection for Windows (similar to [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case)):

1. **Explicit `--target` flag**: User-provided target takes priority (no injection)
2. **Windows platform detection**: Automatically uses `x86_64-w64-windows-gnu` target
3. **MinGW sysroot download**: Downloads MinGW-w64 headers/libraries on first use
4. **Automatic `--sysroot` injection**: Points to `~/.clang-tool-chain/mingw/win/x86_64/`

The wrapper automatically injects `--target=x86_64-w64-windows-gnu` and `--sysroot` when compiling on Windows, ensuring GNU-compatible standard library headers are found.

**Environment Variables:**
```bash
# Override to use MSVC ABI for specific compilations
clang-tool-chain-c --target=x86_64-pc-windows-msvc main.c

# Use MSVC variant commands (skip GNU injection entirely)
clang-tool-chain-c-msvc main.c
clang-tool-chain-cpp-msvc main.cpp
```

**Why GNU ABI is Default:**
- **Cross-platform consistency**: Same ABI on Linux/macOS/Windows
- **C++11 strict mode support**: MSVC headers require C++14 features even in C++11 mode
- **Arduino/embedded compatibility**: Matches GCC toolchain behavior
- **Modern C++ stdlib**: Uses LLVM's libc++ (same as macOS/Linux)

**MSVC ABI Variants (Windows-Specific):**
For Windows-native projects requiring MSVC compatibility:
- `clang-tool-chain-c-msvc` - Uses `x86_64-pc-windows-msvc` target
- `clang-tool-chain-cpp-msvc` - Uses MSVC STL instead of libc++
- Required for: MSVC-compiled DLLs, COM/WinRT, Windows SDK features

**Behavior:**
- Automatic GNU target injection is skipped when:
  - User explicitly provides `--target` in arguments
  - Using MSVC variant commands (`*-msvc`)
  - MinGW sysroot download or installation fails (falls back to default)

### Windows MSVC ABI (Opt-in, Windows-Specific)

The MSVC ABI variants provide explicit MSVC target configuration for Windows-native development that requires compatibility with Visual Studio-compiled code.

**Automatic MSVC Target Injection:**

This package implements automatic MSVC target selection for MSVC variant commands:

1. **Explicit `--target` flag**: User-provided target takes priority (no injection)
2. **Windows platform detection**: Automatically uses `x86_64-pc-windows-msvc` target
3. **Windows SDK detection**: Checks for Visual Studio/Windows SDK environment variables
4. **Helpful warnings**: Shows installation guidance if SDK not detected

The wrapper automatically injects `--target=x86_64-pc-windows-msvc` when using MSVC variant commands, which:
- Selects `lld-link` as the linker (MSVC-compatible)
- Uses MSVC name mangling for C++
- Relies on system Windows SDK for headers and libraries

**MSVC Variant Commands:**
```bash
# C compiler with MSVC ABI
clang-tool-chain-c-msvc main.c -o main.exe

# C++ compiler with MSVC ABI
clang-tool-chain-cpp-msvc main.cpp -o main.exe

# sccache + MSVC variants (compilation caching)
clang-tool-chain-sccache-c-msvc main.c -o main.exe
clang-tool-chain-sccache-cpp-msvc main.cpp -o main.exe
```

**When to Use MSVC ABI:**
- **Linking with MSVC-compiled libraries**: DLLs built with Visual Studio
- **Windows-specific APIs**: COM, WinRT, Windows Runtime components
- **Visual Studio integration**: Projects that must match VS build settings
- **Third-party MSVC libraries**: Libraries distributed as MSVC binaries

**When to Use GNU ABI (Default):**
- **Cross-platform code**: Same ABI on Linux/macOS/Windows
- **Strict C++11 mode**: MSVC headers require C++14 features
- **No Windows SDK**: MinGW sysroot doesn't require VS installation
- **Embedded/Arduino**: Matches GCC toolchain behavior

**Windows SDK Requirements:**

MSVC ABI compilation requires Visual Studio or Windows SDK to be installed for system headers and libraries. The package automatically detects SDK presence via environment variables:

**Detected Environment Variables:**
- `WindowsSdkDir` / `WindowsSDKDir` - Windows SDK installation path
- `UniversalCRTSdkDir` - Universal C Runtime SDK path
- `VCToolsInstallDir` - Visual C++ Tools installation path
- `VSINSTALLDIR` - Visual Studio installation directory
- `WindowsSDKVersion` - SDK version number

**If SDK Not Detected:**

When MSVC variants are used but SDK environment variables are not found, a helpful warning is displayed with solutions:

1. **Use Visual Studio Developer Command Prompt**
   - Search for "Developer Command Prompt" in Start Menu
   - Automatically sets up SDK environment variables

2. **Run vcvarsall.bat in current shell**
   - Location: `C:\Program Files\Microsoft Visual Studio\{version}\VC\Auxiliary\Build\vcvarsall.bat`
   - Run: `vcvarsall.bat x64`

3. **Install Visual Studio or Windows SDK**
   - Visual Studio: https://visualstudio.microsoft.com/downloads/
   - Windows SDK: https://developer.microsoft.com/windows/downloads/windows-sdk/

4. **Alternative: Use GNU ABI instead**
   - Use default `clang-tool-chain-c` and `clang-tool-chain-cpp` commands
   - No SDK required (uses MinGW sysroot)

**Target Override Behavior:**

MSVC variants respect user-provided `--target` flags:
```bash
# Force GNU target even with MSVC variant
clang-tool-chain-c-msvc --target=x86_64-w64-windows-gnu main.c

# Force custom target
clang-tool-chain-cpp-msvc --target=aarch64-pc-windows-msvc main.cpp
```

**Implementation Details:**

The MSVC ABI injection is implemented in `wrapper.py`:
- `_should_use_msvc_abi()` - Checks if MSVC injection should occur
- `_get_msvc_target_args()` - Returns `--target=x86_64-pc-windows-msvc`
- `_detect_windows_sdk()` - Detects SDK via environment variables
- `_print_msvc_sdk_warning()` - Shows helpful warning if SDK not found

These functions are called by:
- `execute_tool()` and `run_tool()` for direct compilation
- `sccache_clang_main()` and `sccache_clang_cpp_main()` for sccache variants

### Emscripten (WebAssembly Compilation)

This package provides Emscripten integration for compiling C/C++ to WebAssembly (WASM). Emscripten is automatically downloaded and installed on first use, similar to the LLVM toolchain.

**Key Features:**
- Pre-built Emscripten SDK (~195 MB compressed, ~1.4 GB installed)
- Automatic download and installation on first use
- WebAssembly compilation (C/C++ → .wasm + .js + .html)
- Cross-platform support (Windows x64, macOS x64/ARM64, Linux x64/ARM64)
- Manifest-based distribution with SHA256 verification
- Compatible with Node.js for running WebAssembly output

**Wrapper Commands:**
```bash
# Compile C to WebAssembly
clang-tool-chain-emcc hello.c -o hello.html

# Compile C++ to WebAssembly
clang-tool-chain-empp hello.cpp -o hello.html

# Compile to .wasm and .js (no HTML)
clang-tool-chain-empp hello.cpp -o hello.js

# With optimization
clang-tool-chain-empp -O3 hello.cpp -o hello.html
```

**What's Included:**
- Emscripten Python scripts (emcc, em++, emconfigure, emmake)
- LLVM/Clang binaries with WebAssembly backend
- Binaryen tools (wasm-opt, wasm-as, etc.)
- System libraries (libc, libc++, libcxxabi)

**Requirements:**
- **Node.js** is required to run compiled WebAssembly programs
- Install Node.js: https://nodejs.org/
- The wrapper will detect Node.js automatically and provide helpful error messages if missing

**Installation Paths:**
- Installation directory: `~/.clang-tool-chain/emscripten/{platform}/{arch}/`
- Success marker: `~/.clang-tool-chain/emscripten/{platform}/{arch}/done.txt`

**Environment Variables:**
The wrapper automatically sets required environment variables:
- `EMSCRIPTEN` - Points to Emscripten installation directory
- `EMSCRIPTEN_ROOT` - Same as above (for compatibility)

**Example Usage:**

```cpp
// hello_world.cpp
#include <iostream>

int main() {
    std::cout << "Hello, WebAssembly!" << std::endl;
    return 0;
}
```

```bash
# Compile to WebAssembly
clang-tool-chain-empp hello_world.cpp -o hello.html

# Run with Node.js
node hello.js

# Or open hello.html in a browser
```

**Output Files:**
- `hello.html` - HTML page that loads and runs the WASM module
- `hello.js` - JavaScript glue code for WASM instantiation
- `hello.wasm` - WebAssembly binary module

**Architecture:**

Emscripten integration follows the same three-layer architecture as LLVM/Clang:

1. **CLI Layer**: Management commands via `clang-tool-chain` CLI
2. **Wrapper Layer**: Entry points `emcc_main()` and `empp_main()` in `wrapper.py`
   - Platform detection (win/linux/darwin)
   - Node.js availability check
   - Environment variable setup (EMSCRIPTEN, EMSCRIPTEN_ROOT)
   - Executes Emscripten Python scripts via Python interpreter
3. **Downloader Layer**: Automatic download from GitHub
   - Fetches manifests: `downloads-bins/assets/emscripten/manifest.json`
   - Downloads `.tar.zst` archives (~195 MB)
   - Verifies SHA256 checksums
   - Extracts to `~/.clang-tool-chain/emscripten/{platform}/{arch}/`
   - File locking prevents concurrent downloads

**Key Differences from LLVM Integration:**

1. **Script-based, not binary-based**: Emscripten tools are Python scripts, not native executables
2. **Executes via Python**: Wrapper runs `python emcc.py args...` instead of direct binary execution
3. **External dependency**: Requires Node.js (not bundled)
4. **Larger size**: ~195 MB compressed vs ~52-91 MB for LLVM (includes full SDK)

**Emscripten Version:**
- Current version: 4.0.15 (Linux x86_64)
- Additional platforms (Windows, macOS) to be added in future releases

**Testing:**

```bash
# Run Emscripten tests (requires Node.js)
uv run pytest tests/test_emscripten.py -v

# Test classes:
# - TestEmscripten: Compilation and execution tests
# - TestEmscriptenDownloader: Infrastructure tests
```

**Common Issues:**

1. **Node.js not found**: Install Node.js and ensure it's in PATH
   ```bash
   # Check Node.js installation
   node --version

   # If not found, install:
   # Windows: https://nodejs.org/
   # macOS: brew install node
   # Linux: apt install nodejs (Debian/Ubuntu)
   ```

2. **First compilation is slow**: Emscripten downloads system libraries on first use
   - Subsequent compilations are faster (~2-10 seconds)
   - Cache directory: `~/.emscripten_cache/`

3. **Large output files**: WebAssembly output includes JS glue code
   - Use `-O3` optimization flag to reduce size
   - Use `--closure 1` for advanced JavaScript minification
   - Consider `-s MODULARIZE=1` for better JS integration

**Future Enhancements:**
- Windows x86_64 archive (pending)
- macOS x86_64 and ARM64 archives (pending)
- Optional Node.js bundling for portable installations
- Support for `emrun` wrapper command
- Integration with CMake via emconfigure/emmake

### Removing Toolchains
```bash
# Remove all downloaded toolchains and cached data
clang-tool-chain purge          # Interactive confirmation
clang-tool-chain purge --yes    # Skip confirmation (for scripts)

# This removes ~/.clang-tool-chain/ directory which contains:
# - LLVM/Clang binaries (~200-400 MB per platform)
# - MinGW sysroot (~176 MB uncompressed, Windows only)
# - Emscripten SDK (~1.4 GB uncompressed)
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

**Diagnostic Test Suite (`clang-tool-chain-test`):**
The test command runs 7 diagnostic tests to verify your toolchain installation:
1. Platform detection
2. Toolchain installation verification
3. clang binary resolution
4. clang++ binary resolution
5. clang version check
6. C compilation test
7. C++ compilation test

This command is especially useful for debugging installation issues in GitHub Actions or other CI/CD environments.

**Windows MSVC ABI Testing:**

The `test_msvc_compile.py` test suite provides comprehensive testing of the Windows MSVC ABI support:

**Test Coverage (15 tests):**
1. MSVC variant command availability
2. MSVC target triple injection verification
3. Basic C compilation
4. Basic C++ compilation
5. Complete C build (compile + link + execute)
6. Complete C++ build (compile + link + execute)
7. C++ STL features (vector, map, algorithms, smart pointers)
8. Multi-file compilation
9. Windows-specific headers (<windows.h>)
10. Optimization levels (-O0, -O1, -O2, -O3)
11. C++ standard versions (-std=c++11, -std=c++14, etc.)
12. User target override behavior
13. Error message reporting
14. Debug symbols (-g)
15. Warning flags (-W*)

**Requirements:**
- Windows platform (tests are skipped on other platforms)
- Visual Studio or Windows SDK installed (most tests require this)
- Tests gracefully skip if SDK not detected

**Running MSVC tests locally:**
```bash
# Requires Visual Studio Developer Command Prompt or vcvarsall.bat
# Option 1: Use Developer Command Prompt
uv run pytest tests/test_msvc_compile.py -v

# Option 2: Set up MSVC environment first
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
uv run pytest tests/test_msvc_compile.py -v
```

**GitHub Actions:**
The `.github/workflows/test-win-msvc.yml` workflow runs comprehensive MSVC tests on every push/PR:
- Uses `ilammy/msvc-dev-cmd@v1` to set up MSVC environment
- Tests all MSVC variant commands
- Verifies target triple injection
- Tests Windows API compilation
- Runs full test suite with Visual Studio SDK
- Tests multi-file projects and optimization levels

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

## Architecture

### Core Components

**Manifest-Based Distribution System:**
- Binary archives stored in separate repository as git submodule (`downloads-bins/`)
- Root manifest indexes all platforms/architectures
- Platform-specific manifests specify versions, download URLs, and SHA256 checksums
- Toolchains are distributed as `.tar.zst` archives (~52 MB for Windows x64)
- First tool execution triggers automatic download from GitHub and installation to `~/.clang-tool-chain/`
- Binary repository: https://github.com/zackees/clang-tool-chain-bins

**⚠️ Git LFS Cannot Be Used:**
- GitHub's LFS requires authentication for downloads, breaking anonymous access
- Files over 100 MB cannot be stored in regular Git repositories
- **Solution**: Large archives (>100 MB) must be split into parts (<100 MB each)
- Format: `archive-name.tar.zst.part1`, `archive-name.tar.zst.part2`, etc.
- Downloader concatenates parts before extraction
- Manifest specifies part count and individual checksums for verification

**Multi-Part Archive Support:**

For archives exceeding GitHub's 100 MB file size limit, the package implements transparent multi-part archive handling:

**Key Features:**
- Archives automatically split into <100 MB parts (default: 95 MB per part)
- Transparent to end users - downloads and extraction happen automatically
- SHA256 checksum verification for each part and final concatenated archive
- Backward compatible - single-file archives continue to work without changes
- No Git LFS required - parts stored directly in repository

**Manifest Format:**
```json
{
  "version": "4.0.15",
  "href": "https://raw.githubusercontent.com/.../archive.tar.zst",
  "sha256": "full-archive-checksum",
  "parts": [
    {
      "href": "https://raw.githubusercontent.com/.../archive.tar.zst.part1",
      "sha256": "part1-checksum"
    },
    {
      "href": "https://raw.githubusercontent.com/.../archive.tar.zst.part2",
      "sha256": "part2-checksum"
    }
  ]
}
```

**Download Flow:**
1. Downloader detects "parts" field in manifest
2. Downloads each part with individual checksum verification
3. Concatenates parts into single archive
4. Verifies final archive checksum matches "sha256" field
5. Extracts using standard `.tar.zst` extraction

**Implementation:**
- `downloader.py:is_multipart_archive()` - Detects multi-part archives
- `downloader.py:download_archive_parts()` - Downloads and concatenates parts
- `downloader.py:download_archive()` - Unified interface for both types
- All download functions (clang, mingw, emscripten, iwyu) support both formats

**Maintainer Tools:**
- `downloads-bins/tools/split_archive.py` - Splits archives into parts
- Generates SHA256 checksums for each part
- Optionally updates manifest with part information
- Usage: `python split_archive.py archive.tar.zst --part-size-mb 95`

**Use Cases:**
- Emscripten SDK (~195 MB) → 3 parts (~95 MB, ~95 MB, ~5 MB)
- Future LLVM releases if they exceed 100 MB
- Any toolchain archive that cannot be stored in regular Git

**Three-Layer Architecture:**

1. **CLI Layer** (`cli.py`): Main entry point providing management commands
   - `info`: Display installation information and available tools
   - `version <tool>`: Show version of a specific tool
   - `list-tools`: List all wrapper commands
   - `path [tool]`: Show binary directory or tool path
   - `package-version`: Display package and LLVM versions

2. **Wrapper Layer** (`wrapper.py`): Core tool execution infrastructure
   - Platform detection: Automatically detects OS (win/linux/darwin) and architecture (x86_64/arm64)
   - Binary resolution: Finds tool binaries with platform-specific extensions
   - Process execution: Uses `os.execv` on Unix, `subprocess.run` on Windows
   - Provides 14 wrapper entry points (clang, clang++, lld, llvm-ar, llvm-nm, etc.)

3. **Downloader Layer** (`downloader.py`): Automatic toolchain installation
   - Fetches manifests from clang-tool-chain-bins repository on GitHub
   - Downloads archives with checksum verification (SHA256)
   - Extracts `.tar.zst` archives using pyzstd decompression
   - Uses file locking (`fasteners.InterProcessLock`) to prevent concurrent downloads
   - Installation path: `~/.clang-tool-chain/clang/<platform>/<arch>/`
   - MinGW sysroot path: `~/.clang-tool-chain/mingw/win/x86_64/` (Windows only)
   - Marks successful installation with `done.txt` file

### Directory Structure
```
clang-tool-chain/
├── src/clang_tool_chain/
│   ├── cli.py               # Main CLI commands (info, version, list-tools, path)
│   ├── wrapper.py           # Tool execution wrappers and entry points
│   ├── downloader.py        # Automatic download/install from manifests
│   ├── checksums.py         # Checksum database for LLVM releases
│   ├── fetch.py             # Fetch utility command
│   ├── paths.py             # Path utility command
│   ├── downloads/           # Maintainer tools for packaging
│   │   ├── fetch_and_archive.py    # Complete packaging pipeline
│   │   ├── download_binaries.py    # Download LLVM releases
│   │   ├── strip_binaries.py       # Optimize binary size
│   │   ├── deduplicate_binaries.py # Find duplicate binaries
│   │   ├── create_hardlink_archive.py # Create hardlinked tarballs
│   │   ├── expand_archive.py       # Extract .tar.zst archives
│   │   └── test_compression.py     # Test compression methods
│   └── __version__.py       # Version information
├── downloads-bins/          # Git submodule with pre-built archives and manifests
│   └── assets/              # Published binary distributions
│       ├── clang/           # Clang toolchain archives
│       │   ├── manifest.json    # Root manifest (all platforms)
│       │   ├── win/         # Windows archives and manifest
│       │   │   ├── x86_64/
│       │   │   │   ├── manifest.json
│       │   │   │   └── llvm-21.1.5-win-x86_64.tar.zst
│       │   ├── linux/       # Linux archives
│       │   └── darwin/      # macOS archives
│       ├── mingw/           # MinGW-w64 sysroot archives (Windows GNU ABI)
│       │   ├── manifest.json    # Root manifest
│       │   ├── README.md    # MinGW sysroot documentation
│       │   └── win/         # Windows MinGW sysroots
│       │       └── x86_64/
│       │           ├── manifest.json
│       │           └── mingw-sysroot-21.1.5-win-x86_64.tar.zst
│       └── iwyu/            # Include What You Use archives
├── tests/                   # Unit and integration tests
│   ├── test_cli.py          # CLI command tests
│   ├── test_downloader.py   # Download/install tests
│   ├── test_build_tools.py  # Build tool tests
│   ├── test_integration.py  # End-to-end tests
│   ├── test_manifest.py     # Manifest parsing tests
│   └── test_gnu_abi.py      # Windows GNU ABI tests (TASK.md scenarios)
├── pyproject.toml           # Package configuration
└── .pre-commit-config.yaml  # Pre-commit hooks
```

### Platform Detection and Binary Resolution

The wrapper system (`wrapper.py`) performs automatic platform detection:

1. **Platform normalization:**
   - Windows → "win"
   - Linux → "linux"
   - macOS (Darwin) → "darwin"

2. **Architecture normalization:**
   - x86_64, amd64 → "x86_64"
   - aarch64, arm64 → "arm64"

3. **Binary location:** `~/.clang-tool-chain/clang/<platform>/<arch>/bin/`

4. **Tool resolution:**
   - Adds `.exe` extension on Windows
   - Handles alternative names (e.g., `lld` → `lld-link` on Windows)
   - Provides detailed error messages with available tools list

### Automatic Download Flow

When a wrapper command is executed for the first time:

1. Check if toolchain is installed (`done.txt` exists)
2. If not installed, acquire file lock (`~/.clang-tool-chain/<platform>-<arch>.lock`)
3. Double-check installation (another process may have finished)
4. Fetch root manifest from GitHub
5. Fetch platform-specific manifest
6. Download archive to temp directory with checksum verification
7. Extract using pyzstd decompression + tarfile
8. Write `done.txt` to mark completion
9. Release lock and execute tool

### Environment Variables

- **`CLANG_TOOL_CHAIN_DOWNLOAD_PATH`**: Override default download location (`~/.clang-tool-chain`)
  - Useful for testing, shared installations, or network drives

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

## Entry Points and Wrapper Commands

The package provides these entry points (defined in `pyproject.toml`):

**Management Commands:**
- `clang-tool-chain` → `cli:main` - Main CLI (subcommands: info, version, list-tools, path, package-version, test, purge)
- `clang-tool-chain-test` → `cli:test_main` - Diagnostic test suite (verifies installation)
- `clang-tool-chain-fetch` → `fetch:main` - Fetch utility
- `clang-tool-chain-paths` → `paths:main` - Path utility
- `clang-tool-chain-fetch-archive` → `downloads.fetch_and_archive:main` - Archive creation

**Build Utility:**
- `clang-tool-chain-build` → `wrapper:build_main` - Simple C/C++ build tool

**Compiler Wrappers:**
- `clang-tool-chain-c` → `wrapper:clang_main` - C compiler (GNU ABI on Windows)
- `clang-tool-chain-cpp` → `wrapper:clang_cpp_main` - C++ compiler (GNU ABI on Windows)
- `clang-tool-chain-c-msvc` → `wrapper:clang_msvc_main` - C compiler (MSVC ABI, Windows only)
- `clang-tool-chain-cpp-msvc` → `wrapper:clang_cpp_msvc_main` - C++ compiler (MSVC ABI, Windows only)

**sccache Integration:**
- `clang-tool-chain-sccache` → `cli:sccache_main` - Direct sccache passthrough (stats, management)
- `clang-tool-chain-sccache-c` → `cli:sccache_c_main` - sccache + C compiler (GNU ABI on Windows)
- `clang-tool-chain-sccache-cpp` → `cli:sccache_cpp_main` - sccache + C++ compiler (GNU ABI on Windows)
- `clang-tool-chain-sccache-c-msvc` → `cli:sccache_c_msvc_main` - sccache + C compiler (MSVC ABI, Windows only)
- `clang-tool-chain-sccache-cpp-msvc` → `cli:sccache_cpp_msvc_main` - sccache + C++ compiler (MSVC ABI, Windows only)

**Linker and Archiver:**
- `clang-tool-chain-ld` → `wrapper:lld_main` - Linker (lld/lld-link)
- `clang-tool-chain-ar` → `wrapper:llvm_ar_main` - Archive tool

**Binary Utilities:**
- `clang-tool-chain-nm` → `wrapper:llvm_nm_main` - Symbol viewer
- `clang-tool-chain-objdump` → `wrapper:llvm_objdump_main` - Object dumper
- `clang-tool-chain-objcopy` → `wrapper:llvm_objcopy_main` - Object copy
- `clang-tool-chain-ranlib` → `wrapper:llvm_ranlib_main` - Archive index
- `clang-tool-chain-strip` → `wrapper:llvm_strip_main` - Symbol stripper
- `clang-tool-chain-readelf` → `wrapper:llvm_readelf_main` - ELF reader

**Additional Tools:**
- `clang-tool-chain-as` → `wrapper:llvm_as_main` - LLVM assembler
- `clang-tool-chain-dis` → `wrapper:llvm_dis_main` - LLVM disassembler
- `clang-tool-chain-format` → `wrapper:clang_format_main` - Code formatter
- `clang-tool-chain-tidy` → `wrapper:clang_tidy_main` - Static analyzer

## Maintainer Tools

Maintainer scripts for creating binary archives are located in the **submodule** at `downloads-bins/tools/`. This keeps the main repository lightweight and separates binary distribution tooling from the package code.

**Setup:**
```bash
# Initialize the submodule (first time only)
git submodule init
git submodule update

# Navigate to tools directory
cd downloads-bins/tools
```

### Archive Creation Pipeline

The `fetch_and_archive.py` script automates the complete packaging process:

```bash
# Create optimized archive for Windows x86_64
cd downloads-bins/tools
python fetch_and_archive.py --platform win --arch x86_64

# Use existing binaries (skip download)
python fetch_and_archive.py --platform win --arch x86_64 --source-dir ./extracted
```

**What it does:**
1. Downloads LLVM from GitHub (or uses `--source-dir`)
2. Extracts archive
3. Strips unnecessary files (docs, examples, static libs)
4. Deduplicates identical binaries (~571 MB savings)
5. Creates hard-linked structure
6. Compresses with zstd level 22 (94.3% reduction)
7. Generates checksums (SHA256, MD5)
8. Names archive: `llvm-{version}-{platform}-{arch}.tar.zst`
9. Places in `../assets/clang/{platform}/{arch}/`

**Requirements:**
```bash
pip install zstandard
```

**Result:** 51.53 MB archive (from 902 MB original) for Windows x86_64

### Individual Maintainer Scripts

Located in `downloads-bins/tools/`:

- `fetch_and_archive.py`: Complete pipeline for LLVM toolchain archives
- `extract_mingw_sysroot.py`: Extract MinGW-w64 sysroot for Windows GNU ABI
- `download_binaries.py`: Download LLVM releases from GitHub
- `strip_binaries.py`: Remove unnecessary files to optimize size
- `deduplicate_binaries.py`: Identify duplicate binaries by MD5 hash
- `create_hardlink_archive.py`: Create hard-linked TAR archives
- `expand_archive.py`: Extract `.tar.zst` archives
- `test_compression.py`: Compare compression methods
- `create_iwyu_archives.py`: Create include-what-you-use archives

See `downloads-bins/tools/README.md` for detailed documentation.

### MinGW Sysroot Generation (Windows GNU ABI)

The `extract_mingw_sysroot.py` script creates MinGW-w64 sysroot archives:

```bash
# Generate MinGW sysroot archive for Windows x86_64
cd downloads-bins/tools
python extract_mingw_sysroot.py --arch x86_64 --work-dir work
```

**What it does:**
1. Downloads LLVM-MinGW release from GitHub (mstorsjo/llvm-mingw)
2. Extracts only the sysroot directory (x86_64-w64-mingw32)
3. Includes C/C++ standard library headers (libc++ from LLVM)
4. Compresses with zstd level 22 (~93% reduction)
5. Generates checksums (SHA256, MD5)
6. Creates manifest.json
7. Names archive: `mingw-sysroot-{version}-win-{arch}.tar.zst`
8. Places in `../assets/mingw/win/{arch}/`

**Result:** ~12 MB archive (from 176 MB uncompressed) for Windows x86_64

### Updating Binary Payloads

Binary archives are stored in a separate repository as a git submodule to keep the main repository lightweight. This architecture reduces main repo clone size from ~450 MB to ~20 MB.

**First-time setup (for maintainers):**
```bash
# Initialize and update the submodule
git submodule init
git submodule update
```

**Adding new binaries:**
```bash
# Navigate to the submodule directory
cd downloads-bins

# Add new archive to appropriate location
# Example: cp new-binary.tar.zst clang/win/x86_64/

# Update the manifest.json with new version info
# Edit clang/win/x86_64/manifest.json to add:
# - version number
# - href URL (pointing to clang-tool-chain-bins repo)
# - sha256 checksum

# Commit and push to the bins repository
git add .
git commit -m "Add LLVM version X.Y.Z for win/x86_64"
git push origin main

# Return to main repository
cd ..

# Update the submodule reference in main repo
git add downloads-bins
git commit -m "Update submodule to latest binaries (version X.Y.Z)"
git push origin main
```

**Binary URL pattern:**
```
https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/{platform}/{arch}/llvm-{version}-{platform}-{arch}.tar.zst
```

**Important notes:**
- End users do NOT need the submodule - binaries are downloaded automatically from GitHub
- The submodule is only needed for maintainers who update binary distributions
- Manifest URLs in the bins repository must point to `clang-tool-chain-bins`, not `clang-tool-chain`
- Always update SHA256 checksums when adding new binaries

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

**Windows GNU ABI Test Coverage:**
- `test_gnu_abi.py` - Complete TASK.md scenarios (10 test cases)
  - Basic C++11 standard library headers with GNU target
  - C++11 code with MSVC headers (should fail)
  - Complete compilation and linking
  - Target triple verification
  - Default GNU ABI behavior on Windows
  - Explicit target override
  - MSVC variant commands
- `test_cli.py` - Windows GNU default detection
- `test_downloader.py` - MinGW sysroot download infrastructure (8 test cases)

## Troubleshooting Binary Dependencies (DLLs and .so files)

### Missing DLL/Shared Library Issues

If binaries in the distributed archives fail with errors like "command not found" (exit code 127) or access violations (0xC0000005), they may be missing DLL/.so file dependencies.

**Diagnostic Steps:**

1. **Check for missing dependencies** (Linux/MSYS2):
   ```bash
   ldd path/to/binary
   # Look for "=> not found" entries
   ```

2. **Check for missing dependencies** (Windows cmd):
   ```cmd
   dumpbin /dependents path\to\binary.exe
   ```

3. **Check for missing dependencies** (macOS):
   ```bash
   otool -L path/to/binary
   # Look for libraries not found in standard paths
   ```

**Repacking Archives with Missing Dependencies:**

If you identify missing DLLs or .so files:

1. **Locate the required dependencies**:
   - For LLVM/Clang tools: Download from llvm-mingw, official LLVM releases, or system package managers
   - Verify version compatibility (same LLVM major version)
   - Example for LLVM 21.x on Windows:
     ```bash
     # Download llvm-mingw distribution
     wget https://github.com/mstorsjo/llvm-mingw/releases/download/20251104/llvm-mingw-20251104-msvcrt-x86_64.zip
     unzip llvm-mingw-*.zip

     # Find required DLLs
     find llvm-mingw-* -name "libLLVM-21.dll" -o -name "libclang-cpp.dll"
     ```

2. **Extract the current archive**:
   ```bash
   cd /tmp/repack_work
   python ~/dev/clang-tool-chain/downloads-bins/tools/expand_archive.py \
     ~/dev/clang-tool-chain/downloads-bins/assets/{tool}/{platform}/{arch}/{archive}.tar.zst \
     extracted/
   ```

3. **Add missing dependencies**:
   ```bash
   # Copy DLLs/.so files to the bin directory
   cp path/to/required/*.dll extracted/bin/

   # Verify all dependencies are resolved
   ldd extracted/bin/your-binary.exe  # Should show no "not found" entries
   ```

4. **Test the binary with dependencies**:
   ```bash
   cd extracted/bin
   ./your-binary.exe --version  # Should not crash
   ```

5. **Repackage the archive**:
   ```python
   # Create tar archive
   import tarfile
   from pathlib import Path

   def tar_filter(tarinfo):
       if tarinfo.isfile() and ('/bin/' in tarinfo.name or tarinfo.name.startswith('bin/')):
           if tarinfo.name.endswith(('.py', '.exe', '.dll', '.so')):
               tarinfo.mode = 0o755  # Executable
           else:
               tarinfo.mode = 0o644  # Readable
       return tarinfo

   with tarfile.open('new-archive.tar', 'w') as tar:
       tar.add('extracted/bin', arcname='bin', filter=tar_filter)
       tar.add('extracted/share', arcname='share', filter=tar_filter)
   ```

6. **Compress with zstd**:
   ```python
   import zstandard as zstd

   cctx = zstd.ZstdCompressor(level=22, threads=-1)
   with open('new-archive.tar', 'rb') as ifh, open('new-archive.tar.zst', 'wb') as ofh:
       reader = cctx.stream_reader(ifh, size=Path('new-archive.tar').stat().st_size)
       while True:
           chunk = reader.read(1024 * 1024)
           if not chunk:
               break
           ofh.write(chunk)
   ```

7. **Generate checksum and update manifest**:
   ```python
   import hashlib

   sha256_hash = hashlib.sha256()
   with open('new-archive.tar.zst', 'rb') as f:
       for byte_block in iter(lambda: f.read(4096), b''):
           sha256_hash.update(byte_block)

   checksum = sha256_hash.hexdigest()
   print(f'SHA256: {checksum}')

   # Update downloads-bins/assets/{tool}/{platform}/{arch}/manifest.json
   # Replace the sha256 field with the new checksum
   ```

8. **Test the new archive**:
   ```bash
   # Remove old installation
   rm -rf ~/.clang-tool-chain/{tool}/

   # Copy new archive to downloads-bins location
   cp new-archive.tar.zst ~/dev/clang-tool-chain/downloads-bins/assets/{tool}/{platform}/{arch}/

   # Run tests to verify
   uv run pytest tests/test_{tool}.py -v
   ```

**Important Caveats:**

⚠️ **Binary Compatibility Warning**: Adding DLLs from different sources can cause compatibility issues:

- **Version mismatches**: DLLs must match the LLVM version used to build the binary
- **Compiler differences**: Binaries built with GCC may not work with MSVC-compiled DLLs
- **ABI incompatibilities**: Different C++ standard library implementations (libc++ vs libstdc++ vs MSVC STL)
- **Runtime errors**: May crash with BAD_INITIAL_STACK (0xC0000009) or other memory errors

**If bundling DLLs fails**, consider these alternatives:

1. **Rebuild from source with static linking** (recommended for long-term stability):
   - Download tool source code
   - Build against LLVM with `-static` linker flags
   - Results in larger binary but no external dependencies
   - Example CMake flags: `-DCMAKE_EXE_LINKER_FLAGS="-static-libgcc -static-libstdc++ -static"`

2. **Use system package managers**:
   - Document that users need to install LLVM/Clang development packages
   - MSYS2: `pacman -S mingw-w64-x86_64-llvm`
   - Debian/Ubuntu: `apt install llvm-dev libclang-dev`
   - macOS: `brew install llvm`

3. **Skip functionality on affected platforms**:
   - Add `@pytest.mark.skipif` decorators for platform-specific tests
   - Document limitation in README and error messages
   - Provide workarounds (WSL, Docker, alternative tools)

**See Also:**
- `IWYU_FIX_RECOMMENDATION.md` - Case study of IWYU Windows DLL bundling attempt and lessons learned
- `downloads-bins/tools/README.md` - Maintainer tools documentation
- `downloads-bins/tools/expand_archive.py` - Archive extraction tool
- `downloads-bins/tools/create_iwyu_archives.py` - Example archive creation script
