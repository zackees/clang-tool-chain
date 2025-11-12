# Architecture

This document describes the technical architecture of the clang-tool-chain package.

## Core Components

### Manifest-Based Distribution System

- Binary archives stored in separate repository as git submodule (`downloads-bins/`)
- Root manifest indexes all platforms/architectures
- Platform-specific manifests specify versions, download URLs, and SHA256 checksums
- Toolchains are distributed as `.tar.zst` archives (~52 MB for Windows x64)
- First tool execution triggers automatic download from GitHub and installation to `~/.clang-tool-chain/`
- Binary repository: https://github.com/zackees/clang-tool-chain-bins

### ⚠️ Git LFS Cannot Be Used

- GitHub's LFS requires authentication for downloads, breaking anonymous access
- Files over 100 MB cannot be stored in regular Git repositories
- **Solution**: Large archives (>100 MB) must be split into parts (<100 MB each)
- Format: `archive-name.tar.zst.part1`, `archive-name.tar.zst.part2`, etc.
- Downloader concatenates parts before extraction
- Manifest specifies part count and individual checksums for verification

### Multi-Part Archive Support

For archives exceeding GitHub's 100 MB file size limit, the package implements transparent multi-part archive handling:

**Key Features:**
- Archives automatically split into <100 MB parts (default: 95 MB per part)
- Transparent to end users - downloads and extraction happen automatically
- SHA256 checksum verification for each part and final concatenated archive
- Backward compatible - single-file archives continue to work without changes
- No Git LFS required - parts stored directly in repository

**Manifest Format:**
```json
{
  "version": "4.0.15",
  "href": "https://raw.githubusercontent.com/.../archive.tar.zst",
  "sha256": "full-archive-checksum",
  "parts": [
    {
      "href": "https://raw.githubusercontent.com/.../archive.tar.zst.part1",
      "sha256": "part1-checksum"
    },
    {
      "href": "https://raw.githubusercontent.com/.../archive.tar.zst.part2",
      "sha256": "part2-checksum"
    }
  ]
}
```

**Download Flow:**
1. Downloader detects "parts" field in manifest
2. Downloads each part with individual checksum verification
3. Concatenates parts into single archive
4. Verifies final archive checksum matches "sha256" field
5. Extracts using standard `.tar.zst` extraction

**Implementation:**
- `downloader.py:is_multipart_archive()` - Detects multi-part archives
- `downloader.py:download_archive_parts()` - Downloads and concatenates parts
- `downloader.py:download_archive()` - Unified interface for both types
- All download functions (clang, mingw, emscripten, iwyu) support both formats

**Maintainer Tools:**
- `downloads-bins/tools/split_archive.py` - Splits archives into parts
- Generates SHA256 checksums for each part
- Optionally updates manifest with part information
- Usage: `python split_archive.py archive.tar.zst --part-size-mb 95`

**Use Cases:**
- Emscripten SDK (~195 MB) → 3 parts (~95 MB, ~95 MB, ~5 MB)
- Future LLVM releases if they exceed 100 MB
- Any toolchain archive that cannot be stored in regular Git

## Three-Layer Architecture

1. **CLI Layer** (`cli.py`): Main entry point providing management commands
   - `info`: Display installation information and available tools
   - `version <tool>`: Show version of a specific tool
   - `list-tools`: List all wrapper commands
   - `path [tool]`: Show binary directory or tool path
   - `package-version`: Display package and LLVM versions

2. **Wrapper Layer** (`wrapper.py`): Core tool execution infrastructure
   - Platform detection: Automatically detects OS (win/linux/darwin) and architecture (x86_64/arm64)
   - Binary resolution: Finds tool binaries with platform-specific extensions
   - Process execution: Uses `os.execv` on Unix, `subprocess.run` on Windows
   - Provides 14 wrapper entry points (clang, clang++, lld, llvm-ar, llvm-nm, etc.)

3. **Downloader Layer** (`downloader.py`): Automatic toolchain installation
   - Fetches manifests from clang-tool-chain-bins repository on GitHub
   - Downloads archives with checksum verification (SHA256)
   - Extracts `.tar.zst` archives using pyzstd decompression
   - Uses file locking (`fasteners.InterProcessLock`) to prevent concurrent downloads
   - Installation path: `~/.clang-tool-chain/clang/<platform>/<arch>/`
   - MinGW sysroot path: `~/.clang-tool-chain/mingw/win/x86_64/` (Windows only)
   - Marks successful installation with `done.txt` file

