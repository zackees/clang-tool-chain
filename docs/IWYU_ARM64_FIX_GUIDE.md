# IWYU Linux ARM64 Fix Guide

This guide documents the complete process for fixing the IWYU Linux ARM64 archive.

## Problem Summary

The Linux ARM64 IWYU archive has these critical issues:

1. **Homebrew binary**: The binary is built for macOS Homebrew (`@@HOMEBREW_PREFIX@@/lib/ld.so`), not Linux
2. **Missing LLVM libraries**: No `lib/` directory - missing `libclang-cpp.so`, `libLLVM.so`, etc.
3. **Tiny archive size**: 749 KB vs expected ~200 MB (similar to x86_64 fixed version)
4. **Wrong archive name**: Missing `-fixed` suffix in manifest

## Background: x86_64 Fix Reference

The x86_64 version had similar issues and was fixed (see commits in TASK.md):

- **Old broken archive**: 291 MB (or 54 MB corrupted version with zstd-22)
- **Fixed archive**: 202 MB with zstd-10 compression
- **Contains**: LLVM libraries (libclang-cpp, libLLVM, libxml2, etc.)
- **Removed**: System libraries (libc, libstdc++, libm, libgcc_s)

## Solution: Build from Source

Since the existing ARM64 binary is a Homebrew build (completely wrong), we must build IWYU from source for Linux ARM64.

### Architecture

```
Build Process:
1. Docker container (linux/arm64)
   └─> Build LLVM 21.1.5 libraries
       └─> Build IWYU 0.25 against LLVM
           └─> Bundle LLVM libs (not system libs)
               └─> Set RPATH to $ORIGIN/../lib
                   └─> Extract to host
```

### Files Created

- `docker/Dockerfile.iwyu-arm64-builder` - Multi-stage build for IWYU + LLVM
- `docker/build-iwyu-arm64.sh` - Automated build script
- `docs/IWYU_ARM64_FIX_GUIDE.md` - This documentation

## Step-by-Step Instructions

### Prerequisites

- Docker with ARM64 platform support (Docker Desktop with buildx, or native ARM64 Linux)
- At least 10 GB free disk space
- 4+ GB RAM for Docker
- `uv` Python package manager installed

### Step 1: Build IWYU Binary

From the `clang-tool-chain` root directory:

```bash
# Make sure you're in the right directory
cd /path/to/clang-tool-chain

# Run the build script
./docker/build-iwyu-arm64.sh
```

This script will:
1. Build Docker image with LLVM 21.1.5 and IWYU 0.25
2. Compile both from source (takes 30-60 minutes depending on hardware)
3. Bundle only LLVM-specific libraries
4. Remove system libraries
5. Set RPATH to `$ORIGIN/../lib`
6. Extract to `downloads-bins/assets/iwyu/linux/arm64/`

**Build time**: 30-60 minutes (ARM64 emulation is slow on x86_64 hosts)

### Step 2: Verify the Binary

```bash
cd downloads-bins/assets/iwyu/linux/arm64

# Check binary type
file bin/include-what-you-use
# Should show: ELF 64-bit LSB pie executable, ARM aarch64, dynamically linked, interpreter /lib/ld-linux-aarch64.so.1

# Check RPATH
readelf -d bin/include-what-you-use | grep RPATH
# Should show: $ORIGIN/../lib

# Check dependencies
readelf -d bin/include-what-you-use | grep NEEDED
# Should show: libclang-cpp, libLLVM, libstdc++, libm, etc. (NOT libc.so.6)

# List bundled libraries
ls -lh lib/
# Should show: libclang-cpp.so.21.1, libLLVM.so.21.1, libxml2, libicu, etc.
# Should NOT show: libc.so.6, libstdc++.so.6, libm.so.6, libgcc_s.so.1
```

### Step 3: Create Fixed Archive

```bash
cd downloads-bins

# Create archive with zstd level 10 (NOT 22 to avoid corruption)
uv run create-iwyu-archives --platform linux --arch arm64 --zstd-level 10
```

