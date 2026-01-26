"""
Platform-specific execution strategies for clang-tool-chain.

This module provides abstractions for executing tools with platform-specific
behavior (os.execv on Unix, subprocess on Windows with DLL deployment).
"""

import os
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from clang_tool_chain.abi import _should_use_gnu_abi
from clang_tool_chain.deployment.dll_deployer import post_link_dependency_deployment, post_link_dll_deployment
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging

logger = configure_logging(__name__)


@dataclass
class ExecutionContext:
    """
    Context for tool execution containing all necessary parameters.

    Attributes:
        tool_path: Absolute path to the tool binary
        args: Arguments to pass to the tool (not including the tool name)
        platform_name: Platform identifier (win, darwin, linux)
        arch: Architecture (x86_64, arm64)
        tool_name: Name of the tool (clang, clang++, etc.)
        use_msvc: True if using MSVC ABI (Windows only)
        deploy_dependencies: True if --deploy-dependencies flag was used
    """

    tool_path: Path
    args: list[str]
    platform_name: str
    arch: str
    tool_name: str
    use_msvc: bool = False
    deploy_dependencies: bool = False


class PlatformExecutor(ABC):
    """
    Abstract base class for platform-specific tool execution.

    Implementations must provide:
    - execute(): Run tool and exit with return code (does not return)
    - execute_and_return(): Run tool and return exit code to caller
    """

    @abstractmethod
    def execute(self, ctx: ExecutionContext) -> NoReturn:
        """
        Execute tool and exit with its return code (does not return).

        On Unix: Replaces current process with tool process (os.execv)
        On Windows: Runs tool and exits with its return code

        Args:
            ctx: Execution context

        Raises:
            SystemExit: Always (does not return to caller)
        """
        raise NotImplementedError

    @abstractmethod
    def execute_and_return(self, ctx: ExecutionContext) -> int:
        """
        Execute tool and return its exit code.

        Args:
            ctx: Execution context

        Returns:
            Tool exit code

        Raises:
            RuntimeError: If tool cannot be executed
        """
        raise NotImplementedError

    def _extract_output_path(self, args: list[str], tool_name: str) -> Path | None:
        """
        Extract the output binary path from compiler/linker arguments.

        Args:
            args: Compiler/linker arguments
            tool_name: Name of the tool being executed

        Returns:
            Path to output binary (.exe or .dll), or None if not a linking operation
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

        return None

    def _extract_shared_library_output_path(self, args: list[str], tool_name: str) -> Path | None:
        """
        Extract the output shared library path from compiler/linker arguments.

        Args:
            args: Compiler/linker arguments
            tool_name: Name of the tool being executed

        Returns:
            Path to output shared library, or None if not building a shared library
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


class WindowsExecutor(PlatformExecutor):
    """
    Windows-specific executor using subprocess with DLL deployment.

    After successful linking, automatically deploys MinGW runtime DLLs
    to the executable directory (for GNU ABI only).
    """

    def execute(self, ctx: ExecutionContext) -> NoReturn:
        """Execute tool and exit with its return code (Windows subprocess)."""
        cmd = [str(ctx.tool_path)] + ctx.args
        logger.debug("Using Windows subprocess execution")

        try:
            result = subprocess.run(cmd)

            # Post-link operations on success
            if result.returncode == 0:
                self._post_link_operations(ctx)

            sys.exit(result.returncode)
        except FileNotFoundError:
            self._handle_file_not_found_error(ctx.tool_path)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            self._handle_execution_error(ctx.tool_path, ctx.args, e)

    def execute_and_return(self, ctx: ExecutionContext) -> int:
        """Execute tool and return its exit code."""
        cmd = [str(ctx.tool_path)] + ctx.args

        try:
            result = subprocess.run(cmd)

            # Post-link operations on success
            if result.returncode == 0:
                self._post_link_operations(ctx)

            return result.returncode
        except FileNotFoundError as err:
            raise RuntimeError(f"Tool not found: {ctx.tool_path}") from err
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return 1  # Should not reach here
        except Exception as e:
            raise RuntimeError(f"Error executing tool: {e}") from e

    def _post_link_operations(self, ctx: ExecutionContext) -> None:
        """Perform post-link operations (DLL deployment) after successful build."""
        # Post-link DLL deployment (Windows GNU ABI only for .exe)
        output_exe = self._extract_output_path(ctx.args, ctx.tool_name)
        if output_exe is not None:
            use_gnu = _should_use_gnu_abi(ctx.platform_name, ctx.args) and not ctx.use_msvc
            try:
                post_link_dll_deployment(output_exe, ctx.platform_name, use_gnu)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                logger.warning(f"DLL deployment failed: {e}")

        # Shared library dependency deployment (when --deploy-dependencies flag used)
        if ctx.deploy_dependencies:
            shared_lib_path = self._extract_shared_library_output_path(ctx.args, ctx.tool_name)
            if shared_lib_path is not None:
                use_gnu = _should_use_gnu_abi(ctx.platform_name, ctx.args) and not ctx.use_msvc
                try:
                    post_link_dependency_deployment(shared_lib_path, ctx.platform_name, use_gnu)
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    logger.warning(f"Dependency deployment failed: {e}")

    def _handle_file_not_found_error(self, tool_path: Path) -> NoReturn:
        """Handle FileNotFoundError with detailed Windows troubleshooting."""
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Tool not found: {tool_path}", file=sys.stderr)
        print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
        print("This may be a permission or compatibility issue.", file=sys.stderr)
        print("\nTroubleshooting:", file=sys.stderr)
        print("  - Verify the binary is compatible with your Windows version", file=sys.stderr)
        print("  - Check Windows Defender or antivirus isn't blocking it", file=sys.stderr)
        print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    def _handle_execution_error(self, tool_path: Path, args: list[str], error: Exception) -> NoReturn:
        """Handle generic execution error with diagnostic information."""
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Error executing tool: {error}", file=sys.stderr)
        print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
        print(f"Arguments: {args}", file=sys.stderr)
        print("\nPlease report this issue at:", file=sys.stderr)
        print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)


