# Docker Testing Infrastructure

This directory contains Docker-based testing infrastructure for clang-tool-chain, specifically for local testing on different architectures.

## ARM64 Testing

### Files

- **Dockerfile.arm64-test** - Ubuntu 24.04 LTS ARM64 image for testing
- **test-arm64.sh** - Helper script to build and run ARM64 tests using Docker emulation

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

### Future Improvements

Consider adding:
- Multi-architecture testing (x86_64 + ARM64 in parallel)
- Cached Docker layers for faster builds
- Additional platform-specific test scenarios
- x86_64 Docker test environment for consistency
