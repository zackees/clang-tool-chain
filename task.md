# IWYU Linux ARM64 Fix Task

## Status: TODO

The Linux ARM64 IWYU tests are failing because the archive has the same issues as x86_64 had:
1. Includes bundled system libraries (libc, libstdc++, etc.) that should not be distributed
2. Small archive size (766KB) suggests it may be missing LLVM libraries or corrupted
3. Possibly has the same compression corruption issue as x86_64

## Background: What We Fixed for Linux x86_64

### Original Problem
The Linux x86_64 IWYU binary was crashing with SIGSEGV (signal 11) immediately upon execution.

### Root Causes Identified

1. **Bundled System Libraries (Primary Issue)**
   - The archive incorrectly included system libraries:
     - `libc.so.6` (glibc)
     - `libm.so.6` (math library)
     - `libgcc_s.so.1` (GCC runtime)
     - `libstdc++.so.6` (C++ standard library)

   - **Why this is wrong**: On Linux, these libraries should NEVER be bundled with applications
     - They must come from the host system
     - The bundled `libc.so.6` was itself dynamically linked (invalid - real glibc is not dynamically linked)
     - This caused the dynamic linker to fail with SIGSEGV
     - Even if not corrupted, would cause ABI incompatibilities

2. **Compression Corruption (Secondary Issue)**
   - First fix attempt used zstd level 22 compression
   - Created a 54MB archive with SHA256: `519f13c0102af406669316d76bf1348cf6f23a6c9650065f3b4cd964517e1f93`
   - Archive was corrupted/truncated during compression
   - Error: "zstd data ends in an incomplete frame, maybe the input data was truncated"

   - **Solution**: Recreated with zstd level 10 instead
   - Produced working 202MB archive
   - Decompresses successfully to 758MB

### What We Kept in the Archive

**LLVM-specific libraries (correct to bundle):**
- `libclang-cpp.so.21.1` - Clang C++ API
- `libLLVM.so.21.1` - LLVM core
- `libLLVM-21.so` - LLVM version link
- `libxml2.so.2.9.13` - XML parsing (LLVM dependency)
- `libz.so.1.2.11` - Compression (LLVM dependency)
- `libicu*.so.70.1` - Unicode support (LLVM dependency)
- `liblzma.so.5.2.5` - LZMA compression (LLVM dependency)

**Python helper scripts:**
- `include-what-you-use` binary
- `iwyu_tool.py`
- `fix_includes.py`

### Final Working x86_64 Configuration

**Archive Details:**
- Filename: `iwyu-0.25-linux-x86_64-fixed.tar.zst`
- Size: 202MB compressed → 758MB uncompressed
- SHA256: `b731a01834d7390023a2e30a2b6f644e98054fa07232f7cf056c0249fba7aa8d`
- Compression: zstd level 10
- Location: `downloads-bins/assets/iwyu/linux/x86_64/`

**Binary Configuration:**
- RUNPATH: `$ORIGIN/../lib` (correct - searches relative to binary)
- Dynamic linker: `/lib64/ld-linux-x86-64.so.2` (standard)
- Uses system libc/libstdc++/libm (correct)
- Bundles only LLVM libraries (correct)

## Key Lessons from x86_64 Fix

1. **Never bundle system libraries on Linux** (libc, libstdc++, libm, libgcc_s)
2. **Only bundle application-specific libraries** (LLVM, ICU, libxml2, etc.)
3. **Use zstd level 10, not 22** for large archives to avoid corruption
4. **Verify decompression** before pushing
5. **Test with `readelf -d`** to check dependencies
6. **Add diagnostic logging** for future debugging (LD_DEBUG=libs)

## Reference: x86_64 Fix Commits

- **downloads-bins repo:**
  - 4a2f344: Initial fix removing system libraries (had wrong SHA256)
  - 55468c4: Corrected SHA256 hash
  - 1b24d21: Replaced with properly compressed archive (zstd level 10)

- **clang-tool-chain repo:**
  - 4c3d6c5: Added verbose crash diagnostics to tests
  - 35e46dc: Updated submodule for corrected hash
  - fb55057: Updated submodule for properly compressed archive

---

**Created**: 2025-12-31
**Status**: Ready for implementation
**Reference**: Linux x86_64 IWYU fix
