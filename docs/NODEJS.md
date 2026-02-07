# Node.js Integration (Bundled)

<!-- AGENT: Read this file when working on bundled Node.js runtime for WebAssembly execution.
     Key topics: Node.js download, version management, Emscripten runtime dependency.
     Related: docs/EMSCRIPTEN.md. -->

**Summary:** Node.js is automatically bundled with this package for running WebAssembly programs compiled with Emscripten. Users no longer need to install Node.js manually.

## Key Features

- Minimal Node.js runtime (~23-24 MB per platform)
- Automatic download on first use
- Falls back to system Node.js if available
- No manual installation required
- Same manifest-based distribution as LLVM/Clang

## Automatic Bundling Behavior

When you run Emscripten commands (emcc, em++), the wrapper:

1. **Checks for bundled Node.js first** (preferred)
   - Location: `~/.clang-tool-chain/nodejs/{platform}/{arch}/bin/node`
   - Fast path: <1ms overhead

2. **Falls back to system Node.js** (if bundled not found)
   - Uses `node` from PATH
   - Respects existing installations

3. **Auto-downloads if neither exists** (automatic, one-time)
   - Downloads minimal Node.js runtime (~23-24 MB)
   - Shows clear progress messages
   - Takes ~10-30 seconds (network dependent)

## Supported Platforms

- Windows x86_64 (Node.js 22.11.0 LTS)
- Linux x86_64 (Node.js 22.11.0 LTS)
- Linux ARM64 (Node.js 22.11.0 LTS)
- macOS x86_64 (Node.js 22.11.0 LTS)
- macOS ARM64 (Node.js 22.11.0 LTS)

## Installation Paths

- Base directory: `~/.clang-tool-chain/nodejs/{platform}/{arch}/`
- Binary location: `~/.clang-tool-chain/nodejs/{platform}/{arch}/bin/node[.exe]`
- Success marker: `~/.clang-tool-chain/nodejs/{platform}/{arch}/done.txt`

## Archive Sizes (compressed with zstd level 22)

- Windows x86_64: ~23-24 MB
- Linux x86_64: ~23-24 MB (estimated)
- Linux ARM64: ~23-24 MB (estimated)
- macOS x86_64: ~24-25 MB (estimated)
- macOS ARM64: ~23-24 MB (estimated)
- **Total download:** ~117 MB (all platforms)

## What's Included

- Node.js binary (`node` or `node.exe`)
- Core runtime libraries (`lib/node_modules`)
- LICENSE file
- **Stripped out:** include/, share/, README, CHANGELOG

## Usage

Node.js bundling is completely automatic. Just run Emscripten commands:

```bash
# Compile C++ to WebAssembly
clang-tool-chain-empp hello.cpp -o hello.html

# If Node.js not found, you'll see:
# ============================================================
# Downloading Node.js Runtime
# ============================================================
# Node.js not found in system PATH.
# Downloading minimal Node.js runtime (~23-24 MB)...
# Platform: linux / Architecture: x86_64
# This is a one-time download.
#
# [Download progress...]
#
# ============================================================
# Node.js installation complete!
# Location: /home/user/.clang-tool-chain/nodejs/linux/x86_64/bin/node
# ============================================================

# Run compiled WebAssembly
node hello.js
```

## Environment Variables

Override default download location:
```bash
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/custom/path
```

## Fallback to System Node.js

If you prefer using your system Node.js installation:

1. Install Node.js: https://nodejs.org/
2. Ensure `node` is in PATH
3. Remove bundled Node.js (optional):
   ```bash
   rm -rf ~/.clang-tool-chain/nodejs/
   ```
4. Run Emscripten commands - will use system Node.js

## Version Information

- Bundled version: Node.js 22.11.0 LTS "Jod"
- Support timeline: Until 2027-04-30 (Long Term Support)
- Update frequency: LTS releases only (stability priority)

## Testing

```bash
# Test Node.js bundling infrastructure
uv run pytest tests/test_nodejs_downloader.py -v

# Test Emscripten with bundled Node.js
uv run pytest tests/test_emscripten.py -v
```

## Architecture

Node.js bundling follows the same three-layer architecture:

1. **CLI Layer**: Management via `clang-tool-chain` CLI
2. **Wrapper Layer**: `ensure_nodejs_available()` in `wrapper.py`
   - Three-tier priority: bundled > system > auto-download
   - PATH modification for Emscripten
   - Clear error messages with workarounds
3. **Downloader Layer**: Automatic download from GitHub
   - Fetches manifests: `downloads-bins/assets/nodejs/manifest.json`
   - Downloads `.tar.zst` archives (~23-24 MB)
   - Verifies SHA256 checksums
   - Extracts to `~/.clang-tool-chain/nodejs/{platform}/{arch}/`
   - File locking prevents concurrent downloads

## Common Issues

1. **Download fails**: Falls back to system Node.js or shows installation instructions
   ```bash
   # Workaround: Install Node.js manually
   # Windows: https://nodejs.org/
   # macOS: brew install node
   # Linux: apt install nodejs
   ```

2. **Want to use system Node.js**: Remove bundled version or set PATH priority
   ```bash
   rm -rf ~/.clang-tool-chain/nodejs/
   ```

3. **Check which Node.js is being used**: Look for log messages
   ```bash
   # Wrapper logs which Node.js it finds:
   # "Using bundled Node.js: /home/user/.clang-tool-chain/nodejs/linux/x86_64/bin/node"
   # or
   # "Using system Node.js: /usr/bin/node"
   ```

## Comparison with System Node.js

| Feature | Bundled Node.js | System Node.js |
|---------|-----------------|----------------|
| Installation | Automatic | Manual |
| Size | ~23-24 MB | ~60-90 MB (full) |
| npm included | Yes (minimal) | Yes |
| Version control | Locked to LTS | User-managed |
| Updates | Package updates | System updates |
| Isolation | Per-package | System-wide |

## Future Enhancements

- Automatic version updates with LTS releases
- Optional stripped npm for smaller downloads
