# Clang Tool Chain

**Motivation**: *make it as easy to run a cpp program as it does to run a python file.*

**A zero-configuration Python package that distributes pre-built Clang/LLVM binaries with automatic downloading and installation. Cosmopolitan for universal builds.**

[![PyPI version](https://img.shields.io/pypi/v/clang-tool-chain.svg)](https://pypi.org/project/clang-tool-chain/)
[![Downloads](https://pepy.tech/badge/clang-tool-chain)](https://pepy.tech/project/clang-tool-chain)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Linting](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/lint.yml)

## 🔥 Script Your C/C++ Like Python (Unix/Linux/macOS)

Make C/C++ files directly executable with a shebang:

```cpp
#!/usr/bin/env -S clang-tool-chain-build-run
#include <iostream>
int main() {
    std::cout << "Hello, scripted C++!" << std::endl;
    return 0;
}
```

```bash
chmod +x hello.cpp
./hello.cpp  # Compiles and runs in one step!
```

Use `--cached` for faster iterations (skips recompilation if source unchanged):

```cpp
#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <stdio.h>
int main() { printf("Cached execution!\n"); return 0; }
```

> **Note:** This package currently uses:
> - **LLVM 21.1.5** for Windows, Linux (x86_64/ARM64)
> - **LLVM 21.1.6** for macOS ARM64
> - **LLVM 19.1.7** for macOS x86_64
>
> See [Platform Support Matrix](#platform-support-matrix) for details.

## 📑 Table of Contents

- [Quick Start](#-quick-start) - Get compiling in 30 seconds
- [Script C/C++ Like Python](#-script-your-cc-like-python-unixlinuxmacos) - Shebang support for executable source files
- [Inlined Build Directives](#-inlined-build-directives) - Self-contained source files with embedded build config
- [Command Quick Reference](#-command-quick-reference) - Common commands at a glance
- [Installation](#-installation) - Installation options
- [Why clang-tool-chain?](#-why-clang-tool-chain) - Features and comparisons
- [Features](#-features) - Capabilities overview
- [Usage](#-usage) - Detailed usage examples
- [All Available Commands](#all-available-commands) - Complete command reference
- [Examples](#-examples) - Code examples
- [CI/CD Integration](#-cicd-integration) - GitHub Actions, GitLab CI, Docker
- [Platform Support Matrix](#-platform-support-matrix) - Supported platforms
- [Configuration](#️-configuration) - Environment variables
- [Performance](#-performance) - Compilation and download speed
- [Windows Target Selection](#-windows-target-selection) - GNU vs MSVC ABI
- [Windows DLL Deployment](#-windows-dll-deployment) - Automatic DLL handling
- [How It Works](#-how-it-works) - Architecture overview
- [Additional Utilities](#-additional-utilities) - Diagnostic tools (test, fetch, paths)
- [Advanced Topics](#-advanced-topics) - Offline mode, version pinning
- [Troubleshooting](#-troubleshooting) - Common issues
- [FAQ](#-faq) - Frequently asked questions
- [Security](#-security) - Checksum verification and trust model
- [Development](#-development) - Dev setup and testing
- [Contributing](#-contributing) - How to add new tools
- [Maintainer Tools](#️-maintainer-tools) - Archive creation and binary packaging
- [Detailed Documentation](#-detailed-documentation) - Links to all docs
- [Test Matrix](#-test-matrix) - Comprehensive test coverage across all platforms

---

## 📊 Test Matrix

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
| **lldb** | [![lldb-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-win.yml) | [![lldb-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-x86.yml) | [![lldb-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-arm.yml) | [![lldb-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-x86.yml) | [![lldb-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-macos-arm.yml) |
| **cosmocc** | [![cosmocc-win](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-win.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-win.yml) | [![cosmocc-linux-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-x86.yml) | [![cosmocc-linux-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-linux-arm.yml) | [![cosmocc-macos-x86](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-x86.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-x86.yml) | [![cosmocc-macos-arm](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-arm.yml/badge.svg)](https://github.com/zackees/clang-tool-chain/actions/workflows/test-cosmocc-macos-arm.yml) |

**Legend:**
- **clang** - Basic Clang/LLVM compilation (C and C++)
- **clang+sccache** - Clang with sccache compilation caching
- **emscripten** - WebAssembly compilation with Emscripten
- **emscripten+sccache** - Emscripten with sccache caching
- **iwyu** - Include What You Use analyzer
- **format-lint** - clang-format and clang-tidy tools
- **binary-utils** - LLVM binary utilities (ar, nm, objdump, strip, readelf, etc.)
- **lldb** - LLDB debugger for crash analysis and debugging
- **cosmocc** - Cosmopolitan Libc for Actually Portable Executables (APE)

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

---

## 🚀 Executable C++ Scripts (Shebang Support)

**Run C++ files directly like shell scripts!** With clang-tool-chain, you can make C++ files executable and run them without a separate compile step.

### How It Works

Add a shebang line to your C++ file:

```cpp
#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "Hello from executable C++!" << std::endl;
    return 0;
}
```

Then make it executable and run:

```bash
# Linux/macOS
chmod +x script.cpp
./script.cpp

# Windows (Git Bash)
./script.cpp
```

**That's it!** The first run compiles the code, subsequent runs use the cached binary (thanks to `--cached`).

### Why This Is Incredible

- **Scripting with C++ performance** - Write quick scripts that run at native speed
- **No build system needed** - Single-file programs just work
- **Instant iteration** - `--cached` flag skips recompilation when source hasn't changed
- **TDD in C++** - Write inline tests with assertions, run with `./test.cpp`

### Example: Inline Tests

```cpp
#!/usr/bin/env -S clang-tool-chain-build-run --cached
#include <iostream>
#include <cassert>
#include <vector>

template<typename T>
T sum(const std::vector<T>& v) {
    T result = T{};
    for (const auto& x : v) result += x;
    return result;
}

int main() {
    // Inline tests - will abort if any assertion fails
    assert(sum(std::vector<int>{1, 2, 3, 4, 5}) == 15);
    assert(sum(std::vector<double>{1.5, 2.5}) == 4.0);
    assert(sum(std::vector<int>{}) == 0);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}
```

```bash
chmod +x test.cpp && ./test.cpp
# Output: All tests passed!
```

### Alternative: Using `uv run`

If clang-tool-chain isn't globally installed, use `uv run`:

```cpp
#!/usr/bin/env -S uv run clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "Running via uv!" << std::endl;
    return 0;
}
```

This works when run from a project directory with `clang-tool-chain` as a dependency.

### Platform Notes

| Platform | How to Run |
|----------|------------|
| **Linux** | `chmod +x script.cpp && ./script.cpp` |
| **macOS** | `chmod +x script.cpp && ./script.cpp` |
| **Windows (Git Bash)** | `./script.cpp` (Git Bash handles shebang) |
| **Windows (cmd/PowerShell)** | `clang-tool-chain-build-run --cached script.cpp` |

---

## 📝 Inlined Build Directives

**Make your source files self-contained!** Embed build configuration directly in your C/C++ source files.

### The Problem

```bash
# Remembering flags is tedious
clang++ -std=c++17 -lpthread -lm -O2 pthread_math.cpp -o program
```

### The Solution

```cpp
// pthread_math.cpp
// @link: [pthread, m]
// @std: c++17
// @cflags: -O2

#include <pthread.h>
#include <cmath>

int main() {
    // Your pthread + math code
    return 0;
}
```

```bash
# Just compile - directives are parsed automatically!
clang-tool-chain-cpp pthread_math.cpp -o program
```

### Supported Directives

| Directive | Description | Example |
|-----------|-------------|---------|
| `@link` | Link libraries | `// @link: pthread` or `// @link: [pthread, m, dl]` |
| `@std` | C/C++ standard | `// @std: c++17` or `// @std: c11` |
| `@cflags` | Compiler flags | `// @cflags: -O2 -Wall -Wextra` |
| `@ldflags` | Linker flags | `// @ldflags: -rpath /opt/lib` |
| `@include` | Include paths | `// @include: /usr/local/include` |
| `@platform` | Platform-specific | See below |

### Cross-Platform Example

```cpp
// @std: c++17

// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
// @platform: darwin
//   @link: pthread

#include <iostream>
#ifdef _WIN32
#include <winsock2.h>
#else
#include <pthread.h>
#endif

int main() {
    std::cout << "Works on all platforms!" << std::endl;
    return 0;
}
```

### Which Commands Support Directives?

| Command | Support |
|---------|---------|
| `clang-tool-chain-cpp` / `clang-tool-chain-c` | ✅ Yes |
| `clang-tool-chain-cpp-msvc` / `clang-tool-chain-c-msvc` | ✅ Yes |
| `clang-tool-chain-build` / `clang-tool-chain-build-run` | ✅ Yes |

### Debug Mode

```bash
# See what directives are being applied
CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1 clang-tool-chain-cpp myfile.cpp -o myfile
# Output: Directive args from source files: ['-std=c++17', '-lpthread']
```

For full documentation, see **[Inlined Build Directives](docs/DIRECTIVES.md)**.

---

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
# - IWYU (downloads ~53-57 MB on first use of clang-tool-chain-iwyu)
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

#### Upgrading

```bash
# Upgrade the package to get new LLVM versions
pip install --upgrade clang-tool-chain

# Force re-download of toolchains (uses new manifest versions)
clang-tool-chain purge --yes && clang-tool-chain install clang
```

**How upgrading works:**
- Package updates include new manifest files pointing to newer LLVM versions
- Downloaded toolchains are cached in `~/.clang-tool-chain/` and persist across package upgrades
- To get new binaries after upgrading, purge and reinstall (or delete `~/.clang-tool-chain/` manually)
- CI/CD pipelines typically get fresh downloads on each run (no cached toolchains)

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
- **Pre-Built Binaries** - Clang 21.1.5 (Windows, Linux), 21.1.6 (macOS ARM64), 19.1.7 (macOS x86_64)
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

<details id="all-available-commands">
<summary><strong>📋 All Available Commands</strong> (click to expand - 35 wrapper commands)</summary>

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

</details>

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
| macOS    | x86_64       | 19.1.7       | ~77 MB       | ~300 MB        | ✅ Stable |
| macOS    | ARM64        | 21.1.6       | ~71 MB       | ~285 MB        | ✅ Stable |

\* **Windows Downloads:**
  - **GNU target (default):** ~90 MB (71 MB LLVM + 19 MB MinGW-w64 sysroot)
  - **MSVC target (opt-in):** ~71 MB (LLVM only, requires Visual Studio SDK)

**Note:** macOS ARM64 uses LLVM 21.1.6 (Homebrew build). macOS x86_64 uses LLVM 19.1.7 (pending upgrade to 21.x).

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

When building Windows executables with GNU ABI (the default), clang-tool-chain automatically copies required MinGW runtime DLLs to your executable directory. Your programs run immediately in `cmd.exe` without any PATH configuration.

```bash
clang-tool-chain-cpp hello.cpp -o hello.exe
# Output: Deployed 3 MinGW DLL(s) for hello.exe

.\hello.exe  # Works immediately - no PATH setup needed!
```

**Key features:**
- Automatic detection via `llvm-objdump`
- Smart timestamp checking (skips unnecessary copies)
- <100ms overhead per executable
- Non-fatal errors (warnings only)

**Environment variables:**
- `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` - Disable DLL deployment
- `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1` - Enable verbose logging

**Shared library deployment:** Use `--deploy-dependencies` flag for `.dll` files.

For comprehensive documentation including troubleshooting, recursive dependency handling, sanitizer support, and advanced usage, see **[docs/DLL_DEPLOYMENT.md](docs/DLL_DEPLOYMENT.md)**.

---

## 🔧 How It Works

**On first use**, clang-tool-chain automatically:
1. Downloads toolchain archives (~71-91 MB) from GitHub
2. Verifies SHA256 checksums
3. Extracts to `~/.clang-tool-chain/` with file locking for concurrent safety
4. Executes your requested tool

**Installation paths by platform:**

| System | Install Path |
|--------|--------------|
| Windows | `~/.clang-tool-chain/clang/win/x86_64/` |
| Linux x86_64 | `~/.clang-tool-chain/clang/linux/x86_64/` |
| Linux ARM64 | `~/.clang-tool-chain/clang/linux/arm64/` |
| macOS x86_64 | `~/.clang-tool-chain/clang/darwin/x86_64/` |
| macOS ARM64 | `~/.clang-tool-chain/clang/darwin/arm64/` |

For detailed architecture information including the three-layer design, manifest system, multi-part archive support, and Emscripten distribution architecture, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

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

| Topic | Description | Details |
|-------|-------------|---------|
| **Offline Mode** | Works offline after initial download | [FAQ: Offline Usage](docs/FAQ.md#can-i-use-clang-tool-chain-offline) |
| **Version Pinning** | Pin LLVM version via `clang-tool-chain==X.Y.Z` in requirements.txt | [FAQ: Version Management](docs/FAQ.md#version-management) |
| **Concurrent Safety** | File locking prevents race conditions in parallel builds | [Architecture](docs/ARCHITECTURE.md) |
| **Manual Installation** | For airgapped environments (see below) | — |

### Manual Installation (Airgapped Environments)

```bash
# 1. Download archive on internet-connected machine
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/{platform}/{arch}/llvm-*.tar.zst

# 2. Transfer and extract on target machine
mkdir -p ~/.clang-tool-chain/clang/{platform}/{arch}
python -m clang_tool_chain.downloads.expand_archive archive.tar.zst ~/.clang-tool-chain/clang/{platform}/{arch}
touch ~/.clang-tool-chain/clang/{platform}/{arch}/done.txt

# 3. Verify
clang-tool-chain info
```

Replace `{platform}` with `win`, `linux`, or `darwin` and `{arch}` with `x86_64` or `arm64`.

---

## ❓ FAQ

Common questions answered in [docs/FAQ.md](docs/FAQ.md):

- **What happens on first use?** - Auto-download of ~71-91 MB in 10-60 seconds
- **Can I use clang-tool-chain offline?** - Yes, after initial download
- **How do I update LLVM?** - `pip install --upgrade clang-tool-chain`
- **Is it safe to delete `~/.clang-tool-chain/`?** - Yes, binaries re-download on next use
- **How much disk space?** - ~271-441 MB per platform
- **Does this work in Docker?** - Yes, see [CI/CD Integration](#cicd-integration)
- **Can I use this with CMake?** - Yes, see [CMake Integration](#cmake-integration)
- **macOS: Do I need Xcode?** - No, just Command Line Tools: `xcode-select --install`

See [docs/FAQ.md](docs/FAQ.md) for the complete FAQ.

---

## 🔍 Troubleshooting

Quick fixes for common issues. Full guide: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

| Issue | Quick Fix |
|-------|-----------|
| **Binaries not found** | `clang-tool-chain info` then `clang-tool-chain-fetch` |
| **Platform not supported** | Requires Windows 10+, macOS 11+, or Linux glibc 2.27+ (64-bit only) |
| **Download fails** | Check internet, retry, or `rm -rf ~/.clang-tool-chain/` |
| **Permission denied** | `chmod +x ~/.clang-tool-chain/clang/*/bin/*` |
| **macOS: headers not found** | `xcode-select --install` |
| **Import errors** | `pip install --reinstall clang-tool-chain` |
| **Slow first compile** | Normal! Toolchain downloading. Pre-fetch: `clang-tool-chain-fetch` |

**Run diagnostics:**
```bash
clang-tool-chain-test  # Run 7 diagnostic tests
clang-tool-chain info  # Check installation status
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed solutions

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

### Quick Setup

```bash
git clone https://github.com/zackees/clang-tool-chain.git
cd clang-tool-chain
./install              # Install dependencies (uses uv)
```

### Essential Commands

| Task | Command |
|------|---------|
| **Run tests** | `./test` |
| **Run linters** | `./lint` |
| **Single test** | `uv run pytest tests/test_cli.py -v` |
| **Build package** | `uv run python -m build` |

For comprehensive testing documentation including platform-specific tests, CI/CD integration, and writing new tests, see **[Testing Guide](docs/TESTING.md)**.

---

## 🤝 Contributing

Want to add a new tool to clang-tool-chain? See the **[Contributing Guide](docs/CONTRIBUTING.md)** for step-by-step instructions.

The guide covers:
- Codebase structure and architecture
- Creating installers for new tools
- Registering entry points in `pyproject.toml`
- Creating binary archives and manifests
- Adding tests and CI workflows
- Platform-specific considerations

This guide is designed for both human developers and AI agents extending the toolchain.

### Quick Codebase Reference (for Adding Tools)

When adding a new tool, these are the key files to modify:

```
src/clang_tool_chain/
├── installers/           # Tool installers (create new_tool.py here)
│   ├── clang.py          # Reference: main Clang/LLVM installer
│   ├── iwyu.py           # Reference: separate archive installer
│   └── cosmocc.py        # Reference: universal (all-platform) installer
├── execution/            # Tool execution (create new_tool.py here)
│   └── core.py           # Reference: Clang execution with platform handling
├── commands/
│   └── entry_points.py   # Add new_tool_main() function here
├── path_utils.py         # Add get_new_tool_install_dir() here
├── manifest.py           # Add fetch_new_tool_manifest() here
└── wrapper.py            # Re-export entry points here

pyproject.toml            # Add console script: clang-tool-chain-newtool = "..."
tests/test_newtool.py     # Add tests
docs/NEWTOOL.md           # Add documentation
```

**Platform-specific code locations:**
- **Windows ABI**: `src/clang_tool_chain/abi/windows_gnu.py`, `windows_msvc.py`
- **macOS SDK**: `src/clang_tool_chain/sdk/macos.py`
- **Platform detection**: `src/clang_tool_chain/platform/detection.py`
- **Binary paths by platform**: `~/.clang-tool-chain/{tool}/{platform}/{arch}/`

---

## 🛠️ Maintainer Tools

For package maintainers who need to create and update binary archives, see the comprehensive **[Maintainer Guide](docs/MAINTAINER.md)**.

The maintainer documentation covers:
- Archive creation pipeline (`fetch_and_archive.py`)
- Binary stripping and deduplication
- Compression optimization (zstd level 22)
- Manifest updates and checksum generation
- MinGW sysroot generation
- LLDB archive builds
- Troubleshooting binary dependencies

---

## 📚 Detailed Documentation

For in-depth information on specific topics, see the documentation in the `docs/` directory:

| Document | Description |
|----------|-------------|
| **[Clang/LLVM Toolchain](docs/CLANG_LLVM.md)** | Compiler wrappers, macOS SDK detection, Windows GNU/MSVC ABI, sccache integration |
| **[Inlined Build Directives](docs/DIRECTIVES.md)** | Self-contained source files with embedded build configuration |
| **[DLL Deployment](docs/DLL_DEPLOYMENT.md)** | Windows MinGW DLL automatic deployment (detailed guide) |
| **[Emscripten](docs/EMSCRIPTEN.md)** | WebAssembly compilation with Emscripten |
| **[LLDB Debugger](docs/LLDB.md)** | LLVM debugger for interactive debugging and crash analysis |
| **[Node.js Integration](docs/NODEJS.md)** | Bundled Node.js runtime for WebAssembly |
| **[Cosmopolitan Libc](docs/COSMOCC.md)** | Actually Portable Executables (APE) with cosmocc |
| **[Include What You Use](docs/IWYU.md)** | IWYU include analyzer for clean header dependencies |
| **[Parallel Downloads](docs/PARALLEL_DOWNLOADS.md)** | High-speed downloads with multi-threaded range requests |
| **[Architecture](docs/ARCHITECTURE.md)** | Technical architecture, manifest system, multi-part archives |
| **[Maintainer Guide](docs/MAINTAINER.md)** | Binary packaging, archive creation, troubleshooting |
| **[Testing Guide](docs/TESTING.md)** | Test infrastructure, running tests, CI/CD |
| **[Contributing](docs/CONTRIBUTING.md)** | How to add new tools (for humans and AI agents) |
| **[FAQ](docs/FAQ.md)** | Frequently asked questions |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Common issues and solutions |

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

## 📊 Changelog

For full version history and release notes, see **[CHANGELOG.md](CHANGELOG.md)**.

**Key highlights:**
- Windows GNU ABI with integrated MinGW headers (single archive download)
- Bundled Node.js runtime for Emscripten users
- Cross-platform support: Windows x64, macOS x64/ARM64, Linux x64/ARM64
- LLVM 21.1.5/21.1.6 with 35+ wrapper commands

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
