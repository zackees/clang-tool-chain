"""
Parallel download module with HTTP range request support.

Provides high-speed downloads using multiple concurrent workers to download
different byte ranges of a file simultaneously. Automatically falls back to
single-threaded downloads for servers that don't support range requests.

Key features:
- Multi-threaded range request downloads (3-5x speedup for large files)
- Automatic server capability detection
- Graceful fallback to single-threaded download
- Progress tracking
- Checksum verification
- Resume capability for interrupted downloads
- Per-read timeouts using httpx (slow but steady streams work fine)
"""

import hashlib
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import httpx

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.manifest import ToolchainInfrastructureError

# Configure logging using centralized configuration
logger = configure_logging(__name__)

# Default configuration values
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunks (optimized for GitHub LFS)
DEFAULT_MAX_WORKERS = 6  # 6 concurrent workers (sweet spot for most connections)
MIN_FILE_SIZE_FOR_PARALLEL = 10 * 1024 * 1024  # 10 MB minimum for parallel download

# Timeout configuration
# - connect: time to establish connection
# - read: time to wait for each chunk of data (per-read, not total)
# - write: time to send request data
# - pool: time to acquire connection from pool
DEFAULT_CONNECT_TIMEOUT = 30.0  # 30 seconds to connect
DEFAULT_READ_TIMEOUT = 60.0  # 60 seconds per read operation (allows slow but steady streams)
DEFAULT_MAX_RETRIES = 3  # Retry failed chunks up to 3 times


@dataclass
class DownloadConfig:
    """Configuration for parallel downloads."""

    chunk_size: int = DEFAULT_CHUNK_SIZE
    max_workers: int = DEFAULT_MAX_WORKERS
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    read_timeout: float = DEFAULT_READ_TIMEOUT  # Per-read timeout (not total)
    min_size_for_parallel: int = MIN_FILE_SIZE_FOR_PARALLEL
    max_retries: int = DEFAULT_MAX_RETRIES  # Max retries per chunk

    @property
    def timeout(self) -> httpx.Timeout:
        """Create httpx Timeout object from config."""
        return httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=30.0,
            pool=30.0,
        )


@dataclass
class ChunkInfo:
    """Information about a chunk to download."""

    start: int
    end: int
    index: int
    total_chunks: int


@dataclass
class ServerCapabilities:
    """Server capabilities for downloads."""

    supports_ranges: bool
    content_length: int | None
    accepts_partial: bool = False


def check_server_capabilities(url: str, timeout: float = 30.0) -> ServerCapabilities:
    """
    Check if server supports range requests via HEAD request.

    Args:
        url: URL to check
        timeout: Request timeout in seconds

    Returns:
        ServerCapabilities with server support information

    Raises:
        ToolchainInfrastructureError: If HEAD request fails
    """
    logger.debug(f"Checking server capabilities for {url}")

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.head(url, headers={"User-Agent": "clang-tool-chain"})
            headers = response.headers
            content_length = headers.get("Content-Length")
            accept_ranges = headers.get("Accept-Ranges", "").lower()

            supports_ranges = accept_ranges == "bytes"
            accepts_partial = response.status_code == 206 or supports_ranges

            size = int(content_length) if content_length else None

            capabilities = ServerCapabilities(
                supports_ranges=supports_ranges, content_length=size, accepts_partial=accepts_partial
            )

            size_str = f"{size / (1024 * 1024):.2f} MB" if size else "unknown"
            logger.info(f"Server capabilities: ranges={supports_ranges}, size={size_str}, partial={accepts_partial}")

            return capabilities

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.warning(f"Failed to check server capabilities: {e}")
        # Return conservative defaults
        return ServerCapabilities(supports_ranges=False, content_length=None, accepts_partial=False)

    # This should never be reached, but satisfies type checker
    return ServerCapabilities(supports_ranges=False, content_length=None, accepts_partial=False)


