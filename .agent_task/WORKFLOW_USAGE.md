# GitHub Actions Workflow: Build LLDB Archives (Linux)

## Overview

This workflow builds LLDB archives with bundled Python 3.10 site-packages for Linux x86_64 and ARM64 platforms. The workflow runs on GitHub Actions infrastructure which has fast network connectivity to download the large LLVM releases (1.9 GB each).

**File:** `.github/workflows/build-lldb-archives-linux.yml`

## Why This Workflow?

The full LLVM releases containing LLDB binaries are very large (~1.9 GB each). Downloading these on a local Windows machine with limited bandwidth is impractical (would take hours and frequently stall). GitHub Actions runners have excellent network connectivity and can download these files in minutes.

## What It Does

For each architecture (x86_64 and/or ARM64):

1. **Downloads LLVM 21.1.5** - Full release from GitHub (1.9 GB)
2. **Extracts LLVM archive** - Tar extraction (~5-10 minutes)
3. **Builds LLDB archive** - Using `create_lldb_archives.py` with Python modules
4. **Compresses with zstd level 22** - Ultra compression (~10-11 MB final size)
5. **Generates SHA256 checksums** - For manifest updates
6. **Uploads artifacts** - 30-day retention for download

## Manual Trigger

This workflow is triggered manually via the GitHub Actions UI:

### Steps to Trigger:

1. Go to: https://github.com/YOUR_USERNAME/clang-tool-chain/actions
2. Click on "Build LLDB Archives (Linux)" workflow in the left sidebar
3. Click "Run workflow" button (top right)
4. Configure inputs:
   - **LLVM version**: `21.1.5` (default)
   - **Architectures**: `x86_64,arm64` (both) or just `x86_64` or `arm64`
5. Click "Run workflow" green button

### Workflow Inputs:

- **`llvm_version`** (required, default: `21.1.5`)
  - LLVM version to download and build
  - Format: `X.Y.Z` (e.g., `21.1.5`)

- **`architectures`** (required, default: `x86_64,arm64`)
  - Comma-separated list of architectures to build
  - Options: `x86_64`, `arm64`, or `x86_64,arm64`
  - Use single arch for faster builds or testing

## Expected Runtime

| Architecture | Download Time | Extract Time | Build Time | Total Time |
|--------------|--------------|--------------|------------|------------|
| Linux x86_64 | ~5-10 min    | ~5-10 min    | ~2-5 min   | ~15-25 min |
| Linux ARM64  | ~5-10 min    | ~5-10 min    | ~2-5 min   | ~15-25 min |
| **Both**     | -            | -            | -          | ~30-50 min |

*Times are estimates based on GitHub Actions runner performance.*

## Output Artifacts

Each job uploads artifacts containing:

### Linux x86_64 Artifact (`lldb-linux-x86_64`)
```
lldb-21.1.5-linux-x86_64.tar.zst         (~10-11 MB)
lldb-21.1.5-linux-x86_64.tar.zst.sha256  (checksum file)
```

### Linux ARM64 Artifact (`lldb-linux-arm64`)
```
lldb-21.1.5-linux-arm64.tar.zst          (~10-11 MB)
lldb-21.1.5-linux-arm64.tar.zst.sha256   (checksum file)
```

### Download Artifacts:

1. Go to the completed workflow run
2. Scroll to "Artifacts" section at bottom
3. Click on artifact name to download (ZIP file)
4. Extract ZIP to get `.tar.zst` and `.sha256` files

## Post-Workflow Steps

After downloading artifacts:

### 1. Extract Artifacts to downloads-bins

```bash
# Extract downloaded artifacts (they're in ZIP format)
unzip lldb-linux-x86_64.zip -d /tmp/
unzip lldb-linux-arm64.zip -d /tmp/

# Copy to downloads-bins repository
cp /tmp/lldb-21.1.5-linux-x86_64.tar.zst downloads-bins/assets/lldb/linux/x86_64/
cp /tmp/lldb-21.1.5-linux-x86_64.tar.zst.sha256 downloads-bins/assets/lldb/linux/x86_64/

cp /tmp/lldb-21.1.5-linux-arm64.tar.zst downloads-bins/assets/lldb/linux/arm64/
cp /tmp/lldb-21.1.5-linux-arm64.tar.zst.sha256 downloads-bins/assets/lldb/linux/arm64/
```

### 2. Update Manifests

Update `downloads-bins/assets/lldb/linux/x86_64/manifest.json`:

```json
{
  "version": "21.1.5",
  "platform": "linux",
  "arch": "x86_64",
  "files": [
    {
      "filename": "lldb-21.1.5-linux-x86_64.tar.zst",
      "sha256": "<SHA256_FROM_CHECKSUM_FILE>",
      "size": <FILE_SIZE_BYTES>,
      "url": "https://github.com/YOUR_USERNAME/downloads-bins/raw/main/assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst"
    }
  ],
  "python_bundled": true,
  "python_version": "3.10"
}
```

Repeat for ARM64 manifest at `downloads-bins/assets/lldb/linux/arm64/manifest.json`.

### 3. Commit to downloads-bins

```bash
cd downloads-bins

# Add new archives and manifests
git add assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst
git add assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst.sha256
git add assets/lldb/linux/x86_64/manifest.json

git add assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst
git add assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst.sha256
git add assets/lldb/linux/arm64/manifest.json

# Commit
git commit -m "Add LLDB 21.1.5 archives with Python 3.10 for Linux x64 and ARM64"

# Push
git push origin main
```

### 4. Update Main Repository Submodule

