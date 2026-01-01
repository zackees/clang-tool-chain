# IWYU Linux ARM64 Fix - Implementation Summary

## Overview

This document summarizes the complete implementation of the fix for IWYU Linux ARM64 archive issues, created on December 31, 2024.

## Problem Identified

The Linux ARM64 IWYU archive (`downloads-bins/assets/iwyu/linux/arm64/`) had critical issues:

1. **Wrong binary type**: Homebrew build for macOS, not Linux
   ```
   interpreter: @@HOMEBREW_PREFIX@@/lib/ld.so  (WRONG - macOS Homebrew)
   Expected:    /lib/ld-linux-aarch64.so.1     (correct Linux ARM64)
   ```

2. **Missing LLVM libraries**: No `lib/` directory - completely missing libclang-cpp, libLLVM, etc.

3. **Tiny archive size**: 749 KB vs expected ~200 MB (like x86_64 fixed version)

4. **Manifest issues**: Missing `-fixed` suffix, incorrect SHA256 hash

## Root Cause

The ARM64 binary was sourced from a macOS Homebrew build instead of being built properly for Linux. This binary cannot run on Linux systems due to:
- Wrong dynamic linker path
- Missing shared libraries
- Incompatible ABI

## Solution Implemented

### 1. Created Docker Build System

**File**: `docker/Dockerfile.iwyu-arm64-builder`
- Multi-stage Docker build for ARM64 Linux
- Builds LLVM 21.1.5 from source (shared libraries only)
- Builds IWYU 0.25 from source against LLVM
- Bundles LLVM-specific libraries (libclang-cpp, libLLVM, libxml2, libicu, liblzma)
- Removes system libraries (libc, libstdc++, libm, libgcc_s)
- Sets RPATH to `$ORIGIN/../lib` for portable binaries
- Uses `patchelf` to ensure correct RPATH

**Build time**: 30-60 minutes (depends on ARM64 emulation speed)

### 2. Created Automated Build Script

**File**: `docker/build-iwyu-arm64.sh`
- Automated Docker build execution
- System library cleanup verification
- Binary dependency checking
- Extraction to `downloads-bins/assets/iwyu/linux/arm64/`
- Comprehensive output and verification steps

**Features**:
- Color-coded output for clarity
- Step-by-step progress indicators
- Automatic backup of old files
- Dependency verification with `readelf`
- Next-steps guidance

### 3. Created Comprehensive Documentation

**File**: `docs/IWYU_ARM64_FIX_GUIDE.md` (3,500+ words)

Complete step-by-step guide including:
- Problem analysis and background
- Architecture overview
- Prerequisites and requirements
- 9-step execution process
- Verification checklist
- Troubleshooting guide
- Expected archive structure
- Key lessons learned

### 4. Updated Project Documentation

**Files modified**:
- `TASK.md` - Added solution summary, root cause analysis, quick start
- `docker/README.md` - Added IWYU ARM64 Builder section with usage instructions

## Files Created/Modified

### New Files (3)
1. `docker/Dockerfile.iwyu-arm64-builder` - Docker build configuration
2. `docker/build-iwyu-arm64.sh` - Automated build script (executable)
3. `docs/IWYU_ARM64_FIX_GUIDE.md` - Complete implementation guide

### Modified Files (2)
1. `TASK.md` - Status update, solution implementation section
2. `docker/README.md` - Added IWYU ARM64 Builder documentation

## Key Technical Details

### Build Process

```
Ubuntu 24.04 ARM64 Container
    ↓
Download LLVM 21.1.5 source
    ↓
Build LLVM shared libraries (cmake + ninja)
    ├─> libclang-cpp.so.21.1
    ├─> libLLVM.so.21.1
    └─> Third-party deps (libxml2, libz, libicu, liblzma)
    ↓
Clone IWYU 0.25 source
    ↓
Build IWYU against LLVM
    ↓
Set RPATH to $ORIGIN/../lib (patchelf)
    ↓
Bundle LLVM libraries (NOT system libraries)
    ↓
Extract to host
```

### Archive Creation Process

```bash
# 1. Build binaries
./docker/build-iwyu-arm64.sh

# 2. Create archive (zstd level 10!)
cd downloads-bins
uv run create-iwyu-archives --platform linux --arch arm64 --zstd-level 10

# 3. Rename with -fixed suffix
mv iwyu-0.25-linux-arm64.tar.zst iwyu-0.25-linux-arm64-fixed.tar.zst

# 4. Update manifest.json
# 5. Commit to downloads-bins
# 6. Update submodule in main repo
# 7. Verify CI tests pass
```

