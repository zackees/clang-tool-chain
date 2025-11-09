# LLVM/Clang Toolchain Downloads

This directory contains pre-built LLVM/Clang toolchain archives.

## Quick Start

The archive creation tool is available as a package entry point after installing the package.

### Download and Create Archive

```bash
# First, install the package in development mode
pip install -e .

# Then use the entry point to create archives:

# Windows x86_64
uv run clang-tool-chain-fetch-archive --platform win --arch x86_64

# Linux x86_64
uv run clang-tool-chain-fetch-archive --platform linux --arch x86_64
uv run clang-tool-chain-fetch-archive --platform linux --arch arm64

# macOS ARM64 (Apple Silicon)
uv run clang-tool-chain-fetch-archive --platform darwin --arch arm64
uv run clang-tool-chain-fetch-archive --platform darwin --arch x86_64
```

### Use Existing Binaries

If you already have extracted LLVM binaries:

```bash
clang-tool-chain-fetch-archive \
    --platform win \
    --arch x86_64 \
    --source-dir ./assets/win
```

### Alternative: Direct Python Module Invocation

You can also run the tool directly as a Python module without installing:

```bash
# Run using uv
uv run python -m clang_tool_chain.downloads.fetch_and_archive --platform win --arch x86_64

# Or if using the virtual environment directly
python -m clang_tool_chain.downloads.fetch_and_archive --platform win --arch x86_64
```

## What The Script Does

The `fetch_and_archive.py` script automates the entire process:

### 1. **Download LLVM Binaries**
   - Fetches official LLVM release for specified platform/arch
   - Or uses existing binaries via `--source-dir`

### 2. **Extract Archive**
   - Handles `.exe` (Windows), `.tar.xz` (Linux/Mac)
   - Extracts to temporary working directory

### 3. **Strip Extras**
   - Keeps only essential build tools (compilers, linkers, binary utilities)
   - Removes documentation, examples, etc.
   - Essential binaries include:
     - Compilers: `clang`, `clang++`, `clang-cl`
     - Linkers: `lld-link`, `ld.lld`, `ld64.lld`, `lld`, `wasm-ld`
     - Tools: `llvm-ar`, `llvm-nm`, `llvm-objdump`, `llvm-strip`, etc.

### 4. **Deduplicate**
   - Analyzes binaries for duplicates (same MD5 hash)
   - Creates deduplication manifest
   - Identifies space savings

### 5. **Create Hard-Linked Structure**
   - Creates directory with hard links for duplicate binaries
   - TAR will automatically store these efficiently

### 6. **Create TAR Archive**
   - Uses tar's native hard link support
   - Stores duplicates as link entries (metadata only)

### 7. **Compress with ZSTD-22**
   - Ultra-compression with zstd level 22
   - Achieves ~94% reduction from original size
   - Fast decompression (~1 second)

### 8. **Generate Checksums**
   - Creates `.sha256` and `.md5` checksum files
   - For integrity verification

### 9. **Name and Place**
   - Names: `llvm-{version}-{platform}-{arch}.tar.zst`
   - Places in: `downloads/clang/{platform}/{arch}/`

## Usage Examples

### Basic Usage

```bash
# Create Windows x86_64 archive
clang-tool-chain-fetch-archive --platform win --arch x86_64

# Create Linux ARM64 archive
clang-tool-chain-fetch-archive --platform linux --arch arm64
```

### Advanced Options

```bash
# Specify LLVM version
clang-tool-chain-fetch-archive \
    --platform linux \
    --arch x86_64 \
    --version 21.1.5

# Custom output directory
clang-tool-chain-fetch-archive \
    --platform win \
    --arch x86_64 \
    --output-dir ./releases/win

# Keep intermediate files (for debugging)
clang-tool-chain-fetch-archive \
    --platform darwin \
    --arch arm64 \
    --keep-intermediate

# Faster compression (lower level)
clang-tool-chain-fetch-archive \
    --platform win \
    --arch x86_64 \
    --zstd-level 10
```

### Use Existing Binaries

```bash
# If you already have binaries extracted:
clang-tool-chain-fetch-archive \
    --platform win \
    --arch x86_64 \
    --source-dir ./assets/win

# This skips the download step
```

## Output

The script creates:

```
downloads/clang/{platform}/{arch}/
├── llvm-{version}-{platform}-{arch}.tar.zst       # Main archive
├── llvm-{version}-{platform}-{arch}.tar.zst.sha256 # SHA256 checksum
└── llvm-{version}-{platform}-{arch}.tar.zst.md5    # MD5 checksum
```

Example:
```
downloads/clang/win/x86_64/
├── llvm-21.1.5-win-x86_64.tar.zst        (51.53 MB)
├── llvm-21.1.5-win-x86_64.tar.zst.sha256
└── llvm-21.1.5-win-x86_64.tar.zst.md5
```

## Requirements

### Python Dependencies

```bash
pip install zstandard
```

### System Tools

