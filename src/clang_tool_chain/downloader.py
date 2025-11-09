"""
Toolchain downloader module.

Handles downloading and installing the LLVM/Clang toolchain binaries
from the manifest-based distribution system.
"""

import contextlib
import hashlib
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar
from urllib.request import Request, urlopen

import fasteners
import pyzstd

# Configure logging for GitHub Actions and general debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Base URL for manifest and downloads
MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain/main/downloads/clang"

# Generic type variable for JSON deserialization
T = TypeVar("T")


@dataclass
class ArchitectureEntry:
    """Represents an architecture entry in the root manifest."""

    arch: str
    manifest_path: str


@dataclass
class PlatformEntry:
    """Represents a platform entry in the root manifest."""

    platform: str
    architectures: list[ArchitectureEntry]


@dataclass
class RootManifest:
    """Represents the root manifest structure."""

    platforms: list[PlatformEntry]


@dataclass
class VersionInfo:
    """Represents version information in a platform manifest."""

    version: str
    href: str
    sha256: str


@dataclass
class Manifest:
    """Represents a platform-specific manifest structure."""

    latest: str
    versions: dict[str, VersionInfo]


def _parse_root_manifest(data: dict[str, Any]) -> RootManifest:
    """
    Parse raw JSON data into a RootManifest dataclass.

    Args:
        data: Raw JSON dictionary

    Returns:
        Parsed RootManifest object
    """
    platforms = []
    for platform_data in data.get("platforms", []):
        architectures = []
        for arch_data in platform_data.get("architectures", []):
            architectures.append(ArchitectureEntry(arch=arch_data["arch"], manifest_path=arch_data["manifest_path"]))
        platforms.append(PlatformEntry(platform=platform_data["platform"], architectures=architectures))
    return RootManifest(platforms=platforms)


def _parse_manifest(data: dict[str, Any]) -> Manifest:
    """
    Parse raw JSON data into a Manifest dataclass.

    Args:
        data: Raw JSON dictionary

    Returns:
        Parsed Manifest object
    """
    latest = data.get("latest", "")
    versions = {}

    # Parse all version entries (excluding 'latest' key)
    for key, value in data.items():
        if key != "latest" and isinstance(value, dict):
            versions[key] = VersionInfo(version=key, href=value["href"], sha256=value["sha256"])

    return Manifest(latest=latest, versions=versions)


def get_home_toolchain_dir() -> Path:
    """
    Get the home directory for clang-tool-chain downloads.

    Can be overridden with CLANG_TOOL_CHAIN_DOWNLOAD_PATH environment variable.

    Returns:
        Path to ~/.clang-tool-chain or the path specified by the environment variable
    """
    # Check for environment variable override
    env_path = os.environ.get("CLANG_TOOL_CHAIN_DOWNLOAD_PATH")
    if env_path:
        return Path(env_path)

    # Default to ~/.clang-tool-chain
    home = Path.home()
    toolchain_dir = home / ".clang-tool-chain"
    return toolchain_dir


def get_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for a specific platform/arch combination.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"{platform}-{arch}.lock"
    return lock_path


def get_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for a specific platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "clang" / platform / arch
    return install_dir


def _fetch_json_raw(url: str) -> dict[str, Any]:
    """
    Fetch and parse JSON from a URL.

    Args:
        url: URL to fetch

    Returns:
        Parsed JSON as a dictionary

    Raises:
        RuntimeError: If fetching or parsing fails
    """
    logger.info(f"Fetching JSON from: {url}")
    try:
        req = Request(url, headers={"User-Agent": "clang-tool-chain"})
        with urlopen(req, timeout=30) as response:
            data = response.read()
            logger.debug(f"Received {len(data)} bytes from {url}")
            result: dict[str, Any] = json.loads(data.decode("utf-8"))
            logger.info(f"Successfully fetched and parsed JSON from {url}")
            return result
    except Exception as e:
        logger.error(f"Failed to fetch JSON from {url}: {e}")
        raise RuntimeError(f"Failed to fetch JSON from {url}: {e}") from e


