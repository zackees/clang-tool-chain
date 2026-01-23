# LLVM Binary Utilities

This document covers the LLVM binary utilities provided by clang-tool-chain, including archive creation, symbol inspection, and binary manipulation.

## Overview

clang-tool-chain includes a comprehensive suite of LLVM binary utilities for working with object files, static libraries, and executables. These tools work across all platforms (Windows, macOS, Linux) and support multiple binary formats:

- **ELF** (Executable and Linkable Format) - Linux, BSD
- **PE/COFF** (Portable Executable) - Windows
- **Mach-O** (Mach Object) - macOS

**Available utilities:** 11 commands for archive creation, symbol inspection, disassembly, and binary manipulation.

---

## Archive Tools

### llvm-ar

Create and manage static libraries (archives).

**Command:** `clang-tool-chain-ar`

**Common Operations:**

```bash
# Create static library
clang-tool-chain-ar rcs libmylib.a obj1.o obj2.o obj3.o

# List archive contents
clang-tool-chain-ar t libmylib.a

# Extract all files from archive
clang-tool-chain-ar x libmylib.a

# Extract specific file
clang-tool-chain-ar x libmylib.a obj1.o

# Add/replace files in existing archive
clang-tool-chain-ar r libmylib.a new_obj.o

# Delete file from archive
clang-tool-chain-ar d libmylib.a unwanted.o

# Print verbose output
clang-tool-chain-ar rv libmylib.a obj1.o obj2.o
```

**Flag Reference:**

