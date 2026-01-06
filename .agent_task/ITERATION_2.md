# Iteration 2: LLDB Python Integration Research (Linux)

**Date:** 2026-01-06
**Status:** Complete
**Goal:** Understand LLDB Python integration on Linux and identify solution for bundling Python bindings

---

## Summary

Successfully identified that official LLVM Linux releases do NOT include Python bindings (unlike Windows), but found a solution using Debian/Ubuntu `python3-lldb-21` packages from apt.llvm.org. Discovered critical architecture differences between Linux and Windows LLDB Python integration.

## Critical Findings

### 1. LLVM Linux Releases Lack Python Bindings

**Discovery:** The official LLVM-21.1.5-Linux-{X64,ARM64}.tar.xz releases include `liblldb.so` (compiled with Python 3.10 support) but do **NOT** include:
- Python binding module (`_lldb.so`)
- Python `lldb` package (`__init__.py`, formatters, plugins, utils)
- Python standard library

**Impact:** This is fundamentally different from Windows, where the LLVM installer includes embedded Python 3.10 and all bindings.

### 2. Solution: Debian/Ubuntu python3-lldb-21 Packages

**Source:** https://apt.llvm.org/

**Packages available:**
- Ubuntu 22.04 (Jammy) - **Python 3.10** ✅ Compatible with LLVM 21.1.5
- Ubuntu 24.04+ (Noble) - **Python 3.12** ❌ Incompatible

**Package URLs:**
```
# x86_64 (Python 3.10)
https://apt.llvm.org/jammy/pool/main/l/llvm-toolchain-21/python3-lldb-21_21.1.5~++20251023083201+45afac62e373-1~exp1~20251023083316.53_amd64.deb

# ARM64 (Python 3.10)
https://apt.llvm.org/jammy/pool/main/l/llvm-toolchain-21/python3-lldb-21_21.1.5~++20251023083201+45afac62e373-1~exp1~20251023083316.53_arm64.deb
```

**Package size:** ~200 KB each (very small!)

### 3. Linux vs. Windows Architecture Differences

| Aspect | Windows | Linux |
|--------|---------|-------|
| **Python bindings in LLVM release** | ✅ Included | ❌ NOT included |
| **_lldb extension module** | Separate 99 MB binary | Symlink to liblldb.so |
| **Binary duplication** | Yes (_lldb.pyd ≈ liblldb.dll) | No (just symlink) |
| **Compression savings** | 90% from deduplication | None (symlink = 0 bytes) |
| **Size impact** | +2.59 MB (with dedup) | +0.5-1 MB (just Python files) |

**Key Insight:** On Linux, `_lldb.cpython-310-*.so` is just a **symlink** to `liblldb.so`, not a duplicate binary. This means:
- No 99 MB binary to bundle
- No deduplication savings needed
- Size increase is minimal (~1 MB for Python source files only)

### 4. Python Version Compatibility

**LLVM 21.1.5 liblldb.so is compiled for Python 3.10:**
```bash
$ strings liblldb.so.21.1.5 | grep python
libpython3.10.so.1.0
bin/python3.10
local/lib/python3.10/dist-packages
```

**python3-lldb-21 versions:**
- Jammy (22.04): `_lldb.cpython-310-*.so` ✅ Compatible
- Noble (24.04+): `_lldb.cpython-312-*.so` ❌ Incompatible

**Decision:** Use Jammy packages for Python 3.10 compatibility.

### 5. Package Contents Analysis

**Downloaded and extracted 4 packages:**
1. Jammy amd64 (Python 3.10) ✅
2. Jammy arm64 (Python 3.10) ✅
3. Noble amd64 (Python 3.12) - for comparison
4. Noble arm64 (Python 3.12) - for comparison

