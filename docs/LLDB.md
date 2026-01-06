# LLDB (LLVM Debugger)

This package provides LLDB (LLVM Debugger) integration for debugging C/C++ programs compiled with clang-tool-chain. LLDB is automatically downloaded and installed on first use as an optional component, similar to IWYU and Emscripten.

## Key Features

- Pre-built LLDB binaries (~30 MB compressed for Windows x64 with Python)
- Automatic download and installation on first use
- Interactive debugging with full symbol support
- Automated crash analysis with `--print` mode
- **Full Python 3.10 support bundled (Windows x64)** - enables complete backtrace functionality
- Cross-platform support (Windows x64 complete, Linux/macOS pending)
- Manifest-based distribution with SHA256 verification
- Zero-configuration debug symbol support

## Platform Support

| Platform | Architecture | LLDB Version | Archive Size | Python Support | Status |
|----------|-------------|--------------|--------------|----------------|--------|
| Windows  | x86_64      | 21.1.5       | ~30 MB       | ✅ Full (3.10) | ✅ Complete |
| Linux    | x86_64      | 21.1.5       | ~10-11 MB (est.) | ✅ Full (3.10) | ⏳ Wrapper Ready, Archives Pending |
| Linux    | arm64       | 21.1.5       | ~10-11 MB (est.) | ✅ Full (3.10) | ⏳ Wrapper Ready, Archives Pending |
| macOS    | x86_64      | 21.1.6       | ~7 MB        | ⏳ Pending     | ⏳ Pending |
| macOS    | arm64       | 21.1.6       | ~7 MB        | ⏳ Pending     | ⏳ Pending |

**Current Status:**
- **Windows x64:** ✅ Complete - Full Python 3.10 bundled, all features working
- **Linux x86_64/ARM64:** ⏳ Wrapper integration complete, CI/CD workflow deployed, archives pending manual trigger
- **macOS:** Framework ready, binary distribution pending

**Note on macOS:** macOS includes a system LLDB via Xcode Command Line Tools. The bundled LLDB provides consistency across platforms and does not require Xcode installation.

## Installation

LLDB is installed automatically on first use. No pre-installation is required.

```bash
# Automatic installation on first use
clang-tool-chain-lldb --version

# Pre-install LLDB (optional, for CI/deployment)
clang-tool-chain install lldb

# Future: Add LLDB to PATH (not yet implemented)
# clang-tool-chain install lldb-env
```

## Wrapper Commands

### Interactive Debugging

Launch LLDB with an executable for interactive debugging:

```bash
# Compile with debug symbols
clang-tool-chain-c program.c -g3 -O0 -o program

# Launch interactive debugger (Windows)
clang-tool-chain-lldb program.exe

# Launch interactive debugger (Linux/macOS)
clang-tool-chain-lldb program
```

**Interactive LLDB Commands:**
```lldb
(lldb) run                    # Run the program
(lldb) breakpoint set -n main # Set breakpoint at main
(lldb) continue               # Continue execution
(lldb) bt                     # Print backtrace
(lldb) frame variable         # Show local variables
(lldb) quit                   # Exit LLDB
```

### Automated Crash Analysis

Use the `--print` flag for automated crash analysis and stack trace printing:

```bash
# Compile test program with debug symbols
clang-tool-chain-c crash_test.c -g3 -O0 -o crash_test.exe

# Run and analyze crash automatically
clang-tool-chain-lldb --print crash_test.exe
```

**What `--print` mode does:**
1. Runs the executable under LLDB in batch mode
2. Captures crash information (SIGSEGV, access violation, etc.)
3. Prints full backtrace with all threads
4. Shows source file names and line numbers
5. Exits after analysis (non-interactive)

**Example output:**
```
Process 12345 launched: 'crash_test.exe' (x86_64)
Starting program...
About to crash...
Process 12345 stopped
* thread #1, name = 'crash_test.exe', stop reason = signal SIGSEGV: invalid address (fault address: 0x0)
    frame #0: 0x00007ff7... crash_test.exe`trigger_crash(ptr=0x0) at crash_test.c:6:9
   4        void trigger_crash(int *ptr) {
   5            printf("About to crash...\n");
-> 6            *ptr = 42;  // Null pointer dereference
   7        }
   8
(lldb) bt all
* thread #1, name = 'crash_test.exe', stop reason = signal SIGSEGV
  * frame #0: 0x00007ff7... crash_test.exe`trigger_crash(ptr=0x0) at crash_test.c:6:9
    frame #1: 0x00007ff7... crash_test.exe`intermediate_function at crash_test.c:10:5
    frame #2: 0x00007ff7... crash_test.exe`main at crash_test.c:15:5
