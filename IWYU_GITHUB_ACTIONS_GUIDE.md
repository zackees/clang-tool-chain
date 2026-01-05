# IWYU GitHub Actions Build Guide

Quick guide to building IWYU archives using GitHub Actions.

## TL;DR - Run the Build

**Recommended Method (Homebrew - Fast & Cheap):**
```bash
# From GitHub UI:
1. Go to Actions tab
2. Select "Build IWYU macOS Archives (Homebrew Method)"
3. Click "Run workflow"
4. Wait ~5-8 minutes
5. Download artifacts

# Or via gh CLI:
gh workflow run build-iwyu-macos-homebrew.yml
gh run watch  # Watch progress
```

**Alternative Method (Source Build - Slower but Static):**
```bash
gh workflow run build-iwyu-macos.yml
gh run watch
```

## Workflow Details

### Homebrew Method ⚡ (Recommended)

**File**: `.github/workflows/build-iwyu-macos-homebrew.yml`

**What it does:**
1. Installs IWYU via Homebrew
2. Extracts binaries and support files
3. Copies required LLVM dylibs
4. Fixes install names for portability
5. Creates compressed archives

**Jobs:**
- `extract-iwyu-macos-x64` - Intel Mac (macos-13)
- `extract-iwyu-macos-arm64` - Apple Silicon (macos-latest)
- `summary` - Displays results

**Runtime:** ~5-8 minutes (both arches in parallel)
**Cost:** ~$0.08-0.16 USD per run

**Output Artifacts:**
- `iwyu-darwin-x86_64-homebrew/`
  - `iwyu-0.25-darwin-x86_64.tar.zst`
  - `iwyu-0.25-darwin-x86_64.tar.zst.sha256`
- `iwyu-darwin-arm64-homebrew/`
  - `iwyu-0.25-darwin-arm64.tar.zst`
  - `iwyu-0.25-darwin-arm64.tar.zst.sha256`

### Source Build Method 🔨

**File**: `.github/workflows/build-iwyu-macos.yml`

**What it does:**
1. Installs Homebrew LLVM
2. Downloads IWYU source
3. Builds with static linking
4. Strips debug symbols
5. Creates compressed archives

**Jobs:**
- `build-iwyu-macos-x64` - Intel Mac (macos-15-large)
- `build-iwyu-macos-arm64` - Apple Silicon (macos-latest)

**Runtime:** ~15-20 minutes (both arches in parallel)
**Cost:** ~$0.16-0.32 USD per run

**Output Artifacts:**
- `iwyu-darwin-x86_64/`
  - `iwyu-0.25-darwin-x86_64.tar.zst`
  - `iwyu-0.25-darwin-x86_64.tar.zst.sha256`
- `iwyu-darwin-arm64/`
  - `iwyu-0.25-darwin-arm64.tar.zst`
  - `iwyu-0.25-darwin-arm64.tar.zst.sha256`

## Step-by-Step: Deploy New IWYU Binaries

### 1. Trigger the Workflow

**Via GitHub UI:**
1. Go to https://github.com/zackees/clang-tool-chain/actions
2. Click "Build IWYU macOS Archives (Homebrew Method)" in left sidebar
3. Click "Run workflow" button (top right)
4. Select branch (usually `main`)
5. Click green "Run workflow" button

**Via gh CLI:**
```bash
# Make sure you're in the repo directory
cd /path/to/clang-tool-chain

# Run the workflow
gh workflow run build-iwyu-macos-homebrew.yml

# Watch the progress
gh run watch

# Or list recent runs
gh run list --workflow=build-iwyu-macos-homebrew.yml
```

### 2. Monitor Progress

**In GitHub UI:**
- Yellow circle = Running
- Green checkmark = Success
- Red X = Failed

**Via gh CLI:**
```bash
# Watch live
gh run watch

# View logs
gh run view --log

# View specific job
gh run view --job=<job-id>
```

### 3. Download Artifacts

**Via GitHub UI:**
1. Click on the completed workflow run
2. Scroll down to "Artifacts" section
3. Download both archives:
   - `iwyu-darwin-x86_64-homebrew`
   - `iwyu-darwin-arm64-homebrew`