**Package structure:**
```
usr/lib/llvm-21/lib/python3.10/site-packages/lldb/
├── __init__.py                                  (788 KB) - SWIG wrapper
├── _lldb.cpython-310-x86_64-linux-gnu.so       (symlink → ../../../liblldb.so)
├── embedded_interpreter.py                      (4 KB)
├── lldb-argdumper                               (symlink → ../../../../bin/lldb-argdumper)
├── formatters/                                  (~50 KB total)
├── plugins/                                     (~30 KB total)
└── utils/                                       (~20 KB total)

Total uncompressed: ~890 KB
Estimated compressed (zstd-22): ~200-300 KB
```

### 6. libpython3.10.so Dependency

**Finding:** LLVM 21.1.5 `liblldb.so` requires `libpython3.10.so.1.0` at runtime.

**Options:**
1. **Rely on system Python 3.10** (recommended) - Most Linux systems have Python 3.10+
2. **Bundle libpython3.10.so** - Adds ~2-3 MB, fully self-contained
3. **Static linking** - Not feasible (LLVM already compiled with dynamic linking)

**Decision:** Use system Python 3.10 with clear error message if not found. Consider bundling in future if users report issues.

---

## Implementation Strategy

### Recommended Approach: Extract from Debian Packages (Option A)

**Rationale:**
- Uses official, tested, stable Debian packages
- Minimal size impact (~1 MB compressed)
- No need to build LLDB from source
- Python 3.10 compatibility guaranteed

**Workflow:**
1. Download Jammy `python3-lldb-21` packages (x64 and ARM64)
2. Extract .deb files: `ar x package.deb` → `tar -xf data.tar.zst`
3. Copy Python lldb module to archive structure
4. Add Python 3.10 standard library (from python.org or system)
5. Create symlink `_lldb.so` → `../../../lib/liblldb.so.21` (relative path)
6. Package with zstd level 22 compression

### Alternative: Build from Source (Option B - Rejected)

**Rationale for rejection:**
- Requires 4+ GB LLVM source download
- Complex build process (30+ minutes per arch)
- Requires build dependencies (CMake, Ninja, SWIG, etc.)
- Much more time-consuming than extracting Debian packages
- No significant advantages over Option A

---

## Size Impact Analysis

### Before (No Python Bindings)
- LLDB binaries: ~8 MB compressed (estimated)

### After (With Python Bindings)

| Component | Uncompressed | Compressed (zstd-22) |
|-----------|-------------|---------------------|
| LLDB binaries | ~25 MB | ~8 MB |
| Python lldb module | ~890 KB | ~200-300 KB |
| Python 3.10 stdlib | ~15 MB | ~3-4 MB |
| **Total** | ~40 MB | **~11-12 MB** |

**Size increase:** ~3-4 MB per platform
**Total for x64 + ARM64:** ~6-8 MB additional

**Comparison to Windows:**
- Windows: 27.72 MB → 30.31 MB (+2.59 MB)
- Linux: ~8 MB → ~11-12 MB (+3-4 MB)
- Linux has slightly higher increase due to no binary deduplication

---

## Directory Structure Design

### Proposed Archive Structure

```
~/.clang-tool-chain/lldb-linux-x86_64/
├── bin/
│   ├── lldb                    # Main LLDB binary
│   ├── lldb-server             # Remote debugging server
│   └── lldb-argdumper          # Argument dumper utility
├── lib/
│   ├── liblldb.so.21.1.5       # Main LLDB library
│   ├── liblldb.so.21           # Symlink → liblldb.so.21.1.5
│   └── liblldb.so              # Symlink → liblldb.so.21
└── python/
    ├── Lib/
    │   ├── site-packages/
    │   │   └── lldb/            # From python3-lldb-21 package
    │   │       ├── __init__.py
    │   │       ├── _lldb.cpython-310-x86_64-linux-gnu.so (symlink → ../../../lib/liblldb.so.21)
    │   │       ├── embedded_interpreter.py
    │   │       ├── formatters/
    │   │       ├── plugins/
    │   │       └── utils/
    │   ├── encodings/           # From Python 3.10 stdlib
    │   ├── collections/
    │   ├── os.py
    │   ├── sys.py
    │   └── ...                  # Core Python modules
    └── lib-dynload/             # Optional: Python C extensions (.so files)
```

### Environment Configuration

