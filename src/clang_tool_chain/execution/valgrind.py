"""
Valgrind execution support.

Valgrind is a Linux-only dynamic analysis tool for detecting memory errors,
leaks, and other issues. This module runs Valgrind inside a Docker container
so it works from any host platform (Windows, macOS, Linux).

The workflow:
1. Compile the program with clang-tool-chain (on the host)
2. Run the compiled binary inside a Docker container with Valgrind
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from clang_tool_chain import downloader
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

# Configure logging
logger = logging.getLogger(__name__)

# Docker image used for running Valgrind
VALGRIND_DOCKER_IMAGE_BASE = "ubuntu:22.04"
VALGRIND_DOCKER_IMAGE = "clang-tool-chain-valgrind:latest"


def get_platform_info() -> tuple[str, str]:
    """
    Detect the current platform and architecture.

    Returns:
        Tuple of (platform, architecture) strings
        Platform: "win", "linux", or "darwin"
        Architecture: "x86_64" or "arm64"
    """
    import platform

    system = platform.system().lower()
    machine = platform.machine().lower()

    logger.debug(f"Detecting platform: system={system}, machine={machine}")

    # Normalize platform name
    if system == "windows":
        platform_name = "win"
    elif system == "linux":
        platform_name = "linux"
    elif system == "darwin":
        platform_name = "darwin"
    else:
        raise RuntimeError(
            f"Unsupported platform: {system}\nclang-tool-chain currently supports: Windows, Linux, and macOS (Darwin)"
        )

    # Normalize architecture
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        raise RuntimeError(
            f"Unsupported architecture: {machine}\nclang-tool-chain currently supports: x86_64 (AMD64) and ARM64"
        )

    logger.info(f"Platform detected: {platform_name}/{arch}")
    return platform_name, arch


def _check_docker_available() -> bool:
    """Check if Docker is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _ensure_docker_image() -> None:
    """
    Ensure the clang-tool-chain-valgrind Docker image exists.

    Builds a minimal Docker image from ubuntu:22.04 with libc6-dbg installed
    (required by Valgrind for glibc symbol redirection).
    """
    # Check if image already exists
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", VALGRIND_DOCKER_IMAGE],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return  # Image exists
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    logger.info("Building clang-tool-chain-valgrind Docker image...")
    print("Building Valgrind Docker image (one-time setup)...", file=sys.stderr)

    # Build inline Dockerfile
    dockerfile_content = (
        f"FROM {VALGRIND_DOCKER_IMAGE_BASE}\n"
        "RUN apt-get update -qq && "
        "apt-get install -qq -y --no-install-recommends libc6-dbg > /dev/null 2>&1 && "
        "rm -rf /var/lib/apt/lists/*\n"
    )

    result = subprocess.run(
        ["docker", "build", "-t", VALGRIND_DOCKER_IMAGE, "-"],
        input=dockerfile_content,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error(f"Failed to build Docker image: {result.stderr}")
        raise RuntimeError(f"Failed to build Valgrind Docker image.\nDocker output: {result.stderr}")

    print("Valgrind Docker image built successfully.", file=sys.stderr)


def get_valgrind_binary_dir() -> Path:
    """
    Get the binary directory for the Valgrind installation.

    Ensures Valgrind is downloaded and returns the path to the bin directory.

    Returns:
        Path to the Valgrind binary directory

    Raises:
        RuntimeError: If binary directory is not found
    """
    _, arch = get_platform_info()
    # Valgrind archives are Linux-only
    platform_name = "linux"

    logger.info(f"Getting Valgrind binary directory for {platform_name}/{arch}")

    # Get the installation directory
    install_dir = downloader.get_valgrind_install_dir(platform_name, arch)
    bin_dir = install_dir / "bin"

    # If binaries already exist on disk, skip the download check
    if not bin_dir.exists():
        # Ensure Valgrind is downloaded and installed
        downloader.ensure_valgrind(platform_name, arch)

    if not bin_dir.exists():
        raise RuntimeError(
            f"Valgrind binaries not found for {platform_name}-{arch}\n"
            f"Expected location: {bin_dir}\n"
            f"\n"
            f"The Valgrind download may have failed. Please try again or report this issue at:\n"
            f"https://github.com/zackees/clang-tool-chain/issues"
        )

    logger.info(f"Valgrind binary directory found: {bin_dir}")
    return bin_dir


def find_valgrind_tool(tool_name: str) -> Path:
    """
    Find the path to a Valgrind tool.

    Args:
        tool_name: Name of the tool (e.g., "valgrind", "vgdb")

    Returns:
        Path to the tool

    Raises:
        RuntimeError: If the tool is not found
    """
    logger.info(f"Finding Valgrind tool: {tool_name}")
    bin_dir = get_valgrind_binary_dir()

    tool_path = bin_dir / tool_name

    if not tool_path.exists():
        available_tools = [f.name for f in bin_dir.iterdir() if f.is_file()]
        raise RuntimeError(
            f"Valgrind tool '{tool_name}' not found at: {tool_path}\n"
            f"Available tools in {bin_dir}:\n"
            f"  {', '.join(available_tools)}"
        )

    logger.info(f"Found Valgrind tool: {tool_path}")
    return tool_path


def _detect_ape_and_resolve_dbg(exe_path: Path) -> Path:
    """
    Detect if an executable is an APE (Actually Portable Executable) from cosmocc
    and resolve it to the .dbg sidecar file that Valgrind can analyze.

    APE .com files have an MZ header and are not standard ELF binaries, so Valgrind
    cannot run them directly. However, cosmocc produces .dbg sidecar files that are
    standard x86-64 Linux ELF binaries with DWARF debug symbols.

    Args:
        exe_path: Resolved path to the executable

    Returns:
        Path to the .dbg sidecar if APE detected, otherwise the original path
    """
    # Fast path: check .com extension
    is_com = exe_path.suffix.lower() == ".com"

    # If not .com, check for MZ magic bytes (APE without .com extension)
    is_ape = is_com
    if not is_ape:
        try:
            with open(exe_path, "rb") as f:
                magic = f.read(2)
            is_ape = magic == b"MZ"
        except OSError:
            return exe_path

    if not is_ape:
        return exe_path

    # APE detected — look for .dbg sidecar
    # cosmocc produces: program.com + program.com.dbg
    # Try program.com.dbg first, then program.dbg
    candidates = [exe_path.with_suffix(exe_path.suffix + ".dbg")]
    if is_com:
        candidates.append(exe_path.with_suffix(".dbg"))

    for dbg_path in candidates:
        if dbg_path.exists():
            print(
                f"APE detected: {exe_path.name} → using debug sidecar: {dbg_path.name}",
                file=sys.stderr,
            )
            return dbg_path

    # No .dbg sidecar found
    print(
        f"ERROR: {exe_path.name} is an APE (Actually Portable Executable) which Valgrind cannot run directly.\n"
        f"\n"
        f"Cosmocc produces a .dbg sidecar file (standard ELF with debug symbols) that\n"
        f"Valgrind can analyze, but no sidecar was found.\n"
        f"\n"
        f"Looked for:\n" + "\n".join(f"  - {c.name}" for c in candidates) + "\n"
        f"\n"
        f"Recompile with debug symbols to produce the .dbg sidecar:\n"
        f"  clang-tool-chain-cosmocc -g -O0 source.c -o {exe_path.name}\n",
        file=sys.stderr,
    )
    sys.exit(1)


def execute_valgrind_tool(args: list[str] | None = None) -> NoReturn | int:
    """
    Execute Valgrind on a target executable using Docker.

    This runs the target binary inside a Docker container with the
    pre-downloaded Valgrind installation mounted. This ensures Valgrind
    works from any host platform.

    Args:
        args: Command-line arguments (default: sys.argv[1:]).
              Expected format: [valgrind-flags...] <executable> [exe-args...]

    Returns:
        Exit code from Valgrind

    Raises:
        SystemExit: Exits with valgrind's return code
    """
    if args is None:
        args = sys.argv[1:]

    if not args:
        print(
            "Usage: clang-tool-chain-valgrind [valgrind-options] <executable> [args...]\n"
            "\n"
            "Runs Valgrind memory error detector on the specified executable.\n"
            "The executable runs inside a Docker container (Docker required).\n"
            "\n"
            "Common options:\n"
            "  --leak-check=full       Show detailed leak information\n"
            "  --track-origins=yes     Track origins of uninitialized values\n"
            "  --show-reachable=yes    Show reachable blocks in leak check\n"
            "  --error-exitcode=1      Exit with code 1 if errors found\n"
            "\n"
            "Example:\n"
            "  clang-tool-chain-cpp program.cpp -g -O0 -o program\n"
            "  clang-tool-chain-valgrind --leak-check=full ./program\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check Docker availability
    if not _check_docker_available():
        print(
            "ERROR: Docker is required to run Valgrind.\n"
            "\n"
            "Valgrind is a Linux-only tool. clang-tool-chain uses Docker to run it\n"
            "on any platform (Windows, macOS, Linux).\n"
            "\n"
            "Install Docker:\n"
            "  Windows/macOS: https://www.docker.com/products/docker-desktop\n"
            "  Linux: sudo apt install docker.io  (or equivalent)\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse valgrind flags vs executable and its args
    valgrind_flags = []
    executable = None
    exe_args = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-") and executable is None:
            # Valgrind flag
            if "=" in arg:
                valgrind_flags.append(arg)
            else:
                # Check if next arg is a value for this flag
                valgrind_flags.append(arg)
                # Some valgrind flags take a separate value
                if arg in ("--tool", "--log-file", "--xml-file", "--suppressions") and i + 1 < len(args):
                    i += 1
                    valgrind_flags.append(args[i])
        elif executable is None:
            executable = arg
        else:
            exe_args.append(arg)
        i += 1

    if executable is None:
        print("ERROR: No executable specified.", file=sys.stderr)
        print("Usage: clang-tool-chain-valgrind [options] <executable> [args...]", file=sys.stderr)
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
        ]
        + valgrind_flags
        + [f"/workdir/{exe_name}"]
        + exe_args
    )

    logger.info(f"Executing Valgrind in Docker: {' '.join(docker_cmd)}")

    try:
        result = subprocess.run(docker_cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        print(f"ERROR: Failed to run Valgrind in Docker: {e}", file=sys.stderr)
        sys.exit(1)
