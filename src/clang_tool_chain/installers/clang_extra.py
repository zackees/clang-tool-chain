"""
Clang Extra Tools installer module.

Handles installation of clang-format, clang-tidy, and clang-query
as a separate distribution from the main Clang/LLVM toolchain.
"""

from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.manifest import Manifest, fetch_clang_extra_platform_manifest


class ClangExtraInstaller(BaseToolchainInstaller):
    """Installer for Clang Extra Tools (clang-format, clang-tidy, clang-query)."""

    tool_name = "clang_extra"
    binary_name = "clang-query"

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        return fetch_clang_extra_platform_manifest(platform, arch)


# Create singleton installer instance
_installer = ClangExtraInstaller()


# Module-level functions for backward compatibility
def is_clang_extra_installed(platform: str, arch: str) -> bool:
    """Check if clang-extra tools are installed and hash matches current manifest."""
    return _installer.is_installed(platform, arch)


def download_and_install_clang_extra(platform: str, arch: str) -> None:
    """Download and install clang-extra tools for the given platform/arch."""
    return _installer.download_and_install(platform, arch)


def _subprocess_install_clang_extra(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """Install clang-extra in a subprocess with proper process-level locking."""
    return _installer.subprocess_install(platform, arch)


def ensure_clang_extra(platform: str, arch: str) -> None:
    """Ensure clang-extra tools are installed for the given platform/arch."""
    return _installer.ensure(platform, arch)
