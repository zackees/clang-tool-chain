"""
Emscripten tool execution support.

This module provides functionality for executing Emscripten tools (emcc, em++, etc.)
with proper Node.js runtime management and environment configuration.

Key Features:
- Automatic Emscripten tool discovery
- Three-tier Node.js availability system (bundled, system, auto-download)
- Proper environment variable setup for Emscripten
- Comprehensive error handling and user guidance
"""

import logging
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

logger = logging.getLogger(__name__)


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
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        logger.error(f"Unsupported architecture detected: {machine}")
        raise RuntimeError(
            f"Unsupported architecture: {machine}\n"
            f"clang-tool-chain currently supports: x86_64 (amd64) and arm64 (aarch64)\n"
            f"Your architecture: {machine}\n"
            f"If you believe this architecture should be supported, please report this at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.debug(f"Detected platform: {platform_name}, arch: {arch}")
    return platform_name, arch


def get_nodejs_install_dir_path(platform_name: str, arch: str) -> Path:
    """
    Get the installation directory path for Node.js.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")
        arch: Architecture ("x86_64", "arm64")

    Returns:
        Path to Node.js installation directory
    """
    return Path.home() / ".clang-tool-chain" / "nodejs" / platform_name / arch


def get_node_binary_name(platform_name: str) -> str:
    """
    Get the Node.js binary name for the given platform.

    Args:
        platform_name: Platform name ("win", "linux", "darwin")

    Returns:
        Binary name ("node.exe" for Windows, "node" for Unix)
    """
    return "node.exe" if platform_name == "win" else "node"


def find_emscripten_tool(tool_name: str) -> Path:
    """
    Find an Emscripten tool binary.

    Args:
        tool_name: Name of the tool (e.g., "emcc", "em++")

    Returns:
        Path to the tool executable

    Raises:
        RuntimeError: If the tool cannot be found
    """
    platform_name, arch = get_platform_info()

    # Ensure Emscripten is installed
    from .. import downloader

    downloader.ensure_emscripten_available(platform_name, arch)

    # Emscripten tools are Python scripts in the emscripten directory
    install_dir = Path.home() / ".clang-tool-chain" / "emscripten" / platform_name / arch
    emscripten_dir = install_dir / "emscripten"

    if not emscripten_dir.exists():
        raise RuntimeError(
            f"Emscripten directory not found: {emscripten_dir}\n"
            f"Installation may have failed or is incomplete.\n"
            f"Try removing ~/.clang-tool-chain/emscripten and running again."
        )

    # Emscripten tools are typically .py files
    tool_script = emscripten_dir / f"{tool_name}.py"
    if not tool_script.exists():
        # Try without .py extension (some versions may not have it)
        tool_script = emscripten_dir / tool_name
        if not tool_script.exists():
            raise RuntimeError(
                f"Emscripten tool not found: {tool_name}\n"
                f"Expected location: {tool_script}\n"
                f"Emscripten directory: {emscripten_dir}"
            )

    return tool_script


def find_emscripten_wasm_ld_binary() -> Path:
    """
    Find Emscripten's bundled wasm-ld binary.

    Unlike emcc/em++ (Python scripts in emscripten/ subdir), wasm-ld is a
    native binary in bin/ directory. Using Emscripten's bundled wasm-ld
    ensures LLVM version compatibility with emcc.

    Returns:
        Path to Emscripten's wasm-ld binary

    Raises:
        RuntimeError: If wasm-ld binary is not found
    """
    platform_name, arch = get_platform_info()

    # Ensure Emscripten is installed
    from .. import downloader

    downloader.ensure_emscripten_available(platform_name, arch)

    # wasm-ld is in bin/ directory (not emscripten/ subdir)
    install_dir = Path.home() / ".clang-tool-chain" / "emscripten" / platform_name / arch
    bin_dir = install_dir / "bin"

    if not bin_dir.exists():
        raise RuntimeError(
            f"Emscripten bin directory not found: {bin_dir}\n"
            f"Installation may have failed or is incomplete.\n"
            f"Try removing ~/.clang-tool-chain/emscripten and running again."
        )

    # Add .exe extension on Windows
    exe_ext = ".exe" if platform_name == "win" else ""
    wasm_ld_path = bin_dir / f"wasm-ld{exe_ext}"

    if not wasm_ld_path.exists():
        raise RuntimeError(
            f"Emscripten wasm-ld binary not found: {wasm_ld_path}\n"
            f"Expected location: {bin_dir}/wasm-ld{exe_ext}\n"
            f"Emscripten directory: {install_dir}\n"
            f"\n"
            f"This binary should be bundled with Emscripten and use the same\n"
            f"LLVM version as emcc. If missing, try reinstalling:\n"
            f"  clang-tool-chain purge\n"
            f"  clang-tool-chain install emscripten"
        )

    logger.info(f"Found Emscripten wasm-ld: {wasm_ld_path}")
    return wasm_ld_path


def ensure_nodejs_available() -> Path:
    """
    Ensure Node.js is available (bundled or system).

    This function implements a three-tier priority system for Node.js availability:
    1. Bundled Node.js: Check ~/.clang-tool-chain/nodejs/{platform}/{arch}/bin/node[.exe]
    2. System Node.js: Check system PATH via shutil.which("node")
    3. Auto-download: Automatically download bundled Node.js if neither exists

    The bundled Node.js is preferred because:
    - Known version and behavior
    - Minimal size (~10-15 MB compressed)
    - No user installation required
    - Consistent across all platforms

    System Node.js is used as fallback for users with existing installations,
    preserving backward compatibility.

    Returns:
        Path to node executable (bundled or system)

    Raises:
        RuntimeError: If Node.js cannot be installed and no system Node.js is available
    """
    platform_name, arch = get_platform_info()

    # Priority 1: Check for bundled Node.js (preferred, fast path <1ms)
    nodejs_install_dir = get_nodejs_install_dir_path(platform_name, arch)
    node_binary_name = get_node_binary_name(platform_name)
    bundled_node = nodejs_install_dir / "bin" / node_binary_name

    if bundled_node.exists():
        logger.info(f"Using bundled Node.js: {bundled_node}")
        logger.debug(f"Bundled Node.js location: {bundled_node}")
        return bundled_node

    # Priority 2: Check for system Node.js (fallback for existing installations)
    system_node = shutil.which("node")
    if system_node:
        logger.info(f"Using system Node.js: {system_node}")
        logger.debug(
            f"Bundled Node.js not found at {bundled_node}. "
            f"Using system Node.js from PATH as fallback. "
            f"To use bundled Node.js, it will be downloaded automatically on next run if system Node.js is removed."
        )
        return Path(system_node)

    # Priority 3: Auto-download bundled Node.js (one-time, ~10-30 seconds)
    logger.info("Node.js not found. Downloading bundled Node.js...")
    print("\n" + "=" * 60, file=sys.stderr)
    print("Node.js Auto-Download", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Node.js is required for Emscripten (WebAssembly compilation).", file=sys.stderr)
    print("Downloading minimal Node.js runtime (~10-15 MB)...", file=sys.stderr)
    print("This is a one-time download and will be cached for future use.", file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)

    try:
        # Import downloader and trigger download
        from .. import downloader

        downloader.ensure_nodejs_available(platform_name, arch)

        # Verify installation succeeded
        if bundled_node.exists():
            logger.info(f"Node.js successfully downloaded: {bundled_node}")
            print(f"\nNode.js successfully installed to: {nodejs_install_dir}", file=sys.stderr)
            print("Future compilations will use the cached Node.js runtime.\n", file=sys.stderr)
            return bundled_node
        else:
            # This should not happen (downloader should raise exception), but handle gracefully
            raise RuntimeError(
                f"Node.js download completed but binary not found at expected location:\n"
                f"  Expected: {bundled_node}\n"
                f"  Installation directory: {nodejs_install_dir}"
            )

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        # Download failed - provide helpful error message
        logger.error(f"Failed to download Node.js: {e}")
        print("\n" + "=" * 60, file=sys.stderr)
        print("Node.js Download Failed", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        print("\nWorkaround: Install Node.js manually", file=sys.stderr)
        print("  - Download from: https://nodejs.org/", file=sys.stderr)
        print("  - Linux: apt install nodejs / yum install nodejs", file=sys.stderr)
        print("  - macOS: brew install node", file=sys.stderr)
        print("  - Windows: Install from https://nodejs.org/", file=sys.stderr)
        print("\nAfter installation, ensure node is in your PATH.", file=sys.stderr)
        print("Verify with: node --version", file=sys.stderr)
        print("\nIf this problem persists, please report it at:", file=sys.stderr)
        print("  https://github.com/zackees/clang-tool-chain/issues", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)

        # Re-raise as RuntimeError for consistent error handling
        raise RuntimeError(
            "Failed to install bundled Node.js and no system Node.js found.\n"
            "Please install Node.js manually (see instructions above) or report this issue."
        ) from e


def execute_emscripten_tool(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute an Emscripten tool with the given arguments.

    Emscripten tools (emcc, em++) are Python scripts that require:
    1. Python interpreter
    2. Node.js runtime (for running WebAssembly) - bundled automatically
    3. Proper environment variables (EM_CONFIG, EMSCRIPTEN, etc.)

    Node.js is provided via three-tier priority system:
    - Bundled Node.js: Preferred, automatically downloaded on first use
    - System Node.js: Used if bundled not available (backward compatible)
    - Auto-download: Downloads bundled Node.js if neither exists

    Args:
        tool_name: Name of the tool to execute (e.g., "emcc", "em++")
        args: Arguments to pass to the tool (defaults to sys.argv[1:])

    Raises:
        RuntimeError: If the tool cannot be found or executed
    """
    if args is None:
        args = sys.argv[1:]

    logger.info(f"Executing Emscripten tool: {tool_name} with {len(args)} arguments")
    logger.debug(f"Arguments: {args}")

    # Find tool script
    try:
        tool_script = find_emscripten_tool(tool_name)
    except RuntimeError as e:
        logger.error(f"Failed to find Emscripten tool: {e}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Ensure Node.js is available (bundled or system)
    # This will auto-download bundled Node.js if needed
    try:
        node_path = ensure_nodejs_available()
        logger.debug(f"Node.js path: {node_path}")
    except RuntimeError as e:
        logger.error(f"Failed to ensure Node.js availability: {e}")
        # Error message already printed by ensure_nodejs_available()
        sys.exit(1)

    # Get platform info
    platform_name, arch = get_platform_info()
    install_dir = Path.home() / ".clang-tool-chain" / "emscripten" / platform_name / arch

    # CRITICAL: Verify .emscripten config file and clang binary are readable before execution
    # This prevents "config file not found" and "clang executable not found" errors
    # in parallel test execution on Windows where filesystem sync delays can make files
    # temporarily invisible to child processes
    config_path = install_dir / ".emscripten"

    # Verify clang binary exists and is accessible
    exe_ext = ".exe" if platform_name == "win" else ""
    clang_binary = install_dir / "bin" / f"clang{exe_ext}"

    if not config_path.exists():
        logger.error(f"Emscripten config file not found: {config_path}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Configuration Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Emscripten config file not found: {config_path}", file=sys.stderr)
        print("This may indicate installation is incomplete or filesystem sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    if not clang_binary.exists():
        logger.error(f"Clang binary not found: {clang_binary}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Installation Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Clang binary not found: {clang_binary}", file=sys.stderr)
        print("This may indicate installation is incomplete or filesystem sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Wait for config file and clang binary to be readable (handles filesystem sync delays on Windows)
    import time

    config_readable = False
    clang_readable = False
    attempt = 0
    for attempt in range(30):  # 30 * 0.1s = 3 seconds max
        try:
            # Check config file
            with open(config_path, encoding="utf-8") as f:
                content = f.read()
                if "LLVM_ROOT" in content:
                    config_readable = True

            # Check clang binary (if config is readable)
            if config_readable:
                with open(clang_binary, "rb") as f:  # type: ignore[assignment]
                    f.read(1)  # Just verify we can read from it
                clang_readable = True

            if config_readable and clang_readable:
                if attempt > 0:
                    elapsed = attempt * 0.1
                    logger.debug(
                        f"Config and clang binary became readable after {elapsed:.2f}s "
                        f"(filesystem sync delay, attempt {attempt + 1})"
                    )
                break
        except OSError as e:
            logger.debug(f"File accessibility check attempt {attempt + 1} failed: {e}")
        time.sleep(0.1)

    if not config_readable:
        logger.error(f"Emscripten config file exists but is not readable: {config_path}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Configuration Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Emscripten config file exists but is not readable: {config_path}", file=sys.stderr)
        print("This may indicate a filesystem permissions issue or sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    if not clang_readable:
        logger.error(f"Clang binary exists but is not readable: {clang_binary}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Installation Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Clang binary exists but is not readable: {clang_binary}", file=sys.stderr)
        print("This may indicate a filesystem permissions issue or sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Set up Emscripten environment variables
    env = os.environ.copy()
    # Use native OS paths - Emscripten is Python-based and handles platform paths correctly
    # Previous approach of converting to forward slashes caused path resolution issues on Windows
    env["EMSCRIPTEN"] = str(install_dir / "emscripten")
    env["EMSCRIPTEN_ROOT"] = str(install_dir / "emscripten")
    env["EM_CONFIG"] = str(config_path)

    # Add Node.js and Emscripten bin directories to PATH
    # Include Emscripten bin for consistency and to ensure tools can find LLVM binaries if needed
    node_bin_dir = node_path.parent
    emscripten_bin_dir = install_dir / "bin"
    env["PATH"] = f"{emscripten_bin_dir}{os.pathsep}{node_bin_dir}{os.pathsep}{env.get('PATH', '')}"
    logger.debug(f"Added to PATH: {emscripten_bin_dir}, {node_bin_dir}")

    # Build command: python tool_script.py args...
    python_exe = sys.executable
    cmd = [python_exe, str(tool_script)] + args

    logger.info(f"Executing command: {python_exe} {tool_script} (with {len(args)} args)")
    logger.debug(f"Environment: EMSCRIPTEN={env.get('EMSCRIPTEN')}")
    logger.debug(f"Environment: EM_CONFIG={env.get('EM_CONFIG')}")

    # Execute
    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        logger.error(f"Failed to execute Python: {python_exe}")
        print(f"\nError: Python interpreter not found: {python_exe}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.error(f"Failed to execute Emscripten tool: {e}")
        print(f"\nError executing {tool_name}: {e}", file=sys.stderr)
        sys.exit(1)


def execute_emscripten_tool_with_sccache(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute an Emscripten tool with sccache compiler caching.

    This function wraps Emscripten tools (emcc, em++) with sccache for faster compilation
    by caching intermediate compilation results. It uses Emscripten's built-in support
    for compiler wrappers via the EM_COMPILER_WRAPPER environment variable.

    Requirements:
    - sccache must be installed and available in PATH
    - All standard Emscripten requirements (Python, Node.js, etc.)

    The function automatically:
    1. Finds sccache binary in system PATH
    2. Configures Emscripten to use sccache via EM_COMPILER_WRAPPER
    3. Skips sanity checks (which don't work with compiler wrappers)
    4. Maintains all standard Emscripten environment setup

    Args:
        tool_name: Name of the tool to execute (e.g., "emcc", "em++")
        args: Arguments to pass to the tool (defaults to sys.argv[1:])

    Raises:
        RuntimeError: If sccache, the tool, or Node.js cannot be found

    Example:
        # Compile with sccache caching
        execute_emscripten_tool_with_sccache("emcc", ["-o", "output.wasm", "input.c"])
    """
    if args is None:
        args = sys.argv[1:]

    logger.info(f"Executing Emscripten tool with sccache: {tool_name} with {len(args)} arguments")
    logger.debug(f"Arguments: {args}")

    # Find sccache binary
    from ..platform.paths import find_sccache_binary

    try:
        sccache_path = find_sccache_binary()
        logger.info(f"Found sccache at: {sccache_path}")

        # Verify sccache works and get version
        try:
            version_result = subprocess.run(
                [str(sccache_path), "--version"], capture_output=True, text=True, timeout=10
            )
            sccache_version = version_result.stdout.strip() if version_result.returncode == 0 else "unknown"
            print(f"\n{'=' * 60}", file=sys.stderr)
            print("DEBUG: sccache verification", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)
            print(f"sccache path: {sccache_path}", file=sys.stderr)
            print(f"sccache version: {sccache_version}", file=sys.stderr)

            # Start sccache server to avoid timeouts during compilation
            # The server mode is more reliable than standalone mode for long-running compilations
            try:
                print("Starting sccache server...", file=sys.stderr)
                start_result = subprocess.run(
                    [str(sccache_path), "--start-server"], capture_output=True, text=True, timeout=30
                )
                if start_result.returncode == 0:
                    print("sccache server started successfully", file=sys.stderr)
                    logger.info("sccache server started")
                else:
                    # Server might already be running, which is fine
                    print(f"sccache server start returned: {start_result.returncode}", file=sys.stderr)
                    if start_result.stderr:
                        print(f"stderr: {start_result.stderr.strip()}", file=sys.stderr)

                # Check server status
                stats_result = subprocess.run(
                    [str(sccache_path), "--show-stats"], capture_output=True, text=True, timeout=10
                )
                if stats_result.returncode == 0:
                    print("sccache server is running", file=sys.stderr)
                    stats_output = stats_result.stdout
                    print(f"sccache stats: {stats_output}", file=sys.stderr)
                else:
                    print("Warning: Could not get sccache stats", file=sys.stderr)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                print(f"Warning: Could not start sccache server: {e}", file=sys.stderr)
                print("Continuing anyway - sccache will use standalone mode if needed", file=sys.stderr)
            print(f"{'=' * 60}\n", file=sys.stderr)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            print(f"Warning: Could not verify sccache version: {e}", file=sys.stderr)

    except RuntimeError as e:
        logger.error(f"Failed to find sccache: {e}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain sccache Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print("\nTo install sccache:", file=sys.stderr)
        print("  - cargo install sccache", file=sys.stderr)
        print("  - Or download from: https://github.com/mozilla/sccache/releases", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Find tool script
    try:
        tool_script = find_emscripten_tool(tool_name)
    except RuntimeError as e:
        logger.error(f"Failed to find Emscripten tool: {e}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Ensure Node.js is available (bundled or system)
    try:
        node_path = ensure_nodejs_available()
        logger.debug(f"Node.js path: {node_path}")
    except RuntimeError as e:
        logger.error(f"Failed to ensure Node.js availability: {e}")
        # Error message already printed by ensure_nodejs_available()
        sys.exit(1)

    # Get platform info
    platform_name, arch = get_platform_info()
    install_dir = Path.home() / ".clang-tool-chain" / "emscripten" / platform_name / arch

    # CRITICAL: Verify .emscripten config file and clang binary are readable before execution
    # This prevents "config file not found" and "clang executable not found" errors
    # in parallel test execution on Windows where filesystem sync delays can make files
    # temporarily invisible to child processes
    config_path = install_dir / ".emscripten"

    # Verify clang binary exists and is accessible
    exe_ext = ".exe" if platform_name == "win" else ""
    clang_binary = install_dir / "bin" / f"clang{exe_ext}"

    if not config_path.exists():
        logger.error(f"Emscripten config file not found: {config_path}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Configuration Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Emscripten config file not found: {config_path}", file=sys.stderr)
        print("This may indicate installation is incomplete or filesystem sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    if not clang_binary.exists():
        logger.error(f"Clang binary not found: {clang_binary}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Installation Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Clang binary not found: {clang_binary}", file=sys.stderr)
        print("This may indicate installation is incomplete or filesystem sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Wait for config file and clang binary to be readable (handles filesystem sync delays on Windows)
    import time

    config_readable = False
    clang_readable = False
    attempt = 0
    for attempt in range(30):  # 30 * 0.1s = 3 seconds max
        try:
            # Check config file
            with open(config_path, encoding="utf-8") as f:
                content = f.read()
                if "LLVM_ROOT" in content:
                    config_readable = True

            # Check clang binary (if config is readable)
            if config_readable:
                with open(clang_binary, "rb") as f:  # type: ignore[assignment]
                    f.read(1)  # Just verify we can read from it
                clang_readable = True

            if config_readable and clang_readable:
                if attempt > 0:
                    elapsed = attempt * 0.1
                    logger.debug(
                        f"Config and clang binary became readable after {elapsed:.2f}s "
                        f"(filesystem sync delay, attempt {attempt + 1})"
                    )
                break
        except OSError as e:
            logger.debug(f"File accessibility check attempt {attempt + 1} failed: {e}")
        time.sleep(0.1)

    if not config_readable:
        logger.error(f"Emscripten config file exists but is not readable: {config_path}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Configuration Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Emscripten config file exists but is not readable: {config_path}", file=sys.stderr)
        print("This may indicate a filesystem permissions issue or sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    if not clang_readable:
        logger.error(f"Clang binary exists but is not readable: {clang_binary}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Installation Error", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Clang binary exists but is not readable: {clang_binary}", file=sys.stderr)
        print("This may indicate a filesystem permissions issue or sync delay.", file=sys.stderr)
        print(f"Try removing {install_dir} and reinstalling.", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
        sys.exit(1)

    # Set up Emscripten environment variables
    env = os.environ.copy()
    # Use native OS paths - Emscripten is Python-based and handles platform paths correctly
    # Previous approach of converting to forward slashes caused path resolution issues on Windows
    env["EMSCRIPTEN"] = str(install_dir / "emscripten")
    env["EMSCRIPTEN_ROOT"] = str(install_dir / "emscripten")
    env["EM_CONFIG"] = str(config_path)

    # Create a trampoline wrapper for clang++ to fix sccache compiler detection
    # sccache runs various compiler detection commands (-E, -dumpmachine, etc.) without the
    # required -target flag, causing detection to fail. The trampoline adds the target flag
    # during detection while passing through normal compilation unchanged.
    import tempfile

    trampoline_dir = None
    if platform_name != "win":
        # Create temporary directory for trampoline (Unix-like systems only)
        trampoline_dir = Path(tempfile.mkdtemp(prefix="emscripten-sccache-"))

        print(f"\n{'=' * 60}", file=sys.stderr)
        print("DEBUG: Creating clang++ trampoline", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"Trampoline dir: {trampoline_dir}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)

        # Find the real clang++ that Emscripten uses
        real_clangpp_original = install_dir / "bin" / "clang++"
        real_clangpp_backup = install_dir / "bin" / "clang++.real"

        # On ARM: Replace the real clang++ with trampoline to fix sccache detection
        # sccache calls clang++ directly by full path, bypassing PATH-based trampoline
        # So we rename real clang++ to clang++.real and create trampoline as clang++
        if arch in ("arm64", "aarch64", "arm"):
            # Rename original clang++ to clang++.real (only once)
            if not real_clangpp_backup.exists():
                import shutil

                shutil.move(str(real_clangpp_original), str(real_clangpp_backup))
                logger.debug(f"Renamed original clang++ to: {real_clangpp_backup}")
                print(f"Renamed original clang++ to: {real_clangpp_backup}", file=sys.stderr)

            # Trampoline will be created as the new clang++
            trampoline_script = real_clangpp_original
            real_clangpp = real_clangpp_backup
        else:
            # x86_64: Use PATH-based trampoline (works fine without replacement)
            trampoline_script = trampoline_dir / "clang++"
            real_clangpp = real_clangpp_original

        # Always enable verbose logging to diagnose timeout issues
        verbose_prefix = """
# Verbose logging enabled for timeout diagnosis
echo "[TRAMPOLINE] clang++ called with args: $*" >&2
echo "[TRAMPOLINE] Called at: $(date '+%H:%M:%S')" >&2
"""
        verbose_detection = '\n    echo "[TRAMPOLINE] Detection command - adding -target wasm32-unknown-emscripten" >&2'
        verbose_normal = '\necho "[TRAMPOLINE] Normal compilation - passing through" >&2'

        trampoline_content = f"""#!/bin/bash
# Trampoline for Emscripten clang++ to fix sccache compiler detection
# sccache runs various compiler detection commands that need the -target flag
{verbose_prefix}
# Check if any argument is a compiler detection flag
# These commands need -target wasm32-unknown-emscripten to work correctly
is_detection_cmd=false
for arg in "$@"; do
    case "$arg" in
        -E|-dumpmachine|-print-target-triple|-print-targets|--version|-v|-dumpversion)
            is_detection_cmd=true
            break
            ;;
    esac
done

if [[ "$is_detection_cmd" == "true" ]]; then
    # Compiler detection command found - replace any 'unknown' target with wasm32
    # sccache may pass "-target unknown" which we need to override
    new_args=()
    skip_next=false
    for current_arg in "$@"; do
        if [[ "$skip_next" == "true" ]]; then
            # Skip the 'unknown' after -target
            skip_next=false
            continue
        fi
        if [[ "$current_arg" == "-target" ]]; then
            # Found -target flag, check if next arg is 'unknown'
            skip_next=true
            continue
        fi
        new_args+=("$current_arg")
    done
    # Execute with correct target for Emscripten{verbose_detection}
    echo "[TRAMPOLINE] Executing: {real_clangpp} -target wasm32-unknown-emscripten ${{new_args[@]}}" >&2
    exec "{real_clangpp}" -target wasm32-unknown-emscripten "${{new_args[@]}}"
fi

# Normal compilation - pass through unchanged{verbose_normal}
echo "[TRAMPOLINE] Executing: {real_clangpp} $@" >&2
exec "{real_clangpp}" "$@"
"""
        trampoline_script.write_text(trampoline_content, encoding="utf-8")
        trampoline_script.chmod(trampoline_script.stat().st_mode | stat.S_IEXEC)
        logger.debug(f"Created clang++ trampoline at: {trampoline_script}")
        print(f"Created trampoline script at: {trampoline_script}", file=sys.stderr)

    # Platform-specific sccache configuration
    # Configure sccache integration via Emscripten's compiler wrapper mechanism
    # Enabled for ALL platforms (Linux, macOS, Windows)
    # Uses EM_COMPILER_WRAPPER to wrap compiler calls with sccache for caching
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"DEBUG: Configuring sccache on {platform_name}/{arch}", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)
    print(f"sccache path: {sccache_path}", file=sys.stderr)
    print(f"Platform: {platform_name}/{arch}", file=sys.stderr)
    print(f"Emscripten dir: {install_dir}", file=sys.stderr)
    print(f"{'=' * 60}\n", file=sys.stderr)

    logger.info(f"Enabling sccache integration on {platform_name}/{arch}")
    env["EM_COMPILER_WRAPPER"] = str(sccache_path)
    env["EMCC_SKIP_SANITY_CHECK"] = "1"  # Sanity checks don't work with compiler wrappers
    # ARM platforms: Disable SCCACHE_DIRECT to allow proper compiler detection via trampoline
    # x86_64 platforms: Enable SCCACHE_DIRECT to skip expensive compiler detection
    # The trampoline script on ARM requires full compiler detection to work correctly
    if arch in ("arm64", "aarch64", "arm"):
        # Disable SCCACHE_DIRECT on ARM - trampoline needs full compiler detection
        pass  # Do not set SCCACHE_DIRECT, let sccache do full compiler detection
    else:
        # Enable SCCACHE_DIRECT on x86_64 - skip expensive compiler detection
        env["SCCACHE_DIRECT"] = "1"
    env["SCCACHE_LOG"] = "debug"  # Enable debug logging
    env["RUST_LOG"] = "sccache=debug"  # Rust logging for sccache

    logger.debug(f"EM_COMPILER_WRAPPER={sccache_path}")
    logger.debug("EMCC_SKIP_SANITY_CHECK=1")
    sccache_direct_status = "disabled" if arch in ("arm64", "aarch64", "arm") else "enabled"
    logger.debug(f"SCCACHE_DIRECT: {sccache_direct_status} ({platform_name}/{arch} daemon mode)")
    logger.debug("SCCACHE_LOG=debug, RUST_LOG=sccache=debug")

    # Add Node.js and Emscripten bin directories to PATH
    # On Unix: Put trampoline FIRST so sccache finds it instead of real clang++
    # On Windows: No trampoline needed (seems to work without it)
    node_bin_dir = node_path.parent
    emscripten_bin_dir = install_dir / "bin"

    if trampoline_dir:
        env["PATH"] = (
            f"{trampoline_dir}{os.pathsep}{emscripten_bin_dir}{os.pathsep}{node_bin_dir}{os.pathsep}{env.get('PATH', '')}"
        )
        logger.debug(f"Added to PATH (priority order): {trampoline_dir}, {emscripten_bin_dir}, {node_bin_dir}")
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("DEBUG: PATH configuration", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        print(f"1. Trampoline dir: {trampoline_dir}", file=sys.stderr)
        print(f"2. Emscripten bin: {emscripten_bin_dir}", file=sys.stderr)
        print(f"3. Node.js bin: {node_bin_dir}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
    else:
        env["PATH"] = f"{emscripten_bin_dir}{os.pathsep}{node_bin_dir}{os.pathsep}{env.get('PATH', '')}"
        logger.debug(f"Added to PATH (priority order): {emscripten_bin_dir}, {node_bin_dir}")

    # Build command: python tool_script.py args...
    python_exe = sys.executable
    cmd = [python_exe, str(tool_script)] + args

    sccache_enabled = True  # sccache now enabled for all platforms
    sccache_status = "enabled" if sccache_enabled else "disabled"

    print(f"\n{'=' * 60}", file=sys.stderr)
    print("DEBUG: About to execute Emscripten with sccache", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)
    print(f"Python: {python_exe}", file=sys.stderr)
    print(f"Tool script: {tool_script}", file=sys.stderr)
    print(f"Args: {args}", file=sys.stderr)
    print(f"sccache status: {sccache_status}", file=sys.stderr)
    print(f"EM_COMPILER_WRAPPER: {env.get('EM_COMPILER_WRAPPER', 'NOT SET')}", file=sys.stderr)
    print(f"EMCC_SKIP_SANITY_CHECK: {env.get('EMCC_SKIP_SANITY_CHECK', 'NOT SET')}", file=sys.stderr)
    print(f"SCCACHE_DIRECT: {env.get('SCCACHE_DIRECT', 'NOT SET')}", file=sys.stderr)
    print(f"SCCACHE_LOG: {env.get('SCCACHE_LOG', 'NOT SET')}", file=sys.stderr)
    print(f"{'=' * 60}\n", file=sys.stderr)

    logger.info(f"Executing command: {python_exe} {tool_script} (with {len(args)} args, sccache {sccache_status})")
    logger.debug(f"Environment: EMSCRIPTEN={env.get('EMSCRIPTEN')}")
    logger.debug(f"Environment: EM_CONFIG={env.get('EM_CONFIG')}")
    logger.debug(f"Environment: EM_COMPILER_WRAPPER={env.get('EM_COMPILER_WRAPPER', 'NOT SET')}")
    logger.debug(f"Platform: {platform_name}/{arch}, sccache: {sccache_status}")

    # Debug: Log command start time for timeout diagnosis
    import time

    start_time = time.time()
    current_time = time.strftime("%H:%M:%S")
    logger.info(f"Starting Emscripten compilation at {current_time}")
    print(f"[{current_time}] Starting compilation (timeout=none, will track manually)...", file=sys.stderr)

    # Execute with periodic progress updates
    return_code: int = 1  # Default error code if execution fails
    try:
        logger.debug(f"Subprocess command: {' '.join(cmd[:2])} [+ {len(args)} args]")

        # Run with output streaming to see progress
        import threading

        def progress_monitor():
            """Print progress every 30 seconds to detect hangs"""
            interval = 30
            while True:
                time.sleep(interval)
                elapsed = time.time() - start_time
                print(
                    f"[{time.strftime('%H:%M:%S')}] Still running... ({elapsed:.0f}s elapsed)",
                    file=sys.stderr,
                    flush=True,
                )

        monitor_thread = threading.Thread(target=progress_monitor, daemon=True)
        monitor_thread.start()

        print(f"[{time.strftime('%H:%M:%S')}] Launching subprocess...", file=sys.stderr, flush=True)
        result = subprocess.run(cmd, env=env)
        return_code = result.returncode
        elapsed = time.time() - start_time

        print(
            f"[{time.strftime('%H:%M:%S')}] Compilation completed in {elapsed:.2f}s with return code {return_code}",
            file=sys.stderr,
            flush=True,
        )
        logger.info(f"Compilation completed in {elapsed:.2f}s with return code {return_code}")
    except FileNotFoundError:
        logger.error(f"Failed to execute Python: {python_exe}")
        print(f"\nError: Python interpreter not found: {python_exe}", file=sys.stderr)
        return_code = 1
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.error(f"Failed to execute Emscripten tool: {e}")
        print(f"\nError executing {tool_name}: {e}", file=sys.stderr)
        return_code = 1
    finally:
        # Clean up trampoline directory if it was created
        if trampoline_dir and trampoline_dir.exists():
            import shutil

            try:
                shutil.rmtree(trampoline_dir)
                logger.debug(f"Cleaned up trampoline directory: {trampoline_dir}")
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                logger.warning(f"Failed to clean up trampoline directory: {e}")

    sys.exit(return_code)


def execute_emscripten_binary_tool(tool_name: str, args: list[str] | None = None) -> NoReturn:
    """
    Execute an Emscripten native binary tool (like wasm-ld).

    Unlike emcc/em++ (Python scripts), some Emscripten tools are native
    binaries that can be executed directly. This function:
    - Finds the binary in Emscripten's bin/ directory
    - Ensures Emscripten is installed
    - Executes directly (no Python interpreter needed)

    Args:
        tool_name: Name of the binary tool (e.g., "wasm-ld")
        args: Arguments to pass to the tool (defaults to sys.argv[1:])

    Raises:
        RuntimeError: If the tool cannot be found or executed
    """
    if args is None:
        args = sys.argv[1:]

    logger.info(f"Executing Emscripten binary tool: {tool_name} with {len(args)} arguments")
    logger.debug(f"Arguments: {args}")

    # Find tool binary based on tool name
    if tool_name == "wasm-ld":
        try:
            tool_path = find_emscripten_wasm_ld_binary()
        except RuntimeError as e:
            logger.error(f"Failed to find Emscripten wasm-ld: {e}")
            print(f"\n{'=' * 60}", file=sys.stderr)
            print("clang-tool-chain Emscripten wasm-ld Error", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)
            print(f"{e}", file=sys.stderr)
            print(f"{'=' * 60}\n", file=sys.stderr)
            sys.exit(1)
    else:
        raise RuntimeError(f"Unknown Emscripten binary tool: {tool_name}")

    # Build command: tool_path args...
    cmd = [str(tool_path)] + args

    logger.info(f"Executing command: {tool_path} (with {len(args)} args)")
    logger.debug(f"Full command: {' '.join(cmd[:5])}{'...' if len(cmd) > 5 else ''}")

    # Execute directly (native binary, no Python interpreter needed)
    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except FileNotFoundError:
        logger.error(f"Failed to execute binary: {tool_path}")
        print(f"\nError: Binary not found or not executable: {tool_path}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.error(f"Failed to execute Emscripten binary tool: {e}")
        print(f"\nError executing {tool_name}: {e}", file=sys.stderr)
        sys.exit(1)
