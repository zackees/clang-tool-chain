# How It Works

Understanding the clang-tool-chain architecture and download process.

## Overview

clang-tool-chain provides a Python wrapper around pre-built Clang/LLVM binaries. On first use, it automatically downloads, verifies, and extracts the appropriate binaries for your platform.

## First Use Workflow

When you run a clang-tool-chain command for the first time:

```bash
clang-tool-chain-cpp hello.cpp -o hello
```

**What happens:**

1. **Platform Detection**
   - Detects OS (Windows, macOS, Linux)
   - Detects architecture (x86_64, ARM64)
   - Selects appropriate manifest

2. **Download**
   - Fetches manifest JSON from GitHub
   - Downloads binary archives (~71-91 MB compressed)
   - Uses parallel HTTP range requests for 3-5x speedup
   - Shows progress bar

3. **Verification**
   - Verifies SHA256 checksums against version-controlled hashes
   - Ensures integrity and authenticity

4. **Extraction**
   - Extracts archives to `~/.clang-tool-chain/`
   - Uses Python 3.12+ tarfile safety filters (prevents path traversal)
   - File locking prevents race conditions in parallel builds

5. **Execution**
   - Executes the requested tool with your arguments
   - Platform-specific setup (SDK detection on macOS, MinGW on Windows, etc.)

**Time:** 10-60 seconds depending on internet speed.

**Subsequent uses:** Instant! Binaries are cached locally.

## Installation Paths

Binaries are installed to platform-specific directories:

| Platform | Install Path |
|----------|--------------|
| Windows x64 | `~/.clang-tool-chain/clang/win/x86_64/` |
| Linux x86_64 | `~/.clang-tool-chain/clang/linux/x86_64/` |
| Linux ARM64 | `~/.clang-tool-chain/clang/linux/arm64/` |
| macOS x86_64 | `~/.clang-tool-chain/clang/darwin/x86_64/` |
| macOS ARM64 | `~/.clang-tool-chain/clang/darwin/arm64/` |

**Tool-specific paths:**
- Emscripten: `~/.clang-tool-chain/emscripten/{platform}/{arch}/`
- IWYU: `~/.clang-tool-chain/iwyu/{platform}/{arch}/`
- LLDB: `~/.clang-tool-chain/lldb/{platform}/{arch}/`
- Cosmocc: `~/.clang-tool-chain/cosmocc/universal/` (all platforms)
- Node.js: `~/.clang-tool-chain/nodejs/{platform}/{arch}/`

## Architecture Layers

clang-tool-chain has a three-layer architecture:

### Layer 1: Entry Points (`pyproject.toml`)

Console scripts defined in `pyproject.toml` create command-line executables:

```toml
[project.scripts]
clang-tool-chain-cpp = "clang_tool_chain.wrapper:clang_cpp_main"
clang-tool-chain-c = "clang_tool_chain.wrapper:clang_c_main"
```

When installed via pip, these become executable commands in your PATH.

### Layer 2: Wrapper Functions (`src/clang_tool_chain/wrapper.py`)

Wrapper functions parse arguments and delegate to installers:

```python
def clang_cpp_main():
    # Parse args, detect platform, invoke installer
    installer = ClangInstaller()
    installer.install()
    # Execute clang++ with user args
```

### Layer 3: Installers (`src/clang_tool_chain/installers/`)

Installers handle downloading, verification, and extraction:

- **`clang.py`** - Clang/LLVM binaries
- **`emscripten.py`** - Emscripten SDK
- **`iwyu.py`** - Include What You Use
- **`lldb.py`** - LLDB debugger
- **`cosmocc.py`** - Cosmopolitan Libc
- **`nodejs.py`** - Node.js runtime

Each installer:
- Fetches manifest from GitHub
- Downloads archives with checksum verification
- Extracts to platform-specific directory
- Returns binary paths for execution

## Manifest System

Manifests are JSON files hosted on GitHub that define binary archives:

**Example manifest structure:**

```json
{
  "version": "21.1.5",
  "archives": {
    "win-x86_64": {
      "url": "https://github.com/.../clang-win-x86_64.tar.zst",
      "sha256": "abc123...",
      "size": 91234567
    },
    "linux-x86_64": {
      "url": "https://github.com/.../clang-linux-x86_64.tar.zst",
      "sha256": "def456...",
      "size": 87654321
    }
  }
}
```

**Manifest locations:**
- Clang: `manifest_urls.py::CLANG_MANIFEST_URL`
- Emscripten: `manifest_urls.py::EMSCRIPTEN_MANIFEST_URL`
- IWYU: `manifest_urls.py::IWYU_MANIFEST_URL`
- LLDB: `manifest_urls.py::LLDB_MANIFEST_URL`
- Cosmocc: `manifest_urls.py::COSMOCC_MANIFEST_URL`
- Node.js: `manifest_urls.py::NODEJS_MANIFEST_URL`

