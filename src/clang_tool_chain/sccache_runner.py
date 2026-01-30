"""
sccache runner using iso-env for isolated execution.

This module provides fallback functionality to run sccache via iso-env
when sccache is not found in the system PATH.

Includes automatic retry logic for Windows when sccache server times out.
"""

import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

# Error patterns that indicate sccache server timeout/disconnection
SCCACHE_SERVER_ERROR_PATTERNS = [
    "Failed to send data to or receive data from server",
    "failed to execute compile",
    "Connection refused",
    "server returned an error",
]

# Retry configuration for Windows sccache server timeout
SCCACHE_RETRY_COUNT = 3
SCCACHE_RETRY_DELAY_SECONDS = 2.0


def _is_sccache_server_error(output: str) -> bool:
    """
    Check if the output contains sccache server timeout/disconnection errors.

    Args:
        output: Combined stdout/stderr output from sccache command

    Returns:
        True if the output contains known sccache server error patterns
    """
    output_lower = output.lower()
    return any(pattern.lower() in output_lower for pattern in SCCACHE_SERVER_ERROR_PATTERNS)


def _run_with_retry(
    cmd: list[str],
    max_retries: int = SCCACHE_RETRY_COUNT,
    retry_delay: float = SCCACHE_RETRY_DELAY_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    """
    Run a command with automatic retry on sccache server errors (Windows only).

    On Windows, sccache server can time out during idle periods, causing
    compilation failures with errors like "Failed to send data to server".
    This function detects these errors and retries after a short delay,
    allowing the sccache server to restart automatically.

    Args:
        cmd: Command to execute
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay in seconds between retries (default: 2.0)

    Returns:
        CompletedProcess result from subprocess.run()

    Note:
        On non-Windows platforms, this function runs the command once without retry.
    """
    is_windows = platform.system() == "Windows"

    for attempt in range(max_retries + 1):
        # Capture output to check for sccache errors
        result = subprocess.run(cmd, capture_output=True)

        # If successful, return immediately
        if result.returncode == 0:
            # Print captured output to maintain expected behavior
            if result.stdout:
                sys.stdout.buffer.write(result.stdout)
            if result.stderr:
                sys.stderr.buffer.write(result.stderr)
            return result

        # Check for sccache server errors (Windows only)
        if is_windows and attempt < max_retries:
            combined_output = (result.stdout or b"").decode("utf-8", errors="replace")
            combined_output += (result.stderr or b"").decode("utf-8", errors="replace")

            if _is_sccache_server_error(combined_output):
                print(
                    f"[sccache] Server connection error detected, retrying in {retry_delay}s "
                    f"(attempt {attempt + 1}/{max_retries})...",
                    file=sys.stderr,
                )
                time.sleep(retry_delay)
                continue

        # Not a retryable error or max retries reached, print output and return
        if result.stdout:
            sys.stdout.buffer.write(result.stdout)
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
        return result

    # Should not reach here, but return last result if we do
    return result  # type: ignore[possibly-undefined]


def get_sccache_path() -> str | None:
    """
    Get the path to sccache executable.

    Returns:
        Path to sccache if found in PATH, None otherwise.
    """
    return shutil.which("sccache")


def get_iso_env_cache_dir() -> Path:
    """
    Get the cache directory for iso-env sccache installation.

    Returns:
        Path to the cache directory.
    """
    # Use the same directory as clang-tool-chain for consistency
    from .settings_warnings import warn_download_path_override

    base_dir = warn_download_path_override()
    cache_dir = Path(base_dir) / "sccache-env" if base_dir else Path.home() / ".clang-tool-chain" / "sccache-env"

    return cache_dir


def run_sccache_via_isoenv(args: list[str]) -> int:
    """
    Run sccache via iso-env in an isolated environment.

    Args:
        args: Command-line arguments to pass to sccache

    Returns:
        Exit code from sccache execution

    Environment Variables:
        SCCACHE_IDLE_TIMEOUT: Set to 60 seconds to prevent server shutdown during parallel builds
    """
    try:
        from iso_env import IsoEnv, IsoEnvArgs, Requirements
    except ImportError:
        print("=" * 70, file=sys.stderr)
        print("ERROR: iso-env package not found", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print("iso-env is required as a fallback when sccache is not in PATH.", file=sys.stderr)
        print("Please install it with:", file=sys.stderr)
        print("  pip install clang-tool-chain", file=sys.stderr)
        print(file=sys.stderr)
        print("Or install sccache directly:", file=sys.stderr)
        print("  pip install clang-tool-chain[sccache]", file=sys.stderr)
        print(file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    cache_dir = get_iso_env_cache_dir()

    # Set sccache idle timeout to 60 seconds to prevent server shutdown during parallel builds
    # A short timeout (e.g., 5 seconds) causes "Failed to send data to server" errors
    # when the server shuts down mid-build during gaps in compilation
    import os

    if "SCCACHE_IDLE_TIMEOUT" not in os.environ:
        os.environ["SCCACHE_IDLE_TIMEOUT"] = "60"

    # Create iso-env configuration for sccache
    try:
        # First time setup - create the environment
        print(f"Setting up isolated sccache environment at {cache_dir}...", file=sys.stderr)

        # Create requirements for sccache
        requirements_txt = "sccache>=0.7.0\n"
        requirements = Requirements(requirements_txt)

        # Create IsoEnvArgs
        iso_args = IsoEnvArgs(venv_path=cache_dir, build_info=requirements)

        # Create IsoEnv instance
        env = IsoEnv(iso_args)

        # Run sccache with the provided arguments
        result = env.run(["sccache"] + args)

        return result.returncode if result.returncode is not None else 0  # type: ignore[no-any-return]

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print("=" * 70, file=sys.stderr)
        print("ERROR: Failed to run sccache via iso-env", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(f"Error details: {e}", file=sys.stderr)
        print(file=sys.stderr)
        print("You may want to install sccache directly:", file=sys.stderr)
        print("  pip install clang-tool-chain[sccache]", file=sys.stderr)
        print("  cargo install sccache", file=sys.stderr)
        print("  # or use your system package manager", file=sys.stderr)
        print(file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1


def run_sccache(args: list[str]) -> int:
    """
    Run sccache, using iso-env as fallback if not found in PATH.

    Args:
        args: Command-line arguments to pass to sccache

    Returns:
        Exit code from sccache execution

    Environment Variables:
        SCCACHE_IDLE_TIMEOUT: Set to 60 seconds to prevent server shutdown during parallel builds
    """
    import os

    # Set sccache idle timeout to 60 seconds to prevent server shutdown during parallel builds
    # A short timeout (e.g., 5 seconds) causes "Failed to send data to server" errors
    # when the server shuts down mid-build during gaps in compilation
    if "SCCACHE_IDLE_TIMEOUT" not in os.environ:
        os.environ["SCCACHE_IDLE_TIMEOUT"] = "60"

    sccache_path = get_sccache_path()

    if sccache_path:
        # sccache found in PATH, use it directly
        cmd = [sccache_path] + args

        try:
            result = _run_with_retry(cmd)
            return result.returncode
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            print(f"ERROR: Failed to execute sccache: {e}", file=sys.stderr)
            return 1
    else:
        # sccache not found in PATH, use iso-env fallback
        print("sccache not found in PATH, using isolated environment...", file=sys.stderr)
        print(file=sys.stderr)
        return run_sccache_via_isoenv(args)


def run_sccache_with_compiler(compiler_path: str, args: list[str]) -> int:
    """
    Run sccache with a compiler, using iso-env as fallback if sccache not found in PATH.

    Args:
        compiler_path: Path to the compiler executable
        args: Command-line arguments to pass to the compiler

    Returns:
        Exit code from sccache execution

    Environment Variables:
        SCCACHE_IDLE_TIMEOUT: Set to 60 seconds to prevent server shutdown during parallel builds
    """
    import os

    # Set sccache idle timeout to 60 seconds to prevent server shutdown during parallel builds
    # A short timeout (e.g., 5 seconds) causes "Failed to send data to server" errors
    # when the server shuts down mid-build during gaps in compilation
    if "SCCACHE_IDLE_TIMEOUT" not in os.environ:
        os.environ["SCCACHE_IDLE_TIMEOUT"] = "60"

    sccache_path = get_sccache_path()

    if sccache_path:
        # sccache found in PATH, use it directly
        cmd = [sccache_path, compiler_path] + args

        try:
            result = _run_with_retry(cmd)
            exit_code = result.returncode

            # Post-link DLL deployment (Windows GNU ABI only)
            if exit_code == 0:
                from .abi import _should_use_gnu_abi
                from .deployment.dll_deployer import post_link_dll_deployment
                from .execution.core import _extract_output_path
                from .logging_config import configure_logging
                from .platform.detection import get_platform_info

                logger = configure_logging(__name__)

                platform_name, _ = get_platform_info()

                # Determine tool name from compiler path (clang or clang++)
                tool_name = "clang++" if "clang++" in compiler_path.lower() else "clang"

                output_exe = _extract_output_path(args, tool_name)
                if output_exe is not None:
                    use_gnu = _should_use_gnu_abi(platform_name, args)
                    try:
                        post_link_dll_deployment(output_exe, platform_name, use_gnu)
                    except KeyboardInterrupt as ke:
                        handle_keyboard_interrupt_properly(ke)
                    except Exception as e:
                        logger.warning(f"DLL deployment failed: {e}")

            return exit_code
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            print(f"ERROR: Failed to execute sccache: {e}", file=sys.stderr)
            return 1
    else:
        # sccache not found in PATH, use iso-env fallback
        print("sccache not found in PATH, using isolated environment...", file=sys.stderr)
        print(file=sys.stderr)
        exit_code = run_sccache_via_isoenv([compiler_path] + args)

        # Post-link DLL deployment (Windows GNU ABI only)
        if exit_code == 0:
            from .abi import _should_use_gnu_abi
            from .deployment.dll_deployer import post_link_dll_deployment
            from .execution.core import _extract_output_path
            from .logging_config import configure_logging
            from .platform.detection import get_platform_info

            logger = configure_logging(__name__)

            platform_name, _ = get_platform_info()

            # Determine tool name from compiler path (clang or clang++)
            tool_name = "clang++" if "clang++" in compiler_path.lower() else "clang"

            output_exe = _extract_output_path(args, tool_name)
            if output_exe is not None:
                use_gnu = _should_use_gnu_abi(platform_name, args)
                try:
                    post_link_dll_deployment(output_exe, platform_name, use_gnu)
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    logger.warning(f"DLL deployment failed: {e}")

        return exit_code
