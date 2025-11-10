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
MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/clang"
IWYU_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/iwyu"
# MinGW sysroot manifests are also in the bins repository for consistency
MINGW_MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain-bins/main/assets/mingw"

# Generic type variable for JSON deserialization
T = TypeVar("T")


# ============================================================================
# Custom Exceptions
# ============================================================================


class ToolchainInfrastructureError(Exception):
    """
    Raised when toolchain infrastructure is broken (404, network errors, etc).

    This exception indicates a problem with the package's distribution infrastructure
    that should cause tests to FAIL rather than skip. Examples:
    - Manifest files return 404
    - Download URLs are broken
    - Network errors accessing expected resources
    """

    pass


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

    # Check if versions are nested under a "versions" key
    if "versions" in data and isinstance(data["versions"], dict):
        # Parse nested versions structure
        for key, value in data["versions"].items():
            if isinstance(value, dict) and "href" in value and "sha256" in value:
                versions[key] = VersionInfo(version=key, href=value["href"], sha256=value["sha256"])
    else:
        # Parse flat structure (all non-"latest" keys are version entries)
        for key, value in data.items():
            if key != "latest" and isinstance(value, dict) and "href" in value and "sha256" in value:
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


def _robust_rmtree(path: Path, max_retries: int = 3) -> None:
    """
    Remove a directory tree robustly, handling Windows file permission issues.

    On Windows, files can sometimes be locked or have permission issues that prevent
    immediate deletion. This function handles those cases by:
    1. Making files writable before deletion (Windows readonly flag)
    2. Retrying with a delay if deletion fails
    3. Using ignore_errors as a last resort

    Args:
        path: Path to the directory to remove
        max_retries: Maximum number of retry attempts (default: 3)
    """
    if not path.exists():
        return

    def handle_remove_readonly(func: Any, path_str: str, exc: Any) -> None:
        """Error handler to remove readonly flag and retry."""
        import stat

        # Make the file writable and try again
        os.chmod(path_str, stat.S_IWRITE)
        func(path_str)

    # Try removing with readonly handler
    try:
        shutil.rmtree(path, onerror=handle_remove_readonly)
    except Exception as e:
        logger.warning(f"Failed to remove {path} on first attempt: {e}")
        # If that fails, try with ignore_errors as last resort
        if max_retries > 0:
            import time

            time.sleep(0.5)  # Wait briefly for file handles to close
            try:
                shutil.rmtree(path, ignore_errors=False, onerror=handle_remove_readonly)
            except Exception as e2:
                logger.warning(f"Failed to remove {path} on retry: {e2}")
                # Last resort: ignore all errors
                shutil.rmtree(path, ignore_errors=True)


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
        ToolchainInfrastructureError: If fetching or parsing fails
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
        raise ToolchainInfrastructureError(f"Failed to fetch JSON from {url}: {e}") from e


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


def _try_system_tar(tar_file: Path, extract_dir: Path) -> bool:
    """
    Try to use system tar command for extraction.

    Returns:
        True if extraction succeeded, False if tar is not available or extraction failed
    """
    import subprocess

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
                        import tempfile

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

                            import sys

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
                        import sys

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
            _robust_rmtree(install_dir)

        # Ensure parent directory exists
        install_dir.parent.mkdir(parents=True, exist_ok=True)

        extract_tarball(archive_path, install_dir)

        # Fix file permissions (set executable bits on binaries and shared libraries)
        if verbose:
            print("Fixing file permissions...")

        fix_file_permissions(install_dir)

        # On Linux, copy clang++ to clang for convenience
        if platform == "linux":
            bin_dir = install_dir / "bin"
            clang_cpp = bin_dir / "clang++"
            clang = bin_dir / "clang"
            if clang_cpp.exists() and not clang.exists():
                if verbose:
                    print("Copying clang++ to clang on Linux...")
                shutil.copy2(clang_cpp, clang)

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
                if hasattr(os, "sync"):
                    os.sync()  # type: ignore[attr-defined]

        # Write done.txt to mark successful installation
        # Ensure install_dir exists before writing done.txt
        install_dir.mkdir(parents=True, exist_ok=True)
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


# ============================================================================
# IWYU (Include What You Use) Support
# ============================================================================


