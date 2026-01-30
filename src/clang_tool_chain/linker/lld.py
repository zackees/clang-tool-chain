"""
LLD linker configuration and flag translation for cross-platform linking.

This module provides functions for:
- Forcing LLVM's lld linker for consistent cross-platform behavior
- Translating GNU ld flags to ld64.lld equivalents on macOS
- Managing linker selection based on platform and user preferences
- Ensuring ld64.lld symlink exists on macOS (runtime fallback)
"""

import logging
import os
import sys

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.llvm_versions import get_llvm_version_tuple, supports_ld64_lld_flag

logger = logging.getLogger(__name__)


def _get_llvm_version_for_platform() -> tuple[int, int, int]:
    """
    Get the LLVM version for the current platform from centralized configuration.

    Returns:
        Tuple of (major, minor, patch) version numbers.
    """
    from ..platform.detection import get_platform_info

    platform_name, _ = get_platform_info()
    return get_llvm_version_tuple(platform_name)


def _llvm_supports_ld64_lld_flag() -> bool:
    """
    Check if the current platform's LLVM version supports -fuse-ld=ld64.lld.

    Note: The clang driver does NOT recognize -fuse-ld=ld64.lld as a valid option.
    This function exists for backward compatibility but always returns False in practice
    because -fuse-ld=lld should be used instead (clang auto-dispatches to ld64.lld on Darwin).

    Returns:
        True if LLVM >= 21.x (but we always fall back to -fuse-ld=lld anyway)
    """
    from ..platform.detection import get_platform_info

    platform_name, _ = get_platform_info()
    supports = supports_ld64_lld_flag(platform_name)
    version = get_llvm_version_tuple(platform_name)
    logger.debug(f"LLVM {version[0]}.x {'supports' if supports else 'does not support'} -fuse-ld=ld64.lld")
    return supports


def _ensure_ld64_lld_symlink() -> bool:
    """
    Ensure the ld64.lld symlink exists on macOS, creating it if needed.

    LLVM's LLD linker uses different binary names for different "personalities":
    - lld: Generic dispatcher
    - ld.lld: ELF linker (Linux)
    - ld64.lld: Mach-O linker (macOS)
    - lld-link: COFF linker (Windows)
    - wasm-ld: WebAssembly linker

    These are typically symlinks to the same `lld` binary, which detects
    the target format from argv[0]. Some LLVM distributions may not include
    ld64.lld, so we create it at runtime if missing.

    The function tries multiple source binaries in order of preference:
    1. lld (generic dispatcher)
    2. ld64 (some macOS distributions use this name)

    Returns:
        True if ld64.lld exists or was created successfully, False otherwise
    """
    from ..platform.detection import get_platform_binary_dir, get_platform_info

    platform_name, _ = get_platform_info()
    if platform_name != "darwin":
        return True  # Only relevant for macOS

    try:
        bin_dir = get_platform_binary_dir()
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.debug(f"Could not get platform binary dir: {e}")
        return False

    ld64_lld_path = bin_dir / "ld64.lld"

    # Check if ld64.lld already exists
    if ld64_lld_path.exists():
        logger.debug(f"ld64.lld already exists at {ld64_lld_path}")
        return True

    # Try multiple source binaries in order of preference
    source_candidates = ["lld", "ld64"]

    for source_name in source_candidates:
        source_path = bin_dir / source_name
        if source_path.exists():
            # Try to create the symlink
            try:
                # Use relative symlink for portability
                os.symlink(source_name, ld64_lld_path)
                logger.info(f"Created ld64.lld symlink: {ld64_lld_path} -> {source_name}")
                return True
            except OSError as e:
                # May fail due to permissions (e.g., read-only filesystem)
                logger.warning(f"Could not create ld64.lld symlink at {ld64_lld_path}: {e}")
                return False

    logger.warning(
        f"No suitable linker binary found for ld64.lld symlink. Tried: {', '.join(source_candidates)} in {bin_dir}"
    )
    return False


