from typing import TYPE_CHECKING

__version__ = "1.1.10"

# Public API is resolved lazily via module-level __getattr__ (PEP 562) so the
# native-trampoline hot path (clang-tool-chain-c / -cpp) doesn't pay ~300 ms of
# eager-import cost from execution.sanitizer_env + platform.detection just to
# reach the shim that execvp's into the C++ binary.

if TYPE_CHECKING:
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
    from clang_tool_chain.platform import (
        find_tool_binary,
        get_platform_binary_dir,
        get_platform_info,
    )

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

_LAZY_ATTRS = {
    "is_feature_disabled": ("clang_tool_chain.env_utils", "is_feature_disabled"),
    "is_auto_disabled": ("clang_tool_chain.env_utils", "is_auto_disabled"),
    "get_disabled_features": ("clang_tool_chain.env_utils", "get_disabled_features"),
    "CONTROLLABLE_FEATURES": ("clang_tool_chain.env_utils", "CONTROLLABLE_FEATURES"),
    "prepare_sanitizer_environment": (
        "clang_tool_chain.execution.sanitizer_env",
        "prepare_sanitizer_environment",
    ),
    "get_runtime_dll_paths": (
        "clang_tool_chain.execution.sanitizer_env",
        "get_runtime_dll_paths",
    ),
    "get_symbolizer_path": (
        "clang_tool_chain.execution.sanitizer_env",
        "get_symbolizer_path",
    ),
    "detect_sanitizers_from_flags": (
        "clang_tool_chain.execution.sanitizer_env",
        "detect_sanitizers_from_flags",
    ),
    "get_asan_runtime_dll": (
        "clang_tool_chain.execution.sanitizer_env",
        "get_asan_runtime_dll",
    ),
    "get_all_sanitizer_runtime_dlls": (
        "clang_tool_chain.execution.sanitizer_env",
        "get_all_sanitizer_runtime_dlls",
    ),
    "get_default_asan_options": (
        "clang_tool_chain.execution.sanitizer_env",
        "get_default_asan_options",
    ),
    "get_platform_info": ("clang_tool_chain.platform", "get_platform_info"),
    "get_platform_binary_dir": ("clang_tool_chain.platform", "get_platform_binary_dir"),
    "find_tool_binary": ("clang_tool_chain.platform", "find_tool_binary"),
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module 'clang_tool_chain' has no attribute {name!r}")
    import importlib

    module_path, attr = target
    mod = importlib.import_module(module_path)
    value = getattr(mod, attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
