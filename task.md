# Task: Build Emscripten Binaries for macOS

**Status**: ⚠️ BLOCKED - Requires macOS Hardware
**Priority**: High
**Created**: 2025-11-15
**Last Updated**: 2025-11-15 (Iteration 1)
**Estimated Time**: 2-3 hours (mostly automated build time)

## ⚠️ ITERATION 1 FINDINGS

**Critical Bug Fixed**: ✅ Line 328 in `fetch_and_archive_emscripten.py` now uses correct URL format
- Changed from `raw.githubusercontent.com` to `media.githubusercontent.com`
- This fix must be committed before any builds
- File modified: `downloads-bins/tools/fetch_and_archive_emscripten.py`

**Platform Blocker**: ❌ Current environment is Windows (MINGW64_NT)
- Cannot build macOS binaries from Windows
- Requires native macOS hardware (Intel Mac or Apple Silicon)
- Next iteration should determine macOS hardware availability

**See**: `.agent_task/ITERATION_1.md` for complete analysis and findings

## Executive Summary

The clang-tool-chain package currently provides Emscripten WebAssembly compilation support for Windows x86_64 and Linux x86_64, but **macOS support is pending**. All infrastructure code is complete and tested - we only need to build and distribute the binary archives for macOS platforms.

### Current Platform Support

| Platform | Architecture | Status | Archive Size | Version |
|----------|-------------|--------|--------------|---------|
| Windows  | x86_64      | ✅ Complete | 153 MB | 4.0.19 |
| Linux    | x86_64      | ✅ Complete | 195 MB | 4.0.15 |
| Linux    | arm64       | ⏳ Pending | - | - |
| **macOS**    | **x86_64**      | **⏳ Pending** | **~150-200 MB** | **4.0.x** |
| **macOS**    | **arm64**       | **⏳ Pending** | **~150-200 MB** | **4.0.x** |

### Why This is Straightforward

- ✅ All wrapper code supports macOS (darwin platform)
- ✅ Build scripts work on macOS (`fetch_and_archive_emscripten.py`)
- ✅ Downloader supports macOS manifests
- ✅ Testing infrastructure ready
- ✅ Recent Windows builds provide a proven template
- ✅ Node.js bundling tested and working
- ⚠️ **Only missing**: The actual binary archives

---

## Recent Emscripten Work (Context)

The last week saw intensive Emscripten development (commits dbf1ec8-8f6ce3d):

1. **Nov 15, 8f6ce3d**: Added `emar` tool + auto-configuration
   - Automatic `.emscripten` config generation
   - LLVM binary linking from main toolchain
   - `EM_CONFIG` environment variable management

2. **Nov 15, 0e5e0d5-2c63114**: Windows binary fixes (5 commits)
   - Fixed Git LFS URLs (`media.githubusercontent.com`)
   - Fixed critical file preservation (`emscripten-version.txt`)
   - Fixed archive structure
   - Fixed manifest format

3. **Nov 15, 6828d35**: Added Windows x86_64 binaries (153 MB)

4. **Nov 11, dbf1ec8**: Comprehensive test suite (741 lines)
   - Tests: header compilation, multi-file builds, object files
   - Tests: thin archives, static linking, PCH generation

**All these fixes apply to macOS** - we're building on a solid foundation.

---

## Prerequisites

### Hardware Requirements

You need **native macOS hardware** for each architecture:

- **For darwin-x86_64**: Intel Mac OR Apple Silicon Mac (can build via Rosetta 2)
- **For darwin-arm64**: Apple Silicon Mac (M1/M2/M3/M4)

**Note**: Cannot use Docker (produces Linux binaries) or cross-compile (LLVM binaries are platform-specific).

### Software Requirements

```bash
# macOS native Python (complete standard library)
python3 --version  # Should be 3.9+

# Git (for cloning emsdk)
git --version

# pyzstd for compression (install if missing)
pip3 install pyzstd

# Verify downloads-bins submodule is present
ls downloads-bins/tools/fetch_and_archive_emscripten.py
```

