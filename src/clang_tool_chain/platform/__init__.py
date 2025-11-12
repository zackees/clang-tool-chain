"""Platform detection and utilities for the Clang tool chain."""

from .detection import get_platform_binary_dir, get_platform_info
from .paths import find_sccache_binary, find_tool_binary

__all__ = ["get_platform_info", "get_platform_binary_dir", "find_tool_binary", "find_sccache_binary"]
