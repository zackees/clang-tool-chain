"""
Installation coordination module.

Handles high-level installation logic for all toolchain components:
- Clang/LLVM toolchain installation
- IWYU installation
- Emscripten installation
- Node.js installation
- Installation verification
- Concurrent download prevention with file locking
"""

import contextlib
import datetime
import os
import shutil
import tempfile
from pathlib import Path

import fasteners

from .archive import download_archive, extract_tarball
from .logging_config import configure_logging
from .manifest import (
    Manifest,
    fetch_emscripten_platform_manifest,
    fetch_iwyu_platform_manifest,
    fetch_lldb_platform_manifest,
    fetch_nodejs_platform_manifest,
    fetch_platform_manifest,
)
from .path_utils import (
    get_emscripten_install_dir,
    get_emscripten_lock_path,
    get_install_dir,
    get_iwyu_install_dir,
    get_iwyu_lock_path,
    get_lldb_install_dir,
    get_lldb_lock_path,
    get_lock_path,
    get_nodejs_install_dir,
    get_nodejs_lock_path,
)
from .permissions import _robust_rmtree, fix_file_permissions

# Configure logging using centralized configuration
logger = configure_logging(__name__)


# ============================================================================
# Helper Functions
# ============================================================================


def _verify_file_readable(file_path: Path, description: str, timeout_seconds: float = 2.0) -> bool:
    """
    Verify that a file exists and is readable, with retry logic for filesystem sync delays.

    This is critical on Windows and macOS where filesystem operations may not be immediately
    visible to other processes due to caching, buffering, or APFS sync delays.

    Args:
        file_path: Path to the file to verify
        description: Human-readable description for logging
        timeout_seconds: Maximum time to wait for file to become readable

    Returns:
        True if file is readable within timeout, False otherwise
    """
    import time

    if not file_path.exists():
        logger.warning(f"{description} not visible yet at {file_path}, waiting for filesystem sync...")
        max_attempts = int(timeout_seconds / 0.01)
        for attempt in range(max_attempts):
            if file_path.exists():
                elapsed = attempt * 0.01
                if elapsed > 0.1:  # Log if it took more than 100ms
                    logger.warning(f"{description} became visible after {elapsed:.2f}s (filesystem sync delay)")
                else:
                    logger.info(f"{description} verified after {elapsed:.3f}s")
                break
            time.sleep(0.01)
        else:
            return False

    # File exists, now verify it's readable
    # Use binary mode to handle both text and binary files
    try:
        with open(file_path, "rb") as f:
            f.read(1)  # Read just one byte to verify readability
        logger.debug(f"{description} verified as readable: {file_path}")
    except (OSError, PermissionError) as e:
        logger.warning(f"{description} exists but not readable yet: {e}. Retrying...")
        max_attempts = int(timeout_seconds / 0.01)
        for attempt in range(max_attempts):
            try:
                with open(file_path, "rb") as f:
                    f.read(1)
                elapsed = attempt * 0.01
                logger.info(f"{description} became readable after {elapsed:.3f}s")
                break
            except (OSError, PermissionError):
                time.sleep(0.01)
        else:
            logger.error(f"{description} still not readable after {timeout_seconds}s")
            return False

    return True


# ============================================================================
# Clang/LLVM Installation
# ============================================================================