### Resource Requirements

- **Disk space**: ~2-5 GB during build, ~200 MB for final archive
- **Time**: 30-60 minutes per architecture (mostly automated)
- **Network**: ~500 MB download (emsdk + LLVM/Clang)

---

## Step-by-Step Build Process

### Step 1: Prepare Environment

```bash
# Navigate to build tools directory
cd downloads-bins/tools

# Verify script exists
ls -lh fetch_and_archive_emscripten.py

# Check Python environment
python3 --version
python3 -c "import ssl, ctypes, zlib"  # Verify complete stdlib

# Install pyzstd if needed
pip3 install pyzstd
```

### Step 2: Build darwin-x86_64 Archive

**On Intel Mac or Apple Silicon (Rosetta 2)**:

```bash
# Build the archive (this will take 30-60 minutes)
python3 fetch_and_archive_emscripten.py --platform darwin --arch x86_64

# Expected output:
# - Clones emsdk repository
# - Installs Emscripten latest version (likely 4.0.x)
# - Strips unnecessary files (docs, tests, examples)
# - Creates emscripten-{version}-darwin-x86_64.tar.zst
# - Generates checksums (SHA256, MD5)
# - Creates manifest.json

# Verify output files
ls -lh emscripten-*-darwin-x86_64.tar.zst
cat manifest.json  # Check version and SHA256
```

**Expected Archive Size**: ~150-200 MB compressed, ~800-1400 MB uncompressed

### Step 3: Build darwin-arm64 Archive

**On Apple Silicon Mac**:

```bash
# Build the archive (this will take 30-60 minutes)
python3 fetch_and_archive_emscripten.py --platform darwin --arch arm64

# Expected output: Same as x86_64 but for arm64
# - emscripten-{version}-darwin-arm64.tar.zst
# - manifest.json with arm64 checksums

# Verify output files
ls -lh emscripten-*-darwin-arm64.tar.zst
cat manifest.json
```

### Step 4: Test Archives Locally (Optional but Recommended)

```bash
# Test extraction
mkdir -p test_extract
cd test_extract
tar --use-compress-program=unzstd -xf ../emscripten-*-darwin-*.tar.zst

# Verify structure
ls -la
# Should contain:
# - upstream/emscripten/ (Python scripts)
# - upstream/bin/ (LLVM/Clang with WebAssembly backend)
# - upstream/lib/ (system libraries)
# - .emscripten (config file)
# - emscripten-version.txt (CRITICAL - must be present!)

# Check critical file exists
cat emscripten-version.txt  # Should show version number

# Quick sanity test (won't work without full setup, but scripts should exist)
ls upstream/emscripten/emcc.py
ls upstream/emscripten/em++.py
ls upstream/emscripten/emar.py

cd ..
rm -rf test_extract
```

---

## Archive Distribution

### Step 5: Handle Archive Size (If Needed)

GitHub has a 100 MB file size limit. If archives exceed 100 MB, split them:

```bash
# Check archive size
ls -lh emscripten-*-darwin-*.tar.zst

# If > 100 MB, split into 95 MB parts
python3 split_archive.py --archive emscripten-{version}-darwin-x86_64.tar.zst --part-size-mb 95

# This creates:
# - emscripten-{version}-darwin-x86_64.tar.zst.part0
# - emscripten-{version}-darwin-x86_64.tar.zst.part1
# - manifest.json (updated with parts array)

# Repeat for arm64 if needed
python3 split_archive.py --archive emscripten-{version}-darwin-arm64.tar.zst --part-size-mb 95
```

**Note**: Windows archive (153 MB) is currently NOT split, so you may choose to split or keep as single file.

### Step 6: Upload to downloads-bins Repository