```

### Python Environment Diagnostics

Check if Python modules are bundled with LLDB for full "bt all" backtraces:

```bash
# Check LLDB Python environment status
clang-tool-chain-lldb-check-python
```

**What this command checks:**
1. Python directory exists in LLDB installation
2. Python site-packages are present (LLDB module)
3. Python standard library is available (python310.zip)
4. Environment variables (PYTHONPATH, PYTHONHOME) configuration
5. Whether Python scripting is enabled or disabled

**Example output (Python available):**
```
LLDB Python Environment Diagnostics
============================================================
Platform: win/x86_64
LLDB Install Dir: C:\Users\user\.clang-tool-chain\lldb\win\x86_64

Status: READY
Message: Python environment is fully configured

Python Components:
  Python Directory: C:\Users\user\.clang-tool-chain\lldb\win\x86_64\python
  Site-Packages: C:\Users\user\.clang-tool-chain\lldb\win\x86_64\python\Lib\site-packages
  LLDB Module: ✓ FOUND
  Python Stdlib (python310.zip): ✓ FOUND

Environment Variables (when LLDB runs):
  PYTHONPATH=C:\Users\user\.clang-tool-chain\lldb\win\x86_64\python\Lib\site-packages
  PYTHONHOME=C:\Users\user\.clang-tool-chain\lldb\win\x86_64\python
  LLDB_DISABLE_PYTHON: (removed - Python enabled)

✓ Python environment is ready for full 'bt all' backtraces!

You can now use:
  - Full stack traces with 'bt all' command
  - Python scripting in LLDB
  - Advanced variable inspection
```

**Exit codes:**
- `0` - Python environment is ready
- `1` - Python modules missing or incomplete

**Use case:** Verify Python integration before debugging complex crashes that require full backtrace support.

## What's Included

### Windows x64 (with Python 3.10)
- **lldb** - Main LLDB debugger executable (80-120 MB uncompressed)
- **lldb-server** - Remote debugging server (15-25 MB uncompressed)
- **lldb-argdumper** - Argument processing helper (5-10 MB uncompressed)
- **Python 3.10** - Full Python runtime and LLDB module for advanced features:
  - python310.dll (4.3 MB)
  - Python standard library (python310.zip)
  - LLDB Python module (_lldb.pyd + lldb package)
  - Enables full "bt all" backtraces, Python scripting, and advanced variable inspection

**Total uncompressed size:** ~209 MB (Windows x64 with Python)
**Compressed archive size:** ~30 MB (Windows x64 with Python) | ~7-8 MB (other platforms without Python)

### Other Platforms (Linux/macOS)
- **lldb** - Main LLDB debugger executable
- **lldb-server** - Remote debugging server
- **lldb-argdumper** - Argument processing helper

**Note:** Python bundling for Linux and macOS is planned but not yet implemented.

**Not included (may be added later):**
- lldb-vscode - VS Code debug adapter
- lldb-instr - Instrumentation tool

## Requirements

### For Effective Debugging

1. **Debug Symbols Required:** Compile with `-g3` flag for full debug information
2. **Disable Optimization:** Use `-O0` for accurate debugging (optimization can reorder/inline code)
3. **Source Files:** Keep source files in original locations for source-level debugging

### Compilation Example

```bash
# Good - Full debug information
clang-tool-chain-c program.c -g3 -O0 -o program.exe

# Also acceptable - Basic debug info
clang-tool-chain-c program.c -g -O0 -o program.exe

# Bad - No debug symbols
clang-tool-chain-c program.c -o program.exe

# Bad - Optimization interferes with debugging
clang-tool-chain-c program.c -g3 -O3 -o program.exe
```

## Usage Examples

### Example 1: Debugging a Segmentation Fault

```c
// crash_test.c
#include <stdio.h>

void trigger_crash(int *ptr) {
    printf("About to crash...\n");
    *ptr = 42;  // Null pointer dereference
}

void intermediate_function() {
    trigger_crash(NULL);
}

int main() {
    printf("Starting program...\n");
    intermediate_function();
    return 0;
}
```

**Compile and debug:**

```bash
# Compile with debug symbols
clang-tool-chain-c crash_test.c -g3 -O0 -o crash_test.exe

# Automated crash analysis
clang-tool-chain-lldb --print crash_test.exe
```

**Expected output:**
- Function names: `main`, `intermediate_function`, `trigger_crash`
- Source file: `crash_test.c`
- Line numbers: `:6`, `:10`, `:15`
- Crash reason: `SIGSEGV`, `access violation`, `invalid address`

### Example 2: Interactive Debugging Session

```bash
# Compile program
clang-tool-chain-c program.c -g3 -O0 -o program.exe

# Launch LLDB
clang-tool-chain-lldb program.exe
```

**Interactive commands:**

```lldb
(lldb) breakpoint set -n main        # Set breakpoint at main
Breakpoint 1: where = program.exe`main at program.c:10

(lldb) run                           # Run program
Process 1234 launched...

(lldb) step                          # Step into function
Process 1234 stopped at program.c:11

(lldb) frame variable                # Show local variables
(int) x = 42
(char *) str = "Hello"

(lldb) continue                      # Continue execution
Process 1234 exited with status = 0

(lldb) quit                          # Exit LLDB
```

