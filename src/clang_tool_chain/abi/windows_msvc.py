"""
Windows MSVC ABI configuration and target arguments.

This module provides functionality for configuring compilation with MSVC ABI
on Windows. MSVC ABI is explicitly requested via the *-msvc variant commands
and requires Windows SDK to be installed.
"""

import logging

from clang_tool_chain.sdk.windows import _detect_windows_sdk, _print_msvc_sdk_warning

logger = logging.getLogger(__name__)


def _should_use_msvc_abi(platform_name: str, args: list[str]) -> bool:  # pyright: ignore[reportUnusedFunction]
    """
    Determine if MSVC ABI should be used based on platform and arguments.

    MSVC ABI is explicitly requested via the *-msvc variant commands.
    Unlike GNU ABI (which is the Windows default), MSVC ABI is opt-in.

    This function checks if the user has explicitly provided a --target flag.
    If so, we respect the user's choice and don't inject MSVC target.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Command-line arguments

    Returns:
        True if MSVC ABI should be used (Windows + no explicit target), False otherwise
    """
    # MSVC ABI only applies to Windows
    if platform_name != "win":
        logger.debug("Not Windows platform, MSVC ABI not applicable")
        return False

    # Check if user explicitly specified target
    args_str = " ".join(args)
    if "--target=" in args_str or "--target " in args_str:
        # User specified target explicitly, don't override
        logger.debug("User specified explicit target, skipping MSVC ABI injection")
        return False

    # MSVC variant was requested and no user override
    logger.debug("MSVC ABI will be used (no user target override)")
    return True


def _get_msvc_target_args(platform_name: str, arch: str) -> list[str]:  # pyright: ignore[reportUnusedFunction]
    """
    Get MSVC ABI target arguments for Windows.

    This function returns the necessary compiler arguments to use MSVC ABI
    instead of GNU ABI. It also detects Windows SDK availability and shows
    helpful warnings if the SDK is not found in environment variables.

    Args:
        platform_name: Platform name
        arch: Architecture

    Returns:
        List of additional compiler arguments for MSVC ABI (just --target)

    Note:
        Unlike GNU ABI which requires downloading a MinGW sysroot, MSVC ABI
        relies on the system's Visual Studio or Windows SDK installation.
        We detect SDK presence via environment variables and warn if not found,
        but still return the target triple and let clang attempt its own SDK detection.
    """
    if platform_name != "win":
        return []

    logger.info(f"Setting up MSVC ABI for Windows {arch}")

    # Detect Windows SDK and warn if not found
    sdk_info = _detect_windows_sdk()
    if sdk_info.is_detected():
        logger.info("Windows SDK detected")
    else:
        logger.warning("Windows SDK not detected in environment variables")
        # Show helpful warning about SDK requirements
        _print_msvc_sdk_warning()

    # Determine target triple for MSVC ABI
    if arch == "x86_64":
        target = "x86_64-pc-windows-msvc"
    elif arch == "arm64":
        target = "aarch64-pc-windows-msvc"
    else:
        raise ValueError(f"Unsupported architecture for MSVC: {arch}")

    logger.info(f"Using MSVC target: {target}")

    # Return just the target triple
    # Clang will automatically:
    # - Select lld-link as the linker (MSVC-compatible)
    # - Use MSVC name mangling for C++
    # - Attempt to find Windows SDK via its own detection logic
    return [f"--target={target}"]
