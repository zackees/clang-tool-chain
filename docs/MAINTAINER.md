# Maintainer Tools

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
