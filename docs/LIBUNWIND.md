# Bundled libunwind (Linux)

**Self-contained stack unwinding - no system packages required**

On Linux, clang-tool-chain bundles libunwind headers and shared libraries, providing a complete solution for stack unwinding, backtracing, and crash analysis without requiring system packages like `libunwind-dev`.

## Overview

libunwind is a portable C library that provides a C API to determine the call-chain of a program. It's essential for:
- **Stack traces and backtraces** - Debugging, profiling, and crash analysis
- **Exception handling** - C++ exception unwinding (works alongside libc++abi)
- **Profiling tools** - Performance analysis and sampling profilers
- **Crash reporters** - Generating meaningful crash reports with function names

## What's Bundled

clang-tool-chain includes the complete libunwind distribution from Ubuntu 22.04 (Jammy):

| Component | Files | Size | Purpose |
|-----------|-------|------|---------|
| **Headers** | `libunwind.h` | ~5 KB | Main API header |
| | `libunwind-common.h` | ~3 KB | Common definitions |
| | `libunwind-x86_64.h` / `libunwind-aarch64.h` | ~5 KB | Architecture-specific |
| | `libunwind-dynamic.h` | ~2 KB | Dynamic unwinding API |
| | `libunwind-ptrace.h` | ~2 KB | ptrace-based unwinding |
| | `unwind.h` | ~3 KB | GCC-compatible unwind API |
| **Libraries** | `libunwind.so.8`, `libunwind.so.8.0.1` | ~150 KB | Main shared library |
| | `libunwind-x86_64.so.8.*` / `libunwind-aarch64.so.8.*` | ~150 KB | Architecture-specific |

**Total size:** ~320 KB (headers + libraries)

## How Automatic Injection Works

When you compile with `clang-tool-chain-c` or `clang-tool-chain-cpp` on Linux, the `LinuxUnwindTransformer` automatically injects the necessary compiler and linker flags:

### Flags Injected

```bash
# What clang-tool-chain-cpp actually passes to clang:
clang++ \
    -I/home/user/.clang-tool-chain/clang/linux/x86_64/include \    # Headers
    -L/home/user/.clang-tool-chain/clang/linux/x86_64/lib \        # Libraries
    -Wl,-rpath,/home/user/.clang-tool-chain/clang/linux/x86_64/lib # Runtime path
    your_code.cpp -lunwind -o your_program
```

### What This Means

1. **`-I` flag** - The compiler finds `libunwind.h` without system packages
2. **`-L` flag** - The linker finds `libunwind.so` without system packages
3. **`-rpath` flag** - The executable finds `libunwind.so` at runtime without `LD_LIBRARY_PATH`

This makes your binaries **self-contained** - they work on any Linux system without requiring libunwind to be installed.

## Usage Examples

### Basic Backtrace

```c
// backtrace.c - Print a stack trace
#define UNW_LOCAL_ONLY
#include <libunwind.h>
#include <stdio.h>

void print_backtrace() {
    unw_cursor_t cursor;
    unw_context_t context;

    // Get current context
    unw_getcontext(&context);
    unw_init_local(&cursor, &context);

    // Walk the stack
    int frame = 0;
    while (unw_step(&cursor) > 0) {
        unw_word_t pc, offset;
        char name[256];

        unw_get_reg(&cursor, UNW_REG_IP, &pc);
        if (pc == 0) break;

        name[0] = '\0';
        unw_get_proc_name(&cursor, name, sizeof(name), &offset);

        printf("#%d 0x%lx %s+0x%lx\n",
               frame++, (unsigned long)pc,
               name[0] ? name : "??",
               (unsigned long)offset);
    }
}

void level3() { print_backtrace(); }
void level2() { level3(); }
void level1() { level2(); }

int main() {
    level1();
    return 0;
}
```

```bash
# Compile with debug info for best symbol resolution
clang-tool-chain-c -g -O0 -fno-omit-frame-pointer backtrace.c -lunwind -o backtrace

# Run - no LD_LIBRARY_PATH needed!
./backtrace
```

**Output:**
```
#0 0x401234 print_backtrace+0x45
#1 0x4012a0 level3+0x10
#2 0x4012b5 level2+0x10
#3 0x4012ca level1+0x10
#4 0x4012df main+0x10
#5 0x7f... __libc_start_main+0xf3
```

### C++ with Exception Handling