**Via gh CLI:**
```bash
# List artifacts for latest run
gh run list --workflow=build-iwyu-macos-homebrew.yml --limit 1

# Download artifacts (replace RUN_ID)
gh run download RUN_ID

# Or download from specific run
gh run download --name iwyu-darwin-arm64-homebrew
gh run download --name iwyu-darwin-x86_64-homebrew
```

### 4. Verify Archives

```bash
# Unzip the downloaded artifacts
unzip iwyu-darwin-arm64-homebrew.zip
unzip iwyu-darwin-x86_64-homebrew.zip

# Verify checksums
cd iwyu-darwin-arm64-homebrew
cat iwyu-0.25-darwin-arm64.tar.zst.sha256
sha256sum iwyu-0.25-darwin-arm64.tar.zst
# Hashes should match!

# Test extraction (optional)
mkdir test_extract
cd test_extract
tar -xf ../iwyu-0.25-darwin-arm64.tar.zst
./bin/include-what-you-use --version
```

### 5. Update Manifests

```bash
# Get SHA256 hashes
ARM64_HASH=$(cat iwyu-darwin-arm64-homebrew/iwyu-0.25-darwin-arm64.tar.zst.sha256 | awk '{print $1}')
X64_HASH=$(cat iwyu-darwin-x86_64-homebrew/iwyu-0.25-darwin-x86_64.tar.zst.sha256 | awk '{print $1}')

echo "ARM64 SHA256: $ARM64_HASH"
echo "x86_64 SHA256: $X64_HASH"

# Update manifests
# Edit: downloads-bins/assets/iwyu/darwin/arm64/manifest.json
# Edit: downloads-bins/assets/iwyu/darwin/x86_64/manifest.json
```

**Manifest format:**
```json
{
  "latest": "0.25",
  "0.25": {
    "href": "https://media.githubusercontent.com/media/zackees/clang-tool-chain-bins/main/assets/iwyu/darwin/arm64/iwyu-0.25-darwin-arm64.tar.zst",
    "sha256": "<PASTE_ARM64_HASH_HERE>"
  }
}
```

### 6. Upload to downloads-bins Repository

```bash
# Navigate to downloads-bins
cd downloads-bins

# Copy archives from downloaded artifacts
cp ../iwyu-darwin-arm64-homebrew/iwyu-0.25-darwin-arm64.tar.zst assets/iwyu/darwin/arm64/
cp ../iwyu-darwin-arm64-homebrew/iwyu-0.25-darwin-arm64.tar.zst.sha256 assets/iwyu/darwin/arm64/

cp ../iwyu-darwin-x86_64-homebrew/iwyu-0.25-darwin-x86_64.tar.zst assets/iwyu/darwin/x86_64/
cp ../iwyu-darwin-x86_64-homebrew/iwyu-0.25-darwin-x86_64.tar.zst.sha256 assets/iwyu/darwin/x86_64/

# Add and commit
git add assets/iwyu/darwin/
git commit -m "fix(iwyu): Update macOS binaries from Homebrew

- Extracted from Homebrew include-what-you-use formula
- Bundles required LLVM dylibs for portability
- Fixes macOS IWYU SIGABRT crashes
- Tested on ARM64 and x86_64

Binary details:
- ARM64 SHA256: $ARM64_HASH
- x86_64 SHA256: $X64_HASH"

# Push (including LFS objects)
git lfs push origin main
git push origin main
```

### 7. Test in Production

```bash
# Remove local IWYU cache
rm -rf ~/.clang-tool-chain/iwyu

# Test via clang-tool-chain
pip install --upgrade clang-tool-chain

# Test IWYU
clang-tool-chain-iwyu --version

# Should output:
# include-what-you-use 0.25 based on clang version 21.1.6
```

### 8. Verify CI Tests Pass

Watch the test workflows:
- https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml
- https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-x86.yml

All 4 IWYU tests should pass ✅

## Troubleshooting Workflows

### Workflow Run Failed