### Example 3: Debugging with Breakpoints

```bash
clang-tool-chain-lldb program.exe
```

```lldb
(lldb) breakpoint set -f program.c -l 25    # Break at line 25
(lldb) breakpoint set -n compute_value      # Break at function
(lldb) breakpoint list                      # List all breakpoints
(lldb) run                                  # Start execution
(lldb) bt                                   # Show backtrace
(lldb) frame select 1                       # Move to frame 1
(lldb) print variable_name                  # Print variable value
(lldb) continue                             # Resume execution
```

## Debug Symbols Guide

### Debug Symbol Levels

| Flag | Level | Description | Size Impact | Use Case |
|------|-------|-------------|-------------|----------|
| (none) | None | No debug info | Smallest | Production release |
| `-g` or `-g2` | Default | Basic debug info | +20-30% | General debugging |
| `-g3` | Full | Macro definitions + all debug info | +30-50% | Comprehensive debugging |
| `-g1` | Minimal | Line numbers only | +10-15% | Stack traces only |

### Debug Symbol Best Practices

```bash
# Development build - full debug info, no optimization
clang-tool-chain-c program.c -g3 -O0 -o program_debug.exe

# Release build with debug symbols - optimized + debug info
clang-tool-chain-c program.c -g2 -O2 -o program_release.exe

# Production release - no debug symbols, full optimization
clang-tool-chain-c program.c -O3 -o program_release.exe
```

## Platform-Specific Notes

### Windows (x64)

- **Status:** ✅ Fully implemented and tested
- **Binary format:** PE (Portable Executable)
- **Debug format:** DWARF (via MinGW) or PDB (via MSVC)
- **Crash signal:** Access violation exception
- **DLL dependencies:** Uses MinGW runtime DLLs (libwinpthread-1.dll, etc.)
- **Expected behavior:** Stack traces show Windows paths with backslashes

**Windows-specific debugging:**

```bash
# Debug GNU ABI executable (default)
clang-tool-chain-lldb program.exe

# Debug MSVC ABI executable
clang-tool-chain-cpp-msvc program.cpp -g3 -O0 -o program_msvc.exe
clang-tool-chain-lldb program_msvc.exe
```

### Linux (x86_64 and ARM64)

- **Status:** ⏳ Wrapper Ready, Archives Pending CI/CD
- **Binary format:** ELF (Executable and Linkable Format)
- **Debug format:** DWARF
- **Crash signal:** SIGSEGV (segmentation fault)
- **Library dependencies:** May require libunwind for stack unwinding
- **Expected behavior:** Standard Unix-style stack traces
- **Python Support:** ✅ Full Python 3.10 will be bundled (like Windows)

**Wrapper Integration Status:**
- ✅ LLDB wrapper supports Linux (src/clang_tool_chain/execution/lldb.py:392-439)
- ✅ PYTHONPATH environment variable configured
- ✅ PYTHONHOME environment variable configured
- ✅ Python module discovery implemented
- ✅ LD_LIBRARY_PATH support for liblldb.so
- ✅ Test infrastructure ready (tests/test_lldb.py)
- ✅ Manifest files prepared with Python metadata
- ⏳ LLDB archives pending GitHub Actions workflow execution

**Environment Variables (Linux):**
```bash
# Set automatically by wrapper when LLDB runs
PYTHONPATH=$HOME/.clang-tool-chain/lldb-linux-x86_64/python/Lib/site-packages
PYTHONHOME=$HOME/.clang-tool-chain/lldb-linux-x86_64/python
LD_LIBRARY_PATH=$HOME/.clang-tool-chain/lldb-linux-x86_64/lib
```

**Known considerations:**
- Python 3.10 site-packages bundled in LLDB archive (~10-11 MB compressed)
- libpython3.10.so may use system library initially (not bundled)
- System LLDB available via package manager (apt, dnf) but lacks Python integration

### macOS (x86_64 and ARM64)

- **Status:** ⏳ Implementation pending
- **Binary format:** Mach-O
- **Debug format:** DWARF (embedded or .dSYM bundle)
- **Crash signal:** EXC_BAD_ACCESS (SIGSEGV)
- **System LLDB:** Available via Xcode Command Line Tools
- **Expected behavior:** macOS uses code signing, may require entitlements

**Known considerations:**
- macOS includes system LLDB (may prefer bundled for consistency)
- Code signing may affect debugging
- SIP (System Integrity Protection) restrictions apply
- Apple Silicon (ARM64) requires proper Rosetta 2 handling for x86_64 binaries

## libunwind Dependency

LLDB uses libunwind for accurate stack unwinding during debugging. This is critical for proper backtrace generation.

### libunwind Status by Platform

