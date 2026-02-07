# Clang/LLVM Toolchain

<!-- AGENT: Read this file when working on compiler wrappers, sanitizers (ASAN/UBSAN), LLD linker,
     macOS SDK detection, Windows GNU/MSVC ABI, or sccache integration.
     Key topics: clang-tool-chain-c, clang-tool-chain-cpp, -fsanitize, lld, ld64.lld, MinGW, MSVC.
     Related: docs/ENVIRONMENT_VARIABLES.md, docs/SHARED_LIBRARY_DEPLOYMENT.md. -->

This document covers the Clang/LLVM toolchain integration, including platform-specific features and compiler wrappers.

## sccache Integration (Optional)

The package provides optional sccache integration for faster compilation through caching:

**Installation:**
```bash
# Option 1: Install via pip (Python package)
pip install clang-tool-chain[sccache]

# Option 2: Install via cargo
cargo install sccache

# Option 3: System package manager
# Linux
apt install sccache        # Debian/Ubuntu
yum install sccache        # RHEL/CentOS

# macOS
brew install sccache

# Option 4: Download binary from GitHub
# https://github.com/mozilla/sccache/releases
```

**Usage:**
```bash
# Use sccache-wrapped compilers
clang-tool-chain-sccache-c main.c -o main
clang-tool-chain-sccache-cpp main.cpp -o main

# Direct sccache commands (passthrough)
clang-tool-chain-sccache --show-stats     # Check cache statistics
clang-tool-chain-sccache --zero-stats     # Clear statistics
clang-tool-chain-sccache --start-server   # Start sccache server
clang-tool-chain-sccache --stop-server    # Stop sccache server
clang-tool-chain-sccache --version        # Show sccache version
```

**How it works:**
- `clang-tool-chain-sccache` provides direct access to sccache for querying stats, managing the server, etc.
- `clang-tool-chain-sccache-c` and `clang-tool-chain-sccache-cpp` automatically invoke sccache with the clang-tool-chain compilers
- Compilation results are cached locally, speeding up repeated builds
- Requires sccache to be available in your PATH
- If sccache is not found, the commands will fail with clear installation instructions

## Sanitizers (AddressSanitizer, UndefinedBehaviorSanitizer)

The Clang/LLVM toolchain includes full support for runtime sanitizers on Windows, with automatic DLL deployment for seamless execution.

**Supported Sanitizers:**
- **AddressSanitizer (ASAN)**: Detects memory errors (buffer overflows, use-after-free, memory leaks)
- **UndefinedBehaviorSanitizer (UBSAN)**: Detects undefined behavior (integer overflow, null pointer dereference, etc.)

**Usage:**
```bash
# AddressSanitizer - detect memory errors
clang-tool-chain-cpp -fsanitize=address main.cpp -o main.exe
./main.exe  # Automatically uses deployed ASAN DLL

# UndefinedBehaviorSanitizer - detect undefined behavior
clang-tool-chain-cpp -fsanitize=undefined main.cpp -o main.exe
./main.exe  # UBSAN runtime is statically linked

# Combine sanitizers
clang-tool-chain-cpp -fsanitize=address,undefined main.cpp -o main.exe
```

**Automatic DLL Deployment:**

When compiling with AddressSanitizer (`-fsanitize=address`), the toolchain automatically deploys required sanitizer runtime DLLs alongside your executable:

- `libclang_rt.asan_dynamic-x86_64.dll` - ASAN runtime library
- `libc++.dll` - LLVM C++ standard library (transitive dependency)
- `libunwind.dll` - LLVM unwinding library (transitive dependency)

**How It Works:**
1. **Recursive dependency scanning**: The DLL deployer scans not only the executable but also the sanitizer DLLs themselves to find transitive dependencies
2. **Automatic deployment**: All required DLLs are copied to the executable directory
3. **No PATH setup required**: Executables run immediately in `cmd.exe` without environment modifications

