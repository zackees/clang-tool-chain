# Investigation: Node.js Version for Linux (Emscripten)

## Executive Summary

**Node.js 22.11.0 LTS ("Jod")** is the configured version for Linux and all other platforms in this project.

## Key Findings

### Version Information

- **Node.js Version:** 22.11.0 LTS
- **Codename:** "Jod"
- **Support Timeline:** Until 2027-04-30
- **Emscripten Version:** 4.0.15

### Platform Coverage

All platforms use the same Node.js version (22.11.0):
- Windows x86_64
- Linux x86_64
- Linux ARM64
- macOS x86_64
- macOS ARM64

### Configuration Location

The Node.js version is centrally defined in:
- **File:** `downloads-bins/tools/fetch_and_archive_nodejs.py`
- **Line:** 48
- **Code:** `NODEJS_VERSION = "22.11.0"`

### Manifest Files

Linux manifests confirm version 22.11.0:
- `downloads-bins/assets/nodejs/linux/x86_64/manifest.json` (line 2)
- `downloads-bins/assets/nodejs/linux/arm64/manifest.json` (line 2)

### Documentation References

- **docs/NODEJS.md** (lines 32-36): Lists all supported platforms with version 22.11.0
- **docs/NODEJS.md** (lines 108-111): Version information and support timeline
- **docs/EMSCRIPTEN.md** (lines 109-111): Emscripten version 4.0.15

## Current State Analysis

### What We Have

1. **Windows binaries:** Node.js 22.11.0 bundled and ready
2. **Linux manifests:** Present and pointing to version 22.11.0
3. **Configuration:** Unified version across all platforms

### What's Missing for Linux

Based on the investigation, the infrastructure appears to be in place for Linux Node.js binaries (manifests exist), but the question implies the binaries themselves may not be present or properly packaged.

### Binary Size Information

From documentation:
- Compressed size: ~23-24 MB per platform (using zstd level 22)
- Uncompressed size: ~90-100 MB

## Recommendation

**Use Node.js 22.11.0 LTS for Linux** as it:
1. Matches the existing Windows configuration
2. Is already configured in the build system
3. Is an LTS release with support until 2027
4. Is compatible with Emscripten 4.0.15
5. Has manifest files already created for Linux x86_64 and ARM64

## Implementation Completed (Iteration 1)

### Actions Taken

1. ✅ Used the existing `fetch_and_archive_nodejs.py` script
2. ✅ Generated Linux x86_64 Node.js 22.11.0 binary
3. ✅ Generated Linux arm64 Node.js 22.11.0 binary
4. ✅ Verified checksums in manifest files

### Results

**Linux x86_64:**
- Archive: `nodejs-22.11.0-linux-x86_64.tar.zst` (28 MB)
- SHA256: `6cbc0d6e0824a116ac34957529477ba207027ef01fb1a200c91706073b7c4c00`
- Manifest: Updated with real checksum

**Linux arm64:**
- Archive: `nodejs-22.11.0-linux-arm64.tar.zst` (28 MB)
- SHA256: `438eec9f1f21e1b719152bc337c73d9442e6c3b9300d287d6a8b258c43b16c53`
- Manifest: Updated with real checksum

### Build Process Summary

Each binary was:
1. Downloaded from official Node.js distribution (27-28 MB)
2. Checksum verified against official SHASUMS256.txt
3. Extracted and stripped of unnecessary files (reduced from ~173 MB to ~112 MB)
4. Compressed with zstd level 22 (final size ~28 MB)
5. SHA256 and MD5 checksums generated
6. Manifest files updated with proper checksums

### Status

**COMPLETE** - Linux Node.js 22.11.0 binaries for both x86_64 and arm64 architectures have been successfully generated and are ready for distribution.

### Next Steps for Repository Maintainer

1. Commit the generated binaries to the `clang-tool-chain-bins` repository
2. Test extraction and execution on actual Linux systems (x86_64 and arm64)
3. Test with Emscripten 4.0.15 on Linux to ensure compatibility
4. Update any deployment scripts or documentation as needed

## Investigation Methodology

This investigation used the Explore agent to:
1. Search for Node.js version configuration files
2. Review Emscripten documentation
3. Examine manifest files across all platforms
4. Cross-reference documentation files (NODEJS.md, EMSCRIPTEN.md)
5. Verify consistency across platform-specific configurations

**Investigation Date:** 2025-11-11
**Implementation Date:** 2025-11-11
