# Troubleshooting Guide

This document covers common issues and their solutions when using clang-tool-chain.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Download Issues](#download-issues)
- [Compilation Issues](#compilation-issues)
- [macOS-Specific Issues](#macos-specific-issues)
- [Windows-Specific Issues](#windows-specific-issues)
- [Linux-Specific Issues](#linux-specific-issues)
- [Configuration Issues](#configuration-issues)

---

## Installation Issues

### Binaries Not Found

**Error:** `Clang binaries are not installed`

**Solution:**

```bash
# Check installation status
clang-tool-chain info

# Try manual fetch
clang-tool-chain-fetch

# Verify installation directory exists
ls ~/.clang-tool-chain/
```

### Platform Not Supported

**Error:** `Unsupported platform`

**Solution:** Ensure you're on a supported platform:
- Windows 10+ (x86_64)
- Linux x86_64 or ARM64 (glibc 2.27+)
- macOS 11+ (x86_64 or ARM64)

32-bit systems are **not supported**.

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'clang_tool_chain'`

**Solutions:**

1. **Ensure package is installed:**
   ```bash
   pip install clang-tool-chain
   ```

2. **Check Python environment:**
   ```bash
   which python  # Verify correct Python interpreter
   pip list | grep clang-tool-chain
   ```

3. **Reinstall:**
   ```bash
   pip uninstall clang-tool-chain
   pip install clang-tool-chain
   ```

---

## Download Issues

### Download Fails

**Error:** `Failed to download archive` or `Checksum verification failed`

**Solutions:**

1. **Check internet connection**

2. **Retry the command** (temporary network issue)

3. **Check GitHub raw content access:**
   ```bash
   curl -I https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang/manifest.json
   ```

4. **Clear partial downloads:**
   ```bash
   rm -rf ~/.clang-tool-chain/
   ```

### Slow First-Time Download

**Observation:** First compilation takes 30-60 seconds

**This is normal!** The toolchain is downloading. Subsequent compilations are instant. To pre-download:

```bash
# Pre-fetch binaries before your build
clang-tool-chain-fetch

# Or just run any command
clang-tool-chain-c --version
```

---

## Compilation Issues

### Tool Execution Fails

**Error:** `Permission denied` (Linux/macOS)

**Solution:**

```bash
# Ensure execute permissions
chmod +x ~/.clang-tool-chain/clang/*/bin/*

# Or reinstall
rm -rf ~/.clang-tool-chain/
clang-tool-chain-c --version  # Re-downloads with correct permissions
```

### Linker Errors

**Error:** `undefined reference to ...` or `unresolved external symbol`

**Solutions:**

1. **Ensure all source files are included:**
   ```bash
   clang-tool-chain-c main.c utils.c helpers.c -o program
   ```

2. **Check library linkage:**
   ```bash
   clang-tool-chain-c main.c -L/path/to/libs -lmylib -o program
   ```

3. **On Windows GNU ABI, ensure C++ standard library:**
   ```bash
   clang-tool-chain-cpp main.cpp -o program  # Links libc++ automatically
   ```

---

## macOS-Specific Issues

### stdio.h or iostream Not Found

**Error:** `fatal error: 'stdio.h' file not found` or `'iostream' file not found`

**Cause:** Xcode Command Line Tools not installed or SDK not detected.

**Solution:**

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Verify SDK is detected
xcrun --show-sdk-path

# Should output something like:
# /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk

# Try compilation again
clang-tool-chain-c hello.c -o hello
```

**Advanced troubleshooting:**

```bash
# Manually specify SDK path
clang-tool-chain-c -isysroot $(xcrun --show-sdk-path) hello.c -o hello

# Or set SDKROOT environment variable
export SDKROOT=$(xcrun --show-sdk-path)
clang-tool-chain-c hello.c -o hello
```

### SDK Path Issues After macOS Update

**Symptom:** Compilation worked before but fails after macOS update.

**Solution:**

```bash
# Reinstall Xcode Command Line Tools
sudo rm -rf /Library/Developer/CommandLineTools
xcode-select --install

# Verify installation
xcrun --show-sdk-path
```

---

## Windows-Specific Issues

### DLLs Not Being Copied

**Problem:** MinGW DLLs not automatically deployed with executable.

**Solutions:**

1. Check you're using GNU ABI (default), not MSVC ABI (`-msvc` variant)
2. Verify you're linking (not just compiling with `-c`)
3. Check the output file has `.exe` extension
4. Ensure `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS` is not set

### Want to Disable Library Deployment

**Solution:**

```bash
# Windows (CMD)
set CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1
clang-tool-chain-cpp main.cpp -o main.exe

# Windows (PowerShell)
$env:CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS="1"
clang-tool-chain-cpp main.cpp -o main.exe
```

### Need Verbose Library Logging

**Solution:**

```bash
set CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1
clang-tool-chain-cpp main.cpp -o main.exe
# Now shows detailed DEBUG logs
```

### MSVC ABI Link Errors

**Problem:** Linking fails when using MSVC ABI (`-msvc` variants).

**Solution:**

1. Ensure Visual Studio or Windows SDK is installed
2. Run from Visual Studio Developer Command Prompt, or
3. Use GNU ABI (default) which doesn't require Visual Studio

---

## Linux-Specific Issues

### GLIBC Version Errors

**Error:** `version 'GLIBC_X.XX' not found`

**Cause:** Your system has an older glibc than the binaries require.

**Requirements:** glibc 2.27 or higher

**Check your version:**
```bash
ldd --version
```

**Solutions:**

1. Update your Linux distribution
2. Use a container with a newer glibc
3. Build from source with older glibc support

### Missing libstdc++

**Error:** `libstdc++.so.6: version 'GLIBCXX_X.X.XX' not found`

**Solution:**

```bash
# Ubuntu/Debian
sudo apt-get install libstdc++6

# Fedora/RHEL
sudo dnf install libstdc++
```

---

## Configuration Issues

### Custom Installation Path Not Working

**Error:** Binaries install to default location despite `CLANG_TOOL_CHAIN_DOWNLOAD_PATH`

**Solution:** Ensure the environment variable is set **before** running the command:

```bash
# Linux/macOS
export CLANG_TOOL_CHAIN_DOWNLOAD_PATH=/custom/path
clang-tool-chain-c hello.c

# Windows (CMD)
set CLANG_TOOL_CHAIN_DOWNLOAD_PATH=C:\custom\path
clang-tool-chain-c hello.c

# Windows (PowerShell)
$env:CLANG_TOOL_CHAIN_DOWNLOAD_PATH="C:\custom\path"
clang-tool-chain-c hello.c
```

### PATH Not Updated After `install clang-env`

**Problem:** `clang` command not found after running `clang-tool-chain install clang-env`

**Solution:**

1. **Restart your terminal** - PATH changes require a new shell session
2. On Windows, you may need to log out and log back in
3. Verify with: `clang-tool-chain path clang`

---

## Diagnostic Tools

### Run Diagnostic Tests

Use the built-in diagnostic tool to verify your installation:

```bash
# Run 7 diagnostic tests
clang-tool-chain-test

# Or via main CLI:
clang-tool-chain test
```

**Tests performed:**
1. Platform detection
2. Toolchain installation verification
3. clang binary resolution
4. clang++ binary resolution
5. clang version check
6. C compilation test
7. C++ compilation test

### Get Installation Paths

```bash
# Get all paths in JSON format
clang-tool-chain-paths

# Show installation info
clang-tool-chain info

# Get path to specific tool
clang-tool-chain path clang
```

---

## Getting Help

If your issue isn't covered here:

1. **Check the FAQ:** [docs/FAQ.md](FAQ.md)
2. **Search existing issues:** [GitHub Issues](https://github.com/zackees/clang-tool-chain/issues)
3. **Open a new issue** with:
   - Your platform and architecture
   - Output of `clang-tool-chain info`
   - Complete error message
   - Steps to reproduce

---

## See Also

- [FAQ](FAQ.md) - Frequently asked questions
- [Architecture Overview](ARCHITECTURE.md) - How clang-tool-chain works
- [Main Documentation](../README.md) - Full documentation
