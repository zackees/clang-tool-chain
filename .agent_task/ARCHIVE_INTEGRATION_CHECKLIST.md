# Archive Integration Checklist - Linux LLDB with Python 3.10

**Date Created:** 2026-01-06 (Iteration 11)
**Date Updated:** 2026-01-06 (Iteration 15 - Automation Script Added)
**Purpose:** Step-by-step checklist for integrating Linux LLDB archives after GitHub Actions workflow completion
**Prerequisites:** Workflow completed successfully, artifacts downloaded

---

## Overview

This checklist guides the integration of Linux LLDB archives (x86_64 and ARM64) into the clang-tool-chain distribution system. Follow each step sequentially to ensure correct integration.

**Estimated Time:**
- Automated: 5-10 minutes (using integration script)
- Manual: 2-3 hours (following checklist below)

**Complexity:** Low (with automation), Medium (manual)
**Risk Level:** Low (changes can be reverted easily)

---

## Automated Integration (RECOMMENDED)

**New in Iteration 15:** Use the `integrate_lldb_linux_archives.py` script for automatic integration!

### Quick Start

```bash
cd downloads-bins

# Option 1: Auto-download from latest workflow run and integrate
python tools/integrate_lldb_linux_archives.py

# Option 2: Download from specific run ID
python tools/integrate_lldb_linux_archives.py --run-id 12345678

# Option 3: Use pre-downloaded artifacts
python tools/integrate_lldb_linux_archives.py --skip-download --artifacts-dir ./my-artifacts

# Option 4: Dry-run (test without making changes)
python tools/integrate_lldb_linux_archives.py --dry-run

# Option 5: Integrate only one architecture
python tools/integrate_lldb_linux_archives.py --arch x86_64
```

### What the Script Does

1. ✅ Checks GitHub CLI is installed and authenticated
2. ✅ Finds latest workflow run (or uses specified run ID)
3. ✅ Downloads artifacts from GitHub Actions
4. ✅ Verifies SHA256 checksums
5. ✅ Tests archive extraction
6. ✅ Moves archives to distribution directories
7. ✅ Updates manifest files with metadata
8. ✅ Validates manifest structure

### Prerequisites for Automation

- GitHub CLI (`gh`) installed and authenticated
- Python 3.10+ with `zstandard` library
- Run from `downloads-bins` directory

### Script Location

`downloads-bins/tools/integrate_lldb_linux_archives.py`

---

## Manual Integration (Alternative)

---

## Pre-Integration Verification

### ✅ Checklist: Workflow Completion

- [ ] GitHub Actions workflow "Build LLDB Archives (Linux)" completed successfully
- [ ] Workflow run has green checkmark (all jobs passed)
- [ ] Artifacts section shows both x86_64 and ARM64 packages
- [ ] Job summary displays archive sizes and checksums
- [ ] Workflow execution time < 2 hours (within timeout limit)

**How to Verify:**
```bash
gh run list --workflow="Build LLDB Archives (Linux)" --limit 1
# Check status: "completed" and conclusion: "success"
```

---

### ✅ Checklist: Artifact Download

- [ ] Downloaded `lldb-linux-x86_64` artifact ZIP
- [ ] Downloaded `lldb-linux-arm64` artifact ZIP
- [ ] Extracted both ZIPs to local directory
- [ ] Files present for x86_64:
  - [ ] `lldb-21.1.5-linux-x86_64.tar.zst`
  - [ ] `lldb-21.1.5-linux-x86_64.tar.zst.sha256`
  - [ ] `size.txt`
- [ ] Files present for ARM64:
  - [ ] `lldb-21.1.5-linux-arm64.tar.zst`
  - [ ] `lldb-21.1.5-linux-arm64.tar.zst.sha256`
  - [ ] `size.txt`

