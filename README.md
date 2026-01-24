# Clang Tool Chain

**Run C++ like a shell script. Build once, run everywhere. The entire C/C++/WASM toolchain in one `pip install`.**

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
int main() { std::cout << "Hello, World!\n"; }
```

```bash
chmod +x hello.cpp && ./hello.cpp  # That's it. No makefiles, no build steps.
# First run auto-installs clang-tool-chain via uvx (only needs: pip install uv)
```

**Build Actually Portable Executables with Cosmopolitan:**

```bash
clang-tool-chain-cosmocc hello.c -o hello.com
# This .com file runs natively on Windows, Linux, macOS, FreeBSD - unchanged.
```

**One `pip install`, 35+ tools auto-download:** Full Clang/LLVM 21 • Complete Emscripten/WASM pipeline • IWYU • clang-format/tidy • LLDB debugger • Cosmopolitan libc • No admin rights needed • Works offline after first use

[![PyPI version](https://img.shields.io/pypi/v/clang-tool-chain.svg)](https://pypi.org/project/clang-tool-chain/)
[![Downloads](https://pepy.tech/badge/clang-tool-chain)](https://pepy.tech/project/clang-tool-chain)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Linting](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml)

## ⚡ Quick Start

```bash
# Install
pip install clang-tool-chain

# Compile C/C++ - toolchain auto-downloads on first use (~71-91 MB)
clang-tool-chain-c hello.c -o hello
clang-tool-chain-cpp hello.cpp -o hello
./hello
```

**Build systems:** Set `CC=clang-tool-chain-c` and `CXX=clang-tool-chain-cpp` for Make/CMake/Meson.

**WebAssembly:** `clang-tool-chain-emcc game.c -o game.js && node game.js`

**Portable executables:** `clang-tool-chain-cosmocc hello.c -o hello.com` (runs on Windows/Linux/macOS/FreeBSD)

**Executable scripts:** Add shebang `#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached` to C++ files.

**📖 [Complete Quick Start Guide](docs/QUICKSTART.md)** - Detailed examples, CMake integration, workflows, tips.

---

## 📊 Test Matrix

Comprehensive test coverage across all platforms and tool categories ensures reliability and quality.

**40 GitHub Actions workflows** covering all platform+tool combinations:
- **5 platforms:** Windows x64, Linux x86_64, Linux ARM64, macOS x86_64, macOS ARM64
- **8 tool categories:** clang, clang-sccache, emscripten, emscripten-sccache, iwyu, lldb, format-lint, binary-utils, cosmocc

### Live Test Status