**CRITICAL**: Use `--zstd-level 10`, not the default level 22!

Level 22 causes corruption on large archives (see TASK.md x86_64 fix history).

This will create:
- `assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64.tar.zst` (~200 MB)
- `assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64.tar.zst.sha256`

### Step 4: Update to Fixed Naming

```bash
cd assets/iwyu/linux/arm64

# Rename to -fixed suffix
mv iwyu-0.25-linux-arm64.tar.zst iwyu-0.25-linux-arm64-fixed.tar.zst
mv iwyu-0.25-linux-arm64.tar.zst.sha256 iwyu-0.25-linux-arm64-fixed.tar.zst.sha256

# Remove old broken archive and typo'd SHA256 file
rm -f iwyu-0.25-linux-arm64.tar.tar.zst.sha256  # Note the double .tar (typo)
# Keep or remove old 749 KB archive as desired

# Get the new SHA256 hash
cat iwyu-0.25-linux-arm64-fixed.tar.zst.sha256
```

### Step 5: Update Manifest

Edit `downloads-bins/assets/iwyu/linux/arm64/manifest.json`:

```json
{
  "latest": "0.25",
  "0.25": {
    "href": "https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/refs/heads/main/assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst",
    "sha256": "<paste the SHA256 hash from step 4>"
  }
}
```

**Important**:
- Change filename to `-fixed` suffix
- Use `refs/heads/main` in URL path (not just `main`)
- Update SHA256 hash

### Step 6: Test Before Committing

Extract and test the archive locally:

```bash
# Create test directory
mkdir -p /tmp/iwyu-test
cd /tmp/iwyu-test

# Extract
tar --use-compress-program=zstd -xf /path/to/downloads-bins/assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst

# Test binary (requires ARM64 system or Docker)
./bin/include-what-you-use --version
# Should print: include-what-you-use 0.25 based on clang version 21.1.5
```

If on x86_64, test in Docker:

```bash
docker run --platform linux/arm64 --rm -it \
    -v /tmp/iwyu-test:/iwyu \
    ubuntu:24.04 \
    /iwyu/bin/include-what-you-use --version
```

### Step 7: Commit to downloads-bins

```bash
cd downloads-bins

# Check status
git status
# Should show:
#   modified: assets/iwyu/linux/arm64/manifest.json
#   new: assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst
#   new: assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst.sha256

# Stage files
git add assets/iwyu/linux/arm64/manifest.json
git add assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst
git add assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst.sha256

# Commit
git commit -m "fix: rebuild IWYU Linux ARM64 with proper LLVM libraries

- Built from source using LLVM 21.1.5
- Removed Homebrew binary (was built for macOS)
- Bundled LLVM libraries (libclang-cpp, libLLVM, etc.)
- Removed system libraries (libc, libstdc++, etc.)
- Set RPATH to \$ORIGIN/../lib
- Compressed with zstd level 10 to avoid corruption
- Archive size: ~200 MB (was 749 KB broken)
- Matches x86_64 fixed architecture

Fixes SIGSEGV crashes on ARM64 Linux runners."

# Push (including LFS)
git push origin main
```

### Step 8: Update clang-tool-chain Submodule

```bash
cd ../..  # Back to clang-tool-chain root

# Update submodule reference
cd downloads-bins
git pull origin main
cd ..

# Commit submodule update
git add downloads-bins
git commit -m "chore: update downloads-bins for fixed ARM64 IWYU

References downloads-bins commit with rebuilt ARM64 IWYU binary."

git push origin main
```

### Step 9: Verify CI Tests

Monitor GitHub Actions:

1. Go to https://github.com/zackees/clang-tool-chain/actions
2. Find workflow: `test-iwyu-linux-arm.yml`
3. Check that tests pass (no SIGSEGV crashes)

Expected test results:
- `test_iwyu_version` - ✅ Should pass (previously crashed)
- `test_iwyu_analyze_file` - ✅ Should pass
- `test_iwyu_with_compile_commands` - ✅ Should pass

