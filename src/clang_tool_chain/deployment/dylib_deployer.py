"""
macOS .dylib deployment using otool for dependency detection.

This module provides automatic shared library deployment for macOS executables
and shared libraries. It handles dylib detection, copying, install_name_tool
modifications, and code signing.

Features:
- Uses otool -L for dependency detection
- Handles @rpath, @loader_path, @executable_path
- Modifies install names with install_name_tool
- Re-signs binaries after modifications
- Non-fatal error handling (warnings only)

Example:
    deployer = DylibDeployer(arch="arm64")
    deployed_count = deployer.deploy_all(Path("program"))
"""

import logging
import os
import re
import subprocess
from pathlib import Path

from .base_deployer import BaseLibraryDeployer

logger = logging.getLogger(__name__)


class DylibDeployer(BaseLibraryDeployer):
    """
    macOS .dylib deployment using otool for detection.

    Provides automatic shared library deployment for macOS:
    - Detects .dylib dependencies using otool -L
    - Copies toolchain-provided dylibs to executable directory
    - Fixes install names with install_name_tool
    - Re-signs binaries after modifications
    - Handles @rpath, @loader_path, @executable_path

    Deployable libraries:
    - libc++.*.dylib - LLVM C++ standard library
    - libc++abi.*.dylib - LLVM C++ ABI library
    - libunwind.*.dylib - LLVM stack unwinding library
    - libclang_rt.*.dylib - Sanitizer runtimes

    Excluded system libraries/frameworks:
    - /usr/lib/* - System libraries
    - /System/Library/* - System frameworks
    """

    # Libraries to deploy (LLVM toolchain libraries)
    DEPLOYABLE_PATTERNS = [
        r"libc\+\+\.\d+\.dylib",
        r"libc\+\+abi\.\d+\.dylib",
        r"libunwind\.\d+\.dylib",
        r"libclang_rt\..*\.dylib",  # Sanitizer runtimes (ASan, TSan, etc.)
    ]

    # System paths to never deploy (libraries from these paths are system-provided)
    SYSTEM_PATHS = [
        "/usr/lib/",
        "/System/Library/",
    ]

    def __init__(self, arch: str = "x86_64"):
        """
        Initialize macOS dylib deployer.

        Args:
            arch: Target architecture ("x86_64" or "arm64")
        """
        super().__init__("darwin", arch)
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.DEPLOYABLE_PATTERNS]

    def detect_dependencies(self, binary_path: Path) -> list[str]:
        """
        Detect .dylib dependencies using otool -L.

        Runs otool -L to extract Mach-O load commands and parses library paths.

        Algorithm:
        1. Run otool -L <binary_path>
        2. Skip first line (binary's own install name)
        3. Parse each line: "\t/path/to/lib.dylib (compatibility...)"
        4. Extract library paths

        Args:
            binary_path: Path to executable or shared library

        Returns:
            List of library paths (may include @rpath, absolute paths, etc.)

        Example:
            >>> deployer = DylibDeployer()
            >>> deps = deployer.detect_dependencies(Path("program"))
            >>> deps
            ['@rpath/libc++.1.dylib', '/usr/lib/libSystem.B.dylib']
        """
        try:
            result = subprocess.run(
                ["otool", "-L", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            lines = result.stdout.strip().split("\n")
            dependencies = []

            # Skip first line (binary's own install name)
            for line in lines[1:]:
                # Format: "\t/path/to/lib.dylib (compatibility version X, current version Y)"
                parts = line.strip().split(" ")
                if parts:
                    lib_path = parts[0]
                    dependencies.append(lib_path)

            return dependencies

        except subprocess.TimeoutExpired:
            self.logger.warning(f"otool timed out on {binary_path}")
            return []
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"otool failed: {e}")
            return []
        except FileNotFoundError:
            self.logger.warning("otool not found - install Xcode Command Line Tools")
            return []
        except KeyboardInterrupt:
            self.logger.info("Interrupted during dependency detection")
            raise
        except Exception as e:
            self.logger.warning(f"Unexpected error in detect_dependencies: {e}")
            return []

    def is_deployable_library(self, lib_name: str) -> bool:
        """
        Check if dylib should be deployed.

        Filters system libraries and frameworks, keeping only toolchain-provided
        libraries that match deployable patterns.

        Rules:
        - Exclude /usr/lib/* (system libraries)
        - Exclude /System/Library/* (frameworks)
        - Include @rpath/* (needs resolution)
        - Include /usr/local/lib/* (Homebrew/custom builds)
        - Include /opt/homebrew/* (ARM Homebrew)

        Args:
            lib_name: Library path from otool -L output

        Returns:
            True if library should be copied, False if system library

        Example:
            >>> deployer = DylibDeployer()
            >>> deployer.is_deployable_library("@rpath/libc++.1.dylib")
            True
            >>> deployer.is_deployable_library("/usr/lib/libSystem.B.dylib")
            False
        """
        # System paths - exclude most, with exceptions
        for sys_path in self.SYSTEM_PATHS:
            if lib_name.startswith(sys_path):
                # Special case: libunwind in /usr/lib is part of libSystem
                if "libunwind" in lib_name and lib_name.startswith("/usr/lib/"):
                    return False
                # Exclude all /usr/lib and /System/Library
                return False

        # @rpath or custom paths - check if matches deployable patterns
        if lib_name.startswith("@rpath") or lib_name.startswith("/usr/local") or lib_name.startswith("/opt/"):
            filename = Path(lib_name).name
            for pattern in self._compiled_patterns:
                if pattern.match(filename):
                    return True

        # Not a deployable library
        return False

    def find_library_in_toolchain(self, lib_name: str) -> Path | None:
        """
        Locate dylib file, resolving @rpath if needed.

        Searches for dylib in toolchain and common macOS library paths,
        resolving @rpath and @loader_path prefixes.

        Search order:
        1. If absolute path, check if exists
        2. If @rpath, search in toolchain lib
        3. Search /usr/local/lib (Homebrew Intel)
        4. Search /opt/homebrew/lib (Homebrew ARM)
        5. Search /opt/local/lib (MacPorts)

        Args:
            lib_name: Library path from otool -L output (may include @rpath)

        Returns:
            Resolved path to .dylib file, or None if not found

        Example:
            >>> deployer = DylibDeployer()
            >>> path = deployer.find_library_in_toolchain("@rpath/libc++.1.dylib")
            >>> path
            PosixPath('/path/to/clang/lib/libc++.1.dylib')
        """
        try:
            # Lazy import to avoid circular dependencies
            from clang_tool_chain.platform.detection import get_platform_binary_dir

            # Extract library name
            if lib_name.startswith("@rpath/"):
                filename = lib_name[7:]  # Remove "@rpath/"
            elif lib_name.startswith("@loader_path/"):
                filename = lib_name[13:]  # Remove "@loader_path/"
            elif lib_name.startswith("@executable_path/"):
                filename = lib_name[17:]  # Remove "@executable_path/"
            else:
                # Absolute path
                path = Path(lib_name)
                if path.exists():
                    return path.resolve()
                filename = path.name

            # Search paths
            clang_bin = get_platform_binary_dir()
            clang_lib = clang_bin.parent / "lib"

            search_paths = [
                clang_lib,
                Path("/usr/local/lib"),
                Path("/opt/homebrew/lib"),  # ARM macOS (Homebrew)
                Path("/opt/local/lib"),  # MacPorts
            ]

            for search_dir in search_paths:
                if not search_dir.exists():
                    continue

                lib_path_obj = search_dir / filename
                if lib_path_obj.exists():
                    return lib_path_obj.resolve()

            return None

        except KeyboardInterrupt:
            self.logger.info("Interrupted during library search")
            raise
        except Exception as e:
            self.logger.debug(f"Error searching for {lib_name}: {e}")
            return None

    def get_library_extension(self) -> str:
        """
        Return platform-specific library extension.

        Returns:
            ".dylib" for macOS
        """
        return ".dylib"

    def _fix_install_name(self, binary_path: Path, old_path: str, new_path: str) -> None:
        """
        Fix dylib path using install_name_tool.

        Changes dependency path from old_path to new_path in binary_path.
        This allows dylibs to be found using @loader_path instead of absolute paths.

        Args:
            binary_path: Path to binary to modify
            old_path: Original library path (e.g., "@rpath/libc++.1.dylib")
            new_path: New library path (e.g., "@loader_path/libc++.1.dylib")

        Example:
            >>> deployer = DylibDeployer()
            >>> deployer._fix_install_name(
            ...     Path("program"),
            ...     "@rpath/libc++.1.dylib",
            ...     "@loader_path/libc++.1.dylib"
            ... )
        """
        try:
            subprocess.run(
                ["install_name_tool", "-change", old_path, new_path, str(binary_path)],
                check=True,
                capture_output=True,
                timeout=10,
            )
            self.logger.debug(f"Fixed install name: {old_path} -> {new_path}")
        except subprocess.TimeoutExpired:
            self.logger.warning(f"install_name_tool timed out on {binary_path}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"install_name_tool failed: {e}")
        except FileNotFoundError:
            self.logger.warning("install_name_tool not found - install Xcode Command Line Tools")
        except KeyboardInterrupt:
            self.logger.info("Interrupted during install_name_tool")
            raise
        except Exception as e:
            self.logger.warning(f"Unexpected error in _fix_install_name: {e}")

    def _resign_binary(self, binary_path: Path) -> None:
        """
        Re-sign binary after install_name_tool modifications.

        Uses ad-hoc signing (-s -) for testing/development.
        Production apps should use proper code signing with certificates.

        Args:
            binary_path: Path to binary to re-sign

        Example:
            >>> deployer = DylibDeployer()
            >>> deployer._resign_binary(Path("program"))
        """
        try:
            subprocess.run(
                ["codesign", "-s", "-", "--force", str(binary_path)],
                check=True,
                capture_output=True,
                timeout=60,
            )
            self.logger.debug(f"Re-signed: {binary_path.name}")
        except subprocess.TimeoutExpired:
            self.logger.warning(f"codesign timed out on {binary_path}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Code signing failed: {e}")
        except FileNotFoundError:
            self.logger.debug("codesign not found - signature will be invalid")
        except KeyboardInterrupt:
            self.logger.info("Interrupted during code signing")
            raise
        except Exception as e:
            self.logger.warning(f"Unexpected error in _resign_binary: {e}")

    def deploy_library(self, lib_name: str, output_dir: Path) -> bool:
        """
        Deploy .dylib and fix install names.

        Steps:
        1. Find dylib in toolchain
        2. Copy to output directory
        3. Fix dylib's install name to @loader_path
        4. Re-sign dylib

        Note: This does NOT fix the executable's reference. Use deploy_all()
        to fix both dylib and executable references.

        Args:
            lib_name: Library path from otool -L output
            output_dir: Directory to deploy library to

        Returns:
            True if library was deployed, False if skipped/failed

        Example:
            >>> deployer = DylibDeployer()
            >>> success = deployer.deploy_library(
            ...     "@rpath/libc++.1.dylib",
            ...     Path("build")
            ... )
        """
        try:
            src_path = self.find_library_in_toolchain(lib_name)
            if src_path is None:
                self.logger.warning(f"Library not found: {lib_name}")
                return False

            filename = src_path.name
            dest_path = output_dir / filename

            # Copy dylib
            try:
                was_deployed = self._atomic_copy(src_path, dest_path)
            except Exception as e:
                self.logger.warning(f"Failed to deploy {filename}: {e}")
                return False

            # Fix dylib's install name (if newly deployed)
            if was_deployed:
                self._fix_install_name(dest_path, str(src_path), f"@loader_path/{filename}")
                self._resign_binary(dest_path)

            return was_deployed

        except KeyboardInterrupt:
            self.logger.info("Interrupted during library deployment")
            raise
        except Exception as e:
            self.logger.warning(f"Unexpected error deploying {lib_name}: {e}")
            return False

    def deploy_all(self, binary_path: Path) -> int:
        """
        Deploy dylibs and fix executable's references.

        Main deployment orchestrator for macOS. Detects all dependencies,
        deploys them, and fixes install names in both dylibs and executable.

        Steps:
        1. Detect all dependencies (direct + transitive)
        2. Deploy each dylib and fix its install name
        3. Fix executable's references to use @loader_path
        4. Re-sign executable

        Args:
            binary_path: Path to executable or shared library

        Returns:
            Number of libraries successfully deployed

        Example:
            >>> deployer = DylibDeployer()
            >>> count = deployer.deploy_all(Path("program"))
            >>> print(f"Deployed {count} dylibs")
        """
        try:
            output_dir = binary_path.parent

            # Detect dependencies
            dependencies = self.detect_all_dependencies(binary_path, recursive=True)

            if not dependencies:
                self.logger.debug("No deployable dependencies found")
                return 0

            # Deploy each library and collect original paths
            deployed_count = 0
            deployed_libs = []  # [(original_path, new_name), ...]

            for lib_path in dependencies:
                src_path = self.find_library_in_toolchain(lib_path)
                if src_path:
                    lib_name = src_path.name
                    if self.deploy_library(lib_path, output_dir):
                        deployed_count += 1
                        deployed_libs.append((lib_path, lib_name))

            # Fix executable's references to use @loader_path
            for old_path, lib_name in deployed_libs:
                self._fix_install_name(binary_path, old_path, f"@loader_path/{lib_name}")

            # Re-sign executable
            if deployed_libs:
                self._resign_binary(binary_path)

            # Summary logging
            if deployed_count > 0:
                self.logger.info(
                    f"Deployed {deployed_count} dylib{'s' if deployed_count != 1 else ''} for {binary_path.name}"
                )

            return deployed_count

        except KeyboardInterrupt:
            self.logger.info("Interrupted during deploy_all")
            raise
        except Exception as e:
            self.logger.warning(f"Unexpected error in deploy_all: {e}")
            return 0


# ===== Backward-Compatible Wrapper Functions =====


def detect_required_dylibs(exe_path: Path, arch: str = "x86_64", recursive: bool = True) -> list[str]:
    """
    Convenience wrapper for detecting required .dylib files.

    Detects .dylib dependencies of a macOS executable or shared library.

    Args:
        exe_path: Path to executable or shared library
        arch: Target architecture ("x86_64" or "arm64")
        recursive: If True, scan transitive dependencies

    Returns:
        List of deployable .dylib names

    Example:
        >>> dylibs = detect_required_dylibs(Path("program"), arch="arm64")
        >>> print(dylibs)
        ['libc++.1.dylib', 'libunwind.1.dylib']
    """
    deployer = DylibDeployer(arch)
    return list(deployer.detect_all_dependencies(exe_path, recursive=recursive))


def post_link_dylib_deployment(output_path: Path, arch: str = "x86_64") -> int:
    """
    Post-link hook for automatic .dylib deployment.

    Integrates with execution/core.py to automatically deploy dylibs after
    successful linking. Checks environment variables and file type before deploying.

    Environment variables:
    - CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1 - Disable all library deployment
    - CLANG_TOOL_CHAIN_NO_DEPLOY_DYLIBS=1 - Disable macOS-specific deployment

    Args:
        output_path: Path to executable or shared library
        arch: Target architecture ("x86_64" or "arm64")

    Returns:
        Number of dylibs deployed

    Example:
        >>> # Called automatically after linking
        >>> count = post_link_dylib_deployment(Path("program"), arch="arm64")
    """
    # Check global disable
    if os.getenv("CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS") == "1":
        logger.debug("dylib deployment disabled (CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1)")
        return 0

    # Check macOS-specific disable
    if os.getenv("CLANG_TOOL_CHAIN_NO_DEPLOY_DYLIBS") == "1":
        logger.debug("dylib deployment disabled (CLANG_TOOL_CHAIN_NO_DEPLOY_DYLIBS=1)")
        return 0

    # Check if output is executable or .dylib
    if not output_path.exists():
        logger.debug(f"Output file does not exist: {output_path}")
        return 0

    # File type check (macOS executables and .dylib files)
    is_dylib = output_path.suffix == ".dylib"
    is_executable = output_path.suffix == "" or output_path.suffix == ".out"

    if not (is_dylib or is_executable):
        logger.debug(f"Skipping dylib deployment for {output_path.suffix} file")
        return 0

    # Deploy dylibs
    try:
        deployer = DylibDeployer(arch)
        return deployer.deploy_all(output_path)
    except KeyboardInterrupt:
        logger.info("dylib deployment interrupted")
        raise
    except Exception as e:
        logger.warning(f"dylib deployment failed: {e}")
        return 0
