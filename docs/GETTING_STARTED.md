# Getting Started

Quick start guides for common use cases with clang-tool-chain.

## Installation

### From PyPI (Recommended)

```bash
pip install clang-tool-chain
```

The toolchain downloads automatically on first use - no additional setup needed!

### Installation Size

| Component | Size | When Downloaded |
|-----------|------|----------------|
| Python package | ~500 KB | During `pip install` |
| Clang/LLVM binaries | 71-91 MB | First compilation |
| Emscripten SDK | ~1.4 GB | First WASM compilation |
| Node.js runtime | 90-100 MB | With Emscripten |
| IWYU binaries | ~5-10 MB | First IWYU analysis |
| LLDB binaries | ~10-35 MB | First debugging session |
| Cosmocc | ~60-80 MB | First APE compilation |

**Total disk space:** ~271-441 MB per platform (excluding Emscripten)

## Quick Start - Basic Compilation

### Hello World (C)

```bash
# Create a simple C program
echo 'int main() { return 0; }' > hello.c

# Compile it
clang-tool-chain-c hello.c -o hello

# Run it
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

### First Compilation (What to Expect)

**First time:** Toolchain downloads automatically (~71-91 MB), takes 10-60 seconds depending on internet speed.

**Subsequent compilations:** Instant! Binaries are cached in `~/.clang-tool-chain/`.

## Override CC/CXX for Build Scripts

Make/CMake/Meson/etc. use clang-tool-chain:

```bash
# Bash/Linux/macOS
export CC=clang-tool-chain-c
export CXX=clang-tool-chain-cpp

# Now run your build
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
```cmd
set CC=clang-tool-chain-c
set CXX=clang-tool-chain-cpp
```

## Platform-Specific Notes

### macOS

**Requirement:** Xcode Command Line Tools for SDK headers

```bash
xcode-select --install
```

clang-tool-chain automatically detects the macOS SDK via `xcrun`. No manual configuration needed!

### Windows

**Default ABI:** GNU (MinGW-w64) for cross-platform consistency

```bash
# Default: GNU ABI
clang-tool-chain-cpp hello.cpp -o hello.exe
```

**MSVC ABI (opt-in):**
```bash
# Requires Visual Studio installed
clang-tool-chain-cpp-msvc main.cpp -o program.exe
```

See [Windows Target Selection](WINDOWS_TARGET_SELECTION.md) for detailed comparison.

### Linux

No special requirements! Works out of the box on glibc 2.27+ systems (Ubuntu 18.04+, Debian 10+, etc.).

## Quick Start - WebAssembly

Compile C/C++ to WebAssembly with bundled Node.js:

```bash
# Compile C to WASM
clang-tool-chain-emcc hello.c -o hello.js

# Compile C++ to WASM
clang-tool-chain-empp hello.cpp -o hello.js

# Run with bundled Node.js
node hello.js
```

**First time:** Downloads Emscripten SDK (~1.4 GB) + Node.js (~90-100 MB)

See [Emscripten Documentation](EMSCRIPTEN.md) for advanced usage.

## Quick Start - Actually Portable Executables (Cosmopolitan)

Build binaries that run on Windows, Linux, macOS, FreeBSD - unchanged:

```bash
# Install cosmocc toolchain
clang-tool-chain install cosmocc

# Build portable executable
clang-tool-chain-cosmocc hello.c -o hello.com

# Same binary works everywhere!
./hello.com  # Linux/macOS/FreeBSD/etc.
# On Windows: hello.com
```

See [Cosmopolitan Documentation](COSMOCC.md) for details.

## Quick Start - Executable C++ Scripts

**Run C++ files directly like shell scripts!** (Unix/Linux/macOS only)

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "Executable C++!" << std::endl;
    return 0;
}
```

```bash
chmod +x script.cpp
./script.cpp  # Compiles and runs!
```

**Requirements:**
- `pip install uv` (one-time setup)
- clang-tool-chain auto-installs via `uvx` on first run

See [Executable Scripts Documentation](EXECUTABLE_SCRIPTS.md) for details.

## Quick Start - Inlined Build Directives

**Self-contained source files** with embedded build configuration:

```cpp
// server.cpp
// @link: pthread
// @std: c++17
// @cflags: -O2 -Wall

