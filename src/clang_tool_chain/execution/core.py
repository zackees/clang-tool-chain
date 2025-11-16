"""
Core tool execution functions for clang-tool-chain.

This module provides the fundamental execution infrastructure for running
LLVM/Clang tools with proper platform detection, SDK configuration, ABI setup,
and linker management.

The main functions are:
- execute_tool(): Execute a tool and exit with its return code (does not return)
- run_tool(): Execute a tool and return its exit code (returns to caller)
- sccache_clang_main(): sccache wrapper for clang with GNU ABI
- sccache_clang_cpp_main(): sccache wrapper for clang++ with GNU ABI
"""

import os
import subprocess
import sys
from typing import NoReturn

from ..abi import (
    _get_gnu_target_args,
    _get_msvc_target_args,
    _should_use_gnu_abi,
    _should_use_msvc_abi,
)
from ..linker import _add_lld_linker_if_needed
from ..logging_config import configure_logging
from ..platform.detection import get_platform_info
from ..platform.paths import find_sccache_binary, find_tool_binary
from ..sdk import _add_macos_sysroot_if_needed

# Configure logging using centralized configuration
logger = configure_logging(__name__)


def execute_tool(tool_name: str, args: list[str] | None = None, use_msvc: bool = False) -> NoReturn:
    """
    Execute a tool with the given arguments and exit with its return code.

    This function does not return - it replaces the current process with
    the tool process (on Unix) or exits with the tool's return code (on Windows).

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool (defaults to sys.argv[1:])
        use_msvc: If True on Windows, skip GNU ABI injection (use MSVC target)

    Raises:
        RuntimeError: If the tool cannot be found or executed

    Environment Variables:
        SDKROOT: Custom SDK path to use (macOS, standard macOS variable)
        CLANG_TOOL_CHAIN_NO_SYSROOT: Set to '1' to disable automatic -isysroot injection (macOS)
        CLANG_TOOL_CHAIN_USE_SYSTEM_LD: Set to '1' to use system linker instead of lld (macOS/Linux)
    """
    if args is None:
        args = sys.argv[1:]

    logger.info(f"Executing tool: {tool_name} with {len(args)} arguments")
    logger.debug(f"Arguments: {args}")

    try:
        tool_path = find_tool_binary(tool_name)
    except RuntimeError as e:
        logger.error(f"Failed to find tool binary: {e}")
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Add macOS SDK path automatically for clang/clang++ if not already specified
    platform_name, arch = get_platform_info()
    if platform_name == "darwin" and tool_name in ("clang", "clang++"):
        logger.debug("Checking if macOS sysroot needs to be added")
        args = _add_macos_sysroot_if_needed(args)

    # Force lld linker on macOS and Linux for cross-platform consistency
    if tool_name in ("clang", "clang++"):
        args = _add_lld_linker_if_needed(platform_name, args)

    # Add Windows GNU ABI target automatically for clang/clang++ if not MSVC variant
    if not use_msvc and tool_name in ("clang", "clang++") and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch, args)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with args: {gnu_args}")
        except Exception as e:
            # If GNU setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target for clang/clang++ when using MSVC variant
    if use_msvc and tool_name in ("clang", "clang++") and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with args: {msvc_args}")
        except Exception as e:
            # If MSVC setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Build command
    cmd = [str(tool_path)] + args
    logger.info(f"Executing command: {tool_path} (with {len(args)} args)")

    # On Unix systems, we can use exec to replace the current process
    # On Windows, we need to use subprocess and exit with the return code
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        logger.debug("Using Windows subprocess execution")
        # Windows: use subprocess
        try:
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except FileNotFoundError:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Tool not found: {tool_path}", file=sys.stderr)
            print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
            print("This may be a permission or compatibility issue.", file=sys.stderr)
            print("\nTroubleshooting:", file=sys.stderr)
            print("  - Verify the binary is compatible with your Windows version", file=sys.stderr)
            print("  - Check Windows Defender or antivirus isn't blocking it", file=sys.stderr)
            print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing tool: {e}", file=sys.stderr)
            print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
            print(f"Arguments: {args}", file=sys.stderr)
            print("\nPlease report this issue at:", file=sys.stderr)
            print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        logger.debug("Using Unix exec replacement")
        # Unix: use exec to replace current process
        try:
            logger.info(f"Replacing process with: {tool_path}")
            os.execv(str(tool_path), cmd)
        except FileNotFoundError:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Tool not found: {tool_path}", file=sys.stderr)
            print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
            print("This may be a permission or compatibility issue.", file=sys.stderr)
            print("\nTroubleshooting:", file=sys.stderr)
            print(f"  - Check file permissions: chmod +x {tool_path}", file=sys.stderr)
            print("  - Verify the binary is compatible with your system", file=sys.stderr)
            print("  - On macOS: Right-click > Open, then allow in Security settings", file=sys.stderr)
            print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing tool: {e}", file=sys.stderr)
            print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
            print(f"Arguments: {args}", file=sys.stderr)
            print("\nPlease report this issue at:", file=sys.stderr)
            print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)


