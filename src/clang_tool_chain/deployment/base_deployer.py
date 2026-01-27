"""
Abstract base class for platform-specific library deployment.

This module provides the foundation for cross-platform shared library deployment,
extracting common logic from the Windows DLL deployer. Platform-specific implementations
inherit from BaseLibraryDeployer and implement detection and filtering methods.
"""

import contextlib
import logging
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

logger = logging.getLogger(__name__)


class BaseLibraryDeployer(ABC):
    """
    Abstract base class for platform-specific library deployment.

    Provides common deployment logic:
    - Recursive dependency scanning
    - Timestamp-based copy optimization
    - Atomic file deployment (hard link + fallback)
    - Non-fatal error handling

    Platform-specific subclasses must implement:
    - detect_dependencies() - Extract library names from binary
    - is_deployable_library() - Filter system vs deployable libraries
    - find_library_in_toolchain() - Locate library source files
    - get_library_extension() - Return platform library extension
    """

    def __init__(self, platform_name: str, arch: str):
        """
        Initialize base deployer.

        Args:
            platform_name: Platform name ("windows", "linux", "darwin")
            arch: Architecture ("x86_64", "arm64", etc.)
        """
        self.platform_name = platform_name
        self.arch = arch
        self.logger = logging.getLogger(__name__)

    # ===== ABSTRACT METHODS (must be implemented by subclasses) =====

    @abstractmethod
    def detect_dependencies(self, binary_path: Path) -> list[str]:
        """
        Detect direct library dependencies of a binary.

        Platform-specific implementations:
        - Windows: llvm-objdump -p (PE import table)
        - Linux: readelf -d (ELF NEEDED entries)
        - macOS: otool -L (Mach-O load commands)

        Args:
            binary_path: Path to executable or shared library

        Returns:
            List of library names (e.g., ["libc++.so.1", "libunwind.so.1"])

        Raises:
            subprocess.TimeoutExpired: If detection tool times out
            subprocess.CalledProcessError: If detection tool fails
        """
        pass

    @abstractmethod
    def is_deployable_library(self, lib_name: str) -> bool:
        """
        Check if a library should be deployed.

        Platform-specific filtering:
        - Windows: Include MinGW/sanitizer DLLs, exclude system DLLs
        - Linux: Include libc++/libunwind, exclude glibc/libpthread
        - macOS: Include custom dylibs, exclude libSystem/frameworks

        Args:
            lib_name: Library filename (e.g., "libc++.so.1")

        Returns:
            True if library should be copied, False if system library
        """
        pass

    @abstractmethod
    def find_library_in_toolchain(self, lib_name: str) -> Path | None:
        """
        Locate library file in toolchain directories.

        Platform-specific search paths:
        - Windows: MinGW sysroot/bin, clang/bin
        - Linux: clang/lib, /usr/lib, /usr/local/lib
        - macOS: clang/lib, /usr/local/lib, Homebrew paths

        Args:
            lib_name: Library filename to locate

        Returns:
            Path to library file if found, None otherwise
        """
        pass

    @abstractmethod
    def get_library_extension(self) -> str:
        """
        Return platform-specific library extension.

        Returns:
            ".dll" (Windows), ".so" (Linux), ".dylib" (macOS)
        """
        pass

    # ===== COMMON METHODS (inherited by all subclasses) =====

    def detect_all_dependencies(self, binary_path: Path, recursive: bool = True) -> set[str]:
        """
        Detect all dependencies (direct + transitive if recursive=True).

        Uses breadth-first traversal to find transitive dependencies:
        1. Detect direct dependencies of binary_path
        2. For each dependency, detect its dependencies (if deployable)
        3. Continue until no new dependencies found
        4. Return deduplicated set

        Args:
            binary_path: Path to executable or shared library
            recursive: If True, scan transitive dependencies

        Returns:
            Set of all deployable library names
        """
        all_deps: set[str] = set()
        to_scan: list[str] = []
        scanned: set[str] = set()

        # Detect direct dependencies
        try:
            direct_deps = self.detect_dependencies(binary_path)
            for dep in direct_deps:
                if self.is_deployable_library(dep):
                    all_deps.add(dep)
                    if recursive:
                        to_scan.append(dep)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            self.logger.warning(f"Failed to detect dependencies: {e}")
            return set()

        # Recursive scan
        if recursive:
            while to_scan:
                current = to_scan.pop(0)
                if current in scanned:
                    continue
                scanned.add(current)

                # Find library in toolchain
                lib_path = self.find_library_in_toolchain(current)
                if lib_path is None:
                    self.logger.debug(f"Library not found in toolchain: {current}")
                    continue

                # Detect transitive dependencies
                try:
                    transitive = self.detect_dependencies(lib_path)
                    for dep in transitive:
                        if self.is_deployable_library(dep) and dep not in all_deps:
                            all_deps.add(dep)
                            to_scan.append(dep)
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    self.logger.debug(f"Failed to scan {current}: {e}")
                    continue

        return all_deps

    def _should_copy(self, src: Path, dest: Path) -> bool:
        """
        Check if file should be copied based on timestamps.

        Args:
            src: Source file path
            dest: Destination file path

        Returns:
            True if dest doesn't exist or src is newer, False otherwise
        """
        if not dest.exists():
            return True

        src_mtime = src.stat().st_mtime
        dest_mtime = dest.stat().st_mtime

        if src_mtime <= dest_mtime:
            self.logger.debug(f"Skipped (up-to-date): {dest.name}")
            return False

        return True

    def _atomic_copy(self, src: Path, dest: Path) -> bool:
        """
        Atomically copy file using hard link (preferred) or copy + rename.

        Algorithm:
        1. Check timestamp - skip if dest is up-to-date
        2. Try hard link (zero disk space, instant)
        3. Fallback to copy + atomic rename
        4. Handle race conditions (concurrent builds)

        Args:
            src: Source file path
            dest: Destination file path

        Returns:
            True if file was copied/linked, False if skipped

        Raises:
            OSError: If copy fails (other than race condition)
        """
        # Timestamp check
        if not self._should_copy(src, dest):
            return False

        # Remove outdated destination
        if dest.exists():
            with contextlib.suppress(OSError):
                dest.unlink()  # Will fail later if removal required

        # Try hard link
        try:
            os.link(src, dest)
            self.logger.debug(f"Deployed (hard link): {dest.name}")
            return True
        except (OSError, NotImplementedError):
            pass  # Fall back to copy

        # Fallback: copy to temp + atomic rename
        temp_name = f".{dest.name}.{uuid.uuid4().hex[:8]}.tmp"
        temp_path = dest.parent / temp_name
        temp_stat = None

        try:
            shutil.copy2(src, temp_path)
            temp_stat = temp_path.stat()

            # Atomic rename
            if os.name == "nt":
                temp_path.replace(dest)  # Windows atomic replace
            else:
                temp_path.rename(dest)  # POSIX atomic rename

            self.logger.debug(f"Deployed (copy): {dest.name}")
            return True

        except FileExistsError:
            # Race condition: another process deployed it
            temp_path.unlink(missing_ok=True)
            return False

        except OSError:
            # Check if files are same size (concurrent write)
            if dest.exists() and temp_stat is not None:
                try:
                    dest_stat = dest.stat()
                    if temp_stat.st_size == dest_stat.st_size:
                        temp_path.unlink(missing_ok=True)
                        return False
                except OSError:
                    pass  # Ignore stat errors
            temp_path.unlink(missing_ok=True)
            raise

        except KeyboardInterrupt as ke:
            temp_path.unlink(missing_ok=True)
            handle_keyboard_interrupt_properly(ke)
            raise  # Re-raise after cleanup
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def deploy_library(self, lib_name: str, output_dir: Path) -> bool:
        """
        Deploy a single library to output directory.

        Args:
            lib_name: Library filename to deploy
            output_dir: Directory containing the executable

        Returns:
            True if library was deployed, False if skipped/failed
        """
        # Find library in toolchain
        src_path = self.find_library_in_toolchain(lib_name)
        if src_path is None:
            self.logger.warning(f"Library not found: {lib_name}")
            return False

        # Deploy to output directory
        dest_path = output_dir / lib_name

        try:
            was_deployed = self._atomic_copy(src_path, dest_path)
            return was_deployed
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return False
        except Exception as e:
            self.logger.warning(f"Failed to deploy {lib_name}: {e}")
            return False

    def deploy_all(self, binary_path: Path) -> int:
        """
        Main deployment orchestrator.

        Detects all dependencies (direct + transitive) and deploys them
        to the directory containing binary_path.

        Args:
            binary_path: Path to executable or shared library

        Returns:
            Number of libraries successfully deployed
        """
        output_dir = binary_path.parent

        # Detect all dependencies
        dependencies = self.detect_all_dependencies(binary_path, recursive=True)

        if not dependencies:
            self.logger.debug("No deployable dependencies found")
            return 0

        # Deploy each library
        deployed_count = 0
        for lib_name in dependencies:
            if self.deploy_library(lib_name, output_dir):
                deployed_count += 1

        # Summary logging
        if deployed_count > 0:
            self.logger.info(
                f"Deployed {deployed_count} shared librar{'y' if deployed_count == 1 else 'ies'} for {binary_path.name}"
            )

        return deployed_count
