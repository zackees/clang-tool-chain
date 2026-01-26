"""
SHA256 checksums for known LLVM releases.

This module provides a database of known SHA256 checksums for LLVM binary releases.
Checksums are used to verify the integrity and authenticity of downloaded binaries.

Note: LLVM releases typically use GPG signatures (.sig files) and GitHub attestations
(.jsonl files) rather than publishing standalone checksum files. The checksums in this
database are computed from verified LLVM releases and can be used for automated
verification during download.

To add checksums for a new release:
1. Download the official binary from https://github.com/llvm/llvm-project/releases
2. Verify the GPG signature or GitHub attestation
3. Compute the SHA256 checksum: `sha256sum <file>` (Linux/macOS) or `certutil -hashfile <file> SHA256` (Windows)
4. Add the checksum to the _RAW_CHECKSUMS dictionary below

Platform keys follow the format: "{os}-{arch}"
- Windows x64: "win-x86_64"
- macOS x64: "mac-x86_64"
- macOS ARM: "mac-arm64"
- Linux x64: "linux-x86_64"
- Linux ARM: "linux-arm64"
"""

from dataclasses import dataclass, field


@dataclass
class PlatformChecksum:
    """
    SHA256 checksum for a specific platform.

    Attributes:
        platform: Platform key in format "{os}-{arch}" (e.g., "linux-x86_64")
        sha256: SHA256 checksum as hex string
    """

    platform: str
    sha256: str


@dataclass
class VersionChecksums:
    """
    All platform checksums for a specific LLVM version.

    Attributes:
        version: LLVM version string (e.g., "21.1.5")
        platforms: Dictionary mapping platform key to PlatformChecksum
    """

    version: str
    platforms: dict[str, PlatformChecksum] = field(default_factory=dict)

    def get_checksum(self, platform: str) -> str | None:
        """Get checksum for a specific platform."""
        checksum_obj = self.platforms.get(platform)
        return checksum_obj.sha256 if checksum_obj else None

    def has_checksum(self, platform: str) -> bool:
        """Check if checksum exists for platform."""
        return platform in self.platforms and bool(self.platforms[platform].sha256)


# Raw database of known SHA256 checksums for LLVM releases (for easier editing)
# Format: {version: {platform: checksum}}
_RAW_CHECKSUMS: dict[str, dict[str, str]] = {
    "21.1.5": {
        # Windows x64 - Full archive (not installer)
        # File: clang+llvm-21.1.5-x86_64-pc-windows-msvc.tar.xz
        # Note: Add checksum after verifying the GPG signature
        # "win-x86_64": "",
        # macOS x64
        # File: clang+llvm-21.1.5-x86_64-apple-darwin.tar.xz
        # Note: May not be available in all releases
        # "mac-x86_64": "",
        # macOS ARM64
        # File: clang+llvm-21.1.5-arm64-apple-darwin.tar.xz
        # Note: May not be available in all releases
        # "mac-arm64": "",
        # Linux x64
        # File: LLVM-21.1.5-Linux-X64.tar.xz
        # Note: Add checksum after verifying the GitHub attestation
        # "linux-x86_64": "",
        # Linux ARM64
        # File: LLVM-21.1.5-Linux-ARM64.tar.xz
        # Note: Add checksum after verifying the GitHub attestation
        # "linux-arm64": "",
    },
    # Additional versions can be added here
    # "21.1.4": {...},
    # "21.1.3": {...},
}

# Convert raw checksums to strongly-typed structure
KNOWN_CHECKSUMS: dict[str, VersionChecksums] = {
    version: VersionChecksums(
        version=version,
        platforms={
            plat: PlatformChecksum(platform=plat, sha256=checksum)
            for plat, checksum in platforms.items()
            if checksum  # Skip empty checksums
        },
    )
    for version, platforms in _RAW_CHECKSUMS.items()
}


def get_checksum(version: str, platform: str) -> str | None:
    """
    Get the known SHA256 checksum for a specific LLVM version and platform.

    Args:
        version: LLVM version string (e.g., "21.1.5")
        platform: Platform key in format "{os}-{arch}" (e.g., "linux-x86_64")

    Returns:
        SHA256 checksum as hex string, or None if not found

    Example:
        >>> get_checksum("21.1.5", "linux-x86_64")
        'abc123...'  # Returns checksum if available, None otherwise
    """
    version_checksums = KNOWN_CHECKSUMS.get(version)
    return version_checksums.get_checksum(platform) if version_checksums else None


def has_checksum(version: str, platform: str) -> bool:
    """
    Check if a checksum is available for a specific version and platform.

    Args:
        version: LLVM version string (e.g., "21.1.5")
        platform: Platform key in format "{os}-{arch}" (e.g., "linux-x86_64")

    Returns:
        True if checksum is available, False otherwise

    Example:
        >>> has_checksum("21.1.5", "linux-x86_64")
        False  # No checksum available yet
    """
    version_checksums = KNOWN_CHECKSUMS.get(version)
    return version_checksums.has_checksum(platform) if version_checksums else False


def get_supported_versions() -> list[str]:
    """
    Get a list of LLVM versions that have checksum information.

    Returns:
        List of version strings

    Example:
        >>> get_supported_versions()
        ['21.1.5']
    """
    return list(KNOWN_CHECKSUMS.keys())


