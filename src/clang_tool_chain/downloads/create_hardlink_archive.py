#!/usr/bin/env python3
"""
Create a hardlink-based archive that uses tar's native deduplication.

This script:
1. Reads the deduplication manifest
2. Creates a directory structure with hard links (not copies!)
3. Creates a tar archive (tar automatically detects and stores hard links efficiently)
4. Compresses with zstd level 22

The tar format natively supports hard links - when multiple files have the
same inode, tar stores the data once and creates link entries for duplicates.
"""

import json
import os
import shutil
import sys
from pathlib import Path


def create_hardlink_structure(manifest_path: Path | str, canonical_dir: Path | str, output_dir: Path | str) -> Path:
    """
    Create directory structure with hard links based on manifest.

    Args:
        manifest_path: Path to dedup_manifest.json
        canonical_dir: Directory containing canonical (unique) binaries
        output_dir: Output directory for hardlinked structure
    """
    manifest_path = Path(manifest_path)
    canonical_dir = Path(canonical_dir)
    output_dir = Path(output_dir)

    # Load manifest
    with open(manifest_path) as f:
        manifest_data = json.load(f)

    manifest = manifest_data["manifest"]

    # Create output bin directory
    bin_dir = output_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Track which canonical files we've copied
    canonical_copied = {}

    # Process each file in manifest
    for filename, canonical_name in sorted(manifest.items()):
        src = canonical_dir / canonical_name
        dst = bin_dir / filename

        if not src.exists():
            print(f"Warning: Canonical file not found: {src}")
            continue

        # If this is the first time we're seeing this canonical file,
        # copy it to the first destination
        if canonical_name not in canonical_copied:
            print(f"Copy:     {filename} <- {canonical_name}")
            shutil.copy2(src, dst)
            canonical_copied[canonical_name] = dst
        else:
            # Create hard link to the first copy
            first_copy = canonical_copied[canonical_name]
            print(f"Hardlink: {filename} -> {first_copy.name}")

            # On Windows, we need to use os.link
            # Remove dst if it exists
            if dst.exists():
                dst.unlink()

            try:
                os.link(first_copy, dst)
            except OSError as e:
                print(f"  Warning: Hard link failed ({e}), using copy instead")
                shutil.copy2(src, dst)

    # Copy lib directory if it exists
    lib_src = canonical_dir.parent / "lib"
    if lib_src.exists():
        lib_dst = output_dir / "lib"
        if lib_dst.exists():
            shutil.rmtree(lib_dst)
        print("\nCopying lib directory...")
        shutil.copytree(lib_src, lib_dst)

    return bin_dir


def verify_hardlinks(bin_dir: Path | str) -> tuple[int, int]:
    """Verify that hard links were created successfully."""
    bin_dir = Path(bin_dir)

    print("\n" + "=" * 70)
    print("VERIFYING HARD LINKS")
    print("=" * 70)

    # Group files by inode
    inode_to_files = {}

    for exe_file in bin_dir.glob("*.exe"):
        stat = exe_file.stat()
        inode = stat.st_ino

        if inode not in inode_to_files:
            inode_to_files[inode] = []

        inode_to_files[inode].append({"name": exe_file.name, "size": stat.st_size, "nlink": stat.st_nlink})

    total_files = 0
    unique_inodes = 0
    hardlinked_groups = 0

    for _inode, files in sorted(inode_to_files.items()):
        total_files += len(files)
        unique_inodes += 1

        if len(files) > 1:
            hardlinked_groups += 1
            size_mb = files[0]["size"] / (1024 * 1024)
            print(f"\nHard link group {hardlinked_groups} ({len(files)} files, {size_mb:.1f} MB each):")
            for f in sorted(files, key=lambda x: x["name"]):  # type: ignore[arg-type]
                print(f"  - {f['name']} (nlink={f['nlink']})")

    print()
    print(f"Total files: {total_files}")
    print(f"Unique inodes: {unique_inodes}")
    print(f"Hard link groups: {hardlinked_groups}")
    print(f"Duplicate files: {total_files - unique_inodes}")

    return total_files, unique_inodes


