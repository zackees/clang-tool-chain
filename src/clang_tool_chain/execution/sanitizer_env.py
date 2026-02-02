"""
Sanitizer runtime environment configuration.

This module provides automatic injection of ASAN_OPTIONS, LSAN_OPTIONS,
ASAN_SYMBOLIZER_PATH, and PATH environment variables to ensure executables
compiled with Address Sanitizer or Leak Sanitizer can run correctly.

The default options fix <unknown module> entries in stack traces from
dlopen()'d shared libraries by enabling slow unwinding and symbolization.

The symbolizer path is automatically detected from the clang-tool-chain
installation, enabling proper address-to-symbol resolution without manual
configuration.

On Windows with shared ASAN runtime (-shared-libasan), the clang runtime
DLL directory is automatically added to PATH to ensure the ASAN DLL can
be found at runtime.
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
# detect_leaks=1: Enable leak detection (ASAN only, NOT on Windows - LSAN unsupported)
#
# LeakSanitizer (LSAN) is NOT supported on Windows. Only Linux, macOS, Android,
# Fuchsia, and NetBSD are supported. See: https://clang.llvm.org/docs/LeakSanitizer.html
#
# On Windows, setting detect_leaks=1 causes immediate failure with:
#   "AddressSanitizer: detect_leaks is not supported on this platform."
_BASE_ASAN_OPTIONS = "fast_unwind_on_malloc=0:symbolize=1"
DEFAULT_LSAN_OPTIONS = "fast_unwind_on_malloc=0:symbolize=1"


def get_default_asan_options() -> str:
    """
    Get platform-appropriate default ASAN options.

    Returns options string with detect_leaks=1 only on platforms where
    LeakSanitizer is supported (Linux, macOS). Windows does not support
    LSAN, so detect_leaks is omitted to prevent runtime failures.

    Returns:
        ASAN options string appropriate for the current platform.

    Example:
        >>> get_default_asan_options()  # On Linux/macOS
        'fast_unwind_on_malloc=0:symbolize=1:detect_leaks=1'
        >>> get_default_asan_options()  # On Windows
        'fast_unwind_on_malloc=0:symbolize=1'
    """
    if platform.system() == "Windows":
        # LSAN (LeakSanitizer) is not supported on Windows
        # See: https://clang.llvm.org/docs/LeakSanitizer.html
        return _BASE_ASAN_OPTIONS
    # Linux, macOS, and other platforms support LSAN
    return f"{_BASE_ASAN_OPTIONS}:detect_leaks=1"


# For backward compatibility - this is now dynamically computed
# Code that imports DEFAULT_ASAN_OPTIONS directly will get the platform-appropriate value
DEFAULT_ASAN_OPTIONS = get_default_asan_options()


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


def get_runtime_dll_paths() -> list[str]:
    """
    Get paths to directories containing runtime DLLs (Windows only).

    On Windows, when using shared ASAN runtime (-shared-libasan), the
    libclang_rt.asan_dynamic-x86_64.dll must be findable at runtime.
    This function returns the paths that should be added to PATH.

    Returns:
        List of directory paths containing runtime DLLs, or empty list
        if not applicable (non-Windows or DLLs not found).

    Example:
        >>> paths = get_runtime_dll_paths()
        >>> if paths:
        ...     os.environ["PATH"] = os.pathsep.join(paths) + os.pathsep + os.environ.get("PATH", "")
    """
    if platform.system() != "Windows":
        return []

    paths = []

    try:
        from clang_tool_chain.platform.detection import get_platform_binary_dir, get_platform_info

        # Get platform info for sysroot lookup
        _platform_name, arch = get_platform_info()

        # Get the clang bin directory and sysroot bin directory
        clang_bin_dir = get_platform_binary_dir()
        clang_root = clang_bin_dir.parent

        # Add clang bin directory (for some sanitizer DLLs)
        if clang_bin_dir.exists():
            paths.append(str(clang_bin_dir))

        # Add MinGW sysroot bin directory (where libclang_rt.asan_dynamic-x86_64.dll lives)
        if arch == "x86_64":
            sysroot_name = "x86_64-w64-mingw32"
        elif arch == "arm64":
            sysroot_name = "aarch64-w64-mingw32"
        else:
            sysroot_name = None

        if sysroot_name:
            sysroot_bin = clang_root / sysroot_name / "bin"
            if sysroot_bin.exists():
                paths.append(str(sysroot_bin))
                logger.debug(f"Found MinGW sysroot bin: {sysroot_bin}")

    except (ImportError, RuntimeError) as e:
        logger.debug(f"Could not get runtime DLL paths: {e}")

    return paths


def get_asan_runtime_dll() -> Path | None:
    """
    Get the full path to the ASAN runtime DLL (Windows only).

    This function locates the shared ASAN runtime DLL used when compiling
    with -fsanitize=address -shared-libasan. The DLL must be accessible
    at runtime for ASAN-instrumented executables to run.

    This is particularly useful when running tests via build systems like
    Meson that reset PATH and don't inherit ASAN DLL directories. By getting
    the DLL path, consuming projects can copy it to their build directory
    where the build system will automatically discover it.

    Returns:
        Path to libclang_rt.asan_dynamic-x86_64.dll (or ARM64 equivalent),
        or None if not found or not on Windows.

    Example:
        >>> dll_path = get_asan_runtime_dll()
        >>> if dll_path:
        ...     shutil.copy(dll_path, build_dir / dll_path.name)
        ...     # Now Meson tests will find the ASAN DLL in build_dir

    Note:
        This function ensures the toolchain is downloaded before searching.
        The DLL is typically located in the MinGW sysroot bin directory:
        ~/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin/

    See Also:
        get_runtime_dll_paths: Returns directories containing runtime DLLs
        prepare_sanitizer_environment: Adds DLL paths to PATH
    """
    if platform.system() != "Windows":
        logger.debug("get_asan_runtime_dll: Not on Windows, returning None")
        return None

    try:
        from clang_tool_chain.platform.detection import get_platform_binary_dir, get_platform_info

        # Get platform info for sysroot lookup
        _platform_name, arch = get_platform_info()

        # Get the clang root directory
        clang_bin_dir = get_platform_binary_dir()
        clang_root = clang_bin_dir.parent

        # Determine sysroot and DLL name based on architecture
        if arch == "x86_64":
            sysroot_name = "x86_64-w64-mingw32"
            dll_name = "libclang_rt.asan_dynamic-x86_64.dll"
        elif arch == "arm64":
            sysroot_name = "aarch64-w64-mingw32"
            dll_name = "libclang_rt.asan_dynamic-aarch64.dll"
        else:
            logger.debug(f"get_asan_runtime_dll: Unsupported architecture {arch}")
            return None

        # Check MinGW sysroot bin directory first (primary location)
        sysroot_bin = clang_root / sysroot_name / "bin"
        dll_path = sysroot_bin / dll_name
        if dll_path.exists():
            logger.debug(f"Found ASAN runtime DLL: {dll_path}")
            return dll_path

        # Fallback: check clang bin directory
        dll_path = clang_bin_dir / dll_name
        if dll_path.exists():
            logger.debug(f"Found ASAN runtime DLL (fallback): {dll_path}")
            return dll_path

        # Try glob pattern for any ASAN DLL (version may vary)
        for search_dir in [sysroot_bin, clang_bin_dir]:
            if search_dir.exists():
                for dll_file in search_dir.glob("libclang_rt.asan*.dll"):
                    logger.debug(f"Found ASAN runtime DLL (glob): {dll_file}")
                    return dll_file

        logger.debug(f"ASAN runtime DLL not found in {sysroot_bin} or {clang_bin_dir}")
        return None

    except (ImportError, RuntimeError) as e:
        logger.debug(f"Could not get ASAN runtime DLL path: {e}")
        return None


def get_all_sanitizer_runtime_dlls() -> list[Path]:
    """
    Get all sanitizer runtime DLLs (Windows only).

    This function locates all shared sanitizer runtime DLLs, including:
    - Address Sanitizer (ASAN)
    - Undefined Behavior Sanitizer (UBSAN)
    - Thread Sanitizer (TSAN) - if available

    This is useful for projects that want to copy all sanitizer DLLs to
    their build directory to ensure all instrumented code can run.

    Returns:
        List of Paths to sanitizer runtime DLLs, or empty list if not
        found or not on Windows.

    Example:
        >>> dlls = get_all_sanitizer_runtime_dlls()
        >>> for dll in dlls:
        ...     shutil.copy(dll, build_dir / dll.name)

    See Also:
        get_asan_runtime_dll: Returns just the ASAN DLL path
    """
    if platform.system() != "Windows":
        return []

    dlls: list[Path] = []

    try:
        from clang_tool_chain.platform.detection import get_platform_binary_dir, get_platform_info

        # Get platform info for sysroot lookup
        _platform_name, arch = get_platform_info()

        # Get the clang root directory
        clang_bin_dir = get_platform_binary_dir()
        clang_root = clang_bin_dir.parent

        # Determine sysroot based on architecture
        if arch == "x86_64":
            sysroot_name = "x86_64-w64-mingw32"
        elif arch == "arm64":
            sysroot_name = "aarch64-w64-mingw32"
        else:
            return []

        # Search directories
        search_dirs = [
            clang_root / sysroot_name / "bin",
            clang_bin_dir,
        ]

        # Patterns for sanitizer DLLs
        patterns = [
            "libclang_rt.asan*.dll",  # Address Sanitizer
            "libclang_rt.ubsan*.dll",  # Undefined Behavior Sanitizer
            "libclang_rt.tsan*.dll",  # Thread Sanitizer
            "libclang_rt.lsan*.dll",  # Leak Sanitizer (standalone)
        ]

        seen_names: set[str] = set()
        for search_dir in search_dirs:
            if search_dir.exists():
                for pattern in patterns:
                    for dll_file in search_dir.glob(pattern):
                        if dll_file.name not in seen_names:
                            dlls.append(dll_file)
                            seen_names.add(dll_file.name)
                            logger.debug(f"Found sanitizer DLL: {dll_file}")

    except (ImportError, RuntimeError) as e:
        logger.debug(f"Could not get sanitizer runtime DLLs: {e}")

    return dlls


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
        suppression_file: Optional path to additional custom LSan suppression file.
            If provided, this file is merged with built-in platform-specific
            suppressions (built-in applied first, then custom).
            Set to empty string "" to disable built-in suppressions entirely.

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
        >>> # Uses BOTH built-in AND custom suppression files (merged)
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
        asan_options = get_default_asan_options()
        env["ASAN_OPTIONS"] = asan_options
        logger.info(f"Injecting ASAN_OPTIONS={asan_options}")

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

    # On Windows, add runtime DLL paths to PATH for shared ASAN runtime
    # This ensures libclang_rt.asan_dynamic-x86_64.dll can be found at runtime
    if asan_enabled and platform.system() == "Windows":
        dll_paths = get_runtime_dll_paths()
        if dll_paths:
            current_path = env.get("PATH", "")
            # Prepend DLL paths to ensure they take priority
            new_path = os.pathsep.join(dll_paths)
            if current_path:
                env["PATH"] = new_path + os.pathsep + current_path
            else:
                env["PATH"] = new_path
            logger.info(f"Injecting runtime DLL paths to PATH: {dll_paths}")

    # Add platform-specific LSan suppressions if LSAN is enabled
    if lsan_enabled:
        # Check if user explicitly disabled built-in suppressions with ""
        disable_builtin = suppression_file == ""

        # Helper to append suppression file to LSAN_OPTIONS
        def _append_suppression(file_path: Path) -> None:
            current_lsan = env.get("LSAN_OPTIONS", "")
            suppression_opt = f"suppressions={file_path.absolute()}"

            if current_lsan:
                env["LSAN_OPTIONS"] = f"{current_lsan}:{suppression_opt}"
            else:
                env["LSAN_OPTIONS"] = suppression_opt

            logger.info(f"Injecting LSan suppression file: {file_path}")

        # First, apply built-in platform-specific suppressions (unless disabled)
        if not disable_builtin:
            builtin_file = _get_builtin_suppression_file()
            if builtin_file and builtin_file.exists():
                _append_suppression(builtin_file)

        # Then, also apply custom suppression file if provided (merge behavior)
        if suppression_file and suppression_file != "":
            custom_path = Path(suppression_file)
            if custom_path.exists():
                _append_suppression(custom_path)
            else:
                logger.warning(f"Custom suppression file not found: {suppression_file}")

    return env
