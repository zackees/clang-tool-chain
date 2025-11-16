"""
Archive operations module.

Handles downloading, checksum verification, and extraction of archives:
- Single-file and multi-part archive downloads
- SHA256 checksum verification
- Zstd decompression
- Tar extraction with system tar fallback
- MinGW archive special handling
"""

import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

import pyzstd

from .logging_config import configure_logging
from .manifest import ToolchainInfrastructureError, VersionInfo
from .permissions import _robust_rmtree

# Configure logging using centralized configuration
logger = configure_logging(__name__)


def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """
    Verify the SHA256 checksum of a file.

    Args:
        file_path: Path to the file to verify
        expected_sha256: Expected SHA256 hash (hex string)

    Returns:
        True if checksum matches, False otherwise
    """
    logger.info(f"Verifying checksum for {file_path}")
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


def download_file(url: str, dest_path: Path, expected_sha256: str | None = None) -> None:
    """
    Download a file from a URL to a destination path.

    Args:
        url: URL to download from
        dest_path: Path to save the file
        expected_sha256: Optional SHA256 checksum to verify

    Raises:
        ToolchainInfrastructureError: If download fails or checksum doesn't match
    """
    logger.info(f"Downloading file from {url}")
    logger.info(f"Destination: {dest_path}")
    try:
        req = Request(url, headers={"User-Agent": "clang-tool-chain"})
        with urlopen(req, timeout=300) as response:
            content_length = response.getheader("Content-Length")
            if content_length:
                logger.info(f"Download size: {int(content_length) / (1024*1024):.2f} MB")

            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download to temporary file first
            with tempfile.NamedTemporaryFile(delete=False, dir=dest_path.parent) as tmp_file:
                tmp_path = Path(tmp_file.name)
                logger.debug(f"Downloading to temporary file: {tmp_path}")
                shutil.copyfileobj(response, tmp_file)
                logger.info(f"Download complete: {tmp_path.stat().st_size / (1024*1024):.2f} MB")

            # Verify checksum if provided
            if expected_sha256 and not verify_checksum(tmp_path, expected_sha256):
                tmp_path.unlink()
                raise ToolchainInfrastructureError(f"Checksum verification failed for {url}")

            # Move to final destination
            logger.debug(f"Moving {tmp_path} to {dest_path}")
            tmp_path.replace(dest_path)
            logger.info(f"File downloaded successfully to {dest_path}")

    except ToolchainInfrastructureError:
        # Re-raise infrastructure errors as-is
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        # Clean up temporary file if it exists
        if "tmp_path" in locals():
            tmp_path = locals()["tmp_path"]
            if tmp_path.exists():
                tmp_path.unlink()
        raise ToolchainInfrastructureError(f"Failed to download {url}: {e}") from e


def is_multipart_archive(version_info: VersionInfo) -> bool:
    """
    Check if a version info specifies a multi-part archive.

    Multi-part archives have a "parts" field with download URLs and checksums
    for each part. This is used for archives >100 MB that can't be stored
    directly in GitHub.

    Args:
        version_info: VersionInfo object from manifest

    Returns:
        True if this is a multi-part archive, False otherwise
    """
    # Check if the VersionInfo has been extended with a parts attribute
    return hasattr(version_info, "parts") and isinstance(version_info.parts, list) and len(version_info.parts) > 0


def download_archive_parts(version_info: VersionInfo, temp_dir: Path) -> Path:
    """
    Download and concatenate multi-part archive.

    This function downloads each part separately, verifies its checksum,
    concatenates all parts into a single archive file, and verifies the
    final archive checksum.

    Args:
        version_info: VersionInfo with 'parts' field containing part URLs and checksums
        temp_dir: Temporary directory for downloads

    Returns:
        Path to concatenated archive file

    Raises:
        ToolchainInfrastructureError: If download or checksum verification fails
    """
    if not hasattr(version_info, "parts") or not version_info.parts:
        raise ToolchainInfrastructureError("Version info does not contain parts information")

    parts = version_info.parts
    output_path = temp_dir / "archive.tar.zst"

    logger.info(f"Downloading multi-part archive ({len(parts)} parts)")

    try:
        with open(output_path, "wb") as outfile:
            for i, part_info in enumerate(parts, 1):
                part_url = part_info["href"]
                part_sha256 = part_info["sha256"]

                logger.info(f"Downloading part {i}/{len(parts)} from {part_url}")

                # Download part to memory (parts should be <100 MB)
                try:
                    req = Request(part_url, headers={"User-Agent": "clang-tool-chain"})
                    with urlopen(req, timeout=300) as response:
                        content_length = response.getheader("Content-Length")
                        if content_length:
                            logger.info(f"Part {i} size: {int(content_length) / (1024*1024):.2f} MB")

                        part_data = response.read()
                        logger.info(f"Part {i} downloaded: {len(part_data) / (1024*1024):.2f} MB")

                except Exception as e:
                    raise ToolchainInfrastructureError(f"Failed to download part {i} from {part_url}: {e}") from e

                # Verify part checksum
                logger.info(f"Verifying checksum for part {i}")
                actual_sha256 = hashlib.sha256(part_data).hexdigest()
                if actual_sha256.lower() != part_sha256.lower():
                    raise ToolchainInfrastructureError(
                        f"Part {i} checksum mismatch: expected {part_sha256}, got {actual_sha256}"
                    )
                logger.info(f"Part {i} checksum verified")

                # Append to output file
                outfile.write(part_data)

        # Verify final concatenated archive checksum
        logger.info("Verifying final archive checksum")
        if not verify_checksum(output_path, version_info.sha256):
            raise ToolchainInfrastructureError(
                f"Final archive checksum mismatch: expected {version_info.sha256}, "
                f"got {hashlib.sha256(output_path.read_bytes()).hexdigest()}"
            )

        logger.info(f"Multi-part archive assembled successfully: {output_path.stat().st_size / (1024*1024):.2f} MB")
        return output_path

    except ToolchainInfrastructureError:
        # Re-raise infrastructure errors as-is
        if output_path.exists():
            output_path.unlink()
        raise
    except Exception as e:
        logger.error(f"Failed to download multi-part archive: {e}")
        if output_path.exists():
            output_path.unlink()
        raise ToolchainInfrastructureError(f"Failed to download multi-part archive: {e}") from e


