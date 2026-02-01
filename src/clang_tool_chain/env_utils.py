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
    "BUNDLED_UNWIND": "Bundled libunwind paths on Linux",
    "MACOS_UNWIND_FIX": "Automatic -lunwind removal on macOS (libunwind in libSystem)",
    # Sanitizer notes (hierarchical)
    "SANITIZER_NOTE": "All sanitizer-related notes (category master)",
    "SHARED_ASAN_NOTE": "-shared-libasan injection note",
    "ALLOW_SHLIB_UNDEFINED_NOTE": "-Wl,--allow-shlib-undefined injection note",
    # Linker notes (hierarchical)
    "LINKER_NOTE": "All linker-related notes (category master)",
    "LINKER_COMPAT_NOTE": "Removed GNU linker flags note",
    "LD64_LLD_CONVERT_NOTE": "-fuse-ld=ld64.lld conversion note",
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


def is_note_disabled(specific: str, category: str | None = None) -> bool:
    """
    Check if a specific note is disabled using hierarchical suppression.

    A note is disabled if ANY of:
    1. CLANG_TOOL_CHAIN_NO_AUTO=1 (global master)
    2. CLANG_TOOL_CHAIN_NO_{category}=1 (category master, if provided)
    3. CLANG_TOOL_CHAIN_NO_{specific}=1 (specific note)

    This allows users to:
    - Disable all automatic features with NO_AUTO=1
    - Disable a category of notes (e.g., all sanitizer notes) with NO_SANITIZER_NOTE=1
    - Disable a specific note with its dedicated variable (e.g., NO_SHARED_ASAN_NOTE=1)

    Args:
        specific: The specific note name (e.g., "SHARED_ASAN_NOTE")
        category: Optional category master (e.g., "SANITIZER_NOTE")

    Returns:
        True if the note should be suppressed

    Example:
        >>> os.environ["CLANG_TOOL_CHAIN_NO_SANITIZER_NOTE"] = "1"
        >>> is_note_disabled("SHARED_ASAN_NOTE", "SANITIZER_NOTE")
        True  # Disabled via category

        >>> os.environ["CLANG_TOOL_CHAIN_NO_SHARED_ASAN_NOTE"] = "1"
        >>> is_note_disabled("SHARED_ASAN_NOTE", "SANITIZER_NOTE")
        True  # Disabled via specific variable
    """
    # Check the global master (NO_AUTO)
    if is_auto_disabled():
        logger.debug(f"Note {specific} disabled via CLANG_TOOL_CHAIN_NO_AUTO=1")
        return True

    # Check the category master (if provided)
    if category:
        var_name = f"CLANG_TOOL_CHAIN_NO_{category}"
        if _is_truthy(os.environ.get(var_name)):
            logger.debug(f"Note {specific} disabled via {var_name}=1 (category master)")
            return True

    # Check the specific note variable
    var_name = f"CLANG_TOOL_CHAIN_NO_{specific}"
    if _is_truthy(os.environ.get(var_name)):
        logger.debug(f"Note {specific} disabled via {var_name}=1")
        return True

    return False
