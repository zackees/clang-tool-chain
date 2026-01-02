# IWYU Dependency Collection Task

## Objective

Create a Docker-based system that:
1. Launches an ARM64 Linux environment
2. Extracts the IWYU binary and its dependencies
3. Identifies all required shared libraries
4. Collects only the necessary runtime dependencies (excluding system libraries)
5. Outputs the collected dependencies to the host filesystem

## Background

The current IWYU ARM64 build process compiles LLVM and IWYU from source, but we need a systematic way to:
- Identify which shared libraries IWYU actually needs at runtime
- Separate LLVM-specific libraries from system libraries
- Package only the portable dependencies (not libc, libstdc++, etc.)

## Requirements

### 1. Docker Environment Setup
- **Platform**: `linux/arm64`
- **Base Image**: `ubuntu:24.04` (matching the build environment)
- **Mounted Volume**: Host directory for output

### 2. Dependency Analysis Tools
The Docker environment should include:
- `ldd` - List dynamic dependencies
- `readelf` - Read ELF binary information
- `patchelf` - Modify RPATH if needed
- `file` - Identify binary types

### 3. Dependency Collection Logic

**Identify dependencies:**
```bash
# Get list of all shared libraries the binary needs
ldd /path/to/include-what-you-use

# Get NEEDED entries from ELF header
readelf -d /path/to/include-what-you-use | grep NEEDED
```

**Categorize libraries:**
- **LLVM-specific** (must bundle):
  - `libclang-cpp.so.*`
  - `libLLVM*.so.*`
  - `libLLVM-*.so`

- **Third-party dependencies** (bundle if not universally available):
  - `libxml2.so.*`
  - `libz.so.*` (zlib)
  - `libicu*.so.*` (ICU Unicode)
  - `liblzma.so.*` (XZ Utils)
  - `libtinfo.so.*` (ncurses terminfo)

- **System libraries** (NEVER bundle):
  - `libc.so.6` (glibc)
  - `libm.so.6` (math library)
  - `libgcc_s.so.1` (GCC runtime)
  - `libstdc++.so.6` (C++ standard library)
  - `libpthread.so.0` (POSIX threads)
  - `libdl.so.2` (dynamic linker)
  - `ld-linux-aarch64.so.1` (dynamic linker itself)

### 4. Output Structure

The Docker container should output to `/output/` (mounted to host):

```
/output/
├── bin/
│   └── include-what-you-use          # The IWYU binary
├── lib/
│   ├── libclang-cpp.so.21.1          # LLVM C++ API
│   ├── libLLVM.so.21.1               # LLVM core
│   ├── libLLVM-21.so -> libLLVM.so.21.1
│   ├── libxml2.so.2.*                # XML parser
│   ├── libz.so.1.*                   # zlib
│   ├── libicu*.so.*                  # ICU libs
│   └── liblzma.so.5.*                # XZ compression
├── share/
│   └── man/...                       # Man pages (if any)
└── dependency_report.txt             # Analysis report
```

### 5. Dependency Report Format

The `dependency_report.txt` should contain:

```
=== IWYU Binary Analysis ===
Binary: /path/to/include-what-you-use
Type: ELF 64-bit LSB pie executable, ARM aarch64
Interpreter: /lib/ld-linux-aarch64.so.1
RPATH: $ORIGIN/../lib

=== Direct Dependencies (NEEDED) ===
libclang-cpp.so.21
libLLVM.so.21
libstdc++.so.6
libm.so.6
libgcc_s.so.1
libc.so.6

=== Resolved Paths (ldd) ===
libclang-cpp.so.21 => /build/llvm-install/lib/libclang-cpp.so.21.1
libLLVM.so.21 => /build/llvm-install/lib/libLLVM.so.21.1
libstdc++.so.6 => /lib/aarch64-linux-gnu/libstdc++.so.6.0.33 [SYSTEM - SKIP]
libm.so.6 => /lib/aarch64-linux-gnu/libm.so.6 [SYSTEM - SKIP]
...

=== LLVM Library Dependencies ===
libclang-cpp.so.21.1 requires:
  - libxml2.so.2
  - libz.so.1
  - libicu*.so.70
  - liblzma.so.5

=== Bundled Libraries ===
✓ libclang-cpp.so.21.1 (81 MB)
✓ libLLVM.so.21.1 (163 MB)
✓ libxml2.so.2.9.14 (687 KB)
✓ libz.so.1.2.13 (95 KB)
✓ libicuuc.so.70.1 (1.9 MB)
✓ libicudata.so.70.1 (28 MB)
✓ liblzma.so.5.4.1 (156 KB)

=== Skipped System Libraries ===
✗ libc.so.6 (system)
✗ libm.so.6 (system)
✗ libgcc_s.so.1 (system)
✗ libstdc++.so.6 (system)
✗ libpthread.so.0 (system)
✗ libdl.so.2 (system)

=== Total Size ===
Binaries: 3.6 MB
Libraries: 275 MB
Total: 278.6 MB
```

