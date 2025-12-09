#!/bin/bash
# Helper script to run clang-tool-chain tests on Linux ARM64 using Docker emulation
# This script should be run from the repository root directory
# Usage: ./docker/test-arm64.sh

set -e

# Change to repository root if script is run from docker/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "ARM64 Test Runner for clang-tool-chain"
echo "=========================================="
echo ""

# Build ARM64 Docker image
echo "Building ARM64 Docker image..."
docker build --platform linux/arm64 -t clang-tool-chain-arm64-test -f docker/Dockerfile.arm64-test .

echo ""
echo "Running test in ARM64 container..."
echo ""

# Run the specific failing test
docker run --platform linux/arm64 --rm \
    -v "$(pwd):/workspace" \
    -w /workspace \
    -e CLANG_TOOL_CHAIN_DEBUG=1 \
    clang-tool-chain-arm64-test \
    bash -c "
        set -e
        echo 'Installing dependencies...'
        uv venv
        source .venv/bin/activate
        uv pip install -e '.[dev]'

        echo ''
        echo 'Installing sccache...'
        # Try to install sccache via cargo
        apt-get update && apt-get install -y cargo
        cargo install sccache --root /usr/local

        echo ''
        echo 'Running failing test...'
        uv run pytest tests/test_emscripten.py::TestEmscriptenSccache::test_compile_with_sccache -v -s
    "

echo ""
echo "=========================================="
echo "Test completed"
echo "=========================================="
