"""
IWYU (Include What You Use) installer module.
"""

from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.manifest import Manifest, fetch_iwyu_platform_manifest


class IWYUInstaller(BaseToolchainInstaller):
    """Installer for Include What You Use (IWYU) analyzer."""

    tool_name = "iwyu"
    binary_name = "include-what-you-use"

    # Use default get_install_dir() and get_lock_path() from base class

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
