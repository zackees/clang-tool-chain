"""
Installation coordination module.

Handles high-level installation logic for all toolchain components:
- Clang/LLVM toolchain installation
- IWYU installation
- LLDB installation
- Emscripten installation
- Node.js installation
- Cosmocc installation
- Installation verification
- Concurrent download prevention with file locking

Most installer implementations have been moved to the installers/ subpackage.
This module re-exports their public APIs for backward compatibility.
"""

# Re-export Clang/LLVM installer
# Re-export helper function
from .installers.base import get_latest_version_info
from .installers.clang import (
    _subprocess_install_toolchain,
    download_and_install_toolchain,
    ensure_toolchain,
    is_toolchain_installed,
)

# Re-export Cosmocc installer
from .installers.cosmocc import (
    _subprocess_install_cosmocc,
    download_and_install_cosmocc,
    ensure_cosmocc,
    is_cosmocc_installed,
)

# Re-export Emscripten installer
# DEPRECATED: link_clang_binaries_to_emscripten kept for backward compatibility
from .installers.emscripten import (
    create_emscripten_config,
    download_and_install_emscripten,
    ensure_emscripten_available,
    is_emscripten_installed,
    link_clang_binaries_to_emscripten,
)

# Re-export IWYU installer
from .installers.iwyu import (
    _subprocess_install_iwyu,
    download_and_install_iwyu,
    ensure_iwyu,
    is_iwyu_installed,
)

# Re-export LLDB installer
from .installers.lldb import (
    _subprocess_install_lldb,
    download_and_install_lldb,
    ensure_lldb,
    is_lldb_installed,
)

# Re-export Node.js installer
from .installers.nodejs import (
    download_and_install_nodejs,
    ensure_nodejs_available,
    is_nodejs_installed,
)

# Re-export manifest functions for backward compatibility
from .manifest import fetch_nodejs_platform_manifest, fetch_platform_manifest

# Re-export path utility functions for backward compatibility
from .path_utils import get_install_dir, get_nodejs_install_dir

# Export all public functions
__all__ = [
    # Clang/LLVM
    "is_toolchain_installed",
    "download_and_install_toolchain",
    "ensure_toolchain",
    "_subprocess_install_toolchain",
    # IWYU
    "is_iwyu_installed",
    "download_and_install_iwyu",
    "ensure_iwyu",
    "_subprocess_install_iwyu",
    # LLDB
    "is_lldb_installed",
    "download_and_install_lldb",
    "ensure_lldb",
    "_subprocess_install_lldb",
    # Emscripten
    "is_emscripten_installed",
    "download_and_install_emscripten",
    "ensure_emscripten_available",
    "create_emscripten_config",
    "link_clang_binaries_to_emscripten",  # DEPRECATED but kept for backward compatibility
    # Node.js
    "is_nodejs_installed",
    "download_and_install_nodejs",
    "ensure_nodejs_available",
    # Cosmocc
    "is_cosmocc_installed",
    "download_and_install_cosmocc",
    "ensure_cosmocc",
    "_subprocess_install_cosmocc",
    # Helpers
    "get_latest_version_info",
    # Path utilities (backward compatibility)
    "get_install_dir",
    "get_nodejs_install_dir",
    # Manifest functions (backward compatibility)
    "fetch_platform_manifest",
    "fetch_nodejs_platform_manifest",
]