def run_tool(tool_name: str, args: list[str] | None = None, use_msvc: bool = False) -> int:
    """
    Run a tool with the given arguments and return its exit code.

    Unlike execute_tool, this function returns to the caller with the
    tool's exit code instead of exiting the process.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool (defaults to sys.argv[1:])
        use_msvc: If True on Windows, skip GNU ABI injection (use MSVC target)

    Returns:
        Exit code from the tool

    Raises:
        RuntimeError: If the tool cannot be found

    Environment Variables:
        SDKROOT: Custom SDK path to use (macOS, standard macOS variable)
        CLANG_TOOL_CHAIN_NO_SYSROOT: Set to '1' to disable automatic -isysroot injection (macOS)
        CLANG_TOOL_CHAIN_USE_SYSTEM_LD: Set to '1' to use system linker instead of lld (macOS/Linux)
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_tool_binary(tool_name)

    # Add macOS SDK path automatically for clang/clang++ if not already specified
    platform_name, arch = get_platform_info()
    if platform_name == "darwin" and tool_name in ("clang", "clang++"):
        logger.debug("Checking if macOS sysroot needs to be added")
        args = _add_macos_sysroot_if_needed(args)

    # Force lld linker on macOS and Linux for cross-platform consistency
    if tool_name in ("clang", "clang++"):
        args = _add_lld_linker_if_needed(platform_name, args)

    # Add Windows GNU ABI target automatically for clang/clang++ if not MSVC variant
    if not use_msvc and tool_name in ("clang", "clang++") and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch, args)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with args: {gnu_args}")
        except Exception as e:
            # If GNU setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target for clang/clang++ when using MSVC variant
    if use_msvc and tool_name in ("clang", "clang++") and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with args: {msvc_args}")
        except Exception as e:
            # If MSVC setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Build command
    cmd = [str(tool_path)] + args

    # Run the tool
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError as err:
        raise RuntimeError(f"Tool not found: {tool_path}") from err
    except Exception as e:
        raise RuntimeError(f"Error executing tool: {e}") from e


# ============================================================================
# sccache wrapper functions
# ============================================================================


def sccache_clang_main(use_msvc: bool = False) -> NoReturn:
    """
    Entry point for sccache + clang wrapper.

    Args:
        use_msvc: If True on Windows, use MSVC ABI instead of GNU ABI
    """
    args = sys.argv[1:]

    try:
        sccache_path = find_sccache_binary()
        clang_path = find_tool_binary("clang")
    except RuntimeError as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Add macOS SDK path automatically if needed
    platform_name, arch = get_platform_info()
    if platform_name == "darwin":
        args = _add_macos_sysroot_if_needed(args)

    # Force lld linker on macOS and Linux for cross-platform consistency
    args = _add_lld_linker_if_needed(platform_name, args)

    # Add Windows GNU ABI target automatically (if not using MSVC variant)
    if not use_msvc and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch, args)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with sccache: {gnu_args}")
        except Exception as e:
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target when using MSVC variant
    if use_msvc and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with sccache: {msvc_args}")
        except Exception as e:
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Build command: sccache <clang_path> <args>
    cmd = [sccache_path, str(clang_path)] + args

    # Execute with platform-appropriate method
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        # Windows: use subprocess
        try:
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        # Unix: use exec to replace current process
        try:
            os.execv(sccache_path, cmd)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)


def sccache_clang_cpp_main(use_msvc: bool = False) -> NoReturn:
    """
    Entry point for sccache + clang++ wrapper.

    Args:
        use_msvc: If True on Windows, use MSVC ABI instead of GNU ABI
    """
    args = sys.argv[1:]

    try:
        sccache_path = find_sccache_binary()
        clang_cpp_path = find_tool_binary("clang++")
    except RuntimeError as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Add macOS SDK path automatically if needed
    platform_name, arch = get_platform_info()
    if platform_name == "darwin":
        args = _add_macos_sysroot_if_needed(args)

    # Force lld linker on macOS and Linux for cross-platform consistency
    args = _add_lld_linker_if_needed(platform_name, args)

    # Add Windows GNU ABI target automatically (if not using MSVC variant)
    if not use_msvc and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch, args)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with sccache: {gnu_args}")
        except Exception as e:
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target when using MSVC variant
    if use_msvc and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with sccache: {msvc_args}")
        except Exception as e:
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Build command: sccache <clang++_path> <args>
    cmd = [sccache_path, str(clang_cpp_path)] + args

    # Execute with platform-appropriate method
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        # Windows: use subprocess
        try:
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        # Unix: use exec to replace current process
        try:
            os.execv(sccache_path, cmd)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
