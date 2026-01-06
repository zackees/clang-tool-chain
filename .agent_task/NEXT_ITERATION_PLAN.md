# Next Iteration Plan: Post-Workflow Trigger

**Date Created:** 2026-01-06 (Iteration 17)
**Current Status:** Waiting for manual GitHub Actions workflow trigger
**Critical Blocker:** Human intervention required to trigger workflow

---

## Current State Summary

### What's Complete ✅
1. **Research & Planning** (Iterations 1-3)
   - Python 3.10 distribution analyzed
   - LLDB Python integration understood
   - Comprehensive packaging strategy designed
   - All technical decisions finalized

2. **Python Module Preparation** (Iteration 4)
   - Python modules extracted for both x86_64 and ARM64
   - Minimized from 43 MB → 11 MB per arch
   - LLDB Python bindings integrated from Debian Jammy
   - Ready at: `downloads-bins/work/python_linux_{x64,arm64}/`

3. **CI/CD Infrastructure** (Iterations 7-9)
   - GitHub Actions workflow created and deployed
   - Workflow location: `.github/workflows/build-lldb-archives-linux.yml`
   - Committed and pushed to main branch (commit: 5675fac)
   - Comprehensive documentation at `.agent_task/WORKFLOW_TRIGGER_GUIDE.md`

4. **Python Wrapper Integration** (Iteration 10)
   - LLDB wrapper already supports Linux (discovered pre-implemented)
   - PYTHONPATH, PYTHONHOME, LD_LIBRARY_PATH configured
   - No code changes needed - ready for archives

5. **Test Infrastructure** (Iterations 12, 16)
   - Enhanced diagnostics and error messages
   - Performance benchmarking added
   - Comprehensive test documentation (200+ lines)
   - Ready for Linux LLDB testing

6. **Archive Integration Automation** (Iteration 15)
   - Script created: `downloads-bins/tools/integrate_lldb_linux_archives.py`
   - Auto-downloads artifacts from GitHub Actions
   - Verifies checksums and tests extraction
   - Updates manifests automatically
   - Reduces integration time from 2-3 hours to 5-10 minutes

7. **Documentation** (Iterations 11, 14)
   - Workflow trigger guide (650+ lines)
   - Archive integration checklist (850+ lines)
   - Linux troubleshooting guide (350+ lines)
   - Test documentation (200+ lines)

### What's Blocked ⏳
1. **Archive Creation** - Requires manual workflow trigger
   - Workflow URL: https://github.com/zackees/clang-tool-chain/actions/workflows/build-lldb-archives-linux.yml
   - Expected runtime: 30-50 minutes (parallel x86_64 and ARM64)
   - Expected output: Two archives (~10-11 MB each)

2. **Archive Integration** - Depends on #1
   - Automation ready, just needs archives
   - 5-10 minute process once archives available

3. **Final Testing** - Depends on #2
   - Test workflows ready: `test-lldb-linux-x86.yml` and `test-lldb-linux-arm.yml`
   - Will verify full "bt all" backtraces

---

## Critical Next Steps for Human Maintainer

### Step 1: Trigger GitHub Actions Workflow ⚡ CRITICAL

**Action Required:** Manually trigger the workflow

**Instructions:**
1. Go to: https://github.com/zackees/clang-tool-chain/actions/workflows/build-lldb-archives-linux.yml
2. Click "Run workflow" button (top-right, green)
3. Configure inputs:
   - Branch: `main`
   - LLVM version: `21.1.5`
   - Architectures: `x86_64,arm64` (build both)
4. Click "Run workflow" to start

**Expected Duration:** 30-50 minutes

**Expected Output:**
- Two artifacts:
  - `lldb-linux-x86_64` (~10-11 MB compressed)
  - `lldb-linux-arm64` (~10-11 MB compressed)
- Each contains: `.tar.zst` archive + `.sha256` checksum

**Detailed Instructions:** See `.agent_task/WORKFLOW_TRIGGER_GUIDE.md`

---

### Step 2: Monitor Workflow Execution (Optional)

**While workflow runs:**
1. Watch progress in GitHub Actions UI
2. View job logs for any errors
3. Verify both architectures build successfully
4. Check artifact uploads complete

**Common Issues:**
- Download timeout (1.9 GB LLVM archives): Retry workflow
- Python module not found: Verify submodule updated
- Compression failure: Check disk space on runner

---

### Step 3: Integrate Archives (After Workflow Completes)

**Option A: Automatic Integration (Recommended)**
```bash
cd downloads-bins
python tools/integrate_lldb_linux_archives.py
```

This script will:
1. Auto-detect latest workflow run
2. Download both artifacts
3. Verify SHA256 checksums
4. Test archive extraction
5. Move archives to `assets/lldb/linux/{x86_64,arm64}/`
6. Update manifest files
7. Print completion summary

**Duration:** 5-10 minutes

**Option B: Manual Integration**
Follow checklist at `.agent_task/ARCHIVE_INTEGRATION_CHECKLIST.md` (850+ lines)

