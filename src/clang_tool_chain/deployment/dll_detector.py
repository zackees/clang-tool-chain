"""
DLL detection strategies for Windows executables and shared libraries.

This module provides pluggable strategies for detecting runtime DLL dependencies
using the Strategy pattern. Supports both precise detection via llvm-objdump and
heuristic fallback strategies.
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly

logger = logging.getLogger(__name__)


class DLLDetector(ABC):
    """
    Abstract base class for DLL detection strategies.

    Implementations should detect required runtime DLLs for a given binary
    (executable or shared library) using various detection methods.
    """

    @abstractmethod
    def detect(self, binary_path: Path) -> list[str]:
        """
        Detect required runtime DLLs for a binary.

        Args:
            binary_path: Path to the binary file (.exe or .dll)

        Returns:
            List of DLL filenames (e.g., ["libwinpthread-1.dll", "libgcc_s_seh-1.dll"])

        Raises:
            FileNotFoundError: If binary_path does not exist
        """
        pass


class ObjdumpDLLDetector(DLLDetector):
    """
    DLL detector using llvm-objdump to parse PE headers.

    This is the primary/preferred detection strategy as it provides precise
    DLL dependency information by parsing the PE import table.
    """

    def __init__(self, objdump_path: Path, dll_filter_func=None):
        """
        Initialize the objdump-based DLL detector.

        Args:
            objdump_path: Path to llvm-objdump executable
            dll_filter_func: Optional function to filter deployable DLLs (takes dll_name: str, returns bool)
        """
        self.objdump_path = objdump_path
        self.dll_filter_func = dll_filter_func

    def detect(self, binary_path: Path) -> list[str]:
        """
        Detect DLLs using llvm-objdump -p (parse PE headers).

        Args:
            binary_path: Path to the binary file (.exe or .dll)

        Returns:
            List of deployable DLL filenames

        Raises:
            FileNotFoundError: If binary_path does not exist
            RuntimeError: If llvm-objdump fails or is not found
        """
        if not binary_path.exists():
            raise FileNotFoundError(f"Binary not found: {binary_path}")

        if not self.objdump_path.exists():
            raise RuntimeError(f"llvm-objdump not found: {self.objdump_path}")

        # Run llvm-objdump -p to get PE headers
        logger.debug(f"Running llvm-objdump on: {binary_path}")

        try:
            result = subprocess.run(
                [str(self.objdump_path), "-p", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("llvm-objdump timed out after 10 seconds") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"llvm-objdump failed (exit {e.returncode})") from e

        # Extract all DLL dependencies from output
        import re

        dll_pattern = re.compile(r"DLL Name:\s+(\S+)", re.IGNORECASE)
        all_dlls = [match.group(1) for match in dll_pattern.finditer(result.stdout)]

        # Filter to deployable DLLs only if filter function provided
        if self.dll_filter_func:
            detected_dlls = [dll for dll in all_dlls if self.dll_filter_func(dll)]
            logger.debug(f"Found {len(detected_dlls)} deployable DLL(s) out of {len(all_dlls)} total")
            return detected_dlls

        return all_dlls


class HeuristicDLLDetector(DLLDetector):
    """
    Fallback DLL detector using a hardcoded heuristic list.

    This strategy is used when llvm-objdump is unavailable or fails.
    Returns a conservative list of common MinGW runtime DLLs.
    """

    # Common MinGW runtime DLLs used by most executables
    DEFAULT_MINGW_DLLS = [
        "libwinpthread-1.dll",
        "libgcc_s_seh-1.dll",
        "libstdc++-6.dll",
    ]

    def __init__(self, dll_list: list[str] | None = None):
        """
        Initialize the heuristic detector.

        Args:
            dll_list: Optional custom DLL list (defaults to DEFAULT_MINGW_DLLS)
        """
        self.dll_list = dll_list if dll_list is not None else self.DEFAULT_MINGW_DLLS.copy()

    def detect(self, binary_path: Path) -> list[str]:
        """
        Return the heuristic DLL list.

        Args:
            binary_path: Path to the binary file (not used, checked for existence only)

        Returns:
            List of heuristic DLL filenames

        Raises:
            FileNotFoundError: If binary_path does not exist
        """
        if not binary_path.exists():
            raise FileNotFoundError(f"Binary not found: {binary_path}")

        logger.debug(f"Using heuristic DLL list ({len(self.dll_list)} DLLs)")
        return self.dll_list.copy()


class TransitiveDependencyScanner:
    """
    Scans DLLs recursively to find transitive dependencies.

    Given a list of direct DLL dependencies, this scanner locates each DLL
    in the toolchain and extracts its dependencies, repeating until all
    transitive dependencies are discovered.
    """

    def __init__(self, dll_locator_func, objdump_path: Path, dll_filter_func=None):
        """
        Initialize the transitive dependency scanner.

        Args:
            dll_locator_func: Function to locate DLLs in toolchain (takes dll_name: str, returns Path | None)
            objdump_path: Path to llvm-objdump executable
            dll_filter_func: Optional function to filter deployable DLLs (takes dll_name: str, returns bool)
        """
        self.dll_locator_func = dll_locator_func
        self.objdump_path = objdump_path
        self.dll_filter_func = dll_filter_func

    def scan_transitive_dependencies(self, direct_deps: list[str]) -> list[str]:
        """
        Recursively scan DLLs to find all transitive dependencies.

        Args:
            direct_deps: List of direct DLL dependencies

        Returns:
            List of all DLL dependencies (direct + transitive)
        """
        all_required_dlls = set(direct_deps)
        dlls_to_scan = direct_deps.copy()
        scanned_dlls = set()

        while dlls_to_scan:
            current_dll = dlls_to_scan.pop(0)

            if current_dll in scanned_dlls:
                continue

            scanned_dlls.add(current_dll)

            # Find the DLL in the toolchain
            dll_path = self.dll_locator_func(current_dll)
            if dll_path is None:
                logger.debug(f"Cannot scan dependencies for {current_dll}: not found in toolchain")
                continue

            # Extract dependencies from this DLL using objdump
            try:
                transitive_deps = self._extract_dll_dependencies(dll_path)

                for dep_name in transitive_deps:
                    # Apply filter if provided
                    if self.dll_filter_func and not self.dll_filter_func(dep_name):
                        continue

                    if dep_name not in all_required_dlls:
                        logger.debug(f"Found transitive dependency: {dep_name} (via {current_dll})")
                        all_required_dlls.add(dep_name)
                        dlls_to_scan.append(dep_name)

            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                logger.debug(f"Failed to scan dependencies for {current_dll}: {e}")

        logger.debug(f"Total DLLs (including transitive): {len(all_required_dlls)}")
        return list(all_required_dlls)

    def _extract_dll_dependencies(self, dll_path: Path) -> list[str]:
        """
        Extract DLL dependencies using llvm-objdump.

        Args:
            dll_path: Path to the DLL file

        Returns:
            List of all DLL names (both deployable and system DLLs)

        Raises:
            subprocess.TimeoutExpired: If objdump times out
            subprocess.CalledProcessError: If objdump fails
        """
        import re

        result = subprocess.run(
            [str(self.objdump_path), "-p", str(dll_path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )

        # Parse DLL dependencies from output
        dll_pattern = re.compile(r"DLL Name:\s+(\S+)", re.IGNORECASE)
        return [match.group(1) for match in dll_pattern.finditer(result.stdout)]