def fetch_iwyu_root_manifest() -> RootManifest:
    """
    Fetch the IWYU root manifest file.

    Returns:
        Root manifest as a RootManifest object
    """
    logger.info("Fetching IWYU root manifest")
    url = f"{IWYU_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"IWYU root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_iwyu_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the IWYU platform-specific manifest file.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
    """
    logger.info(f"Fetching IWYU platform manifest for {platform}/{arch}")
    root_manifest = fetch_iwyu_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.info(f"Found IWYU manifest path: {manifest_path}")
                    url = f"{IWYU_MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    manifest = _parse_manifest(data)
                    logger.info(f"IWYU platform manifest loaded successfully for {platform}/{arch}")
                    return manifest

    logger.error(f"IWYU platform {platform}/{arch} not found in manifest")
    raise RuntimeError(f"IWYU platform {platform}/{arch} not found in manifest")


def get_iwyu_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for IWYU.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the IWYU installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "iwyu" / platform / arch
    return install_dir


def get_iwyu_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for IWYU installation.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"iwyu-{platform}-{arch}.lock"
    return lock_path


def is_iwyu_installed(platform: str, arch: str) -> bool:
    """
    Check if IWYU is already installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed, False otherwise
    """
    install_dir = get_iwyu_install_dir(platform, arch)
    done_file = install_dir / "done.txt"
    return done_file.exists()


def download_and_install_iwyu(platform: str, arch: str) -> None:
    """
    Download and install IWYU for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Downloading and installing IWYU for {platform}/{arch}")

    # Fetch the manifest to get download URL and checksum
    manifest = fetch_iwyu_platform_manifest(platform, arch)
    version_info = manifest.versions[manifest.latest]

    logger.info(f"IWYU version: {manifest.latest}")
    logger.info(f"Download URL: {version_info.href}")

    # Create temporary download directory
    install_dir = get_iwyu_install_dir(platform, arch)
    logger.info(f"Installation directory: {install_dir}")

    # Remove old installation if exists
    if install_dir.exists():
        logger.info("Removing old IWYU installation")
        _robust_rmtree(install_dir)

    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        archive_file = temp_path / "iwyu.tar.zst"

        # Download the archive
        download_file(version_info.href, archive_file, version_info.sha256)

        # Extract to installation directory
        logger.info("Extracting IWYU archive")
        extract_tarball(archive_file, install_dir)

        # Fix permissions on Unix systems
        if os.name != "nt":
            logger.info("Setting executable permissions on IWYU binaries")
            fix_file_permissions(install_dir)

        # Mark installation as complete
        # Ensure install_dir exists before writing done.txt
        install_dir.mkdir(parents=True, exist_ok=True)
        done_file = install_dir / "done.txt"
        with open(done_file, "w") as f:
            f.write(f"IWYU {manifest.latest} installed successfully\n")

        logger.info(f"IWYU installation complete for {platform}/{arch}")


