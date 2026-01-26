"""
Node.js runtime installer module.
"""

import datetime
from pathlib import Path

import fasteners

from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.manifest import Manifest, ToolchainInfrastructureError, fetch_nodejs_platform_manifest
from clang_tool_chain.path_utils import get_nodejs_install_dir, get_nodejs_lock_path
from clang_tool_chain.permissions import _robust_rmtree

logger = configure_logging(__name__)


class NodeJSInstaller(BaseToolchainInstaller):
    """Installer for Node.js runtime."""

    tool_name = "nodejs"
    binary_name = "node"

    # Use default get_install_dir() and get_lock_path() from base class

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        return fetch_nodejs_platform_manifest(platform, arch)

    def download_and_install(self, platform: str, arch: str, verbose: bool = False) -> None:
        """
        Download and install Node.js for the given platform/arch.

        This downloads a minimal Node.js runtime (~10-15 MB compressed) that includes
        only the node binary and essential libraries.

        Args:
            platform: Platform name (e.g., "win", "linux", "darwin")
            arch: Architecture name (e.g., "x86_64", "arm64")
            verbose: Enable verbose logging (optional, default False)
        """
        from ..archive import download_archive, extract_tarball
        from ..archive_cache import get_cached_archive, save_archive_to_cache
        from ..permissions import fix_file_permissions

        logger.info(f"Starting Node.js download and installation for {platform}/{arch}")

        # Initialize to avoid unbound variable errors in exception handler
        cached_archive: Path | None = None
        archive_path: Path | None = None

        try:
            # Fetch manifest
            manifest = self.fetch_manifest(platform, arch)
            latest_version = manifest.latest
            logger.info(f"Latest Node.js version: {latest_version}")

            if latest_version not in manifest.versions:
                raise RuntimeError(f"Version {latest_version} not found in manifest")

            version_info = manifest.versions[latest_version]
            download_url = version_info.href
            expected_checksum = version_info.sha256

            logger.info(f"Download URL: {download_url}")
            logger.info(f"Expected SHA256: {expected_checksum}")

            # Check if archive is cached
            cached_archive = get_cached_archive("nodejs", platform, arch, version_info.sha256)

            if cached_archive:
                # Use cached archive (no download needed)
                archive_path = cached_archive
                logger.info(f"Using cached Node.js archive: {archive_path}")
            else:
                # Create temp file for download
                import tempfile

                with tempfile.NamedTemporaryFile(mode="wb", suffix=".tar.zst", delete=False) as tmp:
                    archive_path = Path(tmp.name)

                logger.info(f"Downloading to: {archive_path}")

                # Download (handles both single-file and multi-part)
                download_archive(version_info, archive_path)
                logger.info("Download and checksum verification successful")

                # Save to cache for future use
                save_archive_to_cache(archive_path, "nodejs", platform, arch, version_info.sha256)

            # Extract
            install_dir = self.get_install_dir(platform, arch)
            logger.info(f"Extracting to: {install_dir}")

            # Remove old installation if it exists (BEFORE extraction)
            if install_dir.exists():
                logger.info("Removing old Node.js installation")
                _robust_rmtree(install_dir)

            # Ensure parent directory exists
            install_dir.parent.mkdir(parents=True, exist_ok=True)

            extract_tarball(archive_path, install_dir)

            # Fix permissions on Unix systems
            if platform in ("linux", "darwin"):
                logger.info("Fixing file permissions...")
                fix_file_permissions(install_dir)

            # Verify node binary exists
            node_binary = install_dir / "bin" / ("node.exe" if platform == "win" else "node")
            if not node_binary.exists():
                raise RuntimeError(
                    f"Node.js binary not found after extraction: {node_binary}\n"
                    f"Expected location: {node_binary}\n"
                    f"Installation may be corrupted. Please try again."
                )

            logger.info(f"Node.js binary found: {node_binary}")

            # Write done marker
            done_file = install_dir / "done.txt"
            with open(done_file, "w") as f:
                f.write(f"Node.js {latest_version} installed on {datetime.datetime.now()}\n")
                f.write(f"Platform: {platform}\n")
                f.write(f"Architecture: {arch}\n")
                f.write(f"SHA256: {version_info.sha256}\n")

            logger.info("Node.js installation complete")

            # Clean up downloaded archive (but not if it came from cache)
            if not cached_archive and archive_path and archive_path.exists():
                archive_path.unlink()

        except ToolchainInfrastructureError:
            # Clean up downloaded archive on error (but not if it came from cache)
            if not cached_archive and archive_path and archive_path.exists():
                archive_path.unlink()
            # Re-raise infrastructure errors as-is
            raise
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            # Clean up downloaded archive on error (but not if it came from cache)
            if not cached_archive and archive_path and archive_path.exists():
                archive_path.unlink()
            logger.error(f"Failed to download and install Node.js: {e}")
            # Clean up failed installation
            install_dir = self.get_install_dir(platform, arch)
            if install_dir.exists():
                logger.info("Cleaning up failed Node.js installation")
                _robust_rmtree(install_dir)
            raise RuntimeError(f"Failed to install Node.js for {platform}/{arch}: {e}") from e


# Create singleton installer instance
_installer = NodeJSInstaller()


# Module-level functions for backward compatibility
def is_nodejs_installed(platform: str, arch: str) -> bool:
    """
    Check if Node.js is already installed and hash matches current manifest.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    return _installer.is_installed(platform, arch)


def download_and_install_nodejs(platform: str, arch: str) -> None:
    """
    Download and install Node.js for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.download_and_install(platform, arch)


def ensure_nodejs_available(platform: str, arch: str) -> Path:
    """
    Ensure Node.js is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    Returns the installation directory path.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the Node.js installation directory
    """
    logger.info(f"Ensuring Node.js is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately (fast path)
    if is_nodejs_installed(platform, arch):
        logger.info(f"Node.js already installed for {platform}/{arch}")
        return get_nodejs_install_dir(platform, arch)

    # Need to download - acquire lock
    logger.info(f"Node.js not installed, acquiring lock for {platform}/{arch}")
    lock_path = get_nodejs_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire Node.js installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Check again inside lock in case another process just finished installing
        if is_nodejs_installed(platform, arch):
            logger.info("Another process installed Node.js while we waited")
            return get_nodejs_install_dir(platform, arch)

        # Download and install
        logger.info("Starting Node.js download and installation")
        try:
            download_and_install_nodejs(platform, arch)
            logger.info(f"Node.js installation complete for {platform}/{arch}")
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            logger.error(f"Node.js installation failed: {e}")
            raise

    return get_nodejs_install_dir(platform, arch)
