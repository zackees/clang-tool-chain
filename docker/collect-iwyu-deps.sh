#!/bin/bash
# Dependency collection script for IWYU
# Analyzes IWYU binary, identifies dependencies, and collects only necessary libraries
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -ne 2 ]; then
    echo -e "${RED}Error: Invalid arguments${NC}"
    echo "Usage: $0 <input-dir> <output-dir>"
    echo "  input-dir:  Directory containing IWYU build (bin/, lib/)"
    echo "  output-dir: Directory to write filtered output"
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_DIR="$2"

# Validate input directory
if [ ! -d "$INPUT_DIR" ]; then
    echo -e "${RED}Error: Input directory not found: $INPUT_DIR${NC}"
    exit 1
fi

if [ ! -f "$INPUT_DIR/bin/include-what-you-use" ]; then
    echo -e "${RED}Error: IWYU binary not found in $INPUT_DIR/bin/${NC}"
    exit 1
fi

# Create output directories
mkdir -p "$OUTPUT_DIR/bin"
mkdir -p "$OUTPUT_DIR/lib"
mkdir -p "$OUTPUT_DIR/share"

IWYU_BIN="$INPUT_DIR/bin/include-what-you-use"
REPORT_FILE="$OUTPUT_DIR/dependency_report.txt"

echo -e "${GREEN}=== IWYU Dependency Collector ===${NC}"
echo ""
echo "Input:  $INPUT_DIR"
echo "Output: $OUTPUT_DIR"
echo ""

# System libraries that should NEVER be bundled
SYSTEM_LIBS=(
    "libc.so"
    "libm.so"
    "libgcc_s.so"
    "libstdc++.so"
    "libpthread.so"
    "libdl.so"
    "librt.so"
    "ld-linux-aarch64.so"
    "ld-linux-x86-64.so"
    "ld-linux.so"
)

# Check if a library is a system library
is_system_lib() {
    local lib="$1"
    local basename=$(basename "$lib")

    for sys_lib in "${SYSTEM_LIBS[@]}"; do
        if [[ "$basename" == ${sys_lib}* ]]; then
            return 0  # Is system lib
        fi
    done
    return 1  # Not system lib
}

# Start dependency report
{
    echo "=== IWYU Binary Analysis ==="
    echo "Binary: $IWYU_BIN"
    file "$IWYU_BIN"
    echo ""

    echo "=== Binary RPATH/RUNPATH ==="
    readelf -d "$IWYU_BIN" | grep -E "(RUNPATH|RPATH)" || echo "(none set)"
    echo ""

    echo "=== Direct Dependencies (NEEDED) ==="
    readelf -d "$IWYU_BIN" | grep NEEDED | awk '{print $5}' | tr -d '[]'
    echo ""
} > "$REPORT_FILE"

echo -e "${YELLOW}Step 1: Analyzing IWYU binary...${NC}"

# Get all dependencies using ldd
echo -e "${BLUE}Running ldd on IWYU binary...${NC}"
LDD_OUTPUT=$(ldd "$IWYU_BIN" 2>&1 || true)

{
    echo "=== Resolved Paths (ldd) ==="
    echo "$LDD_OUTPUT"
    echo ""
} >> "$REPORT_FILE"

# Parse ldd output and categorize libraries
declare -A BUNDLED_LIBS
declare -A SKIPPED_LIBS

echo "$LDD_OUTPUT" | while read -r line; do
    # Extract library name and path from ldd output
    # Format: "libname.so.X => /path/to/lib.so.X (0x...)"
    if [[ "$line" =~ ([^[:space:]]+)[[:space:]]+=\>[[:space:]]+([^[:space:]]+) ]]; then
        lib_name="${BASH_REMATCH[1]}"
        lib_path="${BASH_REMATCH[2]}"

        if is_system_lib "$lib_name"; then
            SKIPPED_LIBS["$lib_name"]="$lib_path"
        else
            BUNDLED_LIBS["$lib_name"]="$lib_path"
        fi
    fi
