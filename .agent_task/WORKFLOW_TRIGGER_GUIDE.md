# GitHub Actions Workflow Trigger Guide - Build LLDB Archives (Linux)

**Date Created:** 2026-01-06 (Iteration 11)
**Purpose:** Step-by-step instructions for manually triggering the Linux LLDB archive build workflow
**Target Audience:** Repository owner/maintainer with GitHub Actions access

---

## Quick Summary

**What:** Manually trigger GitHub Actions workflow to build LLDB archives for Linux x86_64 and ARM64
**Why:** Agent loop cannot trigger workflows automatically - requires human GitHub UI interaction
**Duration:** ~30-50 minutes for parallel x86_64 and ARM64 builds
**Output:** Two zstd-compressed archives (~10-11 MB each) with SHA256 checksums

---

## Prerequisites

### Access Requirements
- ✅ GitHub account with write access to zackees/clang-tool-chain repository
- ✅ Access to GitHub Actions (Settings → Actions → General → Allow actions)
- ✅ Workflow exists at `.github/workflows/build-lldb-archives-linux.yml`
- ✅ Workflow committed and pushed (commit: 5675fac from Iteration 9)

### Preparation Checklist
- ✅ Python modules ready in `downloads-bins/work/python_linux_x64/` (Iteration 4)
- ✅ Python modules ready in `downloads-bins/work/python_linux_arm64/` (Iteration 4)
- ✅ Workflow file exists and is valid
- ✅ Main branch up-to-date

---

## Step-by-Step Instructions

### Step 1: Navigate to Workflow Page

**URL:**
```
https://github.com/zackees/clang-tool-chain/actions/workflows/build-lldb-archives-linux.yml
```

**Alternative Method:**
1. Go to https://github.com/zackees/clang-tool-chain
2. Click "Actions" tab
3. Find "Build LLDB Archives (Linux)" in left sidebar
4. Click workflow name

**Expected Page:** Workflow runs page with "Run workflow" button in top-right

---

### Step 2: Click "Run workflow" Button

**Location:** Top-right of workflow page, green button

**Action:** Click button to open workflow dispatch form

**Expected Result:** Modal dialog appears with input fields

---

### Step 3: Configure Workflow Inputs

**Form Fields:**

#### 1. Branch Selection
- **Field:** "Use workflow from"
- **Value:** `main`
- **Why:** Latest workflow definition is on main branch

#### 2. LLVM Version
- **Field:** "LLVM version"
- **Value:** `21.1.5`
- **Why:** Current LLDB version for Linux (matches Windows)

#### 3. Architecture
- **Field:** "Architecture to build"
- **Options:** `x86_64`, `arm64`, `both`
- **Recommended:** `both`
- **Why:** Build both architectures in parallel for efficiency

**Example Configuration:**
```
Branch: main
LLVM version: 21.1.5
Architecture: both
```

---

### Step 4: Trigger Workflow

**Action:** Click green "Run workflow" button in modal

**Expected Result:**
- Modal closes
- Workflow run appears at top of list
- Status: "Queued" or "In progress"
- Yellow dot next to workflow run

**Refresh:** Page may auto-refresh, or manually refresh to see new run

---

### Step 5: Monitor Workflow Progress

**Duration:** ~30-50 minutes for both architectures (parallel execution)

**Jobs to Watch:**
1. **build-x86_64** - Linux x86_64 archive build
2. **build-arm64** - Linux ARM64 archive build

**Job Steps (per architecture):**
1. Checkout repository (~10 seconds)
2. Set up Python 3.11 (~15 seconds)
3. Install dependencies (zstandard) (~30 seconds)
4. Download LLVM release (~5-10 minutes, 1.9 GB per arch)
5. Extract LLVM archive (~3-5 minutes)
6. Verify LLDB binaries (~5 seconds)
7. Copy Python modules (~10 seconds)
8. Create LLDB archive with Python (~5-10 minutes)
9. Generate checksums (~5 seconds)
10. Generate summary (~5 seconds)
11. Upload artifacts (~1-2 minutes)

