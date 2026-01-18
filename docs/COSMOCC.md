# Cosmopolitan Libc (Cosmocc)

Cosmopolitan Libc (cosmocc) makes C a build-once run-anywhere language. Executables produced by cosmocc are called "Actually Portable Executables" (APE) and run natively on Windows, Linux, macOS, FreeBSD, NetBSD, and OpenBSD without any runtime dependencies or modifications.

## Table of Contents

- [Quick Start](#quick-start)
- [Platform Support](#platform-support)
- [Available Commands](#available-commands)
- [How APE Works](#how-ape-works)
- [Usage Examples](#usage-examples)
- [Requirements](#requirements)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Additional Resources](#additional-resources)

---

## Quick Start

```bash
# Install the Cosmocc toolchain (downloads automatically on first use)
clang-tool-chain install cosmocc

# Compile a portable C executable
clang-tool-chain-cosmocc hello.c -o hello.com

# Compile a portable C++ executable
clang-tool-chain-cosmocpp hello.cpp -o hello.com

# The .com file runs on any supported OS!
./hello.com  # Works on Linux, macOS, FreeBSD, etc.
# On Windows: hello.com
```

---

## Platform Support

| Platform | Architecture | Cosmocc Version | Status |
|----------|-------------|-----------------|--------|
| Windows  | x86_64      | 4.0.2           | ✅ Available |
| Linux    | x86_64      | 4.0.2           | ✅ Available |
| Linux    | arm64       | 4.0.2           | ✅ Available |
| macOS    | x86_64      | 4.0.2           | ✅ Available |
| macOS    | arm64       | 4.0.2           | ✅ Available |

**Universal Installation:** Cosmocc is a universal toolchain - a single installation works across all platforms. The binaries themselves are Actually Portable Executables that run on all supported operating systems.

---

## Available Commands

| Command | Description | Equivalent |
|---------|-------------|------------|
| `clang-tool-chain-cosmocc` | Cosmopolitan C compiler | `cosmocc` |
| `clang-tool-chain-cosmocpp` | Cosmopolitan C++ compiler | `cosmoc++` |

---

## How APE Works

Actually Portable Executables (APE) are polyglot executables that work on multiple operating systems:

1. **Single Binary** - The same `.com` file runs on Windows, Linux, macOS, FreeBSD, NetBSD, and OpenBSD
2. **No Runtime Dependencies** - APE binaries include everything needed to run (no shared libraries required)
3. **Self-Extracting** - On first run, the binary extracts and caches platform-specific code
4. **Small Size** - Despite being universal, APE binaries are often smaller than platform-specific builds

### How It Works

- The `.com` extension is recognized by Windows as an executable
- On Unix systems, the kernel runs it as a shell script that bootstraps the actual code
- The binary contains multiple "views" - one for each supported platform
- No virtualization or emulation - executes natively on each OS

---

## Usage Examples

### Hello World (C)

```c
// hello.c
#include <stdio.h>

int main() {
    printf("Hello from Cosmopolitan!\n");
    return 0;
}
```

```bash
clang-tool-chain-cosmocc hello.c -o hello.com
./hello.com
```

### Hello World (C++)

```cpp
// hello.cpp
#include <iostream>

int main() {
    std::cout << "Hello from Cosmopolitan C++!" << std::endl;
    return 0;
}
```

```bash
clang-tool-chain-cosmocpp hello.cpp -o hello.com
./hello.com
```

### Static Web Server Example

```c
// A simple program that can serve files
#include <cosmo.h>
#include <stdio.h>

int main(int argc, char *argv[]) {
    printf("Running on: %s\n", GetHostOs());
    return 0;
}
```

### Compilation with Optimization

```bash
# Optimized build
clang-tool-chain-cosmocc -O2 myprogram.c -o myprogram.com

# Debug build
clang-tool-chain-cosmocc -g myprogram.c -o myprogram.com

# With warnings
clang-tool-chain-cosmocc -Wall -Wextra myprogram.c -o myprogram.com
```

### Cross-Platform Build Script

```bash
#!/bin/bash
# build.sh - Build a portable executable

set -e

echo "Building with Cosmopolitan..."
clang-tool-chain-cosmocc -O2 -Wall src/*.c -o myapp.com

echo "Build complete!"
echo "myapp.com runs on: Windows, Linux, macOS, FreeBSD, NetBSD, OpenBSD"

# Test run
./myapp.com
```

---

## Requirements

### All Platforms

- **Python 3.10+** - For running clang-tool-chain
- **Internet Connection** - For initial toolchain download (~50 MB)

### Windows-Specific

Cosmocc requires a POSIX shell on Windows to execute its scripts. Install one of:

1. **Git for Windows (Recommended)** - Includes Git Bash
   - Download: https://git-scm.com/download/win
   - Installs `bash.exe` and `sh.exe` to PATH

2. **MSYS2** - Full POSIX environment
   - Download: https://www.msys2.org/

3. **Windows Subsystem for Linux (WSL)** - Full Linux environment
   - Install via Windows Features or `wsl --install`

**Why is a shell needed?** Cosmocc tools (`cosmocc`, `cosmoc++`) are POSIX shell scripts that bootstrap the actual compiler. They require `bash` or `sh` to execute.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `COSMOCC` | Path to Cosmocc installation | Auto-detected |
| `PATH` | Cosmocc adds its bin and libexec directories | Modified at runtime |

**Note:** Unlike other clang-tool-chain components, Cosmocc doesn't require platform-specific environment configuration because APE binaries work everywhere.

---

## Troubleshooting

### "No POSIX shell found" (Windows)

**Error:** Cosmocc requires a POSIX shell on Windows.

**Solution:** Install Git for Windows (recommended) or MSYS2:
```bash
# Git for Windows includes Git Bash
# Download from: https://git-scm.com/download/win
```

### "exec format error" (Linux/macOS)

**Error:** Cannot execute cosmocc tool.

**Solution:** This is usually fixed automatically by clang-tool-chain. If it persists:
```bash
# Force reinstall
clang-tool-chain purge --yes
clang-tool-chain install cosmocc
```

### cosmoc++ produces wrong output

**Symptom:** C++ compiler behaves like C compiler.

**Cause:** Symlink placeholder issue on Windows.

**Solution:** This is fixed automatically during installation. If you encounter it:
```bash
# Force reinstall
clang-tool-chain purge --yes
clang-tool-chain install cosmocc
```

### Program crashes on specific OS

**Symptom:** APE executable works on some OS but crashes on others.

**Solution:**
1. Check that your code doesn't use OS-specific APIs
2. Use Cosmopolitan's cross-platform APIs where available
3. Test on all target platforms during development

---

## Additional Resources

### Official Cosmopolitan Resources

- **GitHub Repository:** https://github.com/jart/cosmopolitan
- **Main Website:** https://justine.lol/cosmopolitan/
- **APE Loader:** https://justine.lol/ape.html

### Cosmopolitan API Documentation

- **C Standard Library:** Cosmopolitan provides a complete libc
- **Cross-Platform APIs:** `<cosmo.h>` for OS detection, portable threading, etc.
- **Networking:** Portable sockets implementation
- **File System:** Unix-style APIs that work on Windows

### What Cosmopolitan Provides

- Complete C11/C17 standard library
- POSIX compatibility layer
- Portable threading (pthreads)
- Networking (BSD sockets)
- Compression (zlib, bz2)
- Cryptography (mbedTLS)
- Regular expressions
- JSON parsing

---

## Comparison with Regular Compilation

| Feature | Regular Clang | Cosmopolitan |
|---------|---------------|--------------|
| Output Format | Platform-specific (ELF, PE, Mach-O) | Universal APE |
| Portability | One OS | 6+ Operating Systems |
| Dependencies | Shared libraries | None (static) |
| Binary Size | Smaller per-platform | Larger but universal |
| Build-Once-Run-Anywhere | ❌ | ✅ |
| Development Workflow | Compile per OS | Compile once, test everywhere |

### When to Use Cosmopolitan

**Good fit:**
- CLI tools and utilities
- Development tools
- Portable scripts and automation
- Cross-platform testing
- Embedded scripting engines

**Consider alternatives:**
- GUI applications (use Qt, Electron, etc.)
- System services requiring OS-specific features
- Performance-critical applications (APE adds ~5% overhead)
- Large applications where binary size matters

---

## See Also

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Main Clang compiler documentation
- [Contributing](CONTRIBUTING.md) - How to add new tools to clang-tool-chain
- [Architecture](ARCHITECTURE.md) - Technical architecture overview
