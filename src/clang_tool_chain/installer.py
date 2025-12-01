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
    fetch_nodejs_platform_manifest,
    fetch_platform_manifest,
)
from .path_utils import (
    get_emscripten_install_dir,
    get_emscripten_lock_path,
    get_install_dir,
    get_iwyu_install_dir,
    get_iwyu_lock_path,
    get_lock_path,
    get_nodejs_install_dir,
    get_nodejs_lock_path,
)
from .permissions import _robust_rmtree, fix_file_permissions

# Configure logging using centralized configuration
logger = configure_logging(__name__)


# ============================================================================
# Clang/LLVM Installation
# ============================================================================


def is_toolchain_installed(platform: str, arch: str) -> bool:
    """
    Check if the toolchain is already installed for the given platform/arch.

    This checks for the presence of a done.txt file which is created after
    successful download and extraction.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed, False otherwise
    """
    install_dir = get_install_dir(platform, arch)
    done_file = install_dir / "done.txt"
    return done_file.exists()


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
        if verbose:
            print(f"Downloading to {archive_path}...")

        download_archive(version_info, archive_path)

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
        done_file.write_text(f"Installation completed successfully\nVersion: {latest_version}\n")

    finally:
        # Clean up downloaded archive
        if archive_path.exists():
            archive_path.unlink()

    if verbose:
        print("Installation complete!")


def ensure_toolchain(platform: str, arch: str) -> None:
    """
    Ensure the toolchain is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    If the toolchain is not installed, it will be downloaded and installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Ensuring toolchain is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately
    if is_toolchain_installed(platform, arch):
        logger.info(f"Toolchain already installed for {platform}/{arch}")
        return

    # Need to download - acquire lock
    logger.info(f"Toolchain not installed, acquiring lock for {platform}/{arch}")
    lock_path = get_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Check again inside lock in case another process just finished installing
        if is_toolchain_installed(platform, arch):
            logger.info("Another process installed the toolchain while we waited")

            # CRITICAL FIX for macOS APFS race condition:
            # done.txt exists, but filesystem may not have synced yet (especially on macOS APFS)
            # The other process may have written done.txt but binaries aren't visible yet
            # Wait up to 2 seconds for the clang binary to become visible
            install_dir = get_install_dir(platform, arch)
            bin_dir = install_dir / "bin"
            clang_binary = bin_dir / "clang.exe" if platform == "win" else bin_dir / "clang"

            if not clang_binary.exists():
                logger.warning("done.txt exists but clang binary not visible yet, waiting for filesystem sync...")
                import time

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
                    # Binary still not visible after 2 seconds - this is unexpected but proceed anyway
                    # The subsequent find_tool_binary() call will give a better error message
                    logger.error(
                        f"Clang binary still not visible after 2s wait. "
                        f"Expected: {clang_binary}. This may indicate a filesystem sync issue or corrupted installation."
                    )
            else:
                logger.info("Clang binary verified immediately (no sync delay)")

            return

        # Download and install
        logger.info("Starting toolchain download and installation")
        download_and_install_toolchain(platform, arch)
        logger.info(f"Toolchain installation complete for {platform}/{arch}")


# ============================================================================
# IWYU Installation
# ============================================================================


def is_iwyu_installed(platform: str, arch: str) -> bool:
    """
    Check if IWYU is already installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed, False otherwise
    """
    install_dir = get_iwyu_install_dir(platform, arch)
    done_file = install_dir / "done.txt"
    return done_file.exists()


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

        # Fix permissions on Unix systems
        if os.name != "nt":
            logger.info("Setting executable permissions on IWYU binaries")
            fix_file_permissions(install_dir)

        # Mark installation as complete
        # Ensure install_dir exists before writing done.txt
        install_dir.mkdir(parents=True, exist_ok=True)
        done_file = install_dir / "done.txt"
        with open(done_file, "w") as f:
            f.write(f"IWYU {manifest.latest} installed successfully\n")

        logger.info(f"IWYU installation complete for {platform}/{arch}")


def ensure_iwyu(platform: str, arch: str) -> None:
    """
    Ensure IWYU is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    If IWYU is not installed, it will be downloaded and installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.info(f"Ensuring IWYU is installed for {platform}/{arch}")

    # Quick check without lock - if already installed, return immediately
    if is_iwyu_installed(platform, arch):
        logger.info(f"IWYU already installed for {platform}/{arch}")
        return

    # Need to download - acquire lock
    logger.info(f"IWYU not installed, acquiring lock for {platform}/{arch}")
    lock_path = get_iwyu_lock_path(platform, arch)
    logger.debug(f"Lock path: {lock_path}")
    lock = fasteners.InterProcessLock(str(lock_path))

    logger.info("Waiting to acquire IWYU installation lock...")
    with lock:
        logger.info("Lock acquired")

        # Check again inside lock in case another process just finished installing
        if is_iwyu_installed(platform, arch):
            logger.info("Another process installed IWYU while we waited")
            return

        # Download and install
        logger.info("Starting IWYU download and installation")
        download_and_install_iwyu(platform, arch)
        logger.info(f"IWYU installation complete for {platform}/{arch}")


# ============================================================================
# Emscripten Installation
# ============================================================================


