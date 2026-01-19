# Inlined Build Directives Examples

This directory contains example C/C++ files demonstrating the **fully implemented** inlined build directive system.

## ✅ Status: IMPLEMENTED

**Directive parsing is now fully working!** You can compile these examples without specifying any flags.

## Quick Start

```bash
# All of these work automatically - directives are parsed from the source file!
clang-tool-chain-cpp pthread_hello.cpp -o pthread_hello
clang-tool-chain-cpp math_intensive.cpp -o math_intensive
clang-tool-chain-cpp cross_platform.cpp -o cross_platform
clang-tool-chain-c simple_c.c -o simple_c

# Or use build-run for compile and execute in one step:
clang-tool-chain-build-run pthread_hello.cpp
clang-tool-chain-build-run math_intensive.cpp
```

## Concept

Inlined directives allow C/C++ source files to be self-contained by embedding build configuration directly in comments at the top of the file. This is similar to hashbangs in shell scripts but for C/C++ compilation.

**No more remembering `-lpthread` or `-std=c++17`!** Just put the directives in your source file.

## Example Files

### `pthread_hello.cpp`
Basic pthread example showing:
- `@link: pthread` - Link against pthread library
- `@std: c++17` - Use C++17 standard

### `math_intensive.cpp`
Multi-threaded math computation showing:
- `@link: [pthread, m]` - Link multiple libraries (list syntax)
- `@cflags: -O2 -march=native` - Compiler optimization flags
- `@std: c++17` - C++ standard version

### `cross_platform.cpp`
Platform-specific configuration showing:
- `@platform: linux` - Platform-conditional directives
- `@platform: windows` - Windows-specific linking (ws2_32)
- `@platform: darwin` - macOS-specific frameworks

### `simple_c.c`
C language example showing:
- `@cflags: -O2 -Wall` - Compiler flags for C

## Syntax Quick Reference

```cpp
// @link: library              // Link single library
// @link: [lib1, lib2, lib3]   // Link multiple libraries
// @cflags: -O2 -Wall          // Compiler flags
// @ldflags: -rpath /opt/lib   // Linker flags
// @std: c++17                 // C++ standard version
// @include: /path/to/headers  // Include path
// @pkg-config: openssl        // Use pkg-config (planned)

// Platform-specific:
// @platform: linux
//   @link: pthread
// @platform: windows
//   @link: ws2_32
// @platform: darwin
//   @ldflags: -framework CoreFoundation
```

## How It Works

1. When you compile with `clang-tool-chain-cpp` or `clang-tool-chain-c`, the tool scans the top of the source file for directive comments
2. Directives are parsed and converted to compiler/linker flags
3. Platform-specific directives are filtered for the current platform
4. Final compilation command is assembled and executed automatically

## Supported Commands

Directives are automatically parsed by these commands:

| Command | Directive Support |
|---------|------------------|
| `clang-tool-chain-cpp` | ✅ Yes |
| `clang-tool-chain-c` | ✅ Yes |
| `clang-tool-chain-cpp-msvc` | ✅ Yes |
| `clang-tool-chain-c-msvc` | ✅ Yes |
| `clang-tool-chain-build` | ✅ Yes |
| `clang-tool-chain-build-run` | ✅ Yes |

## Environment Variables

- `CLANG_TOOL_CHAIN_NO_DIRECTIVES=1` - Disable directive parsing
- `CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1` - Show parsed directives (debug)

## Example: Verbose Mode

```bash
# See what directives are being applied
CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1 clang-tool-chain-cpp pthread_hello.cpp -o pthread_hello
# Output: Directive args from source files: ['-std=c++17', '-lpthread']
```

## Platform Behavior

| Platform | pthread_hello | cross_platform |
|----------|--------------|----------------|
| Windows (GNU ABI) | Uses MinGW pthread | Links ws2_32 |
| Linux | Links -lpthread | Links -lpthread |
| macOS | Links -lpthread | Links -lpthread + frameworks |

## See Also

- [Directive Documentation](../../docs/DIRECTIVES.md) - Full directive reference
- [Original Proposal](../../docs/proposals/INLINED_DIRECTIVES.md) - Design document
- [FastLED @filter directives](https://github.com/FastLED/FastLED) - Inspiration for the syntax
