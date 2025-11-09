#!/usr/bin/env python3
"""
Download pre-built LLVM/Clang binaries for multiple platforms.

This script downloads official LLVM releases from GitHub and prepares them
for packaging with the clang-tool-chain Python package.
"""

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

# Import checksum database
# Note: This import may fail when running the script standalone (before package installation)
try:
    from clang_tool_chain.checksums import get_checksum, has_checksum
except ImportError:
    # Fallback when running standalone
    def get_checksum(version: str, platform: str) -> str | None:
        return None

    def has_checksum(version: str, platform: str) -> bool:
        return False

    def format_platform_key(os_name: str, arch: str) -> str:
        return f"{os_name}-{arch}"


# Default LLVM version to download
DEFAULT_VERSION = "21.1.5"

# Base URLs for LLVM releases
GITHUB_RELEASE_URL = "https://github.com/llvm/llvm-project/releases/download"

# Platform-specific binary URLs and filenames
BINARY_CONFIGS: dict[str, dict[str, str]] = {
    "win-x86_64": {
        "filename": "LLVM-{version}-win64.exe",
        "url": f"{GITHUB_RELEASE_URL}/llvmorg-{{version}}/LLVM-{{version}}-win64.exe",
        "type": "installer",
        "alt_filename": "clang+llvm-{version}-x86_64-pc-windows-msvc.tar.xz",
        "alt_url": f"{GITHUB_RELEASE_URL}/llvmorg-{{version}}/clang+llvm-{{version}}-x86_64-pc-windows-msvc.tar.xz",
    },
    "linux-x86_64": {
        "filename": "LLVM-{version}-Linux-X64.tar.xz",
        "url": f"{GITHUB_RELEASE_URL}/llvmorg-{{version}}/LLVM-{{version}}-Linux-X64.tar.xz",
        "type": "archive",
    },
    "linux-aarch64": {
        "filename": "LLVM-{version}-Linux-ARM64.tar.xz",
        "url": f"{GITHUB_RELEASE_URL}/llvmorg-{{version}}/LLVM-{{version}}-Linux-ARM64.tar.xz",
        "type": "archive",
    },
    "darwin-x86_64": {
        "filename": "clang+llvm-{version}-x86_64-apple-darwin.tar.xz",
        "url": f"{GITHUB_RELEASE_URL}/llvmorg-{{version}}/clang+llvm-{{version}}-x86_64-apple-darwin.tar.xz",
        "type": "archive",
    },
    "darwin-arm64": {
        "filename": "clang+llvm-{version}-arm64-apple-darwin.tar.xz",
        "url": f"{GITHUB_RELEASE_URL}/llvmorg-{{version}}/clang+llvm-{{version}}-arm64-apple-darwin.tar.xz",
        "type": "archive",
    },
}


