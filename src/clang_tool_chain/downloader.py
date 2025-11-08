"""
Toolchain downloader module.

Handles downloading and installing the LLVM/Clang toolchain binaries
from the manifest-based distribution system.
"""

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar
from urllib.request import Request, urlopen

import fasteners
import pyzstd

# Base URL for manifest and downloads
MANIFEST_BASE_URL = "https://raw.githubusercontent.com/zackees/clang-tool-chain/main/downloads"

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


def _parse_root_manifest(data: dict) -> RootManifest:
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


def _parse_manifest(data: dict) -> Manifest:
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
    install_dir = toolchain_dir / platform / arch
    return install_dir


def _fetch_json_raw(url: str) -> dict:
    """
    Fetch and parse JSON from a URL.

    Args:
        url: URL to fetch

    Returns:
        Parsed JSON as a dictionary

    Raises:
        RuntimeError: If fetching or parsing fails
    """
    try:
        req = Request(url, headers={"User-Agent": "clang-tool-chain"})
        with urlopen(req, timeout=30) as response:
            data = response.read()
            result: dict = json.loads(data.decode("utf-8"))
            return result
    except Exception as e:
        raise RuntimeError(f"Failed to fetch JSON from {url}: {e}") from e


def fetch_root_manifest() -> RootManifest:
    """
    Fetch the root manifest file.

    Returns:
        Root manifest as a RootManifest object
    """
    url = f"{MANIFEST_BASE_URL}/manifest.json"
    data = _fetch_json_raw(url)
    return _parse_root_manifest(data)


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
    root_manifest = fetch_root_manifest()

    # Find the platform in the manifest
    for plat_entry in root_manifest.platforms:
        if plat_entry.platform == platform:
            # Find the architecture
            for arch_entry in plat_entry.architectures:
                if arch_entry.arch == arch:
                    manifest_path = arch_entry.manifest_path
                    url = f"{MANIFEST_BASE_URL}/{manifest_path}"
                    data = _fetch_json_raw(url)
                    return _parse_manifest(data)

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
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    actual_hash = sha256_hash.hexdigest()
    return actual_hash.lower() == expected_sha256.lower()


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
    try:
        req = Request(url, headers={"User-Agent": "clang-tool-chain"})
        with urlopen(req, timeout=300) as response:
            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download to temporary file first
            with tempfile.NamedTemporaryFile(delete=False, dir=dest_path.parent) as tmp_file:
                tmp_path = Path(tmp_file.name)
                shutil.copyfileobj(response, tmp_file)

            # Verify checksum if provided
            if expected_sha256 and not verify_checksum(tmp_path, expected_sha256):
                tmp_path.unlink()
                raise RuntimeError(f"Checksum verification failed for {url}")

            # Move to final destination
            tmp_path.replace(dest_path)

    except Exception as e:
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
    import platform

    # Only fix permissions on Unix-like systems (Linux, macOS)
    if platform.system() == "Windows":
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


def extract_tarball(archive_path: Path, dest_dir: Path) -> None:
    """
    Extract a tar.zst archive to a destination directory.

    Args:
        archive_path: Path to the archive file
        dest_dir: Directory to extract to

    Raises:
        RuntimeError: If extraction fails
    """
    try:
        # Decompress zstd to temporary tar file
        temp_tar = archive_path.with_suffix("")  # Remove .zst extension

        # Decompress with pyzstd
        with open(archive_path, "rb") as compressed, open(temp_tar, "wb") as decompressed:
            decompressed.write(pyzstd.decompress(compressed.read()))

        # Extract tar file to temp directory first
        temp_extract_dir = dest_dir.parent / f"{dest_dir.name}_temp"
        temp_extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(temp_tar, "r") as tar:
                # Use filter parameter for Python 3.12+, otherwise use extractall without filter
                import sys

                if sys.version_info >= (3, 12):
                    tar.extractall(temp_extract_dir, filter="data")
                else:
                    tar.extractall(temp_extract_dir)

            # Find the extracted directory (should be single directory with platform name)
            extracted_items = list(temp_extract_dir.iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                # Rename the single extracted subdirectory to dest_dir
                extracted_items[0].rename(dest_dir)
            else:
                # Create dest_dir and move all items into it
                dest_dir.mkdir(parents=True, exist_ok=True)
                for item in temp_extract_dir.iterdir():
                    item.rename(dest_dir / item.name)

        finally:
            # Clean up temporary tar file
            if temp_tar.exists():
                temp_tar.unlink()
            # Clean up temp extraction directory if it still exists
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)

    except Exception as e:
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
    5. Extracts to ~/.clang-tool-chain/<platform>/<arch>

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

    # Create temporary download directory
    toolchain_dir = get_home_toolchain_dir()
    temp_dir = toolchain_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Download archive
    archive_name = download_url.split("/")[-1]
    archive_path = temp_dir / archive_name

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

    # Write done.txt to mark successful installation
    done_file = install_dir / "done.txt"
    done_file.write_text(f"Installation completed successfully\nVersion: {version}\n")

    # Clean up downloaded archive
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
    # Quick check without lock - if already installed, return immediately
    if is_toolchain_installed(platform, arch):
        return

    # Need to download - acquire lock
    lock_path = get_lock_path(platform, arch)
    lock = fasteners.InterProcessLock(str(lock_path))

    with lock:
        # Check again inside lock in case another process just finished installing
        if is_toolchain_installed(platform, arch):
            return

        # Download and install
        download_and_install_toolchain(platform, arch)
