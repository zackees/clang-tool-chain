# sccache Integration

Optional compilation caching for 2-10x faster rebuilds.

**Transparent caching • Distributed backends • All compilers supported**

## Quick Examples

```bash
# Install sccache support
pip install clang-tool-chain[sccache]
# Or: cargo install sccache

# Compile with caching
clang-tool-chain-sccache-c main.c -o main
clang-tool-chain-sccache-cpp main.cpp -o main

# MSVC variants (Windows)
clang-tool-chain-sccache-c-msvc main.c -o main.exe
clang-tool-chain-sccache-cpp-msvc main.cpp -o main.exe

# Emscripten (WebAssembly)
clang-tool-chain-sccache-emcc main.c -o main.js
clang-tool-chain-sccache-empp main.cpp -o main.js

# Manage sccache
clang-tool-chain-sccache --show-stats
clang-tool-chain-sccache --zero-stats
clang-tool-chain-sccache --start-server
clang-tool-chain-sccache --stop-server
```

## How It Works

- **Caches compilation results** locally based on source file content
- **Transparent caching layer** wraps compiler invocations
- **Requires sccache binary** in PATH (installed separately)
- **Optional distributed backends** (Redis, S3, GCS, Azure) for team caching

## Installation Options

```bash
# Option 1: Python package (easiest)
pip install clang-tool-chain[sccache]

# Option 2: Cargo (Rust package manager)
cargo install sccache

# Option 3: System package manager
# Linux (Debian/Ubuntu)
apt install sccache

# macOS
brew install sccache

# Option 4: Download binary from GitHub
# https://github.com/mozilla/sccache/releases
```

## sccache Commands Available

- `clang-tool-chain-sccache` - Direct sccache passthrough (stats, management)
- `clang-tool-chain-sccache-c` - C compiler with caching (GNU ABI)
- `clang-tool-chain-sccache-cpp` - C++ compiler with caching (GNU ABI)
- `clang-tool-chain-sccache-c-msvc` - C compiler with caching (MSVC ABI)
- `clang-tool-chain-sccache-cpp-msvc` - C++ compiler with caching (MSVC ABI)
- `clang-tool-chain-sccache-emcc` - Emscripten C with caching
- `clang-tool-chain-sccache-empp` - Emscripten C++ with caching

## Performance Benefits

**Typical speedups:**
- **First build:** Same as normal (cache miss)
- **Clean rebuild:** 2-5x faster (cache hit, local)
- **Distributed cache:** 5-10x faster (cache hit, shared team cache)
- **No source changes:** Nearly instant (compilation skipped entirely)

### Benchmarks

| Scenario | Without sccache | With sccache (local) | With sccache (distributed) |
|----------|----------------|---------------------|----------------------------|
| First build | 60s | 60s | 60s |
| Clean rebuild | 60s | 12-20s | 6-10s |
| No changes | 60s | <1s | <1s |

## Cache Statistics

```bash
# View cache effectiveness
clang-tool-chain-sccache --show-stats

# Example output:
# Compile requests: 1250
# Compile hits: 1100
# Cache hit rate: 88%
# Cache size: 1.2 GB
```

## Configuration

### Local Cache (Default)

No configuration needed - sccache caches to `~/.cache/sccache/` by default.

### Distributed Cache (Team Sharing)

Configure sccache for shared team caching:

```bash
# Redis backend
export SCCACHE_REDIS=redis://cache-server:6379

# S3 backend
export SCCACHE_BUCKET=my-build-cache
export SCCACHE_REGION=us-east-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# Google Cloud Storage
export SCCACHE_GCS_BUCKET=my-build-cache
export SCCACHE_GCS_KEY_PATH=/path/to/service-account.json

# Azure Blob Storage
export SCCACHE_AZURE_CONNECTION_STRING=...
```

See [sccache documentation](https://github.com/mozilla/sccache#distributed-compilation) for full backend configuration.

## Common Workflows

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Setup sccache
  run: |
    pip install clang-tool-chain[sccache]
    echo "SCCACHE_DIR=${{ runner.temp }}/sccache" >> $GITHUB_ENV

- name: Cache sccache
  uses: actions/cache@v3
  with:
    path: ${{ runner.temp }}/sccache
    key: sccache-${{ runner.os }}-${{ hashFiles('**/src/**') }}

- name: Build with caching
  run: clang-tool-chain-sccache-cpp main.cpp -o program

- name: Show cache stats
  run: clang-tool-chain-sccache --show-stats
```

### Local Development

```bash
# Use sccache for all compilations
export CC=clang-tool-chain-sccache-c
export CXX=clang-tool-chain-sccache-cpp

# Your build system now uses sccache transparently
make
cmake -B build && cmake --build build
```

### Clean Cache

```bash
# Clear local cache
clang-tool-chain-sccache --zero-stats
rm -rf ~/.cache/sccache/

# Or using environment variable
rm -rf $SCCACHE_DIR
```

## Troubleshooting

### sccache not found

```bash
# Verify sccache is installed
which sccache

# If not found, install it
pip install clang-tool-chain[sccache]
# Or: cargo install sccache
```

### Low cache hit rate

```bash
# Check statistics
clang-tool-chain-sccache --show-stats

# Common causes:
# - Frequently changing compiler flags
# - Header files changing often
# - Different compiler versions
# - Cache eviction (SCCACHE_CACHE_SIZE too small)
```

### Cache size management

```bash
# Set maximum cache size (default: 10GB)
export SCCACHE_CACHE_SIZE=20G  # 20GB

# Set cache directory
export SCCACHE_DIR=/path/to/large/disk
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SCCACHE_DIR` | Local cache directory | `~/.cache/sccache/` |
| `SCCACHE_CACHE_SIZE` | Maximum cache size | `10G` |
| `SCCACHE_IDLE_TIMEOUT` | Server idle timeout | `600` (10 min) |
| `SCCACHE_LOG` | Log level (trace, debug, info, warn, error) | `info` |

## Related Documentation

- [Clang/LLVM Toolchain](CLANG_LLVM.md) - Core compiler documentation
- [sccache GitHub](https://github.com/mozilla/sccache) - Official documentation
- [Performance](PERFORMANCE.md) - Compilation speed benchmarks
