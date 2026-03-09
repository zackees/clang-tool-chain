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
    # Extract only the target value, not all args (BUG-005: avoid matching filenames like test-gnu.c)
    target_value = ""
    for i, arg in enumerate(args):
        if arg.startswith("--target="):
            target_value = arg[len("--target=") :]
            break
        elif arg == "--target" and i + 1 < len(args):
            target_value = args[i + 1]
            break
    if target_value:
        # User specified target explicitly — check only the target value
        lower_target = target_value.lower()
        if "-gnu" in lower_target or "mingw" in lower_target:
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
    if any(pattern in arg for arg in args for pattern in msvc_linker_patterns):
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

    # Check if user already specified --target (check actual args, not joined string)
    user_specified_target = any(arg.startswith("--target=") or arg == "--target" for arg in args)

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

    # Detect if this is a compile-only operation: -c, -S, or -E all skip linking
    is_compile_only = "-c" in args or "-S" in args or "-E" in args

    # Build the argument list, conditionally including --target if not already specified
    gnu_args = []
    if not user_specified_target:
        gnu_args.append(f"--target={target}")
        logger.debug(f"Adding --target={target} (not specified by user)")
    else:
        logger.debug("User already specified --target, skipping auto-injection")

    # Always add sysroot and stdlib (needed for both compilation and linking)
    gnu_args.extend(
        [
            f"--sysroot={sysroot_path}",
            "-stdlib=libc++",
        ]
    )

    # Include paths: skip when -nostdinc or -ffreestanding (user wants no system headers)
    has_nostdinc = "-nostdinc" in args or "-nostdinc++" in args
    has_ffreestanding = "-ffreestanding" in args
    if not has_nostdinc and not has_ffreestanding:
        # libc++ headers are not in the sysroot, so we must add them explicitly
        cxx_include_path = clang_root / "include" / "c++" / "v1"
        gnu_args.append(f"-I{cxx_include_path}")
        # NOTE: Do NOT add -I<resource_include> or -resource-dir here.
        # Clang auto-detects resource dir from its binary location and adds
        # -internal-isystem for resource headers automatically. See BUG-001 in BUG.md.
        # MinGW headers use -isystem for lower priority than clang's intrinsic headers
        mingw_include_path = clang_root / "include"
        gnu_args.append(f"-isystem{mingw_include_path}")

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
