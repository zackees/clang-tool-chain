# DLL Detector Architecture

## Overview

The DLL detector module implements the **Strategy Pattern** to provide flexible, testable, and extensible DLL dependency detection for Windows executables and shared libraries.

## Class Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        DLLDetector (ABC)                     │
├─────────────────────────────────────────────────────────────┤
│ + detect(binary_path: Path) -> list[str]                    │
└─────────────────────────────────────────────────────────────┘
                              △
                              │
                ┌─────────────┴─────────────┐
                │                           │
┌───────────────┴────────────┐  ┌──────────┴──────────────────┐
│  ObjdumpDLLDetector        │  │  HeuristicDLLDetector        │
├────────────────────────────┤  ├──────────────────────────────┤
│ - objdump_path: Path       │  │ - dll_list: list[str]        │
│ - dll_filter_func: Callable│  ├──────────────────────────────┤
├────────────────────────────┤  │ + detect() -> list[str]      │
│ + detect() -> list[str]    │  │   Returns hardcoded DLL list │
│   Uses llvm-objdump -p     │  └──────────────────────────────┘
│   Filters deployable DLLs  │
└────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│            TransitiveDependencyScanner                       │
├─────────────────────────────────────────────────────────────┤
│ - dll_locator_func: Callable[str, Path | None]             │
│ - objdump_path: Path                                        │
│ - dll_filter_func: Callable[str, bool]                      │
├─────────────────────────────────────────────────────────────┤
│ + scan_transitive_dependencies(list[str]) -> list[str]      │
│   Recursively scans DLL dependencies                        │
│   Uses BFS to avoid duplicates                              │
└─────────────────────────────────────────────────────────────┘
```

## Sequence Diagram: Complete DLL Detection Workflow

```
┌────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│ Client │    │ dll_deployer │    │ ObjdumpDetector │    │ Transitive   │    │ Heuristic   │
│        │    │              │    │                 │    │ Scanner      │    │ Detector    │
└───┬────┘    └──────┬───────┘    └────────┬────────┘    └──────┬───────┘    └──────┬──────┘
    │                │                     │                     │                   │
    │ detect_required_dlls(exe_path)      │                     │                   │
    │─────────────────>                   │                     │                   │
    │                │                     │                     │                   │
    │                │ Get objdump path   │                     │                   │
    │                │                     │                     │                   │
    │                │ objdump exists?     │                     │                   │
    │                │────────────────────>│                     │                   │
    │                │       YES           │                     │                   │
    │                │<────────────────────│                     │                   │
    │                │                     │                     │                   │
    │                │ detect(exe_path)    │                     │                   │
    │                │────────────────────>│                     │                   │
    │                │                     │                     │                   │
    │                │     Run llvm-objdump -p                   │                   │
    │                │     Parse DLL imports                     │                   │
    │                │     Filter deployable DLLs                │                   │
    │                │                     │                     │                   │
    │                │ ["lib1.dll", ...]  │                     │                   │
    │                │<────────────────────│                     │                   │
    │                │                     │                     │                   │
    │                │ scan_transitive_dependencies(dlls)        │                   │
    │                │──────────────────────────────────────────>│                   │
    │                │                     │                     │                   │
    │                │                     │     locate_dll("lib1.dll")              │
    │                │                     │     Run objdump on lib1.dll             │
    │                │                     │     Find "lib2.dll" dependency          │
    │                │                     │                     │                   │
    │                │                     │     locate_dll("lib2.dll")              │
    │                │                     │     Run objdump on lib2.dll             │
    │                │                     │     No more dependencies                │
    │                │                     │                     │                   │
    │                │ ["lib1.dll", "lib2.dll"]                 │                   │
    │                │<──────────────────────────────────────────│                   │
    │                │                     │                     │                   │
    │ ["lib1.dll", "lib2.dll"]            │                     │                   │
    │<─────────────────                   │                     │                   │
    │                │                     │                     │                   │
    │                                                                                 │
    │                Fallback Path (objdump fails)                                   │
    │                ─────────────────────────────                                   │
    │                │                     │                     │                   │
    │                │ objdump fails       │                     │                   │
    │                │──────────────────────────────────────────────────────────────>│
    │                │                     │                     │                   │
    │                │ detect(exe_path)    │                     │                   │
    │                │──────────────────────────────────────────────────────────────>│
    │                │                     │                     │                   │
    │                │     Return hardcoded DLL list             │                   │
    │                │                     │                     │                   │
    │                │ ["libwinpthread-1.dll", ...]              │                   │
    │                │<──────────────────────────────────────────────────────────────│
    │                │                     │                     │                   │
    │ ["libwinpthread-1.dll", ...]        │                     │                   │
    │<─────────────────                   │                     │                   │
    │                │                     │                     │                   │