```bash
# Navigate to downloads-bins repository
cd ../../downloads-bins  # From tools/ directory

# Create platform directories if they don't exist
mkdir -p assets/emscripten/darwin/x86_64
mkdir -p assets/emscripten/darwin/arm64

# Copy archives and manifests
cp ../tools/emscripten-*-darwin-x86_64.tar.zst* assets/emscripten/darwin/x86_64/
cp ../tools/manifest.json assets/emscripten/darwin/x86_64/manifest.json

cp ../tools/emscripten-*-darwin-arm64.tar.zst* assets/emscripten/darwin/arm64/
cp ../tools/manifest.json assets/emscripten/darwin/arm64/manifest.json

# Add to Git LFS (archives are binary files)
git lfs track "assets/emscripten/darwin/**/*.tar.zst*"
git add .gitattributes

# Add files
git add assets/emscripten/darwin/

# Commit
git commit -m "feat(emscripten): add darwin-x86_64 and darwin-arm64 builds

- Built Emscripten {version} for macOS Intel and Apple Silicon
- Archive sizes: ~150-200 MB compressed per platform
- Includes LLVM/Clang WebAssembly backend
- Includes Binaryen tools and system libraries
- Critical files preserved (emscripten-version.txt)"

# Push to repository
git push origin main
```

### Step 7: Verify Git LFS Upload

```bash
# After push completes, verify LFS files uploaded
git lfs ls-files

# Should show:
# assets/emscripten/darwin/x86_64/emscripten-*.tar.zst* - ...
# assets/emscripten/darwin/arm64/emscripten-*.tar.zst* - ...

# Get the raw download URLs (will be needed for manifests)
# Format: https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/emscripten/darwin/x86_64/emscripten-{version}-darwin-x86_64.tar.zst
```

---

## Manifest Updates

### Step 8: Update Root Manifest

The root manifest at `assets/emscripten/manifest.json` lists all platforms:

```bash
cd assets/emscripten

# Edit manifest.json
# Current structure:
# {
#   "platforms": {
#     "linux": {...},
#     "win": {...},
#     "darwin": {...}  # Currently has PENDING for x86_64 and arm64
#   }
# }

# Update the "darwin" section to include actual manifests
```

**Before**:
```json
"darwin": {
  "x86_64": {"latest": "PENDING", "versions": {}},
  "arm64": {"latest": "PENDING", "versions": {}}
}
```

**After**:
```json
"darwin": {
  "x86_64": {
    "latest": "4.0.x",
    "versions": {
      "4.0.x": {
        "href": "https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/emscripten/darwin/x86_64/emscripten-4.0.x-darwin-x86_64.tar.zst",
        "sha256": "<actual-sha256-from-build>"
      }
    }
  },
  "arm64": {
    "latest": "4.0.x",
    "versions": {
      "4.0.x": {
        "href": "https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/emscripten/darwin/arm64/emscripten-4.0.x-darwin-arm64.tar.zst",
        "sha256": "<actual-sha256-from-build>"
      }
    }
  }
}
```

**If using multi-part archives**, the structure changes to:

```json
"darwin": {
  "x86_64": {
    "latest": "4.0.x",
    "versions": {
      "4.0.x": {
        "parts": [
          {
            "href": "https://media.githubusercontent.com/media/.../emscripten-4.0.x-darwin-x86_64.tar.zst.part0",
            "sha256": "<part0-sha256>"
          },
          {
            "href": "https://media.githubusercontent.com/media/.../emscripten-4.0.x-darwin-x86_64.tar.zst.part1",
            "sha256": "<part1-sha256>"
          }
        ]
      }
    }
  }
}
```

### Step 9: Verify URL Format

**CRITICAL**: Use `media.githubusercontent.com` for Git LFS files, NOT `raw.githubusercontent.com`

✅ **Correct**: `https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/emscripten/darwin/x86_64/emscripten-4.0.x-darwin-x86_64.tar.zst`

❌ **Wrong**: `https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/emscripten/darwin/x86_64/emscripten-4.0.x-darwin-x86_64.tar.zst`

**Why**: `raw.githubusercontent.com` serves the Git LFS pointer file (text), not the actual binary. This causes checksum mismatches and download failures.

**Reference**: Fixed in commit 0e5e0d5 for Windows builds.