| Platform | libunwind Included? | Source | Notes |
|----------|-------------------|--------|-------|
| Windows x64 | ✅ Yes | MinGW sysroot | Bundled with toolchain |
| Linux x64 | ⚠️ TBD | LLVM or system | Investigation pending |
| Linux ARM64 | ⚠️ TBD | LLVM or system | May use ARM EHABI |
| macOS x64 | ✅ Yes | System libunwind | Part of macOS |
| macOS ARM64 | ✅ Yes | System libunwind | Part of macOS |

**For detailed libunwind investigation results, see:** `lib_unwind_issues.md` (pending creation)

### Current libunwind Usage

The clang-tool-chain already uses libunwind for Windows GNU ABI compilation:

```bash
# From src/clang_tool_chain/abi/windows_gnu.py:141
--unwindlib=libunwind
```

This suggests libunwind is available in the MinGW sysroot on Windows.

## Python Support

### Windows x64 - Full Python 3.10 Bundled ✅

LLDB on Windows x64 now includes **complete Python 3.10 support** bundled in the archive, enabling all advanced debugging features out of the box:

**Bundled Components:**
- ✅ python310.dll (4.3 MB) - Python runtime DLL
- ✅ Python standard library (python310.zip) - Core Python modules
- ✅ LLDB Python module (_lldb.pyd + lldb package) - Full LLDB Python API

**What This Enables:**
- ✅ Full stack backtraces using "bt all" command with threading support
- ✅ Advanced variable inspection beyond basic frame variables
- ✅ Python scripting and custom commands
- ✅ LLDB Python API usage
- ✅ All interactive debugging features

**No system Python required!** Everything works out of the box after installation.

**Archive Size Impact:**
- Previous size (without Python): ~29 MB compressed
- Current size (with full Python): ~30 MB compressed
- Size increase: Only ~1 MB due to efficient binary deduplication (zstd level 22)

### Linux (x86_64 and ARM64) - Python 3.10 Bundling Ready ⏳

Python bundling for Linux is **fully integrated in the wrapper** but archives are pending CI/CD workflow execution:

**What Will Be Bundled:**
- ✅ Python 3.10 standard library (minimized from 43 MB → 11 MB)
- ✅ LLDB Python module (_lldb.cpython-310-*.so + lldb package)
- ✅ Relative symlinks for binary deduplication
- ⏳ libpython3.10.so (may use system Python initially)

**Expected Archive Size:**
- ~10-11 MB compressed per platform (includes Python)
- Similar to Windows (~30 MB) but with less binary duplication

**Current Status:**
- ✅ Wrapper integration complete (automatic PYTHONPATH/PYTHONHOME setup)
- ✅ Python modules extracted from Debian Jammy packages
- ✅ GitHub Actions workflow ready (.github/workflows/build-lldb-archives-linux.yml)
- ⏳ Archives pending manual workflow trigger

**Testing:**
Once archives are available, verify with:
```bash
# Check Python environment status
clang-tool-chain-lldb-check-python
# Should show: "Status: READY" and "Python environment is fully configured"
```

### macOS (x86_64 and ARM64)

Python bundling for macOS is planned but not yet implemented. On these platforms:
- Basic LLDB debugging works without Python
- Advanced features may require system Python 3.10.x installation
- Future releases will bundle Python similar to Windows x64 and Linux

### Testing Python Integration

Verify Python is working correctly:

```bash
# Check Python environment status
clang-tool-chain-lldb-check-python

# Should show: "Status: READY" and "Python environment is fully configured"

# Test full backtrace in automated mode
clang-tool-chain-lldb --print crash_test.exe
# Should show complete stack traces with all frames
```

## Troubleshooting

### Issue: LLDB not found after installation

**Symptoms:**
```
RuntimeError: LLDB binary directory not found
```

**Solution:**
```bash
# Check if LLDB downloaded successfully
ls ~/.clang-tool-chain/lldb/bin/

# Should contain: lldb.exe (Windows) or lldb (Linux/macOS)

# Force re-download
rm -rf ~/.clang-tool-chain/lldb
clang-tool-chain-lldb --version

# Check manifest
cat ~/.clang-tool-chain/lldb/done.txt
```

### Issue: No debug symbols in stack trace

**Symptoms:**
```
frame #0: 0x00401234 program.exe
frame #1: 0x00401567 program.exe
# No function names, no line numbers
```

**Solution:**
```bash
# Problem: Compiled without debug symbols
clang-tool-chain-c test.c -o test.exe  # ❌ No debug info

# Fix: Compile with -g3 flag
clang-tool-chain-c test.c -g3 -O0 -o test.exe  # ✅ Full debug info

# Verify debug symbols present (Linux/macOS)
file test
# Output should contain: "with debug_info, not stripped"

# Verify debug symbols (Windows)
llvm-objdump --dwarf=info test.exe | head
# Should show DWARF debug sections
```

### Issue: Optimized code debugging is confusing

**Symptoms:**
- Execution jumps around unexpectedly
- Variables show `<optimized out>`
- Line numbers don't match source