def is_toolchain_installed(platform: str, arch: str) -> bool:
    """
    Check if the toolchain is already installed for the given platform/arch.

    This checks for the presence of a done.txt file which is created after
    successful download and extraction, and verifies that the installed
    version matches the current manifest SHA256 hash.

    If the SHA256 hash in the manifest has changed (e.g., archive was rebuilt),
    this will return False to trigger a re-download.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    install_dir = get_install_dir(platform, arch)
    done_file = install_dir / "done.txt"

    if not done_file.exists():
        return False

    # Read the done.txt file to get the installed SHA256
    try:
        done_content = done_file.read_text()
        installed_sha256 = None
        for line in done_content.splitlines():
            if line.startswith("SHA256:"):
                installed_sha256 = line.split(":", 1)[1].strip()
                break

        if not installed_sha256:
            logger.warning(f"No SHA256 found in {done_file}, will re-download to verify integrity")
            return False

        # Fetch current manifest to compare SHA256
        platform_manifest = fetch_platform_manifest(platform, arch)
        latest_version = platform_manifest.latest
        if not latest_version:
            logger.error("Manifest does not specify a 'latest' version")
            return False

        version_info = platform_manifest.versions.get(latest_version)
        if not version_info:
            logger.error(f"Version {latest_version} not found in manifest")
            return False

        current_sha256 = version_info.sha256

        if installed_sha256.lower() != current_sha256.lower():
            logger.info(
                f"SHA256 mismatch detected for {platform}/{arch}:\n"
                f"  Installed: {installed_sha256}\n"
                f"  Current:   {current_sha256}\n"
                f"Archive was rebuilt or updated - will re-download"
            )
            return False

        logger.debug(f"SHA256 matches for {platform}/{arch}, toolchain is up to date")
        return True

    except Exception as e:
        logger.warning(f"Error checking toolchain installation status: {e}, will re-download")
        return False


def download_and_install_toolchain(platform: str, arch: str, verbose: bool = False) -> None:
    """
    Download and install the toolchain for the given platform/arch.

    This function:
    1. Fetches the root manifest
    2. Fetches the platform-specific manifest
    3. Downloads the latest toolchain archive
    4. Verifies the checksum
    5. Extracts to ~/.clang-tool-chain/clang/<platform>/<arch>

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
        verbose: If True, print progress messages

    Raises:
        RuntimeError: If download or installation fails
    """
    import sys

    if verbose:
        print(f"Downloading clang-tool-chain for {platform}/{arch}...")

    # Fetch platform manifest
    platform_manifest = fetch_platform_manifest(platform, arch)

    # Get latest version info
    latest_version = platform_manifest.latest
    if not latest_version:
        raise RuntimeError("Manifest does not specify a 'latest' version")

    version_info = platform_manifest.versions.get(latest_version)
    if not version_info:
        raise RuntimeError(f"Version {latest_version} not found in manifest")

    if verbose:
        print(f"Latest version: {latest_version}")
        print(f"Download URL: {version_info.href}")

    # Download archive to a temporary file
    # Use tempfile to avoid conflicts with test cleanup that removes temp directories
    # Create temporary file for download
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".tar.zst", delete=False) as tmp:
        archive_path = Path(tmp.name)

    try:
        # Get file size information and print to stderr before download
        # This helps users understand that downloading is in progress and not stalled
        from .parallel_download import check_server_capabilities

        print("Downloading Clang/LLVM toolchain for first-time installation...", file=sys.stderr, flush=True)
        capabilities = check_server_capabilities(version_info.href, timeout=10)
        if capabilities.content_length:
            size_mb = capabilities.content_length / (1024 * 1024)
            print(f"Download size: {size_mb:.1f} MB", file=sys.stderr, flush=True)
        else:
            print("Download size: (size unknown, checking...)", file=sys.stderr, flush=True)

        if verbose:
            print(f"Downloading to {archive_path}...")

        download_archive(version_info, archive_path)

        print("Download complete. Extracting toolchain...", file=sys.stderr, flush=True)

        if verbose:
            print("Download complete. Verifying checksum...")

        # Extract to installation directory
        install_dir = get_install_dir(platform, arch)

        if verbose:
            print(f"Extracting to {install_dir}...")

        # Remove old installation if it exists (BEFORE extraction)
        if install_dir.exists():
            _robust_rmtree(install_dir)

        # Ensure parent directory exists
        install_dir.parent.mkdir(parents=True, exist_ok=True)

        extract_tarball(archive_path, install_dir)

        # Fix file permissions (set executable bits on binaries and shared libraries)
        if verbose:
            print("Fixing file permissions...")

        fix_file_permissions(install_dir)

        # On Linux, copy clang++ to clang for convenience
        if platform == "linux":
            bin_dir = install_dir / "bin"
            clang_cpp = bin_dir / "clang++"
            clang = bin_dir / "clang"
            if clang_cpp.exists() and not clang.exists():
                if verbose:
                    print("Copying clang++ to clang on Linux...")
                shutil.copy2(clang_cpp, clang)

        # Force filesystem sync to ensure all extracted files are fully written to disk
        # This prevents "Text file busy" errors when another thread/process tries to
        # execute the binaries immediately after we release the lock and see done.txt
        import platform as plat

        if plat.system() != "Windows":
            # On Unix systems, use fsync() on the bin directory for synchronous flush
            # This is especially critical on macOS APFS where os.sync() is non-blocking
            # and extracted binaries may not be visible immediately after lock release
            bin_dir = install_dir / "bin"
            fsync_success = False

            try:
                # Try fsync on the bin directory (blocking until flushed to disk)
                bin_dir_fd = os.open(str(bin_dir), os.O_RDONLY)
                try:
                    os.fsync(bin_dir_fd)
                    fsync_success = True
                    logger.info("Binaries synced to disk via fsync() on bin directory")
                finally:
                    os.close(bin_dir_fd)
            except Exception as e:
                # fsync on directories may not work on all filesystems
                logger.warning(f"fsync() on bin directory failed: {e}, falling back to os.sync()")

            # Fallback to os.sync() if fsync failed (best effort)
            if not fsync_success and hasattr(os, "sync"):
                with contextlib.suppress(Exception):
                    os.sync()  # type: ignore[attr-defined]
                    logger.info("Fallback: called os.sync() for filesystem flush")

        # Verify MinGW sysroot exists on Windows (integrated in Clang archive since v2.0.0)
        # This ensures concurrent compiler processes won't fail when checking for MinGW headers
        if platform == "win":
            logger.info("Verifying MinGW sysroot integrity for Windows GNU ABI support")
            sysroot_name = "x86_64-w64-mingw32" if arch == "x86_64" else "aarch64-w64-mingw32"
            sysroot_path = install_dir / sysroot_name

            if not sysroot_path.exists():
                logger.error(f"MinGW sysroot not found after extraction: {sysroot_path}")
                raise RuntimeError(
                    f"MinGW sysroot verification failed: {sysroot_path} does not exist\n"
                    f"The integrated MinGW headers were not properly extracted from the archive.\n"
                    f"This indicates a corrupted download or extraction issue.\n"
                    f"Installation directory: {install_dir}\n"
                    f"Please try again or report at https://github.com/zackees/clang-tool-chain/issues"
                )

            # Verify essential sysroot components
            sysroot_lib = sysroot_path / "lib"
            if not sysroot_lib.exists():
                logger.error(f"MinGW sysroot lib directory missing: {sysroot_lib}")
                raise RuntimeError(
                    f"MinGW sysroot lib directory not found: {sysroot_lib}\n"
                    f"The sysroot structure is incomplete.\n"
                    f"Installation directory: {install_dir}"
                )

            logger.info(f"MinGW sysroot verified at: {sysroot_path}")

            # Also verify MinGW include directory (headers are at install_dir/include/)
            mingw_include = install_dir / "include"
            if not mingw_include.exists():
                logger.error(f"MinGW include directory missing: {mingw_include}")
                raise RuntimeError(
                    f"MinGW include directory not found: {mingw_include}\n"
                    f"The integrated MinGW headers are incomplete.\n"
                    f"Installation directory: {install_dir}"
                )

            logger.info(f"MinGW headers verified at: {mingw_include}")

        # Write done.txt to mark successful installation
        # Ensure install_dir exists before writing done.txt
        install_dir.mkdir(parents=True, exist_ok=True)
        done_file = install_dir / "done.txt"
        done_file.write_text(
            f"Installation completed successfully\n" f"Version: {latest_version}\n" f"SHA256: {version_info.sha256}\n"
        )

        print("Clang/LLVM toolchain installation complete!", file=sys.stderr, flush=True)

    finally:
        # Clean up downloaded archive
        if archive_path.exists():
            archive_path.unlink()

    if verbose:
        print("Installation complete!")


def _subprocess_install_toolchain(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """
    Install toolchain in a subprocess with proper process-level locking.

    This function is called as a subprocess to ensure fasteners.InterProcessLock
    works correctly. InterProcessLock only synchronizes across processes, not threads,
    so we must use subprocess to get proper locking behavior.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Exit code (0 for success, non-zero for failure)
    """

    try:
        logger.info(f"[Subprocess] Installing toolchain for {platform}/{arch}")
        lock_path = get_lock_path(platform, arch)
        logger.debug(f"[Subprocess] Lock path: {lock_path}")
        lock = fasteners.InterProcessLock(str(lock_path))

        logger.info("[Subprocess] Waiting to acquire installation lock...")
        with lock:
            logger.info("[Subprocess] Lock acquired")

            # Check again inside lock in case another process just finished installing
            if is_toolchain_installed(platform, arch):
                logger.info("[Subprocess] Another process installed the toolchain while we waited")
                return 0

            # Download and install
            logger.info("[Subprocess] Starting toolchain download and installation")
            download_and_install_toolchain(platform, arch)
            logger.info(f"[Subprocess] Toolchain installation complete for {platform}/{arch}")
            return 0

    except Exception as e:
        logger.error(f"[Subprocess] Failed to install toolchain: {e}", exc_info=True)
        return 1


def ensure_toolchain(platform: str, arch: str) -> None:
    """
    Ensure the toolchain is installed for the given platform/arch.

    This function uses subprocess-based installation with file locking to prevent
    concurrent downloads. The subprocess approach ensures that fasteners.InterProcessLock
    works correctly, as it only synchronizes across processes (not threads).

    Double-checked locking pattern:
    1. Quick check without lock - if already installed, return immediately
    2. If not installed, spawn subprocess to acquire lock and install
    3. Subprocess uses InterProcessLock for proper inter-process synchronization
    4. After subprocess completes, verify installation succeeded

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Raises:
        RuntimeError: If installation fails or binary verification fails
    """
    import subprocess
    import sys
    import time

    logger.info(f"Ensuring toolchain is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately
    if is_toolchain_installed(platform, arch):
        logger.info(f"Toolchain already installed for {platform}/{arch}")
        return

    # Need to download - spawn subprocess to handle locking and installation
    logger.info(f"Toolchain not installed, spawning subprocess to install for {platform}/{arch}")

    # Call this module's _subprocess_install_toolchain function in a subprocess
    # This ensures InterProcessLock works correctly (it only works across processes, not threads)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from clang_tool_chain.installer import _subprocess_install_toolchain; "
            f"import sys; "
            f"sys.exit(_subprocess_install_toolchain('{platform}', '{arch}'))",
        ],
        capture_output=False,  # Let subprocess write to stderr for user feedback
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to install toolchain for {platform}/{arch} (subprocess exited with code {result.returncode})"
        )

    # Verify installation succeeded
    # CRITICAL: Wait for filesystem sync (especially on macOS APFS)
    # The subprocess may have written done.txt but binaries aren't visible yet
    install_dir = get_install_dir(platform, arch)
    bin_dir = install_dir / "bin"
    clang_binary = bin_dir / "clang.exe" if platform == "win" else bin_dir / "clang"

    logger.info("Verifying toolchain installation after subprocess completion...")
    if not clang_binary.exists():
        logger.warning("Clang binary not visible yet after subprocess, waiting for filesystem sync...")

        for attempt in range(200):  # 200 * 0.01s = 2 seconds max
            if clang_binary.exists():
                elapsed = attempt * 0.01
                if elapsed > 0.1:  # Log if it took more than 100ms
                    logger.warning(f"Clang binary became visible after {elapsed:.2f}s (filesystem sync delay)")
                else:
                    logger.info(f"Clang binary verified after {elapsed:.3f}s")
                break
            time.sleep(0.01)
        else:
            # Binary still not visible after 2 seconds
            raise RuntimeError(
                f"Clang binary not found after subprocess installation: {clang_binary}\n"
                f"Expected location: {clang_binary}\n"
                f"This may indicate a filesystem sync issue or corrupted installation."
            )
    else:
        logger.info("Clang binary verified immediately (no sync delay)")

    logger.info(f"Toolchain installation verified for {platform}/{arch}")


# ============================================================================
# IWYU Installation
# ============================================================================


def is_iwyu_installed(platform: str, arch: str) -> bool:
    """
    Check if IWYU is already installed and hash matches current manifest.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    install_dir = get_iwyu_install_dir(platform, arch)
    done_file = install_dir / "done.txt"

    if not done_file.exists():
        return False

    try:
        done_content = done_file.read_text()
        installed_sha256 = None
        for line in done_content.splitlines():
            if line.startswith("SHA256:"):
                installed_sha256 = line.split(":", 1)[1].strip()
                break

        if not installed_sha256:
            logger.warning(f"No SHA256 found in IWYU {done_file}, will re-download")
            return False

        # Fetch current manifest
        platform_manifest = fetch_iwyu_platform_manifest(platform, arch)
        latest_version = platform_manifest.latest
        if not latest_version:
            return False

        version_info = platform_manifest.versions.get(latest_version)
        if not version_info:
            return False

        current_sha256 = version_info.sha256

        if installed_sha256.lower() != current_sha256.lower():
            logger.info("IWYU SHA256 mismatch - will re-download")
            return False

        return True

    except Exception as e:
        logger.warning(f"Error checking IWYU installation: {e}, will re-download")
        return False


