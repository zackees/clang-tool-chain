# Instructions for Iteration 2

## Current Status
- ✅ Critical bug fix committed (URL format in manifest generation)
- ✅ Build infrastructure verified and ready
- ✅ Comprehensive analysis completed
- ❌ **BLOCKED**: Cannot build macOS binaries on Windows platform

## Platform Blocker Details
The task requires native macOS hardware to build darwin-x86_64 and darwin-arm64 Emscripten binaries. The current environment is Windows (MINGW64_NT-10.0-19045).

**Why cross-compilation doesn't work**:
- Emscripten's emsdk clones and builds LLVM with WebAssembly backend
- LLVM binaries are platform-specific and must be built on the target platform
- Cannot use Docker (produces Linux binaries)
- Cannot cross-compile macOS binaries on Windows or Linux

## Three Paths Forward

### Option A: Wait for macOS Hardware Access
If the repository maintainer or another team member has macOS access:

1. **On macOS system**, run these commands:
   ```bash
   # Pull latest changes with bug fix
   git pull origin main
   git submodule update --remote downloads-bins

   # Install pyzstd
   pip3 install pyzstd

   # Navigate to tools directory
   cd downloads-bins/tools

   # Build x86_64 (Intel Mac or Apple Silicon)
   python3 fetch_and_archive_emscripten.py --platform darwin --arch x86_64

   # Build arm64 (Apple Silicon only)
   python3 fetch_and_archive_emscripten.py --platform darwin --arch arm64
   ```

2. **Upload archives to Git LFS**:
   ```bash
   cd ../..  # Back to downloads-bins root
   git lfs track "assets/emscripten/darwin/**/*.tar.zst*"
   git add .gitattributes
   git add assets/emscripten/darwin/
   git commit -m "feat(emscripten): add darwin x86_64 and arm64 builds"
   git push origin main
   ```

3. **Update main repository**:
   ```bash
   cd ..  # Back to clang-tool-chain
   git add downloads-bins
   git commit -m "chore: update downloads-bins with macOS Emscripten binaries"
   git push origin main
   ```

### Option B: GitHub Actions CI/CD Automation
Set up automated builds using GitHub's macOS runners:

1. **Create workflow file**: `.github/workflows/build-emscripten-macos.yml`
2. **Use macOS runners**:
   - `macos-13` for x86_64 builds
   - `macos-14` for arm64 builds (Apple Silicon)
3. **Automate**: Download, build, upload to Git LFS
4. **Trigger**: Manual workflow dispatch or on release

**Advantages**:
- No need for local macOS hardware
- Reproducible builds
- Can be re-run for future updates
- Free for public repositories

**Disadvantages**:
- Requires workflow setup (~2-4 hours)
- macOS runner minutes count against quota (but generous for public repos)

### Option C: Defer Task
If macOS support is not immediately critical:

1. Document the blocker clearly
2. Mark task as deferred
3. Create GitHub issue for tracking
4. Move to other tasks
5. Return when macOS access becomes available

## What Iteration 2 Should Do

### If macOS Hardware Becomes Available:
1. Execute builds following Option A steps
2. Verify archives are ~150-200 MB each
3. Check critical file exists: `emscripten-version.txt`
4. Upload to Git LFS
5. Test downloads from clang-tool-chain package
6. Mark task as COMPLETE

### If Setting Up CI/CD:
1. Research GitHub Actions macOS runner documentation
2. Create workflow file with build steps
3. Test workflow execution
4. Document automation for future updates
5. Mark task as COMPLETE (automation ready)

### If Hardware Not Available:
1. Document options presented to maintainer
2. Check if there are related tasks that can be done
3. Consider if Linux arm64 Emscripten build is possible (similar PENDING state)
4. Update task.md with decision and timeline

## Key Files to Monitor

### Modified in Iteration 1:
- `downloads-bins/tools/fetch_and_archive_emscripten.py` (bug fixed)
- `task.md` (status updated)
- `.agent_task/ITERATION_1.md` (analysis)

### Will Be Modified in Iteration 2:
- `downloads-bins/assets/emscripten/darwin/x86_64/manifest.json` (after build)
- `downloads-bins/assets/emscripten/darwin/arm64/manifest.json` (after build)
- New archives in `downloads-bins/assets/emscripten/darwin/{arch}/`

### Potentially Create in Iteration 2:
- `.github/workflows/build-emscripten-macos.yml` (if CI/CD approach)
- `.agent_task/ITERATION_2.md` (progress documentation)
- `DONE.md` (if task completes!)

## Success Criteria

The task is COMPLETE when:
- ✅ darwin-x86_64 Emscripten archive built and uploaded
- ✅ darwin-arm64 Emscripten archive built and uploaded
- ✅ Both manifest.json files updated (no longer "PENDING")
- ✅ Archives accessible via media.githubusercontent.com URLs
- ✅ SHA256 checksums verified
- ✅ Test installation succeeds: `clang-tool-chain-emcc --version` on macOS
- ✅ Basic compilation test passes

OR if automation approach:
- ✅ GitHub Actions workflow created and tested
- ✅ Workflow successfully builds and uploads archives
- ✅ Documentation updated with automation instructions

## Questions to Answer in Iteration 2

1. **Is macOS hardware available?**
   - Check with repository maintainer
   - Look for macOS machines in development environment
   - Consider personal/team macOS devices

2. **What's the urgency for macOS support?**
   - High: Block on this until complete
   - Medium: Set up automation or coordinate with maintainer
   - Low: Defer and document blocker

3. **Should we use GitHub Actions?**
   - Would enable future automated updates
   - One-time setup cost
   - Ongoing benefit for maintenance

## Estimated Time Remaining

**With macOS Hardware Available**:
- Builds: 1-2 hours (automated, both architectures)
- Upload: 15 minutes
- Testing: 30 minutes
- Documentation: 15 minutes
- **Total: 2-3 hours**

**With GitHub Actions Setup**:
- Research: 30 minutes
- Workflow creation: 1-2 hours
- Testing: 1 hour
- Documentation: 30 minutes
- **Total: 3-4 hours**

**Without macOS Access**:
- Document blocker: 15 minutes
- Coordinate with maintainer: 15 minutes
- **Total: 30 minutes (then wait)**

## Summary

Iteration 1 successfully prepared everything needed for macOS Emscripten builds and fixed a critical bug that would have affected all platforms. The only remaining blocker is platform availability.

**Next agent should**: Determine which of the three paths forward is most appropriate and proceed accordingly.

**Critical**: The bug fix is now committed, so any future builds (including macOS) will generate correct manifest URLs.
