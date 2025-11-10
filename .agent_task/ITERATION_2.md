# Iteration 2: Fix MinGW Archive Extraction Logic

**Date:** 2025-11-10
**Task:** Fix extract_tarball() to preserve MinGW archive structure (Phase 4 continuation from Iteration 6 blocker)
**Status:** ⚠️ Partial - Found root cause, needs different approach in Iteration 3

---

## Summary

This iteration investigated and partially fixed the MinGW archive extraction issue discovered in Iteration 6. The goal was to fix `extract_tarball()` to properly extract the multi-root MinGW archive structure.

## What Was Accomplished

###  1. Identified Extraction Reorganization Issue

**Found:** `extract_tarball()` has logic (lines 528-553) that "reorganizes" archives:
- **Case 1:** Single top-level directory → renamed to dest_dir
- **Case 2:** Multiple directories/files → moved INTO dest_dir

MinGW archive has 3 intentional top-level directories:
- `x86_64-w64-mingw32/` - MinGW runtime
- `include/` - C/C++ standard library headers (libc++)
- `lib/clang/` - Compiler resource headers (mm_malloc.h, intrinsics)

The reorganization correctly identifies this as "multi-root" and preserves it, BUT there's a different problem...

### 2. Fixed System Tar Incompatibility

**Problem:** Windows `bsdtar` (system tar) silently fails to extract `lib/` directory from MinGW archive.

**Solution:** Force Python tarfile for MinGW archives
- Added detection: `is_mingw_archive = "mingw-sysroot" in archive_path.name`
- Skip system tar when MinGW archive detected (line 496-497)
- Log: "Using Python tarfile for MinGW archive (system tar has multi-root issues)"

**Files Modified:**
- `src/clang_tool_chain/downloader.py` (lines 495-521)

### 3. Discovered Critical Issue: Python Tarfile ALSO Fails

**Shocking Discovery:** Even with Python tarfile, `lib/` directory is NOT extracted!

**Evidence:**
```
DEBUG: Immediate post-extraction check: 2 items in mingw/win: ['include', 'x86_64-w64-mingw32']
```

Only 2 directories extracted instead of 3.

**But manual tests work:**
```python
# This extracts lib/ successfully:
tar = tarfile.open('archive.tar.zst')
tar.extractall('/tmp/test')
# Result: include/, lib/, x86_64-w64-mingw32/ ✓

# This fails (in downloader.py):
tar = tarfile.open(temp_tar, 'r')
tar.extractall(dest_dir.parent)  # mingw/win
# Result: include/, x86_64-w64-mingw32/ ❌ (lib/ missing!)
```

**Root Cause:** UNKNOWN - Same Python code, same archive, different results based on extraction path? Possible:
- Windows path length limits
- Permissions
- Some undiscovered context difference

### 4. Implemented Alternative Solution: Post-Install Copy

Following LOOP.md recommendation (Option 3, line 1840), implemented post-install resource header copy from clang installation.

**Added to `download_and_install_mingw()`** (lines 1128-1167):
- After extraction, copy `lib/clang/<version>/include/*.h` from clang installation
- Copy to `install_dir/lib/clang/<version>/include/`
- Log number of headers copied
- Graceful fallback with warnings if copy fails

**Rationale:** Resource headers should match clang version anyway, so copying from clang installation is more robust than bundling in archive.

### 5. Discovered Second Critical Issue: Clang Installation Missing Resource Headers!

**Problem:** Our LLVM distribution doesn't include resource headers!

```bash
$ ls C:/Users/niteris/.clang-tool-chain/clang/win/x86_64/lib/
# ERROR: No such directory

$ C:/Users/niteris/.clang-tool-chain/clang/win/x86_64/bin/clang.exe -print-resource-dir
C:\Users\niteris\.clang-tool-chain\clang\win\x86_64\lib\clang\21
# ^^^ This directory doesn't exist!

$ find clang/win/x86_64 -name "mm_malloc.h"
# No results
```

So:
1. Clang expects resource headers at `lib/clang/21/include/`
2. That directory doesn't exist in our LLVM binaries
3. Post-install copy has nothing to copy
4. Compilation fails with "mm_malloc.h not found"

