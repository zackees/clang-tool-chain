# Advanced Topics

Advanced usage patterns, edge cases, and technical details for power users.

## Table of Contents

- [Offline Mode](#offline-mode)
- [Version Pinning](#version-pinning)
- [Concurrent Safety](#concurrent-safety)
- [Manual Installation (Airgapped Environments)](#manual-installation-airgapped-environments)
- [Custom Installation Paths](#custom-installation-paths)
- [Multi-Architecture Workflows](#multi-architecture-workflows)
- [Docker Best Practices](#docker-best-practices)
- [Advanced sccache Configuration](#advanced-sccache-configuration)

## Offline Mode

clang-tool-chain works completely offline after the initial download.

### How It Works

1. **First Use (Online):** Downloads toolchain archives (~71-91 MB) from GitHub
2. **Subsequent Uses (Offline):** Uses cached binaries from `~/.clang-tool-chain/`

### Offline Verification

```bash
# Download toolchain while online
pip install clang-tool-chain
clang-tool-chain install clang

# Disconnect from network, then:
clang-tool-chain-cpp hello.cpp -o hello  # Works offline!
```

### What Works Offline

- All compilation commands
- All LLVM utilities
- Emscripten (after initial download)
- IWYU, clang-format, clang-tidy
- LLDB debugger

### What Requires Internet

- Initial toolchain download
- Package installation (`pip install clang-tool-chain`)
- Package updates (`pip install --upgrade clang-tool-chain`)
- Downloading additional toolchains (IWYU, LLDB, Emscripten)

### Airgapped Setup

See [Manual Installation](#manual-installation-airgapped-environments) below for complete airgapped environment setup.

## Version Pinning

Lock your LLVM version for reproducible builds.

### Pin in requirements.txt

```txt
# requirements.txt
clang-tool-chain==1.2.3
```

```bash
pip install -r requirements.txt
```

This ensures everyone on your team uses the same LLVM version.

### Pin in pyproject.toml

```toml
[project]
dependencies = [
    "clang-tool-chain==1.2.3",
]
```

### Check Current Version

```bash
# Package version
clang-tool-chain package-version

# LLVM version
clang-tool-chain version clang
```

### Upgrade Strategy

```bash
# List available versions
pip index versions clang-tool-chain

# Upgrade to specific version
pip install clang-tool-chain==1.2.4

# Upgrade to latest
pip install --upgrade clang-tool-chain
```

### CI/CD Version Pinning

**GitHub Actions:**
```yaml
- name: Install clang-tool-chain
  run: pip install clang-tool-chain==1.2.3
```

**GitLab CI:**
```yaml
before_script:
  - pip install clang-tool-chain==1.2.3
```

**Docker:**
```dockerfile
RUN pip install clang-tool-chain==1.2.3
```

## Concurrent Safety

clang-tool-chain uses file locking to prevent race conditions during parallel installation.

### How It Works

1. **Lock Acquisition:** First process acquires lock file (`~/.clang-tool-chain/clang/{platform}/{arch}/.lock`)
2. **Installation:** First process downloads and extracts toolchain
3. **Lock Release:** First process releases lock after creating `done.txt`
4. **Other Processes:** Wait for lock, then proceed once `done.txt` exists

### Parallel Build Safety

```bash
# All 4 processes safely trigger installation
make -j4  # Uses clang-tool-chain-cpp

# Or with pytest
pytest -n auto  # Parallel test execution
```

The first process installs the toolchain, subsequent processes wait and reuse the installation.

### Lock Timeout

Default timeout: 10 minutes

If a process crashes during installation, the lock is automatically cleaned up.

### Manual Lock Cleanup

If you encounter a stuck lock:

```bash
# Remove lock file
rm ~/.clang-tool-chain/clang/*/.*/.lock

# Or purge everything and re-download
clang-tool-chain purge --yes
```

## Manual Installation (Airgapped Environments)

Complete setup for air-gapped or offline environments.

### Step 1: Download Archives (Online Machine)

```bash
# Determine your platform and architecture
# Platforms: win, linux, darwin
# Architectures: x86_64, arm64

# Example: Linux x86_64
PLATFORM=linux
ARCH=x86_64

# Download main Clang archive
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/${PLATFORM}/${ARCH}/llvm-*.tar.zst

# Download MinGW sysroot (Windows only)
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/mingw-sysroot/win/x86_64/mingw-*.tar.zst

# Download optional toolchains (if needed)
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/iwyu/${PLATFORM}/${ARCH}/iwyu-*.tar.zst
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/lldb/${PLATFORM}/${ARCH}/lldb-*.tar.zst
wget https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/emscripten/${PLATFORM}/${ARCH}/emscripten-*.tar.zst
```

### Step 2: Transfer Archives

Copy the downloaded `.tar.zst` files to the airgapped machine via USB, network share, etc.

### Step 3: Extract on Target Machine

```bash
# Create installation directory
mkdir -p ~/.clang-tool-chain/clang/${PLATFORM}/${ARCH}

# Extract archive using Python
python -m clang_tool_chain.downloads.expand_archive \
    llvm-*.tar.zst \
    ~/.clang-tool-chain/clang/${PLATFORM}/${ARCH}

# Mark installation as complete
touch ~/.clang-tool-chain/clang/${PLATFORM}/${ARCH}/done.txt

# Windows only: Extract MinGW sysroot
mkdir -p ~/.clang-tool-chain/mingw-sysroot/win/x86_64
python -m clang_tool_chain.downloads.expand_archive \
    mingw-*.tar.zst \
    ~/.clang-tool-chain/mingw-sysroot/win/x86_64
touch ~/.clang-tool-chain/mingw-sysroot/win/x86_64/done.txt
```

### Step 4: Verify Installation

```bash
clang-tool-chain info
clang-tool-chain-cpp --version
```

### Platform-Specific Paths

| Platform | PLATFORM value | ARCH value |
|----------|----------------|------------|
| Windows x64 | `win` | `x86_64` |
| Linux x86_64 | `linux` | `x86_64` |
| Linux ARM64 | `linux` | `arm64` |
| macOS Intel | `darwin` | `x86_64` |
| macOS Apple Silicon | `darwin` | `arm64` |

## Custom Installation Paths

Override the default installation location.

### Environment Variable

```bash
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/custom/path
```

**Default:** `~/.clang-tool-chain/`

### Use Cases

- **Shared team directory:** `/opt/clang-tool-chain/` (with proper permissions)
- **CI/CD cache:** `/ci-cache/clang-tool-chain/` (for faster builds)
- **Network storage:** `/mnt/shared/clang-tool-chain/` (shared across machines)

### Example: Shared Installation

```bash
# Setup (run once by admin)
sudo mkdir -p /opt/clang-tool-chain
sudo chown $USER /opt/clang-tool-chain

# Configure for all users
echo 'export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/opt/clang-tool-chain' | \
    sudo tee /etc/profile.d/clang-tool-chain.sh

# All users now share the same toolchain installation
```

## Multi-Architecture Workflows

### Building for Multiple Architectures

clang-tool-chain provides native compilation only (no cross-compilation).

**For cross-compilation, use:**
- **zig cc** - Single binary with all targets
- **Full LLVM** - Configure with cross-compilation targets
- **Docker** - Build in target architecture container

### Example: Docker Multi-Arch Build

```dockerfile
# Dockerfile.aarch64
FROM python:3.11-slim
RUN pip install clang-tool-chain
# This will download Linux ARM64 toolchain if running on ARM64 host
```

```bash
# Build for ARM64 on ARM64 host or with Docker buildx
docker buildx build --platform linux/arm64 -f Dockerfile.aarch64 .
```

## Docker Best Practices

### Minimal Image

```dockerfile
FROM python:3.11-slim
RUN pip install clang-tool-chain
# Toolchain downloads on first use (~71-91 MB)
```

### Cache-Friendly Build

```dockerfile
FROM python:3.11-slim

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Pre-install toolchain (cached layer)
RUN python -c "from clang_tool_chain.installers.clang import install; install()"

# Copy source code (changes frequently)
COPY . .

# Build
RUN clang-tool-chain-cpp main.cpp -o program
```

### Multi-Stage Build

```dockerfile
# Build stage
FROM python:3.11-slim AS builder
RUN pip install clang-tool-chain
COPY . .
RUN clang-tool-chain-cpp main.cpp -o program

# Runtime stage (minimal)
FROM debian:bookworm-slim
COPY --from=builder /app/program /app/program
CMD ["/app/program"]
```

### GitHub Actions Cache

```yaml
- name: Cache clang-tool-chain
  uses: actions/cache@v3
  with:
    path: ~/.clang-tool-chain
    key: clang-tool-chain-${{ runner.os }}-${{ hashFiles('requirements.txt') }}

- name: Install clang-tool-chain
  run: pip install clang-tool-chain
```

## Advanced sccache Configuration

See [sccache Integration Documentation](SCCACHE.md) for:

- Distributed caching with Redis/Memcached/S3
- Custom cache directory configuration
- Cache size limits
- Cache statistics and monitoring
- CI/CD integration

## See Also

- [Installation Guide](INSTALLATION.md) - Basic installation
- [Configuration](CONFIGURATION.md) - Environment variables
- [Architecture](ARCHITECTURE.md) - Technical design
- [CI/CD Integration](CICD_INTEGRATION.md) - CI/CD examples
- [FAQ](FAQ.md) - Common questions
