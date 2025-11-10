#!/usr/bin/env python3
"""
Create IWYU archives for all platforms.

This script:
1. Scans downloads-bins/assets/iwyu/ for extracted binaries
2. Creates tar archives with proper permissions
3. Compresses with zstd level 22
4. Generates SHA256 checksums
5. Outputs archives to downloads-bins/assets/iwyu/{platform}/{arch}/

Unlike the Clang toolchain, IWYU has no duplicate binaries, so no deduplication is needed.
"""

import hashlib
import json
import sys
import tarfile
from pathlib import Path


def create_tar_archive(source_dir: Path, output_tar: Path) -> Path:
    """
    Create tar archive with correct permissions for IWYU.

    Args:
        source_dir: Directory containing bin/ and share/ (e.g., downloads-bins/assets/iwyu/win/x86_64/)
        output_tar: Output tar file path

    Returns:
        Path to created tar file
    """
    print("\n" + "=" * 70)
    print("CREATING TAR ARCHIVE")
    print("=" * 70)
    print(f"Source: {source_dir}")
    print(f"Output: {output_tar}")
    print()

    def tar_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
        """Filter to set correct permissions for IWYU files."""
        if tarinfo.isfile():
            # Python scripts and the main binary should be executable
            if "/bin/" in tarinfo.name or tarinfo.name.startswith("bin/"):
                if tarinfo.name.endswith((".py", "include-what-you-use", ".exe")):
                    tarinfo.mode = 0o755  # rwxr-xr-x
                    print(f"  Setting executable: {tarinfo.name}")
                else:
                    # Other files in bin/ default to readable
                    tarinfo.mode = 0o644  # rw-r--r--
            # Mapping files and other share/ content should be readable
            elif "/share/" in tarinfo.name or tarinfo.name.startswith("share/"):
                tarinfo.mode = 0o644  # rw-r--r--
            # Other files (LICENSE, README, etc.)
            else:
                tarinfo.mode = 0o644  # rw-r--r--
        return tarinfo

    print("Creating tar archive...")
    print("Setting permissions...")

    # Get the architecture directory name (x86_64, arm64)
    # We want the archive structure to be flat: bin/, share/, etc.
    with tarfile.open(output_tar, "w") as tar:
        # Add bin/ directory
        bin_dir = source_dir / "bin"
        if bin_dir.exists():
            tar.add(bin_dir, arcname="bin", filter=tar_filter)

        # Add share/ directory
        share_dir = source_dir / "share"
        if share_dir.exists():
            tar.add(share_dir, arcname="share", filter=tar_filter)

        # Add any other top-level files (LICENSE, README, etc.)
        for item in source_dir.iterdir():
            if item.is_file():
                tar.add(item, arcname=item.name, filter=tar_filter)

    size = output_tar.stat().st_size
    print(f"Created: {output_tar} ({size / (1024*1024):.2f} MB)")

    return output_tar


