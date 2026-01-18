# Contributing: Adding New Tools

This guide explains how to add new Clang/LLVM-related tools to clang-tool-chain. It is designed for both human developers and AI agents working on extending the toolchain.

## Table of Contents

- [Quick Start Checklist](#quick-start-checklist)
- [Architecture Overview](#architecture-overview)
- [Codebase Structure](#codebase-structure)
- [Step 1: Choose Tool Category](#step-1-choose-tool-category)
- [Step 2: Create the Installer](#step-2-create-the-installer)
- [Step 3: Create the Execution Module](#step-3-create-the-execution-module)
- [Step 4: Create Entry Points](#step-4-create-entry-points)
- [Step 5: Register in pyproject.toml](#step-5-register-in-pyprojecttoml)
- [Step 6: Create Binary Archives](#step-6-create-binary-archives)
- [Step 7: Create Manifest Files](#step-7-create-manifest-files)
- [Step 8: Add Tests](#step-8-add-tests)
- [Step 9: Update Documentation](#step-9-update-documentation)
- [Platform-Specific Considerations](#platform-specific-considerations)
- [Reference: Existing Tool Implementations](#reference-existing-tool-implementations)

---

## Quick Start Checklist

When adding a new tool (e.g., `clang-tool-chain-newtool`), complete these steps:

- [ ] **Installer**: Create `src/clang_tool_chain/installers/newtool.py`
- [ ] **Path Utils**: Add path functions to `src/clang_tool_chain/path_utils.py`
- [ ] **Manifest**: Add manifest functions to `src/clang_tool_chain/manifest.py`
- [ ] **Execution**: Create `src/clang_tool_chain/execution/newtool.py`
- [ ] **Entry Points**: Add functions to `src/clang_tool_chain/commands/entry_points.py`
- [ ] **Re-exports**: Export from `src/clang_tool_chain/wrapper.py`
- [ ] **pyproject.toml**: Register console scripts
- [ ] **Archives**: Create and upload binary archives to `clang-tool-chain-bins` repo
- [ ] **Tests**: Add `tests/test_newtool.py`
- [ ] **CI Workflow**: Create `.github/workflows/test-newtool-*.yml`
- [ ] **Documentation**: Add `docs/NEWTOOL.md` and update README.md

---

## Architecture Overview

```
clang-tool-chain uses a three-layer architecture:

                 User invokes: clang-tool-chain-newtool
                              │
                              ▼
         ┌────────────────────────────────────────────┐
         │         Entry Point (pyproject.toml)       │
         │         → newtool_main() function          │
         └────────────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────────┐
         │         Execution Module                   │
         │         → execute_newtool_tool()           │
         │         → Ensures installation             │
         │         → Locates binary                   │
         │         → Runs with args                   │
         └────────────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────────┐
         │         Installer Module                   │
         │         → Checks if installed              │
         │         → Downloads archive                │
         │         → Extracts to ~/.clang-tool-chain/ │
         │         → Verifies installation            │
         └────────────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────────┐
         │         Manifest System                    │
         │         → Fetches manifest.json            │
         │         → Gets download URL + SHA256       │
         │         → Version management               │
         └────────────────────────────────────────────┘
```

---

## Codebase Structure

```
src/clang_tool_chain/
├── __init__.py           # Package exports
├── wrapper.py            # Central re-export hub for backward compatibility
├── manifest.py           # Manifest fetching and parsing (URLs, versions)
├── path_utils.py         # Installation paths, lock file paths
├── archive.py            # Archive download and extraction
├── archive_cache.py      # Archive caching to avoid re-downloads
├── downloader.py         # Low-level download utilities
├── parallel_download.py  # Multi-threaded range request downloads
│
├── installers/           # Tool installers (one per component)
│   ├── base.py           # BaseToolchainInstaller abstract class
│   ├── clang.py          # Clang/LLVM installer
│   ├── iwyu.py           # Include What You Use installer
│   ├── lldb.py           # LLDB debugger installer
│   ├── emscripten.py     # Emscripten SDK installer
│   ├── nodejs.py         # Node.js runtime installer
│   └── cosmocc.py        # Cosmopolitan Libc installer
│
├── execution/            # Tool execution logic
│   ├── core.py           # execute_tool() for Clang/LLVM tools
│   ├── iwyu.py           # IWYU-specific execution
│   ├── lldb.py           # LLDB-specific execution
│   ├── emscripten.py     # Emscripten execution + Node.js setup
│   ├── cosmocc.py        # Cosmopolitan execution
│   └── build.py          # Build utilities (build_run, etc.)
│
├── commands/             # CLI entry points
│   ├── __init__.py       # Re-exports all entry points
│   └── entry_points.py   # *_main() functions for pyproject.toml
│
├── platform/             # Platform detection
│   ├── detection.py      # get_platform_info() → ("linux", "x86_64")
│   └── paths.py          # Binary paths, tool binary finding
│
├── sdk/                  # SDK detection
│   ├── macos.py          # macOS SDK/sysroot detection
│   └── windows.py        # Windows SDK detection
│
├── abi/                  # ABI configuration
│   ├── windows_gnu.py    # MinGW GNU ABI configuration
│   └── windows_msvc.py   # MSVC ABI configuration
│
├── linker/               # Linker configuration
│   └── lld.py            # LLD linker flags and detection
│
└── deployment/           # Post-build deployment
    └── dll_deployer.py   # Windows DLL deployment
```

---

## Step 1: Choose Tool Category

Determine your tool's category:

| Category | Example | Installation Behavior |
|----------|---------|----------------------|
| **Part of Clang Toolchain** | clang-format, clang-tidy | Included in main Clang archive |
| **Separate Component** | IWYU, LLDB | Own archive, separate installer |
| **External SDK** | Emscripten | External download, large archive |
| **Universal Tool** | Cosmocc | Same binary for all platforms |

**If your tool is already in the Clang/LLVM binaries**, skip to [Step 4](#step-4-create-entry-points) (just add entry point).

**If your tool needs its own archive**, continue to Step 2.

---

## Step 2: Create the Installer

Create `src/clang_tool_chain/installers/newtool.py`:

```python
"""
NewTool installer module.
"""

from pathlib import Path

from ..logging_config import configure_logging
from ..manifest import Manifest, fetch_newtool_platform_manifest  # Add to manifest.py
from ..path_utils import get_newtool_install_dir, get_newtool_lock_path  # Add to path_utils.py
from .base import BaseToolchainInstaller

logger = configure_logging(__name__)


class NewToolInstaller(BaseToolchainInstaller):
    """Installer for NewTool."""

    tool_name = "newtool"
    binary_name = "newtool"  # Name of main binary (without .exe)

    def get_install_dir(self, platform: str, arch: str) -> Path:
        return get_newtool_install_dir(platform, arch)

    def get_lock_path(self, platform: str, arch: str) -> Path:
        return get_newtool_lock_path(platform, arch)

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        return fetch_newtool_platform_manifest(platform, arch)

    # Optional: Override for non-standard binary locations
    def get_binary_path(self, install_dir: Path, platform: str) -> Path:
        exe_ext = ".exe" if platform == "win" else ""
        return install_dir / "bin" / f"{self.binary_name}{exe_ext}"

    # Optional: Override for post-extraction steps
    def post_extract_hook(self, install_dir: Path, platform: str, arch: str) -> None:
        # Custom post-extraction logic (e.g., fix symlinks on Windows)
        pass


# Create singleton instance
_installer = NewToolInstaller()


# Module-level convenience functions
def is_newtool_installed(platform: str, arch: str) -> bool:
    return _installer.is_installed(platform, arch)


def download_and_install_newtool(platform: str, arch: str) -> None:
    return _installer.download_and_install(platform, arch)


def _subprocess_install_newtool(platform: str, arch: str) -> int:
    """Called by base.ensure() via subprocess."""
    return _installer.subprocess_install(platform, arch)


def ensure_newtool(platform: str, arch: str) -> None:
    return _installer.ensure(platform, arch)
```

### Add Path Functions

Add to `src/clang_tool_chain/path_utils.py`:

```python
# ============================================================================
# NewTool Paths
# ============================================================================


def get_newtool_install_dir(platform: str, arch: str) -> Path:
    """Get the installation directory for NewTool."""
    toolchain_dir = get_home_toolchain_dir()
    return toolchain_dir / "newtool" / platform / arch


def get_newtool_lock_path(platform: str, arch: str) -> Path:
    """Get the lock file path for NewTool installation."""
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    return toolchain_dir / f"newtool-{platform}-{arch}.lock"
```

### Add Manifest Functions

Add to `src/clang_tool_chain/manifest.py`:

```python
# Add base URL constant
NEWTOOL_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/newtool"


def fetch_newtool_root_manifest() -> RootManifest:
    """Fetch the NewTool root manifest file."""
    logger.info("Fetching NewTool root manifest")
    url = f"{NEWTOOL_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"NewTool root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_newtool_platform_manifest(platform: str, arch: str) -> Manifest:
    """Fetch the NewTool platform-specific manifest file."""
    logger.info(f"Fetching NewTool platform manifest for {platform}/{arch}")
    root_manifest = fetch_newtool_root_manifest()

    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    url = f"{NEWTOOL_MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    manifest = _parse_manifest(data)
                    logger.info(f"NewTool platform manifest loaded for {platform}/{arch}")
                    return manifest

    raise RuntimeError(f"NewTool platform {platform}/{arch} not found in manifest")
```

---

## Step 3: Create the Execution Module

Create `src/clang_tool_chain/execution/newtool.py`:

```python
"""
NewTool execution module.
"""

import os
import sys
from pathlib import Path
from typing import NoReturn

from ..installers.newtool import ensure_newtool
from ..logging_config import configure_logging
from ..path_utils import get_newtool_install_dir
from ..platform.detection import get_platform_info

logger = configure_logging(__name__)


def get_newtool_binary_dir() -> Path:
    """Get the directory containing NewTool binaries."""
    platform, arch = get_platform_info()
    install_dir = get_newtool_install_dir(platform, arch)
    return install_dir / "bin"


def find_newtool_tool(tool_name: str) -> Path:
    """
    Find a NewTool binary.

    Args:
        tool_name: Name of the tool (e.g., "newtool")

    Returns:
        Path to the tool binary

    Raises:
        FileNotFoundError: If tool is not found
    """
    platform, arch = get_platform_info()

    # Ensure NewTool is installed
    ensure_newtool(platform, arch)

    # Find the binary
    bin_dir = get_newtool_binary_dir()
    exe_suffix = ".exe" if platform == "win" else ""
    tool_path = bin_dir / f"{tool_name}{exe_suffix}"

    if not tool_path.exists():
        raise FileNotFoundError(f"NewTool binary not found: {tool_path}")

    return tool_path


def execute_newtool_tool(tool_name: str, extra_args: list[str] | None = None) -> NoReturn:
    """
    Execute a NewTool binary.

    Args:
        tool_name: Name of the tool to execute
        extra_args: Additional arguments (uses sys.argv[1:] if None)
    """
    tool_path = find_newtool_tool(tool_name)

    args = extra_args if extra_args is not None else sys.argv[1:]

    # Build command
    cmd = [str(tool_path)] + list(args)

    logger.debug(f"Executing: {' '.join(cmd)}")

    # Execute with os.execv for direct process replacement (Unix)
    # or subprocess for Windows
    if os.name == "nt":
        import subprocess
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    else:
        os.execv(str(tool_path), cmd)
```

---

## Step 4: Create Entry Points

Add to `src/clang_tool_chain/commands/entry_points.py`:

```python
# ============================================================================
# NewTool Entry Points
# ============================================================================


def newtool_main() -> NoReturn:
    """Entry point for newtool wrapper."""
    from ..execution.newtool import execute_newtool_tool

    execute_newtool_tool("newtool")


def newtool_helper_main() -> NoReturn:
    """Entry point for newtool-helper wrapper (if applicable)."""
    from ..execution.newtool import execute_newtool_tool

    execute_newtool_tool("newtool-helper")
```

### Add Re-exports to wrapper.py

Add to `src/clang_tool_chain/wrapper.py`:

```python
# ============================================================================
# NewTool Imports
# ============================================================================
from .commands import (
    # ... existing imports ...
    newtool_main,
    newtool_helper_main,
)

from .execution.newtool import (
    execute_newtool_tool,
    find_newtool_tool,
    get_newtool_binary_dir,
)

# Add to __all__ list
__all__ = [
    # ... existing exports ...
    # NewTool
    "newtool_main",
    "newtool_helper_main",
    "execute_newtool_tool",
    "find_newtool_tool",
    "get_newtool_binary_dir",
]
```

### Add Re-exports to commands/__init__.py

```python
from .entry_points import (
    # ... existing imports ...
    newtool_main,
    newtool_helper_main,
)
```

---

## Step 5: Register in pyproject.toml

Add console script entries:

```toml
[project.scripts]
# ... existing entries ...
# NewTool
clang-tool-chain-newtool = "clang_tool_chain.wrapper:newtool_main"
clang-tool-chain-newtool-helper = "clang_tool_chain.wrapper:newtool_helper_main"
```

After editing, reinstall the package:

```bash
uv pip install -e ".[dev]"
```

---

## Step 6: Create Binary Archives

Binary archives are stored in the `clang-tool-chain-bins` repository.

### Directory Structure

```
clang-tool-chain-bins/assets/newtool/
├── manifest.json           # Root manifest (lists platforms)
├── win/
│   └── x86_64/
│       ├── manifest.json   # Platform manifest (lists versions)
│       └── newtool-1.0.0-win-x86_64.tar.zst
├── linux/
│   ├── x86_64/
│   │   ├── manifest.json
│   │   └── newtool-1.0.0-linux-x86_64.tar.zst
│   └── arm64/
│       ├── manifest.json
│       └── newtool-1.0.0-linux-arm64.tar.zst
└── darwin/
    ├── x86_64/
    │   ├── manifest.json
    │   └── newtool-1.0.0-darwin-x86_64.tar.zst
    └── arm64/
        ├── manifest.json
        └── newtool-1.0.0-darwin-arm64.tar.zst
```

### Archive Structure

Archives should extract to a directory containing a `bin/` folder:

```
newtool-1.0.0-linux-x86_64/
├── bin/
│   ├── newtool
│   └── newtool-helper
├── lib/          # Optional
└── share/        # Optional
```

### Creating Archives

Use the maintainer tools in `downloads-bins/tools/`:

```bash
# Initialize submodule
git submodule init && git submodule update
cd downloads-bins/tools

# Create archive (customize for your tool)
python fetch_and_archive.py --platform linux --arch x86_64 \
    --source-url https://github.com/newtool/releases/download/v1.0.0/newtool-linux.tar.gz \
    --output-name newtool

# Or manually with zstd
tar -cvf - newtool-1.0.0-linux-x86_64/ | zstd -22 --ultra -o newtool-1.0.0-linux-x86_64.tar.zst
```

### Compute SHA256

```bash
sha256sum newtool-1.0.0-linux-x86_64.tar.zst
# Output: abc123...def789  newtool-1.0.0-linux-x86_64.tar.zst
```

---

## Step 7: Create Manifest Files

### Root Manifest (`manifest.json`)

```json
{
  "platforms": [
    {
      "platform": "win",
      "architectures": [
        {
          "arch": "x86_64",
          "manifest_path": "win/x86_64/manifest.json"
        }
      ]
    },
    {
      "platform": "linux",
      "architectures": [
        {
          "arch": "x86_64",
          "manifest_path": "linux/x86_64/manifest.json"
        },
        {
          "arch": "arm64",
          "manifest_path": "linux/arm64/manifest.json"
        }
      ]
    },
    {
      "platform": "darwin",
      "architectures": [
        {
          "arch": "x86_64",
          "manifest_path": "darwin/x86_64/manifest.json"
        },
        {
          "arch": "arm64",
          "manifest_path": "darwin/arm64/manifest.json"
        }
      ]
    }
  ]
}
```

### Platform Manifest (`win/x86_64/manifest.json`)

```json
{
  "latest": "1.0.0",
  "versions": {
    "1.0.0": {
      "href": "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/newtool/win/x86_64/newtool-1.0.0-win-x86_64.tar.zst",
      "sha256": "abc123def456..."
    }
  }
}
```

---

## Step 8: Add Tests

Create `tests/test_newtool.py`:

```python
"""Tests for NewTool wrapper."""

import subprocess
import pytest


class TestNewTool:
    """Test cases for clang-tool-chain-newtool command."""

    def test_newtool_version(self):
        """Test that newtool --version works."""
        result = subprocess.run(
            ["clang-tool-chain-newtool", "--version"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0
        assert "newtool" in result.stdout.lower() or "version" in result.stdout.lower()

    def test_newtool_help(self):
        """Test that newtool --help works."""
        result = subprocess.run(
            ["clang-tool-chain-newtool", "--help"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### Create CI Workflow

Create `.github/workflows/test-newtool-linux-x86.yml`:

```yaml
name: test-newtool-linux-x86

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install package
        run: |
          pip install uv
          uv pip install -e ".[dev]" --system

      - name: Run NewTool tests
        run: |
          uv run pytest tests/test_newtool.py -v --timeout=300
```

Create similar workflows for other platforms.

---

## Step 9: Update Documentation

### Create `docs/NEWTOOL.md`

```markdown
# NewTool Integration

clang-tool-chain includes NewTool for [description].

## Quick Start

\`\`\`bash
# Run NewTool
clang-tool-chain-newtool --version

# Example usage
clang-tool-chain-newtool input.c -o output
\`\`\`

## Platform Support

| Platform | Architecture | Version | Status |
|----------|-------------|---------|--------|
| Windows  | x86_64      | 1.0.0   | ✅ Available |
| Linux    | x86_64      | 1.0.0   | ✅ Available |
| Linux    | arm64       | 1.0.0   | ✅ Available |
| macOS    | x86_64      | 1.0.0   | ✅ Available |
| macOS    | arm64       | 1.0.0   | ✅ Available |

## Commands

| Command | Description |
|---------|-------------|
| `clang-tool-chain-newtool` | Main NewTool command |
| `clang-tool-chain-newtool-helper` | Helper utility |

## See Also

- [NewTool Official Documentation](https://newtool.example.com)
```

### Update README.md

Add to the command table and platform support sections.

### Update CLAUDE.md

Add version information to the CLAUDE.md version tables if the tool has platform-specific versions.

---

## Platform-Specific Considerations

### Windows

- Binaries must have `.exe` extension
- Consider DLL dependencies (may need `dll_deployer.py` integration)
- Paths use backslashes but Python handles this

### macOS

- No `.exe` extension
- May need to fix permissions after extraction (`chmod +x`)
- Universal binaries (arm64 + x86_64) may need separate archives

### Linux

- No `.exe` extension
- May have glibc version requirements (document minimum version)
- ARM64 may need separate builds

---

## Reference: Existing Tool Implementations

Use these as templates:

| Tool | Installer | Execution | Complexity |
|------|-----------|-----------|------------|
| **Clang** | `installers/clang.py` | `execution/core.py` | Core toolchain |
| **IWYU** | `installers/iwyu.py` | `execution/iwyu.py` | Separate archive |
| **LLDB** | `installers/lldb.py` | `execution/lldb.py` | Python integration |
| **Emscripten** | `installers/emscripten.py` | `execution/emscripten.py` | External SDK |
| **Cosmocc** | `installers/cosmocc.py` | `execution/cosmocc.py` | Universal (all platforms) |

### Cosmocc Example (Universal Tool)

Cosmocc is a good template for tools that are platform-independent:
- Single archive for all platforms
- `get_cosmocc_install_dir()` ignores platform/arch parameters
- Manifest uses `manifest-universal.json`

### LLDB Example (Python Integration)

LLDB shows how to handle tools with Python dependencies:
- Bundled Python runtime
- Environment variable setup for Python paths
- Diagnostic command (`lldb-check-python`)

---

## Troubleshooting

### "Binary not found" after installation

1. Check archive structure - must have `bin/` directory
2. Verify binary name matches `binary_name` in installer
3. Check file permissions on Unix

### Manifest fetch fails

1. Verify manifest URL is correct
2. Check that manifest files are committed to `clang-tool-chain-bins`
3. Ensure raw.githubusercontent.com URLs

### Tests fail in CI but pass locally

1. Check platform-specific behavior
2. Ensure archives exist for all tested platforms
3. Verify timeout is sufficient for first-time download

---

## See Also

- [Architecture Documentation](ARCHITECTURE.md) - Detailed architecture overview
- [Maintainer Guide](MAINTAINER.md) - Archive creation and distribution
- [Testing Guide](TESTING.md) - Running and writing tests
