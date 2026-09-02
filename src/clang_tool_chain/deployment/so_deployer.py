"""
Linux shared library (.so) deployment using readelf for detection.

This module provides automatic deployment of LLVM toolchain shared libraries
(libc++, libunwind, etc.) to executable directories on Linux. It uses readelf
for dependency detection and handles versioned symlinks properly.
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

# Truthy values accepted by the CLANG_TOOL_CHAIN_ALWAYS_DEPLOY escape hatch,
# matching the convention used by clang_tool_chain.env_utils._TRUTHY_VALUES.
_ALWAYS_DEPLOY_TRUTHY = ("1", "true", "yes")


def _is_always_deploy_enabled() -> bool:
    """
    Check the CLANG_TOOL_CHAIN_ALWAYS_DEPLOY escape hatch.

    When set, SoDeployer.deploy_all() falls back to the old unconditional-copy
    behavior and skips the "is this soname already resolvable" check entirely.
    """
    return os.environ.get("CLANG_TOOL_CHAIN_ALWAYS_DEPLOY", "").strip().lower() in _ALWAYS_DEPLOY_TRUTHY


class SoDeployer(BaseLibraryDeployer):
    """
    Linux .so file deployment using readelf for detection.

    Features:
    - Uses readelf -d (safe, no execution)
    - Handles versioned symlinks (libfoo.so.1 -> libfoo.so.1.2.3)
    - Copies toolchain libraries (libc++, libunwind)
    - Excludes system libraries (glibc, libpthread)
    """

    # Libraries to deploy (LLVM toolchain libraries)
    DEPLOYABLE_PATTERNS = [
        r"libc\+\+\.so[.\d]*",
        r"libc\+\+abi\.so[.\d]*",
        r"libunwind\.so[.\d]*",
        r"libunwind-x86_64\.so[.\d]*",  # Platform-specific libunwind (bundled)
        r"libunwind-aarch64\.so[.\d]*",  # Platform-specific libunwind (bundled)
        r"libclang_rt\..*\.so",  # Sanitizer runtimes
    ]

    # System libraries to never deploy
    SYSTEM_LIBRARIES = {
        "libc.so.6",
        "libm.so.6",
        "libpthread.so.0",
        "libdl.so.2",
        "librt.so.1",
        "linux-vdso.so.1",
        "ld-linux-x86-64.so.2",
        "ld-linux-aarch64.so.1",
        "libgcc_s.so.1",  # Usually system-provided
    }

    # Pattern for RPATH/RUNPATH entries in `readelf -d` output, e.g.:
    #   0x000000000000000f (RPATH)              Library rpath: [/opt/foo/lib]
    #   0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/../lib:/opt/bar/lib]
    _RPATH_RUNPATH_PATTERN = re.compile(r"Library (?:rpath|runpath):\s*\[([^\]]*)\]")

    # Pattern for `ldconfig -p` cache lines, e.g.:
    #   \tlibfoo.so.1 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libfoo.so.1
    _LDCONFIG_LINE_PATTERN = re.compile(r"^\s*(\S+)\s*\([^)]*\)\s*=>\s*(.+)$")

    # Default trusted library directories consulted by the dynamic loader
    # when nothing more specific (RPATH/RUNPATH, LD_LIBRARY_PATH, ldconfig
    # cache) resolves the soname. See ld.so(8).
    _DEFAULT_TRUSTED_DIRS = ("/lib", "/lib64", "/usr/lib", "/usr/lib64")

    def __init__(self, arch: str = "x86_64"):
        """
        Initialize Linux .so deployer.

        Args:
            arch: Architecture ("x86_64", "arm64", "aarch64")
        """
        super().__init__("linux", arch)
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.DEPLOYABLE_PATTERNS]
        # Per-binary RPATH/RUNPATH directories, populated as a side effect of
        # detect_dependencies() so is_resolvable() never needs a second
        # `readelf` subprocess call.
        self._rpath_runpath_cache: dict[Path, list[Path]] = {}
        # Parsed `ldconfig -p` cache: soname -> resolved path. None means
        # "not built yet"; built at most once per deployer instance.
        self._ldconfig_cache: dict[str, Path] | None = None
        # Clang install root, resolved lazily. Directories under it never
        # count as "already resolvable" -- see is_resolvable().
        self._toolchain_root: Path | None = None
        self._toolchain_root_resolved = False

    def detect_dependencies(self, binary_path: Path) -> list[str]:
        """
        Detect .so dependencies using readelf -d.

        Algorithm:
        1. Run readelf -d <binary_path>
        2. Extract lines with (NEEDED)
        3. Parse library names from brackets: [libfoo.so.1]
        4. Return list of library names

        Args:
            binary_path: Path to executable or shared library

        Returns:
            List of library names (e.g., ["libc++.so.1", "libunwind.so.1"])

        Raises:
            subprocess.TimeoutExpired: If readelf times out (10s)
            subprocess.CalledProcessError: If readelf fails
        """
        try:
            result = subprocess.run(
                ["readelf", "-d", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            # Parse NEEDED entries
            # Format: 0x0000000000000001 (NEEDED) Shared library: [libc++.so.1]
            needed_pattern = re.compile(r"\(NEEDED\).*\[([^\]]+)\]")
            libraries = []

            for line in result.stdout.splitlines():
                match = needed_pattern.search(line)
                if match:
                    libraries.append(match.group(1))

            # Also parse RPATH/RUNPATH out of the same `readelf -d` output
            # (rather than issuing a second subprocess call) and cache it for
            # is_resolvable(). See _parse_rpath_runpath() for details.
            self._rpath_runpath_cache[binary_path] = self._parse_rpath_runpath(result.stdout, binary_path.parent)

            return libraries

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return []
        except subprocess.TimeoutExpired:
            self.logger.warning(f"readelf timed out on {binary_path}")
            return []
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"readelf failed: {e}")
            return []
        except FileNotFoundError:
            self.logger.warning("readelf not found - install binutils")
            return []

    def is_deployable_library(self, lib_name: str) -> bool:
        """
        Check if library should be deployed.

        Rules:
        - Exclude system libraries (glibc, libpthread, etc.)
        - Include toolchain libraries (libc++, libunwind, etc.)

        Args:
            lib_name: Library filename (e.g., "libc++.so.1")

        Returns:
            True if library should be copied, False if system library
        """
        # Exact match against system libraries
        if lib_name in self.SYSTEM_LIBRARIES:
            return False

        # Pattern match against deployable libraries
        return any(pattern.match(lib_name) for pattern in self._compiled_patterns)

    def _parse_rpath_runpath(self, readelf_output: str, binary_dir: Path) -> list[Path]:
        """
        Parse DT_RPATH / DT_RUNPATH directory lists out of `readelf -d` output.

        Real dynamic-loader search order: DT_RUNPATH is searched *after*
        LD_LIBRARY_PATH, while DT_RPATH is searched *before* it (and is only
        consulted at all when the binary has no DT_RUNPATH). For a simple
        "does this soname resolve at all" check, that relative ordering
        doesn't matter, so we just union both sets of directories here.

        $ORIGIN / ${ORIGIN} expand to the binary's own directory (binary_dir).
        $LIB/$PLATFORM (and their ${...} forms) are dynamic-linker
        substitutions that depend on the running system/ABI and can't be
        resolved statically here, so entries containing them are skipped.

        Args:
            readelf_output: stdout from `readelf -d <binary>`
            binary_dir: Directory containing the binary (for $ORIGIN expansion)

        Returns:
            List of directories, in encounter order, deduplicated.
        """
        dirs: list[Path] = []
        seen: set[str] = set()

        for match in self._RPATH_RUNPATH_PATTERN.finditer(readelf_output):
            for entry in match.group(1).split(":"):
                entry = entry.strip()
                if not entry:
                    continue
                if any(tag in entry for tag in ("$LIB", "${LIB}", "$PLATFORM", "${PLATFORM}")):
                    continue
                entry = entry.replace("${ORIGIN}", str(binary_dir)).replace("$ORIGIN", str(binary_dir))
                if entry in seen:
                    continue
                seen.add(entry)
                dirs.append(Path(entry))

        return dirs

    def _get_rpath_runpath_dirs(self, binary_path: Path) -> list[Path]:
        """
        Return the RPATH/RUNPATH directories for binary_path.

        Populated as a side effect of detect_dependencies(binary_path), which
        is always called before this during deploy_all()'s dependency scan.
        Returns an empty list if detect_dependencies() was never run for this
        exact path (we deliberately do not issue a fresh `readelf` call here).
        """
        return self._rpath_runpath_cache.get(binary_path, [])

    def _get_ld_library_path_dirs(self) -> list[Path]:
        """Return directories from the current LD_LIBRARY_PATH environment variable."""
        raw = os.environ.get("LD_LIBRARY_PATH", "")
        return [Path(entry) for entry in raw.split(os.pathsep) if entry]

    def _get_ldconfig_cache(self) -> dict[str, Path]:
        """
        Parse `ldconfig -p` once and cache the soname -> resolved path mapping.

        Never executes any binary being deployed -- only the system's own
        `ldconfig` tool, mirroring the module's "never executes the binary"
        stance. `ldconfig` missing entirely (e.g. NixOS, which does not ship
        it) or exiting non-zero is treated the same as an empty cache -- the
        resolvability check simply falls through to the trusted-directory
        check.

        Returns:
            Mapping of soname (e.g. "libfoo.so.1") to its resolved Path.
        """
        if self._ldconfig_cache is not None:
            return self._ldconfig_cache

        cache: dict[str, Path] = {}
        try:
            result = subprocess.run(
                ["ldconfig", "-p"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    match = self._LDCONFIG_LINE_PATTERN.match(line)
                    if match:
                        cache[match.group(1)] = Path(match.group(2).strip())
            else:
                self.logger.debug(f"ldconfig -p exited with status {result.returncode}")
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
        except subprocess.TimeoutExpired:
            self.logger.debug("ldconfig -p timed out")
        except FileNotFoundError:
            self.logger.debug("ldconfig not found (e.g. NixOS) - treating ldconfig cache as empty")

        self._ldconfig_cache = cache
        return cache

    def _get_trusted_dirs(self) -> list[Path]:
        """Return the default trusted library directories that exist on this system."""
        candidates = list(self._DEFAULT_TRUSTED_DIRS)
        if self.arch == "x86_64":
            candidates.append("/usr/lib/x86_64-linux-gnu")
        elif self.arch in ("arm64", "aarch64"):
            candidates.append("/usr/lib/aarch64-linux-gnu")

        return [Path(c) for c in candidates if Path(c).exists()]

    def is_resolvable(self, soname: str, binary_path: Path) -> Path | None:
        """
        Check whether `soname` would already resolve via the dynamic loader's
        normal search order, without copying anything and without executing
        `binary_path` (mirrors the module's "uses readelf, never executes the
        binary" stance -- this only ever runs `readelf`/`ldconfig`).

        IMPORTANT SEMANTICS CAVEAT: "resolvable on this machine" is NOT the
        same as "portable to another machine". If we skip deploying a library
        because it resolves here, the produced binary now depends on the
        *host* providing that library at runtime -- copying the binary to a
        machine without it will make it fail to load. This tradeoff is
        exactly what was requested in the GitHub issue this implements
        (request #2): "a check for 'is this soname already resolvable on
        this system' before deploying would make [--deploy-dependencies] a
        no-op where it should be one."

        Search order (mirrors ld.so(8)):
        1. DT_RPATH / DT_RUNPATH embedded in binary_path
        2. LD_LIBRARY_PATH directories
        3. The ldconfig cache (`ldconfig -p`)
        4. Default trusted directories (/lib, /lib64, /usr/lib, /usr/lib64,
           and the arch-specific multiarch directory)

        Directories inside the toolchain install root are deliberately NOT
        counted as resolvable. The toolchain stamps ``-Wl,-rpath,<clang_root>/lib``
        (and the compiler-rt lib dir) into every binary it links, so without
        this exclusion every toolchain-provided library -- libunwind,
        libclang_rt.asan.so -- would look "already resolvable" and never be
        deployed. That would leave the shipped binary depending on
        ``~/.clang-tool-chain`` existing on the target machine, which is
        precisely what --deploy-dependencies exists to avoid.

        Args:
            soname: Library filename to check (e.g. "libc++.so.1")
            binary_path: The binary whose RPATH/RUNPATH should be consulted

        Returns:
            Path to the resolved library if it would already be found by the
            dynamic loader, None otherwise.
        """
        for directory in self._get_rpath_runpath_dirs(binary_path):
            if self._is_toolchain_dir(directory):
                continue
            candidate = directory / soname
            if candidate.is_file():
                return candidate

        for directory in self._get_ld_library_path_dirs():
            if self._is_toolchain_dir(directory):
                continue
            candidate = directory / soname
            if candidate.is_file():
                return candidate

        cached = self._get_ldconfig_cache().get(soname)
        if cached is not None and cached.is_file() and not self._is_toolchain_dir(cached.parent):
            return cached

        for directory in self._get_trusted_dirs():
            candidate = directory / soname
            if candidate.is_file():
                return candidate

        return None

    def _get_toolchain_root(self) -> Path | None:
        """Return the clang install root, or None when it cannot be determined."""
        if self._toolchain_root_resolved:
            return self._toolchain_root

        root: Path | None = None
        try:
            from clang_tool_chain.platform.detection import get_platform_binary_dir

            root = get_platform_binary_dir().parent.resolve()
        except Exception as e:  # pragma: no cover - defensive
            self.logger.debug(f"Could not determine toolchain root: {e}")

        self._toolchain_root = root
        self._toolchain_root_resolved = True
        return root

    def _is_toolchain_dir(self, directory: Path) -> bool:
        """True when `directory` lives inside the clang toolchain install root."""
        root = self._get_toolchain_root()
        if root is None:
            return False
        try:
            resolved = directory.resolve()
        except OSError:  # pragma: no cover - defensive
            return False
        return resolved == root or root in resolved.parents

    def find_library_in_toolchain(self, lib_name: str) -> Path | None:
        """
        Search for .so file in toolchain and system paths.

        Search order:
        1. Clang compiler-rt directory (lib/clang/<version>/lib/<target>/) - for sanitizer runtimes
        2. Clang toolchain lib directory
        3. /usr/local/lib (user installs)
        4. /usr/lib/<arch> (system libs, filtered)
        5. Resolve symlinks to real files

        Args:
            lib_name: Library filename to locate

        Returns:
            Path to actual .so file (not symlink), None if not found
        """
        try:
            from clang_tool_chain.platform.detection import get_platform_binary_dir

            clang_bin = get_platform_binary_dir()
            clang_root = clang_bin.parent
            clang_lib = clang_root / "lib"

            # Architecture-specific lib directory
            if self.arch == "x86_64":
                arch_lib_dir = "x86_64-linux-gnu"
                compiler_rt_targets = ["x86_64-unknown-linux-gnu", "linux"]
            elif self.arch == "arm64" or self.arch == "aarch64":
                arch_lib_dir = "aarch64-linux-gnu"
                compiler_rt_targets = ["aarch64-unknown-linux-gnu", "linux"]
            else:
                arch_lib_dir = self.arch
                compiler_rt_targets = ["linux"]

            search_paths: list[Path] = []

            # Search compiler-rt directories first (for sanitizer runtimes like libclang_rt.asan.so)
            # Path pattern: lib/clang/<version>/lib/<target>/
            clang_version_dir = clang_lib / "clang"
            if clang_version_dir.exists():
                for version_dir in clang_version_dir.iterdir():
                    if version_dir.is_dir():
                        for target in compiler_rt_targets:
                            rt_lib_dir = version_dir / "lib" / target
                            if rt_lib_dir.exists():
                                search_paths.append(rt_lib_dir)

            # Then search standard lib directories
            search_paths.extend(
                [
                    clang_lib,
                    Path("/usr/local/lib"),
                    Path(f"/usr/lib/{arch_lib_dir}"),
                    Path("/usr/lib"),
                ]
            )

            for search_dir in search_paths:
                if not search_dir.exists():
                    continue

                lib_path = search_dir / lib_name
                if lib_path.exists():
                    # Resolve symlink to actual file
                    resolved = lib_path.resolve()
                    if resolved.exists():
                        return resolved

                # For sanitizer runtimes, try architecture-suffixed variants
                # e.g., libclang_rt.asan.so -> libclang_rt.asan-x86_64.so
                if lib_name.startswith("libclang_rt.") and lib_name.endswith(".so"):
                    base_name = lib_name[:-3]  # Remove .so
                    arch_suffixes = ["-x86_64", "-aarch64", "-arm64"]
                    for suffix in arch_suffixes:
                        arch_lib_path = search_dir / f"{base_name}{suffix}.so"
                        if arch_lib_path.exists():
                            resolved = arch_lib_path.resolve()
                            if resolved.exists():
                                self.logger.debug(f"Found architecture-suffixed variant: {arch_lib_path}")
                                return resolved

            return None

        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return None
        except Exception as e:
            self.logger.debug(f"Error searching for {lib_name}: {e}")
            return None

    def get_library_extension(self) -> str:
        """
        Return platform-specific library extension.

        Returns:
            ".so" for Linux
        """
        return ".so"

    def deploy_library(self, lib_name: str, output_dir: Path) -> bool:
        """
        Deploy .so file and create necessary symlinks.

        For versioned libraries (libfoo.so.1.2.3):
        1. Copy actual library file
        2. Create SONAME symlink (libfoo.so.1 -> libfoo.so.1.2.3)

        Args:
            lib_name: Library filename to deploy
            output_dir: Directory containing the executable

        Returns:
            True if library was deployed, False if skipped/failed
        """
        src_path = self.find_library_in_toolchain(lib_name)
        if src_path is None:
            self.logger.warning(f"Library not found: {lib_name}")
            return False

        # Deploy main file
        dest_path = output_dir / src_path.name
        try:
            was_deployed = self._atomic_copy(src_path, dest_path)
        except KeyboardInterrupt as ke:
            handle_keyboard_interrupt_properly(ke)
            return False
        except Exception as e:
            self.logger.warning(f"Failed to deploy {lib_name}: {e}")
            return False

        # Create symlinks if needed
        # Example: libfoo.so.1 (lib_name) -> libfoo.so.1.2.3 (src_path.name)
        if src_path.name != lib_name:
            symlink_path = output_dir / lib_name
            if not symlink_path.exists():
                try:
                    # Create relative symlink
                    symlink_path.symlink_to(src_path.name)
                    self.logger.debug(f"Created symlink: {lib_name} -> {src_path.name}")
                except KeyboardInterrupt as ke:
                    handle_keyboard_interrupt_properly(ke)
                except OSError as e:
                    self.logger.debug(f"Failed to create symlink: {e}")

        return was_deployed

    def deploy_all(self, binary_path: Path) -> int:
        """
        Main deployment orchestrator for Linux .so files.

        Overrides BaseLibraryDeployer.deploy_all() to add a resolvability
        check: before copying a dependency, ask is_resolvable() whether the
        dynamic loader would already find that soname on this system
        (RPATH/RUNPATH, LD_LIBRARY_PATH, the ldconfig cache, or the default
        trusted directories). If so, the copy is skipped -- see
        is_resolvable() for the "resolvable here != portable elsewhere"
        caveat. Set CLANG_TOOL_CHAIN_ALWAYS_DEPLOY=1 to restore the old
        unconditional-copy behavior.

        Args:
            binary_path: Path to executable or shared library

        Returns:
            Number of libraries successfully deployed (copies skipped as
            "already resolvable" are not counted).
        """
        output_dir = binary_path.parent

        # Detect all dependencies (also populates the RPATH/RUNPATH cache for
        # binary_path as a side effect of detect_dependencies()).
        dependencies = self.detect_all_dependencies(binary_path, recursive=True)

        if not dependencies:
            self.logger.debug("No deployable dependencies found")
            return 0

        always_deploy = _is_always_deploy_enabled()

        deployed_count = 0
        for lib_name in dependencies:
            if not always_deploy:
                resolved = self.is_resolvable(lib_name, binary_path)
                if resolved is not None:
                    self.logger.info(
                        f"Skipping {lib_name}: already resolvable at {resolved} "
                        "(set CLANG_TOOL_CHAIN_ALWAYS_DEPLOY=1 to copy anyway)"
                    )
                    continue

            if self.deploy_library(lib_name, output_dir):
                deployed_count += 1

        # Summary logging
        if deployed_count > 0:
            self.logger.info(
                f"Deployed {deployed_count} shared librar{'y' if deployed_count == 1 else 'ies'} for {binary_path.name}"
            )

        return deployed_count


def detect_required_so_files(
    exe_path: Path,
    arch: str = "x86_64",
    recursive: bool = True,
) -> list[str]:
    """
    Detect required .so files for a Linux executable.

    This is a convenience wrapper function that maintains API compatibility
    with the Windows DLL deployment module.

    Args:
        exe_path: Path to executable or shared library
        arch: Architecture ("x86_64", "arm64", "aarch64")
        recursive: If True, scan transitive dependencies

    Returns:
        List of .so filenames to deploy
    """
    deployer = SoDeployer(arch)
    return list(deployer.detect_all_dependencies(exe_path, recursive=recursive))


def post_link_so_deployment(
    output_path: Path,
    arch: str = "x86_64",
) -> int:
    """
    Deploy required .so files after linking (post-link hook).

    This function is called by execution/core.py after successful linking.

    Args:
        output_path: Path to the linked executable or shared library
        arch: Architecture ("x86_64", "arm64", "aarch64")

    Returns:
        Number of .so files deployed

    Environment Variables:
        CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS: Set to "1" to disable all library deployment
        CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB: Set to "1" to disable deployment for shared library outputs
        CLANG_TOOL_CHAIN_NO_AUTO: Set to "1" to disable all automatic features
    """
    # Check environment variables (NO_DEPLOY_LIBS or NO_AUTO)
    if is_feature_disabled("DEPLOY_LIBS"):
        return 0

    # Check if output is a shared library (.so) - if so, check NO_DEPLOY_SHARED_LIB
    is_shared_lib = output_path.suffix == ".so" or ".so." in output_path.name
    if is_shared_lib and is_feature_disabled("DEPLOY_SHARED_LIB"):
        return 0

    # Check if output is a deployable binary
    if not output_path.exists():
        logger.debug(f"Output file does not exist: {output_path}")
        return 0

    # Check file extension (.so or executable)
    is_shared_lib = output_path.suffix == ".so" or ".so." in output_path.name
    is_executable = output_path.is_file() and os.access(output_path, os.X_OK)

    if not is_shared_lib and not is_executable:
        logger.debug(f"Output is not an executable or .so: {output_path}")
        return 0

    # Deploy dependencies
    deployer = SoDeployer(arch)
    try:
        return deployer.deploy_all(output_path)
    except KeyboardInterrupt as ke:
        handle_keyboard_interrupt_properly(ke)
        return 0
    except Exception as e:
        logger.warning(f"Linux .so deployment failed: {e}")
        return 0