def download_chunk(
    url: str,
    chunk: ChunkInfo,
    dest_path: Path,
    lock: threading.Lock,
    config: DownloadConfig,
) -> tuple[int, int, bool]:
    """
    Download a specific byte range chunk of a file with retry support.

    Uses httpx with per-read timeouts: the read timeout applies to each chunk
    of data received, not the total download time. This means slow but steady
    streams will work fine - the timeout only triggers if data stops flowing.

    Args:
        url: URL to download from
        chunk: ChunkInfo describing the byte range
        dest_path: Destination file path (must be pre-allocated)
        lock: Threading lock for synchronized file writes
        config: Download configuration with timeout settings

    Returns:
        Tuple of (chunk_index, bytes_downloaded, success)
    """
    range_header = f"bytes={chunk.start}-{chunk.end}"
    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        if attempt > 0:
            # Exponential backoff: 2s, 4s, 8s...
            delay = 2**attempt
            logger.info(
                f"Chunk {chunk.index + 1}/{chunk.total_chunks}: retry {attempt}/{config.max_retries} after {delay}s"
            )
            time.sleep(delay)

        logger.debug(f"Downloading chunk {chunk.index + 1}/{chunk.total_chunks}: {range_header}")

        try:
            with (
                httpx.Client(timeout=config.timeout, follow_redirects=True) as client,
                client.stream(
                    "GET",
                    url,
                    headers={"User-Agent": "clang-tool-chain", "Range": range_header},
                ) as response,
            ):
                # Verify we got a successful response
                if response.status_code not in (200, 206):
                    logger.warning(
                        f"Chunk {chunk.index + 1}: unexpected status {response.status_code}, expected 206 (Partial Content)"
                    )

                # Stream the data in smaller pieces
                # httpx's read timeout applies to each iter_bytes() call individually
                chunk_data = bytearray()
                read_size = 64 * 1024  # 64 KB reads

                for data in response.iter_bytes(read_size):
                    chunk_data.extend(data)

                bytes_downloaded = len(chunk_data)

                # Write chunk to file at correct position
                with lock, open(dest_path, "r+b") as f:
                    f.seek(chunk.start)
                    f.write(chunk_data)

                logger.debug(
                    f"Chunk {chunk.index + 1}/{chunk.total_chunks} complete: {bytes_downloaded / (1024 * 1024):.2f} MB"
                )

                return (chunk.index, bytes_downloaded, True)

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except httpx.TimeoutException as e:
            last_error = e
            logger.warning(f"Chunk {chunk.index + 1}/{chunk.total_chunks} attempt {attempt + 1} timed out: {e}")
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning(f"Chunk {chunk.index + 1}/{chunk.total_chunks} attempt {attempt + 1} HTTP error: {e}")
        except Exception as e:
            last_error = e
            logger.warning(f"Chunk {chunk.index + 1}/{chunk.total_chunks} attempt {attempt + 1} failed: {e}")

    # All retries exhausted
    logger.error(
        f"Chunk {chunk.index + 1}/{chunk.total_chunks} failed after {config.max_retries + 1} attempts: {last_error}"
    )
    return (chunk.index, 0, False)