| Flag | Description |
|------|-------------|
| `r` | Replace or add files to archive |
| `c` | Create archive (suppress warning if it doesn't exist) |
| `s` | Create or update archive index (symbol table) |
| `t` | List archive contents |
| `x` | Extract files from archive |
| `d` | Delete files from archive |
| `v` | Verbose output |
| `u` | Update only newer files |

**Common Use Cases:**

1. **Creating static library for distribution:**
   ```bash
   # Compile source files
   clang-tool-chain-c -c math.c -o math.o
   clang-tool-chain-c -c string.c -o string.o

   # Create library
   clang-tool-chain-ar rcs libutils.a math.o string.o

   # Link against library
   clang-tool-chain-c main.c -L. -lutils -o program
   ```

2. **Inspecting library contents:**
   ```bash
   # List files in archive
   clang-tool-chain-ar t libutils.a

   # Verbose listing with metadata
   clang-tool-chain-ar tv libutils.a
   ```

### llvm-ranlib

Generate or update archive index (symbol table).

**Command:** `clang-tool-chain-ranlib`

**Usage:**

```bash
# Generate archive index
clang-tool-chain-ranlib libmylib.a

# Equivalent to: clang-tool-chain-ar s libmylib.a
```

**When to use:**

- After manually modifying archives (adding/removing object files)
- When archive doesn't have symbol table (`ar` without `s` flag)
- Ensures fast symbol lookup for linker

**Note:** Modern `llvm-ar rcs` creates index automatically, so `ranlib` is rarely needed.

---

## Symbol Inspection

### llvm-nm

List symbols in object files, archives, and executables.

**Command:** `clang-tool-chain-nm`

**Basic Usage:**

```bash
# List all symbols in object file
clang-tool-chain-nm program.o

# List symbols in executable
clang-tool-chain-nm program

# List symbols in static library
clang-tool-chain-nm libmylib.a
```

**Common Flags:**

```bash
# Demangle C++ symbols (human-readable)
clang-tool-chain-nm --demangle program

# Show undefined symbols only
clang-tool-chain-nm --undefined-only program

# Show defined symbols only
clang-tool-chain-nm --defined-only program

# Show external symbols only (no local/static)
clang-tool-chain-nm --extern-only program

# Sort symbols by address
clang-tool-chain-nm --numeric-sort program

# Show symbol sizes
clang-tool-chain-nm --size-sort program

# Print only symbol names (no type/address)
clang-tool-chain-nm --just-symbol-name program

# Dynamic symbols only (from .dynsym, useful for shared libs)
clang-tool-chain-nm --dynamic program.so
```

**Symbol Type Reference:**

| Type | Meaning |
|------|---------|
| `T` | Text (code) section - defined function |
| `t` | Local text section - static function |
| `D` | Initialized data section - global variable |
| `d` | Local data section - static variable |
| `B` | Uninitialized data (BSS) - global uninitialized |
| `b` | Local BSS - static uninitialized |
| `U` | Undefined - external symbol |
| `W` | Weak symbol |
| `V` | Weak object |
| `C` | Common symbol |

**Example Output:**

```
0000000000001234 T main
0000000000001456 T calculate
                 U printf
0000000000003000 D global_var
0000000000003008 b static_var
```

**Common Workflows:**

1. **Find undefined symbols (missing dependencies):**
   ```bash
   clang-tool-chain-nm --undefined-only program
   # Shows symbols program needs but doesn't have
   ```

2. **Check what symbols a library provides:**
   ```bash
   clang-tool-chain-nm --defined-only --extern-only libmylib.a
   # Shows public API of library
   ```

3. **Debug C++ name mangling:**
   ```bash
   # Raw mangled names
   clang-tool-chain-nm program

   # Human-readable names
   clang-tool-chain-nm --demangle program
   ```

### llvm-readelf

Read ELF file headers and sections (Linux).

**Command:** `clang-tool-chain-readelf`

**Usage:**

```bash
# Show ELF header
clang-tool-chain-readelf -h program

# Show program headers (segments)
clang-tool-chain-readelf -l program

# Show section headers
clang-tool-chain-readelf -S program

# Show symbol table
clang-tool-chain-readelf -s program

# Show dynamic section (shared libraries)
clang-tool-chain-readelf -d program.so

# Show all information
clang-tool-chain-readelf -a program
```

**Common Use Cases:**

1. **Check executable type:**
   ```bash
   clang-tool-chain-readelf -h program | grep Type
   # Output: Type: EXEC (Executable file) or DYN (Shared object)
   ```

2. **Inspect shared library dependencies:**
   ```bash
   clang-tool-chain-readelf -d libmylib.so | grep NEEDED
   # Shows required shared libraries
   ```

3. **View section sizes:**
   ```bash
   clang-tool-chain-readelf -S program | grep -E '\.text|\.data|\.bss'
   # Shows code/data/uninitialized sizes
   ```

**Platform Notes:**

- **Linux:** Full ELF support ✅
- **Windows:** Limited (PE/COFF format, use `llvm-objdump` instead)
- **macOS:** Limited (Mach-O format, use `llvm-objdump` instead)

---

## Binary Manipulation

### llvm-objcopy

Copy and modify object files (change sections, strip symbols, extract data).

**Command:** `clang-tool-chain-objcopy`

**Common Operations:**

```bash
# Strip debug symbols (same as llvm-strip)
clang-tool-chain-objcopy --strip-debug program program.nodebug

# Strip all symbols
clang-tool-chain-objcopy --strip-all program program.stripped

# Remove specific section
clang-tool-chain-objcopy --remove-section=.comment program program.nocomment

# Extract specific section to file
clang-tool-chain-objcopy --only-section=.data --output-target=binary program data.bin

# Add new section from file
clang-tool-chain-objcopy --add-section=.mydata=data.bin program program.new
```

**Advanced Use Cases:**

1. **Extract firmware/data from ELF:**
   ```bash
   # Extract .text section as raw binary
   clang-tool-chain-objcopy --only-section=.text --output-target=binary firmware.elf firmware.bin
   ```

2. **Embed data file in executable:**
   ```bash
   # Embed config.json as .config section
   clang-tool-chain-objcopy --add-section=.config=config.json program program.new
   ```

### llvm-strip

Remove symbols and debug information from binaries.

**Command:** `clang-tool-chain-strip`

**Usage:**

```bash
# Strip debug symbols (keep function names)
clang-tool-chain-strip --strip-debug program -o program.nodebug

# Strip all symbols (maximum size reduction)
clang-tool-chain-strip --strip-all program -o program.stripped

# Strip in-place (overwrite original)
clang-tool-chain-strip program

# Keep specific symbols
clang-tool-chain-strip --keep-symbol=main --keep-symbol=init program
```

**Size Comparison:**

```bash
# Before stripping (with debug info)
-rwxr-xr-x 1 user user 1.2M program

# After --strip-debug (remove DWARF debug info)
-rwxr-xr-x 1 user user 450K program.nodebug

# After --strip-all (remove all symbols)
-rwxr-xr-x 1 user user 380K program.stripped
```

**When to Strip:**

- **Release builds:** Reduce executable size for distribution
- **Embedded systems:** Fit firmware into limited flash/ROM
- **Obfuscation:** Remove symbol names (mild security through obscurity)

**When NOT to Strip:**

- **Debug builds:** Need symbols for debugger (gdb, lldb)
- **Profiling:** Tools need symbols to show function names
- **Stack traces:** Crash reports need symbols for useful backtraces

---

## Disassembly and Inspection

### llvm-objdump

Disassemble and inspect object files, archives, and executables.

**Command:** `clang-tool-chain-objdump`

**Common Operations:**

```bash
# Disassemble all code sections
clang-tool-chain-objdump -d program

# Disassemble specific function
clang-tool-chain-objdump -d --disassemble-symbols=main program

# Show all headers
clang-tool-chain-objdump -x program

# Show section headers
clang-tool-chain-objdump -h program

# Show symbol table
clang-tool-chain-objdump -t program

# Show relocations
clang-tool-chain-objdump -r program.o

# Disassemble with source code interleaved
clang-tool-chain-objdump -d -S program

# Show private headers (PE/COFF, Mach-O, ELF)
clang-tool-chain-objdump -p program
```

**Disassembly Formats:**

```bash
# Intel syntax (default on most platforms)
clang-tool-chain-objdump -d program

# AT&T syntax
clang-tool-chain-objdump -d --x86-asm-syntax=att program

# With line numbers
clang-tool-chain-objdump -d -l program

# With raw bytes
clang-tool-chain-objdump -d --show-raw-insn program
```

**Common Workflows:**

1. **Inspect compiled code:**
   ```bash
   # Compile with debug info
   clang-tool-chain-cpp -g -O2 main.cpp -o program

   # Disassemble with source
   clang-tool-chain-objdump -d -S program | less
   ```

2. **Check optimization:**
   ```bash
   # Compare -O0 vs -O3
   clang-tool-chain-objdump -d program_O0 > O0.asm
   clang-tool-chain-objdump -d program_O3 > O3.asm
   diff O0.asm O3.asm
   ```

3. **Verify symbol exports in DLL/shared library:**
   ```bash
   # Windows DLL
   clang-tool-chain-objdump -p mylib.dll | grep "Export Address Table"

   # Linux shared library
   clang-tool-chain-objdump -T libmylib.so
   ```

### llvm-dis

Disassemble LLVM bitcode (.bc) to LLVM IR (.ll).

**Command:** `clang-tool-chain-dis`

**Usage:**

```bash
# Compile to LLVM bitcode
clang-tool-chain-c -c -emit-llvm program.c -o program.bc

# Disassemble bitcode to IR
clang-tool-chain-dis program.bc -o program.ll

# View LLVM IR
cat program.ll
```

**When to Use:**

- Inspect LLVM optimizations
- Debug compiler behavior
- Learn LLVM intermediate representation
- Verify code generation

---

## Linker

### lld

LLVM linker (ELF, PE/COFF, Mach-O).

**Command:** `clang-tool-chain-ld`

**Usage:**

```bash
# Link object files
clang-tool-chain-ld obj1.o obj2.o -o program

# Create shared library (Linux)
clang-tool-chain-ld -shared obj1.o obj2.o -o libmylib.so

# Create DLL (Windows)
clang-tool-chain-ld -shared obj1.o obj2.o -o mylib.dll

# Link with library search path
clang-tool-chain-ld obj1.o -L/usr/local/lib -lmylib -o program
```

**Platform-Specific Variants:**

- **Linux:** `lld` uses ELF variant (`ld.lld`)
- **Windows:** `lld-link` (MSVC-compatible linker for PE/COFF)
- **macOS:** System linker (ld64) currently used (lld support pending)

**Note:** For most use cases, use the compiler (`clang-tool-chain-c` / `clang-tool-chain-cpp`) to invoke the linker automatically. Direct `clang-tool-chain-ld` usage is for advanced workflows.

### wasm-ld

WebAssembly linker (included with Emscripten).

**Usage:**

```bash
# Link WebAssembly object files
wasm-ld obj1.o obj2.o -o program.wasm

# Typically invoked via emcc/em++, not directly
clang-tool-chain-emcc program.c -o program.js
```

---

## Platform-Specific Notes

### ELF Format (Linux)

**Best supported format** - All tools have full ELF support.

**Common ELF sections:**
- `.text` - Code
- `.data` - Initialized data
- `.bss` - Uninitialized data
- `.rodata` - Read-only data (constants, strings)
- `.symtab` - Symbol table
- `.strtab` - String table
- `.debug_*` - DWARF debug info

**Tools with special ELF features:**
- `llvm-readelf` - Full ELF header inspection
- `llvm-objdump -p` - ELF program headers
- `llvm-objcopy` - ELF section manipulation

### PE/COFF Format (Windows)

**Well supported** - Most tools work with PE/COFF.

**Common PE sections:**
- `.text` - Code
- `.data` - Initialized data
- `.rdata` - Read-only data
- `.bss` - Uninitialized data
- `.idata` - Import table (DLL dependencies)
- `.edata` - Export table (DLL exports)

**Windows-specific tools:**
- `llvm-objdump -p` - Show import/export tables
- `lld-link` - MSVC-compatible linker

**Limitations:**
- `llvm-readelf` - Limited (designed for ELF)

### Mach-O Format (macOS)

**Supported** - Most tools work with Mach-O.

**Common Mach-O sections:**
- `__TEXT,__text` - Code
- `__DATA,__data` - Initialized data
- `__DATA,__bss` - Uninitialized data
- `__TEXT,__cstring` - C string literals

**macOS-specific notes:**
- `llvm-objdump -p` - Mach-O load commands
- System linker (ld64) currently used instead of lld

**Limitations:**
- `llvm-readelf` - Limited (designed for ELF)

---

## Common Workflows

### Creating and Using Static Libraries

```bash
# 1. Compile source files to object files
clang-tool-chain-c -c math.c -o math.o
clang-tool-chain-c -c string.c -o string.o
clang-tool-chain-c -c file.c -o file.o

# 2. Create static library
clang-tool-chain-ar rcs libutils.a math.o string.o file.o

# 3. Verify library contents
clang-tool-chain-ar t libutils.a
# Output: math.o string.o file.o

# 4. Check exported symbols
clang-tool-chain-nm --defined-only --extern-only libutils.a

# 5. Link program against library
clang-tool-chain-c main.c -L. -lutils -o program

# 6. Verify program dependencies
clang-tool-chain-nm --undefined-only program
```

### Inspecting Binary Dependencies

```bash
# Linux - Check shared library dependencies
clang-tool-chain-objdump -p program | grep NEEDED
# Or: clang-tool-chain-readelf -d program | grep NEEDED

# Windows - Check DLL dependencies
clang-tool-chain-objdump -p program.exe | grep "DLL Name"

# macOS - Check dylib dependencies
clang-tool-chain-objdump -p program | grep "cmd LC_LOAD_DYLIB"
```

### Stripping Debug Symbols for Release

```bash
# Build with debug info
clang-tool-chain-cpp -g -O2 program.cpp -o program

# Check size
ls -lh program
# -rwxr-xr-x 1 user user 1.2M program

# Strip debug symbols
clang-tool-chain-strip --strip-debug program -o program.release

# Check new size
ls -lh program.release
# -rwxr-xr-x 1 user user 450K program.release

# Verify symbols are stripped
clang-tool-chain-nm program | grep debug
# (shows debug symbols)

clang-tool-chain-nm program.release | grep debug
# (no output - debug symbols removed)
```

### Cross-Platform Binary Inspection

```bash
# Inspect any binary format (ELF, PE, Mach-O)
clang-tool-chain-objdump -h program      # Section headers
clang-tool-chain-objdump -t program      # Symbol table
clang-tool-chain-objdump -p program      # Private headers
clang-tool-chain-objdump -d program      # Disassembly

# Works on:
# - Linux ELF binaries
# - Windows PE/COFF executables and DLLs
# - macOS Mach-O executables and dylibs
```

---

## Troubleshooting

### "Unknown file format" Error

**Problem:** Tool doesn't recognize binary format.

**Solution:**
```bash
# Check file type
file program

# Supported formats:
# - ELF (Linux)
# - PE/COFF (Windows .exe, .dll)
# - Mach-O (macOS)
# - Archive (.a, .lib)
```

### Empty Symbol Table

**Problem:** `llvm-nm` shows no symbols.

**Cause:** Binary was stripped with `--strip-all`.

**Solution:**
- Use original unstripped binary
- Rebuild with debug info: `-g` flag
- Use `--strip-debug` instead of `--strip-all` for releases

### "llvm-readelf: error: Not an ELF file"

**Problem:** Using `llvm-readelf` on non-ELF binary.

**Solution:**
- Use `llvm-objdump -p` instead (works on all formats)
- `llvm-readelf` is ELF-specific (Linux)

### Symbol Name Mangling (C++)

**Problem:** C++ symbols show mangled names like `_ZN3foo3barEv`.

**Solution:**
```bash
# Use --demangle flag for human-readable names
clang-tool-chain-nm --demangle program

# Output: foo::bar() instead of _ZN3foo3barEv
```

---

## Command Reference Quick Summary

| Command | Tool | Description |
|---------|------|-------------|
| `clang-tool-chain-ar` | `llvm-ar` | Archive/library creator |
| `clang-tool-chain-ranlib` | `llvm-ranlib` | Archive index generator |
| `clang-tool-chain-nm` | `llvm-nm` | Symbol table viewer |
| `clang-tool-chain-readelf` | `llvm-readelf` | ELF file reader (Linux) |
| `clang-tool-chain-objcopy` | `llvm-objcopy` | Object file copier/modifier |
| `clang-tool-chain-strip` | `llvm-strip` | Symbol stripper |
| `clang-tool-chain-objdump` | `llvm-objdump` | Object file dumper/disassembler |
| `clang-tool-chain-dis` | `llvm-dis` | LLVM bitcode disassembler |
| `clang-tool-chain-ld` | `lld` / `lld-link` | LLVM linker |
| `clang-tool-chain-as` | `llvm-as` | LLVM assembler |
| `clang-tool-chain-wasm-ld` | `wasm-ld` | WebAssembly linker |

---

## See Also

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Compiler wrappers and compilation
- [Format & Lint](FORMAT_LINT.md) - clang-format and clang-tidy
- [LLVM Documentation](https://llvm.org/docs/) - Official LLVM docs