def create_tar_archive(source_dir: Path | str, output_tar: Path | str, compression: str = "none") -> Path:
    """Create tar archive (tar auto-detects hard links)."""
    import tarfile

    source_dir = Path(source_dir)
    output_tar = Path(output_tar)

    print("\n" + "=" * 70)
    print("CREATING TAR ARCHIVE")
    print("=" * 70)
    print(f"Source: {source_dir}")
    print(f"Output: {output_tar}")
    print(f"Compression: {compression}")
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

    # Map compression type to tarfile mode
    if compression == "none":
        mode = "w"
    elif compression == "gzip":
        mode = "w:gz"
    elif compression == "xz":
        mode = "w:xz"
    else:
        raise ValueError(f"Unknown compression: {compression}")

    with tarfile.open(output_tar, mode) as tar:
        tar.add(source_dir, arcname=source_dir.name, filter=tar_filter)

    size = output_tar.stat().st_size
    print(f"Created: {output_tar} ({size / (1024*1024):.2f} MB)")

    return output_tar


def verify_tar_permissions(tar_file: Path | str) -> int:
    """Verify that binaries and shared libraries in the tar archive have correct permissions."""
    import tarfile

    tar_file = Path(tar_file)

    print("\n" + "=" * 70)
    print("VERIFYING TAR PERMISSIONS")
    print("=" * 70)
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


def compress_with_zstd(tar_file: Path | str, output_zst: Path | str, level: int = 22) -> Path:
    """Compress tar with zstd."""
    import zstandard as zstd

    tar_file = Path(tar_file)
    output_zst = Path(output_zst)

    print("\n" + "=" * 70)
    print(f"COMPRESSING WITH ZSTD LEVEL {level}")
    print("=" * 70)
    print(f"Input:  {tar_file} ({tar_file.stat().st_size / (1024*1024):.2f} MB)")
    print(f"Output: {output_zst}")
    print()

    # Read tar file
    with open(tar_file, "rb") as f:
        tar_data = f.read()

    print(f"Compressing {len(tar_data) / (1024*1024):.1f} MB...")

    # Compress with zstd
    import time

    start = time.time()
    cctx = zstd.ZstdCompressor(level=level, threads=-1)
    compressed = cctx.compress(tar_data)
    elapsed = time.time() - start

    # Write compressed file
    with open(output_zst, "wb") as f:
        f.write(compressed)

    original_size = len(tar_data)
    compressed_size = len(compressed)
    ratio = original_size / compressed_size

    print(f"Compressed in {elapsed:.1f}s")
    print(f"Original:   {original_size / (1024*1024):.2f} MB")
    print(f"Compressed: {compressed_size / (1024*1024):.2f} MB")
    print(f"Ratio:      {ratio:.2f}:1")
    print(f"Reduction:  {(1 - compressed_size/original_size) * 100:.1f}%")

    return output_zst


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Create hardlink-based tar.zst archive")
    parser.add_argument("deduped_dir", help="Directory containing deduplicated structure")
    parser.add_argument("output_dir", help="Output directory for archive")
    parser.add_argument("--name", default="win_binaries", help="Archive base name")
    parser.add_argument("--zstd-level", type=int, default=22, help="Zstd compression level (default: 22)")

    args = parser.parse_args()

    deduped_dir = Path(args.deduped_dir)
    output_dir = Path(args.output_dir)

    # Paths
    manifest_path = deduped_dir / "dedup_manifest.json"
    canonical_dir = deduped_dir / "canonical"

    if not manifest_path.exists():
        print(f"Error: Manifest not found: {manifest_path}")
        sys.exit(1)

    if not canonical_dir.exists():
        print(f"Error: Canonical directory not found: {canonical_dir}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Create hardlink structure
    print("=" * 70)
    print("STEP 1: CREATE HARDLINK STRUCTURE")
    print("=" * 70)
    print()

    hardlink_dir = output_dir / "win_hardlinked"
    bin_dir = create_hardlink_structure(manifest_path, canonical_dir, hardlink_dir)

    # Step 2: Verify hardlinks
    _ = verify_hardlinks(bin_dir)  # Returns tuple but we don't need the values

    # Step 3: Create tar archive
    tar_file = output_dir / f"{args.name}.tar"
    create_tar_archive(hardlink_dir, tar_file)

    # Step 3.5: Verify tar permissions
    verify_tar_permissions(tar_file)

    # Step 4: Compress with zstd
    try:
        zst_file = output_dir / f"{args.name}.tar.zst"
        compress_with_zstd(tar_file, zst_file, level=args.zstd_level)

        # Clean up uncompressed tar
        print(f"\nRemoving uncompressed tar: {tar_file}")
        tar_file.unlink()

        print("\n" + "=" * 70)
        print("SUCCESS!")
        print("=" * 70)
        print(f"Final archive: {zst_file}")
        print(f"Size: {zst_file.stat().st_size / (1024*1024):.2f} MB")

    except ImportError:
        print("\nWarning: zstandard module not available")
        print(f"Tar archive created: {tar_file}")


if __name__ == "__main__":
    main()