**Solution:**
```bash
# Problem: Optimization reorders/inlines code
clang-tool-chain-c program.c -g3 -O3 -o program.exe  # ❌ Hard to debug

# Fix: Disable optimization for debug builds
clang-tool-chain-c program.c -g3 -O0 -o program.exe  # ✅ Accurate debugging
```

### Issue: Source files not found

**Symptoms:**
```
(lldb) run
Unable to resolve breakpoint to any actual locations.
```

**Solution:**
- Keep source files in original compile location
- Use absolute paths when compiling: `clang-tool-chain-c /full/path/to/program.c`
- Or compile in source directory: `cd /path/to/source && clang-tool-chain-c program.c`

### Issue: libunwind not found (Linux)

**Symptoms:**
```
error: libunwind not found
```

**Solution:**
```bash
# Check if bundled libunwind exists
find ~/.clang-tool-chain/clang/ -name "*unwind*"

# If not found, install system libunwind
sudo apt install libunwind-dev        # Ubuntu/Debian
sudo dnf install libunwind-devel      # Fedora/RHEL
sudo pacman -S libunwind              # Arch Linux
```

### Issue: LLDB crashes on startup (Windows)

**Symptoms:**
```
Error: The program can't start because libwinpthread-1.dll is missing
```

**Solution:**
```bash
# Ensure MinGW sysroot is installed
clang-tool-chain-c --version

# Check MinGW DLLs are present
ls ~/.clang-tool-chain/clang/bin/*.dll | grep -E "(pthread|gcc|stdc++)"

# Should show:
# libwinpthread-1.dll
# libgcc_s_seh-1.dll
# libstdc++-6.dll
```

### Issue: Access denied debugging another user's process

**Symptoms:**
```
error: attach failed: Operation not permitted
```

**Solution:**
- Run LLDB as administrator (Windows) or with sudo (Linux/macOS)
- Or debug your own processes only
- macOS: May need to disable SIP for debugging system processes

## Linux-Specific Troubleshooting

### Issue: Python environment not ready on Linux

**Symptoms:**
```bash
clang-tool-chain-lldb-check-python
# Output: "Status: NOT_READY" or "Python environment not configured"
```

**Solution:**
```bash
# Step 1: Verify LLDB installation
clang-tool-chain install lldb

# Step 2: Check Python directory exists
ls ~/.clang-tool-chain/lldb-linux-x86_64/python/Lib/site-packages/lldb/
# Should show: __init__.py, _lldb.*.so, formatters/, plugins/, utils/

# Step 3: Verify LLDB Python module symlink
ls -l ~/.clang-tool-chain/lldb-linux-x86_64/python/Lib/site-packages/lldb/_lldb.*.so
# Should show symlink to ../../../lib/liblldb.so

# Step 4: Check libpython3.10.so availability
python3.10 --version
# If missing: sudo apt install python3.10 (Ubuntu/Debian)

# Step 5: Re-run diagnostic
clang-tool-chain-lldb-check-python
# Should now show: "Status: READY"
```

**Expected Diagnostic Output (Ready):**
```
LLDB Python Environment Diagnostic
==================================
Python ZIP: NOT FOUND (Linux uses Lib/ directory instead)
Python Lib Directory: FOUND (/home/user/.clang-tool-chain/lldb-linux-x86_64/python/Lib)
LLDB Module: FOUND (/home/user/.clang-tool-chain/lldb-linux-x86_64/python/Lib/site-packages/lldb/__init__.py)
Python Binary: FOUND (3.10.x)
Environment: CONFIGURED (PYTHONPATH and PYTHONHOME set)
Status: READY

Python environment is fully configured. Full 'bt all' backtraces should work.
```

### Issue: "libpython3.10.so.1.0: cannot open shared object file" on Linux

**Symptoms:**
```
lldb: error while loading shared libraries: libpython3.10.so.1.0: cannot open shared object file: No such file or directory
```

**Solution:**
```bash
# Install system Python 3.10 (provides libpython3.10.so)
# Ubuntu 22.04 (Jammy) or later
sudo apt update
sudo apt install python3.10 python3.10-dev

# Ubuntu 20.04 (Focal) - requires PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-dev

# Verify libpython3.10.so is available
ldconfig -p | grep libpython3.10
# Should show: libpython3.10.so.1.0 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libpython3.10.so.1.0

# Retry LLDB
clang-tool-chain-lldb --version
```

**Alternative: Use LD_LIBRARY_PATH (temporary workaround):**
```bash
# If system Python not available, locate libpython3.10.so manually
find /usr -name "libpython3.10.so*" 2>/dev/null

# Add to LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/path/to/python/lib:$LD_LIBRARY_PATH
clang-tool-chain-lldb --version
```

### Issue: Incomplete backtraces on Linux ("?? ()" frames)

