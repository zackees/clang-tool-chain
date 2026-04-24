"""
CLI entry point functions for clang-tool-chain commands.

Legacy clang entry points (`clang-tool-chain-c`, `-cpp`, `-c-msvc`,
`-cpp-msvc`) forward to the zccache shim and print a one-line stderr
deprecation notice. They will be removed in Phase 7 of the zccache
migration. New users should invoke `clang-tool-chain-clang`,
`clang-tool-chain-clang++`, and the `CTC_ABI=msvc` env var instead.
"""

import sys
from typing import NoReturn

# ============================================================================
# Deprecated legacy clang entry points (Phase 6 forwarders)
# ============================================================================

_DEPRECATION_WARNED: set[str] = set()


def _warn_once(old: str, new: str) -> None:
    if old in _DEPRECATION_WARNED:
        return
    _DEPRECATION_WARNED.add(old)
    sys.stderr.write(f"clang-tool-chain: '{old}' is deprecated; use '{new}' instead. Forwarding.\n")


def clang_main() -> NoReturn:
    """Deprecated alias for `clang-tool-chain-clang`."""
    _warn_once("clang-tool-chain-c", "clang-tool-chain-clang")
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def clang_cpp_main() -> NoReturn:
    """Deprecated alias for `clang-tool-chain-clang++`."""
    _warn_once("clang-tool-chain-cpp", "clang-tool-chain-clang++")
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang++", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def clang_msvc_main() -> NoReturn:
    """Deprecated alias for `CTC_ABI=msvc clang-tool-chain-clang`."""
    _warn_once("clang-tool-chain-c-msvc", "CTC_ABI=msvc clang-tool-chain-clang")
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang", use_cache=False, abi="msvc")
    raise AssertionError("unreachable")  # pragma: no cover


def clang_cpp_msvc_main() -> NoReturn:
    """Deprecated alias for `CTC_ABI=msvc clang-tool-chain-clang++`."""
    _warn_once("clang-tool-chain-cpp-msvc", "CTC_ABI=msvc clang-tool-chain-clang++")
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang++", use_cache=False, abi="msvc")
    raise AssertionError("unreachable")  # pragma: no cover


# ============================================================================
# Linker Entry Points
# ============================================================================


def lld_main() -> NoReturn:
    """Entry point for lld linker wrapper."""
    from ..execution.core import execute_tool
    from ..platform.detection import get_platform_info

    platform_name, _ = get_platform_info()
    if platform_name == "win":
        execute_tool("lld-link")
    else:
        execute_tool("lld")


def wasm_ld_main() -> NoReturn:
    """
    Entry point for wasm-ld linker wrapper (WebAssembly linker).

    Uses Emscripten's bundled wasm-ld to ensure LLVM version compatibility
    with emcc. Emscripten bundles its own LLVM toolchain, and all tools
    (emcc, wasm-ld, etc.) must use the same LLVM version to avoid IR
    incompatibility errors.
    """
    from ..execution.emscripten import execute_emscripten_binary_tool

    execute_emscripten_binary_tool("wasm-ld")


# ============================================================================
# LLVM Binary Utilities Entry Points
# ============================================================================


def llvm_ar_main() -> NoReturn:
    """Entry point for llvm-ar wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-ar")


def llvm_nm_main() -> NoReturn:
    """Entry point for llvm-nm wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-nm")


def llvm_objdump_main() -> NoReturn:
    """Entry point for llvm-objdump wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-objdump")


def llvm_objcopy_main() -> NoReturn:
    """Entry point for llvm-objcopy wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-objcopy")


def llvm_ranlib_main() -> NoReturn:
    """Entry point for llvm-ranlib wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-ranlib")


def llvm_strip_main() -> NoReturn:
    """Entry point for llvm-strip wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-strip")


