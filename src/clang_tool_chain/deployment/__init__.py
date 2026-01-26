"""
DLL deployment module for Windows executables built with GNU ABI.

This module provides automatic deployment of MinGW runtime DLLs to
executable directories after successful linking.
"""

from clang_tool_chain.deployment.dll_deployer import detect_required_dlls, post_link_dll_deployment

__all__ = ["detect_required_dlls", "post_link_dll_deployment"]
