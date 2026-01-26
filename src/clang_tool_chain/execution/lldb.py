"""
LLDB (LLVM Debugger) execution support.

This module provides functionality for discovering and executing LLDB debugger tools,
including the main lldb binary and associated helpers like lldb-server and lldb-argdumper.
"""

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NoReturn

from clang_tool_chain import downloader
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

# Configure logging
logger = logging.getLogger(__name__)


class LldbPythonStatus(Enum):
    """Status of LLDB Python environment."""

    READY = "ready"
    MISSING = "missing"
    INCOMPLETE = "incomplete"


@dataclass
class LldbPythonEnvironment:
    """
    Diagnostic information about LLDB Python environment configuration.

    Attributes:
        python_available: True if Python directory exists
        python_dir: Path to Python directory
        site_packages: Path to site-packages directory
        lldb_module: True if LLDB Python module exists
        python_zip: True if python310.zip exists (Windows)
        python_lib_dir: True if Lib/ directory exists (Linux/macOS)
        python_dll: True if python310.dll exists (Windows)
        pythonpath_value: Value for PYTHONPATH environment variable
        pythonhome_value: Value for PYTHONHOME environment variable
        status: Overall status (ready, missing, or incomplete)
        message: Human-readable status message
    """

    python_available: bool = False
    python_dir: str | None = None
    site_packages: str | None = None
    lldb_module: bool = False
    python_zip: bool = False
    python_lib_dir: bool = False
    python_dll: bool = False
    pythonpath_value: str | None = None
    pythonhome_value: str | None = None
    status: LldbPythonStatus = LldbPythonStatus.MISSING
    message: str = "Python modules not found"

    def is_ready(self) -> bool:
        """Check if Python environment is fully configured."""
        return self.status == LldbPythonStatus.READY


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


def get_lldb_binary_dir() -> Path:
    """
    Get the binary directory for LLDB.

    Returns:
        Path to the LLDB binary directory

    Raises:
        RuntimeError: If binary directory is not found
    """
    platform_name, arch = get_platform_info()
    logger.info(f"Getting LLDB binary directory for {platform_name}/{arch}")

    # Ensure LLDB is downloaded and installed
    logger.info(f"Ensuring LLDB is available for {platform_name}/{arch}")
    downloader.ensure_lldb(platform_name, arch)

    # Get the installation directory
    install_dir = downloader.get_lldb_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"
    logger.debug(f"LLDB binary directory: {bin_dir}")

    if not bin_dir.exists():
        logger.error(f"LLDB binary directory does not exist: {bin_dir}")
        raise RuntimeError(
            f"LLDB binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"The LLDB download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"LLDB binary directory found: {bin_dir}")
    return bin_dir


def find_lldb_tool(tool_name: str) -> Path:
    """
    Find the path to an LLDB tool.

    Args:
        tool_name: Name of the tool (e.g., "lldb", "lldb-server", "lldb-argdumper")

    Returns:
        Path to the tool

    Raises:
        RuntimeError: If the tool is not found
    """
    logger.info(f"Finding LLDB tool: {tool_name}")
    bin_dir = get_lldb_binary_dir()
    platform_name, _ = get_platform_info()

    # Add .exe extension on Windows for the binary
    tool_path = bin_dir / f"{tool_name}.exe" if platform_name == "win" else bin_dir / tool_name

    logger.debug(f"Looking for LLDB tool at: {tool_path}")

    # Check if tool exists with retry for Windows file system issues
    tool_exists = tool_path.exists()
    if not tool_exists and platform_name == "win":
        # On Windows, Path.exists() can sometimes return False due to file system
        # caching or hardlink issues, especially during parallel test execution.
        # Retry with a small delay and also check with os.path.exists()
        import time

        time.sleep(0.01)  # 10ms delay
        tool_exists = tool_path.exists() or os.path.exists(str(tool_path))

    if not tool_exists:
        logger.error(f"LLDB tool not found: {tool_path}")
        # List available tools
        available_tools = [f.name for f in bin_dir.iterdir() if f.is_file()]
        raise RuntimeError(
            f"LLDB tool '{tool_name}' not found at: {tool_path}\n"
            f"Available tools in {bin_dir}:\n"
            f"  {', '.join(available_tools)}"
        )

    logger.info(f"Found LLDB tool: {tool_path}")
    return tool_path