def _should_force_lld(platform_name: str, args: list[str]) -> bool:
    """
    Determine if we should force the use of LLVM's lld linker.

    This provides consistent cross-platform behavior by using LLVM's lld
    on supported platforms instead of platform-specific system linkers:
    - macOS: Uses ld64.lld (LLVM's Mach-O linker, requires LLVM 21.x+)
    - Linux: Uses ld.lld (LLVM's ELF linker)
    - Windows: Already uses lld via -fuse-ld=lld in GNU ABI setup

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Command-line arguments

    Returns:
        True if lld should be forced, False otherwise
    """
    # Check if user wants to use system linker
    from ..settings_warnings import warn_use_system_ld

    if warn_use_system_ld():
        logger.debug("CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1, skipping lld injection")
        return False

    # Apply to macOS and Linux (Windows already handled in GNU ABI setup)
    # macOS: Both ARM64 and x86_64 now use LLVM 21.1.6 which supports -fuse-ld flag
    if platform_name not in ("linux", "darwin"):
        return False

    # Check if this is a compile-only operation (no linking)
    if "-c" in args:
        return False

    # Check if user already specified a linker
    args_str = " ".join(args)
    if "-fuse-ld=" in args_str:
        logger.debug("User specified -fuse-ld, skipping lld injection")
        return False

    # Check for MSVC-style linker flags (incompatible with GNU lld)
    # MSVC uses lld-link which expects /MACHINE:, /OUT:, /SUBSYSTEM:, etc.
    # GNU lld expects --target=, -o, etc.
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
        logger.info("MSVC-style linker flags detected, skipping lld injection (will use lld-link)")
        return False

    # Force lld for consistent cross-platform linking
    return True


def _translate_linker_flags_for_macos_lld(args: list[str]) -> list[str]:
    """
    Translate GNU ld linker flags to ld64.lld equivalents for macOS.

    When using lld on macOS (ld64.lld), certain GNU ld flags need to be
    translated to their Mach-O equivalents:
    - --no-undefined -> -undefined error
    - --fatal-warnings -> -fatal_warnings
    - More translations can be added as needed

    This function processes both direct linker flags and flags passed via -Wl,

    Args:
        args: Original compiler arguments

    Returns:
        Modified arguments with translated linker flags
    """
    # Map of GNU ld flags to ld64.lld equivalents
    flag_translations = {
        "--no-undefined": "-undefined error",
        "--fatal-warnings": "-fatal_warnings",
        # Add more translations as needed
    }

    result = []
    i = 0
    while i < len(args):
        arg = args[i]

        # Handle -Wl, prefixed flags (comma-separated linker flags)
        if arg.startswith("-Wl,"):
            # Split by comma to get individual linker flags
            linker_flags = arg[4:].split(",")
            translated_flags = []

            for flag in linker_flags:
                # Check if this flag needs translation
                if flag in flag_translations:
                    # Translate the flag (may result in multiple flags)
                    translated = flag_translations[flag]
                    if " " in translated:
                        # Multiple flags (e.g., "-undefined error")
                        translated_flags.extend(translated.split())
                    else:
                        translated_flags.append(translated)
                    logger.debug(f"Translated linker flag: {flag} -> {translated}")
                else:
                    translated_flags.append(flag)

            # Rejoin with commas
            if translated_flags:
                result.append("-Wl," + ",".join(translated_flags))

        # Handle standalone linker flags passed directly
        elif arg in flag_translations:
            translated = flag_translations[arg]
            logger.debug(f"Translated linker flag: {arg} -> {translated}")
            # Add via -Wl, to pass to linker
            if " " in translated:
                # Multiple flags
                result.append("-Wl," + ",".join(translated.split()))
            else:
                result.append("-Wl," + translated)

        else:
            result.append(arg)

        i += 1

    return result


def _user_specified_lld_on_macos(args: list[str]) -> bool:
    """
    Check if the user explicitly specified LLD linker on macOS.

    This detects when the user passes -fuse-ld=lld or -fuse-ld=ld64.lld,
    which means they want to use ld64.lld and we should translate GNU flags.

    Args:
        args: Command-line arguments

    Returns:
        True if user explicitly specified LLD linker
    """
    args_str = " ".join(args)
    # Check for explicit LLD specification (both generic and macOS-specific variants)
    return "-fuse-ld=lld" in args_str or "-fuse-ld=ld64.lld" in args_str


