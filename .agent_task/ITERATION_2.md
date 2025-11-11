# Iteration 2 Summary: Download and Bundle IWYU from MSYS2 Packages

## Date
November 11, 2025

## Objective
Phase 1 (Tasks 1.5 via Option C): Manually download IWYU and dependencies from MSYS2 repository mirrors and bundle them together.

## Tasks Completed

### 1. Located MSYS2 Package Repository
**Result**: SUCCESS

**Actions**:
- Searched MSYS2 packages website (packages.msys2.org)
- Found all required packages with direct download URLs from mirror.msys2.org

**Packages Identified**:
| Package | Version | Size | Purpose |
|---------|---------|------|---------|
| mingw-w64-x86_64-include-what-you-use | 0.25-1 | 796 KB | IWYU binary and scripts |
| mingw-w64-x86_64-llvm-libs | 21.1.5-1 | 29 MB | libLLVM-21.dll |
| mingw-w64-x86_64-clang-libs | 21.1.5-1 | 21 MB | libclang-cpp.dll |
| mingw-w64-x86_64-libc++ | 21.1.4-1 | 2.0 MB | libc++.dll (not used) |
| mingw-w64-x86_64-libunwind | 21.1.1-1 | 127 KB | libunwind.dll (not used) |
| mingw-w64-x86_64-gcc-libs | 15.2.0-8 | 1.1 MB | libstdc++-6.dll, libgcc_s_seh-1.dll |
| mingw-w64-x86_64-libwinpthread | 13.0.0.r271 | 36 KB | libwinpthread-1.dll |
| mingw-w64-x86_64-libffi | 3.5.1-1 | 44 KB | libffi-8.dll |
| mingw-w64-x86_64-zlib | 1.3.1-1 | 105 KB | zlib1.dll |
| mingw-w64-x86_64-zstd | 1.5.7-1 | 643 KB | libzstd.dll |

---

### 2. Downloaded All MSYS2 Packages
**Result**: SUCCESS

**Download Location**: `/tmp/iwyu_msys2_manual/`

**Total Downloaded**: ~52 MB compressed (10 packages)

**Method**: Used `wget` to download directly from mirror.msys2.org

---

### 3. Extracted All Packages
**Result**: SUCCESS

**Challenge**: System `tar` didn't have zstd support built-in

**Solution**: Used Python with `zstandard` library from project's venv:
```python
import zstandard as zstd
dctx = zstd.ZstdDecompressor()
dctx.copy_stream(ifh, ofh)
```

**Extraction Location**: `/tmp/iwyu_msys2_manual/extracted/`

**Structure**: All packages extracted to `extracted/mingw64/bin/` and `extracted/mingw64/share/`

---

### 4. Identified Required Dependencies Using ldd
**Result**: SUCCESS

**Command**: `ldd extracted/mingw64/bin/include-what-you-use.exe`

**Required DLLs** (non-system):
1. `libclang-cpp.dll` (55 MB) - from clang-libs package
2. `libLLVM-21.dll` (130 MB) - from llvm-libs package
3. `libstdc++-6.dll` (2.4 MB) - from gcc-libs package
4. `libgcc_s_seh-1.dll` (147 KB) - from gcc-libs package
5. `libwinpthread-1.dll` (64 KB) - from libwinpthread package
6. `libffi-8.dll` (35 KB) - from libffi package
7. `zlib1.dll` (118 KB) - from zlib package
8. `libzstd.dll` (1.2 MB) - from zstd package

**System DLLs** (Windows-provided, not bundled):
- ntdll.dll, KERNEL32.DLL, msvcrt.dll, ADVAPI32.dll, etc.

---

### 5. Created Bundle Directory
**Result**: SUCCESS

**Bundle Location**: `/tmp/iwyu_msys2_manual/bundle/`

**Bundle Structure**:
```
bundle/
├── bin/
│   ├── include-what-you-use.exe (2.4 MB)
│   ├── iwyu_tool.py (19 KB)
│   ├── fix_includes.py (103 KB)
│   ├── libclang-cpp.dll (55 MB)
│   ├── libLLVM-21.dll (130 MB)
│   ├── libstdc++-6.dll (2.4 MB)
│   ├── libgcc_s_seh-1.dll (147 KB)
│   ├── libwinpthread-1.dll (64 KB)
│   ├── libffi-8.dll (35 KB)
│   ├── zlib1.dll (118 KB)
│   └── libzstd.dll (1.2 MB)
└── share/
    └── include-what-you-use/
        ├── boost-*.imp (mapping files)
        ├── clang-*.intrinsics.imp
        ├── gcc.*.imp
        ├── libcxx.imp
        └── ... (50+ mapping files)
```

**Total Bundle Size**: 191 MB uncompressed

---

### 6. Verified Dependency Resolution
**Result**: SUCCESS

**Command**: `ldd bundle/bin/include-what-you-use.exe | grep "not found"`

**Output**: (empty - no missing dependencies)

**All DLLs Resolved**:
- All non-system DLLs found in `bundle/bin/` directory
- All system DLLs found in Windows system directories
- No "not found" entries

---

### 7. Initial Testing (INCOMPLETE)
**Result**: IN PROGRESS

**Test 1 - Version Command**:
```bash
cd /tmp/iwyu_msys2_manual/bundle/bin
./include-what-you-use.exe --version
```
**Exit Code**: 127 (command not found or failed to execute)

**Test 2 - No Arguments**:
```bash
./include-what-you-use.exe
```
**Exit Code**: (hung/no output)

**Status**: NEEDS FURTHER INVESTIGATION

