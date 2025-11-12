"""
Settings warnings for clang-tool-chain.

This module provides utilities to warn users when non-default settings
are being used via environment variables.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Track which warnings have been shown to avoid spam
_shown_warnings: set[str] = set()


def warn_if_env_var_set(
    var_name: str,
    expected_value: str | None = None,
    *,
    once: bool = True,
    message: str | None = None,
) -> bool:
    """
    Warn if an environment variable is set (and optionally matches a value).

    Args:
        var_name: Name of the environment variable to check
        expected_value: If provided, only warn if env var equals this value.
                       If None, warn if env var is set to any non-empty value.
        once: If True, only warn once per variable (default: True)
        message: Custom warning message. If None, a default message is generated.

    Returns:
        True if the environment variable is set (and matches expected_value if provided)
    """
    value = os.environ.get(var_name)

    # Check if variable is set
    if not value:
        return False

    # Check if it matches expected value (if specified)
    if expected_value is not None and value != expected_value:
        return False

    # Generate warning key for deduplication
    warning_key = f"{var_name}={value}"

    # Skip if we've already warned about this (and once=True)
    if once and warning_key in _shown_warnings:
        return True

    # Generate default message if not provided
    if message is None:
        message = f"Non-default setting detected: {var_name}={value}"

    # Log the warning
    logger.warning(message)

    # Mark as shown
    if once:
        _shown_warnings.add(warning_key)

    return True


def warn_download_path_override() -> str | None:
    """
    Warn if CLANG_TOOL_CHAIN_DOWNLOAD_PATH is set.

    Returns:
        The custom download path if set, None otherwise
    """
    path = os.environ.get("CLANG_TOOL_CHAIN_DOWNLOAD_PATH")
    if path:
        warn_if_env_var_set(
            "CLANG_TOOL_CHAIN_DOWNLOAD_PATH",
            message=(
                f"Using custom download path: CLANG_TOOL_CHAIN_DOWNLOAD_PATH={path}\n"
                f"Default path (~/.clang-tool-chain) is not being used."
            ),
        )
    return path


def warn_no_sysroot() -> bool:
    """
    Warn if CLANG_TOOL_CHAIN_NO_SYSROOT is set to '1'.

    Returns:
        True if sysroot injection is disabled
    """
    return warn_if_env_var_set(
        "CLANG_TOOL_CHAIN_NO_SYSROOT",
        expected_value="1",
        message=(
            "Automatic macOS SDK detection disabled: CLANG_TOOL_CHAIN_NO_SYSROOT=1\n"
            "You must manually specify -isysroot or set SDKROOT if building for macOS."
        ),
    )


def warn_use_system_ld() -> bool:
    """
    Warn if CLANG_TOOL_CHAIN_USE_SYSTEM_LD is set to '1'.

    Returns:
        True if system linker should be used instead of lld
    """
    return warn_if_env_var_set(
        "CLANG_TOOL_CHAIN_USE_SYSTEM_LD",
        expected_value="1",
        message=(
            "Using system linker instead of lld: CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1\n"
            "This may cause linking issues or inconsistent behavior across platforms."
        ),
    )


def reset_warnings() -> None:
    """
    Reset the warning tracking (useful for testing).

    This clears the set of shown warnings so they can be displayed again.
    """
    _shown_warnings.clear()