def download_file_parallel(
    url: str,
    dest_path: Path,
    expected_sha256: str | None = None,
    config: DownloadConfig | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """
    Download a file using parallel range requests with multiple workers.

    This function checks if the server supports range requests, and if so,
    downloads the file in chunks using multiple threads. Falls back to
    single-threaded download if range requests are not supported.

    Args:
        url: URL to download from
        dest_path: Path to save the file
        expected_sha256: Optional SHA256 checksum to verify
        config: Optional DownloadConfig for tuning performance
        progress_callback: Optional callback(bytes_downloaded, total_bytes)

    Raises:
        ToolchainInfrastructureError: If download fails or checksum doesn't match
    """
    if config is None:
        config = DownloadConfig()

    logger.info(f"Starting parallel download from {url}")
    logger.info(f"Destination: {dest_path}")

    # Check server capabilities
    capabilities = check_server_capabilities(url, timeout=config.connect_timeout)

    # Decide whether to use parallel download
    use_parallel = (
        capabilities.supports_ranges
        and capabilities.content_length is not None
        and capabilities.content_length >= config.min_size_for_parallel
    )

    if not use_parallel:
        if not capabilities.supports_ranges:
            logger.info("Server does not support range requests, using single-threaded download")
        elif capabilities.content_length is None:
            logger.info("Unknown file size, using single-threaded download")
        else:
            logger.info(
                f"File size ({capabilities.content_length / (1024 * 1024):.2f} MB) "
                f"below threshold ({config.min_size_for_parallel / (1024 * 1024):.2f} MB), "
                f"using single-threaded download"
            )

        # Fallback to single-threaded download
        _download_file_single_threaded(url, dest_path, expected_sha256, config, progress_callback)
        return

    # Parallel download
    file_size = capabilities.content_length
    assert file_size is not None, "content_length must be set for parallel download"
    logger.info(f"File size: {file_size / (1024 * 1024):.2f} MB")

    # Calculate chunks
    chunks = _calculate_chunks(file_size, config.chunk_size)
    logger.info(f"Downloading in {len(chunks)} chunks using {config.max_workers} workers")

    # Initialize tmp_path to avoid unbound variable errors
    tmp_path: Path | None = None
    download_success = False

    try:
        # Create parent directory if it doesn't exist
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Download to temporary file first
        with tempfile.NamedTemporaryFile(delete=False, dir=dest_path.parent) as tmp_file:
            tmp_path = Path(tmp_file.name)

        # Pre-allocate file with correct size
        logger.debug(f"Pre-allocating file: {tmp_path}")
        with open(tmp_path, "wb") as f:
            f.seek(file_size - 1)
            f.write(b"\0")

        # Download chunks in parallel
        lock = threading.Lock()
        total_downloaded = 0
        failed_chunks = []

        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            # Submit all chunk download tasks
            future_to_chunk = {
                executor.submit(download_chunk, url, chunk, tmp_path, lock, config): chunk for chunk in chunks
            }

            # Process completed downloads
            for future in as_completed(future_to_chunk):
                chunk_index, bytes_downloaded, success = future.result()

                if success:
                    total_downloaded += bytes_downloaded
                    if progress_callback:
                        progress_callback(total_downloaded, file_size)
                else:
                    failed_chunks.append(chunk_index)

        # Check if any chunks failed
        if failed_chunks:
            raise ToolchainInfrastructureError(f"Failed to download {len(failed_chunks)} chunks: {failed_chunks}")

        logger.info(f"Download complete: {total_downloaded / (1024 * 1024):.2f} MB")

        # Verify checksum if provided
        if expected_sha256:
            logger.info("Verifying checksum")
            if not _verify_checksum(tmp_path, expected_sha256):
                raise ToolchainInfrastructureError(f"Checksum verification failed for {url}")

        # Move to final destination
        logger.debug(f"Moving {tmp_path} to {dest_path}")
        tmp_path.replace(dest_path)
        logger.info(f"File downloaded successfully to {dest_path}")
        download_success = True

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except ToolchainInfrastructureError:
        # Re-raise infrastructure errors as-is
        raise
    except Exception as e:
        logger.error(f"Parallel download failed: {e}")
        raise ToolchainInfrastructureError(f"Failed to download {url}: {e}") from e
    finally:
        # Clean up temporary file if download failed
        if tmp_path and tmp_path.exists() and not download_success:
            try:
                tmp_path.unlink()
                logger.debug(f"Cleaned up temporary file: {tmp_path}")
            except OSError:
                pass  # Best effort cleanup


def _calculate_chunks(file_size: int, chunk_size: int) -> list[ChunkInfo]:
    """
    Calculate chunk boundaries for parallel download.

    Args:
        file_size: Total size of file in bytes
        chunk_size: Desired chunk size in bytes

    Returns:
        List of ChunkInfo objects describing each chunk
    """
    chunks = []
    num_chunks = (file_size + chunk_size - 1) // chunk_size  # Ceiling division

    for i in range(num_chunks):
        start = i * chunk_size
        end = min(start + chunk_size - 1, file_size - 1)
        chunks.append(ChunkInfo(start=start, end=end, index=i, total_chunks=num_chunks))

    return chunks


def _download_file_single_threaded(
    url: str,
    dest_path: Path,
    expected_sha256: str | None = None,
    config: DownloadConfig | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """
    Download a file using single-threaded approach (fallback).

    Args:
        url: URL to download from
        dest_path: Path to save the file
        expected_sha256: Optional SHA256 checksum to verify
        config: Optional DownloadConfig for timeout settings
        progress_callback: Optional callback(bytes_downloaded, total_bytes)

    Raises:
        ToolchainInfrastructureError: If download fails or checksum doesn't match
    """
    if config is None:
        config = DownloadConfig()

    logger.debug("Using single-threaded download")
    tmp_path: Path | None = None
    download_success = False

    try:
        with (
            httpx.Client(timeout=config.timeout, follow_redirects=True) as client,
            client.stream("GET", url, headers={"User-Agent": "clang-tool-chain"}) as response,
        ):
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            total_size = int(content_length) if content_length else None

            if total_size:
                logger.info(f"Download size: {total_size / (1024 * 1024):.2f} MB")

            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download to temporary file first
            with tempfile.NamedTemporaryFile(delete=False, dir=dest_path.parent) as tmp_file:
                tmp_path = Path(tmp_file.name)
                logger.debug(f"Downloading to temporary file: {tmp_path}")

                # Download with progress tracking
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB chunks

                for chunk in response.iter_bytes(chunk_size):
                    tmp_file.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback and total_size:
                        progress_callback(downloaded, total_size)

                logger.info(f"Download complete: {tmp_path.stat().st_size / (1024 * 1024):.2f} MB")

        # Verify checksum if provided
        if expected_sha256 and tmp_path and not _verify_checksum(tmp_path, expected_sha256):
            raise ToolchainInfrastructureError(f"Checksum verification failed for {url}")

        # Move to final destination
        if tmp_path:
            logger.debug(f"Moving {tmp_path} to {dest_path}")
            tmp_path.replace(dest_path)
            logger.info(f"File downloaded successfully to {dest_path}")
            download_success = True

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except ToolchainInfrastructureError:
        # Re-raise infrastructure errors as-is
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        raise ToolchainInfrastructureError(f"Failed to download {url}: HTTP {e.response.status_code}") from e
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise ToolchainInfrastructureError(f"Failed to download {url}: {e}") from e
    finally:
        # Clean up temporary file if download failed
        if tmp_path and tmp_path.exists() and not download_success:
            try:
                tmp_path.unlink()
                logger.debug(f"Cleaned up temporary file: {tmp_path}")
            except OSError:
                pass  # Best effort cleanup


def _verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """
    Verify the SHA256 checksum of a file.

    Args:
        file_path: Path to the file to verify
        expected_sha256: Expected SHA256 hash (hex string)

    Returns:
        True if checksum matches, False otherwise
    """
    logger.debug(f"Verifying checksum for {file_path}")
    logger.debug(f"Expected SHA256: {expected_sha256}")

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    actual_hash = sha256_hash.hexdigest()
    logger.debug(f"Actual SHA256: {actual_hash}")

    matches = actual_hash.lower() == expected_sha256.lower()
    if matches:
        logger.info("Checksum verification passed")
    else:
        logger.error(f"Checksum verification failed! Expected: {expected_sha256}, Got: {actual_hash}")

    return matches