def llvm_readelf_main() -> NoReturn:
    """Entry point for llvm-readelf wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-readelf")


def llvm_dlltool_main() -> NoReturn:
    """Entry point for llvm-dlltool wrapper (generates Windows import libraries from .def files)."""
    from ..execution.core import execute_tool

    execute_tool("llvm-dlltool")


def llvm_lib_main() -> NoReturn:
    """Entry point for llvm-lib wrapper (MSVC-compatible library manager)."""
    from ..execution.core import execute_tool

    execute_tool("llvm-lib")


def llvm_as_main() -> NoReturn:
    """Entry point for llvm-as wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-as")


def llvm_dis_main() -> NoReturn:
    """Entry point for llvm-dis wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-dis")


# ============================================================================
# Def File Generation Entry Points
# ============================================================================


def gendef_main() -> int:
    """Entry point for clang-tool-chain-gendef (generates .def files from DLLs)."""
    from ..execution.gendef import gendef_main as _gendef_main

    return _gendef_main()


# ============================================================================
# Clang Tools Entry Points
# ============================================================================


def clang_format_main() -> NoReturn:
    """Entry point for clang-format wrapper (from clang-extra distribution)."""
    from ..execution.clang_extra import execute_clang_extra_tool

    execute_clang_extra_tool("clang-format")


def clang_tidy_main() -> NoReturn:
    """Entry point for clang-tidy wrapper (from clang-extra distribution)."""
    from ..execution.clang_extra import execute_clang_extra_tool

    execute_clang_extra_tool("clang-tidy")


def clang_query_main() -> NoReturn:
    """Entry point for clang-query wrapper (from clang-extra distribution)."""
    from ..execution.clang_extra import execute_clang_extra_tool

    execute_clang_extra_tool("clang-query")


# ============================================================================
# Emscripten Entry Points
# ============================================================================


def emcc_main() -> NoReturn:
    """Entry point for emcc wrapper (Emscripten C compiler)."""
    from ..execution.emscripten import execute_emscripten_tool

    execute_emscripten_tool("emcc")


def empp_main() -> NoReturn:
    """Entry point for em++ wrapper (Emscripten C++ compiler)."""
    from ..execution.emscripten import execute_emscripten_tool

    execute_emscripten_tool("em++")


def emar_main() -> NoReturn:
    """Entry point for emar wrapper (Emscripten archiver)."""
    from ..execution.emscripten import execute_emscripten_tool

    execute_emscripten_tool("emar")


# ============================================================================
# IWYU (Include What You Use) Entry Points
# ============================================================================


def iwyu_main() -> NoReturn:
    """Entry point for include-what-you-use wrapper."""
    from ..execution.iwyu import execute_iwyu_tool

    execute_iwyu_tool("include-what-you-use")


def iwyu_tool_main() -> NoReturn:
    """Entry point for iwyu_tool.py wrapper."""
    from ..execution.iwyu import execute_iwyu_tool

    execute_iwyu_tool("iwyu_tool.py")


def fix_includes_main() -> NoReturn:
    """Entry point for fix_includes.py wrapper."""
    from ..execution.iwyu import execute_iwyu_tool

    execute_iwyu_tool("fix_includes.py")


# ============================================================================
# LLDB (LLVM Debugger) Entry Points
# ============================================================================


def lldb_main() -> NoReturn | int:
    """
    Entry point for clang-tool-chain-lldb command.

    Special flag:
        --print <executable>: Run executable and print crash stack trace

    Example:
        clang-tool-chain-lldb --print a.exe
        clang-tool-chain-lldb a.exe  # Interactive mode
    """
    import sys

    from ..cli_parsers import parse_lldb_args
    from ..execution.lldb import execute_lldb_tool

    try:
        args = parse_lldb_args()
    except SystemExit as e:
        # ArgumentParser calls sys.exit on error or --help
        sys.exit(e.code if e.code is not None else 1)

    if args.print_mode:
        # Automated crash analysis mode
        # Run executable under LLDB, capture crash, print stack trace
        if not args.executable:
            print("Error: --print requires executable path", file=sys.stderr)
            return 1

        exe_path = args.executable

        # LLDB batch command to run and print backtrace on crash
        # Use -k flag for commands that should run after the process stops (crashes)
        # -o commands run immediately, -k commands run after stop events
        # IMPORTANT: Quote the executable path to handle spaces correctly
        lldb_args = [
            "--batch",
            "-o",
            f'target create "{exe_path}"',  # Create target explicitly (quoted for paths with spaces)
            "-o",
            "run",  # Run the program
            "-k",
            "bt",  # Backtrace after crash (-k = run after stop event)
            "-k",
            "thread list",  # List all threads after crash
        ]

        return execute_lldb_tool("lldb", lldb_args, print_mode=True)

    # Interactive LLDB mode (never returns - calls sys.exit)
    # If executable is provided, pass it; otherwise, pass additional args
    lldb_args = [args.executable] + args.lldb_args if args.executable else args.lldb_args

    execute_lldb_tool("lldb", lldb_args)
    raise AssertionError("execute_lldb_tool should never return in interactive mode")


def lldb_check_python_main() -> int:
    """
    Entry point for clang-tool-chain-lldb-check-python command.

    Prints diagnostic information about LLDB Python environment configuration.

    Returns:
        Exit code (0 if Python is ready, 1 if missing/incomplete)
    """
    from ..execution.lldb import print_lldb_python_diagnostics

    return print_lldb_python_diagnostics()


# ============================================================================
# Build Utilities Entry Points
# ============================================================================

# Note: build_main and build_run_main are imported from the execution.build module
# They are more complex and have been moved to their own module for better organization

# ============================================================================
# Emscripten + sccache Entry Points
# ============================================================================


def sccache_emcc_main() -> NoReturn:
    """Entry point for emcc with sccache wrapper (Emscripten C compiler + caching)."""
    from ..execution.emscripten import execute_emscripten_tool_with_sccache

    execute_emscripten_tool_with_sccache("emcc")


def sccache_empp_main() -> NoReturn:
    """Entry point for em++ with sccache wrapper (Emscripten C++ compiler + caching)."""
    from ..execution.emscripten import execute_emscripten_tool_with_sccache

    execute_emscripten_tool_with_sccache("em++")


# ============================================================================
# Build System Entry Points
# ============================================================================


def meson_main() -> int:
    """Entry point for meson build system wrapper."""
    from mesonbuild.mesonmain import main as meson_main_impl

    # Pass all arguments to meson
    return meson_main_impl()  # type: ignore[no-any-return]


# ============================================================================
# Cosmocc (Cosmopolitan) Entry Points
# ============================================================================


def cosmocc_main() -> NoReturn:
    """
    Entry point for cosmocc wrapper (Cosmopolitan C compiler).

    Produces Actually Portable Executables (APE) that run on Windows,
    Linux, macOS, FreeBSD, NetBSD, and OpenBSD without modification.
    """
    from ..execution.cosmocc import execute_cosmocc_tool

    execute_cosmocc_tool("cosmocc")


def cosmocpp_main() -> NoReturn:
    """
    Entry point for cosmoc++ wrapper (Cosmopolitan C++ compiler).

    Produces Actually Portable Executables (APE) that run on Windows,
    Linux, macOS, FreeBSD, NetBSD, and OpenBSD without modification.
    """
    from ..execution.cosmocc import execute_cosmocc_tool

    execute_cosmocc_tool("cosmoc++")


# ============================================================================
# Valgrind Entry Points
# ============================================================================


def callgrind_main() -> NoReturn | int:
    """
    Entry point for clang-tool-chain-callgrind command.

    Runs Valgrind's callgrind profiler on a compiled executable
    and produces an annotated source-level profiling report.

    Example:
        clang-tool-chain-cpp program.cpp -g -O0 -o program
        clang-tool-chain-callgrind ./program
    """
    from ..execution.callgrind import execute_callgrind_tool

    return execute_callgrind_tool()


def valgrind_main() -> NoReturn | int:
    """
    Entry point for clang-tool-chain-valgrind command.

    Runs Valgrind memory error detector on a compiled executable
    inside a Docker container. Works from any host platform.

    Example:
        clang-tool-chain-cpp program.cpp -g -O0 -o program
        clang-tool-chain-valgrind --leak-check=full ./program
    """
    from ..execution.valgrind import execute_valgrind_tool

    return execute_valgrind_tool()


# ============================================================================
# Zccache Shim Entry Points (Phase 4 — new console scripts)
# ============================================================================
#
# These entry points exec into `zccache` via `zccache_shim.exec_via_zccache`.
# Imports of `..zccache_shim` are inside each function body so this module
# remains importable before P3 lands the shim module.


def clang_new_main() -> NoReturn:
    """Entry point for `clang-tool-chain-clang` — execs zccache-wrapped clang."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def clang_cpp_new_main() -> NoReturn:
    """Entry point for `clang-tool-chain-clang++` — execs zccache-wrapped clang++."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang++", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def zccache_clang_main() -> NoReturn:
    """Entry point for `clang-tool-chain-zccache-clang` — execs clang with caching."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang", use_cache=True)
    raise AssertionError("unreachable")  # pragma: no cover