## Verification Checklist

Before committing, verify:

- [ ] Binary is proper Linux ARM64 (not Homebrew)
- [ ] Binary has RPATH `$ORIGIN/../lib`
- [ ] `lib/` directory exists with LLVM libraries
- [ ] No system libraries in `lib/` (no libc.so.6, libstdc++.so.6, etc.)
- [ ] Archive is ~200 MB (not 749 KB or 291 MB)
- [ ] Archive compressed with zstd level 10
- [ ] Manifest has `-fixed` suffix
- [ ] Manifest uses `refs/heads/main` URL path
- [ ] SHA256 hash is correct
- [ ] Binary runs `--version` without crash (test in ARM64 Docker)

## Troubleshooting

### Build Fails: Out of Memory

**Problem**: Docker build killed due to OOM

**Solution**:
```bash
# Increase Docker memory limit to 6+ GB in Docker Desktop settings
# Or build on native ARM64 Linux with more RAM
```

### Build Fails: Cannot Pull ARM64 Image

**Problem**: `no match for platform in manifest`

**Solution**:
```bash
# Enable buildx in Docker
docker buildx create --use

# Or use native ARM64 machine
```

### Archive Corruption

**Problem**: `zstd: error 70 : cannot allocate decompression context`

**Solution**: Archive was compressed with level 22 and got corrupted. Rebuild with `--zstd-level 10`.

### Binary Crashes with SIGSEGV

**Problem**: `Segmentation fault (core dumped)`

**Possible causes**:
1. System libraries bundled incorrectly
2. RPATH not set correctly
3. LLVM libraries missing

**Debug**:
```bash
# Check what libraries it's trying to load
LD_DEBUG=libs ./bin/include-what-you-use --version 2>&1 | grep -E "(looking for|calling init)"

# Check RPATH
readelf -d bin/include-what-you-use | grep RPATH

# Check if libraries exist
ldd bin/include-what-you-use
```

## Expected Archive Structure

```
iwyu-0.25-linux-arm64-fixed.tar.zst (202 MB compressed)
└─> Extracted (758 MB):
    ├── bin/
    │   ├── include-what-you-use         (3.6 MB)
    │   ├── iwyu_tool.py                 (19 KB)
    │   └── fix_includes.py              (103 KB)
    ├── lib/
    │   ├── libclang-cpp.so              (81 MB)
    │   ├── libclang-cpp.so.21.1         (81 MB)
    │   ├── libLLVM.so                   (163 MB)
    │   ├── libLLVM.so.21.1              (163 MB)
    │   ├── libLLVM-21.so                (163 MB)
    │   ├── libxml2.so.2.9.13            (varies)
    │   ├── libz.so.1.2.11               (varies)
    │   ├── libicu*.so.70.1              (varies)
    │   └── liblzma.so.5.2.5             (varies)
    ├── share/
    │   └── man/
    │       └── man1/
    │           └── include-what-you-use.1
    ├── LICENSE.TXT
    └── README.md
```

## Related Documentation

- TASK.md - Problem statement and x86_64 fix history
- downloads-bins/CLAUDE.md - Binary distribution repository guide
- docs/TESTING.md - Test infrastructure documentation

## Key Lessons

1. **Never use Homebrew binaries for Linux distribution**
2. **Always build from source for proper Linux ABI**
3. **Use zstd level 10 for large archives** (level 22 causes corruption)
4. **Bundle LLVM libraries, not system libraries**
5. **Set RPATH to `$ORIGIN/../lib`** for portable binaries
6. **Test before committing** (extract + run --version)

## Timeline

- **Problem identified**: December 2024 (ARM64 tests failing)
- **x86_64 fixed**: December 31, 2024 (commits 4a2f344, 55468c4, 1b24d21)
- **ARM64 fix created**: December 31, 2024 (this guide)

---

**Created**: 2024-12-31
**Author**: Claude Code
**Status**: Ready for execution