## Binary Compression

Archives use **zstd level 22** compression for maximum size reduction:

| Uncompressed | Compressed | Ratio |
|--------------|------------|-------|
| ~1.2 GB (LLVM binaries) | ~71-91 MB | ~94% reduction |
| ~6.5 GB (Emscripten) | ~1.4 GB | ~78% reduction |

**Benefits:**
- Faster downloads (smaller files)
- Lower bandwidth costs
- Same extraction speed as gzip

## Parallel Downloads

Downloads use **HTTP range requests** with multiple threads:

```python
# Download 3 chunks in parallel
chunk1 = download_range(url, 0, 10_000_000)      # Thread 1
chunk2 = download_range(url, 10_000_001, 20_000_000)  # Thread 2
chunk3 = download_range(url, 20_000_001, 30_000_000)  # Thread 3

# Reassemble
with open(file, 'wb') as f:
    f.write(chunk1 + chunk2 + chunk3)
```

**Speedup:** 3-5x faster than single-threaded downloads on fast connections.

See [Parallel Downloads Documentation](PARALLEL_DOWNLOADS.md) for implementation details.

## Concurrent Safety

File locking prevents race conditions when multiple processes try to download simultaneously:

```python
from fasteners import InterProcessLock

lock = InterProcessLock('/tmp/clang-tool-chain.lock')
with lock:
    # Only one process can download at a time
    if not is_installed():
        download_and_extract()
```

**Benefits:**
- Safe for parallel builds (make -j8, ninja, etc.)
- No duplicate downloads
- No corrupted installations

## Platform-Specific Setup

### macOS SDK Detection

On macOS, clang-tool-chain automatically detects the SDK:

```python
# Auto-detect via xcrun
sdk_path = run_command(['xcrun', '--show-sdk-path'])

# Add to compiler args
args = ['-isysroot', sdk_path] + user_args
```

**Requirement:** Xcode Command Line Tools (`xcode-select --install`)

**Fallback:** If xcrun fails, uses system default includes.

See [Clang/LLVM Documentation](CLANG_LLVM.md) for details.

### Windows MinGW Integration

Windows uses integrated MinGW headers and libraries (GNU ABI by default):

```python
# MinGW headers included in Clang archive
mingw_include = install_dir / 'include'
mingw_lib = install_dir / 'lib'

# Auto-added to compiler search paths
args = [
    f'-I{mingw_include}',
    f'-L{mingw_lib}',
    '-fuse-ld=lld'  # Fast LLD linker
] + user_args
```

**No separate MinGW download required** - everything in one archive!

**DLL Deployment:** After linking, required MinGW DLLs are automatically copied to the executable directory.

See [DLL Deployment Documentation](DLL_DEPLOYMENT.md) for details.

### Linux

No special setup! Works out of the box with glibc 2.27+ systems.

## Execution Flow

**Complete workflow from command to binary execution:**

```
User runs: clang-tool-chain-cpp hello.cpp -o hello
    ↓
Entry point: clang_cpp_main() in wrapper.py
    ↓
Platform detection: Windows x64 / Linux x86_64 / macOS ARM64 / etc.
    ↓
Installer: ClangInstaller.install()
    ↓
Check if installed: ~/.clang-tool-chain/clang/{platform}/{arch}/bin/clang++
    ↓
If not installed:
  - Fetch manifest JSON
  - Download archive (with parallel range requests)
  - Verify SHA256 checksum
  - Extract to install directory
  - Set executable permissions
    ↓
Platform-specific setup:
  - macOS: Detect SDK via xcrun
  - Windows: Add MinGW headers/libs, set up LLD linker
  - Linux: Standard LLVM configuration
    ↓
Build command: /path/to/clang++ [platform-flags] hello.cpp -o hello
    ↓
Execute: subprocess.run([clang_binary, *args])
    ↓
Post-processing (Windows GNU ABI only):
  - Detect required MinGW DLLs via llvm-objdump
  - Copy DLLs to executable directory
    ↓
Success! Executable ready to run
```

## Offline Mode

After first download, clang-tool-chain works completely offline:

```bash
# First use (requires internet)
clang-tool-chain-cpp hello.cpp -o hello

# Subsequent uses (works offline)
clang-tool-chain-cpp world.cpp -o world  # No internet needed!
```

Binaries are cached in `~/.clang-tool-chain/` and reused indefinitely.

See [Advanced Topics](ADVANCED.md) for airgapped environment setup.

## Version Pinning

Lock compiler version in `requirements.txt`:

```txt
clang-tool-chain==2.0.41
```

All team members and CI/CD get the exact same LLVM version (21.1.5 for version 2.0.41).

