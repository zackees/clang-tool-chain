# Configuration

Environment variables and settings for clang-tool-chain.

## Environment Variables

### Installation Path

**`CLANG_TOOL_CHAIN_DOWNLOAD_PATH`**

Override default installation location:

```bash
# Linux/macOS
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/custom/path
clang-tool-chain-c hello.c -o hello

# Windows
set CLANG_TOOL_CHAIN_DOWNLOAD_PATH=C:\custom\path
clang-tool-chain-c hello.c -o hello
```

**Use cases:**
- Testing different toolchain versions
- Shared installations across projects
- Network or cache drives
- CI/CD artifact caching

**Default paths:**
- Windows: `~/.clang-tool-chain/`
- Linux: `~/.clang-tool-chain/`
- macOS: `~/.clang-tool-chain/`

### macOS SDK Configuration

**`SDKROOT`**

Override automatic SDK detection:

```bash
# Use custom SDK path
export SDKROOT=/path/to/sdk

# Or let clang-tool-chain detect automatically (default)
unset SDKROOT
```

**`CLANG_TOOL_CHAIN_NO_SYSROOT`**

Disable automatic SDK injection (not recommended):

```bash
export CLANG_TOOL_CHAIN_NO_SYSROOT=1
```

### Library Deployment (Cross-Platform)

**`CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS`**

Disable automatic library deployment for all outputs (Windows DLLs, Linux .so, macOS .dylib):

```bash
# Windows (cmd)
set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1

# Windows (PowerShell)
$env:CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS = "1"

# Linux/macOS/Git Bash
export CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
```

**`CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB`**

Disable library deployment for shared library outputs only (.dll, .so, .dylib):

```bash
set CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1
```

**`CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE`**

Enable verbose logging for library deployment:

```bash
set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o program.exe
# Output: Detailed library detection and copy logs
```

### Linker Configuration

**`CLANG_TOOL_CHAIN_USE_SYSTEM_LD`**

Use system linker instead of bundled LLD:

```bash
# Linux/macOS
export CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1

# Windows
set CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1
```

**Default linkers:**
- **macOS**: `ld64.lld` (LLVM's Mach-O linker)
- **Linux**: `lld` (LLVM linker)
- **Windows**: `lld` (LLVM linker)

### Build Directives

**`CLANG_TOOL_CHAIN_NO_DIRECTIVES`**

Disable inlined build directives parsing:

```bash
export CLANG_TOOL_CHAIN_NO_DIRECTIVES=1
```

**`CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE`**

Show parsed directives (debug mode):

```bash
export CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE=1
clang-tool-chain-cpp hello.cpp -o hello
# Output: Parsed directives: @link=[pthread], @std=c++17
```

### sccache Configuration

**`SCCACHE_DIR`**

Local cache directory:

```bash
export SCCACHE_DIR=/path/to/cache
```

**`SCCACHE_CACHE_SIZE`**

Maximum cache size:

```bash
export SCCACHE_CACHE_SIZE=20G  # 20GB (default: 10G)
```

**`SCCACHE_LOG`**

Log level:

```bash
export SCCACHE_LOG=debug  # trace, debug, info, warn, error
```

**Distributed backends:**

```bash
# Redis
export SCCACHE_REDIS=redis://cache-server:6379

# S3
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

See [sccache documentation](https://github.com/mozilla/sccache) for full backend configuration.

## macOS SDK Detection (Automatic)

macOS users don't need to configure SDK paths - the toolchain automatically detects your Xcode Command Line Tools SDK.

### Requirements

```bash
xcode-select --install  # One-time setup
```

### How it works

1. Automatically injects `-isysroot` flag when compiling on macOS
2. Detects SDK via `xcrun --show-sdk-path`
3. Respects `SDKROOT` environment variable or explicit `-isysroot` flags

### Verification

```bash
# Check detected SDK
xcrun --show-sdk-path
# Example output: /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk

# Test compilation
clang-tool-chain-cpp hello.cpp -o hello -v
# Look for: -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk
```

### Custom SDK

```bash
# Use custom SDK path
export SDKROOT=/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX14.0.sdk

# Or pass explicitly
clang-tool-chain-cpp hello.cpp -isysroot /path/to/sdk
```

### Troubleshooting

**SDK not found:**
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Verify installation
xcrun --show-sdk-path
```

See [Troubleshooting Guide](TROUBLESHOOTING.md#macos-stdioh-or-iostream-not-found) for more details.

## Common Configuration Scenarios

### CI/CD Caching

```yaml
# GitHub Actions
env:
  CLANG_TOOL_CHAIN_DOWNLOAD_PATH: ${{ github.workspace }}/.clang-cache

- name: Cache toolchain
  uses: actions/cache@v3
  with:
    path: .clang-cache
    key: clang-${{ runner.os }}-${{ runner.arch }}
```

### Shared Team Cache (sccache)

```bash
# .bashrc or team setup script
export SCCACHE_REDIS=redis://build-cache.company.com:6379
export CC=clang-tool-chain-sccache-c
export CXX=clang-tool-chain-sccache-cpp
```

### Offline Development

```bash
# Pre-download all toolchains on internet-connected machine
clang-tool-chain install clang
clang-tool-chain install iwyu
clang-tool-chain install lldb
clang-tool-chain install emscripten
clang-tool-chain install cosmocc

# Transfer ~/.clang-tool-chain/ to offline machine
# Works offline from now on!
```

### Windows GNU ABI without DLL Deployment

```bash
# Disable automatic library deployment
set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1

# Compile (no DLLs copied)
clang-tool-chain-cpp main.cpp -o program.exe

# Manually add MinGW bin to PATH if needed
set PATH=%USERPROFILE%\.clang-tool-chain\mingw-w64\bin;%PATH%
```

## Configuration Files

clang-tool-chain does not use configuration files. All settings are controlled via:

1. **Environment variables** (documented above)
2. **Command-line flags** (passed to clang/llvm tools)
3. **Inlined build directives** (embedded in source files)

This design philosophy keeps configuration explicit and portable.

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Installation paths
- [Windows DLL Deployment](DLL_DEPLOYMENT.md) - DLL configuration
- [Inlined Build Directives](DIRECTIVES.md) - Source file configuration
- [sccache Integration](SCCACHE.md) - Cache configuration
- [Troubleshooting](TROUBLESHOOTING.md) - Common configuration issues