```

## Component Responsibilities

### 1. DLLDetector (Abstract Base Class)
**Responsibility:** Define the interface for all DLL detection strategies.

**Key Method:**
- `detect(binary_path: Path) -> list[str]`: Detect DLL dependencies for a binary

**Purpose:** Allows polymorphic usage of different detection strategies.

### 2. ObjdumpDLLDetector
**Responsibility:** Precise DLL detection using llvm-objdump.

**Strategy:** Parse PE import table using `llvm-objdump -p`

**Features:**
- Reads actual DLL imports from binary
- Supports optional filtering via `dll_filter_func`
- Handles timeouts (10 seconds)
- Raises exceptions on failure (caller handles fallback)

**Example:**
```python
detector = ObjdumpDLLDetector(
    objdump_path=Path("/path/to/llvm-objdump.exe"),
    dll_filter_func=lambda dll: dll.startswith("lib")
)
dlls = detector.detect(Path("program.exe"))
# Returns: ["libwinpthread-1.dll", "libgcc_s_seh-1.dll"]
```

### 3. HeuristicDLLDetector
**Responsibility:** Fallback DLL detection using hardcoded list.

**Strategy:** Return pre-defined DLL list without analyzing binary.

**Features:**
- Fast (no external process)
- Reliable (no dependencies on llvm-objdump)
- Customizable via constructor

**Default DLL List:**
```python
[
    "libwinpthread-1.dll",
    "libgcc_s_seh-1.dll",
    "libstdc++-6.dll",
]
```

**Example:**
```python
detector = HeuristicDLLDetector()
dlls = detector.detect(Path("program.exe"))
# Returns: ["libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll"]
```

### 4. TransitiveDependencyScanner
**Responsibility:** Recursively scan DLLs to find transitive dependencies.

**Algorithm:** Breadth-First Search (BFS)
1. Start with direct dependencies
2. For each DLL:
   - Locate in toolchain using `dll_locator_func`
   - Extract dependencies using objdump
   - Filter deployable DLLs using `dll_filter_func`
   - Add new DLLs to scan queue
3. Continue until no new dependencies found

**Features:**
- Avoids duplicates (tracks scanned DLLs)
- Handles missing DLLs gracefully (logs warning, continues)
- Handles objdump failures per DLL (logs debug, continues)

**Example:**
```python
def locate_dll(dll_name: str) -> Path | None:
    return Path(f"/mingw/bin/{dll_name}") if exists else None

scanner = TransitiveDependencyScanner(
    dll_locator_func=locate_dll,
    objdump_path=Path("/path/to/llvm-objdump.exe"),
    dll_filter_func=lambda dll: dll.startswith("lib")
)

# Starting DLLs: libstdc++-6.dll, libgcc_s_seh-1.dll
# libstdc++-6.dll depends on: libwinpthread-1.dll
# libgcc_s_seh-1.dll depends on: libwinpthread-1.dll
all_dlls = scanner.scan_transitive_dependencies([
    "libstdc++-6.dll",
    "libgcc_s_seh-1.dll"
])
# Returns: ["libstdc++-6.dll", "libgcc_s_seh-1.dll", "libwinpthread-1.dll"]
```

## Integration with dll_deployer.py

The `detect_required_dlls()` function in `dll_deployer.py` orchestrates the detection strategies:

```python
def detect_required_dlls(exe_path, platform_name, arch):
    # 1. Try precise detection with ObjdumpDLLDetector
    try:
        objdump_path = get_platform_binary_dir() / "llvm-objdump.exe"

        if not objdump_path.exists():
            # Fallback to heuristic immediately
            return HeuristicDLLDetector().detect(exe_path)

        # Detect direct dependencies
        detector = ObjdumpDLLDetector(objdump_path, dll_filter_func=_is_deployable_dll)
        direct_dlls = detector.detect(exe_path)

        if direct_dlls:
            # Scan for transitive dependencies
            scanner = TransitiveDependencyScanner(
                dll_locator_func=lambda dll: find_dll_in_toolchain(dll, platform_name, arch),
                objdump_path=objdump_path,
                dll_filter_func=_is_deployable_dll
            )
            return scanner.scan_transitive_dependencies(direct_dlls)

        # No deployable DLLs found - use heuristic
        return HeuristicDLLDetector().detect(exe_path)

    except RuntimeError:
        # Objdump failed - use heuristic fallback
        return HeuristicDLLDetector().detect(exe_path)