**Symptoms:**
```
(lldb) bt all
* thread #1, name = 'program'
    frame #0: 0x00007ffff7a2d000
    frame #1: 0x00007ffff7a2d123 ?? ()
    frame #2: 0x00007ffff7a2d456 ?? ()
# Missing function names and line numbers
```

**Root Cause:** Python environment not configured, limiting LLDB's backtrace capabilities.

**Solution:**
```bash
# Verify Python environment is ready
clang-tool-chain-lldb-check-python
# Must show: "Status: READY"

# If NOT_READY, follow steps in "Python environment not ready" section above

# Re-compile with debug symbols
clang-tool-chain-cpp program.cpp -g3 -O0 -o program

# Test backtrace again
clang-tool-chain-lldb --print program
# Should now show full function names and line numbers
```

### Issue: LLDB crashes with "Illegal instruction" on ARM64

**Symptoms:**
```bash
clang-tool-chain-lldb --version
# Output: Illegal instruction (core dumped)
```

**Root Cause:** ARM64 binaries built for different CPU (e.g., ARMv8.2) running on older ARM CPU (e.g., ARMv8.0).

**Solution:**
```bash
# Check CPU features
lscpu | grep -E "(Architecture|Model name|Flags)"

# Check LLDB binary architecture
file ~/.clang-tool-chain/lldb-linux-arm64/bin/lldb

# If architecture mismatch, file a GitHub issue with CPU details
# GitHub: https://github.com/zackees/clang-tool-chain/issues

# Workaround: Use system LLDB temporarily
sudo apt install lldb-21
lldb-21 --version
```

### Issue: "ptrace: Operation not permitted" on Linux

**Symptoms:**
```
error: attach failed: ptrace: Operation not permitted
```

**Root Cause:** Linux security restrictions (Yama ptrace scope or container restrictions).

**Solution:**

**Option 1: Temporarily disable Yama ptrace restrictions (requires sudo):**
```bash
# Check current ptrace_scope value
cat /proc/sys/kernel/yama/ptrace_scope
# 0 = Classic ptrace (all processes can ptrace)
# 1 = Restricted ptrace (only parent processes, default on Ubuntu)
# 2 = Admin-only attach (only admin can ptrace)
# 3 = No attach (no ptrace allowed)

# Temporarily allow ptrace for debugging session
sudo sysctl kernel.yama.ptrace_scope=0

# Debug your program
clang-tool-chain-lldb program

# Restore security after debugging
sudo sysctl kernel.yama.ptrace_scope=1
```

**Option 2: Run debugger as root (less secure):**
```bash
sudo $(which clang-tool-chain-lldb) program
```

**Option 3: Add CAP_SYS_PTRACE capability (persistent, secure):**
```bash
# Add capability to LLDB binary
sudo setcap cap_sys_ptrace=eip ~/.clang-tool-chain/lldb-linux-x86_64/bin/lldb

# Now debug without sudo
clang-tool-chain-lldb program
```

**Docker/Container Users:**
```bash
# Add --cap-add=SYS_PTRACE to docker run command
docker run --cap-add=SYS_PTRACE -it your-image
```

### Issue: ARM64 and x86_64 confusion (wrong architecture installed)

**Symptoms:**
```bash
clang-tool-chain-lldb --version
# Output: cannot execute binary file: Exec format error
```

**Root Cause:** Installed x86_64 LLDB on ARM64 system, or vice versa.

**Solution:**
```bash
# Check system architecture
uname -m
# x86_64 = Intel/AMD 64-bit
# aarch64 = ARM 64-bit

# Remove wrong architecture
clang-tool-chain purge --yes

# Re-install (will auto-detect correct architecture)
clang-tool-chain install lldb

# Verify correct architecture installed
file ~/.clang-tool-chain/lldb-linux-*/bin/lldb
# Should match system architecture (x86-64 or aarch64)
```

### Issue: Test workflows skipped on Linux (CI/CD)

**Symptoms:**
GitHub Actions shows "Linux LLDB tests" workflow as skipped or "Archives not available yet".

**Root Cause:** LLDB archives not yet built or manual workflow trigger pending.

**Solution:**
```bash
# Check if archives available in downloads-bins repository
cd downloads-bins/
git pull origin main
ls -lh assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst
ls -lh assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst

# If files not present: Archives pending manual workflow trigger
# See: .agent_task/WORKFLOW_TRIGGER_GUIDE.md for instructions

# Once archives available:
cd ../clang-tool-chain/
git submodule update --remote downloads-bins
git add downloads-bins
git commit -m "Update downloads-bins submodule (LLDB Linux archives)"
git push origin main

# CI/CD will automatically run LLDB tests on next push
```

### Expected Test Behavior on Linux

When LLDB archives are available and tests run on Linux:

**Expected: All tests pass ✅**
```bash
pytest tests/test_lldb.py -v
# test_lldb_binary_dir_discovery PASSED
# test_lldb_version PASSED
# test_lldb_print_crash_stack PASSED
# test_lldb_full_backtraces_with_python PASSED
# ============================== 4 passed ==============================
```

