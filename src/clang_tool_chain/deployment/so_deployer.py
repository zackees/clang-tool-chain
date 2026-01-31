"""
Linux shared library (.so) deployment using readelf for detection.

This module provides automatic deployment of LLVM toolchain shared libraries
(libc++, libunwind, etc.) to executable directories on Linux. It uses readelf
for dependency detection and handles versioned symlinks properly.
"""

import logging
import os
import re
import subprocess
from pathlib import Path

from clang_tool_chain.env_utils import is_feature_disabled
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

from .base_deployer import BaseLibraryDeployer

logger = logging.getLogger(__name__)


class SoDeployer(BaseLibraryDeployer):
    """
    Linux .so file deployment using readelf for detection.

    Features:
    - Uses readelf -d (safe, no execution)
    - Handles versioned symlinks (libfoo.so.1 -> libfoo.so.1.2.3)
    - Copies toolchain libraries (libc++, libunwind)
    - Excludes system libraries (glibc, libpthread)
    """

    # Libraries to deploy (LLVM toolchain libraries)
    DEPLOYABLE_PATTERNS = [
        r"libc\+\+\.so[.\d]*",
        r"libc\+\+abi\.so[.\d]*",
        r"libunwind\.so[.\d]*",
        r"libclang_rt\..*\.so",  # Sanitizer runtimes
    ]

    # System libraries to never deploy
    SYSTEM_LIBRARIES = {
        "libc.so.6",
        "libm.so.6",
        "libpthread.so.0",
        "libdl.so.2",
        "librt.so.1",
        "linux-vdso.so.1",
        "ld-linux-x86-64.so.2",
        "ld-linux-aarch64.so.1",
        "libgcc_s.so.1",  # Usually system-provided
    }

    def __init__(self, arch: str = "x86_64"):
        """
        Initialize Linux .so deployer.

        Args:
            arch: Architecture ("x86_64", "arm64", "aarch64")
        """
        super().__init__("linux", arch)
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.DEPLOYABLE_PATTERNS]

    def detect_dependencies(self, binary_path: Path) -> list[str]:
        """
        Detect .so dependencies using readelf -d.

        Algorithm:
        1. Run readelf -d <binary_path>
        2. Extract lines with (NEEDED)
        3. Parse library names from brackets: [libfoo.so.1]
        4. Return list of library names

        Args:
            binary_path: Path to executable or shared library

        Returns:
            List of library names (e.g., ["libc++.so.1", "libunwind.so.1"])

        Raises:
            subprocess.TimeoutExpired: If readelf times out (10s)
            subprocess.CalledProcessError: If readelf fails
        """
        try:
            result = subprocess.run(
                ["readelf", "-d", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            # Parse NEEDED entries
            # Format: 0x0000000000000001 (NEEDED) Shared library: [libc++.so.1]
            needed_pattern = re.compile(r"\(NEEDED\).*\[([^\]]+)\]")
            libraries = []

            for line in result.stdout.splitlines():
                match = needed_pattern.search(line)
                if match:
                    libraries.append(match.group(1))

            return libraries

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return []
        except subprocess.TimeoutExpired:
            self.logger.warning(f"readelf timed out on {binary_path}")
            return []
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"readelf failed: {e}")
            return []
        except FileNotFoundError:
            self.logger.warning("readelf not found - install binutils")
            return []

    def is_deployable_library(self, lib_name: str) -> bool:
        """
        Check if library should be deployed.

        Rules:
        - Exclude system libraries (glibc, libpthread, etc.)
        - Include toolchain libraries (libc++, libunwind, etc.)

        Args:
            lib_name: Library filename (e.g., "libc++.so.1")

        Returns:
            True if library should be copied, False if system library
        """
        # Exact match against system libraries
        if lib_name in self.SYSTEM_LIBRARIES:
            return False

        # Pattern match against deployable libraries
        return any(pattern.match(lib_name) for pattern in self._compiled_patterns)

    def find_library_in_toolchain(self, lib_name: str) -> Path | None:
        """
        Search for .so file in toolchain and system paths.

        Search order:
        1. Clang compiler-rt directory (lib/clang/<version>/lib/<target>/) - for sanitizer runtimes
        2. Clang toolchain lib directory
        3. /usr/local/lib (user installs)
        4. /usr/lib/<arch> (system libs, filtered)
        5. Resolve symlinks to real files

        Args:
            lib_name: Library filename to locate

        Returns:
            Path to actual .so file (not symlink), None if not found
        """
        try:
            from clang_tool_chain.platform.detection import get_platform_binary_dir

            clang_bin = get_platform_binary_dir()
            clang_root = clang_bin.parent
            clang_lib = clang_root / "lib"

            # Architecture-specific lib directory
            if self.arch == "x86_64":
                arch_lib_dir = "x86_64-linux-gnu"
                compiler_rt_targets = ["x86_64-unknown-linux-gnu", "linux"]
            elif self.arch == "arm64" or self.arch == "aarch64":
                arch_lib_dir = "aarch64-linux-gnu"
                compiler_rt_targets = ["aarch64-unknown-linux-gnu", "linux"]
            else:
                arch_lib_dir = self.arch
                compiler_rt_targets = ["linux"]

            search_paths: list[Path] = []

            # Search compiler-rt directories first (for sanitizer runtimes like libclang_rt.asan.so)
            # Path pattern: lib/clang/<version>/lib/<target>/
            clang_version_dir = clang_lib / "clang"
            if clang_version_dir.exists():
                for version_dir in clang_version_dir.iterdir():
                    if version_dir.is_dir():
                        for target in compiler_rt_targets:
                            rt_lib_dir = version_dir / "lib" / target
                            if rt_lib_dir.exists():
                                search_paths.append(rt_lib_dir)

            # Then search standard lib directories
            search_paths.extend(
                [
                    clang_lib,
                    Path("/usr/local/lib"),
                    Path(f"/usr/lib/{arch_lib_dir}"),
                    Path("/usr/lib"),
                ]
            )

            for search_dir in search_paths:
                if not search_dir.exists():
                    continue

                lib_path = search_dir / lib_name
                if lib_path.exists():
                    # Resolve symlink to actual file
                    resolved = lib_path.resolve()
                    if resolved.exists():
                        return resolved

            return None

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return None
        except Exception as e:
            self.logger.debug(f"Error searching for {lib_name}: {e}")
            return None

    def get_library_extension(self) -> str:
        """
        Return platform-specific library extension.

        Returns:
            ".so" for Linux
        """
        return ".so"

    def deploy_library(self, lib_name: str, output_dir: Path) -> bool:
        """
        Deploy .so file and create necessary symlinks.

        For versioned libraries (libfoo.so.1.2.3):
        1. Copy actual library file
        2. Create SONAME symlink (libfoo.so.1 -> libfoo.so.1.2.3)

        Args:
            lib_name: Library filename to deploy
            output_dir: Directory containing the executable

        Returns:
            True if library was deployed, False if skipped/failed
        """
        src_path = self.find_library_in_toolchain(lib_name)
        if src_path is None:
            self.logger.warning(f"Library not found: {lib_name}")
            return False

        # Deploy main file
        dest_path = output_dir / src_path.name
        try:
            was_deployed = self._atomic_copy(src_path, dest_path)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return False
        except Exception as e:
            self.logger.warning(f"Failed to deploy {lib_name}: {e}")
            return False

        # Create symlinks if needed
        # Example: libfoo.so.1 (lib_name) -> libfoo.so.1.2.3 (src_path.name)
        if src_path.name != lib_name:
            symlink_path = output_dir / lib_name
            if not symlink_path.exists():
                try:
                    # Create relative symlink
                    symlink_path.symlink_to(src_path.name)
                    self.logger.debug(f"Created symlink: {lib_name} -> {src_path.name}")
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except OSError as e:
                    self.logger.debug(f"Failed to create symlink: {e}")

        return was_deployed


def detect_required_so_files(
    exe_path: Path,
    arch: str = "x86_64",
    recursive: bool = True,
) -> list[str]:
    """
    Detect required .so files for a Linux executable.

    This is a convenience wrapper function that maintains API compatibility
    with the Windows DLL deployment module.

    Args:
        exe_path: Path to executable or shared library
        arch: Architecture ("x86_64", "arm64", "aarch64")
        recursive: If True, scan transitive dependencies

    Returns:
        List of .so filenames to deploy
    """
    deployer = SoDeployer(arch)
    return list(deployer.detect_all_dependencies(exe_path, recursive=recursive))


def post_link_so_deployment(
    output_path: Path,
    arch: str = "x86_64",
) -> int:
    """
    Deploy required .so files after linking (post-link hook).

    This function is called by execution/core.py after successful linking.

    Args:
        output_path: Path to the linked executable or shared library
        arch: Architecture ("x86_64", "arm64", "aarch64")

    Returns:
        Number of .so files deployed

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS: Set to "1" to disable all library deployment
        CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB: Set to "1" to disable deployment for shared library outputs
        CLANG_TOOL_CHAIN_NO_AUTO: Set to "1" to disable all automatic features
    """
    # Check environment variables (NO_DEPLOY_LIBS or NO_AUTO)
    if is_feature_disabled("DEPLOY_LIBS"):
        return 0

    # Check if output is a shared library (.so) - if so, check NO_DEPLOY_SHARED_LIB
    is_shared_lib = output_path.suffix == ".so" or ".so." in output_path.name
    if is_shared_lib and is_feature_disabled("DEPLOY_SHARED_LIB"):
        return 0

    # Check if output is a deployable binary
    if not output_path.exists():
        logger.debug(f"Output file does not exist: {output_path}")
        return 0

    # Check file extension (.so or executable)
    is_shared_lib = output_path.suffix == ".so" or ".so." in output_path.name
    is_executable = output_path.is_file() and os.access(output_path, os.X_OK)

    if not is_shared_lib and not is_executable:
        logger.debug(f"Output is not an executable or .so: {output_path}")
        return 0

    # Deploy dependencies
    deployer = SoDeployer(arch)
    try:
        return deployer.deploy_all(output_path)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
        return 0
    except Exception as e:
        logger.warning(f"Linux .so deployment failed: {e}")
        return 0