**Commands:**
```bash
# Download artifacts (replace RUN_ID with actual run ID)
gh run download RUN_ID --dir artifacts/

# Verify contents
ls -lh artifacts/lldb-linux-x86_64/
ls -lh artifacts/lldb-linux-arm64/
```

---

### ✅ Checklist: Archive Validation

- [ ] **x86_64 archive size:** 8-15 MB (expected ~10-11 MB)
- [ ] **ARM64 archive size:** 8-15 MB (expected ~10-11 MB)
- [ ] **x86_64 SHA256 checksum:** Passes verification
- [ ] **ARM64 SHA256 checksum:** Passes verification
- [ ] **x86_64 archive extractable:** No errors during test extraction
- [ ] **ARM64 archive extractable:** No errors during test extraction

**Validation Commands:**
```bash
# Check sizes
ls -lh artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst
ls -lh artifacts/lldb-linux-arm64/lldb-21.1.5-linux-arm64.tar.zst

# Verify checksums
cd artifacts/lldb-linux-x86_64/
sha256sum -c lldb-21.1.5-linux-x86_64.tar.zst.sha256
cd ../lldb-linux-arm64/
sha256sum -c lldb-21.1.5-linux-arm64.tar.zst.sha256

# Test extraction (x86_64)
mkdir -p /tmp/test_lldb_x64
cd /tmp/test_lldb_x64
tar --use-compress-program=unzstd -xf ~/artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst
ls -R
rm -rf /tmp/test_lldb_x64

# Test extraction (ARM64)
mkdir -p /tmp/test_lldb_arm64
cd /tmp/test_lldb_arm64
tar --use-compress-program=unzstd -xf ~/artifacts/lldb-linux-arm64/lldb-21.1.5-linux-arm64.tar.zst
ls -R
rm -rf /tmp/test_lldb_arm64
```

---

### ✅ Checklist: Archive Contents Verification

Extract one archive and verify critical components are present:

**x86_64 Archive Contents:**
- [ ] `bin/lldb` - Main LLDB binary
- [ ] `bin/lldb-server` - LLDB server binary
- [ ] `bin/lldb-argdumper` - Argument dumper utility
- [ ] `lib/liblldb.so.21` - LLDB shared library
- [ ] `python/Lib/site-packages/lldb/__init__.py` - LLDB Python module
- [ ] `python/Lib/site-packages/lldb/_lldb.cpython-310-x86_64-linux-gnu.so` - Python binding (symlink)
- [ ] `python/Lib/site-packages/lldb/formatters/` - LLDB formatters
- [ ] `python/Lib/encodings/` - Python encodings module
- [ ] `python/Lib/collections/` - Python collections module

**ARM64 Archive Contents:**
- [ ] Same as x86_64, but with `_lldb.cpython-310-aarch64-linux-gnu.so`

**Verification Script:**
```bash
mkdir -p /tmp/verify_lldb_contents
cd /tmp/verify_lldb_contents
tar --use-compress-program=unzstd -xf ~/artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst

echo "=== Verifying x86_64 Archive Contents ==="

# Check binaries
ls -lh bin/lldb bin/lldb-server bin/lldb-argdumper

# Check libraries
ls -lh lib/liblldb.so.21

# Check Python modules
ls -lh python/Lib/site-packages/lldb/__init__.py
ls -lh python/Lib/site-packages/lldb/_lldb.cpython-310-x86_64-linux-gnu.so
ls -d python/Lib/site-packages/lldb/formatters/
ls -d python/Lib/encodings/
ls -d python/Lib/collections/

# Verify symlink
file python/Lib/site-packages/lldb/_lldb.cpython-310-x86_64-linux-gnu.so
# Expected: "symbolic link to ../../../lib/liblldb.so"

# Count Python modules
find python/Lib/site-packages/lldb/ -type f -name "*.py" | wc -l
# Expected: ~15-20 files

# Clean up
cd ..
rm -rf /tmp/verify_lldb_contents
```

---

## Integration Steps

### Step 1: Backup Current State