#include <pthread.h>
#include <iostream>

int main() {
    std::cout << "Server with pthread support!" << std::endl;
    return 0;
}
```

```bash
# Just compile - directives are parsed automatically!
clang-tool-chain-cpp server.cpp -o server
# Automatically adds: -std=c++17 -lpthread -O2 -Wall
```

See [Inlined Build Directives](DIRECTIVES.md) for all supported directives.

## Pre-Installing Toolchains

By default, toolchains download on first use. To pre-download:

```bash
# Pre-download Clang/LLVM (~71-91 MB)
clang-tool-chain install clang

# Pre-download Emscripten (~1.4 GB)
clang-tool-chain install emscripten

# Pre-download IWYU
clang-tool-chain install iwyu

# Pre-download LLDB
clang-tool-chain install lldb

# Pre-download Cosmocc
clang-tool-chain install cosmocc
```

## Adding to System PATH

Use `clang++` directly without the `clang-tool-chain-` prefix:

```bash
# Add Clang/LLVM to system PATH
clang-tool-chain install clang-env

# Now use directly
clang hello.c -o hello
clang++ hello.cpp -o hello

# Remove from PATH
clang-tool-chain uninstall clang-env
```

**Note:** Uses the `setenvironment` package to modify system/user PATH persistently. Changes take effect in new terminal sessions.

## Managing Toolchains

### Check Installation Status

```bash
# Show installed toolchains and paths
clang-tool-chain info

# Run diagnostic tests
clang-tool-chain test
```

### Remove Toolchains

```bash
# Remove all downloaded toolchains
clang-tool-chain purge          # Interactive confirmation
clang-tool-chain purge --yes    # Skip confirmation (for scripts)
```

This removes `~/.clang-tool-chain/` directory. Toolchains will re-download on next use.

## Common Workflows

### Multi-File Project

```bash
# Compile multiple files
clang-tool-chain-c main.c utils.c math.c -o program

# Or use object files
clang-tool-chain-c -c main.c -o main.o
clang-tool-chain-c -c utils.c -o utils.o
clang-tool-chain-c main.o utils.o -o program
```

### Static Library

```bash
# Create object files
clang-tool-chain-c -c lib.c -o lib.o

# Create static library
clang-tool-chain-ar rcs libmylib.a lib.o

# Link against it
clang-tool-chain-c main.c -L. -lmylib -o program
```

### Compilation with Caching (sccache)

```bash
# Install sccache support
pip install clang-tool-chain[sccache]

# Compile with caching
clang-tool-chain-sccache-cpp main.cpp -o main

# Check cache stats
clang-tool-chain-sccache --show-stats
```

See [sccache Integration](SCCACHE.md) for details.

## Next Steps

### Learn About Tools

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Compiler reference
- [Build Utilities](BUILD_UTILITIES.md) - Build helpers
- [Binary Utilities](BINARY_UTILS.md) - LLVM binary tools
- [Format & Lint](FORMAT_LINT.md) - Code quality tools
- [IWYU](IWYU.md) - Include analyzer
- [LLDB](LLDB.md) - Debugger
- [Emscripten](EMSCRIPTEN.md) - WebAssembly
- [Cosmopolitan](COSMOCC.md) - Portable executables

### Integration Guides

- [CI/CD Integration](CICD_INTEGRATION.md) - GitHub Actions, GitLab CI, Docker
- [Examples](EXAMPLES.md) - Code examples and workflows
- [Configuration](CONFIGURATION.md) - Environment variables

### Advanced Topics

- [Advanced Topics](ADVANCED.md) - Offline mode, version pinning, airgapped setup
- [Architecture](ARCHITECTURE.md) - Technical architecture
- [Performance](PERFORMANCE.md) - Benchmarks and optimization

### Need Help?

- [FAQ](FAQ.md) - Frequently asked questions
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [GitHub Issues](https://github.com/zackees/clang-tool-chain/issues) - Report bugs

## Summary

```bash
# Install
pip install clang-tool-chain

# Compile
clang-tool-chain-cpp hello.cpp -o hello

# Run
./hello
```

That's it! Happy compiling!