def download_and_install_iwyu(platform: str, arch: str) -> None:
    """
    Download and install IWYU for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Downloading and installing IWYU for {platform}/{arch}")

    # Fetch the manifest to get download URL and checksum
    manifest = fetch_iwyu_platform_manifest(platform, arch)
    version_info = manifest.versions[manifest.latest]

    logger.info(f"IWYU version: {manifest.latest}")
    logger.info(f"Download URL: {version_info.href}")

    # Create temporary download directory
    install_dir = get_iwyu_install_dir(platform, arch)
    logger.info(f"Installation directory: {install_dir}")

    # Remove old installation if exists
    if install_dir.exists():
        logger.info("Removing old IWYU installation")
        _robust_rmtree(install_dir)

    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        archive_file = temp_path / "iwyu.tar.zst"

        # Download the archive (handles both single-file and multi-part)
        download_archive(version_info, archive_file)

        # Extract to installation directory
        logger.info("Extracting IWYU archive")
        extract_tarball(archive_file, install_dir)

        # DEBUG: Log directory structure after extraction
        logger.info(f"DEBUG: Checking installation directory: {install_dir}")
        logger.info(f"DEBUG: install_dir exists: {install_dir.exists()}")
        logger.info(f"DEBUG: install_dir is_dir: {install_dir.is_dir()}")

        if install_dir.exists():
            try:
                items = list(install_dir.iterdir())
                logger.info(f"DEBUG: Found {len(items)} items in {install_dir}")
                for item in items:
                    logger.info(f"DEBUG:   - {item.name} ({'dir' if item.is_dir() else 'file'})")
                    if item.is_dir() and item.name == "bin":
                        bin_items = list(item.iterdir())
                        logger.info(f"DEBUG:     bin/ contains {len(bin_items)} items:")
                        for bin_item in bin_items[:10]:  # First 10 items
                            logger.info(f"DEBUG:       - {bin_item.name} ({bin_item.stat().st_size} bytes)")
            except Exception as e:
                logger.error(f"DEBUG: Error listing directory contents: {e}")
        else:
            # Check parent directory
            parent = install_dir.parent
            logger.info(f"DEBUG: install_dir doesn't exist, checking parent: {parent}")
            if parent.exists():
                parent_items = list(parent.iterdir())
                logger.info(f"DEBUG: Parent contains {len(parent_items)} items:")
                for item in parent_items[:20]:  # First 20 items
                    logger.info(f"DEBUG:   - {item.name} ({'dir' if item.is_dir() else 'file'})")

        # Fix permissions on Unix systems
        if os.name != "nt":
            logger.info("Setting executable permissions on IWYU binaries")
            fix_file_permissions(install_dir)

        # Verify the IWYU binary actually exists before marking as complete
        iwyu_binary_name = "include-what-you-use.exe" if platform == "win" else "include-what-you-use"
        iwyu_binary = install_dir / "bin" / iwyu_binary_name
        logger.info(f"DEBUG: Looking for IWYU binary at: {iwyu_binary}")
        logger.info(f"DEBUG: Binary exists: {iwyu_binary.exists()}")

        if not iwyu_binary.exists():
            # Additional debugging before failing
            bin_dir = install_dir / "bin"
            logger.error(f"DEBUG: bin_dir ({bin_dir}) exists: {bin_dir.exists()}")
            if bin_dir.exists():
                bin_contents = list(bin_dir.iterdir())
                logger.error(f"DEBUG: bin_dir contains {len(bin_contents)} items:")
                for item in bin_contents:
                    logger.error(f"DEBUG:   - {item.name}")

            raise RuntimeError(
                f"IWYU installation verification failed: binary not found at {iwyu_binary}. "
                f"Extraction may have failed or archive structure is incorrect."
            )
        logger.info(f"IWYU binary verified at: {iwyu_binary}")

        # Mark installation as complete
        # Ensure install_dir exists before writing done.txt
        install_dir.mkdir(parents=True, exist_ok=True)
        done_file = install_dir / "done.txt"
        with open(done_file, "w") as f:
            f.write(f"IWYU {manifest.latest} installed successfully\n" f"SHA256: {version_info.sha256}\n")

        logger.info(f"IWYU installation complete for {platform}/{arch}")


def _subprocess_install_iwyu(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """
    Install IWYU in a subprocess with proper process-level locking.

    Args:
        platform: Platform name
        arch: Architecture name

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        logger.info(f"[Subprocess] Installing IWYU for {platform}/{arch}")
        lock_path = get_iwyu_lock_path(platform, arch)
        lock = fasteners.InterProcessLock(str(lock_path))

        with lock:
            logger.info("[Subprocess] IWYU lock acquired")
            if is_iwyu_installed(platform, arch):
                logger.info("[Subprocess] Another process installed IWYU while we waited")
                return 0

            download_and_install_iwyu(platform, arch)
            logger.info(f"[Subprocess] IWYU installation complete for {platform}/{arch}")
            return 0

    except Exception as e:
        logger.error(f"[Subprocess] Failed to install IWYU: {e}", exc_info=True)
        return 1


def ensure_iwyu(platform: str, arch: str) -> None:
    """
    Ensure IWYU is installed for the given platform/arch.

    Uses subprocess-based installation with file locking to prevent concurrent downloads.
    InterProcessLock only works across processes, not threads, so we use subprocess.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    import subprocess
    import sys

    logger.info(f"Ensuring IWYU is installed for {platform}/{arch}")

    # Quick check without lock
    if is_iwyu_installed(platform, arch):
        logger.info(f"IWYU already installed for {platform}/{arch}")
        return

    # Spawn subprocess for installation
    logger.info(f"IWYU not installed, spawning subprocess to install for {platform}/{arch}")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from clang_tool_chain.installer import _subprocess_install_iwyu; "
            f"import sys; "
            f"sys.exit(_subprocess_install_iwyu('{platform}', '{arch}'))",
        ],
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to install IWYU for {platform}/{arch} (subprocess exited with code {result.returncode})"
        )

    logger.info(f"IWYU installation verified for {platform}/{arch}")


# ============================================================================
# LLDB Installation
# ============================================================================


def is_lldb_installed(platform: str, arch: str) -> bool:
    """
    Check if LLDB is already installed and hash matches current manifest.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    install_dir = get_lldb_install_dir(platform, arch)
    done_file = install_dir / "done.txt"

    if not done_file.exists():
        return False

    try:
        done_content = done_file.read_text()
        installed_sha256 = None
        for line in done_content.splitlines():
            if line.startswith("SHA256:"):
                installed_sha256 = line.split(":", 1)[1].strip()
                break

        if not installed_sha256:
            logger.warning(f"No SHA256 found in LLDB {done_file}, will re-download")
            return False

        # Fetch current manifest
        platform_manifest = fetch_lldb_platform_manifest(platform, arch)
        latest_version = platform_manifest.latest
        if not latest_version:
            return False

        version_info = platform_manifest.versions.get(latest_version)
        if not version_info:
            return False

        current_sha256 = version_info.sha256

        if installed_sha256.lower() != current_sha256.lower():
            logger.info("LLDB SHA256 mismatch - will re-download")
            return False

        return True

    except Exception as e:
        logger.warning(f"Error checking LLDB installation: {e}, will re-download")
        return False


