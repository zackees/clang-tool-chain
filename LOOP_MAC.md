# Investigation: Node.js Version for macOS (Emscripten)

## Executive Summary

**Node.js 22.11.0 LTS ("Jod")** is the configured version for macOS and all other platforms in this project.

## Key Findings

### Version Information

- **Node.js Version:** 22.11.0 LTS
- **Codename:** "Jod"
- **Support Timeline:** Until 2027-04-30
- **Emscripten Version:** 4.0.15

### macOS Platform Coverage

Both macOS architectures use Node.js 22.11.0:
- **macOS x86_64** (Intel)
- **macOS ARM64** (Apple Silicon)

### Configuration Location

The Node.js version is centrally defined in:
- **File:** `downloads-bins/tools/fetch_and_archive_nodejs.py`
- **Line:** 48
- **Code:** `NODEJS_VERSION = "22.11.0"`

### Manifest Files

macOS manifests confirm version 22.11.0:
- `downloads-bins/assets/nodejs/darwin/x86_64/manifest.json` (line 2)
- `downloads-bins/assets/nodejs/darwin/arm64/manifest.json` (line 2)

### Documentation References

- **docs/NODEJS.md** (lines 32-36): Lists all supported platforms with version 22.11.0
- **docs/NODEJS.md** (lines 108-111): Version information and support timeline
- **docs/EMSCRIPTEN.md** (lines 109-111): Emscripten version 4.0.15

## Current State Analysis

### What We Have

1. **Windows binaries:** Node.js 22.11.0 bundled and ready
2. **macOS manifests:** Present and pointing to version 22.11.0 for both architectures
3. **Configuration:** Unified version across all platforms

### What's Missing for macOS

Based on the investigation, the infrastructure appears to be in place for macOS Node.js binaries (manifests exist for both Intel and Apple Silicon), but the binaries themselves may not be present or properly packaged.

### Binary Size Information

From documentation:
- Compressed size: ~23-24 MB per platform (using zstd level 22)
- Uncompressed size: ~90-100 MB

## Architecture-Specific Notes

### macOS x86_64 (Intel)
- Traditional Intel-based Macs
- Uses darwin/x86_64 platform identifier
- Node.js native binary for x86_64

### macOS ARM64 (Apple Silicon)
- M1, M2, M3, M4 series processors
- Uses darwin/arm64 platform identifier
- Node.js native binary for ARM64
- Better performance and efficiency on Apple Silicon

## Recommendation

**Use Node.js 22.11.0 LTS for macOS (both architectures)** as it:
1. Matches the existing Windows and Linux configuration
2. Is already configured in the build system
3. Is an LTS release with support until 2027
4. Is compatible with Emscripten 4.0.15
5. Has manifest files already created for both macOS architectures
6. Provides native performance on both Intel and Apple Silicon

## Next Steps (If Building Binaries)

1. Use the existing `fetch_and_archive_nodejs.py` script
2. Ensure both macOS platforms (x86_64 and arm64) are processed
3. Verify checksums in manifest files match downloaded binaries
4. Test with Emscripten 4.0.15 on macOS
5. Test on both Intel and Apple Silicon hardware if possible

## macOS-Specific Considerations

### Code Signing
- macOS binaries may require code signing for Gatekeeper
- Consider notarization for distribution
- May need to handle quarantine attributes

### Rosetta 2
- x86_64 binaries can run on ARM64 via Rosetta 2
- Native ARM64 binaries provide better performance
- Both architectures should be provided for optimal user experience

### SDK Dependencies
- Node.js may have dependencies on macOS SDK version
- Current project uses macOS SDK detection (see docs/CLANG_LLVM.md)
- Ensure Node.js binaries are compatible with supported macOS versions

## Investigation Methodology

This investigation used the Explore agent to:
1. Search for Node.js version configuration files
2. Review Emscripten documentation
3. Examine manifest files across all platforms
4. Cross-reference documentation files (NODEJS.md, EMSCRIPTEN.md)
5. Verify consistency across platform-specific configurations
6. Identify macOS-specific architecture requirements

**Investigation Date:** 2025-11-11
