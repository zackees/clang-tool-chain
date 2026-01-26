"""
Cosmocc (Cosmopolitan Libc) execution support.

This module provides functionality for discovering and executing Cosmocc tools,
including cosmocc (C compiler) and cosmoc++ (C++ compiler). Cosmocc produces
Actually Portable Executables (APE) that run on Windows, Linux, macOS, FreeBSD,
NetBSD, and OpenBSD without modification.

For more information about Cosmopolitan Libc, see:
- https://github.com/jart/cosmopolitan
- https://justine.lol/cosmopolitan/
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from clang_tool_chain import downloader
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

# Configure logging
logger = logging.getLogger(__name__)


def get_platform_info() -> tuple[str, str]:
    """
    Detect the current platform and architecture.

    Returns:
        Tuple of (platform, architecture) strings
        Platform: "win", "linux", or "darwin"
        Architecture: "x86_64" or "arm64"
    """
    import platform

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


def get_cosmocc_binary_dir() -> Path:
    """
    Get the binary directory for Cosmocc (universal installation).

    Cosmocc produces Actually Portable Executables (APE) that run on all platforms,
    so a single universal installation is shared across all platforms.

    Returns:
        Path to the Cosmocc binary directory

    Raises:
        RuntimeError: If binary directory is not found
    """
    # Still detect current platform for logging purposes
    platform_name, arch = get_platform_info()
    logger.info(f"Getting Cosmocc binary directory (running on {platform_name}/{arch})")

    # Ensure Cosmocc is downloaded - universal installation
    logger.info("Ensuring Cosmocc is available (universal installation)")
    downloader.ensure_cosmocc()  # No platform/arch needed - universal installation

    # Get the universal installation directory
    install_dir = downloader.get_cosmocc_install_dir()  # No platform/arch needed
    bin_dir = install_dir / "bin"
    logger.debug(f"Cosmocc binary directory: {bin_dir}")

    if not bin_dir.exists():
        logger.error(f"Cosmocc binary directory does not exist: {bin_dir}")
        raise RuntimeError(
            f"Cosmocc binaries not found (universal installation)\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"The Cosmocc download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Cosmocc binary directory found: {bin_dir}")
    return bin_dir


def find_cosmocc_tool(tool_name: str) -> Path:
    """
    Find the path to a Cosmocc tool.

    Args:
        tool_name: Name of the tool (e.g., "cosmocc", "cosmoc++")

    Returns:
        Path to the tool

    Raises:
        RuntimeError: If the tool is not found
    """
    logger.info(f"Finding Cosmocc tool: {tool_name}")
    bin_dir = get_cosmocc_binary_dir()
    platform_name, _ = get_platform_info()

    # On Windows, Cosmocc tools may have .exe extension
    # But the native cosmocc is a shell script on Unix and batch/exe on Windows
    tool_path: Path | None = None
    if platform_name == "win":
        # Try .exe first, then .bat, then without extension
        for ext in [".exe", ".bat", ""]:
            candidate = bin_dir / f"{tool_name}{ext}"
            if candidate.exists():
                logger.info(f"Found Cosmocc tool: {candidate}")
                return candidate
        # Set default tool path for error message
        tool_path = bin_dir / f"{tool_name}.exe"
    else:
        tool_path = bin_dir / tool_name

    logger.debug(f"Looking for Cosmocc tool at: {tool_path}")

    # Check if tool exists with retry for Windows file system issues
    tool_exists = tool_path.exists()
    if not tool_exists and platform_name == "win":
        # On Windows, Path.exists() can sometimes return False due to file system
        # caching issues, especially during parallel test execution.
        import time

        time.sleep(0.01)  # 10ms delay
        tool_exists = tool_path.exists() or os.path.exists(str(tool_path))

    if not tool_exists:
        logger.error(f"Cosmocc tool not found: {tool_path}")
        # List available tools
        available_tools = [f.name for f in bin_dir.iterdir() if f.is_file()][:20]  # Limit to first 20
        raise RuntimeError(
            f"Cosmocc tool '{tool_name}' not found at: {tool_path}\n"
            f"Available tools in {bin_dir} (first 20):\n"
            f"  {', '.join(available_tools)}"
        )

    logger.info(f"Found Cosmocc tool: {tool_path}")
    return tool_path


def execute_cosmocc_tool(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute a Cosmocc tool with the given arguments.

    Args:
        tool_name: Name of the Cosmocc tool (e.g., "cosmocc", "cosmoc++")
        args: Command-line arguments (default: sys.argv[1:])

    Raises:
        SystemExit: Exits with the tool's return code
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_cosmocc_tool(tool_name)
    platform_name, _ = get_platform_info()

    # Set up environment for Cosmocc
    # Cosmocc needs its toolchain directory to find includes and libraries
    bin_dir = get_cosmocc_binary_dir()
    install_dir = bin_dir.parent

    env = os.environ.copy()

    # Add Cosmocc bin directory to PATH
    # Also add libexec directories for GCC internal executables (cc1, cc1plus, etc.)
    libexec_dir = install_dir / "libexec"
    libexec_gcc_dir = libexec_dir / "gcc"

    path_dirs = [str(bin_dir)]

    # Add libexec/gcc to PATH (contains target-specific subdirectories)
    if libexec_gcc_dir.exists():
        path_dirs.append(str(libexec_gcc_dir))
        # On Windows, GCC_EXEC_PREFIX may not work correctly, so we also add the
        # target/version subdirectories directly to PATH for cc1 lookup.
        # This ensures cc1, cc1plus, ld, etc. can be found on all platforms.
        # Sort to ensure consistent ordering across runs.
        for target_dir in sorted(libexec_gcc_dir.iterdir()):
            if target_dir.is_dir():
                for version_dir in sorted(target_dir.iterdir()):
                    if version_dir.is_dir():
                        path_dirs.append(str(version_dir))
                        logger.debug(f"Added GCC internal dir to PATH: {version_dir}")
    elif libexec_dir.exists():
        path_dirs.append(str(libexec_dir))

    # On Windows, convert paths to Unix-style for bash/POSIX shell compatibility
    # The cosmocc script runs under bash, and the GCC APE binaries expect Unix-style paths
    if platform_name == "win":
        # Convert Windows paths to Unix-style (C:\foo\bar -> /c/foo/bar)
        def to_unix_path(path: str) -> str:
            """Convert Windows path to Unix-style path for MSYS/Git Bash."""
            path = path.replace("\\", "/")
            # Convert drive letter: C:/foo -> /c/foo
            if len(path) >= 2 and path[1] == ":":
                drive = path[0].lower()
                path = f"/{drive}{path[2:]}"
            return path

        unix_path_dirs = [to_unix_path(p) for p in path_dirs]
        # Also convert existing PATH entries
        existing_path = env.get("PATH", "")
        # Use colon separator for Unix-style PATH
        env["PATH"] = ":".join(unix_path_dirs) + ":" + existing_path
    else:
        env["PATH"] = f"{os.pathsep.join(path_dirs)}{os.pathsep}{env.get('PATH', '')}"

    # Note: We intentionally do NOT set GCC_EXEC_PREFIX here.
    # On Windows, setting GCC_EXEC_PREFIX can interfere with PATH-based cc1 lookup
    # and cause the wrong architecture's cc1 to be found. The PATH additions above
    # are sufficient for correct cc1 resolution on all platforms.

    # Set COSMOCC environment variable pointing to the Cosmocc installation
    # This helps Cosmocc find its includes and libraries
    env["COSMOCC"] = str(install_dir)

    # Cosmocc tools (cosmocc, cosmoc++) are POSIX shell scripts.
    # They need to be executed through a shell interpreter.
    # On Unix/Linux, try to find sh or bash
    # On Windows, we need to find a POSIX shell (bash/sh from Git Bash, MSYS2, etc.)
    if platform_name == "win":
        # Find a shell to execute the script
        # Try common shell locations on Windows (Git Bash, MSYS2, Cygwin, WSL)
        shell = _find_windows_shell()
        if shell:
            # Convert Windows path to Unix-style for the shell
            tool_path_unix = str(tool_path).replace("\\", "/")
            cmd = [shell, tool_path_unix] + args
        else:
            # No shell found - warn and try running directly (will likely fail)
            logger.warning(
                "No POSIX shell (bash/sh) found. Cosmocc requires a shell like Git Bash, MSYS2, or WSL.\n"
                "Please install Git for Windows (includes Git Bash) or MSYS2."
            )
            cmd = [str(tool_path)] + args
    else:
        # On Unix/Linux, explicitly invoke through shell to handle potential
        # shebang issues or exec format errors
        import shutil

        shell = shutil.which("bash") or shutil.which("sh")
        if shell:
            logger.debug(f"Using shell {shell} to execute Cosmocc tool")
            cmd = [shell, str(tool_path)] + args
        else:
            # Fallback: try direct execution (may fail if script has format issues)
            logger.debug("No bash/sh found in PATH, trying direct execution")
            cmd = [str(tool_path)] + args

    logger.info(f"Executing Cosmocc tool: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError as err:
        if platform_name == "win":
            raise RuntimeError(
                f"Cosmocc tool not found or shell not available: {tool_path}\n"
                f"Cosmocc requires a POSIX shell on Windows. Please install Git for Windows (Git Bash) or MSYS2.\n"
                f"Download Git for Windows from: https://git-scm.com/download/win"
            ) from err
        raise RuntimeError(f"Cosmocc tool not found: {tool_path}") from err
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        raise RuntimeError(f"Error executing Cosmocc tool: {e}") from e


def _find_windows_shell() -> str | None:
    """
    Find a POSIX shell on Windows for running cosmocc scripts.

    Returns:
        Path to shell executable, or None if not found
    """
    import shutil

    # Check common shell locations
    shell_candidates = [
        # Git Bash
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        # MSYS2
        r"C:\msys64\usr\bin\bash.exe",
        r"C:\msys32\usr\bin\bash.exe",
        # Cygwin
        r"C:\cygwin64\bin\bash.exe",
        r"C:\cygwin\bin\bash.exe",
    ]

    # First check if bash is in PATH
    bash_in_path = shutil.which("bash")
    if bash_in_path:
        logger.debug(f"Found bash in PATH: {bash_in_path}")
        return bash_in_path

    # Check sh in PATH (Git for Windows includes sh.exe)
    sh_in_path = shutil.which("sh")
    if sh_in_path:
        logger.debug(f"Found sh in PATH: {sh_in_path}")
        return sh_in_path

    # Check specific locations
    for shell_path in shell_candidates:
        if os.path.exists(shell_path):
            logger.debug(f"Found shell at: {shell_path}")
            return shell_path

    logger.warning("No POSIX shell found on Windows")
    return None
