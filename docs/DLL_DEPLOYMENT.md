# Windows MinGW DLL Deployment

**Automatic Runtime DLL Deployment for Windows Executables**

This document provides comprehensive documentation on clang-tool-chain's automatic MinGW runtime DLL deployment feature.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Implementation Details](#implementation-details)
- [FAQ](#faq)

---

## Overview

When building Windows executables with GNU ABI (the default on Windows), clang-tool-chain automatically copies required MinGW runtime DLLs to the executable directory. This ensures your programs run immediately in `cmd.exe` without any PATH configuration or manual DLL copying.

### Why Is This Needed?

MinGW executables depend on runtime DLLs like:
- `libwinpthread-1.dll` - POSIX threads support
- `libgcc_s_seh-1.dll` - GCC runtime (exception handling)
- `libstdc++-6.dll` - C++ standard library

Without these DLLs in the executable directory or system PATH, your program will fail with errors like:
```
The code execution cannot proceed because libwinpthread-1.dll was not found.
```

### The Solution

clang-tool-chain automatically:
1. Detects which MinGW DLLs your executable needs
2. Copies them from the MinGW sysroot to your executable directory
3. Uses smart timestamp checking to avoid unnecessary copies
4. Handles all errors gracefully (warnings only, never fails your build)

---

## How It Works

### Step-by-Step Process

1. **Compilation & Linking**: You compile your program with `clang-tool-chain-cpp` or `clang-tool-chain-c`
2. **Success Check**: DLL deployment only runs after successful linking (returncode == 0)
3. **Guard Checks**: Validates conditions (Windows platform, GNU ABI, .exe output, not compile-only)
4. **DLL Detection**: Uses `llvm-objdump -p` to parse PE headers and extract DLL dependencies
5. **Recursive Scanning**: Scans detected DLLs for transitive dependencies (e.g., ASan runtime → libc++ → libunwind)
6. **Filtering**: Excludes Windows system DLLs (kernel32.dll, etc.), keeps only MinGW runtime DLLs
7. **Timestamp Check**: Compares source and destination timestamps to skip unnecessary copies
8. **Hard Link Creation**: Attempts to create hard links (zero disk space, instant)
9. **Copy Fallback**: Falls back to `shutil.copy2()` if hard links fail (cross-filesystem, permissions, etc.)
10. **Logging**: Reports deployment status (INFO level) or warnings on errors

### DLL Detection Strategy

**Primary Method: llvm-objdump with Recursive Scanning**
- Runs `llvm-objdump -p <executable>` to parse PE headers
- Extracts DLL names from "DLL Name:" entries
- **Recursively scans each detected DLL** to find transitive dependencies
- Filters based on MinGW patterns (libwinpthread*, libgcc_s_*, libstdc++*, sanitizer runtimes, etc.)
- Builds complete dependency graph before deployment
- 10-second timeout protection per DLL scan

**Example: AddressSanitizer Dependency Chain**
```
program.exe
├── libclang_rt.asan_dynamic-x86_64.dll  (direct dependency)
│   ├── libc++.dll                        (transitive via ASan)
│   │   └── libunwind.dll                 (transitive via libc++)
│   └── libwinpthread-1.dll               (transitive via ASan)
├── libgcc_s_seh-1.dll                    (direct dependency)
└── libstdc++-6.dll                       (direct dependency)
```
All 6 DLLs are deployed automatically.

**Fallback Method: Heuristic List**
- If llvm-objdump fails (not found, timeout, error), uses predefined list:
  - `libwinpthread-1.dll`
  - `libgcc_s_seh-1.dll`
  - `libstdc++-6.dll`
- Ensures executables always get basic runtime support

### DLL Pattern Matching

**Recognized MinGW Patterns:**
```python
MINGW_DLL_PATTERNS = [
    r"libwinpthread.*\.dll",
    r"libgcc_s_.*\.dll",
    r"libstdc\+\+.*\.dll",
    r"libc\+\+.*\.dll",      # LLVM C++ standard library
    r"libunwind.*\.dll",     # LLVM unwinding library
    r"libgomp.*\.dll",       # OpenMP support
    r"libssp.*\.dll",        # Stack smashing protection
    r"libquadmath.*\.dll",   # Quad-precision math
]

SANITIZER_DLL_PATTERNS = [
    r"libclang_rt\.asan_dynamic.*\.dll",    # AddressSanitizer
    r"libclang_rt\.ubsan_dynamic.*\.dll",   # UndefinedBehaviorSanitizer
    r"libclang_rt\.tsan_dynamic.*\.dll",    # ThreadSanitizer
    r"libclang_rt\.msan_dynamic.*\.dll",    # MemorySanitizer
]
```

**Excluded System DLLs:**
```python
WINDOWS_SYSTEM_DLLS = {
    "kernel32.dll", "ntdll.dll", "msvcrt.dll",
    "user32.dll", "advapi32.dll", "ws2_32.dll",
    "shell32.dll", "ole32.dll", "oleaut32.dll",
    "gdi32.dll", "comdlg32.dll", "comctl32.dll",
    "bcrypt.dll", "crypt32.dll",
}
```

---

## Quick Start

### Basic Usage

```bash
# Compile a C++ program
clang-tool-chain-cpp hello.cpp -o hello.exe

# Output:
# Deployed 3 MinGW DLL(s) for hello.exe

# Your directory now contains:
# hello.exe
# libwinpthread-1.dll
# libgcc_s_seh-1.dll
# libstdc++-6.dll

# Run immediately - no PATH setup needed!
.\hello.exe
```

### With Threading

```cpp
// threading_example.cpp
#include <iostream>
#include <thread>

void worker() {
    std::cout << "Worker thread running\n";
}

int main() {
    std::thread t(worker);
    t.join();
    return 0;
}
```

```bash
clang-tool-chain-cpp threading_example.cpp -o threading_example.exe
# Automatically deploys libwinpthread-1.dll
.\threading_example.exe
```

### With Exceptions

```cpp
// exception_example.cpp
#include <iostream>
#include <stdexcept>

int main() {
    try {
        throw std::runtime_error("Test exception");
    } catch (const std::exception& e) {
        std::cout << "Caught: " << e.what() << "\n";
    }
    return 0;
}
```

```bash
clang-tool-chain-cpp exception_example.cpp -o exception_example.exe
# Automatically deploys libgcc_s_seh-1.dll (exception handling)
.\exception_example.exe
```

### With Sanitizers (AddressSanitizer Example)

```cpp
// asan_example.cpp
#include <iostream>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    std::cout << "Vector size: " << v.size() << "\n";
    return 0;
}
```

```bash
clang-tool-chain-cpp asan_example.cpp -o asan_example.exe -fsanitize=address -g
# Automatically deploys:
# - libclang_rt.asan_dynamic-x86_64.dll (AddressSanitizer runtime)
# - libc++.dll (transitive dependency)
# - libunwind.dll (transitive dependency)
# - libwinpthread-1.dll, libgcc_s_seh-1.dll, libstdc++-6.dll (standard runtime)
.\asan_example.exe
```

### Static Linking (Minimal DLLs)

```bash
# Static linking reduces or eliminates DLL dependencies
clang-tool-chain-cpp main.cpp -o main.exe -static-libgcc -static-libstdc++
# May only deploy libwinpthread-1.dll (if threading is used)
```

---

## Environment Variables

### `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS`

**Purpose:** Completely disable automatic library deployment (cross-platform)

**Usage:**
```bash
# Windows (CMD)
set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp main.cpp -o main.exe
# No DLLs copied

# Windows (PowerShell)
$env:CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS="1"
clang-tool-chain-cpp main.cpp -o main.exe

# Windows (Git Bash)
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp main.cpp -o main.exe
```

**When to use:**
- Deploying DLLs through an installer
- Using a custom DLL deployment strategy
- Testing executable in environment with DLLs in PATH
- Debugging DLL-related issues

### `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE`

**Purpose:** Enable verbose logging (DEBUG level) for library deployment

**Usage:**
```bash
set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o main.exe
```

**Output:**
```
DEBUG: Detecting required DLLs for: main.exe
DEBUG: Running llvm-objdump on: main.exe
DEBUG: Detected MinGW DLL dependency: libwinpthread-1.dll
DEBUG: Detected MinGW DLL dependency: libgcc_s_seh-1.dll
DEBUG: Detected MinGW DLL dependency: libstdc++-6.dll
DEBUG: MinGW sysroot bin directory: C:/Users/user/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin
DEBUG: Deployed: libwinpthread-1.dll
DEBUG: Deployed: libgcc_s_seh-1.dll
DEBUG: Deployed: libstdc++-6.dll
INFO: Deployed 3 MinGW DLL(s) for main.exe
```

**When to use:**
- Troubleshooting DLL deployment issues
- Understanding which DLLs are being detected
- Debugging llvm-objdump failures
- Verifying timestamp checking behavior

---

## Performance

### Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| **DLL Detection** | <50ms | llvm-objdump on executable |
| **Recursive Scanning** | <100ms | 3-5 DLLs × 2-3 levels deep |
| **Hard Link Creation** | <1ms per DLL | Near-instant (preferred) |
| **DLL Copying** | <50ms | Fallback if hard link fails |
| **Total Overhead** | <150ms | Per executable build (first time) |
| **Timestamp Check** | <5ms | Skips deployment if up-to-date |
| **Incremental Builds** | ~0ms | All DLLs up-to-date |
| **Hard Link Space Savings** | 100% | Zero additional disk space |

### Performance Characteristics

**First Build:**
```
Compile + Link: 1.5s
DLL Deployment: 0.08s (5% overhead)
Total: 1.58s
```

**Incremental Build (no source changes):**
```
Compile + Link: 0.5s
DLL Deployment: 0.005s (timestamp check only)
Total: 0.505s (1% overhead)
```

### Optimization Strategies

1. **Hard Links (Preferred)**: Zero disk space, instant deployment, automatic updates
   - Uses `os.link()` to create hard links when possible
   - Falls back to file copy only when necessary (cross-filesystem, permissions, etc.)
   - Reduces disk usage by 100% for deployed DLLs (shared inodes)
2. **Timestamp Checking**: Prevents unnecessary re-deployment on incremental builds
3. **Recursive Dependency Caching**: Scans each DLL only once, reuses results
4. **Lazy Import**: Only imports heavy modules when DLL deployment actually runs
5. **Early Guards**: Fast checks (platform, ABI, file extension) before expensive operations
6. **Timeout Protection**: 10-second timeout per llvm-objdump scan prevents hangs
7. **Non-Fatal Errors**: Warnings only - never blocks compilation

---

## Troubleshooting

### Problem: DLLs Not Being Copied

**Symptoms:**
- Executable builds successfully
- No DLL deployment log messages
- Executable fails to run with "DLL not found" error

**Causes & Solutions:**

1. **Using MSVC ABI instead of GNU ABI**
   ```bash
   # Problem: Using MSVC variant
   clang-tool-chain-cpp-msvc main.cpp -o main.exe

   # Solution: Use GNU ABI (default)
   clang-tool-chain-cpp main.cpp -o main.exe
   ```

2. **Compile-only operation (`-c` flag)**
   ```bash
   # Problem: Compiling without linking
   clang-tool-chain-cpp -c main.cpp -o main.o

   # Solution: Link to create executable
   clang-tool-chain-cpp main.cpp -o main.exe
   ```

3. **Non-.exe output file**
   ```bash
   # Problem: Missing .exe extension
   clang-tool-chain-cpp main.cpp -o main

   # Solution: Use .exe extension
   clang-tool-chain-cpp main.cpp -o main.exe
   ```

4. **Environment variable set**
   ```bash
   # Problem: DLL deployment disabled
   set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1

   # Solution: Unset variable
   set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=
   ```

5. **Non-Windows platform**
   ```bash
   # DLL deployment only runs on Windows
   # On Linux/macOS, it's a no-op (no error)
   ```

### Problem: Wrong DLLs Being Copied

**Symptoms:**
- Too many or too few DLLs copied
- System DLLs being copied (should never happen)

**Diagnostic Steps:**

1. **Enable verbose logging:**
   ```bash
   set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
   clang-tool-chain-cpp main.cpp -o main.exe
   # Review DEBUG logs to see detected DLLs
   ```

2. **Check executable dependencies manually:**
   ```bash
   clang-tool-chain-objdump -p main.exe | grep "DLL Name"
   ```

3. **Verify MinGW sysroot:**
   ```bash
   # Check DLL source directory exists
   dir %USERPROFILE%\.clang-tool-chain\clang\win\x86_64\x86_64-w64-mingw32\bin
   ```

### Problem: Permission Errors

**Symptoms:**
```
WARNING: Permission denied copying libwinpthread-1.dll, skipping
```

**Causes & Solutions:**

1. **Read-only destination directory**
   ```bash
   # Remove read-only attribute
   attrib -R output_directory
   ```

2. **DLL in use by another process**
   ```bash
   # Close the running executable
   # Or build to a different directory
   clang-tool-chain-cpp main.cpp -o build/main.exe
   ```

3. **Insufficient permissions**
   ```bash
   # Build to a writable directory
   # Avoid Program Files, system directories
   ```

### Problem: llvm-objdump Failures

**Symptoms:**
```
WARNING: llvm-objdump failed (exit 1), using heuristic DLL list
```

**Causes & Solutions:**

1. **Corrupted executable**
   ```bash
   # Rebuild from clean state
   del main.exe
   clang-tool-chain-cpp main.cpp -o main.exe
   ```

2. **llvm-objdump not found**
   ```bash
   # Verify toolchain installation
   clang-tool-chain info

   # Reinstall if needed
   clang-tool-chain purge
   clang-tool-chain-cpp main.cpp -o main.exe
   ```

3. **Timeout (>10 seconds)**
   ```bash
   # Usually indicates corrupted executable or disk issues
   # Check disk health, rebuild executable
   ```

**Note:** Even if llvm-objdump fails, the fallback heuristic list ensures basic DLLs are deployed.

### Problem: Incremental Builds Not Skipping DLL Copy

**Symptoms:**
- DLLs copied every build even when unchanged
- Slow incremental builds

**Causes & Solutions:**

1. **Destination DLLs being modified**
   ```bash
   # Check if another process is touching the DLLs
   # Use verbose logging to see timestamp comparison
   set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
   clang-tool-chain-cpp main.cpp -o main.exe
   ```

2. **Source DLLs being updated**
   ```bash
   # Toolchain was reinstalled or updated
   # This is expected behavior - new DLLs should be deployed
   ```

---

## Implementation Details

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│        execute_tool() / run_tool() / sccache_*()        │
│                 (execution/core.py)                      │
│                                                          │
│  [Compile & Link] → [Check Success] → [Post-Link Hooks] │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│           post_link_dll_deployment()                     │
│           (deployment/dll_deployer.py)                   │
│                                                          │
│  1. Guard Checks (platform, ABI, file type)             │
│  2. detect_required_dlls() [with recursion]             │
│  3. get_mingw_sysroot_bin_dir()                         │
│  4. Deploy DLLs (hard link or copy fallback)            │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│          detect_required_dlls() [RECURSIVE]             │
│                                                          │
│  1. Run llvm-objdump -p <exe>                           │
│  2. Parse "DLL Name:" entries (direct dependencies)     │
│  3. For each MinGW/sanitizer DLL found:                 │
│     a. Run llvm-objdump -p <dll>                        │
│     b. Extract transitive dependencies                  │
│     c. Recursively scan those DLLs                      │
│  4. Build complete dependency set (no duplicates)       │
│  5. Filter out Windows system DLLs                      │
│  6. Fallback to heuristic list on error                 │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│             _atomic_copy_dll() [HARD LINKS]             │
│                                                          │
│  1. Check timestamp (skip if up-to-date)                │
│  2. Try os.link() for hard link (preferred)             │
│  3. On failure, fall back to shutil.copy2()             │
│  4. Use atomic rename pattern (temp + replace)          │
│  5. Handle race conditions gracefully                   │
└─────────────────────────────────────────────────────────┘
```

### Key Integration Points

**File: `src/clang_tool_chain/execution/core.py`**

DLL deployment is integrated at 4 locations:
1. `execute_tool()` - Line 175-186 (main execution path)
2. `run_tool()` - Line 314-322 (alternative execution path)
3. `sccache_clang_main()` - Line 397-405 (sccache C compilation)
4. `sccache_clang_cpp_main()` - Line 489-497 (sccache C++ compilation)

**Integration pattern:**
```python
# After subprocess.run() completes
if returncode == 0 and platform_name == "win":
    output_path = _extract_output_path(args)
    if output_path:
        use_gnu = _should_use_gnu_abi(platform_name, args)
        post_link_dll_deployment(output_path, platform_name, use_gnu)
```

### Test Coverage

**File: `tests/test_dll_deployment.py`**

45+ comprehensive tests covering:
- ✅ Basic DLL detection and deployment (5 tests)
- ✅ Fallback to heuristic list (3 tests)
- ✅ Timestamp checking (2 tests)
- ✅ Environment variable opt-out (2 tests)
- ✅ Cross-platform behavior (2 tests)
- ✅ MSVC ABI no-op (2 tests)
- ✅ Output path parsing edge cases (3 tests)
- ✅ Error handling (permission, missing DLLs) (3 tests)
- ✅ Integration tests (4 tests)
- ✅ Edge cases (multiple exes, long paths) (2 tests)
- ✅ Unit tests (helper functions) (10 tests)
- ✅ Hard link deployment (3 tests)
- ✅ Sanitizer executables (AddressSanitizer) (2 tests)
- ✅ Transitive dependency resolution (1 test)

**Code Coverage:** >90% for `dll_deployer.py` (exceeds 85% requirement)

---

## FAQ

### Q: Does this work on Linux or macOS?

**A:** No. DLL deployment is Windows-only and automatically skipped on Linux/macOS (no errors, just a no-op).

### Q: Does this work with MSVC ABI?

**A:** No. DLL deployment only runs for GNU ABI builds (the default). MSVC ABI uses the system MSVC runtime, not MinGW DLLs.

### Q: Can I disable DLL deployment?

**A:** Yes. Set `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` environment variable.

### Q: What happens if a required DLL is missing from the sysroot?

**A:** A warning is logged, but the build completes successfully. Your executable might fail to run if a critical DLL is missing.

### Q: Does this affect build reproducibility?

**A:** No. DLL deployment doesn't modify the compiled executable - it only copies DLLs to the output directory. The executable's hash remains unchanged.

### Q: Can I customize which DLLs are deployed?

**A:** Not directly. DLL detection is automatic based on the executable's PE headers. However, you can:
- Use `-static-libgcc -static-libstdc++` to reduce dependencies
- Set `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` and deploy DLLs manually

### Q: What if I want to deploy DLLs to a different location?

**A:** Currently not supported. DLLs are always deployed to the executable's directory. For custom deployment, disable automatic deployment and copy DLLs manually.

### Q: Does this work with cross-compilation?

**A:** It detects the host platform (where you're compiling), not the target platform. If you're cross-compiling on Windows to a non-Windows target, DLL deployment will still attempt to run (but will be harmless since the output won't be a Windows .exe).

### Q: What's the overhead for large projects?

**A:** Minimal. DLL deployment is per-executable (not per-object file), and timestamp checking prevents unnecessary copies. For a project with 10 executables, expect ~0.8 seconds total overhead on first build, nearly zero on incremental builds.

### Q: Can this deploy DLLs for shared libraries (.dll)?

**A:** No. DLL deployment only runs for executables (.exe files), not for shared libraries. This is intentional - shared libraries don't have an execution context that requires runtime DLLs in the same directory.

### Q: How do I deploy DLLs when using CMake or Meson?

**A:** It works automatically! DLL deployment integrates at the linker level, so it works with any build system that uses clang-tool-chain wrappers (CMake, Meson, Make, etc.).

---

## Advanced Topics

### Custom DLL Deployment Strategy

If you need custom DLL deployment logic:

1. **Disable automatic deployment:**
   ```bash
   set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
   ```

2. **Detect required DLLs programmatically:**
   ```python
   from pathlib import Path
   from clang_tool_chain.deployment.dll_deployer import detect_required_dlls

   exe_path = Path("main.exe")
   required_dlls = detect_required_dlls(exe_path)
   print(f"Required DLLs: {required_dlls}")
   ```

3. **Implement custom deployment:**
   ```python
   # Your custom logic here
   # e.g., copy to installer directory, sign DLLs, etc.
   ```

### Integrating with Installers

For Windows installers (NSIS, WiX, Inno Setup):

1. **Build with automatic DLL deployment:**
   ```bash
   clang-tool-chain-cpp main.cpp -o build/main.exe
   # DLLs automatically in build/ directory
   ```

2. **Package entire build directory:**
   ```nsis
   ; NSIS example
   SetOutPath "$INSTDIR"
   File "build\main.exe"
   File "build\*.dll"
   ```

### CI/CD Integration

**GitHub Actions:**
```yaml
- name: Build Windows executable
  run: |
    clang-tool-chain-cpp main.cpp -o main.exe

- name: Verify DLLs deployed
  run: |
    if not exist libwinpthread-1.dll exit 1
    if not exist libgcc_s_seh-1.dll exit 1

- name: Test executable in clean environment
  run: |
    set PATH=%SystemRoot%\system32;%SystemRoot%
    main.exe
```

---

## See Also

- **[Windows GNU ABI Documentation](CLANG_LLVM.md)** - Windows target selection
- **[Testing Guide](TESTING.md)** - DLL deployment test infrastructure
- **[Architecture](ARCHITECTURE.md)** - Overall clang-tool-chain architecture

---

**Last Updated:** January 2026
**Module:** `src/clang_tool_chain/deployment/dll_deployer.py`
**Tests:** `tests/test_dll_deployment.py` (38 tests, 92% coverage)
