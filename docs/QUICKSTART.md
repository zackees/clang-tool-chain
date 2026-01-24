# Quick Start Guide

Get up and running with clang-tool-chain in minutes. This guide covers basic compilation, build system integration, and the most common use cases.

## Table of Contents

- [Basic Compilation](#basic-compilation)
- [Override CC/CXX for Build Scripts](#override-cccxx-for-build-scripts)
- [Actually Portable Executables (Cosmopolitan)](#actually-portable-executables-cosmopolitan)
- [Executable C++ Scripts](#executable-c-scripts)
- [WebAssembly Compilation](#webassembly-compilation)
- [What You Get](#what-you-get)
- [Next Steps](#next-steps)

---

## Basic Compilation

```bash
# Install
pip install clang-tool-chain

# Compile C - toolchain auto-downloads on first use (~71-91 MB)
clang-tool-chain-c hello.c -o hello

# Compile C++
clang-tool-chain-cpp hello.cpp -o hello

# That's it! Run your program
./hello
```

**First run:** Downloads LLVM/Clang binaries (~71-91 MB compressed, takes 10-60 seconds depending on connection).

**Subsequent runs:** Instant - binaries are cached in `~/.clang-tool-chain/`.

**Windows users:** Commands use GNU ABI by default (like `zig cc`) for cross-platform consistency. Use `clang-tool-chain-c-msvc` / `clang-tool-chain-cpp-msvc` for MSVC ABI. See [Windows Target Selection](WINDOWS_TARGET_SELECTION.md).

---

## Override CC/CXX for Build Scripts

Make existing build systems (Make, CMake, Meson, etc.) use clang-tool-chain without modification:

```bash
# Unix/Linux/macOS
export CC=clang-tool-chain-c
export CXX=clang-tool-chain-cpp

# Now your build scripts just work
make
cmake -B build && cmake --build build
meson setup build && ninja -C build
```

**Windows PowerShell:**
```powershell
$env:CC = "clang-tool-chain-c"
$env:CXX = "clang-tool-chain-cpp"
```

**Windows CMD:**
```batch
set CC=clang-tool-chain-c
set CXX=clang-tool-chain-cpp
```

### CMake Example

```bash
# Configure with clang-tool-chain
CC=clang-tool-chain-c CXX=clang-tool-chain-cpp cmake -B build

# Build
cmake --build build
```

Or set environment variables first:

```bash
export CC=clang-tool-chain-c
export CXX=clang-tool-chain-cpp
cmake -B build
cmake --build build
```

See [Examples](EXAMPLES.md#cmake-integration) for more CMake workflows.

---

## Actually Portable Executables (Cosmopolitan)

Build binaries that run natively on Windows, Linux, macOS, FreeBSD, NetBSD, and OpenBSD - same file, no modifications needed.

```bash
# Install cosmocc toolchain (downloads on first use)
clang-tool-chain install cosmocc

# Build C
clang-tool-chain-cosmocc hello.c -o hello.com

# Build C++
clang-tool-chain-cosmocpp hello.cpp -o hello.com

# Same binary works everywhere - no runtime dependencies!
./hello.com  # Linux/macOS/FreeBSD/etc.
# On Windows: hello.com (runs natively, not via Wine)
```

**Benefits:**
- Single binary for all platforms
- No runtime dependencies
- No installation required
- Native performance (not emulation)

**See:** [Cosmopolitan Documentation](COSMOCC.md) for detailed usage and examples.

---

## Executable C++ Scripts

Run C++ files directly like shell scripts with native performance. Perfect for utilities, TDD workflows, and rapid prototyping.

**Create an executable C++ file:**

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
int main() {
    std::cout << "Executable C++!\n";
    return 0;
}
```

**Make it executable and run:**

```bash
chmod +x hello.cpp
./hello.cpp  # Compiles and runs! Auto-installs via uvx
```

**Requirements:**
- `uv` package manager: `pip install uv` (one-time setup)
- Unix-like system (Linux, macOS, WSL)

**How it works:**
1. First run: `uvx` auto-installs clang-tool-chain
2. Source is compiled and cached (SHA256-based)
3. Cached binary is executed
4. Subsequent runs are instant (if source unchanged)

**See:** [Executable Scripts Documentation](EXECUTABLE_SCRIPTS.md) for advanced usage, Windows support, and TDD workflows.

---

## WebAssembly Compilation

Compile C/C++ to WebAssembly with the complete Emscripten SDK (includes bundled Node.js runtime).

```bash
# Compile C to WebAssembly
clang-tool-chain-emcc game.c -o game.js

# Compile C++ to WebAssembly
clang-tool-chain-empp engine.cpp -o engine.js

# Run with bundled Node.js
node game.js
```

**Toolchain auto-downloads on first use:**
- Emscripten SDK (~1.4 GB uncompressed)
- Node.js runtime (~90-100 MB uncompressed)
- Total download: ~200-300 MB compressed

**Browser integration:**

```bash
# Generate HTML with WebAssembly
clang-tool-chain-emcc game.c -o game.html

# Serve with Python
python -m http.server 8000

# Open http://localhost:8000/game.html in browser
```

**Optimization:**

```bash
# Release build with optimizations
clang-tool-chain-emcc -O3 game.c -o game.js

# Minimal size
clang-tool-chain-emcc -Oz game.c -o game.js
```

**See:**
- [Emscripten Documentation](EMSCRIPTEN.md) for detailed usage
- [Node.js Integration](NODEJS.md) for bundled Node.js details
- [Examples](EXAMPLES.md#webassembly-emscripten) for complete workflows

---

## What You Get

When you `pip install clang-tool-chain`, you get **41 wrapper commands** that auto-download toolchains on first use:

### Tools by Category

| Category | Tools | Download Size |
|----------|-------|---------------|
| **Compilers** | Clang/LLVM 21, Emscripten SDK, Cosmopolitan libc | 71-91 MB (clang), ~200-300 MB (emscripten), ~35 MB (cosmocc) |
| **Analysis** | IWYU (include analyzer), clang-tidy, clang-format | Downloads with clang |
| **Debugging** | LLDB debugger with Python scripting | ~10-35 MB |
| **Utilities** | ar, nm, objdump, strip, readelf, ranlib, etc. | Downloads with clang |
| **Runtime** | Bundled Node.js for WebAssembly | Downloads with Emscripten |

### LLVM Versions

| Platform | Architecture | LLVM Version |
|----------|--------------|--------------|
| **Windows** | x86_64 | 21.1.5 |
| **Linux** | x86_64 | 21.1.5 |
| **Linux** | ARM64 | 21.1.5 |
| **macOS** | x86_64 | 19.1.7 |
| **macOS** | ARM64 | 21.1.6 |

**See:** [Platform Support Matrix](PLATFORM_SUPPORT.md) for detailed platform information.

### Command Categories

**Compilers (17 commands):**
- `clang-tool-chain-c`, `clang-tool-chain-cpp` - Basic compilation
- `clang-tool-chain-c-msvc`, `clang-tool-chain-cpp-msvc` - Windows MSVC ABI
- `clang-tool-chain-sccache-c`, `clang-tool-chain-sccache-cpp` - With caching
- `clang-tool-chain-ld`, `clang-tool-chain-clang++` - Direct tool access
- And more...

**Build Utilities (3 commands):**
- `clang-tool-chain-build` - Compile with caching
- `clang-tool-chain-build-run` - Compile and execute
- `clang-tool-chain-run` - Run cached binary

**WebAssembly (5 commands):**
- `clang-tool-chain-emcc`, `clang-tool-chain-empp` - Emscripten compilers
- `clang-tool-chain-sccache-emcc`, `clang-tool-chain-sccache-empp` - With caching
- `clang-tool-chain-emar` - Emscripten archiver

**Cosmopolitan (2 commands):**
- `clang-tool-chain-cosmocc` - C compiler
- `clang-tool-chain-cosmocpp` - C++ compiler

**Binary Utilities (11 commands):**
- `clang-tool-chain-ar`, `clang-tool-chain-nm`, `clang-tool-chain-objdump`
- `clang-tool-chain-strip`, `clang-tool-chain-readelf`, `clang-tool-chain-ranlib`
- And more...

**Analysis & Formatting (5 commands):**
- `clang-tool-chain-format` - Code formatting
- `clang-tool-chain-tidy` - Static analysis
- `clang-tool-chain-iwyu` - Include analyzer
- `clang-tool-chain-iwyu-tool`, `clang-tool-chain-fix-includes` - Auto-fix

**Debugging (2 commands):**
- `clang-tool-chain-lldb` - Interactive debugger
- `clang-tool-chain-lldb-server` - Remote debugging

**Management (6+ commands):**
- `clang-tool-chain` - Main CLI
- `clang-tool-chain-test` - Run diagnostics
- `clang-tool-chain-fetch`, `clang-tool-chain-paths` - Utilities

**See:** [Features Overview](FEATURES.md) for complete command reference.

---

## Next Steps

### Essential Reading

- **[Installation Guide](INSTALLATION.md)** - Installation options, upgrading, uninstallation
- **[Getting Started](GETTING_STARTED.md)** - Platform-specific setup, common workflows
- **[Examples](EXAMPLES.md)** - Real-world code examples and projects
- **[Configuration](CONFIGURATION.md)** - Environment variables, SDK paths, customization

### By Use Case

**If you're building cross-platform C/C++ projects:**
- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Compiler details
- [Windows Target Selection](WINDOWS_TARGET_SELECTION.md) - GNU vs MSVC ABI
- [Platform Support](PLATFORM_SUPPORT.md) - Platform compatibility

**If you're using build systems (Make, CMake, Meson):**
- [Examples: CMake Integration](EXAMPLES.md#cmake-integration)
- [CI/CD Integration](CICD_INTEGRATION.md) - GitHub Actions, GitLab CI, Docker

**If you're developing WebAssembly applications:**
- [Emscripten Documentation](EMSCRIPTEN.md) - Complete WASM workflow
- [Node.js Integration](NODEJS.md) - Bundled runtime details
- [Examples: WebAssembly](EXAMPLES.md#webassembly-emscripten)

**If you want portable executables:**
- [Cosmopolitan Documentation](COSMOCC.md) - APE format details
- [Examples: Cosmopolitan](EXAMPLES.md#cosmopolitan-actually-portable-executables)

**If you're optimizing build times:**
- [sccache Integration](SCCACHE.md) - Compilation caching (2-10x speedup)
- [Performance](PERFORMANCE.md) - Benchmarks and optimization tips

**If you're working on code quality:**
- [Format & Lint](FORMAT_LINT.md) - clang-format, clang-tidy
- [IWYU](IWYU.md) - Include optimization
- [LLDB](LLDB.md) - Debugging with LLDB

### Advanced Topics

- **[Inlined Build Directives](DIRECTIVES.md)** - Self-contained source files
- **[Executable Scripts](EXECUTABLE_SCRIPTS.md)** - Shebang C++ workflows
- **[Advanced Topics](ADVANCED.md)** - Offline mode, version pinning, airgapped environments
- **[Architecture](ARCHITECTURE.md)** - Technical implementation details

### Reference

- **[FAQ](FAQ.md)** - Frequently asked questions
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[Security](SECURITY.md)** - Verification and trust model

---

## Common Workflows

### Quick Test Compilation

```bash
# Test C++ compilation
echo 'int main() { return 0; }' > test.cpp
clang-tool-chain-cpp test.cpp -o test
./test
```

### Build with Optimization

```bash
# Release build with optimizations
clang-tool-chain-cpp -O3 main.cpp -o program

# Debug build with symbols
clang-tool-chain-cpp -g -O0 main.cpp -o program
```

### Multi-file Projects

```bash
# Compile multiple source files
clang-tool-chain-cpp main.cpp utils.cpp math.cpp -o program

# Or compile separately and link
clang-tool-chain-cpp -c main.cpp -o main.o
clang-tool-chain-cpp -c utils.cpp -o utils.o
clang-tool-chain-cpp main.o utils.o -o program
```

### Static Library Creation

```bash
# Create static library
clang-tool-chain-cpp -c lib.cpp -o lib.o
clang-tool-chain-ar rcs libmylib.a lib.o

# Link against library
clang-tool-chain-cpp main.cpp -L. -lmylib -o program
```

### Cross-Compilation (Windows)

```bash
# GNU ABI (default) - no Visual Studio required
clang-tool-chain-cpp main.cpp -o program.exe

# MSVC ABI - requires Visual Studio installed
clang-tool-chain-cpp-msvc main.cpp -o program.exe
```

---

## Tips & Best Practices

### Pre-install Toolchains

Download toolchains before first use to avoid delays:

```bash
# Pre-download core toolchain (~71-91 MB)
clang-tool-chain install clang

# Pre-download Emscripten (~200-300 MB)
clang-tool-chain-emcc --version

# Pre-download Cosmopolitan (~35 MB)
clang-tool-chain install cosmocc
```

### Use in CI/CD

Cache the `~/.clang-tool-chain/` directory to speed up CI/CD:

```yaml
# GitHub Actions example
- name: Cache clang-tool-chain
  uses: actions/cache@v3
  with:
    path: ~/.clang-tool-chain
    key: ${{ runner.os }}-clang-tool-chain
```

See [CI/CD Integration](CICD_INTEGRATION.md) for complete examples.

### Speed Up Rebuilds

Use sccache for compilation caching:

```bash
# Install sccache support
pip install clang-tool-chain[sccache]

# Use sccache-enabled compilers
clang-tool-chain-sccache-cpp main.cpp -o program
```

See [sccache Documentation](SCCACHE.md) for configuration and benchmarks.

### Run Diagnostics

If something doesn't work, run diagnostics:

```bash
# Quick diagnostic test (7 tests)
clang-tool-chain-test

# Check installation details
clang-tool-chain info

# Verify binary paths
clang-tool-chain-paths
```

See [Troubleshooting](TROUBLESHOOTING.md) for solutions to common issues.

---

**Ready to dive deeper?** See the [complete documentation index](../README.md#-detailed-documentation) for all available guides.
