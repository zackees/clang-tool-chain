#!/usr/bin/env python3
"""
Side-by-side comparison: parallel vs single-threaded download.
Using a file that supports range requests.
"""

import logging
import os
import tempfile
import time
from pathlib import Path

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

from clang_tool_chain.parallel_download import download_file_parallel, DownloadConfig

# Use a larger file from Python.org that supports range requests
TEST_URL = "https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe"  # ~25 MB installer

def test_comparison():
    """Compare parallel vs single-threaded download speed."""
    print("\n" + "="*80)
    print("PARALLEL vs SINGLE-THREADED COMPARISON")
    print("="*80)
    print(f"Test file: {TEST_URL}")
    print(f"This file should support range requests\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Test 1: Parallel download
        print("-"*80)
        print("TEST 1: PARALLEL DOWNLOAD (6 workers, 8 MB chunks)")
        print("-"*80)

        dest1 = tmpdir / "python_parallel.exe"
        config_parallel = DownloadConfig(
            chunk_size=8 * 1024 * 1024,  # 8 MB chunks
            max_workers=6,
            min_size_for_parallel=1 * 1024 * 1024  # 1 MB minimum (force parallel)
        )

        start = time.time()
        try:
            download_file_parallel(TEST_URL, dest1, expected_sha256=None, config=config_parallel)
            elapsed_parallel = time.time() - start

            if dest1.exists():
                size = dest1.stat().st_size
                speed = size / elapsed_parallel / (1024*1024)
                print(f"✅ Downloaded {size / (1024*1024):.2f} MB in {elapsed_parallel:.2f}s")
                print(f"   Speed: {speed:.2f} MB/s")
                parallel_stats = {"time": elapsed_parallel, "size": size, "speed": speed}
            else:
                print("❌ Download failed")
                parallel_stats = None
        except Exception as e:
            print(f"❌ Error: {e}")
            parallel_stats = None

        # Test 2: Single-threaded download
        print("\n" + "-"*80)
        print("TEST 2: SINGLE-THREADED DOWNLOAD (for comparison)")
        print("-"*80)

        dest2 = tmpdir / "python_single.exe"

        # Disable parallel via environment
        os.environ["CLANG_TOOL_CHAIN_DISABLE_PARALLEL"] = "1"
        import importlib
        import clang_tool_chain.archive
        importlib.reload(clang_tool_chain.archive)
        from clang_tool_chain.archive import download_file

        start = time.time()
        try:
            download_file(TEST_URL, dest2, expected_sha256=None)
            elapsed_single = time.time() - start

            if dest2.exists():
                size = dest2.stat().st_size
                speed = size / elapsed_single / (1024*1024)
                print(f"✅ Downloaded {size / (1024*1024):.2f} MB in {elapsed_single:.2f}s")
                print(f"   Speed: {speed:.2f} MB/s")
                single_stats = {"time": elapsed_single, "size": size, "speed": speed}
            else:
                print("❌ Download failed")
                single_stats = None
        except Exception as e:
            print(f"❌ Error: {e}")
            single_stats = None
        finally:
            del os.environ["CLANG_TOOL_CHAIN_DISABLE_PARALLEL"]
            importlib.reload(clang_tool_chain.archive)

        # Compare results
        if parallel_stats and single_stats:
            print("\n" + "="*80)
            print("COMPARISON RESULTS")
            print("="*80)
            print(f"Parallel:        {parallel_stats['time']:.2f}s @ {parallel_stats['speed']:.2f} MB/s")
            print(f"Single-threaded: {single_stats['time']:.2f}s @ {single_stats['speed']:.2f} MB/s")

            if parallel_stats['time'] < single_stats['time']:
                speedup = single_stats['time'] / parallel_stats['time']
                print(f"\n✅ Parallel was FASTER by {speedup:.2f}x")
            else:
                slowdown = parallel_stats['time'] / single_stats['time']
                print(f"\n⚠️  Single-threaded was faster by {slowdown:.2f}x")
                print("   (This can happen with slow connections or server throttling)")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    test_comparison()
