"""
Clang/LLVM toolchain installer module.
"""

import contextlib
import os
import shutil
import sys
import time
from pathlib import Path

from clang_tool_chain.archive import download_archive
from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.manifest import Manifest, fetch_platform_manifest
from clang_tool_chain.path_utils import get_install_dir, get_lock_path

logger = configure_logging(__name__)


class ClangInstaller(BaseToolchainInstaller):
    """Installer for Clang/LLVM toolchain."""

    tool_name = "clang"
    binary_name = "clang"

    def get_install_dir(self, platform: str, arch: str) -> Path:
        # Override to use legacy path function for backward compatibility
        return get_install_dir(platform, arch)

    def get_lock_path(self, platform: str, arch: str) -> Path:
        # Override to use legacy path function for backward compatibility
        return get_lock_path(platform, arch)

    def fetch_manifest(self, platform: str, arch: str) -> Manifest:
        return fetch_platform_manifest(platform, arch)

    def download_and_install(self, platform: str, arch: str, verbose: bool = False) -> None:
        """
        Download and install toolchain for the given platform/arch.

        This function overrides the base implementation to add verbose printing
        and additional verification steps specific to the Clang toolchain.

        Args:
            platform: Platform name (e.g., "win", "linux", "darwin")
            arch: Architecture name (e.g., "x86_64", "arm64")
            verbose: If True, print progress messages
        """
        if verbose:
            print(f"Downloading clang-tool-chain for {platform}/{arch}...")

        # Fetch platform manifest
        platform_manifest = self.fetch_manifest(platform, arch)

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

        # Check if archive is cached
        from ..archive_cache import get_cached_archive, save_archive_to_cache

        cached_archive = get_cached_archive("clang", platform, arch, version_info.sha256)

        if cached_archive:
            # Use cached archive (no download needed)
            archive_path = cached_archive
            if verbose:
                print(f"Using cached archive: {archive_path}")
            print("Using cached Clang/LLVM archive (skipping download)", file=sys.stderr, flush=True)
        else:
            # Download archive to a temporary file
            import tempfile

            with tempfile.NamedTemporaryFile(mode="wb", suffix=".tar.zst", delete=False) as tmp:
                archive_path = Path(tmp.name)

            # Get file size information and print to stderr before download
            from ..parallel_download import check_server_capabilities

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

            print("Download complete. Caching and extracting toolchain...", file=sys.stderr, flush=True)

            # Save to cache for future use
            save_archive_to_cache(archive_path, "clang", platform, arch, version_info.sha256)

        try:
            print("Extracting toolchain...", file=sys.stderr, flush=True)

            if verbose:
                print("Download complete. Verifying checksum...")

            # Extract to installation directory
            from ..archive import extract_tarball
            from ..permissions import _robust_rmtree, fix_file_permissions

            install_dir = self.get_install_dir(platform, arch)

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

            # Post-extraction hooks
            self.post_extract_hook(install_dir, platform, arch)

            # Force filesystem sync
            self._force_filesystem_sync(install_dir)

            # Verify installation
            self.verify_installation(install_dir, platform, arch)

            # Write done.txt to mark successful installation
            install_dir.mkdir(parents=True, exist_ok=True)
            done_file = install_dir / "done.txt"
            done_file.write_text(
                f"Installation completed successfully\nVersion: {latest_version}\nSHA256: {version_info.sha256}\n"
            )

            print("Clang/LLVM toolchain installation complete!", file=sys.stderr, flush=True)

        finally:
            # Clean up downloaded archive (but not if it came from cache)
            if not cached_archive and archive_path.exists():
                archive_path.unlink()

        if verbose:
            print("Installation complete!")

    def post_extract_hook(self, install_dir: Path, platform: str, arch: str) -> None:
        """
        Perform platform-specific post-extraction steps.

        Args:
            install_dir: Installation directory
            platform: Platform name
            arch: Architecture name
        """
        # On Linux, copy clang++ to clang for convenience
        if platform == "linux":
            bin_dir = install_dir / "bin"
            clang_cpp = bin_dir / "clang++"
            clang = bin_dir / "clang"
            if clang_cpp.exists() and not clang.exists():
                logger.info("Copying clang++ to clang on Linux...")
                shutil.copy2(clang_cpp, clang)

        # On macOS, create ld64.lld symlink for -fuse-ld=ld64.lld support
        if platform == "darwin":
            bin_dir = install_dir / "bin"
            lld_path = bin_dir / "lld"
            ld64_lld_path = bin_dir / "ld64.lld"
            if lld_path.exists() and not ld64_lld_path.exists():
                logger.info("Creating ld64.lld symlink for macOS Mach-O linker support...")
                try:
                    # Create relative symlink to lld (same directory)
                    os.symlink("lld", ld64_lld_path)
                    logger.info(f"Created ld64.lld symlink at {ld64_lld_path}")
                except OSError as e:
                    # If symlink fails (e.g., permissions), log warning but continue
                    logger.warning(f"Failed to create ld64.lld symlink: {e}")
            elif ld64_lld_path.exists():
                logger.info(f"ld64.lld already exists at {ld64_lld_path}")

    def _force_filesystem_sync(self, install_dir: Path) -> None:
        """
        Force filesystem sync to ensure all extracted files are fully written to disk.

        This prevents "Text file busy" errors when another thread/process tries to
        execute the binaries immediately after we release the lock and see done.txt.

        Args:
            install_dir: Installation directory
        """
        import platform as plat

        if plat.system() != "Windows":
            # On Unix systems, use fsync() on the bin directory for synchronous flush
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
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                # fsync on directories may not work on all filesystems
                logger.warning(f"fsync() on bin directory failed: {e}, falling back to os.sync()")

            # Fallback to os.sync() if fsync failed (best effort)
            if not fsync_success and hasattr(os, "sync"):
                with contextlib.suppress(Exception):
                    os.sync()  # type: ignore[attr-defined]
                    logger.info("Fallback: called os.sync() for filesystem flush")

    def verify_installation(self, install_dir: Path, platform: str, arch: str) -> None:
        """
        Verify that installation was successful.

        For Windows, also verifies MinGW sysroot integrity.

        Args:
            install_dir: Installation directory
            platform: Platform name
            arch: Architecture name
        """
        # Verify the clang binary exists
        super().verify_installation(install_dir, platform, arch)

        # Verify MinGW sysroot exists on Windows (integrated in Clang archive since v2.0.0)
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

    def ensure(self, platform: str, arch: str) -> None:
        """
        Ensure toolchain is installed for the given platform/arch.

        This overrides the base implementation to add additional filesystem sync
        verification specific to the Clang toolchain.

        Args:
            platform: Platform name (e.g., "win", "linux", "darwin")
            arch: Architecture name (e.g., "x86_64", "arm64")
        """
        import subprocess

        logger.info(f"Ensuring toolchain is installed for {platform}/{arch}")

        # Quick check without lock
        if self.is_installed(platform, arch):
            logger.info(f"Toolchain already installed for {platform}/{arch}")
            return

        # Spawn subprocess for installation
        logger.info(f"Toolchain not installed, spawning subprocess to install for {platform}/{arch}")

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"from clang_tool_chain.installers.clang import _subprocess_install_toolchain; "
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
        install_dir = self.get_install_dir(platform, arch)
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


# Create singleton installer instance
_installer = ClangInstaller()


# Module-level functions for backward compatibility
def is_toolchain_installed(platform: str, arch: str) -> bool:
    """
    Check if toolchain is already installed and hash matches current manifest.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Returns:
        True if installed and hash matches, False otherwise
    """
    return _installer.is_installed(platform, arch)


def download_and_install_toolchain(platform: str, arch: str, verbose: bool = False) -> None:
    """
    Download and install the toolchain for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
        verbose: If True, print progress messages
    """
    return _installer.download_and_install(platform, arch, verbose)


def _subprocess_install_toolchain(platform: str, arch: str) -> int:  # pyright: ignore[reportUnusedFunction]
    """
    Install toolchain in a subprocess with proper process-level locking.

    Args:
        platform: Platform name
        arch: Architecture name

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    return _installer.subprocess_install(platform, arch)


def ensure_toolchain(platform: str, arch: str) -> None:
    """
    Ensure the toolchain is installed for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    return _installer.ensure(platform, arch)