def fetch_root_manifest() -> RootManifest:
    """
    Fetch the root manifest file.

    Returns:
        Root manifest as a RootManifest object
    """
    logger.info("Fetching root manifest")
    url = f"{MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"Root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the platform-specific manifest file.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
    """
    logger.info(f"Fetching platform manifest for {platform}/{arch}")
    root_manifest = fetch_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.info(f"Found manifest path: {manifest_path}")
                    url = f"{MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    manifest = _parse_manifest(data)
                    logger.info(f"Platform manifest loaded successfully for {platform}/{arch}")
                    return manifest

    logger.error(f"Platform {platform}/{arch} not found in manifest")
    raise RuntimeError(f"Platform {platform}/{arch} not found in manifest")


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
        RuntimeError: If download fails or checksum doesn't match
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
                raise RuntimeError(f"Checksum verification failed for {url}")

            # Move to final destination
            logger.debug(f"Moving {tmp_path} to {dest_path}")
            tmp_path.replace(dest_path)
            logger.info(f"File downloaded successfully to {dest_path}")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        # Clean up temporary file if it exists
        if "tmp_path" in locals():
            tmp_path = locals()["tmp_path"]
            if tmp_path.exists():
                tmp_path.unlink()
        raise RuntimeError(f"Failed to download {url}: {e}") from e


def fix_file_permissions(install_dir: Path) -> None:
    """
    Fix file permissions after extraction to ensure binaries and shared libraries are executable.

    This function sets correct permissions on Unix/Linux systems:
    - Binaries in bin/ directories: 0o755 (rwxr-xr-x)
    - Shared libraries (.so, .dylib): 0o755 (rwxr-xr-x)
    - Headers, text files, static libs: 0o644 (rw-r--r--)

    On Windows, this is a no-op as permissions work differently.

    Args:
        install_dir: Installation directory to fix permissions in
    """
    import os
    import platform

    logger.info(f"Fixing file permissions in {install_dir}")

    # Only fix permissions on Unix-like systems (Linux, macOS)
    if platform.system() == "Windows":
        logger.debug("Skipping permission fix on Windows")
        return

    # Fix permissions for files in bin/ directory
    bin_dir = install_dir / "bin"
    if bin_dir.exists() and bin_dir.is_dir():
        for binary_file in bin_dir.iterdir():
            if binary_file.is_file():
                # Set executable permissions for all binaries
                binary_file.chmod(0o755)

    # Fix permissions for files in lib/ directory
    lib_dir = install_dir / "lib"
    if lib_dir.exists() and lib_dir.is_dir():
        for file_path in lib_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Headers, text files, and static libraries should be readable but not executable
            if file_path.suffix in {".h", ".inc", ".modulemap", ".tcc", ".txt", ".a", ".syms"}:
                file_path.chmod(0o644)

            # Shared libraries need executable permissions
            elif (
                file_path.suffix in {".so", ".dylib"}
                or ".so." in file_path.name
                or "/bin/" in str(file_path)
                and file_path.suffix not in {".h", ".inc", ".txt", ".a", ".so", ".dylib"}
            ):
                file_path.chmod(0o755)

    # Force filesystem sync to ensure all permission changes are committed
    # This prevents "Text file busy" errors when another thread tries to execute
    # binaries immediately after this function returns
    if bin_dir and bin_dir.exists():
        # Sync the bin directory to ensure all changes are written
        fd = os.open(str(bin_dir), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


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

        # Extract tar file to temp directory first
        temp_extract_dir = dest_dir.parent / f"{dest_dir.name}_temp"
        logger.debug(f"Creating temp extract directory: {temp_extract_dir}")
        temp_extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Extracting tar archive to {temp_extract_dir}")
            with tarfile.open(temp_tar, "r") as tar:
                # Extract all members using extractall, then convert hardlinks to regular files
                # This is necessary because:
                # 1. Python 3.12+ extraction filters can interfere with hardlinks
                # 2. Hardlinks may not work correctly across all platforms
                # 3. We want independent file copies for distribution anyway
                logger.debug("Extracting archive with extractall (preserving hardlinks)")

                import sys

                # For Python 3.12+, use filter="tar" to allow hardlinks
                # The "data" filter blocks hardlinks and causes issues
                if sys.version_info >= (3, 12):
                    logger.debug("Using Python 3.12+ tar extraction with 'tar' filter")
                    tar.extractall(temp_extract_dir, filter="tar")
                else:
                    logger.debug("Using legacy tar extraction")
                    tar.extractall(temp_extract_dir)

                # Convert hardlinks to independent files
                # Find all hardlinks and replace them with copies
                logger.debug("Converting hardlinks to independent files")
                hardlink_count = 0

                for member in tar.getmembers():
                    if member.islnk():
                        # member.linkname is the target of the hardlink
                        # member.name is the hardlink itself
                        link_target = temp_extract_dir / member.linkname
                        link_path = temp_extract_dir / member.name

                        if link_target.exists() and link_path.exists():
                            # Both files exist - check if they're still hardlinked
                            if link_target.stat().st_ino == link_path.stat().st_ino:
                                # They're hardlinked, break the link by copying
                                logger.debug(f"Breaking hardlink: {member.name} -> {member.linkname}")
                                with tempfile.NamedTemporaryFile(delete=False, dir=link_path.parent) as tmp_file:
                                    tmp_path = Path(tmp_file.name)

                                shutil.copy2(link_target, tmp_path)
                                link_path.unlink()
                                tmp_path.rename(link_path)
                                hardlink_count += 1
                        elif not link_path.exists():
                            # Hardlink wasn't created, copy the target
                            if link_target.exists():
                                logger.debug(f"Creating missing hardlink copy: {member.name}")
                                link_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(link_target, link_path)
                                hardlink_count += 1
                            else:
                                logger.warning(f"Hardlink target not found: {member.linkname} for {member.name}")

                logger.info(f"Tar extraction complete ({hardlink_count} hardlinks converted to files)")

            # Find the extracted directory (should be single directory with platform name)
            extracted_items = list(temp_extract_dir.iterdir())
            logger.debug(f"Found {len(extracted_items)} items in temp extract directory")

            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                logger.debug(f"Single directory found: {extracted_items[0].name}")
                # Remove dest_dir if it exists to prevent "Directory not empty" error
                if dest_dir.exists():
                    logger.debug(f"Removing existing destination: {dest_dir}")
                    shutil.rmtree(dest_dir)
                # Rename the single extracted subdirectory to dest_dir
                logger.debug(f"Renaming {extracted_items[0]} to {dest_dir}")
                extracted_items[0].rename(dest_dir)
            else:
                logger.debug("Multiple items found, moving all to destination")
                # Remove dest_dir if it exists to prevent conflicts
                if dest_dir.exists():
                    logger.debug(f"Removing existing destination: {dest_dir}")
                    shutil.rmtree(dest_dir)
                # Create dest_dir and move all items into it
                dest_dir.mkdir(parents=True, exist_ok=True)
                for item in temp_extract_dir.iterdir():
                    logger.debug(f"Moving {item.name} to {dest_dir}")
                    item.rename(dest_dir / item.name)

            logger.info(f"Successfully extracted to {dest_dir}")

        finally:
            # Clean up temporary tar file
            if temp_tar.exists():
                logger.debug(f"Cleaning up temporary tar file: {temp_tar}")
                temp_tar.unlink()
            # Clean up temp extraction directory if it still exists
            if temp_extract_dir.exists():
                logger.debug(f"Cleaning up temp extraction directory: {temp_extract_dir}")
                shutil.rmtree(temp_extract_dir)

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise RuntimeError(f"Failed to extract {archive_path}: {e}") from e


def get_latest_version_info(platform_manifest: Manifest) -> tuple[str, str, str]:
    """
    Get the latest version information from a platform manifest.

    Args:
        platform_manifest: Platform-specific manifest object

    Returns:
        Tuple of (version, download_url, sha256)

    Raises:
        RuntimeError: If manifest is invalid or missing required fields
    """
    latest_version = platform_manifest.latest
    if not latest_version:
        raise RuntimeError("Manifest does not specify a 'latest' version")

    version_info = platform_manifest.versions.get(latest_version)
    if not version_info:
        raise RuntimeError(f"Version {latest_version} not found in manifest")

    download_url = version_info.href
    sha256 = version_info.sha256

    if not download_url:
        raise RuntimeError(f"No download URL for version {latest_version}")

    return latest_version, download_url, sha256


def is_toolchain_installed(platform: str, arch: str) -> bool:
    """
    Check if the toolchain is already installed for the given platform/arch.

    This checks for the presence of a done.txt file which is created after
    successful download and extraction.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed, False otherwise
    """
    install_dir = get_install_dir(platform, arch)
    done_file = install_dir / "done.txt"
    return done_file.exists()


def download_and_install_toolchain(platform: str, arch: str, verbose: bool = False) -> None:
    """
    Download and install the toolchain for the given platform/arch.

    This function:
    1. Fetches the root manifest
    2. Fetches the platform-specific manifest
    3. Downloads the latest toolchain archive
    4. Verifies the checksum
    5. Extracts to ~/.clang-tool-chain/clang/<platform>/<arch>

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
        verbose: If True, print progress messages

    Raises:
        RuntimeError: If download or installation fails
    """
    if verbose:
        print(f"Downloading clang-tool-chain for {platform}/{arch}...")

    # Fetch platform manifest
    platform_manifest = fetch_platform_manifest(platform, arch)

    # Get latest version info
    version, download_url, sha256 = get_latest_version_info(platform_manifest)

    if verbose:
        print(f"Latest version: {version}")
        print(f"Download URL: {download_url}")

    # Download archive to a temporary file
    # Use tempfile to avoid conflicts with test cleanup that removes temp directories
    # Create temporary file for download
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".tar.zst", delete=False) as tmp:
        archive_path = Path(tmp.name)

    try:
        if verbose:
            print(f"Downloading to {archive_path}...")

        download_file(download_url, archive_path, sha256)

        if verbose:
            print("Download complete. Verifying checksum...")

        # Extract to installation directory
        install_dir = get_install_dir(platform, arch)

        if verbose:
            print(f"Extracting to {install_dir}...")

        # Remove old installation if it exists (BEFORE extraction)
        if install_dir.exists():
            shutil.rmtree(install_dir)

        # Ensure parent directory exists
        install_dir.parent.mkdir(parents=True, exist_ok=True)

        extract_tarball(archive_path, install_dir)

        # Fix file permissions (set executable bits on binaries and shared libraries)
        if verbose:
            print("Fixing file permissions...")

        fix_file_permissions(install_dir)

        # Force filesystem sync to ensure all extracted files are fully written to disk
        # This prevents "Text file busy" errors when another thread/process tries to
        # execute the binaries immediately after we release the lock and see done.txt
        import platform as plat

        if plat.system() != "Windows" and hasattr(os, "sync"):
            # On Unix systems, call sync() to flush all filesystem buffers
            # This ensures that all extracted binaries are fully written to disk
            # before we write done.txt and release the lock
            # If sync fails, continue anyway - better to have a rare race condition
            # than to fail the installation entirely
            with contextlib.suppress(Exception):
                os.sync()

        # Write done.txt to mark successful installation
        done_file = install_dir / "done.txt"
        done_file.write_text(f"Installation completed successfully\nVersion: {version}\n")

    finally:
        # Clean up downloaded archive
        if archive_path.exists():
            archive_path.unlink()

    if verbose:
        print("Installation complete!")


def ensure_toolchain(platform: str, arch: str) -> None:
    """
    Ensure the toolchain is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    If the toolchain is not installed, it will be downloaded and installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Ensuring toolchain is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately
    if is_toolchain_installed(platform, arch):
        logger.info(f"Toolchain already installed for {platform}/{arch}")
        return

    # Need to download - acquire lock
    logger.info(f"Toolchain not installed, acquiring lock for {platform}/{arch}")
    lock_path = get_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Check again inside lock in case another process just finished installing
        if is_toolchain_installed(platform, arch):
            logger.info("Another process installed the toolchain while we waited")
            return

        # Download and install
        logger.info("Starting toolchain download and installation")
        download_and_install_toolchain(platform, arch)
        logger.info(f"Toolchain installation complete for {platform}/{arch}")
