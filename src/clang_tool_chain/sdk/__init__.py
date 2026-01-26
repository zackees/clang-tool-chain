"""
SDK detection and utilities for Windows and macOS platforms.

This package provides functions for detecting platform-specific SDKs
and displaying helpful warnings/errors when SDKs are not found.
"""

from clang_tool_chain.sdk.macos import _add_macos_sysroot_if_needed, _print_macos_sdk_error
from clang_tool_chain.sdk.windows import _detect_windows_sdk, _print_msvc_sdk_warning

__all__ = [
    "_detect_windows_sdk",
    "_print_msvc_sdk_warning",
    "_print_macos_sdk_error",
    "_add_macos_sysroot_if_needed",
]
