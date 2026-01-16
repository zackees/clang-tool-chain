"""
LLD linker configuration and flag translation for cross-platform linking.

This module provides functions for:
- Forcing LLVM's lld linker for consistent cross-platform behavior
- Translating GNU ld flags to ld64.lld equivalents on macOS
- Managing linker selection based on platform and user preferences
"""

import logging

logger = logging.getLogger(__name__)


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

    Platform-specific linker flags:
    - macOS: Uses -fuse-ld=ld64.lld (explicit Mach-O variant required by LLVM 21.x+)
    - Linux: Uses -fuse-ld=lld (standard ELF linker)

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
        Modified arguments with platform-specific -fuse-ld flag prepended if needed
    """
    # On macOS, if user explicitly specified LLD, we still need to translate flags
    # even though we don't inject the -fuse-ld flag ourselves
    if platform_name == "darwin" and _user_specified_lld_on_macos(args):
        logger.debug("User specified LLD on macOS, translating GNU ld flags to ld64.lld equivalents")
        return _translate_linker_flags_for_macos_lld(args)

    if not _should_force_lld(platform_name, args):
        return args

    logger.info(f"Forcing lld linker on {platform_name} for cross-platform consistency")

    # On macOS, translate GNU ld flags to ld64.lld equivalents
    if platform_name == "darwin":
        args = _translate_linker_flags_for_macos_lld(args)
        # macOS requires explicit Mach-O linker variant (ld64.lld)
        # LLVM 21.x+ on macOS supports both -fuse-ld=lld and -fuse-ld=ld64.lld
        return ["-fuse-ld=ld64.lld"] + args
    else:
        # Linux uses standard lld
        return ["-fuse-ld=lld"] + args
