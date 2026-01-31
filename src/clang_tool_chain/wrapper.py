"""
Wrapper infrastructure for executing LLVM/Clang tools.

This module has been refactored to organize code into focused sub-modules.
All functions are re-exported here to maintain backward compatibility with
existing code that imports from clang_tool_chain.wrapper.

Module Organization:
--------------------

platform/
    detection.py - Platform and architecture detection
    paths.py     - Tool binary and path utilities

sdk/
    windows.py   - Windows SDK detection and warnings
    macos.py     - macOS SDK detection and configuration

abi/
    windows_gnu.py  - Windows GNU ABI (MinGW) configuration
    windows_msvc.py - Windows MSVC ABI configuration

linker/
    lld.py       - LLD linker configuration and flag translation

execution/
    core.py        - Core tool execution (execute_tool, run_tool, sccache)
    emscripten.py  - Emscripten tool execution and Node.js management
    iwyu.py        - IWYU tool execution
    build.py       - Build utilities (build, build_run)

commands/
    entry_points.py - CLI entry points for all console scripts

Backward Compatibility:
-----------------------
All functions that were previously exported from this module are re-exported
below, so existing imports like:
    from clang_tool_chain.wrapper import execute_tool, get_platform_info
will continue to work without modification.

For new code, you can import from the specific sub-modules:
    from clang_tool_chain.platform import get_platform_info
    from clang_tool_chain.execution import execute_tool
"""

# ============================================================================
# Platform Detection & Paths
# ============================================================================

# ============================================================================
# ABI Configuration
# ============================================================================
from clang_tool_chain.abi import (
    _get_gnu_target_args,
    _get_msvc_target_args,
    _should_use_gnu_abi,
    _should_use_msvc_abi,
)

# ============================================================================
# CLI Entry Points (Main Functions)
# ============================================================================
from clang_tool_chain.commands import (
    clang_cpp_main,
    clang_cpp_msvc_main,
    clang_format_main,
    clang_main,
    clang_msvc_main,
    clang_tidy_main,
    cosmocc_main,
    cosmocpp_main,
    emar_main,
    emcc_main,
    empp_main,
    fix_includes_main,
    iwyu_main,
    iwyu_tool_main,
    lld_main,
    lldb_check_python_main,
    lldb_main,
    llvm_ar_main,
    llvm_as_main,
    llvm_dis_main,
    llvm_nm_main,
    llvm_objcopy_main,
    llvm_objdump_main,
    llvm_ranlib_main,
    llvm_readelf_main,
    llvm_strip_main,
    meson_main,
    sccache_emcc_main,
    sccache_empp_main,
    wasm_ld_main,
)

# ============================================================================
# Build Utilities
# ============================================================================
# Also re-export the internal hash function used by build utilities
from clang_tool_chain.execution.build import (
    _compute_file_hash,
    build_main,
    build_run_main,
    run_main,
)

# ============================================================================
# Core Tool Execution
# ============================================================================
from clang_tool_chain.execution.core import (
    execute_tool,
    run_tool,
    sccache_clang_cpp_main,
    sccache_clang_main,
)

# ============================================================================
# Cosmocc Tool Execution
# ============================================================================
from clang_tool_chain.execution.cosmocc import (
    execute_cosmocc_tool,
    find_cosmocc_tool,
    get_cosmocc_binary_dir,
)

# ============================================================================
# Emscripten Tool Execution
# ============================================================================
from clang_tool_chain.execution.emscripten import (
    ensure_nodejs_available,
    execute_emscripten_tool,
    find_emscripten_tool,
)

# ============================================================================
# IWYU Tool Execution
# ============================================================================
from clang_tool_chain.execution.iwyu import (
    execute_iwyu_tool,
    find_iwyu_tool,
    get_iwyu_binary_dir,
)

# ============================================================================
# LLDB Tool Execution
# ============================================================================
from clang_tool_chain.execution.lldb import (
    execute_lldb_tool,
    find_lldb_tool,
    get_lldb_binary_dir,
)

