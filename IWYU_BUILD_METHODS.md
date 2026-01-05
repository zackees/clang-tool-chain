# IWYU Build Methods for macOS

This document compares two methods for creating IWYU distribution archives for macOS.

## Quick Comparison

| Aspect | Homebrew Extraction | Build from Source |
|--------|---------------------|-------------------|
| **Speed** | ⚡ 3-5 minutes | 🐌 15-20 minutes |
| **Cost** | 💰 ~$0.08-0.16 | 💰💰 ~$0.16-0.32 |
| **Complexity** | ✅ Simple | ⚠️ Complex |
| **Linking** | 🔗 Dynamic + bundled dylibs | 🔗 Static or dynamic |
| **Binary Size** | 📦 ~5 MB + ~50 MB dylibs | 📦 ~80-150 MB |
| **Archive Size** | 📦 ~20-30 MB | 📦 ~15-25 MB |
| **Reliability** | ✅ High (pre-built) | ⚠️ Build failures possible |
| **Recommendation** | ✅ **Preferred** | Use if Homebrew fails |

## Method 1: Homebrew Extraction (Recommended)

### Overview

Extract pre-built IWYU binaries from Homebrew and bundle required LLVM dylibs.

### Advantages

- ⚡ **Fast**: 3-5 minutes (vs 15-20 for building)
- 💰 **Cheap**: 50% less GitHub Actions cost
- ✅ **Reliable**: Uses Homebrew's tested binaries
- 🔄 **Updated**: Gets latest Homebrew IWYU automatically
- 🛠️ **Simple**: No CMake, no compile errors

### How It Works

1. Install `include-what-you-use` via Homebrew
2. Extract binary and support files
3. Copy required LLVM dylibs from Homebrew LLVM
4. Fix install names using `install_name_tool` to use `@executable_path`
5. Create archive with binary + dylibs

### Usage

#### Command Line:
```bash
cd downloads-bins/tools

# Extract for ARM64 (M1/M2/M3 Mac)
python3 extract_iwyu_from_homebrew.py --arch arm64

# Extract for x86_64 (Intel Mac)
python3 extract_iwyu_from_homebrew.py --arch x86_64
```

#### GitHub Actions:
```bash
# Trigger the workflow from GitHub UI
# Or via gh CLI:
gh workflow run build-iwyu-macos-homebrew.yml
```

### What Gets Bundled

**Binary:**
- `bin/include-what-you-use` (~5 MB)
- `bin/iwyu_tool.py`
- `bin/fix_includes.py`

**LLVM Dylibs:** (~50 MB total)
- `lib/libLLVM.dylib` or `lib/libLLVM-*.dylib`
- `lib/libclang-cpp.dylib`
- Any other required LLVM component libraries

**Support Files:**
- `share/include-what-you-use/*.imp` (mapping files)

**Install Names Fixed:**
```bash
# Before:
/opt/homebrew/opt/llvm/lib/libLLVM.dylib

# After:
@executable_path/../lib/libLLVM.dylib
```

This makes dylibs load relative to the binary location.

### Verification

```bash
# Check dependencies
otool -L downloads-bins/assets/iwyu/darwin/arm64/bin/include-what-you-use

# Should show:
# @executable_path/../lib/libLLVM.dylib
# @executable_path/../lib/libclang-cpp.dylib
# /usr/lib/libc++.1.dylib
# /usr/lib/libSystem.B.dylib

# Test the binary
./downloads-bins/assets/iwyu/darwin/arm64/bin/include-what-you-use --version
```

### When to Use

✅ **Use Homebrew extraction when:**
- You want fast builds
- You want reliable, tested binaries
- You're okay with bundling dylibs (~20-30 MB archive)
- You trust Homebrew's build quality

## Method 2: Build from Source with Static Linking

### Overview

Build IWYU from source against Homebrew LLVM with static linking.

### Advantages

- 📦 **Smaller archives**: ~15-25 MB (vs ~20-30 MB)
- 🔒 **Self-contained**: No bundled dylibs
- 🎯 **Control**: Full control over build flags
- ⚙️ **Customizable**: Can apply patches if needed

### Disadvantages

- 🐌 **Slow**: 15-20 minutes per arch
- 💰 **Expensive**: 2x GitHub Actions cost
- ⚠️ **Complex**: CMake, compiler flags, build failures
- 🔧 **Maintenance**: Need to update build scripts

### How It Works

1. Install LLVM via Homebrew (for headers and libraries)
2. Download IWYU source from GitHub
3. Configure CMake with static linking flags:
   - `-DCMAKE_FIND_LIBRARY_SUFFIXES=.a;.dylib`
   - `-DLLVM_LINK_LLVM_DYLIB=OFF`
   - `-DBUILD_SHARED_LIBS=OFF`
4. Build IWYU with `make`
5. Strip debug symbols
6. Create archive

### Usage

#### Command Line:
```bash
cd downloads-bins/tools

# Build for ARM64
python3 build_iwyu_macos.py --arch arm64 --static

# Build for x86_64
python3 build_iwyu_macos.py --arch x86_64 --static
```

#### GitHub Actions:
```bash
# Trigger the original build workflow
gh workflow run build-iwyu-macos.yml
```

### When to Use

✅ **Use source build when:**
- Homebrew IWYU is broken or outdated
- You need specific build flags or patches
- You want the smallest possible archive size
- You need to debug IWYU itself

