# IWYU Build Quick Start (macOS ARM64)

## Prerequisites

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install LLVM
brew install llvm
```

## Build IWYU (Static Linking)

```bash
cd downloads-bins/tools

# Build for ARM64 (M1/M2/M3 Mac)
python3 build_iwyu_macos.py --arch arm64

# Build output will be in:
# downloads-bins/assets/iwyu/darwin/arm64/bin/include-what-you-use
```

## Verify the Build

```bash
cd downloads-bins/assets/iwyu/darwin/arm64

# Check dependencies (should only see system libs)
otool -L bin/include-what-you-use

# Test the binary
./bin/include-what-you-use --version

# Expected output:
# include-what-you-use 0.25 based on clang version 21.1.6
```

## Create Archive

```bash
cd downloads-bins/tools

# Create compressed archive
python3 create_iwyu_archives.py --platform darwin --arch arm64 --version 0.25

# Output will be:
# downloads-bins/assets/iwyu/darwin/arm64/iwyu-0.25-darwin-arm64.tar.zst
# downloads-bins/assets/iwyu/darwin/arm64/iwyu-0.25-darwin-arm64.tar.zst.sha256
```

## Update Manifest

```bash
# Copy the SHA256 hash
cat downloads-bins/assets/iwyu/darwin/arm64/iwyu-0.25-darwin-arm64.tar.zst.sha256

# Edit the manifest
nano downloads-bins/assets/iwyu/darwin/arm64/manifest.json

# Update the sha256 field with the new hash
```

## Upload to GitHub

```bash
cd downloads-bins

# Commit and push
git add assets/iwyu/darwin/arm64/
git commit -m "fix(iwyu): Rebuild macOS ARM64 with static linking"
git lfs push origin main
git push origin main
```

## Test in CI

Watch GitHub Actions:
- https://github.com/zackees/clang-tool-chain/actions/workflows/test-iwyu-macos-arm.yml

Expected: All 4 tests should pass ✅

## Troubleshooting

### "No static libraries found"
```bash
# Check Homebrew LLVM
ls -la $(brew --prefix llvm)/lib/*.a

# If no .a files, reinstall LLVM
brew uninstall llvm
brew install llvm
```

### "Binary has LLVM dependencies"
```bash
# Check the dependencies
otool -L bin/include-what-you-use

# If you see @rpath/libLLVM.dylib, static linking failed
# Try adding --static flag explicitly:
python3 build_iwyu_macos.py --arch arm64 --static
```

### "Symbol not found" when running binary
```bash
# This means dynamic linking was used
# Rebuild with static linking:
rm -rf work_iwyu/
python3 build_iwyu_macos.py --arch arm64 --static
```

## Build Times

- Download source: ~5 seconds
- Extract: ~2 seconds
- CMake configure: ~10 seconds
- Build (make -j): ~2-5 minutes
- Strip: <1 second
- Create archive: ~1-2 minutes (zstd level 22)

**Total:** ~5-10 minutes per architecture

## File Sizes

- Source tarball: ~1.5 MB
- Binary (unstripped): ~150-200 MB
- Binary (stripped): ~80-120 MB
- Archive (zstd-22): ~15-25 MB

## Next Architecture

To build for x86_64 (Intel Mac):
```bash
# Run on Intel Mac, or in x86_64 CI environment
python3 build_iwyu_macos.py --arch x86_64 --static
python3 create_iwyu_archives.py --platform darwin --arch x86_64 --version 0.25
```

---

For detailed information, see:
- `BUILD_IWYU_MACOS_STATIC.md` - Comprehensive technical guide
- `IWYU_MACOS_FIX_SUMMARY.md` - Problem analysis and solution summary
