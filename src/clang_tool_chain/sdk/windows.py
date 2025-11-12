"""
Windows SDK detection and warning utilities.

This module provides functions for detecting Windows SDK installations
and displaying helpful warnings when the SDK is not found for MSVC compilation.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def _detect_windows_sdk() -> dict[str, str] | None:  # pyright: ignore[reportUnusedFunction]
    """
    Detect Windows SDK installation via environment variables.

    This function checks for Visual Studio and Windows SDK environment variables
    that are typically set by vcvars*.bat or Visual Studio Developer Command Prompt.

    Returns:
        Dictionary with SDK information if found, None otherwise.
        Dictionary keys: 'sdk_dir', 'vc_tools_dir', 'sdk_version' (if available)

    Note:
        This function only checks environment variables. It does not search the
        registry or filesystem for SDK installations. The goal is to detect if
        the user has already set up their Visual Studio environment.
    """
    sdk_info = {}

    # Check for Windows SDK environment variables
    # These are set by vcvarsall.bat and similar VS setup scripts
    sdk_dir = os.environ.get("WindowsSdkDir") or os.environ.get("WindowsSDKDir")  # noqa: SIM112
    if sdk_dir:
        sdk_info["sdk_dir"] = sdk_dir
        logger.debug(f"Windows SDK found via environment: {sdk_dir}")

    # Check for Universal CRT SDK (required for C runtime)
    ucrt_sdk_dir = os.environ.get("UniversalCRTSdkDir")  # noqa: SIM112
    if ucrt_sdk_dir:
        sdk_info["ucrt_dir"] = ucrt_sdk_dir
        logger.debug(f"Universal CRT SDK found: {ucrt_sdk_dir}")

    # Check for VC Tools (MSVC compiler toolchain)
    vc_tools_dir = os.environ.get("VCToolsInstallDir")  # noqa: SIM112
    if vc_tools_dir:
        sdk_info["vc_tools_dir"] = vc_tools_dir
        logger.debug(f"VC Tools found: {vc_tools_dir}")

    # Check for VS installation directory
    vs_install_dir = os.environ.get("VSINSTALLDIR")
    if vs_install_dir:
        sdk_info["vs_install_dir"] = vs_install_dir
        logger.debug(f"Visual Studio installation found: {vs_install_dir}")

    # Check for Windows SDK version
    sdk_version = os.environ.get("WindowsSDKVersion")  # noqa: SIM112
    if sdk_version:
        sdk_info["sdk_version"] = sdk_version.rstrip("\\")  # Remove trailing backslash if present
        logger.debug(f"Windows SDK version: {sdk_version}")

    # Return SDK info if we found at least the SDK directory or VC tools
    if sdk_info:
        logger.info(f"Windows SDK detected: {', '.join(sdk_info.keys())}")
        return sdk_info

    logger.debug("Windows SDK not detected in environment variables")
    return None


def _print_msvc_sdk_warning() -> None:  # pyright: ignore[reportUnusedFunction]
    """
    Print a helpful warning message to stderr when Windows SDK is not detected.

    This is called when MSVC target is being used but we cannot detect the
    Windows SDK via environment variables. The compilation may still succeed
    if clang can find the SDK automatically, or it may fail with missing
    headers/libraries errors.
    """
    print("\n" + "=" * 70, file=sys.stderr)
    print("⚠️  Windows SDK Not Detected in Environment", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("\nThe MSVC target requires Windows SDK for system headers and libraries.", file=sys.stderr)
    print("\nNo SDK environment variables found. This may mean:", file=sys.stderr)
    print("  • Visual Studio or Windows SDK is not installed", file=sys.stderr)
    print("  • VS Developer Command Prompt is not being used", file=sys.stderr)
    print("  • Environment variables are not set (vcvarsall.bat not run)", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Recommendation: Set up Visual Studio environment", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\nOption 1: Use Visual Studio Developer Command Prompt", file=sys.stderr)
    print("  • Search for 'Developer Command Prompt' in Start Menu", file=sys.stderr)
    print("  • Run your build commands from that prompt", file=sys.stderr)
    print("\nOption 2: Run vcvarsall.bat in your current shell", file=sys.stderr)
    print("  • Typical location:", file=sys.stderr)
    print(
        "    C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat",
        file=sys.stderr,
    )
    print("  • Run: vcvarsall.bat x64", file=sys.stderr)
    print("\nOption 3: Install Visual Studio or Windows SDK", file=sys.stderr)
    print("  • Visual Studio: https://visualstudio.microsoft.com/downloads/", file=sys.stderr)
    print("  • Windows SDK only: https://developer.microsoft.com/windows/downloads/windows-sdk/", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Alternative: Use GNU ABI (MinGW) instead of MSVC", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\nIf you don't need MSVC compatibility, use the default commands:", file=sys.stderr)
    print("  • clang-tool-chain-c (uses GNU ABI, no SDK required)", file=sys.stderr)
    print("  • clang-tool-chain-cpp (uses GNU ABI, no SDK required)", file=sys.stderr)
    print("\n" + "=" * 70, file=sys.stderr)
    print("Clang will attempt to find Windows SDK automatically...", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)
