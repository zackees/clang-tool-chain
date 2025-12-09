"""
IWYU (Include What You Use) execution support.

This module provides functionality for discovering and executing IWYU tools,
including the main include-what-you-use binary and associated Python scripts
like iwyu_tool.py.
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


def get_iwyu_binary_dir() -> Path:
    """
    Get the binary directory for IWYU.

    Returns:
        Path to the IWYU binary directory

    Raises:
        RuntimeError: If binary directory is not found
    """
    platform_name, arch = get_platform_info()
    logger.info(f"Getting IWYU binary directory for {platform_name}/{arch}")

    # Ensure IWYU is downloaded and installed
    logger.info(f"Ensuring IWYU is available for {platform_name}/{arch}")
    downloader.ensure_iwyu(platform_name, arch)

    # Get the installation directory
    install_dir = downloader.get_iwyu_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"
    logger.debug(f"IWYU binary directory: {bin_dir}")

    if not bin_dir.exists():
        logger.error(f"IWYU binary directory does not exist: {bin_dir}")
        raise RuntimeError(
            f"IWYU binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"The IWYU download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"IWYU binary directory found: {bin_dir}")
    return bin_dir


def find_iwyu_tool(tool_name: str) -> Path:
    """
    Find the path to an IWYU tool.

    Args:
        tool_name: Name of the tool (e.g., "include-what-you-use", "iwyu_tool.py")

    Returns:
        Path to the tool

    Raises:
        RuntimeError: If the tool is not found
    """
    logger.info(f"Finding IWYU tool: {tool_name}")
    bin_dir = get_iwyu_binary_dir()
    platform_name, _ = get_platform_info()

    # Add .exe extension on Windows for the binary
    if tool_name == "include-what-you-use" and platform_name == "win":
        tool_path = bin_dir / f"{tool_name}.exe"
    else:
        tool_path = bin_dir / tool_name

    logger.debug(f"Looking for IWYU tool at: {tool_path}")

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
        logger.error(f"IWYU tool not found: {tool_path}")
        # List available tools
        available_tools = [f.name for f in bin_dir.iterdir() if f.is_file()]
        raise RuntimeError(
            f"IWYU tool '{tool_name}' not found at: {tool_path}\n"
            f"Available tools in {bin_dir}:\n"
            f"  {', '.join(available_tools)}"
        )

    logger.info(f"Found IWYU tool: {tool_path}")
    return tool_path


def execute_iwyu_tool(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute an IWYU tool with the given arguments.

    Args:
        tool_name: Name of the IWYU tool
        args: Command-line arguments (default: sys.argv[1:])

    Raises:
        SystemExit: Always exits with the tool's return code
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_iwyu_tool(tool_name)
    platform_name, _ = get_platform_info()

    # For Python scripts, we need to run them with Python
    if tool_name.endswith(".py"):
        # Find Python executable
        python_exe = sys.executable
        cmd = [python_exe, str(tool_path)] + args
    else:
        cmd = [str(tool_path)] + args

    logger.info(f"Executing IWYU tool: {' '.join(cmd)}")

    # Execute tool
    if platform_name == "win":
        # Windows: use subprocess with modified PATH to find DLLs
        try:
            # Add IWYU bin directory to PATH so DLLs can be found
            bin_dir = get_iwyu_binary_dir()
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

            result = subprocess.run(cmd, env=env)
            sys.exit(result.returncode)
        except FileNotFoundError as err:
            raise RuntimeError(f"IWYU tool not found: {tool_path}") from err
        except Exception as e:
            raise RuntimeError(f"Error executing IWYU tool: {e}") from e
    else:
        # Unix: use exec to replace current process
        # On Linux, we need to set LD_LIBRARY_PATH to find shared libraries
        try:
            # Get the IWYU installation directory
            install_dir = downloader.get_iwyu_install_dir(platform_name, get_platform_info()[1])
            lib_dir = install_dir / "lib"

            # Check if lib directory exists (it should for Linux with bundled .so files)
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

            if tool_name.endswith(".py"):
                # For Python scripts, we can't use execv directly
                result = subprocess.run(cmd, env=env)
                sys.exit(result.returncode)
            else:
                # For native binaries, use execve to pass environment
                if env:
                    os.execve(cmd[0], cmd, env)
                else:
                    os.execv(cmd[0], cmd)
        except FileNotFoundError as err:
            raise RuntimeError(f"IWYU tool not found: {tool_path}") from err
        except Exception as e:
            raise RuntimeError(f"Error executing IWYU tool: {e}") from e