def get_supported_platforms(version: str) -> list[str]:
    """
    Get a list of platforms that have checksums for a specific version.

    Args:
        version: LLVM version string (e.g., "21.1.5")

    Returns:
        List of platform keys, or empty list if version not found

    Example:
        >>> get_supported_platforms("21.1.5")
        []  # No checksums added yet
    """
    version_checksums = KNOWN_CHECKSUMS.get(version)
    if version_checksums is None:
        return []

    return [platform for platform, checksum_obj in version_checksums.platforms.items() if checksum_obj.sha256]


def add_checksum(version: str, platform: str, checksum: str) -> None:
    """
    Add or update a checksum for a specific version and platform.

    This function is primarily for programmatic updates to the checksum database.
    For permanent additions, edit the _RAW_CHECKSUMS dictionary directly.

    Args:
        version: LLVM version string (e.g., "21.1.5")
        platform: Platform key in format "{os}-{arch}" (e.g., "linux-x86_64")
        checksum: SHA256 checksum as hex string

    Example:
        >>> add_checksum("21.1.5", "linux-x86_64", "abc123...")
    """
    if version not in KNOWN_CHECKSUMS:
        KNOWN_CHECKSUMS[version] = VersionChecksums(version=version)

    KNOWN_CHECKSUMS[version].platforms[platform] = PlatformChecksum(platform=platform, sha256=checksum.lower())


def format_platform_key(os_name: str, arch: str) -> str:
    """
    Format an OS name and architecture into a platform key.

    Args:
        os_name: Operating system name ("win", "mac", "linux")
        arch: Architecture name ("x86_64", "arm64", "x86")

    Returns:
        Platform key string

    Example:
        >>> format_platform_key("linux", "x86_64")
        'linux-x86_64'
    """
    # Normalize architecture names
    arch_map = {
        "x86": "x86_64",  # Treat x86 as x86_64 for modern systems
        "x64": "x86_64",
        "amd64": "x86_64",
        "arm": "arm64",  # Treat arm as arm64 for modern systems
        "aarch64": "arm64",
    }
    normalized_arch = arch_map.get(arch.lower(), arch.lower())

    return f"{os_name.lower()}-{normalized_arch}"


# Documentation for adding checksums
CHECKSUM_INSTRUCTIONS = """
How to Add Checksums to the Database
=====================================

1. Download the Official Binary
   - Go to https://github.com/llvm/llvm-project/releases
   - Download the binary for your target platform
   - Example: LLVM-21.1.5-Linux-X64.tar.xz

2. Verify the Official Signature
   For Linux (GitHub attestation):
   ```bash
   gh attestation verify LLVM-21.1.5-Linux-X64.tar.xz --owner llvm
   ```

   For Windows (GPG signature):
   ```bash
   gpg --verify LLVM-21.1.5-win64.exe.sig LLVM-21.1.5-win64.exe
   ```
   (First import LLVM release keys from https://releases.llvm.org/)

3. Compute the SHA256 Checksum
   Linux/macOS:
   ```bash
   sha256sum LLVM-21.1.5-Linux-X64.tar.xz
   ```

   Windows PowerShell:
   ```powershell
   Get-FileHash LLVM-21.1.5-win64.exe -Algorithm SHA256
   ```

   Windows CMD:
   ```cmd
   certutil -hashfile LLVM-21.1.5-win64.exe SHA256
   ```

4. Add to KNOWN_CHECKSUMS Dictionary
   Edit this file and add the checksum:
   ```python
   "21.1.5": {
       "linux-x86_64": "abc123...",  # Your computed checksum
   }
   ```

5. Test the Checksum
   ```bash
   uv run python -c "from clang_tool_chain.checksums import get_checksum; print(get_checksum('21.1.5', 'linux-x86_64'))"
   ```

Platform Keys Reference
=======================
- Windows 64-bit: "win-x86_64"
- macOS Intel:    "mac-x86_64"
- macOS Apple Silicon: "mac-arm64"
- Linux 64-bit:   "linux-x86_64"
- Linux ARM64:    "linux-arm64"

File Naming Conventions
=======================
LLVM uses different naming patterns for releases:

Windows:
- Installer: LLVM-{version}-win64.exe (or win32.exe)
- Archive: clang+llvm-{version}-x86_64-pc-windows-msvc.tar.xz

Linux:
- Archive: LLVM-{version}-Linux-X64.tar.xz (or Linux-ARM64.tar.xz)

macOS (when available):
- Archive: clang+llvm-{version}-x86_64-apple-darwin.tar.xz
- Archive: clang+llvm-{version}-arm64-apple-darwin.tar.xz

Note: macOS binaries are not always available in official releases.
Consider using Homebrew builds or terralang/llvm-build for macOS.
"""


if __name__ == "__main__":
    # Print instructions when run directly
    print(CHECKSUM_INSTRUCTIONS)
    print("\nCurrently Supported Versions:")
    for version in get_supported_versions():
        platforms = get_supported_platforms(version)
        if platforms:
            print(f"  {version}: {', '.join(platforms)}")
        else:
            print(f"  {version}: (no checksums added yet)")
