"""
LLDB debugger installer module.
"""

from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.manifest import Manifest, fetch_lldb_platform_manifest


class LLDBInstaller(BaseToolchainInstaller):
    """Installer for LLDB debugger."""

    tool_name = "lldb"
    binary_name = "lldb"

    # Use default get_install_dir() and get_lock_path() from base class

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        return fetch_lldb_platform_manifest(platform, arch)


# Create singleton installer instance
_installer = LLDBInstaller()


# Module-level functions for backward compatibility
def is_lldb_installed(platform: str, arch: str) -> bool:
    """
    Check if LLDB is already installed and hash matches current manifest.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    return _installer.is_installed(platform, arch)


def download_and_install_lldb(platform: str, arch: str) -> None:
    """
    Download and install LLDB for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.download_and_install(platform, arch)


def _subprocess_install_lldb(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """
    Install LLDB in a subprocess with proper process-level locking.

    Args:
        platform: Platform name
        arch: Architecture name

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    return _installer.subprocess_install(platform, arch)


def ensure_lldb(platform: str, arch: str) -> None:
    """
    Ensure LLDB is installed for the given platform/arch.

    Uses subprocess-based installation with file locking to prevent concurrent downloads.
    InterProcessLock only works across processes, not threads, so we use subprocess.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.ensure(platform, arch)
