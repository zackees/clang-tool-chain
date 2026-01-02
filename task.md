# TASK: Fix IWYU ARM64 Linux Archive and Manifest ✅ COMPLETED

## Problem Summary

The IWYU ARM64 Linux tests are failing with:
```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/.clang-tool-chain/iwyu/linux/arm64/bin/include-what-you-use'
```

**Root Cause**: The archive referenced in `manifest.json` contains an old, broken binary (Homebrew macOS binary, not proper Linux ARM64). While we built a new correct binary and updated it in `downloads-bins`, we never created a new archive or updated the manifest.

**GitHub Actions Failure**: https://github.com/zackees/clang-tool-chain/actions/runs/20666259200/job/59339054875

## Current State Analysis

### What Exists
- ✅ Correct Linux ARM64 binary at `downloads-bins/assets/iwyu/linux/arm64/bin/include-what-you-use`
- ✅ Python helper scripts in `downloads-bins/assets/iwyu/linux/arm64/bin/`
- ✅ share/ directory with IWYU mapping files
- ❌ **MISSING**: lib/ directory with LLVM 21.1.5 shared libraries (314 MB, 327 files)

### What's Wrong
1. **Old archive still deployed**: `iwyu-0.25-linux-arm64.tar.zst` (766 KB)
   - Contains broken Homebrew macOS binary
   - Missing LLVM libraries
   - SHA256: `65e9061ea78c6c505f5290b82925c0fa7bd385fdf783852b96ed68db7e78d9dc`

2. **Manifest points to old archive**: `manifest.json` still references the broken archive

3. **lib/ directory deleted**: Was created by dependency collection but accidentally removed during cleanup
   - **IMPORTANT**: lib/ should be in the .tar.zst archive but NOT git-tracked
   - .gitignore already excludes lib/ from git
   - We need to recreate lib/ temporarily to build the archive

### Why lib/ Is Required

From `src/clang_tool_chain/execution/iwyu.py:211-222`:
```python
# On Linux, we need to set LD_LIBRARY_PATH to find shared libraries
install_dir = downloader.get_iwyu_install_dir(platform_name, arch)
lib_dir = install_dir / "lib"

# Check if lib directory exists (it should for Linux with bundled .so files)
if lib_dir.exists():
    # Prepend lib directory to LD_LIBRARY_PATH
    env["LD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{existing_ld_path}"
```

The IWYU binary for Linux ARM64 is built against LLVM 21.1.5 and requires:
- All LLVM libraries (`libLLVM*.so.21.1`)
- All Clang libraries (`libclang*.so.21.1`)
- Third-party dependencies (libxml2, libicu, libz, liblzma, libzstd)
- Total: ~314 MB uncompressed (327 files)

**System libraries excluded** (libc, libstdc++, libm, libgcc_s, libpthread, libdl)

## Solution: Complete Workflow

### Step 1: Recreate lib/ Directory (Temporary - Not Git Tracked)

The lib/ directory was created by our dependency collection system but was deleted. We need to recreate it TEMPORARILY to build the archive. It will NOT be git-tracked (already in .gitignore).

**Re-run dependency collection:**

```bash
# From clang-tool-chain root
cd /c/Users/niteris/dev/clang-tool-chain

# The IWYU build exists in Docker image, re-run build to get output
docker run --platform linux/arm64 --rm --name iwyu-arm64-temp iwyu-arm64-builder

# Extract from container to temporary location
docker cp iwyu-arm64-temp:/output/iwyu-arm64 docker/output/

# Clean up temp container
docker rm iwyu-arm64-temp 2>/dev/null || true

# Run dependency collection - this creates lib/ in downloads-bins
MSYS_NO_PATHCONV=1 docker run --platform linux/arm64 --rm \
  -v "$(pwd)/docker/output/iwyu-arm64:/input:ro" \
  -v "$(pwd)/downloads-bins/assets/iwyu/linux/arm64:/output" \
  iwyu-deps-collector /input /output
```

After this step, you should have:
```
downloads-bins/assets/iwyu/linux/arm64/
├── bin/
│   └── include-what-you-use (3.4 MB)
├── lib/                        # ← RECREATED (temporary, not git-tracked)
│   ├── libLLVM*.so.21.1       # LLVM libraries
│   ├── libclang*.so.21.1      # Clang libraries
│   └── lib*.so.*              # Third-party deps
└── share/
```

