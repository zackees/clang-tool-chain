"""
Windows GNU ABI (MinGW) configuration and target arguments.

This module provides functionality for configuring compilation with GNU ABI
on Windows using the integrated MinGW sysroot. Windows defaults to GNU ABI
in v1.0.5+ for cross-platform consistency.
"""

import logging

logger = logging.getLogger(__name__)


def _should_use_gnu_abi(platform_name: str, args: list[str]) -> bool:  # pyright: ignore[reportUnusedFunction]
    """
    Determine if GNU ABI should be used based on platform and arguments.

    Windows defaults to GNU ABI (windows-gnu target) in v1.0.5+ for cross-platform consistency.
    This matches the approach of zig cc and ensures consistent C++ ABI across platforms.
    Uses MinGW sysroot for headers/libraries.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Command-line arguments

    Returns:
        True if GNU ABI should be used (Windows + GNU target or no explicit target), False otherwise
    """
    # Non-Windows always uses default (which is GNU-like anyway)
    if platform_name != "win":
        return False

    # Check if user explicitly specified a target
    args_str = " ".join(args)
    if "--target=" in args_str or "--target " in args_str:
        # User specified target explicitly
        # Check if it's a GNU/MinGW target (contains "-gnu" or "mingw")
        if "-gnu" in args_str.lower() or "mingw" in args_str.lower():
            logger.debug("User specified GNU/MinGW target, will use GNU ABI")
            return True
        else:
            # MSVC or other target, don't use GNU ABI
            logger.debug("User specified non-GNU target, skipping GNU ABI injection")
            return False

    # Check for MSVC-style linker flags - if present, don't inject GNU ABI
    # These flags indicate the build system is expecting MSVC/lld-link behavior
    # They can appear as: -Wl,/MACHINE: or directly as /MACHINE:
    msvc_linker_patterns = [
        "-Wl,/MACHINE:",
        "-Wl,/OUT:",
        "-Wl,/SUBSYSTEM:",
        "-Wl,/DEBUG",
        "-Wl,/PDB:",
        "-Wl,/NOLOGO",
        "/MACHINE:",
        "/OUT:",
        "/SUBSYSTEM:",
        "/DEBUG",
        "/PDB:",
        "/NOLOGO",
    ]
    if any(pattern in args_str for pattern in msvc_linker_patterns):
        logger.info("MSVC-style linker flags detected in args, skipping GNU ABI injection")
        return False

    # Windows defaults to GNU ABI in v1.0.5+
    logger.debug("Windows detected without explicit target, will use GNU ABI")
    return True