**Example Output:**
```bash
$ clang-tool-chain-cpp -fsanitize=address test.cpp -o test.exe
2026-01-06 05:21:30,837 - clang_tool_chain.deployment.dll_deployer - INFO - Deployed 3 runtime DLL(s) for test.exe

$ ./test.exe
=================================================================
==12345==ERROR: AddressSanitizer: stack-buffer-overflow on address...
WRITE of size 4 at 0x... thread T0
    #0 0x7ff6ae3a14fc  (test.exe+0x1400014fc)
SUMMARY: AddressSanitizer: stack-buffer-overflow
==12345==ABORTING
```

**Platform Support:**
- **Windows (x64)**: Full support with automatic DLL deployment ✅
- **Linux (x86_64/ARM64)**: Full support (sanitizers statically linked) ✅
- **macOS (x86_64/ARM64)**: Full support (sanitizers statically linked) ✅

**Performance Notes:**
- ASAN adds ~2x memory overhead and ~2x slowdown
- UBSAN adds minimal overhead (~5-20%)
- Use in debug/testing builds only, not production

**Disabling Library Deployment:**

To disable automatic sanitizer library deployment (advanced use):
```bash
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp -fsanitize=address main.cpp -o main.exe
# No libraries deployed - you must manually manage dependencies
```

