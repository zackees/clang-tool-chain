"""
ABI (Application Binary Interface) management for clang-tool-chain.

This package provides platform-specific ABI configuration and target arguments
for cross-platform compilation. It handles the differences between GNU ABI
(MinGW on Windows) and MSVC ABI, ensuring proper compilation and linking
with the appropriate system libraries and headers.

Windows Platform:
    - GNU ABI (default): Uses MinGW sysroot with integrated headers/libraries
    - MSVC ABI (opt-in): Uses Windows SDK and Visual Studio toolchain

Other Platforms:
    - Linux/macOS: Use native GNU-like ABI (no special configuration needed)
"""

from clang_tool_chain.abi.windows_gnu import _get_gnu_target_args, _should_use_gnu_abi
from clang_tool_chain.abi.windows_msvc import _get_msvc_target_args, _should_use_msvc_abi

__all__ = [
    "_should_use_gnu_abi",
    "_get_gnu_target_args",
    "_should_use_msvc_abi",
    "_get_msvc_target_args",
]
