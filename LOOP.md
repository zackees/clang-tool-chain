# Windows GNU ABI Support Implementation Loop

## Executive Summary

This document outlines the complete implementation plan for adding Windows GNU ABI support to clang-tool-chain, making Windows default to GNU target (like zig cc) instead of MSVC target.

**Breaking Change:** This is a v2.0.0 feature that changes default Windows behavior.

**Key Decision:** Windows defaults to GNU ABI (`x86_64-w64-mingw32`), with explicit MSVC variants available.

---

## Part 1: README Changes

### 1.1 Add Windows GNU ABI Warning Section

**Location:** After "Quick Start" section, before "Command Quick Reference"

**Content to Add:**

```markdown
### ⚠️ Windows Users: GNU ABI by Default (v2.0+)

**IMPORTANT:** Starting with v2.0.0, Windows defaults to GNU ABI (MinGW-w64) for cross-platform consistency.

This matches the behavior of [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case) and ensures consistent C++ ABI across all platforms.

**What this means:**
- ✅ **C++11 strict mode works** - No C++14 extensions in standard library headers
- ✅ **Cross-platform consistency** - Same ABI on Windows/Linux/macOS
- ✅ **Arduino/embedded compatibility** - Matches GCC/GNU toolchain behavior
- ⚠️ **Cannot link with MSVC libraries** - Different C++ ABI (use MSVC variant if needed)

**Default behavior (GNU ABI):**
```bash
clang-tool-chain-c main.c -o program       # Uses x86_64-w64-mingw32 target
clang-tool-chain-cpp main.cpp -o program   # Uses GNU ABI, libc++ stdlib
```

**For MSVC ABI (Windows-specific projects):**
```bash
clang-tool-chain-c-msvc main.c -o program.exe     # Uses x86_64-pc-windows-msvc
clang-tool-chain-cpp-msvc main.cpp -o program.exe # Uses MSVC ABI, MSVC stdlib
```

**Download sizes:**
- **First run (GNU target):** ~100-120 MB (includes MinGW-w64 sysroot)
- **MSVC variant:** ~50 MB (uses Visual Studio SDK if available)

**When to use MSVC variant:**
- Linking with MSVC-compiled libraries (DLLs with C++ APIs)
- Windows-specific projects requiring Visual Studio integration
- COM/WinRT/Windows Runtime components
- Using Windows SDK features not available in MinGW
```

### 1.2 Update Command Quick Reference Table

**Replace existing table with:**

```markdown
### 📋 Command Quick Reference

| Task | Command (Default) | Windows MSVC Variant |
|------|-------------------|---------------------|
| **Compile C** | `clang-tool-chain-c main.c -o program` | `clang-tool-chain-c-msvc main.c -o program.exe` |
| **Compile C++** | `clang-tool-chain-cpp main.cpp -o program` | `clang-tool-chain-cpp-msvc main.cpp -o program.exe` |
| **Link Objects** | `clang-tool-chain-ld obj1.o obj2.o -o program` | N/A (use compiler) |
| **Create Library** | `clang-tool-chain-ar rcs libname.a obj1.o obj2.o` | Same |
| **Format Code** | `clang-tool-chain-format -i file.cpp` | Same |
| **Check Installation** | `clang-tool-chain info` | Same |
| **Verify Setup** | `clang-tool-chain-test` | Same |

**Note:** MSVC variants (`*-msvc`) are only available on Windows and require Visual Studio or Windows SDK.
```

### 1.3 Update Platform Support Matrix

**Replace Windows row:**

```markdown
## 🌍 Platform Support Matrix

| Platform | Architecture | LLVM Version | Download Size | Installed Size | Status |
|----------|-------------|--------------|---------------|----------------|--------|
| Windows  | x86_64      | 21.1.5       | ~100 MB*     | ~350 MB        | ✅ Stable |
| ...      | ...         | ...          | ...          | ...            | ... |

\* **Windows Downloads:**
  - **GNU target (default):** ~100 MB (LLVM + MinGW-w64 sysroot)
  - **MSVC target (opt-in):** ~50 MB (LLVM only, requires Visual Studio SDK)
```

### 1.4 Add New Section: Windows Target Selection

**Location:** Before "How It Works" section

**Content:**

```markdown
## 🎯 Windows Target Selection

### Default Behavior (GNU ABI - Recommended)

The default Windows target is `x86_64-w64-mingw32` (GNU ABI) for cross-platform consistency:

```bash
# These commands use GNU ABI by default on Windows:
clang-tool-chain-c hello.c -o hello
clang-tool-chain-cpp hello.cpp -o hello

# Equivalent to explicitly specifying:
clang-tool-chain-c --target=x86_64-w64-mingw32 hello.c -o hello
```

**Why GNU ABI is default:**
1. **Cross-platform consistency** - Same ABI on Linux/macOS/Windows
2. **C++11 strict mode support** - MSVC headers require C++14 features even in C++11 mode
3. **Embedded/Arduino compatibility** - Matches GCC toolchain behavior
4. **Modern C++ standard library** - Uses LLVM's libc++ (same as macOS/Linux)

This matches the approach of [zig cc](https://ziglang.org/learn/overview/#cross-compiling-is-a-first-class-use-case) and other modern cross-platform toolchains.

### MSVC ABI (Windows-Specific Projects)

For Windows-native projects that need MSVC compatibility:

```bash
# Use MSVC variants for Windows-specific development:
clang-tool-chain-c-msvc main.c -o program.exe
clang-tool-chain-cpp-msvc main.cpp -o program.exe

# Or explicitly specify MSVC target with default commands:
clang-tool-chain-c --target=x86_64-pc-windows-msvc main.c -o program.exe
```

**Use MSVC ABI when:**
- Linking with MSVC-compiled DLLs (with C++ APIs)
- Using Windows SDK features not in MinGW
- Requiring Visual Studio debugger integration
- Building COM/WinRT/Windows Runtime components

### Comparison Table

| Feature | GNU ABI (Default) | MSVC ABI (Opt-in) |
|---------|------------------|------------------|
| **C++ Standard Library** | libc++ (LLVM) | MSVC STL |
| **C++ ABI** | Itanium (like GCC) | Microsoft |
| **Cross-platform consistency** | ✅ Yes | ❌ Windows-only |
| **C++11 strict mode** | ✅ Works | ❌ Requires C++14+ |
| **Link with MSVC libs** | ❌ C++ ABI mismatch | ✅ Compatible |
| **Arduino/embedded** | ✅ Compatible | ❌ Different ABI |
| **Download size** | ~100 MB | ~50 MB |
| **Requires Visual Studio** | ❌ No | ⚠️ Recommended |

### Advanced: Manual Target Selection

You can override the target for any compilation:

```bash
# Force GNU target (default on Windows anyway):
clang-tool-chain-c --target=x86_64-w64-mingw32 main.c