---

### Step 4: Test Integration Locally

**Run LLDB tests:**
```bash
cd clang-tool-chain  # Main repository
pytest tests/test_lldb.py -v -k "not windows"
```

**Expected results:**
- ✅ `test_lldb_installs` - LLDB downloads and installs
- ✅ `test_lldb_version` - Version query works
- ✅ `test_lldb_full_backtraces_with_python` - Full "bt all" works
- ✅ `test_lldb_check_python_diagnostic` - Python environment detected

**If tests fail:** See troubleshooting guide in `docs/LLDB.md` (lines 630-927)

---

### Step 5: Commit and Push Changes

**After successful local testing:**

```bash
cd downloads-bins
git add assets/lldb/linux/x86_64/
git add assets/lldb/linux/arm64/
git commit -m "feat: Add Linux LLDB archives with Python 3.10 support

- x86_64: lldb-21.1.5-linux-x86_64.tar.zst (~10-11 MB)
- ARM64: lldb-21.1.5-linux-arm64.tar.zst (~10-11 MB)
- Full Python 3.10 bundled for bt all backtraces
- No system Python required

Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push origin main

# Update main repository submodule
cd ../clang-tool-chain
git add downloads-bins
git commit -m "feat: Update downloads-bins with Linux LLDB archives

Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push origin main
```

---

### Step 6: Monitor CI/CD Tests

**After pushing:**
1. Watch test workflows:
   - https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-x86.yml
   - https://github.com/zackees/clang-tool-chain/actions/workflows/test-lldb-linux-arm.yml
2. Verify tests pass on both architectures
3. Check test logs for any warnings

**Expected CI/CD behavior:**
- Downloads LLDB archives (~10-11 MB each)
- Extracts and verifies Python environment
- Compiles test program with debug symbols
- Runs LLDB and verifies "bt all" backtraces
- All tests should pass ✅

---

### Step 7: Update Documentation

**Final documentation updates:**

1. **CLAUDE.md** - Update LLDB table:
   ```
   | Linux    | x86_64      | 21.1.5       | ✅ Full (Python 3.10 bundled) | ✅ Complete |
   | Linux    | arm64       | 21.1.5       | ✅ Full (Python 3.10 bundled) | ✅ Complete |
   ```

2. **docs/LLDB.md** - Update status:
   - Change "⏳ Wrapper Ready, Archives Pending" → "✅ Complete"
   - Update download sizes
   - Confirm Python 3.10 bundling

3. **README.md** - Update test matrix badges (should auto-update with CI/CD)

---

## Alternative Path: Agent Loop Continuation

**If workflow has already been triggered before next iteration:**

The agent loop can detect this and automatically proceed with:
1. Archive integration using automation script
2. Local testing
3. Commit and push
4. Monitor CI/CD
5. Final documentation updates
6. Create DONE.md to halt loop

**Detection command:**
```bash
gh run list --workflow="build-lldb-archives-linux.yml" --limit 1
```

If run exists and succeeded, agent can proceed without human intervention.

---

## Success Criteria Checklist

Before declaring completion, verify:

### Functional ✅
- [ ] Full "bt all" backtraces work on Linux x86_64
- [ ] Full "bt all" backtraces work on Linux ARM64
- [ ] No system Python required
- [ ] Function names displayed correctly
- [ ] Source file paths shown
- [ ] Line numbers accurate
- [ ] Variable inspection works

### Technical ✅
- [ ] Archives uploaded to downloads-bins
- [ ] Manifests updated correctly
- [ ] SHA256 checksums valid
- [ ] Archive size ≤ 20 MB per platform
- [ ] Python modules extracted correctly
- [ ] Symlinks preserved in archives

### Testing ✅
- [ ] Local tests pass on Linux x64
- [ ] Local tests pass on Linux ARM64
- [ ] CI/CD tests pass on Linux x64
- [ ] CI/CD tests pass on Linux ARM64
- [ ] No regressions in existing tests

### Documentation ✅
- [ ] CLAUDE.md updated
- [ ] docs/LLDB.md updated
- [ ] README.md badges updated
- [ ] Troubleshooting guides complete
- [ ] Integration docs complete

---

## Estimated Timeline

| Step | Duration | Can Agent Do? |
|------|----------|---------------|
| 1. Trigger workflow | 2 minutes | ❌ Human only |
| 2. Workflow execution | 30-50 minutes | ⏳ Automatic (GitHub) |
| 3. Integrate archives | 5-10 minutes | ✅ Agent or human |
| 4. Test locally | 3-5 minutes | ✅ Agent or human |
| 5. Commit and push | 2-3 minutes | ✅ Agent or human |
| 6. Monitor CI/CD | 10-15 minutes | ⏳ Automatic (GitHub) |
| 7. Update docs | 5-10 minutes | ✅ Agent or human |
| **TOTAL** | **60-95 minutes** | **55-90 min automatic** |

**Critical path:** Step 1 (human trigger) blocks everything

---

## Risk Mitigation

