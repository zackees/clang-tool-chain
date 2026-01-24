# Additional Utilities

Diagnostic, fetch, and path utilities for clang-tool-chain.

## clang-tool-chain-test

Run diagnostic tests to verify your installation.

### Usage

```bash
# Run 7 diagnostic tests
clang-tool-chain-test

# Or via main CLI:
clang-tool-chain test
```

### Tests Performed

1. **Platform detection** - Verify OS and architecture detection
2. **Toolchain installation verification** - Check if toolchain is installed
3. **clang binary resolution** - Find clang executable
4. **clang++ binary resolution** - Find clang++ executable
5. **clang version check** - Verify LLVM version
6. **C compilation test** - Compile simple C program
7. **C++ compilation test** - Compile simple C++ program

### Example Output

```
Running clang-tool-chain diagnostics...

✓ Platform: linux-x86_64
✓ Toolchain installed: /home/user/.clang-tool-chain/clang/linux/x86_64
✓ clang binary found: /home/user/.clang-tool-chain/clang/linux/x86_64/bin/clang
✓ clang++ binary found: /home/user/.clang-tool-chain/clang/linux/x86_64/bin/clang++
✓ clang version: 21.1.5
✓ C compilation successful
✓ C++ compilation successful

All tests passed! ✓
```

### When to Use

- **After installation** - Verify setup worked correctly
- **CI/CD debugging** - Diagnose installation issues in workflows
- **Platform validation** - Confirm platform detection
- **Bug reports** - Include test output when reporting issues

## clang-tool-chain-fetch

Manual download utility for pre-fetching binaries.

### Usage

```bash
# Fetch binaries for current platform
clang-tool-chain-fetch

# Check what would be downloaded (dry run)
clang-tool-chain-fetch --dry-run
```

### Features

- Downloads toolchain for current platform
- Shows download URLs and checksums
- Verifies SHA256 checksums
- Supports dry-run mode

### Example Output

```bash
$ clang-tool-chain-fetch --dry-run

Would download:
  Platform: linux-x86_64
  URL: https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/linux/x86_64/llvm-21.1.5.tar.zst
  Size: ~87 MB
  SHA256: abc123...
  Install path: /home/user/.clang-tool-chain/clang/linux/x86_64
```

### Use Cases

- **Pre-install for CI/CD** - Explicitly download in separate step
- **Offline preparation** - Download on internet-connected machine
- **Verify download URLs** - Check what will be downloaded
- **Troubleshoot downloads** - Debug download issues

## clang-tool-chain-paths

Get installation paths in JSON format (useful for scripting).

### Usage

```bash
# Get all paths
clang-tool-chain-paths

# Or via main CLI
clang-tool-chain path
clang-tool-chain path clang  # Show specific tool path
```

### Example Output

```json
{
  "install_dir": "/home/user/.clang-tool-chain/clang/linux/x86_64",
  "bin_dir": "/home/user/.clang-tool-chain/clang/linux/x86_64/bin",
  "clang": "/home/user/.clang-tool-chain/clang/linux/x86_64/bin/clang",
  "clang++": "/home/user/.clang-tool-chain/clang/linux/x86_64/bin/clang++",
  "llvm-ar": "/home/user/.clang-tool-chain/clang/linux/x86_64/bin/llvm-ar"
}
```

### Scripting Examples

**Bash:**
```bash
# Extract bin directory
BIN_DIR=$(clang-tool-chain-paths | python -c "import sys,json; print(json.load(sys.stdin)['bin_dir'])")
echo "Binaries located at: $BIN_DIR"

# Add to PATH
export PATH="$BIN_DIR:$PATH"
```

**Python:**
```python
import json
import subprocess

# Get paths
result = subprocess.run(['clang-tool-chain-paths'], capture_output=True, text=True)
paths = json.loads(result.stdout)

# Use paths
clang_path = paths['clang']
print(f"Using clang at: {clang_path}")
```

**PowerShell:**
```powershell
# Parse JSON output
$paths = clang-tool-chain-paths | ConvertFrom-Json
$binDir = $paths.bin_dir
Write-Host "Binaries at: $binDir"
```

