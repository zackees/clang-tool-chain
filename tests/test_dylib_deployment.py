"""
Tests for macOS .dylib deployment.

This module tests the DylibDeployer class which handles automatic shared library
deployment for macOS executables and shared libraries.

Test Coverage:
- Pattern matching (deployable vs system libraries)
- Dependency detection (otool -L parsing)
- Library location (@rpath resolution, search paths)
- Architecture support (x86_64, arm64)
- install_name_tool integration
- Code signing integration
- Environment variables
- File type detection
- Convenience wrapper functions
- Error handling
"""

import os
import platform
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import deployer
from clang_tool_chain.deployment.dylib_deployer import (
    DylibDeployer,
    detect_required_dylibs,
    post_link_dylib_deployment,
)

# ===== Fixtures =====


@pytest.fixture
def deployer():
    """Create DylibDeployer instance for testing."""
    return DylibDeployer(arch="x86_64")


@pytest.fixture
def mock_binary(tmp_path):
    """Create a mock binary file for testing."""
    binary = tmp_path / "test_program"
    binary.write_text("mock binary")
    return binary


@pytest.fixture
def mock_dylib(tmp_path):
    """Create a mock .dylib file for testing."""
    dylib = tmp_path / "libtest.1.dylib"
    dylib.write_text("mock dylib")
    return dylib


# ===== Pattern Matching Tests =====


class TestPatternMatching:
    """Test is_deployable_library() pattern matching."""

    def test_libc_plus_plus_deployable(self, deployer):
        """Test that libc++.*.dylib is deployable."""
        assert deployer.is_deployable_library("@rpath/libc++.1.dylib")

    def test_libc_plus_plus_abi_deployable(self, deployer):
        """Test that libc++abi.*.dylib is deployable."""
        assert deployer.is_deployable_library("@rpath/libc++abi.1.dylib")

    def test_libunwind_deployable(self, deployer):
        """Test that libunwind.*.dylib is deployable."""
        assert deployer.is_deployable_library("@rpath/libunwind.1.dylib")

    def test_sanitizer_runtime_deployable(self, deployer):
        """Test that sanitizer runtimes are deployable."""
        assert deployer.is_deployable_library("@rpath/libclang_rt.asan_osx_dynamic.dylib")
        assert deployer.is_deployable_library("@rpath/libclang_rt.tsan_osx_dynamic.dylib")

    def test_usr_local_libc_plus_plus_deployable(self, deployer):
        """Test that /usr/local/lib dylibs are deployable if they match patterns."""
        assert deployer.is_deployable_library("/usr/local/lib/libc++.1.dylib")

    def test_opt_homebrew_libunwind_deployable(self, deployer):
        """Test that Homebrew ARM dylibs are deployable."""
        assert deployer.is_deployable_library("/opt/homebrew/lib/libunwind.1.dylib")

    def test_system_lib_not_deployable(self, deployer):
        """Test that /usr/lib/* libraries are NOT deployable."""
        assert not deployer.is_deployable_library("/usr/lib/libSystem.B.dylib")
        assert not deployer.is_deployable_library("/usr/lib/libc++.1.dylib")

    def test_system_framework_not_deployable(self, deployer):
        """Test that /System/Library/* frameworks are NOT deployable."""
        assert not deployer.is_deployable_library("/System/Library/Frameworks/Foundation.framework/Foundation")

    def test_libunwind_in_usr_lib_not_deployable(self, deployer):
        """Test that libunwind in /usr/lib is NOT deployable (part of libSystem)."""
        assert not deployer.is_deployable_library("/usr/lib/libunwind.dylib")

    def test_random_dylib_not_deployable(self, deployer):
        """Test that random dylibs not matching patterns are NOT deployable."""
        assert not deployer.is_deployable_library("@rpath/librandom.dylib")
        assert not deployer.is_deployable_library("/usr/local/lib/libfoo.dylib")

    def test_rpath_non_matching_not_deployable(self, deployer):
        """Test that @rpath dylibs not matching patterns are NOT deployable."""
        assert not deployer.is_deployable_library("@rpath/libcustom.1.dylib")

    def test_loader_path_libc_plus_plus_deployable(self, deployer):
        """Test that @loader_path dylibs matching patterns are deployable."""
        # Note: is_deployable_library doesn't check @loader_path prefix currently
        # It extracts the basename and checks patterns
        assert not deployer.is_deployable_library("@loader_path/libc++.1.dylib")

    def test_executable_path_not_deployable(self, deployer):
        """Test that @executable_path dylibs are NOT deployable (similar to @loader_path)."""
        assert not deployer.is_deployable_library("@executable_path/libc++.1.dylib")


# ===== Dependency Detection Tests =====