**LLDB wrapper (`lldb.py`) will set:**
```python
env["PYTHONPATH"] = f"{lldb_install_dir}/python/Lib"
env["PYTHONHOME"] = f"{lldb_install_dir}/python"
env["LD_LIBRARY_PATH"] = f"{lldb_install_dir}/lib:{env.get('LD_LIBRARY_PATH', '')}"
env.pop("LLDB_DISABLE_PYTHON", None)  # Ensure Python is enabled
```

---

## Testing Requirements

### Python Module Discovery
```bash
$ lldb -P
/home/user/.clang-tool-chain/lldb-linux-x86_64/python/Lib
```

### Python Import
```bash
$ lldb
(lldb) script
>>> import lldb
>>> print(lldb.SBDebugger.GetVersionString())
lldb version 21.1.5
```

### Full Backtrace ("bt all")
```bash
$ lldb program
(lldb) run
(lldb) bt all
# Should show full backtraces for all threads
```

### Automated Tests
- `test_lldb_python_module_exists` - Verify lldb module can be imported
- `test_lldb_full_backtraces_with_python` - Verify "bt all" produces full output
- `test_lldb_python_version` - Verify Python 3.10 is being used

---

## Technical Challenges Encountered

### Challenge 1: Extracting .deb Packages on Windows

**Problem:** .deb packages use `data.tar.zst` (zstd compression)
**Solution:**
- Used `ar x package.deb` to extract control/data files
- Created Python script `extract_zst.py` using `zstandard` module
- Successfully extracted all 4 packages on Windows

### Challenge 2: Python Version Mismatch

**Problem:** Noble packages use Python 3.12, but LLVM 21.1.5 expects Python 3.10
**Solution:**
- Identified using `strings liblldb.so | grep python`
- Found Jammy packages with Python 3.10 bindings
- Documented compatibility matrix for future reference

### Challenge 3: Symlink Handling

**Problem:** `_lldb.so` is a symlink on Linux, not a real file
**Solution:**
- TAR archives preserve symlinks natively
- Use relative paths for portability: `../../../lib/liblldb.so.21`
- Test extraction to ensure symlinks work correctly

---

## Files Created/Modified

### Created
- **docs/PYTHON_PACKAGING_LINUX.md** - Comprehensive Linux Python packaging documentation (5400+ words)
- **.agent_task/ITERATION_2.md** - This iteration summary
- **downloads-bins/work/linux_python_analysis/python_packages/extract_zst.py** - .deb extraction helper

### Downloaded
- **python3-lldb-21_jammy_amd64.deb** (200 KB) - Python 3.10 bindings for x64
- **python3-lldb-21_jammy_arm64.deb** (200 KB) - Python 3.10 bindings for ARM64
- **python3-lldb-21_noble_amd64.deb** (187 KB) - Python 3.12 (for comparison)
- **python3-lldb-21_noble_arm64.deb** (187 KB) - Python 3.12 (for comparison)