def create_emscripten_config(install_dir: Path, platform: str, arch: str) -> None:
    """
    Create .emscripten config file if it doesn't exist.

    The config file contains paths to LLVM, Binaryen, and Node.js tools
    that Emscripten needs to compile WebAssembly code.

    IMPORTANT: This function expects that link_clang_binaries_to_emscripten()
    has already been called. It will not call it itself to avoid circular dependencies.

    Args:
        install_dir: Emscripten installation directory
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    config_path = install_dir / ".emscripten"

    # Verify the Emscripten bin directory exists
    # NOTE: We don't create it or link binaries here to avoid circular dependency
    # with link_clang_binaries_to_emscripten(). The caller is responsible for
    # ensuring binaries are linked before calling this function.
    emscripten_bin = install_dir / "bin"
    exe_ext = ".exe" if platform == "win" else ""
    clang_binary = emscripten_bin / f"clang{exe_ext}"

    if not clang_binary.exists():
        # This indicates a programming error - the caller should have linked binaries first
        logger.error(
            f"Cannot create .emscripten config: clang binary not found at {clang_binary}\n"
            f"This is a programming error. link_clang_binaries_to_emscripten() must be called "
            f"BEFORE create_emscripten_config().\n"
            f"Emscripten bin directory: {emscripten_bin}"
        )
        raise RuntimeError(
            f"Cannot create .emscripten config: clang binary not found at {clang_binary}\n"
            f"The LLVM toolchain must be installed and linked before creating the config file.\n"
            f"This indicates a programming error in the installation sequence.\n"
            f"Please report this at https://github.com/zackees/clang-tool-chain/issues"
        )

    # Set up paths relative to install_dir
    # Emscripten expects Unix-style paths even on Windows
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
                logger.debug(".emscripten config file already exists with correct content")
                return
            else:
                logger.info("Updating .emscripten config file with new paths")
        except Exception as e:
            logger.warning(f"Failed to read existing config file: {e}, will recreate")

    # Write config file (only if it doesn't exist or needs updating)
    logger.info(f"Creating .emscripten config file at {config_path}")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        logger.info(f"Successfully created .emscripten config file with LLVM_ROOT={llvm_root}")

        # Verify the file was actually written
        if not config_path.exists():
            raise RuntimeError(f"Config file was not created: {config_path}")

        # Verify the content is correct
        verify_content = config_path.read_text(encoding="utf-8")
        if verify_content != config_content:
            raise RuntimeError("Config file content mismatch after writing")

    except Exception as e:
        logger.error(f"Failed to create .emscripten config file: {e}")
        raise RuntimeError(
            f"Failed to create Emscripten config file at {config_path}: {e}\n"
            f"This may indicate a permissions issue or disk space problem."
        ) from e


def link_clang_binaries_to_emscripten(platform: str, arch: str) -> None:
    """
    Link or copy clang binaries from main LLVM toolchain to Emscripten bin directory.

    Emscripten expects clang/clang++ to be available in the LLVM_ROOT/bin directory.
    This function ensures those binaries are available by creating symlinks (Unix) or
    copies (Windows) from the main LLVM toolchain installation.

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
                if target.stat().st_size == source.stat().st_size:
                    logger.debug(f"Binary already correct: {target}")
                    continue
                else:
                    # Remove and replace with correct binary from LLVM toolchain
                    logger.info(f"Replacing existing binary {target} with LLVM toolchain version")
                    target.unlink()

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
        except Exception as e:
            logger.warning(f"Failed to link/copy {binary}: {e}")


def is_emscripten_installed(platform: str, arch: str) -> bool:
    """Check if Emscripten is already installed."""
    install_dir = get_emscripten_install_dir(platform, arch)
    done_file = install_dir / "done.txt"
    return done_file.exists()


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

            # Fix permissions on Unix systems
            if platform in ("linux", "darwin"):
                logger.info("Fixing file permissions...")
                fix_file_permissions(install_dir)

            # Link clang binaries from main LLVM toolchain
            logger.info("Linking clang binaries from main LLVM toolchain...")
            link_clang_binaries_to_emscripten(platform, arch)

            # Create .emscripten config file if it doesn't exist
            create_emscripten_config(install_dir, platform, arch)

            # Write done marker
            done_file = install_dir / "done.txt"
            with open(done_file, "w") as f:
                f.write(f"Emscripten {latest_version} installed on {datetime.datetime.now()}\n")
                f.write(f"Platform: {platform}\n")
                f.write(f"Architecture: {arch}\n")

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
    if (
        is_emscripten_installed(platform, arch)
        and config_path.exists()
        and clang_binary.exists()
        and wasm_opt_binary.exists()
    ):
        logger.info(f"Emscripten already installed and configured for {platform}/{arch}")
        return

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

        # Always ensure config and binaries are set up (idempotent operations)
        # This handles cases where LLVM was installed after Emscripten
        logger.info("Ensuring Emscripten configuration and binary links")
        link_clang_binaries_to_emscripten(platform, arch)
        create_emscripten_config(install_dir, platform, arch)

        # Final verification - ensure all critical components are present
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

        logger.info(f"Emscripten setup complete and verified for {platform}/{arch}")


# ============================================================================
# Node.js Installation
# ============================================================================


def is_nodejs_installed(platform: str, arch: str) -> bool:
    """
    Check if Node.js is already installed.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed, False otherwise
    """
    install_dir = get_nodejs_install_dir(platform, arch)
    done_file = install_dir / "done.txt"
    return done_file.exists()


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
