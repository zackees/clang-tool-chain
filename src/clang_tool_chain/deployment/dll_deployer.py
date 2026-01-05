"""
DLL deployment functionality for Windows executables built with GNU ABI.

This module provides automatic deployment of MinGW runtime DLLs to executable
directories after successful linking, ensuring executables can run in cmd.exe
without PATH modifications.
"""

import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

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


def _is_mingw_dll(dll_name: str) -> bool:
    """
    Check if a DLL name matches MinGW runtime DLL patterns.

    Args:
        dll_name: DLL filename (e.g., "libwinpthread-1.dll")

    Returns:
        True if the DLL is a MinGW runtime DLL, False otherwise.

    Examples:
        >>> _is_mingw_dll("libwinpthread-1.dll")
        True
        >>> _is_mingw_dll("kernel32.dll")
        False
        >>> _is_mingw_dll("libgcc_s_seh-1.dll")
        True
    """
    dll_name_lower = dll_name.lower()

    # Exclude Windows system DLLs
    if dll_name_lower in WINDOWS_SYSTEM_DLLS:
        return False

    # Check against MinGW patterns
    return any(re.match(pattern, dll_name_lower) for pattern in MINGW_DLL_PATTERNS)


def detect_required_dlls(exe_path: Path) -> list[str]:
    """
    Detect required MinGW runtime DLLs for a Windows executable.

    Uses llvm-objdump to parse PE headers and extract DLL dependencies.
    Falls back to heuristic list if llvm-objdump fails.

    Args:
        exe_path: Path to the executable file (.exe)

    Returns:
        List of MinGW DLL filenames (e.g., ["libwinpthread-1.dll", "libgcc_s_seh-1.dll"])

    Raises:
        FileNotFoundError: If exe_path does not exist

    Examples:
        >>> detect_required_dlls(Path("test.exe"))
        ['libwinpthread-1.dll', 'libgcc_s_seh-1.dll', 'libstdc++-6.dll']
    """
    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {exe_path}")

    # Try to use llvm-objdump for precise DLL detection
    try:
        from ..platform.detection import get_platform_binary_dir

        # Get llvm-objdump from the toolchain
        clang_bin_dir = get_platform_binary_dir()
        objdump_path = clang_bin_dir / "llvm-objdump.exe"

        if not objdump_path.exists():
            logger.warning("llvm-objdump not found, using heuristic DLL list")
            return HEURISTIC_MINGW_DLLS.copy()

        # Run llvm-objdump -p to get PE headers
        logger.debug(f"Running llvm-objdump on: {exe_path}")
        result = subprocess.run(
            [str(objdump_path), "-p", str(exe_path)],
            capture_output=True,
            text=True,
            timeout=10,  # 10-second timeout
        )

        if result.returncode != 0:
            logger.warning(f"llvm-objdump failed (exit {result.returncode}), using heuristic DLL list")
            return HEURISTIC_MINGW_DLLS.copy()

        # Parse DLL dependencies from output
        # Pattern: "DLL Name: <dll_name>"
        dll_pattern = re.compile(r"DLL Name:\s+(\S+)", re.IGNORECASE)
        detected_dlls = []
        total_dlls_found = 0

        for match in dll_pattern.finditer(result.stdout):
            dll_name = match.group(1)
            total_dlls_found += 1
            if _is_mingw_dll(dll_name):
                detected_dlls.append(dll_name)
                logger.debug(f"Detected MinGW DLL dependency: {dll_name}")

        # If llvm-objdump succeeded and detected MinGW DLLs, use that result
        if detected_dlls:
            logger.debug(f"Found {len(detected_dlls)} MinGW DLL(s) via llvm-objdump")
            return detected_dlls

        # If llvm-objdump found DLL imports but no MinGW DLLs, still use heuristic fallback
        # This covers the case where the executable was compiled but objdump may have
        # missed MinGW DLLs in its output (parsing issues, etc.)
        if total_dlls_found > 0:
            logger.debug("llvm-objdump found DLL imports but no MinGW DLLs, using heuristic list")
            return HEURISTIC_MINGW_DLLS.copy()

        # No DLL imports found at all - likely means PE import table couldn't be parsed
        logger.debug("No DLL imports found by llvm-objdump, using heuristic list")
        return HEURISTIC_MINGW_DLLS.copy()

    except subprocess.TimeoutExpired:
        logger.warning("llvm-objdump timed out after 10 seconds, using heuristic DLL list")
        return HEURISTIC_MINGW_DLLS.copy()

    except Exception as e:
        logger.warning(f"DLL detection failed: {e}, using heuristic DLL list")
        return HEURISTIC_MINGW_DLLS.copy()


