# Task: Add Windows GNU ABI Target Support to clang-tool-chain

## Problem Summary

When attempting to migrate from `ziglang` (Python package) to `clang-tool-chain` v1.0.0, we discovered that `clang-tool-chain` only supports the MSVC ABI target on Windows (`x86_64-pc-windows-msvc`), but does not include the necessary GNU-compatible standard library headers and runtime needed for GNU ABI targets (`x86_64-windows-gnu`).

## Background

The FastLED project previously used the `ziglang` Python package which bundles:
- Clang compiler (via zig cc/zig c++)
- Complete GNU-compatible C/C++ standard library (libc++)
- GNU-compatible linker (lld)
- Support for `--target=x86_64-windows-gnu`

We wanted to migrate to `clang-tool-chain` to:
1. Remove complex wrapper scripts (zig required multi-command wrappers for sccache)
2. Use a dedicated clang toolchain package instead of zig's bundled clang
3. Take advantage of built-in sccache support in clang-tool-chain

## What Works

✅ `clang-tool-chain` successfully provides clang executables on Windows
✅ Targeting MSVC ABI works: `clang-tool-chain-c --version` shows `Target: x86_64-pc-windows-msvc`
✅ Clang accepts the `--target=x86_64-windows-gnu` flag and reports the correct target
✅ Built-in sccache wrapper support (`clang-tool-chain-sccache-c`, `clang-tool-chain-sccache-cpp`)

## What Fails

❌ When compiling C++ code with `--target=x86_64-windows-gnu`, clang cannot find GNU-compatible standard library headers:

```
fatal error: 'initializer_list' file not found
    9 | #include <initializer_list>
      |          ^~~~~~~~~~~~~~~~~~
```

❌ When compiling without `--target` flag (defaults to MSVC ABI), code compiled with `-std=gnu++11` fails because MSVC's `<type_traits>` uses C++14 features:

```
C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC\14.29.30133\include\xstddef:260:22: error: 'auto' return without trailing return type; deduced return types are a C++14 extension
```

## Root Cause

The clang-tool-chain package bundles clang but does not include:
- MinGW-w64 headers (C/C++ standard library headers for GNU ABI)
- MinGW-w64 runtime libraries (libc++, libstdc++, etc.)
- GNU-compatible system headers

When targeting `x86_64-windows-gnu`, clang looks for GNU-style headers but only finds MSVC headers, which are incompatible.

## Requested Solution

Add Windows GNU ABI support to `clang-tool-chain` by bundling or providing access to:

1. **MinGW-w64 headers** - C and C++ standard library headers compatible with GNU ABI
2. **MinGW-w64 runtime libraries** - libc++, libunwind, etc.
3. **Proper header search paths** - Configure clang to find GNU headers when `--target=x86_64-windows-gnu` is specified

### Reference Implementation

The `ziglang` Python package successfully provides this by bundling:
- Zig's bundled clang (version 20.1.2 in ziglang 0.15.1)
- Complete C/C++ standard library (libc++ for GNU target)
- All necessary headers and runtime libraries

When using `python -m ziglang c++ --target=x86_64-windows-gnu`, it works perfectly with GNU ABI and C++11 code.

## Test Scenarios

Please use these test cases to verify GNU ABI support:

### Test 1: Basic C++11 Standard Library Headers (GNU Target)

**Command:**
```bash
clang-tool-chain-cpp --target=x86_64-windows-gnu -std=gnu++11 -c test_gnu_target.cpp
```

**Test File (`test_gnu_target.cpp`):**
```cpp
#include <initializer_list>
#include <vector>
#include <string>

int main() {
    std::vector<int> v = {1, 2, 3};
    std::string s = "hello";
    return 0;
}
```

**Expected:** Compiles successfully with no errors
**Current Result:** `fatal error: 'initializer_list' file not found`

---

### Test 2: C++11 Code with MSVC Headers (MSVC Target - Should Fail)

**Command:**
```bash
clang-tool-chain-cpp -std=gnu++11 -c test_msvc_target.cpp
```

**Test File (`test_msvc_target.cpp`):**
```cpp
#include <type_traits>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    return 0;
}
```

**Expected:** Should fail because MSVC headers use C++14 features
**Current Result:** `error: 'auto' return without trailing return type; deduced return types are a C++14 extension`
**Note:** This test demonstrates why GNU target is needed - MSVC headers are incompatible with strict C++11 mode

---

### Test 3: Complete Compilation and Linking (GNU Target)

**Command:**
```bash
clang-tool-chain-cpp --target=x86_64-windows-gnu -std=gnu++11 -o test_program.exe test_full.cpp
```

**Test File (`test_full.cpp`):**
```cpp
#include <iostream>
#include <vector>
#include <string>

int main() {
    std::vector<std::string> messages = {"Hello", "World"};
    for (const auto& msg : messages) {
        std::cout << msg << " ";
    }
    std::cout << std::endl;
    return 0;
}
```

**Expected:** Compiles and links successfully, produces working executable
**Current Result:** Fails at compilation stage with missing headers

---

### Test 4: Verify Target Triple

**Command:**
```bash
clang-tool-chain-cpp --target=x86_64-windows-gnu -v test.cpp 2>&1 | grep "Target:"
```

**Expected Output:**
```
Target: x86_64-unknown-windows-gnu
```

**Current Result:** ✅ Works correctly - target triple is recognized

---

## Additional Context

### Why GNU ABI is Required for FastLED

1. **C++11 Compatibility**: FastLED uses strict C++11 mode (`-std=gnu++11`) with error flags:
   - `-Werror=c++14-extensions`
   - `-Werror=c++17-extensions`

2. **MSVC STL Incompatibility**: Microsoft's STL headers use C++14 features even when compiling in C++11 mode, which violates FastLED's strict compatibility requirements.

3. **Cross-Platform Consistency**: FastLED builds on Linux, macOS, and Windows. Using GNU ABI on Windows ensures consistent behavior across platforms.

4. **Arduino Compatibility**: FastLED is an Arduino library and many Arduino platforms use GCC/GNU toolchains. GNU ABI on Windows ensures ABI compatibility.

### Suggested Implementation Approaches

1. **Bundle MinGW-w64**: Include MinGW-w64 headers and libraries in the clang-tool-chain package (similar to how ziglang bundles libc++)

2. **Download on Demand**: Download MinGW-w64 components when first using `--target=x86_64-windows-gnu` (similar to how clang-tool-chain downloads the clang binary itself)

3. **Use LLVM's libc++**: Bundle LLVM's libc++ compiled for Windows GNU target instead of relying on MinGW

4. **Configuration File**: Provide a way to configure custom sysroot paths for users who have MinGW installed separately

### Success Criteria

✅ All four test scenarios above pass without errors
✅ `clang-tool-chain-cpp --target=x86_64-windows-gnu` can compile C++11 code with standard library headers
✅ Linking produces working executables that run on Windows
✅ No requirement for users to manually install MinGW or configure paths

## Current Workaround

Until GNU ABI support is added, projects must continue using the `ziglang` Python package:

```toml
dependencies = [
    "ziglang",  # Provides clang with GNU ABI support on Windows
]
```

## Version Information

- **clang-tool-chain version**: 1.0.0
- **Platform**: Windows 10/11 (MSYS_NT-10.0-19045)
- **Python**: 3.11+
- **Previously working**: ziglang 0.15.1 (bundles clang 20.1.2)

## References

- FastLED migration attempt: https://github.com/FastLED/FastLED
- ziglang package: https://pypi.org/project/ziglang/
- Zig's approach to cross-compilation: https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case
