# Frequently Asked Questions (FAQ)

This document answers common questions about clang-tool-chain.

## Table of Contents

- [General Usage](#general-usage)
- [Installation & Updates](#installation--updates)
- [Platform-Specific](#platform-specific)
- [Version Management](#version-management)
- [Security](#security)
- [Integration](#integration)

---

## General Usage

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

### Is it safe to delete `~/.clang-tool-chain/`?

Yes! Deleting this directory just removes the cached binaries. They will re-download automatically on next use. You can also use:

```bash
clang-tool-chain purge          # Interactive confirmation
clang-tool-chain purge --yes    # Skip confirmation (for scripts)
```

### How much disk space do I need?

- **Download:** ~71-91 MB (archive)
- **Installed:** ~200-350 MB (extracted binaries)
- **Total:** ~271-441 MB per platform

The archive is deleted after extraction, so you only need space for the installed binaries.

### What about Windows paths with spaces?

All paths are handled correctly, including those with spaces. The wrappers quote paths appropriately.

---

## Installation & Updates

### How do I update to a new LLVM version?

Currently, the LLVM version is tied to the package version. To update:

```bash
pip install --upgrade clang-tool-chain
```

Future versions will support multiple LLVM versions via manifest updates.

### Can I use multiple LLVM versions simultaneously?

Not currently. Each `clang-tool-chain` package version maps to specific LLVM versions (see [Platform Support Matrix](../README.md#platform-support-matrix)). Use virtual environments to isolate different package versions:

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

### How do I pre-install the toolchain for CI/CD?

```bash
# Pre-download just the core Clang/LLVM toolchain
clang-tool-chain install clang

# Or trigger download with any command
clang-tool-chain-c --version
```

---

## Platform-Specific

### Which LLVM version does macOS use?

macOS uses LLVM 21.1.6 for both ARM64 and x86_64 architectures.

### Do I need to install Xcode on macOS?

No! You only need the **Xcode Command Line Tools**, which is much smaller:

```bash
xcode-select --install
```

This provides the SDK headers needed for compilation without installing the full Xcode IDE.

### Why does Windows use GNU ABI by default?

The default Windows target is `x86_64-w64-mingw32` (GNU ABI) for:
1. **Cross-platform consistency** - Same ABI on Linux/macOS/Windows
2. **C++11 strict mode support** - MSVC headers require C++14 features even in C++11 mode
3. **Embedded/Arduino compatibility** - Matches GCC toolchain behavior
4. **Modern C++ standard library** - Uses LLVM's libc++ (same as macOS/Linux)

This matches the approach of [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case).

For MSVC ABI, use the `-msvc` command variants:
```bash
clang-tool-chain-c-msvc main.c -o program.exe
clang-tool-chain-cpp-msvc main.cpp -o program.exe
```

---

## Version Management

### Which LLVM version is included?

| Platform | Architecture | LLVM Version |
|----------|-------------|--------------|
| Windows  | x86_64      | 21.1.5       |
| Linux    | x86_64      | 21.1.5       |
| Linux    | ARM64       | 21.1.5       |
| macOS    | x86_64      | 21.1.6       |
| macOS    | ARM64       | 21.1.6       |

### Can I pin a specific toolchain version?

Pin specific versions in `requirements.txt`:

```txt
# requirements.txt
clang-tool-chain==1.0.14  # Pins package version (currently uses LLVM 21.1.5)
```

---

## Security

### How does checksum verification work?

Every archive download is verified against SHA256 checksums stored in the platform manifests. If the checksum doesn't match, the download is rejected and an error is raised. This protects against:
- Corrupted downloads
- Man-in-the-middle attacks
- File tampering

### Where are binaries downloaded from?

Binaries are served from GitHub raw content (`raw.githubusercontent.com`):
- **Checksum Verified:** SHA256 validation on every download
- **Version Locked:** Manifests are version-controlled in the repository
- **Trust Model:** You're trusting this package maintainer + GitHub infrastructure
- **HTTPS Only:** All downloads use encrypted connections

---

## Integration

### Can I use this with CMake?

Yes! See [CMake Integration](../README.md#cmake-integration) for full examples.

**Quick example:**
```bash
export CC=clang-tool-chain-c
export CXX=clang-tool-chain-cpp
cmake -B build
cmake --build build
```

### Does this work in Docker containers?

Absolutely! See the [CI/CD Integration](../README.md#cicd-integration) section for Docker examples. The automatic download works seamlessly in containers.

### Can I contribute new platforms or architectures?

Yes! See the [Maintainer Guide](MAINTAINER.md) for how to create optimized archives. Pull requests welcome!

---

## See Also

- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
- [Architecture Overview](ARCHITECTURE.md) - How clang-tool-chain works internally
- [Main Documentation](../README.md) - Full documentation
