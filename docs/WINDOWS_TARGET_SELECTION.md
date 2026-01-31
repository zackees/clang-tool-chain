# Windows Target Selection

Choosing between GNU ABI and MSVC ABI on Windows.

## Default Behavior (GNU ABI - Recommended)

The default Windows target is `x86_64-w64-mingw32` (GNU ABI) for cross-platform consistency:

```bash
# These commands use GNU ABI by default on Windows:
clang-tool-chain-c hello.c -o hello
clang-tool-chain-cpp hello.cpp -o hello

# Equivalent to explicitly specifying:
clang-tool-chain-c --target=x86_64-w64-mingw32 hello.c -o hello
```

### Why GNU ABI is Default

1. **Cross-platform consistency** - Same ABI on Linux/macOS/Windows
2. **C++11 strict mode support** - MSVC headers require C++14 features even in C++11 mode
3. **Embedded/Arduino compatibility** - Matches GCC toolchain behavior
4. **Modern C++ standard library** - Uses LLVM's libc++ (same as macOS/Linux)
5. **No Visual Studio required** - Includes MinGW-w64 sysroot (no external dependencies)

This matches the approach of [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case) and other modern cross-platform toolchains.

## MSVC ABI (Windows-Specific Projects)

For Windows-native projects that need MSVC compatibility:

```bash
# Use MSVC variants for Windows-specific development:
clang-tool-chain-c-msvc main.c -o program.exe
clang-tool-chain-cpp-msvc main.cpp -o program.exe

# Or explicitly specify MSVC target with default commands:
clang-tool-chain-c --target=x86_64-pc-windows-msvc main.c -o program.exe
```

### Use MSVC ABI When

- Linking with MSVC-compiled DLLs (with C++ APIs)
- Using Windows SDK features not in MinGW
- Requiring Visual Studio debugger integration
- Building COM/WinRT/Windows Runtime components
- Distributing libraries to MSVC users

### MSVC Requirements

- **Visual Studio Build Tools 2019+** (or full Visual Studio)
- **Windows SDK** (usually installed with Build Tools)

```powershell
# Install Visual Studio Build Tools
# Download from: https://visualstudio.microsoft.com/downloads/
# Select "Desktop development with C++"
```

## Comparison Table

| Feature | GNU ABI (Default) | MSVC ABI (Opt-in) |
|---------|------------------|------------------|
| **C++ Standard Library** | libc++ (LLVM) | MSVC STL |
| **C++ ABI** | Itanium (like GCC) | Microsoft |
| **Cross-platform consistency** | ✅ Yes | ❌ Windows-only |
| **C++11 strict mode** | ✅ Works | ❌ Requires C++14+ |
| **Link with MSVC libs** | ❌ C++ ABI mismatch | ✅ Compatible |
| **Link with MinGW libs** | ✅ Compatible | ❌ ABI mismatch |
| **Arduino/embedded** | ✅ Compatible | ❌ Different ABI |
| **Download size** | ~90 MB (with MinGW) | ~71 MB (LLVM only) |
| **Requires Visual Studio** | ❌ No | ⚠️ Yes (Build Tools) |
| **DLL deployment** | ✅ Automatic | ❌ Manual (system DLLs) |
| **Exception handling** | SEH (structured) | SEH (structured) |
| **Name mangling** | GCC-style | MSVC-style |

## Advanced: Manual Target Selection

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

## Common Workflows

### GNU ABI (Cross-Platform Project)

```bash
# Compile with GNU ABI (default)
clang-tool-chain-cpp main.cpp utils.cpp -o program.exe

# Automatic DLL deployment
# Output: Deployed 3 MinGW DLL(s) for program.exe

# Run immediately (no PATH setup)
.\program.exe
```

**Deployed DLLs:**
- `libwinpthread-1.dll` - Threading support
- `libgcc_s_seh-1.dll` - GCC runtime support
- `libstdc++-6.dll` - C++ standard library (if using libstdc++)

### MSVC ABI (Windows-Native Project)

```bash
# Compile with MSVC ABI
clang-tool-chain-cpp-msvc main.cpp utils.cpp -o program.exe

# No DLL deployment (uses system MSVC runtime)
# Requires Visual Studio Build Tools installed

# Run (system DLLs automatically found)
.\program.exe
```