## Root Cause Analysis

The MinGW archive (iteration 5-6) was created with `lib/clang/` because:
1. LLVM-MinGW includes resource headers
2. We extracted and bundled them in the archive
3. Archive verified to contain 310 `lib/clang` members

But extraction fails mysteriously, AND our base LLVM installation lacks these headers entirely.

**The real solution:** Get resource headers into the system, either:
- **Option A:** Fix tar extraction bug (unknown cause)
- **Option B:** Bundle headers differently (not in tarball)
- **Option C:** Download LLVM-MinGW resource headers separately
- **Option D:** Use `--resource-dir` flag to point to MinGW archive location
- **Option E:** Copy from LLVM-MinGW download during first-time setup

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `downloader.py` | Force Python tarfile for MinGW archives | 495-521 |
| `downloader.py` | Add debug logging for extraction | 523-529 |
| `downloader.py` | Add MinGW detection for reorganization | 531, 543-545 |
| `downloader.py` | Implement post-install resource header copy | 1128-1167 |

## Test Results

❌ **All GNU ABI tests still fail** with "mm_malloc.h not found"

Example:
```
tests/test_gnu_abi.py::TestGNUABI::test_1_basic_cpp11_gnu_target FAILED
Error: fatal error: 'mm_malloc.h' file not found
```

## Next Iteration Must Do

### Priority 1: Get Resource Headers Working

**Recommended Approach (fastest):**

**Option D: Use `--resource-dir` flag**
1. MinGW archive contains `lib/clang/21/include/` with 232 headers
2. Even though extraction fails, we can work around it
3. Add to `wrapper.py` `_get_gnu_target_args()`:
   ```python
   resource_dir = install_dir / "lib" / "clang" / "21"
   return [
       f"--target={target}",
       f"--sysroot={sysroot_path}",
       "-stdlib=libc++",
       f"--resource-dir={resource_dir}"  # Point to MinGW archive location
   ]
   ```
4. **BUT**: This requires fixing extraction first OR manually placing headers

**Option E: Download and extract LLVM-MinGW headers during setup (BEST)**
1. During `ensure_mingw_sysroot_installed()`, detect missing resource headers
2. Download LLVM-MinGW archive
3. Extract ONLY `lib/clang/21/include/` to `install_dir/lib/clang/21/include/`
4. Use tarfile member filtering: `tar.extractall(members=[m for m in tar if m.name.startswith('lib/clang')])`
5. Works around the mysterious extraction bug by extracting selectively

### Priority 2: Debug Extraction Bug (Optional)

If time permits, investigate why tar.extractall() behavior differs:
- Add extensive logging around tar.extractall()
- Check Windows path length limits
- Test with different extraction paths
- Compare archive member attributes

## Time Spent

- **Investigation:** 45 minutes (tracing extraction logic, testing manually)
- **Implementation:** 30 minutes (system tar fix, post-install copy, debugging)
- **Testing:** 15 minutes (multiple test runs, cache clearing)
- **Documentation:** 10 minutes

**Total:** ~100 minutes (1h 40m)

## Lessons Learned

1. **Archive extraction is platform-dependent** - System tar behaves differently than Python tarfile
2. **Python tarfile has mysterious bugs** - Same code, different paths, different results
3. **Test archives thoroughly** - Just because an archive contains data doesn't mean extraction works
4. **Resource headers are critical** - Without them, even basic C++ compilation fails
5. **Post-install fixes are fragile** - Dependencies on other installations (clang) can fail silently

## Status for Next Iteration

**Blocked Items:**
- All GNU ABI tests (11 tests)
- MinGW sysroot installation (lib/clang/ missing)
- Compilation with GNU target (mm_malloc.h not found)

**Working Items:**
- MinGW sysroot download ✓
- Archive decompression ✓
- Partial extraction (include/, x86_64-w64-mingw32/) ✓
- GNU ABI detection and injection ✓

**Ready for Next Iteration:**
- Option E implementation (selective extraction)
- Or Option D with manual header placement
- Full test suite validation once headers are in place