**Monitoring Tips:**
- Expand job steps to see detailed progress
- Check logs for any errors (red X)
- Green checkmark = step completed successfully
- Step 4 (Download LLVM) takes longest - be patient!

---

### Step 6: Verify Successful Completion

**Success Indicators:**
- ✅ Green checkmark next to workflow run
- ✅ "Success" status badge
- ✅ All job steps completed (green checkmarks)
- ✅ Artifacts section shows uploaded files

**Job Summary Verification:**
1. Click completed workflow run
2. Scroll to bottom for "Summary" section
3. Verify output shows:
   - Archive name
   - Archive size (~10-11 MB)
   - SHA256 checksum
   - Next steps instructions

**Expected Artifacts:**
- `lldb-linux-x86_64` (contains `lldb-21.1.5-linux-x86_64.tar.zst` and checksum files)
- `lldb-linux-arm64` (contains `lldb-21.1.5-linux-arm64.tar.zst` and checksum files)

---

### Step 7: Download Artifacts

**Method 1: GitHub UI**
1. Click completed workflow run
2. Scroll down to "Artifacts" section
3. Click artifact name to download ZIP file
4. Extract ZIP to get .tar.zst archive and checksums

**Method 2: GitHub CLI (gh)**
```bash
# List artifacts
gh run list --workflow="Build LLDB Archives (Linux)" --limit 1

# Get run ID (replace XXXXXX with actual run ID)
RUN_ID=XXXXXX

# Download artifacts
gh run download $RUN_ID --dir artifacts/

# Files will be in artifacts/lldb-linux-x86_64/ and artifacts/lldb-linux-arm64/
```

**Expected Files Per Architecture:**
- `lldb-21.1.5-linux-x86_64.tar.zst` (~10-11 MB)
- `lldb-21.1.5-linux-x86_64.tar.zst.sha256` (SHA256 checksum)
- `size.txt` (archive size in bytes)

---

### Step 8: Verify Downloaded Archives

**Check File Sizes:**
```bash
# Should be ~10-11 MB each
ls -lh artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst
ls -lh artifacts/lldb-linux-arm64/lldb-21.1.5-linux-arm64.tar.zst
```

**Verify SHA256 Checksums:**
```bash
# x86_64
cd artifacts/lldb-linux-x86_64/
sha256sum -c lldb-21.1.5-linux-x86_64.tar.zst.sha256
# Expected: lldb-21.1.5-linux-x86_64.tar.zst: OK

# arm64
cd ../lldb-linux-arm64/
sha256sum -c lldb-21.1.5-linux-arm64.tar.zst.sha256
# Expected: lldb-21.1.5-linux-arm64.tar.zst: OK
```

**Test Archive Extraction (Optional):**
```bash
# Create test directory
mkdir test_extract
cd test_extract

# Extract archive
tar --use-compress-program=unzstd -xf ../lldb-21.1.5-linux-x86_64.tar.zst

# Verify contents
ls -R
# Expected directories: bin/, lib/, python/

# Verify LLDB binaries
ls bin/
# Expected: lldb, lldb-server, lldb-argdumper

# Verify Python modules
ls python/Lib/site-packages/lldb/
# Expected: __init__.py, _lldb.*.so (symlink), formatters/, plugins/, utils/

# Clean up
cd ..
rm -rf test_extract
```

---

## Expected Workflow Output

### Archive Contents (per architecture)

**Directory Structure:**
```
lldb-21.1.5-linux-x86_64/
├── bin/
│   ├── lldb
│   ├── lldb-server
│   └── lldb-argdumper
├── lib/
│   └── liblldb.so.21
└── python/
    └── Lib/
        ├── site-packages/
        │   └── lldb/
        │       ├── __init__.py
        │       ├── _lldb.cpython-310-x86_64-linux-gnu.so (symlink → ../../../lib/liblldb.so)
        │       ├── formatters/
        │       ├── plugins/
        │       └── utils/
        ├── encodings/
        ├── collections/
        └── ... (minimized Python 3.10 stdlib)
```

**Archive Sizes:**
- Uncompressed: ~50-60 MB
- Compressed (zstd-22): ~10-11 MB
- Compression ratio: ~82-83%

