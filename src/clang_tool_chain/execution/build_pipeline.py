"""
Unified build pipeline for clang-tool-chain.

This module provides a unified build pipeline pattern that eliminates
duplication between different build commands (build-run, run, etc.).

The pipeline supports:
- Clang/LLVM compilation (GNU and MSVC ABI)
- Cosmopolitan Libc compilation (Actually Portable Executables)
- Hash-based caching for incremental builds
- Shebang stripping from source files
- Inlined build directives parsing
- Automatic execution after compilation
"""

import hashlib
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from clang_tool_chain.directives import DirectiveParser
from clang_tool_chain.execution.core import run_tool
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly


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
    except KeyboardInterrupt:
        # Re-raise KeyboardInterrupt to allow clean exit
        raise
    except Exception as e:
        # Don't fail the build if directive parsing fails - just warn
        if os.environ.get("CLANG_TOOL_CHAIN_DIRECTIVE_VERBOSE", "").lower() in ("1", "true", "yes"):
            print(f"Warning: Failed to parse directives from {source_path}: {e}", file=sys.stderr)
        return []


@dataclass
class BuildConfig:
    """Configuration for a build pipeline execution."""

    source_file: str
    output_file: str
    compiler_flags: list[str]
    use_cache: bool = False
    program_args: list[str] | None = None


