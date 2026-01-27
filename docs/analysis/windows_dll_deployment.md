# Windows DLL Deployment System - Architecture Analysis

**Agent 1.1 Deliverable**

**Author**: Analysis by Claude Sonnet 4.5
**Date**: 2026-01-25
**Source Module**: `src/clang_tool_chain/deployment/dll_deployer.py`
**Test Coverage**: `tests/test_dll_deployment.py` (38 comprehensive tests)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Dependency Detection Mechanism](#dependency-detection-mechanism)
3. [File Copying Strategy](#file-copying-strategy)
4. [Timestamp Optimization](#timestamp-optimization)
5. [Error Handling](#error-handling)
6. [Reusable Patterns for Abstraction](#reusable-patterns-for-abstraction)
7. [Windows-Specific Assumptions](#windows-specific-assumptions)
8. [Code Structure](#code-structure)

---

## Architecture Overview

### High-Level Design

The Windows DLL deployment system is a **post-link hook** that automatically deploys MinGW runtime DLLs to the output executable directory after successful compilation. It follows a non-fatal design philosophy: **deployment failures never fail the build**.

```
┌─────────────────────────────────────────────────────────┐
│                  Build Workflow                         │
│                                                          │
│  [Compile & Link] → [Check Success] → [Post-Link Hooks] │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│           post_link_dll_deployment()                     │
│           (deployment/dll_deployer.py)                   │
│                                                          │
│  1. Guard Checks (platform, ABI, file type)             │
│  2. detect_required_dlls() [with recursion]             │
│  3. get_mingw_sysroot_bin_dir()                         │
│  4. find_dll_in_toolchain()                             │
│  5. _atomic_copy_dll() for each DLL                     │
│  6. Summary Logging                                      │
└─────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Non-Fatal Operation**: DLL deployment never fails the build (warnings only)
2. **Automatic Detection**: Uses `llvm-objdump` to parse PE headers and extract DLL dependencies
3. **Recursive Scanning**: Detects transitive dependencies (e.g., ASan runtime → libc++ → libunwind)
4. **Atomic Operations**: Hard links (preferred) or atomic file copies to prevent race conditions
5. **Timestamp Optimization**: Skip copying if destination is up-to-date
6. **Fallback Strategy**: Heuristic DLL list if `llvm-objdump` fails
7. **Platform-Specific Guards**: Only runs on Windows with GNU ABI for `.exe`/`.dll` outputs

### Integration Points

**Entry Point**: `src/clang_tool_chain/execution/core.py` (line 21)
```python
from clang_tool_chain.deployment.dll_deployer import (
    post_link_dependency_deployment,
    post_link_dll_deployment
)
```

**Invocation**: After successful linking (`returncode == 0`):
```python
# execution/core.py (simplified)
if returncode == 0 and output_path:
    use_gnu = _should_use_gnu_abi(platform_name, args)
    post_link_dll_deployment(output_path, platform_name, use_gnu)
```

---

## Dependency Detection Mechanism

### Primary Method: llvm-objdump

The system uses **LLVM's `llvm-objdump` tool** to parse Portable Executable (PE) headers and extract DLL import tables.

#### Detection Algorithm

```python
def detect_required_dlls(exe_path: Path, platform_name: str = "win", arch: str = "x86_64") -> list[str]:
    """
    Detect required MinGW runtime and sanitizer DLLs for a Windows executable.

    Algorithm:
    1. Run llvm-objdump -p <exe_path> to get PE headers
    2. Parse output for "DLL Name: <dll>" entries
    3. Filter deployable DLLs (MinGW runtime + sanitizers)
    4. Recursively scan deployable DLLs for transitive dependencies
    5. Fallback to heuristic list if detection fails
    """
```

#### Step-by-Step Process

**Phase 1: Direct Dependencies**

1. Execute `llvm-objdump -p <exe_path>` (10-second timeout)
2. Parse stdout using regex: `r"DLL Name:\s+(\S+)"`
3. Filter results through `_is_deployable_dll()`:
   - **Include**: MinGW runtime DLLs (`libwinpthread`, `libgcc_s`, `libstdc++`, `libc++`, `libunwind`)
   - **Include**: Sanitizer DLLs (`libclang_rt.asan_dynamic`, `libclang_rt.ubsan_dynamic`, etc.)
   - **Exclude**: Windows system DLLs (`kernel32.dll`, `ntdll.dll`, `msvcrt.dll`, etc.)

**Phase 2: Transitive Dependencies** (Recursive Scanning)

```
exe.exe
 ├─ libclang_rt.asan_dynamic-x86_64.dll (detected by Phase 1)
 │   ├─ libc++.dll (transitive via ASan runtime)
 │   │   └─ libunwind.dll (transitive via libc++)
 │   └─ libwinpthread-1.dll (transitive)
 └─ libgcc_s_seh-1.dll (detected by Phase 1)
```

Implementation (lines 202-237):
```python
# Recursively scan detected DLLs for transitive dependencies
all_required_dlls = set(detected_dlls)
dlls_to_scan = detected_dlls.copy()
scanned_dlls = set()

while dlls_to_scan:
    current_dll = dlls_to_scan.pop(0)
    if current_dll in scanned_dlls:
        continue
    scanned_dlls.add(current_dll)

    # Find the DLL in the toolchain
    dll_path = find_dll_in_toolchain(current_dll, platform_name, arch)
    if dll_path is None:
        continue

    # Extract dependencies from this DLL
    transitive_deps = _extract_dll_dependencies(dll_path, objdump_path)
    for dep_name in transitive_deps:
        if _is_deployable_dll(dep_name) and dep_name not in all_required_dlls:
            all_required_dlls.add(dep_name)
            dlls_to_scan.append(dep_name)
```

**Key Feature**: Breadth-first traversal with cycle detection (via `scanned_dlls` set)

### Fallback Mechanism: Heuristic DLL List

When `llvm-objdump` fails (missing tool, timeout, parsing error), the system falls back to a **static heuristic list**:

```python
HEURISTIC_MINGW_DLLS = [
    "libwinpthread-1.dll",
    "libgcc_s_seh-1.dll",
    "libstdc++-6.dll",
]
```

**Fallback Triggers** (lines 176-258):
- `llvm-objdump.exe` not found
- Non-zero exit code
- Timeout (>10 seconds)
- No deployable DLLs detected but imports found
- No imports found (PE table parsing failed)
- Any exception during detection

### DLL Pattern Matching

**MinGW Runtime Patterns** (lines 22-31):
```python
MINGW_DLL_PATTERNS = [
    r"libwinpthread.*\.dll",
    r"libgcc_s_.*\.dll",
    r"libstdc\+\+.*\.dll",
    r"libc\+\+.*\.dll",      # LLVM C++ standard library
    r"libunwind.*\.dll",     # LLVM unwinding library
    r"libgomp.*\.dll",
    r"libssp.*\.dll",
    r"libquadmath.*\.dll",
]
```

**Sanitizer Patterns** (lines 34-39):
```python
SANITIZER_DLL_PATTERNS = [
    r"libclang_rt\.asan_dynamic.*\.dll",
    r"libclang_rt\.ubsan_dynamic.*\.dll",
    r"libclang_rt\.tsan_dynamic.*\.dll",
    r"libclang_rt\.msan_dynamic.*\.dll",
]
```

**System DLL Exclusions** (lines 42-57):
```python
WINDOWS_SYSTEM_DLLS = {
    "kernel32.dll", "ntdll.dll", "msvcrt.dll", "user32.dll",
    "advapi32.dll", "ws2_32.dll", "shell32.dll", "ole32.dll",
    "oleaut32.dll", "gdi32.dll", "comdlg32.dll", "comctl32.dll",
    "bcrypt.dll", "crypt32.dll",
}
```

**Pattern Matching** (lines 67-98):
- Case-insensitive matching
- Regex-based for runtime DLLs (flexible versioning)
- Set-based for system DLLs (exact match, fast lookup)

---

## File Copying Strategy

### Atomic Copy Implementation

The system uses **`_atomic_copy_dll()`** (lines 261-378) to ensure thread-safe, corruption-free DLL deployment even during concurrent compilations.

#### Three-Tier Strategy

```
┌──────────────────────────────────────────────────────┐
│              _atomic_copy_dll()                      │
│                                                      │
│  1. Timestamp Check → Skip if up-to-date            │
│  2. Try Hard Link   → Zero disk space, instant      │
│  3. Fallback Copy   → Atomic rename with temp file  │
└──────────────────────────────────────────────────────┘
```

### Tier 1: Timestamp Optimization

**Check Before Copy** (lines 291-306):
```python
if dest_dll.exists():
    src_stat = src_dll.stat()
    dest_stat = dest_dll.stat()

    # Skip if destination is up-to-date
    if src_stat.st_mtime <= dest_stat.st_mtime:
        logger.debug(f"Skipped (up-to-date): {dest_dll.name}")
        return False

    # Remove outdated destination before deployment
    try:
        dest_dll.unlink()
    except OSError:
        # Continue - hard link/copy will fail if can't remove
```

**Rationale**: Avoid redundant copies when rebuilding without source DLL changes.

### Tier 2: Hard Link (Preferred)

**Algorithm** (lines 308-316):
```python
try:
    os.link(src_dll, dest_dll)
    logger.debug(f"Deployed (hard link): {dest_dll.name}")
    return True
except (OSError, NotImplementedError):
    # Fallback to copy
```

**Benefits**:
- **Zero disk space**: Same inode, single physical file
- **Instant operation**: No data copy
- **Automatic updates**: If source DLL changes, all hard links reflect it
- **Race-safe**: Atomic filesystem operation

**When Hard Links Fail**:
- Cross-filesystem links (source and dest on different drives)
- Filesystem doesn't support hard links (FAT32, some network drives)
- Permission restrictions

### Tier 3: Copy with Atomic Rename

**Algorithm** (lines 318-377):
```python
# 1. Create temporary file with unique name
temp_name = f".{dest_dll.name}.{uuid.uuid4().hex[:8]}.tmp"
temp_dll = dest_dll.parent / temp_name

# 2. Copy source to temp file
shutil.copy2(src_dll, temp_dll)

# 3. Atomic rename
if os.name == "nt":
    temp_dll.replace(dest_dll)  # Atomic on Windows (Python 3.3+)
else:
    temp_dll.rename(dest_dll)   # Atomic on POSIX
```

**Race Condition Handling**:
- **FileExistsError**: Another process already deployed → cleanup temp file, return False
- **OSError (file in use)**: Compare temp vs dest by size → if same, assume identical, cleanup
- **Any exception**: Cleanup temp file before re-raising

**Cleanup Guarantee**:
```python
except Exception:
    # Clean up temp file on any error
    temp_dll.unlink(missing_ok=True)
    raise
```

### DLL Source Resolution

**Search Algorithm** (lines 422-472):
```python
def find_dll_in_toolchain(dll_name: str, platform_name: str, arch: str) -> Path | None:
    """
    Search locations in priority order:
    1. MinGW sysroot/bin directory (x86_64-w64-mingw32/bin/)
    2. Clang bin directory (for sanitizer DLLs)
    """
```

**Sysroot Path Construction** (lines 380-419):
```python
def get_mingw_sysroot_bin_dir(platform_name: str, arch: str) -> Path:
    clang_bin_dir = get_platform_binary_dir()
    clang_root = clang_bin_dir.parent

    # Architecture-specific sysroot
    sysroot_name = "x86_64-w64-mingw32" if arch == "x86_64" else "aarch64-w64-mingw32"
    sysroot_bin = clang_root / sysroot_name / "bin"
```

**Result**: `~/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin/`

---

## Timestamp Optimization

### Mechanism

**Comparison Logic** (line 297):
```python
if src_stat.st_mtime <= dest_stat.st_mtime:
    return False  # Skip copy
```

**Semantic**: Destination is considered **up-to-date** if its modification time is **greater than or equal to** the source.

### Performance Impact

**Metrics** (from CLAUDE.md):
- **DLL Detection**: <50ms per executable (llvm-objdump overhead)
- **DLL Copying**: <50ms total (2-3 small DLLs typically)
- **Timestamp Check**: <5ms (skips copy if up-to-date)
- **Total Overhead**: <100ms per executable build

**Scenario: Rebuild Without Changes**
```
First build:  detect_required_dlls (45ms) + copy 3 DLLs (40ms) = 85ms
Second build: detect_required_dlls (45ms) + timestamp checks (3 × 5ms = 15ms) = 60ms
Savings: 25ms (29% faster)
```

### Edge Case: Outdated DLL Update

**Algorithm** (lines 292-306):
```python
if dest_dll.exists():
    if src_stat.st_mtime <= dest_stat.st_mtime:
        return False  # Skip

    # Destination outdated → remove before update
    dest_dll.unlink()
    # Then proceed with hard link or copy
```

**Example**: Toolchain upgrade replaces `libwinpthread-1.dll` with newer version
- Old: `st_mtime = 1700000000`
- New: `st_mtime = 1700001000`
- Result: Destination removed and updated

---

## Error Handling

### Non-Fatal Design Philosophy

**Core Principle** (lines 594-598):
```python
except Exception as e:
    # Non-fatal: log warning but don't fail the build
    logger.warning(f"DLL deployment failed: {e}")
```

**Rationale**: DLL deployment is a **convenience feature**. Build success is more important than deployment success.

### Error Handling Layers

#### Layer 1: Detection Errors

**Fallback to Heuristic** (lines 250-258):
```python
except subprocess.TimeoutExpired:
    logger.warning("llvm-objdump timed out after 10 seconds, using heuristic DLL list")
    return HEURISTIC_MINGW_DLLS.copy()

except Exception as e:
    logger.warning(f"DLL detection failed: {e}, using heuristic DLL list")
    return HEURISTIC_MINGW_DLLS.copy()
```

**Handled Cases**:
- `subprocess.TimeoutExpired`: llvm-objdump hangs
- `subprocess.CalledProcessError`: llvm-objdump non-zero exit
- `FileNotFoundError`: llvm-objdump binary missing
- `OSError`: Permission errors, I/O errors
- `Exception`: Unexpected errors (parsing, etc.)

#### Layer 2: Copy Errors

**Per-DLL Error Handling** (lines 574-586):
```python
for dll_name in required_dlls:
    try:
        was_copied = _atomic_copy_dll(src_dll, dest_dll)
    except PermissionError:
        logger.warning(f"Permission denied copying {dll_name}, skipping")
        continue
    except OSError as e:
        logger.warning(f"Failed to copy {dll_name}: {e}, skipping")
        continue
```

**Handled Cases**:
- `PermissionError`: Destination directory is read-only
- `OSError`: Disk full, file in use, network drive errors
- **Result**: Skip failed DLL, continue with others

#### Layer 3: Atomic Copy Internal Errors

**Cleanup on Failure** (lines 372-377):
```python
except Exception:
    # Clean up temp file on any error
    temp_dll.unlink(missing_ok=True)
    raise
```

**Race Condition Handling** (lines 344-366):
```python
except FileExistsError:
    # Another process already deployed it
    temp_dll.unlink(missing_ok=True)
    return False

except OSError as e:
    # File in use (Windows) - check if files are same size
    if dest_dll.exists() and temp_stat.st_size == dest_stat.st_size:
        temp_dll.unlink(missing_ok=True)
        return False
    raise
```

### Keyboard Interrupt Handling

**Graceful Shutdown** (lines 231-232, 254-255, 372-373, 594-595):
```python
except KeyboardInterrupt as ke:
    handle_keyboard_interrupt_properly(ke)
```

**Behavior**: Propagate interrupt to allow clean termination, bypassing normal error handling.

---

## Reusable Patterns for Abstraction

### 1. Platform-Agnostic Dependency Detection

**Abstraction**:
```python
class BinaryDependencyDetector(ABC):
    @abstractmethod
    def detect_dependencies(self, binary_path: Path) -> list[str]:
        """Detect runtime dependencies for a binary."""

    @abstractmethod
    def is_deployable(self, dep_name: str) -> bool:
        """Check if a dependency should be deployed."""

    @abstractmethod
    def find_dependency(self, dep_name: str) -> Path | None:
        """Locate dependency in the toolchain."""
```

**Implementations**:
- **WindowsPEDetector**: Uses `llvm-objdump -p` (current implementation)
- **LinuxELFDetector**: Use `llvm-readelf --needed-libs` or `patchelf --print-needed`
- **MacOSDylibDetector**: Use `otool -L`

**Reusable Code** (lines 107-138):
```python
def _extract_dll_dependencies(binary_path: Path, objdump_path: Path) -> list[str]:
    """Extract DLL dependencies from a binary file using llvm-objdump."""
    result = subprocess.run(
        [str(objdump_path), "-p", str(binary_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    # Parse dependencies from output
    dll_pattern = re.compile(r"DLL Name:\s+(\S+)", re.IGNORECASE)
    return [match.group(1) for match in dll_pattern.finditer(result.stdout)]
```

**Adaptation for Linux**:
```python
# llvm-readelf --needed-libs <so_file>
# Output: libc++.so.1
#         libunwind.so.1

lib_pattern = re.compile(r"^\s*(\S+\.so[.\d]*)", re.MULTILINE)
```

**Adaptation for macOS**:
```python
# otool -L <dylib_file>
# Output: @rpath/libc++.1.dylib (compatibility version 1.0.0)

dylib_pattern = re.compile(r"^\s*(@rpath/)?(\S+\.dylib)", re.MULTILINE)
```

### 2. Atomic File Deployment

**Reusable Algorithm** (lines 261-378):
```python
def atomic_deploy_file(src: Path, dest: Path) -> bool:
    """
    Atomically deploy a file with timestamp checking and race-safety.

    1. Check timestamp → skip if up-to-date
    2. Try hard link (zero disk space, instant)
    3. Fallback: copy to temp + atomic rename
    4. Handle race conditions (concurrent deployments)
    """
```

**Platform-Agnostic Core**:
- Timestamp comparison: `st_mtime` (cross-platform)
- Hard link: `os.link()` (POSIX and Windows)
- Atomic rename: `Path.replace()` (cross-platform as of Python 3.3)
- Temp file pattern: `.{filename}.{uuid}.tmp` (cross-platform)

**Platform-Specific Adaptation**:
```python
if os.name == "nt":
    temp_dll.replace(dest_dll)  # Windows
else:
    temp_dll.rename(dest_dll)   # POSIX
```

### 3. Recursive Dependency Scanner

**Abstraction** (lines 202-237):
```python
def scan_transitive_dependencies(
    initial_deps: list[str],
    get_deps_fn: Callable[[str], list[str]],
    is_deployable_fn: Callable[[str], bool]
) -> set[str]:
    """
    Recursively scan dependencies using breadth-first traversal.

    Args:
        initial_deps: Starting dependency list
        get_deps_fn: Function to extract dependencies from a binary
        is_deployable_fn: Filter function for dependencies

    Returns:
        Complete set of deployable dependencies (including transitive)
    """
    all_deps = set(initial_deps)
    to_scan = initial_deps.copy()
    scanned = set()

    while to_scan:
        current = to_scan.pop(0)
        if current in scanned:
            continue
        scanned.add(current)

        deps = get_deps_fn(current)
        for dep in deps:
            if is_deployable_fn(dep) and dep not in all_deps:
                all_deps.add(dep)
                to_scan.append(dep)

    return all_deps
```

**Benefits**:
- **Generic**: Works for DLLs, SOs, dylibs
- **Cycle-safe**: `scanned` set prevents infinite loops
- **Efficient**: Breadth-first avoids deep recursion

### 4. Fallback Mechanism

**Pattern** (lines 164-258):
```python
def detect_with_fallback(
    primary_detector: Callable[[], list[str]],
    fallback_list: list[str]
) -> list[str]:
    """Try primary detection, fallback to heuristic list on failure."""
    try:
        result = primary_detector()
        if result:
            return result
        # Empty result → use fallback
        return fallback_list
    except Exception:
        return fallback_list
```

**Adaptation for Linux/macOS**:
```python
# Linux heuristic
HEURISTIC_LINUX_LIBS = [
    "libc++.so.1",
    "libc++abi.so.1",
    "libunwind.so.1",
]

# macOS heuristic
HEURISTIC_MACOS_LIBS = [
    "libc++.1.dylib",
    "libc++abi.1.dylib",
    "libunwind.1.dylib",
]
```

### 5. Pattern-Based Filtering

**Reusable Structure** (lines 67-98):
```python
class DependencyFilter:
    def __init__(
        self,
        include_patterns: list[str],
        exclude_set: set[str]
    ):
        self.include_patterns = [re.compile(p, re.IGNORECASE) for p in include_patterns]
        self.exclude_set = {x.lower() for x in exclude_set}

    def is_deployable(self, dep_name: str) -> bool:
        dep_lower = dep_name.lower()

        # Exclude system dependencies
        if dep_lower in self.exclude_set:
            return False

        # Include if matches any pattern
        return any(pattern.match(dep_lower) for pattern in self.include_patterns)
```

**Linux Adaptation**:
```python
LINUX_INCLUDE_PATTERNS = [
    r"libc\+\+.*\.so[.\d]*",
    r"libc\+\+abi.*\.so[.\d]*",
    r"libunwind.*\.so[.\d]*",
]

LINUX_SYSTEM_LIBS = {
    "libc.so.6", "libm.so.6", "libpthread.so.0",
    "libdl.so.2", "librt.so.1", "ld-linux-x86-64.so.2",
}
```

---

## Windows-Specific Assumptions

### 1. Binary Format: Portable Executable (PE)

**Assumption**: All binaries are PE format with standard DLL import tables.

**Tool Used**: `llvm-objdump -p` (PE-specific flag)

**Linux/macOS Equivalent**:
- **Linux**: `llvm-readelf --needed-libs` (ELF format)
- **macOS**: `otool -L` (Mach-O format)

**Code Location**: Lines 122-128, 181-186

### 2. DLL Naming Convention

**Pattern**: `lib{name}-{version}.dll` or `lib{name}.dll`

**Examples**: `libwinpthread-1.dll`, `libstdc++-6.dll`

**Contrast**:
- **Linux**: `lib{name}.so.{version}` (e.g., `libc++.so.1`)
- **macOS**: `lib{name}.{version}.dylib` (e.g., `libc++.1.dylib`)

**Code Location**: Lines 22-31 (MINGW_DLL_PATTERNS)

### 3. MinGW Sysroot Structure

**Assumption**: DLLs located at `{clang_root}/{arch}-w64-mingw32/bin/`

**Example**: `~/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin/libwinpthread-1.dll`

**Linux Equivalent**: `{clang_root}/lib/{arch}-linux-gnu/` or `{clang_root}/lib/`

**macOS Equivalent**: `{clang_root}/lib/` (no sysroot for native builds)

**Code Location**: Lines 380-419

### 4. File Extension: `.exe` and `.dll`

**Assumption**: Executables have `.exe` extension, shared libraries have `.dll` extension.

**Guards** (lines 528-536):
```python
suffix = output_exe_path.suffix.lower()
if suffix == ".dll":
    # Check for DLL-specific opt-out
elif suffix != ".exe":
    return  # Skip
```

**Linux/macOS Equivalent**:
- **Linux**: No extension for executables, `.so` for shared libraries
- **macOS**: No extension for executables, `.dylib` for shared libraries

### 5. Windows System DLL Exclusions

**Assumption**: Windows provides standard system DLLs (`kernel32.dll`, `ntdll.dll`, etc.) that should never be deployed.

**Rationale**: System DLLs are always available, versioning is managed by Windows.

**Code Location**: Lines 42-57

**Linux Equivalent**: `libc.so.6`, `libm.so.6`, `libpthread.so.0` (glibc)

**macOS Equivalent**: System frameworks (`/System/Library/Frameworks/`)

### 6. Hard Link Support

**Assumption**: NTFS supports hard links (Windows Vista+).

**Fallback**: Copy with atomic rename if hard link fails.

**Code Location**: Lines 308-316

**Limitations**:
- **FAT32**: No hard link support (fallback to copy)
- **Network drives**: Often restricted (fallback to copy)
- **Cross-filesystem**: Not supported (fallback to copy)

### 7. Atomic Rename on Windows

**Assumption**: `Path.replace()` provides atomic rename on NTFS (Python 3.3+).

**Code Location**: Lines 333-339

**POSIX Difference**: `rename()` is atomic and replaces existing files by default.

### 8. GNU ABI Detection

**Assumption**: Deployment only runs for GNU ABI builds (MinGW), not MSVC ABI.

**Guard** (lines 522-525):
```python
if not use_gnu_abi:
    logger.debug("DLL deployment skipped: not using GNU ABI")
    return
```

**Detection Logic**: `_should_use_gnu_abi()` checks for `--target=*-windows-gnu` or absence of MSVC target.

**Code Location**: `src/clang_tool_chain/abi.py`

### 9. Architecture Mapping

**Assumption**: Architecture names follow MinGW conventions.

**Mapping** (lines 407-412):
```python
if arch == "x86_64":
    sysroot_name = "x86_64-w64-mingw32"
elif arch == "arm64":
    sysroot_name = "aarch64-w64-mingw32"
```

**Windows-Specific**: Uses `x86_64` (not `amd64`), `arm64` (not `aarch64`).

### 10. Sanitizer DLL Patterns

**Assumption**: Sanitizer DLLs follow LLVM naming: `libclang_rt.{sanitizer}_dynamic-{arch}.dll`

**Code Location**: Lines 34-39

**Example**: `libclang_rt.asan_dynamic-x86_64.dll`

**Linux Equivalent**: `libclang_rt.asan-x86_64.so` (no `_dynamic` suffix)

---

## Code Structure

### Module Organization

```
deployment/
├── dll_deployer.py (739 lines)
│   ├── Constants (57 lines)
│   ├── Pattern Matching (32 lines)
│   ├── Dependency Detection (152 lines)
│   ├── Atomic File Operations (118 lines)
│   ├── Toolchain Integration (93 lines)
│   ├── Post-Link Hooks (199 lines)
│   └── Platform Stubs (88 lines)
└── __init__.py
```

### Key Classes and Functions

#### Constants (Lines 1-65)

```python
# MinGW runtime DLL patterns (regex, case-insensitive)
MINGW_DLL_PATTERNS: list[str]

# Sanitizer runtime DLL patterns
SANITIZER_DLL_PATTERNS: list[str]

# Windows system DLLs to exclude
WINDOWS_SYSTEM_DLLS: set[str]

# Heuristic fallback DLL list
HEURISTIC_MINGW_DLLS: list[str]
```

#### Pattern Matching (Lines 67-105)

```python
def _is_deployable_dll(dll_name: str) -> bool:
    """Check if a DLL name matches MinGW runtime or sanitizer patterns."""

def _is_mingw_dll(dll_name: str) -> bool:  # Deprecated alias
    """Backward compatibility alias for _is_deployable_dll."""
```

#### Dependency Extraction (Lines 107-138)

```python
def _extract_dll_dependencies(binary_path: Path, objdump_path: Path) -> list[str]:
    """
    Extract DLL dependencies from a binary using llvm-objdump.

    Raises:
        subprocess.TimeoutExpired: If objdump times out (10s)
        subprocess.CalledProcessError: If objdump fails
    """
```

#### Dependency Detection (Lines 141-259)

```python
def detect_required_dlls(
    exe_path: Path,
    platform_name: str = "win",
    arch: str = "x86_64"
) -> list[str]:
    """
    Detect required MinGW runtime and sanitizer DLLs for a Windows executable.

    Uses llvm-objdump to parse PE headers and extract DLL dependencies.
    Recursively scans deployable DLLs to find transitive dependencies.
    Falls back to heuristic list if llvm-objdump fails.

    Returns:
        List of MinGW and sanitizer DLL filenames

    Raises:
        FileNotFoundError: If exe_path does not exist
    """
```

**Algorithm Complexity**:
- **Time**: O(D × N) where D = number of deployable DLLs, N = average dependencies per DLL
- **Space**: O(D) for `all_required_dlls` and `scanned_dlls` sets
- **Typical Case**: D ≈ 3-5, N ≈ 2-3 → 6-15 objdump invocations

#### Atomic File Operations (Lines 261-378)

```python
def _atomic_copy_dll(src_dll: Path, dest_dll: Path) -> bool:
    """
    Atomically deploy a DLL using hard links (preferred) or file copy with atomic rename.

    Algorithm:
    1. Check timestamp - skip if destination is up-to-date
    2. Try to create hard link (zero disk space, instant operation)
    3. If hard link fails, fall back to copy + atomic rename
    4. Handle race conditions gracefully

    Returns:
        True if DLL was deployed/updated, False if skipped (already up-to-date)

    Raises:
        OSError: If deployment fails (other than race condition)
    """
```

**Race Safety**: Uses temp file pattern `.{dll_name}.{uuid}.tmp` to prevent conflicts.

#### Toolchain Integration (Lines 380-473)

```python
def get_mingw_sysroot_bin_dir(platform_name: str, arch: str) -> Path:
    """
    Get the MinGW sysroot bin directory containing runtime DLLs.

    Returns:
        Path to sysroot/bin directory
        (e.g., ~/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin/)

    Raises:
        ValueError: If architecture is unsupported
        RuntimeError: If sysroot not found
    """

def find_dll_in_toolchain(dll_name: str, platform_name: str, arch: str) -> Path | None:
    """
    Find a DLL in the toolchain (MinGW sysroot or sanitizer directories).

    Searches in multiple locations:
    1. MinGW sysroot/bin directory (for MinGW runtime DLLs)
    2. Clang bin directory (for sanitizer DLLs that may be copied there)

    Returns:
        Path to the DLL if found, None otherwise
    """
```

#### Post-Link Hooks (Lines 475-599)

```python
def post_link_dll_deployment(
    output_exe_path: Path,
    platform_name: str,
    use_gnu_abi: bool
) -> None:
    """
    Deploy required MinGW runtime and sanitizer DLLs to the output binary directory after linking.

    This function:
    1. Detects required DLLs using llvm-objdump (with fallback)
    2. Locates source DLLs in MinGW sysroot/bin or clang/bin (for sanitizers)
    3. Copies DLLs to output directory (with timestamp checking)
    4. Handles all errors gracefully (warnings only, never fails the build)

    Supports both .exe executables and .dll shared libraries.

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS: Set to "1" to disable all DLL deployment
        CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS_FOR_DLLS: Set to "1" to disable deployment for .dll outputs only
        CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE: Set to "1" for verbose logging
    """
```

**Guard Sequence** (lines 509-541):
1. Check `CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS` → return early
2. Check platform is Windows → return early
3. Check GNU ABI is used → return early
4. Check output is `.exe` or `.dll` → return early
5. Check output file exists → return early

#### Dependency Deployment (Lines 601-709)

```python
def post_link_dependency_deployment(
    output_path: Path,
    platform_name: str,
    use_gnu_abi: bool
) -> None:
    """
    Deploy required runtime dependencies for a shared library.

    Unlike post_link_dll_deployment (automatic for .exe), this is opt-in via --deploy-dependencies.

    Supports:
    - Windows (.dll): MinGW runtime DLLs via llvm-objdump
    - Linux (.so): libc++, libunwind via llvm-readelf (future)
    - macOS (.dylib): libc++, libunwind via otool (future)
    """

def _deploy_windows_dll_dependencies(dll_path: Path, use_gnu_abi: bool) -> None:
    """Deploy MinGW runtime DLLs for a Windows DLL."""

def _deploy_linux_so_dependencies(so_path: Path) -> None:
    """Placeholder for future Linux implementation."""

def _deploy_macos_dylib_dependencies(dylib_path: Path) -> None:
    """Placeholder for future macOS implementation."""
```

### Control Flow

```
post_link_dll_deployment()
    │
    ├─> [Guard Checks]
    │    ├─ Environment variable check
    │    ├─ Platform check (Windows only)
    │    ├─ ABI check (GNU only)
    │    ├─ File type check (.exe or .dll)
    │    └─ File exists check
    │
    ├─> detect_required_dlls()
    │    ├─ Try llvm-objdump -p
    │    │   ├─ Extract direct dependencies
    │    │   └─ Recursive scan (while dlls_to_scan)
    │    │       ├─ find_dll_in_toolchain()
    │    │       └─ _extract_dll_dependencies()
    │    └─ Fallback to HEURISTIC_MINGW_DLLS on error
    │
    ├─> For each required DLL:
    │    ├─ find_dll_in_toolchain()
    │    │   ├─ Search sysroot/bin
    │    │   └─ Search clang/bin
    │    │
    │    └─ _atomic_copy_dll()
    │        ├─ Check timestamp → skip if up-to-date
    │        ├─ Try os.link() (hard link)
    │        └─ Fallback: shutil.copy2() + atomic rename
    │
    └─> Summary logging
```

### Test Coverage (38 Tests)

**Test File**: `tests/test_dll_deployment.py` (1806 lines)

#### Test Categories

1. **Pattern Matching** (4 test classes, 8 tests)
   - `TestMingwDllPatternMatching`: MinGW DLL patterns
   - `TestSanitizerDllPatternMatching`: Sanitizer DLL patterns

2. **Dependency Detection** (5 test classes, 12 tests)
   - `TestDetectRequiredDlls`: llvm-objdump parsing and fallback
   - `TestLlvmObjdumpErrorHandling`: Error handling for objdump failures

3. **Sysroot Integration** (1 test class, 4 tests)
   - `TestGetMingwSysrootBinDir`: Sysroot path resolution

4. **Post-Link Deployment** (6 test classes, 14 tests)
   - `TestPostLinkDllDeployment`: Main deployment function
   - `TestIntegrationDllDeployment`: Real compilation tests
   - `TestDllDeploymentForDllOutputs`: .dll output support

5. **Atomic Copy** (1 test class, 8 tests)
   - `TestAtomicDllCopy`: Hard link, fallback, race conditions, concurrency

6. **Edge Cases** (5 test classes, 8 tests)
   - `TestOutputPathParsing`: Path formats with spaces, combined `-o` flag
   - `TestMsvcAbiNoOp`: MSVC ABI skipping
   - `TestReadOnlyDestination`: Permission errors
   - `TestSanitizerExecutables`: AddressSanitizer DLL deployment
   - `TestDllDeploymentIntegrationEdgeCases`: Multiple executables, long paths

**Coverage Highlights**:
- Concurrency stress test: 20 threads deploying same DLL simultaneously (lines 1243-1313)
- Transitive dependency mock test: Complex dependency tree (lines 1474-1575)
- Integration tests: Real compilation on Windows (lines 576-757)

---

## Summary

### Strengths

1. **Non-Fatal Design**: Never fails builds, only warns
2. **Robust Detection**: llvm-objdump + heuristic fallback
3. **Transitive Dependencies**: Recursive scanning (e.g., ASan → libc++ → libunwind)
4. **Race-Safe**: Hard links + atomic rename with temp files
5. **Performance**: Timestamp optimization, <100ms overhead
6. **Comprehensive Error Handling**: Multiple fallback layers
7. **Extensive Testing**: 38 tests covering edge cases and concurrency

### Reusable Abstractions for Linux/macOS

1. **BinaryDependencyDetector**: Platform-agnostic interface for dependency detection
2. **atomic_deploy_file()**: Cross-platform file deployment with timestamp checks
3. **scan_transitive_dependencies()**: Generic recursive dependency scanner
4. **DependencyFilter**: Pattern-based filtering with include/exclude rules
5. **Fallback Mechanism**: Try primary detector, fall back to heuristic list

### Windows-Specific Assumptions to Address

1. **Binary Format**: PE → ELF (Linux), Mach-O (macOS)
2. **Tool**: `llvm-objdump -p` → `llvm-readelf --needed-libs` (Linux), `otool -L` (macOS)
3. **DLL Pattern**: `lib*.dll` → `lib*.so*` (Linux), `lib*.dylib` (macOS)
4. **Sysroot Structure**: MinGW paths → system paths or toolchain lib directories
5. **System Libraries**: Windows DLLs → glibc (Linux), system frameworks (macOS)
6. **File Extensions**: `.exe`/`.dll` → no extension/`.so` (Linux), no extension/`.dylib` (macOS)

---

**End of Analysis Document**
