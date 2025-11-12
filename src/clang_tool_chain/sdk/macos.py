"""
macOS SDK detection and warning utilities.

This module provides functions for detecting macOS SDK installations
and displaying helpful error messages when the SDK is not found.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _print_macos_sdk_error(reason: str) -> None:
    """
    Print a helpful error message to stderr when macOS SDK detection fails.

    This is called when compilation is about to proceed without SDK detection,
    which will likely cause 'stdio.h' or 'iostream' not found errors.

    Args:
        reason: Brief description of why SDK detection failed
    """
    print("\n" + "=" * 70, file=sys.stderr)
    print("⚠️  macOS SDK Detection Failed", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"\nReason: {reason}", file=sys.stderr)
    print("\nYour compilation may fail with errors like:", file=sys.stderr)
    print("  fatal error: 'stdio.h' file not found", file=sys.stderr)
    print("  fatal error: 'iostream' file not found", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Solution: Install Xcode Command Line Tools", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\nRun this command in your terminal:", file=sys.stderr)
    print("\n  \033[1;36mxcode-select --install\033[0m", file=sys.stderr)
    print("\nThen try compiling again.", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Alternative Solutions:", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\n1. Specify SDK path manually:", file=sys.stderr)
    print("   clang-tool-chain-c -isysroot /Library/Developer/.../MacOSX.sdk file.c", file=sys.stderr)
    print("\n2. Set SDKROOT environment variable:", file=sys.stderr)
    print("   export SDKROOT=$(xcrun --show-sdk-path)  # if xcrun works", file=sys.stderr)
    print("\n3. Use freestanding compilation (no standard library):", file=sys.stderr)
    print("   clang-tool-chain-c -ffreestanding -nostdlib file.c", file=sys.stderr)
    print("\n4. Disable automatic SDK detection:", file=sys.stderr)
    print("   export CLANG_TOOL_CHAIN_NO_SYSROOT=1", file=sys.stderr)
    print("   # Then specify SDK manually with -isysroot", file=sys.stderr)
    print("\n" + "=" * 70, file=sys.stderr)
    print("More info: https://github.com/zackees/clang-tool-chain#macos-sdk-detection-automatic", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)


def _add_macos_sysroot_if_needed(args: list[str]) -> list[str]:  # pyright: ignore[reportUnusedFunction]
    """
    Add -isysroot flag for macOS if needed to find system headers.

    On macOS, system headers (like stdio.h, iostream) are NOT in /usr/include.
    Instead, they're only available in SDK bundles provided by Xcode or Command Line Tools.
    Standalone clang binaries cannot automatically find these headers without help.

    This function implements LLVM's official three-tier SDK detection strategy
    (see LLVM patch D136315: https://reviews.llvm.org/D136315):
    1. Explicit -isysroot flag (user override)
    2. SDKROOT environment variable (Xcode/xcrun standard)
    3. Automatic xcrun --show-sdk-path (fallback detection)

    The function automatically detects the macOS SDK path and adds it to
    the compiler arguments, unless:
    - User has disabled it via CLANG_TOOL_CHAIN_NO_SYSROOT=1
    - User has already specified -isysroot in the arguments
    - SDKROOT environment variable is set (will be used by clang automatically)
    - User specified flags indicating freestanding/no stdlib compilation:
      -nostdinc, -nostdinc++, -nostdlib, -ffreestanding

    Args:
        args: Original compiler arguments

    Returns:
        Modified arguments with -isysroot prepended if needed

    References:
        - LLVM D136315: Try to guess SDK root with xcrun when unspecified
        - Apple no longer ships headers in /usr/include since macOS 10.14 Mojave
    """
    # Check if user wants to disable automatic sysroot
    from ..settings_warnings import warn_no_sysroot

    if warn_no_sysroot():
        return args

    # Check if SDKROOT is already set (standard macOS environment variable)
    if "SDKROOT" in os.environ:
        return args

    # Check if user already specified -isysroot
    if "-isysroot" in args:
        return args

    # Check for flags that indicate freestanding or no-stdlib compilation
    # In these cases, the user explicitly doesn't want system headers/libraries
    no_sysroot_flags = {"-nostdinc", "-nostdinc++", "-nostdlib", "-ffreestanding"}
    if any(flag in args for flag in no_sysroot_flags):
        return args

    # Try to detect the SDK path using xcrun
    try:
        result = subprocess.run(
            ["xcrun", "--show-sdk-path"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sdk_path = result.stdout.strip()

        if sdk_path and Path(sdk_path).exists():
            # Prepend -isysroot to arguments
            logger.info(f"macOS SDK detected: {sdk_path}")
            return ["-isysroot", sdk_path] + args
        else:
            # xcrun succeeded but returned invalid path
            logger.warning(f"xcrun returned invalid SDK path: {sdk_path}")
            _print_macos_sdk_error("xcrun returned invalid SDK path")
            return args

    except FileNotFoundError:
        # xcrun command not found - Command Line Tools likely not installed
        logger.error("xcrun command not found - Xcode Command Line Tools may not be installed")
        _print_macos_sdk_error("xcrun command not found")
        return args

    except subprocess.CalledProcessError as e:
        # xcrun failed with non-zero exit code
        stderr_output = e.stderr.strip() if e.stderr else "No error output"
        logger.error(f"xcrun failed: {stderr_output}")
        _print_macos_sdk_error(f"xcrun failed: {stderr_output}")
        return args

    except subprocess.TimeoutExpired:
        # xcrun took too long to respond
        logger.warning("xcrun command timed out")
        return args

    except Exception as e:
        # Unexpected error
        logger.warning(f"Unexpected error detecting SDK: {e}")
        return args
