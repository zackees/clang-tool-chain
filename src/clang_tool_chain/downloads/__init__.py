"""
Downloads subpackage for LLVM/Clang toolchain archive management.

This subpackage provides tools for:
- Downloading official LLVM releases
- Stripping and optimizing binaries
- Creating optimized archives with deduplication
- Extracting archives
- Managing hard-linked binary structures
- Testing compression methods

Main modules:
- fetch_and_archive: Complete pipeline for downloading and packaging
- download_binaries: Download pre-built LLVM binaries
- strip_binaries: Strip and optimize LLVM binaries for minimal size
- deduplicate_binaries: Deduplicate identical binaries
- test_compression: Test various compression methods
"""

from .fetch_and_archive import main as fetch_and_archive_main

__all__ = ["fetch_and_archive_main"]