**See Also:**
- [DLL Deployment Documentation](DLL_DEPLOYMENT.md) - Complete guide to automatic DLL deployment
- [Clang Sanitizer Documentation](https://clang.llvm.org/docs/AddressSanitizer.html) - Official ASAN documentation
- [UBSAN Documentation](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html) - Official UBSAN documentation

### Linux ASAN Configuration

On Linux, when using `-fsanitize=address`, clang-tool-chain automatically injects the following flags:
- `-shared-libasan` - Uses the shared ASAN runtime library (prevents undefined symbol errors during linking)
- `-Wl,--allow-shlib-undefined` - When building shared libraries (`-shared`), allows undefined symbols that will be provided by the sanitizer runtime at load time

Individual notes are printed to stderr when flags are automatically injected:
```
clang-tool-chain: note: automatically injected -shared-libasan for ASAN runtime linking (disable with CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE=1)
clang-tool-chain: note: automatically injected -Wl,--allow-shlib-undefined for shared library ASAN (disable with CLANG_TOOL_CHAIN_NO_ALLOW_SHLIB_UNDEFINED_NOTE=1)
```

**Example:**
```bash
# Compile with ASAN - runtime automatically linked
clang-tool-chain-cpp -fsanitize=address test.cpp -o test

# Build shared library with ASAN - allows undefined sanitizer symbols
clang-tool-chain-cpp -fsanitize=address -shared -fPIC mylib.cpp -o mylib.so

# Deploy ASAN shared library alongside executable (optional)
clang-tool-chain-cpp -fsanitize=address test.cpp -o test --deploy-dependencies

# Run with ASAN enabled
./test
```

**Environment Variables:**
- `CLANG_TOOL_CHAIN_NO_SHARED_ASAN=1` - Disable automatic `-shared-libasan` injection (use static ASAN)
- `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` - Disable automatic library deployment
- `CLANG_TOOL_CHAIN_NO_SANITIZER_ENV=1` - Disable automatic `ASAN_OPTIONS`/`LSAN_OPTIONS` injection at runtime

### Note Suppression (Hierarchical)

Notes can be suppressed at different levels using a hierarchical system:

| Variable | Scope | What it suppresses |
|----------|-------|-------------------|
| `CLANG_TOOL_CHAIN_NO_AUTO=1` | Global | All automatic features and notes |
| `CLANG_TOOL_CHAIN_NO_SANITIZER_NOTE=1` | Category | All sanitizer-related notes |
| `CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE=1` | Specific | Only the -shared-libasan note |
| `CLANG_TOOL_CHAIN_NO_ALLOW_SHLIB_UNDEFINED_NOTE=1` | Specific | Only the --allow-shlib-undefined note |
| `CLANG_TOOL_CHAIN_NO_LINKER_NOTE=1` | Category | All linker-related notes |
| `CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1` | Specific | Only the removed GNU flags note |
| `CLANG_TOOL_CHAIN_NO_LD64_LLD_CONVERT_NOTE=1` | Specific | Only the ld64.lld conversion note |

Each note message includes its specific disable variable for easy discoverability.

### Runtime Environment (ASAN_OPTIONS Injection)

When running executables via `clang-tool-chain-build-run`, optimal sanitizer options are automatically injected to improve stack trace quality **only when the corresponding sanitizer was used during compilation**. This fixes `<unknown module>` entries in stack traces from `dlopen()`'d shared libraries.

**Automatically injected based on compiler flags:**
- `ASAN_OPTIONS=fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1` (when `-fsanitize=address` is used)
- `LSAN_OPTIONS=fast_unwind_on_malloc=0:symbolize=1` (when `-fsanitize=address` or `-fsanitize=leak` is used)
- `ASAN_SYMBOLIZER_PATH=/path/to/llvm-symbolizer` (automatically detected from clang-tool-chain installation)

**What these options do:**
- `fast_unwind_on_malloc=0`: Use slow but accurate stack unwinding (fixes `<unknown module>` in dlopen'd libraries)
- `symbolize=1`: Enable symbolization for readable function names in stack traces
- `detect_leaks=1`: Enable leak detection (ASAN only)
- `ASAN_SYMBOLIZER_PATH`: Points to `llvm-symbolizer` binary for address-to-symbol resolution

**Opt-out:** Set `CLANG_TOOL_CHAIN_NO_SANITIZER_ENV=1` to disable automatic injection.

**User options preserved:** If you set `ASAN_OPTIONS`, `LSAN_OPTIONS`, or `ASAN_SYMBOLIZER_PATH` yourself, your values are preserved (no automatic injection for that variable).

### Programmatic API for Sanitizer Environment

External callers can use the sanitizer environment API programmatically:

```python
from clang_tool_chain import prepare_sanitizer_environment, get_symbolizer_path

# Option A: Complete environment setup (recommended)
env = prepare_sanitizer_environment(
    base_env=os.environ.copy(),
    compiler_flags=["-fsanitize=address", "-O2"]
)
# env now contains ASAN_OPTIONS, LSAN_OPTIONS, and ASAN_SYMBOLIZER_PATH

# Option B: Get just the symbolizer path
symbolizer = get_symbolizer_path()
if symbolizer:
    os.environ["ASAN_SYMBOLIZER_PATH"] = symbolizer
```

**Functions:**
- `prepare_sanitizer_environment(base_env, compiler_flags)` - Returns environment dict with all sanitizer variables injected
- `get_symbolizer_path()` - Returns path to `llvm-symbolizer` or `None` if not found
- `detect_sanitizers_from_flags(flags)` - Returns `(asan_enabled, lsan_enabled)` tuple
- `get_asan_runtime_dll()` - Returns `Path` to the ASAN runtime DLL on Windows, or `None` (for Meson workaround)
- `get_all_sanitizer_runtime_dlls()` - Returns list of `Path` objects for all sanitizer DLLs on Windows
- `get_runtime_dll_paths()` - Returns list of directory paths containing runtime DLLs on Windows

### Windows ASAN Support

Windows ASAN support works with both GNU and MSVC ABIs. Runtime DLLs are automatically deployed for GNU ABI builds.

#### Meson Test Runner Workaround

When running ASAN-instrumented tests via Meson's test runner (`meson test`), Meson overrides PATH to only include build directory DLLs. This causes tests to fail with exit code 3 (DLL not found) because the ASAN runtime DLL (`libclang_rt.asan_dynamic-x86_64.dll`) is external to the build directory.

**Solution:** Copy the ASAN DLL to your build directory so Meson discovers it automatically:

```python
from clang_tool_chain import get_asan_runtime_dll
import shutil
from pathlib import Path

# Get the ASAN DLL path
dll_path = get_asan_runtime_dll()
if dll_path:
    build_dir = Path(".build/meson-debug/tests")  # Your build directory
    shutil.copy(dll_path, build_dir / dll_path.name)
    # Now `meson test` will find the ASAN DLL
```

Alternatively, copy all sanitizer DLLs:
```python
from clang_tool_chain import get_all_sanitizer_runtime_dlls
import shutil

for dll in get_all_sanitizer_runtime_dlls():
    shutil.copy(dll, build_dir / dll.name)
```

See `BUG_ASAN.md` for detailed analysis of this issue.

### macOS ASAN Support

macOS ASAN support uses the bundled LLVM ASAN runtime with automatic deployment via `--deploy-dependencies`.

### Dynamically Loaded Libraries

See README.md "Dynamically Loaded Libraries" section for user-facing documentation on fixing `<unknown module>` in ASAN stack traces (dlopen flags, dlclose handling).

### ASAN Implementation Details

- **ASANRuntimeTransformer** (priority=250) automatically adds `-shared-libasan` when `-fsanitize=address` detected on Linux
- **ASANRuntimeTransformer** also adds `-Wl,--allow-shlib-undefined` when building shared libraries (`-shared`) with ASAN
- Shared library deployment now works on all platforms (previously Windows-only)
- The `execute_tool()` function uses `subprocess.run()` on all platforms to enable post-link deployment
- ASAN runtime library (`libclang_rt.asan.so`) is automatically deployed when `--deploy-dependencies` flag is used
- **`get_symbolizer_path()`** finds `llvm-symbolizer` from clang-tool-chain installation, falls back to system PATH
- **`prepare_sanitizer_environment()`** automatically injects `ASAN_SYMBOLIZER_PATH` when sanitizers are detected

**Implementation Files:**
- `src/clang_tool_chain/execution/arg_transformers.py` - ASANRuntimeTransformer
- `src/clang_tool_chain/execution/core.py` - `subprocess.run()` for Linux/macOS deployment support
- `src/clang_tool_chain/execution/sanitizer_env.py` - `get_symbolizer_path()` and `ASAN_SYMBOLIZER_PATH` injection
- `tests/test_asan_linking.py` - Comprehensive ASAN linking tests
- `tests/test_asan_options_injection.py` - Tests for sanitizer environment injection (43 tests)

## LLVM lld Linker (All Platforms)

Starting with v1.0.8+, clang-tool-chain uses LLVM's `lld` linker on all platforms for consistent cross-platform behavior.

**Platform-Specific Linker Behavior:**
- **macOS**: Uses `ld64.lld` (LLVM's Mach-O linker, LLVM 21.1.6)
- **Linux**: Uses `ld.lld` (LLVM's ELF linker, LLVM 21.1.5)
- **Windows**: Uses `lld` via GNU ABI setup (LLVM 21.1.5)

**Why lld is Used:**
- **Cross-platform consistency**: Same linker behavior across all platforms
- **Better GNU flag support**: Accepts GNU-style linker flags (like `--no-undefined`)
- **Faster linking**: lld is often 2-3x faster than system linkers
- **Uniform toolchain**: Complete LLVM stack (clang + lld)

**Automatic lld Injection:**

The wrapper automatically adds platform-specific lld flags when linking:
- **macOS**: `-fuse-ld=ld64.lld` (explicit Mach-O linker)
- **Linux**: `-fuse-ld=lld` (standard ELF linker)

The injection is skipped when:
- User sets `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` (opt-out)
- User already specified `-fuse-ld=` in arguments
- Compile-only operation (`-c` flag present, no linking)

**Environment Variables:**
```bash
# Use system linker instead of lld (opt-out)
export CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1

# Then compile normally - will use system linker
clang-tool-chain-cpp main.cpp -o main

# Override for specific compilation
CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1 clang-tool-chain-cpp main.cpp -o main
```

**When to Use System Linker:**
- Debugging linker-specific issues (compare lld vs system linker behavior)
- Platform-specific linker features not supported by lld
- Compatibility testing with native toolchain

**macOS Specifics:**
- Uses `ld64.lld` (LLVM's Mach-O linker) for both ARM64 and x86_64
- GNU-style flags like `--no-undefined` are automatically translated to ld64 equivalents (`-undefined error`)

**Linux Specifics:**
- lld's ELF support is mature and well-tested
- Compatible with most GNU ld features
- Significantly faster for large projects
- Thin archive support works correctly

## macOS SDK Detection (Automatic)

On macOS, system headers (like `stdio.h` and `iostream`) are NOT located in `/usr/include`. Since macOS 10.14 Mojave, Apple only provides headers through SDK bundles in Xcode or Command Line Tools. Standalone clang binaries cannot automatically find these headers without help.

**Automatic SDK Detection:**

This package implements LLVM's official three-tier SDK detection strategy (based on [LLVM patch D136315](https://reviews.llvm.org/D136315)):

1. **Explicit `-isysroot` flag**: User-provided SDK path takes priority
2. **`SDKROOT` environment variable**: Standard macOS/Xcode environment variable
3. **Automatic `xcrun --show-sdk-path`**: Fallback detection when nothing else specified

The wrapper automatically injects `-isysroot` when compiling on macOS, ensuring system headers are found without manual configuration.

**Environment Variables:**
```bash
# Disable automatic SDK detection (not recommended)
export CLANG_TOOL_CHAIN_NO_SYSROOT=1

# Use custom SDK path (standard macOS variable)
export SDKROOT=/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk
```

**Requirements:**
- macOS users must have Xcode Command Line Tools installed: `xcode-select --install`
- SDK is automatically detected via `xcrun` - no manual configuration needed

**Behavior:**
- Automatic `-isysroot` injection is skipped when:
  - User explicitly provides `-isysroot` in arguments
  - `SDKROOT` environment variable is set
  - Freestanding compilation flags are used (`-nostdinc`, `-nostdinc++`, `-nostdlib`, `-ffreestanding`)
  - `CLANG_TOOL_CHAIN_NO_SYSROOT=1` is set

## Windows GNU ABI (Automatic, v2.0.0+)

On Windows, starting with v2.0.0, the default target is **GNU ABI** (`x86_64-w64-windows-gnu`) for cross-platform consistency.

**Automatic GNU ABI Injection:**

This package implements automatic GNU target selection for Windows (similar to [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case)):

1. **Explicit `--target` flag**: User-provided target takes priority (no injection)
2. **Windows platform detection**: Automatically uses `x86_64-w64-windows-gnu` target
3. **Integrated MinGW headers**: MinGW-w64 headers/libraries are included in the Clang archive (no separate download)
4. **Automatic `--sysroot` injection**: Points to `<clang_root>/x86_64-w64-mingw32/`

The wrapper automatically injects `--target=x86_64-w64-windows-gnu` and `--sysroot` when compiling on Windows, ensuring GNU-compatible standard library headers are found.

**What's Included (v2.0.0+):**
- MinGW-w64 headers in `<clang_root>/include/` (Windows API, C/C++ standard library)
- Sysroot in `<clang_root>/x86_64-w64-mingw32/` (import libraries, runtime DLLs)
- Compiler-rt in `<clang_root>/lib/clang/<version>/` (runtime libraries and intrinsics)
- **No separate download required** - all components integrated into main Clang archive

**Environment Variables:**
```bash
# Override to use MSVC ABI for specific compilations
clang-tool-chain-c --target=x86_64-pc-windows-msvc main.c

# Use MSVC variant commands (skip GNU injection entirely)
clang-tool-chain-c-msvc main.c
clang-tool-chain-cpp-msvc main.cpp
```

**Why GNU ABI is Default:**
- **Cross-platform consistency**: Same ABI on Linux/macOS/Windows
- **C++11 strict mode support**: MSVC headers require C++14 features even in C++11 mode
- **Arduino/embedded compatibility**: Matches GCC toolchain behavior
- **Modern C++ stdlib**: Uses LLVM's libc++ (same as macOS/Linux)

**MSVC ABI Variants (Windows-Specific):**
For Windows-native projects requiring MSVC compatibility:
- `clang-tool-chain-c-msvc` - Uses `x86_64-pc-windows-msvc` target
- `clang-tool-chain-cpp-msvc` - Uses MSVC STL instead of libc++
- Required for: MSVC-compiled DLLs, COM/WinRT, Windows SDK features

**Behavior:**
- Automatic GNU target injection is skipped when:
  - User explicitly provides `--target` in arguments
  - Using MSVC variant commands (`*-msvc`)
  - MinGW sysroot is not found in the Clang installation (corrupted install)

## Windows MSVC ABI (Opt-in, Windows-Specific)

The MSVC ABI variants provide explicit MSVC target configuration for Windows-native development that requires compatibility with Visual Studio-compiled code.

**Automatic MSVC Target Injection:**

This package implements automatic MSVC target selection for MSVC variant commands:

1. **Explicit `--target` flag**: User-provided target takes priority (no injection)
2. **Windows platform detection**: Automatically uses `x86_64-pc-windows-msvc` target
3. **Windows SDK detection**: Checks for Visual Studio/Windows SDK environment variables
4. **Helpful warnings**: Shows installation guidance if SDK not detected

The wrapper automatically injects `--target=x86_64-pc-windows-msvc` when using MSVC variant commands, which:
- Selects `lld-link` as the linker (MSVC-compatible)
- Uses MSVC name mangling for C++
- Relies on system Windows SDK for headers and libraries

**MSVC Variant Commands:**
```bash
# C compiler with MSVC ABI
clang-tool-chain-c-msvc main.c -o main.exe

# C++ compiler with MSVC ABI
clang-tool-chain-cpp-msvc main.cpp -o main.exe

# sccache + MSVC variants (compilation caching)
clang-tool-chain-sccache-c-msvc main.c -o main.exe
clang-tool-chain-sccache-cpp-msvc main.cpp -o main.exe
```

**When to Use MSVC ABI:**
- **Linking with MSVC-compiled libraries**: DLLs built with Visual Studio
- **Windows-specific APIs**: COM, WinRT, Windows Runtime components
- **Visual Studio integration**: Projects that must match VS build settings
- **Third-party MSVC libraries**: Libraries distributed as MSVC binaries

**When to Use GNU ABI (Default):**
- **Cross-platform code**: Same ABI on Linux/macOS/Windows
- **Strict C++11 mode**: MSVC headers require C++14 features
- **No Windows SDK**: Integrated MinGW headers don't require VS installation
- **Embedded/Arduino**: Matches GCC toolchain behavior

**Windows SDK Requirements:**

MSVC ABI compilation requires Visual Studio or Windows SDK to be installed for system headers and libraries. The package automatically detects SDK presence via environment variables:

**Detected Environment Variables:**
- `WindowsSdkDir` / `WindowsSDKDir` - Windows SDK installation path
- `UniversalCRTSdkDir` - Universal C Runtime SDK path
- `VCToolsInstallDir` - Visual C++ Tools installation path
- `VSINSTALLDIR` - Visual Studio installation directory
- `WindowsSDKVersion` - SDK version number

**If SDK Not Detected:**

When MSVC variants are used but SDK environment variables are not found, a helpful warning is displayed with solutions:

1. **Use Visual Studio Developer Command Prompt**
   - Search for "Developer Command Prompt" in Start Menu
   - Automatically sets up SDK environment variables

2. **Run vcvarsall.bat in current shell**
   - Location: `C:\Program Files\Microsoft Visual Studio\{version}\VC\Auxiliary\Build\vcvarsall.bat`
   - Run: `vcvarsall.bat x64`

3. **Install Visual Studio or Windows SDK**
   - Visual Studio: https://visualstudio.microsoft.com/downloads/
   - Windows SDK: https://developer.microsoft.com/windows/downloads/windows-sdk/

4. **Alternative: Use GNU ABI instead**
   - Use default `clang-tool-chain-c` and `clang-tool-chain-cpp` commands
   - No SDK required (uses integrated MinGW headers)

**Target Override Behavior:**

MSVC variants respect user-provided `--target` flags:
```bash
# Force GNU target even with MSVC variant
clang-tool-chain-c-msvc --target=x86_64-w64-windows-gnu main.c

# Force custom target
clang-tool-chain-cpp-msvc --target=aarch64-pc-windows-msvc main.cpp
```

**Implementation Details:**

The MSVC ABI injection is implemented in `wrapper.py`:
- `_should_use_msvc_abi()` - Checks if MSVC injection should occur
- `_get_msvc_target_args()` - Returns `--target=x86_64-pc-windows-msvc`
- `_detect_windows_sdk()` - Detects SDK via environment variables
- `_print_msvc_sdk_warning()` - Shows helpful warning if SDK not found

These functions are called by:
- `execute_tool()` and `run_tool()` for direct compilation
- `sccache_clang_main()` and `sccache_clang_cpp_main()` for sccache variants

## Build Utilities

clang-tool-chain provides convenient build utilities that simplify compilation and development workflows.

### clang-tool-chain-build

Simple build command for compiling single-file C/C++ programs.

**Usage:**

```bash
# Build C file
clang-tool-chain-build hello.c hello

# Build C++ file
clang-tool-chain-build hello.cpp myprogram

# Build with optimization
clang-tool-chain-build hello.cpp myprogram -O2

# Build with additional flags
clang-tool-chain-build main.cpp program -std=c++17 -Wall
```

**How it works:**
- Automatically detects file extension (`.c` or `.cpp`)
- Chooses appropriate compiler (C or C++)
- Compiles to specified output name
- Passes additional arguments to compiler

### clang-tool-chain-build-run

Compile and immediately execute your program in one step.

**Usage:**

```bash
# Compile and run C++ program
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

**Caching Behavior:**

The `--cached` flag enables compilation caching based on source file content:

1. **First run:** Compiles source, stores SHA256 hash of file
2. **Subsequent runs:** Checks if file hash changed
3. **If unchanged:** Skips compilation, runs cached binary immediately
4. **If changed:** Recompiles and updates cache

**Cache location:** `.build_cache/` directory in current working directory

**Example - TDD Workflow:**

```bash
# Edit test.cpp
nano test.cpp

# Run tests (compiles on first run)
clang-tool-chain-build-run --cached test.cpp
# Output: All tests passed!

# Edit test.cpp again
nano test.cpp

# Run tests (recompiles because file changed)
clang-tool-chain-build-run --cached test.cpp
# Output: Compiling... All tests passed!

# Run again without editing (uses cache)
clang-tool-chain-build-run --cached test.cpp
# Output: All tests passed! (instant - no compilation)
```

### Shebang Support (Unix/Linux/macOS)

Make C++ files directly executable like shell scripts!

**Using installed clang-tool-chain:**

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
./script.cpp
# Output: Hello from executable C++!
```

**Using uvx (recommended - zero installation):**

```cpp
#!/usr/bin/env -S uvx clang-tool-chain-build-run --cached
#include <iostream>

int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
```

```bash
chmod +x hello.cpp
./hello.cpp  # Auto-installs clang-tool-chain via uvx on first run!
```

**Why uvx is better:**
- ✅ **Zero manual installation** - `uvx` automatically installs `clang-tool-chain` if not cached
- ✅ **Works anywhere** - No need to be in a project directory
- ✅ **Only dependency** - Just needs `uvx` in PATH (from `pip install uv`)
- ✅ **Fast subsequent runs** - Package cached after first use
- ✅ **Truly portable** - Share scripts with anyone who has `uvx`

**Install uvx once:**
```bash
pip install uv  # Installs both uv and uvx
```

**Platform Support:**

| Platform | How to Run |
|----------|------------|
| **Linux** | `chmod +x script.cpp && ./script.cpp` |
| **macOS** | `chmod +x script.cpp && ./script.cpp` |
| **Windows (Git Bash)** | `./script.cpp` (Git Bash handles shebang) |
| **Windows (cmd/PowerShell)** | `clang-tool-chain-build-run --cached script.cpp` |

### clang-tool-chain-run

Run a compiled executable (primarily for internal use by build-run command).

**Usage:**

```bash
# Run executable
clang-tool-chain-run ./program

# Run with arguments
clang-tool-chain-run ./program arg1 arg2

# Run executable in specific directory
clang-tool-chain-run /path/to/program
```

**Note:** This command is mainly used internally by `clang-tool-chain-build-run`. For general use, just execute your program directly (`./program`).

## Entry Points and Wrapper Commands

The package provides these entry points (defined in `pyproject.toml`):

**Management Commands:**
- `clang-tool-chain` → `cli:main` - Main CLI (subcommands: info, version, list-tools, path, package-version, test, purge)
- `clang-tool-chain-test` → `cli:test_main` - Diagnostic test suite (verifies installation)
- `clang-tool-chain-fetch` → `fetch:main` - Fetch utility
- `clang-tool-chain-paths` → `paths:main` - Path utility
- `clang-tool-chain-fetch-archive` → `downloads.fetch_and_archive:main` - Archive creation

**Build Utilities:**
- `clang-tool-chain-build` → `wrapper:build_main` - Simple C/C++ build tool
- `clang-tool-chain-build-run` → `wrapper:build_run_main` - Build and run in one step (with caching)
- `clang-tool-chain-run` → `wrapper:run_main` - Run compiled executable

**Compiler Wrappers:**
- `clang-tool-chain-c` → `wrapper:clang_main` - C compiler (GNU ABI on Windows)
- `clang-tool-chain-cpp` → `wrapper:clang_cpp_main` - C++ compiler (GNU ABI on Windows)
- `clang-tool-chain-c-msvc` → `wrapper:clang_msvc_main` - C compiler (MSVC ABI, Windows only)
- `clang-tool-chain-cpp-msvc` → `wrapper:clang_cpp_msvc_main` - C++ compiler (MSVC ABI, Windows only)

**sccache Integration:**
- `clang-tool-chain-sccache` → `cli:sccache_main` - Direct sccache passthrough (stats, management)
- `clang-tool-chain-sccache-c` → `cli:sccache_c_main` - sccache + C compiler (GNU ABI on Windows)
- `clang-tool-chain-sccache-cpp` → `cli:sccache_cpp_main` - sccache + C++ compiler (GNU ABI on Windows)
- `clang-tool-chain-sccache-c-msvc` → `cli:sccache_c_msvc_main` - sccache + C compiler (MSVC ABI, Windows only)
- `clang-tool-chain-sccache-cpp-msvc` → `cli:sccache_cpp_msvc_main` - sccache + C++ compiler (MSVC ABI, Windows only)

**Linker and Archiver:**
- `clang-tool-chain-ld` → `wrapper:lld_main` - Linker (lld/lld-link)
- `clang-tool-chain-ar` → `wrapper:llvm_ar_main` - Archive tool

**Binary Utilities:**
- `clang-tool-chain-nm` → `wrapper:llvm_nm_main` - Symbol viewer
- `clang-tool-chain-objdump` → `wrapper:llvm_objdump_main` - Object dumper
- `clang-tool-chain-objcopy` → `wrapper:llvm_objcopy_main` - Object copy
- `clang-tool-chain-ranlib` → `wrapper:llvm_ranlib_main` - Archive index
- `clang-tool-chain-strip` → `wrapper:llvm_strip_main` - Symbol stripper
- `clang-tool-chain-readelf` → `wrapper:llvm_readelf_main` - ELF reader

**Additional Tools:**
- `clang-tool-chain-as` → `wrapper:llvm_as_main` - LLVM assembler
- `clang-tool-chain-dis` → `wrapper:llvm_dis_main` - LLVM disassembler
- `clang-tool-chain-format` → `wrapper:clang_format_main` - Code formatter
- `clang-tool-chain-tidy` → `wrapper:clang_tidy_main` - Static analyzer