class UnixExecutor(PlatformExecutor):
    """
    Unix-specific executor using os.execv to replace current process.

    On Unix systems, we use exec to replace the current process with
    the tool process, which is more efficient and maintains signal handling.
    """

    def execute(self, ctx: ExecutionContext) -> NoReturn:
        """Execute tool by replacing current process (os.execv)."""
        cmd = [str(ctx.tool_path)] + ctx.args
        logger.debug("Using Unix exec replacement")

        try:
            logger.info(f"Replacing process with: {ctx.tool_path}")
            os.execv(str(ctx.tool_path), cmd)
        except FileNotFoundError:
            self._handle_file_not_found_error(ctx.tool_path)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            sys.exit(1)  # Should not reach here
        except Exception as e:
            self._handle_execution_error(ctx.tool_path, ctx.args, e)

    def execute_and_return(self, ctx: ExecutionContext) -> int:
        """
        Execute tool and return its exit code.

        Note: On Unix, we use subprocess instead of exec since we need to return.
        """
        cmd = [str(ctx.tool_path)] + ctx.args

        try:
            result = subprocess.run(cmd)
            return result.returncode
        except FileNotFoundError as err:
            raise RuntimeError(f"Tool not found: {ctx.tool_path}") from err
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return 1  # Should not reach here
        except Exception as e:
            raise RuntimeError(f"Error executing tool: {e}") from e

    def _handle_file_not_found_error(self, tool_path: Path) -> NoReturn:
        """Handle FileNotFoundError with detailed Unix troubleshooting."""
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Tool not found: {tool_path}", file=sys.stderr)
        print("\nThe binary exists in the package but cannot be executed.", file=sys.stderr)
        print("This may be a permission or compatibility issue.", file=sys.stderr)
        print("\nTroubleshooting:", file=sys.stderr)
        print(f"  - Check file permissions: chmod +x {tool_path}", file=sys.stderr)
        print("  - Verify the binary is compatible with your system", file=sys.stderr)
        print("  - On macOS: Right-click > Open, then allow in Security settings", file=sys.stderr)
        print("  - Report issue: https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    def _handle_execution_error(self, tool_path: Path, args: list[str], error: Exception) -> NoReturn:
        """Handle generic execution error with diagnostic information."""
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Error executing tool: {error}", file=sys.stderr)
        print(f"\nUnexpected error while running: {tool_path}", file=sys.stderr)
        print(f"Arguments: {args}", file=sys.stderr)
        print("\nPlease report this issue at:", file=sys.stderr)
        print("https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)


def get_platform_executor(platform_name: str) -> PlatformExecutor:
    """
    Get the appropriate executor for the given platform.

    Args:
        platform_name: Platform identifier (win, darwin, linux)

    Returns:
        Platform-specific executor instance

    Raises:
        ValueError: If platform is not supported
    """
    if platform_name == "win":
        return WindowsExecutor()
    elif platform_name in ("darwin", "linux"):
        return UnixExecutor()
    else:
        raise ValueError(f"Unsupported platform: {platform_name}")
