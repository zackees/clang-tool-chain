"""
Clang Extra Tools execution support.

Provides functionality for discovering and executing clang-extra tools
(clang-format, clang-tidy, clang-query) from their separate distribution.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from clang_tool_chain import downloader
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.platform.detection import get_platform_info

logger = logging.getLogger(__name__)


def get_clang_extra_binary_dir() -> Path:
    """
    Get the binary directory for clang-extra tools.

    Returns:
        Path to the clang-extra binary directory

    Raises:
        RuntimeError: If binary directory is not found
    """
    platform_name, arch = get_platform_info()
    logger.info(f"Getting clang-extra binary directory for {platform_name}/{arch}")

    downloader.ensure_clang_extra(platform_name, arch)

    install_dir = downloader.get_clang_extra_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"

    if not bin_dir.exists():
        raise RuntimeError(
            f"clang-extra binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"The download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    return bin_dir


def find_clang_extra_tool(tool_name: str) -> Path:
    """
    Find the path to a clang-extra tool.

    Args:
        tool_name: Name of the tool (e.g., "clang-query", "clang-tidy", "clang-format")

    Returns:
        Path to the tool

    Raises:
        RuntimeError: If the tool is not found
    """
    bin_dir = get_clang_extra_binary_dir()
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        tool_path = bin_dir / f"{tool_name}.exe"
    else:
        tool_path = bin_dir / tool_name

    if not tool_path.exists():
        available = [f.name for f in bin_dir.iterdir() if f.is_file()]
        raise RuntimeError(
            f"Tool '{tool_name}' not found at: {tool_path}\nAvailable tools in {bin_dir}:\n  {', '.join(available)}"
        )

    return tool_path


def execute_clang_extra_tool(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute a clang-extra tool with the given arguments.

    Args:
        tool_name: Name of the tool
        args: Command-line arguments (default: sys.argv[1:])
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_clang_extra_tool(tool_name)
    cmd = [str(tool_path)] + args

    logger.info(f"Executing clang-extra tool: {tool_path} (with {len(args)} args)")

    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Tool not found: {tool_path}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print(f"Error executing clang-extra tool: {e}", file=sys.stderr)
        sys.exit(1)