# pyright: reportUnusedFunction=false
def _get_gnu_target_args(platform_name: str, arch: str, args: list[str]) -> list[str]:
    """
    Get GNU ABI target arguments for Windows.

    This function ensures the MinGW sysroot is installed and returns
    the necessary compiler arguments to use GNU ABI instead of MSVC ABI.

    Args:
        platform_name: Platform name
        arch: Architecture
        args: Original command-line arguments (to check if --target already specified)

    Returns:
        List of additional compiler arguments for GNU ABI

    Raises:
        RuntimeError: If MinGW sysroot installation fails or is not found
    """
    # Import here to avoid circular dependency
    from ..wrapper import get_platform_binary_dir

    if platform_name != "win":
        return []

    logger.info(f"Setting up GNU ABI for Windows {arch}")

    # MinGW sysroot is now integrated into the Clang installation (Windows GNU ABI)
    # Get the clang installation root directory
    # This call ensures the toolchain (including MinGW headers) is downloaded with proper locking
    clang_bin_dir = get_platform_binary_dir()
    clang_root = clang_bin_dir.parent

    # Determine target triple and sysroot name based on architecture
    if arch == "x86_64":
        target = "x86_64-w64-windows-gnu"  # Canonical MinGW triple
        sysroot_name = "x86_64-w64-mingw32"
    elif arch == "arm64":
        target = "aarch64-w64-windows-gnu"  # Canonical MinGW triple
        sysroot_name = "aarch64-w64-mingw32"
    else:
        raise ValueError(f"Unsupported architecture for MinGW: {arch}")

    # The sysroot is integrated into the clang installation directory
    sysroot_path = clang_root / sysroot_name
    if not sysroot_path.exists():
        logger.error(f"MinGW sysroot not found at expected location: {sysroot_path}")
        raise RuntimeError(
            f"MinGW sysroot not found in Clang installation: {sysroot_path}\n"
            f"This suggests an incomplete or corrupted installation.\n"
            f"Try purging and reinstalling: clang-tool-chain purge --yes\n"
            f"If this persists, please report at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    # Check if user already specified --target
    args_str = " ".join(args)
    user_specified_target = "--target=" in args_str or "--target " in args_str

    logger.info(f"Using GNU target: {target} with sysroot: {sysroot_path}")

    # NOTE: The -resource-dir flag causes clang 21.1.5 on Windows to hang indefinitely.
    # The integrated archive includes clang resource headers (mm_malloc.h, stddef.h, etc.)
    # in lib/clang/<version>/include directory, which clang finds automatically.
    # MinGW headers are in include/, and sysroot libraries are in <arch>-w64-mingw32/

    # Add -stdlib=libc++ to use the libc++ standard library included in the sysroot
    # Add -fuse-ld=lld to use LLVM's linker instead of system ld (link-time only)
    # Add -rtlib=compiler-rt to use LLVM's compiler-rt instead of libgcc (link-time only)
    # Add --unwindlib=libunwind to use LLVM's libunwind instead of libgcc_s (link-time only)
    # Add -static-libgcc -static-libstdc++ to link runtime libraries statically (link-time only)
    # This avoids DLL dependency issues at runtime

    # Detect if this is a compile-only operation (has -c flag but no linking flags)
    is_compile_only = "-c" in args and not any(arg in args for arg in ["-o", "--output"])
    # Actually, better check: if -c is present, it's compile-only unless there's also a link output
    # The presence of -c means "compile only, don't link"
    is_compile_only = "-c" in args

    # Build the argument list, conditionally including --target if not already specified
    gnu_args = []
    if not user_specified_target:
        gnu_args.append(f"--target={target}")
        logger.debug(f"Adding --target={target} (not specified by user)")
    else:
        logger.debug("User already specified --target, skipping auto-injection")

    # Always add sysroot and stdlib (needed for both compilation and linking)
    #
    # NOTE: We do NOT set -D_LIBCPP_HAS_THREAD_API_PTHREAD here.
    # The Windows LLVM's libc++ __config_site already defines this macro (as 0),
    # indicating it uses Windows native threading rather than pthread.
    # Overriding this causes macro redefinition warnings and conflicts with
    # the upstream LLVM configuration.
    #
    # INCLUDE PATH ORDERING RATIONALE:
    # We carefully order include paths to ensure Clang's headers take precedence over MinGW headers.
    # This prevents GCC-specific headers from interfering with Clang compilation.
    #
    # Search order (high to low priority):
    # 1. libc++ C++ standard library headers (include/c++/v1) - HIGH priority via -I
    # 2. Clang resource headers (lib/clang/*/include) - HIGH priority via -I
    # 3. MinGW platform headers (include/) - SYSTEM priority via -isystem
    # 4. Sysroot libraries and binaries - via --sysroot
    #
    # We use -isystem for MinGW headers (instead of -I) to give them lower search priority.
    # This ensures Clang's intrinsic headers (stddef.h, stdarg.h, etc.) are found first,
    # while still making MinGW platform headers (windows.h, pthread.h) available.
    cxx_include_path = clang_root / "include" / "c++" / "v1"
    mingw_include_path = clang_root / "include"

    # Find the clang resource directory (lib/clang/<version>/include)
    # This contains compiler intrinsic headers like mm_malloc.h, stddef.h, etc.
    clang_lib_dir = clang_root / "lib" / "clang"
    resource_include_path = None
    if clang_lib_dir.exists():
        # Find the version directory (e.g., "19", "21")
        version_dirs = [d for d in clang_lib_dir.iterdir() if d.is_dir()]
        if version_dirs:
            # Use the first (and typically only) version directory
            version_dir = version_dirs[0]
            resource_include_path = version_dir / "include"
            if not resource_include_path.exists():
                resource_include_path = None

    # Build include path arguments in correct priority order
    gnu_args.extend(
        [
            f"--sysroot={sysroot_path}",
            "-stdlib=libc++",
            f"-I{cxx_include_path}",  # 1. libc++ headers (HIGH priority)
        ]
    )

    # Add resource directory if found (needed for both headers and libraries)
    # This sets the base directory for clang's resource files (includes and libs)
    if resource_include_path:
        gnu_args.append(f"-I{resource_include_path}")  # 2. Clang resource headers (HIGH priority)
        logger.debug(f"Added clang resource include path: {resource_include_path}")
        # Also set the resource-dir to point to the correct version directory
        # This is critical for linking with libclang_rt.builtins.a and other runtime libs
        resource_dir = resource_include_path.parent  # lib/clang/<version>/
        gnu_args.append(f"-resource-dir={resource_dir}")
        logger.debug(f"Set resource directory: {resource_dir}")

    # Add MinGW headers with -isystem (SYSTEM priority, lower than -I)
    # This prevents MinGW/GCC headers from overriding Clang's standard headers
    gnu_args.append(f"-isystem{mingw_include_path}")  # 3. MinGW headers (SYSTEM priority)
    logger.debug(f"Added MinGW include path with -isystem: {mingw_include_path}")

    # Only add link-time flags if not compiling only
    if not is_compile_only:
        gnu_args.extend(
            [
                "-rtlib=compiler-rt",
                "-fuse-ld=lld",
                "--unwindlib=libunwind",
                "-static-libgcc",
                "-static-libstdc++",
                "-lpthread",  # Required for pthread functions on Windows MinGW (winpthreads)
            ]
        )
        logger.info("Added link-time flags (not compile-only)")
    else:
        logger.info("Skipping link-time flags (compile-only detected via -c)")

    return gnu_args