def ensure_iwyu(platform: str, arch: str) -> None:
    """
    Ensure IWYU is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    If IWYU is not installed, it will be downloaded and installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Ensuring IWYU is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately
    if is_iwyu_installed(platform, arch):
        logger.info(f"IWYU already installed for {platform}/{arch}")
        return

    # Need to download - acquire lock
    logger.info(f"IWYU not installed, acquiring lock for {platform}/{arch}")
    lock_path = get_iwyu_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire IWYU installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Check again inside lock in case another process just finished installing
        if is_iwyu_installed(platform, arch):
            logger.info("Another process installed IWYU while we waited")
            return

        # Download and install
        logger.info("Starting IWYU download and installation")
        download_and_install_iwyu(platform, arch)
        logger.info(f"IWYU installation complete for {platform}/{arch}")


# ============================================================================
# MinGW Sysroot Support (Windows GNU ABI)
# ============================================================================


def fetch_mingw_root_manifest() -> RootManifest:
    """
    Fetch the MinGW sysroot root manifest file.

    Returns:
        Root manifest as a RootManifest object
    """
    logger.info("Fetching MinGW sysroot root manifest")
    url = f"{MINGW_MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    manifest = _parse_root_manifest(data)
    logger.info(f"MinGW sysroot root manifest loaded with {len(manifest.platforms)} platforms")
    return manifest


def fetch_mingw_platform_manifest(platform: str, arch: str) -> Manifest:
    """
    Fetch the MinGW sysroot platform-specific manifest file.

    Args:
        platform: Platform name (e.g., "win")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Platform manifest as a Manifest object

    Raises:
        RuntimeError: If platform/arch combination is not found
    """
    logger.info(f"Fetching MinGW sysroot platform manifest for {platform}/{arch}")
    root_manifest = fetch_mingw_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    logger.info(f"Found MinGW sysroot manifest path: {manifest_path}")
                    url = f"{MINGW_MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    manifest = _parse_manifest(data)
                    logger.info(f"MinGW sysroot platform manifest loaded successfully for {platform}/{arch}")
                    return manifest

    logger.error(f"MinGW sysroot platform {platform}/{arch} not found in manifest")
    raise RuntimeError(f"MinGW sysroot platform {platform}/{arch} not found in manifest")


def get_mingw_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for MinGW sysroot.

    Args:
        platform: Platform name (e.g., "win")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the MinGW sysroot installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "mingw" / platform / arch
    return install_dir


def get_mingw_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for MinGW sysroot installation.

    Args:
        platform: Platform name (e.g., "win")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"mingw-{platform}-{arch}.lock"
    return lock_path


def is_mingw_installed(platform: str, arch: str) -> bool:
    """
    Check if MinGW sysroot is already installed.

    Args:
        platform: Platform name (e.g., "win")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed, False otherwise
    """
    install_dir = get_mingw_install_dir(platform, arch)
    done_file = install_dir / "done.txt"
    return done_file.exists()


# Alias for consistency with test naming
is_mingw_sysroot_installed = is_mingw_installed


def download_and_install_mingw(platform: str, arch: str) -> None:
    """
    Download and install MinGW sysroot for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Downloading and installing MinGW sysroot for {platform}/{arch}")

    # Fetch the manifest to get download URL and checksum
    manifest = fetch_mingw_platform_manifest(platform, arch)
    version_info = manifest.versions[manifest.latest]

    logger.info(f"MinGW sysroot version: {manifest.latest}")
    logger.info(f"Download URL: {version_info.href}")

    # Create temporary download directory
    install_dir = get_mingw_install_dir(platform, arch)
    logger.info(f"Installation directory: {install_dir}")

    # Remove old installation if exists
    if install_dir.exists():
        logger.info("Removing old MinGW sysroot installation")
        _robust_rmtree(install_dir)

    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        archive_file = temp_path / "mingw-sysroot.tar.zst"

        # Download the archive
        download_file(version_info.href, archive_file, version_info.sha256)

        # Extract to installation directory
        logger.info("Extracting MinGW sysroot archive")
        extract_tarball(archive_file, install_dir)

        # Fix permissions on Unix systems (not needed for Windows but included for consistency)
        if os.name != "nt":
            logger.info("Setting executable permissions on MinGW sysroot")
            fix_file_permissions(install_dir)

        # Copy clang resource headers (mm_malloc.h, intrinsics, etc.) from clang installation
        # These are compiler builtin headers needed for compilation
        logger.info("Copying clang resource headers to MinGW sysroot")
        try:
            # Get the clang binary directory
            from . import wrapper

            clang_bin_dir = wrapper.get_platform_binary_dir()
            clang_root = clang_bin_dir.parent

            # Find clang resource directory: <clang_root>/lib/clang/<version>/include/
            clang_lib = clang_root / "lib" / "clang"
            if clang_lib.exists():
                # Find first version directory (should only be one)
                version_dirs = [d for d in clang_lib.iterdir() if d.is_dir()]
                if version_dirs:
                    clang_version_dir = version_dirs[0]
                    resource_include = clang_version_dir / "include"
                    if resource_include.exists():
                        # Copy to install_dir/lib/clang/<version>/include/
                        dest_resource = install_dir / "lib" / "clang" / clang_version_dir.name / "include"
                        dest_resource.parent.mkdir(parents=True, exist_ok=True)

                        # Copy all .h files
                        copied_count = 0
                        for header_file in resource_include.glob("*.h"):
                            dest_file = dest_resource / header_file.name
                            shutil.copy2(header_file, dest_file)
                            copied_count += 1

                        logger.info(f"Copied {copied_count} resource headers from clang installation")
                    else:
                        logger.warning(f"Clang resource include directory not found: {resource_include}")
                else:
                    logger.warning(f"No version directories found in {clang_lib}")
            else:
                logger.warning(f"Clang lib directory not found: {clang_lib}")
        except Exception as e:
            logger.warning(f"Could not copy clang resource headers: {e}")
            logger.warning("Compilation may fail for code using Intel intrinsics or SIMD instructions")

        # Mark installation as complete
        # Ensure install_dir exists before writing done.txt
        install_dir.mkdir(parents=True, exist_ok=True)
        done_file = install_dir / "done.txt"
        with open(done_file, "w") as f:
            f.write(f"MinGW sysroot {manifest.latest} installed successfully\n")

        logger.info(f"MinGW sysroot installation complete for {platform}/{arch}")


# Alias for consistency with test naming
download_and_install_mingw_sysroot = download_and_install_mingw


def ensure_mingw_sysroot_installed(platform: str, arch: str) -> Path:
    """
    Ensure MinGW sysroot is installed for Windows GNU ABI support.

    This function uses file locking to prevent concurrent downloads.
    If the sysroot is not installed, it will be downloaded and installed.

    Args:
        platform: Platform name ("win")
        arch: Architecture ("x86_64" or "arm64")

    Returns:
        Path to the installed MinGW sysroot directory

    Raises:
        ValueError: If platform is not Windows
    """
    if platform != "win":
        raise ValueError(f"MinGW sysroot only needed on Windows, not {platform}")

    logger.info(f"Ensuring MinGW sysroot is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately
    if is_mingw_installed(platform, arch):
        logger.info(f"MinGW sysroot already installed for {platform}/{arch}")
        return get_mingw_install_dir(platform, arch)

    # Need to download - acquire lock
    logger.info(f"MinGW sysroot not installed, acquiring lock for {platform}/{arch}")
    lock_path = get_mingw_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire MinGW sysroot installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Check again inside lock in case another process just finished installing
        if is_mingw_installed(platform, arch):
            logger.info("Another process installed MinGW sysroot while we waited")
            return get_mingw_install_dir(platform, arch)

        # Download and install
        logger.info("Starting MinGW sysroot download and installation")
        download_and_install_mingw(platform, arch)
        logger.info(f"MinGW sysroot installation complete for {platform}/{arch}")

    return get_mingw_install_dir(platform, arch)
