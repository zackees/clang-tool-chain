# Maintainer Tools

<!-- AGENT: Read this file when packaging binaries, building archives, bundling DLLs for IWYU,
     or working on distribution infrastructure.
     Key topics: archive creation, zstd compression, hard-link deduplication, IWYU DLL bundling.
     Related: downloads-bins/CLAUDE.md, docs/ARCHITECTURE.md. -->

This document describes the tools and workflows for maintainers who package and distribute binary archives.

## Setup

Maintainer scripts for creating binary archives are located in the **submodule** at `downloads-bins/tools/`. This keeps the main repository lightweight and separates binary distribution tooling from the package code.

```bash
# Initialize the submodule (first time only)
git submodule init
git submodule update

# Navigate to tools directory
cd downloads-bins/tools
```

## Archive Creation Pipeline

The `fetch_and_archive.py` script automates the complete packaging process:

```bash
# Create optimized archive for Windows x86_64
cd downloads-bins/tools
python fetch_and_archive.py --platform win --arch x86_64

# Use existing binaries (skip download)
python fetch_and_archive.py --platform win --arch x86_64 --source-dir ./extracted
```

**What it does:**
1. Downloads LLVM from GitHub (or uses `--source-dir`)
2. Extracts archive
3. Strips unnecessary files (docs, examples, static libs)
4. Deduplicates identical binaries (~571 MB savings)
5. Creates hard-linked structure
6. Compresses with zstd level 22 (94.3% reduction)
7. Generates checksums (SHA256, MD5)
8. Names archive: `llvm-{version}-{platform}-{arch}.tar.zst`
9. Places in `../assets/clang/{platform}/{arch}/`

**Requirements:**
```bash
pip install zstandard
```

**Result:** 51.53 MB archive (from 902 MB original) for Windows x86_64

## Platform Upgrade History

### macOS x86_64 LLVM 21.x Upgrade

**Status:** ✅ Complete (January 7, 2026)

**Previous State:**
- **macOS x86_64:** LLVM 19.1.7 (did NOT support `-fuse-ld` flag)
- **macOS arm64:** LLVM 21.1.6
- **Windows/Linux:** LLVM 21.1.5 (all architectures)

**Current State:**
- **All platforms:** LLVM 21.x (macOS x86_64: 21.1.6, macOS ARM64: 21.1.6, Windows/Linux: 21.1.5)
- **Status:** Upgrade complete, all platforms now on LLVM 21.x

**Completed Actions:**
1. ✅ Built LLVM 21.1.6 for macOS x86_64 via GitHub Actions workflow
2. ✅ Uploaded `llvm-21.1.6-darwin-x86_64.tar.zst` (77 MB) to downloads-bins
3. ✅ Updated `manifest.json` with version 21.1.6 (set as latest)
4. ✅ Updated documentation (CLAUDE.md, MAINTAINER.md, version tables)

**Build Method:**
- **Automated GitHub Actions workflow:** `.github/workflows/build-llvm-macos-x86.yml`
- **Build time:** 8 minutes 8 seconds
- **Workflow run:** https://github.com/zackees/clang-tool-chain/actions/runs/20777997930
- **Archive SHA256:** `426e2b0f3a89bb7bc94cb3ff11c84ccf2fc032c29d0ef6d65286ae3e54cd3410`

**Benefits Achieved:**
- ✅ Consistent LLVM 21.x across all platforms
- ✅ Enables `-fuse-ld=lld` support on macOS (both architectures)
- ✅ Better GNU flag support on macOS
- ✅ Removed version inconsistency documentation warnings

**Updated Files:**
- `downloads-bins/assets/clang/darwin/x86_64/llvm-21.1.6-darwin-x86_64.tar.zst` (new)
- `downloads-bins/assets/clang/darwin/x86_64/manifest.json` (updated)
- `CLAUDE.md` (version tables updated)
- `docs/MAINTAINER.md` (this file - marked complete)

**Completed:** January 7, 2026 (Iteration 1)
**Tracking:** Identified in Iteration 9 (2026-01-07), completed in Iteration 1 of agent loop

## Individual Maintainer Scripts

Located in `downloads-bins/tools/`:

- `fetch_and_archive.py`: Complete pipeline for LLVM toolchain archives
- `extract_mingw_sysroot.py`: Extract MinGW-w64 sysroot for Windows GNU ABI
- `download_binaries.py`: Download LLVM releases from GitHub
- `strip_binaries.py`: Remove unnecessary files to optimize size
- `deduplicate_binaries.py`: Identify duplicate binaries by MD5 hash
- `create_hardlink_archive.py`: Create hard-linked TAR archives
- `expand_archive.py`: Extract `.tar.zst` archives
- `test_compression.py`: Compare compression methods
- `create_iwyu_archives.py`: Create include-what-you-use archives