```bash
cd .. # Back to clang-tool-chain root

# Update submodule reference
git add downloads-bins
git commit -m "Update downloads-bins: LLDB 21.1.5 with Python for Linux"
git push origin main
```

### 5. Test Installation

```bash
# Clean old installation
rm -rf ~/.clang-tool-chain/lldb-linux-x86_64

# Test download and installation
clang-tool-chain-lldb --version

# Verify Python bundling
clang-tool-chain-lldb -b -o "script import lldb; print(f'LLDB version: {lldb.__version__}')" -o quit

# Test on ARM64 (if available)
# rm -rf ~/.clang-tool-chain/lldb-linux-arm64
# clang-tool-chain-lldb --version
```

## Workflow Architecture

### Jobs:

1. **`build-lldb-linux-x86_64`** - Builds x86_64 archive (conditional on input)
2. **`build-lldb-linux-arm64`** - Builds ARM64 archive (conditional on input)
3. **`summary`** - Generates summary report (always runs)

### Key Features:

- **Conditional execution**: Jobs only run if architecture is in input
- **Parallel builds**: x86_64 and ARM64 build simultaneously
- **Timeout protection**: 2-hour timeout per job
- **Artifact retention**: 30 days (configurable)
- **Submodule support**: Checks out downloads-bins submodule
- **Python modules**: Uses pre-prepared modules from Iteration 4

## Troubleshooting

### Issue: Download fails or times out

**Solution:** Re-run the workflow. GitHub's network is usually very fast, but occasional hiccups can occur.

### Issue: Extraction fails

**Symptoms:** Tar extraction fails with errors

**Solution:**
1. Check LLVM release exists at URL
2. Verify version number is correct
3. Check GitHub's download status page

### Issue: Build fails with "LLDB binaries not found"

**Symptoms:** `extract_lldb_binaries()` reports 0 binaries extracted

**Solution:**
1. Verify LLVM release contains LLDB (some releases don't)
2. Check extraction directory structure
3. Verify `--source-dir` path is correct

### Issue: Python modules not found

**Symptoms:** `copy_python_modules()` fails with "Python directory not found"

**Solution:**
1. Verify `downloads-bins/work/python_linux_x64/` exists in repository
2. Check Iteration 4 was completed successfully
3. Re-run `prepare_python_for_linux_lldb.py` if needed

### Issue: Artifacts not uploading

**Symptoms:** No artifacts appear in workflow run

**Solution:**
1. Check build actually completed successfully
2. Verify files exist in expected paths
3. Check GitHub Actions artifact storage quota

## Performance Optimization

### Building Single Architecture

For faster builds or testing, build only one architecture:

```yaml
# In workflow inputs
architectures: x86_64  # Only x86_64
# OR
architectures: arm64   # Only ARM64
```

This cuts workflow time in half (~15-25 minutes vs. 30-50 minutes).

### Caching LLVM Downloads

Future improvement: Cache extracted LLVM directories between runs to avoid re-downloading.

**Implementation:**
```yaml
- uses: actions/cache@v4
  with:
    path: downloads-bins/work/lldb/linux/*/extracted
    key: llvm-${{ github.event.inputs.llvm_version }}-linux-${{ matrix.arch }}
```

## Monitoring Workflow Runs

### View Workflow Status:

1. Go to: https://github.com/YOUR_USERNAME/clang-tool-chain/actions
2. Click on workflow run name
3. Expand each job to see detailed logs

### Download Logs:

1. Click on job name (e.g., "build-lldb-linux-x86_64")
2. Click "..." menu (top right)
3. Select "Download log archive"

### Job Summary:

The workflow automatically generates a summary showing:
- LLVM version used
- Architectures built
- Build results (✅ success, ❌ failed, ⏭️ skipped)
- Next steps checklist

View at: Workflow run page → Summary tab

## Workflow Maintenance

### Update LLVM Version:

When a new LLVM release is available:

1. Update `LLVM_VERSIONS` in `create_lldb_archives.py`
2. Update default input in workflow YAML
3. Trigger workflow with new version

### Add New Architecture:

To support new architecture (e.g., `riscv64`):

1. Add download URL to `LLVM_DOWNLOAD_URLS` in `create_lldb_archives.py`
2. Prepare Python modules with `prepare_python_for_linux_lldb.py`
3. Add new job to workflow YAML
4. Update input validation

### Change Compression Level:

To adjust compression (trade speed vs. size):

```yaml
# In build step, add:
python create_lldb_archives.py \
  --zstd-level 19 \
  # ... other args
```

- Level 22 (default): Slowest, best compression (~10-11 MB)
- Level 19: Faster, slightly larger (~11-13 MB)
- Level 3: Very fast, much larger (~30-40 MB)

## References

- **Workflow file:** `.github/workflows/build-lldb-archives-linux.yml`
- **Archive creation script:** `downloads-bins/tools/create_lldb_archives.py`
- **Python extraction script:** `downloads-bins/tools/prepare_python_for_linux_lldb.py`
- **Iteration 7 findings:** `.agent_task/ITERATION_7.md`
- **Packaging strategy:** `.agent_task/PACKAGING_STRATEGY_LINUX.md`

## Success Criteria

Workflow is successful when:

1. ✅ Both architectures build without errors
2. ✅ Archives are ~10-11 MB each (compressed)
3. ✅ SHA256 checksums generated correctly
4. ✅ Artifacts uploaded and downloadable
5. ✅ No timeout or resource issues

---

**Created:** 2026-01-06 (Iteration 8)
**Status:** Ready for first run
**Next:** Trigger workflow manually on GitHub Actions
