# Clang/LLVM Toolchain

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

## LLVM lld Linker (Automatic, macOS/Linux)

Starting with v1.0.8+, clang-tool-chain automatically uses LLVM's `lld` linker on macOS and Linux for consistent cross-platform behavior. This replaces platform-specific system linkers:
- **macOS**: `ld64.lld` (Mach-O variant) instead of Apple's `ld64`
- **Linux**: `lld` (ELF variant) instead of GNU `ld`
- **Windows**: Already uses `lld` via GNU ABI setup

**Why lld is Default:**
- **Cross-platform consistency**: Same linker behavior on all platforms
- **Better GNU flag support**: Accepts GNU-style linker flags (like `--no-undefined`)
- **Faster linking**: lld is often 2-3x faster than system linkers
- **Uniform toolchain**: Complete LLVM stack (clang + lld) on all platforms

**Automatic lld Injection:**

The wrapper automatically adds platform-specific lld flags when linking:
- **macOS**: `-fuse-ld=ld64.lld` (explicit Mach-O variant required by LLVM 19.1.7+)
- **Linux**: `-fuse-ld=lld` (standard ELF linker)

The injection is skipped when:
- User sets `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1` (opt-out)
- User already specified `-fuse-ld=` in arguments
- Compile-only operation (`-c` flag present, no linking)

**Environment Variables:**
```bash
# Use system linker instead of lld (opt-out)
export CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1

# Then compile normally - will use ld64 on macOS, GNU ld on Linux
clang-tool-chain-cpp main.cpp -o main

# Override for specific compilation
CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1 clang-tool-chain-cpp main.cpp -o main
```

**When to Use System Linker:**
- Debugging linker-specific issues (compare lld vs system linker behavior)
- Platform-specific linker features not supported by lld
- Compatibility testing with native toolchain

**macOS Specifics:**
- lld's Mach-O port (`ld64.lld`) is production-ready (used by Chromium)
- System linker (ld64) doesn't support GNU flags like `--no-undefined`
- Using lld improves cross-platform build system compatibility

**Linux Specifics:**
- lld's ELF support is mature and well-tested
- Compatible with most GNU ld features
- Significantly faster for large projects

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

## Entry Points and Wrapper Commands

The package provides these entry points (defined in `pyproject.toml`):

**Management Commands:**
- `clang-tool-chain` → `cli:main` - Main CLI (subcommands: info, version, list-tools, path, package-version, test, purge)
- `clang-tool-chain-test` → `cli:test_main` - Diagnostic test suite (verifies installation)
- `clang-tool-chain-fetch` → `fetch:main` - Fetch utility
- `clang-tool-chain-paths` → `paths:main` - Path utility
- `clang-tool-chain-fetch-archive` → `downloads.fetch_and_archive:main` - Archive creation

**Build Utility:**
- `clang-tool-chain-build` → `wrapper:build_main` - Simple C/C++ build tool

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