- [ ] Create git branch for integration work
- [ ] Document current manifest state (checksums and sizes)
- [ ] Note current downloads-bins submodule commit

**Commands:**
```bash
cd ~/dev/clang-tool-chain/

# Create feature branch
git checkout -b lldb-linux-archives-integration

# Document current state
git log downloads-bins -1 --oneline > /tmp/submodule_before.txt
cat downloads-bins/assets/lldb/linux/x86_64/manifest.json > /tmp/manifest_x64_before.json
cat downloads-bins/assets/lldb/linux/arm64/manifest.json > /tmp/manifest_arm64_before.json
```

---

### Step 2: Copy Archives to downloads-bins Repository

- [ ] Navigate to downloads-bins directory
- [ ] Verify target directories exist
- [ ] Copy x86_64 archive to `assets/lldb/linux/x86_64/`
- [ ] Copy ARM64 archive to `assets/lldb/linux/arm64/`
- [ ] Verify copied files match source (checksums)

**Commands:**
```bash
cd ~/dev/clang-tool-chain/downloads-bins/

# Verify directories exist
ls -ld assets/lldb/linux/x86_64/
ls -ld assets/lldb/linux/arm64/

# Copy archives
cp ~/artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst \
   assets/lldb/linux/x86_64/

cp ~/artifacts/lldb-linux-arm64/lldb-21.1.5-linux-arm64.tar.zst \
   assets/lldb/linux/arm64/

# Verify copies
ls -lh assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst
ls -lh assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst

# Verify checksums match
sha256sum assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst
sha256sum assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst
# Compare with downloaded .sha256 files
```

---

### Step 3: Extract SHA256 Checksums and Sizes

- [ ] Read x86_64 SHA256 from downloaded `.sha256` file
- [ ] Read ARM64 SHA256 from downloaded `.sha256` file
- [ ] Read x86_64 size from downloaded `size.txt` file
- [ ] Read ARM64 size from downloaded `size.txt` file
- [ ] Document values for manifest updates

**Commands:**
```bash
# Extract checksums
SHA256_X64=$(cat ~/artifacts/lldb-linux-x86_64/lldb-21.1.5-linux-x86_64.tar.zst.sha256 | cut -d' ' -f1)
SHA256_ARM64=$(cat ~/artifacts/lldb-linux-arm64/lldb-21.1.5-linux-arm64.tar.zst.sha256 | cut -d' ' -f1)

# Extract sizes
SIZE_X64=$(cat ~/artifacts/lldb-linux-x86_64/size.txt)
SIZE_ARM64=$(cat ~/artifacts/lldb-linux-arm64/size.txt)

# Display values for manual update
echo "x86_64 SHA256: $SHA256_X64"
echo "x86_64 Size: $SIZE_X64"
echo "ARM64 SHA256: $SHA256_ARM64"
echo "ARM64 Size: $SIZE_ARM64"

# Save to file for reference
cat > /tmp/manifest_values.txt <<EOF
x86_64:
  sha256: $SHA256_X64
  size: $SIZE_X64

arm64:
  sha256: $SHA256_ARM64
  size: $SIZE_ARM64
EOF
```

---

### Step 4: Update x86_64 Manifest

- [ ] Open `downloads-bins/assets/lldb/linux/x86_64/manifest.json`
- [ ] Replace `"sha256": "TO_BE_GENERATED_DURING_BUILD"` with actual SHA256
- [ ] Update `"size": 0` with actual size (bytes)
- [ ] Verify JSON syntax is valid
- [ ] Verify all fields present: href, sha256, size, notes, python_included, python_version

**Manual Edit Required:**
Edit `downloads-bins/assets/lldb/linux/x86_64/manifest.json`:
```json
{
  "latest": "21.1.5",
  "21.1.5": {
    "href": "https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst",
    "sha256": "PASTE_ACTUAL_SHA256_HERE",
    "size": PASTE_ACTUAL_SIZE_HERE,
    "notes": "LLDB 21.1.5 debugger for Linux x64 (includes Python 3.10 site-packages for full 'bt all' support)",
    "python_included": true,
    "python_version": "3.10"
  }
}
```