def _user_specified_ld64_lld(args: list[str]) -> bool:
    """
    Check if the user explicitly specified -fuse-ld=ld64.lld.

    This is used to emit a warning that the flag will be auto-converted
    to -fuse-ld=lld since clang driver doesn't recognize ld64.lld.

    Args:
        args: Command-line arguments

    Returns:
        True if user specified -fuse-ld=ld64.lld
    """
    return any("-fuse-ld=ld64.lld" in arg for arg in args)


def _convert_ld64_lld_to_lld(args: list[str]) -> list[str]:
    """
    Convert -fuse-ld=ld64.lld to -fuse-ld=lld in arguments.

    The clang driver does not recognize -fuse-ld=ld64.lld as a valid option.
    This function converts it to -fuse-ld=lld which the driver recognizes
    and automatically dispatches to ld64.lld on Darwin targets.

    Args:
        args: Original compiler arguments

    Returns:
        Modified arguments with -fuse-ld=ld64.lld replaced by -fuse-ld=lld
    """
    return [arg.replace("-fuse-ld=ld64.lld", "-fuse-ld=lld") for arg in args]


# pyright: reportUnusedFunction=false
def _add_lld_linker_if_needed(platform_name: str, args: list[str]) -> list[str]:
    """
    Add platform-specific lld linker flag for macOS and Linux if needed.

    This forces the use of LLVM's lld linker instead of platform-specific
    system linkers (ld64 on macOS, GNU ld on Linux). This provides:
    - Consistent cross-platform behavior
    - Better support for GNU-style linker flags
    - Faster linking performance
    - Uniform toolchain across all platforms

    Platform-specific behavior:
    - Uses -fuse-ld=lld on all platforms (clang driver auto-dispatches)
    - macOS: Clang driver finds ld64.lld (Mach-O linker)
    - Linux: Clang driver finds ld.lld (ELF linker)

    The function is skipped when:
    - User sets CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1
    - User already specified -fuse-ld= in arguments (but flag translation still applies on macOS)
    - Compile-only operation (-c flag present)
    - Platform is Windows (already handled separately)

    On macOS, this function also translates GNU ld flags to ld64.lld equivalents,
    even when the user explicitly specifies -fuse-ld=lld or -fuse-ld=ld64.lld.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Original compiler arguments

    Returns:
        Modified arguments with -fuse-ld=lld flag prepended if needed
    """
    # On macOS, if user explicitly specified LLD, we still need to translate flags
    # and ensure ld64.lld symlink exists, even though we don't inject the -fuse-ld flag ourselves
    if platform_name == "darwin" and _user_specified_lld_on_macos(args):
        logger.debug("User specified LLD on macOS, translating GNU ld flags to ld64.lld equivalents")
        # Ensure ld64.lld symlink exists for lld to dispatch to Mach-O mode
        _ensure_ld64_lld_symlink()

        # Check if user specified -fuse-ld=ld64.lld (which is not a valid clang driver option)
        # and emit a warning about the auto-conversion to -fuse-ld=lld
        if _user_specified_ld64_lld(args):
            print(
                "[clang-tool-chain] Warning: -fuse-ld=ld64.lld is not a valid clang driver option. "
                "Auto-converting to -fuse-ld=lld (clang driver auto-dispatches to ld64.lld on Darwin).",
                file=sys.stderr,
            )
            args = _convert_ld64_lld_to_lld(args)

        return _translate_linker_flags_for_macos_lld(args)

    if not _should_force_lld(platform_name, args):
        return args

    logger.info(f"Forcing lld linker on {platform_name} for cross-platform consistency")

    # On macOS, translate GNU ld flags to ld64.lld equivalents
    if platform_name == "darwin":
        args = _translate_linker_flags_for_macos_lld(args)
        # Ensure ld64.lld symlink exists for lld to dispatch to Mach-O mode
        _ensure_ld64_lld_symlink()

    # Always use -fuse-ld=lld on all platforms.
    # Note: -fuse-ld=ld64.lld is NOT a valid clang driver option.
    # The clang driver only recognizes generic names like "lld", "gold", "bfd".
    # When -fuse-ld=lld is used, clang automatically dispatches to:
    # - Darwin: ld64.lld (Mach-O linker)
    # - Linux: ld.lld (ELF linker)
    return ["-fuse-ld=lld"] + args