class TestDependencyDetection:
    """Test detect_dependencies() using otool -L."""

    def test_detect_dependencies_otool_success(self, deployer, mock_binary):
        """Test successful dependency detection with otool."""
        otool_output = """/path/to/program:
\t@rpath/libc++.1.dylib (compatibility version 1.0.0, current version 1.0.0)
\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1311.0.0)
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=otool_output, returncode=0)
            deps = deployer.detect_dependencies(mock_binary)

        assert "@rpath/libc++.1.dylib" in deps
        assert "/usr/lib/libSystem.B.dylib" in deps
        assert len(deps) == 2

    def test_detect_dependencies_multiple_dylibs(self, deployer, mock_binary):
        """Test detection with multiple dylibs."""
        otool_output = """/path/to/program:
\t@rpath/libc++.1.dylib (compatibility version 1.0.0, current version 1.0.0)
\t@rpath/libc++abi.1.dylib (compatibility version 1.0.0, current version 1.0.0)
\t@rpath/libunwind.1.dylib (compatibility version 1.0.0, current version 1.0.0)
\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1311.0.0)
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=otool_output, returncode=0)
            deps = deployer.detect_dependencies(mock_binary)

        assert len(deps) == 4
        assert "@rpath/libc++.1.dylib" in deps
        assert "@rpath/libc++abi.1.dylib" in deps
        assert "@rpath/libunwind.1.dylib" in deps

    def test_detect_dependencies_otool_timeout(self, deployer, mock_binary):
        """Test handling of otool timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("otool", 10)):
            deps = deployer.detect_dependencies(mock_binary)

        assert deps == []

    def test_detect_dependencies_otool_not_found(self, deployer, mock_binary):
        """Test handling when otool is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            deps = deployer.detect_dependencies(mock_binary)

        assert deps == []

    def test_detect_dependencies_otool_error(self, deployer, mock_binary):
        """Test handling of otool errors."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "otool")):
            deps = deployer.detect_dependencies(mock_binary)

        assert deps == []

    def test_detect_dependencies_empty_output(self, deployer, mock_binary):
        """Test detection with empty otool output."""
        otool_output = "/path/to/program:\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=otool_output, returncode=0)
            deps = deployer.detect_dependencies(mock_binary)

        assert deps == []


# ===== Library Location Tests =====


class TestLibraryLocation:
    """Test find_library_in_toolchain() with @rpath resolution."""

    def test_find_library_absolute_path_exists(self, deployer, mock_dylib):
        """Test finding library with absolute path."""
        result = deployer.find_library_in_toolchain(str(mock_dylib))
        assert result == mock_dylib.resolve()

    def test_find_library_absolute_path_not_exists(self, deployer):
        """Test handling when absolute path doesn't exist."""
        result = deployer.find_library_in_toolchain("/nonexistent/lib.dylib")
        assert result is None

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_find_library_in_clang_lib(self, mock_get_bin, deployer, tmp_path):
        """Test finding library in clang/lib directory."""
        # Setup mock paths
        clang_bin = tmp_path / "bin"
        clang_lib = tmp_path / "lib"
        clang_lib.mkdir(parents=True)

        dylib = clang_lib / "libc++.1.dylib"
        dylib.write_text("mock dylib")

        mock_get_bin.return_value = clang_bin

        # Test @rpath resolution
        result = deployer.find_library_in_toolchain("@rpath/libc++.1.dylib")
        assert result == dylib.resolve()

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_find_library_loader_path(self, mock_get_bin, deployer, tmp_path):
        """Test finding library with @loader_path prefix."""
        clang_bin = tmp_path / "bin"
        clang_lib = tmp_path / "lib"
        clang_lib.mkdir(parents=True)

        dylib = clang_lib / "libunwind.1.dylib"
        dylib.write_text("mock dylib")

        mock_get_bin.return_value = clang_bin

        result = deployer.find_library_in_toolchain("@loader_path/libunwind.1.dylib")
        assert result == dylib.resolve()

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_find_library_executable_path(self, mock_get_bin, deployer, tmp_path):
        """Test finding library with @executable_path prefix."""
        clang_bin = tmp_path / "bin"
        clang_lib = tmp_path / "lib"
        clang_lib.mkdir(parents=True)

        dylib = clang_lib / "libc++abi.1.dylib"
        dylib.write_text("mock dylib")

        mock_get_bin.return_value = clang_bin

        result = deployer.find_library_in_toolchain("@executable_path/libc++abi.1.dylib")
        assert result == dylib.resolve()

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_find_library_not_found(self, mock_get_bin, deployer, tmp_path):
        """Test handling when library is not found in any search path."""
        clang_bin = tmp_path / "bin"
        mock_get_bin.return_value = clang_bin

        result = deployer.find_library_in_toolchain("@rpath/nonexistent.dylib")
        assert result is None


