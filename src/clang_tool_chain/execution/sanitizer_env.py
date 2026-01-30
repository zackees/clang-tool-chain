"""
Sanitizer runtime environment configuration.

This module provides automatic injection of ASAN_OPTIONS and LSAN_OPTIONS
environment variables to improve stack trace quality when running executables
compiled with Address Sanitizer or Leak Sanitizer.

The default options fix <unknown module> entries in stack traces from
dlopen()'d shared libraries by enabling slow unwinding and symbolization.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Default options to inject for optimal stack traces
# fast_unwind_on_malloc=0: Use slow but accurate unwinding (fixes <unknown module>)
# symbolize=1: Enable symbolization for readable stack traces
# detect_leaks=1: Enable leak detection (ASAN only)
DEFAULT_ASAN_OPTIONS = "fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1"
DEFAULT_LSAN_OPTIONS = "fast_unwind_on_malloc=0:symbolize=1"


def detect_sanitizers_from_flags(compiler_flags: list[str]) -> tuple[bool, bool]:
    """
    Detect which sanitizers are enabled from compiler flags.

    Args:
        compiler_flags: List of compiler flags passed to clang.

    Returns:
        Tuple of (asan_enabled, lsan_enabled).

    Example:
        >>> detect_sanitizers_from_flags(["-fsanitize=address", "-O2"])
        (True, True)  # ASAN implies LSAN by default
        >>> detect_sanitizers_from_flags(["-fsanitize=leak"])
        (False, True)
        >>> detect_sanitizers_from_flags(["-O2", "-Wall"])
        (False, False)
    """
    asan_enabled = False
    lsan_enabled = False

    for flag in compiler_flags:
        if flag.startswith("-fsanitize="):
            # Extract sanitizer list (e.g., "-fsanitize=address,undefined" -> "address,undefined")
            sanitizers = flag.split("=", 1)[1].split(",")
            for sanitizer in sanitizers:
                sanitizer = sanitizer.strip()
                if sanitizer == "address":
                    asan_enabled = True
                    # ASAN includes LSAN by default (unless detect_leaks=0)
                    lsan_enabled = True
                elif sanitizer == "leak":
                    lsan_enabled = True

    return asan_enabled, lsan_enabled


def prepare_sanitizer_environment(
    base_env: dict[str, str] | None = None,
    compiler_flags: list[str] | None = None,
) -> dict[str, str]:
    """
    Prepare environment with optimal sanitizer options.

    This function injects ASAN_OPTIONS and/or LSAN_OPTIONS environment variables
    if they are not already set by the user AND the corresponding sanitizer was
    enabled during compilation. The injected options improve stack trace quality
    for executables using dlopen()'d shared libraries.

    Args:
        base_env: Base environment dictionary to modify. If None, uses os.environ.
        compiler_flags: List of compiler flags used to build the executable.
            Used to detect which sanitizers are enabled. If None, no options
            are injected (safe default).

    Returns:
        Environment dictionary with sanitizer options injected as appropriate.

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_SANITIZER_ENV: Set to "1", "true", or "yes" to
            disable automatic injection of sanitizer options.
        ASAN_OPTIONS: If already set, preserved as-is (user config takes priority).
        LSAN_OPTIONS: If already set, preserved as-is (user config takes priority).

    Example:
        >>> env = prepare_sanitizer_environment(compiler_flags=["-fsanitize=address"])
        >>> # env now contains ASAN_OPTIONS and LSAN_OPTIONS
        >>> env = prepare_sanitizer_environment(compiler_flags=["-O2"])
        >>> # env unchanged - no sanitizers enabled
    """
    env = base_env.copy() if base_env is not None else os.environ.copy()

    # Check if disabled via environment variable
    if os.environ.get("CLANG_TOOL_CHAIN_NO_SANITIZER_ENV", "").lower() in ("1", "true", "yes"):
        logger.debug("Sanitizer environment injection disabled via CLANG_TOOL_CHAIN_NO_SANITIZER_ENV")
        return env

    # If no compiler flags provided, don't inject anything (safe default)
    if compiler_flags is None:
        logger.debug("No compiler flags provided, skipping sanitizer environment injection")
        return env

    # Detect which sanitizers are enabled
    asan_enabled, lsan_enabled = detect_sanitizers_from_flags(compiler_flags)

    # Inject ASAN_OPTIONS if ASAN is enabled and not already set by user
    if asan_enabled and "ASAN_OPTIONS" not in env:
        env["ASAN_OPTIONS"] = DEFAULT_ASAN_OPTIONS
        logger.info(f"Injecting ASAN_OPTIONS={DEFAULT_ASAN_OPTIONS}")

    # Inject LSAN_OPTIONS if LSAN is enabled and not already set by user
    if lsan_enabled and "LSAN_OPTIONS" not in env:
        env["LSAN_OPTIONS"] = DEFAULT_LSAN_OPTIONS
        logger.info(f"Injecting LSAN_OPTIONS={DEFAULT_LSAN_OPTIONS}")

    return env