**System DLLs used:**
- `msvcp140.dll` - MSVC C++ standard library
- `vcruntime140.dll` - MSVC runtime support

### Mixing ABIs (Advanced)

You can link C-only code between ABIs (C has standardized ABI):

```bash
# Compile C library with GNU ABI
clang-tool-chain-c -c utils.c -o utils_gnu.o

# Compile C library with MSVC ABI
clang-tool-chain-c-msvc -c utils.c -o utils_msvc.o

# Both work because C ABI is compatible!
```

**Never mix C++ ABIs:**
```bash
# ❌ DON'T DO THIS - ABI mismatch!
clang-tool-chain-cpp -c module1.cpp -o module1.o  # GNU ABI
clang-tool-chain-cpp-msvc module1.o main.cpp -o program.exe  # MSVC ABI
# Result: Linker errors or runtime crashes
```

## DLL Deployment

### GNU ABI (Automatic)

MinGW DLLs are automatically deployed:

```bash
clang-tool-chain-cpp hello.cpp -o hello.exe
# Output: Deployed 3 MinGW DLL(s) for hello.exe

# DLLs copied to executable directory:
# - libwinpthread-1.dll
# - libgcc_s_seh-1.dll
# - libstdc++-6.dll (if needed)
```

**Disable deployment:**
```bash
set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
```

See [DLL Deployment Guide](DLL_DEPLOYMENT.md) for comprehensive details.

### MSVC ABI (Manual)

MSVC runtime DLLs are system-installed:

```bash
# User must have Visual C++ Redistributable installed
# Or DLLs in PATH
# Or use static linking:
clang-tool-chain-cpp-msvc main.cpp -o program.exe -static
```

## ABI Detection at Runtime

You can detect which ABI your binary uses:

```bash
# Windows (check dependencies)
dumpbin /DEPENDENTS program.exe

# GNU ABI shows:
# - libwinpthread-1.dll
# - libgcc_s_seh-1.dll

# MSVC ABI shows:
# - msvcp140.dll
# - vcruntime140.dll
```

Or use clang-tool-chain's bundled objdump:

```bash
clang-tool-chain-objdump -p program.exe | grep "DLL Name"
```

## Troubleshooting

### "MSVC not found" when using -msvc commands

Install Visual Studio Build Tools:
```powershell
# Download from: https://visualstudio.microsoft.com/downloads/
# Install "Desktop development with C++"
```

### "Missing DLL" errors (GNU ABI)

DLL deployment should be automatic. If it fails:

```bash
# Enable verbose logging
set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program.exe

# Or manually copy DLLs
copy %USERPROFILE%\.clang-tool-chain\mingw-w64\bin\*.dll .
```

### "Unresolved external symbol" linker errors

Likely mixing ABIs. Ensure all C++ object files use the same ABI:

```bash
# ✅ Good: All GNU ABI
clang-tool-chain-cpp module1.cpp module2.cpp main.cpp -o program.exe

# ✅ Good: All MSVC ABI
clang-tool-chain-cpp-msvc module1.cpp module2.cpp main.cpp -o program.exe

# ❌ Bad: Mixing ABIs
clang-tool-chain-cpp module1.cpp -c -o module1.o
clang-tool-chain-cpp-msvc module1.o main.cpp -o program.exe
```

## Recommendations

### Use GNU ABI (Default) If

- ✅ Building cross-platform applications
- ✅ Using C++11 (strict mode)
- ✅ Targeting embedded systems / Arduino
- ✅ Want zero external dependencies
- ✅ Distributing standalone executables
- ✅ Working with GCC-compiled libraries

### Use MSVC ABI If

- ✅ Building Windows-only applications
- ✅ Linking with MSVC-compiled C++ libraries
- ✅ Using Windows-specific APIs (COM, WinRT)
- ✅ Distributing libraries to MSVC users
- ✅ Requiring Visual Studio debugger integration
- ✅ Company policy requires MSVC toolchain

## Related Documentation

- [DLL Deployment Guide](DLL_DEPLOYMENT.md) - Automatic DLL deployment details
- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Core compiler documentation
- [Platform Support](PLATFORM_SUPPORT.md) - Windows requirements
- [Examples](EXAMPLES.md) - Windows compilation examples