# Force MSVC target:
clang-tool-chain-c --target=x86_64-pc-windows-msvc main.c

# Cross-compile for Linux from Windows:
clang-tool-chain-c --target=x86_64-unknown-linux-gnu main.c

# Cross-compile for macOS from Windows:
clang-tool-chain-c --target=arm64-apple-darwin main.c
```

**Note:** Cross-compilation requires appropriate sysroots (not included by default).
```

### 1.5 Update "Verify Installation" Example

**Add Windows-specific test:**

```markdown
### Test Windows Targets

```bash
# Test GNU target (default on Windows):
echo '#include <iostream>' > test.cpp
echo 'int main() { std::cout << "Hello GNU ABI" << std::endl; }' >> test.cpp
clang-tool-chain-cpp -std=c++11 test.cpp -o test

# Test MSVC target (Windows only):
echo 'int main() { return 0; }' > test_msvc.c
clang-tool-chain-c-msvc test_msvc.c -o test_msvc.exe
```
```

### 1.6 Update Entry Points Documentation

**Add to Available Tools section:**

```markdown
**Compiler Wrappers:**
- `clang-tool-chain-c` → C compiler (GNU ABI on Windows)
- `clang-tool-chain-cpp` → C++ compiler (GNU ABI on Windows)
- `clang-tool-chain-c-msvc` → C compiler (MSVC ABI, Windows only)
- `clang-tool-chain-cpp-msvc` → C++ compiler (MSVC ABI, Windows only)
```

---

## Part 2: Downloader and Fetch Changes

### 2.1 Create MinGW Sysroot Extractor

**New file:** `src/clang_tool_chain/downloads/extract_mingw_sysroot.py`

**Purpose:** Extract only the x86_64-w64-mingw32 sysroot from LLVM-MinGW release

**Implementation:**

```python
#!/usr/bin/env python3
"""
Extract MinGW sysroot from LLVM-MinGW release.

This script downloads LLVM-MinGW and extracts only the sysroot directory
(x86_64-w64-mingw32/) which contains headers and libraries for GNU ABI support.
"""

import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

# LLVM-MinGW version and download URLs
LLVM_MINGW_VERSION = "19.1.7"  # Match LLVM version or closest available

LLVM_MINGW_URLS = {
    "x86_64": f"https://github.com/mstorsjo/llvm-mingw/releases/download/"
              f"20241124/llvm-mingw-{LLVM_MINGW_VERSION}-ucrt-x86_64.tar.xz",
    "arm64": f"https://github.com/mstorsjo/llvm-mingw/releases/download/"
             f"20241124/llvm-mingw-{LLVM_MINGW_VERSION}-ucrt-aarch64.tar.xz",
}

# Expected SHA256 checksums (update these after downloading)
CHECKSUMS = {
    "x86_64": "TBD",  # Update after first download
    "arm64": "TBD",   # Update after first download
}


def download_llvm_mingw(arch: str, output_dir: Path) -> Path:
    """Download LLVM-MinGW release."""
    url = LLVM_MINGW_URLS.get(arch)
    if not url:
        raise ValueError(f"Unsupported architecture: {arch}")

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(url).name
    output_path = output_dir / filename

    if output_path.exists():
        print(f"Already downloaded: {output_path}")
        return output_path

    print(f"Downloading: {url}")
    print(f"To: {output_path}")

    urllib.request.urlretrieve(url, output_path)
    print(f"Downloaded: {output_path.stat().st_size / (1024*1024):.2f} MB")

    return output_path


def extract_sysroot(archive_path: Path, extract_dir: Path, arch: str) -> Path:
    """Extract only the sysroot directory from LLVM-MinGW."""
    print(f"\nExtracting sysroot from: {archive_path}")

    # Determine target triple based on architecture
    if arch == "x86_64":
        sysroot_name = "x86_64-w64-mingw32"
    elif arch == "arm64":
        sysroot_name = "aarch64-w64-mingw32"
    else:
        raise ValueError(f"Unknown architecture: {arch}")

    # Extract entire archive first (LLVM-MinGW structure)
    temp_extract = extract_dir / "temp"
    temp_extract.mkdir(parents=True, exist_ok=True)

    print(f"Extracting archive...")
    with tarfile.open(archive_path, 'r:xz') as tar:
        tar.extractall(path=temp_extract)

    # Find the llvm-mingw root directory
    llvm_mingw_root = None
    for item in temp_extract.iterdir():
        if item.is_dir() and item.name.startswith("llvm-mingw"):
            llvm_mingw_root = item
            break

    if not llvm_mingw_root:
        raise RuntimeError("Could not find llvm-mingw root directory")

    print(f"Found LLVM-MinGW root: {llvm_mingw_root}")

    # Copy sysroot directory
    sysroot_src = llvm_mingw_root / sysroot_name
    if not sysroot_src.exists():
        raise RuntimeError(f"Sysroot not found: {sysroot_src}")

    sysroot_dst = extract_dir / sysroot_name
    print(f"Copying sysroot: {sysroot_src} -> {sysroot_dst}")

    if sysroot_dst.exists():
        shutil.rmtree(sysroot_dst)

    shutil.copytree(sysroot_src, sysroot_dst, symlinks=True)

    # Also copy generic headers if they exist
    generic_headers = llvm_mingw_root / "generic-w64-mingw32"
    if generic_headers.exists():
        generic_dst = extract_dir / "generic-w64-mingw32"
        print(f"Copying generic headers: {generic_headers} -> {generic_dst}")
        if generic_dst.exists():
            shutil.rmtree(generic_dst)
        shutil.copytree(generic_headers, generic_dst, symlinks=True)

    # Clean up temp directory
    shutil.rmtree(temp_extract)

    print(f"\n✓ Sysroot extracted to: {sysroot_dst}")
    return sysroot_dst


def create_archive(sysroot_dir: Path, output_dir: Path, arch: str) -> Path:
    """Create compressed archive of sysroot."""
    import zstandard as zstd

    archive_name = f"mingw-sysroot-{LLVM_MINGW_VERSION}-win-{arch}.tar.zst"
    archive_path = output_dir / archive_name

    print(f"\nCreating archive: {archive_path}")

    # Create tar archive in memory, then compress
    import io
    tar_buffer = io.BytesIO()

    with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
        # Determine what to archive
        if arch == "x86_64":
            sysroot_name = "x86_64-w64-mingw32"
        else:
            sysroot_name = "aarch64-w64-mingw32"

        sysroot_path = sysroot_dir.parent / sysroot_name
        generic_path = sysroot_dir.parent / "generic-w64-mingw32"

        if sysroot_path.exists():
            print(f"Adding to archive: {sysroot_name}/")
            tar.add(sysroot_path, arcname=sysroot_name)

        if generic_path.exists():
            print(f"Adding to archive: generic-w64-mingw32/")
            tar.add(generic_path, arcname="generic-w64-mingw32")

    tar_data = tar_buffer.getvalue()
    tar_size = len(tar_data)
    print(f"Tar size: {tar_size / (1024*1024):.2f} MB")

    # Compress with zstd level 22
    print(f"Compressing with zstd level 22...")
    cctx = zstd.ZstdCompressor(level=22, threads=-1)
    compressed_data = cctx.compress(tar_data)

    with open(archive_path, 'wb') as f:
        f.write(compressed_data)

    compressed_size = archive_path.stat().st_size
    ratio = (1 - compressed_size / tar_size) * 100

    print(f"Compressed size: {compressed_size / (1024*1024):.2f} MB")
    print(f"Compression ratio: {ratio:.1f}%")

    return archive_path


def generate_checksums(archive_path: Path) -> dict[str, str]:
    """Generate SHA256 and MD5 checksums."""
    print(f"\nGenerating checksums...")

    sha256_hash = hashlib.sha256()
    md5_hash = hashlib.md5()

    with open(archive_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)
            md5_hash.update(chunk)

    checksums = {
        'sha256': sha256_hash.hexdigest(),
        'md5': md5_hash.hexdigest(),
    }

    # Write checksum files
    sha256_file = Path(str(archive_path) + '.sha256')
    md5_file = Path(str(archive_path) + '.md5')

    with open(sha256_file, 'w') as f:
        f.write(f"{checksums['sha256']}  {archive_path.name}\n")

    with open(md5_file, 'w') as f:
        f.write(f"{checksums['md5']}  {archive_path.name}\n")

    print(f"SHA256: {checksums['sha256']}")
    print(f"MD5: {checksums['md5']}")

    return checksums


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract MinGW sysroot from LLVM-MinGW release"
    )
    parser.add_argument(
        "--arch",
        required=True,
        choices=["x86_64", "arm64"],
        help="Target architecture"
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("work"),
        help="Working directory for downloads and extraction"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("downloads/mingw/win"),
        help="Output directory for final archives"
    )

    args = parser.parse_args()

    work_dir = args.work_dir / args.arch
    output_dir = args.output_dir / args.arch
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*70)
    print("MINGW SYSROOT EXTRACTION")
    print("="*70)
    print(f"Architecture: {args.arch}")
    print(f"Work directory: {work_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Step 1: Download
    archive_path = download_llvm_mingw(args.arch, work_dir)

    # Step 2: Extract sysroot
    sysroot_dir = extract_sysroot(archive_path, work_dir / "extracted", args.arch)

    # Step 3: Create compressed archive
    final_archive = create_archive(sysroot_dir, output_dir, args.arch)

    # Step 4: Generate checksums
    checksums = generate_checksums(final_archive)

    # Step 5: Update manifest
    manifest_path = output_dir / "manifest.json"
    manifest_data = {
        "latest": LLVM_MINGW_VERSION,
        "versions": {
            LLVM_MINGW_VERSION: {
                "version": LLVM_MINGW_VERSION,
                "href": f"./mingw-sysroot-{LLVM_MINGW_VERSION}-win-{args.arch}.tar.zst",
                "sha256": checksums['sha256']
            }
        }
    }

    with open(manifest_path, 'w') as f:
        json.dump(manifest_data, f, indent=2)

    print(f"\n✓ Manifest written to: {manifest_path}")
    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)
    print(f"Archive: {final_archive}")
    print(f"Size: {final_archive.stat().st_size / (1024*1024):.2f} MB")
    print(f"SHA256: {checksums['sha256']}")


if __name__ == "__main__":
    main()
```

