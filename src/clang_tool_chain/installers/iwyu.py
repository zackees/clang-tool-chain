"""
IWYU (Include What You Use) installer module.
"""

from pathlib import Path

from ..manifest import Manifest, fetch_iwyu_platform_manifest
from ..path_utils import get_iwyu_install_dir, get_iwyu_lock_path
from .base import BaseToolchainInstaller


class IWYUInstaller(BaseToolchainInstaller):
    """Installer for Include What You Use (IWYU) analyzer."""

    tool_name = "iwyu"
    binary_name = "include-what-you-use"

    def get_install_dir(self, platform: str, arch: str) -> Path:
        return get_iwyu_install_dir(platform, arch)

    def get_lock_path(self, platform: str, arch: str) -> Path:
        return get_iwyu_lock_path(platform, arch)

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        return fetch_iwyu_platform_manifest(platform, arch)


# Create singleton installer instance
_installer = IWYUInstaller()


# Module-level functions for backward compatibility
def is_iwyu_installed(platform: str, arch: str) -> bool:
    """
    Check if IWYU is already installed and hash matches current manifest.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    return _installer.is_installed(platform, arch)


def download_and_install_iwyu(platform: str, arch: str) -> None:
    """
    Download and install IWYU for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.download_and_install(platform, arch)


def _subprocess_install_iwyu(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """
    Install IWYU in a subprocess with proper process-level locking.

    Args:
        platform: Platform name
        arch: Architecture name

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    return _installer.subprocess_install(platform, arch)


def ensure_iwyu(platform: str, arch: str) -> None:
    """
    Ensure IWYU is installed for the given platform/arch.

    Uses subprocess-based installation with file locking to prevent concurrent downloads.
    InterProcessLock only works across processes, not threads, so we use subprocess.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.ensure(platform, arch)