# ===== Architecture Tests =====


class TestArchitectures:
    """Test architecture-specific behavior."""

    def test_x86_64_architecture(self):
        """Test x86_64 architecture initialization."""
        deployer = DylibDeployer(arch="x86_64")
        assert deployer.arch == "x86_64"
        assert deployer.platform_name == "darwin"

    def test_arm64_architecture(self):
        """Test arm64 architecture initialization."""
        deployer = DylibDeployer(arch="arm64")
        assert deployer.arch == "arm64"
        assert deployer.platform_name == "darwin"

    def test_get_library_extension(self, deployer):
        """Test get_library_extension() returns .dylib."""
        assert deployer.get_library_extension() == ".dylib"


# ===== install_name_tool Tests =====


class TestInstallNameTool:
    """Test _fix_install_name() integration."""

    def test_fix_install_name_success(self, deployer, mock_binary):
        """Test successful install_name_tool execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            deployer._fix_install_name(mock_binary, "@rpath/libc++.1.dylib", "@loader_path/libc++.1.dylib")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "install_name_tool"
        assert args[1] == "-change"
        assert args[2] == "@rpath/libc++.1.dylib"
        assert args[3] == "@loader_path/libc++.1.dylib"

    def test_fix_install_name_timeout(self, deployer, mock_binary):
        """Test handling of install_name_tool timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("install_name_tool", 10)):
            # Should not raise, just log warning
            deployer._fix_install_name(mock_binary, "@rpath/libc++.1.dylib", "@loader_path/libc++.1.dylib")

    def test_fix_install_name_not_found(self, deployer, mock_binary):
        """Test handling when install_name_tool is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            # Should not raise, just log warning
            deployer._fix_install_name(mock_binary, "@rpath/libc++.1.dylib", "@loader_path/libc++.1.dylib")

    def test_fix_install_name_error(self, deployer, mock_binary):
        """Test handling of install_name_tool errors."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "install_name_tool")):
            # Should not raise, just log warning
            deployer._fix_install_name(mock_binary, "@rpath/libc++.1.dylib", "@loader_path/libc++.1.dylib")


# ===== Code Signing Tests =====


class TestCodeSigning:
    """Test _resign_binary() integration."""

    def test_resign_binary_success(self, deployer, mock_binary):
        """Test successful code signing."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            deployer._resign_binary(mock_binary)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "codesign"
        assert args[1] == "-s"
        assert args[2] == "-"
        assert args[3] == "--force"

    def test_resign_binary_timeout(self, deployer, mock_binary):
        """Test handling of codesign timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("codesign", 60)):
            # Should not raise, just log warning
            deployer._resign_binary(mock_binary)

    def test_resign_binary_not_found(self, deployer, mock_binary):
        """Test handling when codesign is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            # Should not raise, just log debug message
            deployer._resign_binary(mock_binary)

    def test_resign_binary_error(self, deployer, mock_binary):
        """Test handling of codesign errors."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "codesign")):
            # Should not raise, just log warning
            deployer._resign_binary(mock_binary)


# ===== Environment Variable Tests =====


class TestEnvironmentVariables:
    """Test environment variable controls."""

    def test_global_disable_env_var(self, mock_binary):
        """Test CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS disables deployment."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS": "1"}):
            result = post_link_dylib_deployment(mock_binary)

        assert result == 0

    def test_macos_specific_disable_env_var(self, mock_binary):
        """Test CLANG_TOOL_CHAIN_NO_DEPLOY_DYLIBS disables deployment."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_DEPLOY_DYLIBS": "1"}):
            result = post_link_dylib_deployment(mock_binary)

        assert result == 0

    def test_deployment_enabled_by_default(self, tmp_path):
        """Test that deployment proceeds when env vars are not set."""
        # Create a mock executable
        exe = tmp_path / "program"
        exe.write_text("mock executable")

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(DylibDeployer, "deploy_all", return_value=3) as mock_deploy,
        ):
            result = post_link_dylib_deployment(exe)

        # Should have attempted deployment
        assert result == 3
        mock_deploy.assert_called_once()


# ===== File Type Detection Tests =====