### 2.2 Update Downloader for MinGW Sysroots

**File:** `src/clang_tool_chain/downloader.py`

**Changes needed:**

1. Add MinGW manifest base URL:
```python
MINGW_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain/main/downloads/mingw"
```

2. Add function to download MinGW sysroot:
```python
def ensure_mingw_sysroot_installed(platform_name: str, arch: str) -> Path:
    """
    Ensure MinGW sysroot is installed for Windows GNU ABI support.

    Args:
        platform_name: Platform name ("win")
        arch: Architecture ("x86_64" or "arm64")

    Returns:
        Path to the installed MinGW sysroot directory
    """
    if platform_name != "win":
        raise ValueError("MinGW sysroot only needed on Windows")

    # Use same download directory structure
    download_dir = get_toolchain_download_dir()
    install_dir = download_dir / "mingw" / platform_name / arch
    done_file = install_dir / "done.txt"

    # Check if already installed
    if done_file.exists():
        logger.info(f"MinGW sysroot already installed: {install_dir}")
        return install_dir

    # Use file lock to prevent concurrent downloads
    lock_path = download_dir / f"mingw-{platform_name}-{arch}.lock"
    lock = fasteners.InterProcessLock(lock_path)

    with lock:
        # Double-check after acquiring lock
        if done_file.exists():
            logger.info("MinGW sysroot installed by another process")
            return install_dir

        logger.info(f"Downloading MinGW sysroot for {platform_name}/{arch}...")

        # Fetch manifests
        root_manifest_url = f"{MINGW_MANIFEST_BASE_URL}/manifest.json"
        root_manifest = _fetch_json(root_manifest_url, RootManifest, _parse_root_manifest)

        # Find platform and architecture
        platform_entry = next(
            (p for p in root_manifest.platforms if p.platform == platform_name),
            None
        )
        if not platform_entry:
            raise RuntimeError(f"Platform {platform_name} not found in MinGW manifest")

        arch_entry = next(
            (a for a in platform_entry.architectures if a.arch == arch),
            None
        )
        if not arch_entry:
            raise RuntimeError(f"Architecture {arch} not found for {platform_name}")

        # Fetch platform manifest
        manifest_url = f"{MINGW_MANIFEST_BASE_URL}/{arch_entry.manifest_path}"
        manifest = _fetch_json(manifest_url, Manifest, _parse_manifest)

        # Get latest version
        latest_version = manifest.latest
        version_info = manifest.versions.get(latest_version)
        if not version_info:
            raise RuntimeError(f"Version {latest_version} not found in manifest")

        # Download archive
        archive_url = f"{MINGW_MANIFEST_BASE_URL}/{version_info.href}"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "mingw-sysroot.tar.zst"

            logger.info(f"Downloading from: {archive_url}")
            _download_file(archive_url, archive_path)

            # Verify checksum
            logger.info("Verifying checksum...")
            _verify_checksum(archive_path, version_info.sha256)

            # Extract
            logger.info(f"Extracting to: {install_dir}")
            install_dir.mkdir(parents=True, exist_ok=True)
            _extract_archive(archive_path, install_dir)

            # Mark as complete
            done_file.write_text(f"{latest_version}\n")
            logger.info("MinGW sysroot installation complete")

        return install_dir
```

### 2.3 Create MinGW Manifest Structure

**New directory structure:**

