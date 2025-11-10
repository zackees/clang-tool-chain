#!/usr/bin/env python3
"""
Fetch and Archive LLVM/Clang Toolchain

This script automates the entire process:
1. Downloads LLVM/Clang binaries for specified platform/architecture
2. Strips them of unnecessary extras (keeping only essential build tools)
3. Deduplicates identical binaries
4. Creates hard-linked structure
5. Compresses with zstd level 22
6. Names according to convention: llvm-{version}-{platform}-{arch}.tar.zst
7. Generates checksums
8. Places final archive in downloads-bins/assets/clang/{platform}/{arch}/

Usage:
    python -m clang_tool_chain.downloads.fetch_and_archive --platform win --arch x86_64
    python -m clang_tool_chain.downloads.fetch_and_archive --platform linux --arch x86_64
    python -m clang_tool_chain.downloads.fetch_and_archive --platform darwin --arch arm64

Requirements:
    - Python 3.7+
    - zstandard module: pip install zstandard
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

# ============================================================================
# Configuration
# ============================================================================

LLVM_VERSION = "19.1.7"

# Official LLVM download URLs
LLVM_DOWNLOAD_URLS = {
    (
        "win",
        "x86_64",
    ): f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{LLVM_VERSION}/LLVM-{LLVM_VERSION}-win64.exe",
    (
        "win",
        "arm64",
    ): f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{LLVM_VERSION}/LLVM-{LLVM_VERSION}-woa64.exe",
    (
        "linux",
        "x86_64",
    ): f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{LLVM_VERSION}/LLVM-{LLVM_VERSION}-Linux-X64.tar.xz",
    (
        "linux",
        "arm64",
    ): f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{LLVM_VERSION}/clang+llvm-{LLVM_VERSION}-aarch64-linux-gnu.tar.xz",
    (
        "darwin",
        "x86_64",
    ): f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{LLVM_VERSION}/LLVM-{LLVM_VERSION}-macOS-X64.tar.xz",
    (
        "darwin",
        "arm64",
    ): f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{LLVM_VERSION}/LLVM-{LLVM_VERSION}-macOS-ARM64.tar.xz",
}

# Essential binaries to keep (for C/C++ compilation)
ESSENTIAL_BINARIES = {
    # Compilers
    "clang",
    "clang++",
    "clang-cl",
    "clang-cpp",
    # Linkers
    "lld",
    "lld-link",
    "ld.lld",
    "ld64.lld",
    "wasm-ld",
    # Archive tools
    "llvm-ar",
    "llvm-ranlib",
    # Binary utilities
    "llvm-nm",
    "llvm-objdump",
    "llvm-objcopy",
    "llvm-strip",
    "llvm-readobj",
    "llvm-readelf",
    "llvm-symbolizer",
    # NOTE: Removed clang-format and clang-tidy to reduce archive size
    # These are code quality tools, not needed for compilation
}


# ============================================================================
# Utility Functions
# ============================================================================


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def download_file(url: str, output_path: Path | str, show_progress: bool = True) -> None:
    """Download a file with progress indication."""
    print(f"Downloading from: {url}")
    print(f"Saving to: {output_path}")

    output_path = Path(output_path)
    breadcrumb_path = Path(str(output_path) + ".downloading")

    # Create breadcrumb file to mark download in progress
    breadcrumb_path.touch()

    def report_progress(block_num: int, block_size: int, total_size: int) -> None:
        if show_progress and total_size > 0:
            downloaded = block_num * block_size
            percent = min(100, (downloaded / total_size) * 100)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\rProgress: {percent:5.1f}% ({mb_downloaded:6.1f} MB / {mb_total:6.1f} MB)", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, output_path, reporthook=report_progress)
        if show_progress:
            print()  # New line after progress
        # Download completed successfully, remove breadcrumb
        breadcrumb_path.unlink(missing_ok=True)
    except (KeyboardInterrupt, Exception):
        # Download interrupted or failed, clean up partial file and breadcrumb
        if output_path.exists():
            output_path.unlink()
        breadcrumb_path.unlink(missing_ok=True)
        raise


def get_file_hash(filepath: Path | str, algorithm: str = "md5") -> str:
    """Calculate hash of a file."""
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_binaries(directory: Path | str, extensions: list[str] | None = None) -> list[Path]:
    """Find all binary files in a directory."""
    if extensions is None:
        extensions = [".exe", ""]  # Windows executables and Unix executables (no extension)

    directory = Path(directory)
    binaries = []

    for ext in extensions:
        if ext:
            binaries.extend(directory.glob(f"**/*{ext}"))
        else:
            # Find files without extension that are executable
            for item in directory.rglob("*"):
                if item.is_file() and os.access(item, os.X_OK) and not item.suffix:
                    binaries.append(item)

    return binaries


def should_exclude_lib_file(file_path: Path | str) -> bool:
    """
    Determine if a library file should be excluded to reduce size.

    Excludes:
    - Fortran runtime libraries (libflang_rt.*) - only needed for Fortran compilation
    - hwasan_symbolize binary - debugging tool, not needed for compilation

    Keeps:
    - Headers (.h, .inc, .modulemap, .tcc)
    - Runtime libraries (including sanitizers)
    - Builtins
    - Directory structures
    """
    file_path = Path(file_path)
    name = file_path.name

    # Always keep directories
    if file_path.is_dir():
        return False

    # Always keep headers and text files
    if file_path.suffix in {".h", ".inc", ".modulemap", ".tcc", ".txt"}:
        return False

    # Exclude Fortran runtime (27 MB) - not needed for C/C++
    if "libflang_rt" in name:
        return True

    # Exclude hwasan_symbolize binary - debugging tool only
    # Keep everything else (sanitizers, builtins, headers, etc.)
    return "hwasan_symbolize" in name


# ============================================================================
# Step 1: Download
# ============================================================================


def download_llvm(platform: str, arch: str, work_dir: Path) -> Path:
    """Download LLVM binaries for the specified platform and architecture."""
    print_section("STEP 1: DOWNLOAD LLVM BINARIES")

    key = (platform, arch)
    if key not in LLVM_DOWNLOAD_URLS:
        raise ValueError(f"Unsupported platform/arch combination: {platform}/{arch}")

    url = LLVM_DOWNLOAD_URLS[key]
    filename = Path(url).name
    download_path = work_dir / filename
    breadcrumb_path = Path(str(download_path) + ".downloading")

    print(f"Platform: {platform}")
    print(f"Architecture: {arch}")
    print(f"LLVM Version: {LLVM_VERSION}")
    print()

    # Check for incomplete download from previous attempt
    if breadcrumb_path.exists():
        print(f"⚠️  Found incomplete download marker: {breadcrumb_path.name}")
        if download_path.exists():
            print(f"Removing partial download: {download_path}")
            download_path.unlink()
        breadcrumb_path.unlink()
        print()

    if download_path.exists():
        print(f"File already exists: {download_path}")
        print("Skipping download...")
    else:
        download_file(url, download_path)

    print(f"\nDownloaded: {download_path}")
    print(f"Size: {download_path.stat().st_size / (1024*1024):.2f} MB")

    return download_path


# ============================================================================
# Step 2: Extract
# ============================================================================


def extract_archive(archive_path: Path, extract_dir: Path) -> Path:
    """Extract the downloaded archive."""
    print_section("STEP 2: EXTRACT ARCHIVE")

    archive_path = Path(archive_path)
    extract_dir = Path(extract_dir)

    print(f"Archive: {archive_path}")
    print(f"Extract to: {extract_dir}")
    print()

    extract_dir.mkdir(parents=True, exist_ok=True)

    if archive_path.suffix == ".exe":
        # Windows installer - need 7z or similar
        print("Windows .exe installer detected")
        print("Using 7z to extract...")

        # Try to use 7z
        try:
            subprocess.run(["7z", "x", str(archive_path), f"-o{extract_dir}", "-y"], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                "7z is required to extract Windows .exe installer.\n"
                "Install 7z: https://www.7-zip.org/\n"
                "Or provide pre-extracted binaries."
            ) from e

    elif archive_path.suffix == ".xz" or archive_path.name.endswith(".tar.xz"):
        print("Extracting tar.xz archive...")
        print()

        # Try to use external tar command for better performance (supports multi-threaded decompression)
        # Falls back to Python implementation if tar command not available
        import time

        start = time.time()

        # Check if we have tar command available (much faster, can use pixz for parallel decompression)
        tar_available = shutil.which("tar") is not None

        if tar_available:
            print("Using system tar command for faster extraction...")
            print("NOTE: Progress tracking not available with external tar")
            print("      The process IS working - please wait (typically 30-90 seconds for LLVM)")
            print()
            print("Extracting...")
            sys.stdout.flush()
            try:
                # Use tar command - it's much faster and may use parallel decompression
                subprocess.run(
                    ["tar", "-xJf", str(archive_path), "-C", str(extract_dir)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                elapsed = time.time() - start
                print(f"Extraction complete in {elapsed:.1f}s")
            except subprocess.CalledProcessError as e:
                print(f"External tar failed: {e.stderr}")
                print("Falling back to Python extraction...")
                tar_available = False

        if not tar_available:
            # Fallback to Python's built-in lzma and tarfile modules
            print("Using Python built-in extraction (slower but with progress tracking)...")
            print("Reading archive index (this may take a moment)...")
            import lzma

            with lzma.open(archive_path) as xz_file, tarfile.open(fileobj=xz_file) as tar:
                # Get list of members for progress tracking
                members = tar.getmembers()
                total_members = len(members)
                total_size = sum(m.size for m in members)

                print(f"Found {total_members} files/directories to extract ({total_size / (1024*1024):.1f} MB)")
                print()

                extracted_count = 0
                extracted_size = 0
                last_progress = -1
                last_update_time = start
                progress_counter = 0

                for member in members:
                    tar.extract(member, path=extract_dir)
                    extracted_count += 1
                    extracted_size += member.size

                    # Show progress every 5% or every 2 seconds
                    current_time = time.time()
                    # Use data size for progress percentage (more meaningful than file count)
                    progress = int((extracted_size / total_size) * 100) if total_size > 0 else 0
                    time_since_update = current_time - last_update_time

                    if (progress // 5 > last_progress // 5) or (time_since_update >= 2.0):
                        elapsed = current_time - start
                        mb_extracted = extracted_size / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        mb_per_sec = mb_extracted / elapsed if elapsed > 0 else 0

                        progress_counter += 1
                        print(
                            f"  [{progress_counter:3d}] Progress: {progress:3d}% "
                            f"({mb_extracted:7.1f} / {mb_total:7.1f} MB) "
                            f"- {mb_per_sec:6.1f} MB/s - {elapsed:5.1f}s elapsed",
                            flush=True,
                        )
                        last_progress = progress
                        last_update_time = current_time

                elapsed = time.time() - start
                print()
                print(f"Extracted {extracted_count} files ({extracted_size / (1024*1024):.1f} MB) in {elapsed:.1f}s")

    elif archive_path.suffix == ".gz" or archive_path.name.endswith(".tar.gz"):
        print("Extracting tar.gz archive...")
        print()
        import gzip
        import time

        start = time.time()

        with gzip.open(archive_path, "rb") as gz_file, tarfile.open(fileobj=gz_file) as tar:
            # Get list of members for progress tracking
            members = tar.getmembers()
            total_members = len(members)
            total_size = sum(m.size for m in members)

            print(f"Found {total_members} files/directories to extract ({total_size / (1024*1024):.1f} MB)")
            print()

            extracted_count = 0
            extracted_size = 0
            last_progress = -1
            last_update_time = start
            progress_counter = 0

            for member in members:
                tar.extract(member, path=extract_dir)
                extracted_count += 1
                extracted_size += member.size

                # Show progress every 5% or every 2 seconds
                current_time = time.time()
                # Use data size for progress percentage (more meaningful than file count)
                progress = int((extracted_size / total_size) * 100) if total_size > 0 else 0
                time_since_update = current_time - last_update_time

                if (progress // 5 > last_progress // 5) or (time_since_update >= 2.0):
                    elapsed = current_time - start
                    mb_extracted = extracted_size / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    mb_per_sec = mb_extracted / elapsed if elapsed > 0 else 0

                    progress_counter += 1
                    print(
                        f"  [{progress_counter:3d}] Progress: {progress:3d}% "
                        f"({mb_extracted:7.1f} / {mb_total:7.1f} MB) "
                        f"- {mb_per_sec:6.1f} MB/s - {elapsed:5.1f}s elapsed",
                        flush=True,
                    )
                    last_progress = progress
                    last_update_time = current_time

            elapsed = time.time() - start
            print()
            print(f"Extracted {extracted_count} files ({extracted_size / (1024*1024):.1f} MB) in {elapsed:.1f}s")

    else:
        raise ValueError(f"Unsupported archive format: {archive_path.suffix}")

    print("Extraction complete!")
    return extract_dir


# ============================================================================
# Step 3: Strip Extras (Keep Only Essential Binaries)
# ============================================================================


def strip_extras(extracted_dir: Path, output_dir: Path, platform: str) -> Path:
    """Keep only essential binaries, remove extras."""
    print_section("STEP 3: STRIP UNNECESSARY FILES")

    extracted_dir = Path(extracted_dir)
    output_dir = Path(output_dir)

    # Find the bin directory
    bin_dirs = list(extracted_dir.glob("**/bin"))
    if not bin_dirs:
        raise RuntimeError(f"No bin directory found in {extracted_dir}")

    bin_dir = bin_dirs[0]
    print(f"Found bin directory: {bin_dir}")

    # Create output structure
    output_bin = output_dir / "bin"
    output_bin.mkdir(parents=True, exist_ok=True)

    # Determine binary extension
    ext = ".exe" if platform == "win" else ""

    # Copy essential binaries
    kept_count = 0
    skipped_count = 0

    print("\nKeeping essential binaries:")
    for binary_name in ESSENTIAL_BINARIES:
        binary_file = bin_dir / f"{binary_name}{ext}"

        if binary_file.exists():
            dest = output_bin / binary_file.name
            shutil.copy2(binary_file, dest)
            print(f"  ✓ {binary_file.name}")
            kept_count += 1
        else:
            print(f"  - {binary_name}{ext} (not found)")
            skipped_count += 1

    # Copy only essential lib/clang directory (builtin headers and runtime)
    # Skip Fortran runtime, sanitizers, and other optional libraries
    lib_src = extracted_dir.glob("**/lib/clang")
    lib_clang_copied = False
    excluded_count = 0
    excluded_size = 0

    for lib_clang_dir in lib_src:
        if lib_clang_dir.is_dir():
            lib_dst = output_dir / "lib" / "clang"
            print("\nCopying essential lib/clang files (filtering out optional libraries)...")
            print(f"Source: {lib_clang_dir}")
            print(f"Dest:   {lib_dst}")

            # Use factory function to properly bind lib_clang_dir in closure
            def make_ignore_function(base_dir: Path):  # type: ignore[return]
                def ignore_optional_libs(directory: str, contents: list[str]) -> list[str]:
                    ignored = []
                    for item in contents:
                        item_path = Path(directory) / item
                        if should_exclude_lib_file(item_path):
                            # Calculate size if it's a file
                            if item_path.is_file():
                                size = item_path.stat().st_size
                                excluded_size_mb = size / (1024 * 1024)
                                print(f"  Excluding: {item_path.relative_to(base_dir)} ({excluded_size_mb:.1f} MB)")
                                nonlocal excluded_count, excluded_size
                                excluded_count += 1
                                excluded_size += size
                            ignored.append(item)
                    return ignored

                return ignore_optional_libs

            shutil.copytree(lib_clang_dir, lib_dst, dirs_exist_ok=True, ignore=make_ignore_function(lib_clang_dir))
            lib_clang_copied = True
            break

    print("\nSummary:")
    print(f"  Kept: {kept_count} binaries")
    print(f"  Skipped: {skipped_count} binaries (not found)")
    if lib_clang_copied:
        print("  Copied lib/clang directory")
        if excluded_count > 0:
            print(f"  Excluded {excluded_count} optional files ({excluded_size / (1024*1024):.1f} MB)")
            print("    (Fortran runtime removed - not needed for C/C++ compilation)")

    return output_dir


# ============================================================================
# Step 3.5: Strip Linux Binaries (Remove Debug Symbols)
# ============================================================================


def strip_linux_binaries(bin_dir: Path, platform: str) -> None:
    """
    Strip debug symbols from Linux binaries to reduce size.

    Uses llvm-strip (cross-platform) to remove debug symbols from ELF binaries.
    This typically reduces binary size by ~14% without affecting functionality.

    Windows binaries are skipped as they don't benefit from stripping.
    """
    if platform != "linux":
        return  # Only strip Linux binaries

    print_section("STEP 3.5: STRIP DEBUG SYMBOLS FROM LINUX BINARIES")

    bin_dir = Path(bin_dir)

    # Try to find llvm-strip
    llvm_strip = shutil.which("llvm-strip")
    if not llvm_strip:
        # Try common locations on Windows
        common_paths = [
            r"C:\Program Files\LLVM\bin\llvm-strip.exe",
            r"C:\Program Files (x86)\LLVM\bin\llvm-strip.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                llvm_strip = path
                break

    if not llvm_strip:
        print("⚠️  llvm-strip not found - skipping binary stripping")
        print("   Install LLVM to enable stripping: https://llvm.org/")
        print("   Binaries will be larger but still functional")
        return

    print(f"Using: {llvm_strip}")
    print()

    # Find all binaries
    binaries = sorted(bin_dir.glob("*"))
    binaries = [b for b in binaries if b.is_file()]

    if not binaries:
        print("No binaries found to strip")
        return

    print(f"Stripping {len(binaries)} binaries...")
    print()

    total_before = 0
    total_after = 0
    stripped_count = 0

    for binary in binaries:
        size_before = binary.stat().st_size
        size_before_mb = size_before / (1024 * 1024)

        try:
            # Use --strip-all for maximum size reduction
            # This removes debug symbols and other non-essential data
            subprocess.run([llvm_strip, "--strip-all", str(binary)], check=True, capture_output=True, text=True)

            size_after = binary.stat().st_size
            size_after_mb = size_after / (1024 * 1024)
            saved = size_before - size_after
            saved_mb = saved / (1024 * 1024)
            percent = (saved / size_before * 100) if size_before > 0 else 0

            print(
                f"  ✓ {binary.name:30s} {size_before_mb:7.1f} MB → {size_after_mb:7.1f} MB (saved {saved_mb:5.1f} MB, {percent:4.1f}%)"
            )

            total_before += size_before
            total_after += size_after
            stripped_count += 1

        except subprocess.CalledProcessError as e:
            print(f"  ✗ {binary.name:30s} - Failed to strip: {e.stderr}")
        except Exception as e:
            print(f"  ✗ {binary.name:30s} - Error: {e}")

    total_saved = total_before - total_after

    print()
    print("Summary:")
    print(f"  Stripped: {stripped_count} binaries")
    print(f"  Total before: {total_before / (1024*1024):.2f} MB")
    print(f"  Total after:  {total_after / (1024*1024):.2f} MB")
    print(f"  Total saved:  {total_saved / (1024*1024):.2f} MB ({(total_saved/total_before)*100:.1f}%)")


# ============================================================================
# Step 4: Deduplicate (Create Manifest)
# ============================================================================


def deduplicate_binaries(bin_dir: Path) -> dict[str, Any]:
    """Identify duplicate binaries and create deduplication manifest."""
    print_section("STEP 4: ANALYZE AND DEDUPLICATE BINARIES")

    bin_dir = Path(bin_dir)

    # Find all binaries
    binaries = sorted(bin_dir.glob("*"))
    binaries = [b for b in binaries if b.is_file()]

    print(f"Found {len(binaries)} binary files")
    print("\nCalculating MD5 hashes...")

    # Calculate hashes
    hash_to_files = {}
    hash_to_size = {}

    for binary in binaries:
        file_hash = get_file_hash(binary, "md5")
        size = binary.stat().st_size

        if file_hash not in hash_to_files:
            hash_to_files[file_hash] = []
            hash_to_size[file_hash] = size

        hash_to_files[file_hash].append(binary.name)

    # Create deduplication manifest
    manifest = {}
    canonical_files = {}

    for file_hash, files in sorted(hash_to_files.items()):
        # First file (alphabetically) becomes canonical
        canonical = sorted(files)[0]
        canonical_files[file_hash] = canonical

        for filename in files:
            manifest[filename] = canonical

    # Calculate savings
    total_files = len(binaries)
    unique_files = len(hash_to_files)
    duplicate_count = total_files - unique_files

    total_size = sum(hash_to_size[h] * len(files) for h, files in hash_to_files.items())
    deduped_size = sum(hash_to_size.values())
    savings = total_size - deduped_size

    print("\nDeduplication Analysis:")
    print(f"  Total files: {total_files}")
    print(f"  Unique files: {unique_files}")
    print(f"  Duplicates: {duplicate_count}")
    print(f"  Total size: {total_size / (1024*1024):.1f} MB")
    print(f"  Deduplicated size: {deduped_size / (1024*1024):.1f} MB")
    print(f"  Space savings: {savings / (1024*1024):.1f} MB ({(savings/total_size)*100:.1f}%)")

    # Print duplicate groups
    if duplicate_count > 0:
        print("\nDuplicate groups:")
        for file_hash, files in sorted(hash_to_files.items()):
            if len(files) > 1:
                size_mb = hash_to_size[file_hash] / (1024 * 1024)
                print(f"  {len(files)} files @ {size_mb:.1f} MB each: {', '.join(sorted(files))}")

    manifest_data = {
        "manifest": manifest,
        "canonical_files": canonical_files,
        "stats": {
            "total_size": total_size,
            "deduped_size": deduped_size,
            "savings": savings,
            "savings_percent": (savings / total_size * 100) if total_size > 0 else 0,
            "duplicate_count": duplicate_count,
        },
    }

    return manifest_data


# ============================================================================
# Step 5: Create Hard-Linked Structure
# ============================================================================


def create_hardlink_structure(manifest_data: dict[str, Any], source_bin_dir: Path, output_dir: Path) -> Path:
    """Create directory with hard links based on deduplication manifest."""
    print_section("STEP 5: CREATE HARD-LINKED STRUCTURE")

    source_bin_dir = Path(source_bin_dir)
    output_dir = Path(output_dir)

    manifest = manifest_data["manifest"]

    # Create output bin directory
    bin_dir = output_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Track which canonical files we've copied
    canonical_copied = {}

    print("\nCreating hard-linked structure:")
    for filename, canonical_name in sorted(manifest.items()):
        src = source_bin_dir / canonical_name
        dst = bin_dir / filename

        if not src.exists():
            print(f"  Warning: {canonical_name} not found")
            continue

        if canonical_name not in canonical_copied:
            # First occurrence - copy the file
            shutil.copy2(src, dst)
            canonical_copied[canonical_name] = dst
            print(f"  Copy:     {filename} <- {canonical_name}")
        else:
            # Create hard link
            first_copy = canonical_copied[canonical_name]
            print(f"  Hardlink: {filename} -> {first_copy.name}")

            try:
                if dst.exists():
                    dst.unlink()
                os.link(first_copy, dst)
            except OSError:
                # Hard link failed, copy instead
                shutil.copy2(src, dst)
                print("    (hard link failed, used copy)")

    return output_dir


# ============================================================================
# Step 6: Create TAR Archive
# ============================================================================


def create_tar_archive(source_dir: Path, output_tar: Path) -> Path:
    """Create tar archive (auto-detects hard links)."""
    print_section("STEP 6: CREATE TAR ARCHIVE")

    source_dir = Path(source_dir)
    output_tar = Path(output_tar)

    print(f"Source: {source_dir}")
    print(f"Output: {output_tar}")
    print()

    def tar_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
        """Filter to set correct permissions for binaries and shared libraries."""
        if tarinfo.isfile():
            # Set executable permissions for files in main bin/ directory
            if "/bin/" in tarinfo.name and "/lib/" not in tarinfo.name:
                tarinfo.mode = 0o755  # rwxr-xr-x
                print(f"  Setting executable: {tarinfo.name}")
            # Set executable permissions for shared libraries and certain executables in lib/
            elif "/lib/" in tarinfo.name:
                # Headers, text files, and static libraries should be readable but not executable (check first)
                if tarinfo.name.endswith((".h", ".inc", ".modulemap", ".tcc", ".txt", ".a", ".syms")):
                    tarinfo.mode = 0o644  # rw-r--r--
                # Shared libraries (.so, .dylib) need executable permissions on Unix
                elif tarinfo.name.endswith((".so", ".dylib")) or ".so." in tarinfo.name:
                    tarinfo.mode = 0o755  # rwxr-xr-x for shared libraries
                    print(f"  Setting executable (shared lib): {tarinfo.name}")
                # Executable binaries in lib/clang/*/bin/ directories
                elif "/bin/" in tarinfo.name and not tarinfo.name.endswith(
                    (".h", ".inc", ".txt", ".a", ".so", ".dylib")
                ):
                    tarinfo.mode = 0o755  # rwxr-xr-x
                    print(f"  Setting executable (lib binary): {tarinfo.name}")
        return tarinfo

    print("Creating tar archive using Python tarfile module...")
    print("Setting executable permissions for binaries in bin/...")
    with tarfile.open(output_tar, "w") as tar:
        tar.add(source_dir, arcname=source_dir.name, filter=tar_filter)

    size = output_tar.stat().st_size
    print(f"\nCreated: {output_tar}")
    print(f"Size: {size / (1024*1024):.2f} MB")

    return output_tar


def verify_tar_permissions(tar_file: Path) -> int:
    """Verify that binaries and shared libraries in the tar archive have correct permissions."""
    print_section("STEP 6.5: VERIFY TAR PERMISSIONS")

    tar_file = Path(tar_file)

    print(f"Checking permissions in: {tar_file}")
    print()

    issues_found = []
    binaries_checked = 0
    libs_checked = 0
    headers_checked = 0

    with tarfile.open(tar_file, "r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            # Check files in bin/ directory - should all be executable
            if "/bin/" in member.name:
                binaries_checked += 1
                # Check if executable bit is set (0o100 for user execute)
                if not (member.mode & 0o100):
                    issues_found.append((member.name, oct(member.mode), "binary missing executable"))
                    print(f"  ✗ Missing executable permission: {member.name} (mode: {oct(member.mode)})")
                else:
                    # Only print every 10th binary to avoid spam
                    if binaries_checked % 10 == 1:
                        print(f"  ✓ bin: {member.name} (mode: {oct(member.mode)})")

            # Check files in lib/ directory
            elif "/lib/" in member.name:
                # Headers and static libraries should NOT be executable (check this first)
                if member.name.endswith((".h", ".inc", ".modulemap", ".tcc", ".txt", ".a", ".syms")):
                    headers_checked += 1
                    if member.mode & 0o100:
                        issues_found.append((member.name, oct(member.mode), "header/static lib has executable bit"))
                        print(
                            f"  ✗ Header/static lib should not be executable: {member.name} (mode: {oct(member.mode)})"
                        )

                # Shared libraries (.so, .dylib) should be executable
                elif member.name.endswith((".so", ".dylib")) or ".so." in member.name:
                    libs_checked += 1
                    if not (member.mode & 0o100):
                        issues_found.append((member.name, oct(member.mode), "shared lib missing executable"))
                        print(f"  ✗ Shared lib missing executable: {member.name} (mode: {oct(member.mode)})")
                    elif libs_checked % 10 == 1:
                        print(f"  ✓ lib: {member.name} (mode: {oct(member.mode)})")

                # Executable binaries in lib/ (like *symbolize) - must be files without common extensions
                # These are typically in lib/clang/*/bin/ directories
                elif "/bin/" in member.name and not member.name.endswith((".h", ".inc", ".txt", ".a", ".so", ".dylib")):
                    binaries_checked += 1
                    if not (member.mode & 0o100):
                        issues_found.append((member.name, oct(member.mode), "lib binary missing executable"))
                        print(f"  ✗ Lib binary missing executable: {member.name} (mode: {oct(member.mode)})")

    print()
    print(f"Total binaries checked: {binaries_checked}")
    print(f"Total shared libraries checked: {libs_checked}")
    print(f"Total headers/text files checked: {headers_checked}")

    if issues_found:
        print(f"\n⚠️  WARNING: Found {len(issues_found)} files with incorrect permissions!")
        print("\nFiles with issues:")
        for name, mode, issue in issues_found:
            print(f"  - {name} (mode: {mode}) - {issue}")
        print("\nThese files may not work correctly when extracted on Unix systems.")
        raise RuntimeError(f"Tar archive has {len(issues_found)} files with incorrect permissions")
    else:
        print("✅ All files have correct permissions")

    return binaries_checked + libs_checked


# ============================================================================
# Step 7: Compress with ZSTD
# ============================================================================


def compress_with_zstd(tar_file: Path, output_zst: Path, level: int = 22) -> Path:
    """Compress tar with zstd using streaming compression for better interrupt handling."""
    print_section(f"STEP 7: COMPRESS WITH ZSTD LEVEL {level}")

    try:
        import zstandard as zstd
    except ImportError as e:
        raise ImportError("zstandard module required!\n" "Install with: pip install zstandard") from e

    tar_file = Path(tar_file)
    output_zst = Path(output_zst)

    file_size = tar_file.stat().st_size
    print(f"Input:  {tar_file} ({file_size / (1024*1024):.2f} MB)")
    print(f"Output: {output_zst}")
    print(f"Level:  {level}")
    print()

    print(f"Compressing {file_size / (1024*1024):.1f} MB (streaming mode - press Ctrl+C to cancel)...")
    print()

    # Compress using streaming for better interrupt handling
    import time

    start = time.time()

    try:
        cctx = zstd.ZstdCompressor(level=level, threads=-1)

        # Use streaming compression instead of loading entire file
        # Use 1MB chunks for better interrupt responsiveness on Windows
        chunk_size = 1 * 1024 * 1024  # 1MB chunks for better interrupt handling
        bytes_read = 0
        last_progress = -1
        last_update_time = start
        progress_counter = 0

        with (
            open(tar_file, "rb") as ifh,
            open(output_zst, "wb") as ofh,
            cctx.stream_writer(ofh, closefd=False) as compressor,
        ):
            while True:
                chunk = ifh.read(chunk_size)
                if not chunk:
                    break

                compressor.write(chunk)
                bytes_read += len(chunk)

                # Show progress every 5% for cleaner output that works on all terminals
                current_time = time.time()
                progress = int((bytes_read / file_size) * 100)
                time_since_update = current_time - last_update_time

                # Update every 5% OR every 2 seconds (whichever comes first)
                if (progress // 5 > last_progress // 5) or (time_since_update >= 2.0):
                    elapsed = current_time - start
                    mb_read = bytes_read / (1024 * 1024)
                    mb_total = file_size / (1024 * 1024)
                    mb_per_sec = mb_read / elapsed if elapsed > 0 else 0

                    # Use simple newline-based progress for cross-platform compatibility
                    progress_counter += 1
                    print(
                        f"  [{progress_counter:3d}] Progress: {progress:3d}% "
                        f"({mb_read:7.1f} / {mb_total:7.1f} MB) "
                        f"- {mb_per_sec:6.1f} MB/s - {elapsed:5.1f}s elapsed",
                        flush=True,
                    )
                    last_progress = progress
                    last_update_time = current_time

            # Print final newline and show finalizing message
            print()
            print("  Data read complete. Now finalizing compression...")
            print("  NOTE: Level 22 compression requires flushing buffers - this may take 30-60 seconds...")
            print("  (The process is NOT stalled, just working hard to achieve maximum compression)")
            print()
            finalize_start = time.time()

        # The with block closes here, which triggers the final compression flush
        # This is where most of the CPU time is actually spent for level 22
        finalize_elapsed = time.time() - finalize_start
        print(f"  Finalization complete! ({finalize_elapsed:.1f}s)")
        print()

        elapsed = time.time() - start

        original_size = file_size
        compressed_size = output_zst.stat().st_size
        ratio = original_size / compressed_size

        print("Compression complete!")
        print(f"  Total time:   {elapsed:.1f}s")
        print(f"  Reading:      {elapsed - finalize_elapsed:.1f}s")
        print(f"  Finalizing:   {finalize_elapsed:.1f}s")
        print(f"  Original:     {original_size / (1024*1024):.2f} MB")
        print(f"  Compressed:   {compressed_size / (1024*1024):.2f} MB")
        print(f"  Ratio:        {ratio:.2f}:1")
        print(f"  Reduction:    {(1 - compressed_size/original_size) * 100:.1f}%")

        return output_zst

    except KeyboardInterrupt:
        # Clean up partial output file on interrupt
        print("\n⚠️  Compression interrupted - cleaning up partial file...")
        if output_zst.exists():
            output_zst.unlink()
        raise


# ============================================================================
# Step 8: Generate Checksums
# ============================================================================


def generate_checksums(archive_path: Path) -> tuple[str, str]:
    """Generate SHA256 and MD5 checksums."""
    print_section("STEP 8: GENERATE CHECKSUMS")

    archive_path = Path(archive_path)

    print(f"Generating checksums for: {archive_path.name}")
    print()

    # SHA256
    print("Calculating SHA256...")
    sha256 = get_file_hash(archive_path, "sha256")
    sha256_file = archive_path.parent / f"{archive_path.name}.sha256"
    with open(sha256_file, "w") as f:
        f.write(f"{sha256} *{archive_path.name}\n")
    print(f"  SHA256: {sha256}")
    print(f"  Saved to: {sha256_file.name}")

    # MD5
    print("\nCalculating MD5...")
    md5 = get_file_hash(archive_path, "md5")
    md5_file = archive_path.parent / f"{archive_path.name}.md5"
    with open(md5_file, "w") as f:
        f.write(f"{md5} *{archive_path.name}\n")
    print(f"  MD5: {md5}")
    print(f"  Saved to: {md5_file.name}")

    return sha256, md5


# ============================================================================
# Step 9: Split Archive (If Needed)
# ============================================================================


def split_archive(archive_path: Path, max_size_mb: int = 99) -> list[Path] | None:
    """
    Split archive into parts if it exceeds max_size_mb.

    Creates files like:
    - archive.tar.zst.part1
    - archive.tar.zst.part2
    - archive.tar.zst.join (script to join them back)

    Args:
        archive_path: Path to the archive file
        max_size_mb: Maximum size in MB before splitting (default: 99)

    Returns:
        List of part files created, or None if no split needed
    """
    print_section(f"STEP 9: CHECK IF SPLIT NEEDED (max {max_size_mb} MB)")

    archive_path = Path(archive_path)
    size_mb = archive_path.stat().st_size / (1024 * 1024)

    print(f"Archive: {archive_path.name}")
    print(f"Size: {size_mb:.2f} MB")
    print(f"Limit: {max_size_mb} MB")
    print()

    if size_mb <= max_size_mb:
        print(f"✅ Archive is under {max_size_mb} MB - no split needed")
        return None

    print(f"⚠️  Archive exceeds {max_size_mb} MB - splitting into parts...")
    print()

    # Calculate part size (slightly under max to account for overhead)
    part_size = int((max_size_mb - 1) * 1024 * 1024)  # Leave 1 MB margin

    # Read and split
    parts = []
    part_num = 1

    with open(archive_path, "rb") as f:
        while True:
            chunk = f.read(part_size)
            if not chunk:
                break

            part_name = f"{archive_path.name}.part{part_num}"
            part_path = archive_path.parent / part_name

            with open(part_path, "wb") as pf:
                pf.write(chunk)

            part_size_mb = len(chunk) / (1024 * 1024)
            print(f"  Created: {part_name} ({part_size_mb:.2f} MB)")
            parts.append(part_path)
            part_num += 1

    # Create join script for convenience
    join_script_name = f"{archive_path.name}.join"
    join_script_path = archive_path.parent / join_script_name

    # Create both shell script and Python script
    shell_script = f"""#!/bin/bash
