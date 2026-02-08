"""
Callgrind execution support.

Callgrind is a call-graph generating cache profiler that ships with Valgrind.
This module provides a dedicated CLI command that runs callgrind inside a Docker
container and optionally auto-annotates the output using callgrind_annotate.

The workflow:
1. Compile the program with clang-tool-chain (on the host)
2. Run callgrind via Docker to produce a callgrind.out.* file
3. Optionally annotate the output for human-readable profiling results
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from clang_tool_chain import downloader
from clang_tool_chain.execution.valgrind import (
    VALGRIND_DOCKER_IMAGE,
    _check_docker_available,
    _detect_ape_and_resolve_dbg,
    _ensure_docker_image,
    get_platform_info,
)
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

# Configure logging
logger = logging.getLogger(__name__)


def _parse_callgrind_args(args: list[str]) -> tuple[list[str], list[str], str | None, list[str], bool, str | None, int]:
    """
    Parse callgrind command-line arguments.

    Splits arguments into callgrind-specific flags, valgrind passthrough flags,
    executable path, and executable arguments.

    Args:
        args: Raw command-line arguments

    Returns:
        Tuple of (callgrind_flags, valgrind_flags, executable, exe_args, raw, output_file, threshold)
    """
    valgrind_flags: list[str] = []
    executable: str | None = None
    exe_args: list[str] = []
    raw = False
    output_file: str | None = None
    threshold = 95

    i = 0
    while i < len(args):
        arg = args[i]

        if executable is not None:
            exe_args.append(arg)
            i += 1
            continue

        # Callgrind-specific flags
        if arg == "--raw":
            raw = True
            i += 1
            continue

        if arg in ("--output", "-o") and i + 1 < len(args):
            i += 1
            output_file = args[i]
            i += 1
            continue

        if arg.startswith("--output="):
            output_file = arg.split("=", 1)[1]
            i += 1
            continue

        if arg.startswith("--threshold="):
            try:
                threshold = int(arg.split("=", 1)[1])
            except ValueError:
                print(f"ERROR: Invalid threshold value: {arg}", file=sys.stderr)
                sys.exit(1)
            i += 1
            continue

        if arg == "--threshold" and i + 1 < len(args):
            i += 1
            try:
                threshold = int(args[i])
            except ValueError:
                print(f"ERROR: Invalid threshold value: {args[i]}", file=sys.stderr)
                sys.exit(1)
            i += 1
            continue

        # Valgrind passthrough flags
        if arg.startswith("-"):
            if "=" in arg:
                valgrind_flags.append(arg)
            else:
                valgrind_flags.append(arg)
                # Some valgrind flags take a separate value
                if arg in ("--log-file", "--xml-file", "--suppressions") and i + 1 < len(args):
                    i += 1
                    valgrind_flags.append(args[i])
            i += 1
            continue

        # Must be the executable
        executable = arg
        i += 1

    return valgrind_flags, valgrind_flags, executable, exe_args, raw, output_file, threshold


def _run_callgrind_annotate(
    callgrind_out_name: str,
    valgrind_mount: str,
    exe_dir_mount: str,
    threshold: int = 95,
) -> tuple[int, str]:
    """
    Run callgrind_annotate inside Docker and return the annotated output.

    Tries multiple strategies:
    1. Use callgrind_annotate from our Valgrind distribution
    2. Fall back to system callgrind_annotate (apt valgrind package)
    3. Install valgrind via apt as last resort

    Args:
        callgrind_out_name: Name of the callgrind output file (in /workdir)
        valgrind_mount: Docker mount path for Valgrind installation
        exe_dir_mount: Docker mount path for the executable directory
        threshold: Annotation threshold percentage

    Returns:
        Tuple of (return_code, annotated_output)
    """
    # Build a shell script that tries multiple annotation strategies.
    # The Docker image includes the valgrind package (which provides callgrind_annotate).
    # Fallback strategies handle edge cases where the image was built without it.
    annotate_script = (
        "#!/bin/sh\n"
        # Strategy 1: Our bundled callgrind_annotate
        "if [ -x /opt/valgrind/bin/callgrind_annotate ]; then\n"
        f"  exec /opt/valgrind/bin/callgrind_annotate --threshold={threshold} /workdir/{callgrind_out_name}\n"
        "fi\n"
        # Strategy 2: System callgrind_annotate (from apt valgrind package in Docker image)
        "if command -v callgrind_annotate >/dev/null 2>&1; then\n"
        f"  exec callgrind_annotate --threshold={threshold} /workdir/{callgrind_out_name}\n"
        "fi\n"
        "echo 'ERROR: callgrind_annotate not found in Docker image' >&2\n"
        "exit 1\n"
    )

    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{valgrind_mount}:/opt/valgrind:ro",
        "-v",
        f"{exe_dir_mount}:/workdir",
        "-w",
        "/workdir",
        VALGRIND_DOCKER_IMAGE,
        "sh",
        "-c",
        annotate_script,
    ]

    logger.info("Running callgrind_annotate in Docker")

    try:
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        return 1, ""
    except Exception as e:
        logger.error(f"Failed to run callgrind_annotate: {e}")
        return 1, ""


def execute_callgrind_tool(args: list[str] | None = None) -> NoReturn | int:
    """
    Execute callgrind profiler on a target executable using Docker.

    Runs the target binary inside a Docker container with Valgrind's callgrind
    tool, then optionally annotates the output for human-readable results.

    Args:
        args: Command-line arguments (default: sys.argv[1:]).
              Expected format: [callgrind-flags...] [valgrind-flags...] <executable> [exe-args...]

    Returns:
        Exit code from callgrind
    """
    if args is None:
        args = sys.argv[1:]

    if not args or args == ["--help"] or args == ["-h"]:
        print(
            "Usage: clang-tool-chain-callgrind [options] <executable> [args...]\n"
            "\n"
            "Runs Valgrind's callgrind profiler on the specified executable\n"
            "and produces an annotated source-level profiling report.\n"
            "The executable runs inside a Docker container (Docker required).\n"
            "\n"
            "Callgrind options:\n"
            "  --raw                   Keep raw callgrind.out.* file, skip annotation\n"
            "  --output FILE, -o FILE  Write annotated output to file instead of stdout\n"
            "  --threshold N           Annotation threshold percentage (default: 95)\n"
            "\n"
            "Valgrind passthrough options:\n"
            "  --callgrind-out-file=FILE  Set output file name pattern\n"
            "  --cache-sim=yes            Enable cache simulation\n"
            "  --branch-sim=yes           Enable branch prediction simulation\n"
            "  --collect-jumps=yes        Collect jump counts\n"
            "\n"
            "Example:\n"
            "  clang-tool-chain-cpp program.cpp -g -O0 -o program\n"
            "  clang-tool-chain-callgrind ./program\n"
            "  clang-tool-chain-callgrind --threshold=80 ./program\n"
            "  clang-tool-chain-callgrind --raw ./program  # keep callgrind.out.*\n",
            file=sys.stderr,
        )
        sys.exit(0 if args in (["--help"], ["-h"]) else 1)

    # Check Docker availability
    if not _check_docker_available():
        print(
            "ERROR: Docker is required to run callgrind.\n"
            "\n"
            "Callgrind is a Valgrind tool (Linux-only). clang-tool-chain uses Docker\n"
            "to run it on any platform (Windows, macOS, Linux).\n"
            "\n"
            "Install Docker:\n"
            "  Windows/macOS: https://www.docker.com/products/docker-desktop\n"
            "  Linux: sudo apt install docker.io  (or equivalent)\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse arguments
    _, valgrind_flags, executable, exe_args, raw, output_file, threshold = _parse_callgrind_args(args)

    if executable is None:
        print("ERROR: No executable specified.", file=sys.stderr)
        print("Usage: clang-tool-chain-callgrind [options] <executable> [args...]", file=sys.stderr)
        sys.exit(1)

    # Resolve executable path
    exe_path = Path(executable).resolve()
    if not exe_path.exists():
        print(f"ERROR: Executable not found: {executable}", file=sys.stderr)
        sys.exit(1)

    # Check for APE (cosmocc) executables and redirect to .dbg sidecar
    exe_path = _detect_ape_and_resolve_dbg(exe_path)

    # Get the Valgrind installation directory
    _, arch = get_platform_info()
    valgrind_install_dir = downloader.get_valgrind_install_dir("linux", arch)

    # Ensure valgrind is downloaded (skip if already on disk)
    valgrind_bin_dir = valgrind_install_dir / "bin"
    if not valgrind_bin_dir.exists():
        try:
            downloader.ensure_valgrind("linux", arch)
        except Exception as e:
            print(f"ERROR: Failed to download Valgrind: {e}", file=sys.stderr)
            sys.exit(1)

    # Ensure the Docker image with libc6-dbg is available
    _ensure_docker_image()

    # Build Docker command
    exe_dir = exe_path.parent
    exe_name = exe_path.name

    # Convert paths for Docker mount (handle Windows paths)
    valgrind_mount = str(valgrind_install_dir).replace("\\", "/")
    exe_dir_mount = str(exe_dir).replace("\\", "/")

    # On Windows/MSYS, convert drive paths for Docker
    import platform as platform_mod

    if platform_mod.system().lower() == "windows" or os.environ.get("MSYSTEM"):
        # Convert C:\path to /c/path for Docker
        if len(valgrind_mount) > 1 and valgrind_mount[1] == ":":
            valgrind_mount = f"/{valgrind_mount[0].lower()}{valgrind_mount[2:]}"
        if len(exe_dir_mount) > 1 and exe_dir_mount[1] == ":":
            exe_dir_mount = f"/{exe_dir_mount[0].lower()}{exe_dir_mount[2:]}"

    # Run callgrind via Docker
    docker_cmd = (
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{valgrind_mount}:/opt/valgrind:ro",
            "-v",
            f"{exe_dir_mount}:/workdir",
            "-w",
            "/workdir",
            "--cap-add=SYS_PTRACE",
            VALGRIND_DOCKER_IMAGE,
            "/opt/valgrind/bin/valgrind",
            "--tool=callgrind",
        ]
        + valgrind_flags
        + [f"/workdir/{exe_name}"]
        + exe_args
    )

    logger.info(f"Executing callgrind in Docker: {' '.join(docker_cmd)}")
    print("Running callgrind profiler...", file=sys.stderr)

    try:
        callgrind_result = subprocess.run(docker_cmd)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
        sys.exit(130)  # unreachable, but satisfies type checker
    except Exception as e:
        print(f"ERROR: Failed to run callgrind in Docker: {e}", file=sys.stderr)
        sys.exit(1)

    if callgrind_result.returncode != 0:
        sys.exit(callgrind_result.returncode)

    # Find the callgrind output file
    callgrind_out_files = list(exe_dir.glob("callgrind.out.*"))
    if not callgrind_out_files:
        print("WARNING: No callgrind.out.* file found. The program may not have run to completion.", file=sys.stderr)
        sys.exit(callgrind_result.returncode)

    # Use the most recently modified callgrind output file
    callgrind_out_file = max(callgrind_out_files, key=lambda f: f.stat().st_mtime)
    callgrind_out_name = callgrind_out_file.name

    if raw:
        print(f"Callgrind output: {callgrind_out_file}", file=sys.stderr)
        sys.exit(0)

    # Run callgrind_annotate
    print("Annotating callgrind output...", file=sys.stderr)
    annotate_rc, annotated_output = _run_callgrind_annotate(
        callgrind_out_name,
        valgrind_mount,
        exe_dir_mount,
        threshold=threshold,
    )

    if annotate_rc != 0:
        print(
            f"WARNING: callgrind_annotate failed (exit code {annotate_rc}).\n"
            f"Raw output file preserved: {callgrind_out_file}\n"
            f"You can view it with: callgrind_annotate {callgrind_out_file}\n"
            f"Or open it in KCachegrind/QCachegrind for GUI visualization.",
            file=sys.stderr,
        )
        sys.exit(annotate_rc)

    # Output the annotated results
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(annotated_output)
        print(f"Annotated output written to: {output_file}", file=sys.stderr)
    else:
        print(annotated_output)

    # Clean up callgrind output file after successful annotation
    import contextlib

    with contextlib.suppress(OSError):
        callgrind_out_file.unlink()

    sys.exit(0)
