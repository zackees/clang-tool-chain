"""
CLI tool for fetching clang toolchain binaries.

This module provides a command-line interface for downloading and installing
the LLVM/Clang toolchain binaries.
"""

import argparse
import sys
from dataclasses import dataclass

from . import downloader, wrapper


@dataclass
class FetchConfig:
    """Configuration for fetching toolchain binaries."""

    platform: str | None
    arch: str | None
    output_dir: str | None
    verbose: bool


def parse_args() -> FetchConfig:
    """
    Parse command-line arguments.

    Returns:
        FetchConfig dataclass with parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Fetch and install clang-tool-chain binaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download for current platform
  clang-tool-chain-fetch

  # Download for specific platform (verbose)
  clang-tool-chain-fetch --platform win --arch x86_64 --verbose

  # Download to custom directory
  clang-tool-chain-fetch --output-dir /custom/path --verbose

Environment Variables:
  CLANG_TOOL_CHAIN_DOWNLOAD_PATH  Override default download path (~/.clang-tool-chain)
        """,
    )

    parser.add_argument(
        "--platform",
        choices=["win", "linux", "darwin"],
        help="Target platform (default: current platform)",
    )

    parser.add_argument(
        "--arch",
        choices=["x86_64", "arm64"],
        help="Target architecture (required if --platform is specified, default: current arch)",
    )

    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        help="Output directory for downloads (overrides CLANG_TOOL_CHAIN_DOWNLOAD_PATH)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress information",
    )

    args = parser.parse_args()

    # Validate platform/arch combination
    if args.platform and not args.arch:
        parser.error("--arch is required when --platform is specified")

    return FetchConfig(
        platform=args.platform,
        arch=args.arch,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )


def main() -> int:
    """
    Main entry point for clang-tool-chain-fetch.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        config = parse_args()

        # Determine platform and arch
        if config.platform and config.arch:
            platform = config.platform
            arch = config.arch
        else:
            # Auto-detect current platform
            platform, arch = wrapper.get_platform_info()

        if config.verbose:
            print(f"Platform: {platform}")
            print(f"Architecture: {arch}")

        # Set output directory if specified
        if config.output_dir:
            import os

            os.environ["CLANG_TOOL_CHAIN_DOWNLOAD_PATH"] = config.output_dir
            if config.verbose:
                print(f"Output directory: {config.output_dir}")

        # Download and install
        downloader.ensure_toolchain(platform, arch)

        # Check if download happened or was already installed
        if downloader.is_toolchain_installed(platform, arch):
            install_dir = downloader.get_install_dir(platform, arch)
            bin_dir = install_dir / "bin"

            if config.verbose or not downloader.is_toolchain_installed(platform, arch):
                print("\nToolchain installed successfully!")
                print(f"Install directory: {install_dir}")
                print(f"Binary directory: {bin_dir}")

                # Count binaries
                if bin_dir.exists():
                    bin_count = len(list(bin_dir.iterdir()))
                    print(f"Binaries available: {bin_count}")
            else:
                print(f"Toolchain already installed at: {install_dir}")

            return 0
        else:
            print("ERROR: Toolchain installation failed", file=sys.stderr)
            return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if "--verbose" in sys.argv or "-v" in sys.argv:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
