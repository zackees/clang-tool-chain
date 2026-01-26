"""
Base installer class for toolchain components.

Provides common installation logic and patterns used across all toolchain installers.
"""

import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

import fasteners

from clang_tool_chain.archive import download_archive, extract_tarball
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.manifest import Manifest
from clang_tool_chain.permissions import _robust_rmtree, fix_file_permissions

logger = configure_logging(__name__)


class BaseToolchainInstaller(ABC):
    """
    Base class for toolchain installers with common installation logic.

    Subclasses must define:
    - tool_name: str (e.g., "clang", "iwyu", "lldb")
    - binary_name: str (e.g., "clang", "include-what-you-use", "lldb")

    And implement:
    - fetch_manifest()

    Optional overrides (have default implementations):
    - get_install_dir() - default uses standard pattern
    - get_lock_path() - default uses standard pattern
    """

    tool_name: str
    binary_name: str

    def get_install_dir(self, platform: str, arch: str) -> Path:
        """
        Return the installation directory for this tool.

        Default implementation uses the standard pattern:
        ~/.clang-tool-chain/{tool_name}/{platform}/{arch}

        Override this if your tool needs a custom path (e.g., cosmocc uses universal/).
        """
        from ..path_utils import get_tool_install_dir

        return get_tool_install_dir(self.tool_name, platform, arch)

    def get_lock_path(self, platform: str, arch: str) -> Path:
        """
        Return the lock file path for this tool.

        Default implementation uses the standard pattern:
        ~/.clang-tool-chain/{tool_name}-{platform}-{arch}.lock

        Override this if your tool needs a custom lock path (e.g., cosmocc uses universal lock).
        """
        from ..path_utils import get_tool_lock_path

        return get_tool_lock_path(self.tool_name, platform, arch)

    @abstractmethod
    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        """Fetch the platform-specific manifest for this tool."""
        pass

    def get_binary_path(self, install_dir: Path, platform: str) -> Path:
        """
        Return path to main binary for verification.

        Override this if the binary has a non-standard location or name.
        """
        exe_ext = ".exe" if platform == "win" else ""
        return install_dir / "bin" / f"{self.binary_name}{exe_ext}"

    def post_extract_hook(self, install_dir: Path, platform: str, arch: str) -> None:  # noqa: B027
        """
        Called after extraction, before verification.

        Override this to perform custom post-extraction steps.
        """
        pass

    def verify_installation(self, install_dir: Path, platform: str, arch: str) -> None:
        """
        Verify that installation was successful.

        Override this to perform custom verification beyond checking the binary exists.
        """
        binary_path = self.get_binary_path(install_dir, platform)

        # DEBUG logging
        logger.info(f"DEBUG: Looking for {self.tool_name} binary at: {binary_path}")
        logger.info(f"DEBUG: Binary exists: {binary_path.exists()}")

        if not binary_path.exists():
            # Additional debugging before failing
            bin_dir = install_dir / "bin"
            logger.error(f"DEBUG: bin_dir ({bin_dir}) exists: {bin_dir.exists()}")
            if bin_dir.exists():
                bin_contents = list(bin_dir.iterdir())
                logger.error(f"DEBUG: bin_dir contains {len(bin_contents)} items:")
                for item in bin_contents:
                    logger.error(f"DEBUG:   - {item.name}")

            raise RuntimeError(
                f"{self.tool_name} installation verification failed: binary not found at {binary_path}. "
                f"Extraction may have failed or archive structure is incorrect."
            )
        logger.info(f"{self.tool_name} binary verified at: {binary_path}")

    def is_installed(self, platform: str, arch: str) -> bool:
        """
        Check if tool is already installed and hash matches current manifest.

        Args:
            platform: Platform name (e.g., "win", "linux", "darwin")
            arch: Architecture name (e.g., "x86_64", "arm64")

        Returns:
            True if installed and hash matches, False otherwise
        """
        install_dir = self.get_install_dir(platform, arch)
        done_file = install_dir / "done.txt"

        if not done_file.exists():
            return False

        try:
            done_content = done_file.read_text()
            installed_sha256 = None
            for line in done_content.splitlines():
                if line.startswith("SHA256:"):
                    installed_sha256 = line.split(":", 1)[1].strip()
                    break

            if not installed_sha256:
                logger.warning(f"No SHA256 found in {self.tool_name} {done_file}, will re-download")
                return False

            # Fetch current manifest
            platform_manifest = self.fetch_manifest(platform, arch)
            latest_version = platform_manifest.latest
            if not latest_version:
                return False

            version_info = platform_manifest.versions.get(latest_version)
            if not version_info:
                return False

            current_sha256 = version_info.sha256

            if installed_sha256.lower() != current_sha256.lower():
                logger.info(f"{self.tool_name} SHA256 mismatch - will re-download")
                return False

            return True

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return False  # Never reached, but needed for type checking
        except Exception as e:
            logger.warning(f"Error checking {self.tool_name} installation: {e}, will re-download")
            return False

    def download_and_install(self, platform: str, arch: str, verbose: bool = False) -> None:
        """
        Download and install tool for the given platform/arch.

        Args:
            platform: Platform name (e.g., "win", "linux", "darwin")
            arch: Architecture name (e.g., "x86_64", "arm64")
            verbose: Enable verbose logging (optional, default False)
        """
        logger.info(f"Downloading and installing {self.tool_name} for {platform}/{arch}")

        # Fetch the manifest to get download URL and checksum
        manifest = self.fetch_manifest(platform, arch)
        version_info = manifest.versions[manifest.latest]

        logger.info(f"{self.tool_name} version: {manifest.latest}")
        logger.info(f"Download URL: {version_info.href}")

        # Create temporary download directory
        install_dir = self.get_install_dir(platform, arch)
        logger.info(f"Installation directory: {install_dir}")

        # Remove old installation if exists
        if install_dir.exists():
            logger.info(f"Removing old {self.tool_name} installation")
            _robust_rmtree(install_dir)

        # Check if archive is cached
        from ..archive_cache import get_cached_archive, save_archive_to_cache

        cached_archive = get_cached_archive(self.tool_name, platform, arch, version_info.sha256)

        if cached_archive:
            # Use cached archive (no download needed)
            archive_file = cached_archive
            logger.info(f"Using cached {self.tool_name} archive: {archive_file}")
        else:
            # Create temp file for download
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".tar.zst", delete=False) as tmp:
                archive_file = Path(tmp.name)

            # Download the archive (handles both single-file and multi-part)
            download_archive(version_info, archive_file)

            # Save to cache for future use
            save_archive_to_cache(archive_file, self.tool_name, platform, arch, version_info.sha256)

        try:
            # Extract to installation directory
            logger.info(f"Extracting {self.tool_name} archive")
            extract_tarball(archive_file, install_dir)

            # DEBUG: Log directory structure after extraction
            logger.info(f"DEBUG: Checking installation directory: {install_dir}")
            logger.info(f"DEBUG: install_dir exists: {install_dir.exists()}")
            logger.info(f"DEBUG: install_dir is_dir: {install_dir.is_dir()}")

            if install_dir.exists():
                try:
                    items = list(install_dir.iterdir())
                    logger.info(f"DEBUG: Found {len(items)} items in {install_dir}")
                    for item in items:
                        logger.info(f"DEBUG:   - {item.name} ({'dir' if item.is_dir() else 'file'})")
                        if item.is_dir() and item.name == "bin":
                            bin_items = list(item.iterdir())
                            logger.info(f"DEBUG:     bin/ contains {len(bin_items)} items:")
                            for bin_item in bin_items[:10]:  # First 10 items
                                logger.info(f"DEBUG:       - {bin_item.name} ({bin_item.stat().st_size} bytes)")
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    logger.error(f"DEBUG: Error listing directory contents: {e}")
            else:
                # Check parent directory
                parent = install_dir.parent
                logger.info(f"DEBUG: install_dir doesn't exist, checking parent: {parent}")
                if parent.exists():
                    parent_items = list(parent.iterdir())
                    logger.info(f"DEBUG: Parent contains {len(parent_items)} items:")
                    for item in parent_items[:20]:  # First 20 items
                        logger.info(f"DEBUG:   - {item.name} ({'dir' if item.is_dir() else 'file'})")

            # Fix permissions on Unix systems
            if os.name != "nt":
                logger.info(f"Setting executable permissions on {self.tool_name} binaries")
                fix_file_permissions(install_dir)

            # Call post-extraction hook (for custom steps)
            self.post_extract_hook(install_dir, platform, arch)

            # Verify the installation
            self.verify_installation(install_dir, platform, arch)

            # Mark installation as complete
            # Ensure install_dir exists before writing done.txt
            install_dir.mkdir(parents=True, exist_ok=True)
            done_file = install_dir / "done.txt"
            with open(done_file, "w") as f:
                f.write(f"{self.tool_name} {manifest.latest} installed successfully\nSHA256: {version_info.sha256}\n")

            logger.info(f"{self.tool_name} installation complete for {platform}/{arch}")

        finally:
            # Clean up downloaded archive (but not if it came from cache)
            if not cached_archive and archive_file.exists():
                archive_file.unlink()

    def subprocess_install(self, platform: str, arch: str) -> int:
        """
        Install tool in a subprocess with proper process-level locking.

        Args:
            platform: Platform name
            arch: Architecture name

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            logger.info(f"[Subprocess] Installing {self.tool_name} for {platform}/{arch}")
            lock_path = self.get_lock_path(platform, arch)
            lock = fasteners.InterProcessLock(str(lock_path))

            with lock:
                logger.info(f"[Subprocess] {self.tool_name} lock acquired")
                if self.is_installed(platform, arch):
                    logger.info(f"[Subprocess] Another process installed {self.tool_name} while we waited")
                    return 0

                self.download_and_install(platform, arch)
                logger.info(f"[Subprocess] {self.tool_name} installation complete for {platform}/{arch}")

            return 0

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return 1  # Never reached, but needed for type checking
        except Exception as e:
            logger.error(f"[Subprocess] Failed to install {self.tool_name}: {e}", exc_info=True)
            return 1

    def ensure(self, platform: str, arch: str) -> None:
        """
        Ensure tool is installed for the given platform/arch.

        Uses subprocess-based installation with file locking to prevent concurrent downloads.
        InterProcessLock only works across processes, not threads, so we use subprocess.

        Args:
            platform: Platform name (e.g., "win", "linux", "darwin")
            arch: Architecture name (e.g., "x86_64", "arm64")
        """
        logger.info(f"Ensuring {self.tool_name} is installed for {platform}/{arch}")

        # Quick check without lock
        if self.is_installed(platform, arch):
            logger.info(f"{self.tool_name} already installed for {platform}/{arch}")
            return

        # Spawn subprocess for installation
        logger.info(f"{self.tool_name} not installed, spawning subprocess to install for {platform}/{arch}")

        # Get the module path for the installer
        module_path = f"{self.__class__.__module__}.{self.__class__.__name__}"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"from {module_path.rsplit('.', 1)[0]} import _subprocess_install_{self.tool_name}; "
                f"import sys; "
                f"sys.exit(_subprocess_install_{self.tool_name}('{platform}', '{arch}'))",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Include stderr in the error message so callers can detect specific errors (e.g., 404)
            error_details = result.stderr.strip() if result.stderr else ""
            raise RuntimeError(
                f"Failed to install {self.tool_name} for {platform}/{arch} "
                f"(subprocess exited with code {result.returncode}): {error_details}"
            )


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