**Possible Issues**:
1. Binary may require specific environment variables
2. May need to be run from different shell (CMD vs MSYS2)
3. May have initialization issues despite DLL resolution

---

## Key Achievements

1. **Successful Manual Package Download**: Bypassed need for `pacman` by downloading directly from mirrors
2. **Complete Dependency Resolution**: Identified and bundled ALL required DLLs from SAME source (MSYS2)
3. **Proper Extraction**: Overcame zstd extraction challenge using Python
4. **Clean Bundle Structure**: Organized directory matching expected installation layout
5. **No Missing Dependencies**: `ldd` confirms all DLLs are available

---

## Critical Next Steps for Iteration 3

### PRIORITY 1: Complete Phase 2 Testing (MUST COMPLETE BEFORE ARCHIVING)

According to LOOP.md Phase 2 requirements, we MUST:

1. **Test in isolated environment** (no MSYS2 in PATH):
   ```bash
   export PATH="/c/Windows/System32:/c/Windows"
   cd /tmp/iwyu_msys2_manual/bundle/bin
   ./include-what-you-use.exe --version
   ```

2. **Test with real C++ file**:
   ```bash
   ./include-what-you-use.exe /tmp/test_iwyu.cpp -- -std=c++11
   ```

3. **Test Python helper scripts**:
   ```bash
   python3 iwyu_tool.py --help
   python3 fix_includes.py --help
   ```

4. **Expected Success Criteria**:
   - Exit codes: 0, 1, or 2 (IWYU valid return codes)
   - NOT crash codes: 127, 3221225781 (0xC0000005), 3221225785 (0xC0000009)
   - Actual output produced (not empty)
   - Helper scripts execute successfully

### PRIORITY 2: Debug Current Test Failure

The exit code 127 is concerning. Investigate:

1. **Try CMD window instead of Git Bash**:
   ```cmd
   cd C:\tmp\iwyu_msys2_manual\bundle\bin
   include-what-you-use.exe --version
   ```

2. **Check if binary is actually executable**:
   ```bash
   file bundle/bin/include-what-you-use.exe
   ```

3. **Try running with full path**:
   ```bash
   /tmp/iwyu_msys2_manual/bundle/bin/include-what-you-use.exe --version
   ```

4. **Check for MSYS2-specific path issues**:
   - IWYU binary may expect MSYS2-style paths (`/tmp/...`)
   - May need to convert Windows paths for testing

### PRIORITY 3: If Tests Pass, Proceed to Phase 3

**ONLY IF ALL PHASE 2 TESTS PASS**:
- Create TAR archive
- Compress with zstd level 22
- Generate SHA256 checksum
- Update manifest
- Run Phase 4 archive extraction tests

---

## Critical Lessons Learned

1. **All Dependencies from Same Source**: Mixing MSYS2 IWYU binary with llvm-mingw DLLs failed (ABI incompatibility). Solution: Download ALL components from MSYS2 packages.

2. **Manual Package Download Works**: Can bypass `pacman` by downloading `.pkg.tar.zst` files directly from mirror.msys2.org and extracting with Python.

3. **ldd Shows Dependencies Correctly**: Even though `ldd` shows dependencies resolved, exit code 127 suggests runtime issue beyond simple DLL resolution.

4. **Test Before Archive**: Previous iteration's mistake was archiving before local testing. This iteration follows LOOP.md correctly by testing first.

---

## Files Created This Iteration

- `/tmp/iwyu_msys2_manual/` - Working directory
  - `*.pkg.tar.zst` - Downloaded MSYS2 packages (10 files)
  - `extracted/` - Extracted package contents
  - `bundle/` - Final bundle directory ready for testing
- `/tmp/test_iwyu.cpp` - Test C++ file for IWYU analysis

---

## Progress: Phase 1 (90% Complete), Phase 2 (10% Complete)

- [x] Task 1.5: Extract from MSYS2 (via manual download)
- [x] Bundle IWYU + exact DLLs from MSYS2
- [x] Verify no missing dependencies with ldd
- [ ] **Test binary locally** (IN PROGRESS - exit code 127 issue)
- [ ] Verify works in clean environment
- [ ] Test with actual C++ file
- [ ] Test Python helper scripts
- [ ] Document working configuration
- [ ] Phase 3: Create archive (BLOCKED until Phase 2 complete)

---

## Time Spent
Approximately 25 minutes of downloading, extracting, and bundling

## Status
**IN PROGRESS** - Bundle created and dependencies verified, but initial testing shows exit code 127. Need to debug execution issue before proceeding to archive creation.

## Critical Warning
⚠️ **DO NOT CREATE ARCHIVE YET** - Phase 2 testing is NOT complete. LOOP.md explicitly requires ALL Phase 2 tests to PASS before creating archive. Current exit code 127 indicates execution failure.

---

## Next Agent Instructions

**IMMEDIATE ACTION**: Debug why bundled IWYU binary returns exit code 127 despite all DLLs being resolved:

1. Try running in CMD window (not Git Bash)
2. Check file type and permissions
3. Try different invocation methods
4. Check for missing environment variables
5. Compare with working MSYS2 installation

**IF DEBUGGING SUCCEEDS**: Complete all Phase 2 tests per LOOP.md

**IF DEBUGGING FAILS**: Research alternative IWYU sources (Task 1.3 Chocolatey, Task 1.4 vcpkg) or investigate if IWYU requires additional setup beyond DLLs

**UNDER NO CIRCUMSTANCES**: Create archive until Phase 2 tests show valid exit codes (0-2) and actual IWYU output.
