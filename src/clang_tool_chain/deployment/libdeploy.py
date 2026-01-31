"""
Library deployment CLI for deploying runtime dependencies after the fact.

This module provides a command-line interface to deploy library dependencies
for already-built executables and shared libraries. It supports:
- Windows: .exe and .dll files (MinGW runtime DLLs)
- Linux: executables and .so files (libc++, libunwind, etc.)
- macOS: executables and .dylib files (libc++, libunwind, etc.)

Usage:
    clang-tool-chain-libdeploy myprogram.exe
    clang-tool-chain-libdeploy mylib.dll
    clang-tool-chain-libdeploy myprogram
    clang-tool-chain-libdeploy mylib.so
    clang-tool-chain-libdeploy mylib.dylib
"""

import argparse
import logging
import sys
from pathlib import Path

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stderr,
    )
    # Also set the deployment module loggers
    logging.getLogger("clang_tool_chain.deployment").setLevel(level)


def _detect_binary_type(binary_path: Path) -> tuple[str, str]:
    """
    Detect the binary type and platform from file extension and magic bytes.

    Args:
        binary_path: Path to the binary file

    Returns:
        Tuple of (platform, binary_type) where:
        - platform: "windows", "linux", or "darwin"
        - binary_type: "executable" or "shared_library"

    Raises:
        ValueError: If binary type cannot be determined
    """
    suffix = binary_path.suffix.lower()

    # Windows binaries
    if suffix == ".exe":
        return ("windows", "executable")
    if suffix == ".dll":
        return ("windows", "shared_library")

    # macOS binaries
    if suffix == ".dylib":
        return ("darwin", "shared_library")

    # Linux shared libraries (including versioned: .so.1, .so.1.2.3)
    if suffix == ".so" or ".so." in binary_path.name:
        return ("linux", "shared_library")

    # No extension - could be Linux/macOS executable or a .so with version
    # Try to detect from magic bytes
    if binary_path.exists() and binary_path.is_file():
        try:
            with open(binary_path, "rb") as f:
                magic = f.read(4)

            # ELF magic: 0x7f 'E' 'L' 'F'
            if magic[:4] == b"\x7fELF":
                return ("linux", "executable")

            # Mach-O magic numbers
            # MH_MAGIC (32-bit): 0xfeedface
            # MH_MAGIC_64 (64-bit): 0xfeedfacf
            # Fat binary: 0xcafebabe
            if magic[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe"):
                return ("darwin", "executable")
            if magic[:4] == b"\xca\xfe\xba\xbe":
                return ("darwin", "executable")

            # PE magic: 'MZ'
            if magic[:2] == b"MZ":
                return ("windows", "executable")

        except (OSError, PermissionError) as e:
            logger.debug(f"Could not read magic bytes: {e}")

    raise ValueError(
        f"Cannot determine binary type for: {binary_path}\n"
        "Supported formats: .exe, .dll (Windows), .so (Linux), .dylib (macOS), "
        "or ELF/Mach-O executables without extension"
    )


def deploy_dependencies(
    binary_path: Path,
    platform_override: str | None = None,
    arch: str | None = None,
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    """
    Deploy library dependencies for a binary.

    Args:
        binary_path: Path to executable or shared library
        platform_override: Override auto-detected platform ("windows", "linux", "darwin")
        arch: Target architecture (default: auto-detect from current platform)
        verbose: Enable verbose output
        dry_run: If True, only show what would be deployed without actually copying

    Returns:
        Number of libraries deployed, or -1 on error
    """
    from clang_tool_chain.deployment.factory import create_deployer
    from clang_tool_chain.platform.detection import get_platform_info

    # Get architecture if not specified
    if arch is None:
        _, arch = get_platform_info()

    # Detect or use override for platform
    if platform_override:
        platform = platform_override.lower()
        if platform not in ("windows", "linux", "darwin", "win", "win32", "macos"):
            logger.error(f"Invalid platform: {platform_override}")
            return -1
        # Normalize platform names
        if platform in ("win", "win32"):
            platform = "windows"
        elif platform == "macos":
            platform = "darwin"
    else:
        try:
            platform, _ = _detect_binary_type(binary_path)
        except ValueError as e:
            logger.error(str(e))
            return -1

    # Validate binary exists
    if not binary_path.exists():
        logger.error(f"Binary not found: {binary_path}")
        return -1

    if not binary_path.is_file():
        logger.error(f"Not a file: {binary_path}")
        return -1

    # Create appropriate deployer
    deployer = create_deployer(platform, arch)
    if deployer is None:
        logger.error(f"No deployer available for platform: {platform}")
        return -1

    if verbose:
        logger.info(f"Deploying dependencies for: {binary_path}")
        logger.info(f"Platform: {platform}, Architecture: {arch}")

    if dry_run:
        # Dry run - just show what would be deployed
        dependencies = deployer.detect_all_dependencies(binary_path, recursive=True)
        if not dependencies:
            logger.info("No deployable dependencies found")
            return 0

        logger.info(f"Would deploy {len(dependencies)} libraries:")
        for dep in sorted(dependencies):
            src = deployer.find_library_in_toolchain(dep)
            if src:
                logger.info(f"  {dep} <- {src}")
            else:
                logger.info(f"  {dep} (source not found)")
        return len(dependencies)

    # Actually deploy
    try:
        deployed_count = deployer.deploy_all(binary_path)
        if deployed_count == 0 and verbose:
            logger.info("No libraries needed deployment (all up-to-date or none required)")
        return deployed_count
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return -1


def main() -> int:
    """
    Main entry point for clang-tool-chain-libdeploy.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="clang-tool-chain-libdeploy",
        description="Deploy runtime library dependencies for executables and shared libraries",
        epilog="""
Examples:
  clang-tool-chain-libdeploy myprogram.exe          # Windows executable
  clang-tool-chain-libdeploy mylib.dll              # Windows DLL
  clang-tool-chain-libdeploy myprogram              # Linux/macOS executable
  clang-tool-chain-libdeploy mylib.so               # Linux shared library
  clang-tool-chain-libdeploy mylib.dylib            # macOS dynamic library
  clang-tool-chain-libdeploy --dry-run myprogram    # Show what would be deployed

Supported platforms:
  Windows: Deploys MinGW runtime DLLs (libwinpthread, libgcc_s, libstdc++, etc.)
  Linux:   Deploys libc++, libunwind, sanitizer runtimes
  macOS:   Deploys libc++, libunwind, sanitizer runtimes
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "binary",
        type=Path,
        help="Path to executable (.exe) or shared library (.dll, .so, .dylib)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be deployed without copying files",
    )

    parser.add_argument(
        "-p",
        "--platform",
        choices=["windows", "linux", "darwin"],
        help="Override auto-detected platform",
    )

    parser.add_argument(
        "-a",
        "--arch",
        help="Target architecture (default: auto-detect)",
    )

    args = parser.parse_args()

    # Setup logging
    _setup_logging(args.verbose)

    try:
        result = deploy_dependencies(
            binary_path=args.binary.resolve(),
            platform_override=args.platform,
            arch=args.arch,
            verbose=args.verbose,
            dry_run=args.dry_run,
        )

        if result < 0:
            return 1

        if result == 0 and not args.dry_run:
            # No libraries deployed is not necessarily an error
            return 0

        return 0

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)  # NoReturn - re-raises
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