**Test Details:**

1. **test_lldb_binary_dir_discovery** - Verifies LLDB installation directory exists
   - Checks `~/.clang-tool-chain/lldb-linux-{arch}/bin/lldb` exists
   - Validates directory structure (bin/, lib/, python/)

2. **test_lldb_version** - Verifies LLDB version query works
   - Runs `clang-tool-chain-lldb --version`
   - Validates version output contains "lldb version"

3. **test_lldb_print_crash_stack** - Tests automated crash analysis
   - Compiles test program with intentional crash (null pointer dereference)
   - Runs `clang-tool-chain-lldb --print crash_test`
   - Verifies stack trace contains function names, file names, line numbers

4. **test_lldb_full_backtraces_with_python** - Tests Python-powered deep backtraces
   - Compiles program with 7-level deep call stack
   - Verifies "bt all" captures all 7 user frames
   - Confirms Python environment enables full backtrace functionality
   - Validates frame details (function names, file names, line numbers)

**If tests fail:**
```bash
# Check Python environment
clang-tool-chain-lldb-check-python
# Should show: "Status: READY"

# Verify libpython3.10.so available
python3.10 --version

# Check LLDB can start
clang-tool-chain-lldb --version

# Run tests with verbose output
pytest tests/test_lldb.py -v -s

# File GitHub issue if tests fail consistently
# GitHub: https://github.com/zackees/clang-tool-chain/issues
```

## Command Reference

### Basic Commands

```bash
# Show LLDB version
clang-tool-chain-lldb --version

# Interactive debugging
clang-tool-chain-lldb <executable>

# Automated crash analysis
clang-tool-chain-lldb --print <executable>

# LLDB with arguments
clang-tool-chain-lldb <executable> -- arg1 arg2 arg3

# Help (launches interactive LLDB help)
clang-tool-chain-lldb
(lldb) help
```

### LLDB Interactive Commands

```lldb
# Process control
run [args]              # Run the program with optional arguments
continue                # Resume execution
step                    # Step into (source level)
next                    # Step over (source level)
finish                  # Step out of current function
kill                    # Kill the process
quit                    # Exit LLDB

# Breakpoints
breakpoint set -n <func>            # Break at function name
breakpoint set -f <file> -l <line>  # Break at file:line
breakpoint list                     # List all breakpoints
breakpoint delete <num>             # Delete breakpoint
breakpoint disable <num>            # Disable breakpoint

# Inspection
bt [all]                # Print backtrace (all threads)
frame select <num>      # Select stack frame
frame variable          # Show local variables
print <expr>            # Evaluate and print expression
p <var>                 # Short form of print
expr <statement>        # Execute arbitrary code

# Memory inspection
memory read <addr>      # Read memory at address
disassemble             # Disassemble current function
register read           # Show register values

# Thread control
thread list             # List all threads
thread select <num>     # Select thread
thread backtrace        # Show thread backtrace

# Settings
settings set target.x86-disassembly-flavor intel  # Intel disassembly
settings show           # Show all settings
```

## Advanced Features

### Remote Debugging (Future)

LLDB includes `lldb-server` for remote debugging. This feature is not yet documented but is supported.

```bash
# Server (target machine)
lldb-server platform --listen *:1234

# Client (development machine)
clang-tool-chain-lldb
(lldb) platform select remote-linux
(lldb) platform connect connect://remote-ip:1234
(lldb) file program
(lldb) run
```

### Python Scripting (Future)

LLDB has a Python API for automation and custom commands. This feature is not yet documented.

```python
import lldb

# Create debugger
debugger = lldb.SBDebugger.Create()

# Create target
target = debugger.CreateTarget("program.exe")

# Set breakpoint
breakpoint = target.BreakpointCreateByName("main")

# Launch process
process = target.LaunchSimple(None, None, os.getcwd())

# Continue execution
process.Continue()
```

### VS Code Integration (Future)

LLDB includes `lldb-vscode` for VS Code integration. This may be bundled in a future release.

## Architecture Integration

### Installation Directory Structure

```
~/.clang-tool-chain/lldb/
├── win/
│   └── x86_64/
│       ├── bin/
│       │   ├── lldb.exe
│       │   ├── lldb-server.exe
│       │   └── lldb-argdumper.exe
│       ├── lib/           # Shared libraries (Linux/macOS)
│       └── done.txt       # Version + SHA256
├── linux/
│   ├── x86_64/
│   └── arm64/
└── darwin/
    ├── x86_64/
    └── arm64/
```

### Manifest Structure

LLDB uses the same manifest system as IWYU and Emscripten:

- **Root manifest:** `assets/lldb/manifest.json` (platform + arch list)
- **Platform manifests:** `assets/lldb/{platform}/{arch}/manifest.json` (version + URL + SHA256)

### Integration with clang-tool-chain

