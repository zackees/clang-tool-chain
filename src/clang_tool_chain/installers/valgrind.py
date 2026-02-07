"""
Valgrind installer module.

Valgrind is a Linux-only memory analysis tool. It is downloaded as a
pre-built archive and runs inside a Docker container to ensure
compatibility across host platforms.
"""

from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.manifest import Manifest, fetch_valgrind_platform_manifest


class ValgrindInstaller(BaseToolchainInstaller):
    """Installer for Valgrind memory analysis tool."""

    tool_name = "valgrind"
    binary_name = "valgrind"

    # Use default get_install_dir() and get_lock_path() from base class

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        return fetch_valgrind_platform_manifest(platform, arch)


# Create singleton installer instance
_installer = ValgrindInstaller()


# Module-level functions for backward compatibility
def is_valgrind_installed(platform: str, arch: str) -> bool:
    """
    Check if Valgrind is already installed and hash matches current manifest.

    Args:
        platform: Platform name (must be "linux")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    return _installer.is_installed(platform, arch)


def download_and_install_valgrind(platform: str, arch: str) -> None:
    """
    Download and install Valgrind for the given platform/arch.

    Args:
        platform: Platform name (must be "linux")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.download_and_install(platform, arch)


def _subprocess_install_valgrind(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """
    Install Valgrind in a subprocess with proper process-level locking.

    Args:
        platform: Platform name
        arch: Architecture name

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    return _installer.subprocess_install(platform, arch)


def ensure_valgrind(platform: str, arch: str) -> None:
    """
    Ensure Valgrind is installed for the given platform/arch.

    Uses subprocess-based installation with file locking to prevent concurrent downloads.
    InterProcessLock only works across processes, not threads, so we use subprocess.

    Args:
        platform: Platform name (must be "linux")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.ensure(platform, arch)