def _atomic_copy_dll(src_dll: Path, dest_dll: Path) -> bool:
    """
    Atomically copy a DLL using temp file + rename pattern to avoid race conditions.

    This function ensures that concurrent compilations writing to the same directory
    don't corrupt DLL files. Uses the following algorithm:
    1. Copy source to a temporary file (unique name)
    2. Attempt atomic rename to destination
    3. If rename fails due to existing file (race condition), clean up temp and return success
    4. If other errors occur, clean up temp and raise

    Args:
        src_dll: Source DLL path in MinGW sysroot
        dest_dll: Destination DLL path in executable directory

    Returns:
        True if DLL was copied/updated, False if skipped (already up-to-date)

    Raises:
        OSError: If copy or rename fails (other than race condition)

    Examples:
        >>> _atomic_copy_dll(Path("/src/libwinpthread-1.dll"), Path("/dest/libwinpthread-1.dll"))
        True  # DLL copied successfully
    """
    # Check if destination exists and compare timestamps
    if dest_dll.exists():
        src_stat = src_dll.stat()
        dest_stat = dest_dll.stat()

        # Skip if destination is up-to-date
        if src_stat.st_mtime <= dest_stat.st_mtime:
            logger.debug(f"Skipped (up-to-date): {dest_dll.name}")
            return False

    # Create temporary file in destination directory with unique name
    # Format: .{dll_name}.{uuid}.tmp
    temp_name = f".{dest_dll.name}.{uuid.uuid4().hex[:8]}.tmp"
    temp_dll = dest_dll.parent / temp_name

    try:
        # Copy source to temporary file
        shutil.copy2(src_dll, temp_dll)
        logger.debug(f"Copied to temp: {temp_name}")

        # Atomic rename (on Windows, this may fail if destination exists)
        try:
            # On POSIX, this is atomic and replaces existing files
            # On Windows, this fails if destination exists (need to handle)
            if os.name == "nt":
                # Windows: use os.replace() which is atomic if supported by filesystem
                # If destination exists, replace will succeed atomically (Python 3.3+)
                temp_dll.replace(dest_dll)
            else:
                # POSIX: rename is atomic and replaces existing files
                temp_dll.rename(dest_dll)

            logger.debug(f"Deployed (atomic): {dest_dll.name}")
            return True

        except FileExistsError:
            # Race condition: another process already created the file
            # This is OK - just clean up our temp file
            logger.debug(f"Skipped (race condition): {dest_dll.name} - another process deployed it")
            temp_dll.unlink(missing_ok=True)
            return False

        except OSError as e:
            # On Windows, replace() might fail if file is in use
            # Try to compare temp with destination - if identical, it's OK
            if dest_dll.exists():
                # Check if files are identical by size and mtime
                try:
                    temp_stat = temp_dll.stat()
                    dest_stat = dest_dll.stat()
                    if temp_stat.st_size == dest_stat.st_size:
                        # Files are same size, likely identical - clean up and succeed
                        logger.debug(
                            f"Skipped (file in use but same size): {dest_dll.name} - " f"assuming identical, error: {e}"
                        )
                        temp_dll.unlink(missing_ok=True)
                        return False
                except OSError:
                    pass  # Ignore stat errors, will re-raise original error below

            # Re-raise if we couldn't handle it
            raise

    except Exception:
        # Clean up temp file on any error
        temp_dll.unlink(missing_ok=True)
        raise