### Step 10: Commit Manifest Updates

```bash
# In downloads-bins repository
git add assets/emscripten/manifest.json
git add assets/emscripten/darwin/x86_64/manifest.json  # If platform-specific manifests exist
git add assets/emscripten/darwin/arm64/manifest.json

git commit -m "feat(emscripten): update manifests for darwin x86_64 and arm64

- Set darwin x86_64 latest to version {version}
- Set darwin arm64 latest to version {version}
- Added download URLs and SHA256 checksums
- Using media.githubusercontent.com for LFS files"

git push origin main
```

---

## Testing & Validation

### Step 11: Test Installation from Main Repository

Return to the main `clang-tool-chain` repository and test:

```bash
# Clean any existing Emscripten installation
clang-tool-chain purge --yes

# Or manually:
rm -rf ~/.clang-tool-chain/emscripten

# Pull latest downloads-bins submodule changes
git submodule update --remote downloads-bins
git add downloads-bins
git commit -m "chore: update downloads-bins submodule for darwin emscripten"

# Test Emscripten download and installation
clang-tool-chain-emcc --version

# Expected behavior:
# 1. Detects darwin platform and architecture
# 2. Downloads manifest from downloads-bins
# 3. Downloads archive (or parts) from media.githubusercontent.com
# 4. Verifies SHA256 checksum
# 5. Extracts to ~/.clang-tool-chain/emscripten/darwin/{arch}/
# 6. Creates .emscripten config file
# 7. Links LLVM binaries from main toolchain
# 8. Runs emcc --version

# Should show: emcc (Emscripten gcc/clang-like replacement) 4.0.x
```

### Step 12: Test Node.js Bundling

```bash
# Node.js should auto-download if not present
clang-tool-chain-node --version

# Should download bundled Node.js and show version
# Expected: v23.x or v24.x (bundled version)
```

### Step 13: Run Compilation Tests

```bash
# Test basic compilation
uv run pytest tests/test_emscripten.py -v

# Test comprehensive pipeline (if tests are updated for macOS)
uv run pytest tests/test_emscripten_full_pipeline.py -v

# Tests should cover:
# - Header compilation (-c header.h)
# - Multi-file builds (main.c + lib.c)
# - Object file generation (-c)
# - Thin archive creation (ar rcsT)
# - Static library linking
# - Precompiled headers (.pch)
# - WebAssembly output (.wasm)
```

### Step 14: Manual Compilation Test

```bash
# Create a simple hello world
cat > hello.c << 'EOF'
#include <stdio.h>
int main() {
    printf("Hello from Emscripten on macOS!\n");
    return 0;
}
EOF

# Compile to WebAssembly
clang-tool-chain-emcc hello.c -o hello.html

# Should create:
# - hello.html (test page)
# - hello.js (JavaScript glue code)
# - hello.wasm (WebAssembly binary)

# Run with Node.js
clang-tool-chain-node hello.js

# Should print: Hello from Emscripten on macOS!

# Clean up
rm hello.c hello.html hello.js hello.wasm
```

---

## Known Issues & Solutions

### Issue 1: Critical File Preservation

**Problem**: `emscripten-version.txt` was being stripped from archives during build.

**Symptom**: Emscripten initialization fails with "cannot determine version".

**Solution**: The build script (`fetch_and_archive_emscripten.py`) now preserves critical files:
- `emscripten-version.txt`
- `.emscripten` (config file)
- `LLVM_ROOT` file
- Version-related files

**Reference**: Fixed in commit afc013e (Nov 15)

**Verification**: After extraction, check `cat emscripten-version.txt` shows version number.

### Issue 2: Git LFS URL Format

**Problem**: Using `raw.githubusercontent.com` URLs for LFS files serves pointer file instead of binary.

**Symptom**: SHA256 checksum mismatch, tiny downloads (~130 bytes), download failures.

**Solution**: Always use `media.githubusercontent.com/media/...` for LFS files.

**Reference**: Fixed in commit 0e5e0d5 (Nov 15)