## Expected Outcomes

### Before Fix
- Archive: 749 KB (broken)
- Binary: Homebrew macOS build
- Libraries: None (no lib/ directory)
- Tests: ❌ SIGSEGV crashes

### After Fix
- Archive: ~200 MB (like x86_64)
- Binary: Proper Linux ARM64 ELF
- Libraries: LLVM-specific libs included
- Tests: ✅ All IWYU tests pass

### Archive Structure

```
iwyu-0.25-linux-arm64-fixed.tar.zst (202 MB)
├── bin/
│   ├── include-what-you-use (3.6 MB)
│   ├── iwyu_tool.py
│   └── fix_includes.py
├── lib/
│   ├── libclang-cpp.so.21.1 (81 MB)
│   ├── libLLVM.so.21.1 (163 MB)
│   ├── libxml2.so.*
│   ├── libz.so.*
│   ├── libicu*.so.*
│   └── liblzma.so.*
└── share/
    └── man/...
```

## Verification Steps

1. **Binary type**: `file bin/include-what-you-use`
   - Should show: ARM aarch64, interpreter `/lib/ld-linux-aarch64.so.1`

2. **RPATH**: `readelf -d bin/include-what-you-use | grep RPATH`
   - Should show: `$ORIGIN/../lib`

3. **Libraries**: `ls -lh lib/`
   - Should have: libclang-cpp, libLLVM, libxml2, libicu, liblzma
   - Should NOT have: libc.so.6, libstdc++.so.6, libm.so.6

4. **Execution**: `./bin/include-what-you-use --version` (in ARM64 Docker)
   - Should print: `include-what-you-use 0.25 based on clang version 21.1.5`

## Lessons Applied from x86_64 Fix

1. ✅ Use zstd level 10 (not 22) to avoid compression corruption
2. ✅ Bundle only LLVM libraries, not system libraries
3. ✅ Set RPATH to `$ORIGIN/../lib` for portability
4. ✅ Use `-fixed` suffix in archive name
5. ✅ Use `refs/heads/main` in manifest URL path
6. ✅ Test binary before committing

## Next Actions (For Repository Owner)

The implementation is complete and ready to execute:

1. **Build the binary**:
   ```bash
   ./docker/build-iwyu-arm64.sh
   ```

2. **Follow the guide**:
   See `docs/IWYU_ARM64_FIX_GUIDE.md` for complete step-by-step instructions

3. **Timeline**: Allow 1-2 hours total
   - Build: 30-60 minutes (Docker build)
   - Archive creation: 5-10 minutes
   - Testing: 5-10 minutes
   - Commit & push: 5 minutes

## References

- **TASK.md** - Original problem statement
- **docs/IWYU_ARM64_FIX_GUIDE.md** - Complete implementation guide
- **downloads-bins commits**: 4a2f344, 55468c4, 1b24d21 (x86_64 fix reference)
- **clang-tool-chain commits**: 4c3d6c5, 35e46dc, fb55057 (x86_64 fix reference)

## Technical Specifications

| Aspect | Specification |
|--------|--------------|
| LLVM Version | 21.1.5 |
| IWYU Version | 0.25 |
| Platform | Linux ARM64 (aarch64) |
| Dynamic Linker | /lib/ld-linux-aarch64.so.1 |
| RPATH | $ORIGIN/../lib |
| Compression | zstd level 10 |
| Archive Size | ~202 MB compressed, ~758 MB uncompressed |
| Build System | Docker (linux/arm64), CMake + Ninja |
| Base Image | Ubuntu 24.04 |

## Success Criteria

- [ ] Binary is proper Linux ARM64 ELF
- [ ] Binary has correct dynamic linker path
- [ ] RPATH is set to `$ORIGIN/../lib`
- [ ] lib/ directory contains LLVM libraries
- [ ] lib/ directory does NOT contain system libraries
- [ ] Archive size is ~200 MB
- [ ] Archive compressed with zstd level 10
- [ ] Manifest has `-fixed` suffix and correct SHA256
- [ ] Binary runs `--version` without crash
- [ ] All IWYU tests pass on GitHub Actions ARM64 runners

---

**Created**: 2024-12-31
**Author**: Claude Code
**Status**: Implementation complete, ready for execution
**Estimated execution time**: 1-2 hours
