# Docker Testing Infrastructure

This directory contains Docker-based testing infrastructure for clang-tool-chain, specifically for local testing on different architectures.

## ARM64 Testing

### Files

- **Dockerfile.arm64-test** - Ubuntu 24.04 LTS ARM64 image for testing
- **test-arm64.sh** - Helper script to build and run ARM64 tests using Docker emulation
- **Dockerfile.iwyu-arm64-builder** - Builder for IWYU 0.25 with LLVM 21.1.5 on ARM64
- **build-iwyu-arm64.sh** - Automated script to build and extract IWYU ARM64 binaries

### Purpose

These files enable local testing of clang-tool-chain on Linux ARM64 architecture without requiring physical ARM64 hardware. This is particularly useful for:

1. Reproducing platform-specific issues (e.g., sccache + Emscripten timeouts on ARM64)
2. Validating fixes across different architectures locally
3. Debugging architecture-specific behavior before submitting changes

### Requirements

- Docker with ARM64 platform support (Docker Desktop or buildx)
- Sufficient disk space for ARM64 Ubuntu image and build artifacts

### Usage

#### Quick Test

Run the entire test suite on ARM64:

```bash
./docker/test-arm64.sh
```

This script will:
1. Build an ARM64 Docker image with Ubuntu 24.04
2. Install Python, uv, and development dependencies
3. Install sccache (for Emscripten integration tests)
4. Run the Emscripten sccache integration test

#### Manual Testing

Build the ARM64 image:

```bash
docker build --platform linux/arm64 -t clang-tool-chain-arm64-test -f docker/Dockerfile.arm64-test .
```

Run interactive shell for debugging:

```bash
docker run --platform linux/arm64 --rm -it \
    -v "$(pwd):/workspace" \
    -w /workspace \
    clang-tool-chain-arm64-test \
    bash
```

Run specific tests:

```bash
docker run --platform linux/arm64 --rm \
    -v "$(pwd):/workspace" \
    -w /workspace \
    clang-tool-chain-arm64-test \
    bash -c "
        uv venv
        source .venv/bin/activate
        uv pip install -e '.[dev]'
        uv run pytest tests/test_emscripten.py -v
    "
```

### Docker Image Details

**Base Image:** ubuntu:24.04

**Installed Packages:**
- Python 3.12 (Ubuntu 24.04 default)
- uv (Python package manager)
- curl, git
- build-essential (GCC, G++, make, etc.)
- software-properties-common

**Working Directory:** `/workspace`

The Docker image mounts the current repository directory to `/workspace`, allowing you to test local changes without rebuilding the image.

### Known Issues

1. **Emscripten + sccache on ARM64**: As of the latest fixes, sccache integration is disabled on all Linux platforms due to timeout issues. This is documented in:
   - `src/clang_tool_chain/execution/emscripten.py:680-693`
   - `tests/test_emscripten.py:307` (test skip condition)

2. **Docker Emulation Performance**: ARM64 emulation on x86_64 hosts is significantly slower than native execution. Expect tests to take 2-5x longer.

## IWYU ARM64 Builder

### Purpose

Build Include-What-You-Use (IWYU) 0.25 from source for Linux ARM64 with proper LLVM 21.1.5 dependencies. This is needed because the original ARM64 binary was a Homebrew build (for macOS) and incompatible with Linux.

### Files

- **Dockerfile.iwyu-arm64-builder** - Multi-stage build that compiles LLVM and IWYU from source
- **build-iwyu-arm64.sh** - Automated build, cleanup, and extraction script

### Quick Start

```bash
# From clang-tool-chain root directory
./docker/build-iwyu-arm64.sh
```

This will:
1. Build LLVM 21.1.5 shared libraries (libclang-cpp, libLLVM)
2. Build IWYU 0.25 against LLVM
3. Bundle only LLVM-specific libraries (no system libraries)
4. Set RPATH to `$ORIGIN/../lib`
5. Extract to `downloads-bins/assets/iwyu/linux/arm64/`

**Build time**: 30-60 minutes (depends on hardware and ARM64 emulation speed)

**Output**: ~758 MB uncompressed IWYU installation with proper Linux ARM64 binaries

### Manual Build

```bash
# Build Docker image
docker build --platform linux/arm64 \
    -t iwyu-arm64-builder \
    -f docker/Dockerfile.iwyu-arm64-builder \
    .

# Run build and extract to output/
mkdir -p docker/output
docker run --platform linux/arm64 --rm \
    -v "$(pwd)/docker/output:/output" \
    iwyu-arm64-builder
```

### Next Steps

After building, create the distribution archive:

```bash
cd downloads-bins

# Create compressed archive (zstd level 10, NOT 22!)
uv run create-iwyu-archives --platform linux --arch arm64 --zstd-level 10

# Rename to -fixed suffix
cd assets/iwyu/linux/arm64
mv iwyu-0.25-linux-arm64.tar.zst iwyu-0.25-linux-arm64-fixed.tar.zst
mv iwyu-0.25-linux-arm64.tar.zst.sha256 iwyu-0.25-linux-arm64-fixed.tar.zst.sha256

# Update manifest.json with new SHA256 and filename
```

See `docs/IWYU_ARM64_FIX_GUIDE.md` for complete instructions.

### What's Different from x86_64?

- ARM64 uses `/lib/ld-linux-aarch64.so.1` dynamic linker
- Built from source (no pre-built ARM64 Linux binaries available)
- Same LLVM 21.1.5 version as x86_64
- Same library bundling strategy (LLVM libs only, no system libs)

### Verification

```bash
# Check binary type
file downloads-bins/assets/iwyu/linux/arm64/bin/include-what-you-use
# Should show: ARM aarch64, interpreter /lib/ld-linux-aarch64.so.1

# Check RPATH
readelf -d downloads-bins/assets/iwyu/linux/arm64/bin/include-what-you-use | grep RPATH
# Should show: $ORIGIN/../lib

# Test (requires ARM64 Docker or native ARM64)
docker run --platform linux/arm64 --rm \
    -v "$(pwd)/downloads-bins/assets/iwyu/linux/arm64:/iwyu" \
    ubuntu:24.04 \
    /iwyu/bin/include-what-you-use --version
# Should print: include-what-you-use 0.25 based on clang version 21.1.5
```

### Future Improvements

Consider adding:
- Multi-architecture testing (x86_64 + ARM64 in parallel)
- Cached Docker layers for faster builds
- Additional platform-specific test scenarios
- x86_64 Docker test environment for consistency
- IWYU builder for other architectures (if needed)
