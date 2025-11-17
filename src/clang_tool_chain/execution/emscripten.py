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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

logger = logging.getLogger(__name__)


def get_platform_info() -> tuple[str, str]:
    """
    Detect the current platform and architecture.

    Returns:
        Tuple of (platform, architecture) strings
        Platform: "win", "linux", or "darwin"
        Architecture: "x86_64" or "aarch64"
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
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
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

    # Set up Emscripten environment variables
    env = os.environ.copy()
    env["EMSCRIPTEN"] = str(install_dir / "emscripten")
    env["EMSCRIPTEN_ROOT"] = str(install_dir / "emscripten")
    env["EM_CONFIG"] = str(install_dir / ".emscripten")

    # Add Node.js bin directory to PATH (ensures Emscripten finds the right node)
    node_bin_dir = node_path.parent
    env["PATH"] = f"{node_bin_dir}{os.pathsep}{env.get('PATH', '')}"
    logger.debug(f"Added to PATH: {node_bin_dir}")

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
    except RuntimeError as e:
        logger.error(f"Failed to find sccache: {e}")
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain sccache Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print("\nTo install sccache:", file=sys.stderr)
        print("  - cargo install sccache", file=sys.stderr)
        print("  - Or download from: https://github.com/mozilla/sccache/releases", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)

    # Find tool script
    try:
        tool_script = find_emscripten_tool(tool_name)
    except RuntimeError as e:
        logger.error(f"Failed to find Emscripten tool: {e}")
        print(f"\n{'='*60}", file=sys.stderr)
        print("clang-tool-chain Emscripten Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
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

    # Set up Emscripten environment variables
    env = os.environ.copy()
    env["EMSCRIPTEN"] = str(install_dir / "emscripten")
    env["EMSCRIPTEN_ROOT"] = str(install_dir / "emscripten")
    env["EM_CONFIG"] = str(install_dir / ".emscripten")

    # Configure sccache integration via Emscripten's compiler wrapper mechanism
    env["EM_COMPILER_WRAPPER"] = str(sccache_path)
    env["EMCC_SKIP_SANITY_CHECK"] = "1"  # Sanity checks don't work with compiler wrappers
    logger.debug(f"EM_COMPILER_WRAPPER={sccache_path}")
    logger.debug("EMCC_SKIP_SANITY_CHECK=1")

    # Add Node.js bin directory to PATH
    node_bin_dir = node_path.parent
    env["PATH"] = f"{node_bin_dir}{os.pathsep}{env.get('PATH', '')}"
    logger.debug(f"Added to PATH: {node_bin_dir}")

    # Build command: python tool_script.py args...
    python_exe = sys.executable
    cmd = [python_exe, str(tool_script)] + args

    logger.info(f"Executing command: {python_exe} {tool_script} (with {len(args)} args, sccache enabled)")
    logger.debug(f"Environment: EMSCRIPTEN={env.get('EMSCRIPTEN')}")
    logger.debug(f"Environment: EM_CONFIG={env.get('EM_CONFIG')}")
    logger.debug(f"Environment: EM_COMPILER_WRAPPER={env.get('EM_COMPILER_WRAPPER')}")

    # Execute
    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        logger.error(f"Failed to execute Python: {python_exe}")
        print(f"\nError: Python interpreter not found: {python_exe}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to execute Emscripten tool: {e}")
        print(f"\nError executing {tool_name}: {e}", file=sys.stderr)
        sys.exit(1)