class BinaryDownloader:
    """Download and extract LLVM binaries for different platforms."""

    def __init__(self, version: str = DEFAULT_VERSION, output_dir: str = "downloads", verify_checksums: bool = True):
        """
        Initialize the downloader.

        Args:
            version: LLVM version to download (e.g., "21.1.5")
            output_dir: Directory to store downloaded files
            verify_checksums: Whether to verify SHA256 checksums after download
        """
        self.version = version
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verify_checksums = verify_checksums

    def compute_sha256(self, file_path: Path) -> str:
        """
        Compute SHA256 checksum of a file.

        Args:
            file_path: Path to the file

        Returns:
            SHA256 checksum as hex string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def verify_checksum(self, file_path: Path, expected_checksum: str | None = None) -> bool:
        """
        Verify SHA256 checksum of a downloaded file.

        Args:
            file_path: Path to the file to verify
            expected_checksum: Expected SHA256 checksum (optional)

        Returns:
            True if checksum matches or verification is skipped, False otherwise
        """
        if not self.verify_checksums:
            return True

        if expected_checksum is None:
            print(f"Note: No checksum provided for {file_path.name}, skipping verification")
            return True

        try:
            print(f"Verifying checksum for {file_path.name}...")
            actual_checksum = self.compute_sha256(file_path)

            if actual_checksum.lower() == expected_checksum.lower():
                print(f"✓ Checksum verified: {actual_checksum[:16]}...")
                return True
            else:
                print("✗ Checksum mismatch!")
                print(f"  Expected: {expected_checksum}")
                print(f"  Actual:   {actual_checksum}")
                return False

        except Exception as e:
            print(f"Error verifying checksum: {e}")
            return False

    def download_file(
        self, url: str, destination: Path, show_progress: bool = True, expected_checksum: str | None = None
    ) -> bool:
        """
        Download a file from URL to destination.

        Args:
            url: URL to download from
            destination: Path to save the file
            show_progress: Whether to show download progress
            expected_checksum: Expected SHA256 checksum for verification (optional)

        Returns:
            True if download was successful, False otherwise
        """
        try:
            print(f"Downloading {url}...")

            # Check if file already exists
            if destination.exists():
                print(f"File already exists: {destination}")
                # Verify existing file's checksum if provided
                if expected_checksum and self.verify_checksums:
                    if self.verify_checksum(destination, expected_checksum):
                        print("Existing file verified, skipping download.")
                        return True
                    else:
                        print("Existing file failed verification, re-downloading...")
                else:
                    response = input("Overwrite? (y/n): ").lower()
                    if response != "y":
                        print("Skipping download.")
                        return True

            # Download with progress reporting
            def reporthook(blocknum: int, blocksize: int, totalsize: int) -> None:
                if show_progress and totalsize > 0:
                    downloaded = blocknum * blocksize
                    percent = min(100, downloaded * 100 / totalsize)
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = totalsize / (1024 * 1024)
                    print(f"\rProgress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="")

            urllib.request.urlretrieve(url, destination, reporthook if show_progress else None)

            if show_progress:
                print()  # New line after progress

            print(f"Successfully downloaded to {destination}")

            # Verify checksum if provided
            if expected_checksum and not self.verify_checksum(destination, expected_checksum):
                print("Warning: Downloaded file failed checksum verification")
                print("The file may be corrupted or tampered with")
                # Don't return False to allow continuation, but warn user
                return False

            return True

        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False

    def extract_archive(self, archive_path: Path, extract_dir: Path) -> bool:
        """
        Extract a tar.xz archive.

        Args:
            archive_path: Path to the archive file
            extract_dir: Directory to extract to

        Returns:
            True if extraction was successful, False otherwise
        """
        try:
            print(f"Extracting {archive_path}...")
            extract_dir.mkdir(parents=True, exist_ok=True)

            with tarfile.open(archive_path, "r:xz") as tar:
                tar.extractall(extract_dir)

            print(f"Successfully extracted to {extract_dir}")
            return True

        except Exception as e:
            print(f"Error extracting {archive_path}: {e}")
            return False

    def extract_windows_installer(self, installer_path: Path, extract_dir: Path) -> bool:
        """
        Extract Windows .exe installer using 7zip or fallback method.

        Args:
            installer_path: Path to the .exe installer
            extract_dir: Directory to extract to

        Returns:
            True if extraction was successful, False otherwise
        """
        try:
            print(f"Extracting Windows installer {installer_path}...")
            extract_dir.mkdir(parents=True, exist_ok=True)

            # Try using 7zip if available
            if shutil.which("7z"):
                result = subprocess.run(
                    ["7z", "x", str(installer_path), f"-o{extract_dir}", "-y"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    print(f"Successfully extracted to {extract_dir}")
                    return True
                else:
                    print(f"7zip extraction failed: {result.stderr}")

            # Fallback: suggest manual extraction
            print("Warning: Could not automatically extract Windows installer.")
            print(f"Please manually extract {installer_path} to {extract_dir}")
            print("You can use 7-Zip or run the installer in extract-only mode.")
            return False

        except Exception as e:
            print(f"Error extracting {installer_path}: {e}")
            return False

    def download_platform(self, platform_key: str, expected_checksum: str | None = None) -> Path | None:
        """
        Download binaries for a specific platform.

        Args:
            platform_key: Platform identifier (e.g., "linux-x86_64")
            expected_checksum: Optional SHA256 checksum to verify download

        Returns:
            Path to the extracted directory, or None if download failed
        """
        if platform_key not in BINARY_CONFIGS:
            print(f"Unknown platform: {platform_key}")
            print(f"Available platforms: {', '.join(BINARY_CONFIGS.keys())}")
            return None

        config = BINARY_CONFIGS[platform_key]
        filename = config["filename"].format(version=self.version)
        url = config["url"].format(version=self.version)

        # Try to get checksum from database if not provided
        if expected_checksum is None and self.verify_checksums:
            # Normalize platform key for checksum lookup
            # Convert platform_key format to checksum format
            # e.g., "darwin-x86_64" -> "mac-x86_64", "linux-aarch64" -> "linux-arm64"
            checksum_platform = platform_key
            if platform_key.startswith("darwin-"):
                checksum_platform = platform_key.replace("darwin-", "mac-")
            if "aarch64" in platform_key:
                checksum_platform = checksum_platform.replace("aarch64", "arm64")

            db_checksum = get_checksum(self.version, checksum_platform)
            if db_checksum:
                print(f"Using checksum from database for {checksum_platform}")
                expected_checksum = db_checksum
            elif has_checksum(self.version, checksum_platform):
                # Checksum exists but is empty (should not happen with current implementation)
                print(f"Warning: Empty checksum found in database for {checksum_platform}")
            else:
                print(f"Note: No checksum available in database for {checksum_platform} version {self.version}")
                print("      The file will be downloaded but cannot be automatically verified.")
                print("      To add checksum verification, see: src/clang_tool_chain/checksums.py")

        # Download the file
        download_path = self.output_dir / filename
        if not self.download_file(url, download_path, expected_checksum=expected_checksum):
            # Try alternative URL if available
            if "alt_url" in config and "alt_filename" in config:
                print("Trying alternative download URL...")
                filename = config["alt_filename"].format(version=self.version)
                url = config["alt_url"].format(version=self.version)
                download_path = self.output_dir / filename
                if not self.download_file(url, download_path, expected_checksum=expected_checksum):
                    return None
            else:
                return None

        # Extract the archive
        extract_dir = self.output_dir / f"{platform_key}-extracted"

        if config["type"] == "installer":
            if not self.extract_windows_installer(download_path, extract_dir):
                print(f"Note: You may need to manually extract {download_path}")
        else:
            if not self.extract_archive(download_path, extract_dir):
                return None

        return extract_dir

    def download_all(self, platforms: list[str] | None = None) -> dict[str, Path | None]:
        """
        Download binaries for all or specified platforms.

        Args:
            platforms: List of platform keys to download, or None for all

        Returns:
            Dictionary mapping platform keys to extracted directory paths
        """
        if platforms is None:
            platforms = list(BINARY_CONFIGS.keys())

        results = {}
        for platform_key in platforms:
            print(f"\n{'='*60}")
            print(f"Downloading {platform_key}")
            print(f"{'='*60}\n")

            extract_dir = self.download_platform(platform_key)
            results[platform_key] = extract_dir

            if extract_dir:
                print(f"✓ {platform_key}: Success")
            else:
                print(f"✗ {platform_key}: Failed")

        return results


def get_current_platform() -> str | None:
    """
    Detect the current platform and return its key.

    Returns:
        Platform key string, or None if platform not supported
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "win-x86_64"
    elif system == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x86_64"
        elif machine in ("aarch64", "arm64"):
            return "linux-aarch64"
    elif system == "darwin":
        if machine == "x86_64":
            return "darwin-x86_64"
        elif machine in ("arm64", "aarch64"):
            return "darwin-arm64"

    return None


