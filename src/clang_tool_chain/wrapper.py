"""
Wrapper infrastructure for executing LLVM/Clang tools.

This module provides the core functionality for wrapping LLVM toolchain
binaries and forwarding commands to them with proper platform detection.
"""

import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from . import downloader

# Configure logging for GitHub Actions and general debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


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

    logger.debug(f"Detecting platform: system={system}, machine={machine}")

    # Normalize platform name
    if system == "windows":
        platform_name = "win"
    elif system == "linux":
        platform_name = "linux"
    elif system == "darwin":
        platform_name = "darwin"
    else:
        logger.error(f"Unsupported platform detected: {system}")
        raise RuntimeError(
            f"Unsupported platform: {system}\n"
            f"clang-tool-chain currently supports: Windows, Linux, and macOS (Darwin)\n"
            f"Your system: {system}\n"
            f"If you believe this platform should be supported, please report this at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    # Normalize architecture
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        logger.error(f"Unsupported architecture detected: {machine}")
        raise RuntimeError(
            f"Unsupported architecture: {machine}\n"
            f"clang-tool-chain currently supports: x86_64 (AMD64) and ARM64\n"
            f"Your architecture: {machine}\n"
            f"Supported architectures:\n"
            f"  - x86_64, amd64 (Intel/AMD 64-bit)\n"
            f"  - aarch64, arm64 (ARM 64-bit)\n"
            f"If you believe this architecture should be supported, please report this at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Platform detected: {platform_name}/{arch}")
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
    logger.info("Getting platform binary directory")
    platform_name, arch = get_platform_info()

    # Ensure toolchain is downloaded and installed
    logger.info(f"Ensuring toolchain is available for {platform_name}/{arch}")
    downloader.ensure_toolchain(platform_name, arch)

    # Get the installation directory
    install_dir = downloader.get_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"
    logger.debug(f"Binary directory: {bin_dir}")

    if not bin_dir.exists():
        logger.error(f"Binary directory does not exist: {bin_dir}")
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

    logger.info(f"Binary directory found: {bin_dir}")
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
    logger.info(f"Finding binary for tool: {tool_name}")
    bin_dir = get_platform_binary_dir()
    platform_name, _ = get_platform_info()

    # Add .exe extension on Windows
    tool_path = bin_dir / f"{tool_name}.exe" if platform_name == "win" else bin_dir / tool_name
    logger.debug(f"Looking for tool at: {tool_path}")

    if not tool_path.exists():
        logger.warning(f"Tool not found at primary location: {tool_path}")
        # Try alternative names for some tools
        alternatives = {
            "lld": ["lld-link", "ld.lld"],
            "clang": ["clang++", "clang-cpp"],
            "lld-link": ["lld", "ld.lld"],
            "ld.lld": ["lld", "lld-link"],
        }

        if tool_name in alternatives:
            logger.debug(f"Trying alternative names for {tool_name}: {alternatives[tool_name]}")
            for alt_name in alternatives[tool_name]:
                alt_path = bin_dir / f"{alt_name}.exe" if platform_name == "win" else bin_dir / alt_name
                logger.debug(f"Checking alternative: {alt_path}")

                if alt_path.exists():
                    logger.info(f"Found alternative tool at: {alt_path}")
                    return alt_path

        # List available tools
        available_tools = [f.stem for f in bin_dir.iterdir() if f.is_file()]
        logger.error(f"Tool '{tool_name}' not found. Available tools: {', '.join(sorted(available_tools)[:20])}")

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
            f"  - Report issue: https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Tool binary found: {tool_path}")
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


