# Shared Library Deployment Architecture Design

**Phase 2 Design Document**
**Author**: Agent 2.1 (Architecture Design)
**Date**: 2026-01-25
**Status**: Complete

This document provides comprehensive architecture design for implementing automatic shared library deployment on Linux and macOS, extending the existing Windows DLL deployment feature.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Principles](#design-principles)
3. [Architecture Overview](#architecture-overview)
4. [Class Hierarchy](#class-hierarchy)
5. [Platform-Specific Implementations](#platform-specific-implementations)
6. [Integration Points](#integration-points)
7. [API Design](#api-design)
8. [Environment Variables](#environment-variables)
9. [Error Handling Strategy](#error-handling-strategy)
10. [Performance Considerations](#performance-considerations)
11. [Testing Strategy](#testing-strategy)
12. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

### Objective

Port the Windows DLL deployment feature to Linux (`.so` files) and macOS (`.dylib` files), enabling automatic shared library deployment for executables and shared libraries built with clang-tool-chain.

### Key Features

- **Linux**: Detect `.so` dependencies using `readelf`, copy to executable directory, handle symlinks
- **macOS**: Detect `.dylib` dependencies using `otool`, copy to executable directory, fix paths with `install_name_tool`
- **Cross-platform**: Abstract base class for common deployment logic
- **Opt-in**: Use `--deploy-dependencies` flag (conservative approach)
- **Non-fatal**: Warnings only, never fails builds
- **Fast**: <150ms overhead per executable

### Success Criteria

1. **Functional**: Executables run without LD_LIBRARY_PATH/DYLD_LIBRARY_PATH setup
2. **Performance**: <150ms deployment overhead (similar to Windows <100ms)
3. **Compatibility**: All Windows tests pass unchanged
4. **Coverage**: >90% test coverage for new code
5. **Documentation**: User-facing docs and maintainer guides

---

## Design Principles

### 1. Consistency with Windows DLL Deployment

**Rationale**: Users expect uniform behavior across platforms.

**Implementation**:
- Same environment variable patterns (`NO_DEPLOY_*`, `*_VERBOSE`)
- Same logging levels (INFO/DEBUG/WARNING)
- Same non-fatal error handling
- Same timestamp optimization
- Same recursive dependency scanning

### 2. Platform Abstraction

**Rationale**: Minimize code duplication, maximize reusability.

**Implementation**:
- Abstract base class (`BaseLibraryDeployer`) with common logic
- Platform-specific subclasses override detection/deployment methods
- Factory pattern for runtime platform selection

### 3. Conservative Defaults

**Rationale**: Linux/macOS users rely on system package managers.

**Implementation**:
- **Opt-in** deployment via `--deploy-dependencies` flag
- Can be changed to automatic in future releases based on user feedback
- Clear documentation explaining when to use

### 4. Non-Fatal Operation

**Rationale**: Deployment is convenience, not requirement.

**Implementation**:
- All exceptions caught and logged as warnings
- Build succeeds even if deployment fails
- Users can manually set library paths if needed

### 5. Security-First Design

**Rationale**: Avoid library hijacking vulnerabilities.

**Implementation**:
- Never copy system libraries (glibc, libSystem)
- Only copy toolchain-provided libraries
- Set restrictive file permissions (644)
- Log all deployment actions for audit trail

---

## Architecture Overview

### High-Level Flow

```
┌─────────────────────────────────────────────────────────┐
│              Compilation & Linking                      │
│  clang++ -o program program.cpp --deploy-dependencies   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│            execution/core.py (Post-Link Hook)           │
│                                                          │
│  if returncode == 0 and deploy_dependencies_requested:  │
│      DeploymentFactory.create_deployer(platform)        │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              BaseLibraryDeployer (ABC)                  │
│                                                          │
│  1. detect_dependencies()  [abstract]                   │
│  2. filter_deployable()     [abstract]                  │
│  3. find_library()          [abstract]                  │
│  4. deploy_library()        [common]                    │
│  5. recursive_scan()        [common]                    │
└─────────────────────────────────────────────────────────┘
           ↓               ↓               ↓
┌─────────────┐  ┌──────────────┐  ┌─────────────────┐
│ DllDeployer │  │ SoDeployer   │  │ DylibDeployer   │
│ (Windows)   │  │ (Linux)      │  │ (macOS)         │
│             │  │              │  │                 │
│ llvm-objdump│  │ readelf -d   │  │ otool -L        │
│ .dll files  │  │ .so files    │  │ .dylib files    │
│ MinGW DLLs  │  │ libc++, etc. │  │ @rpath, etc.    │
└─────────────┘  └──────────────┘  └─────────────────┘
```

### Module Structure

```
src/clang_tool_chain/deployment/
├── __init__.py
├── base_deployer.py       (NEW: Abstract base class)
├── dll_deployer.py        (REFACTOR: Inherit from BaseLibraryDeployer)
├── so_deployer.py         (NEW: Linux .so deployment)
├── dylib_deployer.py      (NEW: macOS .dylib deployment)
└── factory.py             (NEW: Platform selection factory)

tests/
├── test_dll_deployment.py    (EXISTING: Windows tests, 38 tests)
├── test_so_deployment.py     (NEW: Linux tests, mirror Windows structure)
├── test_dylib_deployment.py  (NEW: macOS tests, mirror Windows structure)
└── test_deployment_factory.py (NEW: Factory pattern tests)
```

---

## Class Hierarchy

### Base Class: `BaseLibraryDeployer`

**Purpose**: Provides common deployment logic shared across all platforms.

**Location**: `src/clang_tool_chain/deployment/base_deployer.py`

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Set, List, Optional
import logging

class BaseLibraryDeployer(ABC):
    """
    Abstract base class for platform-specific library deployment.

    Provides common deployment logic:
    - Recursive dependency scanning
    - Timestamp-based copy optimization
    - Atomic file deployment (hard link + fallback)
    - Non-fatal error handling

    Platform-specific subclasses must implement:
    - detect_dependencies() - Extract library names from binary
    - is_deployable_library() - Filter system vs deployable libraries
    - find_library_in_toolchain() - Locate library source files
    - get_library_extension() - Return platform library extension
    """

    def __init__(self, platform_name: str, arch: str):
        self.platform_name = platform_name
        self.arch = arch
        self.logger = logging.getLogger(__name__)

    # ===== ABSTRACT METHODS (must be implemented by subclasses) =====

    @abstractmethod
    def detect_dependencies(self, binary_path: Path) -> List[str]:
        """
        Detect direct library dependencies of a binary.

        Platform-specific implementations:
        - Windows: llvm-objdump -p (PE import table)
        - Linux: readelf -d (ELF NEEDED entries)
        - macOS: otool -L (Mach-O load commands)

        Args:
            binary_path: Path to executable or shared library

        Returns:
            List of library names (e.g., ["libc++.so.1", "libunwind.so.1"])

        Raises:
            subprocess.TimeoutExpired: If detection tool times out
            subprocess.CalledProcessError: If detection tool fails
        """
        pass

    @abstractmethod
    def is_deployable_library(self, lib_name: str) -> bool:
        """
        Check if a library should be deployed.

        Platform-specific filtering:
        - Windows: Include MinGW/sanitizer DLLs, exclude system DLLs
        - Linux: Include libc++/libunwind, exclude glibc/libpthread
        - macOS: Include custom dylibs, exclude libSystem/frameworks

        Args:
            lib_name: Library filename (e.g., "libc++.so.1")

        Returns:
            True if library should be copied, False if system library
        """
        pass

    @abstractmethod
    def find_library_in_toolchain(self, lib_name: str) -> Optional[Path]:
        """
        Locate library file in toolchain directories.

        Platform-specific search paths:
        - Windows: MinGW sysroot/bin, clang/bin
        - Linux: clang/lib, /usr/lib, /usr/local/lib
        - macOS: clang/lib, /usr/local/lib, Homebrew paths

        Args:
            lib_name: Library filename to locate

        Returns:
            Path to library file if found, None otherwise
        """
        pass

    @abstractmethod
    def get_library_extension(self) -> str:
        """
        Return platform-specific library extension.

        Returns:
            ".dll" (Windows), ".so" (Linux), ".dylib" (macOS)
        """
        pass

    # ===== COMMON METHODS (inherited by all subclasses) =====

    def detect_all_dependencies(
        self,
        binary_path: Path,
        recursive: bool = True
    ) -> Set[str]:
        """
        Detect all dependencies (direct + transitive if recursive=True).

        Uses breadth-first traversal to find transitive dependencies:
        1. Detect direct dependencies of binary_path
        2. For each dependency, detect its dependencies (if deployable)
        3. Continue until no new dependencies found
        4. Return deduplicated set

        Args:
            binary_path: Path to executable or shared library
            recursive: If True, scan transitive dependencies

        Returns:
            Set of all deployable library names
        """
        all_deps: Set[str] = set()
        to_scan: List[str] = []
        scanned: Set[str] = set()

        # Detect direct dependencies
        try:
            direct_deps = self.detect_dependencies(binary_path)
            for dep in direct_deps:
                if self.is_deployable_library(dep):
                    all_deps.add(dep)
                    if recursive:
                        to_scan.append(dep)
        except Exception as e:
            self.logger.warning(f"Failed to detect dependencies: {e}")
            return set()

        # Recursive scan
        if recursive:
            while to_scan:
                current = to_scan.pop(0)
                if current in scanned:
                    continue
                scanned.add(current)

                # Find library in toolchain
                lib_path = self.find_library_in_toolchain(current)
                if lib_path is None:
                    self.logger.debug(f"Library not found in toolchain: {current}")
                    continue

                # Detect transitive dependencies
                try:
                    transitive = self.detect_dependencies(lib_path)
                    for dep in transitive:
                        if self.is_deployable_library(dep) and dep not in all_deps:
                            all_deps.add(dep)
                            to_scan.append(dep)
                except Exception as e:
                    self.logger.debug(f"Failed to scan {current}: {e}")
                    continue

        return all_deps

    def _should_copy(self, src: Path, dest: Path) -> bool:
        """
        Check if file should be copied based on timestamps.

        Args:
            src: Source file path
            dest: Destination file path

        Returns:
            True if dest doesn't exist or src is newer, False otherwise
        """
        if not dest.exists():
            return True

        src_mtime = src.stat().st_mtime
        dest_mtime = dest.stat().st_mtime

        if src_mtime <= dest_mtime:
            self.logger.debug(f"Skipped (up-to-date): {dest.name}")
            return False

        return True

    def _atomic_copy(self, src: Path, dest: Path) -> bool:
        """
        Atomically copy file using hard link (preferred) or copy + rename.

        Algorithm:
        1. Check timestamp - skip if dest is up-to-date
        2. Try hard link (zero disk space, instant)
        3. Fallback to copy + atomic rename
        4. Handle race conditions (concurrent builds)

        Args:
            src: Source file path
            dest: Destination file path

        Returns:
            True if file was copied/linked, False if skipped

        Raises:
            OSError: If copy fails (other than race condition)
        """
        import os
        import shutil
        import uuid

        # Timestamp check
        if not self._should_copy(src, dest):
            return False

        # Remove outdated destination
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass  # Will fail later if removal required

        # Try hard link
        try:
            os.link(src, dest)
            self.logger.debug(f"Deployed (hard link): {dest.name}")
            return True
        except (OSError, NotImplementedError):
            pass  # Fall back to copy

        # Fallback: copy to temp + atomic rename
        temp_name = f".{dest.name}.{uuid.uuid4().hex[:8]}.tmp"
        temp_path = dest.parent / temp_name

        try:
            shutil.copy2(src, temp_path)
            temp_stat = temp_path.stat()

            # Atomic rename
            if os.name == "nt":
                temp_path.replace(dest)  # Windows atomic replace
            else:
                temp_path.rename(dest)   # POSIX atomic rename

            self.logger.debug(f"Deployed (copy): {dest.name}")
            return True

        except FileExistsError:
            # Race condition: another process deployed it
            temp_path.unlink(missing_ok=True)
            return False

        except OSError as e:
            # Check if files are same size (concurrent write)
            if dest.exists():
                dest_stat = dest.stat()
                if temp_stat.st_size == dest_stat.st_size:
                    temp_path.unlink(missing_ok=True)
                    return False
            raise

        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def deploy_library(self, lib_name: str, output_dir: Path) -> bool:
        """
        Deploy a single library to output directory.

        Args:
            lib_name: Library filename to deploy
            output_dir: Directory containing the executable

        Returns:
            True if library was deployed, False if skipped/failed
        """
        # Find library in toolchain
        src_path = self.find_library_in_toolchain(lib_name)
        if src_path is None:
            self.logger.warning(f"Library not found: {lib_name}")
            return False

        # Deploy to output directory
        dest_path = output_dir / lib_name

        try:
            was_deployed = self._atomic_copy(src_path, dest_path)
            return was_deployed
        except Exception as e:
            self.logger.warning(f"Failed to deploy {lib_name}: {e}")
            return False

    def deploy_all(self, binary_path: Path) -> int:
        """
        Main deployment orchestrator.

        Detects all dependencies (direct + transitive) and deploys them
        to the directory containing binary_path.

        Args:
            binary_path: Path to executable or shared library

        Returns:
            Number of libraries successfully deployed
        """
        output_dir = binary_path.parent

        # Detect all dependencies
        dependencies = self.detect_all_dependencies(binary_path, recursive=True)

        if not dependencies:
            self.logger.debug("No deployable dependencies found")
            return 0

        # Deploy each library
        deployed_count = 0
        for lib_name in dependencies:
            if self.deploy_library(lib_name, output_dir):
                deployed_count += 1

        # Summary logging
        if deployed_count > 0:
            self.logger.info(
                f"Deployed {deployed_count} shared librar{'y' if deployed_count == 1 else 'ies'} "
                f"for {binary_path.name}"
            )

        return deployed_count
```

### Rationale for Base Class Design

1. **Template Method Pattern**: `deploy_all()` defines the deployment workflow, subclasses implement platform-specific steps
2. **Single Responsibility**: Each method has one clear purpose
3. **Open/Closed Principle**: Base class is closed for modification, open for extension via abstract methods
4. **DRY**: Timestamp checking, atomic copy, recursive scanning shared across platforms
5. **Testability**: Each method can be unit tested independently

---

## Platform-Specific Implementations

### Linux: `SoDeployer`

**Location**: `src/clang_tool_chain/deployment/so_deployer.py`

```python
import subprocess
import re
from pathlib import Path
from typing import List, Optional, Set
from .base_deployer import BaseLibraryDeployer

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
        r"libclang_rt\..*\.so",  # Sanitizer runtimes
    ]

    # System libraries to never deploy
    SYSTEM_LIBRARIES = {
        "libc.so.6", "libm.so.6", "libpthread.so.0",
        "libdl.so.2", "librt.so.1", "linux-vdso.so.1",
        "ld-linux-x86-64.so.2", "ld-linux-aarch64.so.1",
        "libgcc_s.so.1",  # Usually system-provided
    }

    def __init__(self, arch: str = "x86_64"):
        super().__init__("linux", arch)
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DEPLOYABLE_PATTERNS
        ]

    def detect_dependencies(self, binary_path: Path) -> List[str]:
        """
        Detect .so dependencies using readelf -d.

        Algorithm:
        1. Run readelf -d <binary_path>
        2. Extract lines with (NEEDED)
        3. Parse library names from brackets: [libfoo.so.1]
        4. Return list of library names

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
                check=True
            )

            # Parse NEEDED entries
            # Format: 0x0000000000000001 (NEEDED) Shared library: [libc++.so.1]
            needed_pattern = re.compile(r"\(NEEDED\).*\[([^\]]+)\]")
            libraries = []

            for line in result.stdout.splitlines():
                match = needed_pattern.search(line)
                if match:
                    libraries.append(match.group(1))

            return libraries

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
        """
        # Exact match against system libraries
        if lib_name in self.SYSTEM_LIBRARIES:
            return False

        # Pattern match against deployable libraries
        for pattern in self._compiled_patterns:
            if pattern.match(lib_name):
                return True

        return False

    def find_library_in_toolchain(self, lib_name: str) -> Optional[Path]:
        """
        Search for .so file in toolchain and system paths.

        Search order:
        1. Clang toolchain lib directory
        2. /usr/local/lib (user installs)
        3. /usr/lib/<arch> (system libs, filtered)
        4. Resolve symlinks to real files

        Returns:
            Path to actual .so file (not symlink)
        """
        from clang_tool_chain.platform_info import get_platform_binary_dir

        clang_bin = get_platform_binary_dir()
        clang_lib = clang_bin.parent / "lib"

        # Architecture-specific lib directory
        if self.arch == "x86_64":
            arch_lib_dir = "x86_64-linux-gnu"
        elif self.arch == "arm64" or self.arch == "aarch64":
            arch_lib_dir = "aarch64-linux-gnu"
        else:
            arch_lib_dir = self.arch

        search_paths = [
            clang_lib,
            Path("/usr/local/lib"),
            Path(f"/usr/lib/{arch_lib_dir}"),
            Path("/usr/lib"),
        ]

        for search_dir in search_paths:
            if not search_dir.exists():
                continue

            lib_path = search_dir / lib_name
            if lib_path.exists():
                # Resolve symlink to actual file
                resolved = lib_path.resolve()
                if resolved.exists():
                    return resolved

        return None

    def get_library_extension(self) -> str:
        return ".so"

    def deploy_library(self, lib_name: str, output_dir: Path) -> bool:
        """
        Deploy .so file and create necessary symlinks.

        For versioned libraries (libfoo.so.1.2.3):
        1. Copy actual library file
        2. Create SONAME symlink (libfoo.so.1 -> libfoo.so.1.2.3)
        3. Optionally create dev symlink (libfoo.so -> libfoo.so.1)
        """
        src_path = self.find_library_in_toolchain(lib_name)
        if src_path is None:
            self.logger.warning(f"Library not found: {lib_name}")
            return False

        # Deploy main file
        dest_path = output_dir / src_path.name
        try:
            was_deployed = self._atomic_copy(src_path, dest_path)
        except Exception as e:
            self.logger.warning(f"Failed to deploy {lib_name}: {e}")
            return False

        # Create symlinks if needed
        # Example: libfoo.so.1 (lib_name) -> libfoo.so.1.2.3 (src_path.name)
        if src_path.name != lib_name:
            symlink_path = output_dir / lib_name
            if not symlink_path.exists():
                try:
                    symlink_path.symlink_to(src_path.name)
                    self.logger.debug(f"Created symlink: {lib_name} -> {src_path.name}")
                except OSError as e:
                    self.logger.debug(f"Failed to create symlink: {e}")

        return was_deployed
```

### macOS: `DylibDeployer`

**Location**: `src/clang_tool_chain/deployment/dylib_deployer.py`

```python
import subprocess
import re
from pathlib import Path
from typing import List, Optional
from .base_deployer import BaseLibraryDeployer

class DylibDeployer(BaseLibraryDeployer):
    """
    macOS .dylib deployment using otool for detection.

    Features:
    - Uses otool -L for dependency detection
    - Handles @rpath, @loader_path, @executable_path
    - Modifies install names with install_name_tool
    - Re-signs binaries after modifications
    """

    # Libraries to deploy
    DEPLOYABLE_PATTERNS = [
        r"libc\+\+\.\d+\.dylib",
        r"libc\+\+abi\.\d+\.dylib",
        r"libunwind\.\d+\.dylib",
        r"libclang_rt\..*\.dylib",  # Sanitizer runtimes
    ]

    # System libraries/frameworks to never deploy
    SYSTEM_PATHS = [
        "/usr/lib/",
        "/System/Library/",
    ]

    def __init__(self, arch: str = "x86_64"):
        super().__init__("darwin", arch)
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DEPLOYABLE_PATTERNS
        ]

    def detect_dependencies(self, binary_path: Path) -> List[str]:
        """
        Detect .dylib dependencies using otool -L.

        Algorithm:
        1. Run otool -L <binary_path>
        2. Skip first line (binary's own install name)
        3. Parse each line: "\t/path/to/lib.dylib (compatibility...)"
        4. Extract library paths

        Returns:
            List of library paths (may include @rpath, absolute paths, etc.)
        """
        try:
            result = subprocess.run(
                ["otool", "-L", str(binary_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )

            lines = result.stdout.strip().split('\n')
            dependencies = []

            # Skip first line (binary's own install name)
            for line in lines[1:]:
                # Format: "\t/path/to/lib.dylib (compatibility version X, current version Y)"
                parts = line.strip().split(' ')
                if parts:
                    lib_path = parts[0]
                    dependencies.append(lib_path)

            return dependencies

        except subprocess.TimeoutExpired:
            self.logger.warning(f"otool timed out on {binary_path}")
            return []
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"otool failed: {e}")
            return []
        except FileNotFoundError:
            self.logger.warning("otool not found - install Xcode Command Line Tools")
            return []

    def is_deployable_library(self, lib_path: str) -> bool:
        """
        Check if dylib should be deployed.

        Rules:
        - Exclude /usr/lib/* (system libraries)
        - Exclude /System/Library/* (frameworks)
        - Include @rpath/* (needs resolution)
        - Include /usr/local/lib/* (Homebrew/custom builds)
        """
        # System paths
        for sys_path in self.SYSTEM_PATHS:
            if lib_path.startswith(sys_path):
                # Exception: libunwind is part of libSystem
                if "libunwind" in lib_path and lib_path.startswith("/usr/lib/"):
                    return False
                return False

        # @rpath or custom paths
        if lib_path.startswith("@rpath") or lib_path.startswith("/usr/local"):
            # Check if matches deployable patterns
            lib_name = Path(lib_path).name
            for pattern in self._compiled_patterns:
                if pattern.match(lib_name):
                    return True

        return False

    def find_library_in_toolchain(self, lib_path: str) -> Optional[Path]:
        """
        Locate dylib file, resolving @rpath if needed.

        Search order:
        1. If absolute path, check if exists
        2. If @rpath, search in toolchain lib
        3. Search /usr/local/lib (Homebrew)
        4. Search /opt/homebrew/lib (ARM Homebrew)

        Returns:
            Resolved path to .dylib file
        """
        from clang_tool_chain.platform_info import get_platform_binary_dir

        # Extract library name
        if lib_path.startswith("@rpath/"):
            lib_name = lib_path[7:]  # Remove "@rpath/"
        elif lib_path.startswith("@loader_path/"):
            lib_name = lib_path[13:]  # Remove "@loader_path/"
        else:
            # Absolute path
            path = Path(lib_path)
            if path.exists():
                return path.resolve()
            lib_name = path.name

        # Search paths
        clang_bin = get_platform_binary_dir()
        clang_lib = clang_bin.parent / "lib"

        search_paths = [
            clang_lib,
            Path("/usr/local/lib"),
            Path("/opt/homebrew/lib"),  # ARM macOS
            Path("/opt/local/lib"),     # MacPorts
        ]

        for search_dir in search_paths:
            if not search_dir.exists():
                continue

            lib_path_obj = search_dir / lib_name
            if lib_path_obj.exists():
                return lib_path_obj.resolve()

        return None

    def get_library_extension(self) -> str:
        return ".dylib"

    def _fix_install_name(self, binary_path: Path, old_path: str, new_path: str):
        """
        Fix dylib path using install_name_tool.

        Changes dependency path from old_path to new_path in binary_path.
        """
        try:
            subprocess.run(
                ["install_name_tool", "-change", old_path, new_path, str(binary_path)],
                check=True,
                capture_output=True
            )
            self.logger.debug(f"Fixed path: {old_path} -> {new_path}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"install_name_tool failed: {e}")
        except FileNotFoundError:
            self.logger.warning("install_name_tool not found")

    def _resign_binary(self, binary_path: Path):
        """
        Re-sign binary after install_name_tool modifications.

        Uses ad-hoc signing (-s -) for testing/development.
        """
        try:
            subprocess.run(
                ["codesign", "-s", "-", "--force", str(binary_path)],
                check=True,
                capture_output=True
            )
            self.logger.debug(f"Re-signed: {binary_path.name}")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Code signing failed: {e}")
        except FileNotFoundError:
            self.logger.debug("codesign not found - signature invalid")

    def deploy_library(self, lib_path: str, output_dir: Path) -> bool:
        """
        Deploy .dylib and fix install names.

        Steps:
        1. Find dylib in toolchain
        2. Copy to output directory
        3. Fix dylib's install name to @loader_path
        4. Fix executable's reference to @loader_path
        5. Re-sign both files
        """
        src_path = self.find_library_in_toolchain(lib_path)
        if src_path is None:
            self.logger.warning(f"Library not found: {lib_path}")
            return False

        lib_name = src_path.name
        dest_path = output_dir / lib_name

        # Copy dylib
        try:
            was_deployed = self._atomic_copy(src_path, dest_path)
        except Exception as e:
            self.logger.warning(f"Failed to deploy {lib_name}: {e}")
            return False

        # Fix dylib's install name
        if was_deployed:
            self._fix_install_name(dest_path, str(src_path), f"@loader_path/{lib_name}")
            self._resign_binary(dest_path)

        return was_deployed

    def deploy_all(self, binary_path: Path) -> int:
        """
        Deploy dylibs and fix executable's references.

        Overrides base class to add install_name_tool fixes.
        """
        output_dir = binary_path.parent

        # Detect dependencies
        dependencies = self.detect_all_dependencies(binary_path, recursive=True)

        if not dependencies:
            self.logger.debug("No deployable dependencies found")
            return 0

        # Deploy each library and collect original paths
        deployed_count = 0
        deployed_libs = []  # [(original_path, new_name), ...]

        for lib_path in dependencies:
            src_path = self.find_library_in_toolchain(lib_path)
            if src_path:
                lib_name = src_path.name
                if self.deploy_library(lib_path, output_dir):
                    deployed_count += 1
                    deployed_libs.append((lib_path, lib_name))

        # Fix executable's references to use @loader_path
        for old_path, lib_name in deployed_libs:
            self._fix_install_name(binary_path, old_path, f"@loader_path/{lib_name}")

        # Re-sign executable
        if deployed_libs:
            self._resign_binary(binary_path)

        # Summary
        if deployed_count > 0:
            self.logger.info(
                f"Deployed {deployed_count} dylib(s) for {binary_path.name}"
            )

        return deployed_count
```

### Windows: Refactored `DllDeployer`

**Changes Required**:

1. Inherit from `BaseLibraryDeployer`
2. Move common logic to base class
3. Keep Windows-specific detection (llvm-objdump -p)

**Example refactoring** (conceptual, not full implementation):

```python
class DllDeployer(BaseLibraryDeployer):
    def __init__(self, arch: str = "x86_64"):
        super().__init__("windows", arch)

    def detect_dependencies(self, binary_path: Path) -> List[str]:
        # Existing llvm-objdump -p logic
        ...

    def is_deployable_library(self, lib_name: str) -> bool:
        # Existing _is_deployable_dll() logic
        ...

    def find_library_in_toolchain(self, lib_name: str) -> Optional[Path]:
        # Existing find_dll_in_toolchain() logic
        ...

    def get_library_extension(self) -> str:
        return ".dll"

    # deploy_all() inherits from BaseLibraryDeployer
```

---

## Integration Points

### Factory Pattern

**Location**: `src/clang_tool_chain/deployment/factory.py`

```python
from pathlib import Path
from typing import Optional
from .base_deployer import BaseLibraryDeployer
from .dll_deployer import DllDeployer
from .so_deployer import SoDeployer
from .dylib_deployer import DylibDeployer

class DeploymentFactory:
    """
    Factory for creating platform-specific deployers.
    """

    @staticmethod
    def create_deployer(platform_name: str, arch: str) -> Optional[BaseLibraryDeployer]:
        """
        Create platform-specific deployer.

        Args:
            platform_name: "windows", "linux", or "darwin"
            arch: "x86_64", "arm64", etc.

        Returns:
            Platform-specific deployer instance, or None if unsupported
        """
        if platform_name == "windows":
            return DllDeployer(arch)
        elif platform_name == "linux":
            return SoDeployer(arch)
        elif platform_name == "darwin":
            return DylibDeployer(arch)
        else:
            return None
```

### Integration into `execution/core.py`

**Location**: `src/clang_tool_chain/execution/core.py:304-313`

**Current Code**:
```python
if platform_name == "windows":
    # Windows DLL deployment
    post_link_dll_deployment(output_exe, platform_name, use_gnu)
```

**New Code**:
```python
from clang_tool_chain.deployment.factory import DeploymentFactory

# ... in run_tool() function ...

if deploy_dependencies_requested and output_path:
    deployer = DeploymentFactory.create_deployer(platform_name, arch)
    if deployer:
        try:
            deployer.deploy_all(output_path)
        except Exception as e:
            logger.warning(f"Library deployment failed: {e}")
```

**Note**: Windows automatic .exe deployment should be kept separate for backward compatibility.

---

## API Design

### Environment Variables

#### Global Disable

- `CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1` - Disable all library deployment (Windows/Linux/macOS)

**Rationale**: Unified control across all platforms

#### Shared Library Output Disable

- `CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB=1` - Disable deployment for shared library outputs only (.dll, .so, .dylib)

**Rationale**: Granular control for shared library outputs (executables still get deployment)

#### Verbose Logging

- `CLANG_TOOL_CHAIN_LIB_DEPLOY_VERBOSE=1` - Enable DEBUG logging for all platforms

**Rationale**: Unified debugging flag

#### Check Order

```python
def should_deploy(platform_name: str, is_shared_lib: bool) -> bool:
    import os

    # Global disable
    if os.getenv("CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS") == "1":
        return False

    # Shared library output disable
    if is_shared_lib and os.getenv("CLANG_TOOL_CHAIN_NO_DEPLOY_SHARED_LIB") == "1":
        return False

    return True
```

### Command-Line Flag

**Flag**: `--deploy-dependencies`

**Usage**:
```bash
# Deploy dependencies for executable
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies

# Deploy dependencies for shared library
clang-tool-chain-cpp -shared lib.cpp -o libfoo.so --deploy-dependencies
```

**Extraction**: Already implemented in `core.py:36-60`

---

## Error Handling Strategy

### Non-Fatal Design

**Principle**: Library deployment never fails the build.

**Implementation**:
```python
try:
    deployer.deploy_all(binary_path)
except Exception as e:
    logger.warning(f"Library deployment failed: {e}")
    # Build continues successfully
```

### Logging Levels

| Level | Use Case | Example |
|-------|----------|---------|
| DEBUG | Individual operations | "Deployed (hard link): libc++.so.1" |
| INFO | Summary | "Deployed 3 shared libraries for program" |
| WARNING | Non-fatal errors | "Library not found: libcustom.so" |
| ERROR | (Never used) | Deployment errors are warnings |

### Specific Error Cases

| Error | Handling | Log Level |
|-------|----------|-----------|
| Detection tool not found | Log warning, skip deployment | WARNING |
| Detection timeout | Log warning, skip deployment | WARNING |
| Library not found | Log warning, skip that library | WARNING |
| Permission denied | Log warning, skip that library | WARNING |
| Disk full | Log warning, skip that library | WARNING |
| Code signing failed (macOS) | Log debug, continue | DEBUG |

---

## Performance Considerations

### Overhead Budget

**Target**: <150ms per executable (vs Windows <100ms)

**Breakdown**:
- Linux:
  - `readelf -d`: ~10-20ms
  - Recursive scan (3 deps): ~30ms
  - Copy 3 .so files: ~40ms
  - Symlink creation: ~5ms
  - **Total**: ~85ms ✅

- macOS:
  - `otool -L`: ~10-20ms
  - Recursive scan (3 deps): ~30ms
  - Copy 3 .dylib files: ~40ms
  - `install_name_tool` (3 calls): ~30ms
  - `codesign` (1 call): ~50ms
  - **Total**: ~160ms ⚠️ (slightly over budget)

### Optimizations

1. **Timestamp Checking**: Skip copy if dest is newer (~5ms saved per file)
2. **Hard Links**: Zero disk space, instant operation (when supported)
3. **Caching**: Cache toolchain search paths between invocations
4. **Parallel Deployment**: Copy libraries in parallel (ThreadPoolExecutor)

**Example parallel deployment**:
```python
from concurrent.futures import ThreadPoolExecutor

def deploy_all_parallel(self, binary_path: Path) -> int:
    dependencies = self.detect_all_dependencies(binary_path)
    output_dir = binary_path.parent

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(self.deploy_library, lib, output_dir)
            for lib in dependencies
        ]
        results = [f.result() for f in futures]

    return sum(results)
```

**Estimated speedup**: 3x for 3+ libraries

---

## Testing Strategy

### Unit Tests

**Coverage Target**: >90% for new code

#### Base Class Tests (`test_base_deployer.py`)

- `test_detect_all_dependencies_recursive`
- `test_detect_all_dependencies_direct_only`
- `test_should_copy_new_file`
- `test_should_copy_outdated_file`
- `test_should_skip_uptodate_file`
- `test_atomic_copy_hard_link`
- `test_atomic_copy_fallback`
- `test_atomic_copy_race_condition`

#### Linux Tests (`test_so_deployment.py`)

Mirror Windows test structure (38 tests):

1. **Pattern Matching** (6 tests)
   - `test_is_deployable_libcpp`
   - `test_is_deployable_libunwind`
   - `test_is_not_deployable_glibc`
   - `test_is_not_deployable_libpthread`

2. **Dependency Detection** (8 tests)
   - `test_detect_dependencies_readelf`
   - `test_detect_dependencies_missing_readelf`
   - `test_detect_dependencies_timeout`
   - `test_detect_dependencies_nonexistent_file`

3. **Library Location** (6 tests)
   - `test_find_library_in_clang_lib`
   - `test_find_library_in_usr_local`
   - `test_find_library_not_found`

4. **Deployment** (10 tests)
   - `test_deploy_single_library`
   - `test_deploy_versioned_symlinks`
   - `test_deploy_all_with_transitive_deps`
   - `test_deploy_skips_system_libs`

5. **Integration** (8 tests)
   - `test_real_compilation_with_libcpp`
   - `test_shared_library_deployment`
   - `test_environment_variable_disable`

#### macOS Tests (`test_dylib_deployment.py`)

Similar structure, plus macOS-specific:

1. **install_name_tool Tests** (4 tests)
   - `test_fix_install_name`
   - `test_fix_install_name_missing_tool`

2. **Code Signing Tests** (3 tests)
   - `test_resign_binary`
   - `test_resign_binary_missing_codesign`

3. **@rpath Resolution** (4 tests)
   - `test_find_library_rpath`
   - `test_find_library_absolute_path`

#### Factory Tests (`test_deployment_factory.py`)

- `test_create_windows_deployer`
- `test_create_linux_deployer`
- `test_create_darwin_deployer`
- `test_create_unsupported_platform`

### Integration Tests

**Platform**: GitHub Actions (Linux/macOS runners)

#### Linux Integration
```bash
# Compile with libc++ dependency
clang-tool-chain-cpp -stdlib=libc++ main.cpp -o program --deploy-dependencies

# Verify deployment
ls -la program libc++.so.1
ldd program | grep libc++

# Run without LD_LIBRARY_PATH
./program
```

#### macOS Integration
```bash
# Compile with custom dylib
clang-tool-chain-cpp main.cpp -o program --deploy-dependencies

# Verify deployment
ls -la program *.dylib
otool -L program

# Run without DYLD_LIBRARY_PATH
./program
```

### Performance Tests

**Benchmark**: Measure deployment overhead

```python
def test_deployment_performance(tmp_path):
    # Compile executable
    source = tmp_path / "main.cpp"
    source.write_text("int main() { return 0; }")

    exe = tmp_path / "program"

    # Time compilation + deployment
    import time
    start = time.time()
    subprocess.run([
        "clang-tool-chain-cpp",
        str(source),
        "-o", str(exe),
        "--deploy-dependencies"
    ], check=True)
    elapsed = time.time() - start

    # Assert overhead is reasonable
    assert elapsed < 1.0  # Should complete in <1s
```

---

## Implementation Roadmap

### Phase 3.1: Base Class Extraction (1 day)

**Tasks**:
1. Create `base_deployer.py` with abstract methods
2. Extract common logic from `dll_deployer.py`:
   - `detect_all_dependencies()` (recursive scanning)
   - `_should_copy()` (timestamp check)
   - `_atomic_copy()` (hard link + fallback)
3. Refactor `dll_deployer.py` to inherit from `BaseLibraryDeployer`
4. Run existing Windows tests to ensure no regression

**Deliverables**:
- `src/clang_tool_chain/deployment/base_deployer.py`
- Updated `dll_deployer.py`
- All 38 Windows tests pass

### Phase 3.2: Linux Implementation (2 days)

**Tasks**:
1. Create `so_deployer.py` with readelf detection
2. Implement symlink handling for versioned .so files
3. Write 30+ unit tests (mirror Windows structure)
4. Test on Linux x86_64 and ARM64

**Deliverables**:
- `src/clang_tool_chain/deployment/so_deployer.py`
- `tests/test_so_deployment.py`
- GitHub Actions workflow for Linux testing

### Phase 3.3: macOS Implementation (2 days)

**Tasks**:
1. Create `dylib_deployer.py` with otool detection
2. Implement install_name_tool integration
3. Implement code signing (codesign)
4. Write 30+ unit tests
5. Test on macOS x86_64 and ARM64

**Deliverables**:
- `src/clang_tool_chain/deployment/dylib_deployer.py`
- `tests/test_dylib_deployment.py`
- GitHub Actions workflow for macOS testing

### Phase 3.4: Factory Integration (0.5 days)

**Tasks**:
1. Create `factory.py` with platform selection
2. Write factory tests
3. Document factory pattern

**Deliverables**:
- `src/clang_tool_chain/deployment/factory.py`
- `tests/test_deployment_factory.py`

### Phase 3.5: Execution Core Integration (1 day)

**Tasks**:
1. Update `execution/core.py` to use factory
2. Add environment variable checks
3. Add logging integration
4. Integration testing on all platforms

**Deliverables**:
- Updated `execution/core.py`
- Integration tests in `tests/test_integration.py`

### Phase 3.6: Documentation (1 day)

**Tasks**:
1. Update `CLAUDE.md` with Linux/macOS deployment
2. Create `docs/SHARED_LIBRARY_DEPLOYMENT.md`
3. Update `docs/TESTING.md`
4. Update `README.md`

**Deliverables**:
- Complete documentation

### Timeline Summary

- **Phase 3.1**: 1 day (Base class)
- **Phase 3.2**: 2 days (Linux)
- **Phase 3.3**: 2 days (macOS)
- **Phase 3.4**: 0.5 days (Factory)
- **Phase 3.5**: 1 day (Integration)
- **Phase 3.6**: 1 day (Documentation)

**Total**: 7.5 days

---

## Conclusion

This design provides a comprehensive, well-architected solution for cross-platform shared library deployment. Key strengths:

1. **Abstraction**: Base class eliminates code duplication
2. **Extensibility**: Easy to add new platforms
3. **Reliability**: Non-fatal error handling, extensive testing
4. **Performance**: <150ms overhead, optimizations available
5. **Security**: Only deploys toolchain libraries, never system libs
6. **Maintainability**: Clear separation of concerns, well-documented

**Next Steps**: Proceed to Phase 3 (Implementation) using this design as the blueprint.

---

**Design Status**: ✅ Complete and Ready for Implementation

**Approvals Required**: None (agent loop, autonomous execution)

**Risk Assessment**: Low (mirrors proven Windows design, comprehensive testing planned)
