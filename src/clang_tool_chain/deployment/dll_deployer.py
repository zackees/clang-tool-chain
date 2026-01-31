"""
DLL deployment functionality for Windows executables built with GNU ABI.

This module provides automatic deployment of MinGW runtime DLLs to executable
directories after successful linking, ensuring executables can run in cmd.exe
without PATH modifications.
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

# MinGW runtime DLL patterns (case-insensitive matching)
MINGW_DLL_PATTERNS = [
    r"libwinpthread.*\.dll",
    r"libgcc_s_.*\.dll",
    r"libstdc\+\+.*\.dll",
    r"libc\+\+.*\.dll",  # LLVM C++ standard library
    r"libunwind.*\.dll",  # LLVM unwinding library
    r"libgomp.*\.dll",
    r"libssp.*\.dll",
    r"libquadmath.*\.dll",
]

# Sanitizer runtime DLL patterns (case-insensitive matching)
SANITIZER_DLL_PATTERNS = [
    r"libclang_rt\.asan_dynamic.*\.dll",
    r"libclang_rt\.ubsan_dynamic.*\.dll",
    r"libclang_rt\.tsan_dynamic.*\.dll",
    r"libclang_rt\.msan_dynamic.*\.dll",
]

# Windows system DLLs to exclude (case-insensitive)
WINDOWS_SYSTEM_DLLS = {
    "kernel32.dll",
    "ntdll.dll",
    "msvcrt.dll",
    "user32.dll",
    "advapi32.dll",
    "ws2_32.dll",
    "shell32.dll",
    "ole32.dll",
    "oleaut32.dll",
    "gdi32.dll",
    "comdlg32.dll",
    "comctl32.dll",
    "bcrypt.dll",
    "crypt32.dll",
}

# Heuristic fallback DLL list when llvm-objdump fails
HEURISTIC_MINGW_DLLS = [
    "libwinpthread-1.dll",
    "libgcc_s_seh-1.dll",
    "libstdc++-6.dll",
]


def _get_mingw_sysroot_bin_dir_impl(arch: str) -> Path:
    """
    Get the MinGW sysroot bin directory containing runtime DLLs.

    Helper function that can be mocked in tests.

    Args:
        arch: Architecture ("x86_64" or "arm64")

    Returns:
        Path to sysroot/bin directory

    Raises:
        ValueError: If architecture is unsupported
        RuntimeError: If sysroot not found
    """
    from ..platform.detection import get_platform_binary_dir

    # Get clang bin directory (downloads toolchain if needed)
    clang_bin_dir = get_platform_binary_dir()
    clang_root = clang_bin_dir.parent

    # Determine sysroot name
    if arch == "x86_64":
        sysroot_name = "x86_64-w64-mingw32"
    elif arch == "arm64":
        sysroot_name = "aarch64-w64-mingw32"
    else:
        raise ValueError(f"Unsupported architecture: {arch}")

    sysroot_bin = clang_root / sysroot_name / "bin"

    if not sysroot_bin.exists():
        raise RuntimeError(f"MinGW sysroot bin directory not found: {sysroot_bin}")

    return sysroot_bin


def _find_dll_in_toolchain_impl(dll_name: str, arch: str) -> Path | None:
    """
    Find DLL in MinGW sysroot or clang bin directory.

    Helper function that can be mocked in tests.

    Args:
        dll_name: DLL filename
        arch: Architecture ("x86_64" or "arm64")

    Returns:
        Path to DLL if found, None otherwise
    """
    from ..platform.detection import get_platform_binary_dir

    # Search locations in priority order
    search_dirs = []

    # 1. MinGW sysroot/bin directory
    try:
        sysroot_bin = _get_mingw_sysroot_bin_dir_impl(arch)
        search_dirs.append(sysroot_bin)
    except (ValueError, RuntimeError) as e:
        logger.debug(f"Cannot access MinGW sysroot: {e}")

    # 2. Clang bin directory (for sanitizer DLLs that may be in bin/)
    try:
        clang_bin_dir = get_platform_binary_dir()
        search_dirs.append(clang_bin_dir)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
        return None
    except Exception as e:
        logger.debug(f"Cannot access clang bin directory: {e}")

    # Search each directory
    for search_dir in search_dirs:
        dll_path = search_dir / dll_name
        if dll_path.exists():
            logger.debug(f"Found {dll_name} in {search_dir}")
            return dll_path

    logger.debug(f"DLL not found in any search directory: {dll_name}")
    return None


class DllDeployer(BaseLibraryDeployer):
    """
    Windows DLL deployer using llvm-objdump for detection.

    Features:
    - Uses llvm-objdump -p (PE import table parsing)
    - Handles MinGW runtime and sanitizer DLLs
    - Recursive transitive dependency scanning
    - Atomic deployment with hard link optimization
    """

    def __init__(self, arch: str = "x86_64"):
        super().__init__("windows", arch)
        self._compiled_mingw_patterns = [re.compile(p, re.IGNORECASE) for p in MINGW_DLL_PATTERNS]
        self._compiled_sanitizer_patterns = [re.compile(p, re.IGNORECASE) for p in SANITIZER_DLL_PATTERNS]

    def detect_dependencies(self, binary_path: Path) -> list[str]:
        """
        Detect DLL dependencies using llvm-objdump -p.

        Parses PE import table to extract DLL dependencies. Falls back to
        heuristic list if objdump fails.

        Args:
            binary_path: Path to executable or DLL

        Returns:
            List of DLL names

        Raises:
            subprocess.TimeoutExpired: If objdump times out
            subprocess.CalledProcessError: If objdump fails
        """
        try:
            from ..platform.detection import get_platform_binary_dir

            # Get llvm-objdump from the toolchain
            clang_bin_dir = get_platform_binary_dir()
            objdump_path = clang_bin_dir / "llvm-objdump.exe"

            if not objdump_path.exists():
                self.logger.warning("llvm-objdump not found, using heuristic DLL list")
                return HEURISTIC_MINGW_DLLS.copy()

            # Run llvm-objdump -p to get PE headers
            self.logger.debug(f"Running llvm-objdump on: {binary_path}")
            result = subprocess.run(
                [str(objdump_path), "-p", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            # Parse DLL dependencies from output
            dll_pattern = re.compile(r"DLL Name:\s+(\S+)", re.IGNORECASE)
            detected_dlls = []

            for match in dll_pattern.finditer(result.stdout):
                dll_name = match.group(1)
                detected_dlls.append(dll_name)

            return detected_dlls

        except subprocess.TimeoutExpired:
            self.logger.warning(f"llvm-objdump timed out on {binary_path}")
            return HEURISTIC_MINGW_DLLS.copy()
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"llvm-objdump failed: {e}")
            return HEURISTIC_MINGW_DLLS.copy()
        except FileNotFoundError:
            self.logger.warning("llvm-objdump not found")
            return HEURISTIC_MINGW_DLLS.copy()
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return []
        except Exception as e:
            self.logger.warning(f"DLL detection failed: {e}")
            return HEURISTIC_MINGW_DLLS.copy()

    def is_deployable_library(self, lib_name: str) -> bool:
        """
        Check if a DLL should be deployed.

        Rules:
        - Exclude Windows system DLLs
        - Include MinGW runtime DLLs
        - Include sanitizer DLLs

        Args:
            lib_name: DLL filename

        Returns:
            True if DLL should be deployed
        """
        dll_name_lower = lib_name.lower()

        # Exclude Windows system DLLs
        if dll_name_lower in WINDOWS_SYSTEM_DLLS:
            return False

        # Check against MinGW patterns
        if any(pattern.match(dll_name_lower) for pattern in self._compiled_mingw_patterns):
            return True

        # Check against sanitizer patterns
        return any(pattern.match(dll_name_lower) for pattern in self._compiled_sanitizer_patterns)

    def find_library_in_toolchain(self, lib_name: str) -> Path | None:
        """
        Find DLL in MinGW sysroot or clang bin directory.

        Search order:
        1. MinGW sysroot/bin (runtime DLLs)
        2. Clang bin directory (sanitizer DLLs)

        Args:
            lib_name: DLL filename

        Returns:
            Path to DLL if found, None otherwise
        """
        # Call module-level function so it can be mocked in tests
        return find_dll_in_toolchain(lib_name, "win", self.arch)

    def get_library_extension(self) -> str:
        """Return Windows library extension."""
        return ".dll"

    def _get_mingw_sysroot_bin_dir(self) -> Path:
        """
        Get the MinGW sysroot bin directory containing runtime DLLs.

        Returns:
            Path to sysroot/bin directory

        Raises:
            ValueError: If architecture is unsupported
            RuntimeError: If sysroot not found
        """
        # Call module-level function so it can be mocked in tests
        return get_mingw_sysroot_bin_dir("win", self.arch)


# ===== BACKWARD COMPATIBILITY FUNCTIONS =====
# These functions maintain the existing API for code that uses dll_deployer directly


def _is_deployable_dll(dll_name: str) -> bool:
    """
    Check if a DLL name matches MinGW runtime or sanitizer DLL patterns.

    Backward compatibility wrapper for existing code.

    Args:
        dll_name: DLL filename (e.g., "libwinpthread-1.dll", "libclang_rt.asan_dynamic-x86_64.dll")

    Returns:
        True if the DLL is a MinGW runtime or sanitizer DLL, False otherwise.

    Examples:
        >>> _is_deployable_dll("libwinpthread-1.dll")
        True
        >>> _is_deployable_dll("kernel32.dll")
        False
        >>> _is_deployable_dll("libgcc_s_seh-1.dll")
        True
        >>> _is_deployable_dll("libclang_rt.asan_dynamic-x86_64.dll")
        True
    """
    deployer = DllDeployer()
    return deployer.is_deployable_library(dll_name)


# Keep backward compatibility alias
def _is_mingw_dll(dll_name: str) -> bool:  # pyright: ignore[reportUnusedFunction]
    """Deprecated: Use _is_deployable_dll instead."""
    return _is_deployable_dll(dll_name)


def _extract_dll_dependencies(binary_path: Path, objdump_path: Path) -> list[str]:
    """
    Extract DLL dependencies from a binary file (EXE or DLL) using llvm-objdump.

    Backward compatibility wrapper.

    Args:
        binary_path: Path to the binary file (.exe or .dll)
        objdump_path: Path to llvm-objdump executable

    Returns:
        List of DLL names (both deployable and system DLLs)

    Raises:
        subprocess.TimeoutExpired: If objdump times out
        subprocess.CalledProcessError: If objdump fails
    """
    result = subprocess.run(
        [str(objdump_path), "-p", str(binary_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    # Parse DLL dependencies from output
    dll_pattern = re.compile(r"DLL Name:\s+(\S+)", re.IGNORECASE)
    detected_dlls = []

    for match in dll_pattern.finditer(result.stdout):
        dll_name = match.group(1)
        detected_dlls.append(dll_name)

    return detected_dlls


def detect_required_dlls(exe_path: Path, platform_name: str = "win", arch: str = "x86_64") -> list[str]:
    """
    Detect required MinGW runtime and sanitizer DLLs for a Windows executable.

    Uses llvm-objdump to parse PE headers and extract DLL dependencies.
    Recursively scans deployable DLLs to find transitive dependencies.
    Falls back to heuristic list if llvm-objdump fails.

    Args:
        exe_path: Path to the executable file (.exe)
        platform_name: Platform name ("win")
        arch: Architecture ("x86_64" or "arm64")

    Returns:
        List of MinGW and sanitizer DLL filenames (e.g., ["libwinpthread-1.dll", "libclang_rt.asan_dynamic-x86_64.dll", "libc++.dll"])

    Raises:
        FileNotFoundError: If exe_path does not exist

    Examples:
        >>> detect_required_dlls(Path("test.exe"))
        ['libwinpthread-1.dll', 'libgcc_s_seh-1.dll', 'libstdc++-6.dll']
    """
    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {exe_path}")

    deployer = DllDeployer(arch)

    # First attempt direct detection
    try:
        direct_deps = deployer.detect_dependencies(exe_path)

        # If heuristic was returned (empty list, or fallback list), return it directly
        if direct_deps == HEURISTIC_MINGW_DLLS:
            return HEURISTIC_MINGW_DLLS.copy()

        # Check if any deployable DLLs were found
        deployable_direct = [d for d in direct_deps if deployer.is_deployable_library(d)]
        if not deployable_direct and direct_deps:
            # objdump found DLLs but none are deployable - use heuristic
            return HEURISTIC_MINGW_DLLS.copy()
        if not direct_deps:
            # No DLLs found - use heuristic
            return HEURISTIC_MINGW_DLLS.copy()

        # Normal case: use full recursive detection
        dependencies = deployer.detect_all_dependencies(exe_path, recursive=True)
        return sorted(dependencies)  # Sort for consistent ordering

    except Exception:
        return HEURISTIC_MINGW_DLLS.copy()


def _atomic_copy_dll(src_dll: Path, dest_dll: Path) -> bool:
    """
    Atomically deploy a DLL using hard links (preferred) or file copy with atomic rename.

    Backward compatibility wrapper using BaseLibraryDeployer._atomic_copy.

    Args:
        src_dll: Source DLL path in MinGW sysroot
        dest_dll: Destination DLL path in executable directory

    Returns:
        True if DLL was deployed/updated, False if skipped (already up-to-date)

    Raises:
        OSError: If deployment fails (other than race condition)

    Examples:
        >>> _atomic_copy_dll(Path("/src/libwinpthread-1.dll"), Path("/dest/libwinpthread-1.dll"))
        True  # DLL deployed successfully (hard link or copy)
    """
    deployer = DllDeployer()
    return deployer._atomic_copy(src_dll, dest_dll)


def get_mingw_sysroot_bin_dir(platform_name: str, arch: str) -> Path:
    """
    Get the MinGW sysroot bin directory containing runtime DLLs.

    Backward compatibility wrapper.

    Args:
        platform_name: Platform name ("win")
        arch: Architecture ("x86_64" or "arm64")

    Returns:
        Path to sysroot/bin directory
        (e.g., ~/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin/)

    Raises:
        ValueError: If architecture is unsupported
        RuntimeError: If sysroot not found

    Examples:
        >>> get_mingw_sysroot_bin_dir("win", "x86_64")
        PosixPath('~/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin')
    """
    return _get_mingw_sysroot_bin_dir_impl(arch)


def find_dll_in_toolchain(dll_name: str, platform_name: str, arch: str) -> Path | None:
    """
    Find a DLL in the toolchain (MinGW sysroot or sanitizer directories).

    Backward compatibility wrapper.

    Args:
        dll_name: DLL filename (e.g., "libwinpthread-1.dll", "libclang_rt.asan_dynamic-x86_64.dll")
        platform_name: Platform name ("win")
        arch: Architecture ("x86_64" or "arm64")

    Returns:
        Path to the DLL if found, None otherwise

    Examples:
        >>> find_dll_in_toolchain("libwinpthread-1.dll", "win", "x86_64")
        PosixPath('~/.clang-tool-chain/clang/win/x86_64/x86_64-w64-mingw32/bin/libwinpthread-1.dll')
    """
    return _find_dll_in_toolchain_impl(dll_name, arch)


def post_link_dll_deployment(output_exe_path: Path, platform_name: str, use_gnu_abi: bool) -> None:
    """
    Deploy required MinGW runtime and sanitizer DLLs to the output binary directory after linking.

    This function:
    1. Detects required DLLs using llvm-objdump (with fallback)
    2. Locates source DLLs in MinGW sysroot/bin or clang/bin (for sanitizers)
    3. Copies DLLs to output directory (with timestamp checking)
    4. Handles all errors gracefully (warnings only, never fails the build)

    Supports both .exe executables and .dll shared libraries. For .dll outputs,
    deployment ensures that transitive dependencies are available alongside the
    built library.

    Args:
        output_exe_path: Path to the output binary (.exe or .dll)
        platform_name: Platform name from get_platform_info() (e.g., "win")
        use_gnu_abi: Whether GNU ABI is being used

    Returns:
        None

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS: Set to "1" to disable all library deployment
        CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB: Set to "1" to disable deployment for shared library outputs only
        CLANG_TOOL_CHAIN_NO_AUTO: Set to "1" to disable all automatic features
        CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE: Set to "1" for verbose logging

    Examples:
        >>> post_link_dll_deployment(Path("test.exe"), "win", True)
        # Deploys libwinpthread-1.dll, libgcc_s_seh-1.dll, sanitizer DLLs, etc. to test.exe directory
        >>> post_link_dll_deployment(Path("mylib.dll"), "win", True)
        # Deploys runtime DLLs alongside the shared library
    """
    # Check opt-out environment variable (via NO_DEPLOY_LIBS or NO_AUTO)
    if is_feature_disabled("DEPLOY_LIBS"):
        return

    # Enable verbose logging if requested
    if os.environ.get("CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE") == "1":
        logger.setLevel(logging.DEBUG)

    # Guard: only deploy on Windows
    if platform_name != "win":
        logger.debug(f"DLL deployment skipped: not Windows (platform={platform_name})")
        return

    # Guard: only deploy for GNU ABI
    if not use_gnu_abi:
        logger.debug("DLL deployment skipped: not using GNU ABI")
        return

    # Guard: only deploy for .exe and .dll files
    suffix = output_exe_path.suffix.lower()
    if suffix == ".dll":
        # Check for shared library-specific opt-out (via NO_DEPLOY_SHARED_LIB or NO_AUTO)
        if is_feature_disabled("DEPLOY_SHARED_LIB"):
            return
    elif suffix != ".exe":
        logger.debug(f"DLL deployment skipped: not .exe or .dll file (suffix={output_exe_path.suffix})")
        return

    # Guard: check if executable exists
    if not output_exe_path.exists():
        logger.debug(f"DLL deployment skipped: executable not found: {output_exe_path}")
        return

    try:
        from ..platform.detection import get_platform_info

        # Get platform info for sysroot lookup
        _, arch = get_platform_info()

        # Use deployer for actual deployment
        deployer = DllDeployer(arch)
        deployed_count = deployer.deploy_all(output_exe_path)

        # Log results
        if deployed_count == 0:
            logger.debug("No runtime DLLs deployed (all up-to-date or none required)")

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        # Non-fatal: log warning but don't fail the build
        logger.warning(f"DLL deployment failed: {e}")


def post_link_dependency_deployment(output_path: Path, platform_name: str, use_gnu_abi: bool) -> None:
    """
    Deploy required runtime dependencies for a shared library.

    Unlike post_link_dll_deployment (automatic for .exe), this is opt-in via --deploy-dependencies.

    Supports:
    - Windows (.dll): MinGW runtime DLLs via llvm-objdump
    - Linux (.so): libc++, libunwind via ldd/readelf
    - macOS (.dylib): libc++, libunwind via otool

    Args:
        output_path: Path to the output shared library (.dll, .so, or .dylib)
        platform_name: Platform name from get_platform_info() (e.g., "win", "linux", "darwin")
        use_gnu_abi: Whether GNU ABI is being used (Windows only)

    Returns:
        None

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS: Set to "1" to disable all library deployment
        CLANG_TOOL_CHAIN_NO_AUTO: Set to "1" to disable all automatic features
        CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE: Set to "1" for verbose logging

    Examples:
        >>> post_link_dependency_deployment(Path("mylib.dll"), "win", True)
        # Deploys libwinpthread-1.dll, libstdc++-6.dll, etc. to mylib.dll directory
        >>> post_link_dependency_deployment(Path("mylib.so"), "linux", False)
        # Deploys libunwind.so.8, libc++.so.1, etc. to mylib.so directory
        >>> post_link_dependency_deployment(Path("mylib.dylib"), "darwin", False)
        # Deploys libunwind.1.dylib, libc++.1.dylib, etc. to mylib.dylib directory
    """
    # Check opt-out environment variables (NO_DEPLOY_LIBS or NO_AUTO)
    if is_feature_disabled("DEPLOY_LIBS"):
        return

    # Enable verbose logging if requested
    if os.environ.get("CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE") == "1":
        logger.setLevel(logging.DEBUG)

    # Check if output exists
    if not output_path.exists():
        logger.debug(f"Dependency deployment skipped: output not found: {output_path}")
        return

    suffix = output_path.suffix.lower()

    if platform_name == "win" and suffix in (".dll", ".exe"):
        _deploy_windows_dll_dependencies(output_path, use_gnu_abi)
    elif platform_name == "linux":
        # Deploy for shared libraries (.so, .so.1.2.3) and executables (no extension)
        # Skip object files (.o) and static libraries (.a)
        if suffix in (".o", ".a"):
            logger.debug(f"Dependency deployment skipped for object/static file: {suffix}")
        else:
            _deploy_linux_so_dependencies(output_path)
    elif platform_name == "darwin":
        # Deploy for dylibs and executables (no extension)
        # Skip object files (.o) and static libraries (.a)
        if suffix in (".o", ".a"):
            logger.debug(f"Dependency deployment skipped for object/static file: {suffix}")
        else:
            _deploy_macos_dylib_dependencies(output_path)
    else:
        logger.debug(f"Dependency deployment not supported for {suffix} on {platform_name}")


def _deploy_windows_dll_dependencies(dll_path: Path, use_gnu_abi: bool) -> None:
    """
    Deploy MinGW runtime DLLs for a Windows DLL.

    Uses llvm-objdump to detect DLL dependencies and copies MinGW runtime DLLs
    to the output directory.

    Args:
        dll_path: Path to the output DLL
        use_gnu_abi: Whether GNU ABI is being used

    Returns:
        None
    """
    if not use_gnu_abi:
        logger.debug("Dependency deployment skipped: not using GNU ABI")
        return

    try:
        from ..platform.detection import get_platform_info

        _, arch = get_platform_info()

        # Use deployer
        deployer = DllDeployer(arch)
        deployed_count = deployer.deploy_all(dll_path)

        if deployed_count == 0:
            logger.debug("No runtime dependencies deployed")

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.warning(f"Dependency deployment failed: {e}")


def _deploy_linux_so_dependencies(so_path: Path) -> None:
    """
    Deploy libc++/libunwind for a Linux shared library.

    Uses SoDeployer to detect shared library dependencies and copies them
    to the output directory.

    Args:
        so_path: Path to the output .so file

    Returns:
        None
    """
    try:
        from ..platform.detection import get_platform_info
        from .factory import create_deployer

        _, arch = get_platform_info()

        # Use factory to create Linux deployer
        deployer = create_deployer("linux", arch)
        if deployer is None:
            logger.warning("Linux deployer not available")
            return

        deployed_count = deployer.deploy_all(so_path)

        if deployed_count == 0:
            logger.debug("No shared libraries deployed")

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.warning(f"Linux shared library deployment failed: {e}")


def _deploy_macos_dylib_dependencies(dylib_path: Path) -> None:
    """
    Deploy libc++/libunwind for a macOS dylib.

    Uses DylibDeployer to detect dylib dependencies and copies them
    to the output directory.

    Args:
        dylib_path: Path to the output .dylib file

    Returns:
        None
    """
    try:
        from ..platform.detection import get_platform_info
        from .factory import create_deployer

        _, arch = get_platform_info()

        # Use factory to create macOS deployer
        deployer = create_deployer("darwin", arch)
        if deployer is None:
            logger.warning("macOS deployer not available")
            return

        deployed_count = deployer.deploy_all(dylib_path)

        if deployed_count == 0:
            logger.debug("No dylibs deployed")

    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.warning(f"macOS dylib deployment failed: {e}")