def _detect_windows_sdk() -> dict[str, str] | None:
    """
    Detect Windows SDK installation via environment variables.

    This function checks for Visual Studio and Windows SDK environment variables
    that are typically set by vcvars*.bat or Visual Studio Developer Command Prompt.

    Returns:
        Dictionary with SDK information if found, None otherwise.
        Dictionary keys: 'sdk_dir', 'vc_tools_dir', 'sdk_version' (if available)

    Note:
        This function only checks environment variables. It does not search the
        registry or filesystem for SDK installations. The goal is to detect if
        the user has already set up their Visual Studio environment.
    """
    sdk_info = {}

    # Check for Windows SDK environment variables
    # These are set by vcvarsall.bat and similar VS setup scripts
    sdk_dir = os.environ.get("WindowsSdkDir") or os.environ.get("WindowsSDKDir")  # noqa: SIM112
    if sdk_dir:
        sdk_info["sdk_dir"] = sdk_dir
        logger.debug(f"Windows SDK found via environment: {sdk_dir}")

    # Check for Universal CRT SDK (required for C runtime)
    ucrt_sdk_dir = os.environ.get("UniversalCRTSdkDir")  # noqa: SIM112
    if ucrt_sdk_dir:
        sdk_info["ucrt_dir"] = ucrt_sdk_dir
        logger.debug(f"Universal CRT SDK found: {ucrt_sdk_dir}")

    # Check for VC Tools (MSVC compiler toolchain)
    vc_tools_dir = os.environ.get("VCToolsInstallDir")  # noqa: SIM112
    if vc_tools_dir:
        sdk_info["vc_tools_dir"] = vc_tools_dir
        logger.debug(f"VC Tools found: {vc_tools_dir}")

    # Check for VS installation directory
    vs_install_dir = os.environ.get("VSINSTALLDIR")
    if vs_install_dir:
        sdk_info["vs_install_dir"] = vs_install_dir
        logger.debug(f"Visual Studio installation found: {vs_install_dir}")

    # Check for Windows SDK version
    sdk_version = os.environ.get("WindowsSDKVersion")  # noqa: SIM112
    if sdk_version:
        sdk_info["sdk_version"] = sdk_version.rstrip("\\")  # Remove trailing backslash if present
        logger.debug(f"Windows SDK version: {sdk_version}")

    # Return SDK info if we found at least the SDK directory or VC tools
    if sdk_info:
        logger.info(f"Windows SDK detected: {', '.join(sdk_info.keys())}")
        return sdk_info

    logger.debug("Windows SDK not detected in environment variables")
    return None


