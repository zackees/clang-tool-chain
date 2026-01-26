"""
Unified sccache wrapper for clang/clang++ compilation with caching.

This module provides a single implementation for running clang or clang++
through sccache, eliminating the duplication between sccache_clang_main()
and sccache_clang_cpp_main().
"""

import os
import sys
from pathlib import Path
from typing import Literal, NoReturn

from clang_tool_chain.abi import _get_gnu_target_args, _get_msvc_target_args, _should_use_gnu_abi, _should_use_msvc_abi
from clang_tool_chain.execution.platform_executor import ExecutionContext, get_platform_executor
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.linker import _add_lld_linker_if_needed
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.platform.detection import get_platform_info
from clang_tool_chain.platform.paths import find_sccache_binary, find_tool_binary
from clang_tool_chain.sdk import _add_macos_sysroot_if_needed

logger = configure_logging(__name__)


def _extract_deploy_dependencies_flag(args: list[str]) -> tuple[list[str], bool]:
    """
    Extract --deploy-dependencies flag from arguments.

    Args:
        args: Compiler/linker arguments

    Returns:
        Tuple of (filtered_args, should_deploy)
    """
    if "--deploy-dependencies" in args:
        filtered = [arg for arg in args if arg != "--deploy-dependencies"]
        return (filtered, True)
    return (args, False)


def execute_with_sccache(compiler: Literal["clang", "clang++"], use_msvc: bool = False) -> NoReturn:
    """
    Execute clang or clang++ through sccache with proper ABI and platform setup.

    This function unifies the logic for both clang and clang++, eliminating
    the duplication between sccache_clang_main() and sccache_clang_cpp_main().

    Args:
        compiler: Compiler to use ("clang" or "clang++")
        use_msvc: If True on Windows, use MSVC ABI instead of GNU ABI

    Environment Variables:
        SCCACHE_IDLE_TIMEOUT: Set to 5 seconds to minimize file locking window
    """
    # Set sccache idle timeout to 5 seconds to minimize file locking window
    # This prevents sccache daemon from holding .venv/Scripts/sccache.exe locked
    # for extended periods, which blocks pip/uv package updates
    if "SCCACHE_IDLE_TIMEOUT" not in os.environ:
        os.environ["SCCACHE_IDLE_TIMEOUT"] = "5"

    args = sys.argv[1:]

    # Extract --deploy-dependencies flag (must be stripped before passing to clang)
    args, deploy_dependencies_requested = _extract_deploy_dependencies_flag(args)

    # Find sccache and compiler binaries
    try:
        sccache_path = find_sccache_binary()
        compiler_path = find_tool_binary(compiler)
    except RuntimeError as e:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Platform-specific argument transformations
    platform_name, arch = get_platform_info()

    # Add macOS SDK path automatically if needed
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
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
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
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Build command: sccache <compiler_path> <args>
    # Note: We use the sccache binary as tool_path, but pass compiler as the first arg
    sccache_args = [str(compiler_path)] + args

    # Create execution context
    ctx = ExecutionContext(
        tool_path=Path(sccache_path),
        args=sccache_args,
        platform_name=platform_name,
        arch=arch,
        tool_name=compiler,
        use_msvc=use_msvc,
        deploy_dependencies=deploy_dependencies_requested,
    )

    # Execute with platform-appropriate executor
    executor = get_platform_executor(platform_name)
    executor.execute(ctx)
