#!/usr/bin/env python3
"""
Deduplicate identical binaries in the toolchain by storing one copy
and creating a manifest for expansion.

This script:
1. Identifies duplicate files by MD5 hash
2. Keeps one "canonical" copy of each unique file
3. Creates a manifest mapping all filenames to their canonical source
4. Can expand the deduped structure back to full structure
"""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def get_file_hash(filepath: Path | str) -> str:
    """Calculate MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def analyze_directory(directory: Path | str) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Analyze directory for duplicate files."""
    directory = Path(directory)

    # Map hash -> list of files
    hash_to_files = {}
    # Map hash -> file size
    hash_to_size = {}

    for exe_file in directory.glob("*.exe"):
        file_hash = get_file_hash(exe_file)
        size = exe_file.stat().st_size

        if file_hash not in hash_to_files:
            hash_to_files[file_hash] = []
            hash_to_size[file_hash] = size

        hash_to_files[file_hash].append(exe_file.name)

    return hash_to_files, hash_to_size


def calculate_savings(hash_to_files: dict[str, list[str]], hash_to_size: dict[str, int]) -> dict[str, Any]:
    """Calculate potential space savings from deduplication."""
    total_size = 0
    deduped_size = 0
    duplicate_count = 0

    for file_hash, files in hash_to_files.items():
        size = hash_to_size[file_hash]
        total_size += size * len(files)
        deduped_size += size  # Only count once

        if len(files) > 1:
            duplicate_count += len(files) - 1

    savings = total_size - deduped_size

    return {
        "total_size": total_size,
        "deduped_size": deduped_size,
        "savings": savings,
        "savings_percent": (savings / total_size * 100) if total_size > 0 else 0,
        "duplicate_count": duplicate_count,
    }


def create_deduped_structure(source_dir: Path | str, dest_dir: Path | str) -> dict[str, Any]:
    """Create deduplicated directory structure with manifest."""
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)

    # Create destination directories
    bin_dir = dest_dir / "bin"
    canonical_dir = dest_dir / "canonical"
    bin_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir.mkdir(parents=True, exist_ok=True)

    hash_to_files, hash_to_size = analyze_directory(source_dir)

    # Manifest: filename -> canonical_file
    manifest = {}
    canonical_files = {}  # hash -> canonical filename

    # Process each unique hash
    for file_hash, files in sorted(hash_to_files.items()):
        # First file in sorted list becomes canonical
        canonical = sorted(files)[0]
        canonical_path = canonical_dir / canonical

        # Copy canonical file
        shutil.copy2(source_dir / canonical, canonical_path)
        canonical_files[file_hash] = canonical

        # Map all files to this canonical
        for filename in files:
            manifest[filename] = canonical

    # Save manifest
    manifest_data = {
        "manifest": manifest,
        "canonical_files": canonical_files,
        "stats": calculate_savings(hash_to_files, hash_to_size),
    }

    with open(dest_dir / "dedup_manifest.json", "w") as f:
        json.dump(manifest_data, f, indent=2)

    return manifest_data


def expand_deduped_structure(deduped_dir: Path | str, output_dir: Path | str) -> None:
    """Expand deduplicated structure back to full structure."""
    deduped_dir = Path(deduped_dir)
    output_dir = Path(output_dir)

    # Load manifest
    with open(deduped_dir / "dedup_manifest.json") as f:
        manifest_data = json.load(f)

    manifest = manifest_data["manifest"]
    canonical_dir = deduped_dir / "canonical"
    output_bin_dir = output_dir / "bin"
    output_bin_dir.mkdir(parents=True, exist_ok=True)

    # Copy or hardlink each file
    for filename, canonical in manifest.items():
        src = canonical_dir / canonical
        dst = output_bin_dir / filename

        # Copy the file
        shutil.copy2(src, dst)
        print(f"Created {filename} from {canonical}")

    print(f"\nExpanded {len(manifest)} files from {len(set(manifest.values()))} canonical files")


def print_analysis(source_dir: Path | str) -> None:
    """Print detailed analysis of duplicates."""
    hash_to_files, hash_to_size = analyze_directory(source_dir)
    stats = calculate_savings(hash_to_files, hash_to_size)

    print("=" * 70)
    print("BINARY DEDUPLICATION ANALYSIS")
    print("=" * 70)
    print()

    print(f"Total uncompressed size: {stats['total_size'] / (1024*1024):.1f} MB")
    print(f"Deduplicated size:       {stats['deduped_size'] / (1024*1024):.1f} MB")
    print(f"Space savings:           {stats['savings'] / (1024*1024):.1f} MB ({stats['savings_percent']:.1f}%)")
    print(f"Duplicate files:         {stats['duplicate_count']}")
    print()

    print("Duplicate Groups:")
    print("-" * 70)

    for file_hash, files in sorted(hash_to_files.items()):
        if len(files) > 1:
            size_mb = hash_to_size[file_hash] / (1024 * 1024)
            waste_mb = size_mb * (len(files) - 1)
            print(f"\n{len(files)} identical files ({size_mb:.1f} MB each, {waste_mb:.1f} MB wasted):")
            for filename in sorted(files):
                canonical = "← CANONICAL" if filename == sorted(files)[0] else ""
                print(f"  - {filename} {canonical}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Analyze:     python deduplicate_binaries.py analyze <directory>")
        print("  Deduplicate: python deduplicate_binaries.py dedup <source_dir> <dest_dir>")
        print("  Expand:      python deduplicate_binaries.py expand <deduped_dir> <output_dir>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "analyze":
        if len(sys.argv) < 3:
            print("Error: Missing directory argument")
            sys.exit(1)
        print_analysis(sys.argv[2])

    elif command == "dedup":
        if len(sys.argv) < 4:
            print("Error: Missing source or destination directory")
            sys.exit(1)
        source = sys.argv[2]
        dest = sys.argv[3]
        print("Creating deduplicated structure...")
        manifest_data = create_deduped_structure(source, dest)
        print("\nDeduplication complete!")
        print(f"Original size:  {manifest_data['stats']['total_size'] / (1024*1024):.1f} MB")
        print(f"Deduped size:   {manifest_data['stats']['deduped_size'] / (1024*1024):.1f} MB")
        print(f"Saved:          {manifest_data['stats']['savings'] / (1024*1024):.1f} MB")
        print(f"Manifest saved to: {dest}/dedup_manifest.json")

    elif command == "expand":
        if len(sys.argv) < 4:
            print("Error: Missing deduped or output directory")
            sys.exit(1)
        deduped = sys.argv[2]
        output = sys.argv[3]
        expand_deduped_structure(deduped, output)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
