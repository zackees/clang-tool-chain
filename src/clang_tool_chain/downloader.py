"""
Toolchain downloader module.

Handles downloading and installing the LLVM/Clang toolchain binaries
from the manifest-based distribution system.

This module has been refactored into smaller, focused modules:
- manifest.py: Manifest data structures and fetching
- archive.py: Archive download and extraction
- path_utils.py: Path management and resolution
- permissions.py: File permissions and filesystem utilities
- installer.py: High-level installation coordination

This file serves as a compatibility layer that re-exports all public APIs
to maintain backward compatibility with existing code.
"""

# ============================================================================
# Re-exports from manifest.py
# ============================================================================
# ============================================================================
# Re-exports from archive.py
# ============================================================================
from clang_tool_chain.archive import (
    download_archive,
    download_archive_parts,
    download_file,
    extract_tarball,
    is_multipart_archive,
    verify_checksum,
)

# ============================================================================
# Re-exports from installer.py
# ============================================================================
from clang_tool_chain.installer import (
    download_and_install_cosmocc,
    download_and_install_emscripten,
    download_and_install_iwyu,
    download_and_install_lldb,
    download_and_install_nodejs,
    download_and_install_toolchain,
    ensure_cosmocc,
    ensure_emscripten_available,
    ensure_iwyu,
    ensure_lldb,
    ensure_nodejs_available,
    ensure_toolchain,
    get_latest_version_info,
    is_cosmocc_installed,
    is_emscripten_installed,
    is_iwyu_installed,
    is_lldb_installed,
    is_nodejs_installed,
    is_toolchain_installed,
)

# ============================================================================
# Re-exports from logging_config.py
# ============================================================================
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.manifest import (
    EMSCRIPTEN_MANIFEST_BASE_URL,
    IWYU_MANIFEST_BASE_URL,
    LLDB_MANIFEST_BASE_URL,
    MANIFEST_BASE_URL,
    NODEJS_MANIFEST_BASE_URL,
    ArchitectureEntry,
    Manifest,
    PlatformEntry,
    RootManifest,
    ToolchainInfrastructureError,
    VersionInfo,
    _fetch_json_raw,
    _parse_manifest,
    _parse_root_manifest,
    fetch_emscripten_platform_manifest,
    fetch_emscripten_root_manifest,
    fetch_iwyu_platform_manifest,
    fetch_iwyu_root_manifest,
    fetch_lldb_platform_manifest,
    fetch_lldb_root_manifest,
    fetch_nodejs_platform_manifest,
    fetch_nodejs_root_manifest,
    fetch_platform_manifest,
    fetch_root_manifest,
)

# ============================================================================
# Re-exports from path_utils.py
# ============================================================================
from clang_tool_chain.path_utils import (
    get_cosmocc_install_dir,
    get_cosmocc_lock_path,
    get_emscripten_install_dir,
    get_emscripten_lock_path,
    get_home_toolchain_dir,
    get_install_dir,
    get_iwyu_install_dir,
    get_iwyu_lock_path,
    get_lldb_install_dir,
    get_lldb_lock_path,
    get_lock_path,
    get_nodejs_install_dir,
    get_nodejs_lock_path,
)

# ============================================================================
# Re-exports from permissions.py
# ============================================================================
from clang_tool_chain.permissions import _robust_rmtree, fix_file_permissions

# Configure logging using centralized configuration
logger = configure_logging(__name__)

# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Exceptions
    "ToolchainInfrastructureError",
    # Data structures
    "ArchitectureEntry",
    "PlatformEntry",
    "RootManifest",
    "VersionInfo",
    "Manifest",
    # Manifest URLs
    "MANIFEST_BASE_URL",
    "IWYU_MANIFEST_BASE_URL",
    "LLDB_MANIFEST_BASE_URL",
    "EMSCRIPTEN_MANIFEST_BASE_URL",
    "NODEJS_MANIFEST_BASE_URL",
    # Internal functions (for testing)
    "_fetch_json_raw",
    "_parse_root_manifest",
    "_parse_manifest",
    # Manifest fetching
    "fetch_root_manifest",
    "fetch_platform_manifest",
    "fetch_iwyu_root_manifest",
    "fetch_iwyu_platform_manifest",
    "fetch_lldb_root_manifest",
    "fetch_lldb_platform_manifest",
    "fetch_emscripten_root_manifest",
    "fetch_emscripten_platform_manifest",
    "fetch_nodejs_root_manifest",
    "fetch_nodejs_platform_manifest",
    # Archive operations
    "verify_checksum",
    "download_file",
    "is_multipart_archive",
    "download_archive_parts",
    "download_archive",
    "extract_tarball",
    # Path management
    "get_home_toolchain_dir",
    "get_install_dir",
    "get_lock_path",
    "get_iwyu_install_dir",
    "get_iwyu_lock_path",
    "get_lldb_install_dir",
    "get_lldb_lock_path",
    "get_emscripten_install_dir",
    "get_emscripten_lock_path",
    "get_nodejs_install_dir",
    "get_nodejs_lock_path",
    "get_cosmocc_install_dir",
    "get_cosmocc_lock_path",
    # Permissions
    "_robust_rmtree",
    "fix_file_permissions",
    # Installation
    "is_toolchain_installed",
    "download_and_install_toolchain",
    "ensure_toolchain",
    "get_latest_version_info",
    "is_iwyu_installed",
    "download_and_install_iwyu",
    "ensure_iwyu",
    "is_lldb_installed",
    "download_and_install_lldb",
    "ensure_lldb",
    "is_emscripten_installed",
    "download_and_install_emscripten",
    "ensure_emscripten_available",
    "is_nodejs_installed",
    "download_and_install_nodejs",
    "ensure_nodejs_available",
    "is_cosmocc_installed",
    "download_and_install_cosmocc",
    "ensure_cosmocc",
]