def download_and_install_lldb(platform: str, arch: str) -> None:
    """
    Download and install LLDB for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Downloading and installing LLDB for {platform}/{arch}")

    # Fetch the manifest to get download URL and checksum
    manifest = fetch_lldb_platform_manifest(platform, arch)
    version_info = manifest.versions[manifest.latest]

    logger.info(f"LLDB version: {manifest.latest}")
    logger.info(f"Download URL: {version_info.href}")

    # Create temporary download directory
    install_dir = get_lldb_install_dir(platform, arch)
    logger.info(f"Installation directory: {install_dir}")

    # Remove old installation if exists
    if install_dir.exists():
        logger.info("Removing old LLDB installation")
        _robust_rmtree(install_dir)

    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        archive_file = temp_path / "lldb.tar.zst"

        # Download the archive (handles both single-file and multi-part)
        download_archive(version_info, archive_file)

        # Extract to installation directory
        logger.info("Extracting LLDB archive")
        extract_tarball(archive_file, install_dir)

        # Fix permissions on Unix systems
        if os.name != "nt":
            logger.info("Setting executable permissions on LLDB binaries")
            fix_file_permissions(install_dir)

        # Verify the LLDB binary actually exists before marking as complete
        lldb_binary_name = "lldb.exe" if platform == "win" else "lldb"
        lldb_binary = install_dir / "bin" / lldb_binary_name
        logger.info(f"Looking for LLDB binary at: {lldb_binary}")

        if not lldb_binary.exists():
            # Additional debugging before failing
            bin_dir = install_dir / "bin"
            logger.error(f"bin_dir ({bin_dir}) exists: {bin_dir.exists()}")
            if bin_dir.exists():
                bin_contents = list(bin_dir.iterdir())
                logger.error(f"bin_dir contains {len(bin_contents)} items:")
                for item in bin_contents:
                    logger.error(f"  - {item.name}")

            raise RuntimeError(
                f"LLDB installation verification failed: binary not found at {lldb_binary}. "
                f"Extraction may have failed or archive structure is incorrect."
            )
        logger.info(f"LLDB binary verified at: {lldb_binary}")

        # Mark installation as complete
        # Ensure install_dir exists before writing done.txt
        install_dir.mkdir(parents=True, exist_ok=True)
        done_file = install_dir / "done.txt"
        with open(done_file, "w") as f:
            f.write(f"LLDB {manifest.latest} installed successfully\n" f"SHA256: {version_info.sha256}\n")

        logger.info(f"LLDB installation complete for {platform}/{arch}")


def _subprocess_install_lldb(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """
    Install LLDB in a subprocess with proper process-level locking.

    Args:
        platform: Platform name
        arch: Architecture name

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        logger.info(f"[Subprocess] Installing LLDB for {platform}/{arch}")
        lock_path = get_lldb_lock_path(platform, arch)
        lock = fasteners.InterProcessLock(str(lock_path))

        with lock:
            logger.info("[Subprocess] LLDB lock acquired")
            if is_lldb_installed(platform, arch):
                logger.info("[Subprocess] Another process installed LLDB while we waited")
                return 0

            download_and_install_lldb(platform, arch)
            logger.info(f"[Subprocess] LLDB installation complete for {platform}/{arch}")
            return 0

    except Exception as e:
        logger.error(f"[Subprocess] Failed to install LLDB: {e}", exc_info=True)
        return 1


def ensure_lldb(platform: str, arch: str) -> None:
    """
    Ensure LLDB is installed for the given platform/arch.

    Uses subprocess-based installation with file locking to prevent concurrent downloads.
    InterProcessLock only works across processes, not threads, so we use subprocess.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    import subprocess
    import sys

    logger.info(f"Ensuring LLDB is installed for {platform}/{arch}")

    # Quick check without lock
    if is_lldb_installed(platform, arch):
        logger.info(f"LLDB already installed for {platform}/{arch}")
        return

    # Spawn subprocess for installation
    logger.info(f"LLDB not installed, spawning subprocess to install for {platform}/{arch}")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"from clang_tool_chain.installer import _subprocess_install_lldb; "
            f"import sys; "
            f"sys.exit(_subprocess_install_lldb('{platform}', '{arch}'))",
        ],
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to install LLDB for {platform}/{arch} (subprocess exited with code {result.returncode})"
        )

    logger.info(f"LLDB installation verified for {platform}/{arch}")


# ============================================================================
# Emscripten Installation
# ============================================================================


def create_emscripten_config(install_dir: Path, platform: str, arch: str) -> None:
    """
    Create .emscripten config file if it doesn't exist.

    The config file contains paths to LLVM, Binaryen, and Node.js tools
    that Emscripten needs to compile WebAssembly code.

    IMPORTANT: Emscripten distributions include their own LLVM binaries
    (e.g., LLVM 22 for Emscripten 4.0.19). This function configures paths
    to use Emscripten's bundled LLVM, NOT clang-tool-chain's LLVM.
    This ensures version compatibility between Emscripten and LLVM.

    Args:
        install_dir: Emscripten installation directory
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    config_path = install_dir / ".emscripten"

    # Verify the Emscripten bin directory exists and contains bundled LLVM binaries
    # NOTE: Emscripten distributions include LLVM binaries. We do NOT link or override
    # them with clang-tool-chain's LLVM to avoid version mismatches.
    # The binaries should be present after archive extraction.
    emscripten_bin = install_dir / "bin"
    exe_ext = ".exe" if platform == "win" else ""
    clang_binary = emscripten_bin / f"clang{exe_ext}"

    # CRITICAL: On Windows, wait for filesystem sync before checking if binary exists
    # This prevents race conditions where link_clang_binaries_to_emscripten() completes
    # but the binaries aren't yet visible to other processes
    if not clang_binary.exists():
        logger.warning(f"Clang binary not visible yet, waiting for filesystem sync: {clang_binary}")
        import time

        for attempt in range(200):  # 200 * 0.01s = 2 seconds max
            if clang_binary.exists():
                elapsed = attempt * 0.01
                if elapsed > 0.1:
                    logger.warning(f"Clang binary became visible after {elapsed:.2f}s (filesystem sync delay)")
                break
            time.sleep(0.01)

    if not clang_binary.exists():
        # This indicates archive extraction failed or produced incomplete installation
        logger.error(
            f"Cannot create .emscripten config: clang binary not found at {clang_binary}\n"
            f"Emscripten archive extraction may have failed or produced incomplete installation.\n"
            f"Expected Emscripten's bundled LLVM binary: {clang_binary}\n"
            f"Emscripten bin directory: {emscripten_bin}"
        )
        raise RuntimeError(
            f"Cannot create .emscripten config: clang binary not found at {clang_binary}\n"
            f"Emscripten archive extraction may have failed.\n"
            f"Expected Emscripten's bundled LLVM binary at: {clang_binary}\n"
            f"Try removing {install_dir} and reinstalling.\n"
            f"Please report persistent issues at https://github.com/zackees/clang-tool-chain/issues"
        )

    # Set up paths relative to install_dir
    # IMPORTANT: Use forward slashes in the config file even on Windows!
    # The config is a Python file and backslashes would be interpreted as escape sequences.
    # Python and Emscripten handle forward slashes correctly on all platforms.
    llvm_root = str(install_dir / "bin").replace("\\", "/")
    # BINARYEN_ROOT should point to parent of bin/ directory
    # Emscripten will append "/bin" to find tools like wasm-opt
    binaryen_root = str(install_dir).replace("\\", "/")

    # Node.js path - use 'node' from PATH (will be added by wrapper)
    node_js = "node.exe" if platform == "win" else "node"

    # Create config content based on the template
    config_content = f"""# Emscripten configuration file
# Auto-generated by clang-tool-chain installer

import os

# LLVM tools directory (clang, wasm-ld, etc.)
LLVM_ROOT = '{llvm_root}'

# Binaryen tools directory (wasm-opt, wasm-emscripten-finalize, etc.)
BINARYEN_ROOT = '{binaryen_root}'

# Node.js executable for running JavaScript code
# The wrapper sets up PATH to include the bundled Node.js
NODE_JS = '{node_js}'

# Cache directory for compiled libraries
# CACHE = os.path.expanduser(os.path.join('~', '.emscripten_cache'))

# Ports directory for emscripten ports
# PORTS = os.path.join(CACHE, 'ports')
"""

    # Check if config file already exists and has the correct content
    # This prevents race conditions where one process overwrites the config
    # while another process is reading it during compilation
    if config_path.exists():
        try:
            existing_content = config_path.read_text(encoding="utf-8")
            if existing_content == config_content:
                # Verify that the LLVM_ROOT path in the config actually contains clang
                # This catches cases where the config was created but installation is incomplete
                if clang_binary.exists():
                    logger.debug(".emscripten config file already exists with correct content")
                    return
                else:
                    logger.warning(
                        f"Config file exists but clang binary not found at {clang_binary}. "
                        f"Recreating config file..."
                    )
            else:
                logger.info("Updating .emscripten config file with new paths")
        except Exception as e:
            logger.warning(f"Failed to read existing config file: {e}, will recreate")

    # Write config file (only if it doesn't exist or needs updating)
    logger.info(f"Creating .emscripten config file at {config_path}")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
            # Explicitly flush and sync to ensure file is fully written
            # This is critical on Windows to prevent "Permission denied" errors
            # when other processes try to read the file immediately after
            f.flush()
            os.fsync(f.fileno())
        logger.info(f"Successfully created .emscripten config file with LLVM_ROOT={llvm_root}")

        # Verify the file was actually written
        if not config_path.exists():
            raise RuntimeError(f"Config file was not created: {config_path}")

        # Verify the content is correct
        verify_content = config_path.read_text(encoding="utf-8")
        if verify_content != config_content:
            raise RuntimeError("Config file content mismatch after writing")

        # CRITICAL: Wait for filesystem to fully sync the file so other processes can see it
        # This prevents "config file not found" errors in parallel test execution on Windows
        # where file metadata may not be immediately visible to other processes
        if not _verify_file_readable(config_path, "Emscripten config (post-creation sync)", timeout_seconds=2.0):
            # Log warning but don't fail - the file was written successfully above
            # Filesystem sync issues are transient and should resolve when emcc actually runs
            logger.warning(
                f"Config file was created but verification failed: {config_path}\n"
                f"This may indicate a filesystem sync delay, but the file should be accessible shortly."
            )

    except Exception as e:
        logger.error(f"Failed to create .emscripten config file: {e}")
        raise RuntimeError(
            f"Failed to create Emscripten config file at {config_path}: {e}\n"
            f"This may indicate a permissions issue or disk space problem."
        ) from e