See [Advanced Topics](ADVANCED.md) for version management strategies.

## Security

### SHA256 Verification

All downloads are verified against version-controlled checksums:

```python
# Compute downloaded file checksum
actual_sha256 = hashlib.sha256(downloaded_file).hexdigest()

# Compare with manifest
if actual_sha256 != manifest['sha256']:
    raise SecurityError("Checksum mismatch!")
```

**Protection:** Ensures binaries haven't been tampered with.

### HTTPS Only

All downloads use encrypted HTTPS connections from GitHub infrastructure.

### Tarfile Safety Filters

Python 3.12+ tarfile safety filters prevent path traversal attacks:

```python
import tarfile

# Safe extraction (Python 3.12+)
with tarfile.open(archive, mode='r:*') as tar:
    tar.extractall(dest_dir, filter='data')  # Prevents ../../../etc/passwd
```

### Trust Model

You're trusting:
1. **LLVM Project** - Source of binaries
2. **GitHub** - Hosting and delivery
3. **Package Maintainer** - Archive creation and manifest updates

See [Security Documentation](SECURITY.md) for manual verification and responsible disclosure.

## Binary Size Optimization

Maintainers use several techniques to minimize archive size:

1. **Symbol Stripping** - Remove debug symbols from release binaries
2. **Binary Deduplication** - Hard-link identical files (ld.lld = ld64.lld)
3. **Selective Inclusion** - Only essential tools (no docs, examples, unused libraries)
4. **Ultra Compression** - zstd level 22 (~94% size reduction)

**Result:** 71-91 MB vs 1-3 GB for full LLVM distribution.

See [Maintainer Guide](MAINTAINER.md) for archive creation details.

## Multi-Part Archives

Some toolchains use multi-part archives for modularity:

**Example: Windows Clang with MinGW**
- `clang-win-x86_64-part1.tar.zst` - Clang/LLVM binaries
- `clang-win-x86_64-part2.tar.zst` - MinGW headers and libraries

Both parts extract to the same directory and are downloaded/extracted together.

**Benefits:**
- Modular updates (update MinGW without re-uploading LLVM)
- GitHub file size limits (100 MB per file for some tiers)

See [Architecture Documentation](ARCHITECTURE.md) for technical details.

## Emscripten Distribution

Emscripten uses a separate LLVM version from the main clang toolchain:

| Component | LLVM Version | Size |
|-----------|--------------|------|
| Main Clang toolchain | 21.1.5 (Windows/Linux), 21.1.6 (macOS) | 71-91 MB |
| Emscripten SDK | 22.0 (bundled with Emscripten 4.0.19/4.0.21) | ~1.4 GB |

**Why separate?** Emscripten requires specific LLVM patches and configurations for WebAssembly.

**Installation:**
- Main Clang: `~/.clang-tool-chain/clang/{platform}/{arch}/`
- Emscripten: `~/.clang-tool-chain/emscripten/{platform}/{arch}/`

See [Emscripten Documentation](EMSCRIPTEN.md) for details.

## Node.js Bundling

Node.js is bundled with Emscripten for WebAssembly execution:

**Download:** Happens automatically with Emscripten (no separate install needed)

**Location:** `~/.clang-tool-chain/nodejs/{platform}/{arch}/`

**Usage:**
```bash
# Compile to WASM
clang-tool-chain-emcc hello.c -o hello.js

# Run with bundled Node.js
node hello.js  # Uses bundled Node.js automatically
```

See [Node.js Integration](NODEJS.md) for details.

## Custom Installation Path

Override default installation location:

```bash
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/opt/clang-tool-chain
clang-tool-chain-cpp hello.cpp -o hello
```

Binaries install to `/opt/clang-tool-chain/clang/{platform}/{arch}/` instead of `~/.clang-tool-chain/`.

See [Configuration Documentation](CONFIGURATION.md) for all environment variables.

## Diagnostic Tools

Check installation status and run diagnostics:

```bash
# Show installed toolchains and paths
clang-tool-chain info

# Run 7 diagnostic tests
clang-tool-chain test

# Get JSON paths for scripting
clang-tool-chain-paths
```

See [Additional Utilities](ADDITIONAL_UTILITIES.md) for details.

## Summary

**Key concepts:**

1. **Auto-download** - Binaries download on first use
2. **Platform-specific** - Correct binaries for your OS and architecture
3. **Cached locally** - Stored in `~/.clang-tool-chain/` for offline use
4. **Verified** - SHA256 checksums prevent tampering
5. **Concurrent-safe** - File locking prevents race conditions
6. **Minimal size** - 71-91 MB via ultra compression and optimization

**Flow:** Command → Wrapper → Installer → Download → Extract → Execute

For technical architecture details, see **[Architecture Documentation](ARCHITECTURE.md)**.