# Join script for {archive_path.name}
# This script joins the split parts back into the original archive

echo "Joining {len(parts)} parts into {archive_path.name}..."

cat {' '.join(p.name for p in parts)} > {archive_path.name}

echo "Done! Created {archive_path.name}"
echo "Size: $(du -h {archive_path.name} | cut -f1)"
echo ""
echo "To extract:"
echo "  tar --zstd -xf {archive_path.name}"
"""

    with open(join_script_path, "w", newline="\n") as f:
        f.write(shell_script)

    # Make it executable on Unix-like systems
    import contextlib

    with contextlib.suppress(Exception):
        os.chmod(join_script_path, 0o755)

    # Also create Python join script for Windows
    py_script_name = f"{archive_path.name}.join.py"
    py_script_path = archive_path.parent / py_script_name

    python_script = f"""#!/usr/bin/env python3
\"\"\"Join script for {archive_path.name}\"\"\"
import sys
from pathlib import Path

parts = {[p.name for p in parts]}
output = "{archive_path.name}"

print(f"Joining {{len(parts)}} parts into {{output}}...")

try:
    with open(output, 'wb') as out:
        for part in parts:
            print(f"  Adding {{part}}...")
            with open(part, 'rb') as inp:
                out.write(inp.read())

    size_mb = Path(output).stat().st_size / (1024 * 1024)
    print(f"\\nDone! Created {{output}} ({{size_mb:.2f}} MB)")
    print("\\nTo extract:")
    print(f"  tar --zstd -xf {{output}}")

