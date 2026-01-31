"""
Environment variable utilities for clang-tool-chain.

This module provides centralized handling of environment variable checks,
including support for the aggregate CLANG_TOOL_CHAIN_NO_AUTO variable
that disables all automatic features.

Example:
    >>> from clang_tool_chain.env_utils import is_feature_disabled
    >>> if is_feature_disabled("DIRECTIVES"):
    ...     # Skip directive parsing
    ...     pass
"""

import logging
import os

logger = logging.getLogger(__name__)

# Truthy values for boolean environment variables
_TRUTHY_VALUES = ("1", "true", "yes")

# All features that can be disabled via NO_AUTO
# Maps feature name to the specific environment variable suffix
CONTROLLABLE_FEATURES = {
    "DIRECTIVES": "Inlined build directives (@link, @std, @cflags)",
    "SHARED_ASAN": "Automatic -shared-libasan injection (Linux)",
    "SANITIZER_ENV": "Automatic ASAN_OPTIONS/LSAN_OPTIONS injection",
    "RPATH": "Automatic rpath injection for library loading",
    "SYSROOT": "Automatic macOS SDK detection (-isysroot)",
    "DEPLOY_LIBS": "Cross-platform library deployment (all outputs)",
    "DEPLOY_SHARED_LIB": "Library deployment for shared library outputs only (.dll, .so, .dylib)",
}


def _is_truthy(value: str | None) -> bool:
    """Check if an environment variable value is truthy."""
    if value is None:
        return False
    return value.lower() in _TRUTHY_VALUES


def is_auto_disabled() -> bool:
    """
    Check if all automatic features are disabled via CLANG_TOOL_CHAIN_NO_AUTO.

    Returns:
        True if CLANG_TOOL_CHAIN_NO_AUTO is set to a truthy value.

    Example:
        >>> os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "1"
        >>> is_auto_disabled()
        True
    """
    return _is_truthy(os.environ.get("CLANG_TOOL_CHAIN_NO_AUTO"))


def is_feature_disabled(feature: str) -> bool:
    """
    Check if a specific feature is disabled.

    A feature is disabled if either:
    1. The aggregate CLANG_TOOL_CHAIN_NO_AUTO=1 is set, OR
    2. The specific CLANG_TOOL_CHAIN_NO_{feature}=1 is set

    Args:
        feature: The feature name (e.g., "DIRECTIVES", "SHARED_ASAN", "DEPLOY_LIBS").
                 Should match one of the keys in CONTROLLABLE_FEATURES.

    Returns:
        True if the feature is disabled, False otherwise.

    Example:
        >>> os.environ["CLANG_TOOL_CHAIN_NO_DIRECTIVES"] = "1"
        >>> is_feature_disabled("DIRECTIVES")
        True

        >>> os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "1"
        >>> is_feature_disabled("SHARED_ASAN")  # Disabled by NO_AUTO
        True
    """
    # Check the aggregate NO_AUTO variable first
    if is_auto_disabled():
        logger.debug(f"Feature {feature} disabled via CLANG_TOOL_CHAIN_NO_AUTO=1")
        return True

    # Check the specific feature variable
    var_name = f"CLANG_TOOL_CHAIN_NO_{feature}"
    if _is_truthy(os.environ.get(var_name)):
        logger.debug(f"Feature {feature} disabled via {var_name}=1")
        return True

    return False


def get_disabled_features() -> list[str]:
    """
    Get a list of all currently disabled features.

    Returns:
        List of feature names that are disabled.

    Example:
        >>> os.environ["CLANG_TOOL_CHAIN_NO_AUTO"] = "1"
        >>> get_disabled_features()
        ['DIRECTIVES', 'SHARED_ASAN', 'SANITIZER_ENV', ...]
    """
    disabled = []

    # If NO_AUTO is set, all features are disabled
    if is_auto_disabled():
        return list(CONTROLLABLE_FEATURES.keys())

    # Check each feature individually
    for feature in CONTROLLABLE_FEATURES:
        var_name = f"CLANG_TOOL_CHAIN_NO_{feature}"
        if _is_truthy(os.environ.get(var_name)):
            disabled.append(feature)

    return disabled


def log_disabled_features_summary() -> None:
    """
    Log a summary of disabled features (useful for debugging).

    Only logs if at least one feature is disabled.
    """
    disabled = get_disabled_features()
    if not disabled:
        return

    if is_auto_disabled():
        logger.info("All automatic features disabled via CLANG_TOOL_CHAIN_NO_AUTO=1")
    else:
        logger.info(f"Disabled features: {', '.join(disabled)}")
