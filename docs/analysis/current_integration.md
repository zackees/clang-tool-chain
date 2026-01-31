# Analysis: Current Integration Points for Shared Library Deployment

**Agent 1.4 Report** - January 25, 2026

This document analyzes the current clang-tool-chain codebase to identify where shared libraries are handled and where the Linux/macOS shared library deployment feature should be integrated.

---

## Table of Contents

1. [libunwind References](#libunwind-references)
2. [Linker Flag Handling](#linker-flag-handling)
3. [Integration Points in execution/core.py](#integration-points-in-executioncorepy)
4. [Existing Shared Library Handling](#existing-shared-library-handling)
5. [Windows DLL Deployment Integration Architecture](#windows-dll-deployment-integration-architecture)
6. [Recommendations for Linux/macOS Integration](#recommendations-for-linuxmacos-integration)

---

## 1. libunwind References

libunwind is already integrated into the codebase in several key locations:

### 1.1 Windows GNU ABI Setup

**Location**: `src/clang_tool_chain/abi/windows_gnu.py:228`

```python
# --unwindlib=libunwind flag is added during linking
```

This tells clang to use LLVM's libunwind instead of libgcc_s for exception handling on Windows GNU ABI.

### 1.2 DLL Deployer Patterns

**Location**: `src/clang_tool_chain/deployment/dll_deployer.py:27`

```python
MINGW_DLL_PATTERNS = [
    # ...
    r"libunwind.*\.dll",  # LLVM unwinding library
    # ...
]
```

libunwind.dll is explicitly recognized as a MinGW runtime DLL that should be automatically deployed with Windows executables.

### 1.3 Documentation References

**Location**: `docs/DLL_DEPLOYMENT.md:99`

libunwind.dll is documented as:
- LLVM unwinding library
- Transitive dependency in complex dependency chains (e.g., ASan → libc++ → libunwind)

### 1.4 Tests

**Location**: `tests/test_dll_deployment.py:1504`, line 1567

libunwind.dll is tested as a transitive dependency in complex linking scenarios, ensuring the deployment system handles multi-level dependencies correctly.

---

## 2. Linker Flag Handling

The codebase has a sophisticated argument transformation pipeline for processing compiler and linker flags.

### 2.1 Architecture

**Location**: `src/clang_tool_chain/execution/arg_transformers.py`

The argument transformation system uses:

- **ArgumentTransformer** (ABC): Base class for all transformers
- **Pipeline Pattern**: Transformers execute in priority order
- **ToolContext**: Passes platform, arch, tool_name, use_msvc info to transformers

### 2.2 Current Transformers

| Transformer | Priority | Purpose |
|------------|----------|---------|
| MacOSSDKTransformer | 100 | Adds macOS SDK flags |
| DirectivesTransformer | 50 | Parses inlined directives (@link, @std, etc.) |
| LLDLinkerTransformer | 200 | Configures LLVM lld linker |
| GNUABITransformer | 300 | Windows GNU ABI setup |
| MSVCABITransformer | 300 | Windows MSVC ABI setup |

### 2.3 Inlined Directives Support

**Location**: `src/clang_tool_chain/execution/parser.py`

The DirectivesTransformer parses source file comments for build configuration:

```cpp
// @link: pthread
// @ldflags: -rpath /opt/lib
// @std: c++17
// @include: /usr/local/include
// @platform: linux
//   @link: rt
```

These directives are automatically extracted and converted to compiler/linker flags.

---

## 3. Integration Points in execution/core.py

The execution module has well-established deployment hooks that can be extended for Linux/macOS.

### 3.1 Import Statement

**Location**: `src/clang_tool_chain/execution/core.py:22`

```python
from clang_tool_chain.deployment.dll_deployer import (
    post_link_dependency_deployment,
    post_link_dll_deployment
)
```

This is where Linux/macOS deployer imports should be added.

### 3.2 Deploy Dependencies Flag Extraction

**Location**: `src/clang_tool_chain/execution/core.py:36-60`

```python
def _extract_deploy_dependencies_flag(args: list[str]) -> tuple[list[str], bool]:
    """
    Extracts the custom --deploy-dependencies flag from args.

    This flag triggers deployment of shared library dependencies
    for .dll/.so/.dylib outputs.
    """
    # Implementation removes --deploy-dependencies before passing to clang
```

This custom flag enables manual dependency deployment for shared libraries (not just executables).

### 3.3 Shared Library Output Path Detection

**Location**: `src/clang_tool_chain/execution/core.py:160-220`

```python
def _extract_shared_library_output_path(args: list[str], tool_name: str) -> Path | None:
    """
    Extracts output path for shared libraries (.dll, .so, .dylib).

    Returns:
        Path to output file if:
        - Output has .dll, .so, .so.*, or .dylib extension
        - -shared flag is present
        None otherwise
    """
```

**Key Features**:
- Already detects `.dll`, `.so`, `.so.*`, `.dylib` outputs
- Checks for `-shared` flag to identify shared library builds
- Returns Path or None

This function is already cross-platform ready.

### 3.4 Post-Link Deployment Hooks (Windows)

**Location**: `src/clang_tool_chain/execution/core.py:291-313`

```python
# After successful linking (result.returncode == 0)
if platform_name == "windows":
    output_exe = _extract_output_path(args, tool_name)
    if output_exe is not None:
        # Automatic DLL deployment for .exe files
        post_link_dll_deployment(output_exe, ...)

    if deploy_dependencies_requested:
        shared_lib_path = _extract_shared_library_output_path(args, tool_name)
        if shared_lib_path is not None:
            # Manual dependency deployment for .dll files
            post_link_dependency_deployment(shared_lib_path, ...)
```

**This is the primary integration point for Linux/macOS deployment.**

### 3.5 Additional Hook Locations

Similar deployment hooks exist at:
- Lines 429-451: `run_tool()` function
- Lines 523-545: `run_tool_with_sccache()` wrapper
- Lines 628-650: Sccache variant for non-Windows

All these locations need Linux/macOS deployment logic added.

### 3.6 Existing Linux/macOS Stubs

**Location**: `src/clang_tool_chain/execution/core.py:711-738`

```python
def _deploy_linux_so_dependencies(...) -> None:
    """Deploy .so dependencies on Linux (not yet implemented)."""
    logger.info("Linux .so deployment not yet implemented")

def _deploy_macos_dylib_dependencies(...) -> None:
    """Deploy .dylib dependencies on macOS (not yet implemented)."""
    logger.info("macOS .dylib deployment not yet implemented")
```

These placeholder functions show where the implementation should go.

---

## 4. Existing Shared Library Handling

### 4.1 Windows DLL Deployment (Fully Implemented)

**Automatic Deployment** (for .exe files):
- Function: `post_link_dll_deployment()`
- Trigger: Any .exe output with GNU ABI (automatic)
- Detection: llvm-objdump -p (PE headers)
- Deployment: Hard links with fallback to shutil.copy2()
- Recursive: Scans transitive dependencies

**Manual Deployment** (for .dll files):
- Function: `post_link_dependency_deployment()`
- Trigger: `--deploy-dependencies` flag
- Same detection/deployment as automatic

### 4.2 Linux/macOS Shared Libraries (Partially Stubbed)

**Current State**:
- `_deploy_linux_so_dependencies()`: Placeholder, logs "not yet implemented"
- `_deploy_macos_dylib_dependencies()`: Placeholder, logs "not yet implemented"

**Supported Output Extensions** (already detected):
- Windows: `.exe`, `.dll`
- Linux: `.so`, `.so.*` (versioned libs like libfoo.so.1.2.3)
- macOS: `.dylib`

---

## 5. Windows DLL Deployment Integration Architecture

Understanding the Windows implementation helps design the Linux/macOS version.

### 5.1 Detection Method

**Primary**: `llvm-objdump -p` (parses PE import table)

```python
def detect_required_dlls(exe_path: Path, ...) -> set[str]:
    """
    1. Run llvm-objdump -p on exe_path
    2. Extract DLL names from PE import table
    3. Filter against MINGW_DLL_PATTERNS and SANITIZER_DLL_PATTERNS
    4. Recursively scan detected DLLs for their dependencies
    5. Fallback to HEURISTIC_MINGW_DLLS if llvm-objdump fails
    """
```

**Fallback**: `HEURISTIC_MINGW_DLLS` list

If llvm-objdump fails or times out, use a hardcoded list of common MinGW DLLs.

### 5.2 Key Functions

| Function | Purpose |
|----------|---------|
| `_is_deployable_dll()` | Filters DLLs based on regex patterns |
| `detect_required_dlls()` | Main detection with recursive scanning |
| `find_dll_in_toolchain()` | Locates DLL in MinGW sysroot |
| `_atomic_copy_dll()` | Hard link with copy fallback |
| `post_link_dll_deployment()` | Main deployment orchestrator |

### 5.3 Environment Variables

| Variable | Effect |
|----------|--------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` | Disable all library deployment |
| `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1` | Disable deployment for shared library outputs only |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` | Enable DEBUG logging |

### 5.4 Deployment Workflow

1. **Trigger**: Successful link (returncode 0) + output is .exe or (.dll with --deploy-dependencies)
2. **Detection**: Run llvm-objdump -p with 10-second timeout
3. **Filtering**: Apply MINGW_DLL_PATTERNS and exclude system DLLs
4. **Recursive Scan**: For each detected DLL, scan its dependencies
5. **Locate**: Find DLL in MinGW sysroot using architecture
6. **Deploy**: Hard link (preferred) or copy with atomic rename
7. **Timestamp Check**: Skip if destination is newer than source
8. **Error Handling**: Non-fatal warnings only, never fails build

---

## 6. Recommendations for Linux/macOS Integration

### 6.1 Immediate Integration Points

**In `execution/core.py`**, lines 304-313:

Currently:
```python
if platform_name == "windows":
    # Deploy DLLs
```

Proposed:
```python
if platform_name == "windows":
    # Deploy DLLs (keep existing)
elif platform_name == "linux" and deploy_dependencies_requested:
    _deploy_linux_so_dependencies(output_exe, ...)
elif platform_name == "darwin" and deploy_dependencies_requested:
    _deploy_macos_dylib_dependencies(output_exe, ...)
```

**Note**: Linux/macOS deployment should be **opt-in** via `--deploy-dependencies` flag initially (unlike Windows which auto-deploys .exe). This is conservative and mirrors the current pattern for .dll deployment.

### 6.2 New Deployment Module Structure

```
src/clang_tool_chain/deployment/
├── __init__.py
├── base_deployer.py       (NEW: abstract base class)
├── dll_deployer.py        (REFACTOR: inherit from base)
├── so_deployer.py         (NEW: Linux implementation)
└── dylib_deployer.py      (NEW: macOS implementation)
```

### 6.3 Detection Methods

**Linux**: Use `readelf -d` or `ldd`

```bash
# Direct dependencies (safe, no execution)
readelf -d /path/to/executable | grep NEEDED
# Output: (NEEDED) Shared library: [libunwind.so.1]

# Full dependency tree (shows transitive deps, but executes binary)
ldd /path/to/executable
# Output:
#   libunwind.so.1 => /usr/lib/x86_64-linux-gnu/libunwind.so.1
#   libc++.so.1 => /usr/lib/x86_64-linux-gnu/libc++.so.1
```

**macOS**: Use `otool -L`

```bash
otool -L /path/to/executable
# Output:
#   @rpath/libunwind.dylib (compatibility version 1.0.0)
#   /usr/lib/libc++.1.dylib (compatibility version 1.0.0)
```

### 6.4 Shared Library Locator

**Linux Search Paths**:
1. Toolchain lib directories (clang runtime)
2. `/usr/lib`, `/usr/lib64`
3. `/usr/local/lib`
4. RPATH/RUNPATH from ELF headers (as hints)

**macOS Search Paths**:
1. Toolchain lib directories
2. `/usr/local/lib`
3. `/opt/local/lib` (MacPorts)
4. `/opt/homebrew/lib` (Homebrew on ARM)
5. @rpath hints from dylib

**Filter Logic**:
- **Include**: libunwind, libc++, libc++abi, compiler-rt libs
- **Exclude**: glibc (libc.so.6), libpthread, libdl, libm (system libraries)
- **Exclude**: macOS frameworks (/System/Library/*)

### 6.5 Deployment Method

**Strategy**: Copy to executable directory (like Windows DLL deployment)

```python
def _atomic_copy_library(src: Path, dst: Path) -> None:
    """
    1. Check timestamps (skip if dst is newer)
    2. Try hard link (preferred - zero disk, instant)
    3. Fallback to copy with atomic rename (race-safe)
    """
```

**Symlink Handling** (Linux):

```python
# If libunwind.so.8 -> libunwind.so.8.0.1:
# 1. Copy libunwind.so.8.0.1 (real file)
# 2. Create symlink libunwind.so.8 -> libunwind.so.8.0.1
# 3. Create symlink libunwind.so -> libunwind.so.8 (if exists)
```

**install_name_tool** (macOS):

If dylib uses absolute paths, update to @loader_path:

```python
# Change:
#   /usr/local/lib/libunwind.dylib
# To:
#   @loader_path/libunwind.dylib
subprocess.run([
    "install_name_tool",
    "-change", "/usr/local/lib/libunwind.dylib",
    "@loader_path/libunwind.dylib",
    str(executable_path)
])
```

### 6.6 Environment Variable Pattern

Mirror Windows DLL deployment variables:

| Variable | Effect |
|----------|--------|
| `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` | Disable Linux/macOS deployment |
| `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` | Enable DEBUG logging |

**Note**: The unified `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` variable disables library deployment across all platforms.

### 6.7 Recursive Scanning

**Essential**: Handle transitive dependencies like Windows

Example dependency chain:
```
executable
  ├── libc++.so.1
  │     └── libunwind.so.1  (transitive)
  └── libunwind.so.1 (direct)
```

Algorithm:
1. Detect direct dependencies of executable
2. For each dependency, detect its dependencies (recursive)
3. De-duplicate (use set)
4. Filter system libraries at each level
5. Deploy all unique toolchain libraries

### 6.8 Opt-In vs Automatic

**Windows Current Behavior**:
- `.exe` files: **Automatic** deployment
- `.dll` files: **Opt-in** via `--deploy-dependencies`

**Linux/macOS Proposed Behavior**:
- Executables: **Opt-in** via `--deploy-dependencies` (conservative approach)
- `.so`/`.dylib` files: **Opt-in** via `--deploy-dependencies`

**Rationale**:
- Linux/macOS users are more familiar with system package managers
- Avoids surprising behavior changes
- Can make automatic in future release after user feedback

### 6.9 Platform Detection

**Already done** via `get_platform_info()`:

```python
from clang_tool_chain.platform_info import get_platform_info

platform_info = get_platform_info()
if platform_info.name == "linux":
    # Linux deployment
elif platform_info.name == "darwin":
    # macOS deployment
elif platform_info.name == "windows":
    # Windows deployment
```

### 6.10 Error Handling

**Non-Fatal Design** (mirror Windows):

```python
try:
    deploy_shared_libraries(...)
except Exception as e:
    logger.warning(f"Failed to deploy shared libraries: {e}")
    # Build succeeds even if deployment fails
```

**Rationale**:
- Deployment is a convenience feature, not required for compilation
- Users can manually set LD_LIBRARY_PATH or install system packages
- Errors logged but don't break CI/CD pipelines

### 6.11 Timestamp Checking

**Optimization** (reuse Windows logic):

```python
def should_deploy(src: Path, dst: Path) -> bool:
    """
    Returns True if dst doesn't exist or src is newer.
    Skips deployment if dst is up-to-date.
    """
    if not dst.exists():
        return True
    return src.stat().st_mtime > dst.stat().st_mtime
```

**Performance Impact**: ~5ms timestamp check vs ~40ms copy

---

## Summary

### Current State

✅ **Ready for Extension**:
- Deployment hooks in place (`execution/core.py`)
- Output path extraction supports `.so` and `.dylib`
- Argument transformation pipeline ready
- Error handling patterns established
- Test framework exists (`test_dll_deployment.py` as model)
- Environment variable control pattern established
- libunwind already recognized and used

❌ **Missing Implementation**:
- Linux `.so` detection and deployment
- macOS `.dylib` detection and deployment
- Cross-platform base class abstraction
- Tests for Linux/macOS deployment
- Documentation for new features

### Integration Strategy

1. **Phase 3.1**: Extract common base class from `dll_deployer.py`
2. **Phase 3.2**: Implement `so_deployer.py` (Linux)
3. **Phase 3.3**: Implement `dylib_deployer.py` (macOS)
4. **Phase 3.4**: Create factory pattern for platform selection
5. **Phase 3.5**: Integrate into `execution/core.py` (lines 304-313, etc.)

### Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Opt-in deployment (--deploy-dependencies) | Conservative, matches current .dll behavior |
| Copy to executable directory | Simple, portable, mirrors Windows |
| Recursive dependency scanning | Essential for transitive deps (e.g., libc++ → libunwind) |
| Non-fatal error handling | Deployment is convenience, not requirement |
| Timestamp optimization | Avoid redundant copies on rebuild |
| Hard link preferred | Zero disk space, instant (when supported) |

### Next Steps

With Phase 1 analysis complete, **Phase 2 (Design)** can now begin:
- Use findings from Agent 1.1, 1.2, 1.3, 1.4
- Design cross-platform abstraction layer
- Create detailed API design
- Plan integration points
- Design testing strategy

---

**End of Report**