def main() -> None:
    """Main entry point for the download script."""
    parser = argparse.ArgumentParser(description="Download pre-built LLVM/Clang binaries for multiple platforms")
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help=f"LLVM version to download (default: {DEFAULT_VERSION})",
    )
    parser.add_argument(
        "--output",
        default="downloads",
        help="Output directory for downloaded files (default: downloads)",
    )
    parser.add_argument(
        "--platform",
        action="append",
        choices=list(BINARY_CONFIGS.keys()),
        help="Platform to download (can specify multiple times, default: all)",
    )
    parser.add_argument(
        "--current-only",
        action="store_true",
        help="Only download binaries for the current platform",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip SHA256 checksum verification (not recommended)",
    )

    args = parser.parse_args()

    # Determine which platforms to download
    platforms = None
    if args.current_only:
        current_platform = get_current_platform()
        if current_platform:
            platforms = [current_platform]
            print(f"Detected current platform: {current_platform}")
        else:
            print("Error: Could not detect current platform")
            sys.exit(1)
    elif args.platform:
        platforms = args.platform

    # Download binaries
    downloader = BinaryDownloader(version=args.version, output_dir=args.output, verify_checksums=not args.no_verify)
    results = downloader.download_all(platforms=platforms)

    # Print summary
    print(f"\n{'='*60}")
    print("Download Summary")
    print(f"{'='*60}\n")

    success_count = sum(1 for path in results.values() if path is not None)
    total_count = len(results)

    for platform_key, extract_dir in results.items():
        status = "✓ Success" if extract_dir else "✗ Failed"
        print(f"{platform_key:20s} {status}")
        if extract_dir:
            print(f"  Location: {extract_dir}")

    print(f"\nTotal: {success_count}/{total_count} successful")

    if success_count < total_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
