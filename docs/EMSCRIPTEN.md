# Emscripten (WebAssembly Compilation)

This package provides Emscripten integration for compiling C/C++ to WebAssembly (WASM). Emscripten is automatically downloaded and installed on first use, similar to the LLVM toolchain.

## Key Features

- Pre-built Emscripten SDK (~160-195 MB compressed, ~1.4 GB installed)
- Automatic download and installation on first use
- WebAssembly compilation (C/C++ → .wasm + .js + .html)
- Cross-platform support (Windows x64, macOS x64/ARM64, Linux x64/ARM64)
- Manifest-based distribution with SHA256 verification
- Compatible with Node.js for running WebAssembly output

## Platform Support

| Platform | Architecture | Emscripten Version | Archive Size | Status |
|----------|-------------|-------------------|--------------|--------|
| macOS    | x86_64      | 4.0.19            | 166 MB       | ✅ Available |
| macOS    | arm64       | 4.0.19            | 160 MB       | ✅ Available |
| Windows  | x86_64      | 4.0.19            | 153 MB       | ✅ Available |
| Linux    | x86_64      | 4.0.15            | 195 MB       | ✅ Available |
| Linux    | arm64       | -                 | -            | ⏳ Pending |

*macOS support added November 16, 2025*

## Wrapper Commands

## sccache Integration (Compiler Caching)

sccache provides compilation caching for faster rebuilds. The package includes special wrappers that integrate sccache with Emscripten using the `EM_COMPILER_WRAPPER` environment variable.

**Requirements:**
- sccache must be installed separately (not bundled)
- Install via: `cargo install sccache` or from https://github.com/mozilla/sccache/releases

**Commands:**
```bash
# Compile C to WebAssembly with sccache caching
clang-tool-chain-sccache-emcc hello.c -o hello.html

# Compile C++ to WebAssembly with sccache caching
clang-tool-chain-sccache-empp hello.cpp -o hello.html

# View sccache statistics
sccache --show-stats
```

