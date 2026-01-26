"""
Cosmopolitan Libc (Cosmocc) installer module.
"""

import sys
from pathlib import Path

from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.manifest import Manifest, fetch_cosmocc_platform_manifest
from clang_tool_chain.path_utils import get_cosmocc_install_dir, get_cosmocc_lock_path
from clang_tool_chain.permissions import _robust_rmtree

logger = configure_logging(__name__)


def _fix_cosmocc_symlinks_on_windows(install_dir: Path) -> None:
    """
    Fix cosmoc++ and other symlink-like files on Windows and Linux.

    The Cosmocc distribution uses a Unix-style symlink workaround where files like
    `cosmoc++` contain just the text "cosmocc" (7 bytes). This is meant to work like
    a symlink on Unix systems where the shell script checks $0 (argv[0]) to determine
    the invocation mode.

    However, when invoked through bash explicitly (bash cosmoc++), this doesn't work because:
    1. Bash treats the file as a shell script that runs "cosmocc" with no args
    2. This causes "no input files" or "precompiled headers" errors
    3. The $0 variable becomes "cosmocc" instead of "cosmoc++"

    The fix is to replace these placeholder files with actual copies of the main script.
    When the copied script is run, $0 will be "cosmoc++" which triggers C++ mode.

    Args:
        install_dir: Path to the Cosmocc installation directory
    """
    # NOTE: Originally only applied on Windows, but needed on Linux too when invoking through bash explicitly
    # (which we do to fix exec format errors on Linux)

    bin_dir = install_dir / "bin"
    if not bin_dir.exists():
        logger.warning(f"Cosmocc bin directory not found at {bin_dir}")
        return

    # Files that need to be fixed (symlink placeholders)
    symlink_files = ["cosmoc++"]

    # The source script that these should be copies of
    cosmocc_script = bin_dir / "cosmocc"

    if not cosmocc_script.exists():
        logger.warning(f"cosmocc script not found at {cosmocc_script}, cannot fix symlinks")
        return

    # Read the cosmocc script content
    cosmocc_content = cosmocc_script.read_bytes()

    for symlink_name in symlink_files:
        symlink_path = bin_dir / symlink_name

        if not symlink_path.exists():
            logger.debug(f"Symlink placeholder {symlink_name} not found, skipping")
            continue

        # Check if it's a small placeholder file (not a real script)
        file_size = symlink_path.stat().st_size
        if file_size > 100:
            # File is larger than expected for a placeholder, skip
            logger.debug(f"{symlink_name} is {file_size} bytes, not a placeholder - skipping")
            continue

        # Read the content to verify it's a placeholder
        content = symlink_path.read_text(encoding="utf-8", errors="ignore").strip()
        if content != "cosmocc":
            logger.debug(f"{symlink_name} content is '{content[:50]}...', not a placeholder - skipping")
            continue

        # This is a placeholder file - replace it with a copy of cosmocc
        logger.info(f"Fixing {symlink_name} placeholder on Windows (replacing with copy of cosmocc)")

        try:
            # Remove the placeholder and write the full script
            symlink_path.unlink()
            symlink_path.write_bytes(cosmocc_content)
            logger.info(f"Fixed {symlink_name}: replaced placeholder with {len(cosmocc_content)} byte script")
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            logger.warning(f"Failed to fix {symlink_name}: {e}")


