"""
Wrapper infrastructure for executing LLVM/Clang tools.

This module provides the core functionality for wrapping LLVM toolchain
binaries and forwarding commands to them with proper platform detection.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from . import downloader


def _get_toolchain_directory_listing(platform_name: str) -> str:
    """
    Get a directory listing of ~/.clang-tool-chain for debugging purposes.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")

    Returns:
        Formatted directory listing string (2 levels deep)
    """
    import subprocess as _subprocess

    toolchain_dir = Path.home() / ".clang-tool-chain"

    try:
        if platform_name == "win":
            # On Windows, manually walk the directory tree (2 levels)
            lines = []
            if toolchain_dir.exists():
                lines.append(str(toolchain_dir))
                for item in toolchain_dir.iterdir():
                    lines.append(f"  {item.name}")
                    if item.is_dir():
                        try:
                            for subitem in item.iterdir():
                                lines.append(f"    {item.name}/{subitem.name}")
                        except (PermissionError, OSError):
                            pass
            return "\n".join(lines)
        else:
            # On Unix, use find
            result = _subprocess.run(
                ["find", str(toolchain_dir), "-maxdepth", "2"], capture_output=True, text=True, timeout=5
            )
            return result.stdout
    except Exception as e:
        return f"Could not list directory: {e}"


def get_platform_info() -> tuple[str, str]:
    """
    Detect the current platform and architecture.

    Returns:
        Tuple of (platform, architecture) strings
        Platform: "win", "linux", or "darwin"
        Architecture: "x86_64" or "aarch64"
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize platform name
    if system == "windows":
        platform_name = "win"
    elif system == "linux":
        platform_name = "linux"
    elif system == "darwin":
        platform_name = "darwin"
    else:
        raise RuntimeError(
            f"Unsupported platform: {system}\n"
            f"clang-tool-chain currently supports: Windows, Linux, and macOS (Darwin)\n"
            f"Your system: {system}\n"
            f"If you believe this platform should be supported, please report this at:\n"
            f"https://github.com/yourusername/clang-tool-chain/issues"
        )

    # Normalize architecture
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        raise RuntimeError(
            f"Unsupported architecture: {machine}\n"
            f"clang-tool-chain currently supports: x86_64 (AMD64) and ARM64\n"
            f"Your architecture: {machine}\n"
            f"Supported architectures:\n"
            f"  - x86_64, amd64 (Intel/AMD 64-bit)\n"
            f"  - aarch64, arm64 (ARM 64-bit)\n"
            f"If you believe this architecture should be supported, please report this at:\n"
            f"https://github.com/yourusername/clang-tool-chain/issues"
        )

    return platform_name, arch


def get_assets_dir() -> Path:
    """
    Get the path to the assets directory containing LLVM binaries.

    Returns:
        Path to the assets directory
    """
    # Get the package directory
    package_dir = Path(__file__).parent

    # Assets should be in the project root (two levels up from package)
    project_root = package_dir.parent.parent
    assets_dir = project_root / "assets"

    return assets_dir


