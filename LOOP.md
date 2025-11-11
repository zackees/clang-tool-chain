# Agent Loop: Find Working IWYU Distribution with Bundled Dependencies

## Objective
Find a pre-built IWYU distribution for Windows that includes all necessary DLLs and works locally, then package it for distribution.

## Constraints
- **Cannot rebuild with static linking** (unsigned binaries cannot be redistributed)
- **Must find existing distribution** with all dependencies bundled
- **Must verify locally first** before creating archive
- **Must test on clean system** (no MSYS2/LLVM in PATH)

---

## Phase 1: Search for Pre-built IWYU Distributions

### Task 1.1: Check Official IWYU Sources
**Goal**: Determine if official IWYU provides Windows binaries with dependencies

**Commands**:
```bash
# Check IWYU releases
curl -s https://api.github.com/repos/include-what-you-use/include-what-you-use/releases/latest

# Check if any releases have Windows binaries
curl -s https://api.github.com/repos/include-what-you-use/include-what-you-use/releases | jq '.[].assets[] | select(.name | contains("win"))'
```

**Success Criteria**: Find official Windows binaries
**If Failed**: Proceed to Task 1.2

---

### Task 1.2: Check llvm-mingw Distribution
**Goal**: Verify if llvm-mingw includes IWYU and test if it works standalone

**Investigation**:
```bash
# Already have llvm-mingw downloaded
cd /tmp/iwyu_fix/llvm-mingw-20251104-msvcrt-x86_64

# Check if IWYU is included
find . -name "*iwyu*" -o -name "include-what-you-use*"

# If found, check what it is
file bin/include-what-you-use* 2>/dev/null
```

**Test Locally**:
```bash
# If IWYU binary found in llvm-mingw
cd /tmp/iwyu_fix/llvm-mingw-20251104-msvcrt-x86_64/bin

# Test version (all DLLs should be in same directory)
./include-what-you-use.exe --version
echo "Exit code: $?"

# Test with actual file
cat > /tmp/test.cpp << 'EOF'
#include <iostream>
int main() {
    std::cout << "test" << std::endl;
    return 0;
}
EOF

./include-what-you-use.exe /tmp/test.cpp -- -std=c++11
echo "Exit code: $?"
```

**Success Criteria**:
- IWYU binary exists in llvm-mingw
- `--version` returns exit code 0 or 1 (not crash codes)
- Actual analysis completes without crashing
- `ldd` shows all dependencies resolved within llvm-mingw directory

**If Failed**: Proceed to Task 1.3

---

### Task 1.3: Check Chocolatey Packages
**Goal**: Check if Chocolatey has IWYU package with bundled dependencies

**Commands**:
```powershell
# Search Chocolatey
choco search include-what-you-use

# If found, install to temp location
choco install include-what-you-use --install-directory=C:\temp\iwyu-test -y

# Test the binary
cd C:\temp\iwyu-test
.\include-what-you-use.exe --version
```

**Success Criteria**: Working IWYU binary with all dependencies
**If Failed**: Proceed to Task 1.4

---

### Task 1.4: Check vcpkg
**Goal**: Check if vcpkg provides IWYU binary package

**Commands**:
```bash
# Search vcpkg
vcpkg search include-what-you-use

# If found, install
vcpkg install include-what-you-use:x64-windows

# Find installed binary
find ~/vcpkg/installed/x64-windows -name "include-what-you-use.exe"

# Test
cd ~/vcpkg/installed/x64-windows/tools/
./include-what-you-use.exe --version
```

**Success Criteria**: Working IWYU binary with dependencies
**If Failed**: Proceed to Task 1.5

---

### Task 1.5: Check MSYS2 with Full LLVM Package
**Goal**: Install complete LLVM package in MSYS2 and extract IWYU + dependencies

**Investigation**:
The current IWYU binary came from MSYS2 but was extracted without its DLL dependencies. Instead of bundling incompatible DLLs from llvm-mingw, extract the EXACT dependencies from the same MSYS2 environment.