❌ **Don't use when:**
- You want fast iteration
- You want to minimize CI costs
- You don't need custom build configuration

## Recommended Workflow

### For Production Releases

**Use Homebrew Extraction:**
1. Fast and reliable
2. Tested by Homebrew community
3. Lower cost for frequent builds

### For Development/Testing

**Either method works:**
- Homebrew for quick iterations
- Source build if testing patches

### For Troubleshooting

**Start with Homebrew, fall back to source:**
1. Try Homebrew extraction first
2. If it fails, try source build
3. Report issues upstream (Homebrew or IWYU)

## Implementation Files

### Homebrew Method
- **Script**: `downloads-bins/tools/extract_iwyu_from_homebrew.py`
- **Workflow**: `.github/workflows/build-iwyu-macos-homebrew.yml`
- **Runtime**: ~5-8 minutes total (both arches in parallel)

### Source Build Method
- **Script**: `downloads-bins/tools/build_iwyu_macos.py`
- **Workflow**: `.github/workflows/build-iwyu-macos.yml`
- **Runtime**: ~15-20 minutes total (both arches in parallel)

### Archive Creation (Both Methods)
- **Script**: `downloads-bins/tools/create_iwyu_archives.py`
- **Output**: `.tar.zst` archives with SHA256 checksums

## Testing Both Methods

### Quick Test (Homebrew)
```bash
cd downloads-bins/tools

# Extract and test
time python3 extract_iwyu_from_homebrew.py --arch arm64
downloads-bins/assets/iwyu/darwin/arm64/bin/include-what-you-use --version

# Should complete in ~2-3 minutes
```

### Full Test (Source Build)
```bash
cd downloads-bins/tools

# Build and test
time python3 build_iwyu_macos.py --arch arm64 --static
downloads-bins/assets/iwyu/darwin/arm64/bin/include-what-you-use --version

# Should complete in ~8-12 minutes
```

## Archive Size Comparison

### Homebrew Method
```
Uncompressed:
- Binary: ~5 MB
- LLVM dylibs: ~50 MB
- Support files: ~1 MB
- Total: ~56 MB

Compressed (zstd-22):
- Archive: ~20-30 MB
- Compression ratio: ~2:1
```

### Source Build (Static)
```
Uncompressed:
- Binary: ~120 MB
- Support files: ~1 MB
- Total: ~121 MB

Compressed (zstd-22):
- Archive: ~15-25 MB
- Compression ratio: ~6:1
```

**Note:** Static binaries compress better due to LLVM's repetitive code patterns.

## Troubleshooting

### Homebrew Method Issues

**Problem:** `brew install include-what-you-use` fails
```bash
# Update Homebrew
brew update

# Try again
brew install include-what-you-use

# If still fails, check formula
brew info include-what-you-use
```

**Problem:** Missing LLVM dylibs
```bash
# Check LLVM installation
brew list llvm | grep dylib

# Reinstall if needed
brew reinstall llvm
```

**Problem:** Binary crashes with "Symbol not found"
```bash
# Check install names were fixed
otool -L bin/include-what-you-use

# Should show @executable_path, not /opt/homebrew paths
```

### Source Build Issues

**Problem:** CMake can't find LLVM
```bash
# Verify LLVM path
ls $(brew --prefix llvm)/lib/cmake/llvm

# Try with explicit path
cmake -DCMAKE_PREFIX_PATH=$(brew --prefix llvm) ..
```

**Problem:** Binary has dynamic LLVM dependencies
```bash
# Check dependencies
otool -L bin/include-what-you-use

# If you see @rpath/libLLVM.dylib, static linking failed
# Try rebuilding with --static flag explicitly
```

## Recommendations

### Default Choice: Homebrew Extraction ✅

The Homebrew extraction method should be the **default** for these reasons:

1. **Speed**: 3x faster than building from source
2. **Cost**: 50% cheaper in CI
3. **Reliability**: Homebrew tests their builds extensively
4. **Maintenance**: No build script maintenance
5. **Updates**: Automatically gets Homebrew updates

### When to Use Source Build

Use source build **only** when:
- Homebrew method fails or is unavailable
- You need bleeding-edge IWYU version
- You need custom patches or build flags
- You're debugging IWYU itself

## Migration Guide

### From Old (Source Build) to New (Homebrew)

1. Update workflows to use `build-iwyu-macos-homebrew.yml`
2. Update documentation to reference Homebrew method
3. Keep source build method as fallback
4. Test both archives to ensure compatibility

### Backwards Compatibility

Both methods produce compatible archives:
- Same directory structure (`bin/`, `lib/`, `share/`)
- Same binary name (`include-what-you-use`)
- Same support files (`.imp` mapping files)
- Same manifest format

Users won't see any difference in functionality.

## Future Improvements

### Homebrew Method
- [ ] Auto-detect and copy only required dylibs (reduce size)
- [ ] Support for universal binaries (x86_64 + arm64 in one)
- [ ] Verify binary signatures

### Source Build Method
- [ ] Implement proper static linking (no dylib dependencies)
- [ ] Cross-compilation support
- [ ] LTO (Link-Time Optimization) for smaller binaries

## Conclusion

**Use Homebrew extraction** for production builds. It's faster, cheaper, and more reliable.

Keep the source build method as a fallback option for edge cases.

---

**Last Updated**: 2026-01-05
**Maintainer**: See MAINTAINER.md
**Issues**: https://github.com/zackees/clang-tool-chain/issues