**Verification**:
```bash
ls -lh downloads-bins/assets/iwyu/linux/arm64/lib/ | wc -l
# Should show 327 files

du -sh downloads-bins/assets/iwyu/linux/arm64/lib/
# Should show ~314M

# Verify lib/ is NOT staged in git
cd downloads-bins
git status
# lib/ should NOT appear (it's gitignored)
```

### Step 2: Create New Archive (Including lib/)

Navigate to downloads-bins and create the archive:

```bash
cd /c/Users/niteris/dev/clang-tool-chain/downloads-bins/assets/iwyu/linux/arm64

# Create archive with zstd level 10 (NOT 22 - IWYU archives use level 10)
# This includes lib/ in the archive but lib/ remains git-ignored
tar -cf - bin lib share LICENSE.TXT README.md sbom.spdx.json | zstd -10 -T0 -o iwyu-0.25-linux-arm64-fixed.tar.zst

# Generate SHA256
sha256sum iwyu-0.25-linux-arm64-fixed.tar.zst > iwyu-0.25-linux-arm64-fixed.tar.zst.sha256

# Show archive size and checksum
ls -lh iwyu-0.25-linux-arm64-fixed.tar.zst
cat iwyu-0.25-linux-arm64-fixed.tar.zst.sha256
```

**Expected Results**:
- Archive size: ~80-100 MB (compressed from ~320 MB)
- Contains: bin/ (3.4 MB), lib/ (314 MB), share/ (~1 MB), metadata files

**Important Notes**:
- Use `-10` compression level (IWYU standard), NOT `-22` (corrupts large archives)
- Archive name: `iwyu-0.25-linux-arm64-fixed.tar.zst` (with `-fixed` suffix)
- Include LICENSE.TXT, README.md, sbom.spdx.json in the archive
- **lib/ goes IN the archive but NOT in git** (already gitignored)

### Step 3: Verify Archive Contents

```bash
# Test extraction (requires zstd)
mkdir -p /tmp/test-iwyu-arm64
tar -xf iwyu-0.25-linux-arm64-fixed.tar.zst -C /tmp/test-iwyu-arm64

# Verify structure
ls -la /tmp/test-iwyu-arm64/
# Should show: bin/, lib/, share/, LICENSE.TXT, README.md, sbom.spdx.json

ls /tmp/test-iwyu-arm64/lib/ | wc -l
# Should show 327 files

file /tmp/test-iwyu-arm64/bin/include-what-you-use
# Should show: ELF 64-bit LSB pie executable, ARM aarch64

readelf -d /tmp/test-iwyu-arm64/bin/include-what-you-use | grep -E "RUNPATH|RPATH"
# Should show: Library runpath: [$ORIGIN/../lib]

# Clean up
rm -rf /tmp/test-iwyu-arm64
```

### Step 4: Update Manifest

Update `manifest.json` with the new archive details:

```bash
cd /c/Users/niteris/dev/clang-tool-chain/downloads-bins/assets/iwyu/linux/arm64

# Get the new SHA256
NEW_SHA256=$(cat iwyu-0.25-linux-arm64-fixed.tar.zst.sha256 | awk '{print $1}')
echo "New SHA256: $NEW_SHA256"
```

Edit `manifest.json`:
```json
{
  "latest": "0.25",
  "0.25": {
    "href": "https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst",
    "sha256": "PUT_NEW_SHA256_HERE"
  }
}
```

**CRITICAL**: The URL must use the GitHub LFS media server format:
```
https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/...
```

NOT:
```
https://github.com/zackees/clang-tool-chain-bins/blob/main/assets/...
```

### Step 5: Clean Up lib/ Directory

After creating the archive, **remove lib/ from the working directory** since it's not git-tracked:

```bash
cd /c/Users/niteris/dev/clang-tool-chain/downloads-bins/assets/iwyu/linux/arm64

# Remove lib/ (it's now in the archive, doesn't need to be on disk)
rm -rf lib/

# Also remove docker/output build artifacts
rm -rf /c/Users/niteris/dev/clang-tool-chain/docker/output/iwyu-arm64/

# Verify git status - lib/ should not appear
cd /c/Users/niteris/dev/clang-tool-chain/downloads-bins
git status
# Should only show: iwyu-0.25-linux-arm64-fixed.tar.zst, .sha256, manifest.json
```

### Step 6: Test with Docker (Verification)

Before committing, verify the binary works in a clean Ubuntu ARM64 environment:

```bash
cd /c/Users/niteris/dev/clang-tool-chain/downloads-bins/assets/iwyu/linux/arm64

# Extract archive for testing
mkdir -p test-extract
tar -xf iwyu-0.25-linux-arm64-fixed.tar.zst -C test-extract

# Test binary loads libraries correctly
docker run --platform linux/arm64 --rm \
  -v "$(pwd)/test-extract:/iwyu:ro" \
  ubuntu:24.04 \
  /iwyu/bin/include-what-you-use --version

# Expected output: "include-what-you-use 0.25 (..." or LLVM error messages
# If you get "No such file or directory" or linker errors, lib/ is missing/incorrect

# Clean up test extraction
rm -rf test-extract
```

### Step 7: Commit and Push to downloads-bins

```bash
cd /c/Users/niteris/dev/clang-tool-chain/downloads-bins

# Check Git LFS status
git lfs ls-files | grep arm64

# Check what will be committed (lib/ should NOT appear)
git status
# Should show: iwyu-0.25-linux-arm64-fixed.tar.zst, .sha256, manifest.json

# Stage the new archive and updated manifest
git add assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst
git add assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst.sha256
git add assets/iwyu/linux/arm64/manifest.json

# Commit
git commit -m "fix: replace IWYU ARM64 archive with proper Linux build

Replace broken Homebrew macOS binary with correct Linux ARM64 build.
This archive includes LLVM 21.1.5 libraries and all dependencies.

Changes:
- Archive: iwyu-0.25-linux-arm64-fixed.tar.zst (~80-100 MB)
- Binary: Proper Linux ARM64 ELF with /lib/ld-linux-aarch64.so.1
- Libraries: All LLVM 21.1.5 .so files in lib/ (314 MB uncompressed)
- RPATH: Set to \$ORIGIN/../lib for portable loading
- Manifest: Updated with new archive URL and SHA256

Built using Docker-based dependency collection system.
Fixes IWYU ARM64 test failures.

SHA256: [paste the actual SHA256]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push LFS objects first, then the commit
git lfs push origin main
git push origin main
```

### Step 8: Update Submodule in clang-tool-chain

```bash
cd /c/Users/niteris/dev/clang-tool-chain

# Update submodule reference
git add downloads-bins

# Commit
git commit -m "chore: update downloads-bins for IWYU ARM64 fixed archive

Update submodule to include fixed IWYU ARM64 archive with proper
Linux binary and LLVM 21.1.5 libraries.

Fixes: https://github.com/zackees/clang-tool-chain/actions/runs/20666259200

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push
git push origin main
```

### Step 9: Verify CI Passes

After pushing, monitor the GitHub Actions workflow:
- Go to: https://github.com/zackees/clang-tool-chain/actions
- Check "IWYU (Linux ARM64)" job
- Verify all tests pass

Expected test results:
```
tests/test_iwyu.py::TestIWYUInstallation::test_iwyu_binary_dir_exists PASSED
tests/test_iwyu.py::TestIWYUInstallation::test_find_iwyu_tool PASSED
tests/test_iwyu.py::TestIWYUExecution::test_iwyu_version PASSED
tests/test_iwyu.py::TestIWYUExecution::test_iwyu_analyze_file PASSED
tests/test_iwyu.py::TestIWYUExecution::test_iwyu_on_good_file PASSED
```

## Technical Details

### Why the Old Archive Failed

The old `iwyu-0.25-linux-arm64.tar.zst` (766 KB) contained a Homebrew macOS binary:

```bash
$ file bin/include-what-you-use
ELF 64-bit LSB pie executable, ARM aarch64, dynamically linked,
interpreter @@HOMEBREW_PREFIX@@/lib/ld.so
```

This is completely wrong for Linux:
- Uses Homebrew placeholder path instead of `/lib/ld-linux-aarch64.so.1`
- Not a proper Linux binary
- Missing all LLVM libraries
- Size (766 KB) indicates it's missing ~314 MB of dependencies

### Why lib/ Directory Is Critical

The IWYU binary we built is dynamically linked against LLVM 21.1.5:

```bash
$ readelf -d bin/include-what-you-use | grep NEEDED
 0x0000000000000001 (NEEDED)  Shared library: [libLLVMTargetParser.so.21.1]
 0x0000000000000001 (NEEDED)  Shared library: [libLLVMAArch64AsmParser.so.21.1]
 0x0000000000000001 (NEEDED)  Shared library: [libclangFrontendTool.so.21.1]
 # ... (17+ LLVM/Clang libraries)
```

Without lib/ directory in the archive:
- Binary fails to load: "error while loading shared libraries"
- Tests fail with FileNotFoundError
- IWYU cannot run at all

