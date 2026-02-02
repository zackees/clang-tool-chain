__version__ = "1.0.30"

# Re-export commonly used functions for convenient access
from clang_tool_chain.env_utils import (
    CONTROLLABLE_FEATURES,
    get_disabled_features,
    is_auto_disabled,
    is_feature_disabled,
)
from clang_tool_chain.execution.sanitizer_env import (
    detect_sanitizers_from_flags,
    get_all_sanitizer_runtime_dlls,
    get_asan_runtime_dll,
    get_default_asan_options,
    get_runtime_dll_paths,
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
    # Environment utilities
    "is_feature_disabled",
    "is_auto_disabled",
    "get_disabled_features",
    "CONTROLLABLE_FEATURES",
    # Sanitizer environment
    "prepare_sanitizer_environment",
    "get_runtime_dll_paths",
    "get_symbolizer_path",
    "detect_sanitizers_from_flags",
    "get_asan_runtime_dll",
    "get_all_sanitizer_runtime_dlls",
    "get_default_asan_options",
]