LLDB integrates with the existing clang-tool-chain infrastructure:

1. **Download on first use:** `ensure_lldb()` called by `get_lldb_binary_dir()`
2. **File locking:** Prevents concurrent downloads (InterProcessLock)
3. **Version tracking:** `done.txt` contains version + SHA256
4. **Re-download on mismatch:** If manifest SHA256 changes, re-downloads
5. **Purge support:** `clang-tool-chain purge` removes LLDB installation

## Future Enhancements

### Planned Features

- **PATH integration:** `clang-tool-chain install lldb-env` to add LLDB to system PATH
- **Linux x64 support:** Complete binary packaging and testing
- **Linux ARM64 support:** Complete binary packaging and testing
- **macOS x64 support:** Complete binary packaging and testing
- **macOS ARM64 support:** Complete binary packaging and testing
- **VS Code integration:** Bundle `lldb-vscode` for IDE debugging
- **Python scripting docs:** Document LLDB Python API usage
- **Pretty printers:** STL container visualization

### Optional Future Tools

- **GDB support:** Alternative debugger for Linux developers
- **lldb-instr:** Instrumentation tool
- **Remote debugging guide:** Comprehensive remote debugging documentation

## Testing

LLDB is tested via `tests/test_lldb.py` with comprehensive automated tests for full backtrace functionality.

### Test Coverage

- **Basic functionality:**
  - LLDB binary directory discovery
  - Tool finding (lldb, lldb-server, lldb-argdumper)
  - Version queries

- **Crash analysis (Windows x64 with Python):**
  - Automated crash analysis (`--print` mode)
  - Stack trace verification (function names, file names, line numbers, crash reason)
  - Full backtrace testing with deep call stacks (7+ levels)
  - Python integration verification (ensures "bt all" works)

- **Platform-specific behavior:**
  - Windows GNU ABI executable debugging
  - Windows MSVC ABI executable debugging (future)
  - Linux/macOS testing framework (pending)

### Running Tests Locally

```bash
# Run all LLDB tests (4 tests)
uv run pytest tests/test_lldb.py -v

# Output should show:
# test_lldb_binary_dir_discovery PASSED
# test_lldb_version PASSED
# test_lldb_print_crash_stack PASSED
# test_lldb_full_backtraces_with_python PASSED
# ============================== 4 passed in ~7s ==============================

# Run specific test
uv run pytest tests/test_lldb.py::test_lldb_full_backtraces_with_python -v

# Run with verbose output to see full backtraces
uv run pytest tests/test_lldb.py -v -s
```

### Test Design

The LLDB tests use a sophisticated approach to ensure full backtrace functionality:

1. **Deep call stack generation:** Tests create 7-level deep call stacks to verify complete backtrace capture
2. **Automated crash analysis:** Uses `--print` mode to run LLDB non-interactively
3. **Python integration verification:** Confirms Python modules are loaded and "bt all" works
4. **Cross-ABI testing:** Tests both GNU ABI (default) and MSVC ABI executables (future)

**Key test: `test_lldb_full_backtraces_with_python`**
- Creates a 7-level deep call stack (level7 → level6 → ... → level1 → main)
- Crashes at deepest level (null pointer dereference)
- Verifies all 7 user frames appear in backtrace
- Confirms Python-powered "bt all" command works
- Ensures function names, file names, and line numbers are present

## References

### External Documentation

- **LLDB Official Docs:** https://lldb.llvm.org/
- **LLDB Tutorial:** https://lldb.llvm.org/use/tutorial.html
- **LLDB Python API:** https://lldb.llvm.org/python_api.html
- **LLVM libunwind:** https://libunwind.llvm.org/
- **DWARF Debug Format:** http://dwarfstd.org/

### Internal Documentation

- **LOOP.md:** Implementation guide and progress tracking
- **ITERATION_*.md:** Development iteration summaries
- **lib_unwind_issues.md:** libunwind investigation (pending)
- **ARCHITECTURE.md:** Overall system architecture
- **TESTING.md:** Testing infrastructure guide

### Code References

- **Execution module:** `src/clang_tool_chain/execution/lldb.py`
- **Entry point:** `src/clang_tool_chain/commands/entry_points.py::lldb_main()`
- **Installer:** `src/clang_tool_chain/installer.py::ensure_lldb()`
- **Tests:** `tests/test_lldb.py`
- **CI Workflows:** `.github/workflows/test-lldb-*.yml`

## Changelog

### Version History

- **2026-01-05:** Initial LLDB implementation (Windows x64 complete)
  - Python wrapper infrastructure complete
  - Test infrastructure complete (all platforms)
  - GitHub Actions workflows created (all platforms)
  - Documentation created
  - Linux/macOS framework ready, binaries pending

---

**Status:** Windows x64 implementation complete and ready for testing. Linux and macOS support framework complete, binary distribution pending.

**Last Updated:** 2026-01-05

**Maintained By:** clang-tool-chain project
