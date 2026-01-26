"""
Execution utilities for building and running C/C++ programs.

This package provides:
- Core tool execution: execute_tool, run_tool
- Build utilities: build_main, build_run_main
- sccache wrappers for compilation caching
"""

from clang_tool_chain.execution.build import build_main, build_run_main
from clang_tool_chain.execution.core import execute_tool, run_tool, sccache_clang_cpp_main, sccache_clang_main

__all__ = [
    # Core execution
    "execute_tool",
    "run_tool",
    # Build utilities
    "build_main",
    "build_run_main",
    # sccache wrappers
    "sccache_clang_main",
    "sccache_clang_cpp_main",
]