**Commands**:
```bash
# Install LLVM package in MSYS2 (includes libLLVM-21.dll, libclang-cpp.dll)
pacman -S mingw-w64-x86_64-llvm

# Install IWYU package
pacman -S mingw-w64-x86_64-include-what-you-use

# Locate installed IWYU
which include-what-you-use.exe

# Check dependencies
ldd /mingw64/bin/include-what-you-use.exe

# Find all required DLLs that are NOT system DLLs
ldd /mingw64/bin/include-what-you-use.exe | grep mingw64 | awk '{print $3}'

# Copy IWYU + all mingw64 DLLs to test directory
mkdir -p /tmp/iwyu_msys2_bundle/bin
cp /mingw64/bin/include-what-you-use.exe /tmp/iwyu_msys2_bundle/bin/

# Copy all non-system DLL dependencies
for dll in $(ldd /mingw64/bin/include-what-you-use.exe | grep mingw64 | awk '{print $3}'); do
    cp "$dll" /tmp/iwyu_msys2_bundle/bin/
done

# Copy Python helper scripts
cp /mingw64/bin/iwyu_tool.py /tmp/iwyu_msys2_bundle/bin/
cp /mingw64/bin/fix_includes.py /tmp/iwyu_msys2_bundle/bin/

# Copy share directory (IWYU mappings)
cp -r /mingw64/share/include-what-you-use /tmp/iwyu_msys2_bundle/share/
```

**Test Locally (CRITICAL - must work BEFORE archiving)**:
```bash
# Test in isolated directory (no MSYS2 in PATH)
cd /tmp/iwyu_msys2_bundle/bin

# Open new CMD window (not MSYS2 shell) and test
cmd /c "include-what-you-use.exe --version"
echo "Exit code: $?"

# Test with real C++ file
cat > /tmp/test.cpp << 'EOF'
#include <iostream>
#include <vector>
int main() {
    std::cout << "test" << std::endl;
    return 0;
}
EOF

cmd /c "include-what-you-use.exe /tmp/test.cpp -- -std=c++11"
echo "Exit code: $?"

# Verify no missing dependencies
ldd include-what-you-use.exe | grep "not found"
# Should return nothing
```

**Success Criteria**:
- IWYU binary executes without crashes
- Exit codes are 0, 1, or 2 (valid IWYU return codes, not crash codes like 127 or 3221225781)
- `ldd` shows NO "not found" entries
- Works in CMD window (not MSYS2 shell) proving it's standalone
- All dependencies are in the same `bin/` directory

**If Failed**: Proceed to Task 1.6

---

### Task 1.6: Check Official LLVM Releases
**Goal**: Download official LLVM Windows release and check if it includes IWYU

**Commands**:
```bash
# Download LLVM 21.1.5 Windows release
wget https://github.com/llvm/llvm-project/releases/download/llvmorg-21.1.5/LLVM-21.1.5-win64.exe

# Extract with 7zip
7z x LLVM-21.1.5-win64.exe -o/tmp/llvm-official

# Search for IWYU
find /tmp/llvm-official -name "*iwyu*" -o -name "include-what-you-use*"
```

**Success Criteria**: Find working IWYU with dependencies
**If Failed**: Proceed to Phase 2

---

## Phase 2: Test Working Distribution Locally

**CRITICAL**: This phase must be completed SUCCESSFULLY before creating any archives.

### Task 2.1: Verify Binary Works Standalone
**Goal**: Ensure IWYU binary works WITHOUT system LLVM installed

**Setup Clean Test Environment**:
```bash
# Remove any MSYS2/LLVM from PATH
export PATH="/usr/bin:/bin"  # Minimal PATH

# Or test in fresh CMD window
cmd /c "set PATH=C:\Windows\System32;C:\Windows"
```

**Test Commands**:
```bash
cd /tmp/iwyu_bundle_test/bin  # Wherever you have the candidate IWYU

# Test 1: Version command
./include-what-you-use.exe --version
RESULT=$?
echo "Version test exit code: $RESULT"
# Expected: 0 or 1 (NOT 127, 3221225781, 3221225785)

# Test 2: Help command
./include-what-you-use.exe --help 2>&1 | head -5
RESULT=$?
echo "Help test exit code: $RESULT"

# Test 3: Real analysis
cat > /tmp/test_simple.cpp << 'EOF'
#include <iostream>
int main() {
    std::cout << "Hello" << std::endl;
    return 0;
}
EOF

./include-what-you-use.exe /tmp/test_simple.cpp -- -std=c++11
RESULT=$?
echo "Analysis test exit code: $RESULT"
# Expected: 0, 1, or 2 (IWYU returns non-zero when suggesting changes)

# Test 4: Python helper scripts
python3 iwyu_tool.py --help
RESULT=$?
echo "iwyu_tool.py test exit code: $RESULT"

python3 fix_includes.py --help
RESULT=$?
echo "fix_includes.py test exit code: $RESULT"
```

