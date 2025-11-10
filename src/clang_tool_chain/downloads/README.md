# Scripts Directory

This directory contains utility scripts for downloading and processing LLVM/Clang binaries.

## Scripts

### download_binaries.py

Downloads pre-built LLVM/Clang binaries from official GitHub releases.

**Usage:**
```bash
# Download binaries for current platform only
python scripts/download_binaries.py --current-only

# Download binaries for all platforms
python scripts/download_binaries.py

# Download specific platform
python scripts/download_binaries.py --platform linux-x86_64

# Specify version and output directory
python scripts/download_binaries.py --version 21.1.5 --output work
```

**Supported Platforms:**
- `win-x86_64` - Windows 64-bit
- `linux-x86_64` - Linux x86-64
- `linux-aarch64` - Linux ARM64
- `darwin-x86_64` - macOS Intel
- `darwin-arm64` - macOS Apple Silicon

**Output:**
Downloads are saved to the `work/` directory by default. Each platform is extracted to a separate subdirectory.

### strip_binaries.py

Optimizes downloaded LLVM distributions by removing unnecessary files and stripping debug symbols.

**Usage:**
```bash
# Strip binaries for a specific platform
python scripts/strip_binaries.py \
  work/linux-x86_64-extracted \
  downloads-bins/assets/clang/linux/x86_64 \
  --platform linux-x86_64

# Keep header files (not recommended, increases size)
python scripts/strip_binaries.py <source> <output> --platform <platform> --keep-headers

# Skip binary stripping (debug symbols)
python scripts/strip_binaries.py <source> <output> --platform <platform> --no-strip

# Verbose output
python scripts/strip_binaries.py <source> <output> --platform <platform> --verbose
```

**What it removes:**
- Documentation (share/doc, share/man)
- Static libraries (*.a, *.lib)
- CMake files
- Python bindings
- Examples and unnecessary tools
- Debug symbols from binaries

**What it keeps:**
- Essential binaries (clang, clang++, lld, llvm-ar, etc.)
- Runtime libraries (lib/clang/*, *.so, *.dll, *.dylib)
- License files

**Expected Size Reduction:**
- Original: ~3.5 GB per platform
- After stripping: ~300-400 MB per platform
- Reduction: ~85-90%

## Workflow

Complete workflow to prepare binaries for the package:

```bash
# 1. Download binaries for current platform
python scripts/download_binaries.py --current-only

# 2. Find the extracted directory (example for Windows)
# It will be something like: work/win-x86_64-extracted/

# 3. Strip the binaries and move to assets
python scripts/strip_binaries.py \
  work/win-x86_64-extracted \
  downloads-bins/assets/clang/win/x86_64 \
  --platform win-x86_64 \
  --verbose

# 4. Verify the output
ls -lh downloads-bins/assets/clang/win/x86_64/bin/
```

## Platform-Specific Notes

### Windows
- May require 7-Zip installed for installer extraction
- Alternative: Use the .tar.xz archive instead of .exe installer

### macOS
- Official binaries may not always be available for all versions
- May need to use Homebrew or community builds as alternatives
- Separate binaries needed for Intel (x86_64) and Apple Silicon (arm64)

### Linux
- Most reliable platform for official binaries
- Minimal dependencies required (glibc, libstdc++)
- Both x86_64 and aarch64 architectures available

## Troubleshooting

**Download fails with 404 error:**
- Check if the specified version exists on GitHub releases
- Try the alternative URL (script will attempt automatically)
- Verify version format (e.g., "21.1.5" not "21.1")

**Extraction fails on Windows:**
- Install 7-Zip: https://www.7-zip.org/
- Add 7z.exe to your PATH
- Or manually extract the installer and provide extracted path to strip script

**Strip script fails:**
- Verify the source directory contains a valid LLVM installation
- Check that bin/ directory exists in source
- Use --verbose flag to see detailed error messages

## Requirements

- Python 3.10+
- Internet connection (for download_binaries.py)
- ~4-5 GB free disk space per platform (temporary)
- 7-Zip (Windows only, for .exe extraction)

## Security Note

Always verify downloads are from official LLVM GitHub releases:
- Primary: https://github.com/llvm/llvm-project/releases
- Mirror: https://releases.llvm.org/

The download script only uses these official sources.