def get_platform_binary_dir() -> Path:
    """
    Get the directory containing binaries for the current platform.

    This function ensures the toolchain is downloaded before returning the path.

    Returns:
        Path to the platform-specific binary directory

    Raises:
        RuntimeError: If the platform is not supported or binaries cannot be installed
    """
    platform_name, arch = get_platform_info()

    # Ensure toolchain is downloaded and installed
    downloader.ensure_toolchain(platform_name, arch)

    # Get the installation directory
    install_dir = downloader.get_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"

    if not bin_dir.exists():
        # Get directory listing for debugging
        dir_listing = _get_toolchain_directory_listing(platform_name)

        raise RuntimeError(
            f"Binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"Directory structure of ~/.clang-tool-chain (2 levels deep):\n"
            f"{dir_listing}\n"
            f"\n"
            f"The toolchain download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    return bin_dir


def find_tool_binary(tool_name: str) -> Path:
    """
    Find the path to a specific tool binary.

    Args:
        tool_name: Name of the tool (e.g., "clang", "llvm-ar")

    Returns:
        Path to the tool binary

    Raises:
        RuntimeError: If the tool binary is not found
    """
    bin_dir = get_platform_binary_dir()
    platform_name, _ = get_platform_info()

    # Add .exe extension on Windows
    tool_path = bin_dir / f"{tool_name}.exe" if platform_name == "win" else bin_dir / tool_name

    if not tool_path.exists():
        # Try alternative names for some tools
        alternatives = {
            "lld": ["lld-link", "ld.lld"],
            "lld-link": ["lld", "ld.lld"],
            "ld.lld": ["lld", "lld-link"],
        }

        if tool_name in alternatives:
            for alt_name in alternatives[tool_name]:
                alt_path = bin_dir / f"{alt_name}.exe" if platform_name == "win" else bin_dir / alt_name

                if alt_path.exists():
                    return alt_path

        # List available tools
        available_tools = [f.stem for f in bin_dir.iterdir() if f.is_file()]

        # Get directory listing for debugging
        dir_listing = _get_toolchain_directory_listing(platform_name)

        raise RuntimeError(
            f"Tool '{tool_name}' not found\n"
            f"Expected location: {tool_path}\n"
            f"\n"
            f"This tool may not be included in your LLVM installation.\n"
            f"\n"
            f"Available tools in {bin_dir.name}/:\n"
            f"  {', '.join(sorted(available_tools)[:20])}\n"
            f"  {'... and more' if len(available_tools) > 20 else ''}\n"
            f"\n"
            f"Directory structure of ~/.clang-tool-chain (2 levels deep):\n"
            f"{dir_listing}\n"
            f"\n"
            f"Troubleshooting:\n"
            f"  - Verify the tool name is correct\n"
            f"  - Check if the tool is part of LLVM {tool_name}\n"
            f"  - Re-download binaries: python scripts/download_binaries.py\n"
            f"  - Report issue: https://github.com/yourusername/clang-tool-chain/issues"
        )

    return tool_path


def find_sccache_binary() -> str:
    """
    Find the sccache binary in PATH.

    Returns:
        Path to the sccache binary

    Raises:
        RuntimeError: If sccache is not found in PATH
    """
    sccache_path = shutil.which("sccache")

    if sccache_path is None:
        raise RuntimeError(
            "sccache not found in PATH\n"
            "\n"
            "sccache is required to use the sccache wrapper commands.\n"
            "\n"
            "Installation options:\n"
            "  - pip install clang-tool-chain[sccache]\n"
            "  - cargo install sccache\n"
            "  - Download from: https://github.com/mozilla/sccache/releases\n"
            "  - Linux: apt install sccache / yum install sccache\n"
            "  - macOS: brew install sccache\n"
            "\n"
            "After installation, ensure sccache is in your PATH.\n"
            "Verify with: sccache --version"
        )

    return sccache_path


def _add_macos_sysroot_if_needed(args: list[str]) -> list[str]:
    """
    Add -isysroot flag for macOS if needed to find system headers.

    This function automatically detects the macOS SDK path and adds it to
    the compiler arguments, unless:
    - User has disabled it via CLANG_TOOL_CHAIN_NO_SYSROOT=1
    - User has already specified -isysroot in the arguments
    - SDKROOT environment variable is set (will be used by clang automatically)
    - User specified flags indicating freestanding/no stdlib compilation:
      -nostdinc, -nostdinc++, -nostdlib, -ffreestanding

    Args:
        args: Original compiler arguments

    Returns:
        Modified arguments with -isysroot prepended if needed
    """
    # Check if user wants to disable automatic sysroot
    if os.environ.get("CLANG_TOOL_CHAIN_NO_SYSROOT") == "1":
        return args

    # Check if SDKROOT is already set (standard macOS environment variable)
    if "SDKROOT" in os.environ:
        return args

    # Check if user already specified -isysroot
    if "-isysroot" in args:
        return args

    # Check for flags that indicate freestanding or no-stdlib compilation
    # In these cases, the user explicitly doesn't want system headers/libraries
    no_sysroot_flags = {"-nostdinc", "-nostdinc++", "-nostdlib", "-ffreestanding"}
    if any(flag in args for flag in no_sysroot_flags):
        return args

    # Try to detect the SDK path using xcrun
    try:
        result = subprocess.run(
            ["xcrun", "--show-sdk-path"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sdk_path = result.stdout.strip()

        if sdk_path and Path(sdk_path).exists():
            # Prepend -isysroot to arguments
            return ["-isysroot", sdk_path] + args
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        # If xcrun fails, just continue without adding -isysroot
        # This allows the tool to work even if Command Line Tools aren't installed,
        # though compilation may fail if system headers are needed
        pass

    return args


def execute_tool(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute a tool with the given arguments and exit with its return code.

    This function does not return - it replaces the current process with
    the tool process (on Unix) or exits with the tool's return code (on Windows).

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool (defaults to sys.argv[1:])

    Raises:
        RuntimeError: If the tool cannot be found or executed

    Environment Variables (macOS only):
        SDKROOT: Custom SDK path to use (standard macOS variable)
        CLANG_TOOL_CHAIN_NO_SYSROOT: Set to '1' to disable automatic -isysroot injection
    """
    if args is None:
        args = sys.argv[1:]

    try:
        tool_path = find_tool_binary(tool_name)
    except RuntimeError as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Add macOS SDK path automatically for clang/clang++ if not already specified
    platform_name, _ = get_platform_info()
    if platform_name == "darwin" and tool_name in ("clang", "clang++"):
        args = _add_macos_sysroot_if_needed(args)

    # Build command
    cmd = [str(tool_path)] + args

    # On Unix systems, we can use exec to replace the current process
    # On Windows, we need to use subprocess and exit with the return code
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        # Windows: use subprocess
        try:
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except FileNotFoundError:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Tool not found: {tool_path}", file=sys.stderr)
            print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
            print("This may be a permission or compatibility issue.", file=sys.stderr)
            print("\nTroubleshooting:", file=sys.stderr)
            print("  - Verify the binary is compatible with your Windows version", file=sys.stderr)
            print("  - Check Windows Defender or antivirus isn't blocking it", file=sys.stderr)
            print("  - Report issue: https://github.com/yourusername/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing tool: {e}", file=sys.stderr)
            print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
            print(f"Arguments: {args}", file=sys.stderr)
            print("\nPlease report this issue at:", file=sys.stderr)
            print("https://github.com/yourusername/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        # Unix: use exec to replace current process
        try:
            os.execv(str(tool_path), cmd)
        except FileNotFoundError:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Tool not found: {tool_path}", file=sys.stderr)
            print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
            print("This may be a permission or compatibility issue.", file=sys.stderr)
            print("\nTroubleshooting:", file=sys.stderr)
            print(f"  - Check file permissions: chmod +x {tool_path}", file=sys.stderr)
            print("  - Verify the binary is compatible with your system", file=sys.stderr)
            print("  - On macOS: Right-click > Open, then allow in Security settings", file=sys.stderr)
            print("  - Report issue: https://github.com/yourusername/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing tool: {e}", file=sys.stderr)
            print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
            print(f"Arguments: {args}", file=sys.stderr)
            print("\nPlease report this issue at:", file=sys.stderr)
            print("https://github.com/yourusername/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)


def run_tool(tool_name: str, args: list[str] | None = None) -> int:
    """
    Run a tool with the given arguments and return its exit code.

    Unlike execute_tool, this function returns to the caller with the
    tool's exit code instead of exiting the process.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool (defaults to sys.argv[1:])

    Returns:
        Exit code from the tool

    Raises:
        RuntimeError: If the tool cannot be found
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_tool_binary(tool_name)

    # Build command
    cmd = [str(tool_path)] + args

    # Run the tool
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError as err:
        raise RuntimeError(f"Tool not found: {tool_path}") from err
    except Exception as e:
        raise RuntimeError(f"Error executing tool: {e}") from e


# Wrapper functions for specific tools
def clang_main() -> NoReturn:
    """Entry point for clang wrapper."""
    execute_tool("clang")


def clang_cpp_main() -> NoReturn:
    """Entry point for clang++ wrapper."""
    execute_tool("clang++")


def lld_main() -> NoReturn:
    """Entry point for lld linker wrapper."""
    platform_name, _ = get_platform_info()
    if platform_name == "win":
        execute_tool("lld-link")
    else:
        execute_tool("lld")


def llvm_ar_main() -> NoReturn:
    """Entry point for llvm-ar wrapper."""
    execute_tool("llvm-ar")


def llvm_nm_main() -> NoReturn:
    """Entry point for llvm-nm wrapper."""
    execute_tool("llvm-nm")


def llvm_objdump_main() -> NoReturn:
    """Entry point for llvm-objdump wrapper."""
    execute_tool("llvm-objdump")


def llvm_objcopy_main() -> NoReturn:
    """Entry point for llvm-objcopy wrapper."""
    execute_tool("llvm-objcopy")


def llvm_ranlib_main() -> NoReturn:
    """Entry point for llvm-ranlib wrapper."""
    execute_tool("llvm-ranlib")


def llvm_strip_main() -> NoReturn:
    """Entry point for llvm-strip wrapper."""
    execute_tool("llvm-strip")


def llvm_readelf_main() -> NoReturn:
    """Entry point for llvm-readelf wrapper."""
    execute_tool("llvm-readelf")


def llvm_as_main() -> NoReturn:
    """Entry point for llvm-as wrapper."""
    execute_tool("llvm-as")


def llvm_dis_main() -> NoReturn:
    """Entry point for llvm-dis wrapper."""
    execute_tool("llvm-dis")


def clang_format_main() -> NoReturn:
    """Entry point for clang-format wrapper."""
    execute_tool("clang-format")


def clang_tidy_main() -> NoReturn:
    """Entry point for clang-tidy wrapper."""
    execute_tool("clang-tidy")


def build_main() -> NoReturn:
    """
    Entry point for build wrapper.

    Simple build utility that compiles and links a C/C++ source file to an executable.

    Usage:
        clang-tool-chain-build <source_file> <output_file> [additional_args...]

    Examples:
        clang-tool-chain-build main.cpp main.exe
        clang-tool-chain-build main.c main -O2
        clang-tool-chain-build main.cpp app.exe -std=c++17 -Wall
    """
    args = sys.argv[1:]

    if len(args) < 2:
        print("\n" + "=" * 60, file=sys.stderr)
        print("clang-tool-chain-build - Build Utility", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("Usage: clang-tool-chain-build <source_file> <output_file> [compiler_flags...]", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  clang-tool-chain-build main.cpp main.exe", file=sys.stderr)
        print("  clang-tool-chain-build main.c main -O2", file=sys.stderr)
        print("  clang-tool-chain-build main.cpp app.exe -std=c++17 -Wall", file=sys.stderr)
        print("\nArguments:", file=sys.stderr)
        print("  source_file     - C/C++ source file to compile (.c, .cpp, .cc, .cxx)", file=sys.stderr)
        print("  output_file     - Output executable file", file=sys.stderr)
        print("  compiler_flags  - Optional additional compiler flags", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
        sys.exit(1)

    source_file = args[0]
    output_file = args[1]
    additional_flags = args[2:] if len(args) > 2 else []

    # Determine if this is C or C++ based on file extension
    source_path = Path(source_file)
    cpp_extensions = {".cpp", ".cc", ".cxx", ".C", ".c++"}
    is_cpp = source_path.suffix.lower() in cpp_extensions

    # Choose the appropriate compiler
    compiler = "clang++" if is_cpp else "clang"

    # Build the compiler command
    compiler_args = [source_file, "-o", output_file] + additional_flags

    # Execute the compiler
    execute_tool(compiler, compiler_args)


# sccache wrapper functions
def sccache_clang_main() -> NoReturn:
    """Entry point for sccache + clang wrapper."""
    args = sys.argv[1:]

    try:
        sccache_path = find_sccache_binary()
        clang_path = find_tool_binary("clang")
    except RuntimeError as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Add macOS SDK path automatically if needed
    platform_name, _ = get_platform_info()
    if platform_name == "darwin":
        args = _add_macos_sysroot_if_needed(args)

    # Build command: sccache <clang_path> <args>
    cmd = [sccache_path, str(clang_path)] + args

    # Execute with platform-appropriate method
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        # Windows: use subprocess
        try:
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        # Unix: use exec to replace current process
        try:
            os.execv(sccache_path, cmd)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)


def sccache_clang_cpp_main() -> NoReturn:
    """Entry point for sccache + clang++ wrapper."""
    args = sys.argv[1:]

    try:
        sccache_path = find_sccache_binary()
        clang_cpp_path = find_tool_binary("clang++")
    except RuntimeError as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Add macOS SDK path automatically if needed
    platform_name, _ = get_platform_info()
    if platform_name == "darwin":
        args = _add_macos_sysroot_if_needed(args)

    # Build command: sccache <clang++_path> <args>
    cmd = [sccache_path, str(clang_cpp_path)] + args

    # Execute with platform-appropriate method
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        # Windows: use subprocess
        try:
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        # Unix: use exec to replace current process
        try:
            os.execv(sccache_path, cmd)
        except Exception as e:
            print(f"\n{'='*60}", file=sys.stderr)
            print("clang-tool-chain Error", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            print(f"Error executing sccache: {e}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
