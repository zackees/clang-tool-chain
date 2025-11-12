"""
Main entry point for clang-tool-chain CLI.

Provides commands for managing and using the LLVM toolchain.
"""

import argparse
import subprocess
import sys
from typing import NoReturn

from . import sccache_runner, wrapper

try:
    from .__version__ import __version__
except ImportError:
    __version__ = "unknown"


def cmd_info(args: argparse.Namespace) -> int:
    """Display information about the toolchain installation."""
    print("Clang Tool Chain - LLVM/Clang Distribution")
    print("=" * 60)
    print()

    # Platform information
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"Platform:     {platform_name}")
        print(f"Architecture: {arch}")
        print()
    except RuntimeError as e:
        print(f"Error detecting platform: {e}")
        return 1

    # Windows GNU ABI information
    if platform_name == "win":
        print("Windows Target Configuration:")
        print("  Default ABI:  GNU (x86_64-w64-windows-gnu)")
        print("  MSVC ABI:     Available via clang-tool-chain-c-msvc")
        print("                and clang-tool-chain-cpp-msvc")
        print()
        print("Why GNU ABI is default:")
        print("  - Cross-platform consistency (same ABI on Linux/macOS/Windows)")
        print("  - C++11 strict mode support (MSVC headers require C++14+)")
        print("  - Arduino/embedded compatibility (matches GCC toolchain)")
        print()

    # Assets directory
    assets_dir = wrapper.get_assets_dir()
    print(f"Assets directory: {assets_dir}")
    print(f"Assets exist:     {assets_dir.exists()}")
    print()

    # Binary directory
    try:
        bin_dir = wrapper.get_platform_binary_dir()
        print(f"Binary directory: {bin_dir}")
        print("Binaries installed: Yes")
        print()

        # List available tools
        if bin_dir.exists():
            binaries = sorted(
                [f.stem for f in bin_dir.iterdir() if f.is_file()],
                key=str.lower,
            )
            print(f"Available tools ({len(binaries)}):")
            for binary in binaries:
                print(f"  - {binary}")
    except RuntimeError:
        print("Binaries installed: No")
        print()
        print("To install binaries, run:")
        print("  python scripts/download_binaries.py --current-only")
        print("  python scripts/strip_binaries.py <extracted_dir> <output_dir> --platform <platform>")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Display version of a specific tool."""
    tool_name: str = args.tool

    # Map common names to actual tool names
    tool_map = {
        "c": "clang",
        "cpp": "clang++",
        "c++": "clang++",
        "ld": "lld",
    }

    actual_tool: str = tool_map.get(tool_name, tool_name)

    try:
        wrapper.find_tool_binary(actual_tool)
        result = wrapper.run_tool(actual_tool, ["--version"])
        return result
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_list_tools(args: argparse.Namespace) -> int:
    """List all available wrapper tools."""
    print("Available clang-tool-chain commands:")
    print("=" * 60)
    print()

    tools = [
        ("clang-tool-chain-c", "C compiler (clang) - GNU ABI on Windows"),
        ("clang-tool-chain-cpp", "C++ compiler (clang++) - GNU ABI on Windows"),
        ("clang-tool-chain-c-msvc", "C compiler (clang) - MSVC ABI (Windows only)"),
        ("clang-tool-chain-cpp-msvc", "C++ compiler (clang++) - MSVC ABI (Windows only)"),
        ("clang-tool-chain-ld", "LLVM linker (lld/lld-link)"),
        ("clang-tool-chain-ar", "Archive tool (llvm-ar)"),
        ("clang-tool-chain-nm", "Symbol table viewer (llvm-nm)"),
        ("clang-tool-chain-objdump", "Object file dumper (llvm-objdump)"),
        ("clang-tool-chain-objcopy", "Object copying tool (llvm-objcopy)"),
        ("clang-tool-chain-ranlib", "Archive index generator (llvm-ranlib)"),
        ("clang-tool-chain-strip", "Symbol stripper (llvm-strip)"),
        ("clang-tool-chain-readelf", "ELF file reader (llvm-readelf)"),
        ("clang-tool-chain-as", "LLVM assembler (llvm-as)"),
        ("clang-tool-chain-dis", "LLVM disassembler (llvm-dis)"),
        ("clang-tool-chain-format", "Code formatter (clang-format)"),
        ("clang-tool-chain-tidy", "Static analyzer (clang-tidy)"),
    ]

    for cmd, desc in tools:
        print(f"  {cmd:30s} - {desc}")

    print()
    print("sccache integration (requires sccache in PATH):")
    print("=" * 60)
    print()

    sccache_tools = [
        ("clang-tool-chain-sccache", "Direct sccache access (stats, management)"),
        ("clang-tool-chain-sccache-c", "sccache + C compiler (clang)"),
        ("clang-tool-chain-sccache-cpp", "sccache + C++ compiler (clang++)"),
    ]

    for cmd, desc in sccache_tools:
        print(f"  {cmd:30s} - {desc}")

    print()
    print("For more information, run:")
    print("  clang-tool-chain info")

    return 0


def cmd_path(args: argparse.Namespace) -> int:
    """Display the path to the binary directory or a specific tool."""
    try:
        if args.tool:
            tool_name: str = args.tool
            # Map common names to actual tool names
            tool_map = {
                "c": "clang",
                "cpp": "clang++",
                "c++": "clang++",
                "ld": "lld",
            }

            actual_tool: str = tool_map.get(tool_name, tool_name)
            tool_path = wrapper.find_tool_binary(actual_tool)
            print(tool_path)
        else:
            bin_dir = wrapper.get_platform_binary_dir()
            print(bin_dir)
        return 0
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_package_version(args: argparse.Namespace) -> int:
    """Display the package version."""
    print(f"clang-tool-chain version: {__version__}")
    print()

    if args.verbose:
        # Show more detailed version information
        print("Package Information:")
        print("=" * 60)
        print("  Package:       clang-tool-chain")
        print(f"  Version:       {__version__}")
        print()

        # Try to get actual clang version from installed binaries
        try:
            platform_name, arch = wrapper.get_platform_info()
            print("Platform Information:")
            print(f"  Platform:      {platform_name}")
            print(f"  Architecture:  {arch}")
            print()

            # Try to get installed clang version
            try:
                wrapper.find_tool_binary("clang")
                print("Installed LLVM/Clang:")
                result = wrapper.run_tool("clang", ["--version"])
                if result != 0:
                    print("  (Unable to determine version)")
            except RuntimeError:
                print("Installed LLVM/Clang:")
                print("  Not installed yet")
                print()
                print("To install binaries, run:")
                print("  python scripts/download_binaries.py --current-only")
                print("  python scripts/strip_binaries.py <extracted_dir> <output_dir> --platform <platform>")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)

    return 0


def cmd_purge(args: argparse.Namespace) -> int:
    """Remove all downloaded toolchains and cached data."""
    from . import downloader

    toolchain_dir = downloader.get_home_toolchain_dir()

    if not toolchain_dir.exists():
        print(f"No toolchain directory found at: {toolchain_dir}")
        print("Nothing to purge.")
        return 0

    # Show what will be removed
    print("Clang Tool Chain - Purge")
    print("=" * 60)
    print()
    print("This will remove all downloaded toolchains from:")
    print(f"  {toolchain_dir}")
    print()

    # Calculate total size
    try:
        total_size = sum(f.stat().st_size for f in toolchain_dir.rglob("*") if f.is_file())
        total_size_mb = total_size / (1024 * 1024)
        print(f"Total size: {total_size_mb:.2f} MB")
    except Exception:
        print("Total size: (unable to calculate)")

    print()

    # Ask for confirmation unless --yes flag is provided
    if not args.yes:
        response = input("Are you sure you want to remove all toolchains? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            print("Purge cancelled.")
            return 0

    # Remove the directory
    print()
    print("Removing toolchain directory...")
    try:
        downloader._robust_rmtree(toolchain_dir)
        print("✓ Successfully removed all toolchains.")
        print()
        print("Toolchains will be re-downloaded on next use of clang-tool-chain commands.")
        return 0
    except Exception as e:
        print(f"✗ Failed to remove toolchain directory: {e}")
        return 1


def cmd_test(args: argparse.Namespace) -> int:
    """Run diagnostic tests to verify the toolchain installation."""
    import tempfile
    from pathlib import Path

    print("Clang Tool Chain - Diagnostic Tests")
    print("=" * 70)
    print()

    # Test 1: Platform Detection
    print("[1/7] Testing platform detection...")
    try:
        platform_name, arch = wrapper.get_platform_info()
        print(f"      Platform: {platform_name}/{arch}")
        print("      ✓ PASSED")
    except Exception as e:
        print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 2: Toolchain Download/Installation
    print("[2/7] Testing toolchain installation...")
    try:
        bin_dir = wrapper.get_platform_binary_dir()
        if bin_dir.exists():
            print(f"      Binary directory: {bin_dir}")
            print("      ✓ PASSED")
        else:
            print(f"      ✗ FAILED: Binary directory does not exist: {bin_dir}")
            return 1
    except Exception as e:
        print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 3: Finding clang binary
    print("[3/7] Testing binary resolution (clang)...")
    try:
        clang_path = wrapper.find_tool_binary("clang")
        print(f"      Found: {clang_path}")
        if not clang_path.exists():
            print(f"      ✗ FAILED: Binary does not exist: {clang_path}")
            return 1
        print("      ✓ PASSED")
    except Exception as e:
        print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 4: Finding clang++ binary
    print("[4/7] Testing binary resolution (clang++)...")
    try:
        clang_cpp_path = wrapper.find_tool_binary("clang++")
        print(f"      Found: {clang_cpp_path}")
        if not clang_cpp_path.exists():
            print(f"      ✗ FAILED: Binary does not exist: {clang_cpp_path}")
            return 1
        print("      ✓ PASSED")
    except Exception as e:
        print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 5: Version check for clang
    print("[5/7] Testing clang version...")
    try:
        result = subprocess.run([str(clang_path), "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            print(f"      {version_line}")
            print("      ✓ PASSED")
        else:
            print(f"      ✗ FAILED: clang --version returned {result.returncode}")
            print(f"      stderr: {result.stderr}")
            return 1
    except Exception as e:
        print(f"      ✗ FAILED: {e}")
        return 1
    print()

    # Test 6: Simple compilation test
    print("[6/7] Testing C compilation...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_c = tmpdir_path / "test.c"
        test_out = tmpdir_path / "test"
        if platform_name == "win":
            test_out = test_out.with_suffix(".exe")

        # Write simple C program
        test_c.write_text(
            """
