"""
Sanitizer runtime environment configuration.

This module provides automatic injection of ASAN_OPTIONS, LSAN_OPTIONS, and
ASAN_SYMBOLIZER_PATH environment variables to improve stack trace quality
when running executables compiled with Address Sanitizer or Leak Sanitizer.

The default options fix <unknown module> entries in stack traces from
dlopen()'d shared libraries by enabling slow unwinding and symbolization.

The symbolizer path is automatically detected from the clang-tool-chain
installation, enabling proper address-to-symbol resolution without manual
configuration.
"""

import logging
import os
import platform
import shutil
from pathlib import Path

from clang_tool_chain.env_utils import is_feature_disabled

logger = logging.getLogger(__name__)

# Default options to inject for optimal stack traces
# fast_unwind_on_malloc=0: Use slow but accurate unwinding (fixes <unknown module>)
# symbolize=1: Enable symbolization for readable stack traces
# detect_leaks=1: Enable leak detection (ASAN only)
DEFAULT_ASAN_OPTIONS = "fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1"
DEFAULT_LSAN_OPTIONS = "fast_unwind_on_malloc=0:symbolize=1"


def get_symbolizer_path() -> str | None:
    """
    Get the path to llvm-symbolizer from the clang-tool-chain installation.

    This function finds the llvm-symbolizer binary bundled with clang-tool-chain,
    which is required by ASAN/LSAN to convert memory addresses into function names
    and source locations in stack traces.

    Returns:
        Absolute path to llvm-symbolizer, or None if not found.

    Example:
        >>> path = get_symbolizer_path()
        >>> if path:
        ...     os.environ["ASAN_SYMBOLIZER_PATH"] = path

    Note:
        Falls back to system PATH if the clang-tool-chain binary is not available.
        This allows the function to work even when clang-tool-chain is not fully
        installed (e.g., during development or in CI environments).
    """
    # Try to find llvm-symbolizer from clang-tool-chain installation
    try:
        from clang_tool_chain.platform.paths import find_tool_binary

        symbolizer = find_tool_binary("llvm-symbolizer")
        return str(symbolizer)
    except (ImportError, RuntimeError) as e:
        logger.debug(f"Could not find llvm-symbolizer in clang-tool-chain: {e}")

    # Fall back to system PATH
    system_symbolizer = shutil.which("llvm-symbolizer")
    if system_symbolizer:
        logger.debug(f"Using system llvm-symbolizer: {system_symbolizer}")
        return system_symbolizer

    logger.debug("llvm-symbolizer not found in clang-tool-chain or system PATH")
    return None


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


def _get_builtin_suppression_file() -> Path | None:
    """
    Get path to built-in LSan suppression file for current platform.

    Returns:
        Path to built-in suppression file, or None if not applicable.

    Note:
        - macOS: Returns path to lsan_suppressions_darwin.txt
        - Linux: Returns path to lsan_suppressions_linux.txt
        - Windows: Returns None (LSan not supported on Windows)
    """
    system = platform.system()

    # Locate data directory in installed package
    data_dir = Path(__file__).parent.parent / "data"

    if system == "Darwin":
        suppression_file = data_dir / "lsan_suppressions_darwin.txt"
    elif system == "Linux":
        suppression_file = data_dir / "lsan_suppressions_linux.txt"
    else:
        return None  # No suppressions for Windows (no LSan support)

    return suppression_file if suppression_file.exists() else None


def prepare_sanitizer_environment(
    base_env: dict[str, str] | None = None,
    compiler_flags: list[str] | None = None,
    suppression_file: str | Path | None = None,
) -> dict[str, str]:
    """
    Prepare environment with optimal sanitizer options and symbolizer path.

    This function injects ASAN_OPTIONS, LSAN_OPTIONS, and ASAN_SYMBOLIZER_PATH
    environment variables if they are not already set by the user AND the
    corresponding sanitizer was enabled during compilation. The injected options
    improve stack trace quality for executables using dlopen()'d shared libraries.

    The ASAN_SYMBOLIZER_PATH is automatically detected from the clang-tool-chain
    installation, enabling proper address-to-symbol resolution (function names,
    file paths, line numbers) without manual configuration.

    On macOS and Linux, platform-specific LSan suppression files are automatically
    applied to filter out false positive leaks from system libraries.

    Args:
        base_env: Base environment dictionary to modify. If None, uses os.environ.
        compiler_flags: List of compiler flags used to build the executable.
            Used to detect which sanitizers are enabled. If None, no options
            are injected (safe default).
        suppression_file: Optional path to custom LSan suppression file.
            If None, uses built-in platform-specific suppressions.
            Set to empty string "" to disable built-in suppressions.

    Returns:
        Environment dictionary with sanitizer options injected as appropriate.

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_SANITIZER_ENV: Set to "1", "true", or "yes" to
            disable automatic injection of sanitizer options.
        CLANG_TOOL_CHAIN_NO_AUTO: Set to "1" to disable all automatic features.
        ASAN_OPTIONS: If already set, preserved as-is (user config takes priority).
        LSAN_OPTIONS: If already set, preserved as-is (user config takes priority).
        ASAN_SYMBOLIZER_PATH: If already set, preserved as-is (user config takes priority).

    Example:
        >>> env = prepare_sanitizer_environment(compiler_flags=["-fsanitize=address"])
        >>> # env now contains ASAN_OPTIONS, LSAN_OPTIONS, ASAN_SYMBOLIZER_PATH, and suppressions
        >>> env = prepare_sanitizer_environment(compiler_flags=["-O2"])
        >>> # env unchanged - no sanitizers enabled
        >>> env = prepare_sanitizer_environment(
        ...     compiler_flags=["-fsanitize=address"],
        ...     suppression_file="/path/to/custom.txt"
        ... )
        >>> # Uses custom suppression file instead of built-in
    """
    env = base_env.copy() if base_env is not None else os.environ.copy()

    # Check if disabled via environment variable (NO_SANITIZER_ENV or NO_AUTO)
    if is_feature_disabled("SANITIZER_ENV"):
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

    # Inject ASAN_SYMBOLIZER_PATH if any sanitizer is enabled and not already set
    if (asan_enabled or lsan_enabled) and "ASAN_SYMBOLIZER_PATH" not in env:
        symbolizer_path = get_symbolizer_path()
        if symbolizer_path:
            env["ASAN_SYMBOLIZER_PATH"] = symbolizer_path
            logger.info(f"Injecting ASAN_SYMBOLIZER_PATH={symbolizer_path}")
        else:
            logger.warning(
                "llvm-symbolizer not found - ASAN/LSAN stack traces may show "
                "raw addresses instead of function names. Install llvm-symbolizer "
                "or ensure clang-tool-chain is properly installed."
            )

    # Add platform-specific LSan suppressions if LSAN is enabled
    if lsan_enabled:
        # Use built-in suppression file if no custom file specified
        if suppression_file is None:
            suppression_file = _get_builtin_suppression_file()

        # Apply suppression file if it exists (unless explicitly disabled with "")
        if suppression_file and suppression_file != "" and Path(suppression_file).exists():
            current_lsan = env.get("LSAN_OPTIONS", "")
            suppression_opt = f"suppressions={Path(suppression_file).absolute()}"

            if current_lsan:
                # Append to existing options
                env["LSAN_OPTIONS"] = f"{current_lsan}:{suppression_opt}"
            else:
                # Set new options
                env["LSAN_OPTIONS"] = suppression_opt

            logger.info(f"Injecting LSan suppression file: {suppression_file}")

    return env