class CosmoccInstaller(BaseToolchainInstaller):
    """Installer for Cosmopolitan Libc (Cosmocc) toolchain."""

    tool_name = "cosmocc"
    binary_name = "cosmocc"

    def get_install_dir(self, platform: str, arch: str) -> Path:
        # Cosmocc is universal, ignore platform/arch
        return get_cosmocc_install_dir()

    def get_lock_path(self, platform: str, arch: str) -> Path:
        # Cosmocc is universal, ignore platform/arch
        return get_cosmocc_lock_path()

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        # Cosmocc is universal, ignore platform/arch
        return fetch_cosmocc_platform_manifest()

    def get_binary_path(self, install_dir: Path, platform: str) -> Path:
        """Return path to cosmocc binary (no .exe extension even on Windows - APE format)."""
        return install_dir / "bin" / "cosmocc"

    def post_extract_hook(self, install_dir: Path, platform: str, arch: str) -> None:
        """Fix cosmoc++ symlink placeholders on all platforms."""
        _fix_cosmocc_symlinks_on_windows(install_dir)  # Function name is historical, now runs on all platforms

    def download_and_install(self, platform: str, arch: str, verbose: bool = False) -> None:
        """
        Download and install Cosmocc (universal installation).

        Cosmocc is the Cosmopolitan Libc toolchain that produces Actually Portable
        Executables (APE). The installation is universal/shared across all platforms.

        Args:
            platform: Optional platform name (ignored, kept for compatibility)
            arch: Optional architecture name (ignored, kept for compatibility)
            verbose: Enable verbose logging (optional, default False)
        """
        from ..archive import download_archive, extract_tarball
        from ..archive_cache import get_cached_archive, save_archive_to_cache
        from ..permissions import fix_file_permissions

        logger.info("Downloading and installing Cosmocc (universal)")

        # Initialize to avoid unbound variable errors in exception handler
        cached_archive: Path | None = None
        archive_file: Path | None = None

        try:
            # Fetch the manifest to get download URL and checksum
            manifest = self.fetch_manifest(platform, arch)
            version_info = manifest.versions[manifest.latest]

            logger.info(f"Cosmocc version: {manifest.latest}")
            logger.info(f"Download URL: {version_info.href}")

            # Get installation directory
            install_dir = self.get_install_dir(platform, arch)
            logger.info(f"Installation directory: {install_dir}")

            # Remove old installation if exists
            if install_dir.exists():
                logger.info("Removing old Cosmocc installation")
                _robust_rmtree(install_dir)

            # Check if archive is cached
            # Use "universal" as platform/arch for cache key since cosmocc is universal
            cached_archive = get_cached_archive("cosmocc", "universal", "universal", version_info.sha256)

            if cached_archive:
                # Use cached archive (no download needed)
                archive_file = cached_archive
                logger.info(f"Using cached Cosmocc archive: {archive_file}")
                print("Using cached Cosmocc archive (skipping download)", file=sys.stderr, flush=True)
            else:
                # Create temp file for download
                import tempfile

                with tempfile.NamedTemporaryFile(mode="wb", suffix=".tar.zst", delete=False) as tmp:
                    archive_file = Path(tmp.name)

                # Get file size information and print to stderr before download
                from ..parallel_download import check_server_capabilities

                print("Downloading Cosmocc toolchain for first-time installation...", file=sys.stderr, flush=True)
                capabilities = check_server_capabilities(version_info.href, timeout=10)
                if capabilities.content_length:
                    size_mb = capabilities.content_length / (1024 * 1024)
                    print(f"Download size: {size_mb:.1f} MB", file=sys.stderr, flush=True)
                else:
                    print("Download size: (size unknown, checking...)", file=sys.stderr, flush=True)

                # Download the archive (handles both single-file and multi-part)
                download_archive(version_info, archive_file)

                print("Download complete. Caching and extracting toolchain...", file=sys.stderr, flush=True)

                # Save to cache for future use (use "universal" as platform/arch)
                save_archive_to_cache(archive_file, "cosmocc", "universal", "universal", version_info.sha256)

            # Extract to installation directory
            print("Extracting Cosmocc toolchain...", file=sys.stderr, flush=True)
            logger.info("Extracting Cosmocc archive")

            # Ensure parent directory exists
            install_dir.parent.mkdir(parents=True, exist_ok=True)

            extract_tarball(archive_file, install_dir)

            # Fix permissions on Unix systems
            import os

            if os.name != "nt":
                logger.info("Setting executable permissions on Cosmocc binaries")
                fix_file_permissions(install_dir)

            # Post-extraction hooks
            self.post_extract_hook(install_dir, platform, arch)

            # Verify installation
            self.verify_installation(install_dir, platform, arch)

            # Mark installation as complete
            install_dir.mkdir(parents=True, exist_ok=True)
            done_file = install_dir / "done.txt"
            with open(done_file, "w") as f:
                f.write(f"Cosmocc {manifest.latest} installed successfully\nSHA256: {version_info.sha256}\n")

            print("Cosmocc toolchain installation complete!", file=sys.stderr, flush=True)
            logger.info("Cosmocc installation complete (universal)")

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            logger.error(f"Failed to install Cosmocc: {e}", exc_info=True)
            # Clean up failed installation
            install_dir = get_cosmocc_install_dir()
            if install_dir.exists():
                logger.info("Cleaning up failed Cosmocc installation")
                _robust_rmtree(install_dir)
            raise RuntimeError(f"Failed to install Cosmocc: {e}") from e
        finally:
            # Clean up downloaded archive (but not if it came from cache)
            if not cached_archive and archive_file and archive_file.exists():
                archive_file.unlink()


# Create singleton installer instance
_installer = CosmoccInstaller()


# Module-level functions for backward compatibility
def is_cosmocc_installed(platform: str | None = None, arch: str | None = None) -> bool:
    """
    Check if Cosmocc is already installed and hash matches current manifest.

    Args:
        platform: Optional platform name (ignored, kept for backward compatibility)
        arch: Optional architecture name (ignored, kept for backward compatibility)

    Returns:
        True if installed and hash matches, False otherwise
    """
    # Use empty strings for universal installation
    return _installer.is_installed("", "")


def download_and_install_cosmocc(platform: str | None = None, arch: str | None = None) -> None:
    """
    Download and install Cosmocc for the given platform/arch.

    Args:
        platform: Optional platform name (ignored, kept for backward compatibility)
        arch: Optional architecture name (ignored, kept for backward compatibility)
    """
    # Use empty strings for universal installation
    return _installer.download_and_install("", "")


def _subprocess_install_cosmocc(  # pyright: ignore[reportUnusedFunction]
    platform: str | None = None, arch: str | None = None
) -> int:
    """
    Install Cosmocc in a subprocess with proper process-level locking.

    Args:
        platform: Optional platform name (ignored, kept for backward compatibility)
        arch: Optional architecture name (ignored, kept for backward compatibility)

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Use empty strings for universal installation
    return _installer.subprocess_install("", "")


def ensure_cosmocc(platform: str | None = None, arch: str | None = None) -> None:
    """
    Ensure Cosmocc is installed for the given platform/arch.

    Args:
        platform: Optional platform name (ignored, kept for backward compatibility)
        arch: Optional architecture name (ignored, kept for backward compatibility)
    """
    # Use empty strings for universal installation
    return _installer.ensure("", "")