# DEPRECATED: This function is no longer used (see docstring for details)
def link_clang_binaries_to_emscripten(platform: str, arch: str) -> None:
    """
    DEPRECATED: This function is no longer used.

    Previously linked clang-tool-chain's LLVM 21.1.5 binaries to Emscripten's bin directory.
    This caused version mismatches because Emscripten 4.0.19 expects LLVM 22.

    REASON FOR DEPRECATION:
    Emscripten distributions already include their own LLVM binaries that match
    their expected version. Overriding these binaries breaks version compatibility.

    ARCHITECTURAL DECISION:
    Emscripten should use its bundled LLVM, not clang-tool-chain's LLVM.
    Each tool maintains its own LLVM version to ensure compatibility.

    This function is kept for code history but should not be called.
    It may be removed in a future version.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    # Get paths
    emscripten_install_dir = get_emscripten_install_dir(platform, arch)
    emscripten_bin = emscripten_install_dir / "bin"
    clang_install_dir = get_install_dir(platform, arch)
    clang_bin = clang_install_dir / "bin"

    # Ensure Clang/LLVM is installed - this is REQUIRED for Emscripten to work
    if not clang_bin.exists():
        logger.info(f"Clang/LLVM toolchain not found at {clang_bin}. Installing main LLVM toolchain...")
        # Ensure the main LLVM toolchain is installed
        ensure_toolchain(platform, arch)

        # CRITICAL: On Windows, wait for filesystem sync before checking if binaries exist
        # This prevents race conditions in parallel test execution
        import time

        for attempt in range(200):  # 200 * 0.01s = 2 seconds max
            if clang_bin.exists():
                if attempt > 0:
                    elapsed = attempt * 0.01
                    if elapsed > 0.1:
                        logger.warning(
                            f"Clang bin directory became visible after {elapsed:.2f}s (filesystem sync delay)"
                        )
                break
            time.sleep(0.01)
        else:
            # Timeout - directory still not visible
            raise RuntimeError(
                f"Failed to install Clang/LLVM toolchain. Expected binaries at {clang_bin}.\n"
                f"Directory not visible after 2 seconds (filesystem sync timeout).\n"
                f"Emscripten requires the main LLVM toolchain to be installed."
            )

        # Verify installation succeeded
        if not clang_bin.exists():
            raise RuntimeError(
                f"Failed to install Clang/LLVM toolchain. Expected binaries at {clang_bin}.\n"
                f"Emscripten requires the main LLVM toolchain to be installed."
            )

    # Ensure emscripten bin directory exists
    emscripten_bin.mkdir(parents=True, exist_ok=True)

    # Determine file extension based on platform
    exe_ext = ".exe" if platform == "win" else ""

    # List of binaries to link
    # Critical binaries are required for Emscripten to function
    critical_binaries = [f"clang{exe_ext}", f"clang++{exe_ext}", f"wasm-ld{exe_ext}"]
    optional_binaries = [
        f"llvm-ar{exe_ext}",
        f"llvm-nm{exe_ext}",
        f"llvm-objcopy{exe_ext}",
        f"llvm-ranlib{exe_ext}",
        f"llvm-strip{exe_ext}",
    ]
    binaries_to_link = critical_binaries + optional_binaries

    for binary in binaries_to_link:
        source = clang_bin / binary
        target = emscripten_bin / binary

        # Check if source exists - fail for critical binaries, skip for optional
        if not source.exists():
            if binary in critical_binaries:
                raise RuntimeError(
                    f"Critical binary not found in LLVM toolchain: {binary}\n"
                    f"Expected location: {source}\n"
                    f"LLVM toolchain directory: {clang_bin}\n"
                    f"This binary is required for Emscripten to function.\n"
                    f"Try removing ~/.clang-tool-chain and reinstalling."
                )
            else:
                logger.debug(f"Optional binary not found: {source}, skipping")
                continue

        # Check if target already exists and is correct
        if target.exists():
            # On Unix, check if it's already a symlink to the right place
            if platform in ("linux", "darwin"):
                if target.is_symlink() and target.resolve() == source.resolve():
                    logger.debug(f"Symlink already correct: {target} -> {source}")
                    continue
                else:
                    # Remove incorrect symlink/file
                    target.unlink()
            else:
                # On Windows, check if the file size matches (simple verification)
                # If sizes don't match, it's a different binary (e.g., from Emscripten archive)
                try:
                    target_size = target.stat().st_size
                    source_size = source.stat().st_size
                    if target_size == source_size:
                        logger.debug(f"Binary already correct: {target}")
                        continue
                    else:
                        # Remove and replace with correct binary from LLVM toolchain
                        logger.info(f"Replacing existing binary {target} with LLVM toolchain version")
                        target.unlink()
                except (FileNotFoundError, OSError) as e:
                    # File disappeared between exists() check and stat() call (filesystem sync issue)
                    # This can happen on Windows with parallel processes
                    logger.warning(f"File {target} disappeared during stat check: {e}, will recreate")
                    # Fall through to copy the file below

        # Create symlink (Unix) or copy (Windows)
        try:
            if platform in ("linux", "darwin"):
                # Use symlink on Unix systems
                target.symlink_to(source)
                logger.info(f"Created symlink: {target} -> {source}")
            else:
                # Copy on Windows (symlinks require admin privileges)
                shutil.copy2(source, target)
                logger.info(f"Copied binary: {source} -> {target}")

                # CRITICAL: On Windows, ensure the copied file is visible to other processes
                # This prevents "file not found" errors in parallel test execution
                # Wait up to 1 second for the file to become accessible
                import time

                for attempt in range(100):  # 100 * 0.01s = 1 second max
                    if target.exists():
                        if attempt > 0:
                            elapsed = attempt * 0.01
                            if elapsed > 0.1:  # Log if it took more than 100ms
                                logger.warning(
                                    f"Binary {binary} became visible after {elapsed:.2f}s (filesystem sync delay)"
                                )
                        break
                    time.sleep(0.01)
                else:
                    # If this is a critical binary, fail immediately
                    if binary in critical_binaries:
                        raise RuntimeError(
                            f"Critical binary {binary} not accessible after 1s: {target}\n"
                            f"This indicates a Windows filesystem sync issue.\n"
                            f"Source: {source}\n"
                            f"Try removing ~/.clang-tool-chain and reinstalling."
                        )
                    else:
                        logger.warning(f"Optional binary {binary} still not visible after 1s: {target}")
        except Exception as e:
            if binary in critical_binaries:
                logger.error(f"Failed to link/copy critical binary {binary}: {e}")
                raise RuntimeError(
                    f"Failed to link/copy critical binary {binary} from LLVM toolchain\n"
                    f"Source: {source}\n"
                    f"Target: {target}\n"
                    f"Error: {e}\n"
                    f"This binary is required for Emscripten to function.\n"
                    f"Try removing ~/.clang-tool-chain and reinstalling."
                ) from e
            else:
                logger.warning(f"Failed to link/copy optional binary {binary}: {e}")

    # Final verification: ensure all critical binaries are present and accessible
    logger.info("Verifying critical binaries are present in Emscripten bin directory")
    for binary in critical_binaries:
        target = emscripten_bin / binary
        if not target.exists():
            raise RuntimeError(
                f"Critical binary verification failed: {binary} not found at {target}\n"
                f"This should not happen after successful linking/copying.\n"
                f"This indicates a filesystem sync issue or a programming error.\n"
                f"Try removing ~/.clang-tool-chain and reinstalling."
            )
        logger.debug(f"Verified critical binary: {target}")

    logger.info(f"Successfully linked {len(binaries_to_link)} binaries to Emscripten")


def is_emscripten_installed(platform: str, arch: str) -> bool:
    """Check if Emscripten is already installed and hash matches current manifest."""
    install_dir = get_emscripten_install_dir(platform, arch)
    done_file = install_dir / "done.txt"

    if not done_file.exists():
        return False

    try:
        done_content = done_file.read_text()
        installed_sha256 = None
        for line in done_content.splitlines():
            if line.startswith("SHA256:"):
                installed_sha256 = line.split(":", 1)[1].strip()
                break

        if not installed_sha256:
            logger.warning(f"No SHA256 found in Emscripten {done_file}, will re-download")
            return False

        # Fetch current manifest
        platform_manifest = fetch_emscripten_platform_manifest(platform, arch)
        latest_version = platform_manifest.latest
        if not latest_version:
            return False

        version_info = platform_manifest.versions.get(latest_version)
        if not version_info:
            return False

        current_sha256 = version_info.sha256

        if installed_sha256.lower() != current_sha256.lower():
            logger.info("Emscripten SHA256 mismatch - will re-download")
            return False

        return True

    except Exception as e:
        logger.warning(f"Error checking Emscripten installation: {e}, will re-download")
        return False


def download_and_install_emscripten(platform: str, arch: str) -> None:
    """
    Download and install Emscripten for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Raises:
        RuntimeError: If download or installation fails
    """
    logger.info(f"Starting Emscripten download and installation for {platform}/{arch}")

    try:
        # Fetch manifest
        manifest = fetch_emscripten_platform_manifest(platform, arch)
        latest_version = manifest.latest
        logger.info(f"Latest Emscripten version: {latest_version}")

        if latest_version not in manifest.versions:
            raise RuntimeError(f"Version {latest_version} not found in manifest")

        version_info = manifest.versions[latest_version]
        download_url = version_info.href
        expected_checksum = version_info.sha256

        logger.info(f"Download URL: {download_url}")
        logger.info(f"Expected SHA256: {expected_checksum}")

        # Create temp directory for download
        with tempfile.TemporaryDirectory(prefix="emscripten_download_") as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / f"emscripten-{latest_version}-{platform}-{arch}.tar.zst"

            logger.info(f"Downloading to: {archive_path}")

            # Download (handles both single-file and multi-part)
            download_archive(version_info, archive_path)
            logger.info("Download and checksum verification successful")

            # Extract
            install_dir = get_emscripten_install_dir(platform, arch)
            logger.info(f"Extracting to: {install_dir}")
            install_dir.mkdir(parents=True, exist_ok=True)

            extract_tarball(archive_path, install_dir)

            # CRITICAL: On Windows, verify extracted files are visible before proceeding
            # This prevents race conditions where extraction completes but files aren't
            # yet visible to other processes due to filesystem caching
            exe_ext = ".exe" if platform == "win" else ""
            bin_dir = install_dir / "bin"
            critical_extracted_files = [
                (install_dir / "emscripten" / "emcc.py", "emcc.py script"),
                (bin_dir / f"wasm-opt{exe_ext}", "wasm-opt binary"),
            ]

            logger.info("Verifying critical extracted files are accessible...")
            for file_path, description in critical_extracted_files:
                if not _verify_file_readable(file_path, description, timeout_seconds=2.0):
                    raise RuntimeError(
                        f"Critical file not accessible after extraction: {description}\n"
                        f"Expected: {file_path}\n"
                        f"This indicates a filesystem sync issue or corrupted archive.\n"
                        f"Try removing ~/.clang-tool-chain/emscripten and reinstalling."
                    )
            logger.info("All critical extracted files verified")

            # Fix permissions on Unix systems
            if platform in ("linux", "darwin"):
                logger.info("Fixing file permissions...")
                fix_file_permissions(install_dir)

            # On Windows, create clang++.exe from clang.exe if it doesn't exist
            # Some Emscripten distributions may not include clang++.exe
            if platform == "win":
                clang_exe = bin_dir / f"clang{exe_ext}"
                clang_pp_exe = bin_dir / f"clang++{exe_ext}"
                if clang_exe.exists() and not clang_pp_exe.exists():
                    logger.info(f"Creating clang++{exe_ext} from clang{exe_ext}...")
                    try:
                        shutil.copy2(clang_exe, clang_pp_exe)
                        logger.info(f"Successfully created {clang_pp_exe}")
                        # Verify the copied file is accessible
                        if not _verify_file_readable(clang_pp_exe, f"clang++{exe_ext}", timeout_seconds=1.0):
                            logger.warning(f"clang++{exe_ext} created but not immediately readable")
                    except Exception as e:
                        logger.error(f"Failed to create clang++{exe_ext}: {e}")
                        raise RuntimeError(
                            f"Failed to create clang++{exe_ext} from clang{exe_ext}: {e}\n"
                            f"This is required for C++ compilation with Emscripten."
                        ) from e

            # REMOVED: Binary linking no longer needed - Emscripten bundles its own LLVM 22
            # Previously, we linked clang-tool-chain's LLVM 21.1.5 to Emscripten, causing version mismatch
            # Emscripten distributions are self-contained with matching LLVM versions
            # link_clang_binaries_to_emscripten(platform, arch)  # DEPRECATED

            # Create .emscripten config file if it doesn't exist
            create_emscripten_config(install_dir, platform, arch)

            # CRITICAL: Remove entire cache directory to force proper header installation on first compile
            # The extracted archive may contain an incomplete or corrupted cache from the build process.
            # By removing it entirely, we ensure Emscripten's install_system_headers() runs on first use,
            # properly generating all C/C++ headers from system/lib/libcxx/include to cache/sysroot/include.
            # This fixes issues where iostream, bits/alltypes.h, and other headers are missing after installation.
            cache_dir = install_dir / "emscripten" / "cache"
            if cache_dir.exists():
                logger.info("Removing Emscripten cache directory to ensure proper header installation on first compile")
                try:
                    shutil.rmtree(cache_dir)
                    logger.info(f"Removed cache directory: {cache_dir}")
                except Exception as e:
                    logger.warning(f"Failed to remove cache directory (non-critical): {e}")

            # Write done marker
            done_file = install_dir / "done.txt"
            with open(done_file, "w") as f:
                f.write(f"Emscripten {latest_version} installed on {datetime.datetime.now()}\n")
                f.write(f"Platform: {platform}\n")
                f.write(f"Architecture: {arch}\n")
                f.write(f"SHA256: {version_info.sha256}\n")
                # Flush and sync to ensure file is fully written
                f.flush()
                os.fsync(f.fileno())

            # Verify done.txt is readable
            if not _verify_file_readable(done_file, "done.txt marker file", timeout_seconds=1.0):
                logger.warning(f"done.txt file verification failed: {done_file}")

            logger.info("Emscripten installation complete")

    except Exception as e:
        logger.error(f"Failed to download and install Emscripten: {e}")
        raise RuntimeError(f"Failed to install Emscripten for {platform}/{arch}: {e}") from e


def ensure_emscripten_available(platform: str, arch: str) -> None:
    """
    Ensure Emscripten is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    If Emscripten is not installed, it will be downloaded and installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Ensuring Emscripten is installed for {platform}/{arch}")

    # Get paths for checks
    install_dir = get_emscripten_install_dir(platform, arch)
    config_path = install_dir / ".emscripten"
    bin_dir = install_dir / "bin"
    exe_ext = ".exe" if platform == "win" else ""
    clang_binary = bin_dir / f"clang{exe_ext}"
    wasm_opt_binary = bin_dir / f"wasm-opt{exe_ext}"

    # Quick check without lock - if fully set up, return immediately
    # This avoids lock contention for the common case where everything is ready
    # Check all critical files to ensure complete installation
    # CRITICAL: Also verify files are readable, not just exists() - fixes filesystem sync race
    clang_pp_binary = bin_dir / f"clang++{exe_ext}"
    if (
        is_emscripten_installed(platform, arch)
        and config_path.exists()
        and clang_binary.exists()
        and clang_pp_binary.exists()  # Also check clang++ exists
        and wasm_opt_binary.exists()
    ):
        # Files exist, but verify they're readable (Windows filesystem sync issue)
        # Use a moderate timeout (2 seconds) to handle filesystem sync delays in parallel tests
        # CRITICAL: Also verify clang binary is readable, not just config and wasm-opt
        if (
            _verify_file_readable(config_path, "Emscripten config (quick check)", timeout_seconds=2.0)
            and _verify_file_readable(wasm_opt_binary, "wasm-opt binary (quick check)", timeout_seconds=2.0)
            and _verify_file_readable(clang_binary, "clang binary (quick check)", timeout_seconds=2.0)
        ):
            # Emscripten is already installed and configured
            logger.info(f"Emscripten already installed and configured for {platform}/{arch}")
            return
        else:
            # Files exist but aren't readable yet - fall through to acquire lock and wait
            logger.warning(
                "Emscripten files exist but aren't fully readable yet. "
                "Acquiring lock to wait for installation to complete."
            )

    # Need to install or configure - acquire lock for thread-safe setup
    logger.info(f"Emscripten needs setup, acquiring lock for {platform}/{arch}")
    lock_path = get_emscripten_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire Emscripten installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Re-check inside lock (another process might have completed setup)
        if (
            is_emscripten_installed(platform, arch)
            and config_path.exists()
            and clang_binary.exists()
            and wasm_opt_binary.exists()
        ):
            logger.info("Another process completed Emscripten setup while we waited")

            # CRITICAL FIX for filesystem sync race condition:
            # done.txt and config file exist, but filesystem may not have synced yet
            # Similar to LLVM toolchain (lines 274-303), wait for critical files to be readable
            # This prevents "config file not found" and "clang not found" errors in parallel test execution

            # Verify critical files are readable (not just exists)
            # This is essential because Emscripten will try to execute these immediately
            # Use a longer timeout (5 seconds) since another process just created these files
            if not _verify_file_readable(config_path, "Emscripten config", timeout_seconds=5.0):
                # Log warning but don't fail - another process completed the setup
                logger.warning(
                    f"Emscripten config file exists but verification failed: {config_path}\n"
                    f"Another process may have just created it. Continuing..."
                )

            # Also verify clang binary is readable - critical for Emscripten execution
            # Use same longer timeout to handle post-creation filesystem sync delays
            if not _verify_file_readable(clang_binary, "clang binary", timeout_seconds=5.0):
                logger.warning(
                    f"Clang binary exists but verification failed: {clang_binary}\n"
                    f"Filesystem sync delay detected. File should be accessible when needed."
                )

            logger.info(f"Emscripten setup complete and verified for {platform}/{arch}")
            return

        # Check if installation is corrupted (done.txt exists but critical files missing)
        # This can happen if a previous installation was interrupted or if the archive was incomplete
        done_file = install_dir / "done.txt"
        if done_file.exists():
            # Verify critical Emscripten components (not just clang binaries which are linked separately)
            emscripten_dir = install_dir / "emscripten"
            critical_emscripten_files = [
                (wasm_opt_binary, "wasm-opt (Binaryen tool)"),
                (emscripten_dir / "emcc.py", "emcc.py (Emscripten compiler)"),
                (clang_binary, "clang binary (Emscripten's bundled LLVM)"),
            ]

            missing_components = []
            for file_path, description in critical_emscripten_files:
                if not file_path.exists():
                    missing_components.append(f"  - {description}: {file_path}")

            if missing_components:
                missing_list = "\n".join(missing_components)
                logger.warning(
                    f"Emscripten installation is corrupted. done.txt exists but critical components are missing:\n"
                    f"{missing_list}\n"
                    f"Removing installation and re-downloading..."
                )
                # Remove corrupted installation
                _robust_rmtree(install_dir)
                logger.info("Corrupted Emscripten installation removed")

        # Install Emscripten if not installed or was just removed due to corruption
        if not is_emscripten_installed(platform, arch):
            logger.info("Starting Emscripten download and installation")
            download_and_install_emscripten(platform, arch)
        else:
            logger.info("Emscripten installed but needs configuration")

        # On Windows, ensure clang++.exe exists (create from clang.exe if missing)
        # This handles cases where the installation predates this fix or the distribution
        # doesn't include clang++.exe
        if platform == "win":
            clang_pp_binary = bin_dir / f"clang++{exe_ext}"
            if not clang_pp_binary.exists() and clang_binary.exists():
                logger.info(f"Creating missing clang++{exe_ext} from clang{exe_ext}...")
                try:
                    shutil.copy2(clang_binary, clang_pp_binary)
                    logger.info(f"Successfully created {clang_pp_binary}")
                    # Verify the copied file is accessible
                    if not _verify_file_readable(clang_pp_binary, f"clang++{exe_ext}", timeout_seconds=1.0):
                        logger.warning(f"clang++{exe_ext} created but not immediately readable")
                except Exception as e:
                    logger.error(f"Failed to create clang++{exe_ext}: {e}")
                    # Don't fail here - the verification below will catch it

        # Create Emscripten configuration file
        # NOTE: Emscripten bundles its own LLVM binaries - we do NOT override them
        # Previously, we linked clang-tool-chain's LLVM 21.1.5, causing version mismatch
        logger.info("Creating Emscripten configuration file")
        # link_clang_binaries_to_emscripten(platform, arch)  # DEPRECATED - removed to fix LLVM version mismatch
        create_emscripten_config(install_dir, platform, arch)

        # Final verification - ensure all critical components are present and readable
        logger.info("Verifying Emscripten installation")
        exe_ext = ".exe" if platform == "win" else ""
        critical_files = [
            (config_path, "Emscripten config file"),
            (clang_binary, "clang compiler"),
            (bin_dir / f"clang++{exe_ext}", "clang++ compiler"),
            (bin_dir / f"wasm-ld{exe_ext}", "wasm-ld linker"),
            (bin_dir / f"wasm-opt{exe_ext}", "wasm-opt (Binaryen)"),
        ]

        missing_files = []
        for file_path, description in critical_files:
            if not file_path.exists():
                missing_files.append(f"  - {description}: {file_path}")

        if missing_files:
            missing_list = "\n".join(missing_files)
            raise RuntimeError(
                f"Emscripten installation verification failed. Missing critical files:\n"
                f"{missing_list}\n\n"
                f"Installation directory: {install_dir}\n"
                f"This indicates an incomplete installation. Try:\n"
                f"  1. clang-tool-chain purge --yes\n"
                f"  2. Re-run your command to trigger a fresh installation"
            )

        # CRITICAL: Verify critical files are readable (not just exists)
        # This prevents "config file not found" and "clang not found" errors in parallel test execution
        # where filesystem may not have synced yet
        if not _verify_file_readable(config_path, "Emscripten config", timeout_seconds=2.0):
            # Log warning but don't fail - the file was verified to exist above
            logger.warning(
                f"Emscripten config file exists but verification failed: {config_path}\n"
                f"This may indicate a filesystem sync delay, continuing..."
            )

        # Also verify clang binary is readable - critical for Emscripten execution
        if not _verify_file_readable(clang_binary, "clang binary (final check)", timeout_seconds=2.0):
            logger.warning(
                f"Clang binary exists but verification failed: {clang_binary}\n"
                f"Filesystem sync delay detected. File should be accessible when needed."
            )

        logger.info(f"Emscripten setup complete and verified for {platform}/{arch}")

    # CRITICAL: After releasing the lock, do a final verification that critical files are
    # accessible to external processes (like child processes that will run emcc)
    # On Windows, filesystem metadata may not propagate immediately after lock release
    # Use a longer timeout (5 seconds) in parallel test scenarios where filesystem sync is slower
    if not _verify_file_readable(config_path, "Emscripten config (post-lock verification)", timeout_seconds=5.0):
        # Log warning but don't fail - the file should be accessible when emcc actually needs it
        logger.warning(
            f"Emscripten config file verification failed after lock release: {config_path}\n"
            f"This may indicate a filesystem sync delay, but file should be accessible when needed."
        )

    # Also verify clang binary is accessible after lock release
    # Use same longer timeout to handle filesystem sync delays under parallel test load
    if not _verify_file_readable(clang_binary, "clang binary (post-lock verification)", timeout_seconds=5.0):
        logger.warning(
            f"Clang binary verification failed after lock release: {clang_binary}\n"
            f"Filesystem sync delay detected, but file should be accessible when needed."
        )