With lib/ directory in archive and `RPATH=$ORIGIN/../lib`:
- Binary finds libraries relative to its location
- Portable across different Linux distributions
- No system LLVM installation required

### Git vs Archive Workflow

**KEY POINT**: lib/ has a dual lifecycle:

1. **In Git** (downloads-bins repo):
   - lib/ is in `.gitignore` - NEVER committed
   - Only bin/, share/, metadata files are tracked
   - Archives (.tar.zst) ARE tracked via Git LFS

2. **In Archive** (.tar.zst file):
   - lib/ IS included in the archive
   - Archive contains: bin/, lib/, share/, metadata
   - Archive is uploaded to GitHub LFS

3. **Workflow**:
   ```
   Build → Create lib/ → Create archive (with lib/) → Delete lib/ → Commit archive
   ```

This keeps the git repo clean while ensuring users get lib/ when they extract the archive.

### Archive Compression Strategy

IWYU archives use zstd level 10 (not 22):
- Level 22: Ultra-compressed but can corrupt large archives (202 MB corrupted for x86_64)
- Level 10: Balanced compression, reliable for archives >200 MB
- Reference: Linux x86_64 archive uses level 10 successfully

### File Structure Reference

Compare with working Linux x86_64 archive:
```
assets/iwyu/linux/x86_64/
├── bin/
│   ├── include-what-you-use (3.6 MB)
│   ├── fix_includes.py
│   └── iwyu_tool.py
├── lib/                        # ← IN ARCHIVE, NOT IN GIT
│   ├── libLLVM*.so.21.1
│   └── libclang*.so.21.1
├── share/include-what-you-use/
│   └── *.imp mapping files
├── LICENSE.TXT
├── README.md
├── sbom.spdx.json
└── iwyu-0.25-linux-x86_64-fixed.tar.zst (202 MB) # ← Git LFS tracked
```

ARM64 should match this structure.

## Troubleshooting

### If lib/ recreation fails

```bash
# Check Docker images exist
docker images | grep iwyu

# If images missing, rebuild from scratch
./docker/build-iwyu-arm64.sh
./docker/collect-deps-arm64.sh
```

### If archive is too small

```bash
# Archive should be 80-100 MB
ls -lh iwyu-0.25-linux-arm64-fixed.tar.zst

# If < 10 MB, lib/ is missing
tar -tzf iwyu-0.25-linux-arm64-fixed.tar.zst | grep "^lib/"
# Should show 327 library files
```

### If lib/ appears in git status

```bash
# Verify .gitignore
cat downloads-bins/.gitignore | grep lib
# Should show: lib/

# If lib/ still appears, it means .gitignore isn't working
# Force remove from git index:
git rm -r --cached lib/
```

### If tests still fail after fix

```bash
# Check manifest URL format
cat downloads-bins/assets/iwyu/linux/arm64/manifest.json
# Must use: media.githubusercontent.com/media/...

# Check SHA256 matches
sha256sum downloads-bins/assets/iwyu/linux/arm64/iwyu-0.25-linux-arm64-fixed.tar.zst
cat downloads-bins/assets/iwyu/linux/arm64/manifest.json
# Values must match exactly
```

## Success Criteria

- [ ] lib/ directory recreated temporarily with 327 files (~314 MB)
- [ ] Archive created: `iwyu-0.25-linux-arm64-fixed.tar.zst` (80-100 MB)
- [ ] SHA256 checksum generated
- [ ] Manifest updated with new archive URL and SHA256
- [ ] Archive verified with Docker Ubuntu test
- [ ] lib/ removed from working directory (not git-tracked)
- [ ] Only archive and manifest committed (lib/ excluded)
- [ ] Changes pushed to downloads-bins (LFS objects uploaded)
- [ ] Submodule updated in clang-tool-chain
- [ ] GitHub Actions IWYU ARM64 tests pass

## Reference Links

- Failed CI Run: https://github.com/zackees/clang-tool-chain/actions/runs/20666259200
- Dependency Collection System: `docker/collect-deps-arm64.sh`
- IWYU Execution Code: `src/clang_tool_chain/execution/iwyu.py`
- Linux x86_64 Fix Commits (reference):
  - downloads-bins: 1b24d21 (properly compressed archive)
  - clang-tool-chain: fb55057 (updated submodule)

---

**Priority**: CRITICAL (blocks ARM64 CI)
**Estimated Time**: 30-60 minutes (mostly Docker operations)
**Key Insight**: lib/ must be IN the archive but NOT in git. This is the correct workflow.