#include <stdio.h>
int main() {
    printf("Hello from clang-tool-chain!\\n");
    return 0;
}
"""
        )

        try:
            # Compile
            result = subprocess.run(
                [str(clang_path), str(test_c), "-o", str(test_out)], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print("      ✗ FAILED: Compilation failed")
                print(f"      stdout: {result.stdout}")
                print(f"      stderr: {result.stderr}")
                return 1

            # Verify output file was created
            if not test_out.exists():
                print(f"      ✗ FAILED: Output binary not created: {test_out}")
                return 1

            print(f"      Compiled: {test_out}")
            print("      ✓ PASSED")
        except Exception as e:
            print(f"      ✗ FAILED: {e}")
            return 1
    print()

    # Test 7: Simple C++ compilation test
    print("[7/7] Testing C++ compilation...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_cpp = tmpdir_path / "test.cpp"
        test_out = tmpdir_path / "test"
        if platform_name == "win":
            test_out = test_out.with_suffix(".exe")

        # Write simple C++ program
        test_cpp.write_text(
            """
#include <iostream>
int main() {
    std::cout << "Hello from clang-tool-chain C++!" << std::endl;
    return 0;
}
"""
        )

        try:
            # Compile
            result = subprocess.run(
                [str(clang_cpp_path), str(test_cpp), "-o", str(test_out)], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print("      ✗ FAILED: Compilation failed")
                print(f"      stdout: {result.stdout}")
                print(f"      stderr: {result.stderr}")
                return 1

            # Verify output file was created
            if not test_out.exists():
                print(f"      ✗ FAILED: Output binary not created: {test_out}")
                return 1

            print(f"      Compiled: {test_out}")
            print("      ✓ PASSED")
        except Exception as e:
            print(f"      ✗ FAILED: {e}")
            return 1
    print()

    print("=" * 70)
    print("All tests passed! ✓")
    print()
    return 0


def main() -> int:
    """Main entry point for the clang-tool-chain CLI."""
    parser = argparse.ArgumentParser(
        prog="clang-tool-chain",
        description="LLVM/Clang toolchain management and wrapper utilities",
        epilog="For more information, visit: https://github.com/your-repo/clang-tool-chain",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
    )

    # info command
    parser_info = subparsers.add_parser(
        "info",
        help="Display information about the toolchain installation",
    )
    parser_info.set_defaults(func=cmd_info)

    # version command
    parser_version = subparsers.add_parser(
        "version",
        help="Display version of a specific tool",
    )
    parser_version.add_argument(
        "tool",
        help="Tool name (e.g., clang, clang++, lld)",
    )
    parser_version.set_defaults(func=cmd_version)

    # list-tools command
    parser_list = subparsers.add_parser(
        "list-tools",
        help="List all available wrapper tools",
    )
    parser_list.set_defaults(func=cmd_list_tools)

    # path command
    parser_path = subparsers.add_parser(
        "path",
        help="Display the path to the binary directory or a specific tool",
    )
    parser_path.add_argument(
        "tool",
        nargs="?",
        help="Tool name (optional, prints binary directory if not specified)",
    )
    parser_path.set_defaults(func=cmd_path)

    # package-version command
    parser_pkg_version = subparsers.add_parser(
        "package-version",
        help="Display the package version and target LLVM version",
    )
    parser_pkg_version.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed version information including installed LLVM version",
    )
    parser_pkg_version.set_defaults(func=cmd_package_version)

    # test command
    parser_test = subparsers.add_parser(
        "test",
        help="Run diagnostic tests to verify the toolchain installation",
    )
    parser_test.set_defaults(func=cmd_test)

    # purge command
    parser_purge = subparsers.add_parser(
        "purge",
        help="Remove all downloaded toolchains and cached data",
    )
    parser_purge.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt and remove immediately",
    )
    parser_purge.set_defaults(func=cmd_purge)

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 0

    # Execute command
    return args.func(args)


def test_main() -> int:
    """
    Standalone entry point for the test command.

    This allows running: clang-tool-chain-test
    """
    import argparse

    args = argparse.Namespace()  # Empty namespace
    return cmd_test(args)


def sccache_main() -> int:
    """
    Entry point for direct sccache passthrough command.

    This command allows users to run sccache directly for commands like:
    - clang-tool-chain-sccache --show-stats
    - clang-tool-chain-sccache --zero-stats
    - clang-tool-chain-sccache --start-server
    - clang-tool-chain-sccache --stop-server

    If sccache is not found in PATH, automatically uses iso-env to run it in an isolated environment.
    """
    args = sys.argv[1:]
    return sccache_runner.run_sccache(args)


def sccache_c_main() -> int:
    """
    Entry point for sccache + clang C compiler wrapper.

    This command wraps the clang C compiler with sccache for compilation caching.
    If sccache is not found in PATH, automatically uses iso-env to run it in an isolated environment.
    """
    args = sys.argv[1:]

    # Find the clang binary from clang-tool-chain
    try:
        clang_path = wrapper.find_tool_binary("clang")
    except RuntimeError as e:
        print("=" * 70, file=sys.stderr)
        print("ERROR: Failed to locate clang binary", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    return sccache_runner.run_sccache_with_compiler(str(clang_path), args)


def sccache_cpp_main() -> int:
    """
    Entry point for sccache + clang++ C++ compiler wrapper.

    This command wraps the clang++ C++ compiler with sccache for compilation caching.
    If sccache is not found in PATH, automatically uses iso-env to run it in an isolated environment.
    """
    args = sys.argv[1:]

    # Find the clang++ binary from clang-tool-chain
    try:
        clang_cpp_path = wrapper.find_tool_binary("clang++")
    except RuntimeError as e:
        print("=" * 70, file=sys.stderr)
        print("ERROR: Failed to locate clang++ binary", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    return sccache_runner.run_sccache_with_compiler(str(clang_cpp_path), args)


def sccache_c_msvc_main() -> NoReturn:
    """
    Entry point for sccache + clang C compiler wrapper with MSVC ABI.

    This command wraps the clang C compiler with sccache for compilation caching,
    using MSVC ABI target on Windows.
    """
    wrapper.sccache_clang_main(use_msvc=True)


def sccache_cpp_msvc_main() -> NoReturn:
    """
    Entry point for sccache + clang++ C++ compiler wrapper with MSVC ABI.

    This command wraps the clang++ C++ compiler with sccache for compilation caching,
    using MSVC ABI target on Windows.
    """
    wrapper.sccache_clang_cpp_main(use_msvc=True)


if __name__ == "__main__":
    sys.exit(main())