**Check the logs:**
```bash
gh run view --log

# Or in GitHub UI:
# Click on failed run → Click on failed job → Expand failed step
```

**Common issues:**

1. **Homebrew installation failed**
   - Check if Homebrew is down: https://www.apple.com/support/systemstatus/
   - Try re-running the workflow

2. **IWYU formula not found**
   - Homebrew may have renamed/removed the formula
   - Check: `brew info include-what-you-use`
   - Fall back to source build method

3. **Archive creation failed**
   - Check if zstandard is installed
   - Check disk space on runner

4. **Artifact upload failed**
   - GitHub Actions may have issues
   - Try re-running just the failed job

### Re-run Failed Jobs

**Via GitHub UI:**
1. Click on failed workflow run
2. Click "Re-run failed jobs" button

**Via gh CLI:**
```bash
gh run rerun <run-id>

# Or rerun failed jobs only
gh run rerun <run-id> --failed
```

### View Workflow Status

```bash
# List recent runs
gh run list --workflow=build-iwyu-macos-homebrew.yml --limit 10

# Watch a specific run
gh run watch <run-id>

# View run details
gh run view <run-id>
```

## Cost Optimization

### Minimize GitHub Actions Costs

**Use Homebrew method** (50% cheaper):
- Runs faster → Less runner time
- Cheaper runners (standard vs large)

**Avoid unnecessary runs:**
- Only run when IWYU needs updating
- Don't run on every commit
- Use `workflow_dispatch` (manual trigger)

**Runner selection:**
- ARM64: `macos-latest` (Apple Silicon)
- x86_64: `macos-13` (Intel, cheaper than macos-15-large)

### Estimated Costs

**Homebrew method:**
- ARM64: ~$0.04-0.08 (3-5 min on macos-latest)
- x86_64: ~$0.04-0.08 (3-5 min on macos-13)
- **Total: ~$0.08-0.16 per full run**

**Source build method:**
- ARM64: ~$0.08-0.16 (8-12 min on macos-latest)
- x86_64: ~$0.08-0.16 (8-12 min on macos-15-large)
- **Total: ~$0.16-0.32 per full run**

## Best Practices

### When to Run Builds

**Run builds when:**
- ✅ Homebrew IWYU version updates
- ✅ Fixing bugs in binaries
- ✅ Testing new extraction logic
- ✅ Initial setup

**Don't run builds when:**
- ❌ Changing documentation only
- ❌ Updating tests (unless for IWYU)
- ❌ Modifying unrelated workflows

### Archive Management

**Keep archives organized:**
```
downloads-bins/assets/iwyu/darwin/
├── arm64/
│   ├── manifest.json
│   ├── iwyu-0.25-darwin-arm64.tar.zst
│   └── iwyu-0.25-darwin-arm64.tar.zst.sha256
└── x86_64/
    ├── manifest.json
    ├── iwyu-0.25-darwin-x86_64.tar.zst
    └── iwyu-0.25-darwin-x86_64.tar.zst.sha256
```

**Version management:**
- Keep old versions for rollback
- Update `latest` in manifest.json
- Document changes in commit messages

## Quick Commands Reference

```bash
# Trigger build
gh workflow run build-iwyu-macos-homebrew.yml

# Watch progress
gh run watch

# List recent runs
gh run list --workflow=build-iwyu-macos-homebrew.yml --limit 5

# Download artifacts
gh run download <run-id>

# View logs
gh run view <run-id> --log

# Re-run failed jobs
gh run rerun <run-id> --failed
```

## See Also

- [IWYU Build Methods](IWYU_BUILD_METHODS.md) - Comparison of build methods
- [IWYU macOS Fix Summary](IWYU_MACOS_FIX_SUMMARY.md) - Problem analysis
- [Build Quick Start](IWYU_BUILD_QUICK_START.md) - Local build guide
- [GitHub Actions Docs](https://docs.github.com/en/actions)

---

**Last Updated**: 2026-01-05
**Workflow Files**:
- `.github/workflows/build-iwyu-macos-homebrew.yml`
- `.github/workflows/build-iwyu-macos.yml`
