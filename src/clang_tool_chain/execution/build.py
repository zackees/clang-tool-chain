"""
Build utility functions for compiling and running C/C++ programs.

This module provides simple build utilities that wrap the Clang compiler
for quick compilation and execution of C/C++ source files.
"""

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

from ..cli_parsers import parse_build_args, parse_build_run_args
from ..platform import get_platform_info
from .core import execute_tool, run_tool


def build_main() -> NoReturn:
    """
    Entry point for build wrapper.

    Simple build utility that compiles and links a C/C++ source file to an executable.

    Usage:
        clang-tool-chain-build <source_file> <output_file> [additional_args...]

    Examples:
        clang-tool-chain-build main.cpp main.exe
        clang-tool-chain-build main.c main -O2
        clang-tool-chain-build main.cpp app.exe -std=c++17 -Wall
    """
    try:
        args = parse_build_args()
    except SystemExit as e:
        # ArgumentParser calls sys.exit on error or --help
        sys.exit(e.code if e.code is not None else 1)

    # Determine if this is C or C++ based on file extension
    source_path = Path(args.source_file)
    cpp_extensions = {".cpp", ".cc", ".cxx", ".C", ".c++"}
    is_cpp = source_path.suffix.lower() in cpp_extensions

    # Choose the appropriate compiler
    compiler = "clang++" if is_cpp else "clang"

    # Build the compiler command
    compiler_args = [args.source_file, "-o", args.output_file] + args.compiler_flags

    # Execute the compiler
    execute_tool(compiler, compiler_args)


def _compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hexadecimal string representation of the SHA256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def build_run_main() -> NoReturn:
    """
    Entry point for build-run wrapper.

    Simple build-and-run utility that:
    1. Takes a C/C++ source file (e.g., src.cpp)
    2. Compiles it to an executable (src or src.exe)
    3. Runs the executable

    With --cached flag:
    1. Computes hash of source file
    2. Checks if cached hash matches (stored in src.hash)
    3. Skips compilation if hash matches and executable exists
    4. Runs the executable

    Usage:
        clang-tool-chain-build-run [--cached] <source_file> [compiler_flags...] [-- program_args...]

    Examples:
        clang-tool-chain-build-run main.cpp
        clang-tool-chain-build-run --cached main.c
        clang-tool-chain-build-run --cached main.cpp -O2
        clang-tool-chain-build-run main.cpp -std=c++17 -Wall
        clang-tool-chain-build-run --cached main.cpp -- arg1 arg2  # Pass args to program
    """
    try:
        args = parse_build_run_args()
    except SystemExit as e:
        # ArgumentParser calls sys.exit on error or --help
        sys.exit(e.code if e.code is not None else 1)

    use_cache = args.cached
    source_file = args.source_file
    compiler_flags = args.compiler_flags
    program_args = args.program_args

    # Determine output executable name from source file
    source_path = Path(source_file)

    if not source_path.exists():
        print(f"Error: Source file not found: {source_file}", file=sys.stderr)
        sys.exit(1)

    platform_name, _ = get_platform_info()

    # Generate output filename: src.cpp -> src (or src.exe on Windows)
    output_file = str(source_path.with_suffix(".exe")) if platform_name == "win" else str(source_path.with_suffix(""))

    output_path = Path(output_file)
    hash_file = source_path.with_suffix(".hash")

    # Determine if this is C or C++ based on file extension
    cpp_extensions = {".cpp", ".cc", ".cxx", ".C", ".c++"}
    is_cpp = source_path.suffix.lower() in cpp_extensions

    # Choose the appropriate compiler
    compiler = "clang++" if is_cpp else "clang"

    # Check cache if enabled
    should_compile = True
    if use_cache:
        print(f"Checking cache for {source_file}...", file=sys.stderr)

        # Compute current hash
        current_hash = _compute_file_hash(source_path)

        # Check if hash file exists and matches
        if hash_file.exists() and output_path.exists():
            try:
                stored_hash = hash_file.read_text().strip()
                if stored_hash == current_hash:
                    print("Cache hit! Hash matches, skipping compilation.", file=sys.stderr)
                    print(f"Using cached executable: {output_file}", file=sys.stderr)
                    should_compile = False
                else:
                    print("Cache miss: Hash mismatch, recompiling...", file=sys.stderr)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                print(f"Warning: Could not read hash file: {e}", file=sys.stderr)
                print("Recompiling...", file=sys.stderr)
        else:
            if not output_path.exists():
                print("Cache miss: Executable not found, compiling...", file=sys.stderr)
            else:
                print("Cache miss: No hash file found, compiling...", file=sys.stderr)

    # Compile if needed
    if should_compile:
        # Build the compiler command
        compiler_args = [source_file, "-o", output_file] + compiler_flags

        print(f"Compiling: {source_file} -> {output_file}", file=sys.stderr)

        # Run the compiler (returns exit code instead of calling sys.exit)
        exit_code = run_tool(compiler, compiler_args)

        if exit_code != 0:
            print(f"\n{'='*60}", file=sys.stderr)
            print("Compilation failed", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            sys.exit(exit_code)

        # Update hash file if caching is enabled
        if use_cache:
            try:
                current_hash = _compute_file_hash(source_path)
                hash_file.write_text(current_hash)
                print(f"Updated cache hash: {hash_file}", file=sys.stderr)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                print(f"Warning: Could not write hash file: {e}", file=sys.stderr)

    print(f"\nRunning: {output_file}", file=sys.stderr)
    if program_args:
        print(f"Program arguments: {' '.join(program_args)}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Run the compiled executable
    try:
        # Use absolute path for Windows compatibility
        abs_output = output_path.absolute()
        result = subprocess.run([str(abs_output)] + program_args)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print(f"\n{'='*60}", file=sys.stderr)
        print("Execution Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"Compiled executable not found: {output_file}", file=sys.stderr)
        print("\nThe compilation appeared to succeed, but the output file cannot be found.", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print("Execution Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"Error running {output_file}: {e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)
