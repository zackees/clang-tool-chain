# Cross-Platform Library Dependency Deployment

**Automatic Runtime Library Deployment for Windows, Linux, and macOS**

This document provides comprehensive documentation on clang-tool-chain's automatic library dependency deployment feature across all platforms.

## Table of Contents

- [Overview](#overview)
- [Platform-Specific Guides](#platform-specific-guides)
  - [Windows: MinGW DLL Deployment](#windows-mingw-dll-deployment)
  - [Linux: Shared Object (.so) Deployment](#linux-shared-object-so-deployment)
  - [macOS: Dynamic Library (.dylib) Deployment](#macos-dynamic-library-dylib-deployment)
- [Cross-Platform Features](#cross-platform-features)
- [Environment Variables](#environment-variables)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Implementation Architecture](#implementation-architecture)
- [FAQ](#faq)

---

## Overview

clang-tool-chain automatically detects and deploys required runtime libraries to the output directory on all platforms. This ensures your executables and shared libraries run immediately without PATH, LD_LIBRARY_PATH, or DYLD_LIBRARY_PATH modifications.

### Platform Summary

| Platform | Extension | Deployment Trigger | Detection Tool | Status |
|----------|-----------|-------------------|----------------|--------|
| **Windows** | `.dll` | Automatic for `.exe` and `.dll` | `llvm-objdump -p` | ✅ Default ON |
| **Linux** | `.so` | Opt-in via `--deploy-dependencies` | `ldd` | ✅ Available |
| **macOS** | `.dylib` | Opt-in via `--deploy-dependencies` | `otool -L` | ✅ Available |

### Why Is This Needed?

**Without Library Deployment:**
- Windows: "The code execution cannot proceed because libwinpthread-1.dll was not found"
- Linux: "error while loading shared libraries: libunwind.so.8: cannot open shared object file"
- macOS: "dyld: Library not loaded: @rpath/libunwind.dylib"

**With Library Deployment:**
- All required runtime libraries are automatically copied to the output directory
- Executables run immediately without environment variable configuration
- Distribution simplified - just zip the output directory

### Design Philosophy

1. **Windows**: Automatic deployment (default ON) - Windows users expect DLLs alongside .exe files
2. **Linux/macOS**: Opt-in deployment (via `--deploy-dependencies`) - Unix users may use system package managers
3. **Non-fatal**: Deployment errors never fail your build - warnings only
4. **Smart**: Timestamp checking avoids unnecessary copies
5. **Fast**: Typical overhead <300ms per build

---

## Platform-Specific Guides

### Windows: MinGW DLL Deployment

**Deployment Mode**: Automatic (always enabled for GNU ABI)

#### How It Works

When compiling Windows executables (`.exe`) or shared libraries (`.dll`) with the GNU ABI (default on Windows), clang-tool-chain automatically:
1. Uses `llvm-objdump -p` to parse PE headers
2. Extracts DLL dependencies recursively (including transitive dependencies)
3. Copies MinGW runtime DLLs from the sysroot to the executable directory
4. Uses hard links when possible (zero disk space, instant)

#### Example

```bash
# Compile a program
clang-tool-chain-cpp hello.cpp -o hello.exe

# Output: Deployed 3 MinGW DLL(s) for hello.exe

# Your directory now contains:
# hello.exe
# libwinpthread-1.dll
# libgcc_s_seh-1.dll
# libstdc++-6.dll

# Run immediately - no PATH setup needed!
.\hello.exe
```

#### Typical DLLs Deployed

- `libwinpthread-1.dll` - POSIX threads support
- `libgcc_s_seh-1.dll` - GCC runtime (exception handling)
- `libstdc++-6.dll` - C++ standard library
- `libc++.dll` - LLVM C++ standard library (when used)
- `libunwind.dll` - LLVM unwinding library (when used)
- `libclang_rt.asan_dynamic-x86_64.dll` - AddressSanitizer runtime (when `-fsanitize=address`)

#### When It's Skipped

- **Non-Windows platforms**: No-op on Linux/macOS
- **MSVC ABI**: `clang-tool-chain-cpp-msvc` uses MSVC runtime instead
- **Compile-only**: `-c` flag present (no linking)
- **Non-executable outputs**: `.o`, `.obj`, `.a`, `.lib` files
- **Environment variable**: `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` or `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1`

#### Environment Variables

- `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1` - Disable DLL deployment for all outputs
- `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS=1` - Disable for `.dll` outputs only (`.exe` still deployed)
- `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE=1` - Enable verbose DEBUG logging

#### Performance

- **DLL Detection**: <50ms per executable (llvm-objdump overhead)
- **DLL Copying**: <50ms total (2-3 DLLs typically, hard links used)
- **Total Overhead**: <100ms per executable build

#### See Also

- Implementation: `src/clang_tool_chain/deployment/dll_deployer.py`
- Tests: `tests/test_dll_deployment.py` (38 comprehensive tests)
- Legacy Guide: [docs/DLL_DEPLOYMENT.md](DLL_DEPLOYMENT.md) (detailed Windows-specific documentation)

---

### Linux: Shared Object (.so) Deployment

**Deployment Mode**: Opt-in via `--deploy-dependencies` flag

#### How It Works

When compiling Linux executables or shared libraries with the `--deploy-dependencies` flag, clang-tool-chain:
1. Uses `ldd` to detect required shared libraries
2. Filters for deployable libraries (excludes system libraries like libc.so)
3. Copies `.so` files to the executable directory
4. Preserves symlinks (e.g., `libunwind.so.8` → `libunwind.so.8.0.1`)

#### Example

```bash
# Build executable with library deployment
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies -lunwind

# Output: Deployed 1 shared library for program

# Your directory now contains:
# program
# libunwind.so.8 (symlink)
# libunwind.so.8.0.1 (actual file)

# Run immediately - no LD_LIBRARY_PATH setup needed!
./program
```

#### Build Shared Library with Dependencies

```bash
# Build shared library with automatic dependency deployment
clang-tool-chain-cpp -shared -fPIC mylib.cpp -o mylib.so --deploy-dependencies

# Output: Deployed 2 shared libraries for mylib.so

# Your directory contains all required .so files
# mylib.so
# libunwind.so.8 -> libunwind.so.8.0.1
# libunwind.so.8.0.1
# libc++.so.1 -> libc++.so.1.0
# libc++.so.1.0
```

#### Typical Libraries Deployed

- `libunwind.so.*` - LLVM unwinding library
- `libc++.so.*` - LLVM C++ standard library (when used)
- `libc++abi.so.*` - LLVM C++ ABI library (when used)
- `libstdc++.so.*` - GNU C++ standard library (when used)
- `libgomp.so.*` - OpenMP support (when `-fopenmp`)

#### System Libraries (NOT Deployed)

The following system libraries are detected but **not** deployed (assumed available on all Linux systems):
- `libc.so.*`, `libm.so.*`, `libdl.so.*`, `libpthread.so.*`, `librt.so.*`
- `ld-linux*.so.*`, `libgcc_s.so.*`, `libresolv.so.*`, `libutil.so.*`

#### Symlink Handling

Linux shared libraries use versioned symlinks. clang-tool-chain preserves this structure:
```
libunwind.so.8 -> libunwind.so.8.0.1  (symlink copied)
libunwind.so.8.0.1                     (actual file copied)
```

#### Environment Variables

- `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` - Disable library deployment
- `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` - Enable verbose DEBUG logging

#### Performance

- **Dependency Detection**: ~50-200ms (`ldd` overhead)
- **Library Copying**: ~50-100ms (2-3 libraries typically)
- **Total Overhead**: ~100-300ms per build

#### See Also

- Implementation: `src/clang_tool_chain/deployment/so_deployer.py`
- Tests: `tests/test_so_deployment.py` (43 comprehensive tests)
- Factory: `src/clang_tool_chain/deployment/factory.py`

---

### macOS: Dynamic Library (.dylib) Deployment

**Deployment Mode**: Opt-in via `--deploy-dependencies` flag

#### How It Works

When compiling macOS executables or dynamic libraries with the `--deploy-dependencies` flag, clang-tool-chain:
1. Uses `otool -L` to detect required dynamic libraries
2. Filters for deployable libraries (excludes system frameworks)
3. Copies `.dylib` files to the executable directory
4. Handles `@rpath`, `@loader_path`, and absolute paths

#### Example

```bash
# Build executable with library deployment
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies -lunwind

# Output: Deployed 1 dynamic library for program

# Your directory now contains:
# program
# libunwind.dylib

# Run immediately - no DYLD_LIBRARY_PATH setup needed!
./program
```

#### Build Dynamic Library with Dependencies

```bash
# Build dynamic library with automatic dependency deployment
clang-tool-chain-cpp -shared -fPIC mylib.cpp -o mylib.dylib --deploy-dependencies

# Output: Deployed 2 dynamic libraries for mylib.dylib

# Your directory contains all required .dylib files
# mylib.dylib
# libunwind.dylib
# libc++.dylib
```

#### Typical Libraries Deployed

- `libunwind.dylib` - LLVM unwinding library
- `libc++.dylib` - LLVM C++ standard library (when used)
- `libc++abi.dylib` - LLVM C++ ABI library (when used)
- `libomp.dylib` - OpenMP support (when `-fopenmp`)

#### System Libraries (NOT Deployed)

The following system libraries/frameworks are detected but **not** deployed (part of macOS):
- `/usr/lib/libSystem.B.dylib`, `/usr/lib/libc++.1.dylib` (system C++ library)
- All frameworks in `/System/Library/Frameworks/` (Foundation, AppKit, etc.)
- All libraries in `/usr/lib/` that are not from LLVM toolchain

#### @rpath Handling

macOS uses `@rpath` for relocatable library paths. clang-tool-chain:
- Detects libraries with `@rpath/libfoo.dylib` format
- Resolves to actual library paths using LLVM toolchain directories
- Copies resolved libraries to output directory

**Note**: `install_name_tool` patching is NOT required - libraries work with original install names when copied to the same directory as the executable.

#### Environment Variables

- `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` - Disable library deployment
- `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` - Enable verbose DEBUG logging

#### Performance

- **Dependency Detection**: ~50-200ms (`otool` overhead)
- **Library Copying**: ~50-100ms (2-3 libraries typically)
- **Total Overhead**: ~100-300ms per build

#### See Also

- Implementation: `src/clang_tool_chain/deployment/dylib_deployer.py`
- Tests: `tests/test_dylib_deployment.py` (51 comprehensive tests)
- Factory: `src/clang_tool_chain/deployment/factory.py`

---

## Cross-Platform Features

### Unified Deployment Interface

All platforms use a common interface via the factory pattern:

```python
from clang_tool_chain.deployment.factory import create_deployer

# Create platform-specific deployer
deployer = create_deployer(platform_name, arch)  # "windows", "linux", "darwin"

# Deploy all dependencies for an output file
deployed_count = deployer.deploy_all(output_path)
```

### Common Behavior Across Platforms

| Feature | Windows | Linux | macOS | Implementation |
|---------|---------|-------|-------|----------------|
| **Automatic detection** | ✅ | ✅ | ✅ | Platform-specific tools |
| **Smart copying** | ✅ | ✅ | ✅ | Timestamp checking |
| **Non-fatal errors** | ✅ | ✅ | ✅ | Warnings only |
| **Recursive scanning** | ✅ | ✅ | ✅ | Transitive dependencies |
| **System library filtering** | ✅ | ✅ | ✅ | Platform-specific exclusion lists |
| **Hard link optimization** | ✅ | ✅ | ✅ | Falls back to copy |
| **Verbose logging** | ✅ | ✅ | ✅ | DEBUG level logs |
| **Environment variable control** | ✅ | ✅ | ✅ | `NO_DEPLOY_LIBS`, `LIB_DEPLOY_VERBOSE` |

### Factory Pattern Architecture

```
BaseLibraryDeployer (Abstract Base Class)
├── detect_dependencies() - Abstract method
├── filter_deployable_libraries() - Abstract method
├── locate_library() - Abstract method
├── copy_library() - Common implementation (timestamp check, hard link, fallback)
└── deploy_all() - Common workflow orchestration

Windows: DllDeployer
├── detect_dependencies() → llvm-objdump -p (recursive)
├── filter_deployable_libraries() → MinGW patterns, exclude Windows system DLLs
└── locate_library() → Search MinGW sysroot

Linux: SoDeployer
├── detect_dependencies() → ldd
├── filter_deployable_libraries() → Exclude /lib, /usr/lib system libraries
└── locate_library() → Parse ldd output for paths

macOS: DylibDeployer
├── detect_dependencies() → otool -L
├── filter_deployable_libraries() → Exclude system frameworks, /usr/lib
└── locate_library() → Resolve @rpath, check toolchain directories
```

---

## Environment Variables

### Modern Cross-Platform Variables (Recommended)

| Variable | Platforms | Purpose | Default |
|----------|-----------|---------|---------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` | All | Disable library deployment | `0` (enabled) |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE` | All | Enable verbose DEBUG logging | `0` (INFO only) |

**Usage:**
```bash
# Disable deployment on all platforms
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
# No libraries deployed

# Enable verbose logging
export CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
# DEBUG: Detecting dependencies for program
# DEBUG: Found library: libunwind.so.8
# DEBUG: Copying libunwind.so.8 to /path/to/output
# INFO: Deployed 1 shared library for program
```

### Legacy Windows-Specific Variables (Backward Compatible)

| Variable | Platform | Purpose | Notes |
|----------|----------|---------|-------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS` | Windows | Disable DLL deployment | Checked alongside `NO_DEPLOY_LIBS` |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS` | Windows | Disable for `.dll` outputs only | `.exe` still deployed |
| `CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE` | Windows | Verbose DLL logging | Checked alongside `LIB_DEPLOY_VERBOSE` |

**Backward Compatibility**: All legacy Windows variables (`*_DLLS`, `*_DLL_*`) are honored alongside modern variables (`*_LIBS`, `*_LIB_*`). If either is set, the behavior applies.

---

## Performance

### Overhead by Platform

| Platform | Detection | Copying | Total | Notes |
|----------|-----------|---------|-------|-------|
| **Windows** | ~50ms | ~50ms | **~100ms** | llvm-objdump + hard links |
| **Linux** | ~50-200ms | ~50-100ms | **~100-300ms** | ldd + symlink copying |
| **macOS** | ~50-200ms | ~50-100ms | **~100-300ms** | otool + file copying |

### Optimization Strategies

1. **Timestamp Checking**: Skips copy if destination is newer than source (~5ms check)
2. **Hard Links**: Zero-copy when possible (Windows: ~1ms vs ~50ms for copy)
3. **Early Exit**: Detection skipped when deployment disabled via environment variable
4. **Cached Results**: Factory creates deployer once per platform/arch combination

### When Deployment Is Skipped (Zero Overhead)

- **Compile-only mode**: `-c` flag present (no linking, no deployment)
- **Non-executable outputs**: `.o`, `.obj`, `.a`, `.lib` files
- **MSVC ABI** (Windows): Uses MSVC runtime instead of MinGW
- **Environment variable disabled**: `NO_DEPLOY_LIBS=1` or `NO_DEPLOY_DLLS=1`
- **Linux/macOS without flag**: `--deploy-dependencies` not specified

---

## Troubleshooting

### Common Issues

#### "Library not found" During Deployment

**Symptoms:**
```
WARNING: Library 'libfoo.so.1' required by 'program' but not found in system
```

**Causes:**
- Library not installed on the build system
- Library in non-standard location
- Detection tool (ldd/otool) cannot find library

**Solutions:**
1. **Install the library**: `sudo apt-get install libfoo-dev` (Linux) or `brew install libfoo` (macOS)
2. **Use system library**: If it's a system library, this warning is safe to ignore (deployment is non-fatal)
3. **Check LD_LIBRARY_PATH/DYLD_LIBRARY_PATH**: Ensure library is in search path during build
4. **Disable deployment**: Set `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` if not needed

#### Windows: "llvm-objdump returned non-zero exit code"

**Symptoms:**
```
WARNING: Windows DLL deployment failed: llvm-objdump returned non-zero exit code
```

**Causes:**
- llvm-objdump cannot parse PE headers (invalid executable)
- Executable not linked yet (compile-only mode)

**Solutions:**
1. **Verify executable is valid**: Run the executable to ensure it's properly linked
2. **Check for `-c` flag**: This warning should not appear with compile-only mode
3. **Fallback activated**: Heuristic list (libwinpthread, libgcc_s, libstdc++) still deployed

#### Linux/macOS: "--deploy-dependencies flag required"

**Symptoms:**
- Libraries not deployed after build
- No deployment message in output

**Cause:**
- Linux/macOS deployment is opt-in via `--deploy-dependencies` flag

**Solution:**
```bash
# Add the flag to enable deployment
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
```

### Debugging Tips

#### Enable Verbose Logging

```bash
# See detailed deployment process
export CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies

# Output includes:
# DEBUG: Detecting dependencies for program
# DEBUG: Running: ldd /path/to/program
# DEBUG: Detected dependencies: ['libunwind.so.8', 'libc++.so.1']
# DEBUG: Filtering deployable libraries
# DEBUG: Deployable libraries: ['libunwind.so.8']
# DEBUG: Locating library: libunwind.so.8
# DEBUG: Found library at: /usr/lib/x86_64-linux-gnu/libunwind.so.8
# DEBUG: Copying libunwind.so.8 to /path/to/output
# INFO: Deployed 1 shared library for program
```

#### Check Deployment Status

**Windows:**
```cmd
REM List deployed DLLs in output directory
dir *.dll

REM Verify executable dependencies
clang-tool-chain-llvm-objdump -p program.exe | findstr "DLL Name"
```

**Linux:**
```bash
# List deployed .so files in output directory
ls -la *.so*

# Verify executable dependencies
ldd ./program
```

**macOS:**
```bash
# List deployed .dylib files in output directory
ls -la *.dylib

# Verify executable dependencies
otool -L ./program
```

---

## Implementation Architecture

### Component Overview

```
deployment/
├── base_deployer.py          - Abstract base class (BaseLibraryDeployer)
├── dll_deployer.py            - Windows DLL deployment (DllDeployer)
├── so_deployer.py             - Linux .so deployment (SoDeployer)
├── dylib_deployer.py          - macOS .dylib deployment (DylibDeployer)
└── factory.py                 - Factory pattern for platform selection

execution/
└── core.py                    - Integration point (post_link_dependency_deployment)

platform/
└── detection.py               - Platform and architecture detection
```

### Class Hierarchy

```python
class BaseLibraryDeployer(ABC):
    """Abstract base class for library deployers."""

    @abstractmethod
    def detect_dependencies(self, output_path: Path) -> list[str]:
        """Detect library dependencies using platform-specific tools."""
        pass

    @abstractmethod
    def filter_deployable_libraries(self, dependencies: list[str]) -> list[str]:
        """Filter libraries that should be deployed (exclude system libraries)."""
        pass

    @abstractmethod
    def locate_library(self, lib_name: str) -> Path | None:
        """Locate library file in system directories."""
        pass

    def copy_library(self, src: Path, dst: Path) -> bool:
        """Copy library with timestamp checking and hard link optimization."""
        # Common implementation for all platforms
        pass

    def deploy_all(self, output_path: Path) -> int:
        """Deploy all dependencies for an output file."""
        # Common workflow orchestration
        dependencies = self.detect_dependencies(output_path)
        deployable = self.filter_deployable_libraries(dependencies)
        for lib in deployable:
            src = self.locate_library(lib)
            if src:
                self.copy_library(src, output_path.parent / lib)
        return len(deployable)
```

### Integration Flow

```
User builds with: clang-tool-chain-cpp main.cpp -o program --deploy-dependencies
                          ↓
    execution/core.py extracts --deploy-dependencies flag
                          ↓
    Clang++ compiles and links (flag stripped from args)
                          ↓
    If returncode == 0 and --deploy-dependencies flag present:
                          ↓
    post_link_dependency_deployment(program, "linux", False)
                          ↓
    _deploy_linux_so_dependencies(program)
                          ↓
    Factory creates SoDeployer("x86_64")
                          ↓
    SoDeployer.deploy_all(program)
      ├── detect_dependencies("program") → ["libunwind.so.8", "libc++.so.1"]
      ├── filter_deployable_libraries() → ["libunwind.so.8"] (libc++ is system lib)
      ├── locate_library("libunwind.so.8") → /usr/lib/x86_64-linux-gnu/libunwind.so.8
      └── copy_library() → Copies to output directory
                          ↓
    Logs: "Deployed 1 shared library for program"
```

### Test Suite Organization

| Test File | Platform | Tests | Coverage | Purpose |
|-----------|----------|-------|----------|---------|
| `test_dll_deployment.py` | Windows | 38 | 90%+ | DLL deployment testing |
| `test_so_deployment.py` | Linux | 43 | 80%+ | .so deployment testing |
| `test_dylib_deployment.py` | macOS | 51 | 68%+ | .dylib deployment testing |
| `test_deployment_factory.py` | All | 43 | 100% | Factory pattern testing |
| `test_execution_core_deployment.py` | All | 5 | N/A | Integration testing |

---

## FAQ

### General Questions

**Q: Why is Windows deployment automatic but Linux/macOS opt-in?**

A: Platform conventions differ:
- **Windows**: Users expect DLLs alongside .exe files (no package manager for runtime libraries)
- **Linux/macOS**: Users often use system package managers (apt, brew) to install libraries globally

The `--deploy-dependencies` flag gives Unix users explicit control while maintaining zero-config Windows experience.

**Q: Does deployment work with static linking?**

A: No, deployment only applies to dynamically linked libraries:
- Use `-static` flag to link libraries statically (no deployment needed)
- Static linking includes library code in the executable itself

**Q: Can I deploy custom libraries (not system libraries)?**

A: Yes, with caveats:
- **Windows**: All MinGW-pattern DLLs detected by llvm-objdump are deployed
- **Linux/macOS**: Libraries in non-system directories are deployed (if detected by ldd/otool)
- **Custom libraries**: Must be in linker search path during build for detection to work

**Q: Does deployment work with sanitizers (ASan, UBSan, etc.)?**

A: Yes!
- **Windows**: Sanitizer runtimes (`libclang_rt.asan_dynamic-x86_64.dll`) are automatically deployed
- **Linux/macOS**: Sanitizer runtimes bundled with LLVM toolchain are deployed when detected

### Platform-Specific Questions

**Q: Windows - Why are some DLLs not deployed?**

A: Windows system DLLs (kernel32.dll, user32.dll, etc.) are excluded because:
- They're part of Windows OS (always available)
- Deploying them can cause version conflicts

Only MinGW runtime DLLs are deployed (libwinpthread, libgcc_s, libstdc++, etc.).

**Q: Linux - Why is libc.so.6 not deployed?**

A: System libraries like libc, libm, libpthread are:
- Part of the Linux standard base (available on all systems)
- Tightly coupled to kernel version (deploying can break the executable)

Only non-system libraries (libunwind, LLVM libc++, etc.) are deployed.

**Q: macOS - Do I need to run install_name_tool?**

A: No, clang-tool-chain handles library paths automatically:
- Libraries work with original install names when in the same directory as the executable
- macOS dyld searches the executable directory by default

**Q: How do I deploy to a different directory?**

A: Currently, libraries are deployed to the output file's directory:
- Use `-o /path/to/output_dir/program` to control deployment location
- Future enhancement: `CLANG_TOOL_CHAIN_DEPLOY_DIR` environment variable (not yet implemented)

### Performance Questions

**Q: Does deployment slow down my builds?**

A: Minimal impact:
- **Overhead**: 100-300ms per build (detection + copying)
- **Optimizations**: Timestamp checking, hard links (Windows), cached deployers
- **Skip conditions**: Compile-only mode, disabled via environment variable

For incremental builds, timestamp checking ensures libraries are only copied when updated.

**Q: Why use hard links on Windows?**

A: Hard links provide:
- **Zero disk space**: Multiple directory entries point to the same file data
- **Instant copying**: No file data transfer required (~1ms vs ~50ms for copy)
- **Automatic updates**: Updating source DLL automatically updates all hard-linked copies

Fallback to regular copy if hard links fail (cross-filesystem, permissions, etc.).

### Troubleshooting Questions

**Q: Deployment failed - will my build fail?**

A: No, deployment is **non-fatal**:
- Warnings are logged, but build succeeds
- If deployment is critical, check logs and manually copy required libraries
- Use `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` to debug issues

**Q: How do I disable deployment entirely?**

A: Use environment variables:
```bash
# Disable on all platforms
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1

# Windows-specific (legacy)
export CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1
```

**Q: Can I test if deployment works without building?**

A: Yes, use pytest:
```bash
# Test Windows deployment
pytest tests/test_dll_deployment.py -v

# Test Linux deployment
pytest tests/test_so_deployment.py -v

# Test macOS deployment
pytest tests/test_dylib_deployment.py -v

# Test all deployment
pytest tests/test_*deployment*.py -v
```

---

## See Also

- **[Windows DLL Deployment (Legacy Guide)](DLL_DEPLOYMENT.md)** - Detailed Windows-specific documentation
- **[Testing Guide](TESTING.md)** - Running deployment tests
- **[Architecture](ARCHITECTURE.md)** - Technical architecture overview
- **Source Code**:
  - `src/clang_tool_chain/deployment/base_deployer.py`
  - `src/clang_tool_chain/deployment/dll_deployer.py`
  - `src/clang_tool_chain/deployment/so_deployer.py`
  - `src/clang_tool_chain/deployment/dylib_deployer.py`
  - `src/clang_tool_chain/deployment/factory.py`

---

**Document Version**: 1.0.0
**Last Updated**: 2026-01-25
**Status**: Complete (Phase 5 Documentation)
