"""
CLI entry point functions for clang-tool-chain commands.

This module provides all the main() entry point functions that are registered
as console scripts in pyproject.toml. These functions are thin wrappers that
delegate to the execution modules.
"""

from typing import NoReturn

# ============================================================================
# Clang/Clang++ Entry Points
# ============================================================================


def clang_main() -> NoReturn:
    """
    Entry point for clang wrapper (GNU ABI on Windows by default).

    Supports inlined build directives in source files:
        // @link: pthread
        // @std: c11
        // @cflags: -O2 -Wall

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to show parsed directives
    """
    import sys

    from ..execution.build import get_directive_args_from_compiler_args
    from ..execution.core import execute_tool

    # Get original arguments
    args = sys.argv[1:]

    # Parse directives from source files in arguments
    directive_args = get_directive_args_from_compiler_args(args)

    # Prepend directive args so they can be overridden by explicit flags
    if directive_args:
        args = directive_args + args

    execute_tool("clang", args)


def clang_cpp_main() -> NoReturn:
    """
    Entry point for clang++ wrapper (GNU ABI on Windows by default).

    Supports inlined build directives in source files:
        // @link: pthread
        // @std: c++17
        // @cflags: -O2 -Wall

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to show parsed directives
    """
    import sys

    from ..execution.build import get_directive_args_from_compiler_args
    from ..execution.core import execute_tool

    # Get original arguments
    args = sys.argv[1:]

    # Parse directives from source files in arguments
    directive_args = get_directive_args_from_compiler_args(args)

    # Prepend directive args so they can be overridden by explicit flags
    if directive_args:
        args = directive_args + args

    execute_tool("clang++", args)


def clang_msvc_main() -> NoReturn:
    """
    Entry point for clang-tool-chain-c-msvc (MSVC ABI on Windows).

    Supports inlined build directives in source files:
        // @link: pthread
        // @std: c11
        // @cflags: -O2 -Wall

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to show parsed directives
    """
    import sys

    from ..execution.build import get_directive_args_from_compiler_args
    from ..execution.core import execute_tool

    # Get original arguments
    args = sys.argv[1:]

    # Parse directives from source files in arguments
    directive_args = get_directive_args_from_compiler_args(args)

    # Prepend directive args so they can be overridden by explicit flags
    if directive_args:
        args = directive_args + args

    execute_tool("clang", args, use_msvc=True)


def clang_cpp_msvc_main() -> NoReturn:
    """
    Entry point for clang-tool-chain-cpp-msvc (MSVC ABI on Windows).

    Supports inlined build directives in source files:
        // @link: pthread
        // @std: c++17
        // @cflags: -O2 -Wall

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to show parsed directives
    """
    import sys

    from ..execution.build import get_directive_args_from_compiler_args
    from ..execution.core import execute_tool

    # Get original arguments
    args = sys.argv[1:]

    # Parse directives from source files in arguments
    directive_args = get_directive_args_from_compiler_args(args)

    # Prepend directive args so they can be overridden by explicit flags
    if directive_args:
        args = directive_args + args

    execute_tool("clang++", args, use_msvc=True)


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


def llvm_as_main() -> NoReturn:
    """Entry point for llvm-as wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-as")


def llvm_dis_main() -> NoReturn:
    """Entry point for llvm-dis wrapper."""
    from ..execution.core import execute_tool

    execute_tool("llvm-dis")


# ============================================================================
# Clang Tools Entry Points
# ============================================================================


def clang_format_main() -> NoReturn:
    """Entry point for clang-format wrapper."""
    from ..execution.core import execute_tool

    execute_tool("clang-format")


def clang_tidy_main() -> NoReturn:
    """Entry point for clang-tidy wrapper."""
    from ..execution.core import execute_tool

    execute_tool("clang-tidy")


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