def zccache_clang_cpp_main() -> NoReturn:
    """Entry point for `clang-tool-chain-zccache-clang++` — execs clang++ with caching."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang++", use_cache=True)
    raise AssertionError("unreachable")  # pragma: no cover


def emcc_new_main() -> NoReturn:
    """Entry point for `clang-tool-chain-emcc` — execs zccache-wrapped emcc."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("emcc", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def empp_new_main() -> NoReturn:
    """Entry point for `clang-tool-chain-em++` — execs zccache-wrapped em++."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("em++", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def zccache_emcc_main() -> NoReturn:
    """Entry point for `clang-tool-chain-zccache-emcc` — execs emcc with caching."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("emcc", use_cache=True)
    raise AssertionError("unreachable")  # pragma: no cover


def zccache_empp_main() -> NoReturn:
    """Entry point for `clang-tool-chain-zccache-em++` — execs em++ with caching."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("em++", use_cache=True)
    raise AssertionError("unreachable")  # pragma: no cover


def wasm_ld_new_main() -> NoReturn:
    """Entry point for `clang-tool-chain-wasm-ld` — execs zccache-wrapped wasm-ld."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("wasm-ld", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def zccache_wasm_ld_main() -> NoReturn:
    """Entry point for `clang-tool-chain-zccache-wasm-ld` — execs wasm-ld with caching."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("wasm-ld", use_cache=True)
    raise AssertionError("unreachable")  # pragma: no cover


def clang_tidy_new_main() -> NoReturn:
    """Entry point for `clang-tool-chain-clang-tidy` — execs zccache-wrapped clang-tidy."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang-tidy", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def zccache_clang_tidy_main() -> NoReturn:
    """Entry point for `clang-tool-chain-zccache-clang-tidy` — execs clang-tidy with caching."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("clang-tidy", use_cache=True)
    raise AssertionError("unreachable")  # pragma: no cover


def iwyu_new_main() -> NoReturn:
    """Entry point for `clang-tool-chain-iwyu` — execs zccache-wrapped include-what-you-use."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("iwyu", use_cache=False)
    raise AssertionError("unreachable")  # pragma: no cover


def zccache_iwyu_main() -> NoReturn:
    """Entry point for `clang-tool-chain-zccache-iwyu` — execs iwyu with caching."""
    from ..zccache_shim import exec_via_zccache

    exec_via_zccache("iwyu", use_cache=True)
    raise AssertionError("unreachable")  # pragma: no cover