```cpp
// exception_trace.cpp - Backtrace inside catch block
#define UNW_LOCAL_ONLY
#include <libunwind.h>
#include <iostream>
#include <stdexcept>

int count_frames() {
    unw_cursor_t cursor;
    unw_context_t context;
    int count = 0;

    if (unw_getcontext(&context) != 0) return -1;
    if (unw_init_local(&cursor, &context) != 0) return -1;

    while (unw_step(&cursor) > 0 && count < 50) {
        count++;
    }
    return count;
}

void throw_and_catch() {
    try {
        throw std::runtime_error("test exception");
    } catch (const std::exception& e) {
        std::cout << "Caught: " << e.what() << std::endl;
        std::cout << "Stack depth: " << count_frames() << " frames" << std::endl;
    }
}

int main() {
    throw_and_catch();
    return 0;
}
```

```bash
clang-tool-chain-cpp -g exception_trace.cpp -lunwind -o exception_trace
./exception_trace
```

### Signal Handler Backtrace (Crash Handler)

```c
// crash_handler.c - Print backtrace on SIGSEGV
#define UNW_LOCAL_ONLY
#include <libunwind.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>

void crash_handler(int sig) {
    fprintf(stderr, "\n=== CRASH: Signal %d ===\n", sig);

    unw_cursor_t cursor;
    unw_context_t context;
    unw_getcontext(&context);
    unw_init_local(&cursor, &context);

    int frame = 0;
    while (unw_step(&cursor) > 0 && frame < 20) {
        unw_word_t pc, offset;
        char name[256];

        unw_get_reg(&cursor, UNW_REG_IP, &pc);
        name[0] = '\0';
        unw_get_proc_name(&cursor, name, sizeof(name), &offset);

        fprintf(stderr, "#%d 0x%lx %s+0x%lx\n",
                frame++, (unsigned long)pc,
                name[0] ? name : "??",
                (unsigned long)offset);
    }

    exit(1);
}

void cause_crash() {
    int* p = NULL;
    *p = 42;  // SIGSEGV
}

int main() {
    signal(SIGSEGV, crash_handler);
    cause_crash();
    return 0;
}
```

```bash
clang-tool-chain-c -g crash_handler.c -lunwind -o crash_handler
./crash_handler
```

## Integration with ASAN

libunwind works seamlessly with Address Sanitizer. When both are used together:

```bash
# ASAN + libunwind for comprehensive debugging
clang-tool-chain-cpp -g -fsanitize=address backtrace.cpp -lunwind -o debug_build

# Deploy both ASAN runtime and libunwind
clang-tool-chain-cpp -g -fsanitize=address backtrace.cpp -lunwind -o debug_build --deploy-dependencies
```

The `--deploy-dependencies` flag will copy both `libclang_rt.asan.so` and `libunwind.so` to your output directory.

## API Reference

### Core Functions

| Function | Description |
|----------|-------------|
| `unw_getcontext(&context)` | Capture current execution context |
| `unw_init_local(&cursor, &context)` | Initialize cursor for local unwinding |
| `unw_step(&cursor)` | Move to next (caller) frame; returns >0 on success, 0 at end, <0 on error |
| `unw_get_reg(&cursor, reg, &value)` | Get register value (e.g., `UNW_REG_IP` for instruction pointer) |
| `unw_get_proc_name(&cursor, buf, len, &offset)` | Get function name and offset |

### Common Registers

| Register | Description |
|----------|-------------|
| `UNW_REG_IP` | Instruction pointer (program counter) |
| `UNW_REG_SP` | Stack pointer |
| `UNW_X86_64_RAX` ... `UNW_X86_64_R15` | x86_64 general purpose registers |
| `UNW_AARCH64_X0` ... `UNW_AARCH64_X30` | ARM64 general purpose registers |

### Important Defines

```c
#define UNW_LOCAL_ONLY  // Define before including libunwind.h for local-only unwinding
                        // This reduces code size and improves performance
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND=1` | Disable bundled libunwind, use system version |
| `CLANG_TOOL_CHAIN_NO_AUTO=1` | Disable all automatic flag injection (includes libunwind) |

### Disabling Bundled libunwind

If you need to use the system libunwind instead of the bundled version:

```bash
# Use system libunwind
export CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND=1
clang-tool-chain-cpp backtrace.cpp -lunwind -o backtrace

# Requires: apt-get install libunwind-dev
```

## Platform Support

