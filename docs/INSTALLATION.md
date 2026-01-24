# Installation Guide

Complete guide to installing and configuring clang-tool-chain.

## From PyPI (Recommended)

```bash
pip install clang-tool-chain
```

That's it! The toolchain downloads automatically on first use.

## From Source

```bash
# Clone the repository
git clone https://github.com/zackees/clang-tool-chain.git
cd clang-tool-chain

# Install dependencies
./install

# Or manually with uv
uv venv --python 3.11
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

**macOS Users:** Requires Xcode Command Line Tools for system headers. Run `xcode-select --install` if not already installed.

## Installation Options

### Option 1: Auto-Download (Recommended)

The toolchain downloads automatically on first use - no setup needed!

```bash
pip install clang-tool-chain
clang-tool-chain-c hello.c -o hello  # Downloads toolchain on first use
```

**What happens on first use:**
1. Downloads toolchain archive (~71-91 MB) from GitHub
2. Verifies SHA256 checksum
3. Extracts to `~/.clang-tool-chain/`
4. Executes your command

### Option 2: Pre-Install Toolchain

Download the toolchain before use (useful for CI/CD or offline work):

```bash
# Pre-download just the core Clang/LLVM toolchain
clang-tool-chain install clang

# This downloads ~71-91 MB and does NOT include:
# - IWYU (downloads ~53-57 MB on first use of clang-tool-chain-iwyu)
# - LLDB (downloads ~10-35 MB on first use of clang-tool-chain-lldb)
# - Emscripten (downloads on first use of clang-tool-chain-emcc)
# - Node.js (downloads with Emscripten)
# - Cosmopolitan (downloads on first use of clang-tool-chain-cosmocc)
```

**Pre-install all tools:**
```bash
clang-tool-chain install clang      # Core toolchain (~71-91 MB)
clang-tool-chain install iwyu       # Include analyzer (~53-57 MB)
clang-tool-chain install lldb       # Debugger (~10-35 MB)
clang-tool-chain install emscripten # WebAssembly (~1.4 GB with Node.js)
clang-tool-chain install cosmocc    # Cosmopolitan (~40-60 MB)
```

### Option 3: Install to System PATH

Use `clang` directly without the `clang-tool-chain-` prefix:

```bash
# Add Clang/LLVM to system PATH (auto-installs if needed)
clang-tool-chain install clang-env

# Now use tools directly (after restarting terminal)
clang --version
clang++ main.cpp -o program
```

**Remove from PATH:**
```bash
clang-tool-chain uninstall clang-env  # Keeps files, removes PATH entry
```

**Remove everything:**
```bash
clang-tool-chain purge  # Deletes files + auto-removes from PATH
```

**Important Notes:**
- PATH changes require terminal restart (or log out/in)
- Works cross-platform (Windows, macOS, Linux)
- Wrapper commands (`clang-tool-chain-*`) always available
- Uses [setenvironment](https://github.com/zackees/setenvironment) for persistent PATH modification
- Tracked in SQLite database for automatic cleanup

**Future commands:**
- `install iwyu-env` - IWYU analyzer to PATH
- `install lldb-env` - LLDB debugger to PATH
- `install emscripten-env` - Emscripten WebAssembly (includes own LLVM)

## Installation Paths

| System | Install Path |
|--------|--------------|
| Windows | `~/.clang-tool-chain/clang/win/x86_64/` |
| Linux x86_64 | `~/.clang-tool-chain/clang/linux/x86_64/` |
| Linux ARM64 | `~/.clang-tool-chain/clang/linux/arm64/` |
| macOS x86_64 | `~/.clang-tool-chain/clang/darwin/x86_64/` |
| macOS ARM64 | `~/.clang-tool-chain/clang/darwin/arm64/` |

**Custom path:**
```bash
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/custom/path
```

## Upgrading

```bash
# Upgrade the package to get new LLVM versions
pip install --upgrade clang-tool-chain

# Force re-download of toolchains (uses new manifest versions)
clang-tool-chain purge --yes && clang-tool-chain install clang
```

**How upgrading works:**
- Package updates include new manifest files pointing to newer LLVM versions
- Downloaded toolchains are cached in `~/.clang-tool-chain/` and persist across package upgrades
- To get new binaries after upgrading, purge and reinstall (or delete `~/.clang-tool-chain/` manually)
- CI/CD pipelines typically get fresh downloads on each run (no cached toolchains)

## Optional Dependencies

### sccache (Compilation Caching)

```bash
# Install with sccache support
pip install clang-tool-chain[sccache]

# Or install sccache separately
cargo install sccache        # Via Rust's cargo
brew install sccache         # macOS
apt install sccache          # Debian/Ubuntu
```

See [sccache Integration](SCCACHE.md) for details.

### Development Dependencies

```bash
# Install with development tools (testing, linting)
pip install clang-tool-chain[dev]

# Or from source
./install  # Runs: uv pip install -e ".[dev]"
```

## Verification

After installation, verify everything works:

```bash
# Show installation info
clang-tool-chain info

# Run diagnostic tests
clang-tool-chain test

# Test a simple compilation
echo '#include <stdio.h>' > test.c
echo 'int main() { printf("Hello!\n"); return 0; }' >> test.c
clang-tool-chain-c test.c -o test
./test
```

## Uninstallation

```bash
# Remove all downloaded toolchains
clang-tool-chain purge --yes

# Uninstall Python package
pip uninstall clang-tool-chain
```

## Platform-Specific Notes

### Windows

- GNU ABI (default) includes MinGW-w64 sysroot (~19 MB additional download)
- MSVC ABI requires Visual Studio Build Tools (not included)
- Git Bash recommended for shebang support

### macOS

- **Required:** Xcode Command Line Tools (`xcode-select --install`)
- Automatic SDK detection via `xcrun --show-sdk-path`
- macOS ARM64 uses LLVM 21.1.6 (Homebrew build)
- macOS x86_64 uses LLVM 19.1.7 (pending upgrade to 21.x)

### Linux

- Requires glibc 2.27+ (Ubuntu 18.04+, Debian 10+, RHEL 8+)
- ARM64 supported (tested on Raspberry Pi 4, AWS Graviton)
- No additional system dependencies needed

## Offline Installation

For airgapped environments:

```bash
# 1. Download archive on internet-connected machine
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/{platform}/{arch}/llvm-*.tar.zst

# 2. Transfer and extract on target machine
mkdir -p ~/.clang-tool-chain/clang/{platform}/{arch}
python -m clang_tool_chain.downloads.expand_archive archive.tar.zst ~/.clang-tool-chain/clang/{platform}/{arch}
touch ~/.clang-tool-chain/clang/{platform}/{arch}/done.txt
```

Replace `{platform}` with `win`, `linux`, or `darwin` and `{arch}` with `x86_64` or `arm64`.

## Troubleshooting

### Common Issues

**"Command not found" after PATH installation:**
- Restart terminal or log out/in
- Check PATH: `echo $PATH` (Unix) or `echo %PATH%` (Windows)
- Verify entry: `clang-tool-chain info`

**Download failures:**
- Check internet connection
- Verify firewall/proxy settings
- Try manual download: `clang-tool-chain-fetch --dry-run`

**Permission errors:**
- Ensure write access to `~/.clang-tool-chain/`
- On Windows, run terminal as Administrator if needed
- Check disk space: ~500 MB required

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more solutions.

## Related Documentation

- [Platform Support](PLATFORM_SUPPORT.md) - System requirements
- [Configuration](CONFIGURATION.md) - Environment variables
- [Management CLI](MANAGEMENT_CLI.md) - Install/uninstall commands