done

echo -e "${YELLOW}Step 2: Collecting bundled libraries...${NC}"

# Collect all non-system libraries from input lib directory
TOTAL_SIZE=0

for lib_file in "$INPUT_DIR/lib"/*; do
    if [ ! -f "$lib_file" ] && [ ! -L "$lib_file" ]; then
        continue
    fi

    lib_basename=$(basename "$lib_file")

    # Skip system libraries
    if is_system_lib "$lib_basename"; then
        echo -e "  ${RED}Skipping system lib:${NC} $lib_basename"
        continue
    fi

    # Copy library (preserving symlinks)
    echo -e "  ${GREEN}Bundling:${NC} $lib_basename"
    cp -P "$lib_file" "$OUTPUT_DIR/lib/"

    # Calculate size if it's a regular file
    if [ -f "$lib_file" ] && [ ! -L "$lib_file" ]; then
        size=$(stat -c%s "$lib_file" 2>/dev/null || stat -f%z "$lib_file" 2>/dev/null || echo 0)
        TOTAL_SIZE=$((TOTAL_SIZE + size))
    fi
done

echo ""
echo -e "${YELLOW}Step 3: Analyzing library dependencies recursively...${NC}"

# Analyze each bundled library's dependencies
{
    echo "=== Library Dependency Analysis ==="
    echo ""
} >> "$REPORT_FILE"

for lib_file in "$OUTPUT_DIR/lib"/*; do
    if [ ! -f "$lib_file" ] || [ -L "$lib_file" ]; then
        continue
    fi

    lib_basename=$(basename "$lib_file")
    echo -e "${BLUE}  Analyzing: $lib_basename${NC}"

    {
        echo "Library: $lib_basename"
        readelf -d "$lib_file" | grep NEEDED | awk '{print "  " $5}' | tr -d '[]' || echo "  (no dependencies)"
        echo ""
    } >> "$REPORT_FILE"
done

echo ""
echo -e "${YELLOW}Step 4: Copying IWYU binary...${NC}"

# Copy the binary
cp -P "$IWYU_BIN" "$OUTPUT_DIR/bin/"
echo -e "  ${GREEN}Copied:${NC} include-what-you-use"

# Copy Python helper scripts if they exist
if [ -d "$INPUT_DIR/bin" ]; then
    for py_file in "$INPUT_DIR/bin"/*.py; do
        if [ -f "$py_file" ]; then
            cp "$py_file" "$OUTPUT_DIR/bin/"
            chmod +x "$OUTPUT_DIR/bin/$(basename "$py_file")"
            echo -e "  ${GREEN}Copied:${NC} $(basename "$py_file")"
        fi
    done
fi

# Calculate binary size
BIN_SIZE=$(stat -c%s "$OUTPUT_DIR/bin/include-what-you-use" 2>/dev/null || stat -f%z "$OUTPUT_DIR/bin/include-what-you-use" 2>/dev/null || echo 0)

echo ""
echo -e "${YELLOW}Step 5: Copying additional files...${NC}"

# Copy share directory if it exists
if [ -d "$INPUT_DIR/share" ]; then
    cp -r "$INPUT_DIR/share"/* "$OUTPUT_DIR/share/" 2>/dev/null || true
    echo -e "  ${GREEN}Copied:${NC} share/ directory"
fi

# Copy license and readme files
for file in "$INPUT_DIR"/{LICENSE*,README*,*.txt,*.json}; do
    if [ -f "$file" ]; then
        cp "$file" "$OUTPUT_DIR/"
        echo -e "  ${GREEN}Copied:${NC} $(basename "$file")"
    fi
done

echo ""
echo -e "${YELLOW}Step 6: Verifying RPATH...${NC}"

# Verify RPATH is correct
RPATH=$(readelf -d "$OUTPUT_DIR/bin/include-what-you-use" | grep -E "(RUNPATH|RPATH)" | grep -o '\$ORIGIN[^]]*' || echo "")
if [ -z "$RPATH" ]; then
    echo -e "  ${RED}Warning: No RPATH set, setting to \$ORIGIN/../lib${NC}"
    patchelf --set-rpath '$ORIGIN/../lib' "$OUTPUT_DIR/bin/include-what-you-use"
    RPATH='$ORIGIN/../lib'
fi
echo -e "  ${GREEN}RPATH:${NC} $RPATH"

echo ""
echo -e "${YELLOW}Step 7: Generating dependency report...${NC}"

# Generate summary
{
    echo "=== Bundled Libraries Summary ==="
    echo ""
    for lib in "$OUTPUT_DIR/lib"/*; do
        if [ -f "$lib" ] && [ ! -L "$lib" ]; then
            size=$(stat -c%s "$lib" 2>/dev/null || stat -f%z "$lib" 2>/dev/null || echo 0)
            size_mb=$(echo "scale=2; $size / 1048576" | bc 2>/dev/null || echo "0")
            echo "✓ $(basename "$lib") (${size_mb} MB)"
        elif [ -L "$lib" ]; then
            target=$(readlink "$lib")
            echo "✓ $(basename "$lib") -> $target (symlink)"
        fi
    done
    echo ""

    echo "=== Skipped System Libraries ==="
    echo ""
    for sys_lib in "${SYSTEM_LIBS[@]}"; do
        echo "✗ ${sys_lib}* (system library)"
    done
    echo ""

    echo "=== Size Summary ==="
    bin_mb=$(echo "scale=2; $BIN_SIZE / 1048576" | bc 2>/dev/null || echo "0")
    lib_mb=$(echo "scale=2; $TOTAL_SIZE / 1048576" | bc 2>/dev/null || echo "0")
    total_mb=$(echo "scale=2; ($BIN_SIZE + $TOTAL_SIZE) / 1048576" | bc 2>/dev/null || echo "0")
    echo "Binaries: ${bin_mb} MB"
    echo "Libraries: ${lib_mb} MB"
    echo "Total: ${total_mb} MB"
    echo ""

    echo "=== Verification ==="
    echo "RPATH: $RPATH"
    echo "Output directory: $OUTPUT_DIR"
    echo ""

} >> "$REPORT_FILE"

echo -e "  ${GREEN}Report written to:${NC} dependency_report.txt"

echo ""
echo -e "${YELLOW}Step 8: Testing binary can find libraries...${NC}"

# Test that libraries can be found
export LD_LIBRARY_PATH="$OUTPUT_DIR/lib:$LD_LIBRARY_PATH"
if ldd "$OUTPUT_DIR/bin/include-what-you-use" | grep -q "not found"; then
    echo -e "  ${RED}Warning: Some libraries not found!${NC}"
    ldd "$OUTPUT_DIR/bin/include-what-you-use" | grep "not found"
else
    echo -e "  ${GREEN}Success: All libraries resolved${NC}"
fi

echo ""
echo -e "${GREEN}=== Dependency Collection Complete ===${NC}"
echo ""
echo "Output directory: $OUTPUT_DIR"
echo "Dependency report: $OUTPUT_DIR/dependency_report.txt"
echo ""
echo "Contents:"
ls -lh "$OUTPUT_DIR"
echo ""
echo "Library count:"
lib_count=$(find "$OUTPUT_DIR/lib" -type f | wc -l)
symlink_count=$(find "$OUTPUT_DIR/lib" -type l | wc -l)
echo "  Regular files: $lib_count"
echo "  Symlinks: $symlink_count"
echo ""
echo "Total size:"
du -sh "$OUTPUT_DIR"
echo ""
echo -e "${BLUE}Review the dependency report:${NC}"
echo "  cat $OUTPUT_DIR/dependency_report.txt"
echo ""