```
downloads/mingw/
├── manifest.json                     # Root manifest
└── win/
    └── x86_64/
        ├── manifest.json             # Platform-specific manifest
        ├── mingw-sysroot-19.1.7-win-x86_64.tar.zst
        ├── mingw-sysroot-19.1.7-win-x86_64.tar.zst.sha256
        └── mingw-sysroot-19.1.7-win-x86_64.tar.zst.md5
```

**Root manifest template** (`downloads/mingw/manifest.json`):

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
    }
  ]
}
```

**Platform manifest template** (`downloads/mingw/win/x86_64/manifest.json`):

```json
{
  "latest": "19.1.7",
  "versions": {
    "19.1.7": {
      "version": "19.1.7",
      "href": "win/x86_64/mingw-sysroot-19.1.7-win-x86_64.tar.zst",
      "sha256": "TBD_AFTER_GENERATION"
    }
  }
}
```

### 2.4 Update Wrapper for GNU Default

**File:** `src/clang_tool_chain/wrapper.py`

**Changes:**

1. Add function to determine target:
```python
def should_use_gnu_abi(platform_name: str, args: list[str]) -> bool:
    """
    Determine if GNU ABI should be used based on platform and arguments.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Command-line arguments

    Returns:
        True if GNU ABI should be used, False otherwise
    """
    # Non-Windows always uses default (which is GNU-like anyway)
    if platform_name != "win":
        return False

    # Check if user explicitly specified target
    args_str = " ".join(args)
    if "--target=" in args_str:
        # User specified target explicitly, don't override
        return False

    # Windows defaults to GNU ABI in v2.0+
    return True


def get_gnu_target_args(platform_name: str, arch: str) -> list[str]:
    """
    Get GNU ABI target arguments for Windows.

    Args:
        platform_name: Platform name
        arch: Architecture

    Returns:
        List of additional compiler arguments for GNU ABI
    """
    if platform_name != "win":
        return []

    # Ensure MinGW sysroot is installed
    from . import downloader
    sysroot_dir = downloader.ensure_mingw_sysroot_installed(platform_name, arch)

    # Determine target triple
    if arch == "x86_64":
        target = "x86_64-w64-mingw32"
        sysroot_name = "x86_64-w64-mingw32"
    elif arch == "arm64":
        target = "aarch64-w64-mingw32"
        sysroot_name = "aarch64-w64-mingw32"
    else:
        raise ValueError(f"Unsupported architecture for MinGW: {arch}")

    sysroot_path = sysroot_dir / sysroot_name
    if not sysroot_path.exists():
        raise RuntimeError(f"MinGW sysroot not found: {sysroot_path}")

    return [
        f"--target={target}",
        f"--sysroot={sysroot_path}",
    ]
```

2. Update `exec_tool` to inject GNU args:
```python
def exec_tool(tool_name: str, args: list[str], use_msvc: bool = False) -> NoReturn:
    """
    Execute an LLVM tool with the given arguments.

    Args:
        tool_name: Name of the tool (e.g., "clang", "lld")
        args: Command-line arguments to pass to the tool
        use_msvc: If True on Windows, use MSVC ABI (skip GNU injection)

    Raises:
        RuntimeError: If the tool cannot be found or executed
    """
    platform_name, arch = get_platform_info()
    bin_dir = get_platform_binary_dir()

    # Inject GNU ABI args on Windows (unless MSVC requested)
    if not use_msvc and should_use_gnu_abi(platform_name, args):
        gnu_args = get_gnu_target_args(platform_name, arch)
        args = gnu_args + args
        logger.info(f"Using GNU ABI with args: {gnu_args}")

    # ... rest of existing implementation
```

3. Add MSVC variant entry points:
```python
def clang_msvc_main() -> NoReturn:
    """Entry point for clang-tool-chain-c-msvc (MSVC ABI on Windows)."""
    exec_tool("clang", sys.argv[1:], use_msvc=True)


def clang_cpp_msvc_main() -> NoReturn:
    """Entry point for clang-tool-chain-cpp-msvc (MSVC ABI on Windows)."""
    exec_tool("clang++", sys.argv[1:], use_msvc=True)
```

### 2.5 Update pyproject.toml Entry Points

**File:** `pyproject.toml`

**Add new entry points:**

```toml
[project.scripts]
# ... existing entries ...

# MSVC ABI variants (Windows only)
clang-tool-chain-c-msvc = "clang_tool_chain.wrapper:clang_msvc_main"
clang-tool-chain-cpp-msvc = "clang_tool_chain.wrapper:clang_cpp_msvc_main"
```

---

## Part 3: Test Changes

### 3.1 Update Existing Tests

**File:** `tests/test_cli.py`

**Changes:**

1. Update Windows compilation tests to expect GNU behavior:
```python
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_gnu_default(self):
    """Test that Windows defaults to GNU ABI."""
    # Create test file
    test_file = "test_gnu_default.cpp"
    with open(test_file, "w") as f:
        f.write("#include <iostream>\n")
        f.write("int main() { std::cout << \"Hello\"; return 0; }\n")

    try:
        # Compile with default (should use GNU)
        result = subprocess.run(
            ["clang-tool-chain-cpp", "-v", "-c", test_file],
            capture_output=True,
            text=True
        )

        # Check that target is GNU
        assert "x86_64-w64-mingw32" in result.stderr
        assert result.returncode == 0
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists("test_gnu_default.o"):
            os.remove("test_gnu_default.o")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_msvc_variant(self):
    """Test MSVC variant on Windows."""
    test_file = "test_msvc.c"
    with open(test_file, "w") as f:
        f.write("int main() { return 0; }\n")

    try:
        result = subprocess.run(
            ["clang-tool-chain-c-msvc", "-v", "-c", test_file],
            capture_output=True,
            text=True
        )

        # Check that target is MSVC
        assert "x86_64-pc-windows-msvc" in result.stderr or "msvc" in result.stderr.lower()
        assert result.returncode == 0
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists("test_msvc.o"):
            os.remove("test_msvc.o")
