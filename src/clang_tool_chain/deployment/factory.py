"""
Factory for creating platform-specific library deployers.

This module provides a factory pattern for instantiating the appropriate
library deployer based on the target platform (Windows, Linux, macOS).
"""

import logging

from .base_deployer import BaseLibraryDeployer

logger = logging.getLogger(__name__)


class DeploymentFactory:
    """
    Factory for creating platform-specific library deployers.

    This factory handles instantiation of the appropriate deployer
    (DllDeployer, SoDeployer, or DylibDeployer) based on the platform name.

    Example usage:
        >>> from pathlib import Path
        >>> deployer = DeploymentFactory.create_deployer("linux", "x86_64")
        >>> if deployer:
        ...     deployer.deploy_all(Path("./program"))
    """

    @staticmethod
    def create_deployer(platform_name: str, arch: str = "x86_64") -> BaseLibraryDeployer | None:
        """
        Create platform-specific library deployer.

        Args:
            platform_name: Platform identifier ("windows", "linux", or "darwin")
            arch: Target architecture (default: "x86_64")
                  Options: "x86_64", "arm64", "aarch64", "i686", etc.

        Returns:
            Platform-specific deployer instance, or None if platform unsupported

        Example:
            >>> deployer = DeploymentFactory.create_deployer("windows", "x86_64")
            >>> type(deployer).__name__
            'DllDeployer'

            >>> deployer = DeploymentFactory.create_deployer("linux", "arm64")
            >>> type(deployer).__name__
            'SoDeployer'

            >>> deployer = DeploymentFactory.create_deployer("darwin", "x86_64")
            >>> type(deployer).__name__
            'DylibDeployer'

            >>> deployer = DeploymentFactory.create_deployer("freebsd", "x86_64")
            >>> deployer is None
            True
        """
        platform_lower = platform_name.lower().strip()

        if platform_lower == "windows" or platform_lower == "win32":
            from .dll_deployer import DllDeployer

            logger.debug(f"Creating DllDeployer for {platform_name}/{arch}")
            return DllDeployer(arch)

        elif platform_lower == "linux":
            from .so_deployer import SoDeployer

            logger.debug(f"Creating SoDeployer for {platform_name}/{arch}")
            return SoDeployer(arch)

        elif platform_lower == "darwin" or platform_lower == "macos":
            from .dylib_deployer import DylibDeployer

            logger.debug(f"Creating DylibDeployer for {platform_name}/{arch}")
            return DylibDeployer(arch)

        else:
            logger.warning(f"Unsupported platform for library deployment: {platform_name}")
            return None

    @staticmethod
    def create_deployer_for_current_platform(arch: str = "x86_64") -> BaseLibraryDeployer | None:
        """
        Create deployer for the current runtime platform.

        This convenience method automatically detects the current platform
        using sys.platform and creates the appropriate deployer.

        Args:
            arch: Target architecture (default: "x86_64")

        Returns:
            Platform-specific deployer instance for current platform,
            or None if platform unsupported

        Example:
            >>> import sys
            >>> deployer = DeploymentFactory.create_deployer_for_current_platform()
            >>> if sys.platform == "linux":
            ...     assert type(deployer).__name__ == "SoDeployer"
            >>> elif sys.platform == "win32":
            ...     assert type(deployer).__name__ == "DllDeployer"
            >>> elif sys.platform == "darwin":
            ...     assert type(deployer).__name__ == "DylibDeployer"
        """
        import sys

        platform_map = {"win32": "windows", "linux": "linux", "darwin": "darwin"}

        current_platform = platform_map.get(sys.platform)

        if current_platform:
            logger.debug(f"Detected current platform: {sys.platform} -> {current_platform}")
            return DeploymentFactory.create_deployer(current_platform, arch)
        else:
            logger.warning(f"Current platform not supported for library deployment: {sys.platform}")
            return None

    @staticmethod
    def get_supported_platforms() -> list[str]:
        """
        Get list of supported platform names.

        Returns:
            List of platform identifiers that have deployer implementations

        Example:
            >>> platforms = DeploymentFactory.get_supported_platforms()
            >>> sorted(platforms)
            ['darwin', 'linux', 'windows']
        """
        return ["windows", "linux", "darwin"]

    @staticmethod
    def is_platform_supported(platform_name: str) -> bool:
        """
        Check if a platform has library deployment support.

        Args:
            platform_name: Platform identifier to check

        Returns:
            True if platform is supported, False otherwise

        Example:
            >>> DeploymentFactory.is_platform_supported("linux")
            True
            >>> DeploymentFactory.is_platform_supported("freebsd")
            False
        """
        platform_lower = platform_name.lower().strip()
        return platform_lower in ["windows", "win32", "linux", "darwin", "macos"]


def create_deployer(platform_name: str, arch: str = "x86_64") -> BaseLibraryDeployer | None:
    """
    Convenience function for creating platform-specific deployers.

    This is a module-level wrapper around DeploymentFactory.create_deployer()
    for backwards compatibility and easier imports.

    Args:
        platform_name: Platform identifier ("windows", "linux", or "darwin")
        arch: Target architecture (default: "x86_64")

    Returns:
        Platform-specific deployer instance, or None if unsupported

    Example:
        >>> from pathlib import Path
        >>> from clang_tool_chain.deployment.factory import create_deployer
        >>> deployer = create_deployer("linux", "arm64")
        >>> if deployer:
        ...     deployer.deploy_all(Path("./program"))
    """
    return DeploymentFactory.create_deployer(platform_name, arch)
