#!/usr/bin/env python3
"""
Test various compression methods to find the smallest archive size.

Tests:
- gzip (levels 1-9)
- bzip2 (levels 1-9)
- xz (levels 0-9, plus extreme mode)
- zstd (levels 1-22)
"""

import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

try:
    import zstandard as zstd
except ImportError:
    print("Warning: zstandard module not available")
    zstd = None


def format_size(bytes_size: int) -> str:
    """Format bytes as human-readable string."""
    mb = bytes_size / (1024 * 1024)
    return f"{mb:.2f} MB"


def format_time(seconds: float) -> str:
    """Format seconds as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def test_gzip(source_dir: str, output_base: str, levels: list[int] | None = None) -> list[dict[str, Any]]:
    """Test gzip compression at various levels."""
    if levels is None:
        levels = [1, 6, 9]  # Fast, default, max

    results = []
    source_path = Path(source_dir)

    for level in levels:
        output = f"{output_base}_gzip{level}.tar.gz"
        print(f"Testing gzip level {level}...", end=" ", flush=True)

        start = time.time()
        cmd = f'tar -czf "{output}" -C "{source_path.parent}" "{source_path.name}"'
        env = {"GZIP": f"-{level}"}
        subprocess.run(cmd, shell=True, env={**os.environ, **env}, check=True)
        elapsed = time.time() - start

        size = Path(output).stat().st_size
        print(f"{format_size(size)} in {format_time(elapsed)}")

        results.append({"method": f"gzip-{level}", "file": output, "size": size, "time": elapsed})

    return results


def test_bzip2(source_dir: str, output_base: str, levels: list[int] | None = None) -> list[dict[str, Any]]:
    """Test bzip2 compression at various levels."""
    if levels is None:
        levels = [1, 6, 9]  # Fast, default, max

    results = []
    source_path = Path(source_dir)

    for level in levels:
        output = f"{output_base}_bzip2_{level}.tar.bz2"
        print(f"Testing bzip2 level {level}...", end=" ", flush=True)

        start = time.time()
        cmd = f'tar -cjf "{output}" -C "{source_path.parent}" "{source_path.name}"'
        env = {"BZIP2": f"-{level}"}
        subprocess.run(cmd, shell=True, env={**os.environ, **env}, check=True)
        elapsed = time.time() - start

        size = Path(output).stat().st_size
        print(f"{format_size(size)} in {format_time(elapsed)}")

        results.append({"method": f"bzip2-{level}", "file": output, "size": size, "time": elapsed})

    return results


def test_xz(
    source_dir: str, output_base: str, levels: list[int] | None = None, test_extreme: bool = True
) -> list[dict[str, Any]]:
    """Test xz compression at various levels."""
    if levels is None:
        levels = [0, 6, 9]  # Fast, default, max

    results = []
    source_path = Path(source_dir)

    for level in levels:
        output = f"{output_base}_xz{level}.tar.xz"
        print(f"Testing xz level {level}...", end=" ", flush=True)

        start = time.time()
        cmd = f'tar -cJf "{output}" -C "{source_path.parent}" "{source_path.name}"'
        env = {"XZ_OPT": f"-{level}"}
        subprocess.run(cmd, shell=True, env={**os.environ, **env}, check=True)
        elapsed = time.time() - start

        size = Path(output).stat().st_size
        print(f"{format_size(size)} in {format_time(elapsed)}")

        results.append({"method": f"xz-{level}", "file": output, "size": size, "time": elapsed})

    # Test extreme mode
    if test_extreme:
        for level in [9]:  # Only test extreme on max level
            output = f"{output_base}_xz{level}e.tar.xz"
            print(f"Testing xz level {level} --extreme...", end=" ", flush=True)

            start = time.time()
            cmd = f'tar -cJf "{output}" -C "{source_path.parent}" "{source_path.name}"'
            env = {"XZ_OPT": f"-{level}e"}
            subprocess.run(cmd, shell=True, env={**os.environ, **env}, check=True)
            elapsed = time.time() - start

            size = Path(output).stat().st_size
            print(f"{format_size(size)} in {format_time(elapsed)}")

            results.append({"method": f"xz-{level}e", "file": output, "size": size, "time": elapsed})

    return results


def test_zstd_python(source_dir: str, output_base: str, levels: list[int] | None = None) -> list[dict[str, Any]]:
    """Test zstd compression using Python library."""
    if zstd is None:
        print("Skipping zstd tests (module not available)")
        return []

    if levels is None:
        levels = [1, 3, 10, 19, 22]  # Fast, default, high, very high, ultra

    results = []
    source_path = Path(source_dir)

    for level in levels:
        output = f"{output_base}_zstd{level}.tar.zst"
        print(f"Testing zstd level {level}...", end=" ", flush=True)

        start = time.time()

        # Create tar in memory, then compress with zstd
        # Create tar data
        import io

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            tar.add(source_path, arcname=source_path.name)
        tar_data = tar_buffer.getvalue()

        # Compress with zstd
        cctx = zstd.ZstdCompressor(level=level)
        compressed = cctx.compress(tar_data)

        # Write to file
        with open(output, "wb") as f:
            f.write(compressed)

        elapsed = time.time() - start
        size = len(compressed)
        print(f"{format_size(size)} in {format_time(elapsed)}")

        results.append({"method": f"zstd-{level}", "file": output, "size": size, "time": elapsed})

    return results


def print_results_table(all_results: list[dict[str, Any]]) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 80)
    print("COMPRESSION COMPARISON RESULTS")
    print("=" * 80)
    print()
    print(f"{'Method':<15} {'Size':<12} {'Time':<10} {'vs Best':<12}")
    print("-" * 80)

    # Sort by size
    sorted_results = sorted(all_results, key=lambda x: x["size"])
    best_size = sorted_results[0]["size"]

    for result in sorted_results:
        size_str = format_size(result["size"])
        time_str = format_time(result["time"])
        percent_vs_best = (result["size"] / best_size - 1) * 100
        vs_best = f"+{percent_vs_best:.1f}%" if percent_vs_best > 0 else "BEST"

        marker = " ⭐" if result["size"] == best_size else ""
        print(f"{result['method']:<15} {size_str:<12} {time_str:<10} {vs_best:<12}{marker}")

    print()
    print(f"Best compression: {sorted_results[0]['method']} - {format_size(sorted_results[0]['size'])}")
    print(f"Worst compression: {sorted_results[-1]['method']} - {format_size(sorted_results[-1]['size'])}")
    print(f"Difference: {format_size(sorted_results[-1]['size'] - sorted_results[0]['size'])}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_compression.py <directory_to_compress> [output_prefix]")
        sys.exit(1)

    source_dir = sys.argv[1]
    output_base = sys.argv[2] if len(sys.argv) > 2 else "compressed"

    if not Path(source_dir).exists():
        print(f"Error: Directory '{source_dir}' does not exist")
        sys.exit(1)

    print(f"Testing compression methods on: {source_dir}")
    print(f"Output prefix: {output_base}")
    print()

    all_results = []

    # Test gzip
    print("=" * 80)
    print("GZIP COMPRESSION")
    print("=" * 80)
    all_results.extend(test_gzip(source_dir, output_base, levels=[1, 6, 9]))

    # Test bzip2
    print("\n" + "=" * 80)
    print("BZIP2 COMPRESSION")
    print("=" * 80)
    all_results.extend(test_bzip2(source_dir, output_base, levels=[1, 6, 9]))

    # Test xz
    print("\n" + "=" * 80)
    print("XZ COMPRESSION")
    print("=" * 80)
    all_results.extend(test_xz(source_dir, output_base, levels=[0, 6, 9], test_extreme=True))

    # Test zstd
    if zstd is not None:
        print("\n" + "=" * 80)
        print("ZSTD COMPRESSION")
        print("=" * 80)
        all_results.extend(test_zstd_python(source_dir, output_base, levels=[1, 3, 10, 15, 19, 22]))

    # Print final results
    print_results_table(all_results)


if __name__ == "__main__":
    main()