```

### 3.2 Add New Test File for TASK.md Scenarios

**New file:** `tests/test_gnu_abi.py`

```python
"""
Test Windows GNU ABI support (TASK.md scenarios).
"""
import os
import subprocess
import sys
import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
class TestGNUABI:
    """Test suite for Windows GNU ABI support from TASK.md."""

    def test_1_basic_cpp11_gnu_target(self):
        """Test 1: Basic C++11 Standard Library Headers (GNU Target)."""
        test_file = "test_gnu_target.cpp"
        test_code = """
#include <initializer_list>
#include <vector>
#include <string>

int main() {
    std::vector<int> v = {1, 2, 3};
    std::string s = "hello";
    return 0;
}
"""
        with open(test_file, "w") as f:
            f.write(test_code)

        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp", "--target=x86_64-windows-gnu",
                 "-std=gnu++11", "-c", test_file],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0, f"Compilation failed:\n{result.stderr}"
            assert os.path.exists("test_gnu_target.o")
        finally:
            for f in [test_file, "test_gnu_target.o"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_2_cpp11_with_msvc_headers_should_fail(self):
        """Test 2: C++11 Code with MSVC Headers (Should Fail)."""
        test_file = "test_msvc_target.cpp"
        test_code = """
#include <type_traits>
#include <vector>

int main() {
    std::vector<int> v = {1, 2, 3};
    return 0;
}
"""
        with open(test_file, "w") as f:
            f.write(test_code)

        try:
            # This should fail with MSVC headers in C++11 strict mode
            result = subprocess.run(
                ["clang-tool-chain-cpp-msvc", "-std=gnu++11",
                 "-Werror=c++14-extensions", "-c", test_file],
                capture_output=True,
                text=True
            )

            # We expect this to fail
            assert result.returncode != 0
            assert "c++14" in result.stderr.lower() or "auto" in result.stderr.lower()
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_3_complete_compilation_and_linking(self):
        """Test 3: Complete Compilation and Linking (GNU Target)."""
        test_file = "test_full.cpp"
        test_code = """
#include <iostream>
#include <vector>
#include <string>

int main() {
    std::vector<std::string> messages = {"Hello", "World"};
    for (const auto& msg : messages) {
        std::cout << msg << " ";
    }
    std::cout << std::endl;
    return 0;
}
"""
        with open(test_file, "w") as f:
            f.write(test_code)

        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp", "--target=x86_64-windows-gnu",
                 "-std=gnu++11", "-o", "test_program.exe", test_file],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0, f"Compilation failed:\n{result.stderr}"
            assert os.path.exists("test_program.exe")

            # Try to run the program
            run_result = subprocess.run(
                ["./test_program.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert run_result.returncode == 0
            assert "Hello World" in run_result.stdout
        finally:
            for f in [test_file, "test_program.exe"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_4_verify_target_triple(self):
        """Test 4: Verify Target Triple."""
        test_file = "test.cpp"
        with open(test_file, "w") as f:
            f.write("int main() { return 0; }\n")

        try:
            result = subprocess.run(
                ["clang-tool-chain-cpp", "--target=x86_64-windows-gnu",
                 "-v", test_file],
                capture_output=True,
                text=True
            )

            # Check for correct target in verbose output
            output = result.stderr + result.stdout
            assert "x86_64" in output.lower()
            assert "windows-gnu" in output.lower() or "w64-mingw32" in output.lower()
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
            # Clean up potential output files
            for f in ["test.exe", "a.out", "a.exe"]:
                if os.path.exists(f):
                    os.remove(f)

    def test_default_is_gnu_on_windows(self):
        """Test that default compilation uses GNU ABI on Windows."""
        test_file = "test_default.cpp"
        test_code = """
#include <iostream>
int main() {
    std::cout << "Hello" << std::endl;
    return 0;
}
"""
        with open(test_file, "w") as f:
            f.write(test_code)

        try:
            # Compile without explicit --target
            result = subprocess.run(
                ["clang-tool-chain-cpp", "-v", "-std=c++11", "-c", test_file],
                capture_output=True,
                text=True
            )

            # Should use GNU target by default
            output = result.stderr + result.stdout
            assert "w64-mingw32" in output.lower() or "windows-gnu" in output.lower()
            assert result.returncode == 0
        finally:
            for f in [test_file, "test_default.o"]:
                if os.path.exists(f):
                    os.remove(f)
```

### 3.3 Add Downloader Tests for MinGW

**File:** `tests/test_downloader.py`

**Add tests:**

```python
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_mingw_sysroot_download():
    """Test MinGW sysroot download on Windows."""
    from clang_tool_chain import downloader

    # This will trigger download if not already present
    sysroot_dir = downloader.ensure_mingw_sysroot_installed("win", "x86_64")

    assert sysroot_dir.exists()
    assert (sysroot_dir / "x86_64-w64-mingw32").exists()
    assert (sysroot_dir / "x86_64-w64-mingw32" / "include").exists()
    assert (sysroot_dir / "x86_64-w64-mingw32" / "lib").exists()

    # Check for key headers
    headers_dir = sysroot_dir / "x86_64-w64-mingw32" / "include"
    assert (headers_dir / "_mingw.h").exists()

    # Check for key libraries
    lib_dir = sysroot_dir / "x86_64-w64-mingw32" / "lib"
    assert (lib_dir / "libkernel32.a").exists()
```

### 3.4 Update Integration Tests

**File:** `tests/test_integration.py`

**Changes:**

1. Update expected download sizes for Windows:
```python
EXPECTED_DOWNLOAD_SIZES = {
    "win": {
        "x86_64": (90, 130),  # ~100 MB range (LLVM + MinGW)
    },
    # ... other platforms
}
```

2. Add test for both GNU and MSVC compilation:
```python
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_both_windows_targets():
    """Test both GNU and MSVC targets on Windows."""
    test_file = "test_both.c"
    with open(test_file, "w") as f:
        f.write("int main() { return 0; }\n")

    try:
        # Test GNU (default)
        result_gnu = subprocess.run(
            ["clang-tool-chain-c", "-c", test_file, "-o", "test_gnu.o"],
            capture_output=True
        )
        assert result_gnu.returncode == 0
        assert os.path.exists("test_gnu.o")

        # Test MSVC
        result_msvc = subprocess.run(
            ["clang-tool-chain-c-msvc", "-c", test_file, "-o", "test_msvc.o"],
            capture_output=True
        )
        assert result_msvc.returncode == 0
        assert os.path.exists("test_msvc.o")
    finally:
        for f in [test_file, "test_gnu.o", "test_msvc.o"]:
            if os.path.exists(f):
                os.remove(f)
```

### 3.5 Update CLI Tests

**File:** `tests/test_cli.py`

**Add test for list-tools:**

```python
def test_list_tools_includes_msvc_variants():
    """Test that list-tools includes MSVC variants on Windows."""
    result = subprocess.run(
        ["clang-tool-chain", "list-tools"],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    output = result.stdout

    if sys.platform == "win32":
        assert "clang-tool-chain-c-msvc" in output
        assert "clang-tool-chain-cpp-msvc" in output
```

---

## Part 4: Agent Loop Implementation Plan

### Phase 1: Research and Setup (Completed Above)

**Status:** ✅ Complete
- Researched LLVM-MinGW differences
- Identified minimum required components
- Documented all changes needed

### Phase 2: Create MinGW Sysroot Infrastructure

**Agent Task 1:** Create MinGW sysroot extractor tool

```yaml
Task: Create extract_mingw_sysroot.py
Description: |
  Create src/clang_tool_chain/downloads/extract_mingw_sysroot.py that:
  1. Downloads LLVM-MinGW release from GitHub
  2. Extracts only x86_64-w64-mingw32 sysroot directory
  3. Creates compressed tar.zst archive
  4. Generates checksums (SHA256, MD5)
  5. Creates manifest.json
Tools: Write, Bash
Success Criteria:
  - Script runs without errors
  - Produces mingw-sysroot-*.tar.zst archive
  - Archive is ~70-100 MB
  - Checksums are generated
  - Manifest is created
```

**Agent Task 2:** Generate MinGW sysroot archives

```yaml
Task: Generate MinGW sysroot archives for Windows x86_64
Description: |
  Run extract_mingw_sysroot.py to generate actual archives:
  1. Run for x86_64 architecture
  2. Place in downloads/mingw/win/x86_64/
  3. Verify archive contents
  4. Update manifest with actual checksums
Tools: Bash, Edit
Success Criteria:
  - Archive exists in downloads/mingw/win/x86_64/
  - Manifest has correct SHA256
  - Archive extracts correctly
  - Size is reasonable (~70-120 MB)
```

**Agent Task 3:** Create root MinGW manifest

```yaml
Task: Create downloads/mingw/manifest.json
Description: |
  Create root manifest for MinGW sysroots following existing pattern
Tools: Write
Success Criteria:
  - Manifest follows same structure as downloads/clang/manifest.json
  - Points to win/x86_64/manifest.json
  - Valid JSON format
```

### Phase 3: Update Downloader Logic

**Agent Task 4:** Add MinGW downloader functions

```yaml
Task: Update src/clang_tool_chain/downloader.py
Description: |
  Add MinGW sysroot download support:
  1. Add MINGW_MANIFEST_BASE_URL constant
  2. Add ensure_mingw_sysroot_installed() function
  3. Follow same pattern as ensure_toolchain_installed()
  4. Use file locking for concurrent safety
  5. Verify checksums
  6. Extract to ~/.clang-tool-chain/mingw/win/x86_64/
Tools: Read, Edit
Success Criteria:
  - Function downloads MinGW sysroot on first call
  - Subsequent calls return cached path
  - File locking prevents concurrent downloads
  - Checksums are verified
  - done.txt marker is created
Testing:
  - Run ensure_mingw_sysroot_installed("win", "x86_64")
  - Verify download occurs
  - Run again, verify no re-download
  - Check ~/.clang-tool-chain/mingw/ structure
```

### Phase 4: Update Wrapper for GNU Default

**Agent Task 5:** Add GNU ABI detection logic

```yaml
Task: Update src/clang_tool_chain/wrapper.py for GNU default
Description: |
  Modify wrapper.py to default Windows to GNU ABI:
  1. Add should_use_gnu_abi() function
  2. Add get_gnu_target_args() function
  3. Update exec_tool() to inject GNU args
  4. Add clang_msvc_main() and clang_cpp_msvc_main() entry points
Tools: Read, Edit
Success Criteria:
  - Windows defaults to --target=x86_64-w64-mingw32
  - --sysroot points to MinGW sysroot
  - User can override with explicit --target
  - MSVC entry points skip GNU injection
Testing:
  - Test default clang-tool-chain-c on Windows
  - Verify --target=x86_64-w64-mingw32 is used
  - Verify --sysroot is set correctly
  - Test clang-tool-chain-c-msvc doesn't inject GNU args
```

**Agent Task 6:** Update entry points in pyproject.toml

```yaml
Task: Add MSVC variant entry points
Description: |
  Add new entry points to pyproject.toml:
  - clang-tool-chain-c-msvc
  - clang-tool-chain-cpp-msvc
Tools: Read, Edit
Success Criteria:
  - Entry points added to [project.scripts]
  - Points to correct functions in wrapper.py
  - After reinstall, commands are available
Testing:
  - Run: uv pip install -e .
  - Verify: clang-tool-chain-c-msvc --version
  - Verify: clang-tool-chain-cpp-msvc --version
```

### Phase 5: Update Tests

**Agent Task 7:** Update existing Windows tests

```yaml
Task: Update tests to expect GNU default on Windows
Description: |
  Modify tests/test_cli.py:
  1. Update Windows compilation tests
  2. Add test_windows_gnu_default()
  3. Add test_windows_msvc_variant()
  4. Update any tests that assume MSVC default
Tools: Read, Edit, Bash
Success Criteria:
  - All existing tests pass
  - New tests verify GNU default
  - MSVC variant tests pass
Testing:
  - pytest tests/test_cli.py -v -k windows
```

**Agent Task 8:** Create TASK.md test scenarios

```yaml
Task: Create tests/test_gnu_abi.py
Description: |
  Implement all 4 test scenarios from TASK.md plus default test:
  1. test_1_basic_cpp11_gnu_target
  2. test_2_cpp11_with_msvc_headers_should_fail
  3. test_3_complete_compilation_and_linking
  4. test_4_verify_target_triple
  5. test_default_is_gnu_on_windows
Tools: Write, Bash
Success Criteria:
  - All 5 tests implemented
  - Tests only run on Windows (skipif decorator)
  - Tests pass on Windows
  - Tests properly clean up temp files
Testing:
  - pytest tests/test_gnu_abi.py -v (on Windows)
```

**Agent Task 9:** Add MinGW downloader tests

```yaml
Task: Add MinGW sysroot download tests
Description: |
  Update tests/test_downloader.py:
  1. Add test_mingw_sysroot_download()
  2. Verify sysroot structure
  3. Check for key headers and libraries
Tools: Read, Edit, Bash
Success Criteria:
  - Test downloads MinGW sysroot
  - Verifies directory structure
  - Checks for _mingw.h and libkernel32.a
Testing:
  - pytest tests/test_downloader.py -v -k mingw
```

**Agent Task 10:** Update integration tests

```yaml
Task: Update integration tests for new download sizes
Description: |
  Modify tests/test_integration.py:
  1. Update expected Windows download size to ~100 MB
  2. Add test_both_windows_targets()
  3. Update any size-related assertions
Tools: Read, Edit
Success Criteria:
  - Integration tests expect correct sizes
  - Both targets tested on Windows
Testing:
  - pytest tests/test_integration.py -v
```

### Phase 6: Documentation

**Agent Task 11:** Update README.md

```yaml
Task: Update README with Windows GNU ABI documentation
Description: |
  Add all sections from Part 1 of this document:
  1. Add Windows GNU ABI warning section
  2. Update Command Quick Reference table
  3. Update Platform Support Matrix
  4. Add "Windows Target Selection" section
  5. Update entry points documentation
  6. Update examples
Tools: Read, Edit
Success Criteria:
  - All new sections added
  - Tables properly formatted
  - Examples are correct
  - Links work
  - Markdown is valid
Testing:
  - Render README in GitHub
  - Check all links
  - Verify formatting
```

**Agent Task 12:** Update CLAUDE.md

```yaml
Task: Update CLAUDE.md with Windows GNU ABI information
Description: |
  Update project instructions:
  1. Add to Version Information table
  2. Update Entry Points section
  3. Add testing information
  4. Update development workflow
Tools: Read, Edit
Success Criteria:
  - CLAUDE.md reflects new Windows behavior
  - Entry points documented
  - Testing scenarios included
```

### Phase 7: Version and Release

**Agent Task 13:** Update version to 2.0.0

```yaml
Task: Bump version to 2.0.0
Description: |
  Update version in src/clang_tool_chain/__version__.py to 2.0.0
  This is a breaking change (Windows default behavior changed)
Tools: Read, Edit
Success Criteria:
  - Version is 2.0.0
  - Version follows semver
```

**Agent Task 14:** Update CLI info command

```yaml
Task: Update info command to show target information
Description: |
  Modify src/clang_tool_chain/cli.py:
  1. Show default Windows target in info output
  2. Mention MSVC variants availability
Tools: Read, Edit
Success Criteria:
  - clang-tool-chain info shows Windows uses GNU by default
  - Mentions clang-tool-chain-c-msvc availability
```

### Phase 8: Testing and Validation

**Agent Task 15:** Run full test suite

```yaml
Task: Run complete test suite on all platforms
Description: |
  Execute all tests and verify they pass:
  1. Run on Windows (primary concern)
  2. Run on Linux (verify no regressions)
  3. Run on macOS (verify no regressions)
Tools: Bash
Success Criteria:
  - All tests pass on Windows
  - No regressions on Linux
  - No regressions on macOS
  - Coverage remains high
Commands:
  - uv run pytest -v
  - uv run pytest tests/test_gnu_abi.py -v (Windows only)
```

**Agent Task 16:** Manual verification with TASK.md scenarios

```yaml
Task: Manually test the 4 TASK.md scenarios
Description: |
  Run the exact commands from TASK.md to verify:
  1. Basic C++11 compilation with GNU target
  2. MSVC C++11 compilation (should fail)
  3. Complete linking with GNU target
  4. Verify target triple
Tools: Bash
Success Criteria:
  - Test 1: Compiles successfully
  - Test 2: Fails as expected with C++14 error
  - Test 3: Produces working executable
  - Test 4: Shows correct target triple
```

### Phase 9: Final Cleanup

**Agent Task 17:** Update .gitignore if needed

```yaml
Task: Ensure MinGW artifacts are properly ignored
Description: |
  Check .gitignore includes:
  1. work/ directory (for extraction)
  2. .tar.zst archives in root (if generated locally)
Tools: Read, Edit
Success Criteria:
  - Generated artifacts not tracked
  - downloads/mingw/ IS tracked (published)
```

**Agent Task 18:** Create migration guide

```yaml
Task: Create MIGRATION_V2.md
Description: |
  Document migration from v1.x to v2.0:
  1. What changed (Windows default)
  2. How to update code
  3. Breaking changes list
  4. How to use MSVC variant
Tools: Write
Success Criteria:
  - Clear migration guide exists
  - Examples for both scenarios
  - Troubleshooting section
```

---

## Execution Order Summary

### Ultra-Think Agent Loop Plan

**Context:** We're adding Windows GNU ABI support, making it the default (breaking change for v2.0.0)

**Prerequisites:**
- LLVM-MinGW release available (19.1.7 or 21.1.x)
- ~500 MB disk space for work directory
- Windows machine for testing (or Windows VM)
- Access to commit to downloads/ directory

**Execution Sequence:**

```
Phase 1: Infrastructure Setup
├─ Task 1: Create extract_mingw_sysroot.py ⏱️ 30 min
├─ Task 2: Generate MinGW archives         ⏱️ 45 min (download + compress)
└─ Task 3: Create root manifest            ⏱️ 5 min

Phase 2: Code Updates
├─ Task 4: Update downloader.py            ⏱️ 30 min
├─ Task 5: Update wrapper.py               ⏱️ 45 min
└─ Task 6: Update pyproject.toml           ⏱️ 5 min

Phase 3: Testing
├─ Task 7: Update existing tests           ⏱️ 20 min
├─ Task 8: Create test_gnu_abi.py          ⏱️ 30 min
├─ Task 9: Add downloader tests            ⏱️ 15 min
└─ Task 10: Update integration tests       ⏱️ 15 min

Phase 4: Documentation
├─ Task 11: Update README.md               ⏱️ 30 min
├─ Task 12: Update CLAUDE.md               ⏱️ 15 min
├─ Task 13: Bump version to 2.0.0          ⏱️ 5 min
└─ Task 14: Update CLI info                ⏱️ 10 min

Phase 5: Validation
├─ Task 15: Run full test suite            ⏱️ 10 min
├─ Task 16: Manual TASK.md verification    ⏱️ 15 min
├─ Task 17: Update .gitignore              ⏱️ 5 min
└─ Task 18: Create MIGRATION_V2.md         ⏱️ 20 min

Total Estimated Time: ~5-6 hours
```

**Critical Path:**
1. Task 1-3 (must be done first - creates artifacts)
2. Task 4-6 (core implementation)
3. Task 7-10 (tests must pass)
4. Task 11-14 (documentation)
5. Task 15-18 (validation)

**Parallelization Opportunities:**
- Tasks 11-14 can be done in parallel with 7-10
- Task 17-18 can be done anytime after Task 1

**Rollback Plan:**
If issues are discovered:
1. Revert wrapper.py changes (remove GNU default)
2. Keep MinGW infrastructure (for future use)
3. Document as experimental feature
4. Stay on v1.x version

**Success Metrics:**
- ✅ All 4 TASK.md scenarios pass
- ✅ FastLED use case works (C++11 strict mode)
- ✅ No regressions on Linux/macOS
- ✅ Windows tests pass with both GNU and MSVC
- ✅ Documentation is clear and complete
- ✅ Download size is acceptable (~100 MB)

**Risk Mitigation:**
- Test on multiple Windows versions (10, 11)
- Test with and without Visual Studio installed
- Test in CI environment (GitHub Actions)
- Provide clear error messages if MinGW download fails
- Document troubleshooting steps

---

## Next Steps

After this LOOP.md is approved:

1. **Start with Phase 1, Task 1** - Create the extractor tool
2. **Generate actual artifacts** - Run on Windows to create archives
3. **Commit artifacts to repo** - Push downloads/mingw/ directory
4. **Implement downloader** - Add MinGW support
5. **Update wrapper** - Make GNU default on Windows
6. **Add tests** - Verify everything works
7. **Update docs** - Make it clear for users
8. **Test thoroughly** - All platforms
9. **Create release** - v2.0.0 with breaking changes noted

**Ready to proceed?** The agent loop is designed to be executed sequentially with clear success criteria at each step.

---

## Progress Tracking

### ✅ Iteration 1 (Phase 2, Task 1) - COMPLETED
**Date:** 2025-11-09
**Task:** Create extract_mingw_sysroot.py script
**Status:** ✅ Complete
**Deliverables:**
- Created `src/clang_tool_chain/downloads/extract_mingw_sysroot.py` (300 lines)
- Script tested and validated (help output, CLI parsing)
- Follows project code patterns and style
- Ready for use in next iteration

**Details:** See `.agent_task/ITERATION_1.md`

---

### ✅ Iteration 2 (Phase 3, Task 4) - COMPLETED
**Date:** 2025-11-09
**Task:** Update downloader.py to add MinGW sysroot download support
**Status:** ✅ Complete
**Deliverables:**
- Added `MINGW_MANIFEST_BASE_URL` constant to downloader.py
- Implemented 7 MinGW-specific functions (207 lines of code)
- Created manifest structure: `downloads/mingw/manifest.json`
- Created platform manifest: `downloads/mingw/win/x86_64/manifest.json`
- Created maintainer documentation: `downloads/mingw/README.md`
- Validated syntax and JSON structure
- Follows existing IWYU pattern for consistency

**Key Functions Added:**
- `ensure_mingw_sysroot_installed(platform, arch)` - Main entry point
- `fetch_mingw_root_manifest()` - Fetches root manifest
- `fetch_mingw_platform_manifest()` - Fetches platform manifest
- `get_mingw_install_dir()` - Returns install directory
- `download_and_install_mingw()` - Downloads and extracts archive
- Plus supporting functions for locking and checking installation

**Details:** See `.agent_task/ITERATION_2.md`

---

### ✅ Iteration 3 (Phase 4, Task 5) - COMPLETED
**Date:** 2025-11-09
**Task:** Update wrapper.py to add GNU ABI detection logic and implement default GNU target for Windows
**Status:** ✅ Complete
**Deliverables:**
- Added `_should_use_gnu_abi()` function - Detects when to use GNU ABI on Windows
- Added `_get_gnu_target_args()` function - Gets GNU target compiler flags with MinGW sysroot
- Updated `execute_tool()` to inject GNU ABI args on Windows (added `use_msvc` parameter)
- Updated `run_tool()` to inject GNU ABI args on Windows
- Updated `sccache_clang_main()` to support GNU ABI
- Updated `sccache_clang_cpp_main()` to support GNU ABI
- Created `clang_msvc_main()` entry point for MSVC ABI variant
- Created `clang_cpp_msvc_main()` entry point for MSVC C++ ABI variant
- Total additions: ~159 lines of functional code
- All syntax validated successfully

**GNU ABI Injection Logic:**
- Windows defaults to `--target=x86_64-w64-mingw32` automatically
- User can override with explicit `--target` flag
- MSVC variants skip GNU injection entirely
- MinGW sysroot downloaded on-demand via `ensure_mingw_sysroot_installed()`
- Graceful error handling if sysroot installation fails

**Entry Points Created:**
- `clang_msvc_main()` - For `clang-tool-chain-c-msvc` command
- `clang_cpp_msvc_main()` - For `clang-tool-chain-cpp-msvc` command

**Details:** See `.agent_task/ITERATION_3.md`

---

### ✅ Iteration 4 (Phase 4, Task 6) - COMPLETED
**Date:** 2025-11-09
**Task:** Update pyproject.toml to add MSVC variant entry points
**Status:** ✅ Complete
**Deliverables:**
- Added `clang-tool-chain-c-msvc` entry point to pyproject.toml (line 72)
- Added `clang-tool-chain-cpp-msvc` entry point to pyproject.toml (line 73)
- Both entry points registered in `[project.scripts]` section
- Total entry points increased from 26 to 28
- TOML syntax validated successfully with Python's tomllib
- Cross-referenced with wrapper.py functions (lines 709, 714)

**Entry Points Registered:**
```toml
# MSVC ABI variants (Windows only)
clang-tool-chain-c-msvc = "clang_tool_chain.wrapper:clang_msvc_main"
clang-tool-chain-cpp-msvc = "clang_tool_chain.wrapper:clang_cpp_msvc_main"
```

**Integration Status:**
- Entry points correctly point to functions created in Iteration 3
- Commands will be available after package reinstallation: `uv pip install -e .`
- No syntax errors or configuration issues

**Next Iteration Should Do:**
- **CRITICAL DECISION:** Either generate MinGW archives (Phase 2, Task 2) OR create tests (Phase 3, Task 7)
- **Recommendation:** Generate archives first to enable full end-to-end testing

**Details:** See `.agent_task/ITERATION_4.md`

---

### ✅ Iteration 5 (Phase 2, Task 2) - COMPLETED
**Date:** 2025-11-09
**Task:** Generate MinGW sysroot archives for Windows x86_64
**Status:** ✅ Complete
**Deliverables:**
- Generated MinGW-w64 sysroot archive from LLVM-MinGW 20251104 (LLVM 21.1.5)
- Archive size: 12.14 MB compressed (176.46 MB uncompressed, 93.1% compression)
- SHA256: 2f0b5335580f969fc3d57fc345a9f430a53a82bf2a27bf55558022771162dcf3
- Verified archive contents: C++ headers (iostream, vector, string, initializer_list)
- 955 library files included
- Updated extract_mingw_sysroot.py to use correct LLVM-MinGW release
- Fixed extraction to include top-level include/ directory with C++ headers
- Committed to repository (commit 8529f5c)

**Archive Contents:**
- `x86_64-w64-mingw32/` - MinGW sysroot with runtime libraries
- `include/` - Complete C/C++ standard library headers (libc++ from LLVM)
- `include/c++/v1/` - LLVM libc++ headers

**Script Updates:**
- Changed LLVM-MinGW version from 20241124 to 20251104
- Changed archive format from tar.xz to .zip (Windows native)
- Added zipfile module import
- Added extraction of top-level include/ directory
- Updated create_archive to include include/ in output

**Files Committed:**
- `downloads/mingw/manifest.json` - Root manifest
- `downloads/mingw/README.md` - Maintainer documentation
- `downloads/mingw/win/x86_64/manifest.json` - Platform manifest
- `downloads/mingw/win/x86_64/mingw-sysroot-21.1.5-win-x86_64.tar.zst` - Archive (12.14 MB)
- `downloads/mingw/win/x86_64/mingw-sysroot-21.1.5-win-x86_64.tar.zst.sha256` - Checksum
- `downloads/mingw/win/x86_64/mingw-sysroot-21.1.5-win-x86_64.tar.zst.md5` - Checksum
- `src/clang_tool_chain/downloads/extract_mingw_sysroot.py` - Updated extraction tool

**Next Iteration Should Do:**
- **Phase 3, Task 7:** Update existing Windows tests to expect GNU default
- OR continue with testing infrastructure (Tasks 8-10)

**Details:** See `.agent_task/ITERATION_5.md`