**Validation:**
```bash
# Validate JSON syntax
python3 -m json.tool downloads-bins/assets/lldb/linux/x86_64/manifest.json

# Check SHA256 matches
grep "$SHA256_X64" downloads-bins/assets/lldb/linux/x86_64/manifest.json
```

---

### Step 5: Update ARM64 Manifest

- [ ] Open `downloads-bins/assets/lldb/linux/arm64/manifest.json`
- [ ] Replace `"sha256": "TO_BE_GENERATED_DURING_BUILD"` with actual SHA256
- [ ] Update `"size": 0` with actual size (bytes)
- [ ] Verify JSON syntax is valid
- [ ] Verify all fields present: href, sha256, size, notes, python_included, python_version

**Manual Edit Required:**
Edit `downloads-bins/assets/lldb/linux/arm64/manifest.json`:
```json
{
  "latest": "21.1.5",
  "21.1.5": {
    "href": "https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst",
    "sha256": "PASTE_ACTUAL_SHA256_HERE",
    "size": PASTE_ACTUAL_SIZE_HERE,
    "notes": "LLDB 21.1.5 debugger for Linux ARM64 (includes Python 3.10 site-packages for full 'bt all' support)",
    "python_included": true,
    "python_version": "3.10"
  }
}
```

**Validation:**
```bash
# Validate JSON syntax
python3 -m json.tool downloads-bins/assets/lldb/linux/arm64/manifest.json

# Check SHA256 matches
grep "$SHA256_ARM64" downloads-bins/assets/lldb/linux/arm64/manifest.json
```

---

### Step 6: Verify Manifest Updates

- [ ] Both manifest JSON files valid syntax
- [ ] SHA256 checksums match downloaded archives
- [ ] Sizes match downloaded archives (bytes)
- [ ] All required fields present in manifests
- [ ] No placeholder values remain ("TO_BE_GENERATED_DURING_BUILD" removed)

**Comprehensive Validation:**
```bash
cd ~/dev/clang-tool-chain/downloads-bins/

# Validate JSON syntax
echo "=== Validating Manifest Syntax ==="
python3 -m json.tool assets/lldb/linux/x86_64/manifest.json > /dev/null && echo "x86_64 manifest: OK"
python3 -m json.tool assets/lldb/linux/arm64/manifest.json > /dev/null && echo "ARM64 manifest: OK"

# Verify SHA256 checksums
echo "=== Verifying SHA256 Checksums ==="
MANIFEST_SHA256_X64=$(python3 -c "import json; print(json.load(open('assets/lldb/linux/x86_64/manifest.json'))['21.1.5']['sha256'])")
MANIFEST_SHA256_ARM64=$(python3 -c "import json; print(json.load(open('assets/lldb/linux/arm64/manifest.json'))['21.1.5']['sha256'])")

echo "Manifest x86_64: $MANIFEST_SHA256_X64"
echo "Archive x86_64:  $SHA256_X64"
[ "$MANIFEST_SHA256_X64" = "$SHA256_X64" ] && echo "x86_64 checksum: MATCH" || echo "x86_64 checksum: MISMATCH"

echo "Manifest ARM64: $MANIFEST_SHA256_ARM64"
echo "Archive ARM64:  $SHA256_ARM64"
[ "$MANIFEST_SHA256_ARM64" = "$SHA256_ARM64" ] && echo "ARM64 checksum: MATCH" || echo "ARM64 checksum: MISMATCH"

# Verify sizes
echo "=== Verifying Sizes ==="
MANIFEST_SIZE_X64=$(python3 -c "import json; print(json.load(open('assets/lldb/linux/x86_64/manifest.json'))['21.1.5']['size'])")
MANIFEST_SIZE_ARM64=$(python3 -c "import json; print(json.load(open('assets/lldb/linux/arm64/manifest.json'))['21.1.5']['size'])")

echo "Manifest x86_64: $MANIFEST_SIZE_X64 bytes"
echo "Archive x86_64:  $SIZE_X64 bytes"
[ "$MANIFEST_SIZE_X64" = "$SIZE_X64" ] && echo "x86_64 size: MATCH" || echo "x86_64 size: MISMATCH"

echo "Manifest ARM64: $MANIFEST_SIZE_ARM64 bytes"
echo "Archive ARM64:  $SIZE_ARM64 bytes"
[ "$MANIFEST_SIZE_ARM64" = "$SIZE_ARM64" ] && echo "ARM64 size: MATCH" || echo "ARM64 size: MISMATCH"

# Verify no placeholders remain
echo "=== Checking for Placeholders ==="
grep -r "TO_BE_GENERATED_DURING_BUILD" assets/lldb/linux/ && echo "WARNING: Placeholders found!" || echo "No placeholders: OK"
```