def download_archive(version_info: VersionInfo, dest_path: Path) -> None:
    """
    Download archive (single or multi-part) to destination path.

    This is a convenience wrapper that automatically detects whether the
    archive is single-file or multi-part, and handles download accordingly.

    Args:
        version_info: VersionInfo with download information
        dest_path: Destination path for the final archive

    Raises:
        ToolchainInfrastructureError: If download or checksum verification fails
    """
    if is_multipart_archive(version_info):
        # Multi-part archive - download parts and concatenate
        logger.info("Detected multi-part archive")
        with tempfile.TemporaryDirectory(prefix="multipart_download_") as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = download_archive_parts(version_info, temp_path)
            # Move to destination
            shutil.move(str(archive_path), str(dest_path))
    else:
        # Single-file download
        download_file(version_info.href, dest_path, version_info.sha256)


def _try_system_tar(tar_file: Path, extract_dir: Path) -> bool:
    """
    Try to use system tar command for extraction.

    Returns:
        True if extraction succeeded, False if tar is not available or extraction failed
    """
    # Check if tar is available
    try:
        result = subprocess.run(["tar", "--version"], capture_output=True, timeout=5)
        if result.returncode != 0:
            logger.debug("System tar not available")
            return False
        logger.info(f"System tar available: {result.stdout.decode()[:100]}")
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"System tar not available: {e}")
        return False

    # Try to extract using system tar
    try:
        logger.info(f"Using system tar to extract {tar_file}")
        result = subprocess.run(
            ["tar", "-xf", str(tar_file), "-C", str(extract_dir)], capture_output=True, timeout=300, check=True
        )
        logger.info("System tar extraction completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"System tar extraction failed: {e.stderr.decode()[:500]}")
        return False
    except Exception as e:
        logger.warning(f"System tar extraction failed: {e}")
        return False


def extract_tarball(archive_path: Path, dest_dir: Path) -> None:
    """
    Extract a tar.zst archive to a destination directory.

    Args:
        archive_path: Path to the archive file
        dest_dir: Directory to extract to

    Raises:
        RuntimeError: If extraction fails
    """
    logger.info(f"Extracting archive {archive_path} to {dest_dir}")
    try:
        # Decompress zstd to temporary tar file
        temp_tar = archive_path.with_suffix("")  # Remove .zst extension
        logger.debug(f"Decompressing zstd archive to {temp_tar}")

        # Decompress with pyzstd
        with open(archive_path, "rb") as compressed, open(temp_tar, "wb") as decompressed:
            compressed_data = compressed.read()
            logger.info(f"Decompressing {len(compressed_data) / (1024*1024):.2f} MB")
            decompressed.write(pyzstd.decompress(compressed_data))
            logger.info(f"Decompression complete: {temp_tar.stat().st_size / (1024*1024):.2f} MB")

        # DEBUG: Verify tar file immediately after decompression
        logger.debug(f"Verifying decompressed tar file: {temp_tar}")
        try:
            with tarfile.open(temp_tar, "r") as verify_tar:
                verify_members = verify_tar.getmembers()
                logger.info(f"Decompressed tar has {len(verify_members)} members")
                verify_top = set()
                for m in verify_members[:100]:  # Check first 100 members
                    parts = m.name.split("/")
                    if parts:
                        verify_top.add(parts[0])
                logger.info(f"Sample top-level dirs from tar: {sorted(verify_top)}")
        except Exception as e:
            logger.warning(f"Could not verify tar file: {e}")

        # Remove dest_dir if it exists to ensure clean extraction
        if dest_dir.exists():
            logger.debug(f"Removing existing destination: {dest_dir}")
            _robust_rmtree(dest_dir)

        # Create parent directory for extraction
        dest_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            # MinGW archives must use Python tarfile (system tar has issues with multi-root structure)
            is_mingw_archive = "mingw-sysroot" in archive_path.name
            use_python_tar = is_mingw_archive

            # Try system tar first (more reliable on Linux/macOS) unless forced to use Python
            if not use_python_tar and _try_system_tar(temp_tar, dest_dir.parent):
                logger.info("Extraction successful using system tar")
            else:
                # Use Python tarfile
                if use_python_tar:
                    logger.info("Using Python tarfile for MinGW archive (system tar has multi-root issues)")
                else:
                    logger.info("Extracting tar archive using Python tarfile")

                with tarfile.open(temp_tar, "r") as tar:
                    # For MinGW archives, extract to a temporary directory first
                    # (workaround for mysterious tar.extractall() bug where lib/ directory is lost)
                    if is_mingw_archive:
                        logger.info("Extracting MinGW archive to temp location first (workaround for extraction bug)")

                        # Sanity check: verify tar file has all expected top-level directories
                        members = tar.getmembers()
                        logger.info(f"Tar file has {len(members)} members total")
                        top_level_dirs = set()
                        for m in members:
                            parts = m.name.split("/")
                            if parts:
                                top_level_dirs.add(parts[0])
                        logger.info(f"Top-level directories in tar: {sorted(top_level_dirs)}")

                        with tempfile.TemporaryDirectory() as temp_extract:
                            temp_extract_path = Path(temp_extract)
                            logger.debug(f"Temp extraction dir: {temp_extract_path}")

                            if sys.version_info >= (3, 12):
                                tar.extractall(temp_extract_path, filter="tar")
                            else:
                                tar.extractall(temp_extract_path)

                            # Verify all expected directories are present
                            extracted = list(temp_extract_path.iterdir())
                            logger.info(f"Extracted {len(extracted)} items to temp: {[e.name for e in extracted]}")

                            # Move to final location
                            dest_dir.parent.mkdir(parents=True, exist_ok=True)
                            for item in extracted:
                                target = dest_dir.parent / item.name
                                logger.info(f"Moving {item.name} from temp to {target}")
                                shutil.move(str(item), str(target))
                    else:
                        # Regular extraction for non-MinGW archives
                        if sys.version_info >= (3, 12):
                            tar.extractall(dest_dir.parent, filter="tar")
                        else:
                            tar.extractall(dest_dir.parent)

                    logger.info("Python tarfile extraction complete")

                    # DEBUG: Check what was actually extracted
                    if is_mingw_archive:
                        extracted_check = list(dest_dir.parent.iterdir())
                        logger.info(
                            f"Post-extraction check: {len(extracted_check)} items in {dest_dir.parent}: "
                            f"{[item.name for item in extracted_check]}"
                        )

            # The archive should extract to a single directory with the expected name
            # If it doesn't match dest_dir name, rename it
            if not dest_dir.exists():
                # Look for what was extracted in the parent directory
                extracted_items = list(dest_dir.parent.iterdir())
                extracted_dirs = [d for d in extracted_items if d.is_dir()]
                extracted_files = [f for f in extracted_items if f.is_file() and f.name != "done.txt"]

                logger.debug(
                    f"Found {len(extracted_dirs)} directories and {len(extracted_files)} files in {dest_dir.parent}: "
                    f"dirs={[d.name for d in extracted_dirs]}, files={[f.name for f in extracted_files[:5]]}"
                )

                # Special case: MinGW sysroot archives have intentional multi-root structure
                # They contain: x86_64-w64-mingw32/, include/, lib/
                # This structure should be preserved as-is
                is_mingw_archive = "mingw-sysroot" in archive_path.name

                # Case 1: Archive extracted to a single top-level directory (e.g., clang archives)
                # Filter out dest_dir itself in case it was already created
                candidates = [d for d in extracted_dirs if d != dest_dir]
                if len(candidates) == 1 and len(extracted_files) == 0:
                    actual_dir = candidates[0]
                    logger.info(f"Renaming extracted directory {actual_dir} to {dest_dir}")
                    shutil.move(str(actual_dir), str(dest_dir))
                # Case 2: Archive has flat structure with bin/, share/, etc. (e.g., IWYU archives)
                # Also handles MinGW archives which have multi-root structure that must be preserved
                elif extracted_dirs or extracted_files:
                    if is_mingw_archive:
                        logger.info(f"MinGW archive detected, moving multi-root structure into {dest_dir}")
                        logger.info(f"Found {len(extracted_dirs)} directories and {len(extracted_files)} files to move")
                    else:
                        logger.info(f"Archive has flat structure, moving contents into {dest_dir}")
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for item in extracted_items:
                        if item.is_dir() or (item.is_file() and item.name != "done.txt"):
                            target = dest_dir / item.name
                            logger.info(f"Moving {item.name} to {target}")
                            shutil.move(str(item), str(target))
                else:
                    logger.warning(f"No extracted content found to move to {dest_dir}")

            logger.info(f"Successfully extracted to {dest_dir}")

        finally:
            # Clean up temporary tar file
            if temp_tar.exists():
                logger.debug(f"Cleaning up temporary tar file: {temp_tar}")
                temp_tar.unlink()

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise RuntimeError(f"Failed to extract {archive_path}: {e}") from e