def verify_tar_permissions(tar_file: Path) -> int:
    """Verify that files in the tar archive have correct permissions."""
    print("\n" + "=" * 70)
    print("VERIFYING TAR PERMISSIONS")
    print("=" * 70)
    print(f"Checking permissions in: {tar_file}")
    print()

    issues_found = []
    executables_checked = 0
    data_files_checked = 0

    with tarfile.open(tar_file, "r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue

            # Check files in bin/ directory
            if "/bin/" in member.name or member.name.startswith("bin/"):
                # Python scripts and binaries should be executable
                if member.name.endswith((".py", "include-what-you-use", ".exe")):
                    executables_checked += 1
                    if not (member.mode & 0o100):
                        issues_found.append((member.name, oct(member.mode), "executable missing +x"))
                        print(f"  ✗ Missing executable permission: {member.name} (mode: {oct(member.mode)})")
                    else:
                        print(f"  ✓ bin: {member.name} (mode: {oct(member.mode)})")

            # Check files in share/ directory
            elif "/share/" in member.name or member.name.startswith("share/"):
                data_files_checked += 1
                # These should NOT be executable
                if member.mode & 0o100:
                    issues_found.append((member.name, oct(member.mode), "data file has +x"))
                    print(f"  ✗ Data file should not be executable: {member.name} (mode: {oct(member.mode)})")

    print()
    print(f"Total executables checked: {executables_checked}")
    print(f"Total data files checked: {data_files_checked}")

    if issues_found:
        print(f"\n⚠️  WARNING: Found {len(issues_found)} files with incorrect permissions!")
        print("\nFiles with issues:")
        for name, mode, issue in issues_found:
            print(f"  - {name} (mode: {mode}) - {issue}")
        raise RuntimeError(f"Tar archive has {len(issues_found)} files with incorrect permissions")
    else:
        print("✅ All files have correct permissions")

    return executables_checked + data_files_checked


def compress_with_zstd(tar_file: Path, output_zst: Path, level: int = 22) -> Path:
    """Compress tar with zstd."""
    import zstandard as zstd

    print("\n" + "=" * 70)
    print(f"COMPRESSING WITH ZSTD LEVEL {level}")
    print("=" * 70)
    print(f"Input:  {tar_file} ({tar_file.stat().st_size / (1024*1024):.2f} MB)")
    print(f"Output: {output_zst}")
    print()

    # Use streaming compression to handle large files and allow interruption
    print("Compressing (this may take a while)...")

    import time

    start = time.time()

    # Create compressor with multi-threading
    cctx = zstd.ZstdCompressor(level=level, threads=-1)

    # Stream compress
    with open(tar_file, "rb") as ifh, open(output_zst, "wb") as ofh:
        # Read in chunks to allow interruption
        chunk_size = 1024 * 1024  # 1MB chunks
        reader = cctx.stream_reader(ifh, size=tar_file.stat().st_size)

        while True:
            chunk = reader.read(chunk_size)
            if not chunk:
                break
            ofh.write(chunk)

    elapsed = time.time() - start

    original_size = tar_file.stat().st_size
    compressed_size = output_zst.stat().st_size
    ratio = original_size / compressed_size if compressed_size > 0 else 0

    print(f"Compressed in {elapsed:.1f}s")
    print(f"Original:   {original_size / (1024*1024):.2f} MB")
    print(f"Compressed: {compressed_size / (1024*1024):.2f} MB")
    print(f"Ratio:      {ratio:.2f}:1")
    print(f"Reduction:  {(1 - compressed_size/original_size) * 100:.1f}%")

    return output_zst


def generate_checksum(file_path: Path) -> str:
    """Generate SHA256 checksum for a file."""
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def process_platform_arch(iwyu_root: Path, platform: str, arch: str, version: str) -> dict[str, str | int] | None:
    """
    Process a single platform/arch combination.

    Args:
        iwyu_root: Root downloads-bins/assets/iwyu directory
        platform: Platform name (win, linux, darwin)
        arch: Architecture (x86_64, arm64)
        version: IWYU version (e.g., "0.25")

    Returns:
        Dict with archive info, or None if skipped
    """
    source_dir = iwyu_root / platform / arch

    # Check if directory exists and has bin/
    if not source_dir.exists() or not (source_dir / "bin").exists():
        print(f"Skipping {platform}/{arch} - no binaries found")
        return None

    print("\n" + "=" * 70)
    print(f"PROCESSING: {platform}/{arch}")
    print("=" * 70)

    # Create archive name
    archive_base = f"iwyu-{version}-{platform}-{arch}"
    tar_file = source_dir / f"{archive_base}.tar"
    zst_file = source_dir / f"{archive_base}.tar.zst"

    # Step 1: Create TAR
    create_tar_archive(source_dir, tar_file)

    # Step 2: Verify permissions
    verify_tar_permissions(tar_file)

    # Step 3: Compress with zstd
    compress_with_zstd(tar_file, zst_file)

    # Step 4: Generate checksum
    print("\nGenerating SHA256 checksum...")
    sha256 = generate_checksum(zst_file)
    print(f"SHA256: {sha256}")

    # Write checksum file
    checksum_file = zst_file.with_suffix(".tar.zst.sha256")
    with open(checksum_file, "w") as f:
        f.write(f"{sha256}  {zst_file.name}\n")

    # Clean up uncompressed tar
    print(f"\nRemoving uncompressed tar: {tar_file}")
    tar_file.unlink()

    print("\n✅ SUCCESS!")
    print(f"Archive: {zst_file}")
    print(f"Size: {zst_file.stat().st_size / (1024*1024):.2f} MB")
    print(f"SHA256: {sha256}")

    return {
        "filename": zst_file.name,
        "path": str(zst_file.relative_to(iwyu_root)),
        "sha256": sha256,
        "size": zst_file.stat().st_size,
    }


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Create IWYU archives for all platforms")
    parser.add_argument(
        "--iwyu-root",
        type=Path,
        default=Path("downloads-bins/assets/iwyu"),
        help="Root IWYU directory (default: downloads-bins/assets/iwyu)",
    )
    parser.add_argument("--version", default="0.25", help="IWYU version (default: 0.25)")
    parser.add_argument("--zstd-level", type=int, default=22, help="Zstd compression level (default: 22)")
    parser.add_argument(
        "--platform", help="Process only this platform (win, linux, darwin). If not specified, process all."
    )
    parser.add_argument("--arch", help="Process only this architecture (x86_64, arm64). If not specified, process all.")

    args = parser.parse_args()

    iwyu_root = args.iwyu_root.resolve()

    if not iwyu_root.exists():
        print(f"Error: IWYU root directory not found: {iwyu_root}")
        sys.exit(1)

    # Define platforms and architectures to process
    platforms = [args.platform] if args.platform else ["win", "linux", "darwin"]
    architectures = [args.arch] if args.arch else ["x86_64", "arm64"]

    # Process each platform/arch combination
    results = {}
    for platform in platforms:
        results[platform] = {}
        for arch in architectures:
            result = process_platform_arch(iwyu_root, platform, arch, args.version)
            if result:
                results[platform][arch] = result

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_archives = sum(len(arches) for arches in results.values())
    print(f"\nCreated {total_archives} archives:")

    for platform, arches in results.items():
        for arch, info in arches.items():
            print(f"\n{platform}/{arch}:")
            print(f"  File: {info['filename']}")
            print(f"  Size: {info['size'] / (1024*1024):.2f} MB")
            print(f"  SHA256: {info['sha256']}")

    # Save results to JSON for manifest creation
    results_file = iwyu_root / "archive_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nArchive info saved to: {results_file}")
    print("\nNext steps:")
    print("1. Create manifests with these SHA256 hashes")
    print("2. Upload archives to GitHub")
    print("3. Update downloader.py to support IWYU")


if __name__ == "__main__":
    main()