See `downloads-bins/tools/README.md` for detailed documentation.

## MinGW Sysroot Generation (Windows GNU ABI)

The `extract_mingw_sysroot.py` script creates MinGW-w64 sysroot archives:

```bash
# Generate MinGW sysroot archive for Windows x86_64
cd downloads-bins/tools
python extract_mingw_sysroot.py --arch x86_64 --work-dir work
```

**What it does:**
1. Downloads LLVM-MinGW release from GitHub (mstorsjo/llvm-mingw)
2. Extracts only the sysroot directory (x86_64-w64-mingw32)
3. Includes C/C++ standard library headers (libc++ from LLVM)
4. Compresses with zstd level 22 (~93% reduction)
5. Generates checksums (SHA256, MD5)
6. Creates manifest.json
7. Names archive: `mingw-sysroot-{version}-win-{arch}.tar.zst`
8. Places in `../assets/mingw/win/{arch}/`

**Result:** ~12 MB archive (from 176 MB uncompressed) for Windows x86_64

## LLDB Archive Generation

### Windows LLDB Archive Build Workflow

An automated GitHub Actions workflow is available for building Windows LLDB archives with Python 3.10 support:

**Workflow:** `.github/workflows/build-lldb-archives-windows.yml`

**Purpose:**
- Automates Windows LLDB archive creation with python310.dll bundled
- Based on proven Linux workflow template
- Handles Windows-specific requirements (7-Zip, PowerShell, .exe extraction)
- Supports both x86_64 and ARM64 architectures

**How to Execute:**
1. Navigate to GitHub → Actions → "Build LLDB Archives (Windows)"
2. Click "Run workflow"
3. Configure parameters (optional):
   - LLVM version (default: 21.1.5)
   - Architectures (default: x86_64)
4. Wait ~60-90 minutes for build to complete
5. Download artifacts from workflow run:
   - `lldb-windows-x86_64.tar.zst` (~35 MB compressed)
   - `lldb-windows-x86_64.tar.zst.sha256` (checksum file)

**What the Workflow Does:**
1. Downloads LLVM release from GitHub
2. Extracts LLDB binaries (lldb.exe, lldb-server.exe, liblldb.dll)
3. Downloads Python embeddable package (python-3.10.11-embed-amd64.zip)
4. Extracts python310.dll and python310.zip
5. Packages Python modules (LLDB Python API + site-packages)
6. Creates archive structure:
   ```
   lldb-windows-x86_64/
   ├── bin/
   │   ├── lldb.exe
   │   ├── lldb-server.exe
   │   ├── lldb-argdumper.exe
   │   ├── liblldb.dll
   │   └── python310.dll          # ← Critical for Python support
   ├── python/
   │   ├── python310.dll           # ← Backup copy
   │   ├── python310.zip           # ← Standard library
   │   └── Lib/
   │       └── site-packages/
   │           └── lldb/           # ← LLDB Python module
   └── lib/
       └── liblldb.dll
   ```
7. Compresses with zstd level 22
8. Generates SHA256 checksum
9. Uploads artifacts (30-day retention)

**Expected Archive Size:**
- Compressed: ~35 MB (+5 MB from current ~30 MB)
- Uncompressed: ~209 MB

**After Workflow Completion:**
1. Download artifacts from GitHub Actions
2. Test locally:
   ```bash
   # Extract to test directory
   tar --use-compress-program=unzstd -xf lldb-windows-x86_64.tar.zst

   # Verify python310.dll exists
   ls lldb-windows-x86_64/bin/python310.dll
   ls lldb-windows-x86_64/python/python310.dll

   # Test LLDB launch
   ./lldb-windows-x86_64/bin/lldb.exe --version
   # Should work without DLL errors
   ```
3. Upload to downloads-bins repository:
   ```bash
   cd downloads-bins/assets/lldb/windows/x86_64/
   cp ~/Downloads/lldb-windows-x86_64.tar.zst .
   ```
4. Update manifest with new SHA256:
   ```bash
   # Get SHA256 from downloaded .sha256 file
   cat ~/Downloads/lldb-windows-x86_64.tar.zst.sha256

   # Update downloads-bins/assets/lldb/windows/x86_64/manifest.json
   # Replace sha256 field with new checksum
   ```
