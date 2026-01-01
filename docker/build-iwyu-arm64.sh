#!/bin/bash
# Build IWYU for Linux ARM64 using Docker
#
# This script:
# 1. Builds IWYU 0.25 from source for ARM64 Linux
# 2. Bundles only LLVM-specific libraries (no system libraries)
# 3. Extracts the build to downloads-bins/assets/iwyu/linux/arm64/
# 4. Cleans up the extracted directory (removes system libs if any)
# 5. Creates the fixed archive with zstd level 10
#
# Requirements:
#   - Docker with ARM64 platform support
#   - Run from clang-tool-chain root directory

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Building IWYU for Linux ARM64 ===${NC}"
echo ""

# Check we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "downloads-bins" ]; then
    echo -e "${RED}Error: Must run from clang-tool-chain root directory${NC}"
    exit 1
fi

# Create output directory
OUTPUT_DIR="$(pwd)/docker/output"
mkdir -p "$OUTPUT_DIR"

echo -e "${YELLOW}Step 1: Building Docker image...${NC}"
docker build --platform linux/arm64 \
    -t iwyu-arm64-builder \
    -f docker/Dockerfile.iwyu-arm64-builder \
    .

echo ""
echo -e "${YELLOW}Step 2: Running build container...${NC}"
docker run --platform linux/arm64 --rm \
    -v "$OUTPUT_DIR:/output" \
    iwyu-arm64-builder

echo ""
echo -e "${YELLOW}Step 3: Cleaning extracted build...${NC}"

# Check if build succeeded
if [ ! -d "$OUTPUT_DIR/iwyu-arm64" ]; then
    echo -e "${RED}Error: Build failed - output directory not found${NC}"
    exit 1
fi

cd "$OUTPUT_DIR/iwyu-arm64"

# Remove system libraries that should NOT be bundled
echo "Removing system libraries from lib/..."
SYSTEM_LIBS="libc.so* libm.so* libstdc++.so* libgcc_s.so* libpthread.so* libdl.so* librt.so*"
for pattern in $SYSTEM_LIBS; do
    if ls lib/$pattern 2>/dev/null; then
        echo "  Removing: lib/$pattern"
        rm -f lib/$pattern
    fi
done

echo ""
echo "Remaining libraries:"
ls -lh lib/ | grep -v "^total" | awk '{print "  " $9 " (" $5 ")"}'

echo ""
echo -e "${YELLOW}Step 4: Verifying binary dependencies...${NC}"
echo "Binary info:"
file bin/include-what-you-use
echo ""
echo "RPATH:"
readelf -d bin/include-what-you-use | grep -E "(RUNPATH|RPATH)" || echo "  (none set)"
echo ""
echo "Dynamic library dependencies:"
readelf -d bin/include-what-you-use | grep NEEDED | awk '{print "  " $0}'

echo ""
echo -e "${YELLOW}Step 5: Copying to downloads-bins...${NC}"
TARGET_DIR="$(pwd)/../../downloads-bins/assets/iwyu/linux/arm64"
mkdir -p "$TARGET_DIR"

# Backup old files
if [ -d "$TARGET_DIR/bin" ]; then
    echo "Backing up old installation..."
    mv "$TARGET_DIR/bin" "$TARGET_DIR/bin.old.$(date +%Y%m%d_%H%M%S)" || true
    mv "$TARGET_DIR/lib" "$TARGET_DIR/lib.old.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    mv "$TARGET_DIR/share" "$TARGET_DIR/share.old.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
fi

# Copy new files
echo "Copying bin/..."
cp -r bin "$TARGET_DIR/"
echo "Copying lib/..."
cp -r lib "$TARGET_DIR/"
echo "Copying share/..."
cp -r share "$TARGET_DIR/" 2>/dev/null || echo "  (no share directory)"

# Copy additional files if they exist
for file in LICENSE* README* *.txt *.json; do
    if [ -f "$file" ]; then
        cp "$file" "$TARGET_DIR/" 2>/dev/null || true
    fi
done

echo ""
echo -e "${GREEN}=== Build complete! ===${NC}"
echo ""
echo "Output directory: $TARGET_DIR"
echo ""
echo "Directory contents:"
ls -lh "$TARGET_DIR"
echo ""
echo "Total size:"
du -sh "$TARGET_DIR"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. cd to downloads-bins directory"
echo "2. Run: uv run create-iwyu-archives --platform linux --arch arm64 --zstd-level 10"
echo "3. Update manifest.json with new hash"
echo "4. Test the binary: $TARGET_DIR/bin/include-what-you-use --version"
echo ""
echo -e "${YELLOW}Cleanup:${NC}"
echo "To remove build artifacts: rm -rf $OUTPUT_DIR"