### Risk 1: Workflow Fails
**Symptoms:** Build errors, download timeouts, Python module not found

**Mitigation:**
1. Check workflow logs for specific error
2. Verify Python modules exist in work directory
3. Retry workflow (transient failures common)
4. Check submodule is up-to-date
5. See troubleshooting in `.agent_task/WORKFLOW_TRIGGER_GUIDE.md`

### Risk 2: Archives Corrupted
**Symptoms:** SHA256 mismatch, extraction fails

**Mitigation:**
1. Integration script verifies checksums automatically
2. Tests extraction before committing
3. Re-run workflow if corrupted
4. Manual verification: `zstd -t archive.tar.zst`

### Risk 3: Tests Fail After Integration
**Symptoms:** LLDB crashes, Python not found, incomplete backtraces

**Mitigation:**
1. Check diagnostic output: `clang-tool-chain-lldb --check-python`
2. Verify Python directory exists: `~/.clang-tool-chain/lldb-linux-x86_64/python/Lib/`
3. Check symlinks preserved: `ls -la ~/.clang-tool-chain/lldb-linux-x86_64/python/Lib/site-packages/lldb/`
4. See Linux troubleshooting guide: `docs/LLDB.md` lines 630-927
5. Rollback if needed: restore previous manifest

### Risk 4: CI/CD Tests Fail
**Symptoms:** GitHub Actions tests fail after push

**Mitigation:**
1. Check test logs for specific failures
2. Verify archive checksums in manifest
3. Test download manually: `wget <manifest-url>`
4. Check test workflow configuration
5. Rollback and investigate locally

---

## Files Ready for Next Iteration

All infrastructure and documentation complete:

### Scripts (Ready to Execute)
- `downloads-bins/tools/integrate_lldb_linux_archives.py` (650+ lines)
- `downloads-bins/tools/prepare_python_for_linux_lldb.py` (490+ lines)
- `downloads-bins/tools/extract_clang_archive.py` (147 lines)

### Workflows (Deployed)
- `.github/workflows/build-lldb-archives-linux.yml` (280+ lines)
- `.github/workflows/test-lldb-linux-x86.yml` (ready, skip removed)
- `.github/workflows/test-lldb-linux-arm.yml` (ready, skip removed)

### Documentation (Comprehensive)
- `.agent_task/WORKFLOW_TRIGGER_GUIDE.md` (650+ lines)
- `.agent_task/ARCHIVE_INTEGRATION_CHECKLIST.md` (850+ lines)
- `docs/LLDB.md` Linux troubleshooting (350+ lines)
- `docs/TESTING.md` LLDB testing (200+ lines)

### Python Modules (Ready)
- `downloads-bins/work/python_linux_x64/` (13 MB)
- `downloads-bins/work/python_linux_arm64/` (13 MB)

---

## Completion Criteria

**When to create DONE.md:**

Only after ALL of the following are complete:
1. ✅ Workflow triggered and succeeded
2. ✅ Archives integrated and committed
3. ✅ Local tests pass (x86_64 and ARM64)
4. ✅ Changes pushed to GitHub
5. ✅ CI/CD tests pass (both architectures)
6. ✅ Documentation updated (CLAUDE.md, LLDB.md)
7. ✅ All success criteria met (see checklist above)

**DONE.md location:** Project root (`C:\Users\niteris\dev\clang-tool-chain\DONE.md`)

**DONE.md content should include:**
- Completion date
- Summary of achievements
- Links to archives
- Test results
- Known limitations
- Future work recommendations

---

## Agent Loop Strategy for Next Iterations

**Iteration 18+ Strategy:**

1. **Check workflow status first:**
   ```bash
   gh run list --workflow="build-lldb-archives-linux.yml" --limit 1
   ```

2. **If workflow completed:**
   - Run integration script
   - Test locally
   - Commit and push
   - Monitor CI/CD
   - Update documentation
   - Create DONE.md if all success criteria met

3. **If workflow still pending:**
   - Continue documentation improvements
   - Or wait for workflow completion
   - Or create interim status report

4. **If workflow failed:**
   - Analyze logs
   - Document failure reasons
   - Recommend retry or fixes
   - Update this plan with findings

---

## Quick Reference Commands

**Check workflow status:**
```bash
gh run list --workflow="build-lldb-archives-linux.yml" --limit 1
```

**Integrate archives (after workflow):**
```bash
cd downloads-bins
python tools/integrate_lldb_linux_archives.py
```

**Test locally:**
```bash
pytest tests/test_lldb.py -v -k "not windows"
```

**Check Python environment:**
```bash
clang-tool-chain-lldb --check-python
```

**Verify archive integrity:**
```bash
cd downloads-bins/assets/lldb/linux/x86_64
sha256sum -c lldb-21.1.5-linux-x86_64.tar.zst.sha256
```

---

**Status:** Iteration 17 complete - Ready for human trigger or automatic continuation in Iteration 18+

**Next Action:** Human triggers workflow, then agent loop can automate remaining steps
