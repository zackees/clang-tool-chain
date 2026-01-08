"""
Archive caching module.

Manages caching of downloaded archives to avoid re-downloading when toolchains are purged.
Archives are validated by SHA256 hash before reuse.
"""

import contextlib
import hashlib
import shutil
from pathlib import Path

from .logging_config import configure_logging
from .path_utils import get_archive_cache_dir, get_cached_archive_path

logger = configure_logging(__name__)


def verify_archive_hash(archive_path: Path, expected_sha256: str) -> bool:
    """
    Verify the SHA256 hash of a cached archive.

    Args:
        archive_path: Path to the archive file
        expected_sha256: Expected SHA256 hash (hex string)

    Returns:
        True if hash matches, False otherwise
    """
    if not archive_path.exists():
        return False

    logger.debug(f"Verifying cached archive hash: {archive_path}")
    sha256_hash = hashlib.sha256()

    try:
        with open(archive_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192 * 1024), b""):  # 8MB chunks
                sha256_hash.update(chunk)

        actual_hash = sha256_hash.hexdigest()
        matches = actual_hash.lower() == expected_sha256.lower()

        if matches:
            logger.info(f"Cached archive hash verified: {archive_path.name}")
        else:
            logger.warning(
                f"Cached archive hash mismatch for {archive_path.name}:\n"
                f"  Expected: {expected_sha256}\n"
                f"  Actual:   {actual_hash}"
            )

        return matches
    except Exception as e:
        logger.warning(f"Error verifying cached archive hash: {e}")
        return False


def get_cached_archive(component: str, platform: str, arch: str, sha256: str) -> Path | None:
    """
    Get a cached archive if it exists and hash matches.

    Args:
        component: Component name (e.g., "clang", "iwyu", "lldb", "emscripten", "nodejs")
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
        sha256: Expected SHA256 hash of the archive

    Returns:
        Path to cached archive if valid, None otherwise
    """
    cache_path = get_cached_archive_path(component, platform, arch, sha256)

    if not cache_path.exists():
        logger.debug(f"No cached archive found at {cache_path}")
        return None

    logger.info(f"Found cached archive: {cache_path.name}")

    # Verify hash before returning
    if verify_archive_hash(cache_path, sha256):
        logger.info(f"Using cached {component} archive (skipping download)")
        return cache_path
    else:
        # Hash mismatch - remove invalid cache
        logger.warning(f"Removing invalid cached archive: {cache_path.name}")
        try:
            cache_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove invalid cache: {e}")
        return None


def save_archive_to_cache(source_path: Path, component: str, platform: str, arch: str, sha256: str) -> Path | None:
    """
    Save a downloaded archive to the cache.

    Args:
        source_path: Path to the downloaded archive
        component: Component name (e.g., "clang", "iwyu", "lldb", "emscripten", "nodejs")
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
        sha256: SHA256 hash of the archive

    Returns:
        Path to cached archive if successful, None on failure
    """
    if not source_path.exists():
        logger.warning(f"Source archive does not exist: {source_path}")
        return None

    cache_dir = get_archive_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = get_cached_archive_path(component, platform, arch, sha256)

    # Skip if already cached with matching hash
    if cache_path.exists():
        if verify_archive_hash(cache_path, sha256):
            logger.debug(f"Archive already cached: {cache_path.name}")
            return cache_path
        else:
            # Remove invalid cache
            logger.warning(f"Removing existing cache with mismatched hash: {cache_path.name}")
            try:
                cache_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove invalid cache: {e}")

    # Copy to cache
    try:
        logger.info(f"Caching {component} archive: {cache_path.name}")
        shutil.copy2(source_path, cache_path)

        # Verify the cached copy
        if verify_archive_hash(cache_path, sha256):
            logger.info(f"Successfully cached {component} archive ({cache_path.stat().st_size / (1024 * 1024):.1f} MB)")
            return cache_path
        else:
            logger.error(f"Cached archive verification failed: {cache_path.name}")
            cache_path.unlink()
            return None

    except Exception as e:
        logger.warning(f"Failed to cache archive: {e}")
        return None


def clear_archive_cache() -> int:
    """
    Clear all cached archives.

    Returns:
        Number of archives removed
    """
    cache_dir = get_archive_cache_dir()

    if not cache_dir.exists():
        logger.info("Archive cache directory does not exist")
        return 0

    count = 0
    for archive in cache_dir.glob("*.tar.zst"):
        try:
            archive.unlink()
            count += 1
            logger.debug(f"Removed cached archive: {archive.name}")
        except Exception as e:
            logger.warning(f"Failed to remove {archive.name}: {e}")

    logger.info(f"Cleared {count} cached archive(s)")
    return count


def get_cache_size() -> int:
    """
    Get the total size of cached archives in bytes.

    Returns:
        Total size in bytes
    """
    cache_dir = get_archive_cache_dir()

    if not cache_dir.exists():
        return 0

    total_size = 0
    for archive in cache_dir.glob("*.tar.zst"):
        with contextlib.suppress(Exception):
            total_size += archive.stat().st_size

    return total_size