def get_mingw_sysroot_bin_dir(platform_name: str, arch: str) -> Path:
    """
    Get the MinGW sysroot bin directory containing runtime DLLs.

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
    from ..platform.detection import get_platform_binary_dir

    # Get clang bin directory (downloads toolchain if needed)
    clang_bin_dir = get_platform_binary_dir()
    clang_root = clang_bin_dir.parent

    # Determine sysroot name (from windows_gnu.py:106-113)
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


def post_link_dll_deployment(output_exe_path: Path, platform_name: str, use_gnu_abi: bool) -> None:
    """
    Deploy required MinGW runtime DLLs to the executable directory after linking.

    This function:
    1. Detects required DLLs using llvm-objdump (with fallback)
    2. Locates source DLLs in MinGW sysroot/bin
    3. Copies DLLs to executable directory (with timestamp checking)
    4. Handles all errors gracefully (warnings only, never fails the build)

    Args:
        output_exe_path: Path to the output executable
        platform_name: Platform name from get_platform_info() (e.g., "win")
        use_gnu_abi: Whether GNU ABI is being used

    Returns:
        None

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS: Set to "1" to disable deployment
        CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE: Set to "1" for verbose logging

    Examples:
        >>> post_link_dll_deployment(Path("test.exe"), "win", True)
        # Deploys libwinpthread-1.dll, libgcc_s_seh-1.dll, etc. to test.exe directory
    """
    # Check opt-out environment variable
    if os.environ.get("CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS") == "1":
        logger.debug("DLL deployment disabled via CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS")
        return

    # Enable verbose logging if requested
    if os.environ.get("CLANG_TOOL_CHAIN_DLL_DEPLOY_VERBOSE") == "1":
        logger.setLevel(logging.DEBUG)

    # Guard: only deploy on Windows
    if platform_name != "win":
        logger.debug(f"DLL deployment skipped: not Windows (platform={platform_name})")
        return

    # Guard: only deploy for GNU ABI
    if not use_gnu_abi:
        logger.debug("DLL deployment skipped: not using GNU ABI")
        return

    # Guard: only deploy for .exe files
    if output_exe_path.suffix.lower() != ".exe":
        logger.debug(f"DLL deployment skipped: not .exe file (suffix={output_exe_path.suffix})")
        return

    # Guard: check if executable exists
    if not output_exe_path.exists():
        logger.debug(f"DLL deployment skipped: executable not found: {output_exe_path}")
        return

    try:
        from ..platform.detection import get_platform_info

        # Get platform info for sysroot lookup
        _, arch = get_platform_info()

        # Detect required DLLs
        logger.debug(f"Detecting required DLLs for: {output_exe_path}")
        required_dlls = detect_required_dlls(output_exe_path)

        if not required_dlls:
            logger.debug("No MinGW DLLs required")
            return

        # Locate MinGW sysroot bin directory
        sysroot_bin = get_mingw_sysroot_bin_dir(platform_name, arch)
        logger.debug(f"MinGW sysroot bin directory: {sysroot_bin}")

        # Destination directory (same as executable)
        dest_dir = output_exe_path.parent.resolve()

        # Deploy each required DLL
        deployed_count = 0
        skipped_count = 0

        for dll_name in required_dlls:
            src_dll = sysroot_bin / dll_name
            dest_dll = dest_dir / dll_name

            # Check if source DLL exists
            if not src_dll.exists():
                logger.warning(f"Source DLL not found, skipping: {dll_name}")
                continue

            # Atomically copy DLL (handles race conditions)
            try:
                was_copied = _atomic_copy_dll(src_dll, dest_dll)
                if was_copied:
                    deployed_count += 1
                else:
                    skipped_count += 1
            except PermissionError:
                logger.warning(f"Permission denied copying {dll_name}, skipping")
                continue
            except OSError as e:
                logger.warning(f"Failed to copy {dll_name}: {e}, skipping")
                continue

        # Summary logging
        if deployed_count > 0:
            logger.info(f"Deployed {deployed_count} MinGW DLL(s) for {output_exe_path.name}")
        elif skipped_count > 0:
            logger.debug(f"All {skipped_count} MinGW DLL(s) up-to-date for {output_exe_path.name}")

    except Exception as e:
        # Non-fatal: log warning but don't fail the build
        logger.warning(f"DLL deployment failed: {e}")
