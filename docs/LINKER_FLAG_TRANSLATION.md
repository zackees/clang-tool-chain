<!-- AGENT: Read this file when working on linker flag translation, GNU-to-MSVC mapping, or cross-platform linking -->

# Linker Flag Translation

## Overview

clang-tool-chain automatically translates GNU ld-style linker flags to platform-native equivalents, enabling single-flag syntax across all platforms. This eliminates the need for platform-specific conditionals in build scripts and makefiles.

**Key Benefit:** Write GNU ld flags once, and they work everywhere — clang-tool-chain handles the translation automatically.

## Supported Platforms

### Windows: GNU ld → MSVC/lld-link

On Windows, clang-tool-chain uses LLVM's `lld-link` (MSVC-compatible linker). GNU ld flags are automatically translated to their MSVC equivalents.

**Translation happens when:**
- Using clang-tool-chain compilers (`clang-tool-chain-cc`, `clang-tool-chain-cpp`)
- Linking operations (not compile-only with `-c`)
- Not disabled via `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1`

### macOS: GNU ld → ld64.lld

On macOS, clang-tool-chain uses LLVM's `ld64.lld` (Mach-O linker). GNU ld flags are translated to ld64 equivalents.

**Translation happens when:**
- Using clang-tool-chain compilers
- `-fuse-ld=lld` is injected or user-specified
- Not disabled via `CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1`

### Linux: GNU ld (pass-through)

On Linux, clang-tool-chain uses LLVM's `ld.lld` (ELF linker), which natively understands GNU ld syntax. No translation is needed — flags pass through unchanged.

## Flag Mapping Reference

### Windows (GNU ld → MSVC/lld-link)

| GNU ld Flag | MSVC Equivalent | Purpose |
|-------------|-----------------|---------|
| `--allow-shlib-undefined` | `/FORCE:UNRESOLVED` | Allow undefined symbols in DLLs (useful for runtime-resolved symbols) |
| `--allow-multiple-definition` | `/FORCE:MULTIPLE` | Allow multiply-defined symbols (linker picks first) |
| `--no-undefined` | *(removed)* | Disallow undefined symbols — MSVC default behavior, no flag needed |
| `--gc-sections` | `/OPT:REF` | Remove unreferenced code/data (dead code elimination) |
| `--no-gc-sections` | `/OPT:NOREF` | Keep all code/data sections |
| `-shared` | `/DLL` | Build shared library (DLL on Windows) |

**Note:** MSVC-style flags (e.g., `/FORCE:UNRESOLVED`) pass through unchanged for backward compatibility.

### macOS (GNU ld → ld64.lld)

| GNU ld Flag | ld64 Equivalent | Purpose |
|-------------|-----------------|---------|
| `--no-undefined` | `-undefined error` | Disallow undefined symbols (strict linking) |
| `--fatal-warnings` | `-fatal_warnings` | Treat linker warnings as errors |
| `--allow-shlib-undefined` | *(removed)* | No-op on macOS — ld64 allows undefined symbols in dylibs by default |

**Note:** ld64-style flags (e.g., `-undefined error`) pass through unchanged if user-specified.

### Linux (GNU ld → ld.lld)

No translation needed — `ld.lld` on Linux natively understands GNU ld syntax.

## Usage Examples

### Cross-Platform DLL/Shared Library

**Before (platform-specific):**
```makefile
# Requires platform conditionals
ifeq ($(OS),Windows_NT)
  LINK_FLAGS = -shared -Wl,/FORCE:UNRESOLVED
else
  LINK_FLAGS = -shared -Wl,--allow-shlib-undefined
endif
```

**After (cross-platform):**
```makefile
# Works on all platforms!
LINK_FLAGS = -shared -Wl,--allow-shlib-undefined
```

On Windows, clang-tool-chain automatically translates:
- `-shared` → `-Wl,/DLL`
- `--allow-shlib-undefined` → `/FORCE:UNRESOLVED`

On macOS and Linux, the flags work natively or are translated as needed.

### Dead Code Elimination

**Before (platform-specific):**
```bash
# Windows
clang++ -O2 main.cpp -Wl,/OPT:REF -o main.exe

# Linux/macOS
clang++ -O2 main.cpp -Wl,--gc-sections -o main
```

**After (cross-platform):**
```bash
# Works everywhere!
clang-tool-chain-cpp -O2 main.cpp -Wl,--gc-sections -o main
```

### Multiple Flags

**Cross-platform build command:**
```bash
clang-tool-chain-cpp \
  -shared \
  -Wl,--allow-shlib-undefined,--gc-sections \
  plugin.cpp \
  -o plugin.dll  # Or plugin.so / plugin.dylib
```

**Windows translation:**
- `-shared` → `-Wl,/DLL`
- `--allow-shlib-undefined` → `/FORCE:UNRESOLVED`
- `--gc-sections` → `/OPT:REF`

**Final Windows linker flags:**
```
-Wl,/DLL,/FORCE:UNRESOLVED,/OPT:REF
```

## Translation Warnings

When flags are translated or removed, clang-tool-chain emits a note to stderr:

```
clang-tool-chain: note: translated GNU linker flags to MSVC equivalents:
  --allow-shlib-undefined → /FORCE:UNRESOLVED
  --gc-sections → /OPT:REF
(disable with CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1)
```

This helps you verify the translation is correct. Suppress these notes if desired (see Environment Variables below).

## Environment Variables

### Suppress Translation Warnings

Control translation warning output using hierarchical suppression:

| Environment Variable | Scope | Effect |
|----------------------|-------|--------|
| `CLANG_TOOL_CHAIN_NO_AUTO=1` | **Global master** | Suppress ALL automatic features and notes |
| `CLANG_TOOL_CHAIN_NO_LINKER_NOTE=1` | **Category master** | Suppress all linker-related notes |
| `CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1` | Specific | Suppress only GNU→MSVC/ld64 translation notes |

**Example:**
```bash
# Suppress translation warnings
export CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1
clang-tool-chain-cpp -shared -Wl,--allow-shlib-undefined test.cpp -o test.dll
# No warning emitted
```

### Disable Translation Entirely

To use the system linker instead of LLD (disables automatic translation):

```bash
export CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1
clang-tool-chain-cpp main.cpp -o main
# Uses system linker (ld64 on macOS, GNU ld on Linux, MSVC link.exe on Windows)
# No flag translation occurs
```

**Warning:** Disabling LLD may break cross-platform builds if you rely on GNU flags working on all platforms.

## Implementation Details

### Translation Pipeline

1. **Compile-only detection**: Skip translation if `-c` flag present (no linking)
2. **Platform detection**: Determine target platform (win/darwin/linux)
3. **User linker check**: Skip if user specified `-fuse-ld=` (except on macOS for LLD)
4. **Flag translation**: Apply platform-specific translation rules
5. **Linker injection**: Add `-fuse-ld=lld` (except Windows, handled separately)

### Translation Functions

- **Windows:** `_translate_linker_flags_for_windows_lld()` in `src/clang_tool_chain/linker/lld.py`
- **macOS:** `_translate_linker_flags_for_macos_lld()` in `src/clang_tool_chain/linker/lld.py`
- **Linux:** No translation needed (GNU ld native)

### Flag Processing

Translation handles both:
- **Direct flags:** `--allow-shlib-undefined` (standalone)
- **Linker flags:** `-Wl,--allow-shlib-undefined` (comma-separated)
- **Mixed flags:** `-Wl,--gc-sections,-rpath,/lib` (translated + passthrough)

### Backward Compatibility

MSVC-style flags on Windows pass through unchanged:
```bash
# Both work on Windows
clang-tool-chain-cpp -Wl,--allow-shlib-undefined test.cpp -o test.dll  # Translated
clang-tool-chain-cpp -Wl,/FORCE:UNRESOLVED test.cpp -o test.dll        # Pass-through
```

This allows gradual migration and mixing of flag styles.

## Testing

### Unit Tests

Run cross-platform unit tests (all platforms):
```bash
uv run pytest tests/test_windows_lld_flags.py::TestWindowsLLDFlagTranslation -v
uv run pytest tests/test_macos_lld_flags.py::TestMacOSLLDFlagTranslation -v
```

### Integration Tests

Run platform-specific integration tests:

**Windows only:**
```bash
uv run pytest tests/test_windows_lld_flags.py::TestWindowsLLDFlagIntegration -v
```

**macOS only:**
```bash
uv run pytest tests/test_macos_lld_flags.py::TestMacOSLLDIntegration -v
```

### Verify Translation with Verbose Mode

Use `-v` to see actual linker invocation:
```bash
clang-tool-chain-cpp -v -shared -Wl,--allow-shlib-undefined test.cpp -o test.dll
```

**Expected output (Windows):**
```
clang-tool-chain: note: translated GNU linker flags to MSVC equivalents:
  --allow-shlib-undefined → /FORCE:UNRESOLVED
(disable with CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1)

...linker invocation...
lld-link /DLL /OUT:test.dll /FORCE:UNRESOLVED ...
```

## Common Issues

### Issue: GNU flags not working on Windows

**Symptom:** Linker errors when using GNU flags like `--allow-shlib-undefined`

**Cause:** Using system linker instead of clang-tool-chain wrappers

**Solution:** Use `clang-tool-chain-cpp` instead of `clang++`:
```bash
# Wrong (no translation)
clang++ -Wl,--allow-shlib-undefined test.cpp -o test.dll  # Error!

# Correct (automatic translation)
clang-tool-chain-cpp -Wl,--allow-shlib-undefined test.cpp -o test.dll  # Works!
```

### Issue: Translation warnings cluttering output

**Symptom:** Too many translation notes in build logs

**Solution:** Suppress warnings after verifying translation is correct:
```bash
export CLANG_TOOL_CHAIN_NO_LINKER_COMPAT_NOTE=1
```

Or suppress all linker notes:
```bash
export CLANG_TOOL_CHAIN_NO_LINKER_NOTE=1
```

### Issue: Need to use MSVC-specific flags

**Symptom:** Advanced MSVC linker flags not available via GNU equivalents

**Solution:** MSVC flags pass through unchanged — you can mix both styles:
```bash
# Mix GNU and MSVC flags
clang-tool-chain-cpp \
  -shared \
  -Wl,--allow-shlib-undefined \
  -Wl,/MANIFESTINPUT:custom.manifest \
  test.cpp -o test.dll
```

## Related Documentation

- **[Clang/LLVM](CLANG_LLVM.md)** - LLD linker overview, platform-specific behavior
- **[Environment Variables](ENVIRONMENT_VARIABLES.md)** - Complete list of env vars
- **[Testing Guide](TESTING.md)** - Running linker translation tests

## See Also

- **LLVM LLD Documentation:** https://lld.llvm.org/
- **MSVC Linker Reference:** https://docs.microsoft.com/en-us/cpp/build/reference/linker-options
- **GNU ld Manual:** https://sourceware.org/binutils/docs/ld/