**Verification**: Download should be ~150-200 MB, not ~130 bytes.

### Issue 3: Configuration File Generation

**Problem**: `.emscripten` config file had incorrect paths or missing entries.

**Symptom**: Emscripten can't find LLVM binaries, Node.js, or Binaryen tools.

**Solution**: Auto-generate `.emscripten` config on first use with correct paths:
```python
LLVM_ROOT = '{path_to_clang_tool_chain}/llvm/bin'
BINARYEN_ROOT = '{path_to_emscripten}/upstream/bin'
NODE_JS = '{path_to_bundled_node}/node'
```

**Reference**: Fixed in commit 8f6ce3d (Nov 15)

**Verification**: Check `~/.clang-tool-chain/emscripten/darwin/{arch}/.emscripten` after first run.

### Issue 4: LLVM Binary Duplication

**Problem**: Emscripten includes LLVM/Clang binaries (~500 MB), duplicating main toolchain.

**Solution**: Link LLVM binaries from main clang-tool-chain installation to Emscripten bin directory:
```bash
# Automated by wrapper on first use
ln -s ~/.clang-tool-chain/llvm/darwin/{arch}/bin/clang \
      ~/.clang-tool-chain/emscripten/darwin/{arch}/upstream/bin/clang
```

**Benefits**:
- Smaller archives (~150-200 MB instead of ~650-850 MB)
- Reduced disk usage (~400-500 MB savings)
- Single LLVM installation to maintain

**Reference**: Implemented in commit 8f6ce3d (Nov 15)

### Issue 5: Python Environment on macOS

**Problem**: Some Python environments lack complete standard library (ctypes, ssl, etc.).

**Symptom**: emsdk installation fails with "No module named '_ctypes'" or similar.

**Solution**: Use macOS system Python (`/usr/bin/python3`) or official Python.org installer.

**Verification**:
```bash
python3 -c "import ssl, ctypes, zlib, lzma, bz2"
# Should complete without errors
```

---

## Complete Checklist

### Build Phase
- [ ] Verify macOS hardware access (Intel for x86_64, Apple Silicon for arm64)
- [ ] Install prerequisites (Python 3.9+, Git, pyzstd)
- [ ] Navigate to `downloads-bins/tools/`
- [ ] Build darwin-x86_64 archive: `python3 fetch_and_archive_emscripten.py --platform darwin --arch x86_64`
- [ ] Build darwin-arm64 archive: `python3 fetch_and_archive_emscripten.py --platform darwin --arch arm64`
- [ ] Verify archive sizes (~150-200 MB each)
- [ ] Verify checksums generated (SHA256, MD5)
- [ ] Test local extraction (optional but recommended)
- [ ] Verify `emscripten-version.txt` exists in extracted archive

### Distribution Phase
- [ ] Check archive sizes (if >100 MB, consider splitting with `split_archive.py`)
- [ ] Copy archives to `downloads-bins/assets/emscripten/darwin/x86_64/`
- [ ] Copy archives to `downloads-bins/assets/emscripten/darwin/arm64/`
- [ ] Copy manifests to platform directories
- [ ] Configure Git LFS tracking: `git lfs track "assets/emscripten/darwin/**/*.tar.zst*"`
- [ ] Add and commit to downloads-bins repository
- [ ] Push to GitHub (verify LFS upload with `git lfs ls-files`)
- [ ] Verify archives accessible via `media.githubusercontent.com` URLs

### Manifest Phase
- [ ] Update `assets/emscripten/manifest.json` (root manifest)
- [ ] Set darwin x86_64 "latest" version
- [ ] Set darwin arm64 "latest" version
- [ ] Add download URLs (use `media.githubusercontent.com`, NOT `raw.githubusercontent.com`)
- [ ] Add SHA256 checksums from build
- [ ] If using multi-part archives, use "parts" array format
- [ ] Commit and push manifest updates

