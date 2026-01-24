# Management CLI

Toolchain installation, verification, and maintenance commands.

**6 commands • Pre-install • PATH management • Diagnostics • Cleanup**

## Quick Examples

```bash
# Show installation info
clang-tool-chain info

# Run diagnostic tests
clang-tool-chain test

# Pre-install Clang toolchain
clang-tool-chain install clang

# Add Clang to system PATH
clang-tool-chain install clang-env

# Remove everything
clang-tool-chain purge
```

## Available Commands

| Command | Description |
|---------|-------------|
| `clang-tool-chain info` | Show installation details and paths |
| `clang-tool-chain test` | Run 7 diagnostic tests |
| `clang-tool-chain install <tool>` | Pre-install toolchain components |
| `clang-tool-chain uninstall <tool>` | Remove from PATH (keeps files) |
| `clang-tool-chain purge` | Delete all toolchains (with confirmation) |
| `clang-tool-chain list-tools` | Show all available wrapper commands |
| `clang-tool-chain version <tool>` | Show version of specific tool |
| `clang-tool-chain path [tool]` | Show path to binaries directory |
| `clang-tool-chain package-version` | Show package and LLVM versions |

## Key Features

- **Auto-Download** - Toolchains download automatically on first use
- **PATH Management** - Add/remove tools from system PATH
- **Diagnostics** - Verify installation with test suite
- **Cleanup** - Remove all toolchains with single command

## Common Workflows

### Initial Setup

```bash
# Install package
pip install clang-tool-chain

# Verify installation
clang-tool-chain info
clang-tool-chain test

# Pre-install core toolchain (optional)
clang-tool-chain install clang
```

### Add to System PATH

```bash
# Add Clang to PATH (use clang directly without clang-tool-chain- prefix)
clang-tool-chain install clang-env

# Restart terminal, then use directly
clang --version
clang++ main.cpp -o program
```

### Cleanup

```bash
# Remove all downloaded toolchains
clang-tool-chain purge

# Or non-interactive (for scripts)
clang-tool-chain purge --yes
```

### Diagnostics

```bash
# Run all tests (7 diagnostic checks)
clang-tool-chain-test
# Or: clang-tool-chain test

# Show installation paths
clang-tool-chain path

# Show specific tool path
clang-tool-chain path clang
```

## Installation Targets

| Target | Description | Downloads |
|--------|-------------|-----------|
| `clang` | Pre-install Clang/LLVM | ~71-91 MB |
| `clang-env` | Add Clang to PATH | Auto-installs if needed |
| `iwyu` | Pre-install IWYU | ~53-57 MB (separate) |
| `lldb` | Pre-install LLDB | ~10-35 MB (separate) |
| `emscripten` | Pre-install Emscripten | ~1.4 GB (includes Node.js) |
| `cosmocc` | Pre-install Cosmopolitan | ~40-60 MB |

**Note:** Most tools auto-download on first use, so `install` is optional.

## Purge Command

The `purge` command removes all downloaded toolchains and clears PATH entries:

```bash
# Interactive confirmation
clang-tool-chain purge

# Skip confirmation (for scripts)
clang-tool-chain purge --yes
```

**What gets removed:**
- `~/.clang-tool-chain/` directory (all toolchains)
- All PATH entries added by `install <tool>-env` commands
- Lock files

**What's preserved:**
- Python package installation (use `pip uninstall` separately)

## PATH Management

### How PATH Management Works

- Uses [setenvironment](https://github.com/zackees/setenvironment) package
- Modifies system/user PATH persistently
- Changes take effect in new terminal sessions
- Cross-platform (Windows, macOS, Linux)

### Example

```bash
# Add Clang to PATH
clang-tool-chain install clang-env

# Restart terminal
clang --version        # Works! (no clang-tool-chain- prefix)
clang++ hello.cpp      # Direct access

# Remove from PATH (keeps files)
clang-tool-chain uninstall clang-env

# Or remove everything (files + PATH)
clang-tool-chain purge
```

## Test Command

The `test` command runs 7 diagnostic checks:

1. Platform detection
2. Toolchain installation verification
3. clang binary resolution
4. clang++ binary resolution
5. clang version check
6. C compilation test
7. C++ compilation test

```bash
# Run all diagnostics
clang-tool-chain test

# Or use dedicated command
clang-tool-chain-test
```

## Info Command

Shows detailed installation information:

```bash
clang-tool-chain info

# Example output:
# clang-tool-chain v1.0.0
# LLVM Version: 21.1.5
# Install Path: /home/user/.clang-tool-chain/clang/linux/x86_64
# Bin Path: /home/user/.clang-tool-chain/clang/linux/x86_64/bin
# Platform: linux-x86_64
```

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Package installation options
- [Configuration](CONFIGURATION.md) - Environment variables
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
