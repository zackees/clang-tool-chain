"""
Path management module.

Handles all path-related operations for the toolchain:
- Home directory resolution
- Installation directories
- Lock file paths
- Environment variable overrides
"""

from pathlib import Path


def get_home_toolchain_dir() -> Path:
    """
    Get the home directory for clang-tool-chain downloads.

    Can be overridden with CLANG_TOOL_CHAIN_DOWNLOAD_PATH environment variable.

    Returns:
        Path to ~/.clang-tool-chain or the path specified by the environment variable
    """
    # Check for environment variable override
    from .settings_warnings import warn_download_path_override

    env_path = warn_download_path_override()
    if env_path:
        return Path(env_path)

    # Default to ~/.clang-tool-chain
    home = Path.home()
    toolchain_dir = home / ".clang-tool-chain"
    return toolchain_dir


# ============================================================================
# Clang/LLVM Paths
# ============================================================================


def get_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for Clang/LLVM toolchain.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "clang" / platform / arch
    return install_dir


def get_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for Clang/LLVM installation.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"{platform}-{arch}.lock"
    return lock_path


# ============================================================================
# IWYU Paths
# ============================================================================


def get_iwyu_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for IWYU.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the IWYU installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "iwyu" / platform / arch
    return install_dir


def get_iwyu_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for IWYU installation.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"iwyu-{platform}-{arch}.lock"
    return lock_path


# ============================================================================
# Emscripten Paths
# ============================================================================


def get_emscripten_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for Emscripten.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the Emscripten installation directory
    """
    from .settings_warnings import warn_download_path_override

    base_dir = warn_download_path_override()
    if base_dir:
        return Path(base_dir) / "emscripten" / platform / arch
    return Path.home() / ".clang-tool-chain" / "emscripten" / platform / arch


def get_emscripten_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for Emscripten installation.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    from .settings_warnings import warn_download_path_override

    base_dir = warn_download_path_override()
    base = Path(base_dir) if base_dir else Path.home() / ".clang-tool-chain"
    base.mkdir(parents=True, exist_ok=True)  # Ensure directory exists for lock file
    return base / f"emscripten-{platform}-{arch}.lock"


# ============================================================================
# LLDB Paths
# ============================================================================


def get_lldb_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for LLDB.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the LLDB installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "lldb" / platform / arch
    return install_dir


def get_lldb_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for LLDB installation.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"lldb-{platform}-{arch}.lock"
    return lock_path


# ============================================================================
# Node.js Paths
# ============================================================================


def get_nodejs_install_dir(platform: str, arch: str) -> Path:
    """
    Get the installation directory for Node.js.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the Node.js installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "nodejs" / platform / arch
    return install_dir


def get_nodejs_lock_path(platform: str, arch: str) -> Path:
    """
    Get the lock file path for Node.js installation.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"nodejs-{platform}-{arch}.lock"
    return lock_path
