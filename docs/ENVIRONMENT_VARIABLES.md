# Environment Variables

**Comprehensive Guide to clang-tool-chain Environment Variables**

This document lists all environment variables recognized by clang-tool-chain for configuration and customization.

## Table of Contents

- [Master Control](#master-control)
- [Library Deployment](#library-deployment)
- [Linker Configuration](#linker-configuration)
- [Sanitizer Configuration](#sanitizer-configuration)
- [Build Tools](#build-tools)
- [Toolchain Installation](#toolchain-installation)
- [Download Configuration](#download-configuration)
- [Debugging and Diagnostics](#debugging-and-diagnostics)

---

## Master Control

### Disable All Automatic Features

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_AUTO` | All | Boolean | `0` | Disable all automatic features at once |

**Usage:**

```bash
# Disable all automatic features (passthrough mode)
export CLANG_TOOL_CHAIN_NO_AUTO=1
clang-tool-chain-cpp main.cpp -o program
# No directives, no rpath injection, no library deployment, no sanitizer injection
```

**What Gets Disabled:**

When `CLANG_TOOL_CHAIN_NO_AUTO=1` is set, the following features are disabled:

| Feature | Individual Variable | Description |
|---------|---------------------|-------------|
| Inlined Build Directives | `NO_DIRECTIVES` | `@link`, `@std`, `@cflags` parsing |
| Shared ASAN Runtime | `NO_SHARED_ASAN` | Auto `-shared-libasan` on Linux |
| Sanitizer Environment | `NO_SANITIZER_ENV` | Auto `ASAN_OPTIONS`/`LSAN_OPTIONS`/`ASAN_SYMBOLIZER_PATH` |
| Rpath Injection | `NO_RPATH` | Auto `-rpath` for library loading |
| macOS Sysroot | `NO_SYSROOT` | Auto `-isysroot` SDK detection |
| Library Deployment | `NO_DEPLOY_LIBS` | Auto copy of runtime libraries (all outputs) |
| Shared Lib Deployment | `NO_DEPLOY_SHARED_LIB` | Library deployment for .dll/.so/.dylib outputs only |

**Use Cases:**

1. **CI/CD pipelines** that need deterministic builds without automatic modifications
2. **Debugging** clang-tool-chain behavior by isolating features
3. **Compatibility** with build systems that manage their own flags
4. **Testing** to verify builds work without clang-tool-chain magic

**Note:** Individual `NO_*` variables can still be used to disable specific features when `NO_AUTO` is not set.

---

## Library Deployment

Environment variables for controlling automatic library dependency deployment (Windows DLL, Linux .so, macOS .dylib).

### Deployment Control Variables

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` | All | Boolean | `0` | Disable library deployment for all output types |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB` | All | Boolean | `0` | Disable library deployment for shared library outputs only (.dll, .so, .dylib) |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` | All | Boolean | `0` | Enable verbose DEBUG logging for library deployment |

**Usage:**

```bash
# Disable all library deployment on all platforms
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
# No libraries deployed (Windows DLLs, Linux .so, macOS .dylib)

# Disable deployment for shared library outputs only (executables still get deployment)
export CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1
clang-tool-chain-cpp -shared mylib.cpp -o mylib.dll  # No deployment
clang-tool-chain-cpp main.cpp -o main.exe            # DLLs still deployed for .exe

# Enable verbose deployment logging
export CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
# DEBUG: Detecting dependencies for program
# DEBUG: Found library: libunwind.so.8
# DEBUG: Copying libunwind.so.8 to /path/to/output
# INFO: Deployed 1 shared library for program
```

**Difference Between NO_DEPLOY_LIBS and NO_DEPLOY_SHARED_LIB:**

| Variable | Executables (.exe, ELF, Mach-O) | Shared Libraries (.dll, .so, .dylib) |
|----------|--------------------------------|--------------------------------------|
| `NO_DEPLOY_LIBS=1` | No deployment | No deployment |
| `NO_DEPLOY_SHARED_LIB=1` | **Deployment enabled** | No deployment |

Use `NO_DEPLOY_SHARED_LIB` when you want runtime libraries deployed alongside executables, but not alongside shared library outputs (e.g., when building plugins or libraries that will be loaded by other executables).

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

## Sanitizer Configuration

Environment variables for controlling Address Sanitizer (ASAN), Leak Sanitizer (LSAN), and UndefinedBehaviorSanitizer (UBSAN) behavior.

### Compiler-Time Configuration

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_SHARED_ASAN` | Linux | Boolean | `0` | Disable automatic `-shared-libasan` injection |

**Usage:**

```bash
# Default behavior - shared ASAN runtime automatically used
clang-tool-chain-cpp -fsanitize=address main.cpp -o program
# clang-tool-chain: note: automatically injected sanitizer flags: -shared-libasan

# Disable shared ASAN (use static ASAN runtime)
export CLANG_TOOL_CHAIN_NO_SHARED_ASAN=1
clang-tool-chain-cpp -fsanitize=address main.cpp -o program
# Uses static ASAN runtime (may cause issues with shared libraries)
```

**Why Shared ASAN is Default:**
- Prevents "undefined symbol: __asan_*" errors during linking
- Required for proper ASAN support with dynamically loaded libraries (dlopen)
- Enables consistent sanitizer behavior across shared library boundaries

### Runtime Environment Configuration

| Variable | Platforms | Type | Default | Description |
|----------|-----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_SANITIZER_ENV` | All | Boolean | `0` | Disable automatic `ASAN_OPTIONS`/`LSAN_OPTIONS`/`ASAN_SYMBOLIZER_PATH` injection |

**Usage:**

```bash
# Default behavior - optimal sanitizer options automatically injected
clang-tool-chain-build-run -fsanitize=address main.cpp
# Automatically sets ASAN_OPTIONS, LSAN_OPTIONS, and ASAN_SYMBOLIZER_PATH

# Disable automatic injection (use your own settings)
export CLANG_TOOL_CHAIN_NO_SANITIZER_ENV=1
clang-tool-chain-build-run -fsanitize=address main.cpp
# Uses whatever ASAN_OPTIONS/LSAN_OPTIONS you have set (or defaults)
```

**What Gets Injected (When Sanitizers Are Detected):**
- `ASAN_OPTIONS=fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1`
- `LSAN_OPTIONS=fast_unwind_on_malloc=0:symbolize=1`
- `ASAN_SYMBOLIZER_PATH=/path/to/llvm-symbolizer` (auto-detected)

**Why These Options:**
- `fast_unwind_on_malloc=0`: Fixes `<unknown module>` in stack traces from dlopen'd libraries
- `symbolize=1`: Enables readable function names instead of raw addresses
- `detect_leaks=1`: Enables leak detection (ASAN only)
- `ASAN_SYMBOLIZER_PATH`: Points to the bundled `llvm-symbolizer` for address-to-symbol resolution

**User Options Preserved:**
If you set `ASAN_OPTIONS`, `LSAN_OPTIONS`, or `ASAN_SYMBOLIZER_PATH` yourself, your values are preserved (no automatic injection for that variable).

### Programmatic API

For build systems integrating with clang-tool-chain:

```python
from clang_tool_chain import prepare_sanitizer_environment, get_symbolizer_path

# Get complete environment with sanitizer settings
env = prepare_sanitizer_environment(
    base_env=os.environ.copy(),
    compiler_flags=["-fsanitize=address", "-O2"]
)
# env contains ASAN_OPTIONS, LSAN_OPTIONS, and ASAN_SYMBOLIZER_PATH

# Get just the symbolizer path
symbolizer = get_symbolizer_path()
if symbolizer:
    os.environ["ASAN_SYMBOLIZER_PATH"] = symbolizer
```

**See Also:** [ASAN Documentation in CLAUDE.md](../CLAUDE.md#address-sanitizer-asan-support)

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
- `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1` - Inlined directive parsing debug logs

---

## Variable Summary Table

### All Environment Variables

| Variable | Platform | Category | Type | Default | Description |
|----------|----------|----------|------|---------|-------------|
| `CLANG_TOOL_CHAIN_NO_AUTO` | All | **Master** | Boolean | `0` | **Disable all automatic features** |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` | All | Deployment | Boolean | `0` | Disable library deployment (all outputs) |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB` | All | Deployment | Boolean | `0` | Disable deployment for shared library outputs only |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` | All | Deployment | Boolean | `0` | Verbose library deployment logs |
| `CLANG_TOOL_CHAIN_USE_SYSTEM_LD` | All | Linker | Boolean | `0` | Use system linker instead of lld |
| `CLANG_TOOL_CHAIN_NO_RPATH` | Linux | Linker | Boolean | `0` | Disable automatic rpath injection |
| `CLANG_TOOL_CHAIN_NO_SYSROOT` | macOS | SDK | Boolean | `0` | Disable automatic -isysroot injection |
| `CLANG_TOOL_CHAIN_NO_SHARED_ASAN` | Linux | Sanitizer | Boolean | `0` | Disable automatic `-shared-libasan` injection |
| `CLANG_TOOL_CHAIN_NO_SANITIZER_ENV` | All | Sanitizer | Boolean | `0` | Disable automatic ASAN/LSAN options injection |
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
REM Disable all library deployment
set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1

REM Disable deployment for shared library outputs only (.dll)
set CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1

REM Enable verbose logging
set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1

REM Use custom installation directory
set CLANG_TOOL_CHAIN_HOME=C:\tools\clang-tool-chain

REM Build with custom configuration
clang-tool-chain-cpp main.cpp -o program.exe
```

### Linux/macOS Environment Variable Configuration

```bash
# Disable all library deployment
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

**Document Version**: 1.1.0
**Last Updated**: 2026-01-30
**Status**: Complete (Phase 5 Documentation)
