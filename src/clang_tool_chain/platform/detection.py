"""
Platform detection utilities for the Clang tool chain.

This module provides functions to detect the current platform and architecture,
and to locate platform-specific binary directories.
"""

import platform
import subprocess
from pathlib import Path

from clang_tool_chain import downloader
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging

# Configure logging using centralized configuration
logger = configure_logging(__name__)


def _get_toolchain_directory_listing(platform_name: str) -> str:
    """
    Get a directory listing of ~/.clang-tool-chain for debugging purposes.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")

    Returns:
        Formatted directory listing string (2 levels deep)
    """
    toolchain_dir = Path.home() / ".clang-tool-chain"

    try:
        if platform_name == "win":
            # On Windows, manually walk the directory tree (2 levels)
            lines = []
            if toolchain_dir.exists():
                lines.append(str(toolchain_dir))
                for item in toolchain_dir.iterdir():
                    lines.append(f"  {item.name}")
                    if item.is_dir():
                        try:
                            for subitem in item.iterdir():
                                lines.append(f"    {item.name}/{subitem.name}")
                        except (PermissionError, OSError):
                            pass
            return "\n".join(lines)
        else:
            # On Unix, use find
            result = subprocess.run(
                ["find", str(toolchain_dir), "-maxdepth", "2"], capture_output=True, text=True, timeout=5
            )
            return result.stdout
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        return f"Could not list directory: {e}"


def get_platform_info() -> tuple[str, str]:
    """
    Detect the current platform and architecture.

    Returns:
        Tuple of (platform, architecture) strings
        Platform: "win", "linux", or "darwin"
        Architecture: "x86_64" or "aarch64"
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    logger.debug(f"Detecting platform: system={system}, machine={machine}")

    # Normalize platform name
    if system == "windows":
        platform_name = "win"
    elif system == "linux":
        platform_name = "linux"
    elif system == "darwin":
        platform_name = "darwin"
    else:
        logger.error(f"Unsupported platform detected: {system}")
        raise RuntimeError(
            f"Unsupported platform: {system}\n"
            f"clang-tool-chain currently supports: Windows, Linux, and macOS (Darwin)\n"
            f"Your system: {system}\n"
            f"If you believe this platform should be supported, please report this at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    # Normalize architecture
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        logger.error(f"Unsupported architecture detected: {machine}")
        raise RuntimeError(
            f"Unsupported architecture: {machine}\n"
            f"clang-tool-chain currently supports: x86_64 (AMD64) and ARM64\n"
            f"Your architecture: {machine}\n"
            f"Supported architectures:\n"
            f"  - x86_64, amd64 (Intel/AMD 64-bit)\n"
            f"  - aarch64, arm64 (ARM 64-bit)\n"
            f"If you believe this architecture should be supported, please report this at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Platform detected: {platform_name}/{arch}")
    return platform_name, arch


def get_platform_binary_dir() -> Path:
    """
    Get the directory containing binaries for the current platform.

    This function ensures the toolchain is downloaded before returning the path.

    Returns:
        Path to the platform-specific binary directory

    Raises:
        RuntimeError: If the platform is not supported or binaries cannot be installed
    """
    logger.info("Getting platform binary directory")
    platform_name, arch = get_platform_info()

    # Ensure toolchain is downloaded and installed
    logger.info(f"Ensuring toolchain is available for {platform_name}/{arch}")
    downloader.ensure_toolchain(platform_name, arch)

    # Get the installation directory
    install_dir = downloader.get_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"
    logger.debug(f"Binary directory: {bin_dir}")

    if not bin_dir.exists():
        logger.error(f"Binary directory does not exist: {bin_dir}")
        # Get directory listing for debugging
        dir_listing = _get_toolchain_directory_listing(platform_name)

        raise RuntimeError(
            f"Binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"Directory structure of ~/.clang-tool-chain (2 levels deep):\n"
            f"{dir_listing}\n"
            f"\n"
            f"The toolchain download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Binary directory found: {bin_dir}")
    return bin_dir
