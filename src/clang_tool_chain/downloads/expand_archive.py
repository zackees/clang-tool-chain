#!/usr/bin/env python3
"""
Expand tar.zst archive created with hard links.

This script:
1. Decompresses zstd archive
2. Extracts tar (tar automatically restores hard links as regular files)
3. Copies/moves binaries to target location

The tar format preserves hard links, but when extracted, they become
regular files (duplicates) which is what we want for distribution.
"""

import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any


def expand_zst_archive(archive_path: Path | str, output_dir: Path | str, keep_hardlinks: bool = False) -> Path:
    """
    Expand a tar.zst archive.

    Args:
        archive_path: Path to .tar.zst file
        output_dir: Directory to extract to
        keep_hardlinks: If True, preserve hard links; if False, copy to separate files
    """
    try:
        import zstandard as zstd
    except ImportError:
        print("Error: zstandard module not installed")
        print("Install with: pip install zstandard")
        sys.exit(1)

    archive_path = Path(archive_path)
    output_dir = Path(output_dir)

    if not archive_path.exists():
        print(f"Error: Archive not found: {archive_path}")
        sys.exit(1)

    print("=" * 70)
    print("EXPANDING ARCHIVE")
    print("=" * 70)
    print(f"Archive: {archive_path}")
    print(f"Output:  {output_dir}")
    print(f"Size:    {archive_path.stat().st_size / (1024*1024):.2f} MB")
    print()

    # Step 1: Decompress zstd
    print("Step 1: Decompressing zstd...")
    import time

    start = time.time()

    with open(archive_path, "rb") as f:
        compressed_data = f.read()

    dctx = zstd.ZstdDecompressor()
    tar_data = dctx.decompress(compressed_data)

    elapsed = time.time() - start
    print(
        f"  Decompressed {len(compressed_data) / (1024*1024):.2f} MB -> {len(tar_data) / (1024*1024):.2f} MB in {elapsed:.2f}s"
    )

    # Step 2: Extract tar
    print("\nStep 2: Extracting tar archive...")
    import io

    tar_buffer = io.BytesIO(tar_data)

    output_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
        # Get list of members
        members = tar.getmembers()
        print(f"  Archive contains {len(members)} items")

        # Extract
        tar.extractall(path=output_dir)

    print(f"  Extracted to: {output_dir}")

    # Step 3: Check for hard links
    print("\nStep 3: Analyzing extracted files...")

    extracted_root = output_dir / "win_hardlinked"
    if not extracted_root.exists():
        # Find the actual extraction root
        subdirs = list(output_dir.iterdir())
        if len(subdirs) == 1 and subdirs[0].is_dir():
            extracted_root = subdirs[0]

    bin_dir = extracted_root / "bin"
    if bin_dir.exists():
        exe_files = list(bin_dir.glob("*.exe"))
        print(f"  Found {len(exe_files)} .exe files")

        # Check if hard links were preserved
        inode_to_files = {}
        for exe_file in exe_files:
            stat = exe_file.stat()
            inode = stat.st_ino
            nlink = stat.st_nlink

            if inode not in inode_to_files:
                inode_to_files[inode] = []
            inode_to_files[inode].append((exe_file.name, nlink))

        hardlink_count = sum(1 for files in inode_to_files.values() if len(files) > 1)

        if hardlink_count > 0:
            print(f"  ✓ Hard links preserved: {hardlink_count} groups")

            if not keep_hardlinks:
                print("\n  Converting hard links to independent files...")
                convert_hardlinks_to_files(bin_dir, inode_to_files)
        else:
            print("  ✓ Files are independent copies")

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"Location: {extracted_root}")

    return extracted_root


def convert_hardlinks_to_files(bin_dir: Path, inode_to_files: dict[int, list[Any]]) -> None:
    """Convert hard links to independent file copies."""
    import tempfile

    for _inode, files in inode_to_files.items():
        if len(files) <= 1:
            continue  # Not a hard link group

        print(f"\n  Processing hard link group ({len(files)} files):")

        # Keep the first file as-is, copy the rest
        first_file = bin_dir / files[0][0]

        for filename, _nlink in files[1:]:
            target_file = bin_dir / filename

            # Copy to temp, delete original, move temp to original
            # This breaks the hard link
            with tempfile.NamedTemporaryFile(delete=False, dir=bin_dir) as tmp:
                tmp_path = Path(tmp.name)

            shutil.copy2(first_file, tmp_path)
            target_file.unlink()
            tmp_path.rename(target_file)

            print(f"    - {filename} (converted to independent file)")


def verify_extraction(extracted_dir: Path | str, original_dir: Path | str | None = None) -> bool:
    """Verify extracted files."""
    import hashlib

    extracted_dir = Path(extracted_dir)
    bin_dir = extracted_dir / "bin"

    if not bin_dir.exists():
        print(f"Warning: bin directory not found in {extracted_dir}")
        return False

    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    exe_files = sorted(bin_dir.glob("*.exe"))
    print(f"Extracted {len(exe_files)} .exe files:")

    hashes = {}
    for exe_file in exe_files:
        md5 = hashlib.md5()
        with open(exe_file, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)

        file_hash = md5.hexdigest()
        hashes[exe_file.name] = file_hash
        size_mb = exe_file.stat().st_size / (1024 * 1024)
        print(f"  {exe_file.name:<25} {size_mb:6.1f} MB  {file_hash[:16]}...")

    # Compare with original if provided
    if original_dir:
        print("\n" + "=" * 70)
        print("COMPARING WITH ORIGINAL")
        print("=" * 70)

        original_dir = Path(original_dir)
        original_bin = original_dir / "bin"

        if not original_bin.exists():
            print(f"Warning: Original bin directory not found: {original_bin}")
            return False

        all_match = True
        for filename, extracted_hash in sorted(hashes.items()):
            original_file = original_bin / filename

            if not original_file.exists():
                print(f"  ✗ {filename}: NOT FOUND in original")
                all_match = False
                continue

            # Calculate original hash
            md5 = hashlib.md5()
            with open(original_file, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    md5.update(chunk)
            original_hash = md5.hexdigest()

            if original_hash == extracted_hash:
                print(f"  ✓ {filename}")
            else:
                print(f"  ✗ {filename}: HASH MISMATCH")
                print(f"      Original:  {original_hash}")
                print(f"      Extracted: {extracted_hash}")
                all_match = False

        print()
        if all_match:
            print("✅ ALL FILES MATCH ORIGINAL!")
        else:
            print("❌ SOME FILES DO NOT MATCH")

        return all_match

    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Expand tar.zst archive")
    parser.add_argument("archive", help="Path to .tar.zst archive")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--verify", help="Original directory to verify against")
    parser.add_argument(
        "--keep-hardlinks", action="store_true", help="Keep hard links instead of converting to independent files"
    )

    args = parser.parse_args()

    extracted_root = expand_zst_archive(args.archive, args.output_dir, args.keep_hardlinks)

    if args.verify:
        verify_extraction(extracted_root, args.verify)
    else:
        verify_extraction(extracted_root)


if __name__ == "__main__":
    main()