except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
"""

    with open(py_script_path, "w") as f:
        f.write(python_script)

    print()
    print("Summary:")
    print(f"  Created {len(parts)} parts")
    print(f"  Total size: {size_mb:.2f} MB")
    print(f"  Part size: ~{max_size_mb - 1} MB each")
    print()
    print("Join scripts created:")
    print(f"  {join_script_name} (for Linux/Mac)")
    print(f"  {py_script_name} (for Windows/cross-platform)")
    print()
    print("To rejoin:")
    print(f"  bash {join_script_name}")
    print("  or")
    print(f"  python {py_script_name}")

    # Remove original archive
    print()
    print(f"Removing original archive: {archive_path.name}")
    archive_path.unlink()

    return parts


# ============================================================================
# Main Pipeline
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch and archive LLVM/Clang toolchain binaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m clang_tool_chain.downloads.fetch_and_archive --platform win --arch x86_64
  python -m clang_tool_chain.downloads.fetch_and_archive --platform linux --arch x86_64
  python -m clang_tool_chain.downloads.fetch_and_archive --platform darwin --arch arm64

  # Use existing extracted binaries:
  python -m clang_tool_chain.downloads.fetch_and_archive --platform win --arch x86_64 --source-dir ./assets/win

Note: Press Ctrl+C at any time to safely interrupt the operation.
        """,
    )

    parser.add_argument("--platform", required=True, choices=["win", "linux", "darwin"], help="Target platform")
    parser.add_argument("--arch", required=True, choices=["x86_64", "arm64"], help="Target architecture")
    parser.add_argument("--version", default=LLVM_VERSION, help=f"LLVM version (default: {LLVM_VERSION})")
    parser.add_argument("--source-dir", type=Path, help="Use existing extracted binaries instead of downloading")
    parser.add_argument(
        "--work-dir", type=Path, default=Path("work"), help="Working directory for temporary files (default: work)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: downloads-bins/assets/clang/{platform}/{arch})",
    )
    parser.add_argument("--zstd-level", type=int, default=22, help="Zstd compression level (default: 22)")
    parser.add_argument("--keep-intermediate", action="store_true", help="Keep intermediate files (for debugging)")

    args = parser.parse_args()

    # Use version from args
    llvm_version = args.version

    # Setup directories
    work_dir = args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)

    output_dir = args.output_dir or Path("downloads-bins/assets/clang") / args.platform / args.arch
    output_dir.mkdir(parents=True, exist_ok=True)

    # Archive name
    archive_name = f"llvm-{llvm_version}-{args.platform}-{args.arch}"

    print("=" * 70)
    print("LLVM/Clang Toolchain Fetch and Archive")
    print("=" * 70)
    print(f"Platform: {args.platform}")
    print(f"Architecture: {args.arch}")
    print(f"Version: {llvm_version}")
    print(f"Output: {output_dir}/{archive_name}.tar.zst")
    print("=" * 70)
    print("\n💡 Tip: Press Ctrl+C at any time to safely interrupt the operation.\n")

    try:
        # Step 1: Download (or use existing)
        if args.source_dir:
            print_section("STEP 1: USING EXISTING BINARIES")
            print(f"Source directory: {args.source_dir}")
            extracted_dir = args.source_dir
        else:
            archive_path = download_llvm(args.platform, args.arch, work_dir)

            # Step 2: Extract
            extracted_dir = extract_archive(archive_path, work_dir / "extracted")

        # Step 3: Strip extras
        stripped_dir = work_dir / "stripped"
        strip_extras(extracted_dir, stripped_dir, args.platform)

        # Step 3.5: Strip Linux binaries (remove debug symbols)
        strip_linux_binaries(stripped_dir / "bin", args.platform)

        # Step 4: Deduplicate
        manifest_data = deduplicate_binaries(stripped_dir / "bin")

        # Save manifest
        manifest_file = stripped_dir / "dedup_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest_data, f, indent=2)
        print(f"\nManifest saved: {manifest_file}")

        # Step 5: Create hard-linked structure
        hardlinked_dir = work_dir / "hardlinked"
        create_hardlink_structure(manifest_data, stripped_dir / "bin", hardlinked_dir)

        # Copy lib/clang directory if it exists (builtin headers only)
        lib_clang_src = stripped_dir / "lib" / "clang"
        if lib_clang_src.exists():
            lib_dst = hardlinked_dir / "lib" / "clang"
            print("\nCopying lib/clang directory (builtin headers)...")
            shutil.copytree(lib_clang_src, lib_dst, dirs_exist_ok=True)

        # Step 6: Create TAR
        tar_file = work_dir / f"{archive_name}.tar"
        create_tar_archive(hardlinked_dir, tar_file)

        # Step 6.5: Verify permissions in TAR archive
        verify_tar_permissions(tar_file)

        # Step 7: Compress with ZSTD
        # Initialize final_archive here, before compression, so it's defined for cleanup
        final_archive: Path = output_dir / f"{archive_name}.tar.zst"
        compress_with_zstd(tar_file, final_archive, level=args.zstd_level)

        # Step 8: Generate checksums
        sha256, md5 = generate_checksums(final_archive)

        # Step 9: Split if too large (before cleanup, so we can remove original)
        parts = split_archive(final_archive, max_size_mb=99)

        # Cleanup
        if not args.keep_intermediate:
            print_section("CLEANUP")
            print("Removing intermediate files...")
            if tar_file.exists():
                tar_file.unlink()
                print(f"  Removed: {tar_file.name}")
            if not args.source_dir:  # Don't remove if using existing source
                for item in [work_dir / "extracted", work_dir / "stripped", work_dir / "hardlinked"]:
                    if item.exists():
                        shutil.rmtree(item)
                        print(f"  Removed: {item}")

        # Final summary
        print_section("SUCCESS!")

        if parts:
            # Archive was split
            print(f"Archive split into {len(parts)} parts:")
            for i, part in enumerate(parts, 1):
                size_mb = part.stat().st_size / (1024 * 1024)
                print(f"  {i}. {part.name} ({size_mb:.2f} MB)")
            print()
            print("Join scripts:")
            print(f"  {final_archive.name}.join (bash)")
            print(f"  {final_archive.name}.join.py (python)")
            print()
            print("To rejoin and extract:")
            print(f"  python {final_archive.name}.join.py")
            print(f"  tar --zstd -xf {final_archive.name}")
        else:
            # Single archive
            print(f"Archive created: {final_archive}")
            print(f"Size: {final_archive.stat().st_size / (1024*1024):.2f} MB")
            print(f"SHA256: {sha256}")
            print(f"MD5: {md5}")
            print()
            print("Files created:")
            print(f"  {final_archive.name}")
            print(f"  {final_archive.name}.sha256")
            print(f"  {final_archive.name}.md5")

        print()
        print("✅ Done!")

    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("❌ OPERATION CANCELLED BY USER")
        print("=" * 70)
        print("\nInterrupted! Cleaning up...")
        # Cleanup on interrupt - check if final_archive was defined
        # Use locals() check to avoid NameError if interrupted before final_archive is set
        if "final_archive" in locals():
            final_archive_local: Path = final_archive  # type: ignore[possibly-undefined]
            if final_archive_local.exists():
                print(f"  Removing incomplete archive: {final_archive_local}")
                final_archive_local.unlink()
        sys.exit(130)  # Standard exit code for SIGINT

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
