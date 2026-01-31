__version__ = "1.0.30"

# Re-export commonly used functions for convenient access
from clang_tool_chain.execution.sanitizer_env import (
    detect_sanitizers_from_flags,
    get_symbolizer_path,
    prepare_sanitizer_environment,
)
from clang_tool_chain.platform import find_tool_binary, get_platform_binary_dir, get_platform_info

__all__ = [
    "__version__",
    # Platform utilities
    "get_platform_info",
    "get_platform_binary_dir",
    "find_tool_binary",
    # Sanitizer environment
    "prepare_sanitizer_environment",
    "get_symbolizer_path",
    "detect_sanitizers_from_flags",
]