**How it works:**
- Sets `EM_COMPILER_WRAPPER=sccache` to wrap Emscripten's internal Clang calls
- Sets `EMCC_SKIP_SANITY_CHECK=1` (sanity checks don't work with compiler wrappers)
- Maintains all standard Emscripten environment configuration
- Caches compilation results for faster subsequent builds

**Performance benefits:**
- First build: Same as regular emcc/em++ (cache miss)
- Subsequent builds: 10-100x faster (cache hit)
- Shared cache across different projects using same compilation flags

**Example workflow:**
```bash
# First build (cache miss, ~10 seconds)
clang-tool-chain-sccache-emcc -O3 hello.c -o hello.html

# Modify unrelated file and rebuild (cache hit, <1 second)
clang-tool-chain-sccache-emcc -O3 hello.c -o hello.html

# Check cache statistics
sccache --show-stats
```


```bash
# Compile C to WebAssembly
clang-tool-chain-emcc hello.c -o hello.html

# Compile C++ to WebAssembly
clang-tool-chain-empp hello.cpp -o hello.html

# Compile to .wasm and .js (no HTML)
clang-tool-chain-empp hello.cpp -o hello.js

# With optimization
clang-tool-chain-empp -O3 hello.cpp -o hello.html
```

## What's Included

- Emscripten Python scripts (emcc, em++, emconfigure, emmake)
- **LLVM 22 binaries with WebAssembly backend** (bundled with Emscripten, not shared with clang-tool-chain)
- Binaryen tools (wasm-opt, wasm-as, etc.)
- System libraries (libc, libc++, libcxxabi)
- **Node.js runtime** (bundled automatically, ~23-24 MB)

**Note on LLVM Version:** Emscripten uses its own bundled LLVM binaries (LLVM 22 for Emscripten 4.0.19) rather than sharing clang-tool-chain's LLVM 21.1.5. This ensures version compatibility between Emscripten's Python scripts and the LLVM toolchain. The two LLVM installations coexist independently.

## Requirements

- **Node.js** is bundled automatically for running compiled WebAssembly programs
- Falls back to system Node.js if available
- No manual installation required (downloads on first use)
- See [Node.js Integration](NODEJS.md) for details

## Installation Paths

- Installation directory: `~/.clang-tool-chain/emscripten/{platform}/{arch}/`
- Success marker: `~/.clang-tool-chain/emscripten/{platform}/{arch}/done.txt`

## Environment Variables

The wrapper automatically sets required environment variables:
- `EMSCRIPTEN` - Points to Emscripten installation directory
- `EMSCRIPTEN_ROOT` - Same as above (for compatibility)

## Example Usage

```cpp
// hello_world.cpp
#include <iostream>

int main() {
    std::cout << "Hello, WebAssembly!" << std::endl;
    return 0;
}
```

```bash
# Compile to WebAssembly
clang-tool-chain-empp hello_world.cpp -o hello.html

# Run with Node.js
node hello.js

# Or open hello.html in a browser
```

## Output Files

- `hello.html` - HTML page that loads and runs the WASM module
- `hello.js` - JavaScript glue code for WASM instantiation
- `hello.wasm` - WebAssembly binary module

## Architecture

Emscripten integration follows the same three-layer architecture as LLVM/Clang:

1. **CLI Layer**: Management commands via `clang-tool-chain` CLI
2. **Wrapper Layer**: Entry points `emcc_main()` and `empp_main()` in `wrapper.py`
   - Platform detection (win/linux/darwin)
   - Node.js availability check
   - Environment variable setup (EMSCRIPTEN, EMSCRIPTEN_ROOT)
   - Executes Emscripten Python scripts via Python interpreter
3. **Downloader Layer**: Automatic download from GitHub
   - Fetches manifests: `downloads-bins/assets/emscripten/manifest.json`
   - Downloads `.tar.zst` archives (~195 MB)
   - Verifies SHA256 checksums
   - Extracts to `~/.clang-tool-chain/emscripten/{platform}/{arch}/`
   - File locking prevents concurrent downloads

### LLVM Separation

clang-tool-chain provides two separate LLVM installations:

1. **Main LLVM Toolchain (LLVM 21.1.5)** - Located at `~/.clang-tool-chain/{platform}/{arch}/`
   - Used for: `clang`, `clang++`, `clang-format`, `clang-tidy`, etc.
   - Purpose: Native compilation for the target platform

2. **Emscripten LLVM (LLVM 22)** - Located at `~/.clang-tool-chain/emscripten/{platform}/{arch}/`
   - Used for: WebAssembly compilation via Emscripten
   - Purpose: WebAssembly compilation (bundled with Emscripten distribution)
   - Installed: Extracted from Emscripten archive (not linked from main LLVM)

This separation ensures that each tool uses the LLVM version it was designed for, avoiding version mismatch errors.

### Why Not Share LLVM?

Previously, clang-tool-chain attempted to share LLVM binaries between the main toolchain and Emscripten to save space (~200-400 MB). However, this caused version mismatches:

- Emscripten 4.0.19 expects LLVM 22
- Main toolchain provides LLVM 21.1.5
- Result: "LLVM version mismatch" errors

**Design Decision:** Correctness > Space Savings

Emscripten distributions are designed to be self-contained. By using Emscripten's bundled LLVM, we ensure version compatibility and follow upstream's intended architecture.

## Key Differences from LLVM Integration

1. **Script-based, not binary-based**: Emscripten tools are Python scripts, not native executables
2. **Executes via Python**: Wrapper runs `python emcc.py args...` instead of direct binary execution
3. **Node.js dependency**: Bundled automatically (no manual installation)
4. **Larger size**: ~195 MB compressed vs ~52-91 MB for LLVM (includes full SDK)

## Emscripten Version

- Current version: 4.0.15 (Linux x86_64)
- Additional platforms (Windows, macOS) to be added in future releases

## Testing

```bash
# Run Emscripten tests (requires Node.js)
uv run pytest tests/test_emscripten.py -v

# Test classes:
# - TestEmscripten: Compilation and execution tests
# - TestEmscriptenDownloader: Infrastructure tests
```

## Common Issues

1. **Node.js download fails**: Bundled Node.js will download automatically on first use
   ```bash
   # If automatic download fails, install manually:
   # Windows: https://nodejs.org/
   # macOS: brew install node
   # Linux: apt install nodejs (Debian/Ubuntu)

   # Verify installation:
   node --version

   # Wrapper will fall back to system Node.js
   ```

2. **First compilation is slow**: Emscripten downloads system libraries on first use
   - Subsequent compilations are faster (~2-10 seconds)
   - Cache directory: `~/.emscripten_cache/`

3. **Large output files**: WebAssembly output includes JS glue code
   - Use `-O3` optimization flag to reduce size
   - Use `--closure 1` for advanced JavaScript minification
   - Consider `-s MODULARIZE=1` for better JS integration

## Future Enhancements

- Windows x86_64 archive (pending)
- macOS x86_64 and ARM64 archives (pending)
- Support for `emrun` wrapper command
- Integration with CMake via emconfigure/emmake
