"""
Core tool execution functions for clang-tool-chain.

This module provides the fundamental execution infrastructure for running
LLVM/Clang tools with proper platform detection, SDK configuration, ABI setup,
and linker management.

The main functions are:
- execute_tool(): Execute a tool and exit with its return code (does not return)
- run_tool(): Execute a tool and return its exit code (returns to caller)
- sccache_clang_main(): sccache wrapper for clang with GNU ABI
- sccache_clang_cpp_main(): sccache wrapper for clang++ with GNU ABI
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from clang_tool_chain.abi import _should_use_gnu_abi
from clang_tool_chain.deployment.dll_deployer import post_link_dependency_deployment, post_link_dll_deployment
from clang_tool_chain.execution.arg_transformers import ArgumentPipeline, ToolContext, create_default_pipeline
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.platform.detection import get_platform_info
from clang_tool_chain.platform.paths import find_sccache_binary, find_tool_binary
from clang_tool_chain.sccache_runner import _run_with_retry

# Configure logging using centralized configuration
logger = configure_logging(__name__)

# Global pipeline instance (created once and reused)
_default_pipeline: ArgumentPipeline | None = None


def _extract_deploy_dependencies_flag(args: list[str]) -> tuple[list[str], bool]:
    """
    Extract --deploy-dependencies flag from arguments.

    This flag is specific to clang-tool-chain and must be stripped before
    passing arguments to clang, as clang doesn't recognize it.

    When the flag is present, this also sets CLANG_TOOL_CHAIN_DEPLOY_DEPENDENCIES=1
    environment variable so transformers (like RPathTransformer) can detect it.

    Args:
        args: Compiler/linker arguments

    Returns:
        Tuple of (filtered_args, should_deploy)
        - filtered_args: Arguments with --deploy-dependencies removed
        - should_deploy: True if the flag was present

    Examples:
        >>> _extract_deploy_dependencies_flag(["test.cpp", "--deploy-dependencies", "-o", "test.dll"])
        (['test.cpp', '-o', 'test.dll'], True)
        >>> _extract_deploy_dependencies_flag(["test.cpp", "-o", "test.dll"])
        (['test.cpp', '-o', 'test.dll'], False)
    """
    if "--deploy-dependencies" in args:
        filtered = [arg for arg in args if arg != "--deploy-dependencies"]
        # Set env var so transformers can detect this flag (e.g., RPathTransformer)
        os.environ["CLANG_TOOL_CHAIN_DEPLOY_DEPENDENCIES"] = "1"
        return (filtered, True)
    return (args, False)


def _get_pipeline() -> ArgumentPipeline:
    """
    Get or create the default argument transformation pipeline.

    The pipeline is created once and reused for all subsequent calls
    to avoid repeated initialization.

    Returns:
        Configured ArgumentPipeline instance
    """
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = create_default_pipeline()
    return _default_pipeline


def _transform_arguments(args: list[str], tool_name: str, platform_name: str, arch: str, use_msvc: bool) -> list[str]:
    """
    Apply platform-specific argument transformations using the pipeline.

    Args:
        args: Original compiler/linker arguments
        tool_name: Name of the tool being executed
        platform_name: Platform name (e.g., "win", "darwin", "linux")
        arch: Architecture (e.g., "x86_64", "arm64")
        use_msvc: True if using MSVC ABI

    Returns:
        Transformed arguments with platform-specific flags added
    """
    context = ToolContext(
        platform_name=platform_name,
        arch=arch,
        tool_name=tool_name,
        use_msvc=use_msvc,
    )

    pipeline = _get_pipeline()
    return pipeline.transform(args, context)


def _transform_args_with_error_handling(
    args: list[str], tool_name: str, platform_name: str, arch: str, use_msvc: bool
) -> list[str]:
    """
    Apply argument transformation with standard error handling.

    Wraps _transform_arguments with error handling that prints warnings
    but allows continuation with original arguments if transformation fails.

    Args:
        args: Original compiler/linker arguments
        tool_name: Name of the tool being executed
        platform_name: Platform name (e.g., "win", "darwin", "linux")
        arch: Architecture (e.g., "x86_64", "arm64")
        use_msvc: True if using MSVC ABI

    Returns:
        Transformed arguments, or original arguments if transformation fails
    """
    try:
        transformed = _transform_arguments(args, tool_name, platform_name, arch, use_msvc)
        logger.debug(f"Transformed arguments: {len(transformed)} args")
        return transformed
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        # If transformation fails, let the tool try anyway (may fail at compile time)
        logger.error(f"Failed to transform arguments: {e}")
        print(f"\nWarning: Failed to apply platform-specific transformations: {e}", file=sys.stderr)
        print("Continuing with original arguments (may fail)...\n", file=sys.stderr)
        return args


def _handle_post_link_deployment(
    args: list[str],
    tool_name: str,
    platform_name: str,
    use_msvc: bool,
    deploy_dependencies_requested: bool,
) -> None:
    """
    Handle post-link deployment for Windows DLLs and cross-platform dependencies.

    This function encapsulates all post-link deployment logic:
    1. Windows GNU ABI automatic DLL deployment (for .exe and .dll outputs)
    2. Opt-in dependency deployment via --deploy-dependencies flag (all platforms)

    Args:
        args: Compiler/linker arguments (used to extract output paths)
        tool_name: Name of the tool ("clang" or "clang++")
        platform_name: Platform name (e.g., "win", "darwin", "linux")
        use_msvc: True if using MSVC ABI
        deploy_dependencies_requested: True if --deploy-dependencies flag was used
    """
    use_gnu = _should_use_gnu_abi(platform_name, args) and not use_msvc

    # Windows GNU ABI .exe/.dll deployment (automatic)
    if platform_name == "win":
        output_exe = _extract_output_path(args, tool_name)
        if output_exe is not None:
            try:
                post_link_dll_deployment(output_exe, platform_name, use_gnu)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                logger.warning(f"DLL deployment failed: {e}")

    # Dependency deployment (opt-in via --deploy-dependencies, all platforms)
    if deploy_dependencies_requested:
        # Try shared library first
        shared_lib_path = _extract_shared_library_output_path(args, tool_name)
        if shared_lib_path is not None:
            try:
                post_link_dependency_deployment(shared_lib_path, platform_name, use_gnu)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                logger.warning(f"Dependency deployment failed: {e}")
        else:
            # Try executable
            exe_path = _extract_executable_output_path(args, tool_name)
            if exe_path is not None:
                try:
                    post_link_dependency_deployment(exe_path, platform_name, use_gnu)
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    logger.warning(f"Dependency deployment failed: {e}")


def _extract_output_path(args: list[str], tool_name: str) -> Path | None:
    """
    Extract the output binary path from compiler/linker arguments.

    Args:
        args: Compiler/linker arguments
        tool_name: Name of the tool being executed

    Returns:
        Path to output binary (.exe or .dll), or None if not a linking operation

    Examples:
        >>> _extract_output_path(["-o", "test.exe", "test.cpp"], "clang++")
        Path('test.exe')
        >>> _extract_output_path(["-otest.exe", "test.cpp"], "clang++")
        Path('test.exe')
        >>> _extract_output_path(["-o", "test.dll", "-shared", "test.cpp"], "clang++")
        Path('test.dll')
        >>> _extract_output_path(["-c", "test.cpp"], "clang++")
        None
    """
    # Skip if compile-only flag present
    if "-c" in args:
        return None

    # Only process clang/clang++ commands
    if tool_name not in ("clang", "clang++"):
        return None

    # Look for -o flag
    i = 0
    while i < len(args):
        arg = args[i]

        # Format: -o output.exe or -o output.dll
        if arg == "-o" and i + 1 < len(args):
            output_path = Path(args[i + 1]).resolve()
            # Only deploy for .exe and .dll files (Windows linking operations)
            if output_path.suffix.lower() in (".exe", ".dll"):
                return output_path
            return None

        # Format: -ooutput.exe or -ooutput.dll
        if arg.startswith("-o") and len(arg) > 2:
            output_path = Path(arg[2:]).resolve()
            if output_path.suffix.lower() in (".exe", ".dll"):
                return output_path
            return None

        i += 1

    # No -o flag: default output is a.exe on Windows (only for linking, not compiling)
    # But we can't determine if it's a link operation without -o, so skip
    return None


def _extract_executable_output_path(args: list[str], tool_name: str) -> Path | None:
    """
    Extract the output executable path from compiler/linker arguments.

    This detects executable builds (not shared libraries, not compile-only)
    and returns the output path on all platforms.

    Args:
        args: Compiler/linker arguments
        tool_name: Name of the tool being executed

    Returns:
        Path to output executable, or None if not building an executable

    Examples:
        >>> _extract_executable_output_path(["test.cpp", "-o", "test"], "clang++")
        Path('test')
        >>> _extract_executable_output_path(["test.cpp", "-o", "test.exe"], "clang++")
        Path('test.exe')
        >>> _extract_executable_output_path(["-c", "test.cpp", "-o", "test.o"], "clang++")
        None  # Compile-only
        >>> _extract_executable_output_path(["-shared", "lib.cpp", "-o", "lib.so"], "clang++")
        None  # Shared library, not executable
    """
    # Skip if compile-only flag present
    if "-c" in args:
        return None

    # Only process clang/clang++ commands
    if tool_name not in ("clang", "clang++"):
        return None

    # Skip if building shared library
    if "-shared" in args:
        return None

    # Parse -o flag for output path
    output_path = None
    i = 0
    while i < len(args):
        arg = args[i]

        # Format: -o output
        if arg == "-o" and i + 1 < len(args):
            output_path = Path(args[i + 1]).resolve()
            break

        # Format: -ooutput
        if arg.startswith("-o") and len(arg) > 2:
            output_path = Path(arg[2:]).resolve()
            break

        i += 1

    if output_path is None:
        return None

    # Exclude object files and static libraries
    suffix = output_path.suffix.lower()
    if suffix in (".o", ".obj", ".a", ".lib"):
        return None

    return output_path


def _extract_shared_library_output_path(args: list[str], tool_name: str) -> Path | None:
    """
    Extract the output shared library path from compiler/linker arguments.

    This detects shared library builds (-shared flag) and returns the output path
    for .dll, .so, or .dylib files.

    Args:
        args: Compiler/linker arguments
        tool_name: Name of the tool being executed

    Returns:
        Path to output shared library, or None if not building a shared library

    Examples:
        >>> _extract_shared_library_output_path(["-shared", "lib.cpp", "-o", "lib.dll"], "clang++")
        Path('lib.dll')
        >>> _extract_shared_library_output_path(["-shared", "lib.cpp", "-o", "lib.so"], "clang++")
        Path('lib.so')
        >>> _extract_shared_library_output_path(["lib.cpp", "-o", "lib.dll"], "clang++")
        None  # No -shared flag
    """
    # Skip if compile-only flag present
    if "-c" in args:
        return None

    # Only process clang/clang++ commands
    if tool_name not in ("clang", "clang++"):
        return None

    # Check for -shared flag (required for shared library)
    if "-shared" not in args:
        return None

    # Parse -o flag for output path
    output_path = None
    i = 0
    while i < len(args):
        arg = args[i]

        # Format: -o output.dll
        if arg == "-o" and i + 1 < len(args):
            output_path = Path(args[i + 1]).resolve()
            break

        # Format: -ooutput.dll
        if arg.startswith("-o") and len(arg) > 2:
            output_path = Path(arg[2:]).resolve()
            break

        i += 1

    if output_path is None:
        return None

    # Accept shared library extensions
    suffix = output_path.suffix.lower()
    if suffix in (".dll", ".so", ".dylib") or ".so." in output_path.name:
        return output_path

    return None


# ============================================================================
# Unified clang execution implementation
# ============================================================================


def _execute_clang_impl(
    tool_name: str,
    args: list[str],
    use_msvc: bool = False,
    use_sccache: bool = False,
    return_code: bool = False,
) -> int:
    """
    Unified implementation for executing clang/clang++ with or without sccache.

    This function consolidates the shared logic between direct clang execution
    and sccache-wrapped execution, handling:
    - Argument extraction and transformation
    - Environment setup (SCCACHE_IDLE_TIMEOUT)
    - Tool binary discovery
    - Command execution (with or without sccache, with or without retry)
    - Post-link deployment (DLLs, dependencies)
    - Error handling and exit

    Args:
        tool_name: Name of the tool ("clang" or "clang++")
        args: Arguments to pass to the tool
        use_msvc: If True on Windows, skip GNU ABI injection (use MSVC target)
        use_sccache: If True, wrap command with sccache and use retry logic
        return_code: If True, return the exit code; if False, call sys.exit()

    Returns:
        Exit code from the tool (only if return_code=True)

    Raises:
        RuntimeError: If the tool cannot be found (only if return_code=True)
    """
    # Extract --deploy-dependencies flag (must be stripped before passing to clang)
    args, deploy_dependencies_requested = _extract_deploy_dependencies_flag(args)

    # Set sccache idle timeout to minimize file locking window
    if use_sccache and "SCCACHE_IDLE_TIMEOUT" not in os.environ:
        os.environ["SCCACHE_IDLE_TIMEOUT"] = "5"

    # Find tool binaries
    try:
        tool_path = find_tool_binary(tool_name)
        sccache_path = find_sccache_binary() if use_sccache else None
    except RuntimeError as e:
        if return_code:
            raise
        logger.error(f"Failed to find tool binary: {e}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Apply platform-specific argument transformations
    platform_name, arch = get_platform_info()
    args = _transform_args_with_error_handling(args, tool_name, platform_name, arch, use_msvc)

    # Build command
    cmd = [sccache_path, str(tool_path)] + args if use_sccache and sccache_path else [str(tool_path)] + args

    logger.info(f"Executing {'sccache + ' if use_sccache else ''}{tool_name} (with {len(args)} args)")

    # Execute command
    try:
        result = _run_with_retry(cmd) if use_sccache else subprocess.run(cmd)

        # Post-link deployment (all platforms)
        if result.returncode == 0:
            _handle_post_link_deployment(args, tool_name, platform_name, use_msvc, deploy_dependencies_requested)

        if return_code:
            return result.returncode
        sys.exit(result.returncode)

    except FileNotFoundError as err:
        if return_code:
            raise RuntimeError(f"Tool not found: {tool_path}") from err
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Tool not found: {tool_path}", file=sys.stderr)
        print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
        print("This may be a permission or compatibility issue.", file=sys.stderr)
        print("\nTroubleshooting:", file=sys.stderr)
        print("  - Verify the binary is compatible with your system", file=sys.stderr)
        print("  - Check file permissions: chmod +x {tool_path}", file=sys.stderr)
        print("  - On macOS: Right-click > Open, then allow in Security settings", file=sys.stderr)
        print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        if return_code:
            raise RuntimeError(f"Error executing tool: {e}") from e
        error_type = "sccache" if use_sccache else "tool"
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Error executing {error_type}: {e}", file=sys.stderr)
        if not use_sccache:
            print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
            print(f"Arguments: {args}", file=sys.stderr)
            print("\nPlease report this issue at:", file=sys.stderr)
            print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # This should never be reached, but satisfies type checker
    return 1  # pragma: no cover


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
        CLANG_TOOL_CHAIN_USE_SYSTEM_LD: Set to '1' to use system linker instead of lld (macOS/Linux)
    """
    if args is None:
        args = sys.argv[1:]

    # Use unified implementation for clang/clang++
    if tool_name in ("clang", "clang++"):
        _execute_clang_impl(tool_name, args, use_msvc, use_sccache=False, return_code=False)
        # _execute_clang_impl calls sys.exit(), so this line is never reached
        raise AssertionError("Unreachable")  # pragma: no cover

    # Non-clang tools: simple execution without transformation or deployment
    logger.info(f"Executing tool: {tool_name} with {len(args)} arguments")
    logger.debug(f"Arguments: {args}")

    try:
        tool_path = find_tool_binary(tool_name)
    except RuntimeError as e:
        logger.error(f"Failed to find tool binary: {e}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    cmd = [str(tool_path)] + args
    logger.info(f"Executing command: {tool_path} (with {len(args)} args)")

    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Tool not found: {tool_path}", file=sys.stderr)
        print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
        print("This may be a permission or compatibility issue.", file=sys.stderr)
        print("\nTroubleshooting:", file=sys.stderr)
        print("  - Verify the binary is compatible with your system", file=sys.stderr)
        print("  - Check file permissions: chmod +x {tool_path}", file=sys.stderr)
        print("  - On macOS: Right-click > Open, then allow in Security settings", file=sys.stderr)
        print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Error executing tool: {e}", file=sys.stderr)
        print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
        print(f"Arguments: {args}", file=sys.stderr)
        print("\nPlease report this issue at:", file=sys.stderr)
        print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
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
        CLANG_TOOL_CHAIN_USE_SYSTEM_LD: Set to '1' to use system linker instead of lld (macOS/Linux)
    """
    if args is None:
        args = sys.argv[1:]

    # Use unified implementation for clang/clang++
    if tool_name in ("clang", "clang++"):
        return _execute_clang_impl(tool_name, args, use_msvc, use_sccache=False, return_code=True)

    # Non-clang tools: simple execution without transformation or deployment
    tool_path = find_tool_binary(tool_name)
    cmd = [str(tool_path)] + args

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except FileNotFoundError as err:
        raise RuntimeError(f"Tool not found: {tool_path}") from err
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        raise RuntimeError(f"Error executing tool: {e}") from e

    # This should never be reached (handle_keyboard_interrupt_properly doesn't return)
    return 1  # pragma: no cover


# ============================================================================
# sccache wrapper functions
# ============================================================================


def sccache_clang_main(use_msvc: bool = False) -> NoReturn:
    """
    Entry point for sccache + clang wrapper.

    Args:
        use_msvc: If True on Windows, use MSVC ABI instead of GNU ABI

    Environment Variables:
        SCCACHE_IDLE_TIMEOUT: Set to 5 seconds to minimize file locking window
    """
    _execute_clang_impl("clang", sys.argv[1:], use_msvc, use_sccache=True, return_code=False)
    # _execute_clang_impl calls sys.exit(), so this line is never reached
    raise AssertionError("Unreachable")  # pragma: no cover


def sccache_clang_cpp_main(use_msvc: bool = False) -> NoReturn:
    """
    Entry point for sccache + clang++ wrapper.

    Args:
        use_msvc: If True on Windows, use MSVC ABI instead of GNU ABI

    Environment Variables:
        SCCACHE_IDLE_TIMEOUT: Set to 5 seconds to minimize file locking window
    """
    _execute_clang_impl("clang++", sys.argv[1:], use_msvc, use_sccache=True, return_code=False)
    # _execute_clang_impl calls sys.exit(), so this line is never reached
    raise AssertionError("Unreachable")  # pragma: no cover
