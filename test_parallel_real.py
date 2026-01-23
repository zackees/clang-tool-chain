#!/usr/bin/env python3
"""
Throwaway test script to verify parallel downloads work with real files.

This downloads a real file from the internet to test the parallel download
functionality. This is NOT part of the test suite - just a quick verification.
"""

import logging
import os
import tempfile
import time
from pathlib import Path

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from clang_tool_chain.parallel_download import DownloadConfig, download_file_parallel  # noqa: E402

# Test URLs - these are publicly available files of various sizes
TEST_FILES = [
    {
        "name": "Small file (1.5 MB) - Python Windows installer",
        "url": "https://www.python.org/ftp/python/3.11.0/python-3.11.0-embed-amd64.zip",
        "expected_size": 1_500_000,  # Approximate
        "sha256": None,  # We'll skip checksum for this quick test
    },
    {
        "name": "Medium file (10 MB) - Ubuntu ISO fragment",
        "url": "https://releases.ubuntu.com/20.04/SHA256SUMS",
        "expected_size": 200,  # Small file, will use single-threaded
        "sha256": None,
    },
]

# Use a large test file from a CDN that supports range requests
LARGE_TEST_FILE = {
    "name": "Large test file from CDN (50 MB)",
    "url": "https://github.com/python/cpython/archive/refs/tags/v3.11.0.tar.gz",
    "expected_size": 50_000_000,  # Approximate
    "sha256": None,
}


def test_parallel_download():
    """Test parallel download with a real file."""
    print("\n" + "=" * 80)
    print("PARALLEL DOWNLOAD REAL-WORLD TEST")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Test 1: Small file (should fall back to single-threaded)
        print("\n" + "-" * 80)
        print("TEST 1: Small file (should use single-threaded)")
        print("-" * 80)

        dest_path = tmpdir / "small_file.zip"
        url = TEST_FILES[0]["url"]

        print(f"URL: {url}")
        print(f"Destination: {dest_path}")

        start_time = time.time()
        try:
            config = DownloadConfig(
                chunk_size=4 * 1024 * 1024,  # 4 MB chunks
                max_workers=6,
                min_size_for_parallel=10 * 1024 * 1024,  # 10 MB minimum
            )
            download_file_parallel(url, dest_path, expected_sha256=None, config=config)
            elapsed = time.time() - start_time

            if dest_path.exists():
                size = dest_path.stat().st_size
                print(f"✅ SUCCESS: Downloaded {size / (1024*1024):.2f} MB in {elapsed:.2f}s")
                print(f"   Speed: {size / elapsed / (1024*1024):.2f} MB/s")
            else:
                print("❌ FAILED: File not downloaded")
        except Exception as e:
            print(f"❌ FAILED: {e}")

        # Test 2: Large file (should use parallel if server supports it)
        print("\n" + "-" * 80)
        print("TEST 2: Large file (should use parallel if server supports range requests)")
        print("-" * 80)

        dest_path = tmpdir / "large_file.tar.gz"
        url = LARGE_TEST_FILE["url"]

        print(f"URL: {url}")
        print(f"Destination: {dest_path}")

        start_time = time.time()
        try:
            config = DownloadConfig(
                chunk_size=8 * 1024 * 1024,  # 8 MB chunks
                max_workers=6,
                min_size_for_parallel=10 * 1024 * 1024,  # 10 MB minimum
            )
            download_file_parallel(url, dest_path, expected_sha256=None, config=config)
            elapsed = time.time() - start_time

            if dest_path.exists():
                size = dest_path.stat().st_size
                print(f"✅ SUCCESS: Downloaded {size / (1024*1024):.2f} MB in {elapsed:.2f}s")
                print(f"   Speed: {size / elapsed / (1024*1024):.2f} MB/s")
            else:
                print("❌ FAILED: File not downloaded")
        except Exception as e:
            print(f"❌ FAILED: {e}")

        # Test 3: Test with parallel disabled
        print("\n" + "-" * 80)
        print("TEST 3: Same file with parallel disabled (for comparison)")
        print("-" * 80)

        dest_path2 = tmpdir / "large_file_single.tar.gz"

        # Set environment variable to disable parallel
        os.environ["CLANG_TOOL_CHAIN_DISABLE_PARALLEL"] = "1"

        # Reload the module to pick up the environment variable
        import importlib

        import clang_tool_chain.archive

        importlib.reload(clang_tool_chain.archive)

        from clang_tool_chain.archive import download_file

        print(f"URL: {url}")
        print(f"Destination: {dest_path2}")

        start_time = time.time()
        try:
            download_file(url, dest_path2, expected_sha256=None)
            elapsed = time.time() - start_time

            if dest_path2.exists():
                size = dest_path2.stat().st_size
                print(f"✅ SUCCESS: Downloaded {size / (1024*1024):.2f} MB in {elapsed:.2f}s")
                print(f"   Speed: {size / elapsed / (1024*1024):.2f} MB/s")
            else:
                print("❌ FAILED: File not downloaded")
        except Exception as e:
            print(f"❌ FAILED: {e}")
        finally:
            # Clean up environment
            del os.environ["CLANG_TOOL_CHAIN_DISABLE_PARALLEL"]
            importlib.reload(clang_tool_chain.archive)

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_parallel_download()