### Testing Phase
- [ ] Update clang-tool-chain submodule: `git submodule update --remote downloads-bins`
- [ ] Clean existing installation: `clang-tool-chain purge --yes`
- [ ] Test download: `clang-tool-chain-emcc --version`
- [ ] Verify archive downloads from correct URL
- [ ] Verify SHA256 verification passes
- [ ] Verify extraction to `~/.clang-tool-chain/emscripten/darwin/{arch}/`
- [ ] Verify `.emscripten` config created automatically
- [ ] Verify LLVM binaries linked correctly
- [ ] Test Node.js bundling: `clang-tool-chain-node --version`
- [ ] Run basic test: `uv run pytest tests/test_emscripten.py -v`
- [ ] Run pipeline test: `uv run pytest tests/test_emscripten_full_pipeline.py -v`
- [ ] Manual compilation test (hello.c → hello.wasm → run with Node.js)

### Documentation Phase
- [ ] Update `docs/EMSCRIPTEN.md` with macOS support status
- [ ] Update version table in `CLAUDE.md` (change macOS rows from PENDING to version)
- [ ] Add macOS-specific notes if needed (SDK detection, architecture considerations)
- [ ] Update `README.md` if it mentions platform support
- [ ] Consider adding macOS build instructions to `docs/MAINTAINER.md`