### Extracted (4 packages)
- **jammy_amd64_extract/** - Python 3.10 x64 package contents
- **jammy_arm64_extract/** - Python 3.10 ARM64 package contents
- **amd64_extract/** (Noble) - Python 3.12 for comparison
- **arm64_extract/** (Noble) - Python 3.12 for comparison

---

## Success Criteria Met

- ✅ Linux Python distribution analyzed (Debian packages identified)
- ✅ LLDB Python integration understood (symlink architecture documented)
- ✅ Environment variable requirements identified (PYTHONPATH, PYTHONHOME, LD_LIBRARY_PATH)
- ✅ LLDB's Python module search paths documented (`lldb -P`)
- ✅ libpython3.10.so requirements documented (system dependency)
- ✅ Proof-of-concept approach designed (extract from Debian packages)
- ✅ Comprehensive documentation created (PYTHON_PACKAGING_LINUX.md)

---

## Key Decisions Made

### 1. Use Debian Jammy Packages (Not Noble)
- **Rationale:** Python 3.10 compatibility with LLVM 21.1.5
- **Alternative rejected:** Noble packages (Python 3.12 incompatible)

### 2. Extract from Debian Packages (Not Build from Source)
- **Rationale:** Faster, simpler, uses tested official packages
- **Alternative rejected:** Building from LLVM source (too complex, time-consuming)

### 3. Rely on System libpython3.10.so (Don't Bundle Initially)
- **Rationale:** Most Linux systems have Python 3.10+, reduces archive size
- **Fallback plan:** Bundle libpython3.10.so if users report issues

### 4. Use Relative Symlinks
- **Rationale:** Portable across different installation directories
- **Implementation:** `_lldb.so` → `../../../lib/liblldb.so.21`

---

## Lessons Learned

### 1. Linux LLDB Python Architecture is Fundamentally Different from Windows

**Windows:**
- Python bindings included in LLVM installer
- `_lldb.pyd` is a duplicate 99 MB binary (same as liblldb.dll)
- Binary deduplication provides 90% compression savings
- Archive size increase: +2.59 MB

**Linux:**
- Python bindings NOT included in LLVM release
- `_lldb.so` is just a symlink (0 bytes)
- No binary duplication, no deduplication savings
- Archive size increase: +3-4 MB (just Python source files + stdlib)

### 2. Debian/Ubuntu Package Versioning Matters

Different Ubuntu versions ship python3-lldb-21 with different Python versions:
- Jammy (22.04) → Python 3.10 (compatible)
- Noble (24.04+) → Python 3.12 (incompatible)

Always verify Python version compatibility with target LLVM build.

### 3. Symlinks Must Use Relative Paths

Absolute paths like `/usr/lib/llvm-21/lib/liblldb.so` won't work in `~/.clang-tool-chain/`.
Use relative paths: `../../../lib/liblldb.so.21`

### 4. Package Extraction on Windows is Feasible

With `zstandard` Python module, we can extract .deb packages on Windows for analysis.
No need for Linux VM for this research phase.

---

## Next Steps (Iteration 3)

**Goal:** Finalize packaging strategy and begin archive creation

**Tasks:**
1. Decide on Python 3.10 stdlib source (python.org vs. system Python)
2. Test symlink handling in TAR archives (ensure relative paths work)
3. Update `create_lldb_archives.py` to support Linux Python extraction
4. Design archive structure with Python bindings integrated
5. Create test archives for x64 and ARM64
6. Verify extraction and PYTHONPATH setup

**Estimated iterations remaining:** 8-12 (faster than Windows due to existing infrastructure)

---

## Time Spent

- Research and web searches: ~1.5 hours
- Package downloads and extraction: ~1 hour
- Analysis and testing: ~1 hour
- Documentation: ~1.5 hours

**Total:** ~5 hours (Iteration 2)

---

## References

### Documentation Created
- [docs/PYTHON_PACKAGING_LINUX.md](../docs/PYTHON_PACKAGING_LINUX.md) - Comprehensive Linux Python packaging guide

### Web Sources
- [LLVM Debian/Ubuntu Packages](https://apt.llvm.org/)
- [LLDB Python API Documentation](https://lldb.llvm.org/python_api.html)
- [LLDB Python Reference](https://lldb.llvm.org/use/python-reference.html)
- [Debian python3-lldb Packages](https://packages.debian.org/search?keywords=python-lldb)
- [Ubuntu python3-lldb Packages](https://packages.ubuntu.com/search?keywords=python3-lldb)

### Package Downloads
- Jammy x64: https://apt.llvm.org/jammy/pool/main/l/llvm-toolchain-21/python3-lldb-21_21.1.5~++20251023083201+45afac62e373-1~exp1~20251023083316.53_amd64.deb
- Jammy ARM64: https://apt.llvm.org/jammy/pool/main/l/llvm-toolchain-21/python3-lldb-21_21.1.5~++20251023083201+45afac62e373-1~exp1~20251023083316.53_arm64.deb

---

**Next Iteration:** Packaging strategy finalization and Python 3.10 stdlib integration

*Created: 2026-01-06*
*Status: Complete - Research Phase Finished*
