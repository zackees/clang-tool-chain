"""
sccache runner using iso-env for isolated execution.

This module provides fallback functionality to run sccache via iso-env
when sccache is not found in the system PATH.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_sccache_path() -> str | None:
    """
    Get the path to sccache executable.

    Returns:
        Path to sccache if found in PATH, None otherwise.
    """
    return shutil.which("sccache")


def get_iso_env_cache_dir() -> Path:
    """
    Get the cache directory for iso-env sccache installation.

    Returns:
        Path to the cache directory.
    """
    # Use the same directory as clang-tool-chain for consistency
    base_dir = os.environ.get("CLANG_TOOL_CHAIN_DOWNLOAD_PATH")
    cache_dir = Path(base_dir) / "sccache-env" if base_dir else Path.home() / ".clang-tool-chain" / "sccache-env"

    return cache_dir


def run_sccache_via_isoenv(args: list[str]) -> int:
    """
    Run sccache via iso-env in an isolated environment.

    Args:
        args: Command-line arguments to pass to sccache

    Returns:
        Exit code from sccache execution
    """
    try:
        from iso_env import IsoEnv, IsoEnvArgs, Requirements
    except ImportError:
        print("=" * 70, file=sys.stderr)
        print("ERROR: iso-env package not found", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print("iso-env is required as a fallback when sccache is not in PATH.", file=sys.stderr)
        print("Please install it with:", file=sys.stderr)
        print("  pip install clang-tool-chain", file=sys.stderr)
        print(file=sys.stderr)
        print("Or install sccache directly:", file=sys.stderr)
        print("  pip install clang-tool-chain[sccache]", file=sys.stderr)
        print(file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    cache_dir = get_iso_env_cache_dir()

    # Create iso-env configuration for sccache
    try:
        # First time setup - create the environment
        print(f"Setting up isolated sccache environment at {cache_dir}...", file=sys.stderr)

        # Create requirements for sccache
        requirements_txt = "sccache>=0.7.0\n"
        requirements = Requirements(requirements_txt)

        # Create IsoEnvArgs
        iso_args = IsoEnvArgs(venv_path=cache_dir, build_info=requirements)

        # Create IsoEnv instance
        env = IsoEnv(iso_args)

        # Run sccache with the provided arguments
        result = env.run(["sccache"] + args)

        return result.returncode if result.returncode is not None else 0

    except Exception as e:
        print("=" * 70, file=sys.stderr)
        print("ERROR: Failed to run sccache via iso-env", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print(f"Error details: {e}", file=sys.stderr)
        print(file=sys.stderr)
        print("You may want to install sccache directly:", file=sys.stderr)
        print("  pip install clang-tool-chain[sccache]", file=sys.stderr)
        print("  cargo install sccache", file=sys.stderr)
        print("  # or use your system package manager", file=sys.stderr)
        print(file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1


def run_sccache(args: list[str]) -> int:
    """
    Run sccache, using iso-env as fallback if not found in PATH.

    Args:
        args: Command-line arguments to pass to sccache

    Returns:
        Exit code from sccache execution
    """
    sccache_path = get_sccache_path()

    if sccache_path:
        # sccache found in PATH, use it directly
        cmd = [sccache_path] + args

        try:
            result = subprocess.run(cmd)
            return result.returncode
        except Exception as e:
            print(f"ERROR: Failed to execute sccache: {e}", file=sys.stderr)
            return 1
    else:
        # sccache not found in PATH, use iso-env fallback
        print("sccache not found in PATH, using isolated environment...", file=sys.stderr)
        print(file=sys.stderr)
        return run_sccache_via_isoenv(args)


def run_sccache_with_compiler(compiler_path: str, args: list[str]) -> int:
    """
    Run sccache with a compiler, using iso-env as fallback if sccache not found in PATH.

    Args:
        compiler_path: Path to the compiler executable
        args: Command-line arguments to pass to the compiler

    Returns:
        Exit code from sccache execution
    """
    sccache_path = get_sccache_path()

    if sccache_path:
        # sccache found in PATH, use it directly
        cmd = [sccache_path, compiler_path] + args

        try:
            result = subprocess.run(cmd)
            return result.returncode
        except Exception as e:
            print(f"ERROR: Failed to execute sccache: {e}", file=sys.stderr)
            return 1
    else:
        # sccache not found in PATH, use iso-env fallback
        print("sccache not found in PATH, using isolated environment...", file=sys.stderr)
        print(file=sys.stderr)
        return run_sccache_via_isoenv([compiler_path] + args)