```

## Error Handling Strategy

### ObjdumpDLLDetector
**Errors raised:**
- `FileNotFoundError`: Binary path doesn't exist
- `RuntimeError`: objdump not found, timed out, or failed

**Caller responsibility:** Catch exceptions and fall back to HeuristicDLLDetector.

### HeuristicDLLDetector
**Errors raised:**
- `FileNotFoundError`: Binary path doesn't exist

**Never fails:** Always returns hardcoded DLL list.

### TransitiveDependencyScanner
**Error handling:**
- **Missing DLL in toolchain:** Log debug, continue scanning
- **Objdump failure on DLL:** Log debug, continue scanning
- **KeyboardInterrupt:** Propagate (critical)
- **Other exceptions:** Log debug, continue scanning

**Philosophy:** Best-effort scanning - collect as many dependencies as possible, never fail completely.

## Extension Points

### Adding New Detection Strategies

Implement `DLLDetector` interface:

```python
class PEParserDLLDetector(DLLDetector):
    """Detector using pure Python PE parser (no llvm-objdump needed)."""

    def detect(self, binary_path: Path) -> list[str]:
        import pefile
        pe = pefile.PE(str(binary_path))
        dlls = []
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            dll_name = entry.dll.decode()
            if is_deployable_dll(dll_name):
                dlls.append(dll_name)
        return dlls
```

### Adding Caching

Wrap detector with cache:

```python
class CachedDLLDetector(DLLDetector):
    def __init__(self, inner_detector: DLLDetector):
        self.inner = inner_detector
        self.cache = {}

    def detect(self, binary_path: Path) -> list[str]:
        cache_key = (binary_path, binary_path.stat().st_mtime)
        if cache_key not in self.cache:
            self.cache[cache_key] = self.inner.detect(binary_path)
        return self.cache[cache_key]
```

### Parallel Scanning

Modify `TransitiveDependencyScanner` to use thread pool:

```python
from concurrent.futures import ThreadPoolExecutor

class ParallelTransitiveDependencyScanner(TransitiveDependencyScanner):
    def scan_transitive_dependencies(self, direct_deps):
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all DLL scans concurrently
            # Collect results from futures
            pass
```

## Benefits of Strategy Pattern

### 1. Separation of Concerns
- **Detection logic** isolated from deployment logic
- Each strategy has single responsibility
- Easy to understand and modify

### 2. Testability
- Mock objdump output easily
- Test transitive scanning with fake locators
- Verify fallback behavior without real binaries

### 3. Extensibility
- Add new strategies without modifying existing code
- Swap strategies at runtime
- Compose strategies (caching, logging, etc.)

### 4. Maintainability
- Clear class names communicate intent
- Reduced nesting (5 levels → 2 levels)
- Better error handling through focused exception contexts

### 5. Reusability
- Strategies can be used independently
- TransitiveDependencyScanner works with any detector
- Easy to use in different contexts (tests, CLI tools, etc.)

## Performance Characteristics

| Strategy | Time Complexity | Space Complexity | External Deps |
|----------|----------------|------------------|---------------|
| HeuristicDLLDetector | O(1) | O(1) | None |
| ObjdumpDLLDetector | O(n) where n = imports | O(n) | llvm-objdump |
| TransitiveDependencyScanner | O(n*m) where n = DLLs, m = avg deps | O(n) | llvm-objdump |

**Typical Performance:**
- HeuristicDLLDetector: <1ms
- ObjdumpDLLDetector: 10-50ms per binary
- TransitiveDependencyScanner: 50-200ms total (3-10 DLLs)

## Summary

The DLL detector module provides a clean, testable, and extensible architecture for detecting Windows DLL dependencies. By using the Strategy pattern, it achieves:

- **Flexibility:** Multiple detection strategies (precise, heuristic, custom)
- **Reliability:** Graceful fallback when llvm-objdump unavailable
- **Performance:** Fast heuristic fallback, reasonable objdump performance
- **Maintainability:** Clear separation of concerns, reduced complexity
- **Extensibility:** Easy to add new strategies without modifying existing code

The refactoring reduces nesting depth by 60% (5 → 2 levels) and makes the code significantly easier to understand, test, and extend.
