# Environment Variables

**Comprehensive Guide to clang-tool-chain Environment Variables**

This document lists all environment variables recognized by clang-tool-chain for configuration and customization.

## Table of Contents

- [Library Deployment](#library-deployment)
- [Linker Configuration](#linker-configuration)
- [Build Tools](#build-tools)
- [Toolchain Installation](#toolchain-installation)
- [Download Configuration](#download-configuration)
- [Debugging and Diagnostics](#debugging-and-diagnostics)

---

## Library Deployment

Environment variables for controlling automatic library dependency deployment (Windows DLL, Linux .so, macOS .dylib).

### Cross-Platform Variables (Recommended)

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` | All | Boolean | `0` | Disable automatic library deployment for all output types |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` | All | Boolean | `0` | Enable verbose DEBUG logging for library deployment |

**Usage:**

```bash
# Disable library deployment on all platforms
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
# No libraries deployed (Windows DLLs, Linux .so, macOS .dylib)

# Enable verbose deployment logging
export CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
# DEBUG: Detecting dependencies for program
# DEBUG: Found library: libunwind.so.8
# DEBUG: Copying libunwind.so.8 to /path/to/output
# INFO: Deployed 1 shared library for program
```

### Windows-Specific Variables (Legacy, Backward Compatible)

| Variable | Platform | Type | Default | Description |
|----------|----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS` | Windows | Boolean | `0` | Disable automatic DLL deployment for all outputs |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS` | Windows | Boolean | `0` | Disable DLL deployment for `.dll` outputs only (`.exe` still deployed) |
| `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE` | Windows | Boolean | `0` | Enable verbose DEBUG logging for DLL deployment |

**Backward Compatibility Note:**

All legacy Windows variables (`*_DLLS`, `*_DLL_*`) are checked alongside modern cross-platform variables (`*_LIBS`, `*_LIB_*`). Setting either variable applies the behavior:

```bash
# Windows: Either variable disables deployment
export CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1   # Legacy
# OR
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1   # Modern

# Both are equivalent on Windows
```

**Usage:**

```bash
# Disable DLL deployment for all outputs (Windows)
set CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1
clang-tool-chain-cpp main.cpp -o program.exe
# No DLLs deployed

# Disable DLL deployment for .dll outputs only (Windows)
set CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS=1
clang-tool-chain-cpp -shared mylib.cpp -o mylib.dll
# No DLLs deployed for mylib.dll
clang-tool-chain-cpp main.cpp -o main.exe
# DLLs still deployed for main.exe

# Enable verbose DLL logging (Windows)
set CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program.exe
# DEBUG: Detecting dependencies for program.exe
# DEBUG: Found DLL: libwinpthread-1.dll
# DEBUG: Copying libwinpthread-1.dll to output directory
# INFO: Deployed 3 MinGW DLL(s) for program.exe
```

### Boolean Value Interpretation

Environment variables are interpreted as booleans:
- **Enabled**: `1`, `true`, `True`, `TRUE`, `yes`, `Yes`, `YES`
- **Disabled**: `0`, `false`, `False`, `FALSE`, `no`, `No`, `NO`, empty string, not set

**Example:**

```bash
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1      # Disabled
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=true   # Disabled
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=yes    # Disabled
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=0      # Enabled (not disabled)
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=       # Enabled (empty = not disabled)
```

---

## Linker Configuration

### System Linker Override

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_USE_SYSTEM_LD` | All | Boolean | `0` | Use system linker instead of bundled LLVM lld |

**Usage:**

```bash
# Use system linker (ld, ld64) instead of LLVM lld
export CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1
clang-tool-chain-cpp main.cpp -o program
# Uses system linker (ld on Linux, ld64 on macOS)
```

**Why Use System Linker:**
- Compatibility with older build systems
- Distribution-specific linker features
- Debugging linker-specific issues

**Default Behavior (System Linker NOT Used):**
- **macOS**: Uses `-fuse-ld=ld64.lld` (LLVM 21.x+) or `-fuse-ld=lld` (older versions)
- **Linux**: Uses `-fuse-ld=lld` (LLVM lld)
- **Windows**: Uses lld-link (integrated MinGW support)

---

## Build Tools

### Inlined Build Directives

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_DIRECTIVES` | All | Boolean | `0` | Disable parsing of inlined build directives (`@link`, `@std`, etc.) |
| `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE` | All | Boolean | `0` | Show parsed directives (debug output) |

**Usage:**

```bash
# Disable inlined build directives
export CLANG_TOOL_CHAIN_NO_DIRECTIVES=1
clang-tool-chain-cpp main.cpp -o program
# @link, @std, @cflags directives in source files are ignored

# Show parsed directives (debug)
export CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program
# Parsed directive: @std: c++17
# Parsed directive: @link: pthread
```

**See Also:** [Inlined Build Directives Documentation](DIRECTIVES.md)

---

## Toolchain Installation

### Installation Paths

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_HOME` | All | Path | `~/.clang-tool-chain` | Base directory for toolchain installation |

**Usage:**

```bash
# Install toolchain to custom directory
export CLANG_TOOL_CHAIN_HOME=/opt/clang-tool-chain
clang-tool-chain install clang
# Toolchain installed to /opt/clang-tool-chain/clang-x86_64-linux/
```

**Default Locations:**
- **Linux/macOS**: `~/.clang-tool-chain/`
- **Windows**: `%USERPROFILE%\.clang-tool-chain\`

---

## Download Configuration

### Parallel Downloads

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_PARALLEL_CHUNKS` | All | Integer | `8` | Number of parallel chunks for multi-threaded downloads |
| `CLANG_TOOL_CHAIN_CHUNK_SIZE` | All | Integer | `8388608` | Chunk size for parallel downloads (bytes, default 8 MB) |

**Usage:**

```bash
# Use 16 parallel chunks for faster downloads
export CLANG_TOOL_CHAIN_PARALLEL_CHUNKS=16
clang-tool-chain install clang
# Downloads using 16 parallel HTTP range requests

# Use smaller chunk size (4 MB)
export CLANG_TOOL_CHAIN_CHUNK_SIZE=4194304
clang-tool-chain install clang
```

**Performance Notes:**
- Default (8 chunks, 8 MB each) provides ~3-5x speedup vs single-threaded
- Higher chunk count improves speed on high-bandwidth connections
- Lower chunk size reduces memory usage

**See Also:** [Parallel Downloads Documentation](PARALLEL_DOWNLOADS.md)

---

## Debugging and Diagnostics

### Logging Levels

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_LOG_LEVEL` | All | String | `INFO` | Global logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

**Usage:**

```bash
# Enable debug logging for all components
export CLANG_TOOL_CHAIN_LOG_LEVEL=DEBUG
clang-tool-chain-cpp main.cpp -o program
# DEBUG: Detecting platform: linux-x86_64
# DEBUG: Toolchain found at: ~/.clang-tool-chain/clang-x86_64-linux
# DEBUG: Executing: clang++ main.cpp -o program
```

### Component-Specific Debugging

Some components have dedicated verbose flags (see [Library Deployment](#library-deployment) section):

- `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` - Library deployment debug logs
- `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1` - Windows DLL deployment debug logs
- `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1` - Inlined directive parsing debug logs

---

## Variable Summary Table

### All Environment Variables

| Variable | Platform | Category | Type | Default | Description |
|----------|----------|----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` | All | Deployment | Boolean | `0` | Disable library deployment |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` | All | Deployment | Boolean | `0` | Verbose library deployment logs |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS` | Windows | Deployment | Boolean | `0` | Disable DLL deployment (legacy) |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS` | Windows | Deployment | Boolean | `0` | Disable DLL deployment for .dll only |
| `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE` | Windows | Deployment | Boolean | `0` | Verbose DLL deployment logs (legacy) |
| `CLANG_TOOL_CHAIN_USE_SYSTEM_LD` | All | Linker | Boolean | `0` | Use system linker instead of lld |
| `CLANG_TOOL_CHAIN_NO_DIRECTIVES` | All | Build | Boolean | `0` | Disable inlined directives |
| `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE` | All | Build | Boolean | `0` | Show parsed directives |
| `CLANG_TOOL_CHAIN_HOME` | All | Install | Path | `~/.clang-tool-chain` | Toolchain installation directory |
| `CLANG_TOOL_CHAIN_PARALLEL_CHUNKS` | All | Download | Integer | `8` | Parallel download chunks |
| `CLANG_TOOL_CHAIN_CHUNK_SIZE` | All | Download | Integer | `8388608` | Download chunk size (bytes) |
| `CLANG_TOOL_CHAIN_LOG_LEVEL` | All | Debug | String | `INFO` | Global logging level |

---

## Platform-Specific Guides

### Windows Environment Variable Configuration

```cmd
REM Disable DLL deployment
set CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1

REM Enable verbose logging
set CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1

REM Use custom installation directory
set CLANG_TOOL_CHAIN_HOME=C:\tools\clang-tool-chain

REM Build with custom configuration
clang-tool-chain-cpp main.cpp -o program.exe
```

### Linux/macOS Environment Variable Configuration

```bash
# Disable library deployment
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1

# Enable verbose logging
export CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1

# Use custom installation directory
export CLANG_TOOL_CHAIN_HOME=/opt/clang-tool-chain

# Build with custom configuration
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
```

### Persistent Configuration

**Linux/macOS (bash/zsh):**

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1' >> ~/.bashrc
source ~/.bashrc
```

**Windows (PowerShell):**

```powershell
# Add to PowerShell profile
[System.Environment]::SetEnvironmentVariable('CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS', '1', 'User')
```

**Windows (cmd.exe via setx):**

```cmd
REM Set persistent user variable
setx CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS 1
```

---

## See Also

- **[Library Deployment Guide](SHARED_LIBRARY_DEPLOYMENT.md)** - Comprehensive deployment documentation
- **[Inlined Build Directives](DIRECTIVES.md)** - Source file embedded configuration
- **[Parallel Downloads](PARALLEL_DOWNLOADS.md)** - High-speed download configuration
- **[Clang/LLVM Toolchain](CLANG_LLVM.md)** - Compiler wrapper documentation

---

**Document Version**: 1.0.0
**Last Updated**: 2026-01-25
**Status**: Complete (Phase 5 Documentation)