**Success Criteria**:
- All tests return valid exit codes (0-2, NOT crash codes)
- No DLL missing errors
- IWYU provides actual output (not empty stderr/stdout)
- Helper scripts execute successfully

**Documentation**:
```bash
# Document the working configuration
echo "Working IWYU Configuration:" > /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
echo "Date: $(date)" >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
echo "IWYU Version: $(./include-what-you-use.exe --version 2>&1 | head -1)" >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
echo "" >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
echo "Bundled DLLs:" >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
ls -lh bin/*.dll >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
echo "" >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
echo "Dependency Check:" >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
ldd bin/include-what-you-use.exe >> /tmp/iwyu_bundle_test/WORKING_CONFIG.txt
```

**If ALL Tests Pass**: Proceed to Task 2.2
**If ANY Test Fails**: Return to Phase 1, try next source

---

### Task 2.2: Test with clang-tool-chain Integration
**Goal**: Verify IWYU works when installed to clang-tool-chain location

**Commands**:
```bash
# Backup current installation
mv ~/.clang-tool-chain/iwyu ~/.clang-tool-chain/iwyu.backup

# Create new installation with candidate IWYU
mkdir -p ~/.clang-tool-chain/iwyu/win/x86_64
cp -r /tmp/iwyu_bundle_test/* ~/.clang-tool-chain/iwyu/win/x86_64/

# Create done.txt marker
echo "Local test installation" > ~/.clang-tool-chain/iwyu/win/x86_64/done.txt

# Test via Python wrapper
cd ~/dev/clang-tool-chain
uv run python -c "
from clang_tool_chain import wrapper
import subprocess

iwyu_path = wrapper.find_iwyu_tool('include-what-you-use')
print(f'IWYU path: {iwyu_path}')

result = subprocess.run([str(iwyu_path), '--version'], capture_output=True, text=True, timeout=10)
print(f'Exit code: {result.returncode}')
print(f'Output: {result.stdout}{result.stderr}')
"

# Run actual tests (with skip removed temporarily for this test only)
uv run pytest tests/test_iwyu.py::TestIWYUExecution::test_iwyu_version -v
```

**Success Criteria**:
- Python wrapper finds IWYU successfully
- Version command completes with exit code 0 or 1
- Test passes (not skipped, not failed)

**If Failed**: Binary doesn't work in clang-tool-chain context, debug or try different source
**If Passed**: Proceed to Phase 3

---

## Phase 3: Create Archive

**PREREQUISITE**: Phase 2 must be 100% successful before proceeding

### Task 3.1: Prepare Archive Contents
**Goal**: Prepare clean directory structure for archiving

**Commands**:
```bash
cd /tmp/archive_prep
mkdir -p iwyu_final/{bin,share}

# Copy from working installation
cp ~/.clang-tool-chain/iwyu/win/x86_64/bin/* iwyu_final/bin/
cp -r ~/.clang-tool-chain/iwyu/win/x86_64/share/* iwyu_final/share/

# List all files to be archived
find iwyu_final -type f -exec ls -lh {} \;

# Verify binaries and DLLs
echo "=== Binaries and DLLs ==="
ls -lh iwyu_final/bin/

# Calculate total size
du -sh iwyu_final
```

**Documentation**:
Create `iwyu_final/README.txt`:
```
IWYU Bundle for Windows x86_64
==============================

Source: [Document where you got this - MSYS2/vcpkg/etc]
Date: [Current date]
LLVM Version: 21.x.x
IWYU Version: 0.25

Bundled Components:
- include-what-you-use.exe
- iwyu_tool.py
- fix_includes.py
- Required DLLs (list them)
- IWYU mappings (share/include-what-you-use/)

Tested on:
- Windows 10/11 x64
- Clean system without LLVM installed
- Exit codes: 0-2 (success)
```

---

### Task 3.2: Create TAR Archive
**Goal**: Create uncompressed TAR archive with correct permissions