def check_lldb_python_environment() -> LldbPythonEnvironment:
    """
    Check the LLDB Python environment configuration and return diagnostic information.

    Returns:
        LldbPythonEnvironment object containing diagnostic information
    """
    platform_name, arch = get_platform_info()
    install_dir = downloader.get_lldb_install_dir(platform_name, arch)
    python_dir = install_dir / "python"
    bin_dir = install_dir / "bin"

    result = LldbPythonEnvironment()

    if python_dir.exists():
        result.python_available = True
        result.python_dir = str(python_dir)
        result.pythonhome_value = str(python_dir)

        # Check site-packages
        site_packages = python_dir / "Lib" / "site-packages"
        if site_packages.exists():
            result.site_packages = str(site_packages)
            result.pythonpath_value = str(site_packages)

            # Check for LLDB Python module
            lldb_module = site_packages / "lldb"
            if lldb_module.exists():
                result.lldb_module = True

        # Check for Python standard library (two possible formats)
        # Windows: python310.zip (compressed)
        python_zip = python_dir / "python310.zip"
        if python_zip.exists():
            result.python_zip = True

        # Linux/macOS: Lib/ directory (extracted)
        lib_dir = python_dir / "Lib"
        if lib_dir.exists() and lib_dir.is_dir():
            result.python_lib_dir = True

        # Check for python310.dll on Windows (required by liblldb.dll)
        if platform_name == "win":
            python_dll = bin_dir / "python310.dll"
            if python_dll.exists():
                result.python_dll = True

        # Determine overall status
        # Python stdlib can be either python310.zip (Windows) or Lib/ directory (Linux/macOS)
        has_stdlib = result.python_zip or result.python_lib_dir

        # On Windows, python310.dll is required for LLDB to run
        has_python_runtime = True
        if platform_name == "win":
            has_python_runtime = result.python_dll

        if result.lldb_module and has_stdlib and has_python_runtime:
            result.status = LldbPythonStatus.READY
            stdlib_type = "python310.zip" if result.python_zip else "Lib/ directory"
            result.message = f"Python environment is fully configured (stdlib: {stdlib_type})"
        elif not has_python_runtime:
            result.status = LldbPythonStatus.INCOMPLETE
            result.message = "Python runtime (python310.dll) is missing from bin/ directory"
        elif result.lldb_module:
            result.status = LldbPythonStatus.INCOMPLETE
            result.message = "LLDB module found but Python standard library missing"
        elif has_stdlib:
            result.status = LldbPythonStatus.INCOMPLETE
            result.message = "Python standard library found but LLDB module missing"
        else:
            result.status = LldbPythonStatus.INCOMPLETE
            result.message = "Python directory exists but modules are incomplete"
    else:
        result.message = f"Python directory not found at {python_dir}"

    return result