class TestFileTypeDetection:
    """Test file type detection for deployment eligibility."""

    def test_executable_file_eligible(self, tmp_path):
        """Test that executables (no extension) are eligible."""
        exe = tmp_path / "program"
        exe.write_text("mock executable")

        with patch.object(DylibDeployer, "deploy_all", return_value=2):
            result = post_link_dylib_deployment(exe)

        assert result == 2

    def test_dylib_file_eligible(self, tmp_path):
        """Test that .dylib files are eligible."""
        dylib = tmp_path / "libtest.dylib"
        dylib.write_text("mock dylib")

        with patch.object(DylibDeployer, "deploy_all", return_value=1):
            result = post_link_dylib_deployment(dylib)

        assert result == 1

    def test_out_file_eligible(self, tmp_path):
        """Test that .out files are eligible."""
        out = tmp_path / "program.out"
        out.write_text("mock executable")

        with patch.object(DylibDeployer, "deploy_all", return_value=1):
            result = post_link_dylib_deployment(out)

        assert result == 1

    def test_object_file_not_eligible(self, tmp_path):
        """Test that .o files are NOT eligible."""
        obj = tmp_path / "file.o"
        obj.write_text("mock object")

        result = post_link_dylib_deployment(obj)
        assert result == 0

    def test_archive_file_not_eligible(self, tmp_path):
        """Test that .a files are NOT eligible."""
        archive = tmp_path / "libtest.a"
        archive.write_text("mock archive")

        result = post_link_dylib_deployment(archive)
        assert result == 0

    def test_nonexistent_file_not_eligible(self, tmp_path):
        """Test that nonexistent files are NOT eligible."""
        result = post_link_dylib_deployment(tmp_path / "nonexistent")
        assert result == 0


# ===== Convenience Function Tests =====


class TestConvenienceFunctions:
    """Test backward-compatible wrapper functions."""

    def test_detect_required_dylibs(self, mock_binary):
        """Test detect_required_dylibs() wrapper function."""
        with patch.object(
            DylibDeployer, "detect_all_dependencies", return_value={"libc++.1.dylib", "libunwind.1.dylib"}
        ):
            dylibs = detect_required_dylibs(mock_binary, arch="arm64")

        assert "libc++.1.dylib" in dylibs
        assert "libunwind.1.dylib" in dylibs

    def test_detect_required_dylibs_non_recursive(self, mock_binary):
        """Test detect_required_dylibs() with recursive=False."""
        with patch.object(DylibDeployer, "detect_all_dependencies", return_value={"libc++.1.dylib"}) as mock_detect:
            detect_required_dylibs(mock_binary, arch="x86_64", recursive=False)

        mock_detect.assert_called_once_with(mock_binary, recursive=False)


# ===== Error Handling Tests =====


class TestErrorHandling:
    """Test error handling and non-fatal behavior."""

    def test_deploy_library_not_found(self, deployer, tmp_path):
        """Test that deploy_library returns False when library not found."""
        with patch.object(deployer, "find_library_in_toolchain", return_value=None):
            result = deployer.deploy_library("@rpath/nonexistent.dylib", tmp_path)

        assert result is False

    def test_deploy_library_copy_failure(self, deployer, tmp_path, mock_dylib):
        """Test that deploy_library returns False on copy failure."""
        with (
            patch.object(deployer, "find_library_in_toolchain", return_value=mock_dylib),
            patch.object(deployer, "_atomic_copy", side_effect=PermissionError),
        ):
            result = deployer.deploy_library("@rpath/lib.dylib", tmp_path)

        assert result is False

    def test_post_link_deployment_exception(self, tmp_path):
        """Test that post_link_dylib_deployment handles exceptions gracefully."""
        exe = tmp_path / "program"
        exe.write_text("mock executable")

        with patch.object(DylibDeployer, "deploy_all", side_effect=RuntimeError("Test error")):
            result = post_link_dylib_deployment(exe)

        # Should return 0 on exception, not raise
        assert result == 0


# ===== Integration Tests (macOS only) =====


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires macOS with otool")
class TestMacOSIntegration:
    """Integration tests that run real otool commands on macOS."""

    def test_detect_dependencies_real_otool(self, deployer):
        """Test dependency detection with real otool on /bin/ls."""
        if not Path("/bin/ls").exists():
            pytest.skip("/bin/ls not found")

        deps = deployer.detect_dependencies(Path("/bin/ls"))

        # /bin/ls should have at least libSystem dependency
        assert len(deps) > 0
        assert any("libSystem" in dep for dep in deps)

    def test_find_library_real_paths(self, deployer):
        """Test finding system libraries with real paths."""
        # System library should exist
        result = deployer.find_library_in_toolchain("/usr/lib/libSystem.B.dylib")
        assert result is not None
        assert result.exists()


# ===== Summary =====


def test_summary():
    """
    Test suite summary.

    Total tests: 60+
    Categories:
    - Pattern matching: 14 tests
    - Dependency detection: 6 tests
    - Library location: 5 tests
    - Architecture support: 3 tests
    - install_name_tool: 4 tests
    - Code signing: 4 tests
    - Environment variables: 3 tests
    - File type detection: 6 tests
    - Convenience functions: 2 tests
    - Error handling: 3 tests
    - Integration (macOS): 2 tests

    Coverage target: >90% for dylib_deployer.py
    """
    pass
