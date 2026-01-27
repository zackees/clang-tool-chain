"""
Unit tests for shared library dependency deployment functionality.

Tests cover:
- Flag extraction (_extract_deploy_dependencies_flag)
- Shared library output path detection (_extract_shared_library_output_path)
- Dependency deployment for Windows DLLs (post_link_dependency_deployment)
"""

import os
import shutil
import tempfile
from pathlib import Path
from types import TracebackType
from unittest.mock import patch

import pytest

from clang_tool_chain.deployment.dll_deployer import (
    post_link_dependency_deployment,
)
from clang_tool_chain.execution.core import (
    _extract_deploy_dependencies_flag,
    _extract_shared_library_output_path,
)


class WindowsSafeTemporaryDirectory:
    """
    Drop-in replacement for tempfile.TemporaryDirectory that handles Windows DLL cleanup.

    Uses ignore_errors=True on cleanup to prevent PermissionError when DLLs are locked.
    """

    def __init__(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
        ignore_cleanup_errors: bool = True,
    ):
        self._tmpdir = None
        self.name = None
        self._suffix = suffix
        self._prefix = prefix
        self._dir = dir
        self._ignore_cleanup_errors = ignore_cleanup_errors

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(suffix=self._suffix, prefix=self._prefix, dir=self._dir)
        self.name = self._tmpdir
        return self._tmpdir

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if self._tmpdir:
            # Use ignore_errors to handle locked DLLs on Windows
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        return False


class TestFlagExtraction:
    """Test the _extract_deploy_dependencies_flag() function."""

    def test_flag_extracted_and_stripped(self):
        """Test that --deploy-dependencies flag is extracted and stripped."""
        args = ["test.cpp", "--deploy-dependencies", "-o", "test.dll", "-shared"]
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(args)

        assert should_deploy is True
        assert "--deploy-dependencies" not in filtered_args
        assert filtered_args == ["test.cpp", "-o", "test.dll", "-shared"]

    def test_flag_absent_returns_false(self):
        """Test that should_deploy is False when flag is absent."""
        args = ["test.cpp", "-o", "test.dll", "-shared"]
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(args)

        assert should_deploy is False
        assert filtered_args == args  # Unchanged

    def test_flag_at_beginning(self):
        """Test flag at beginning of args."""
        args = ["--deploy-dependencies", "test.cpp", "-o", "test.dll"]
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(args)

        assert should_deploy is True
        assert filtered_args == ["test.cpp", "-o", "test.dll"]

    def test_flag_at_end(self):
        """Test flag at end of args."""
        args = ["test.cpp", "-o", "test.dll", "--deploy-dependencies"]
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(args)

        assert should_deploy is True
        assert filtered_args == ["test.cpp", "-o", "test.dll"]

    def test_empty_args(self):
        """Test with empty args list."""
        args = []
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(args)

        assert should_deploy is False
        assert filtered_args == []

    def test_only_flag(self):
        """Test with only the flag."""
        args = ["--deploy-dependencies"]
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(args)

        assert should_deploy is True
        assert filtered_args == []


