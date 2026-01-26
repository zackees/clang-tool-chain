"""
Path utilities for locating toolchain binaries and directories.

This module provides functions for finding tool binaries, Node.js installation
paths, and other path-related utilities for the Clang tool chain.
"""

import os
import shutil
from pathlib import Path

from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.platform.detection import (
    _get_toolchain_directory_listing,
    get_platform_binary_dir,
    get_platform_info,
)

# Configure logging using centralized configuration
logger = configure_logging(__name__)


def get_nodejs_install_dir_path(platform_name: str, arch: str) -> Path:
    """
    Get the installation directory path for Node.js.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        arch: Architecture ("x86_64", "arm64")

    Returns:
        Path to Node.js installation directory
    """
    return Path.home() / ".clang-tool-chain" / "nodejs" / platform_name / arch


def get_node_binary_name(platform_name: str) -> str:
    """
    Get the Node.js binary name for the given platform.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")

    Returns:
        Binary name ("node.exe" for Windows, "node" for Unix)
    """
    return "node.exe" if platform_name == "win" else "node"


def get_assets_dir() -> Path:
    """
    Get the path to the assets directory containing LLVM binaries.

    Returns:
        Path to the assets directory
    """
    # Get the package directory
    package_dir = Path(__file__).parent.parent

    # Assets should be in the project root (two levels up from package)
    project_root = package_dir.parent
    assets_dir = project_root / "assets"

    return assets_dir


def find_tool_binary(tool_name: str) -> Path:
    """
    Find the path to a specific tool binary.

    Args:
        tool_name: Name of the tool (e.g., "clang", "llvm-ar")

    Returns:
        Path to the tool binary

    Raises:
        RuntimeError: If the tool binary is not found
    """
    logger.info(f"Finding binary for tool: {tool_name}")
    bin_dir = get_platform_binary_dir()
    platform_name, _ = get_platform_info()

    # Add .exe extension on Windows
    tool_path = bin_dir / f"{tool_name}.exe" if platform_name == "win" else bin_dir / tool_name
    logger.debug(f"Looking for tool at: {tool_path}")

    # Check if tool exists with retry for Windows file system issues
    tool_exists = tool_path.exists()
    if not tool_exists and platform_name == "win":
        # On Windows, Path.exists() can sometimes return False due to file system
        # caching or hardlink issues, especially during parallel test execution.
        # Retry with a small delay and also check with os.path.exists()
        import time

        time.sleep(0.01)  # 10ms delay
        tool_exists = tool_path.exists() or os.path.exists(str(tool_path))

    if not tool_exists:
        logger.warning(f"Tool not found at primary location: {tool_path}")
        # Try alternative names for some tools
        alternatives = {
            "lld": ["lld-link", "ld.lld", "ld64.lld"],
            "clang": ["clang++", "clang-cpp"],
            "lld-link": ["lld", "ld.lld"],
            "ld.lld": ["lld", "lld-link"],
            "ld64.lld": ["lld", "ld.lld"],  # macOS Mach-O linker variant
        }

        if tool_name in alternatives:
            logger.debug(f"Trying alternative names for {tool_name}: {alternatives[tool_name]}")
            for alt_name in alternatives[tool_name]:
                alt_path = bin_dir / f"{alt_name}.exe" if platform_name == "win" else bin_dir / alt_name
                logger.debug(f"Checking alternative: {alt_path}")

                if alt_path.exists():
                    logger.info(f"Found alternative tool at: {alt_path}")
                    return alt_path

        # List available tools
        available_tools = [f.stem for f in bin_dir.iterdir() if f.is_file()]
        logger.error(f"Tool '{tool_name}' not found. Available tools: {', '.join(sorted(available_tools)[:20])}")

        # Get directory listing for debugging
        dir_listing = _get_toolchain_directory_listing(platform_name)

        raise RuntimeError(
            f"Tool '{tool_name}' not found\n"
            f"Expected location: {tool_path}\n"
            f"\n"
            f"This tool may not be included in your LLVM installation.\n"
            f"\n"
            f"Available tools in {bin_dir.name}/:\n"
            f"  {', '.join(sorted(available_tools)[:20])}\n"
            f"  {'... and more' if len(available_tools) > 20 else ''}\n"
            f"\n"
            f"Directory structure of ~/.clang-tool-chain (2 levels deep):\n"
            f"{dir_listing}\n"
            f"\n"
            f"Troubleshooting:\n"
            f"  - Verify the tool name is correct\n"
            f"  - Check if the tool is part of LLVM {tool_name}\n"
            f"  - Re-download binaries: python scripts/download_binaries.py\n"
            f"  - Report issue: https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Tool binary found: {tool_path}")
    return tool_path


def find_sccache_binary() -> str:
    """
    Find the sccache binary in PATH.

    Returns:
        Path to the sccache binary

    Raises:
        RuntimeError: If sccache is not found in PATH
    """
    sccache_path = shutil.which("sccache")

    if sccache_path is None:
        raise RuntimeError(
            "sccache not found in PATH\n"
            "\n"
            "sccache is required to use the sccache wrapper commands.\n"
            "\n"
            "Installation options:\n"
            "  - pip install clang-tool-chain[sccache]\n"
            "  - cargo install sccache\n"
            "  - Download from: https://github.com/mozilla/sccache/releases\n"
            "  - Linux: apt install sccache / yum install sccache\n"
            "  - macOS: brew install sccache\n"
            "\n"
            "After installation, ensure sccache is in your PATH.\n"
            "Verify with: sccache --version"
        )

    return sccache_path
