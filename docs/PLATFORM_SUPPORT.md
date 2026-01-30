# Platform Support Matrix

Comprehensive platform support for Windows, macOS, and Linux.

## Supported Platforms

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

## Requirements

### General Requirements

- **Python**: 3.10 or higher
- **Disk Space**: ~100 MB for archive + ~200-350 MB installed
- **Internet**: Required for initial download (works offline after installation)

### Windows Requirements

- **OS**: Windows 10+ (x86_64)
- **MSVC ABI** (optional): Visual Studio 2019+ Build Tools
- **Git Bash** (optional): Recommended for shebang support

**Note:** GNU ABI (default) includes MinGW-w64 sysroot and does not require Visual Studio.

### macOS Requirements

- **OS**: macOS 11+ (Big Sur or later)
- **Architecture**: x86_64 (Intel) or ARM64 (Apple Silicon)
- **Required**: Xcode Command Line Tools

**Install Xcode Command Line Tools:**
```bash
xcode-select --install
```

**SDK Detection:**
- Automatic via `xcrun --show-sdk-path`
- No manual configuration needed
- Supports custom SDKs via `SDKROOT` environment variable

### Linux Requirements

- **OS**: glibc 2.27+ (Ubuntu 18.04+, Debian 10+, RHEL 8+, Alpine with glibc)
- **Architecture**: x86_64 or ARM64 (aarch64)
- **No system dependencies** needed (static linking)

**Tested distributions:**
- Ubuntu 18.04+ (Bionic, Focal, Jammy, Noble)
- Debian 10+ (Buster, Bullseye, Bookworm)
- RHEL/CentOS 8+
- Fedora 32+
- Arch Linux
- Raspberry Pi OS (ARM64)

## LLVM Version by Platform

| Platform | LLVM Version | Source | Notes |
|----------|--------------|--------|-------|
| Windows x64 | 21.1.5 | Custom build | Includes MinGW-w64 for GNU ABI |
| Linux x86_64 | 21.1.5 | Official LLVM | Portable binary |
| Linux ARM64 | 21.1.5 | Official LLVM | Portable binary |
| macOS x86_64 | 21.1.6 | Homebrew | Native Intel |
| macOS ARM64 | 21.1.6 | Homebrew | Native Apple Silicon |

## Tool-Specific Platform Support

### Emscripten (WebAssembly)

| Platform | Architecture | Emscripten Version | Status |
|----------|-------------|-------------------|--------|
| Windows  | x86_64      | 4.0.19            | ✅ Available |
| Linux    | x86_64      | 4.0.21            | ✅ Available |
| Linux    | ARM64       | 4.0.21            | ✅ Available |
| macOS    | x86_64      | 4.0.19            | ✅ Available |
| macOS    | ARM64       | 4.0.19            | ✅ Available |

*Emscripten uses its own bundled LLVM (LLVM 22), separate from the main toolchain.*

### LLDB Debugger

| Platform | Architecture | LLDB Version | Python Support | Status |
|----------|-------------|--------------|----------------|--------|
| Windows  | x86_64      | 21.1.5       | ✅ Ready (workflow available) | ⏳ Build Pending |
| Linux    | x86_64      | 21.1.5       | ✅ Full (Python 3.10 ready) | ⏳ Wrapper Ready, Archives Pending |
| Linux    | ARM64       | 21.1.5       | ✅ Full (Python 3.10 ready) | ⏳ Wrapper Ready, Archives Pending |
| macOS    | x86_64      | 21.1.6       | ⏳ Planned | ⏳ Pending |
| macOS    | ARM64       | 21.1.6       | ⏳ Planned | ⏳ Pending |

### Cosmopolitan Libc (Actually Portable Executables)

| Platform | Architecture | Cosmocc Version | Status |
|----------|-------------|-----------------|--------|
| Windows  | x86_64      | 4.0.2           | ✅ Available |
| Linux    | x86_64      | 4.0.2           | ✅ Available |
| Linux    | ARM64       | 4.0.2           | ✅ Available |
| macOS    | x86_64      | 4.0.2           | ✅ Available |
| macOS    | ARM64       | 4.0.2           | ✅ Available |

## Linker Support

| Platform | Default Linker | Alternative | Configuration |
|----------|---------------|-------------|---------------|
| Windows  | lld (LLVM)    | System ld   | `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` |
| Linux    | lld (LLVM)    | System ld   | `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` |
| macOS    | ld64.lld (LLVM) | System ld | `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` |

**Linker Notes:**
- **macOS**: Uses `-fuse-ld=ld64.lld` on LLVM 21.x+ (explicit Mach-O linker)
  - Older LLVM versions automatically fall back to `-fuse-ld=lld` with compatibility notice
  - GNU-style flags like `--no-undefined` auto-translate to ld64 equivalents (`-undefined error`)
- **Linux/Windows**: Uses LLVM lld for faster linking and cross-platform consistency
- **Opt-out**: Set `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` to use system linker

## CI/CD Platform Support

Tested and supported on:

- **GitHub Actions** - ubuntu-latest, windows-latest, macos-latest
- **GitLab CI** - Linux runners (Docker)
- **Azure Pipelines** - Linux, Windows, macOS agents
- **CircleCI** - Linux, macOS executors
- **Travis CI** - Linux, macOS
- **Jenkins** - All platforms
- **Docker** - Linux x86_64/ARM64 containers

## Known Limitations

### Windows

- **Shebang support**: Only works in Git Bash / MSYS2 (not cmd.exe or PowerShell)
- **MSVC ABI**: Requires Visual Studio Build Tools (not included in package)
- **Cross-compilation**: Limited without additional sysroots

### macOS

- **Xcode required**: Command Line Tools mandatory for system headers
- **LLVM 21.1.6**: Both x86_64 and ARM64 use LLVM 21.1.6
- **Rosetta 2**: ARM64 binaries on x86_64 Macs require Rosetta

### Linux

- **glibc requirement**: Not compatible with musl libc (Alpine without glibc)
- **Old distributions**: glibc 2.27+ required (Ubuntu 18.04+, Debian 10+)

## Performance by Platform

### Compilation Speed

clang-tool-chain uses unmodified LLVM binaries - expect **identical performance** to official LLVM releases.

### Download Speed (First Use)

Archives (71-91 MB) download time depends on connection:

| Connection Type | Download Time |
|----------------|---------------|
| Fiber (100 Mbps) | ~5 seconds |
| Cable (20 Mbps) | ~25 seconds |
| DSL (5 Mbps) | ~2 minutes |

Subsequent compilations are instant (no download).

## Platform Detection

clang-tool-chain automatically detects:

- Operating system (Windows, Linux, Darwin)
- Architecture (x86_64, ARM64)
- macOS SDK path (via `xcrun --show-sdk-path`)
- Windows target ABI (GNU vs MSVC)

No manual configuration needed for standard setups.

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Platform-specific installation
- [Configuration](CONFIGURATION.md) - Environment variables
- [Windows Target Selection](WINDOWS_TARGET_SELECTION.md) - GNU vs MSVC ABI
- [Troubleshooting](TROUBLESHOOTING.md) - Platform-specific issues