---

### Step 7: Commit to downloads-bins Repository

- [ ] Stage archive files for commit
- [ ] Stage manifest files for commit
- [ ] Review changes with `git diff --cached`
- [ ] Create descriptive commit message
- [ ] Commit changes locally
- [ ] Verify commit includes all expected files

**Commands:**
```bash
cd ~/dev/clang-tool-chain/downloads-bins/

# Stage files
git add assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst
git add assets/lldb/linux/x86_64/manifest.json
git add assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst
git add assets/lldb/linux/arm64/manifest.json

# Review changes
git diff --cached

# Verify file sizes in staging
git diff --cached --stat

# Commit
git commit -m "Add LLDB 21.1.5 archives for Linux x64 and ARM64 with Python 3.10

- Add lldb-21.1.5-linux-x86_64.tar.zst (~10-11 MB compressed)
- Add lldb-21.1.5-linux-arm64.tar.zst (~10-11 MB compressed)
- Update x86_64 manifest with SHA256 checksum and size
- Update ARM64 manifest with SHA256 checksum and size
- Archives include Python 3.10 site-packages for full 'bt all' support
- Built by GitHub Actions workflow: build-lldb-archives-linux.yml

Python modules: ~11 MB uncompressed stdlib + LLDB Python bindings
Archive sizes: ~10-11 MB compressed (zstd level 22)
Binary deduplication: liblldb.so + _lldb.so symlink

Enables:
- Full LLDB 'bt all' backtraces without system Python
- Python scripting in LLDB
- Advanced variable inspection
- LLDB Python API access

Tested on: GitHub Actions Ubuntu runners (x86_64 and ARM64)
LLVM Version: 21.1.5
Python Version: 3.10"

# Verify commit
git log -1 --stat
git show --name-status
```

---

### Step 8: Push to downloads-bins Repository

- [ ] Verify remote URL is correct
- [ ] Push commit to main branch
- [ ] Verify push succeeded (no errors)
- [ ] Check GitHub repository web UI for commit
- [ ] Verify archive files uploaded (LFS or regular)

**Commands:**
```bash
cd ~/dev/clang-tool-chain/downloads-bins/

# Verify remote
git remote -v

# Push to main branch
git push origin main

# Verify push succeeded
git log origin/main -1 --oneline

# Verify on GitHub (manual check via browser)
# https://github.com/zackees/clang-tool-chain-bins/tree/main/assets/lldb/linux
```

**Important:** If using Git LFS for large files, ensure LFS push completes successfully:
```bash
git lfs push origin main
```

---

### Step 9: Update Main Repository Submodule

- [ ] Return to main clang-tool-chain repository
- [ ] Navigate to downloads-bins submodule directory
- [ ] Pull latest changes from origin/main
- [ ] Return to main repository root
- [ ] Stage submodule update
- [ ] Verify submodule commit hash updated
- [ ] Commit submodule update

