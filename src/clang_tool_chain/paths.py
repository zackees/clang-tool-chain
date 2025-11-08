"""
CLI tool for displaying paths to installed toolchain binaries.

This module provides a command-line interface for listing all installed
toolchain binary paths in JSON format.
"""

import json
import sys

from . import downloader, wrapper


def main() -> int:
    """
    Main entry point for clang-tool-chain-paths.

    Outputs JSON with paths to all installed tools.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Get current platform info
        platform, arch = wrapper.get_platform_info()

        # Check if toolchain is installed
        if not downloader.is_toolchain_installed(platform, arch):
            result = {
                "error": "Toolchain not installed",
                "platform": platform,
                "arch": arch,
                "installed": False,
                "install_dir": None,
                "bin_dir": None,
                "tools": {},
            }
            print(json.dumps(result, indent=2))
            return 1

        # Get installation directories
        install_dir = downloader.get_install_dir(platform, arch)
        bin_dir = install_dir / "bin"

        if not bin_dir.exists():
            result = {
                "error": "Binary directory not found",
                "platform": platform,
                "arch": arch,
                "installed": True,
                "install_dir": str(install_dir),
                "bin_dir": str(bin_dir),
                "tools": {},
            }
            print(json.dumps(result, indent=2))
            return 1

        # Enumerate all tools in bin directory
        tools = {}
        for binary_path in sorted(bin_dir.iterdir()):
            if binary_path.is_file():
                tool_name = binary_path.stem  # Remove .exe on Windows
                tools[tool_name] = str(binary_path)

        # Build result
        result = {
            "platform": platform,
            "arch": arch,
            "installed": True,
            "install_dir": str(install_dir),
            "bin_dir": str(bin_dir),
            "tool_count": len(tools),
            "tools": tools,
        }

        # Output as JSON
        print(json.dumps(result, indent=2))
        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        result = {
            "error": str(e),
            "installed": False,
        }
        print(json.dumps(result, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