### Final Verification
- [ ] Test on both Intel Mac and Apple Silicon (if available)
- [ ] Verify both architectures download correct binary
- [ ] Verify cross-architecture safety (arm64 Mac shouldn't download x86_64)
- [ ] Test clean installation on fresh machine (no cached files)
- [ ] Verify disk usage reasonable (~1.5-2 GB total for full installation)
- [ ] Check CI/CD pipeline still passes (if macOS runners available)

---

## Success Criteria

✅ **Builds Complete**:
- [ ] darwin-x86_64 archive built (~150-200 MB)
- [ ] darwin-arm64 archive built (~150-200 MB)
- [ ] Both archives contain all critical files
- [ ] Both archives extract correctly

✅ **Distribution Working**:
- [ ] Archives uploaded to Git LFS
- [ ] Accessible via `media.githubusercontent.com` URLs
- [ ] SHA256 checksums match
- [ ] Manifests updated with correct information

✅ **Installation Working**:
- [ ] `clang-tool-chain-emcc --version` triggers download
- [ ] Download completes successfully
- [ ] SHA256 verification passes
- [ ] Extraction succeeds
- [ ] Configuration auto-generated
- [ ] Shows correct Emscripten version

✅ **Compilation Working**:
- [ ] Can compile simple C program to WebAssembly
- [ ] Generated `.wasm` file is valid
- [ ] Node.js can execute WebAssembly output
- [ ] Multi-file compilation works
- [ ] Static libraries work
- [ ] All pipeline tests pass

✅ **Documentation Updated**:
- [ ] EMSCRIPTEN.md reflects macOS support
- [ ] CLAUDE.md version table updated
- [ ] Any macOS-specific quirks documented

---

## Troubleshooting Guide

### Build Fails with "No module named '_ctypes'"

**Cause**: Python environment missing standard library components.

**Fix**: Use macOS system Python or official Python.org installer:
```bash
/usr/bin/python3 fetch_and_archive_emscripten.py --platform darwin --arch x86_64
```

### Build Fails with "Cannot find Git"

**Cause**: Git not installed or not in PATH.

**Fix**: Install Xcode Command Line Tools:
```bash
xcode-select --install
```

### Archive Size Much Larger Than Expected (>500 MB)

**Cause**: LLVM binaries not stripped, or extra files included.

**Fix**: Check build script filters are working. Expected ~150-200 MB compressed.

### Download Fails with Checksum Mismatch

**Cause**: Using `raw.githubusercontent.com` instead of `media.githubusercontent.com`.

**Fix**: Update manifest URLs to use `media.githubusercontent.com/media/...`.

### Emscripten Version Detection Fails

**Cause**: `emscripten-version.txt` missing from archive.

**Fix**: Verify file exists after extraction. If missing, rebuild archive with updated script.

### Compilation Fails: "Cannot find clang"

**Cause**: LLVM binaries not linked correctly.

**Fix**: Check `.emscripten` config file has correct `LLVM_ROOT` path. Wrapper should auto-link on first use.

### Tests Fail on Apple Silicon with Rosetta

**Cause**: Architecture mismatch (running x86_64 binary on arm64).

**Fix**: Ensure using correct architecture binary (`clang-tool-chain-emcc` should auto-detect).

---

## Timeline Estimate

| Phase | Time | Description |
|-------|------|-------------|
| Preparation | 15 min | Install prerequisites, navigate to build directory |
| Build darwin-x86_64 | 30-60 min | Automated build process |
| Build darwin-arm64 | 30-60 min | Automated build process |
| Upload & Manifest | 20 min | Upload archives, update manifests |
| Testing | 20 min | Installation and compilation tests |
| Documentation | 15 min | Update docs with macOS support |
| **Total** | **2-3 hours** | Mostly automated build time |

**Parallelization**: If you have both Intel and Apple Silicon Macs available, builds can run in parallel, reducing total time to ~1-1.5 hours.

---

## Notes for Maintainers

### Version Alignment

Consider aligning macOS version with Windows (4.0.19) or Linux (4.0.15) for consistency. The build script uses `emsdk install latest`, which will fetch the current latest version (likely 4.0.x series).

**Recommendation**: Build all platforms at once to ensure version consistency across the project.

### Multi-Part Archives

Windows archive (153 MB) is currently NOT split despite exceeding the 100 MB limit. Decision points:

1. **Keep as single file**: Simpler manifest, single download
2. **Split into parts**: Follows GitHub's 100 MB recommendation, more future-proof

**Recommendation**: If macOS archives are 150-200 MB, split into 2 parts (95 MB + remainder) for consistency.

### Architecture Testing

Ideally, test on:
- Intel Mac (native x86_64)
- Apple Silicon Mac running x86_64 binary via Rosetta 2
- Apple Silicon Mac running arm64 binary (native)

This ensures both architectures work and auto-detection is correct.

### CI/CD Integration

If GitHub Actions provides macOS runners:
- Add macOS jobs to `.github/workflows/test-emscripten.yml`
- Test on both `macos-13` (Intel) and `macos-14` (Apple Silicon)
- Verify downloads work in CI environment

### Future Improvements

1. **Automated builds**: GitHub Actions workflow to build and publish on new Emscripten releases
2. **Version pinning**: Option to install specific Emscripten version, not just latest
3. **Cache integration**: sccache support for Emscripten compilation (like Clang/LLVM)
4. **Incremental updates**: Delta downloads for version upgrades

---

## References

### Recent Commits (Nov 11-15, 2025)
- `8f6ce3d`: Added emar tool + auto-configuration
- `0e5e0d5`: Fixed media.githubusercontent.com URLs
- `afc013e`: Fixed emscripten-version.txt preservation
- `2c63114`: Fixed archive structure
- `6828d35`: Added Windows x86_64 binaries
- `dbf1ec8`: Added comprehensive test suite

### Documentation
- [docs/EMSCRIPTEN.md](docs/EMSCRIPTEN.md) - Emscripten usage guide
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Manifest and archive system
- [docs/MAINTAINER.md](docs/MAINTAINER.md) - Build and distribution tools
- [docs/TESTING.md](docs/TESTING.md) - Test infrastructure

### External Resources
- [Emscripten SDK](https://github.com/emscripten-core/emsdk)
- [Emscripten Documentation](https://emscripten.org/docs/)
- [Git LFS Documentation](https://git-lfs.github.com/)

---

## Contact

For questions or issues during the build process:
- Check the troubleshooting guide above
- Review recent commit history for similar fixes
- Consult `docs/MAINTAINER.md` for build tool details
- Test on a clean environment if issues persist

---

**Status**: Ready to execute when macOS hardware is available.
**Next Steps**: Follow Step 1 (Prepare Environment) on macOS machine.