| Tool Category | Windows x64 | Linux x86_64 | Linux ARM64 | macOS x86_64 | macOS ARM64 |
|---------------|-------------|--------------|-------------|--------------|-------------|
| **clang** | [![clang-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-win.yml) | [![clang-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-x86.yml) | [![clang-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-linux-arm.yml) | [![clang-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-x86.yml) | [![clang-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-macos-arm.yml) |
| **clang+sccache** | [![clang-sccache-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-win.yml) | [![clang-sccache-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-x86.yml) | [![clang-sccache-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-linux-arm.yml) | [![clang-sccache-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-x86.yml) | [![clang-sccache-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-clang-sccache-macos-arm.yml) |
| **emscripten** | [![emscripten-windows-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-windows-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-windows-x86.yml) | [![emscripten-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-x86.yml) | [![emscripten-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-linux-arm.yml) | [![emscripten-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-x86.yml) | [![emscripten-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-macos-arm.yml) |
| **emscripten+sccache** | [![emscripten-sccache-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-win.yml) | [![emscripten-sccache-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-x86.yml) | [![emscripten-sccache-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-linux-arm.yml) | [![emscripten-sccache-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-x86.yml) | [![emscripten-sccache-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-emscripten-sccache-macos-arm.yml) |
| **iwyu** | [![iwyu-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-win.yml) | [![iwyu-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-x86.yml) | [![iwyu-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-linux-arm.yml) | [![iwyu-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-x86.yml) | [![iwyu-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml) |
| **format-lint** | [![format-lint-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-win.yml) | [![format-lint-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-x86.yml) | [![format-lint-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-linux-arm.yml) | [![format-lint-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-x86.yml) | [![format-lint-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-format-lint-macos-arm.yml) |
| **binary-utils** | [![binary-utils-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-win.yml) | [![binary-utils-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-x86.yml) | [![binary-utils-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-linux-arm.yml) | [![binary-utils-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-x86.yml) | [![binary-utils-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-binary-utils-macos-arm.yml) |
| **lldb** | [![lldb-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-win.yml) | [![lldb-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-x86.yml) | [![lldb-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-arm.yml) | [![lldb-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-x86.yml) | [![lldb-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-arm.yml) |
| **cosmocc** | [![cosmocc-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-win.yml) | [![cosmocc-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-x86.yml) | [![cosmocc-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-arm.yml) | [![cosmocc-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-x86.yml) | [![cosmocc-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-arm.yml) |

**📖 [Complete Test Matrix Documentation](docs/TEST_MATRIX.md)** - Tool category descriptions, test organization, running tests locally.

---

## 📋 All Commands (41 Total)

Comprehensive reference of all available commands organized by category.

### Compiler Commands (6)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-c` | C compiler (GNU ABI, cross-platform) |
| `clang-tool-chain-cpp` | C++ compiler (GNU ABI, cross-platform) |
| `clang-tool-chain-c-msvc` | C compiler (MSVC ABI, Windows only) |
| `clang-tool-chain-cpp-msvc` | C++ compiler (MSVC ABI, Windows only) |
| `clang-tool-chain-cosmocc` | C compiler for Actually Portable Executables |
| `clang-tool-chain-cosmocpp` | C++ compiler for Actually Portable Executables |

### Compiler Commands with sccache (5)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-sccache-c` | Cached C compiler (GNU ABI) |
| `clang-tool-chain-sccache-cpp` | Cached C++ compiler (GNU ABI) |
| `clang-tool-chain-sccache-c-msvc` | Cached C compiler (MSVC ABI, Windows only) |
| `clang-tool-chain-sccache-cpp-msvc` | Cached C++ compiler (MSVC ABI, Windows only) |
| `clang-tool-chain-sccache-stats` | Display sccache statistics |

### Build Utilities (3)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-build` | Build source files with caching |
| `clang-tool-chain-build-run` | Build and execute with caching |
| `clang-tool-chain-run` | Execute cached binary (no rebuild) |

### Binary Utilities (11)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-ar` | Create, modify, extract from archives (llvm-ar) |
| `clang-tool-chain-ranlib` | Generate archive symbol index (llvm-ranlib) |
| `clang-tool-chain-nm` | Display symbol table (llvm-nm) |
| `clang-tool-chain-objdump` | Disassemble and analyze binaries (llvm-objdump) |
| `clang-tool-chain-readelf` | Display ELF file information (llvm-readelf) |
| `clang-tool-chain-readobj` | Display object file information (llvm-readobj) |
| `clang-tool-chain-size` | Display section sizes (llvm-size) |
| `clang-tool-chain-strings` | Extract printable strings (llvm-strings) |
| `clang-tool-chain-strip` | Remove symbols from binaries (llvm-strip) |
| `clang-tool-chain-cxxfilt` | Demangle C++ symbols (llvm-cxxfilt) |
| `clang-tool-chain-symbolizer` | Symbolize stack traces (llvm-symbolizer) |

### Format & Lint (2)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-format` | Format C/C++ code (clang-format) |
| `clang-tool-chain-tidy` | Static analysis and linting (clang-tidy) |

### IWYU - Include Analyzer (3)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-iwyu` | Analyze #include usage (include-what-you-use) |
| `clang-tool-chain-iwyu-tool` | Run IWYU on compilation database |
| `clang-tool-chain-fix-includes` | Auto-fix includes from IWYU output |

### LLDB - Debugger (2)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-lldb` | Interactive debugger and crash analyzer (lldb) |
| `clang-tool-chain-lldb-check-python` | Verify Python 3.10 integration status |

### Emscripten - WebAssembly (5)

| Command | Description |
|---------|-------------|
| `clang-tool-chain-emcc` | Emscripten C compiler (C/C++ → WebAssembly) |
| `clang-tool-chain-empp` | Emscripten C++ compiler (C/C++ → WebAssembly) |
| `clang-tool-chain-emar` | Emscripten archiver for WebAssembly libraries |
| `clang-tool-chain-sccache-emcc` | Cached Emscripten C compiler |
| `clang-tool-chain-sccache-empp` | Cached Emscripten C++ compiler |

### Management & Diagnostics (4)

| Command | Description |
|---------|-------------|
| `clang-tool-chain` | Main CLI (install, purge, info, help) |
| `clang-tool-chain-test` | Run diagnostic tests (7 checks) |
| `clang-tool-chain-fetch` | Download toolchain components |
| `clang-tool-chain-paths` | Display installation paths |

**Total: 41 commands** providing complete C/C++/WebAssembly toolchain capabilities.

---

## 📑 Table of Contents

### Getting Started
- [Quick Start](#-quick-start)
- [Test Matrix](#-test-matrix) - Live CI/CD status for all platforms
- [All Commands](#-all-commands-41-total) - Complete command reference
- [Installation](#-installation)
- [Why clang-tool-chain?](#-why-clang-tool-chain)

### Tools by Category
- [Clang/LLVM Toolchain](#️-clangllvm-toolchain) - C/C++ compilation (17 commands)
- [Build Utilities](#-build-utilities) - build, build-run, run (3 commands)
- [Binary Utilities](#-binary-utilities) - ar, nm, objdump, strip, readelf (11 commands)
- [Format & Lint](#-format--lint) - clang-format, clang-tidy (2 commands)
- [IWYU](#-iwyu-include-what-you-use) - Include analyzer (3 commands)
- [LLDB](#-lldb-debugger) - Debugger with Python support (2 commands)
- [Emscripten](#-emscripten-webassembly) - WebAssembly compiler (5 commands)
- [Cosmopolitan](#-cosmopolitan-actually-portable-executables) - APE compiler (2 commands)
- [Management CLI](#️-management-cli) - install, purge, info, test (4 commands)

### Cross-Cutting Features
- [Inlined Build Directives](#-inlined-build-directives)
- [Executable C++ Scripts](#-executable-c-scripts-shebang-support)
- [Windows DLL Deployment](#-windows-dll-deployment)
- [sccache Integration](#-sccache-integration)

### Platform & Configuration
- [Platform Support Matrix](#-platform-support-matrix)
- [Windows Target Selection](#-windows-target-selection)
- [Configuration](#️-configuration)
- [Performance](#-performance)

### Integration & Examples
- [CI/CD Integration](#-cicd-integration)
- [Examples](#-examples)

### Reference & Help
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)
- [Security](#-security)
- [Advanced Topics](#-advanced-topics)

### Development
- [Development](#-development)
- [Contributing](#-contributing)
- [Maintainer Tools](#️-maintainer-tools)

### Documentation
- [Detailed Documentation](#-detailed-documentation)

---

## 🛠️ Clang/LLVM Toolchain

**17 commands** • Modern C/C++ compiler • Auto SDK detection • GNU/MSVC ABI • sccache support

### Platform & Version Matrix

| Platform | Architecture | LLVM Version | Archive Size | Linker | Status |
|----------|--------------|--------------|--------------|--------|--------|
| Windows  | x86_64       | 21.1.5       | ~71-90 MB    | lld    | ✅ Stable |
| Linux    | x86_64       | 21.1.5       | ~87 MB       | lld    | ✅ Stable |
| Linux    | ARM64        | 21.1.5       | ~91 MB       | lld    | ✅ Stable |
| macOS    | x86_64       | 21.1.6       | ~77 MB       | ld64.lld | ✅ Stable |
| macOS    | ARM64        | 21.1.6       | ~71 MB       | ld64.lld | ✅ Stable |

### Windows ABI Selection

| Feature | GNU ABI (Default) | MSVC ABI |
|---------|-------------------|----------|
| **Commands** | `clang-tool-chain-c/cpp` | `clang-tool-chain-c/cpp-msvc` |
| **Cross-platform** | ✅ Yes | ❌ Windows only |
| **Visual Studio** | ❌ Not needed | ✅ Required |
| **MinGW Headers** | ✅ Integrated (~176 MB) | ❌ N/A |
| **DLL Deployment** | ✅ Automatic | ❌ Uses MSVC runtime |
| **C++ Standard** | ✅ C++11+ | ✅ C++14+ |
| **Use Case** | Cross-platform projects | Windows-native MSVC projects |

### Quick Examples

```bash
# GNU ABI (cross-platform, default)
clang-tool-chain-cpp hello.cpp -o hello

# MSVC ABI (Windows native)
clang-tool-chain-cpp-msvc main.cpp -o program.exe

# Build system integration
export CC=clang-tool-chain-c CXX=clang-tool-chain-cpp
```

**📖 [Complete Documentation](docs/CLANG_LLVM.md)** - Command reference, environment variables, SDK detection, ABI selection, sanitizers, build system integration.

---

## 🔨 Build Utilities

**3 commands** • SHA256 caching • Shebang support • Auto-run

```bash
clang-tool-chain-build-run --cached hello.cpp
chmod +x script.cpp && ./script.cpp
```

**📖 [Complete Documentation](docs/BUILD_UTILITIES.md)** - Caching details, shebang setup, TDD workflows.

---

## 🔧 Binary Utilities

**11 commands** • LLVM binary tools • ELF/PE/Mach-O support • Archives & symbols

```bash
clang-tool-chain-ar rcs libmylib.a obj1.o obj2.o
clang-tool-chain-nm --demangle program
clang-tool-chain-objdump -d program
```

**📖 [Complete Documentation](docs/BINARY_UTILS.md)** - All commands, symbol inspection, archive creation, disassembly.

---

## ✨ Format & Lint

**2 commands** • clang-format • clang-tidy • Auto-formatting & static analysis

```bash
clang-tool-chain-format -i src/*.cpp
clang-tool-chain-tidy -fix file.cpp -- -std=c++17
```

**📖 [Complete Documentation](docs/FORMAT_LINT.md)** - Configuration, style presets, IDE integration, CI/CD examples.

---

## 📐 IWYU (Include What You Use)

**3 commands** • Include analyzer • Auto-fix • Build time optimization

### Platform Support Matrix

| Platform | Architecture | IWYU Version | Status | Notes |
|----------|--------------|--------------|--------|-------|
| Windows  | x86_64       | 0.21         | ⚠️ Partial | Basic analysis works, some limitations |
| Linux    | x86_64       | 0.21         | ✅ Full | All features supported |
| Linux    | ARM64        | 0.21         | ✅ Full | All features supported |
| macOS    | x86_64       | 0.21         | ✅ Full | All features supported |
| macOS    | ARM64        | 0.21         | ✅ Full | All features supported |

### Quick Examples

```bash
# Analyze includes with auto-fix
clang-tool-chain-iwyu file.cpp -- -std=c++17 | clang-tool-chain-fix-includes

# Run on entire build directory
clang-tool-chain-iwyu-tool -p build/
```

**📖 [Complete Documentation](docs/IWYU.md)** - Usage guide, CMake integration, auto-fix workflows, CI/CD.

---

## 🐛 LLDB Debugger

**2 commands** • Interactive debugging • Crash analysis • Python 3.10 support

### Platform & Python Support Matrix

| Platform | Architecture | LLDB Version | Python 3.10 | Status | Notes |
|----------|--------------|--------------|-------------|--------|-------|
| Windows  | x86_64       | 21.1.5       | ⏳ Pending  | ✅ Basic | Archive rebuild needed for Python support |
| Linux    | x86_64       | 21.1.5       | ✅ Ready    | ✅ Full | Wrapper complete, archives pending |
| Linux    | ARM64        | 21.1.5       | ✅ Ready    | ✅ Full | Wrapper complete, archives pending |
| macOS    | x86_64       | 21.1.6       | ⏳ Planned  | ✅ Basic | Python integration planned |
| macOS    | ARM64        | 21.1.6       | ⏳ Planned  | ✅ Basic | Python integration planned |

**Python 3.10 Features:** Full backtraces (`bt all`), Python scripting, advanced variable inspection, LLDB Python API

### Quick Examples

```bash
# Compile with debug symbols
clang-tool-chain-cpp -g program.cpp -o program

# Interactive debugging
clang-tool-chain-lldb program

# Crash analysis mode (Windows)
clang-tool-chain-lldb --print crash_test.exe

# Check Python integration status
clang-tool-chain-lldb-check-python
```

**📖 [Complete Documentation](docs/LLDB.md)** - Commands, Python integration, crash analysis, platform status.

---

## 🌐 Emscripten (WebAssembly)

**5 commands** • C/C++ → WASM • Bundled Node.js • sccache support

### Platform & Version Matrix

| Platform | Architecture | Emscripten | Node.js | LLVM (bundled) | Status |
|----------|--------------|------------|---------|----------------|--------|
| Windows  | x86_64       | 4.0.19     | 20.18.2 | 22.0.0         | ✅ Full |
| Linux    | x86_64       | 4.0.21     | 20.18.2 | 22.0.0         | ✅ Full |
| Linux    | ARM64        | 4.0.21     | 20.18.2 | 22.0.0         | ✅ Full |
| macOS    | x86_64       | 4.0.19     | 20.18.2 | 22.0.0         | ✅ Full |
| macOS    | ARM64        | 4.0.19     | 20.18.2 | 22.0.0         | ✅ Full |

**Note:** Emscripten includes its own bundled LLVM 22.0.0, separate from the main clang-tool-chain LLVM (21.1.5/21.1.6).

### Quick Examples

```bash
# Compile to WebAssembly
clang-tool-chain-emcc hello.c -o hello.js
node hello.js  # Run with bundled Node.js

# Browser output
clang-tool-chain-emcc game.c -o game.html

# With sccache for faster rebuilds
clang-tool-chain-sccache-emcc main.c -o main.js
```

**📖 [Complete Documentation](docs/EMSCRIPTEN.md)** - Usage guide, optimization, browser integration, [Node.js details](docs/NODEJS.md).

---

## 🌍 Cosmopolitan (Actually Portable Executables)

**2 commands** • Build-once run-anywhere • Single binary • No runtime deps

### Universal Platform Support

| Build Platform | Architecture | Cosmocc Version | Output Format | Status |
|----------------|--------------|-----------------|---------------|--------|
| Windows        | x86_64       | 4.0.2           | .com (APE)    | ✅ Full |
| Linux          | x86_64       | 4.0.2           | .com (APE)    | ✅ Full |
| Linux          | ARM64        | 4.0.2           | .com (APE)    | ✅ Full |
| macOS          | x86_64       | 4.0.2           | .com (APE)    | ✅ Full |
| macOS          | ARM64        | 4.0.2           | .com (APE)    | ✅ Full |

**APE Runtime Support:** Windows x64, Linux x64/ARM64, macOS x64/ARM64, FreeBSD, NetBSD, OpenBSD

**Note:** Cosmocc produces identical .com files on all platforms - the output is "Actually Portable" and runs natively on all supported operating systems without modification.

### Quick Examples

```bash
# Install cosmocc toolchain
clang-tool-chain install cosmocc

# Build portable executable
clang-tool-chain-cosmocc hello.c -o hello.com
clang-tool-chain-cosmocpp hello.cpp -o hello.com

# The .com file runs on ANY supported OS
./hello.com  # Works on Linux, macOS, FreeBSD, etc.
# On Windows: hello.com
```

**📖 [Complete Documentation](docs/COSMOCC.md)** - Usage guide, APE format, platform support, [Cosmopolitan project](https://github.com/jart/cosmopolitan).

---

## ⚙️ Management CLI

**4 diagnostic commands + 1 main CLI** • Pre-install • PATH management • Diagnostics • Cleanup

### Main CLI Subcommands

```bash
clang-tool-chain install <target>    # Pre-install toolchains
clang-tool-chain uninstall <target>  # Remove PATH entries
clang-tool-chain purge              # Remove all downloaded toolchains
clang-tool-chain info               # Show installation details
clang-tool-chain help               # Show help message
```

**Available Targets:**
- `clang` - Core Clang/LLVM toolchain
- `clang-env` - Add Clang binaries to system PATH
- `iwyu` - Include What You Use analyzer
- `iwyu-env` - Add IWYU to system PATH
- `lldb` - LLDB debugger
- `lldb-env` - Add LLDB to system PATH
- `emscripten` - Emscripten WebAssembly SDK
- `emscripten-env` - Add Emscripten to system PATH
- `cosmocc` - Cosmopolitan Libc toolchain

### Diagnostic Commands

```bash
clang-tool-chain-test     # Run 7 diagnostic tests
clang-tool-chain-fetch    # Download toolchain components
clang-tool-chain-paths    # Display installation paths
```

### Quick Examples

```bash
# Pre-install Clang toolchain
clang-tool-chain install clang

# Add to system PATH (no clang-tool-chain- prefix needed)
clang-tool-chain install clang-env
clang++ hello.cpp -o hello  # Use directly

# Check installation status
clang-tool-chain info

# Run diagnostics
clang-tool-chain test

# Clean everything
clang-tool-chain purge --yes
```

**📖 [Complete Documentation](docs/MANAGEMENT_CLI.md)** - Full command reference, workflows, installation targets.

---

## 🚀 Executable C++ Scripts (Shebang Support)

Run C++ files directly like shell scripts with native performance.

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>
int main() { std::cout << "Hello!\n"; }
```

```bash
chmod +x script.cpp && ./script.cpp
```

**📖 [Complete Documentation](docs/EXECUTABLE_SCRIPTS.md)** - Examples, TDD workflows, platform setup.

---

## 📝 Inlined Build Directives

Embed build configuration in source files - no makefiles needed.

```cpp
// @link: [pthread, m]
// @std: c++17
#include <pthread.h>
int main() { /* code */ }
```

```bash
clang-tool-chain-cpp file.cpp -o program  # Auto-detects!
```

**📖 [Complete Documentation](docs/DIRECTIVES.md)** - Full directive reference, cross-platform examples.

---

## ⚡ sccache Integration

Optional compilation caching for 2-10x faster rebuilds.

```bash
pip install clang-tool-chain[sccache]
clang-tool-chain-sccache-cpp main.cpp -o main
```

**📖 [Complete Documentation](docs/SCCACHE.md)** - Installation, configuration, backends, benchmarks.

---

## 📦 Installation

```bash
pip install clang-tool-chain
```

Toolchain downloads automatically on first use - no setup needed!

### Installation Options

```bash
# Option 1: Auto-download (recommended)
clang-tool-chain-c hello.c -o hello  # Downloads on first use

# Option 2: Pre-install
clang-tool-chain install clang       # Pre-download (~71-91 MB)

# Option 3: Add to PATH
clang-tool-chain install clang-env   # Use 'clang' directly
```

**📖 [Complete Documentation](docs/INSTALLATION.md)** - From-source installation, upgrading, uninstallation, offline setup.

---

## 🎯 Why clang-tool-chain?

**The Problem:** Traditional LLVM needs 1-3 GB downloads, admin rights, manual PATH setup.

**The Solution:** 71-91 MB, auto-download, no admin rights, works everywhere.

| Feature | clang-tool-chain | Full LLVM | zig cc |
|---------|------------------|-----------|--------|
| **Size** | 71-91 MB | 1-3 GB | ~80 MB |
| **Admin** | ❌ No | ✅ Yes | ❌ No |
| **Auto Download** | ✅ Yes | ❌ No | ✅ Yes |
| **Version Pin** | ✅ requirements.txt | ❌ No | ⚠️ Tied to Zig |
| **Python** | ✅ Native | ❌ Manual | ❌ Manual |

**Perfect for:** CI/CD • Education • Teams • Python projects • Quick prototyping

**📖 [Complete Documentation](docs/WHY.md)** - Detailed comparison, use cases, tradeoff analysis.

---

## ✨ Features

41 wrapper commands • Auto-download • 94% size reduction • Cross-platform

- **Zero Configuration** - Auto-downloads to `~/.clang-tool-chain/`
- **Ultra-Compact** - 71-91 MB (94% smaller via zstd-22)
- **41 Commands** - Clang/LLVM, Emscripten, IWYU, LLDB, formatters, binary utils
- **Cross-Platform** - Windows x64, macOS x64/ARM64, Linux x64/ARM64
- **Concurrent-Safe** - File locking for parallel builds
- **Python Native** - Seamless Python integration

**📖 [Complete Documentation](docs/FEATURES.md)** - All 41 commands by category, detailed capabilities.

---

## 📚 Examples

```cpp
#include <iostream>
int main() {
    std::cout << "Hello from clang-tool-chain!" << std::endl;
    return 0;
}
```

```bash
clang-tool-chain-cpp hello.cpp -o hello && ./hello
clang-tool-chain-c main.c utils.c math.c -o program
```

**📖 [Complete Documentation](docs/EXAMPLES.md)** - Multi-file projects, static libraries, CMake, WebAssembly, Cosmopolitan, executable scripts, directives, Windows examples, IWYU, formatting, debugging, sccache, binary utilities.

---

## 🚀 CI/CD Integration

```yaml
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
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install clang-tool-chain
      - run: clang-tool-chain-cpp main.cpp -o program
```

**📖 [Complete Documentation](docs/CICD_INTEGRATION.md)** - GitHub Actions with caching, GitLab CI, Docker, Azure Pipelines, CircleCI, Travis CI, multi-platform matrices, best practices.

---

## 🌍 Platform Support Matrix

| Platform | Architecture | LLVM Version | Archive Size | Status |
|----------|--------------|--------------|--------------|--------|
| Windows  | x86_64       | 21.1.5       | ~71-90 MB    | ✅ Stable |
| Linux    | x86_64       | 21.1.5       | ~87 MB       | ✅ Stable |
| Linux    | ARM64        | 21.1.5       | ~91 MB       | ✅ Stable |
| macOS    | x86_64       | 19.1.7       | ~77 MB       | ✅ Stable |
| macOS    | ARM64        | 21.1.6       | ~71 MB       | ✅ Stable |

**Requirements:** Python 3.10+, ~100-400 MB disk space

**📖 [Complete Documentation](docs/PLATFORM_SUPPORT.md)** - Detailed requirements, LLVM versions, tool-specific support, CI/CD compatibility.

---

## ⚙️ Configuration

**Key Environment Variables:**
- `CLANG_TOOL_CHAIN_DOWNLOAD_PATH` - Override installation location
- `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS` - Disable Windows DLL deployment
- `CLANG_TOOL_CHAIN_USE_SYSTEM_LD` - Use system linker instead of LLD
- `CLANG_TOOL_CHAIN_NO_DIRECTIVES` - Disable inlined build directives
- `SDKROOT` - Custom macOS SDK path (auto-detected by default)

**📖 [Complete Documentation](docs/CONFIGURATION.md)** - All environment variables, macOS SDK, Windows DLL settings, sccache backends.

---

## ⚡ Performance

**Compilation:** Identical to official LLVM (native binaries, zero wrapper overhead).

**Downloads:** ~5 seconds (100 Mbps) or ~25 seconds (20 Mbps). Subsequent use: instant.

**📖 [Complete Documentation](docs/PERFORMANCE.md)** - Detailed benchmarks, sccache speedups, memory usage, optimization tips.

---

## 🎯 Windows Target Selection

```bash
# Default: GNU ABI (MinGW-w64) - Cross-platform, no VS required
clang-tool-chain-cpp hello.cpp -o hello

# MSVC ABI - Windows-native projects, requires Visual Studio
clang-tool-chain-cpp-msvc main.cpp -o program.exe
```

| Feature | GNU ABI | MSVC ABI |
|---------|---------|----------|
| Cross-platform | ✅ Yes | ❌ No |
| Visual Studio | ❌ Not needed | ✅ Required |
| C++11 strict | ✅ Yes | ❌ C++14+ |

**📖 [Complete Documentation](docs/WINDOWS_TARGET_SELECTION.md)** - Detailed comparison, DLL deployment, troubleshooting, recommendations.

---

## 🪟 Windows DLL Deployment

Automatic MinGW runtime DLL deployment for Windows executables (GNU ABI). Programs run immediately without PATH setup.

**📖 [Complete Documentation](docs/DLL_DEPLOYMENT.md)** - Environment variables, troubleshooting.

---

## 🔧 How It Works

Auto-downloads on first use (~71-91 MB, 10-60 seconds). Subsequent uses are instant.

**📖 [Complete Documentation](docs/HOW_IT_WORKS.md)** - Architecture, download process, installation paths, technical details.

---

## 🔧 Additional Utilities

Diagnostic commands: `clang-tool-chain-test`, `clang-tool-chain-fetch`, `clang-tool-chain-paths`

**📖 [Complete Documentation](docs/ADDITIONAL_UTILITIES.md)** - Detailed usage, scripting integration.

---

## 🔬 Advanced Topics

Offline mode • Version pinning • Airgapped environments • Custom paths • Docker • Advanced sccache

**📖 [Complete Documentation](docs/ADVANCED.md)** - Complete guides for advanced use cases.

---

## ❓ FAQ

Common questions about first use, offline mode, updates, disk space, Docker, CMake, platform requirements.

**📖 [Complete Documentation](docs/FAQ.md)** - Frequently asked questions with detailed answers.

---

## 🔍 Troubleshooting

Common issues: binaries not found, download failures, permissions, platform requirements.

```bash
clang-tool-chain-test  # Run diagnostics
clang-tool-chain info  # Check installation
```

**📖 [Complete Documentation](docs/TROUBLESHOOTING.md)** - Detailed solutions to common issues.

---

## 🔒 Security

SHA256 verification • Safe extraction • HTTPS-only • Transparent trust model

**📖 [Complete Documentation](docs/SECURITY.md)** - Verification procedures, trust model details.

---

## 👨‍💻 Development

```bash
git clone https://github.com/zackees/clang-tool-chain.git
cd clang-tool-chain
./install              # Install dependencies (uses uv)
./test                 # Run tests
./lint                 # Run linters
```

**📖 [Testing Guide](docs/TESTING.md)** - Platform-specific tests, CI/CD integration, writing new tests.

---

## 🤝 Contributing

Want to add a new tool? See the **[Contributing Guide](docs/CONTRIBUTING.md)** for step-by-step instructions.

**Key topics:**
- Codebase structure and architecture
- Creating installers for new tools
- Registering entry points in `pyproject.toml`
- Creating binary archives and manifests
- Adding tests and CI workflows
- Platform-specific considerations

Designed for both human developers and AI agents.

---

## 🛠️ Maintainer Tools

For creating and updating binary archives, see the **[Maintainer Guide](docs/MAINTAINER.md)**.

**Topics:** Archive creation, binary stripping, compression, manifests, checksums, MinGW sysroot, LLDB builds, dependency troubleshooting.

---

## 📚 Detailed Documentation

For in-depth information on specific topics, see the documentation in the `docs/` directory:

### Tools & Features
| Document | Description |
|----------|-------------|
| **[Features Overview](docs/FEATURES.md)** | Complete feature list and all 41 commands |
| **[Clang/LLVM Toolchain](docs/CLANG_LLVM.md)** | Compiler wrappers, macOS SDK detection, Windows GNU/MSVC ABI |
| **[Build Utilities](docs/BUILD_UTILITIES.md)** | Build, build-run, caching, shebang support |
| **[Binary Utilities](docs/BINARY_UTILS.md)** | LLVM binary tools (ar, nm, objdump, strip, etc.) |
| **[Format & Lint](docs/FORMAT_LINT.md)** | clang-format and clang-tidy |
| **[IWYU](docs/IWYU.md)** | Include What You Use analyzer |
| **[LLDB Debugger](docs/LLDB.md)** | LLVM debugger with Python support |
| **[Emscripten](docs/EMSCRIPTEN.md)** | WebAssembly compilation |
| **[Cosmopolitan Libc](docs/COSMOCC.md)** | Actually Portable Executables (APE) |
| **[sccache Integration](docs/SCCACHE.md)** | Compilation caching (2-10x speedup) |
| **[Inlined Build Directives](docs/DIRECTIVES.md)** | Self-contained source files |

### Setup & Configuration
| Document | Description |
|----------|-------------|
| **[Quick Start Guide](docs/QUICKSTART.md)** | Comprehensive quick start with all major features |
| **[Getting Started](docs/GETTING_STARTED.md)** | Platform-specific setup and common workflows |
| **[Installation Guide](docs/INSTALLATION.md)** | Installation, upgrading, uninstallation |
| **[Management CLI](docs/MANAGEMENT_CLI.md)** | CLI commands (install, purge, info, test) |
| **[Platform Support](docs/PLATFORM_SUPPORT.md)** | Platform matrix, requirements, compatibility |
| **[Configuration](docs/CONFIGURATION.md)** | Environment variables and settings |
| **[Windows Target Selection](docs/WINDOWS_TARGET_SELECTION.md)** | GNU vs MSVC ABI selection |
| **[DLL Deployment](docs/DLL_DEPLOYMENT.md)** | Windows MinGW DLL automatic deployment |

### Integration & Usage
| Document | Description |
|----------|-------------|
| **[Examples](docs/EXAMPLES.md)** | Code examples and workflows |
| **[Executable Scripts](docs/EXECUTABLE_SCRIPTS.md)** | Shebang support details |
| **[CI/CD Integration](docs/CICD_INTEGRATION.md)** | GitHub Actions, GitLab CI, Docker, Azure |
| **[Additional Utilities](docs/ADDITIONAL_UTILITIES.md)** | Test, fetch, paths commands |

### Technical & Reference
| Document | Description |
|----------|-------------|
| **[Why clang-tool-chain?](docs/WHY.md)** | Comparison matrix, use cases, tradeoff analysis |
| **[How It Works](docs/HOW_IT_WORKS.md)** | Architecture, download process, technical details |
| **[Advanced Topics](docs/ADVANCED.md)** | Offline mode, version pinning, airgapped setup, Docker |
| **[Performance](docs/PERFORMANCE.md)** | Benchmarks and optimization |
| **[Security](docs/SECURITY.md)** | Security practices and verification |
| **[Architecture](docs/ARCHITECTURE.md)** | Technical architecture, manifest system |
| **[Parallel Downloads](docs/PARALLEL_DOWNLOADS.md)** | Multi-threaded range requests |
| **[Node.js Integration](docs/NODEJS.md)** | Bundled Node.js runtime |
| **[Test Matrix](docs/TEST_MATRIX.md)** | CI/CD test coverage across all platforms |
| **[License Information](docs/LICENSE_INFO.md)** | Complete licensing details for all components |

### Development & Maintenance
| Document | Description |
|----------|-------------|
| **[Testing Guide](docs/TESTING.md)** | Test infrastructure, running tests, CI/CD |
| **[Contributing](docs/CONTRIBUTING.md)** | How to add new tools |
| **[Maintainer Guide](docs/MAINTAINER.md)** | Binary packaging, archive creation |
| **[Acknowledgments](docs/ACKNOWLEDGMENTS.md)** | Credits, licenses, special thanks |
| **[FAQ](docs/FAQ.md)** | Frequently asked questions |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Common issues and solutions |

---

## 📄 License

This package is distributed under the **Apache License 2.0**. Bundled Clang/LLVM binaries use **Apache License 2.0 with LLVM Exception**.

**See [License Information Documentation](docs/LICENSE_INFO.md) for complete licensing details for all components.**

---

## 🙏 Acknowledgments

Thanks to LLVM Project, Zstandard, Emscripten, Cosmopolitan, and all the open source projects that make this possible.

**📖 [Complete Acknowledgments](docs/ACKNOWLEDGMENTS.md)** - Full credits, licenses, and special thanks.

---

## 📊 Changelog

For full version history and release notes, see **[CHANGELOG.md](CHANGELOG.md)**.

**Key highlights:**
- Windows GNU ABI with integrated MinGW headers (single archive download)
- Bundled Node.js runtime for Emscripten users
- Cross-platform support: Windows x64, macOS x64/ARM64, Linux x64/ARM64
- LLVM 21.1.5/21.1.6 with 35+ wrapper commands

---

## 🚀 Getting Started

```bash
pip install clang-tool-chain
echo 'int main() { return 0; }' > hello.c
clang-tool-chain-c hello.c -o hello
./hello
```

That's it! The toolchain downloads automatically.

**📖 [Complete Documentation](docs/GETTING_STARTED.md)** - Installation options, platform-specific notes, common workflows.

---

**Repository:** [github.com/zackees/clang-tool-chain](https://github.com/zackees/clang-tool-chain)
**Issues:** [github.com/zackees/clang-tool-chain/issues](https://github.com/zackees/clang-tool-chain/issues)
**PyPI:** [pypi.org/project/clang-tool-chain/](https://pypi.org/project/clang-tool-chain/)

---

**Keywords:** clang wrapper, llvm python, portable clang, clang installer, llvm toolchain, cross-platform compiler, python clang, automated llvm, clang docker, ci/cd compiler
