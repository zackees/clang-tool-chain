# Clang Tool Chain

**A zero-configuration Python package that distributes pre-built Clang/LLVM binaries with automatic downloading and installation.**

[![PyPI version](https://img.shields.io/pypi/v/clang-tool-chain.svg)](https://pypi.org/project/clang-tool-chain/)
[![Downloads](https://pepy.tech/badge/clang-tool-chain)](https://pepy.tech/project/clang-tool-chain)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Linting](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml)

## Test Matrix

Comprehensive test coverage across all platforms and tool categories:

| Tool Category | Windows x64 | Linux x86_64 | Linux ARM64 | macOS x86_64 | macOS ARM64 |
|---------------|-------------|--------------|-------------|--------------|-------------|
| **clang** | [![clang-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-win.yml) | [![clang-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-x86.yml) | [![clang-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-arm.yml) | [![clang-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-x86.yml) | [![clang-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-arm.yml) |
| **clang+sccache** | [![clang-sccache-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-win.yml) | [![clang-sccache-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-x86.yml) | [![clang-sccache-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-arm.yml) | [![clang-sccache-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-x86.yml) | [![clang-sccache-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-arm.yml) |
| **emscripten** | [![emscripten-windows-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-windows-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-windows-x86.yml) | [![emscripten-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-x86.yml) | [![emscripten-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-arm.yml) | [![emscripten-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-x86.yml) | [![emscripten-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-arm.yml) |
| **emscripten+sccache** | [![emscripten-sccache-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-win.yml) | [![emscripten-sccache-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-x86.yml) | [![emscripten-sccache-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-arm.yml) | [![emscripten-sccache-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-x86.yml) | [![emscripten-sccache-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-arm.yml) |
| **iwyu** | [![iwyu-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-win.yml) | [![iwyu-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-x86.yml) | [![iwyu-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-arm.yml) | [![iwyu-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-x86.yml) | [![iwyu-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml) |
| **format-lint** | [![format-lint-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-win.yml) | [![format-lint-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-x86.yml) | [![format-lint-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-arm.yml) | [![format-lint-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-x86.yml) | [![format-lint-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-arm.yml) |
| **binary-utils** | [![binary-utils-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-win.yml) | [![binary-utils-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-x86.yml) | [![binary-utils-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-arm.yml) | [![binary-utils-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-x86.yml) | [![binary-utils-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-arm.yml) |

**Legend:**
- **clang** - Basic Clang/LLVM compilation (C and C++)
- **clang+sccache** - Clang with sccache compilation caching
- **emscripten** - WebAssembly compilation with Emscripten
- **emscripten+sccache** - Emscripten with sccache caching
- **iwyu** - Include What You Use analyzer
- **format-lint** - clang-format and clang-tidy tools
- **binary-utils** - LLVM binary utilities (ar, nm, objdump, strip, readelf, etc.)


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

# Verify installation (optional but recommended)
clang-tool-chain-test  # Runs 7 diagnostic tests
```

**That's it!** The LLVM toolchain (~71-91 MB) downloads automatically on first use. No manual setup required.

> **Note:** This package currently uses:
> - **LLVM 21.1.5** for Windows, Linux (x86_64/ARM64)
> - **LLVM 21.1.6** for macOS (x86_64/ARM64)
>
> See [Platform Support Matrix](#platform-support-matrix) for details.

### ⚠️ Windows Users: GNU ABI by Default

Windows commands use **GNU ABI** (`x86_64-w64-mingw32` target) for cross-platform consistency, matching [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case) behavior.

**Default commands (GNU ABI):**
```bash
clang-tool-chain-c main.c -o program       # GNU ABI, no Visual Studio required
clang-tool-chain-cpp main.cpp -o program   # Downloads ~90 MB on first use
```

**MSVC ABI variants (Windows-specific projects):**
```bash
clang-tool-chain-c-msvc main.c -o program.exe     # Requires Visual Studio/Windows SDK
clang-tool-chain-cpp-msvc main.cpp -o program.exe # Downloads ~71 MB on first use
```

**✨ Automatic DLL Deployment:** GNU ABI executables automatically include required MinGW runtime DLLs in the executable directory. Your programs run immediately in `cmd.exe` without PATH setup! See [Windows DLL Deployment](#windows-dll-deployment) for details.

**Which to use?** See [Windows Target Selection](#windows-target-selection) for detailed comparison and requirements.

### 📋 Command Quick Reference

#### Compilation Commands

| Task | Command (Default) | Windows MSVC Variant |
|------|-------------------|---------------------|
| **Compile C** | `clang-tool-chain-c main.c -o program` | `clang-tool-chain-c-msvc main.c -o program.exe` |
| **Compile C++** | `clang-tool-chain-cpp main.cpp -o program` | `clang-tool-chain-cpp-msvc main.cpp -o program.exe` |
| **Build & Run** | `clang-tool-chain-build-run main.cpp` | Same |
| **Build & Run (Cached)** | `clang-tool-chain-build-run --cached main.cpp` | Same |
| **Cached C** | `clang-tool-chain-sccache-c main.c -o program` | `clang-tool-chain-sccache-c-msvc main.c -o program.exe` |
| **Cached C++** | `clang-tool-chain-sccache-cpp main.cpp -o program` | `clang-tool-chain-sccache-cpp-msvc main.cpp -o program.exe` |
| **Link Objects** | `clang-tool-chain-ld obj1.o obj2.o -o program` | N/A (use compiler) |
| **Create Library** | `clang-tool-chain-ar rcs libname.a obj1.o obj2.o` | Same |
| **Format Code** | `clang-tool-chain-format -i file.cpp` | Same |

**Note:** MSVC variants require Windows SDK. See [Windows Target Selection](#windows-target-selection) for details.

#### Management Commands

| Task | Command | Description |
|------|---------|-------------|
| **Pre-install Clang** | `clang-tool-chain install clang` | Download Clang/LLVM (~71-91 MB) |
| **Add to PATH** | `clang-tool-chain install clang-env` | Use `clang` directly (auto-installs if needed) |
| **Remove from PATH** | `clang-tool-chain uninstall clang-env` | Keep files, remove from PATH |
| **Remove Everything** | `clang-tool-chain purge` | Delete all toolchains + auto-remove from PATH |
| **Check Installation** | `clang-tool-chain info` | Show installation details |
| **Verify Setup** | `clang-tool-chain-test` | Run 7 diagnostic tests |
| **List Tools** | `clang-tool-chain list-tools` | Show all available wrappers |

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

**macOS Users:** Requires Xcode Command Line Tools for system headers. Run `xcode-select --install` if not already installed.

### Installation Options

#### Option 1: Auto-Download (Recommended)

The toolchain downloads automatically on first use - no setup needed!

```bash
pip install clang-tool-chain
clang-tool-chain-c hello.c -o hello  # Downloads toolchain on first use
```

#### Option 2: Pre-Install Toolchain

Download the toolchain before use (useful for CI/CD or offline work):

```bash
# Pre-download just the core Clang/LLVM toolchain
clang-tool-chain install clang

# This downloads ~71-91 MB and does NOT include:
# - IWYU (downloads on first use of clang-tool-chain-iwyu)
# - Emscripten (downloads on first use of clang-tool-chain-emcc)
# - Node.js (downloads with Emscripten)
```

#### Option 3: Install to System PATH

Use `clang` directly without the `clang-tool-chain-` prefix:

```bash
# Add Clang/LLVM to system PATH (auto-installs if needed)
clang-tool-chain install clang-env

# Now use tools directly (after restarting terminal)
clang --version
clang++ main.cpp -o program
```

**Remove from PATH:**
```bash
clang-tool-chain uninstall clang-env  # Keeps files, removes PATH entry
```

**Remove everything:**
```bash
clang-tool-chain purge  # Deletes files + auto-removes from PATH
```

**Important Notes:**
- PATH changes require terminal restart (or log out/in)
- Works cross-platform (Windows, macOS, Linux)
- Wrapper commands (`clang-tool-chain-*`) always available
- Uses [setenvironment](https://github.com/zackees/setenvironment) for persistent PATH modification
- Tracked in SQLite database for automatic cleanup

**Future commands:**
- `install iwyu` / `install iwyu-env` - IWYU analyzer
- `install emscripten` / `install emscripten-env` - Emscripten WebAssembly (includes own LLVM)

---

## 🎯 Why clang-tool-chain?

### The Problem

Installing Clang/LLVM traditionally requires:
- Large downloads (1-3 GB installer/archive)
- System-wide installation with admin privileges
- Manual PATH configuration
- Platform-specific installation procedures
- Version management headaches in CI/CD

### The Solution

`clang-tool-chain` provides:

| Feature | clang-tool-chain | Full LLVM Install | System Compiler | zig cc |
|---------|------------------|-------------------|-----------------|--------|
| **Size** | 71-91 MB | 1-3 GB | Varies | ~80 MB |
| **Setup Time** | < 30 seconds | 5-15 minutes | Varies | < 30 seconds |
| **Admin Required** | ❌ No | ✅ Yes (usually) | ✅ Yes | ❌ No |
| **Auto Download** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **Version Control** | ✅ Pin in requirements | ❌ System-wide | ❌ System-wide | ⚠️ Tied to Zig version |
| **Cross-Platform** | ✅ Identical on all OS | ❌ Different procedures | ❌ Different versions | ✅ Yes |
| **Cross-Compilation** | Platform-specific | ❌ Complex | ❌ Complex | ✅ Single binary, all targets |
| **CI/CD Ready** | ✅ Zero config | ❌ Complex setup | ⚠️ Depends on runner | ✅ Zero config |
| **Offline After DL** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Python Integration** | ✅ Native | ❌ Manual | ❌ Manual | ❌ Manual |

### Perfect For

- **CI/CD Pipelines** - Reproducible builds with pinned toolchain versions
- **Educational Environments** - Students get started instantly without installation hassles
- **Development Teams** - Everyone uses the exact same compiler version
- **Containerized Builds** - Minimal Docker image overhead
- **Python Projects** - Seamless integration with Python build systems

### Not Recommended For

- **Production Embedded Systems** - Use vendor-specific toolchains
- **Kernel Development** - System compilers with specific patches
- **Custom LLVM Builds** - If you need specific LLVM patches/features
- **Air-Gapped Environments** - Requires manual setup (see [Offline Mode](#offline-mode))
- **Cross-Compilation to Different Architectures** - Use `zig cc` for multi-target cross-compilation

---

## ✨ Features

- **Automatic Download on First Use** - Zero-configuration installation to `~/.clang-tool-chain/`
- **Manifest-Based Distribution** - Version-controlled releases with SHA256 checksum verification
- **Multi-Part Archive Support** - Transparent handling of large archives (>100 MB) split into parts
- **Ultra-Optimized Archives** - 94.3% size reduction via binary stripping, deduplication, and zstd-22 compression
- **Cross-Platform Support** - Windows x86_64, macOS x86_64/ARM64, Linux x86_64/ARM64
- **Concurrent-Safe Installation** - File locking prevents race conditions in parallel builds
- **Python Wrapper Commands** - 35 entry points for all essential LLVM tools
- **Pre-Built Binaries** - Clang 21.1.5 (Windows, Linux) and Clang 21.1.6 (macOS)
- **Essential Toolchain Utilities** - Compilers, linkers, binary utilities, and code formatters
- **Automatic macOS SDK Detection** - Seamlessly finds system headers on macOS without configuration

---

## 🚀 Usage

### CLI Commands

Manage your toolchain installation:

```bash
# Show installation information and available tools
clang-tool-chain info

# Run diagnostic tests (verify installation)
clang-tool-chain test

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

# Remove all downloaded toolchains and cached data
clang-tool-chain purge          # Interactive confirmation
clang-tool-chain purge --yes    # Skip confirmation (for scripts)
```

**About `purge` command:**
- Removes `~/.clang-tool-chain/` directory containing all toolchains
- Frees up ~200-400 MB per platform (Clang/LLVM binaries)
- Also removes MinGW sysroot (~176 MB, Windows), Emscripten SDK (~1.4 GB), Node.js runtime (~90-100 MB)
- Toolchains will be re-downloaded automatically on next use
- Use `--yes` flag to skip confirmation prompt (useful for CI/CD scripts)
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

#### Using the Build Utilities

**Basic Build Command**

The `clang-tool-chain-build` command provides a simple way to compile projects:

```bash
# Build a single C file
clang-tool-chain-build hello.c hello

# Build a C++ file with custom output name
clang-tool-chain-build hello.cpp myprogram

# Build with optimization
clang-tool-chain-build hello.cpp myprogram -O2
```

**Build-and-Run Command**

The `clang-tool-chain-build-run` command compiles and immediately executes your program:

```bash
# Compile and run a C++ program
clang-tool-chain-build-run hello.cpp

# With compiler flags
clang-tool-chain-build-run hello.cpp -O2 -std=c++17

# Pass arguments to the program
clang-tool-chain-build-run hello.cpp -- arg1 arg2

# Use caching for faster development iterations
clang-tool-chain-build-run --cached hello.cpp

# Combined: caching + compiler flags + program arguments
clang-tool-chain-build-run --cached hello.cpp -O2 -- input.txt
```

**How it works:**
- Takes a source file (e.g., `hello.cpp`)
- Compiles to executable (e.g., `hello.exe` on Windows, `hello` on Unix)
- Runs the executable immediately
- With `--cached`: Skips compilation if source hasn't changed (SHA256 hash-based)

**Shebang Support (Unix/Linux/macOS):**

Make C++ files directly executable:

```cpp
#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>
int main() {
    std::cout << "Hello from executable C++!" << std::endl;
    return 0;
}
```

```bash
chmod +x script.cpp
./script.cpp  # Compiles on first run, cached on subsequent runs
```

#### CMake Integration

**Option 1: Environment Variables (Recommended)**

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.15)
project(MyProject)

# No changes needed - respects CC/CXX environment variables
add_executable(myapp main.cpp)
```

```bash
export CC=clang-tool-chain-c
export CXX=clang-tool-chain-cpp
cmake -B build
cmake --build build
```

**Option 2: Direct Compiler Specification**

```bash
cmake -B build \
    -DCMAKE_C_COMPILER=clang-tool-chain-c \
    -DCMAKE_CXX_COMPILER=clang-tool-chain-cpp
cmake --build build
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

# Windows MSVC variants with sccache
clang-tool-chain-sccache-c-msvc main.c -o main.exe
clang-tool-chain-sccache-cpp-msvc main.cpp -o main.exe

# Emscripten (WebAssembly) with sccache
clang-tool-chain-sccache-emcc main.c -o main.js
clang-tool-chain-sccache-empp main.cpp -o main.js

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

#### IWYU (Include What You Use)

Analyze and optimize C/C++ #include directives:

```bash
# Analyze includes in a source file
clang-tool-chain-iwyu myfile.cpp -- -std=c++17

# With additional compiler flags
clang-tool-chain-iwyu myfile.cpp -- -I./include -DDEBUG

# Run IWYU tool (Python wrapper)
clang-tool-chain-iwyu-tool -p build/

# Automatically fix includes based on IWYU output
clang-tool-chain-iwyu myfile.cpp -- -std=c++17 | clang-tool-chain-fix-includes

# Or save recommendations to file first
clang-tool-chain-iwyu myfile.cpp -- -std=c++17 > iwyu.out
clang-tool-chain-fix-includes < iwyu.out
```

**What it does:**
- Detects unnecessary #include directives
- Suggests missing #include directives
- Recommends forward declarations instead of full includes
- Helps reduce compilation times and header dependencies

**How it works:**
- IWYU analyzes what symbols are actually used in your code
- Compares against what headers are included
- Generates recommendations for includes to add/remove
- `fix-includes` can automatically apply the changes

#### Emscripten (WebAssembly Compilation)

Compile C/C++ to WebAssembly using Emscripten:

```bash
# Compile C to WebAssembly
clang-tool-chain-emcc hello.c -o hello.js

# Compile C++ to WebAssembly
clang-tool-chain-empp hello.cpp -o hello.js

# With optimization
clang-tool-chain-emcc -O3 main.c -o main.js

# Create WebAssembly library
clang-tool-chain-emcc -c lib.c -o lib.o
clang-tool-chain-emar rcs libmylib.a lib.o

# Run the compiled WebAssembly (requires Node.js)
node hello.js

# With sccache for faster rebuilds
clang-tool-chain-sccache-emcc main.c -o main.js
clang-tool-chain-sccache-empp main.cpp -o main.js
```

**Platform Support:**
- Windows x86_64: Emscripten 4.0.19
- macOS x86_64/ARM64: Emscripten 4.0.19
- Linux x86_64: Emscripten 4.0.15
- Linux ARM64: Coming soon

**What it includes:**
- Emscripten compiler toolchain
- Bundled Node.js runtime for running WebAssembly
- Full emscripten SDK integration
- sccache support for compilation caching

**Learn more:** See [docs/EMSCRIPTEN.md](docs/EMSCRIPTEN.md) for detailed Emscripten documentation and [docs/NODEJS.md](docs/NODEJS.md) for Node.js integration details.

### All Available Commands

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain` | CLI | Main management interface (subcommands: info, version, list-tools, path, package-version, test, purge) |
| `clang-tool-chain-test` | Diagnostic | Run 7 diagnostic tests to verify installation |
| `clang-tool-chain-fetch` | Fetch utility | Manual download utility for pre-fetching binaries |
| `clang-tool-chain-paths` | Path utility | Get installation paths in JSON format |
| `clang-tool-chain-c` | `clang` | C compiler (GNU ABI on Windows) |
| `clang-tool-chain-cpp` | `clang++` | C++ compiler (GNU ABI on Windows) |
| `clang-tool-chain-c-msvc` | `clang` | C compiler (MSVC ABI, Windows only) |
| `clang-tool-chain-cpp-msvc` | `clang++` | C++ compiler (MSVC ABI, Windows only) |
| `clang-tool-chain-build` | Build utility | Simple build tool for C/C++ |
| `clang-tool-chain-build-run` | Build & Run utility | Compile and run in one step (with optional caching) |
| `clang-tool-chain-sccache` | `sccache` | Direct sccache access (stats, management) |
| `clang-tool-chain-sccache-c` | `sccache` + `clang` | C compiler with sccache caching (GNU ABI) |
| `clang-tool-chain-sccache-cpp` | `sccache` + `clang++` | C++ compiler with sccache caching (GNU ABI) |
| `clang-tool-chain-sccache-c-msvc` | `sccache` + `clang` | C compiler with sccache caching (MSVC ABI, Windows only) |
| `clang-tool-chain-sccache-cpp-msvc` | `sccache` + `clang++` | C++ compiler with sccache caching (MSVC ABI, Windows only) |
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
| `clang-tool-chain-iwyu` | `include-what-you-use` | Include analyzer - finds unnecessary includes |
| `clang-tool-chain-iwyu-tool` | `iwyu_tool.py` | IWYU batch runner for projects |
| `clang-tool-chain-fix-includes` | `fix_includes.py` | Automatically fix includes based on IWYU output |
| `clang-tool-chain-emcc` | `emcc` | Emscripten C compiler (WebAssembly) |
| `clang-tool-chain-empp` | `em++` | Emscripten C++ compiler (WebAssembly) |
| `clang-tool-chain-emar` | `emar` | Emscripten archiver (WebAssembly) |
| `clang-tool-chain-sccache-emcc` | `sccache` + `emcc` | Emscripten C compiler with sccache caching |
| `clang-tool-chain-sccache-empp` | `sccache` + `em++` | Emscripten C++ compiler with sccache caching |

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
          ./program

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
    - clang-tool-chain-c src/main.c -o program
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

# Pre-download binaries (optional)
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
| Windows  | x86_64       | 21.1.5       | ~71 MB*      | ~350 MB        | ✅ Stable |
| Linux    | x86_64       | 21.1.5       | ~87 MB       | ~350 MB        | ✅ Stable |
| Linux    | ARM64        | 21.1.5       | ~91 MB       | ~340 MB        | ✅ Stable |
| macOS    | x86_64       | 21.1.6       | ~77 MB       | ~300 MB        | ✅ Stable |
| macOS    | ARM64        | 21.1.6       | ~71 MB       | ~285 MB        | ✅ Stable |

\* **Windows Downloads:**
  - **GNU target (default):** ~90 MB (71 MB LLVM + 19 MB MinGW-w64 sysroot)
  - **MSVC target (opt-in):** ~71 MB (LLVM only, requires Visual Studio SDK)

**Note:** macOS uses LLVM 21.1.6 (Homebrew build for x86_64).

### Requirements

- **Python**: 3.10 or higher
- **Disk Space**: ~100 MB for archive + ~200-350 MB installed
- **Internet**: Required for initial download (works offline after installation)
- **Operating System**:
  - Windows 10+ (x86_64)
  - macOS 11+ (x86_64 or ARM64/Apple Silicon) - **Requires Xcode Command Line Tools**: `xcode-select --install`
  - Linux with glibc 2.27+ (x86_64 or ARM64)

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

### macOS SDK Detection (Automatic)

macOS users don't need to configure SDK paths - the toolchain automatically detects your Xcode Command Line Tools SDK using `xcrun`.

**Requirements:**
```bash
xcode-select --install  # One-time setup
```

**How it works:**
- Automatically injects `-isysroot` flag when compiling on macOS
- Detects SDK via `xcrun --show-sdk-path`
- Respects `SDKROOT` environment variable or explicit `-isysroot` flags

**Custom configuration:**
```bash
# Use custom SDK path
export SDKROOT=/path/to/sdk

# Disable automatic detection (not recommended)
export CLANG_TOOL_CHAIN_NO_SYSROOT=1
```

For troubleshooting SDK issues, see [macOS: stdio.h or iostream Not Found](#macos-stdioh-or-iostream-not-found).

---

## ⚡ Performance

### Compilation Speed

clang-tool-chain uses unmodified LLVM binaries - expect **identical performance** to official LLVM releases.

### Download Benchmarks (First Use)

Archives (71-91 MB) download in **~5 seconds on fiber (100 Mbps)** or **~25 seconds on cable (20 Mbps)**. Subsequent compilations are instant (no download).

---

## 🎯 Windows Target Selection

### Default Behavior (GNU ABI - Recommended)

The default Windows target is `x86_64-w64-mingw32` (GNU ABI) for cross-platform consistency:

```bash
# These commands use GNU ABI by default on Windows:
clang-tool-chain-c hello.c -o hello
clang-tool-chain-cpp hello.cpp -o hello

# Equivalent to explicitly specifying:
clang-tool-chain-c --target=x86_64-w64-mingw32 hello.c -o hello
```

**Why GNU ABI is default:**
1. **Cross-platform consistency** - Same ABI on Linux/macOS/Windows
2. **C++11 strict mode support** - MSVC headers require C++14 features even in C++11 mode
3. **Embedded/Arduino compatibility** - Matches GCC toolchain behavior
4. **Modern C++ standard library** - Uses LLVM's libc++ (same as macOS/Linux)

This matches the approach of [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case) and other modern cross-platform toolchains.

### MSVC ABI (Windows-Specific Projects)

For Windows-native projects that need MSVC compatibility:

```bash
# Use MSVC variants for Windows-specific development:
clang-tool-chain-c-msvc main.c -o program.exe
clang-tool-chain-cpp-msvc main.cpp -o program.exe

# Or explicitly specify MSVC target with default commands:
clang-tool-chain-c --target=x86_64-pc-windows-msvc main.c -o program.exe
```

**Use MSVC ABI when:**
- Linking with MSVC-compiled DLLs (with C++ APIs)
- Using Windows SDK features not in MinGW
- Requiring Visual Studio debugger integration
- Building COM/WinRT/Windows Runtime components

### Comparison Table

| Feature | GNU ABI (Default) | MSVC ABI (Opt-in) |
|---------|------------------|------------------|
| **C++ Standard Library** | libc++ (LLVM) | MSVC STL |
| **C++ ABI** | Itanium (like GCC) | Microsoft |
| **Cross-platform consistency** | ✅ Yes | ❌ Windows-only |
| **C++11 strict mode** | ✅ Works | ❌ Requires C++14+ |
| **Link with MSVC libs** | ❌ C++ ABI mismatch | ✅ Compatible |
| **Arduino/embedded** | ✅ Compatible | ❌ Different ABI |
| **Download size** | ~100 MB | ~50 MB |
| **Requires Visual Studio** | ❌ No | ⚠️ Recommended |

### Advanced: Manual Target Selection

You can override the target for any compilation:

```bash
# Force GNU target (default on Windows anyway):
clang-tool-chain-c --target=x86_64-w64-mingw32 main.c

# Force MSVC target:
clang-tool-chain-c --target=x86_64-pc-windows-msvc main.c

# Cross-compile for Linux from Windows:
clang-tool-chain-c --target=x86_64-unknown-linux-gnu main.c

# Cross-compile for macOS from Windows:
clang-tool-chain-c --target=arm64-apple-darwin main.c
```

**Note:** Cross-compilation requires appropriate sysroots (not included by default).

---

## 🪟 Windows DLL Deployment

**Automatic MinGW Runtime DLL Deployment (GNU ABI only)**

When building Windows executables with GNU ABI (the default), clang-tool-chain automatically copies required MinGW runtime DLLs to your executable directory. This ensures your programs run immediately in `cmd.exe` without any PATH configuration.

### How It Works

1. **Automatic Detection**: After successful linking, `llvm-objdump` analyzes the executable to detect DLL dependencies
2. **Smart Copying**: Only MinGW runtime DLLs are copied (system DLLs like `kernel32.dll` are excluded)
3. **Timestamp Optimization**: DLLs are only copied if the source is newer than the destination
4. **Non-Fatal Errors**: DLL deployment never fails your build - it only logs warnings

### Quick Example

```bash
# Compile a C++ program (GNU ABI - default on Windows)
clang-tool-chain-cpp hello.cpp -o hello.exe

# Console output shows:
# Deployed 3 MinGW DLL(s) for hello.exe

# Your executable directory now contains:
# hello.exe
# libwinpthread-1.dll
# libgcc_s_seh-1.dll
# libstdc++-6.dll

# Run immediately in cmd.exe - no PATH setup needed!
.\hello.exe
```

### Environment Variables

| Variable | Effect | Example |
|----------|--------|---------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` | Disable DLL deployment | `set CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` |
| `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1` | Enable verbose logging | `set CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1` |

### Performance Impact

- **DLL Detection**: <50ms (via llvm-objdump)
- **DLL Copying**: <50ms (typically 2-3 small DLLs)
- **Total Overhead**: <100ms per executable
- **Incremental Builds**: ~0ms (timestamp check skips unnecessary copies)

### Typical DLLs Deployed

- **`libwinpthread-1.dll`** - POSIX threads support
- **`libgcc_s_seh-1.dll`** - GCC runtime (exception handling)
- **`libstdc++-6.dll`** - C++ standard library

### When DLL Deployment is Skipped

- ❌ **Non-Windows platforms** (Linux/macOS)
- ❌ **MSVC ABI builds** (`clang-tool-chain-cpp-msvc`)
- ❌ **Compile-only operations** (`-c` flag)
- ❌ **Non-executable outputs** (`.o`, `.a`, `.lib` files)
- ❌ **Environment variable set** (`CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1`)
- ❌ **Linker failures** (only deploys after successful linking)

### Troubleshooting

**Problem:** DLLs not being copied

**Solutions:**
1. Check you're using GNU ABI (default), not MSVC ABI (`-msvc` variant)
2. Verify you're linking (not just compiling with `-c`)
3. Check the output file has `.exe` extension
4. Ensure `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS` is not set

**Problem:** Want to disable DLL deployment

**Solution:**
```bash
# Windows (CMD)
set CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1
clang-tool-chain-cpp main.cpp -o main.exe

# Windows (PowerShell)
$env:CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS="1"
clang-tool-chain-cpp main.cpp -o main.exe
```

**Problem:** Need verbose logging for debugging

**Solution:**
```bash
set CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o main.exe
# Now shows detailed DEBUG logs
```

### Implementation Details

- **Source Code**: `src/clang_tool_chain/deployment/dll_deployer.py`
- **Integration**: `src/clang_tool_chain/execution/core.py` (post-link hooks)
- **Tests**: `tests/test_dll_deployment.py` (38 comprehensive tests, 92% coverage)
- **Fallback Strategy**: If `llvm-objdump` fails, uses heuristic list of common DLLs

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
│  • macOS SDK Auto-Detection (xcrun integration)              │
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

1. **Root Manifest** (`downloads-bins/assets/clang/manifest.json`) - Indexes all platforms and architectures
2. **Platform Manifests** (`downloads-bins/assets/clang/{platform}/{arch}/manifest.json`) - Contains version info, download URLs, and SHA256 checksums

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
- **macOS**: Automatically detects and injects SDK path via `xcrun`
- **Alternative Names**: Supports tool aliases (e.g., `clang` → `clang-cl` on Windows)

---

## 🔧 Additional Utilities

### clang-tool-chain-test

Run diagnostic tests to verify your installation:

```bash
# Run 7 diagnostic tests
clang-tool-chain-test

# Or via main CLI:
clang-tool-chain test
```

**Tests performed:**
1. Platform detection
2. Toolchain installation verification
3. clang binary resolution
4. clang++ binary resolution
5. clang version check
6. C compilation test
7. C++ compilation test

This command is especially useful for debugging installation issues in GitHub Actions or other CI/CD environments.

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

## 🔬 Advanced Topics

### Manual Installation (Without Auto-Download)

If you need to manually install binaries (e.g., for offline environments):

1. **Download archive:**
   ```bash
   wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst
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
clang-tool-chain==1.0.14  # Pins package version (currently uses LLVM 21.1.5)
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
3. Downloads the appropriate archive (~71-91 MB)
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
pip install clang-tool-chain==1.0.14

# Environment 2: Future LLVM version
python -m venv env2
source env2/bin/activate
pip install clang-tool-chain==1.1.0  # (hypothetical future version)
```

### How does checksum verification work?

Every archive download is verified against SHA256 checksums stored in the platform manifests. If the checksum doesn't match, the download is rejected and an error is raised. This protects against:
- Corrupted downloads
- Man-in-the-middle attacks
- File tampering

### Does macOS support LLVM 21.1.5?

macOS uses LLVM 21.1.6 for both x86_64 and ARM64 architectures. The x86_64 build uses Homebrew's LLVM since no official binary is available from the LLVM project.

### Can I contribute new platforms or architectures?

Yes! See the [Maintainer Tools](#maintainer-tools) section for how to create optimized archives. Pull requests welcome!

### Does this work in Docker containers?

Absolutely! See the [CI/CD Integration](#cicd-integration) section for Docker examples. The automatic download works seamlessly in containers.

### How much disk space do I need?

- **Download:** ~71-91 MB (archive)
- **Installed:** ~200-350 MB (extracted binaries)
- **Total:** ~271-441 MB per platform

The archive is deleted after extraction, so you only need space for the installed binaries.

### Can I use this with CMake?

Yes! See [CMake Integration](#cmake-integration) section for full examples.

### What about Windows paths with spaces?

All paths are handled correctly, including those with spaces. The wrappers quote paths appropriately.

### Do I need to install Xcode on macOS?

No! You only need the **Xcode Command Line Tools**, which is much smaller:

```bash
xcode-select --install
```

This provides the SDK headers needed for compilation without installing the full Xcode IDE.

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
- Windows 10+ (x86_64)
- Linux x86_64 or ARM64 (glibc 2.27+)
- macOS 11+ (x86_64 or ARM64)

32-bit systems are **not supported**.

### Download Fails

**Error:** `Failed to download archive` or `Checksum verification failed`

**Solutions:**
1. **Check internet connection**
2. **Retry the command** (temporary network issue)
3. **Check GitHub raw content access:**
   ```bash
   curl -I https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/manifest.json
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

### macOS: stdio.h or iostream Not Found

**Error:** `fatal error: 'stdio.h' file not found` or `'iostream' file not found`

**Cause:** Xcode Command Line Tools not installed or SDK not detected.

**Solution:**
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Verify SDK is detected
xcrun --show-sdk-path

# Should output something like:
# /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk

# Try compilation again
clang-tool-chain-c hello.c -o hello
```

**Advanced troubleshooting:**
```bash
# Manually specify SDK path
clang-tool-chain-c -isysroot $(xcrun --show-sdk-path) hello.c -o hello

# Or set SDKROOT environment variable
export SDKROOT=$(xcrun --show-sdk-path)
clang-tool-chain-c hello.c -o hello
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
- **Transparency:** All checksums visible in `downloads-bins/assets/clang/{platform}/{arch}/manifest.json`

### Safe Extraction

- **Python 3.12+ Tarfile Safety:** Uses `filter="data"` to prevent path traversal attacks
- **Temporary Directory:** Extraction happens in temp directory, then moved atomically
- **Validation:** Verifies archive integrity before extraction

### Download Security

Binaries are served from GitHub raw content (`raw.githubusercontent.com`):
- ✅ **Checksum Verified:** SHA256 validation on every download
- ✅ **Version Locked:** Manifests are version-controlled in the repository
- ⚠️ **Trust Model:** You're trusting this package maintainer + GitHub infrastructure
- 🔒 **HTTPS Only:** All downloads use encrypted connections

**For maximum security:**
```bash
# Option 1: Manual verification
clang-tool-chain-fetch --dry-run  # Shows download URLs
# Verify checksums in downloads-bins/assets/clang/<platform>/<arch>/manifest.json

# Option 2: Offline installation
# Download archive, verify checksum independently, then extract manually
```

### Reporting Security Issues

For security vulnerabilities, please see our [Security Policy](SECURITY.md) for responsible disclosure instructions.

**Do NOT** report security issues in public GitHub issues.

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

<details>
<summary><b>Click to expand maintainer documentation</b> (for package maintainers only)</summary>

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
9. ✅ Places in `downloads-bins/assets/clang/{platform}/{arch}/`
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
    work/clang+llvm-21.1.5-x86_64-pc-windows-msvc \
    downloads-bins/assets/clang/win/x86_64 \
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
    work/clang+llvm-21.1.5-x86_64-pc-windows-msvc/bin
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
    llvm-21.1.5-win-x86_64.tar.zst \
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

**macOS ARM64 (LLVM 21.1.6):**
- Original: ~750 MB
- After optimization: **71 MB archive**

### Updating Manifests

After creating archives, update the manifest files:

1. **Generate SHA256 checksum:**
   ```bash
   sha256sum downloads-bins/assets/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst
   ```

2. **Update platform manifest** (`downloads-bins/assets/clang/win/x86_64/manifest.json`):
   ```json
   {
     "latest": "21.1.5",
     "21.1.5": {
       "href": "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst",
       "sha256": "3c21e45edeee591fe8ead5427d25b62ddb26c409575b41db03d6777c77bba44f"
     }
   }
   ```

3. **Commit and push to downloads-bins submodule:**
   ```bash
   cd downloads-bins
   git add assets/clang/
   git commit -m "chore: add LLVM 21.1.5 for Windows x86_64"
   git push
   cd ..
   git add downloads-bins
   git commit -m "chore: update submodule to latest binaries"
   git push
   ```

</details>

---

## 📄 License

This package is distributed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.

The bundled Clang/LLVM binaries are licensed under the **Apache License 2.0 with LLVM Exception**. See [LLVM License](https://llvm.org/LICENSE.txt) for details.

---

## 🙏 Acknowledgments

- **[LLVM Project](https://llvm.org/)** - For the excellent Clang/LLVM toolchain
- **[GitHub LLVM Releases](https://github.com/llvm/llvm-project/releases)** - For providing pre-built binaries
- **[Zstandard (zstd)](https://facebook.github.io/zstd/)** - For incredible compression performance
- **[pyzstd](https://github.com/animalize/pyzstd)** - For Python zstd bindings
- **[fasteners](https://github.com/harlowja/fasteners)** - For cross-platform file locking

---

## 📊 Version History

### 1.0.1 (2025-11-09)
- ✅ Automatic macOS SDK detection via xcrun
- ✅ Improved error messages and troubleshooting
- ✅ Enhanced documentation with platform-specific guidance

### 1.0.0 (2025-11-07) - Initial Release
- ✅ Core wrapper infrastructure for 22 wrapper commands
- ✅ Automatic download and installation system
- ✅ Manifest-based distribution with SHA256 verification
- ✅ Binary optimization pipeline (stripping, deduplication, compression)
- ✅ CLI management commands (`info`, `version`, `list-tools`, `path`)
- ✅ Cross-platform support (Windows x86_64, macOS x86_64/ARM64, Linux x86_64/ARM64)
- ✅ File locking for concurrent-safe downloads
- ✅ Ultra-compressed archives (zstd level 22, 94.3% size reduction)
- ✅ LLVM 21.1.5 for Windows and Linux; LLVM 21.1.6 for macOS
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

---

**Keywords:** clang wrapper, llvm python, portable clang, clang installer, llvm toolchain, cross-platform compiler, python clang, automated llvm, clang docker, ci/cd compiler