**Commands**:
```python
import tarfile
from pathlib import Path

def tar_filter(tarinfo):
    """Set correct permissions for IWYU files."""
    if tarinfo.isfile():
        if '/bin/' in tarinfo.name or tarinfo.name.startswith('bin/'):
            if tarinfo.name.endswith(('.py', '.exe', '.dll')):
                tarinfo.mode = 0o755  # Executable
            else:
                tarinfo.mode = 0o644  # Readable
        else:
            tarinfo.mode = 0o644
    return tarinfo

source_dir = Path('/tmp/archive_prep/iwyu_final')
output_tar = Path('/tmp/archive_prep/iwyu-0.25-win-x86_64.tar')

print(f"Creating TAR archive...")
with tarfile.open(output_tar, 'w') as tar:
    bin_dir = source_dir / 'bin'
    if bin_dir.exists():
        tar.add(bin_dir, arcname='bin', filter=tar_filter)

    share_dir = source_dir / 'share'
    if share_dir.exists():
        tar.add(share_dir, arcname='share', filter=tar_filter)

size_mb = output_tar.stat().st_size / (1024*1024)
print(f"Created: {output_tar} ({size_mb:.2f} MB)")
```

---

### Task 3.3: Compress with zstd
**Goal**: Compress TAR archive to final distributable format

**Commands**:
```python
import zstandard as zstd
from pathlib import Path
import time

tar_file = Path('/tmp/archive_prep/iwyu-0.25-win-x86_64.tar')
output_zst = Path('/tmp/archive_prep/iwyu-0.25-win-x86_64.tar.zst')

print(f"Compressing with zstd level 22...")
start = time.time()

cctx = zstd.ZstdCompressor(level=22, threads=-1)

with open(tar_file, 'rb') as ifh, open(output_zst, 'wb') as ofh:
    chunk_size = 1024 * 1024
    reader = cctx.stream_reader(ifh, size=tar_file.stat().st_size)
    while True:
        chunk = reader.read(chunk_size)
        if not chunk:
            break
        ofh.write(chunk)

elapsed = time.time() - start
original_size = tar_file.stat().st_size
compressed_size = output_zst.stat().st_size
ratio = original_size / compressed_size if compressed_size > 0 else 0

print(f"Compressed in {elapsed:.1f}s")
print(f"Original:   {original_size / (1024*1024):.2f} MB")
print(f"Compressed: {compressed_size / (1024*1024):.2f} MB")
print(f"Ratio:      {ratio:.2f}:1")
print(f"Reduction:  {(1 - compressed_size/original_size) * 100:.1f}%")
```

---

### Task 3.4: Generate Checksum
**Goal**: Generate SHA256 checksum for archive

**Commands**:
```python
import hashlib
from pathlib import Path

archive_file = Path('/tmp/archive_prep/iwyu-0.25-win-x86_64.tar.zst')
sha256_hash = hashlib.sha256()

print("Generating SHA256 checksum...")
with open(archive_file, 'rb') as f:
    for byte_block in iter(lambda: f.read(4096), b''):
        sha256_hash.update(byte_block)

checksum = sha256_hash.hexdigest()
print(f"SHA256: {checksum}")

# Write checksum file
checksum_file = Path(f'{archive_file}.sha256')
with open(checksum_file, 'w') as f:
    f.write(f'{checksum}  {archive_file.name}\n')

print(f"Wrote: {checksum_file}")
```

---

## Phase 4: Test Archive Installation

**CRITICAL**: Must test archive extraction and installation before committing

### Task 4.1: Test Archive Extraction
**Goal**: Verify archive can be extracted correctly

**Commands**:
```bash
# Clean test location
rm -rf ~/.clang-tool-chain/iwyu

# Extract using expand_archive.py
cd /tmp/archive_test
python ~/dev/clang-tool-chain/downloads-bins/tools/expand_archive.py \
    /tmp/archive_prep/iwyu-0.25-win-x86_64.tar.zst \
    test_extract

# Verify structure
ls -la test_extract/
ls -la test_extract/bin/
ls -la test_extract/share/

# Check file permissions
find test_extract/bin -name "*.exe" -exec ls -l {} \;
find test_extract/bin -name "*.dll" -exec ls -l {} \;
```

**Success Criteria**:
- All files extracted successfully
- Directory structure is correct (bin/, share/)
- Executables have +x permission
- No extraction errors

---

### Task 4.2: Test Extracted Binary
**Goal**: Verify extracted IWYU works identically to source

**Commands**:
```bash
cd /tmp/archive_test/test_extract/bin

# Same tests as Phase 2
./include-what-you-use.exe --version
echo "Exit code: $?"

cat > /tmp/test.cpp << 'EOF'
#include <iostream>
int main() {
    std::cout << "test" << std::endl;
    return 0;
}
EOF

./include-what-you-use.exe /tmp/test.cpp -- -std=c++11
echo "Exit code: $?"
```