5. Commit and push:
   ```bash
   git add lldb-windows-x86_64.tar.zst manifest.json
   git commit -m "Update Windows LLDB archive with python310.dll (v21.1.5)"
   git push origin main

   # Update submodule reference in main repo
   cd ~/dev/clang-tool-chain
   git add downloads-bins
   git commit -m "chore: Update downloads-bins with LLDB python310.dll fix"
   git push origin main
   ```

**Verification After Deployment:**
```bash
# Remove old installation
clang-tool-chain purge --yes

# Install fresh
clang-tool-chain install lldb

# Check Python environment
clang-tool-chain-lldb-check-python
# Should show: "Status: READY"

# Test LLDB
clang-tool-chain-lldb --version
# Should work without DLL errors

# Run tests
uv run pytest tests/test_lldb.py -v
# All 4 tests should pass
```

**Documentation:**
- Complete workflow documentation: [Iteration 5](.agent_task/ITERATION_5.md)
- Troubleshooting: [LLDB.md](LLDB.md#troubleshooting)
- Linux workflow (similar): `.github/workflows/build-lldb-archives-linux.yml`

### Linux LLDB Archive Build Workflow

A similar automated workflow exists for Linux LLDB archives:

**Workflow:** `.github/workflows/build-lldb-archives-linux.yml`

**Status:** Ready for execution, archives pending

**Differences from Windows:**
- Uses `tar` instead of 7-Zip
- Extracts Python from Debian Jammy packages
- Creates symlinks instead of copying binaries
- Smaller archive size (~10-11 MB vs ~35 MB)

See workflow file for complete documentation.

## Updating Binary Payloads

Binary archives are stored in a separate repository as a git submodule to keep the main repository lightweight. This architecture reduces main repo clone size from ~450 MB to ~20 MB.

**First-time setup (for maintainers):**
```bash
# Initialize and update the submodule
git submodule init
git submodule update
```

**Adding new binaries:**
```bash
# Navigate to the submodule directory
cd downloads-bins

# Add new archive to appropriate location
# Example: cp new-binary.tar.zst clang/win/x86_64/

# Update the manifest.json with new version info
# Edit clang/win/x86_64/manifest.json to add:
# - version number
# - href URL (pointing to clang-tool-chain-bins repo)
# - sha256 checksum

# Commit and push to the bins repository
git add .
git commit -m "Add LLVM version X.Y.Z for win/x86_64"
git push origin main

# Return to main repository
cd ..

# Update the submodule reference in main repo
git add downloads-bins
git commit -m "Update submodule to latest binaries (version X.Y.Z)"
git push origin main
```

**Binary URL pattern:**
```
https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/{platform}/{arch}/llvm-{version}-{platform}-{arch}.tar.zst
```

**Important notes:**
- End users do NOT need the submodule - binaries are downloaded automatically from GitHub
- The submodule is only needed for maintainers who update binary distributions
- Manifest URLs in the bins repository must point to `clang-tool-chain-bins`, not `clang-tool-chain`
- Always update SHA256 checksums when adding new binaries

## Troubleshooting Binary Dependencies (DLLs and .so files)

### Missing DLL/Shared Library Issues

If binaries in the distributed archives fail with errors like "command not found" (exit code 127) or access violations (0xC0000005), they may be missing DLL/.so file dependencies.

**Diagnostic Steps:**

1. **Check for missing dependencies** (Linux/MSYS2):
   ```bash
   ldd path/to/binary
   # Look for "=> not found" entries
   ```

2. **Check for missing dependencies** (Windows cmd):
   ```cmd
   dumpbin /dependents path\to\binary.exe
   ```

3. **Check for missing dependencies** (macOS):
   ```bash
   otool -L path/to/binary
   # Look for libraries not found in standard paths
   ```

### Repacking Archives with Missing Dependencies

If you identify missing DLLs or .so files:

1. **Locate the required dependencies**:
   - For LLVM/Clang tools: Download from llvm-mingw, official LLVM releases, or system package managers
   - Verify version compatibility (same LLVM major version)
   - Example for LLVM 21.x on Windows:
     ```bash
     # Download llvm-mingw distribution
     wget https://github.com/mstorsjo/llvm-mingw/releases/download/20251104/llvm-mingw-20251104-msvcrt-x86_64.zip
     unzip llvm-mingw-*.zip

     # Find required DLLs
     find llvm-mingw-* -name "libLLVM-21.dll" -o -name "libclang-cpp.dll"
     ```

2. **Extract the current archive**:
   ```bash
   cd /tmp/repack_work
   python ~/dev/clang-tool-chain/downloads-bins/tools/expand_archive.py \
     ~/dev/clang-tool-chain/downloads-bins/assets/{tool}/{platform}/{arch}/{archive}.tar.zst \
     extracted/
   ```

3. **Add missing dependencies**:
   ```bash
   # Copy DLLs/.so files to the bin directory
   cp path/to/required/*.dll extracted/bin/

   # Verify all dependencies are resolved
   ldd extracted/bin/your-binary.exe  # Should show no "not found" entries
   ```

4. **Test the binary with dependencies**:
   ```bash
   cd extracted/bin
   ./your-binary.exe --version  # Should not crash
   ```

5. **Repackage the archive**:
   ```python
   # Create tar archive
   import tarfile
   from pathlib import Path

   def tar_filter(tarinfo):
       if tarinfo.isfile() and ('/bin/' in tarinfo.name or tarinfo.name.startswith('bin/')):
           if tarinfo.name.endswith(('.py', '.exe', '.dll', '.so')):
               tarinfo.mode = 0o755  # Executable
           else:
               tarinfo.mode = 0o644  # Readable
       return tarinfo

   with tarfile.open('new-archive.tar', 'w') as tar:
       tar.add('extracted/bin', arcname='bin', filter=tar_filter)
       tar.add('extracted/share', arcname='share', filter=tar_filter)
   ```

6. **Compress with zstd**:
   ```python
   import zstandard as zstd

   cctx = zstd.ZstdCompressor(level=22, threads=-1)
   with open('new-archive.tar', 'rb') as ifh, open('new-archive.tar.zst', 'wb') as ofh:
       reader = cctx.stream_reader(ifh, size=Path('new-archive.tar').stat().st_size)
       while True:
           chunk = reader.read(1024 * 1024)
           if not chunk:
               break
           ofh.write(chunk)
   ```

7. **Generate checksum and update manifest**:
   ```python
   import hashlib

   sha256_hash = hashlib.sha256()
   with open('new-archive.tar.zst', 'rb') as f:
       for byte_block in iter(lambda: f.read(4096), b''):
           sha256_hash.update(byte_block)

   checksum = sha256_hash.hexdigest()
   print(f'SHA256: {checksum}')

   # Update downloads-bins/assets/{tool}/{platform}/{arch}/manifest.json
   # Replace the sha256 field with the new checksum
   ```

8. **Test the new archive**:
   ```bash
   # Remove old installation
   rm -rf ~/.clang-tool-chain/{tool}/

   # Copy new archive to downloads-bins location
   cp new-archive.tar.zst ~/dev/clang-tool-chain/downloads-bins/assets/{tool}/{platform}/{arch}/

   # Run tests to verify
   uv run pytest tests/test_{tool}.py -v
   ```

### Important Caveats

⚠️ **Binary Compatibility Warning**: Adding DLLs from different sources can cause compatibility issues:

- **Version mismatches**: DLLs must match the LLVM version used to build the binary
- **Compiler differences**: Binaries built with GCC may not work with MSVC-compiled DLLs
- **ABI incompatibilities**: Different C++ standard library implementations (libc++ vs libstdc++ vs MSVC STL)
- **Runtime errors**: May crash with BAD_INITIAL_STACK (0xC0000009) or other memory errors

**If bundling DLLs fails**, consider these alternatives:

1. **Rebuild from source with static linking** (recommended for long-term stability):
   - Download tool source code
   - Build against LLVM with `-static` linker flags
   - Results in larger binary but no external dependencies
   - Example CMake flags: `-DCMAKE_EXE_LINKER_FLAGS="-static-libgcc -static-libstdc++ -static"`

2. **Use system package managers**:
   - Document that users need to install LLVM/Clang development packages
   - MSYS2: `pacman -S mingw-w64-x86_64-llvm`
   - Debian/Ubuntu: `apt install llvm-dev libclang-dev`
   - macOS: `brew install llvm`

3. **Skip functionality on affected platforms**:
   - Add `@pytest.mark.skipif` decorators for platform-specific tests
   - Document limitation in README and error messages
   - Provide workarounds (WSL, Docker, alternative tools)

**See Also:**
- `IWYU_FIX_RECOMMENDATION.md` - Case study of IWYU Windows DLL bundling attempt and lessons learned
- `downloads-bins/tools/README.md` - Maintainer tools documentation
- `downloads-bins/tools/expand_archive.py` - Archive extraction tool
- `downloads-bins/tools/create_iwyu_archives.py` - Example archive creation script
