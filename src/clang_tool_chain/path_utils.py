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
# Archive Cache Paths
# ============================================================================


def get_archive_cache_dir() -> Path:
    """
    Get the directory for cached downloaded archives.

    Archives are stored here to avoid re-downloading when toolchains are purged.
    Structure: ~/.clang-tool-chain/archives/

    Returns:
        Path to the archive cache directory
    """
    toolchain_dir = get_home_toolchain_dir()
    cache_dir = toolchain_dir / "archives"
    return cache_dir


def get_cached_archive_path(component: str, platform: str, arch: str, sha256: str) -> Path:
    """
    Get the path for a cached archive file.

    Archives are named with their SHA256 hash to ensure uniqueness and integrity.
    Format: {component}-{platform}-{arch}-{sha256[:16]}.tar.zst

    Args:
        component: Component name (e.g., "clang", "iwyu", "lldb", "emscripten", "nodejs")
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
        sha256: Full SHA256 hash of the archive

    Returns:
        Path to the cached archive file
    """
    cache_dir = get_archive_cache_dir()
    # Use first 16 chars of SHA256 for filename (enough to avoid collisions)
    short_hash = sha256[:16]
    filename = f"{component}-{platform}-{arch}-{short_hash}.tar.zst"
    return cache_dir / filename


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


# ============================================================================
# Cosmocc (Cosmopolitan) Paths
# ============================================================================


def get_cosmocc_install_dir(platform: str | None = None, arch: str | None = None) -> Path:
    """
    Get the installation directory for Cosmocc (Cosmopolitan Libc).

    Cosmocc produces Actually Portable Executables (APE) that run on all platforms,
    so a single universal installation is shared across all platforms.

    Args:
        platform: Deprecated, ignored. Kept for backward compatibility.
        arch: Deprecated, ignored. Kept for backward compatibility.

    Returns:
        Path to the universal Cosmocc installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / "cosmocc" / "universal"
    return install_dir


def get_cosmocc_lock_path(platform: str | None = None, arch: str | None = None) -> Path:
    """
    Get the lock file path for Cosmocc installation (universal).

    Args:
        platform: Deprecated, ignored. Kept for backward compatibility.
        arch: Deprecated, ignored. Kept for backward compatibility.

    Returns:
        Path to the universal lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / "cosmocc-universal.lock"
    return lock_path


# ============================================================================
# Generic Tool Paths (Template Pattern Support)
# ============================================================================


def get_tool_install_dir(tool_name: str, platform: str, arch: str) -> Path:
    """
    Get the installation directory for a toolchain component (generic pattern).

    This provides a standard path pattern for all tools:
    ~/.clang-tool-chain/{tool_name}/{platform}/{arch}

    Args:
        tool_name: Tool name (e.g., "clang", "iwyu", "lldb")
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the tool installation directory
    """
    toolchain_dir = get_home_toolchain_dir()
    install_dir = toolchain_dir / tool_name / platform / arch
    return install_dir


def get_tool_lock_path(tool_name: str, platform: str, arch: str) -> Path:
    """
    Get the lock file path for a toolchain component installation (generic pattern).

    This provides a standard lock file pattern for all tools:
    ~/.clang-tool-chain/{tool_name}-{platform}-{arch}.lock

    Args:
        tool_name: Tool name (e.g., "clang", "iwyu", "lldb")
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the lock file
    """
    toolchain_dir = get_home_toolchain_dir()
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    lock_path = toolchain_dir / f"{tool_name}-{platform}-{arch}.lock"
    return lock_path