class TestSharedLibraryOutputPathDetection:
    """Test the _extract_shared_library_output_path() function."""

    def test_detect_dll_with_shared_flag(self):
        """Test detection of .dll output with -shared flag."""
        args = ["-shared", "lib.cpp", "-o", "mylib.dll"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is not None
        assert result.name == "mylib.dll"

    def test_detect_so_with_shared_flag(self):
        """Test detection of .so output with -shared flag."""
        args = ["-shared", "lib.cpp", "-o", "libtest.so"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is not None
        assert result.name == "libtest.so"

    def test_detect_dylib_with_shared_flag(self):
        """Test detection of .dylib output with -shared flag."""
        args = ["-shared", "lib.cpp", "-o", "libtest.dylib"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is not None
        assert result.name == "libtest.dylib"

    def test_detect_versioned_so(self):
        """Test detection of versioned .so files (e.g., libtest.so.1.2)."""
        args = ["-shared", "lib.cpp", "-o", "libtest.so.1.2"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is not None
        assert "libtest.so.1.2" in result.name

    def test_no_shared_flag_returns_none(self):
        """Test that output without -shared flag returns None."""
        args = ["lib.cpp", "-o", "mylib.dll"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is None

    def test_compile_only_returns_none(self):
        """Test that -c flag causes None to be returned."""
        args = ["-c", "-shared", "lib.cpp", "-o", "mylib.dll"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is None

    def test_non_clang_tool_returns_none(self):
        """Test that non-clang tools return None."""
        args = ["-shared", "lib.cpp", "-o", "mylib.dll"]
        result = _extract_shared_library_output_path(args, "llvm-ar")

        assert result is None

    def test_exe_output_returns_none(self):
        """Test that .exe output returns None (not a shared library)."""
        args = ["-shared", "lib.cpp", "-o", "test.exe"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is None

    def test_o_format_with_space(self):
        """Test -o format with space."""
        args = ["-shared", "lib.cpp", "-o", "mylib.dll"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is not None
        assert result.name == "mylib.dll"

    def test_o_format_without_space(self):
        """Test -ooutput format without space."""
        args = ["-shared", "lib.cpp", "-omylib.dll"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is not None
        assert result.name == "mylib.dll"

    def test_no_output_flag_returns_none(self):
        """Test that missing -o flag returns None."""
        args = ["-shared", "lib.cpp"]
        result = _extract_shared_library_output_path(args, "clang++")

        assert result is None


class TestDependencyDeployment:
    """Test the post_link_dependency_deployment() function."""

    def test_opt_out_environment_variable(self):
        """Test that CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1 disables deployment."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dll_path = Path(tmpdir) / "test.dll"
            dll_path.touch()

            with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS": "1"}):
                # Should not raise, just skip
                post_link_dependency_deployment(dll_path, "win", True)

    def test_nonexistent_output_skipped(self):
        """Test that deployment is skipped for non-existent output files."""
        # Should not raise, just skip
        post_link_dependency_deployment(Path("/nonexistent/test.dll"), "win", True)

    def test_non_windows_dll_skipped(self):
        """Test that non-Windows DLLs are skipped with appropriate logging."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dll_path = Path(tmpdir) / "test.dll"
            dll_path.touch()

            # Linux platform with .dll file - should skip
            post_link_dependency_deployment(dll_path, "linux", True)

    def test_non_gnu_abi_skipped(self):
        """Test that non-GNU ABI builds are skipped."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dll_path = Path(tmpdir) / "test.dll"
            dll_path.touch()

            # GNU ABI = False should skip
            post_link_dependency_deployment(dll_path, "win", False)

    def test_linux_so_not_implemented(self):
        """Test that Linux .so deployment logs 'not implemented'."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            so_path = Path(tmpdir) / "libtest.so"
            so_path.touch()

            # Should not raise, just log debug message
            post_link_dependency_deployment(so_path, "linux", True)

    def test_macos_dylib_not_implemented(self):
        """Test that macOS .dylib deployment logs 'not implemented'."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dylib_path = Path(tmpdir) / "libtest.dylib"
            dylib_path.touch()

            # Should not raise, just log debug message
            post_link_dependency_deployment(dylib_path, "darwin", True)


class TestWindowsDependencyDeployment:
    """Windows-specific integration tests for dependency deployment."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_dll_deployment_with_detect_required_dlls(self):
        """Test that DLL deployment works when detect_required_dlls succeeds."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dll_path = Path(tmpdir) / "test.dll"
            # Create a minimal valid DLL-like file for testing
            dll_path.touch()

            # Mock the DllDeployer's deploy_all method
            with patch("clang_tool_chain.deployment.dll_deployer.DllDeployer") as mock_deployer_class:
                mock_deployer = mock_deployer_class.return_value
                mock_deployer.deploy_all.return_value = 2  # Simulate 2 DLLs deployed

                post_link_dependency_deployment(dll_path, "win", True)

                # Verify deployer was instantiated and deploy_all was called
                mock_deployer_class.assert_called_once()
                mock_deployer.deploy_all.assert_called_once_with(dll_path)

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_dll_deployment_with_missing_source_dll(self):
        """Test that missing source DLLs are handled gracefully."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dll_path = Path(tmpdir) / "test.dll"
            dll_path.touch()

            # Mock the DllDeployer's deploy_all method to return 0 (no DLLs deployed)
            with patch("clang_tool_chain.deployment.dll_deployer.DllDeployer") as mock_deployer_class:
                mock_deployer = mock_deployer_class.return_value
                mock_deployer.deploy_all.return_value = 0  # No DLLs deployed (all missing)

                # Should not raise, just warn
                post_link_dependency_deployment(dll_path, "win", True)

                # Verify deployer was instantiated and deploy_all was called
                mock_deployer_class.assert_called_once()
                mock_deployer.deploy_all.assert_called_once_with(dll_path)


class TestFlagNotPassedToClang:
    """Test that --deploy-dependencies flag is not passed to clang."""

    def test_flag_stripped_before_execution(self):
        """Verify the flag is stripped from args before passing to clang."""
        original_args = ["test.cpp", "--deploy-dependencies", "-o", "test.dll", "-shared"]
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(original_args)

        # The flag should be removed
        assert "--deploy-dependencies" not in filtered_args
        assert should_deploy is True

        # All other args should be preserved in order
        expected = ["test.cpp", "-o", "test.dll", "-shared"]
        assert filtered_args == expected

    def test_multiple_flags_not_supported(self):
        """Test behavior with multiple --deploy-dependencies flags (edge case)."""
        # If someone passes the flag twice, both should be removed
        args = ["--deploy-dependencies", "test.cpp", "--deploy-dependencies", "-o", "test.dll"]
        filtered_args, should_deploy = _extract_deploy_dependencies_flag(args)

        assert should_deploy is True
        # All instances should be removed
        assert "--deploy-dependencies" not in filtered_args
        assert filtered_args == ["test.cpp", "-o", "test.dll"]