# ============================================================================
# Sanitizer Environment
# ============================================================================
from clang_tool_chain.execution.sanitizer_env import (
    detect_sanitizers_from_flags,
    get_symbolizer_path,
    prepare_sanitizer_environment,
)

# ============================================================================
# Linker Configuration
# ============================================================================
from clang_tool_chain.linker import (
    _add_lld_linker_if_needed,
    _should_force_lld,
    _translate_linker_flags_for_macos_lld,
)
from clang_tool_chain.platform import (
    find_sccache_binary,
    find_tool_binary,
    get_platform_binary_dir,
    get_platform_info,
)

# Also import internal functions that other modules need
from clang_tool_chain.platform.detection import _get_toolchain_directory_listing
from clang_tool_chain.platform.paths import (
    get_assets_dir,
    get_node_binary_name,
    get_nodejs_install_dir_path,
)

# ============================================================================
# SDK Detection & Configuration
# ============================================================================
from clang_tool_chain.sdk import (
    _add_macos_sysroot_if_needed,
    _detect_windows_sdk,
    _print_macos_sdk_error,
    _print_msvc_sdk_warning,
)

# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Platform Detection & Paths
    "get_platform_info",
    "get_platform_binary_dir",
    "find_tool_binary",
    "find_sccache_binary",
    "get_assets_dir",
    "get_node_binary_name",
    "get_nodejs_install_dir_path",
    # Internal platform functions
    "_get_toolchain_directory_listing",
    # SDK Detection & Configuration
    "_add_macos_sysroot_if_needed",
    "_detect_windows_sdk",
    "_print_macos_sdk_error",
    "_print_msvc_sdk_warning",
    # ABI Configuration
    "_get_gnu_target_args",
    "_get_msvc_target_args",
    "_should_use_gnu_abi",
    "_should_use_msvc_abi",
    # Linker Configuration
    "_add_lld_linker_if_needed",
    "_should_force_lld",
    "_translate_linker_flags_for_macos_lld",
    # Core Tool Execution
    "execute_tool",
    "run_tool",
    "sccache_clang_main",
    "sccache_clang_cpp_main",
    # Sanitizer Environment
    "prepare_sanitizer_environment",
    "detect_sanitizers_from_flags",
    "get_symbolizer_path",
    # Emscripten
    "ensure_nodejs_available",
    "execute_emscripten_tool",
    "find_emscripten_tool",
    # IWYU
    "execute_iwyu_tool",
    "find_iwyu_tool",
    "get_iwyu_binary_dir",
    # LLDB
    "execute_lldb_tool",
    "find_lldb_tool",
    "get_lldb_binary_dir",
    # Build Utilities
    "build_main",
    "build_run_main",
    "run_main",
    "_compute_file_hash",
    # CLI Entry Points
    "clang_main",
    "clang_cpp_main",
    "clang_msvc_main",
    "clang_cpp_msvc_main",
    "lld_main",
    "wasm_ld_main",
    "llvm_ar_main",
    "llvm_nm_main",
    "llvm_objdump_main",
    "llvm_objcopy_main",
    "llvm_ranlib_main",
    "llvm_strip_main",
    "llvm_readelf_main",
    "llvm_as_main",
    "llvm_dis_main",
    "clang_format_main",
    "clang_tidy_main",
    "emcc_main",
    "emar_main",
    "empp_main",
    "iwyu_main",
    "iwyu_tool_main",
    "fix_includes_main",
    "lldb_main",
    "lldb_check_python_main",
    "meson_main",
    "sccache_emcc_main",
    "sccache_empp_main",
    # Cosmocc (Cosmopolitan)
    "cosmocc_main",
    "cosmocpp_main",
    "execute_cosmocc_tool",
    "find_cosmocc_tool",
    "get_cosmocc_binary_dir",
]
