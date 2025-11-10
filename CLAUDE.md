# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python package that distributes pre-built Clang/LLVM binaries for Windows, macOS, and Linux with Python wrapper executables. The package provides automatic downloading, installation, and execution of LLVM/Clang toolchain binaries with minimal configuration required.

## Version Information

| Platform | Architecture | Clang/LLVM Version |
|----------|-------------|-------------------|
| macOS    | x86_64      | 19.1.6            |
| macOS    | arm64       | 19.1.6            |
| Windows  | x86_64      | 21.1.5            |
| Linux    | x86_64      | 21.1.5            |
| Linux    | arm64       | 21.1.5            |

*Version information as of November 9, 2025*

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
├── downloads-bins/          # Git submodule for binary archives (442 MB)
│   │                        # Repository: https://github.com/zackees/clang-tool-chain-bins
│   └── assets/              # Binary assets directory
│       ├── clang/           # Clang toolchain downloads
│       │   ├── manifest.json    # Root manifest (all platforms)
│       │   ├── win/             # Windows archives and manifest
│       │   │   ├── x86_64/
│       │   │   │   ├── manifest.json
│       │   │   │   └── llvm-21.1.5-win-x86_64.tar.zst
│       │   ├── linux/           # Linux archives
│       │   └── darwin/          # macOS archives
│       └── iwyu/            # Include What You Use downloads
├── tests/                   # Unit and integration tests
│   ├── test_cli.py          # CLI command tests
│   ├── test_downloader.py   # Download/install tests
│   ├── test_build_tools.py  # Build tool tests
│   ├── test_integration.py  # End-to-end tests
│   └── test_manifest.py     # Manifest parsing tests
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
- `clang-tool-chain` → `cli:main` - Main CLI
- `clang-tool-chain-test` → `cli:test_main` - Diagnostic test suite (verifies installation)
- `clang-tool-chain-fetch` → `fetch:main` - Fetch utility
- `clang-tool-chain-paths` → `paths:main` - Path utility
- `clang-tool-chain-fetch-archive` → `downloads.fetch_and_archive:main` - Archive creation

**Build Utility:**
- `clang-tool-chain-build` → `wrapper:build_main` - Simple C/C++ build tool

**Compiler Wrappers:**
- `clang-tool-chain-c` → `wrapper:clang_main` - C compiler
- `clang-tool-chain-cpp` → `wrapper:clang_cpp_main` - C++ compiler

**sccache Integration:**
- `clang-tool-chain-sccache` → `cli:sccache_main` - Direct sccache passthrough (stats, management)
- `clang-tool-chain-sccache-c` → `cli:sccache_c_main` - sccache + C compiler
- `clang-tool-chain-sccache-cpp` → `cli:sccache_cpp_main` - sccache + C++ compiler

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

### Archive Creation Pipeline

The `clang-tool-chain-fetch-archive` command automates the complete packaging process:

```bash
# Create optimized archive for Windows x86_64
clang-tool-chain-fetch-archive --platform win --arch x86_64

# Use existing binaries (skip download)
clang-tool-chain-fetch-archive --platform win --arch x86_64 --source-dir ./assets/win
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
9. Places in `downloads-bins/assets/clang/{platform}/{arch}/` (submodule directory)

**Result:** 51.53 MB archive (from 902 MB original) for Windows x86_64

### Individual Maintainer Scripts

Available as Python modules in `clang_tool_chain.downloads`:

- `download_binaries.py`: Download LLVM releases from GitHub
- `strip_binaries.py`: Remove unnecessary files to optimize size
- `deduplicate_binaries.py`: Identify duplicate binaries by MD5 hash
- `create_hardlink_archive.py`: Create hard-linked TAR archives
- `expand_archive.py`: Extract `.tar.zst` archives
- `test_compression.py`: Compare compression methods

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
```
