"""
File permissions and filesystem utilities module.

Handles file permission management and robust filesystem operations:
- Setting executable permissions on Unix/Linux
- Handling Windows readonly files
- Robust directory removal
- Filesystem synchronization
"""

import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


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
        import stat

        # Make the file writable and try again
        os.chmod(path_str, stat.S_IWRITE)
        func(path_str)

    # Try removing with readonly handler
    try:
        shutil.rmtree(path, onerror=handle_remove_readonly)
    except Exception as e:
        logger.warning(f"Failed to remove {path} on first attempt: {e}")
        # If that fails, try with ignore_errors as last resort
        if max_retries > 0:
            import time

            time.sleep(0.5)  # Wait briefly for file handles to close
            try:
                shutil.rmtree(path, ignore_errors=False, onerror=handle_remove_readonly)
            except Exception as e2:
                logger.warning(f"Failed to remove {path} on retry: {e2}")
                # Last resort: ignore all errors
                shutil.rmtree(path, ignore_errors=True)


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
    if bin_dir.exists() and bin_dir.is_dir():
        for binary_file in bin_dir.iterdir():
            if binary_file.is_file():
                # Set executable permissions for all binaries
                binary_file.chmod(0o755)

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

    # Force filesystem sync to ensure all permission changes are committed
    # This prevents "Text file busy" errors when another thread tries to execute
    # binaries immediately after this function returns
    if bin_dir and bin_dir.exists():
        # Sync the bin directory to ensure all changes are written
        fd = os.open(str(bin_dir), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