| Platform | Headers | Libraries | Automatic Injection | Status |
|----------|---------|-----------|---------------------|--------|
| Linux x86_64 | ✅ Bundled | ✅ Bundled | ✅ Yes | Full support |
| Linux ARM64 | ✅ Bundled | ✅ Bundled | ✅ Yes | Full support |
| Windows | MinGW sysroot | MinGW sysroot | N/A | Different API (SEH) |
| macOS | System | System | N/A | Uses system libunwind |

## Technical Details

### Transformer Implementation

The automatic injection is handled by `LinuxUnwindTransformer` in `src/clang_tool_chain/execution/arg_transformers.py`:

```python
class LinuxUnwindTransformer(ArgumentTransformer):
    """Injects bundled libunwind include/library paths on Linux."""

    def priority(self) -> int:
        return 150  # After SDK detection, before sanitizers

    def transform(self, args: list[str], context: ToolContext) -> list[str]:
        # Only applies to Linux clang/clang++
        if context.platform_name != "linux":
            return args
        if context.tool_name not in ("clang", "clang++"):
            return args

        # Check opt-out
        if is_feature_disabled("BUNDLED_UNWIND"):
            return args

        # Find clang root and check for bundled libunwind.h
        clang_root = get_clang_root()
        include_dir = clang_root / "include"
        lib_dir = clang_root / "lib"

        if not (include_dir / "libunwind.h").exists():
            return args  # Not bundled, skip

        # Inject flags
        return [
            f"-I{include_dir}",
            f"-L{lib_dir}",
            f"-Wl,-rpath,{lib_dir}",
            *args
        ]
```

### Library Deployment

When using `--deploy-dependencies`, libunwind libraries are recognized by `SoDeployer`:

```python
DEPLOYABLE_PATTERNS = [
    r"libunwind\.so[.\d]*",           # Main libunwind
    r"libunwind-x86_64\.so[.\d]*",    # x86_64-specific
    r"libunwind-aarch64\.so[.\d]*",   # ARM64-specific
    # ... other patterns
]
```

### Archive Building

Bundled libunwind is extracted from Ubuntu 22.04 during archive building:

```bash
# In downloads-bins/tools/fetch_and_archive.py
# Step 5.5a: Integrate libunwind for Linux (requires Docker)
if args.platform == "linux":
    libunwind_dir = extract_libunwind_from_docker(work_dir, args.arch)
    if libunwind_dir:
        integrate_libunwind_into_hardlinked(libunwind_dir, hardlinked_dir)
```

The Docker-based extraction ensures consistent, reproducible builds across all build environments.

## Troubleshooting

### "libunwind.h not found"

If you see this error, it means the bundled libunwind wasn't included in your archive:

```
fatal error: 'libunwind.h' file not found
```

**Solutions:**
1. Check if using an older archive version (pre-bundling)
2. Rebuild archives with Docker to include libunwind
3. As a workaround, install system libunwind: `apt-get install libunwind-dev`

### "cannot find -lunwind"

If linking fails with this error:

```
ld.lld: error: unable to find library -lunwind
```

**Solutions:**
1. Verify bundled libunwind exists: `ls ~/.clang-tool-chain/clang/linux/x86_64/lib/libunwind*`
2. Check transformer is active (not opt-out via environment variable)
3. Install system libunwind as fallback

### Runtime "libunwind.so not found"

If the executable fails at runtime:

```
./program: error while loading shared libraries: libunwind.so.8: cannot open shared object file
```

**Solutions:**
1. Verify rpath was set: `readelf -d program | grep RUNPATH`
2. Check library exists at rpath location
3. Use `--deploy-dependencies` to copy libraries to output directory
4. Manually set `LD_LIBRARY_PATH` as workaround

### Wrong libunwind version

If you need a specific version different from bundled:

```bash
# Disable bundled version
export CLANG_TOOL_CHAIN_NO_BUNDLED_UNWIND=1

# Install your preferred version
apt-get install libunwind-dev=1.6.2-3

# Compile with system version
clang-tool-chain-cpp backtrace.cpp -lunwind -o backtrace
```

## See Also

- [ASAN Support](../README.md#️-address-sanitizer-asan-support) - Address Sanitizer integration
- [Library Deployment](SHARED_LIBRARY_DEPLOYMENT.md) - Cross-platform library deployment
- [LLDB Debugger](LLDB.md) - Interactive debugging with Python support
- [libunwind Project](https://www.nongnu.org/libunwind/) - Upstream project documentation
