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
    args = sys.argv[1:]

    if len(args) < 2:
        print("\n" + "=" * 60, file=sys.stderr)
        print("clang-tool-chain-build - Build Utility", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("Usage: clang-tool-chain-build <source_file> <output_file> [compiler_flags...]", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  clang-tool-chain-build main.cpp main.exe", file=sys.stderr)
        print("  clang-tool-chain-build main.c main -O2", file=sys.stderr)
        print("  clang-tool-chain-build main.cpp app.exe -std=c++17 -Wall", file=sys.stderr)
        print("\nArguments:", file=sys.stderr)
        print("  source_file     - C/C++ source file to compile (.c, .cpp, .cc, .cxx)", file=sys.stderr)
        print("  output_file     - Output executable file", file=sys.stderr)
        print("  compiler_flags  - Optional additional compiler flags", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
        sys.exit(1)

    source_file = args[0]
    output_file = args[1]
    additional_flags = args[2:] if len(args) > 2 else []

    # Determine if this is C or C++ based on file extension
    source_path = Path(source_file)
    cpp_extensions = {".cpp", ".cc", ".cxx", ".C", ".c++"}
    is_cpp = source_path.suffix.lower() in cpp_extensions

    # Choose the appropriate compiler
    compiler = "clang++" if is_cpp else "clang"

    # Build the compiler command
    compiler_args = [source_file, "-o", output_file] + additional_flags

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
    args = sys.argv[1:]

    if len(args) < 1:
        print("\n" + "=" * 60, file=sys.stderr)
        print("clang-tool-chain-build-run - Build and Run Utility", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            "Usage: clang-tool-chain-build-run [--cached] <source_file> [compiler_flags...] [-- program_args...]",
            file=sys.stderr,
        )
        print("\nExamples:", file=sys.stderr)
        print("  clang-tool-chain-build-run main.cpp", file=sys.stderr)
        print("  clang-tool-chain-build-run --cached main.c", file=sys.stderr)
        print("  clang-tool-chain-build-run --cached main.cpp -O2", file=sys.stderr)
        print("  clang-tool-chain-build-run main.cpp -std=c++17 -Wall", file=sys.stderr)
        print("  clang-tool-chain-build-run --cached main.cpp -- arg1 arg2  # Pass args to program", file=sys.stderr)
        print("\nBehavior:", file=sys.stderr)
        print("  - Compiles source_file to an executable with the same base name", file=sys.stderr)
        print("  - On Windows: src.cpp -> src.exe", file=sys.stderr)
        print("  - On Unix: src.cpp -> src", file=sys.stderr)
        print("  - Runs the executable immediately after successful compilation", file=sys.stderr)
        print("  - Use '--' to separate compiler flags from program arguments", file=sys.stderr)
        print("\nCaching (--cached flag):", file=sys.stderr)
        print("  - Computes SHA256 hash of source file", file=sys.stderr)
        print("  - Stores hash in src.hash file", file=sys.stderr)
        print("  - Skips compilation if hash matches and executable exists", file=sys.stderr)
        print("  - Useful for quick development iterations", file=sys.stderr)
        print("\nArguments:", file=sys.stderr)
        print("  --cached        - Enable hash-based compilation caching", file=sys.stderr)
        print("  source_file     - C/C++ source file to compile (.c, .cpp, .cc, .cxx)", file=sys.stderr)
        print("  compiler_flags  - Optional compiler flags (before '--')", file=sys.stderr)
        print("  program_args    - Optional arguments to pass to the program (after '--')", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)
        sys.exit(1)

    # Check for --cached flag
    use_cache = False
    if args[0] == "--cached":
        use_cache = True
        args = args[1:]

    if len(args) < 1:
        print("Error: source_file is required", file=sys.stderr)
        sys.exit(1)

    # Split args into compiler flags and program args
    if "--" in args:
        separator_idx = args.index("--")
        compile_args = args[:separator_idx]
        program_args = args[separator_idx + 1 :]
    else:
        compile_args = args
        program_args = []

    source_file = compile_args[0]
    compiler_flags = compile_args[1:] if len(compile_args) > 1 else []

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
    except Exception as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print("Execution Error", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"Error running {output_file}: {e}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)