def _print_msvc_sdk_warning() -> None:
    """
    Print a helpful warning message to stderr when Windows SDK is not detected.

    This is called when MSVC target is being used but we cannot detect the
    Windows SDK via environment variables. The compilation may still succeed
    if clang can find the SDK automatically, or it may fail with missing
    headers/libraries errors.
    """
    print("\n" + "=" * 70, file=sys.stderr)
    print("⚠️  Windows SDK Not Detected in Environment", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("\nThe MSVC target requires Windows SDK for system headers and libraries.", file=sys.stderr)
    print("\nNo SDK environment variables found. This may mean:", file=sys.stderr)
    print("  • Visual Studio or Windows SDK is not installed", file=sys.stderr)
    print("  • VS Developer Command Prompt is not being used", file=sys.stderr)
    print("  • Environment variables are not set (vcvarsall.bat not run)", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Recommendation: Set up Visual Studio environment", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\nOption 1: Use Visual Studio Developer Command Prompt", file=sys.stderr)
    print("  • Search for 'Developer Command Prompt' in Start Menu", file=sys.stderr)
    print("  • Run your build commands from that prompt", file=sys.stderr)
    print("\nOption 2: Run vcvarsall.bat in your current shell", file=sys.stderr)
    print("  • Typical location:", file=sys.stderr)
    print(
        "    C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat",
        file=sys.stderr,
    )
    print("  • Run: vcvarsall.bat x64", file=sys.stderr)
    print("\nOption 3: Install Visual Studio or Windows SDK", file=sys.stderr)
    print("  • Visual Studio: https://visualstudio.microsoft.com/downloads/", file=sys.stderr)
    print("  • Windows SDK only: https://developer.microsoft.com/windows/downloads/windows-sdk/", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Alternative: Use GNU ABI (MinGW) instead of MSVC", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\nIf you don't need MSVC compatibility, use the default commands:", file=sys.stderr)
    print("  • clang-tool-chain-c (uses GNU ABI, no SDK required)", file=sys.stderr)
    print("  • clang-tool-chain-cpp (uses GNU ABI, no SDK required)", file=sys.stderr)
    print("\n" + "=" * 70, file=sys.stderr)
    print("Clang will attempt to find Windows SDK automatically...", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)


def _print_macos_sdk_error(reason: str) -> None:
    """
    Print a helpful error message to stderr when macOS SDK detection fails.

    This is called when compilation is about to proceed without SDK detection,
    which will likely cause 'stdio.h' or 'iostream' not found errors.

    Args:
        reason: Brief description of why SDK detection failed
    """
    print("\n" + "=" * 70, file=sys.stderr)
    print("⚠️  macOS SDK Detection Failed", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"\nReason: {reason}", file=sys.stderr)
    print("\nYour compilation may fail with errors like:", file=sys.stderr)
    print("  fatal error: 'stdio.h' file not found", file=sys.stderr)
    print("  fatal error: 'iostream' file not found", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Solution: Install Xcode Command Line Tools", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\nRun this command in your terminal:", file=sys.stderr)
    print("\n  \033[1;36mxcode-select --install\033[0m", file=sys.stderr)
    print("\nThen try compiling again.", file=sys.stderr)
    print("\n" + "-" * 70, file=sys.stderr)
    print("Alternative Solutions:", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print("\n1. Specify SDK path manually:", file=sys.stderr)
    print("   clang-tool-chain-c -isysroot /Library/Developer/.../MacOSX.sdk file.c", file=sys.stderr)
    print("\n2. Set SDKROOT environment variable:", file=sys.stderr)
    print("   export SDKROOT=$(xcrun --show-sdk-path)  # if xcrun works", file=sys.stderr)
    print("\n3. Use freestanding compilation (no standard library):", file=sys.stderr)
    print("   clang-tool-chain-c -ffreestanding -nostdlib file.c", file=sys.stderr)
    print("\n4. Disable automatic SDK detection:", file=sys.stderr)
    print("   export CLANG_TOOL_CHAIN_NO_SYSROOT=1", file=sys.stderr)
    print("   # Then specify SDK manually with -isysroot", file=sys.stderr)
    print("\n" + "=" * 70, file=sys.stderr)
    print("More info: https://github.com/zackees/clang-tool-chain#macos-sdk-detection-automatic", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)


def _add_macos_sysroot_if_needed(args: list[str]) -> list[str]:
    """
    Add -isysroot flag for macOS if needed to find system headers.

    On macOS, system headers (like stdio.h, iostream) are NOT in /usr/include.
    Instead, they're only available in SDK bundles provided by Xcode or Command Line Tools.
    Standalone clang binaries cannot automatically find these headers without help.

    This function implements LLVM's official three-tier SDK detection strategy
    (see LLVM patch D136315: https://reviews.llvm.org/D136315):
    1. Explicit -isysroot flag (user override)
    2. SDKROOT environment variable (Xcode/xcrun standard)
    3. Automatic xcrun --show-sdk-path (fallback detection)

    The function automatically detects the macOS SDK path and adds it to
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

    References:
        - LLVM D136315: Try to guess SDK root with xcrun when unspecified
        - Apple no longer ships headers in /usr/include since macOS 10.14 Mojave
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
            logger.info(f"macOS SDK detected: {sdk_path}")
            return ["-isysroot", sdk_path] + args
        else:
            # xcrun succeeded but returned invalid path
            logger.warning(f"xcrun returned invalid SDK path: {sdk_path}")
            _print_macos_sdk_error("xcrun returned invalid SDK path")
            return args

    except FileNotFoundError:
        # xcrun command not found - Command Line Tools likely not installed
        logger.error("xcrun command not found - Xcode Command Line Tools may not be installed")
        _print_macos_sdk_error("xcrun command not found")
        return args

    except subprocess.CalledProcessError as e:
        # xcrun failed with non-zero exit code
        stderr_output = e.stderr.strip() if e.stderr else "No error output"
        logger.error(f"xcrun failed: {stderr_output}")
        _print_macos_sdk_error(f"xcrun failed: {stderr_output}")
        return args

    except subprocess.TimeoutExpired:
        # xcrun took too long to respond
        logger.warning("xcrun command timed out")
        return args

    except Exception as e:
        # Unexpected error
        logger.warning(f"Unexpected error detecting SDK: {e}")
        return args


def _should_use_gnu_abi(platform_name: str, args: list[str]) -> bool:
    """
    Determine if GNU ABI should be used based on platform and arguments.

    Windows defaults to GNU ABI (MinGW) in v2.0+ for cross-platform consistency.
    This matches the approach of zig cc and ensures consistent C++ ABI across platforms.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Command-line arguments

    Returns:
        True if GNU ABI should be used (Windows + no explicit target), False otherwise
    """
    # Non-Windows always uses default (which is GNU-like anyway)
    if platform_name != "win":
        return False

    # Check if user explicitly specified target
    args_str = " ".join(args)
    if "--target=" in args_str or "--target " in args_str:
        # User specified target explicitly, don't override
        logger.debug("User specified explicit target, skipping GNU ABI injection")
        return False

    # Windows defaults to GNU ABI in v2.0+
    logger.debug("Windows detected without explicit target, will use GNU ABI")
    return True


def _get_gnu_target_args(platform_name: str, arch: str) -> list[str]:
    """
    Get GNU ABI target arguments for Windows.

    This function ensures the MinGW sysroot is installed and returns
    the necessary compiler arguments to use GNU ABI instead of MSVC ABI.

    Args:
        platform_name: Platform name
        arch: Architecture

    Returns:
        List of additional compiler arguments for GNU ABI

    Raises:
        RuntimeError: If MinGW sysroot installation fails or is not found
    """
    if platform_name != "win":
        return []

    logger.info(f"Setting up GNU ABI for Windows {arch}")

    # Ensure MinGW sysroot is installed
    try:
        sysroot_dir = downloader.ensure_mingw_sysroot_installed(platform_name, arch)
        logger.debug(f"MinGW sysroot installed at: {sysroot_dir}")
    except Exception as e:
        logger.error(f"Failed to install MinGW sysroot: {e}")
        raise RuntimeError(
            f"Failed to install MinGW sysroot for Windows GNU ABI support\n"
            f"Error: {e}\n"
            f"\n"
            f"This is required for GNU ABI support on Windows.\n"
            f"If this persists, please report at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        ) from e

    # Determine target triple and sysroot path
    if arch == "x86_64":
        target = "x86_64-w64-mingw32"
    elif arch == "arm64":
        target = "aarch64-w64-mingw32"
    else:
        raise ValueError(f"Unsupported architecture for MinGW: {arch}")

    # The sysroot is the directory containing include/ and the target subdirectory
    sysroot_path = sysroot_dir
    if not sysroot_path.exists():
        logger.error(f"MinGW sysroot not found at expected location: {sysroot_path}")
        raise RuntimeError(
            f"MinGW sysroot not found: {sysroot_path}\n"
            f"The sysroot was downloaded but the expected directory is missing.\n"
            f"Please report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Using GNU target: {target} with sysroot: {sysroot_path}")

    # Check if resource directory exists in the sysroot
    # The archive should contain lib/clang/<version>/ with resource headers
    resource_dir = sysroot_path / "lib" / "clang"
    resource_dir_arg = []
    if resource_dir.exists():
        # Find the version directory (should be only one, e.g., "21")
        version_dirs = [d for d in resource_dir.iterdir() if d.is_dir()]
        if version_dirs:
            # Use the first (and should be only) version directory
            clang_version_dir = version_dirs[0]
            resource_include = clang_version_dir / "include"
            if resource_include.exists():
                logger.info(f"Found clang resource directory at: {clang_version_dir}")
                # Use -resource-dir to tell clang where to find its builtin headers
                # This makes clang look in <resource-dir>/include/ for headers like stddef.h, mm_malloc.h
                resource_dir_arg = [f"-resource-dir={clang_version_dir}"]
            else:
                logger.warning(f"Resource include directory not found: {resource_include}")
        else:
            logger.warning(f"No version directories found in: {resource_dir}")
    else:
        logger.warning(f"Resource directory not found: {resource_dir}")

    # Add -stdlib=libc++ to use the libc++ standard library included in the sysroot
    # Add -fuse-ld=lld to use LLVM's linker instead of system ld
    # Add -rtlib=compiler-rt to use LLVM's compiler-rt instead of libgcc
    # Add --unwindlib=libunwind to use LLVM's libunwind instead of libgcc_s
    # Add -static-libgcc -static-libstdc++ to link runtime libraries statically
    # This avoids DLL dependency issues at runtime
    return [
        f"--target={target}",
        f"--sysroot={sysroot_path}",
        "-stdlib=libc++",
        "-rtlib=compiler-rt",
        "-fuse-ld=lld",
        "--unwindlib=libunwind",
        "-static-libgcc",
        "-static-libstdc++",
    ] + resource_dir_arg


def _should_use_msvc_abi(platform_name: str, args: list[str]) -> bool:
    """
    Determine if MSVC ABI should be used based on platform and arguments.

    MSVC ABI is explicitly requested via the *-msvc variant commands.
    Unlike GNU ABI (which is the Windows default), MSVC ABI is opt-in.

    This function checks if the user has explicitly provided a --target flag.
    If so, we respect the user's choice and don't inject MSVC target.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        args: Command-line arguments

    Returns:
        True if MSVC ABI should be used (Windows + no explicit target), False otherwise
    """
    # MSVC ABI only applies to Windows
    if platform_name != "win":
        logger.debug("Not Windows platform, MSVC ABI not applicable")
        return False

    # Check if user explicitly specified target
    args_str = " ".join(args)
    if "--target=" in args_str or "--target " in args_str:
        # User specified target explicitly, don't override
        logger.debug("User specified explicit target, skipping MSVC ABI injection")
        return False

    # MSVC variant was requested and no user override
    logger.debug("MSVC ABI will be used (no user target override)")
    return True


def _get_msvc_target_args(platform_name: str, arch: str) -> list[str]:
    """
    Get MSVC ABI target arguments for Windows.

    This function returns the necessary compiler arguments to use MSVC ABI
    instead of GNU ABI. It also detects Windows SDK availability and shows
    helpful warnings if the SDK is not found in environment variables.

    Args:
        platform_name: Platform name
        arch: Architecture

    Returns:
        List of additional compiler arguments for MSVC ABI (just --target)

    Note:
        Unlike GNU ABI which requires downloading a MinGW sysroot, MSVC ABI
        relies on the system's Visual Studio or Windows SDK installation.
        We detect SDK presence via environment variables and warn if not found,
        but still return the target triple and let clang attempt its own SDK detection.
    """
    if platform_name != "win":
        return []

    logger.info(f"Setting up MSVC ABI for Windows {arch}")

    # Detect Windows SDK and warn if not found
    sdk_info = _detect_windows_sdk()
    if sdk_info:
        logger.info(f"Windows SDK detected with keys: {', '.join(sdk_info.keys())}")
    else:
        logger.warning("Windows SDK not detected in environment variables")
        # Show helpful warning about SDK requirements
        _print_msvc_sdk_warning()

    # Determine target triple for MSVC ABI
    if arch == "x86_64":
        target = "x86_64-pc-windows-msvc"
    elif arch == "arm64":
        target = "aarch64-pc-windows-msvc"
    else:
        raise ValueError(f"Unsupported architecture for MSVC: {arch}")

    logger.info(f"Using MSVC target: {target}")

    # Return just the target triple
    # Clang will automatically:
    # - Select lld-link as the linker (MSVC-compatible)
    # - Use MSVC name mangling for C++
    # - Attempt to find Windows SDK via its own detection logic
    return [f"--target={target}"]


def execute_tool(tool_name: str, args: list[str] | None = None, use_msvc: bool = False) -> NoReturn:
    """
    Execute a tool with the given arguments and exit with its return code.

    This function does not return - it replaces the current process with
    the tool process (on Unix) or exits with the tool's return code (on Windows).

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool (defaults to sys.argv[1:])
        use_msvc: If True on Windows, skip GNU ABI injection (use MSVC target)

    Raises:
        RuntimeError: If the tool cannot be found or executed

    Environment Variables:
        SDKROOT: Custom SDK path to use (macOS, standard macOS variable)
        CLANG_TOOL_CHAIN_NO_SYSROOT: Set to '1' to disable automatic -isysroot injection (macOS)
    """
    if args is None:
        args = sys.argv[1:]

    logger.info(f"Executing tool: {tool_name} with {len(args)} arguments")
    logger.debug(f"Arguments: {args}")

    try:
        tool_path = find_tool_binary(tool_name)
    except RuntimeError as e:
        logger.error(f"Failed to find tool binary: {e}")
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Add macOS SDK path automatically for clang/clang++ if not already specified
    platform_name, arch = get_platform_info()
    if platform_name == "darwin" and tool_name in ("clang", "clang++"):
        logger.debug("Checking if macOS sysroot needs to be added")
        args = _add_macos_sysroot_if_needed(args)

    # Add Windows GNU ABI target automatically for clang/clang++ if not MSVC variant
    if not use_msvc and tool_name in ("clang", "clang++") and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with args: {gnu_args}")
        except Exception as e:
            # If GNU setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target for clang/clang++ when using MSVC variant
    if use_msvc and tool_name in ("clang", "clang++") and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with args: {msvc_args}")
        except Exception as e:
            # If MSVC setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Build command
    cmd = [str(tool_path)] + args
    logger.info(f"Executing command: {tool_path} (with {len(args)} args)")

    # On Unix systems, we can use exec to replace the current process
    # On Windows, we need to use subprocess and exit with the return code
    platform_name, _ = get_platform_info()

    if platform_name == "win":
        logger.debug("Using Windows subprocess execution")
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
            print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
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
            print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        logger.debug("Using Unix exec replacement")
        # Unix: use exec to replace current process
        try:
            logger.info(f"Replacing process with: {tool_path}")
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
            print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
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
            print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(1)


def run_tool(tool_name: str, args: list[str] | None = None, use_msvc: bool = False) -> int:
    """
    Run a tool with the given arguments and return its exit code.

    Unlike execute_tool, this function returns to the caller with the
    tool's exit code instead of exiting the process.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool (defaults to sys.argv[1:])
        use_msvc: If True on Windows, skip GNU ABI injection (use MSVC target)

    Returns:
        Exit code from the tool

    Raises:
        RuntimeError: If the tool cannot be found

    Environment Variables:
        SDKROOT: Custom SDK path to use (macOS, standard macOS variable)
        CLANG_TOOL_CHAIN_NO_SYSROOT: Set to '1' to disable automatic -isysroot injection (macOS)
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_tool_binary(tool_name)

    # Add macOS SDK path automatically for clang/clang++ if not already specified
    platform_name, arch = get_platform_info()
    if platform_name == "darwin" and tool_name in ("clang", "clang++"):
        logger.debug("Checking if macOS sysroot needs to be added")
        args = _add_macos_sysroot_if_needed(args)

    # Add Windows GNU ABI target automatically for clang/clang++ if not MSVC variant
    if not use_msvc and tool_name in ("clang", "clang++") and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with args: {gnu_args}")
        except Exception as e:
            # If GNU setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target for clang/clang++ when using MSVC variant
    if use_msvc and tool_name in ("clang", "clang++") and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with args: {msvc_args}")
        except Exception as e:
            # If MSVC setup fails, let the tool try anyway (may fail at compile time)
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

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
    """Entry point for clang wrapper (GNU ABI on Windows by default)."""
    execute_tool("clang")


def clang_cpp_main() -> NoReturn:
    """Entry point for clang++ wrapper (GNU ABI on Windows by default)."""
    execute_tool("clang++")


def clang_msvc_main() -> NoReturn:
    """Entry point for clang-tool-chain-c-msvc (MSVC ABI on Windows)."""
    execute_tool("clang", use_msvc=True)


def clang_cpp_msvc_main() -> NoReturn:
    """Entry point for clang-tool-chain-cpp-msvc (MSVC ABI on Windows)."""
    execute_tool("clang++", use_msvc=True)


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
def sccache_clang_main(use_msvc: bool = False) -> NoReturn:
    """
    Entry point for sccache + clang wrapper.

    Args:
        use_msvc: If True on Windows, use MSVC ABI instead of GNU ABI
    """
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
    platform_name, arch = get_platform_info()
    if platform_name == "darwin":
        args = _add_macos_sysroot_if_needed(args)

    # Add Windows GNU ABI target automatically (if not using MSVC variant)
    if not use_msvc and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with sccache: {gnu_args}")
        except Exception as e:
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target when using MSVC variant
    if use_msvc and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with sccache: {msvc_args}")
        except Exception as e:
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

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


def sccache_clang_cpp_main(use_msvc: bool = False) -> NoReturn:
    """
    Entry point for sccache + clang++ wrapper.

    Args:
        use_msvc: If True on Windows, use MSVC ABI instead of GNU ABI
    """
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
    platform_name, arch = get_platform_info()
    if platform_name == "darwin":
        args = _add_macos_sysroot_if_needed(args)

    # Add Windows GNU ABI target automatically (if not using MSVC variant)
    if not use_msvc and _should_use_gnu_abi(platform_name, args):
        try:
            gnu_args = _get_gnu_target_args(platform_name, arch)
            args = gnu_args + args
            logger.info(f"Using GNU ABI with sccache: {gnu_args}")
        except Exception as e:
            logger.error(f"Failed to set up GNU ABI: {e}")
            print(f"\nWarning: Failed to set up Windows GNU ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

    # Add Windows MSVC ABI target when using MSVC variant
    if use_msvc and _should_use_msvc_abi(platform_name, args):
        try:
            msvc_args = _get_msvc_target_args(platform_name, arch)
            args = msvc_args + args
            logger.info(f"Using MSVC ABI with sccache: {msvc_args}")
        except Exception as e:
            logger.error(f"Failed to set up MSVC ABI: {e}")
            print(f"\nWarning: Failed to set up Windows MSVC ABI: {e}", file=sys.stderr)
            print("Continuing with default target (may fail)...\n", file=sys.stderr)

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


# ============================================================================
# IWYU (Include What You Use) Support
# ============================================================================


def get_iwyu_binary_dir() -> Path:
    """
    Get the binary directory for IWYU.

    Returns:
        Path to the IWYU binary directory

    Raises:
        RuntimeError: If binary directory is not found
    """
    platform_name, arch = get_platform_info()
    logger.info(f"Getting IWYU binary directory for {platform_name}/{arch}")

    # Ensure IWYU is downloaded and installed
    logger.info(f"Ensuring IWYU is available for {platform_name}/{arch}")
    downloader.ensure_iwyu(platform_name, arch)

    # Get the installation directory
    install_dir = downloader.get_iwyu_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"
    logger.debug(f"IWYU binary directory: {bin_dir}")

    if not bin_dir.exists():
        logger.error(f"IWYU binary directory does not exist: {bin_dir}")
        raise RuntimeError(
            f"IWYU binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"The IWYU download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"IWYU binary directory found: {bin_dir}")
    return bin_dir


def find_iwyu_tool(tool_name: str) -> Path:
    """
    Find the path to an IWYU tool.

    Args:
        tool_name: Name of the tool (e.g., "include-what-you-use", "iwyu_tool.py")

    Returns:
        Path to the tool

    Raises:
        RuntimeError: If the tool is not found
    """
    logger.info(f"Finding IWYU tool: {tool_name}")
    bin_dir = get_iwyu_binary_dir()
    platform_name, _ = get_platform_info()

    # Add .exe extension on Windows for the binary
    if tool_name == "include-what-you-use" and platform_name == "win":
        tool_path = bin_dir / f"{tool_name}.exe"
    else:
        tool_path = bin_dir / tool_name

    logger.debug(f"Looking for IWYU tool at: {tool_path}")

    if not tool_path.exists():
        logger.error(f"IWYU tool not found: {tool_path}")
        # List available tools
        available_tools = [f.name for f in bin_dir.iterdir() if f.is_file()]
        raise RuntimeError(
            f"IWYU tool '{tool_name}' not found at: {tool_path}\n"
            f"Available tools in {bin_dir}:\n"
            f"  {', '.join(available_tools)}"
        )

    logger.info(f"Found IWYU tool: {tool_path}")
    return tool_path


def execute_iwyu_tool(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute an IWYU tool with the given arguments.

    Args:
        tool_name: Name of the IWYU tool
        args: Command-line arguments (default: sys.argv[1:])

    Raises:
        SystemExit: Always exits with the tool's return code
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_iwyu_tool(tool_name)
    platform_name, _ = get_platform_info()

    # For Python scripts, we need to run them with Python
    if tool_name.endswith(".py"):
        # Find Python executable
        python_exe = sys.executable
        cmd = [python_exe, str(tool_path)] + args
    else:
        cmd = [str(tool_path)] + args

    logger.info(f"Executing IWYU tool: {' '.join(cmd)}")

    # Execute tool
    if platform_name == "win":
        # Windows: use subprocess
        try:
            result = subprocess.run(cmd)
            sys.exit(result.returncode)
        except FileNotFoundError as err:
            raise RuntimeError(f"IWYU tool not found: {tool_path}") from err
        except Exception as e:
            raise RuntimeError(f"Error executing IWYU tool: {e}") from e
    else:
        # Unix: use exec to replace current process
        try:
            if tool_name.endswith(".py"):
                # For Python scripts, we can't use execv directly
                result = subprocess.run(cmd)
                sys.exit(result.returncode)
            else:
                os.execv(cmd[0], cmd)
        except FileNotFoundError as err:
            raise RuntimeError(f"IWYU tool not found: {tool_path}") from err
        except Exception as e:
            raise RuntimeError(f"Error executing IWYU tool: {e}") from e


# IWYU wrapper entry points
def iwyu_main() -> NoReturn:
    """Entry point for include-what-you-use wrapper."""
    execute_iwyu_tool("include-what-you-use")


def iwyu_tool_main() -> NoReturn:
    """Entry point for iwyu_tool.py wrapper."""
    execute_iwyu_tool("iwyu_tool.py")


def fix_includes_main() -> NoReturn:
    """Entry point for fix_includes.py wrapper."""
    execute_iwyu_tool("fix_includes.py")