def print_lldb_python_diagnostics() -> int:
    """
    Print diagnostic information about LLDB Python environment.

    Returns:
        Exit code (0 if Python is ready, 1 if missing/incomplete)
    """
    print("LLDB Python Environment Diagnostics")
    print("=" * 60)

    try:
        # Get platform info
        platform_name, arch = get_platform_info()
        print(f"Platform: {platform_name}/{arch}")

        # Get installation directory
        install_dir = downloader.get_lldb_install_dir(platform_name, arch)
        print(f"LLDB Install Dir: {install_dir}")
        print()

        # Check Python environment
        diagnostics = check_lldb_python_environment()

        status = diagnostics.status.value
        print(f"Status: {status.upper()}")
        print(f"Message: {diagnostics.message}")
        print()

        print("Python Components:")
        print(f"  Python Directory: {diagnostics.python_dir or 'NOT FOUND'}")
        print(f"  Site-Packages: {diagnostics.site_packages or 'NOT FOUND'}")
        print(f"  LLDB Module: {'✓ FOUND' if diagnostics.lldb_module else '✗ MISSING'}")
        # Show both Windows (python310.zip) and Linux (Lib/) stdlib formats
        if diagnostics.python_zip:
            print("  Python Stdlib (python310.zip): ✓ FOUND")
        elif diagnostics.python_lib_dir:
            print("  Python Stdlib (Lib/ directory): ✓ FOUND")
        else:
            print("  Python Stdlib: ✗ MISSING")
        # Show python310.dll status on Windows
        if platform_name == "win":
            print(f"  Python Runtime (python310.dll): {'✓ FOUND' if diagnostics.python_dll else '✗ MISSING'}")
        print()

        print("Environment Variables (when LLDB runs):")
        if diagnostics.pythonpath_value:
            print(f"  PYTHONPATH={diagnostics.pythonpath_value}")
        else:
            print("  PYTHONPATH: (not set - Python disabled)")

        if diagnostics.pythonhome_value:
            print(f"  PYTHONHOME={diagnostics.pythonhome_value}")
        else:
            print("  PYTHONHOME: (not set - Python disabled)")

        if diagnostics.python_available:
            print("  LLDB_DISABLE_PYTHON: (removed - Python enabled)")
        else:
            print("  LLDB_DISABLE_PYTHON: 1 (Python disabled)")
        print()

        # Print recommendations
        if diagnostics.is_ready():
            print("✓ Python environment is ready for full 'bt all' backtraces!")
            print()
            print("You can now use:")
            print("  - Full stack traces with 'bt all' command")
            print("  - Python scripting in LLDB")
            print("  - Advanced variable inspection")
            return 0
        elif diagnostics.status == LldbPythonStatus.INCOMPLETE:
            print("⚠ Python environment is incomplete.")
            print()
            print("Troubleshooting:")
            print("  1. Try reinstalling LLDB: clang-tool-chain purge --yes && clang-tool-chain install lldb")
            print("  2. Check archive integrity during download")
            print("  3. Report issue at: https://github.com/zackees/clang-tool-chain/issues")
            return 1
        else:  # missing
            print("✗ Python modules are not bundled with this LLDB installation.")
            print()
            print("This means:")
            print("  - 'bt all' backtraces may be incomplete")
            print("  - Python scripting is disabled")
            print("  - Advanced features not available")
            print()
            print("Note: This may be expected for older LLDB installations.")
            print("      The current release includes Python 3.10 modules.")
            print()
            print("To get Python support:")
            print("  1. Update to latest version: pip install --upgrade clang-tool-chain")
            print("  2. Reinstall LLDB: clang-tool-chain purge --yes && clang-tool-chain install lldb")
            return 1

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print(f"Error checking LLDB Python environment: {e}")
        return 1