**SHA256 Checksums:**
- Format: `<checksum> <filename>`
- Example: `a1b2c3d4e5f6... lldb-21.1.5-linux-x86_64.tar.zst`

---

## Troubleshooting

### Problem: Workflow Not Found

**Symptom:** 404 error or workflow doesn't appear in Actions list

**Solution:**
1. Verify workflow file exists: `.github/workflows/build-lldb-archives-linux.yml`
2. Check file is committed and pushed to main branch
3. Verify GitHub Actions enabled (Settings → Actions → General)

---

### Problem: "Run workflow" Button Disabled

**Symptom:** Button greyed out or not clickable

**Solution:**
1. Verify you have write access to repository
2. Check if Actions are disabled for your account/organization
3. Try different browser or clear cache
4. Check repository permissions (Settings → Actions)

---

### Problem: Workflow Fails During LLVM Download

**Symptom:** Step 4 fails with network error or timeout

**Solution:**
1. Re-run workflow (click "Re-run failed jobs" button)
2. Check GitHub's status page for outages
3. LLVM mirrors may be temporarily unavailable
4. Workflow has 2-hour timeout per job - sufficient for most cases

---

### Problem: Workflow Fails During Archive Creation

**Symptom:** Step 8 fails with zstandard error

**Solution:**
1. Check if zstandard installed correctly (Step 3 logs)
2. Verify Python modules exist in work/ directory (Step 7 logs)
3. Check disk space on GitHub runner (rare issue)

---

### Problem: Artifacts Not Uploaded

**Symptom:** "Artifacts" section empty after successful run

**Solution:**
1. Check Step 11 logs for upload errors
2. Verify archives created in Step 8 (check logs)
3. Re-run workflow if artifacts expired (30-day retention)

---

### Problem: Archive Size Too Large

**Symptom:** Archive > 15 MB

**Solution:**
1. Check if Python modules minimized correctly
2. Verify only required Python stdlib modules included
3. Check if compression level correct (zstd -22)
4. Acceptable range: 8-15 MB (10-11 MB expected)

---

### Problem: Archive Size Too Small

**Symptom:** Archive < 8 MB

**Solution:**
1. Verify Python modules copied (Step 7 logs)
2. Check if LLDB binaries extracted correctly (Step 6 logs)
3. Extract archive and verify contents
4. May be missing Python modules or LLDB components

---

## Next Steps After Workflow Completion

Once workflow completes successfully and artifacts downloaded:

### 1. Move Archives to downloads-bins Repository

```bash
# Navigate to downloads-bins repository
cd downloads-bins/

# Create destination directories if needed
mkdir -p assets/lldb/linux/x86_64
mkdir -p assets/lldb/linux/arm64

# Copy archives
cp ~/artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst assets/lldb/linux/x86_64/
cp ~/artifacts/lldb-linux-arm64/lldb-21.1.5-linux-arm64.tar.zst assets/lldb/linux/arm64/
```

### 2. Update Manifest Files

```bash
# Extract checksums
SHA256_X64=$(cat ~/artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst.sha256 | cut -d' ' -f1)
SHA256_ARM64=$(cat ~/artifacts/lldb-linux-arm64/lldb-21.1.5-linux-arm64.tar.zst.sha256 | cut -d' ' -f1)

# Extract sizes
SIZE_X64=$(cat ~/artifacts/lldb-linux-x86_64/size.txt)
SIZE_ARM64=$(cat ~/artifacts/lldb-linux-arm64/size.txt)

# Update manifests manually (edit JSON files)
# Replace "TO_BE_GENERATED_DURING_BUILD" with actual SHA256
# Replace "size: 0" with actual size
```

### 3. Commit to downloads-bins Repository

```bash
cd downloads-bins/

# Add archives and manifests
git add assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst
git add assets/lldb/linux/x86_64/manifest.json
git add assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst
git add assets/lldb/linux/arm64/manifest.json

# Commit
git commit -m "Add LLDB 21.1.5 archives for Linux x64 and ARM64 with Python 3.10

- Add lldb-21.1.5-linux-x86_64.tar.zst (~10-11 MB)
- Add lldb-21.1.5-linux-arm64.tar.zst (~10-11 MB)
- Update manifests with SHA256 checksums and sizes
- Archives include Python 3.10 site-packages for full 'bt all' support

Built by GitHub Actions workflow: build-lldb-archives-linux.yml"

# Push to GitHub
git push origin main
```