## Implementation Plan

### Step 1: Create Dockerfile.iwyu-deps-collector

```dockerfile
FROM ubuntu:24.04

# Install analysis tools
RUN apt-get update && apt-get install -y \
    file \
    binutils \
    patchelf \
    findutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy dependency analysis script
COPY docker/collect-iwyu-deps.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/collect-iwyu-deps.sh

ENTRYPOINT ["/usr/local/bin/collect-iwyu-deps.sh"]
```

### Step 2: Create docker/collect-iwyu-deps.sh

The script should:
1. Accept input path to IWYU installation (from builder)
2. Analyze binary dependencies with `ldd` and `readelf`
3. Recursively analyze LLVM library dependencies
4. Filter out system libraries
5. Copy bundled libraries to `/output/lib/`
6. Copy binary to `/output/bin/`
7. Generate dependency report
8. Verify RPATH is set correctly
9. Test that binary can load libraries

### Step 3: Create wrapper script docker/collect-deps-arm64.sh

```bash
#!/bin/bash
set -e

echo "=== IWYU ARM64 Dependency Collector ==="
echo ""

# Check if IWYU was built
if [ ! -d "docker/output/iwyu-arm64" ]; then
    echo "Error: IWYU ARM64 build not found!"
    echo "Run ./docker/build-iwyu-arm64.sh first"
    exit 1
fi

# Create output directory
mkdir -p downloads-bins/assets/iwyu/linux/arm64

echo "Building dependency collector Docker image..."
docker build --platform linux/arm64 \
    -t iwyu-deps-collector \
    -f docker/Dockerfile.iwyu-deps-collector \
    .

echo ""
echo "Analyzing and collecting dependencies..."
docker run --platform linux/arm64 --rm \
    -v "$(pwd)/docker/output/iwyu-arm64:/input:ro" \
    -v "$(pwd)/downloads-bins/assets/iwyu/linux/arm64:/output" \
    iwyu-deps-collector \
    /input /output

echo ""
echo "=== Dependency collection complete ==="
echo ""
echo "Output location: downloads-bins/assets/iwyu/linux/arm64/"
echo ""
echo "Next steps:"
echo "1. Review dependency_report.txt"
echo "2. Verify binary: docker run --platform linux/arm64 --rm -v \"\$(pwd)/downloads-bins/assets/iwyu/linux/arm64:/iwyu\" ubuntu:24.04 /iwyu/bin/include-what-you-use --version"
echo "3. Create archive: cd downloads-bins && uv run create-iwyu-archives --platform linux --arch arm64 --zstd-level 10"
echo ""
```

## Expected Workflow

```bash
# 1. Build IWYU from source (already done)
./docker/build-iwyu-arm64.sh

# 2. Collect and filter dependencies (new task)
./docker/collect-deps-arm64.sh

# 3. Review the dependency report
cat downloads-bins/assets/iwyu/linux/arm64/dependency_report.txt

# 4. Verify the binary works
docker run --platform linux/arm64 --rm \
    -v "$(pwd)/downloads-bins/assets/iwyu/linux/arm64:/iwyu" \
    ubuntu:24.04 \
    /iwyu/bin/include-what-you-use --version

# 5. Create the distribution archive
cd downloads-bins
uv run create-iwyu-archives --platform linux --arch arm64 --zstd-level 10

# 6. Update manifest and commit
# ... (existing process)
```

## Benefits

1. **Reproducible**: Systematic dependency collection process
2. **Transparent**: Clear report of what's included and why
3. **Verifiable**: Can validate dependencies before packaging
4. **Portable**: Docker-based, works on any platform
5. **Maintainable**: Easy to adjust filtering rules

## Files to Create

1. `docker/Dockerfile.iwyu-deps-collector` - Dependency analysis environment
2. `docker/collect-iwyu-deps.sh` - Dependency collection script
3. `docker/collect-deps-arm64.sh` - Wrapper script for easy execution

## Success Criteria

- [ ] Dependency collector Docker image builds successfully
- [ ] Script correctly identifies LLVM vs system libraries
- [ ] All LLVM libraries are collected with proper symlinks
- [ ] System libraries are excluded
- [ ] RPATH is verified as `$ORIGIN/../lib`
- [ ] Generated dependency report is accurate
- [ ] Binary runs successfully in clean Ubuntu 24.04 container
- [ ] Total size matches expected ~275-280 MB for libraries

---

**Status**: Ready to implement
**Priority**: High (needed to complete ARM64 IWYU fix)
**Estimated Time**: 1-2 hours
