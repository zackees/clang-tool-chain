#!/usr/bin/env python3
"""
Verbose test to see exactly what's happening with parallel downloads.
"""

import logging
import tempfile
import time
from pathlib import Path

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,  # Use DEBUG to see everything
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from clang_tool_chain.parallel_download import DownloadConfig, check_server_capabilities, download_file_parallel


def test_server_capabilities():
    """Test server capability detection for various URLs."""
    print("\n" + "="*80)
    print("SERVER CAPABILITY DETECTION TEST")
    print("="*80)

    test_urls = [
        ("GitHub Release", "https://github.com/python/cpython/archive/refs/tags/v3.11.0.tar.gz"),
        ("Python.org", "https://www.python.org/ftp/python/3.11.0/python-3.11.0-embed-amd64.zip"),
        # Add more URLs as needed
    ]

    for name, url in test_urls:
        print(f"\n{name}:")
        print(f"  URL: {url}")
        try:
            caps = check_server_capabilities(url, timeout=10)
            print(f"  ✓ Supports ranges: {caps.supports_ranges}")
            print(f"  ✓ Content length: {caps.content_length / (1024*1024):.2f} MB" if caps.content_length else "  ✓ Content length: Unknown")
            print(f"  ✓ Accepts partial: {caps.accepts_partial}")

            # Determine strategy
            config = DownloadConfig()
            will_use_parallel = (
                caps.supports_ranges
                and caps.content_length is not None
                and caps.content_length >= config.min_size_for_parallel
            )
            print(f"  → Strategy: {'PARALLEL' if will_use_parallel else 'SINGLE-THREADED'}")

        except Exception as e:
            print(f"  ✗ Error: {e}")

def test_download_with_logging():
    """Test download with detailed logging."""
    print("\n" + "="*80)
    print("DETAILED DOWNLOAD TEST")
    print("="*80)

    url = "https://github.com/python/cpython/archive/refs/tags/v3.11.0.tar.gz"

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_path = Path(tmpdir) / "test.tar.gz"

        print(f"\nDownloading: {url}")
        print(f"Destination: {dest_path}")
        print("\nWatch the logs above for details...\n")

        config = DownloadConfig(
            chunk_size=4 * 1024 * 1024,  # 4 MB chunks for faster test
            max_workers=4,  # Use 4 workers
            min_size_for_parallel=5 * 1024 * 1024  # 5 MB minimum
        )

        start = time.time()
        try:
            download_file_parallel(url, dest_path, expected_sha256=None, config=config)
            elapsed = time.time() - start

            if dest_path.exists():
                size = dest_path.stat().st_size
                print("\n✅ Download complete!")
                print(f"   Size: {size / (1024*1024):.2f} MB")
                print(f"   Time: {elapsed:.2f}s")
                print(f"   Speed: {size / elapsed / (1024*1024):.2f} MB/s")
            else:
                print("\n❌ Download failed - file not found")

        except Exception as e:
            print(f"\n❌ Download failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_server_capabilities()
    test_download_with_logging()
    print("\n" + "="*80)
    print("TESTS COMPLETE")
    print("="*80)
