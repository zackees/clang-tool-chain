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
    - macOS: Uses system ld64 (temporarily disabled - ARM64 on 21.1.6 ready, x86_64 on 19.1.7 not ready)
    - Linux: lld instead of GNU ld
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

    # TEMPORARY: Disable LLD on macOS due to mixed LLVM versions across architectures
    # - macOS ARM64: LLVM 21.1.6 (supports -fuse-ld flag) ✅
    # - macOS x86_64: LLVM 19.1.7 (doesn't support -fuse-ld flag) ❌
    # Cannot enable lld until both architectures support it to maintain consistent behavior
    # This causes compilation failures on x86_64 with: "clang: error: invalid linker name in argument '-fuse-ld=...'"
    # TODO: Re-enable when x86_64 upgrades to LLVM 21.x+ (blocked: no pre-built binary available)
    if platform_name == "darwin":
        logger.info("Skipping lld on macOS (x86_64 LLVM 19.1.7 doesn't support -fuse-ld flag)")
        return False

    # Only apply to Linux (macOS disabled above, Windows already handled in GNU ABI setup)
    if platform_name not in ("linux",):
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
    - macOS: Uses -fuse-ld=ld64.lld (explicit Mach-O variant required by LLVM 19.1.7+)
    - Linux: Uses -fuse-ld=lld (standard ELF linker)

    The function is skipped when:
    - User sets CLANG_TOOL_CHAIN_USE_SYSTEM_LD=1
    - User already specified -fuse-ld= in arguments
    - Compile-only operation (-c flag present)
    - Platform is Windows (already handled separately)

    On macOS, this function also translates GNU ld flags to ld64.lld equivalents.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Original compiler arguments

    Returns:
        Modified arguments with platform-specific -fuse-ld flag prepended if needed
    """
    if not _should_force_lld(platform_name, args):
        return args

    logger.info(f"Forcing lld linker on {platform_name} for cross-platform consistency")

    # On macOS, translate GNU ld flags to ld64.lld equivalents
    if platform_name == "darwin":
        args = _translate_linker_flags_for_macos_lld(args)
        # macOS requires explicit Mach-O linker variant (ld64.lld)
        # LLVM 19.1.7+ on macOS doesn't recognize generic "-fuse-ld=lld"
        return ["-fuse-ld=ld64.lld"] + args
    else:
        # Linux uses standard lld
        return ["-fuse-ld=lld"] + args