### 4. Update Main Repository Submodule

```bash
cd ../clang-tool-chain/

# Update submodule
cd downloads-bins/
git pull origin main
cd ..

# Commit submodule update
git add downloads-bins
git commit -m "Update downloads-bins submodule (LLDB Linux archives)"
git push origin main
```

### 5. Test on Linux (if available)

```bash
# Install package
pip install -e .

# Download LLDB (will use new archives)
clang-tool-chain install lldb

# Test basic functionality
clang-tool-chain-lldb --version

# Test Python environment
clang-tool-chain-lldb-check-python
# Expected: "Status: READY" and "Python environment is fully configured"

# Run comprehensive tests
pytest tests/test_lldb.py -v
# Expected: All tests pass (no skips)
```

---

## Reference Information

### Workflow File Location
```
.github/workflows/build-lldb-archives-linux.yml
```

### Workflow Documentation
```
.agent_task/WORKFLOW_USAGE.md
```

### Python Module Preparation
```
downloads-bins/tools/prepare_python_for_linux_lldb.py
```

### Archive Creation Script
```
downloads-bins/tools/create_lldb_archives.py
```

### Manifest Files
```
downloads-bins/assets/lldb/linux/x86_64/manifest.json
downloads-bins/assets/lldb/linux/arm64/manifest.json
```

---

## Timing Estimates

| Stage | Duration | Notes |
|-------|----------|-------|
| Workflow trigger | 1 minute | GitHub UI interaction |
| Job queue time | 0-5 minutes | Depends on runner availability |
| LLVM download | 5-10 minutes | 1.9 GB per arch, parallel |
| LLVM extraction | 3-5 minutes | Tar decompression |
| Archive creation | 5-10 minutes | Zstd compression level 22 |
| Artifact upload | 1-2 minutes | ~10 MB per arch |
| **Total (both archs)** | **30-50 minutes** | Parallel execution |

**Single Architecture:** ~25-35 minutes
**Both Architectures (parallel):** ~30-50 minutes (recommended)

---

## Success Criteria

✅ **Workflow triggered successfully** - Workflow run appears in Actions list
✅ **Both jobs complete** - Green checkmarks for build-x86_64 and build-arm64
✅ **Artifacts uploaded** - Two artifact packages in Artifacts section
✅ **Correct sizes** - Archives ~10-11 MB each
✅ **Valid checksums** - SHA256 verification passes
✅ **Archives extractable** - Can decompress and view contents
✅ **Python modules present** - Lib/site-packages/lldb/ exists with files
✅ **LLDB binaries present** - bin/lldb, lldb-server, lldb-argdumper exist

---

## Failure Recovery

### If Workflow Fails
1. Review job logs for error messages
2. Check which step failed
3. Consult troubleshooting section above
4. Re-run workflow (button in workflow run page)
5. If persistent failures, file GitHub issue with logs

### If Artifacts Corrupt
1. Re-download from GitHub Actions
2. Verify SHA256 checksums
3. Try extracting with different tools (tar, zstd)
4. If still corrupt, re-run workflow

### If Archive Size Incorrect
1. Extract and verify contents manually
2. Check Python module count and sizes
3. Verify LLDB binaries present
4. If missing content, check workflow logs for copy errors
5. May need to re-run workflow

---

## Contact Information

**Repository:** https://github.com/zackees/clang-tool-chain
**Issues:** https://github.com/zackees/clang-tool-chain/issues
**Workflow:** https://github.com/zackees/clang-tool-chain/actions/workflows/build-lldb-archives-linux.yml

---

**Document Status:** Complete
**Created:** 2026-01-06 (Iteration 11)
**For:** Manual workflow triggering by repository maintainer
**Next:** Follow archive integration checklist after successful workflow completion
