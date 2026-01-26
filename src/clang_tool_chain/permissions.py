"""
File permissions and filesystem utilities module.

Handles file permission management and robust filesystem operations:
- Setting executable permissions on Unix/Linux
- Handling Windows readonly files
- Robust directory removal
- Filesystem synchronization
"""

import os
import platform
import shutil
from pathlib import Path
from typing import Any

from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging

# Configure logging using centralized configuration
logger = configure_logging(__name__)


def _robust_rmtree(path: Path, max_retries: int = 3) -> None:  # pyright: ignore[reportUnusedFunction]
    """
    Remove a directory tree robustly, handling Windows file permission issues.

    On Windows, files can sometimes be locked or have permission issues that prevent
    immediate deletion. This function handles those cases by:
    1. Making files writable before deletion (Windows readonly flag)
    2. Retrying with a delay if deletion fails
    3. Using ignore_errors as a last resort

    Args:
        path: Path to the directory to remove
        max_retries: Maximum number of retry attempts (default: 3)
    """
    if not path.exists():
        return

    def handle_remove_readonly(func: Any, path_str: str, exc: Any) -> None:
        """Error handler to remove readonly flag and retry."""
        import contextlib
        import stat

        # Make the file writable and try again
        os.chmod(path_str, stat.S_IWRITE)
        # Handle os.open which requires (path, flags) signature
        if func is os.open:
            # For directory removal, we typically don't hit os.open, but be defensive
            with contextlib.suppress(Exception):
                func(path_str, os.O_RDONLY)
        else:
            func(path_str)

    # Try removing with readonly handler
    try:
        shutil.rmtree(path, onerror=handle_remove_readonly)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
    except Exception as e:
        logger.warning(f"Failed to remove {path} on first attempt: {e}")
        # If that fails, try with ignore_errors as last resort
        if max_retries > 0:
            import time

            time.sleep(0.1)  # Wait briefly for file handles to close (reduced from 0.5s for faster test execution)
            try:
                shutil.rmtree(path, ignore_errors=False, onerror=handle_remove_readonly)
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e2:
                logger.warning(f"Failed to remove {path} on retry: {e2}")
                # Last resort: ignore all errors
                shutil.rmtree(path, ignore_errors=True)

                # After ignore_errors, check if directory still exists with locked files
                # If so, fail fast rather than attempting extraction which will fail anyway
                if path.exists():
                    logger.error(f"Directory {path} still exists after removal attempts - likely has locked files")
                    raise RuntimeError(
                        f"Failed to remove directory {path}: files may be locked by another process. "
                        f"Please close any programs using files in this directory and try again."
                    ) from e2


def fix_file_permissions(install_dir: Path) -> None:
    """
    Fix file permissions after extraction to ensure binaries and shared libraries are executable.

    This function sets correct permissions on Unix/Linux systems:
    - Binaries in bin/ directories: 0o755 (rwxr-xr-x)
    - Shared libraries (.so, .dylib): 0o755 (rwxr-xr-x)
    - Headers, text files, static libs: 0o644 (rw-r--r--)

    On Windows, this is a no-op as permissions work differently.

    Args:
        install_dir: Installation directory to fix permissions in
    """
    logger.info(f"Fixing file permissions in {install_dir}")

    # Only fix permissions on Unix-like systems (Linux, macOS)
    if platform.system() == "Windows":
        logger.debug("Skipping permission fix on Windows")
        return

    # Fix permissions for files in bin/ directory
    bin_dir = install_dir / "bin"
    logger.info(f"DEBUG: Checking bin directory: {bin_dir}")
    logger.info(f"DEBUG: bin_dir exists: {bin_dir.exists()}")
    logger.info(f"DEBUG: bin_dir is_dir: {bin_dir.is_dir() if bin_dir.exists() else 'N/A'}")

    if bin_dir.exists() and bin_dir.is_dir():
        bin_files = list(bin_dir.iterdir())
        logger.info(f"DEBUG: Found {len(bin_files)} items in bin/")
        for binary_file in bin_files:
            if binary_file.is_file():
                # Get current permissions before change
                old_mode = binary_file.stat().st_mode
                # Set executable permissions for all binaries
                binary_file.chmod(0o755)
                new_mode = binary_file.stat().st_mode
                logger.info(
                    f"DEBUG: Set permissions on {binary_file.name}: "
                    f"{oct(old_mode)[-3:]} -> {oct(new_mode)[-3:]} "
                    f"(executable: {new_mode & 0o111 != 0})"
                )
    else:
        logger.warning(f"DEBUG: bin directory does not exist or is not a directory: {bin_dir}")

    # Fix permissions for files in emscripten/ directory
    # Emscripten tools (emcc, em++, emar, etc.) need executable permissions
    emscripten_dir = install_dir / "emscripten"
    if emscripten_dir.exists() and emscripten_dir.is_dir():
        # Set executable permissions on all files in the emscripten root
        # This includes emcc, em++, emar, emranlib, etc.
        for emscripten_file in emscripten_dir.iterdir():
            if emscripten_file.is_file():
                # Most files in emscripten/ are executables or scripts
                # Set executable permissions
                emscripten_file.chmod(0o755)

    # Fix permissions for files in lib/ directory
    lib_dir = install_dir / "lib"
    if lib_dir.exists() and lib_dir.is_dir():
        for file_path in lib_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Headers, text files, and static libraries should be readable but not executable
            if file_path.suffix in {".h", ".inc", ".modulemap", ".tcc", ".txt", ".a", ".syms"}:
                file_path.chmod(0o644)

            # Shared libraries need executable permissions
            elif (
                file_path.suffix in {".so", ".dylib"}
                or ".so." in file_path.name
                or "/bin/" in str(file_path)
                and file_path.suffix not in {".h", ".inc", ".txt", ".a", ".so", ".dylib"}
            ):
                file_path.chmod(0o755)

    # Fix permissions for files in libexec/ directory
    # This is important for GCC internal executables like cc1, cc1plus, ld, etc.
    # which are used by cosmocc and other GCC-based toolchains
    libexec_dir = install_dir / "libexec"
    if libexec_dir.exists() and libexec_dir.is_dir():
        logger.info(f"Fixing permissions in libexec/ directory: {libexec_dir}")
        for file_path in libexec_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Most files in libexec are executables (cc1, cc1plus, collect2, lto-wrapper, etc.)
            # Set executable permissions on all files in libexec
            old_mode = file_path.stat().st_mode
            file_path.chmod(0o755)
            new_mode = file_path.stat().st_mode
            logger.debug(f"Set permissions on {file_path.name}: {oct(old_mode)[-3:]} -> {oct(new_mode)[-3:]}")

    # Force filesystem sync to ensure all permission changes are committed
    # This prevents "Text file busy" errors when another thread tries to execute
    # binaries immediately after this function returns
    # Note: Directory fsync is only supported on Unix-like systems
    if bin_dir and bin_dir.exists() and platform.system() != "Windows":
        try:
            # Sync the bin directory to ensure all changes are written
            fd = os.open(str(bin_dir), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except (OSError, PermissionError) as e:
            # fsync on directories is not universally supported
            # Log but don't fail if it doesn't work
            logger.debug(f"Could not fsync directory {bin_dir}: {e}")