**Commands:**
```bash
cd ~/dev/clang-tool-chain/

# Update submodule
cd downloads-bins/
git pull origin main
cd ..

# Verify submodule state
git status
# Should show: "modified:   downloads-bins (new commits)"

# Show submodule changes
git diff downloads-bins

# Stage submodule update
git add downloads-bins

# Commit
git commit -m "Update downloads-bins submodule (LLDB Linux archives)

LLDB 21.1.5 archives for Linux x64 and ARM64 now available with Python 3.10

- x86_64: ~10-11 MB compressed
- ARM64: ~10-11 MB compressed
- Includes Python 3.10 site-packages for full 'bt all' support
- Built by GitHub Actions workflow: build-lldb-archives-linux.yml

Submodule commit: $(git rev-parse downloads-bins/HEAD:downloads-bins)"

# Verify commit
git log -1 --stat
```

---

### Step 10: Push Main Repository Changes

- [ ] Push feature branch to GitHub
- [ ] Verify push succeeded
- [ ] Check GitHub Actions CI/CD starts automatically
- [ ] Monitor initial test runs

**Commands:**
```bash
cd ~/dev/clang-tool-chain/

# Push feature branch
git push origin lldb-linux-archives-integration

# Verify push
git log origin/lldb-linux-archives-integration -1 --oneline

# Check GitHub Actions (manual)
# https://github.com/zackees/clang-tool-chain/actions
```

---

## Post-Integration Testing

### Step 11: Local Testing (if on Linux)

**Requirements:**
- Linux x86_64 or ARM64 machine
- Python 3.10 or later installed
- Git and build tools available

**Testing Steps:**

- [ ] Clone fresh repository copy (or use existing)
- [ ] Checkout feature branch
- [ ] Install package in editable mode
- [ ] Test LLDB installation
- [ ] Test LLDB version check
- [ ] Test Python environment diagnostic
- [ ] Run full test suite
- [ ] Verify all LLDB tests pass (no skips)

**Commands:**
```bash
# Install package
cd ~/dev/clang-tool-chain/
pip install -e .

# Pre-download LLDB (will use new archives)
clang-tool-chain install lldb

# Verify installation directory
ls -la ~/.clang-tool-chain/lldb-linux-x86_64/
# Should show: bin/, lib/, python/ directories

# Test LLDB version
clang-tool-chain-lldb --version
# Expected: "lldb version 21.1.5"

# Test Python environment
clang-tool-chain-lldb-check-python
# Expected: "Status: READY" and "Python environment is fully configured"

# Run comprehensive tests
pytest tests/test_lldb.py -v
# Expected: All tests PASS (no skips, no failures)

# Specific Python test
pytest tests/test_lldb.py::TestLLDB::test_lldb_full_backtraces_with_python -v
# Expected: PASS (not skipped)
```

---

### Step 12: CI/CD Testing

**Requirements:**
- GitHub Actions enabled
- Test workflows configured: test-lldb-linux-x64.yml, test-lldb-linux-arm64.yml
- Feature branch pushed to GitHub

**Monitoring:**

- [ ] Check GitHub Actions for triggered workflows
- [ ] Monitor test-lldb-linux-x64 workflow
- [ ] Monitor test-lldb-linux-arm64 workflow
- [ ] Verify both workflows complete successfully
- [ ] Check test logs for any failures or warnings
- [ ] Verify download times acceptable (<5 minutes)
- [ ] Verify extraction times acceptable (<30 seconds)

**Commands:**
```bash
# List recent workflow runs
gh run list --branch lldb-linux-archives-integration --limit 10

# Watch specific workflow
gh run watch

# Check workflow status
gh run view RUN_ID

# Download workflow logs (if needed)
gh run view RUN_ID --log
```

---

### Step 13: Integration Testing

**Test Scenarios:**