## Directory Structure

```
clang-tool-chain/
├── src/clang_tool_chain/
│   ├── cli.py               # Main CLI commands (info, version, list-tools, path)
│   ├── wrapper.py           # Tool execution wrappers and entry points
│   ├── downloader.py        # Automatic download/install from manifests
│   ├── checksums.py         # Checksum database for LLVM releases
│   ├── fetch.py             # Fetch utility command
│   ├── paths.py             # Path utility command
│   ├── downloads/           # Maintainer tools for packaging
│   │   ├── fetch_and_archive.py    # Complete packaging pipeline
│   │   ├── download_binaries.py    # Download LLVM releases
│   │   ├── strip_binaries.py       # Optimize binary size
│   │   ├── deduplicate_binaries.py # Find duplicate binaries
│   │   ├── create_hardlink_archive.py # Create hardlinked tarballs
│   │   ├── expand_archive.py       # Extract .tar.zst archives
│   │   └── test_compression.py     # Test compression methods
│   └── __version__.py       # Version information
├── downloads-bins/          # Git submodule with pre-built archives and manifests
│   └── assets/              # Published binary distributions
│       ├── clang/           # Clang toolchain archives
│       │   ├── manifest.json    # Root manifest (all platforms)
│       │   ├── win/         # Windows archives and manifest
│       │   │   ├── x86_64/
│       │   │   │   ├── manifest.json
│       │   │   │   └── llvm-21.1.5-win-x86_64.tar.zst
│       │   ├── linux/       # Linux archives
│       │   └── darwin/      # macOS archives
│       ├── mingw/           # MinGW-w64 sysroot archives (Windows GNU ABI)
│       │   ├── manifest.json    # Root manifest
│       │   ├── README.md    # MinGW sysroot documentation
│       │   └── win/         # Windows MinGW sysroots
│       │       └── x86_64/
│       │           ├── manifest.json
│       │           └── mingw-sysroot-21.1.5-win-x86_64.tar.zst
│       └── iwyu/            # Include What You Use archives
├── tests/                   # Unit and integration tests
│   ├── test_cli.py          # CLI command tests
│   ├── test_downloader.py   # Download/install tests
│   ├── test_build_tools.py  # Build tool tests
│   ├── test_integration.py  # End-to-end tests
│   ├── test_manifest.py     # Manifest parsing tests
│   └── test_gnu_abi.py      # Windows GNU ABI tests (TASK.md scenarios)
├── pyproject.toml           # Package configuration
└── .pre-commit-config.yaml  # Pre-commit hooks
```

## Platform Detection and Binary Resolution

The wrapper system (`wrapper.py`) performs automatic platform detection:

1. **Platform normalization:**
   - Windows → "win"
   - Linux → "linux"
   - macOS (Darwin) → "darwin"

2. **Architecture normalization:**
   - x86_64, amd64 → "x86_64"
   - aarch64, arm64 → "arm64"

3. **Binary location:** `~/.clang-tool-chain/clang/<platform>/<arch>/bin/`

4. **Tool resolution:**
   - Adds `.exe` extension on Windows
   - Handles alternative names (e.g., `lld` → `lld-link` on Windows)
   - Provides detailed error messages with available tools list

## Automatic Download Flow

When a wrapper command is executed for the first time:

1. Check if toolchain is installed (`done.txt` exists)
2. If not installed, acquire file lock (`~/.clang-tool-chain/<platform>-<arch>.lock`)
3. Double-check installation (another process may have finished)
4. Fetch root manifest from GitHub
5. Fetch platform-specific manifest
6. Download archive to temp directory with checksum verification
7. Extract using pyzstd decompression + tarfile
8. Write `done.txt` to mark completion
9. Release lock and execute tool

## Environment Variables

- **`CLANG_TOOL_CHAIN_DOWNLOAD_PATH`**: Override default download location (`~/.clang-tool-chain`)
  - Useful for testing, shared installations, or network drives
