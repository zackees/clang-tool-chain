# Clang Tool Chain

**A zero-configuration Python package that distributes pre-built Clang/LLVM binaries with automatic downloading and installation.**

[![PyPI version](https://img.shields.io/pypi/v/clang-tool-chain.svg)](https://pypi.org/project/clang-tool-chain/)
[![Linting](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml)
[![win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-win.yml)
[![linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-linux-x86.yml)
[![linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-linux-arm.yml)
[![macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-macos-x86.yml)
[![macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-macos-arm.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## ⚡ Quick Start

Get compiling in 30 seconds:

```bash
# Install the package
pip install clang-tool-chain

# Compile C code - binaries download automatically on first use!
echo 'int main() { return 0; }' > hello.c
clang-tool-chain-c hello.c -o hello
./hello  # Windows: .\hello.exe
```

**That's it!** The LLVM toolchain (~52-91 MB) downloads automatically on first use. No manual setup required.

---

## 🎯 Why clang-tool-chain?

### The Problem

Installing LLVM/Clang traditionally requires:
- Large downloads (1-3 GB installer/archive)
- System-wide installation with admin privileges
- Manual PATH configuration
- Platform-specific installation procedures
- Version management headaches in CI/CD

### The Solution

`clang-tool-chain` provides:

| Feature | clang-tool-chain | Full LLVM Install | System Compiler | Docker Image |
|---------|------------------|-------------------|-----------------|--------------|
| **Size** | 52-91 MB | 1-3 GB | Varies | 500+ MB |
| **Setup Time** | < 30 seconds | 5-15 minutes | Varies | 1-5 minutes |
| **Admin Required** | ❌ No | ✅ Yes (usually) | ✅ Yes | ✅ Yes |
| **Auto Download** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **Version Control** | ✅ Pin in requirements | ❌ System-wide | ❌ System-wide | ✅ Dockerfile |
| **Cross-Platform** | ✅ Identical on all OS | ❌ Different procedures | ❌ Different versions | ✅ Yes |
| **CI/CD Ready** | ✅ Zero config | ❌ Complex setup | ⚠️ Depends on runner | ⚠️ Slow builds |
| **Offline After DL** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Python Integration** | ✅ Native | ❌ Manual | ❌ Manual | ⚠️ Extra layer |

### Perfect For

- **CI/CD Pipelines** - Reproducible builds with pinned toolchain versions
- **Educational Environments** - Students get started instantly without installation hassles
- **Cross-Compilation** - Consistent toolchain across development machines
- **Containerized Builds** - Minimal Docker image overhead
- **Development Teams** - Everyone uses the exact same compiler version
- **Embedded Development** - Lightweight toolchain for resource-constrained workflows

---

## ✨ Features

- **🚀 Automatic Download on First Use** - Zero-configuration installation to `~/.clang-tool-chain/`
- **🔒 Manifest-Based Distribution** - Version-controlled releases with SHA256 checksum verification
- **⚡ Ultra-Compressed Archives** - 94.3% size reduction using zstd level 22 compression
- **🌍 Cross-Platform Support** - Windows x64, macOS x64/ARM64, Linux x64/ARM64
- **🛡️ Concurrent-Safe Installation** - File locking prevents race conditions in parallel builds
- **🐍 Python Wrapper Commands** - 22 entry points for all essential LLVM tools
- **📦 Pre-Built Binaries** - Clang 21.1.5 (Linux/Windows), 19.1.7 (macOS)
- **🔧 Essential Toolchain Utilities** - Compilers, linkers, binary utilities, and code formatters

---

## 🔧 How It Works

### Architecture Overview

`clang-tool-chain` uses a sophisticated three-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Layer (cli.py)                        │
│  Commands: info, version, list-tools, path, package-version  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                 Wrapper Layer (wrapper.py)                   │
│  • Platform Detection (win/linux/darwin)                     │
│  • Architecture Normalization (x86_64/arm64)                 │
│  • Binary Resolution (.exe handling, tool alternatives)      │
│  • Process Execution (os.execv on Unix, subprocess on Win)   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Downloader Layer (downloader.py)                │
│  • Fetch root manifest from GitHub                          │
│  • Fetch platform-specific manifest                         │
│  • Download .tar.zst archive with progress                  │
│  • Verify SHA256 checksum                                   │
│  • Extract with pyzstd decompression                        │
│  • File locking (prevents concurrent downloads)             │
│  • Atomic installation with 'done.txt' marker               │
└─────────────────────────────────────────────────────────────┘
```

### Manifest-Based Distribution System

The package uses a **two-tier manifest system** for version management:

1. **Root Manifest** (`downloads/clang/manifest.json`) - Indexes all platforms and architectures
2. **Platform Manifests** (`downloads/clang/{platform}/{arch}/manifest.json`) - Contains version info, download URLs, and SHA256 checksums

**On first use:**
```
User runs: clang-tool-chain-c hello.c -o hello
    ↓
Check: ~/.clang-tool-chain/{platform}/{arch}/done.txt exists?
    ↓ (No)
Acquire lock: ~/.clang-tool-chain/{platform}-{arch}.lock
    ↓
Fetch: Root manifest → Platform manifest
    ↓
Download: .tar.zst archive to temp directory
    ↓
Verify: SHA256 checksum
    ↓
Extract: Using pyzstd + tarfile (with safety filters)
    ↓
Mark complete: Write done.txt
    ↓
Release lock → Execute tool
```

### Platform Detection

Automatic platform and architecture detection:

| System | Platform | Architecture | Install Path |
|--------|----------|--------------|--------------|
| Windows 10+ | `win` | `x86_64` | `~/.clang-tool-chain/clang/win/x86_64/` |
| Linux | `linux` | `x86_64` | `~/.clang-tool-chain/clang/linux/x86_64/` |
| Linux | `linux` | `arm64` | `~/.clang-tool-chain/clang/linux/arm64/` |
| macOS | `darwin` | `x86_64` | `~/.clang-tool-chain/clang/darwin/x86_64/` |
| macOS | `darwin` | `arm64` | `~/.clang-tool-chain/clang/darwin/arm64/` |

### Binary Resolution

The wrapper automatically handles platform differences:
- **Windows**: Adds `.exe` extension, uses `lld-link` instead of `lld`
- **Unix**: Uses `lld` or `ld.lld`, handles `chmod +x` permissions
- **Alternative Names**: Supports tool aliases (e.g., `clang` → `clang-cl` on Windows)

---

## 📦 Installation

### From PyPI (Recommended)

```bash
pip install clang-tool-chain
```

### From Source

```bash
# Clone the repository
git clone https://github.com/zackees/clang-tool-chain.git
cd clang-tool-chain

# Install dependencies
./install

# Or manually with uv
uv venv --python 3.11
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

**Note:** Binaries download automatically on first use. No manual setup required!

---

## 🚀 Usage

### CLI Commands

Manage your toolchain installation:

```bash
# Show installation information and available tools
clang-tool-chain info

# List all available wrapper commands
clang-tool-chain list-tools

# Show version of a specific tool
clang-tool-chain version clang
clang-tool-chain version clang++

# Show path to binaries directory
clang-tool-chain path

# Show path to specific tool
clang-tool-chain path clang

# Show package and LLVM versions
clang-tool-chain package-version
```

### Wrapper Commands

#### Compiling C Code

```bash
# Simple compilation
clang-tool-chain-c hello.c -o hello

# With optimization
clang-tool-chain-c -O2 hello.c -o hello

# With debugging symbols
clang-tool-chain-c -g hello.c -o hello

# Check version
clang-tool-chain-c --version
```

#### Compiling C++ Code

```bash
# Simple compilation
clang-tool-chain-cpp hello.cpp -o hello

# With C++20 standard
clang-tool-chain-cpp -std=c++20 hello.cpp -o hello

# With optimization and warnings
clang-tool-chain-cpp -O3 -Wall -Wextra hello.cpp -o hello

# Check version
clang-tool-chain-cpp --version
```

#### Using the Build Utility

The `clang-tool-chain-build` command provides a simple way to compile projects:

```bash
# Build a single C file
clang-tool-chain-build hello.c

# Build a C++ file with custom output name
clang-tool-chain-build hello.cpp -o myprogram

# Build with optimization
clang-tool-chain-build -O2 hello.c
```

#### Linking

```bash
# Link object files
clang-tool-chain-ld obj1.o obj2.o -o program

# Create shared library (Linux/macOS)
clang-tool-chain-ld -shared obj1.o obj2.o -o libmylib.so

# Create DLL (Windows)
clang-tool-chain-ld -shared obj1.o obj2.o -o mylib.dll
```

#### Binary Utilities

```bash
# Create static library
clang-tool-chain-ar rcs libmylib.a obj1.o obj2.o

# List symbols in binary
clang-tool-chain-nm program

# List symbols in library
clang-tool-chain-nm libmylib.a

# Disassemble binary
clang-tool-chain-objdump -d program

# Show all headers
clang-tool-chain-objdump -x program

# Strip debug symbols
clang-tool-chain-strip program -o program.stripped

# Copy and modify object files
clang-tool-chain-objcopy --strip-debug program program.stripped

# Generate archive index
clang-tool-chain-ranlib libmylib.a

# Read ELF headers (Linux)
clang-tool-chain-readelf -h program

# Show program headers
clang-tool-chain-readelf -l program
```

#### Code Formatting and Analysis

```bash
# Format C/C++ code (in-place)
clang-tool-chain-format -i myfile.cpp

# Format with specific style
clang-tool-chain-format -i -style=LLVM myfile.cpp

# Check formatting (don't modify)
clang-tool-chain-format myfile.cpp

# Run static analysis
clang-tool-chain-tidy myfile.cpp -- -std=c++17

# Run with specific checks
clang-tool-chain-tidy -checks='-*,readability-*' myfile.cpp --
```

#### sccache Integration (Optional)

Speed up repeated builds with compilation caching:

```bash
# Install with sccache support
pip install clang-tool-chain[sccache]
# Or: cargo install sccache

# Compile with sccache caching
clang-tool-chain-sccache-c main.c -o main
clang-tool-chain-sccache-cpp main.cpp -o main

# Query cache statistics
clang-tool-chain-sccache --show-stats

# Clear cache statistics
clang-tool-chain-sccache --zero-stats

# Manage sccache server
clang-tool-chain-sccache --start-server
clang-tool-chain-sccache --stop-server
clang-tool-chain-sccache --version
```

**How it works:**
- Caches compilation results locally for faster rebuilds
- Transparent caching layer on top of clang
- Requires `sccache` binary in PATH
- Works with distributed caching backends (optional)

### All Available Commands

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain` | CLI | Main management interface |
| `clang-tool-chain-fetch` | Fetch utility | Manual download utility for pre-fetching binaries |
| `clang-tool-chain-paths` | Path utility | Get installation paths in JSON format |
| `clang-tool-chain-fetch-archive` | Archive utility | Maintainer tool for creating optimized archives |
| `clang-tool-chain-c` | `clang` | C compiler |
| `clang-tool-chain-cpp` | `clang++` | C++ compiler |
| `clang-tool-chain-build` | Build utility | Simple build tool for C/C++ |
| `clang-tool-chain-sccache` | `sccache` | Direct sccache access (stats, management) |
| `clang-tool-chain-sccache-c` | `sccache` + `clang` | C compiler with sccache caching |
| `clang-tool-chain-sccache-cpp` | `sccache` + `clang++` | C++ compiler with sccache caching |
| `clang-tool-chain-ld` | `lld` / `lld-link` | LLVM linker |
| `clang-tool-chain-ar` | `llvm-ar` | Archive/library creator |
| `clang-tool-chain-nm` | `llvm-nm` | Symbol table viewer |
| `clang-tool-chain-objdump` | `llvm-objdump` | Object file dumper/disassembler |
| `clang-tool-chain-objcopy` | `llvm-objcopy` | Object file copier/modifier |
| `clang-tool-chain-ranlib` | `llvm-ranlib` | Archive index generator |
| `clang-tool-chain-strip` | `llvm-strip` | Symbol stripper |
| `clang-tool-chain-readelf` | `llvm-readelf` | ELF file reader |
| `clang-tool-chain-as` | `llvm-as` | LLVM assembler |
| `clang-tool-chain-dis` | `llvm-dis` | LLVM disassembler |
| `clang-tool-chain-format` | `clang-format` | Code formatter |
| `clang-tool-chain-tidy` | `clang-tidy` | Static analyzer/linter |

---

## 📚 Examples

### Hello World (C)

```c
// hello.c
#include <stdio.h>

int main() {
    printf("Hello from clang-tool-chain!\n");
    return 0;
}
```

```bash
clang-tool-chain-c hello.c -o hello
./hello
```

### Hello World (C++)

```cpp
// hello.cpp
#include <iostream>

int main() {
    std::cout << "Hello from clang-tool-chain!" << std::endl;
    return 0;
}
```

```bash
clang-tool-chain-cpp hello.cpp -o hello
./hello
```

### Multi-File Compilation

```c
// math_ops.h
#ifndef MATH_OPS_H
#define MATH_OPS_H
int add(int a, int b);
int multiply(int a, int b);
#endif

// math_ops.c
#include "math_ops.h"
int add(int a, int b) { return a + b; }
int multiply(int a, int b) { return a * b; }

// main.c
#include <stdio.h>
#include "math_ops.h"

int main() {
    printf("5 + 3 = %d\n", add(5, 3));
    printf("5 * 3 = %d\n", multiply(5, 3));
    return 0;
}
```

```bash
# Compile and link in one step
clang-tool-chain-c main.c math_ops.c -o program
./program

# Or compile separately then link
clang-tool-chain-c -c math_ops.c -o math_ops.o
clang-tool-chain-c -c main.c -o main.o
clang-tool-chain-c main.o math_ops.o -o program
./program
```

### Creating a Static Library

```bash
# Compile source files to object files
clang-tool-chain-c -c math_ops.c -o math_ops.o
clang-tool-chain-c -c string_ops.c -o string_ops.o

# Create static library
clang-tool-chain-ar rcs libmylib.a math_ops.o string_ops.o

# Generate archive index (optional but recommended)
clang-tool-chain-ranlib libmylib.a

# Link against the library
clang-tool-chain-c main.c -L. -lmylib -o program
./program
```

### Cross-Platform Build Script

```bash
#!/bin/bash
# build.sh - Cross-platform build script

set -e

# Compile
echo "Compiling..."
clang-tool-chain-c -O2 -Wall -Wextra src/*.c -o myprogram

# Strip symbols for release
echo "Stripping symbols..."
clang-tool-chain-strip myprogram -o myprogram.release

echo "Build complete: myprogram.release"
```

---

## 🚀 CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/build.yml
name: Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install clang-tool-chain
        run: pip install clang-tool-chain

      - name: Compile project
        run: |
          clang-tool-chain-c src/main.c -o program
          ./program  # Binaries download automatically on first use!

      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: program-${{ matrix.os }}
          path: program*
```

### GitLab CI

```yaml
# .gitlab-ci.yml
image: python:3.11

stages:
  - build
  - test

build:
  stage: build
  script:
    - pip install clang-tool-chain
    - clang-tool-chain-c src/main.c -o program  # Auto-downloads on first use
    - clang-tool-chain-strip program
  artifacts:
    paths:
      - program

test:
  stage: test
  script:
    - ./program
```

### Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install clang-tool-chain
RUN pip install clang-tool-chain

# Pre-download binaries (optional - they auto-download on first use)
RUN clang-tool-chain info || true

# Copy source code
COPY src/ /app/src/
WORKDIR /app

# Build
RUN clang-tool-chain-c src/main.c -o program

CMD ["./program"]
```

**Build and run:**
```bash
docker build -t myapp .
docker run myapp
```

### Azure Pipelines

```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.11'

- script: |
    pip install clang-tool-chain
    clang-tool-chain-c src/main.c -o program
  displayName: 'Build with clang-tool-chain'

- task: PublishBuildArtifacts@1
  inputs:
    pathToPublish: 'program'
    artifactName: 'executable'
```

---

## 🌍 Platform Support Matrix

| Platform | Architecture | LLVM Version | Archive Size | Installed Size | Status |
|----------|--------------|--------------|--------------|----------------|--------|
| Windows  | x86_64       | 21.1.5       | ~52 MB       | ~200 MB        | ✅ Stable |
| Linux    | x86_64       | 21.1.5       | ~88 MB       | ~350 MB        | ✅ Stable |
| Linux    | ARM64        | 21.1.5       | ~91 MB       | ~340 MB        | ✅ Stable |
| macOS    | x86_64       | 19.1.7       | ~75 MB       | ~300 MB        | ✅ Stable |
| macOS    | ARM64        | 19.1.7       | ~71 MB       | ~285 MB        | ✅ Stable |

**Note:** macOS uses LLVM 19.1.7 due to availability of pre-built binaries. LLVM 21.1.5 support coming soon.

### Requirements

- **Python**: 3.10 or higher
- **Disk Space**: ~100 MB for archive + ~200-350 MB installed
- **Internet**: Required for initial download (works offline after installation)
- **Operating System**:
  - Windows 10+ (x64)
  - macOS 11+ (x64 or ARM64/Apple Silicon)
  - Linux with glibc 2.27+ (x64 or ARM64)

---

## ⚙️ Configuration

### Environment Variables

- **`CLANG_TOOL_CHAIN_DOWNLOAD_PATH`**: Override default installation location

  ```bash
  # Linux/macOS
  export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/custom/path
  clang-tool-chain-c hello.c -o hello

  # Windows
  set CLANG_TOOL_CHAIN_DOWNLOAD_PATH=C:\custom\path
  clang-tool-chain-c hello.c -o hello
  ```

  **Use cases:**
  - Testing different toolchain versions
  - Shared installations across projects
  - Network or cache drives
  - CI/CD artifact caching

---

## 🔧 Additional Utilities

### clang-tool-chain-fetch

Manual download utility for pre-fetching binaries:

```bash
# Fetch binaries for current platform
clang-tool-chain-fetch

# Check what would be downloaded
clang-tool-chain-fetch --dry-run
```

### clang-tool-chain-paths

Get installation paths in JSON format (useful for scripting):

```bash
# Get all paths
clang-tool-chain-paths

# Example output:
# {
#   "install_dir": "/home/user/.clang-tool-chain/clang/linux/x86_64",
#   "bin_dir": "/home/user/.clang-tool-chain/clang/linux/x86_64/bin",
#   "clang": "/home/user/.clang-tool-chain/clang/linux/x86_64/bin/clang"
# }
```

```bash
# Use in scripts
BIN_DIR=$(clang-tool-chain-paths | python -c "import sys,json; print(json.load(sys.stdin)['bin_dir'])")
echo "Binaries located at: $BIN_DIR"
```

---

## 👨‍💻 Development

### Development Setup

```bash
# Clone repository
git clone https://github.com/zackees/clang-tool-chain.git
cd clang-tool-chain

# Install dependencies (using uv - recommended)
./install

# Or manually:
uv venv --python 3.11
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
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
# Install pre-commit hooks
pre-commit install

# Run all pre-commit checks manually
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

### Building and Publishing

```bash
# Build the package
uv run python -m build

# Check the built package
twine check dist/*

# Upload to PyPI (maintainers only)
./upload_package.sh
```

---

## 🛠️ Maintainer Tools

### Archive Creation Pipeline

The `clang-tool-chain-fetch-archive` command automates the complete packaging process:

```bash
# Create optimized archive for Windows x86_64
clang-tool-chain-fetch-archive --platform win --arch x86_64

# Create archive for Linux x86_64
clang-tool-chain-fetch-archive --platform linux --arch x86_64

# Create archive for macOS ARM64 (Apple Silicon)
clang-tool-chain-fetch-archive --platform darwin --arch arm64

# Use existing extracted binaries (skip download)
clang-tool-chain-fetch-archive \
    --platform win --arch x86_64 \
    --source-dir ./assets/win
```

**What it does:**

1. ✅ Downloads LLVM 21.1.5 from official GitHub releases (~400-900 MB)
2. ✅ Extracts the archive
3. ✅ Strips unnecessary files (docs, examples, static libs)
4. ✅ Deduplicates identical binaries (~571 MB savings via MD5 hash detection)
5. ✅ Creates hard-linked structure (reduces size without data loss)
6. ✅ Compresses with **zstd level 22** (94.3% reduction!)
7. ✅ Generates checksums (SHA256, MD5)
8. ✅ Names archive: `llvm-{version}-{platform}-{arch}.tar.zst`
9. ✅ Places in `downloads/clang/{platform}/{arch}/`
10. ✅ Updates platform manifest with URLs and checksums

**Result:** 51.53 MB archive (from 902 MB original) for Windows x86_64!

### Individual Maintainer Scripts

Available as Python modules in `clang_tool_chain.downloads`:

#### download_binaries.py
Download LLVM releases from GitHub:

```bash
python -m clang_tool_chain.downloads.download_binaries \
    --platform win --arch x86_64 --version 21.1.5

# Download for current platform only
python -m clang_tool_chain.downloads.download_binaries --current-only

# Skip checksum verification (not recommended)
python -m clang_tool_chain.downloads.download_binaries --current-only --no-verify
```

#### strip_binaries.py
Optimize binary size by removing unnecessary files:

```bash
python -m clang_tool_chain.downloads.strip_binaries \
    downloads/clang+llvm-21.1.5-x86_64-pc-windows-msvc \
    output/win \
    --platform win
```

**Removes:**
- Documentation (`share/doc`, `share/man`)
- Headers and examples
- Static libraries (`*.a`, `*.lib`)
- CMake files
- Debug symbols (using `llvm-strip`)

**Keeps:**
- 14 essential binaries
- Runtime libraries (`*.so`, `*.dll`, `*.dylib`)
- License files

**Size reduction:** ~3.5 GB → ~200-400 MB per platform

#### deduplicate_binaries.py
Find duplicate binaries by MD5 hash:

```bash
python -m clang_tool_chain.downloads.deduplicate_binaries \
    downloads/clang+llvm-21.1.5-x86_64-pc-windows-msvc/bin
```

**Output:**
```
Duplicate groups found: 45
Total duplicates: 158 files
Potential space savings: 571.23 MB

Duplicate group #1 (MD5: a1b2c3d4...):
  - clang.exe (12.5 MB)
  - clang++.exe (12.5 MB)
  - clang-cl.exe (12.5 MB)
```

#### create_hardlink_archive.py
Create hard-linked TAR archives (preserves hard links during extraction):

```bash
python -m clang_tool_chain.downloads.create_hardlink_archive \
    input/win \
    output/llvm-21.1.5-win-x86_64.tar.zst \
    --compression-level 22
```

**Benefits:**
- Preserves hard links (deduplication survives extraction)
- Ultra-high compression (zstd level 22)
- Maintains file permissions and metadata

#### expand_archive.py
Extract `.tar.zst` archives:

```bash
python -m clang_tool_chain.downloads.expand_archive \
    downloads/llvm-21.1.5-win-x86_64.tar.zst \
    output/win
```

**Features:**
- Handles zstd compression
- Preserves hard links
- Shows extraction progress
- Validates archive integrity

#### test_compression.py
Compare compression methods and levels:

```bash
python -m clang_tool_chain.downloads.test_compression \
    input/win \
    --methods zstd gzip xz \
    --levels 1 9 22
```

**Output:**
```
Testing compression methods...

zstd level 1:  Size: 156 MB, Time: 2.3s
zstd level 9:  Size: 78 MB,  Time: 8.7s
zstd level 22: Size: 51 MB,  Time: 45.2s ⭐ BEST RATIO

gzip level 9:  Size: 124 MB, Time: 15.6s
xz level 9:    Size: 89 MB,  Time: 67.3s
```

### Compression Statistics

**Windows x86_64 (LLVM 21.1.5):**
- Original: 902 MB
- After stripping: 200 MB
- After deduplication (hard links): 200 MB (same size, but ~571 MB savings on disk)
- After zstd level 22: **51.53 MB** (94.3% reduction from original!)

**Linux x86_64 (LLVM 21.1.5):**
- Original: ~850 MB
- After optimization: **88 MB archive**

**macOS ARM64 (LLVM 19.1.7):**
- Original: ~750 MB
- After optimization: **71 MB archive**

### Updating Manifests

After creating archives, update the manifest files:

1. **Generate SHA256 checksum:**
   ```bash
   sha256sum downloads/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst
   ```

2. **Update platform manifest** (`downloads/clang/win/x86_64/manifest.json`):
   ```json
   {
     "latest": "21.1.5",
     "21.1.5": {
       "href": "https://raw.githubusercontent.com/zackees/clang-tool-chain/main/downloads/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst",
       "sha256": "3c21e45edeee591fe8ead5427d25b62ddb26c409575b41db03d6777c77bba44f"
     }
   }
   ```

3. **Commit and push:**
   ```bash
   git add downloads/clang/
   git commit -m "chore: add LLVM 21.1.5 for Windows x86_64"
   git push
   ```

---

## 🔬 Advanced Topics

### Manual Installation (Without Auto-Download)

If you need to manually install binaries (e.g., for offline environments):

1. **Download archive:**
   ```bash
   wget https://raw.githubusercontent.com/zackees/clang-tool-chain/main/downloads/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst
   ```

2. **Extract to installation directory:**
   ```bash
   # Create installation directory
   mkdir -p ~/.clang-tool-chain/clang/win/x86_64

   # Extract archive
   python -m clang_tool_chain.downloads.expand_archive \
       llvm-21.1.5-win-x86_64.tar.zst \
       ~/.clang-tool-chain/clang/win/x86_64

   # Mark as complete
   touch ~/.clang-tool-chain/clang/win/x86_64/done.txt
   ```

3. **Verify installation:**
   ```bash
   clang-tool-chain info
   ```

### Offline Mode

After initial download, `clang-tool-chain` works completely offline:

```bash
# First use (requires internet)
clang-tool-chain-c hello.c -o hello  # Downloads binaries

# Subsequent uses (offline)
clang-tool-chain-c world.c -o world  # Uses cached binaries
```

**For fully offline environments:**
1. Pre-download binaries on a machine with internet
2. Package `~/.clang-tool-chain/` directory
3. Extract to target machines
4. Ensure `done.txt` exists in platform directory

### Version Pinning

Pin specific LLVM versions in `requirements.txt`:

```txt
# requirements.txt
clang-tool-chain==0.0.1  # Pins package version (currently uses LLVM 21.1.5)
```

**Future:** The package will support multiple LLVM versions via manifest updates.

### Concurrent Build Safety

The downloader uses **file locking** (`fasteners.InterProcessLock`) to prevent race conditions:

```python
# Multiple processes can safely call this simultaneously
clang-tool-chain-c hello.c -o hello  # Process 1
clang-tool-chain-c world.c -o world  # Process 2
```

**What happens:**
1. Process 1 acquires lock `~/.clang-tool-chain/win-x86_64.lock`
2. Process 2 waits for lock
3. Process 1 downloads and installs binaries
4. Process 1 writes `done.txt` and releases lock
5. Process 2 acquires lock, sees `done.txt`, skips download
6. Both processes compile successfully

**Perfect for:**
- Parallel CI/CD builds
- Multi-core test runners
- Concurrent development environments

---

## ❓ FAQ

### What happens on first use?

On first use, `clang-tool-chain` automatically:
1. Detects your platform and architecture
2. Fetches the manifest for your platform
3. Downloads the appropriate archive (~52-91 MB)
4. Verifies the SHA256 checksum
5. Extracts to `~/.clang-tool-chain/clang/{platform}/{arch}/`
6. Executes your command

**Total time:** ~10-60 seconds depending on internet speed.

### Can I use clang-tool-chain offline?

Yes! After the initial download, `clang-tool-chain` works completely offline. The binaries are cached in `~/.clang-tool-chain/`.

### How do I update to a new LLVM version?

Currently, the LLVM version is tied to the package version. To update:
```bash
pip install --upgrade clang-tool-chain
```

Future versions will support multiple LLVM versions via manifest updates.

### Is it safe to delete `~/.clang-tool-chain/`?

Yes! Deleting this directory just removes the cached binaries. They will re-download automatically on next use.

### Can I use multiple LLVM versions simultaneously?

Not currently. Each `clang-tool-chain` package version maps to specific LLVM versions (see Platform Support Matrix). Use virtual environments to isolate different package versions:

```bash
# Environment 1: LLVM 21.1.5
python -m venv env1
source env1/bin/activate
pip install clang-tool-chain==0.0.1

# Environment 2: Future LLVM version
python -m venv env2
source env2/bin/activate
pip install clang-tool-chain==0.1.0  # (hypothetical future version)
```

### How does checksum verification work?

Every archive download is verified against SHA256 checksums stored in the platform manifests. If the checksum doesn't match, the download is rejected and an error is raised. This protects against:
- Corrupted downloads
- Man-in-the-middle attacks
- File tampering

### Why does macOS use LLVM 19.1.7 instead of 21.1.5?

LLVM 21.1.5 pre-built binaries for macOS were not available at the time of initial release. We're working on building and distributing LLVM 21.1.5 for macOS. Track progress in [Issue #XX](https://github.com/zackees/clang-tool-chain/issues).

### Can I contribute new platforms or architectures?

Yes! See the [Maintainer Tools](#-maintainer-tools) section for how to create optimized archives. Pull requests welcome!

### Does this work in Docker containers?

Absolutely! See the [CI/CD Integration](#-cicd-integration) section for Docker examples. The automatic download works seamlessly in containers.

### How much disk space do I need?

- **Download:** ~52-91 MB (archive)
- **Installed:** ~200-350 MB (extracted binaries)
- **Total:** ~252-441 MB per platform

The archive is deleted after extraction, so you only need space for the installed binaries.

### Can I use this with CMake?

Yes! Set the compiler in your `CMakeLists.txt` or via environment variables:

```bash
# Option 1: Environment variables
export CC=clang-tool-chain-c
export CXX=clang-tool-chain-cpp
cmake -B build

# Option 2: CMake command line
cmake -B build \
    -DCMAKE_C_COMPILER=clang-tool-chain-c \
    -DCMAKE_CXX_COMPILER=clang-tool-chain-cpp
```

### What about Windows paths with spaces?

All paths are handled correctly, including those with spaces. The wrappers quote paths appropriately.

---

## 🔍 Troubleshooting

### Binaries Not Found

**Error:** `Clang binaries are not installed`

**Solution:**
```bash
# Check installation status
clang-tool-chain info

# Try manual fetch
clang-tool-chain-fetch

# Verify installation directory exists
ls ~/.clang-tool-chain/
```

### Platform Not Supported

**Error:** `Unsupported platform`

**Solution:** Ensure you're on a supported platform:
- Windows 10+ (x64)
- Linux x64 or ARM64 (glibc 2.27+)
- macOS 11+ (x64 or ARM64)

32-bit systems are **not supported**.

### Download Fails

**Error:** `Failed to download archive` or `Checksum verification failed`

**Solutions:**
1. **Check internet connection**
2. **Retry the command** (temporary network issue)
3. **Check GitHub raw content access:**
   ```bash
   curl -I https://raw.githubusercontent.com/zackees/clang-tool-chain/main/downloads/clang/manifest.json
   ```
4. **Clear partial downloads:**
   ```bash
   rm -rf ~/.clang-tool-chain/
   ```

### Tool Execution Fails

**Error:** `Permission denied` (Linux/macOS)

**Solution:**
```bash
# Ensure execute permissions
chmod +x ~/.clang-tool-chain/clang/*/bin/*

# Or reinstall
rm -rf ~/.clang-tool-chain/
clang-tool-chain-c --version  # Re-downloads with correct permissions
```

### Slow First-Time Download

**Observation:** First compilation takes 30-60 seconds

**This is normal!** The toolchain is downloading. Subsequent compilations are instant. To pre-download:

```bash
# Pre-fetch binaries before your build
clang-tool-chain-fetch

# Or just run any command
clang-tool-chain-c --version
```

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'clang_tool_chain'`

**Solutions:**
1. **Ensure package is installed:**
   ```bash
   pip install clang-tool-chain
   ```

2. **Check Python environment:**
   ```bash
   which python  # Verify correct Python interpreter
   pip list | grep clang-tool-chain
   ```

3. **Reinstall:**
   ```bash
   pip uninstall clang-tool-chain
   pip install clang-tool-chain
   ```

### Custom Installation Path Not Working

**Error:** Binaries install to default location despite `CLANG_TOOL_CHAIN_DOWNLOAD_PATH`

**Solution:** Ensure the environment variable is set **before** running the command:

```bash
# Linux/macOS
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/custom/path
clang-tool-chain-c hello.c

# Windows (CMD)
set CLANG_TOOL_CHAIN_DOWNLOAD_PATH=C:\custom\path
clang-tool-chain-c hello.c

# Windows (PowerShell)
$env:CLANG_TOOL_CHAIN_DOWNLOAD_PATH="C:\custom\path"
clang-tool-chain-c hello.c
```

---

## 🔒 Security

Security is a top priority for this project.

### Checksum Verification

- **Automatic:** SHA256 checksums are verified during download (enabled by default)
- **Manifest-Based:** Checksums stored in version-controlled manifests
- **Protection:** Detects corrupted downloads, MITM attacks, and file tampering
- **Transparency:** All checksums visible in `downloads/clang/{platform}/{arch}/manifest.json`

### Safe Extraction

- **Python 3.12+ Tarfile Safety:** Uses `filter="data"` to prevent path traversal attacks
- **Temporary Directory:** Extraction happens in temp directory, then moved atomically
- **Validation:** Verifies archive integrity before extraction

### Reporting Security Issues

For security vulnerabilities, please see our [Security Policy](SECURITY.md) for responsible disclosure instructions.

**Do NOT** report security issues in public GitHub issues.

---

## 📄 License

This package is distributed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.

The bundled LLVM/Clang binaries are licensed under the **Apache License 2.0 with LLVM Exception**. See [LLVM License](https://llvm.org/LICENSE.txt) for details.

---

## 🙏 Acknowledgments

- **[LLVM Project](https://llvm.org/)** - For the excellent Clang/LLVM toolchain
- **[GitHub LLVM Releases](https://github.com/llvm/llvm-project/releases)** - For providing pre-built binaries
- **[Zstandard (zstd)](https://facebook.github.io/zstd/)** - For incredible compression performance
- **[pyzstd](https://github.com/animalize/pyzstd)** - For Python zstd bindings
- **[fasteners](https://github.com/harlowja/fasteners)** - For cross-platform file locking

---

## 📊 Version History

### 0.0.1 (2025-11-07) - Initial Alpha Release
- ✅ Core wrapper infrastructure for 22 wrapper commands
- ✅ Automatic download and installation system
- ✅ Manifest-based distribution with SHA256 verification
- ✅ Binary optimization pipeline (stripping, deduplication, compression)
- ✅ CLI management commands (`info`, `version`, `list-tools`, `path`)
- ✅ Cross-platform support (Windows x64, macOS x64/ARM64, Linux x64/ARM64)
- ✅ File locking for concurrent-safe downloads
- ✅ Ultra-compressed archives (zstd level 22, 94.3% size reduction)
- ✅ LLVM 21.1.5 for Windows/Linux, 19.1.7 for macOS
- ✅ Comprehensive test suite with CI/CD integration

---

## 🚀 Getting Started

Ready to compile? Install and run:

```bash
pip install clang-tool-chain
echo 'int main() { return 0; }' > hello.c
clang-tool-chain-c hello.c -o hello
./hello
```

That's all you need! The toolchain downloads automatically. Happy compiling! 🎉

---

**Repository:** [github.com/zackees/clang-tool-chain](https://github.com/zackees/clang-tool-chain)
**Issues:** [github.com/zackees/clang-tool-chain/issues](https://github.com/zackees/clang-tool-chain/issues)
**PyPI:** [pypi.org/project/clang-tool-chain/](https://pypi.org/project/clang-tool-chain/)