- [ ] **Fresh installation:** Verify LLDB downloads and installs correctly
- [ ] **Version check:** `clang-tool-chain-lldb --version` works
- [ ] **Python check:** `clang-tool-chain-lldb-check-python` shows "READY"
- [ ] **Full backtraces:** "bt all" command produces complete stack traces
- [ ] **Python API:** Can import lldb module in Python
- [ ] **No system Python:** Works without system Python 3.10 installed
- [ ] **Crash analysis:** `clang-tool-chain-lldb-print-crash-stack` works
- [ ] **Multiple architectures:** Both x64 and ARM64 work correctly

---

### Step 14: Performance Validation

**Metrics to Check:**

- [ ] **Download time:** < 2 minutes on typical connection
- [ ] **Download size:** ~10-11 MB per architecture
- [ ] **Extraction time:** < 30 seconds
- [ ] **First run time:** < 5 seconds
- [ ] **LLDB startup time:** < 1 second
- [ ] **Memory usage:** < 100 MB for basic debugging
- [ ] **Python module load time:** < 500ms

**Benchmark Commands:**
```bash
# Purge existing installation
clang-tool-chain purge --yes

# Time download and install
time clang-tool-chain install lldb

# Time LLDB startup
time clang-tool-chain-lldb --version

# Time Python environment check
time clang-tool-chain-lldb-check-python
```

---

## Rollback Procedure

If integration fails or issues discovered:

### Rollback downloads-bins Repository

```bash
cd ~/dev/clang-tool-chain/downloads-bins/

# Revert commit
git revert HEAD

# Or hard reset (if not pushed)
git reset --hard HEAD~1

# Remove archives
rm assets/lldb/linux/x86_64/lldb-21.1.5-linux-x86_64.tar.zst
rm assets/lldb/linux/arm64/lldb-21.1.5-linux-arm64.tar.zst

# Restore manifests from backup
cp /tmp/manifest_x64_before.json assets/lldb/linux/x86_64/manifest.json
cp /tmp/manifest_arm64_before.json assets/lldb/linux/arm64/manifest.json

# Commit rollback
git add assets/lldb/linux/*/manifest.json
git commit -m "Rollback LLDB Linux archives (issues found)"
git push origin main
```

### Rollback Main Repository

```bash
cd ~/dev/clang-tool-chain/

# Update submodule to previous commit
cd downloads-bins/
git checkout $(cat /tmp/submodule_before.txt | cut -d' ' -f1)
cd ..

# Commit rollback
git add downloads-bins
git commit -m "Rollback downloads-bins submodule (LLDB Linux archives)"
git push origin lldb-linux-archives-integration --force
```

---

## Success Criteria

### ✅ Integration Success Checklist

- [ ] Archives copied to downloads-bins repository
- [ ] Manifests updated with correct SHA256 and sizes
- [ ] downloads-bins committed and pushed successfully
- [ ] Main repository submodule updated
- [ ] CI/CD tests pass on both x86_64 and ARM64
- [ ] Local testing passes (if available)
- [ ] Python environment check shows "READY"
- [ ] Full "bt all" backtraces work
- [ ] No system Python required
- [ ] Documentation matches actual behavior

### ✅ Quality Metrics

- [ ] Archive sizes within expected range (8-15 MB)
- [ ] Download times acceptable (< 2 minutes)
- [ ] Extraction times acceptable (< 30 seconds)
- [ ] No errors or warnings in logs
- [ ] Test coverage maintained (no skipped tests)
- [ ] Performance acceptable (startup < 1 second)

---

## Next Steps After Integration

### Documentation Updates

- [ ] Update `docs/LLDB.md` with final archive sizes
- [ ] Update `CLAUDE.md` table with "✅ Complete" status
- [ ] Update README.md badges (if needed)
- [ ] Create release notes for Linux LLDB support

### Communication

- [ ] Notify team of Linux LLDB availability
- [ ] Update project board/issues
- [ ] Consider blog post or announcement
- [ ] Update PyPI release notes

