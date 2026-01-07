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


def _is_deployable_dll(dll_name: str) -> bool:
    """
    Check if a DLL name matches MinGW runtime or sanitizer DLL patterns.

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
    dll_name_lower = dll_name.lower()

    # Exclude Windows system DLLs
    if dll_name_lower in WINDOWS_SYSTEM_DLLS:
        return False

    # Check against MinGW patterns
    if any(re.match(pattern, dll_name_lower) for pattern in MINGW_DLL_PATTERNS):
        return True

    # Check against sanitizer patterns
    return any(re.match(pattern, dll_name_lower) for pattern in SANITIZER_DLL_PATTERNS)


# Keep backward compatibility alias
def _is_mingw_dll(dll_name: str) -> bool:  # pyright: ignore[reportUnusedFunction]
    """Deprecated: Use _is_deployable_dll instead."""
    return _is_deployable_dll(dll_name)


def _extract_dll_dependencies(binary_path: Path, objdump_path: Path) -> list[str]:
    """
    Extract DLL dependencies from a binary file (EXE or DLL) using llvm-objdump.

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

        # Extract direct dependencies from the executable
        all_direct_deps = _extract_dll_dependencies(exe_path, objdump_path)
        total_dlls_found = len(all_direct_deps)

        detected_dlls = []
        for dll_name in all_direct_deps:
            if _is_deployable_dll(dll_name):
                detected_dlls.append(dll_name)
                logger.debug(f"Detected deployable DLL dependency: {dll_name}")

        # If llvm-objdump succeeded and detected deployable DLLs, recursively scan them
        if detected_dlls:
            logger.debug(f"Found {len(detected_dlls)} direct deployable DLL(s)")

            # Recursively scan detected DLLs for transitive dependencies
            all_required_dlls = set(detected_dlls)
            dlls_to_scan = detected_dlls.copy()
            scanned_dlls = set()

            while dlls_to_scan:
                current_dll = dlls_to_scan.pop(0)
                if current_dll in scanned_dlls:
                    continue
                scanned_dlls.add(current_dll)

                # Find the DLL in the toolchain
                dll_path = find_dll_in_toolchain(current_dll, platform_name, arch)
                if dll_path is None:
                    logger.debug(f"Cannot scan dependencies for {current_dll}: not found in toolchain")
                    continue

                # Extract dependencies from this DLL
                try:
                    transitive_deps = _extract_dll_dependencies(dll_path, objdump_path)
                    for dep_name in transitive_deps:
                        if _is_deployable_dll(dep_name) and dep_name not in all_required_dlls:
                            logger.debug(f"Found transitive dependency: {dep_name} (via {current_dll})")
                            all_required_dlls.add(dep_name)
                            dlls_to_scan.append(dep_name)
                except Exception as e:
                    logger.debug(f"Failed to scan dependencies for {current_dll}: {e}")

            logger.debug(f"Total deployable DLLs (including transitive): {len(all_required_dlls)}")
            return list(all_required_dlls)

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
    Atomically deploy a DLL using hard links (preferred) or file copy with atomic rename.

    This function ensures that concurrent compilations writing to the same directory
    don't corrupt DLL files. Uses the following algorithm:
    1. Check timestamp - skip if destination is up-to-date
    2. Try to create hard link (zero disk space, instant operation)
    3. If hard link fails, fall back to copy + atomic rename
    4. Handle race conditions gracefully

    Hard links are preferred because:
    - Zero additional disk space (same inode)
    - Instant operation (no data copy)
    - Automatic updates (if source DLL changes, all links reflect it)

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
    # Check if destination exists and compare timestamps
    if dest_dll.exists():
        src_stat = src_dll.stat()
        dest_stat = dest_dll.stat()

        # Skip if destination is up-to-date
        if src_stat.st_mtime <= dest_stat.st_mtime:
            logger.debug(f"Skipped (up-to-date): {dest_dll.name}")
            return False

        # Destination exists but is outdated - remove it before deployment
        try:
            dest_dll.unlink()
        except OSError as e:
            logger.debug(f"Could not remove outdated {dest_dll.name}: {e}")
            # Continue anyway - hard link/copy will fail if can't remove

    # Try hard link first (preferred - zero disk space, instant)
    try:
        os.link(src_dll, dest_dll)
        logger.debug(f"Deployed (hard link): {dest_dll.name}")
        return True
    except (OSError, NotImplementedError) as e:
        # Hard link failed - fall back to copy
        # Common reasons: cross-filesystem, permissions, filesystem doesn't support hard links
        logger.debug(f"Hard link failed for {dest_dll.name} ({e.__class__.__name__}), falling back to copy")

    # Fallback: Copy with atomic rename
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

            logger.debug(f"Deployed (copy): {dest_dll.name}")
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


def find_dll_in_toolchain(dll_name: str, platform_name: str, arch: str) -> Path | None:
    """
    Find a DLL in the toolchain (MinGW sysroot or sanitizer directories).

    Searches in multiple locations:
    1. MinGW sysroot/bin directory (for MinGW runtime DLLs)
    2. Clang bin directory (for sanitizer DLLs that may be copied there)
    3. MinGW sysroot/bin directory again (sanitizer DLLs are also stored here)

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
    from ..platform.detection import get_platform_binary_dir

    # Search locations in priority order
    search_dirs = []

    # 1. MinGW sysroot/bin directory
    try:
        sysroot_bin = get_mingw_sysroot_bin_dir(platform_name, arch)
        search_dirs.append(sysroot_bin)
    except (ValueError, RuntimeError) as e:
        logger.debug(f"Cannot access MinGW sysroot: {e}")

    # 2. Clang bin directory (for sanitizer DLLs that may be in bin/)
    try:
        clang_bin_dir = get_platform_binary_dir()
        search_dirs.append(clang_bin_dir)
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


def post_link_dll_deployment(output_exe_path: Path, platform_name: str, use_gnu_abi: bool) -> None:
    """
    Deploy required MinGW runtime and sanitizer DLLs to the executable directory after linking.

    This function:
    1. Detects required DLLs using llvm-objdump (with fallback)
    2. Locates source DLLs in MinGW sysroot/bin or clang/bin (for sanitizers)
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
        # Deploys libwinpthread-1.dll, libgcc_s_seh-1.dll, sanitizer DLLs, etc. to test.exe directory
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

        # Detect required DLLs (with recursive scanning)
        logger.debug(f"Detecting required DLLs for: {output_exe_path}")
        required_dlls = detect_required_dlls(output_exe_path, platform_name, arch)

        if not required_dlls:
            logger.debug("No deployable DLLs required")
            return

        # Destination directory (same as executable)
        dest_dir = output_exe_path.parent.resolve()

        # Deploy each required DLL
        deployed_count = 0
        skipped_count = 0

        for dll_name in required_dlls:
            # Find DLL in toolchain (MinGW sysroot or sanitizer directories)
            src_dll = find_dll_in_toolchain(dll_name, platform_name, arch)

            if src_dll is None:
                logger.warning(f"Source DLL not found in toolchain, skipping: {dll_name}")
                continue

            dest_dll = dest_dir / dll_name

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
            logger.info(f"Deployed {deployed_count} runtime DLL(s) for {output_exe_path.name}")
        elif skipped_count > 0:
            logger.debug(f"All {skipped_count} runtime DLL(s) up-to-date for {output_exe_path.name}")

    except Exception as e:
        # Non-fatal: log warning but don't fail the build
        logger.warning(f"DLL deployment failed: {e}")