class BuildPipeline(ABC):
    """
    Abstract base class for build pipelines.

    A build pipeline handles the complete workflow of:
    1. Checking cache (if enabled)
    2. Compiling source code
    3. Running the executable (if requested)
    """

    def __init__(self, config: BuildConfig):
        """
        Initialize the build pipeline.

        Args:
            config: Build configuration
        """
        self.config = config
        self.source_path = Path(config.source_file)
        self.output_path = Path(config.output_file)
        self.hash_file = self.source_path.with_suffix(".hash")

    def _check_cache(self) -> bool:
        """
        Check if cached executable is valid.

        Returns:
            True if cache is valid and compilation can be skipped, False otherwise
        """
        if not self.config.use_cache:
            return False

        print(f"Checking cache for {self.config.source_file}...", file=sys.stderr)

        # Compute current hash
        current_hash = _compute_file_hash(self.source_path)

        # Check if hash file exists and matches
        if self.hash_file.exists() and self.output_path.exists():
            try:
                stored_hash = self.hash_file.read_text().strip()
                if stored_hash == current_hash:
                    print("Cache hit! Hash matches, skipping compilation.", file=sys.stderr)
                    print(f"Using cached executable: {self.config.output_file}", file=sys.stderr)
                    return True
                else:
                    print("Cache miss: Hash mismatch, recompiling...", file=sys.stderr)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                print(f"Warning: Could not read hash file: {e}", file=sys.stderr)
                print("Recompiling...", file=sys.stderr)
        else:
            if not self.output_path.exists():
                print("Cache miss: Executable not found, compiling...", file=sys.stderr)
            else:
                print("Cache miss: No hash file found, compiling...", file=sys.stderr)

        return False

    def _update_cache(self) -> None:
        """Update the cache hash file after successful compilation."""
        if not self.config.use_cache:
            return

        try:
            current_hash = _compute_file_hash(self.source_path)
            self.hash_file.write_text(current_hash)
            print(f"Updated cache hash: {self.hash_file}", file=sys.stderr)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            print(f"Warning: Could not write hash file: {e}", file=sys.stderr)

    @abstractmethod
    def _compile(self) -> int:
        """
        Compile the source file.

        Returns:
            Exit code from compilation (0 = success, non-zero = failure)
        """
        pass

    def _run_executable(self) -> NoReturn:
        """
        Run the compiled executable with program arguments.

        Raises:
            SystemExit: Always exits with the executable's return code
        """
        from clang_tool_chain.execution.sanitizer_env import prepare_sanitizer_environment

        program_args = self.config.program_args or []

        print(f"\nRunning: {self.config.output_file}", file=sys.stderr)
        if program_args:
            print(f"Program arguments: {' '.join(program_args)}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        # Prepare environment with sanitizer options for better stack traces
        # Only inject options if the corresponding sanitizer was used during compilation
        env = prepare_sanitizer_environment(compiler_flags=self.config.compiler_flags)

        # Run the compiled executable
        try:
            # Use absolute path for Windows compatibility
            abs_output = self.output_path.absolute()
            result = subprocess.run([str(abs_output)] + program_args, env=env)
            sys.exit(result.returncode)
        except FileNotFoundError:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print("Execution Error", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)
            print(f"Compiled executable not found: {self.config.output_file}", file=sys.stderr)
            print("\nThe compilation appeared to succeed, but the output file cannot be found.", file=sys.stderr)
            print(f"{'=' * 60}\n", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print("Execution Error", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)
            print(f"Error running {self.config.output_file}: {e}", file=sys.stderr)
            print(f"{'=' * 60}\n", file=sys.stderr)
            sys.exit(1)

    def execute(self, run_after_build: bool = False) -> NoReturn:
        """
        Execute the complete build pipeline.

        Args:
            run_after_build: If True, run the executable after successful compilation

        Raises:
            SystemExit: Always exits with appropriate code
        """
        # Validate source file exists
        if not self.source_path.exists():
            print(f"Error: Source file not found: {self.config.source_file}", file=sys.stderr)
            sys.exit(1)

        # Check cache
        if self._check_cache():
            # Cache hit - skip compilation
            if run_after_build:
                self._run_executable()
            else:
                sys.exit(0)

        # Compile
        exit_code = self._compile()

        if exit_code != 0:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print("Compilation failed", file=sys.stderr)
            print(f"{'=' * 60}\n", file=sys.stderr)
            sys.exit(exit_code)

        # Update cache
        self._update_cache()

        # Run if requested
        if run_after_build:
            self._run_executable()
        else:
            sys.exit(0)


class ClangBuildPipeline(BuildPipeline):
    """Build pipeline for Clang/LLVM compilation."""

    def _compile(self) -> int:
        """Compile using Clang/LLVM toolchain."""
        # Check for shebang and strip if present
        compile_source, temp_created = _strip_shebang(self.source_path)

        try:
            # Determine if this is C or C++ based on file extension
            cpp_extensions = {".cpp", ".cc", ".cxx", ".C", ".c++"}
            is_cpp = self.source_path.suffix.lower() in cpp_extensions

            # Choose the appropriate compiler
            compiler = "clang++" if is_cpp else "clang"

            # Parse inlined build directives from the source file
            directive_args = _get_directive_args(self.source_path)

            # Build the compiler command
            # Directive args come before user-specified flags so user can override
            compiler_args = (
                directive_args + [str(compile_source), "-o", self.config.output_file] + self.config.compiler_flags
            )

            print(f"Compiling: {self.config.source_file} -> {self.config.output_file}", file=sys.stderr)

            # Run the compiler (returns exit code instead of calling sys.exit)
            exit_code = run_tool(compiler, compiler_args)
            return exit_code
        finally:
            # Clean up temp file if created
            if temp_created:
                compile_source.unlink(missing_ok=True)


class CosmoccBuildPipeline(BuildPipeline):
    """Build pipeline for Cosmopolitan Libc compilation."""

    def _compile(self) -> int:
        """Compile using Cosmopolitan CC toolchain."""
        # Check for shebang and strip if present
        compile_source, temp_created = _strip_shebang(self.source_path)

        try:
            # Determine if this is C or C++ based on file extension
            cpp_extensions = {".cpp", ".cc", ".cxx", ".C", ".c++"}
            is_cpp = self.source_path.suffix.lower() in cpp_extensions

            # Import cosmocc execution after determining platform
            from .cosmocc import _find_windows_shell, find_cosmocc_tool, get_cosmocc_binary_dir, get_platform_info

            # Choose the appropriate Cosmopolitan compiler
            cosmo_compiler_name = "cosmoc++" if is_cpp else "cosmocc"

            # Parse inlined build directives from the source file
            directive_args = _get_directive_args(self.source_path)

            # Build the compiler command
            # Directive args come before user-specified flags so user can override
            compiler_args = (
                directive_args + [str(compile_source), "-o", self.config.output_file] + self.config.compiler_flags
            )

            print(
                f"Compiling with Cosmopolitan CC: {self.config.source_file} -> {self.config.output_file}",
                file=sys.stderr,
            )

            # Find the cosmocc tool and compile
            cosmo_tool_path = find_cosmocc_tool(cosmo_compiler_name)

            # Set up environment for Cosmocc
            platform_name, _ = get_platform_info()
            bin_dir = get_cosmocc_binary_dir()
            install_dir = bin_dir.parent

            env = os.environ.copy()

            # Add Cosmocc bin directory to PATH
            libexec_dir = install_dir / "libexec"
            libexec_gcc_dir = libexec_dir / "gcc"

            path_dirs = [str(bin_dir)]

            # Add libexec/gcc to PATH (contains target-specific subdirectories)
            if libexec_gcc_dir.exists():
                path_dirs.append(str(libexec_gcc_dir))
                for target_dir in sorted(libexec_gcc_dir.iterdir()):
                    if target_dir.is_dir():
                        for version_dir in sorted(target_dir.iterdir()):
                            if version_dir.is_dir():
                                path_dirs.append(str(version_dir))
            elif libexec_dir.exists():
                path_dirs.append(str(libexec_dir))

            # On Windows, convert paths to Unix-style for bash/POSIX shell compatibility
            if platform_name == "win":

                def to_unix_path(path: str) -> str:
                    """Convert Windows path to Unix-style path for MSYS/Git Bash."""
                    path = path.replace("\\", "/")
                    # Convert drive letter: C:/foo -> /c/foo
                    if len(path) >= 2 and path[1] == ":":
                        drive = path[0].lower()
                        path = f"/{drive}{path[2:]}"
                    return path

                unix_path_dirs = [to_unix_path(p) for p in path_dirs]
                existing_path = env.get("PATH", "")
                env["PATH"] = ":".join(unix_path_dirs) + ":" + existing_path
            else:
                env["PATH"] = f"{os.pathsep.join(path_dirs)}{os.pathsep}{env.get('PATH', '')}"

            # Set COSMOCC environment variable
            env["COSMOCC"] = str(install_dir)

            # On Windows, need to use bash to execute the script
            if platform_name == "win":
                shell = _find_windows_shell()
                if shell:
                    tool_path_unix = str(cosmo_tool_path).replace("\\", "/")
                    cmd = [shell, tool_path_unix] + compiler_args
                else:
                    print(
                        "Warning: No POSIX shell (bash/sh) found. Cosmocc requires a shell like Git Bash, MSYS2, or WSL.",
                        file=sys.stderr,
                    )
                    cmd = [str(cosmo_tool_path)] + compiler_args
            else:
                import shutil

                shell = shutil.which("bash") or shutil.which("sh")
                cmd = [shell, str(cosmo_tool_path)] + compiler_args if shell else [str(cosmo_tool_path)] + compiler_args

            # Run the compiler
            result = subprocess.run(cmd, env=env)
            return result.returncode
        finally:
            # Clean up temp file if created
            if temp_created:
                compile_source.unlink(missing_ok=True)