### Future Improvements

- [ ] Consider bundling libpython3.10.so (remove system dependency)
- [ ] Optimize Python module sizes further
- [ ] Add macOS LLDB support (same process)
- [ ] Add automated archive rebuilds (workflow_dispatch + cron)

---

## Reference Files

### Key Files for Integration

| File | Purpose |
|------|---------|
| `.agent_task/WORKFLOW_TRIGGER_GUIDE.md` | Workflow triggering instructions |
| `.agent_task/ARCHIVE_INTEGRATION_CHECKLIST.md` | This file |
| `downloads-bins/assets/lldb/linux/x86_64/manifest.json` | x86_64 manifest |
| `downloads-bins/assets/lldb/linux/arm64/manifest.json` | ARM64 manifest |
| `tests/test_lldb.py` | LLDB test suite |
| `docs/LLDB.md` | LLDB documentation |

### Archive Details

| Architecture | Archive Name | Expected Size | Python Version |
|--------------|-------------|---------------|----------------|
| x86_64 | lldb-21.1.5-linux-x86_64.tar.zst | ~10-11 MB | 3.10 |
| ARM64 | lldb-21.1.5-linux-arm64.tar.zst | ~10-11 MB | 3.10 |

---

## Troubleshooting

### Problem: Manifest Validation Fails

**Symptom:** JSON syntax error or validation fails

**Solution:**
1. Check JSON syntax with `python3 -m json.tool manifest.json`
2. Verify all required fields present
3. Check for typos in SHA256 (64 hex characters)
4. Verify size is integer (not string)
5. Use JSON validator online if needed

---

### Problem: SHA256 Mismatch

**Symptom:** Manifest checksum doesn't match archive

**Solution:**
1. Recalculate archive checksum: `sha256sum archive.tar.zst`
2. Verify checksum from workflow artifact
3. Check if archive was corrupted during download
4. Re-download archive from GitHub Actions
5. Update manifest with correct checksum

---

### Problem: Archive Size Unexpected

**Symptom:** Archive significantly larger or smaller than expected

**Solution:**
1. Extract archive and verify contents
2. Check Python module directory size
3. Verify LLDB binaries present
4. Check compression level (should be zstd -22)
5. If too small: Python modules may be missing
6. If too large: Extra files may be included
7. Review workflow logs for anomalies

---

### Problem: Submodule Update Fails

**Symptom:** Git error when updating submodule

**Solution:**
1. Verify downloads-bins commit pushed successfully
2. Check submodule URL correct in `.gitmodules`
3. Try `git submodule update --remote downloads-bins`
4. If persistent, re-clone repository
5. Check SSH key or HTTPS credentials

---

### Problem: CI/CD Tests Fail

**Symptom:** GitHub Actions workflows fail after integration

**Solution:**
1. Check workflow logs for specific error
2. Verify archive download URL accessible
3. Check manifest JSON valid
4. Verify SHA256 checksum correct
5. Test download manually
6. Check if archive extractable
7. Review test_lldb.py for issues

---

### Problem: Python Environment Not Ready

**Symptom:** `clang-tool-chain-lldb-check-python` shows error

**Solution:**
1. Verify Python modules extracted correctly
2. Check PYTHONPATH set in wrapper
3. Verify `python/Lib/site-packages/lldb/` exists
4. Check symlinks preserved during extraction
5. Verify liblldb.so present in lib/ directory
6. Check permissions on Python files

---

## Contact and Support

**Repository:** https://github.com/zackees/clang-tool-chain
**Issues:** https://github.com/zackees/clang-tool-chain/issues
**Actions:** https://github.com/zackees/clang-tool-chain/actions

---

**Document Status:** Complete
**Created:** 2026-01-06 (Iteration 11)
**For:** Archive integration after successful workflow completion
**Prerequisites:** Workflow completed, artifacts downloaded and validated
