#!/bin/bash
# Wrapper script for IWYU ARM64 dependency collection
#
# This script:
# 1. Checks that IWYU was built successfully
# 2. Builds the dependency collector Docker image
# 3. Runs dependency analysis and collection
# 4. Outputs filtered dependencies to downloads-bins/
#
# Requirements:
#   - Docker with ARM64 platform support
#   - IWYU build must exist in docker/output/iwyu-arm64/
#   - Run from clang-tool-chain root directory

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== IWYU ARM64 Dependency Collector ===${NC}"
echo ""

# Check we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "downloads-bins" ]; then
    echo -e "${RED}Error: Must run from clang-tool-chain root directory${NC}"
    exit 1
fi

# Check if IWYU was built
if [ ! -d "docker/output/iwyu-arm64" ]; then
    echo -e "${RED}Error: IWYU ARM64 build not found!${NC}"
    echo ""
    echo "Please run the build script first:"
    echo "  ./docker/build-iwyu-arm64.sh"
    echo ""
    exit 1
fi

# Check if IWYU binary exists
if [ ! -f "docker/output/iwyu-arm64/bin/include-what-you-use" ]; then
    echo -e "${RED}Error: IWYU binary not found in build output!${NC}"
    echo ""
    echo "Expected: docker/output/iwyu-arm64/bin/include-what-you-use"
    echo ""
    exit 1
fi

# Create output directory
OUTPUT_DIR="downloads-bins/assets/iwyu/linux/arm64"
mkdir -p "$OUTPUT_DIR"

echo -e "${YELLOW}Step 1: Building dependency collector Docker image...${NC}"
docker build --platform linux/arm64 \
    -t iwyu-deps-collector \
    -f docker/Dockerfile.iwyu-deps-collector \
    .

echo ""
echo -e "${YELLOW}Step 2: Analyzing and collecting dependencies...${NC}"
echo ""
echo "Input:  docker/output/iwyu-arm64/"
echo "Output: $OUTPUT_DIR/"
echo ""

docker run --platform linux/arm64 --rm \
    -v "$(pwd)/docker/output/iwyu-arm64:/input:ro" \
    -v "$(pwd)/$OUTPUT_DIR:/output" \
    iwyu-deps-collector \
    /input /output

echo ""
echo -e "${GREEN}=== Dependency collection complete ===${NC}"
echo ""
echo "Output location: $OUTPUT_DIR/"
echo ""

# Display the dependency report
if [ -f "$OUTPUT_DIR/dependency_report.txt" ]; then
    echo -e "${BLUE}=== Dependency Report Summary ===${NC}"
    echo ""
    # Show size summary and verification sections
    sed -n '/=== Size Summary ===/,/=== Verification ===/p' "$OUTPUT_DIR/dependency_report.txt"
    echo ""
    echo -e "${BLUE}Full report available at:${NC}"
    echo "  $OUTPUT_DIR/dependency_report.txt"
    echo ""
fi

echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Review the dependency report:"
echo "   ${BLUE}cat $OUTPUT_DIR/dependency_report.txt${NC}"
echo ""
echo "2. Verify the binary works in a clean Ubuntu container:"
echo "   ${BLUE}docker run --platform linux/arm64 --rm \\${NC}"
echo "   ${BLUE}  -v \"\$(pwd)/$OUTPUT_DIR:/iwyu\" \\${NC}"
echo "   ${BLUE}  ubuntu:24.04 \\${NC}"
echo "   ${BLUE}  /iwyu/bin/include-what-you-use --version${NC}"
echo ""
echo "3. If verification succeeds, create the distribution archive:"
echo "   ${BLUE}cd downloads-bins${NC}"
echo "   ${BLUE}uv run create-iwyu-archives --platform linux --arch arm64 --zstd-level 10${NC}"
echo ""
echo "4. Test the archive with the toolchain:"
echo "   ${BLUE}cd ..${NC}"
echo "   ${BLUE}clang-tool-chain-test${NC}"
echo ""
echo "5. Update manifest.json and commit the changes"
echo ""

# Check if old backups exist and suggest cleanup
OLD_BACKUPS=$(find "$OUTPUT_DIR" -maxdepth 1 -type d -name "*.old.*" 2>/dev/null | wc -l)
if [ "$OLD_BACKUPS" -gt 0 ]; then
    echo -e "${YELLOW}Cleanup suggestion:${NC}"
    echo "  Found $OLD_BACKUPS old backup directories in $OUTPUT_DIR/"
    echo "  You may want to remove them:"
    echo "    ${BLUE}rm -rf $OUTPUT_DIR/*.old.*${NC}"
    echo ""
fi
