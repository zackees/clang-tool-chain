"""
Build utility functions for compiling and running C/C++ programs.

This module provides simple build utilities that wrap the Clang compiler
for quick compilation and execution of C/C++ source files.

Shebang Support:
    C++ files can include a shebang line for direct execution:
        #!/usr/bin/env -S clang-tool-chain-build-run --cached
    This line is automatically stripped before compilation.

Inlined Directives Support:
    C/C++ files can include build directives in comments at the top of the file:
        // @link: pthread
        // @std: c++17
        // @cflags: -O2 -Wall
    These directives are automatically parsed and added to the compiler command.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

from ..cli_parsers import parse_build_args, parse_build_run_args
from ..directives import DirectiveParser
from ..platform import get_platform_info
from .core import execute_tool, run_tool


def _get_directive_args(source_path: Path) -> list[str]:
    """
    Parse inlined build directives from a source file and return compiler args.

    Directives are embedded in comments at the top of the file:
        // @link: pthread
        // @std: c++17
        // @cflags: -O2 -Wall
        // @platform: linux
        //   @link: pthread

    Args:
        source_path: Path to the source file

    Returns:
        List of compiler/linker arguments derived from directives
    """
    # Check if directives parsing is disabled via environment variable
    if os.environ.get("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "").lower() in ("1", "true", "yes"):
        return []

    try:
        parser = DirectiveParser()
        directives = parser.parse_file_for_current_platform(source_path)

        # Get all compiler and linker arguments
        all_args = directives.get_all_args()

        # Log if verbose mode is enabled
        if os.environ.get("CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE", "").lower() in ("1", "true", "yes") and all_args:
            print(f"Parsed directives from {source_path.name}:", file=sys.stderr)
            if directives.std:
                print(f"  @std: {directives.std}", file=sys.stderr)
            if directives.links:
                print(f"  @link: {directives.links}", file=sys.stderr)
            if directives.cflags:
                print(f"  @cflags: {directives.cflags}", file=sys.stderr)
            if directives.ldflags:
                print(f"  @ldflags: {directives.ldflags}", file=sys.stderr)
            if directives.includes:
                print(f"  @include: {directives.includes}", file=sys.stderr)
            print(f"  Effective args: {' '.join(all_args)}", file=sys.stderr)

        return all_args
    except Exception as e:
        # Don't fail the build if directive parsing fails - just warn
        if os.environ.get("CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE", "").lower() in ("1", "true", "yes"):
            print(f"Warning: Failed to parse directives from {source_path}: {e}", file=sys.stderr)
        return []


# C/C++ source file extensions
_SOURCE_EXTENSIONS = {".c", ".cpp", ".cc", ".cxx", ".c++", ".m", ".mm"}


def get_directive_args_from_compiler_args(args: list[str]) -> list[str]:
    """
    Extract source files from compiler arguments and parse their directives.

    This function finds C/C++ source files in the argument list and parses
    any inlined build directives from them. This allows clang-tool-chain-c
    and clang-tool-chain-cpp to automatically pick up directives.

    Args:
        args: List of compiler arguments (e.g., from sys.argv[1:])

    Returns:
        List of additional compiler/linker arguments derived from directives.
        If multiple source files have directives, all are combined.

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to show parsed directives
    """
    # Check if directives parsing is disabled via environment variable
    if os.environ.get("CLANG_TOOL_CHAIN_NO_DIRECTIVES", "").lower() in ("1", "true", "yes"):
        return []

    directive_args: list[str] = []
    seen_args: set[str] = set()  # Avoid duplicates

    for arg in args:
        # Skip flags and options
        if arg.startswith("-"):
            continue

        # Check if this looks like a source file
        path = Path(arg)
        suffix = path.suffix.lower()

        if suffix in _SOURCE_EXTENSIONS and path.exists():
            # Parse directives from this source file
            file_args = _get_directive_args(path)
            for file_arg in file_args:
                if file_arg not in seen_args:
                    seen_args.add(file_arg)
                    directive_args.append(file_arg)

    return directive_args


def _strip_shebang(source_path: Path) -> tuple[Path, bool]:
    """
    Check if source file has a shebang and create a temporary file without it.

    Args:
        source_path: Path to the source file

    Returns:
        Tuple of (path to use for compilation, whether a temp file was created)
        If no shebang, returns (original path, False)
        If shebang found, returns (temp file path, True)
    """
    with open(source_path, encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
        if not first_line.startswith("#!"):
            # No shebang, use original file
            return source_path, False

        # Has shebang - read rest of file and create temp file
        rest_of_file = f.read()

    # Create temp file with same extension in same directory
    # (same directory ensures relative includes work)
    temp_dir = source_path.parent
    suffix = source_path.suffix
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=suffix,
        dir=temp_dir,
        delete=False,
        encoding="utf-8",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        try:
            # Write file without the shebang line
            temp_file.write(rest_of_file)
        except KeyboardInterrupt as ke:
            # Clean up on interrupt
            temp_path.unlink(missing_ok=True)
            handle_keyboard_interrupt_properly(ke)
        except Exception:
            # Clean up on error
            temp_path.unlink(missing_ok=True)
            raise
    return temp_path, True


def build_main() -> NoReturn:
    """
    Entry point for build wrapper.

    Simple build utility that compiles and links a C/C++ source file to an executable.

    Supports inlined build directives in source files:
        // @link: pthread
        // @std: c++17
        // @cflags: -O2 -Wall

    Usage:
        clang-tool-chain-build <source_file> <output_file> [additional_args...]

    Examples:
        clang-tool-chain-build main.cpp main.exe
        clang-tool-chain-build main.c main -O2
        clang-tool-chain-build main.cpp app.exe -std=c++17 -Wall

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to show parsed directives
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

    # Parse inlined build directives from the source file
    directive_args = _get_directive_args(source_path)

    # Build the compiler command
    # Directive args come before user-specified flags so user can override
    compiler_args = directive_args + [args.source_file, "-o", args.output_file] + args.compiler_flags

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

    Supports inlined build directives in source files:
        // @link: pthread
        // @std: c++17
        // @cflags: -O2 -Wall

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

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DIRECTIVES: Set to '1' to disable directive parsing
        CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE: Set to '1' to show parsed directives
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
        # Check for shebang and strip if present
        compile_source, temp_created = _strip_shebang(source_path)

        try:
            # Parse inlined build directives from the source file
            directive_args = _get_directive_args(source_path)

            # Build the compiler command
            # Directive args come before user-specified flags so user can override
            compiler_args = directive_args + [str(compile_source), "-o", output_file] + compiler_flags

            print(f"Compiling: {source_file} -> {output_file}", file=sys.stderr)

            # Run the compiler (returns exit code instead of calling sys.exit)
            exit_code = run_tool(compiler, compiler_args)
        finally:
            # Clean up temp file if created
            if temp_created:
                compile_source.unlink(missing_ok=True)

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