## clang-tool-chain info

Show detailed installation information.

### Usage

```bash
clang-tool-chain info
```

### Example Output

```
clang-tool-chain v1.2.3

Platform: linux-x86_64
LLVM Version: 21.1.5
Install Path: /home/user/.clang-tool-chain/clang/linux/x86_64
Bin Path: /home/user/.clang-tool-chain/clang/linux/x86_64/bin
Installed: Yes

Available tools:
  - clang, clang++, clang-format, clang-tidy
  - llvm-ar, llvm-nm, llvm-objdump, llvm-strip
  - iwyu (separate download)
  - lldb (separate download)
  - emcc, em++ (separate download)
  - cosmocc, cosmoc++ (separate download)
```

## clang-tool-chain version

Show version information for tools.

### Usage

```bash
# Package version
clang-tool-chain package-version

# Specific tool version
clang-tool-chain version clang
clang-tool-chain version llvm
clang-tool-chain version emscripten
```

### Example Output

```bash
$ clang-tool-chain package-version
clang-tool-chain: 1.2.3
LLVM: 21.1.5

$ clang-tool-chain version clang
clang version 21.1.5
Target: x86_64-unknown-linux-gnu
Thread model: posix
```

## clang-tool-chain list-tools

List all available wrapper commands.

### Usage

```bash
clang-tool-chain list-tools
```

### Example Output

```
Available clang-tool-chain commands:

Compilers:
  - clang-tool-chain-c
  - clang-tool-chain-cpp
  - clang-tool-chain-c-msvc (Windows)
  - clang-tool-chain-cpp-msvc (Windows)

Build Utilities:
  - clang-tool-chain-build
  - clang-tool-chain-build-run
  - clang-tool-chain-run

Binary Utilities:
  - clang-tool-chain-ar
  - clang-tool-chain-nm
  - clang-tool-chain-objdump
  - clang-tool-chain-strip
  - clang-tool-chain-readelf
  ... (11 total)

Analysis & Formatting:
  - clang-tool-chain-format
  - clang-tool-chain-tidy
  - clang-tool-chain-iwyu

Debugging:
  - clang-tool-chain-lldb

WebAssembly:
  - clang-tool-chain-emcc
  - clang-tool-chain-empp

Cosmopolitan:
  - clang-tool-chain-cosmocc
  - clang-tool-chain-cosmocpp

Management:
  - clang-tool-chain-test
  - clang-tool-chain-fetch
  - clang-tool-chain-paths
```

## Common Workflows

### CI/CD Validation

```bash
# Verify installation in CI
clang-tool-chain info
clang-tool-chain test

# Pre-fetch binaries
clang-tool-chain-fetch
```

### Scripting Integration

```bash
#!/bin/bash
# get_clang_path.sh

# Get clang path for custom build system
CLANG_PATH=$(clang-tool-chain-paths | jq -r '.clang')
echo "Using clang at: $CLANG_PATH"

# Use in build
$CLANG_PATH -O2 main.c -o program
```

### Offline Setup

```bash
# On internet-connected machine
clang-tool-chain-fetch --dry-run  # See what will be downloaded
clang-tool-chain-fetch            # Download
clang-tool-chain install clang    # Install

# Package ~/.clang-tool-chain/ directory
tar czf clang-toolchain.tar.gz ~/.clang-tool-chain/

# On offline machine
tar xzf clang-toolchain.tar.gz -C ~
clang-tool-chain test  # Verify
```

### Debugging Installation Issues

```bash
# Full diagnostic suite
clang-tool-chain info
clang-tool-chain test
clang-tool-chain path
clang-tool-chain version clang

# Check what would be downloaded
clang-tool-chain-fetch --dry-run

# Verify paths in scripts
clang-tool-chain-paths | jq .
```

## Related Documentation

- [Management CLI](MANAGEMENT_CLI.md) - Install/purge commands
- [Installation Guide](INSTALLATION.md) - Installation options
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
- [CI/CD Integration](CICD_INTEGRATION.md) - Automation examples
