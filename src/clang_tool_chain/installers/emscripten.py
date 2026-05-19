"""
Emscripten installer module.

Handles installation of the Emscripten SDK for WebAssembly compilation.
"""

import os
import shutil
from pathlib import Path

import fasteners

from clang_tool_chain.installers.base import BaseToolchainInstaller
from clang_tool_chain.interrupt_utils import handle_keyboard_interrupt_properly
from clang_tool_chain.logging_config import configure_logging
from clang_tool_chain.manifest import fetch_emscripten_platform_manifest
from clang_tool_chain.path_utils import get_emscripten_install_dir, get_emscripten_lock_path
from clang_tool_chain.permissions import _robust_rmtree

logger = configure_logging(__name__)


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


class EmscriptenInstaller(BaseToolchainInstaller):
    """Installer for Emscripten SDK."""

    tool_name = "emscripten"
    binary_name = "clang"  # Emscripten bundles its own clang

    def get_install_dir(self, platform: str, arch: str) -> Path:
        """
        Return the installation directory for Emscripten.

        Override to use legacy function for environment variable override support.
        """
        return get_emscripten_install_dir(platform, arch)

    def get_lock_path(self, platform: str, arch: str) -> Path:
        """
        Return the lock file path for Emscripten.

        Override to use legacy function for environment variable override support.
        """
        return get_emscripten_lock_path(platform, arch)

    def fetch_manifest(self, platform: str, arch: str):
        """Fetch the platform-specific manifest for Emscripten."""
        return fetch_emscripten_platform_manifest(platform, arch)

    def get_binary_path(self, install_dir: Path, platform: str) -> Path:
        """Return path to main binary for verification."""
        exe_ext = ".exe" if platform == "win" else ""
        return install_dir / "bin" / f"clang{exe_ext}"

    # Marker comment written into shared.py to detect prior application of the
    # EMCC_WASM_LD patch and make re-application idempotent.
    _WASM_LD_PATCH_MARKER = "# CTC_EMCC_WASM_LD_PATCH"

    # Sidecar marker file written next to .emscripten after a successful patch.
    # Used as a one-stat() fast-path so we don't re-read the ~30 MB shared.py
    # on every ensure_emscripten_available() call. Versioned filename — bump
    # the suffix when the patch content changes so old markers don't
    # falsely advertise the new patch as applied.
    _WASM_LD_PATCH_MARKER_FILE = ".ctc-wasm-ld-patched.v1"

    def post_extract_hook(self, install_dir: Path, platform: str, arch: str) -> None:
        """
        Custom post-extraction steps for Emscripten.

        Creates clang++ on Windows, patches shared.py to honor EMCC_WASM_LD,
        creates config file, and removes cache.
        """
        exe_ext = ".exe" if platform == "win" else ""
        bin_dir = install_dir / "bin"

        # CRITICAL: On Windows, verify extracted files are visible before proceeding
        # This prevents race conditions where extraction completes but files aren't
        # yet visible to other processes due to filesystem caching
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
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    logger.error(f"Failed to create clang++{exe_ext}: {e}")
                    raise RuntimeError(
                        f"Failed to create clang++{exe_ext} from clang{exe_ext}: {e}\n"
                        f"This is required for C++ compilation with Emscripten."
                    ) from e

        # Create .emscripten config file if it doesn't exist
        self._create_config(install_dir, platform, arch)

        # Patch shared.py so EMCC_WASM_LD env var overrides the bundled wasm-ld.
        # This lets downstream projects plug in ctc-wasm-ld (or any wasm-ld replacement)
        # without symlinking or shipping their own emscripten fork.
        self._apply_wasm_ld_patch(install_dir)

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
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
            except Exception as e:
                logger.warning(f"Failed to remove cache directory (non-critical): {e}")

    def verify_installation(self, install_dir: Path, platform: str, arch: str) -> None:
        """Extended verification for Emscripten."""
        exe_ext = ".exe" if platform == "win" else ""
        config_path = install_dir / ".emscripten"
        bin_dir = install_dir / "bin"

        critical_files = [
            (config_path, "Emscripten config file"),
            (bin_dir / f"clang{exe_ext}", "clang compiler"),
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

        logger.info(f"Emscripten binary verified at: {self.get_binary_path(install_dir, platform)}")

    def _create_config(self, install_dir: Path, platform: str, arch: str) -> None:
        """
        Create .emscripten config file if it doesn't exist.

        The config file contains paths to LLVM, Binaryen, and Node.js tools
        that Emscripten needs to compile WebAssembly code.

        IMPORTANT: Emscripten distributions include their own LLVM binaries
        (e.g., LLVM 22 for Emscripten 4.0.19). This function configures paths
        to use Emscripten's bundled LLVM, NOT clang-tool-chain's LLVM.
        This ensures version compatibility between Emscripten and LLVM.
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
            except KeyboardInterrupt as ke:
                handle_keyboard_interrupt_properly(ke)
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

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except Exception as e:
            logger.error(f"Failed to create .emscripten config file: {e}")
            raise RuntimeError(
                f"Failed to create Emscripten config file at {config_path}: {e}\n"
                f"This may indicate a permissions issue or disk space problem."
            ) from e

    def _apply_wasm_ld_patch(self, install_dir: Path) -> None:
        """
        Patch emscripten/tools/shared.py so EMCC_WASM_LD overrides the bundled
        wasm-ld path. Idempotent — re-applying on an already-patched file is a no-op.

        Hot path (1.5.5+): if the sidecar marker file
        ``{install_dir}/.ctc-wasm-ld-patched.v1`` exists, return immediately
        after a single ``stat()``. Skips the ~30 MB read of shared.py that
        used to dominate ``ensure_emscripten_available`` (~50–800 ms per call).

        Cold path: read shared.py, scan for the inline marker, apply if needed,
        then drop the sidecar marker so future calls take the hot path.

        Background:
          Emscripten sets WASM_LD = llvm_tool_path('wasm-ld') at module load and
          has no built-in env-var override. building.link_lld() invokes WASM_LD
          directly, so swapping in ctc-wasm-ld requires either a symlink or a
          source patch. We choose the source patch because symlinks get stomped
          on every reinstall.
        """
        marker_path = install_dir / self._WASM_LD_PATCH_MARKER_FILE
        if marker_path.exists():
            # Hot path: single stat. Marker is written only after a successful
            # patch, and reinstalls wipe install_dir whole, so marker presence
            # is a reliable "patch is in shared.py" signal.
            return

        shared_py = install_dir / "emscripten" / "tools" / "shared.py"
        if not shared_py.exists():
            logger.warning(
                f"EMCC_WASM_LD patch skipped — {shared_py} not found. emcc will not honor EMCC_WASM_LD on this install."
            )
            return

        try:
            content = shared_py.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"EMCC_WASM_LD patch skipped — could not read {shared_py}: {e}")
            return

        if self._WASM_LD_PATCH_MARKER in content:
            # Patch already present in shared.py — likely from a pre-1.5.5
            # install that pre-dates the sidecar marker. Drop the marker so the
            # next call takes the hot path and skip the (already-applied) patch.
            self._write_marker_quietly(marker_path)
            logger.debug(f"shared.py already patched for EMCC_WASM_LD: {shared_py}")
            return

        original = "WASM_LD = llvm_tool_path('wasm-ld')"
        replacement = (
            f"{self._WASM_LD_PATCH_MARKER}: honor EMCC_WASM_LD for ctc-wasm-ld integration\n"
            "WASM_LD = os.environ.get('EMCC_WASM_LD') or llvm_tool_path('wasm-ld')"
        )

        if original not in content:
            # Unexpected emscripten version or already-replaced source. Don't crash
            # the install — log and move on. Users can still opt in via symlink.
            logger.warning(
                f"EMCC_WASM_LD patch skipped — expected line not found in {shared_py}. "
                f"This usually means an unknown emscripten version. "
                f"ctc-wasm-ld auto-injection will be a no-op for this install."
            )
            return

        patched = content.replace(original, replacement, 1)
        try:
            shared_py.write_text(patched, encoding="utf-8")
            logger.info(f"Applied EMCC_WASM_LD patch to {shared_py}")
            self._write_marker_quietly(marker_path)
        except OSError as e:
            logger.warning(f"EMCC_WASM_LD patch skipped — could not write {shared_py}: {e}")

    @staticmethod
    def _write_marker_quietly(marker_path: Path) -> None:
        """Drop the sidecar marker. Best-effort — failures aren't fatal since
        the next call just takes the cold path and re-detects the patch."""
        try:
            marker_path.write_text(
                "# Sidecar marker — clang-tool-chain has applied the EMCC_WASM_LD\n"
                "# patch to emscripten/tools/shared.py. Delete this file to force a\n"
                "# re-check on the next ensure_emscripten_available() call.\n",
                encoding="utf-8",
            )
        except OSError as e:
            logger.debug(f"Could not write {marker_path} (non-fatal): {e}")


# Module-level singleton installer instance
_installer = EmscriptenInstaller()

# Per-process memo of (platform, arch) tuples that have been fully verified
# by ensure_emscripten_available() in this Python process. Lets a single
# build script that calls ensure() multiple times pay the check cost only once.
# Reset across processes (which is what FastLED's bash compile wasm pattern hits)
# — that's covered by the marker file + done.txt-age fast paths.
_ensure_memo: set[tuple[str, str]] = set()


def _emscripten_ensure_memo_reset_for_tests() -> None:
    """Test-only hook to clear the per-process memoization set."""
    _ensure_memo.clear()


# Age of done.txt past which we trust the install is settled and skip the
# expensive open()+read() readability checks. The race window that
# _verify_file_readable was written to handle (Windows filesystem sync after
# extraction) closes within a couple of seconds; 5 s is conservative.
_DONE_TXT_RACE_WINDOW_SECONDS = 5.0

# How long to trust a previously-verified install before re-fetching the
# upstream manifest from GitHub. The manifest fetch is the dominant cost in
# warm ``ensure_emscripten_available`` calls (~250–900 ms depending on
# network latency). Caching for 24 hours means an interactive build pays the
# manifest cost once a day instead of every invocation.
#
# Force a fresh check by setting ``CLANG_TOOL_CHAIN_FORCE_MANIFEST_CHECK=1``,
# or by removing done.txt to trigger a full reinstall path.
_MANIFEST_RECHECK_INTERVAL_SECONDS = 24 * 60 * 60


def _is_post_race_window(done_path: Path) -> bool:
    """True if done.txt exists and was created/modified more than
    ``_DONE_TXT_RACE_WINDOW_SECONDS`` seconds ago. Used to skip
    ``_verify_file_readable`` calls that are only meaningful while the
    filesystem-sync race window is open."""
    import time as _time

    try:
        age = _time.time() - done_path.stat().st_mtime
    except OSError:
        return False
    return age > _DONE_TXT_RACE_WINDOW_SECONDS


def _can_skip_manifest_recheck(done_path: Path) -> bool:
    """True if we can trust the existing install without re-fetching the
    upstream manifest from GitHub. Saves ~250–900 ms per call.

    Returns False when:
      - done.txt is missing or unreadable (treat as not installed)
      - done.txt is older than ``_MANIFEST_RECHECK_INTERVAL_SECONDS``
      - ``CLANG_TOOL_CHAIN_FORCE_MANIFEST_CHECK`` is set (testing / debugging)
    """
    if os.environ.get("CLANG_TOOL_CHAIN_FORCE_MANIFEST_CHECK", "").lower() in ("1", "true", "yes"):
        return False
    import time as _time

    try:
        age = _time.time() - done_path.stat().st_mtime
    except OSError:
        return False
    return 0 <= age < _MANIFEST_RECHECK_INTERVAL_SECONDS


def is_emscripten_installed(platform: str, arch: str) -> bool:
    """Check if Emscripten is already installed and hash matches current manifest."""
    return _installer.is_installed(platform, arch)


def download_and_install_emscripten(platform: str, arch: str) -> None:
    """
    Download and install Emscripten for the given platform/arch.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")

    Raises:
        RuntimeError: If download or installation fails
    """
    return _installer.download_and_install(platform, arch)


def ensure_emscripten_available(platform: str, arch: str) -> None:
    """
    Ensure Emscripten is installed for the given platform/arch.

    This function uses file locking to prevent concurrent downloads.
    If Emscripten is not installed, it will be downloaded and installed.

    This function extends the base ensure() method with additional
    Emscripten-specific verification and configuration steps.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    # Process-level memoization: if we already verified this (platform, arch)
    # in the current Python process, every subsequent call is a no-op. Covers
    # build scripts that call ensure() multiple times per invocation. Cross-
    # process callers (e.g. ``bash compile wasm`` spawning fresh interpreters)
    # don't hit this — that's what the marker file + done.txt-age gates are for.
    memo_key = (platform, arch)
    if memo_key in _ensure_memo:
        return

    logger.info(f"Ensuring Emscripten is installed for {platform}/{arch}")

    # Get paths for checks
    install_dir = get_emscripten_install_dir(platform, arch)
    config_path = install_dir / ".emscripten"
    bin_dir = install_dir / "bin"
    exe_ext = ".exe" if platform == "win" else ""
    clang_binary = bin_dir / f"clang{exe_ext}"
    wasm_opt_binary = bin_dir / f"wasm-opt{exe_ext}"
    done_path = install_dir / "done.txt"

    # Quick check without lock - if fully set up, return immediately
    # This avoids lock contention for the common case where everything is ready
    # Check all critical files to ensure complete installation
    # CRITICAL: Also verify files are readable, not just exists() - fixes filesystem sync race
    clang_pp_binary = bin_dir / f"clang++{exe_ext}"

    # is_emscripten_installed() makes two HTTPS calls to GitHub to verify the
    # upstream SHA256 hasn't changed. Skip that round-trip when done.txt is
    # recent (default: 24 h). User can force a recheck by setting
    # ``CLANG_TOOL_CHAIN_FORCE_MANIFEST_CHECK=1`` or by deleting done.txt.
    install_is_current = _can_skip_manifest_recheck(done_path) or is_emscripten_installed(platform, arch)

    if (
        install_is_current
        and config_path.exists()
        and clang_binary.exists()
        and clang_pp_binary.exists()  # Also check clang++ exists
        and wasm_opt_binary.exists()
    ):
        # Readability checks via _verify_file_readable() guard against a Windows
        # filesystem-sync race that's only present in the few seconds after
        # extraction. Once done.txt is older than the race window, skip them —
        # they cost ~30–100 ms per call (one open() + read() each) and add no
        # safety on a settled install. Fresh installs still get the full check.
        skip_readability_checks = _is_post_race_window(done_path)
        readable_ok = skip_readability_checks or (
            _verify_file_readable(config_path, "Emscripten config (quick check)", timeout_seconds=2.0)
            and _verify_file_readable(wasm_opt_binary, "wasm-opt binary (quick check)", timeout_seconds=2.0)
            and _verify_file_readable(clang_binary, "clang binary (quick check)", timeout_seconds=2.0)
        )
        if readable_ok:
            # Apply the EMCC_WASM_LD patch on existing installs (idempotent — no-op once applied).
            # Covers users who installed before the patch was added to clang-tool-chain.
            _installer._apply_wasm_ld_patch(install_dir)

            # Emscripten is already installed and configured
            logger.info(f"Emscripten already installed and configured for {platform}/{arch}")
            _ensure_memo.add(memo_key)
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
            # Similar to LLVM toolchain, wait for critical files to be readable
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

            # Apply the EMCC_WASM_LD patch (idempotent) — covers existing installs.
            _installer._apply_wasm_ld_patch(install_dir)

            logger.info(f"Emscripten setup complete and verified for {platform}/{arch}")
            _ensure_memo.add(memo_key)
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
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except Exception as e:
                    logger.error(f"Failed to create clang++{exe_ext}: {e}")
                    # Don't fail here - the verification below will catch it

        # Create Emscripten configuration file
        # NOTE: Emscripten bundles its own LLVM binaries - we do NOT override them
        # Previously, we linked clang-tool-chain's LLVM 21.1.5, causing version mismatch
        logger.info("Creating Emscripten configuration file")
        _installer._create_config(install_dir, platform, arch)

        # Final verification - ensure all critical components are present and readable
        logger.info("Verifying Emscripten installation")
        _installer.verify_installation(install_dir, platform, arch)

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
        _ensure_memo.add(memo_key)

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


def create_emscripten_config(install_dir: Path, platform: str, arch: str) -> None:
    """
    Create .emscripten config file if it doesn't exist.

    Public API for backward compatibility.
    """
    _installer._create_config(install_dir, platform, arch)


# DEPRECATED: This function is no longer used (kept for backward compatibility)
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

    This function is kept for code history and backward compatibility but should not be called.
    It may be removed in a future version.

    Args:
        platform: Platform name (e.g., "win", "linux", "darwin")
        arch: Architecture name (e.g., "x86_64", "arm64")
    """
    logger.warning(
        "link_clang_binaries_to_emscripten() is deprecated and does nothing. "
        "Emscripten uses its own bundled LLVM binaries."
    )
    pass  # No-op for backward compatibility


__all__ = [
    "is_emscripten_installed",
    "download_and_install_emscripten",
    "ensure_emscripten_available",
    "create_emscripten_config",
    "link_clang_binaries_to_emscripten",  # DEPRECATED but kept for backward compatibility
]
