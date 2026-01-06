"""
LLDB (LLVM Debugger) execution support.

This module provides functionality for discovering and executing LLDB debugger tools,
including the main lldb binary and associated helpers like lldb-server and lldb-argdumper.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from .. import downloader

# Configure logging
logger = logging.getLogger(__name__)


def get_platform_info() -> tuple[str, str]:
    """
    Detect the current platform and architecture.

    Returns:
        Tuple of (platform, architecture) strings
        Platform: "win", "linux", or "darwin"
        Architecture: "x86_64" or "arm64"
    """
    import platform

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


def get_lldb_binary_dir() -> Path:
    """
    Get the binary directory for LLDB.

    Returns:
        Path to the LLDB binary directory

    Raises:
        RuntimeError: If binary directory is not found
    """
    platform_name, arch = get_platform_info()
    logger.info(f"Getting LLDB binary directory for {platform_name}/{arch}")

    # Ensure LLDB is downloaded and installed
    logger.info(f"Ensuring LLDB is available for {platform_name}/{arch}")
    downloader.ensure_lldb(platform_name, arch)

    # Get the installation directory
    install_dir = downloader.get_lldb_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"
    logger.debug(f"LLDB binary directory: {bin_dir}")

    if not bin_dir.exists():
        logger.error(f"LLDB binary directory does not exist: {bin_dir}")
        raise RuntimeError(
            f"LLDB binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"The LLDB download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"LLDB binary directory found: {bin_dir}")
    return bin_dir


def find_lldb_tool(tool_name: str) -> Path:
    """
    Find the path to an LLDB tool.

    Args:
        tool_name: Name of the tool (e.g., "lldb", "lldb-server", "lldb-argdumper")

    Returns:
        Path to the tool

    Raises:
        RuntimeError: If the tool is not found
    """
    logger.info(f"Finding LLDB tool: {tool_name}")
    bin_dir = get_lldb_binary_dir()
    platform_name, _ = get_platform_info()

    # Add .exe extension on Windows for the binary
    if platform_name == "win":
        tool_path = bin_dir / f"{tool_name}.exe"
    else:
        tool_path = bin_dir / tool_name

    logger.debug(f"Looking for LLDB tool at: {tool_path}")

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
        logger.error(f"LLDB tool not found: {tool_path}")
        # List available tools
        available_tools = [f.name for f in bin_dir.iterdir() if f.is_file()]
        raise RuntimeError(
            f"LLDB tool '{tool_name}' not found at: {tool_path}\n"
            f"Available tools in {bin_dir}:\n"
            f"  {', '.join(available_tools)}"
        )

    logger.info(f"Found LLDB tool: {tool_path}")
    return tool_path


def execute_lldb_tool(
    tool_name: str, args: list[str] | None = None, print_mode: bool = False
) -> NoReturn | int:
    """
    Execute an LLDB tool with the given arguments.

    Args:
        tool_name: Name of the LLDB tool
        args: Command-line arguments (default: sys.argv[1:])
        print_mode: If True, run in automated crash analysis mode and return exit code

    Returns:
        Exit code if print_mode is True

    Raises:
        SystemExit: Exits with the tool's return code if not in print_mode
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_lldb_tool(tool_name)
    platform_name, _ = get_platform_info()

    cmd = [str(tool_path)] + args

    logger.info(f"Executing LLDB tool: {' '.join(cmd)}")

    # Execute tool
    if platform_name == "win":
        # Windows: use subprocess with modified PATH to find DLLs
        try:
            # Add LLDB bin directory to PATH so DLLs can be found
            bin_dir = get_lldb_binary_dir()
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            # Disable Python to avoid initialization errors when Python site-packages aren't available
            env["LLDB_DISABLE_PYTHON"] = "1"

            result = subprocess.run(cmd, env=env)

            if print_mode:
                return result.returncode
            sys.exit(result.returncode)
        except FileNotFoundError as err:
            raise RuntimeError(f"LLDB tool not found: {tool_path}") from err
        except Exception as e:
            raise RuntimeError(f"Error executing LLDB tool: {e}") from e
    else:
        # Unix: use subprocess for consistency (execv doesn't allow returning)
        try:
            # Get the LLDB installation directory
            install_dir = downloader.get_lldb_install_dir(platform_name, get_platform_info()[1])
            lib_dir = install_dir / "lib"

            # Check if lib directory exists
            if lib_dir.exists():
                logger.debug(f"Adding {lib_dir} to LD_LIBRARY_PATH")
                env = os.environ.copy()
                # Prepend lib directory to LD_LIBRARY_PATH
                existing_ld_path = env.get("LD_LIBRARY_PATH", "")
                if existing_ld_path:
                    env["LD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{existing_ld_path}"
                else:
                    env["LD_LIBRARY_PATH"] = str(lib_dir)
            else:
                logger.debug(f"No lib directory found at {lib_dir}, using system libraries")
                env = None

            result = subprocess.run(cmd, env=env)

            if print_mode:
                return result.returncode
            sys.exit(result.returncode)
        except FileNotFoundError as err:
            raise RuntimeError(f"LLDB tool not found: {tool_path}") from err
        except Exception as e:
            raise RuntimeError(f"Error executing LLDB tool: {e}") from e