# ============================================================================
# Node.js Installation
# ============================================================================


def is_nodejs_installed(platform: str, arch: str) -> bool:
    """
    Check if Node.js is already installed and hash matches current manifest.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    install_dir = get_nodejs_install_dir(platform, arch)
    done_file = install_dir / "done.txt"

    if not done_file.exists():
        return False

    try:
        done_content = done_file.read_text()
        installed_sha256 = None
        for line in done_content.splitlines():
            if line.startswith("SHA256:"):
                installed_sha256 = line.split(":", 1)[1].strip()
                break

        if not installed_sha256:
            logger.warning(f"No SHA256 found in Node.js {done_file}, will re-download")
            return False

        # Fetch current manifest
        platform_manifest = fetch_nodejs_platform_manifest(platform, arch)
        latest_version = platform_manifest.latest
        if not latest_version:
            return False

        version_info = platform_manifest.versions.get(latest_version)
        if not version_info:
            return False

        current_sha256 = version_info.sha256

        if installed_sha256.lower() != current_sha256.lower():
            logger.info("Node.js SHA256 mismatch - will re-download")
            return False

        return True

    except Exception as e:
        logger.warning(f"Error checking Node.js installation: {e}, will re-download")
        return False


def download_and_install_nodejs(platform: str, arch: str) -> None:
    """
    Download and install Node.js for the given platform/arch.

    This downloads a minimal Node.js runtime (~10-15 MB compressed) that includes
    only the node binary and essential libraries. The full Node.js distribution
    is much larger (~28-49 MB), but we strip out headers, documentation, npm,
    and other unnecessary files.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Raises:
        RuntimeError: If download or installation fails
        ToolchainInfrastructureError: If manifest or download URLs are broken
    """
    from .manifest import ToolchainInfrastructureError

    logger.info(f"Starting Node.js download and installation for {platform}/{arch}")

    try:
        # Fetch manifest
        manifest = fetch_nodejs_platform_manifest(platform, arch)
        latest_version = manifest.latest
        logger.info(f"Latest Node.js version: {latest_version}")

        if latest_version not in manifest.versions:
            raise RuntimeError(f"Version {latest_version} not found in manifest")

        version_info = manifest.versions[latest_version]
        download_url = version_info.href
        expected_checksum = version_info.sha256

        logger.info(f"Download URL: {download_url}")
        logger.info(f"Expected SHA256: {expected_checksum}")

        # Create temp directory for download
        with tempfile.TemporaryDirectory(prefix="nodejs_download_") as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / f"nodejs-{latest_version}-{platform}-{arch}.tar.zst"

            logger.info(f"Downloading to: {archive_path}")

            # Download (handles both single-file and multi-part)
            download_archive(version_info, archive_path)
            logger.info("Download and checksum verification successful")

            # Extract
            install_dir = get_nodejs_install_dir(platform, arch)
            logger.info(f"Extracting to: {install_dir}")

            # Remove old installation if it exists (BEFORE extraction)
            if install_dir.exists():
                logger.info("Removing old Node.js installation")
                _robust_rmtree(install_dir)

            # Ensure parent directory exists
            install_dir.parent.mkdir(parents=True, exist_ok=True)

            extract_tarball(archive_path, install_dir)

            # Fix permissions on Unix systems
            if platform in ("linux", "darwin"):
                logger.info("Fixing file permissions...")
                fix_file_permissions(install_dir)

            # Verify node binary exists
            node_binary = install_dir / "bin" / ("node.exe" if platform == "win" else "node")
            if not node_binary.exists():
                raise RuntimeError(
                    f"Node.js binary not found after extraction: {node_binary}\n"
                    f"Expected location: {node_binary}\n"
                    f"Installation may be corrupted. Please try again."
                )

            logger.info(f"Node.js binary found: {node_binary}")

            # Write done marker
            done_file = install_dir / "done.txt"
            with open(done_file, "w") as f:
                f.write(f"Node.js {latest_version} installed on {datetime.datetime.now()}\n")
                f.write(f"Platform: {platform}\n")
                f.write(f"Architecture: {arch}\n")
                f.write(f"SHA256: {version_info.sha256}\n")

            logger.info("Node.js installation complete")

    except ToolchainInfrastructureError:
        # Re-raise infrastructure errors as-is
        raise
    except Exception as e:
        logger.error(f"Failed to download and install Node.js: {e}")
        # Clean up failed installation
        install_dir = get_nodejs_install_dir(platform, arch)
        if install_dir.exists():
            logger.info("Cleaning up failed Node.js installation")
            _robust_rmtree(install_dir)
        raise RuntimeError(f"Failed to install Node.js for {platform}/{arch}: {e}") from e


def ensure_nodejs_available(platform: str, arch: str) -> Path:
    """
    Ensure Node.js is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    If Node.js is not installed, it will be downloaded and installed automatically.

    The bundled Node.js is a minimal runtime (~10-15 MB compressed) that includes
    only the node binary and essential libraries, without npm, headers, or docs.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        Path to the Node.js installation directory

    Raises:
        RuntimeError: If installation fails
        ToolchainInfrastructureError: If download infrastructure is broken
    """
    logger.info(f"Ensuring Node.js is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately (fast path)
    if is_nodejs_installed(platform, arch):
        logger.info(f"Node.js already installed for {platform}/{arch}")
        return get_nodejs_install_dir(platform, arch)

    # Need to download - acquire lock
    logger.info(f"Node.js not installed, acquiring lock for {platform}/{arch}")
    lock_path = get_nodejs_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire Node.js installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Check again inside lock in case another process just finished installing
        if is_nodejs_installed(platform, arch):
            logger.info("Another process installed Node.js while we waited")
            return get_nodejs_install_dir(platform, arch)

        # Download and install
        logger.info("Starting Node.js download and installation")
        try:
            download_and_install_nodejs(platform, arch)
            logger.info(f"Node.js installation complete for {platform}/{arch}")
        except Exception as e:
            logger.error(f"Node.js installation failed: {e}")
            raise

    return get_nodejs_install_dir(platform, arch)


# ============================================================================
# Helper Functions
# ============================================================================


def get_latest_version_info(platform_manifest: Manifest) -> tuple[str, str, str]:
    """
    Get the latest version information from a platform manifest.

    Args:
        platform_manifest: Platform-specific manifest object

    Returns:
        Tuple of (version, download_url, sha256)

    Raises:
        RuntimeError: If manifest is invalid or missing required fields
    """
    latest_version = platform_manifest.latest
    if not latest_version:
        raise RuntimeError("Manifest does not specify a 'latest' version")

    version_info = platform_manifest.versions.get(latest_version)
    if not version_info:
        raise RuntimeError(f"Version {latest_version} not found in manifest")

    download_url = version_info.href
    sha256 = version_info.sha256

    if not download_url:
        raise RuntimeError(f"No download URL for version {latest_version}")

    return latest_version, download_url, sha256