def execute_lldb_tool(tool_name: str, args: list[str] | None = None, print_mode: bool = False) -> NoReturn | int:
    """
    Execute an LLDB tool with the given arguments.

    Args:
        tool_name: Name of the LLDB tool
        args: Command-line arguments (default: sys.argv[1:])
        print_mode: If True, run in automated crash analysis mode and return exit code

    Returns:
        Exit code if print_mode is True

    Raises:
        SystemExit: Exits with the tool's return code if not in print_mode
    """
    if args is None:
        args = sys.argv[1:]

    tool_path = find_lldb_tool(tool_name)
    platform_name, _ = get_platform_info()

    # Check for python310.dll on Windows (required by liblldb.dll)
    if platform_name == "win":
        bin_dir = get_lldb_binary_dir()
        python_dll = bin_dir / "python310.dll"
        if not python_dll.exists():
            error_msg = (
                f"ERROR: python310.dll is missing from LLDB installation\n"
                f"Expected location: {python_dll}\n"
                f"\n"
                f"This is a critical dependency for liblldb.dll. The LLDB archive may be incomplete.\n"
                f"\n"
                f"Troubleshooting:\n"
                f"  1. Reinstall LLDB: clang-tool-chain purge --yes && clang-tool-chain install lldb\n"
                f"  2. If the problem persists, report it at:\n"
                f"     https://github.com/zackees/clang-tool-chain/issues\n"
            )
            logger.error(error_msg)
            if print_mode:
                # In print mode, write error to stderr and return error code
                sys.stderr.write(error_msg)
                return 1
            else:
                # In interactive mode, print error and exit
                sys.stderr.write(error_msg)
                sys.exit(1)

    cmd = [str(tool_path)] + args

    logger.info(f"Executing LLDB tool: {' '.join(cmd)}")

    # Execute tool
    if platform_name == "win":
        # Windows: use subprocess with modified PATH to find DLLs
        try:
            # Add LLDB bin directory to PATH so DLLs can be found
            bin_dir = get_lldb_binary_dir()
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

            # Configure Python environment for LLDB
            # Python 3.10 site-packages are bundled with LLDB for full "bt all" support
            install_dir = downloader.get_lldb_install_dir(platform_name, get_platform_info()[1])
            python_dir = install_dir / "python"

            if python_dir.exists():
                # Set PYTHONPATH to site-packages directory
                site_packages = python_dir / "Lib" / "site-packages"
                if site_packages.exists():
                    env["PYTHONPATH"] = str(site_packages)
                    logger.debug(f"Set PYTHONPATH={site_packages}")

                # Set PYTHONHOME to Python installation directory
                # This helps LLDB find the Python standard library
                env["PYTHONHOME"] = str(python_dir)
                logger.debug(f"Set PYTHONHOME={python_dir}")

                # Remove LLDB_DISABLE_PYTHON if it exists (enable Python scripting)
                if "LLDB_DISABLE_PYTHON" in env:
                    del env["LLDB_DISABLE_PYTHON"]
                    logger.debug("Removed LLDB_DISABLE_PYTHON (Python enabled)")
            else:
                # Python modules not bundled (fallback to system Python or disable)
                logger.warning(f"Python directory not found at {python_dir}, Python features may be limited")
                # Keep Python disabled if modules aren't available
                env["LLDB_DISABLE_PYTHON"] = "1"

            result = subprocess.run(cmd, env=env)

            if print_mode:
                return result.returncode
            sys.exit(result.returncode)
        except FileNotFoundError as err:
            raise RuntimeError(f"LLDB tool not found: {tool_path}") from err
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            raise RuntimeError(f"Error executing LLDB tool: {e}") from e
    else:
        # Unix: use subprocess for consistency (execv doesn't allow returning)
        try:
            # Get the LLDB installation directory
            install_dir = downloader.get_lldb_install_dir(platform_name, get_platform_info()[1])
            lib_dir = install_dir / "lib"

            # Check if lib directory exists
            if lib_dir.exists():
                logger.debug(f"Adding {lib_dir} to LD_LIBRARY_PATH")
                env = os.environ.copy()
                # Prepend lib directory to LD_LIBRARY_PATH
                existing_ld_path = env.get("LD_LIBRARY_PATH", "")
                if existing_ld_path:
                    env["LD_LIBRARY_PATH"] = f"{lib_dir}{os.pathsep}{existing_ld_path}"
                else:
                    env["LD_LIBRARY_PATH"] = str(lib_dir)
            else:
                logger.debug(f"No lib directory found at {lib_dir}, using system libraries")
                env = os.environ.copy()

            # Configure Python environment for LLDB (future: Linux/macOS support)
            python_dir = install_dir / "python"
            if python_dir.exists():
                # Set PYTHONPATH to site-packages directory
                site_packages = python_dir / "Lib" / "site-packages"
                if site_packages.exists():
                    env["PYTHONPATH"] = str(site_packages)
                    logger.debug(f"Set PYTHONPATH={site_packages}")

                # Set PYTHONHOME to Python installation directory
                env["PYTHONHOME"] = str(python_dir)
                logger.debug(f"Set PYTHONHOME={python_dir}")

                # Remove LLDB_DISABLE_PYTHON if it exists
                if "LLDB_DISABLE_PYTHON" in env:
                    del env["LLDB_DISABLE_PYTHON"]
                    logger.debug("Removed LLDB_DISABLE_PYTHON (Python enabled)")

            result = subprocess.run(cmd, env=env)

            if print_mode:
                return result.returncode
            sys.exit(result.returncode)
        except FileNotFoundError as err:
            raise RuntimeError(f"LLDB tool not found: {tool_path}") from err
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            raise RuntimeError(f"Error executing LLDB tool: {e}") from e