**Success Criteria**: Identical behavior to Phase 2 tests

---

### Task 4.3: Test via clang-tool-chain
**Goal**: Verify archive works when installed to clang-tool-chain location

**Commands**:
```bash
# Install extracted archive
mkdir -p ~/.clang-tool-chain/iwyu/win/x86_64
cp -r /tmp/archive_test/test_extract/* ~/.clang-tool-chain/iwyu/win/x86_64/
echo "Archive test installation" > ~/.clang-tool-chain/iwyu/win/x86_64/done.txt

# Run full test suite
cd ~/dev/clang-tool-chain
uv run pytest tests/test_iwyu.py -v

# Verify results
# - TestIWYUInstallation tests should PASS
# - TestIWYUExecution tests should PASS (not skip, not fail)
# - TestIWYUHelperScripts tests should PASS
```

**Success Criteria**: All tests pass

---

## Phase 5: Deploy Archive

**PREREQUISITE**: All Phase 4 tests must pass

### Task 5.1: Copy Archive to downloads-bins
**Commands**:
```bash
# Copy archive and checksum
cp /tmp/archive_prep/iwyu-0.25-win-x86_64.tar.zst \
    ~/dev/clang-tool-chain/downloads-bins/assets/iwyu/win/x86_64/

cp /tmp/archive_prep/iwyu-0.25-win-x86_64.tar.zst.sha256 \
    ~/dev/clang-tool-chain/downloads-bins/assets/iwyu/win/x86_64/

# List files
ls -lh ~/dev/clang-tool-chain/downloads-bins/assets/iwyu/win/x86_64/
```

---

### Task 5.2: Update Manifest
**Goal**: Update manifest.json with new checksum

**Commands**:
```bash
# Read checksum
CHECKSUM=$(cat /tmp/archive_prep/iwyu-0.25-win-x86_64.tar.zst.sha256 | awk '{print $1}')
echo "New checksum: $CHECKSUM"

# Update manifest manually or with jq
cd ~/dev/clang-tool-chain/downloads-bins/assets/iwyu/win/x86_64
cat manifest.json

# Edit manifest.json to update sha256 field
# Use Edit tool to update the sha256 value
```

---

### Task 5.3: Remove Windows Skip from Tests
**Goal**: Enable IWYU tests on Windows now that it works

**Commands**:
```bash
cd ~/dev/clang-tool-chain

# Remove @pytest.mark.skipif decorators from tests/test_iwyu.py
# Edit TestIWYUExecution class (remove lines 68-71)
# Edit TestIWYUHelperScripts class (remove lines 257-260)
```

---

### Task 5.4: Final Verification
**Goal**: Run complete test suite to verify everything works

**Commands**:
```bash
# Clean installation
rm -rf ~/.clang-tool-chain/iwyu

# Run tests (will trigger download from local downloads-bins)
cd ~/dev/clang-tool-chain
uv run pytest tests/test_iwyu.py -v

# Verify:
# - All tests PASS (no skips, no failures)
# - IWYU binary downloaded and extracted correctly
# - All functionality works as expected
```

**Success Criteria**:
- 12 tests passed, 0 skipped, 0 failed
- IWYU fully functional on Windows

---

## Phase 6: Commit and Push

**PREREQUISITE**: Phase 5 complete and verified

### Task 6.1: Commit to downloads-bins Repository
```bash
cd ~/dev/clang-tool-chain/downloads-bins

git status
git add assets/iwyu/win/x86_64/iwyu-0.25-win-x86_64.tar.zst
git add assets/iwyu/win/x86_64/iwyu-0.25-win-x86_64.tar.zst.sha256
git add assets/iwyu/win/x86_64/manifest.json

git commit -m "Fix: IWYU Windows bundle with all required DLLs

- Include IWYU binary with bundled dependencies
- Source: [MSYS2/vcpkg/etc - document actual source]
- Tested locally before archiving
- All dependencies verified with ldd
- Archive size: [X MB]
- SHA256: [checksum]

Fixes IWYU crash on Windows (exit codes 0xC0000005, 0xC0000009)
All tests passing on clean Windows system"

git push origin main
```

---