- **For Windows archives:** 7-Zip (to extract .exe installers)
  - Download: https://www.7-zip.org/
  - Or use `--source-dir` with pre-extracted binaries

- **For Linux/Mac archives:** tar with xz support (usually pre-installed)

## Compression Results

Typical compression results:

| Original | Deduplicated | Compressed | Ratio | Reduction |
|----------|--------------|------------|-------|-----------|
| 902 MB | 289 MB | 51.53 MB | 5.6:1 | 94.3% |

### Size Breakdown

1. **Original:** ~900 MB (with duplicate binaries)
2. **After deduplication:** ~290 MB (unique binaries only)
3. **After compression:** ~52 MB (zstd-22)

## Supported Platforms

| Platform | Architecture | Status | URL Pattern |
|----------|--------------|--------|-------------|
| **Windows** | x86_64 | ✅ Tested | `LLVM-{version}-win64.exe` |
| **Windows** | arm64 | ⚠️ Untested | `LLVM-{version}-woa64.exe` |
| **Linux** | x86_64 | ⚠️ Untested | `clang+llvm-{version}-x86_64-linux-gnu-ubuntu-22.04.tar.xz` |
| **Linux** | arm64 | ⚠️ Untested | `clang+llvm-{version}-aarch64-linux-gnu.tar.xz` |
| **macOS** | x86_64 | ⚠️ Untested | `clang+llvm-{version}-x86_64-apple-darwin.tar.xz` |
| **macOS** | arm64 | ⚠️ Untested | `clang+llvm-{version}-arm64-apple-darwin22.0.tar.xz` |

## Extraction

To extract the created archive:

```bash
# Using the expansion script
python scripts/expand_archive.py \
    downloads/clang/win/x86_64/llvm-21.1.5-win-x86_64.tar.zst \
    ./install

# Or manually
zstd -d llvm-21.1.5-win-x86_64.tar.zst
tar -xf llvm-21.1.5-win-x86_64.tar
```

## Verification

```bash
# Verify SHA256
sha256sum -c llvm-21.1.5-win-x86_64.tar.zst.sha256

# Or manually
sha256sum llvm-21.1.5-win-x86_64.tar.zst
# Compare with .sha256 file
```

## Troubleshooting

### "7z is required to extract Windows .exe installer"

**Solution:** Install 7-Zip or use `--source-dir` with pre-extracted binaries:

```bash
# Option 1: Install 7-Zip
# Download from https://www.7-zip.org/

# Option 2: Use existing binaries
clang-tool-chain-fetch-archive \
    --platform win --arch x86_64 \
    --source-dir ./assets/win
```

### "zstandard module required"

**Solution:** Install the Python module (required dependency):

```bash
pip install zstandard
# Or with uv:
uv pip install zstandard
```

### "Unsupported platform/arch combination"

**Solution:** Check supported platforms above. Example:

```bash
# Correct:
clang-tool-chain-fetch-archive --platform win --arch x86_64

# Incorrect:
clang-tool-chain-fetch-archive --platform win --arch i386  # Not supported
```

### Hard links not working

The script will automatically fall back to copying if hard links fail. You'll see:

```
Hardlink: clang.exe -> clang++.exe
  (hard link failed, used copy)
```

This is fine - the archive will be slightly larger but still work.

## Advanced: Customizing Essential Binaries

Edit the `ESSENTIAL_BINARIES` set in `fetch_and_archive.py`:

```python
ESSENTIAL_BINARIES = {
    # Compilers
    "clang", "clang++",
    # Linkers
    "lld-link", "ld.lld",
    # Archive tools
    "llvm-ar",
    # Add more as needed
}
```

## Integration with Package Build

```python
# In your setup.py or pyproject.toml build script:
import subprocess

# Create archive during build
subprocess.run([
    'python', '-m', 'clang_tool_chain.downloads.fetch_and_archive',
    '--platform', 'win',
    '--arch', 'x86_64',
    '--source-dir', './assets/win'
])

# Archive will be in downloads/clang/win/x86_64/
```

## Performance

### Compression Time

- **zstd-22:** ~3-4 minutes (maximum compression)
- **zstd-10:** ~4 seconds (fast, still 3.3:1 ratio)
- **zstd-3:** ~1 second (very fast, 2.9:1 ratio)

### Decompression Time

- **Always fast:** ~1 second regardless of compression level

## Related Documentation

- `../HARDLINK_ARCHIVE_SOLUTION.md` - Technical details
- `../COMPRESSION_COMPARISON.md` - Compression analysis
- `../WINDOWS_HARDLINK_SUPPORT.md` - Platform compatibility
- `../scripts/expand_archive.py` - Archive extraction tool

## Current Archives

### Windows x86_64

- **File:** `llvm-21.1.5-win-x86_64.tar.zst`
- **Size:** 51.53 MB
- **SHA256:** `3c21e45edeee591fe8ead5427d25b62ddb26c409575b41db03d6777c77bba44f`
- **Status:** ✅ Tested and verified

See `win/` subdirectory for more details.
