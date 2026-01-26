"""
ArgumentParser factory functions for clang-tool-chain CLI commands.

This module provides factory functions that create configured ArgumentParser
instances for various entry points in the clang-tool-chain package.
"""

import argparse

from clang_tool_chain.cli_args import BuildArgs, BuildRunArgs, LldbArgs


def create_build_parser() -> argparse.ArgumentParser:
    """
    Create ArgumentParser for build command.

    Returns:
        Configured ArgumentParser for clang-tool-chain-build
    """
    parser = argparse.ArgumentParser(
        prog="clang-tool-chain-build",
        description="Build utility that compiles and links a C/C++ source file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clang-tool-chain-build main.cpp main.exe
  clang-tool-chain-build main.c main -O2
  clang-tool-chain-build main.cpp app.exe -std=c++17 -Wall

Arguments:
  source_file     - C/C++ source file to compile (.c, .cpp, .cc, .cxx)
  output_file     - Output executable file
  compiler_flags  - Optional additional compiler flags
        """,
    )
    parser.add_argument("source_file", help="C/C++ source file to compile")
    parser.add_argument("output_file", help="Output executable file")
    parser.add_argument("compiler_flags", nargs="*", help="Additional compiler flags")
    return parser


def parse_build_args(args: list[str] | None = None) -> BuildArgs:
    """
    Parse build command arguments.

    Args:
        args: Command-line arguments to parse (defaults to sys.argv[1:])

    Returns:
        BuildArgs dataclass with parsed arguments

    Raises:
        SystemExit: On parse error or --help
    """
    parser = create_build_parser()
    parsed = parser.parse_args(args)
    return BuildArgs(
        source_file=parsed.source_file,
        output_file=parsed.output_file,
        compiler_flags=parsed.compiler_flags,
    )


def create_build_run_parser() -> argparse.ArgumentParser:
    """
    Create ArgumentParser for build-run command.

    Returns:
        Configured ArgumentParser for clang-tool-chain-build-run
    """
    parser = argparse.ArgumentParser(
        prog="clang-tool-chain-build-run",
        description="Build and run utility that compiles and executes a C/C++ source file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clang-tool-chain-build-run main.cpp
  clang-tool-chain-build-run --cached main.c
  clang-tool-chain-build-run --cached main.cpp -O2
  clang-tool-chain-build-run main.cpp -std=c++17 -Wall
  clang-tool-chain-build-run --cached main.cpp -- arg1 arg2  # Pass args to program

Behavior:
  - Compiles source_file to an executable with the same base name
  - On Windows: src.cpp -> src.exe
  - On Unix: src.cpp -> src
  - Runs the executable immediately after successful compilation
  - Use '--' to separate compiler flags from program arguments

Caching (--cached flag):
  - Computes SHA256 hash of source file
  - Stores hash in src.hash file
  - Skips compilation if hash matches and executable exists
  - Useful for quick development iterations

Arguments:
  --cached        - Enable hash-based compilation caching
  source_file     - C/C++ source file to compile (.c, .cpp, .cc, .cxx)
  compiler_flags  - Optional compiler flags (before '--')
  program_args    - Optional arguments to pass to the program (after '--')
        """,
    )
    parser.add_argument("--cached", action="store_true", help="Enable hash-based compilation caching")
    parser.add_argument("source_file", help="C/C++ source file to compile")
    parser.add_argument(
        "compiler_flags",
        nargs=argparse.REMAINDER,
        help="Optional compiler flags (before '--') and program arguments (after '--')",
    )
    return parser


def parse_build_run_args(args: list[str] | None = None) -> BuildRunArgs:
    """
    Parse build-run command arguments.

    Args:
        args: Command-line arguments to parse (defaults to sys.argv[1:])

    Returns:
        BuildRunArgs dataclass with parsed arguments

    Raises:
        SystemExit: On parse error or --help

    Note:
        This parser handles the special '--' separator to split compiler flags
        from program arguments. Everything before '--' goes to compiler_flags,
        everything after goes to program_args.
    """
    import sys

    parser = create_build_run_parser()

    # If args is None, use sys.argv[1:]
    if args is None:
        args = sys.argv[1:]

    # Special handling for '--' separator
    # We need to split args before calling parse_args
    if args and "--" in args:
        separator_idx = args.index("--")
        args_before_sep = args[:separator_idx]
        program_args = args[separator_idx + 1 :]
    else:
        args_before_sep = args
        program_args = []

    parsed = parser.parse_args(args_before_sep)

    return BuildRunArgs(
        cached=parsed.cached,
        source_file=parsed.source_file,
        compiler_flags=parsed.compiler_flags,
        program_args=program_args,
    )


def create_lldb_parser() -> argparse.ArgumentParser:
    """
    Create ArgumentParser for LLDB command.

    Returns:
        Configured ArgumentParser for clang-tool-chain-lldb
    """
    parser = argparse.ArgumentParser(
        prog="clang-tool-chain-lldb",
        description="LLDB debugger for interactive debugging and crash analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clang-tool-chain-lldb --print a.exe      # Automated crash analysis
  clang-tool-chain-lldb a.exe              # Interactive mode
  clang-tool-chain-lldb                    # Interactive mode (no executable)

Modes:
  --print <executable>: Run executable and print crash stack trace
  <executable>: Launch interactive LLDB session with executable
  (no args): Launch interactive LLDB session

Example:
  clang-tool-chain-lldb --print a.exe
  clang-tool-chain-lldb a.exe  # Interactive mode
        """,
    )
    parser.add_argument("--print", action="store_true", help="Run executable and print crash stack trace")
    parser.add_argument("executable", nargs="?", help="Executable to debug (optional)")
    parser.add_argument("lldb_args", nargs="*", help="Additional LLDB arguments")
    return parser


def parse_lldb_args(args: list[str] | None = None) -> LldbArgs:
    """
    Parse LLDB command arguments.

    Args:
        args: Command-line arguments to parse (defaults to sys.argv[1:])

    Returns:
        LldbArgs dataclass with parsed arguments

    Raises:
        SystemExit: On parse error or --help
    """
    parser = create_lldb_parser()
    parsed = parser.parse_args(args)

    return LldbArgs(
        print_mode=parsed.print,
        executable=parsed.executable,
        lldb_args=parsed.lldb_args,
    )