### Task 6.2: Update Main Repository
```bash
cd ~/dev/clang-tool-chain

# Update submodule reference
git add downloads-bins

# Stage test file changes (removed skips)
git add tests/test_iwyu.py

git commit -m "Fix: Enable IWYU tests on Windows

- Remove Windows skip from IWYU tests
- Update submodule to include working IWYU bundle
- All IWYU tests now passing on Windows

Tested with bundled DLLs from [source]
Exit codes: 0-2 (success, not crash codes)"

git push origin main
```

---

## Success Criteria Summary

### Phase 1 Success:
- [ ] Found pre-built IWYU distribution with bundled DLLs
- [ ] Source documented and reproducible

### Phase 2 Success (CRITICAL):
- [ ] IWYU binary executes without crashes (exit codes 0-2)
- [ ] Works in clean environment (no system LLVM)
- [ ] All dependencies resolved
- [ ] Helper scripts functional
- [ ] Integration with clang-tool-chain verified

### Phase 3 Success:
- [ ] Archive created with correct structure
- [ ] Compression successful
- [ ] Checksum generated

### Phase 4 Success (CRITICAL):
- [ ] Archive extracts correctly
- [ ] Extracted binary works identically to source
- [ ] All clang-tool-chain tests pass

### Phase 5 Success:
- [ ] Archive deployed to downloads-bins
- [ ] Manifest updated
- [ ] Windows skips removed
- [ ] Final test suite passes (12 passed, 0 skipped)

### Phase 6 Success:
- [ ] Changes committed to both repositories
- [ ] Changes pushed to remote

---

## Failure Recovery

### If Phase 1 Fails (No Pre-built Distribution Found):
**Action**: Cannot proceed with current approach. Alternatives:
1. Request permission to redistribute statically-linked binaries
2. Document that IWYU requires system LLVM installation on Windows
3. Skip IWYU functionality on Windows permanently

### If Phase 2 Fails (Binary Doesn't Work Locally):
**Action**: DO NOT CREATE ARCHIVE. Return to Phase 1, try different source.

### If Phase 4 Fails (Archive Installation Broken):
**Action**: Fix archive creation process, repeat Phase 3 and Phase 4.

---

## Notes

- **DO NOT skip Phase 2 local testing** - this is where previous attempt failed
- **DO NOT create archive until Phase 2 is 100% successful**
- **Document exact source of working IWYU** for reproducibility
- **Keep WORKING_CONFIG.txt** from Phase 2 for reference
- **Test in CMD window, not MSYS2 shell** to ensure true isolation

---

## Current Status: ITERATION 3 COMPLETE ✅

**Iteration 3 Results**:
- ✓ ROOT CAUSE FOUND: Missing transitive dependencies (libxml2-16.dll, libiconv-2.dll, liblzma-5.dll)
- ✓ Downloaded 3 additional MSYS2 packages
- ✓ Bundle Complete: IWYU + 11 DLLs (200 MB) - ALL dependencies resolved
- ✓ Phase 2 Testing: SUCCESS - Exit code 0, all tests passing locally
- ✓ Phase 3 Archive: SUCCESS - Created iwyu-0.25-win-x86_64.tar.zst (43.31 MB, 78.2% compression)
- ✓ Phase 4 Testing: SUCCESS - Archive extraction and execution verified
- ✓ Phase 5 Deploy: SUCCESS - Archive deployed to downloads-bins, manifest updated, tests enabled

**Key Discovery**: Must check `ldd *.dll` for ALL DLLs, not just main executable, to catch transitive dependencies.

**Remaining Work**: Phase 6 (Commit and Push to GitHub)

**Next Action for Iteration 4**:

### PRIORITY 1: Execute Phase 6 (Commit and Push)

**Files Ready for Commit**:
- `downloads-bins/assets/iwyu/win/x86_64/iwyu-0.25-win-x86_64.tar.zst` (43.31 MB)
- `downloads-bins/assets/iwyu/win/x86_64/iwyu-0.25-win-x86_64.tar.zst.sha256`
- `downloads-bins/assets/iwyu/win/x86_64/manifest.json` (updated SHA256)
- `tests/test_iwyu.py` (removed Windows skip decorators)

**Commit Steps**:

1. **Commit to downloads-bins repository** (submodule):
   ```bash
   cd ~/dev/clang-tool-chain/downloads-bins
   git add assets/iwyu/win/x86_64/iwyu-0.25-win-x86_64.tar.zst
   git add assets/iwyu/win/x86_64/iwyu-0.25-win-x86_64.tar.zst.sha256
   git add assets/iwyu/win/x86_64/manifest.json

   git commit -m "Fix: IWYU Windows bundle with complete dependencies

   - Bundle now includes all 11 required DLLs from MSYS2
   - Added missing transitive dependencies: libxml2, libiconv, liblzma
   - Source: MSYS2 packages (13 total packages)
   - Archive size: 43.31 MB (78.2% compression)
   - SHA256: b65f07afdd48257a1147fca1cd9024e74be549a82015124c689848bb68e5e7cb

   Tested locally: All dependencies resolved, exit code 0, tests passing
   Fixes exit code 127 / 0xC0000005 crashes from missing DLLs"

   git push origin main
   ```

2. **Update main repository**:
   ```bash
   cd ~/dev/clang-tool-chain
   git add downloads-bins  # Update submodule reference
   git add tests/test_iwyu.py  # Removed Windows skips

   git commit -m "Fix: Enable IWYU tests on Windows

   - Remove Windows skip from IWYU execution tests
   - Remove Windows skip from IWYU helper script tests
   - Update submodule to include working IWYU bundle

   All IWYU tests now passing on Windows with bundled DLLs from MSYS2"

   git push origin main
   ```

3. **Verify CI/CD tests pass** with remote archive download

4. **If all tests pass**: Create DONE.md to halt loop

---

### ALTERNATIVE: Option C - Manual MSYS2 Package Download (COMPLETED)
~~Download IWYU + dependencies from MSYS2 repo mirrors and extract manually:~~

**STATUS**: ✓ COMPLETED in Iteration 2
- Downloaded 10 MSYS2 packages from mirror.msys2.org
- Extracted using Python + zstandard
- Created bundle with all dependencies (191 MB)
- Verified dependencies with `ldd` (no missing DLLs)
- **BLOCKED**: Binary execution fails with exit code 127

1. **Find MSYS2 mirror with packages**:
   - Main repo: https://repo.msys2.org/mingw/mingw64/
   - Packages needed:
     * `mingw-w64-x86_64-include-what-you-use-0.25-*.pkg.tar.zst`
     * `mingw-w64-x86_64-llvm-21.*-*.pkg.tar.zst` (for DLLs)
     * Dependencies: libc++, libclang, libunwind

2. **Download packages**:
   ```bash
   cd /tmp/iwyu_msys2_manual
   wget https://repo.msys2.org/mingw/mingw64/[package-name].pkg.tar.zst
   ```

3. **Extract packages**:
   ```bash
   # Extract IWYU package
   tar -xf mingw-w64-x86_64-include-what-you-use-*.pkg.tar.zst

   # Extract LLVM package (for DLLs)
   tar -xf mingw-w64-x86_64-llvm-*.pkg.tar.zst
   ```

4. **Bundle IWYU + exact DLLs from extracted MSYS2 packages**:
   ```bash
   mkdir -p bundle/bin bundle/share

   # Copy IWYU
   cp mingw64/bin/include-what-you-use.exe bundle/bin/
   cp mingw64/bin/iwyu_tool.py bundle/bin/
   cp mingw64/bin/fix_includes.py bundle/bin/

   # Copy DLLs from SAME MSYS2 packages
   cp mingw64/bin/libLLVM-21.dll bundle/bin/
   cp mingw64/bin/libclang-cpp.dll bundle/bin/
   cp mingw64/bin/libc++.dll bundle/bin/
   cp mingw64/bin/libunwind.dll bundle/bin/
   # (may need more - use ldd to find all)

   # Copy share directory
   cp -r mingw64/share/include-what-you-use bundle/share/
   ```

5. **Test locally BEFORE archiving** (Phase 2 requirements):
   ```bash
   cd bundle/bin
   ./include-what-you-use.exe --version
   # Must return exit code 0 or 1, NOT crash codes
   ```

### Alternative: Use wget to download from MSYS2 mirrors
If current environment has wget/curl, download packages directly without pacman.

### Why This Will Work:
- All binaries and DLLs from SAME source (MSYS2 packages)
- No ABI incompatibility (unlike previous attempt mixing MSYS2 binary + llvm-mingw DLLs)
- Can extract .pkg.tar.zst with standard tar (zstd support built-in)
- Testing before archiving ensures it works

See `.agent_task/ITERATION_1.md` for detailed findings.
