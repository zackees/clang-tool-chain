"""
Command entry points for clang-tool-chain.

This package provides all the CLI entry point functions that are registered
as console scripts in pyproject.toml. The entry points are organized into
logical groups:

Compilers:
    - clang_main: C compiler (GNU ABI on Windows by default)
    - clang_cpp_main: C++ compiler (GNU ABI on Windows by default)
    - clang_msvc_main: C compiler with MSVC ABI (Windows only)
    - clang_cpp_msvc_main: C++ compiler with MSVC ABI (Windows only)

Linker:
    - lld_main: LLVM linker (lld-link on Windows, lld on Unix)
    - wasm_ld_main: WebAssembly linker (wasm-ld)

Binary Utilities:
    - llvm_ar_main: Archive utility
    - llvm_nm_main: Name list utility
    - llvm_objdump_main: Object dump utility
    - llvm_objcopy_main: Object copy utility
    - llvm_ranlib_main: Archive index generator
    - llvm_strip_main: Symbol stripper
    - llvm_readelf_main: ELF reader
    - llvm_as_main: LLVM assembler
    - llvm_dis_main: LLVM disassembler

Clang Tools:
    - clang_format_main: Code formatter
    - clang_tidy_main: Code analyzer and linter

Emscripten (WebAssembly):
    - emcc_main: Emscripten C compiler
    - emar_main: Emscripten archiver
    - empp_main: Emscripten C++ compiler

IWYU (Include What You Use):
    - iwyu_main: include-what-you-use analyzer
    - iwyu_tool_main: iwyu_tool.py wrapper
    - fix_includes_main: fix_includes.py wrapper

LLDB (LLVM Debugger):
    - lldb_main: LLDB debugger

Build Utilities:
    - build_main: Simple build utility (from wrapper.py)
    - build_run_main: Build and run utility (from wrapper.py)

Note: build_main and build_run_main need to be imported from wrapper.py
until they are moved to execution.build module.
"""

from clang_tool_chain.commands.entry_points import (
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

__all__ = [
    # Compilers
    "clang_main",
    "clang_cpp_main",
    "clang_msvc_main",
    "clang_cpp_msvc_main",
    # Linker
    "lld_main",
    "wasm_ld_main",
    # Binary Utilities
    "llvm_ar_main",
    "llvm_nm_main",
    "llvm_objdump_main",
    "llvm_objcopy_main",
    "llvm_ranlib_main",
    "llvm_strip_main",
    "llvm_readelf_main",
    "llvm_as_main",
    "llvm_dis_main",
    # Clang Tools
    "clang_format_main",
    "clang_tidy_main",
    # Emscripten
    "emcc_main",
    "emar_main",
    "empp_main",
    # sccache wrappers
    "sccache_emcc_main",
    "sccache_empp_main",
    # IWYU
    "iwyu_main",
    "iwyu_tool_main",
    "fix_includes_main",
    # LLDB
    "lldb_main",
    "lldb_check_python_main",
    # Build Systems
    "meson_main",
    # Cosmocc (Cosmopolitan)
    "cosmocc_main",
    "cosmocpp_main",
]
