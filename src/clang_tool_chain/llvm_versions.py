"""
Centralized LLVM version configuration for clang-tool-chain.

This module provides a single source of truth for LLVM versions used by the toolchain.
When updating LLVM versions, only this file needs to be modified.

Version history:
- 21.1.6: macOS (darwin) x86_64 and arm64
- 21.1.5: Windows x86_64, Linux x86_64 and arm64
"""

from typing import NamedTuple


class LLVMVersion(NamedTuple):
    """LLVM version as a tuple of (major, minor, patch)."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def from_string(cls, version_str: str) -> "LLVMVersion":
        """Parse a version string like '21.1.6' into an LLVMVersion."""
        parts = version_str.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version string: {version_str}")
        return cls(int(parts[0]), int(parts[1]), int(parts[2]))


# Centralized LLVM version configuration by platform
# Format: {platform_name: LLVMVersion}
# Platform names match detection.py: "darwin", "linux", "win"
LLVM_VERSIONS: dict[str, LLVMVersion] = {
    "darwin": LLVMVersion(21, 1, 6),  # macOS x86_64 and arm64
    "linux": LLVMVersion(21, 1, 5),  # Linux x86_64 and arm64
    "win": LLVMVersion(21, 1, 5),  # Windows x86_64
}

# Default version when platform is unknown (should not happen in practice)
DEFAULT_LLVM_VERSION = LLVMVersion(21, 1, 5)


def get_llvm_version(platform_name: str) -> LLVMVersion:
    """
    Get the LLVM version for a specific platform.

    Args:
        platform_name: Platform name ("darwin", "linux", "win")

    Returns:
        LLVMVersion tuple for the platform
    """
    return LLVM_VERSIONS.get(platform_name, DEFAULT_LLVM_VERSION)


def get_llvm_version_string(platform_name: str) -> str:
    """
    Get the LLVM version string for a specific platform.

    Args:
        platform_name: Platform name ("darwin", "linux", "win")

    Returns:
        Version string like "21.1.6"
    """
    return str(get_llvm_version(platform_name))


def get_llvm_version_tuple(platform_name: str) -> tuple[int, int, int]:
    """
    Get the LLVM version as a tuple for a specific platform.

    Args:
        platform_name: Platform name ("darwin", "linux", "win")

    Returns:
        Version tuple like (21, 1, 6)
    """
    version = get_llvm_version(platform_name)
    return (version.major, version.minor, version.patch)


def supports_ld64_lld_flag(platform_name: str) -> bool:
    """
    Check if the platform's LLVM version supports -fuse-ld=ld64.lld.

    The -fuse-ld=ld64.lld flag is only recognized by LLVM 21.x and later.
    Earlier versions require -fuse-ld=lld (which auto-detects Mach-O from target).

    Args:
        platform_name: Platform name ("darwin", "linux", "win")

    Returns:
        True if LLVM >= 21.x, False otherwise
    """
    version = get_llvm_version(platform_name)
    return version.major >= 21
