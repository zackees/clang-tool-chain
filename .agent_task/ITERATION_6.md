# Iteration 6: Fix Missing mm_malloc.h Header

## Date
2025-11-10

## Goal
Fix the missing `mm_malloc.h` header issue that caused compilation failures in Windows GNU ABI support.

## Problem Summary
After implementing GNU ABI support (Iterations 1-5), compilation failed with:
```
fatal error: 'mm_malloc.h' file not found
```

**Root Cause:** The MinGW sysroot archive (v1, 12.14 MB) only contained:
- `x86_64-w64-mingw32/` - MinGW runtime libraries
- `include/` - C/C++ standard library headers (libc++)

But was missing clang **resource headers** (compiler intrinsics like `mm_malloc.h`).

## Solution Approach
Following LOOP.md Option 2 recommendation: Extract resource headers from LLVM-MinGW and include in sysroot archive.

## Investigation (Tasks A1-A2)

###  1. Checked Our Clang Installation
- Clang reports resource dir: `C:\Users\niteris\.clang-tool-chain\clang\win\x86_64\lib\clang\21`
- But `lib/clang/21/include/` directory **does not exist** in our stripped LLVM distribution
- Our stripped binaries don't include resource headers

### 2. Checked LLVM-MinGW Source
Downloaded and extracted `llvm-mingw-20251104-ucrt-x86_64.zip` (172 MB):
- Found `lib/clang/21/include/mm_malloc.h` ✓
- Total resource headers: **232 files**
- Directory size: **16 MB uncompressed**

## Implementation (Tasks A3-A4)

### 1. Updated `extract_mingw_sysroot.py`

**File:** `src/clang_tool_chain/downloads/extract_mingw_sysroot.py`

**Change 1 - Extract resource headers** (lines 138-155):
```python
# Copy clang resource headers (mm_malloc.h, intrinsics, etc.)
# These are compiler builtin headers needed for compilation
clang_resource_src = llvm_mingw_root / "lib" / "clang"
if clang_resource_src.exists():
    # Find the version directory (e.g., "21")
    version_dirs = [d for d in clang_resource_src.iterdir() if d.is_dir()]
    if version_dirs:
        clang_version_dir = version_dirs[0]  # Should only be one
        resource_include_src = clang_version_dir / "include"
        if resource_include_src.exists():
            # Copy to lib/clang/<version>/include in sysroot
            resource_dst = extract_dir / "lib" / "clang" / clang_version_dir.name / "include"
            print(f"Copying clang resource headers: {resource_include_src} -> {resource_dst}")
            resource_dst.parent.mkdir(parents=True, exist_ok=True)
            if resource_dst.exists():
                shutil.rmtree(resource_dst)
            shutil.copytree(resource_include_src, resource_dst, symlinks=True)
            print(f"Copied {len(list(resource_dst.glob('*.h')))} resource headers")
```

**Change 2 - Include in archive** (lines 191, 205-207):
```python
lib_clang_path = sysroot_dir.parent / "lib" / "clang"
...
if lib_clang_path.exists():
    print("Adding to archive: lib/clang/ (resource headers)")
    tar.add(lib_clang_path, arcname="lib/clang")
```

**Change 3 - Fix zstandard import** (lines 168, 215):
Changed from `import zstandard as zstd` to `import pyzstd` (zstandard package was broken).

### 2. Regenerated Archive

**Command:**
```bash
uv run python src/clang_tool_chain/downloads/extract_mingw_sysroot.py --arch x86_64 --work-dir work --output-dir downloads/mingw/win
```

**Results:**
```
Copying clang resource headers: ...
Copied 232 resource headers
Adding to archive: lib/clang/ (resource headers)
Tar size: 191.77 MB
Compressing with zstd level 22...
Compressed size: 12.89 MB
Compression ratio: 93.3%
```

**Archive v2 Stats:**
- **Size:** 12.89 MB (increased from 12.14 MB - only 750 KB for 232 headers!)
- **SHA256:** `6d8b044a56e40380b49357f19de436cb3f5e8fb37d50287d7f1b22ffe1b77dba`
- **Contents:**
  - `x86_64-w64-mingw32/` - MinGW sysroot
  - `include/` - C/C++ headers (libc++)
  - `lib/clang/21/include/` - **NEW: Resource headers (232 files, 16 MB uncompressed)**

**Archive updated:**
- `downloads/mingw/win/x86_64/mingw-sysroot-21.1.5-win-x86_64.tar.zst`
- `downloads/mingw/win/x86_64/mingw-sysroot-21.1.5-win-x86_64.tar.zst.sha256`
- `downloads/mingw/win/x86_64/mingw-sysroot-21.1.5-win-x86_64.tar.zst.md5`
- `downloads/mingw/win/x86_64/manifest.json` (updated SHA256)

## Blocker Discovered

### Archive Extraction Issue

When testing, discovered that `extract_tarball()` in `downloader.py` has "smart" extraction logic that **reorganizes multi-root archives**:

**The Problem:**
- Our MinGW archive intentionally has 3 top-level directories:
  - `x86_64-w64-mingw32/`
  - `include/`
  - `lib/clang/`

- The extraction logic detects this as a "flat structure" and tries to "fix" it by moving items
- This causes `lib/clang/` to be lost during extraction
- Headers end up in wrong locations

**Evidence:**
```bash
# After extraction:
$ ls /c/Users/niteris/.clang-tool-chain/mingw/win/x86_64/
include/  x86_64-w64-mingw32/  done.txt    # lib/clang/ is MISSING!

$ find ... -name "mm_malloc.h"
# No results - headers lost during reorganization
```

**Log Output:**
```
Archive has flat structure, moving contents into \c\Users\niteris\.clang-tool-chain\mingw\win\x86_64
```

## Status

### ✅ Completed
1. ✓ Investigated mm_malloc.h location (found in LLVM-MinGW lib/clang/21/include/)
2. ✓ Researched LLVM-MinGW archive structure (232 resource headers, 16 MB)
3. ✓ Updated extract_mingw_sysroot.py to extract and include resource headers
4. ✓ Regenerated MinGW archive with resource headers (12.89 MB, SHA256: 6d8b044...)
5. ✓ Verified archive contains lib/clang/21/include/ with 310 entries

### ❌ Blocked
6. ✗ Testing blocked by extract_tarball() reorganization logic
7. ✗ Tests cannot pass until extraction preserves lib/clang/ directory

## Next Iteration Should Fix

**Root Cause:** `extract_tarball()` in `downloader.py` (lines 536-542) has logic that reorganizes "flat structure" archives.

**Two Solution Paths:**

**Option A: Fix extract_tarball() Logic (Preferred)**
```python
# In extract_tarball(), detect MinGW archives and skip reorganization:
if "mingw-sysroot" in tar_file.name:
    # MinGW archives have intentional multi-root structure, don't reorganize
    logger.info("MinGW archive detected, preserving original structure")
    # Skip the "flat structure moving" logic
    pass
else:
    # Existing logic for other archives
    ...
```

**Option B: Custom MinGW Extraction Function**
Create separate `extract_mingw_archive()` function in `downloader.py` that:
1. Decompresses .tar.zst with pyzstd
2. Extracts tarball directly without reorganization logic
3. Called specifically by `download_and_install_mingw()`

**Recommendation:** Use Option A - minimal change, preserves existing architecture.

## Files Modified This Iteration

1. `src/clang_tool_chain/downloads/extract_mingw_sysroot.py`
   - Added resource header extraction (lines 138-155)
   - Added lib/clang to archive creation (lines 191, 205-207)
   - Fixed pyzstd import (lines 168, 215)

2. `downloads/mingw/win/x86_64/mingw-sysroot-21.1.5-win-x86_64.tar.zst` (regenerated)
3. `downloads/mingw/win/x86_64/manifest.json` (updated SHA256)
4. `downloads/mingw/win/x86_64/*.sha256` and `*.md5` (regenerated)

## Key Learnings

1. **Clang resource headers are separate** from C/C++ standard library headers
   - Resource headers: Compiler intrinsics (`mm_malloc.h`, `*intrin.h`, etc.)
   - Standard library headers: libc++ (`<vector>`, `<string>`, etc.)

2. **Our stripped LLVM binaries don't include resource headers**
   - Must get them from LLVM-MinGW distribution
   - LLVM-MinGW has complete `lib/clang/21/include/` directory

3. **Archive extraction logic is too "smart"**
   - Tries to reorganize flat archives into single-root structure
   - Doesn't handle intentional multi-root archives (like MinGW sysroot)
   - Need to preserve original structure for MinGW

4. **pyzstd vs zstandard**
   - zstandard package has broken installation (missing backend_c)
   - pyzstd works reliably
   - Project already uses pyzstd

## Testing Plan for Next Iteration

After fixing extraction:

1. Clear cache: `rm -rf ~/.clang-tool-chain/mingw/`
2. Run single test: `pytest tests/test_gnu_abi.py::TestGNUABI::test_1_basic_cpp11_gnu_target -xvs`
3. Verify mm_malloc.h found and compilation succeeds
4. Run full GNU ABI test suite: `pytest tests/test_gnu_abi.py -v`
5. Run full test suite: `./test`
6. Verify all 11 previously failing tests now pass

## Summary

**Successfully:**
- Generated MinGW sysroot archive v2 with resource headers (12.89 MB)
- Archive contains all 232 clang resource headers
- Archive compression still excellent (93.3% reduction)
- Minimal size increase (750 KB for 16 MB of headers)

**Blocked by:**
- Archive extraction logic reorganizes multi-root archives
- `lib/clang/` directory lost during extraction
- Need to fix `extract_tarball()` to preserve MinGW archive structure

**Next iteration:** Fix extraction logic and complete testing.
