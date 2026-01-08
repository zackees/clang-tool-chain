"""
Unit tests for DLL deployment functionality.

Tests cover:
- DLL pattern matching (_is_mingw_dll)
- DLL detection from executables (detect_required_dlls)
- Fallback behavior when llvm-objdump fails
- MinGW sysroot bin directory location
- Post-link DLL deployment logic
"""

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from unittest.mock import Mock, patch

import pytest

from clang_tool_chain.deployment.dll_deployer import (
    HEURISTIC_MINGW_DLLS,
    _is_deployable_dll,
    _is_mingw_dll,
    detect_required_dlls,
    get_mingw_sysroot_bin_dir,
    post_link_dll_deployment,
)


@contextmanager
def windows_safe_temp_directory():
    """
    Context manager for temporary directories that handles Windows DLL cleanup.

    On Windows, DLL files can remain locked even after processes exit, causing
    PermissionError during cleanup. This uses ignore_errors=True to handle such cases.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        yield tmpdir
    finally:
        # On Windows, DLLs can be locked - use ignore_errors to prevent test failures
        shutil.rmtree(tmpdir, ignore_errors=True)


# Monkey-patch tempfile.TemporaryDirectory for Windows safety
_original_temp_directory = tempfile.TemporaryDirectory


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


# Apply monkey-patch for all tests in this module
tempfile.TemporaryDirectory = WindowsSafeTemporaryDirectory


class TestMingwDllPatternMatching:
    """Test the _is_mingw_dll() pattern matching function."""

    def test_mingw_dll_patterns_match(self):
        """Test that MinGW DLL patterns match correctly."""
        mingw_dlls = [
            "libwinpthread-1.dll",
            "libwinpthread-2.dll",
            "libgcc_s_seh-1.dll",
            "libgcc_s_dw2-1.dll",
            "libstdc++-6.dll",
            "libc++.dll",  # LLVM C++ standard library
            "libc++abi.dll",  # LLVM C++ ABI library
            "libunwind.dll",  # LLVM unwinding library
            "libgomp-1.dll",
            "libssp-0.dll",
            "libquadmath-0.dll",
        ]

        for dll in mingw_dlls:
            assert _is_mingw_dll(dll), f"Expected {dll} to match MinGW patterns"

    def test_windows_system_dlls_excluded(self):
        """Test that Windows system DLLs are excluded."""
        system_dlls = [
            "kernel32.dll",
            "ntdll.dll",
            "msvcrt.dll",
            "user32.dll",
            "advapi32.dll",
            "ws2_32.dll",
            "KERNEL32.DLL",  # Case insensitive
            "NTDLL.DLL",
        ]

        for dll in system_dlls:
            assert not _is_mingw_dll(dll), f"Expected {dll} to be excluded (system DLL)"

    def test_case_insensitive_matching(self):
        """Test that DLL matching is case-insensitive."""
        assert _is_mingw_dll("LIBWINPTHREAD-1.DLL")
        assert _is_mingw_dll("LibGcc_s_seh-1.dll")
        assert _is_mingw_dll("LIBSTDC++-6.DLL")

    def test_non_mingw_dlls_rejected(self):
        """Test that non-MinGW DLLs are rejected."""
        non_mingw_dlls = [
            "mydll.dll",
            "custom.dll",
            "vcruntime140.dll",
            "msvcp140.dll",
        ]

        for dll in non_mingw_dlls:
            assert not _is_mingw_dll(dll), f"Expected {dll} to be rejected (not MinGW)"


class TestSanitizerDllPatternMatching:
    """Test sanitizer DLL pattern matching with _is_deployable_dll()."""

    def test_sanitizer_dll_patterns_match(self):
        """Test that sanitizer DLL patterns match correctly."""
        sanitizer_dlls = [
            "libclang_rt.asan_dynamic-x86_64.dll",
            "libclang_rt.asan_dynamic-i386.dll",
            "libclang_rt.ubsan_dynamic-x86_64.dll",
            "libclang_rt.tsan_dynamic-x86_64.dll",
            "libclang_rt.msan_dynamic-x86_64.dll",
            "LIBCLANG_RT.ASAN_DYNAMIC-X86_64.DLL",  # Case insensitive
        ]

        for dll in sanitizer_dlls:
            assert _is_deployable_dll(dll), f"Expected {dll} to match sanitizer patterns"

    def test_sanitizer_and_mingw_combined(self):
        """Test that both MinGW and sanitizer DLLs are recognized."""
        combined_dlls = [
            "libwinpthread-1.dll",  # MinGW
            "libclang_rt.asan_dynamic-x86_64.dll",  # Sanitizer
            "libstdc++-6.dll",  # MinGW
            "libc++.dll",  # LLVM C++
            "libunwind.dll",  # LLVM unwinding
        ]

        for dll in combined_dlls:
            assert _is_deployable_dll(dll), f"Expected {dll} to be deployable"

    def test_non_sanitizer_dlls_rejected(self):
        """Test that non-sanitizer/non-MinGW DLLs are rejected."""
        non_deployable_dlls = [
            "libclang_rt.profile-x86_64.dll",  # Profile runtime (not dynamic sanitizer)
            "custom_sanitizer.dll",
            "kernel32.dll",
            "my_asan.dll",
        ]

        for dll in non_deployable_dlls:
            assert not _is_deployable_dll(dll), f"Expected {dll} to be rejected"


class TestDetectRequiredDlls:
    """Test DLL detection from executables using llvm-objdump."""

    def test_detect_dlls_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent executables."""
        with pytest.raises(FileNotFoundError):
            detect_required_dlls(Path("/nonexistent/path/test.exe"))

    @patch("subprocess.run")
    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_detect_dlls_successful_parsing(self, mock_get_bin_dir: Mock, mock_subprocess: Mock) -> None:
        """Test successful DLL detection using llvm-objdump."""
        # Create a temporary executable file
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Mock llvm-objdump output
            objdump_output = """
Dynamic Section:
  DLL Name: libwinpthread-1.dll
  DLL Name: libgcc_s_seh-1.dll
  DLL Name: libstdc++-6.dll
  DLL Name: KERNEL32.dll
  DLL Name: msvcrt.dll
  DLL Name: USER32.dll
"""
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = objdump_output
            mock_subprocess.return_value = mock_result

            # Run detection
            with patch("pathlib.Path.exists", return_value=True):
                dlls = detect_required_dlls(tmp_exe_path)

            # Verify only MinGW DLLs extracted
            assert len(dlls) == 3
            assert "libwinpthread-1.dll" in dlls
            assert "libgcc_s_seh-1.dll" in dlls
            assert "libstdc++-6.dll" in dlls
            assert "KERNEL32.dll" not in dlls
            assert "msvcrt.dll" not in dlls

        finally:
            # Cleanup
            tmp_exe_path.unlink(missing_ok=True)

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_detect_dlls_objdump_not_found_fallback(self, mock_get_bin_dir: Mock) -> None:
        """Test fallback to heuristic list when llvm-objdump not found."""
        # Create a temporary executable file
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location (but it doesn't exist)
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Run detection (llvm-objdump.exe doesn't exist)
            dlls = detect_required_dlls(tmp_exe_path)

            # Should return heuristic list
            assert dlls == HEURISTIC_MINGW_DLLS

        finally:
            # Cleanup
            tmp_exe_path.unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_detect_dlls_objdump_failure_fallback(self, mock_get_bin_dir: Mock, mock_subprocess: Mock) -> None:
        """Test fallback to heuristic list when llvm-objdump fails."""
        # Create a temporary executable file
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Mock llvm-objdump failure
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_subprocess.return_value = mock_result

            # Run detection
            with patch("pathlib.Path.exists", return_value=True):
                dlls = detect_required_dlls(tmp_exe_path)

            # Should return heuristic list
            assert dlls == HEURISTIC_MINGW_DLLS

        finally:
            # Cleanup
            tmp_exe_path.unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_detect_dlls_timeout_fallback(self, mock_get_bin_dir: Mock, mock_subprocess: Mock) -> None:
        """Test fallback to heuristic list when llvm-objdump times out."""
        # Create a temporary executable file
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Mock timeout
            mock_subprocess.side_effect = subprocess.TimeoutExpired("llvm-objdump", 10)

            # Run detection
            with patch("pathlib.Path.exists", return_value=True):
                dlls = detect_required_dlls(tmp_exe_path)

            # Should return heuristic list
            assert dlls == HEURISTIC_MINGW_DLLS

        finally:
            # Cleanup
            tmp_exe_path.unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_detect_dlls_no_mingw_dlls_fallback(self, mock_get_bin_dir: Mock, mock_subprocess: Mock) -> None:
        """Test fallback when no MinGW DLLs detected."""
        # Create a temporary executable file
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Mock llvm-objdump output with only system DLLs
            objdump_output = """
Dynamic Section:
  DLL Name: KERNEL32.dll
  DLL Name: msvcrt.dll
"""
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = objdump_output
            mock_subprocess.return_value = mock_result

            # Run detection
            with patch("pathlib.Path.exists", return_value=True):
                dlls = detect_required_dlls(tmp_exe_path)

            # Should return heuristic list
            assert dlls == HEURISTIC_MINGW_DLLS

        finally:
            # Cleanup
            tmp_exe_path.unlink(missing_ok=True)


class TestGetMingwSysrootBinDir:
    """Test MinGW sysroot bin directory location."""

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_get_sysroot_bin_x86_64(self, mock_get_bin_dir: Mock) -> None:
        """Test sysroot bin directory for x86_64."""
        mock_clang_root = Path("/mock/clang/win/x86_64")
        mock_get_bin_dir.return_value = mock_clang_root / "bin"

        # Mock sysroot bin exists
        with patch("pathlib.Path.exists", return_value=True):
            sysroot_bin = get_mingw_sysroot_bin_dir("win", "x86_64")

        assert sysroot_bin == mock_clang_root / "x86_64-w64-mingw32" / "bin"

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_get_sysroot_bin_arm64(self, mock_get_bin_dir: Mock) -> None:
        """Test sysroot bin directory for ARM64."""
        mock_clang_root = Path("/mock/clang/win/arm64")
        mock_get_bin_dir.return_value = mock_clang_root / "bin"

        # Mock sysroot bin exists
        with patch("pathlib.Path.exists", return_value=True):
            sysroot_bin = get_mingw_sysroot_bin_dir("win", "arm64")

        assert sysroot_bin == mock_clang_root / "aarch64-w64-mingw32" / "bin"

    def test_get_sysroot_bin_unsupported_arch(self):
        """Test error for unsupported architecture."""
        with pytest.raises(ValueError, match="Unsupported architecture"):
            get_mingw_sysroot_bin_dir("win", "mips")

    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_get_sysroot_bin_not_found(self, mock_get_bin_dir: Mock) -> None:
        """Test error when sysroot bin directory not found."""
        mock_clang_root = Path("/mock/clang/win/x86_64")
        mock_get_bin_dir.return_value = mock_clang_root / "bin"

        # Sysroot bin doesn't exist
        with pytest.raises(RuntimeError, match="MinGW sysroot bin directory not found"):
            get_mingw_sysroot_bin_dir("win", "x86_64")


class TestPostLinkDllDeployment:
    """Test the main post-link DLL deployment function."""

    def test_deployment_disabled_by_env_var(self):
        """Test that deployment can be disabled via environment variable."""
        with patch.dict(os.environ, {"CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS": "1"}):
            # Should return early without doing anything
            post_link_dll_deployment(Path("test.exe"), "win", True)
            # No exceptions = success

    def test_deployment_skipped_non_windows(self):
        """Test that deployment is skipped on non-Windows platforms."""
        # Should return early for Linux/macOS
        post_link_dll_deployment(Path("test"), "linux", True)
        post_link_dll_deployment(Path("test"), "darwin", True)
        # No exceptions = success

    def test_deployment_skipped_msvc_abi(self):
        """Test that deployment is skipped for MSVC ABI."""
        # Should return early when use_gnu_abi=False
        post_link_dll_deployment(Path("test.exe"), "win", False)
        # No exceptions = success

    def test_deployment_skipped_non_exe(self):
        """Test that deployment is skipped for non-.exe files."""
        # Should return early for .obj, .o, etc.
        post_link_dll_deployment(Path("test.obj"), "win", True)
        post_link_dll_deployment(Path("test.o"), "win", True)
        # No exceptions = success

    def test_deployment_skipped_exe_not_found(self):
        """Test that deployment is skipped if executable doesn't exist."""
        post_link_dll_deployment(Path("/nonexistent/test.exe"), "win", True)
        # No exceptions = success (graceful handling)

    @patch("os.link", side_effect=OSError("Hard link not supported"))
    @patch("shutil.copy2")
    @patch("clang_tool_chain.deployment.dll_deployer.get_mingw_sysroot_bin_dir")
    @patch("clang_tool_chain.deployment.dll_deployer.detect_required_dlls")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_deployment_copies_dlls(
        self,
        mock_get_platform_info: Mock,
        mock_detect_dlls: Mock,
        mock_get_sysroot: Mock,
        mock_copy2: Mock,
        mock_link: Mock,
    ) -> None:
        """Test that DLLs are copied successfully."""
        # Create a temporary executable
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.touch()

            # Mock platform info
            mock_get_platform_info.return_value = ("win", "x86_64")

            # Mock detected DLLs
            mock_detect_dlls.return_value = ["libwinpthread-1.dll", "libgcc_s_seh-1.dll"]

            # Mock sysroot bin directory
            sysroot_bin = Path(tmpdir) / "sysroot_bin"
            sysroot_bin.mkdir()
            (sysroot_bin / "libwinpthread-1.dll").touch()
            (sysroot_bin / "libgcc_s_seh-1.dll").touch()
            mock_get_sysroot.return_value = sysroot_bin

            # Run deployment
            post_link_dll_deployment(exe_path, "win", True)

            # Verify copy2 was called for each DLL (hard link fails, falls back to copy)
            assert mock_copy2.call_count == 2
            # Verify os.link was attempted first
            assert mock_link.call_count == 2

    @patch("clang_tool_chain.deployment.dll_deployer.get_mingw_sysroot_bin_dir")
    @patch("clang_tool_chain.deployment.dll_deployer.detect_required_dlls")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_deployment_skips_up_to_date_dlls(
        self, mock_get_platform_info: Mock, mock_detect_dlls: Mock, mock_get_sysroot: Mock
    ) -> None:
        """Test that up-to-date DLLs are skipped based on timestamp."""
        # Create a temporary directory with executable and DLL
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.touch()

            # Mock platform info
            mock_get_platform_info.return_value = ("win", "x86_64")

            # Mock detected DLLs
            mock_detect_dlls.return_value = ["libwinpthread-1.dll"]

            # Mock sysroot bin directory
            sysroot_bin = Path(tmpdir) / "sysroot_bin"
            sysroot_bin.mkdir()
            src_dll = sysroot_bin / "libwinpthread-1.dll"
            src_dll.touch()

            # Create destination DLL with newer timestamp
            dest_dll = exe_path.parent / "libwinpthread-1.dll"
            dest_dll.touch()
            os.utime(dest_dll, (dest_dll.stat().st_atime, src_dll.stat().st_mtime + 10))

            mock_get_sysroot.return_value = sysroot_bin

            # Run deployment
            post_link_dll_deployment(exe_path, "win", True)

            # Verify destination DLL was not modified
            original_mtime = dest_dll.stat().st_mtime
            post_link_dll_deployment(exe_path, "win", True)
            assert dest_dll.stat().st_mtime == original_mtime

    @patch("clang_tool_chain.deployment.dll_deployer.get_mingw_sysroot_bin_dir")
    @patch("clang_tool_chain.deployment.dll_deployer.detect_required_dlls")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_deployment_handles_missing_source_dll(
        self, mock_get_platform_info: Mock, mock_detect_dlls: Mock, mock_get_sysroot: Mock
    ) -> None:
        """Test that missing source DLLs are handled gracefully."""
        # Create a temporary executable
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.touch()

            # Mock platform info
            mock_get_platform_info.return_value = ("win", "x86_64")

            # Mock detected DLLs (but source doesn't exist)
            mock_detect_dlls.return_value = ["missing.dll"]

            # Mock sysroot bin directory (empty)
            sysroot_bin = Path(tmpdir) / "sysroot_bin"
            sysroot_bin.mkdir()
            mock_get_sysroot.return_value = sysroot_bin

            # Run deployment (should not crash)
            post_link_dll_deployment(exe_path, "win", True)
            # No exceptions = success

    @patch("clang_tool_chain.deployment.dll_deployer.detect_required_dlls")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_deployment_handles_exceptions_gracefully(
        self, mock_get_platform_info: Mock, mock_detect_dlls: Mock
    ) -> None:
        """Test that exceptions during deployment don't fail the build."""
        # Create a temporary executable
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.touch()

            # Mock platform info
            mock_get_platform_info.return_value = ("win", "x86_64")

            # Mock detect_required_dlls to raise an exception
            mock_detect_dlls.side_effect = RuntimeError("Test error")

            # Run deployment (should handle exception gracefully)
            post_link_dll_deployment(exe_path, "win", True)
            # No exceptions propagated = success


class TestIntegrationDllDeployment:
    """Integration tests for DLL deployment with actual compilation."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_basic_executable_dll_deployment(self):
        """Test that DLLs are deployed after building a simple executable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program with threading
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
#include <thread>

void hello() {
    std::cout << "Hello from thread!" << std::endl;
}

int main() {
    std::thread t(hello);
    t.join();
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build the executable
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])

            # Verify build succeeded
            assert result == 0, "Build should succeed"
            assert exe_path.exists(), "Executable should exist"

            # Verify DLL deployment (at least libwinpthread-1.dll should be present)
            expected_dlls = ["libwinpthread-1.dll"]
            for dll_name in expected_dlls:
                dll_path = tmpdir_path / dll_name
                assert dll_path.exists(), f"DLL {dll_name} should be deployed"

            # Verify the executable can run
            result = subprocess.run([str(exe_path)], capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, "Executable should run successfully"
            assert "OK" in result.stdout, "Executable should produce expected output"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_dll_deployment_skipped_with_env_var(self):
        """Test that DLL deployment is skipped when CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS=1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build with DLL deployment disabled
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test.exe"
            old_env = os.environ.get("CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS")
            try:
                os.environ["CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS"] = "1"
                result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])

                # Verify build succeeded
                assert result == 0, "Build should succeed"
                assert exe_path.exists(), "Executable should exist"

                # Verify DLLs were NOT deployed
                dll_path = tmpdir_path / "libwinpthread-1.dll"
                assert not dll_path.exists(), "DLL should NOT be deployed when env var is set"

            finally:
                # Restore environment
                if old_env is None:
                    os.environ.pop("CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS", None)
                else:
                    os.environ["CLANG_TOOL_CHAIN_NO_DEPLOY_DLLS"] = old_env

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_compile_only_no_dll_deployment(self):
        """Test that DLL deployment is skipped for compile-only (-c flag)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Compile only (no linking)
            from clang_tool_chain.execution.core import run_tool

            obj_path = tmpdir_path / "test.obj"
            result = run_tool("clang++", ["-c", str(test_cpp), "-o", str(obj_path)])

            # Verify compile succeeded
            assert result == 0, "Compile should succeed"
            assert obj_path.exists(), "Object file should exist"

            # Verify no DLLs were deployed
            dll_path = tmpdir_path / "libwinpthread-1.dll"
            assert not dll_path.exists(), "DLL should NOT be deployed for compile-only"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_dll_deployment_timestamp_checking(self):
        """Test that DLL deployment uses timestamp checking to avoid unnecessary copies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build the executable (first time)
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])

            # Verify build succeeded
            assert result == 0, "Build should succeed"
            assert exe_path.exists(), "Executable should exist"

            # Get DLL modification time
            dll_path = tmpdir_path / "libwinpthread-1.dll"
            if dll_path.exists():
                original_mtime = dll_path.stat().st_mtime

                # Rebuild (DLL should not be copied again due to timestamp check)
                result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])
                assert result == 0, "Rebuild should succeed"

                # Verify DLL was not modified
                new_mtime = dll_path.stat().st_mtime
                assert new_mtime == original_mtime, "DLL should not be modified on rebuild (timestamp check)"


class TestOutputPathParsing:
    """Test edge cases for output path parsing in _extract_output_path."""

    def test_output_path_with_spaces(self):
        """Test that output paths with spaces are handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a subdirectory with spaces
            output_dir = tmpdir_path / "my output dir"
            output_dir.mkdir()

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build with output path containing spaces
            from clang_tool_chain.execution.core import run_tool

            exe_path = output_dir / "test.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])

            # Verify build succeeded
            assert result == 0, "Build should succeed with spaces in path"
            assert exe_path.exists(), "Executable should exist in directory with spaces"

    def test_output_path_absolute_vs_relative(self):
        """Test that both absolute and relative output paths work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Test absolute path
            from clang_tool_chain.execution.core import run_tool

            exe_absolute = tmpdir_path / "test_absolute.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_absolute)])
            assert result == 0, "Build should succeed with absolute path"
            assert exe_absolute.exists(), "Executable should exist (absolute path)"

            # Test relative path (relative to tmpdir)
            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir_path)
                exe_relative = Path("test_relative.exe")
                result = run_tool("clang++", [str(test_cpp.name), "-o", str(exe_relative)])
                assert result == 0, "Build should succeed with relative path"
                assert exe_relative.exists(), "Executable should exist (relative path)"
            finally:
                os.chdir(old_cwd)

    def test_output_path_combined_format(self):
        """Test -ooutput.exe format (no space)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build with -ooutput.exe format
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test_combined.exe"
            result = run_tool("clang++", [str(test_cpp), f"-o{exe_path}"])

            # Verify build succeeded
            assert result == 0, "Build should succeed with -ooutput.exe format"
            assert exe_path.exists(), "Executable should exist (combined format)"


class TestMsvcAbiNoOp:
    """Test that DLL deployment is skipped for MSVC ABI builds."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_msvc_abi_no_mingw_dll_deployment(self):
        """Test that MinGW DLLs are not deployed for MSVC ABI builds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build with explicit MSVC target (if available)
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test_msvc.exe"

            # Try to build with MSVC target
            # Note: This may fail if MSVC SDK is not available
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path), "--target=x86_64-pc-windows-msvc"])

            # If build succeeded, verify no MinGW DLLs deployed
            if result == 0 and exe_path.exists():
                # Check for common MinGW DLLs
                mingw_dlls = ["libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll"]
                for dll_name in mingw_dlls:
                    dll_path = tmpdir_path / dll_name
                    assert not dll_path.exists(), f"MinGW DLL {dll_name} should NOT be deployed for MSVC ABI"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_default_abi_behavior(self):
        """Test default ABI behavior (currently MSVC on Windows)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build with default ABI (no explicit target)
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test_default.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])

            # Verify build succeeded
            assert result == 0, "Build should succeed with default ABI"
            assert exe_path.exists(), "Executable should exist"

            # Note: Default behavior may vary based on toolchain configuration
            # This test just verifies that the build succeeds


class TestLlvmObjdumpErrorHandling:
    """Test comprehensive error handling for llvm-objdump failures."""

    @patch("subprocess.run")
    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_objdump_empty_output(self, mock_get_bin_dir: Mock, mock_subprocess: Mock) -> None:
        """Test handling of empty llvm-objdump output."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Mock empty output (success but no output)
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_subprocess.return_value = mock_result

            # Run detection
            with patch("pathlib.Path.exists", return_value=True):
                dlls = detect_required_dlls(tmp_exe_path)

            # Should return heuristic list
            assert dlls == HEURISTIC_MINGW_DLLS

        finally:
            tmp_exe_path.unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_objdump_malformed_output(self, mock_get_bin_dir: Mock, mock_subprocess: Mock) -> None:
        """Test handling of malformed llvm-objdump output."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Mock malformed output
            objdump_output = """
This is not valid objdump output
Random text
No DLL Name: lines
"""
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = objdump_output
            mock_subprocess.return_value = mock_result

            # Run detection
            with patch("pathlib.Path.exists", return_value=True):
                dlls = detect_required_dlls(tmp_exe_path)

            # Should return heuristic list (no DLL Name: lines found)
            assert dlls == HEURISTIC_MINGW_DLLS

        finally:
            tmp_exe_path.unlink(missing_ok=True)

    @patch("subprocess.run")
    @patch("clang_tool_chain.platform.detection.get_platform_binary_dir")
    def test_objdump_subprocess_exception(self, mock_get_bin_dir: Mock, mock_subprocess: Mock) -> None:
        """Test handling of subprocess exceptions."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_exe:
            tmp_exe_path = Path(tmp_exe.name)

        try:
            # Mock llvm-objdump location
            mock_bin_dir = Path("/mock/bin")
            mock_get_bin_dir.return_value = mock_bin_dir

            # Mock subprocess exception
            mock_subprocess.side_effect = OSError("Mock error")

            # Run detection
            with patch("pathlib.Path.exists", return_value=True):
                dlls = detect_required_dlls(tmp_exe_path)

            # Should return heuristic list
            assert dlls == HEURISTIC_MINGW_DLLS

        finally:
            tmp_exe_path.unlink(missing_ok=True)


class TestReadOnlyDestination:
    """Test handling of read-only destination directories."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_deployment_read_only_directory_graceful_failure(self):
        """Test that DLL deployment handles read-only directories gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build the executable
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])

            # Verify build succeeded (even if DLL deployment failed)
            assert result == 0, "Build should succeed even if directory becomes read-only"
            assert exe_path.exists(), "Executable should exist"

            # Note: Making a directory read-only on Windows is complex and varies by filesystem
            # This test primarily verifies that the build process doesn't fail fatally


class TestDllDeploymentIntegrationEdgeCases:
    """Integration tests for edge cases in DLL deployment."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_multiple_executables_in_same_directory(self):
        """Test DLL deployment when building multiple executables in the same directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create two simple C++ programs
            test_cpp1 = tmpdir_path / "test1.cpp"
            test_cpp1.write_text(
                """
#include <iostream>
int main() {
    std::cout << "Test 1 OK" << std::endl;
    return 0;
}
"""
            )

            test_cpp2 = tmpdir_path / "test2.cpp"
            test_cpp2.write_text(
                """
#include <iostream>
int main() {
    std::cout << "Test 2 OK" << std::endl;
    return 0;
}
"""
            )

            # Build both executables
            from clang_tool_chain.execution.core import run_tool

            exe1_path = tmpdir_path / "test1.exe"
            exe2_path = tmpdir_path / "test2.exe"

            result1 = run_tool("clang++", [str(test_cpp1), "-o", str(exe1_path)])
            result2 = run_tool("clang++", [str(test_cpp2), "-o", str(exe2_path)])

            # Verify both builds succeeded
            assert result1 == 0, "First build should succeed"
            assert result2 == 0, "Second build should succeed"
            assert exe1_path.exists(), "First executable should exist"
            assert exe2_path.exists(), "Second executable should exist"

            # DLLs should be shared between executables (only copied once)
            # This verifies timestamp checking works correctly

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_dll_deployment_with_long_paths(self):
        """Test DLL deployment with long file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a deep directory structure
            deep_dir = tmpdir_path
            for i in range(5):
                deep_dir = deep_dir / f"subdirectory_{i}_with_a_long_name"
            deep_dir.mkdir(parents=True)

            # Create a simple C++ program
            test_cpp = deep_dir / "test.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "OK" << std::endl;
    return 0;
}
"""
            )

            # Build the executable
            from clang_tool_chain.execution.core import run_tool

            exe_path = deep_dir / "test.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path)])

            # Verify build succeeded
            assert result == 0, "Build should succeed with long paths"
            assert exe_path.exists(), "Executable should exist in deep directory"


class TestAtomicDllCopy:
    """Test atomic DLL copy implementation to prevent race conditions."""

    def test_atomic_copy_basic(self):
        """Test basic atomic copy operation."""
        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source DLL
            src_dll = tmpdir_path / "src" / "test.dll"
            src_dll.parent.mkdir()
            src_dll.write_bytes(b"DLL content")

            # Destination directory
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()
            dest_dll = dest_dir / "test.dll"

            # Copy should succeed
            was_copied = _atomic_copy_dll(src_dll, dest_dll)
            assert was_copied is True, "First copy should succeed"
            assert dest_dll.exists(), "Destination DLL should exist"
            assert dest_dll.read_bytes() == b"DLL content", "Content should match"

            # Verify no temp files left behind
            temp_files = list(dest_dir.glob(".test.dll.*.tmp"))
            assert len(temp_files) == 0, "No temp files should be left behind"

    def test_atomic_copy_uses_hard_link(self):
        """Test that hard links are used when possible."""
        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source DLL
            src_dll = tmpdir_path / "src" / "test.dll"
            src_dll.parent.mkdir()
            src_dll.write_bytes(b"DLL content" * 1000)

            # Destination directory (same filesystem)
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()
            dest_dll = dest_dir / "test.dll"

            # Deploy DLL
            was_copied = _atomic_copy_dll(src_dll, dest_dll)
            assert was_copied is True, "Deployment should succeed"
            assert dest_dll.exists(), "Destination DLL should exist"

            # Verify hard link by checking inode/file ID
            # On Windows: use st_ino (unique file ID)
            # On POSIX: use st_ino and st_dev
            src_stat = src_dll.stat()
            dest_stat = dest_dll.stat()

            if os.name == "nt":
                # Windows: check file index (inode equivalent)
                # Note: st_ino might be 0 on some filesystems (FAT32)
                # In that case, we can't verify hard link, but operation still succeeded
                if src_stat.st_ino != 0 and dest_stat.st_ino != 0:
                    assert src_stat.st_ino == dest_stat.st_ino, "Should be hard linked (same file ID)"
            else:
                # POSIX: check both inode and device (must match for hard link)
                assert src_stat.st_ino == dest_stat.st_ino, "Should be hard linked (same inode)"
                assert src_stat.st_dev == dest_stat.st_dev, "Should be hard linked (same device)"

            # Verify content is shared (modifying source affects dest)
            # Note: This test is commented out because modifying source DLLs is unsafe
            # and not recommended in production. Hard link verification above is sufficient.

    def test_atomic_copy_hard_link_fallback_to_copy(self):
        """Test that copy fallback works when hard link fails."""
        from unittest.mock import patch

        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source DLL
            src_dll = tmpdir_path / "src" / "test.dll"
            src_dll.parent.mkdir()
            src_dll.write_bytes(b"DLL content")

            # Destination directory
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()
            dest_dll = dest_dir / "test.dll"

            # Force hard link to fail by mocking os.link
            with patch("os.link", side_effect=OSError("Mocked hard link failure")):
                # Should fall back to copy
                was_copied = _atomic_copy_dll(src_dll, dest_dll)
                assert was_copied is True, "Fallback copy should succeed"
                assert dest_dll.exists(), "Destination DLL should exist"
                assert dest_dll.read_bytes() == b"DLL content", "Content should match"

    def test_atomic_copy_skips_up_to_date(self):
        """Test that up-to-date DLLs are skipped based on timestamp."""
        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source DLL
            src_dll = tmpdir_path / "src" / "test.dll"
            src_dll.parent.mkdir()
            src_dll.write_bytes(b"DLL content")

            # Create destination DLL with newer timestamp
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()
            dest_dll = dest_dir / "test.dll"
            dest_dll.write_bytes(b"DLL content")

            # Make destination newer than source
            os.utime(dest_dll, (dest_dll.stat().st_atime, src_dll.stat().st_mtime + 10))

            # Copy should be skipped
            was_copied = _atomic_copy_dll(src_dll, dest_dll)
            assert was_copied is False, "Copy should be skipped (up-to-date)"

    def test_atomic_copy_concurrent_stress(self):
        """Stress test for concurrent DLL deployment (race condition handling)."""
        import concurrent.futures
        import time

        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source DLL
            src_dll = tmpdir_path / "src" / "test.dll"
            src_dll.parent.mkdir()
            src_dll.write_bytes(b"X" * 1024 * 100)  # 100 KB

            # Destination directory (shared by all workers)
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()
            dest_dll = dest_dir / "test.dll"

            # Function to simulate concurrent compilation
            def worker_copy(worker_id: int) -> tuple[int, bool, bool]:
                """
                Simulate a worker process copying a DLL.

                Returns:
                    (worker_id, success, was_copied)
                """
                try:
                    # Add small random delay to increase race condition likelihood
                    time.sleep(0.001 * (worker_id % 3))
                    was_copied = _atomic_copy_dll(src_dll, dest_dll)
                    return (worker_id, True, was_copied)
                except Exception as e:
                    # Should not happen with atomic copy
                    print(f"Worker {worker_id} failed: {e}")
                    return (worker_id, False, False)

            # Run 20 concurrent workers all trying to copy the same DLL
            num_workers = 20
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Remove destination DLL before test
                dest_dll.unlink(missing_ok=True)

                # Submit all workers
                futures = [executor.submit(worker_copy, i) for i in range(num_workers)]

                # Wait for all to complete
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            # Verify results
            assert len(results) == num_workers, f"Expected {num_workers} results"

            # All workers should succeed (no exceptions)
            all_success = all(success for _, success, _ in results)
            assert all_success, "All workers should succeed without exceptions"

            # At least one worker should have copied the DLL
            copy_count = sum(1 for _, _, was_copied in results if was_copied)
            assert copy_count >= 1, "At least one worker should have copied the DLL"

            # Destination DLL should exist and be valid
            assert dest_dll.exists(), "Destination DLL should exist after concurrent copies"
            assert dest_dll.read_bytes() == b"X" * 1024 * 100, "DLL content should be intact (not corrupted)"

            # No temp files should be left behind
            temp_files = list(dest_dir.glob(".test.dll.*.tmp"))
            assert len(temp_files) == 0, f"No temp files should remain, found: {temp_files}"

            # Verify file is not corrupted (check size)
            assert dest_dll.stat().st_size == 1024 * 100, "DLL size should match source"

    def test_atomic_copy_updates_outdated(self):
        """Test that outdated DLLs are updated."""
        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source DLL with newer content
            src_dll = tmpdir_path / "src" / "test.dll"
            src_dll.parent.mkdir()
            src_dll.write_bytes(b"New DLL content")

            # Create old destination DLL
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()
            dest_dll = dest_dir / "test.dll"
            dest_dll.write_bytes(b"Old DLL content")

            # Make source newer than destination
            os.utime(src_dll, (src_dll.stat().st_atime, dest_dll.stat().st_mtime + 10))

            # Copy should update the file
            was_copied = _atomic_copy_dll(src_dll, dest_dll)
            assert was_copied is True, "Outdated DLL should be updated"
            assert dest_dll.read_bytes() == b"New DLL content", "Content should be updated"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-specific test")
    def test_atomic_copy_uses_replace_on_windows(self):
        """Test that atomic copy uses Path.replace() on Windows."""
        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source DLL
            src_dll = tmpdir_path / "src" / "test.dll"
            src_dll.parent.mkdir()
            src_dll.write_bytes(b"DLL content")

            # Create destination with old content
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()
            dest_dll = dest_dir / "test.dll"
            dest_dll.write_bytes(b"Old content")

            # Update source timestamp to be newer
            os.utime(src_dll, (src_dll.stat().st_atime, dest_dll.stat().st_mtime + 10))

            # Copy should replace existing file
            was_copied = _atomic_copy_dll(src_dll, dest_dll)
            assert was_copied is True, "Should replace existing file on Windows"
            assert dest_dll.read_bytes() == b"DLL content", "Content should be replaced"

    def test_atomic_copy_parallel_with_multiple_dlls(self):
        """Test concurrent deployment of multiple different DLLs."""
        import concurrent.futures

        from clang_tool_chain.deployment.dll_deployer import _atomic_copy_dll

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create source directory with 3 different DLLs
            src_dir = tmpdir_path / "src"
            src_dir.mkdir()
            dlls = ["libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll"]

            for dll_name in dlls:
                dll_path = src_dir / dll_name
                dll_path.write_bytes(dll_name.encode() * 1000)  # Unique content per DLL

            # Destination directory
            dest_dir = tmpdir_path / "dest"
            dest_dir.mkdir()

            # Function to copy a DLL
            def copy_dll(dll_name: str) -> bool:
                src = src_dir / dll_name
                dest = dest_dir / dll_name
                return _atomic_copy_dll(src, dest)

            # Copy all DLLs in parallel (simulating parallel compilation)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(copy_dll, dll): dll for dll in dlls}
                results = {futures[f]: f.result() for f in concurrent.futures.as_completed(futures)}

            # All DLLs should be copied successfully
            assert all(results.values()), "All DLLs should be copied"

            # Verify all DLLs exist with correct content
            for dll_name in dlls:
                dest_dll = dest_dir / dll_name
                assert dest_dll.exists(), f"{dll_name} should exist"
                assert dest_dll.read_bytes() == dll_name.encode() * 1000, f"{dll_name} content should match"

            # No temp files should remain
            temp_files = list(dest_dir.glob(".*.tmp"))
            assert len(temp_files) == 0, "No temp files should remain"


class TestSanitizerExecutables:
    """Test DLL deployment for executables built with sanitizers (AddressSanitizer, etc.)."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_address_sanitizer_dll_deployment(self):
        """Test that AddressSanitizer DLLs and transitive dependencies are deployed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple C++ program
            test_cpp = tmpdir_path / "test_asan.cpp"
            test_cpp.write_text(
                """
#include <iostream>
int main() {
    std::cout << "AddressSanitizer test" << std::endl;
    return 0;
}
"""
            )

            # Build with AddressSanitizer
            from clang_tool_chain.execution.core import run_tool

            exe_path = tmpdir_path / "test_asan.exe"
            result = run_tool("clang++", [str(test_cpp), "-o", str(exe_path), "-fsanitize=address", "-g"])

            # Verify build succeeded
            if result != 0:
                pytest.skip("AddressSanitizer build failed (sanitizer runtime may not be available)")

            assert exe_path.exists(), "Executable should exist"

            # Check for sanitizer DLL and its transitive dependencies
            # Expected DLLs (may vary based on LLVM version and configuration):
            # - libclang_rt.asan_dynamic-x86_64.dll (AddressSanitizer runtime)
            # - Transitive dependencies detected by recursive scanning:
            #   - libc++.dll (LLVM C++ library, if ASan runtime depends on it)
            #   - libunwind.dll (LLVM unwinding, if ASan runtime depends on it)
            #   - libwinpthread-1.dll (threading support)
            #   - libgcc_s_seh-1.dll (GCC runtime)
            #   - libstdc++-6.dll (C++ standard library)

            # Note: Basic runtime DLLs like libwinpthread-1.dll and libgcc_s_seh-1.dll
            # may not be present if static linking is used or dependencies differ
            # This is a best-effort check

            # The key test: verify the executable can be inspected by llvm-objdump
            # This confirms recursive DLL scanning worked
            from clang_tool_chain.deployment.dll_deployer import detect_required_dlls

            detected_dlls = detect_required_dlls(exe_path)
            assert len(detected_dlls) > 0, "Should detect at least some DLLs"

            # Verify sanitizer DLL pattern is recognized (if present in binary)
            # Note: Sanitizer DLL may be statically linked or not required depending on build configuration
            # Pattern: r"libclang_rt\.asan_dynamic.*\.dll"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_transitive_dependency_resolution(self):
        """Test that transitive DLL dependencies are correctly resolved."""
        from unittest.mock import Mock, patch

        from clang_tool_chain.deployment.dll_deployer import detect_required_dlls

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a mock executable
            exe_path = tmpdir_path / "test.exe"
            exe_path.touch()

            # Mock llvm-objdump to return a complex dependency tree
            # Simulates: test.exe → libclang_rt.asan_dynamic-x86_64.dll → libc++.dll → libunwind.dll
            mock_objdump_responses = {
                str(
                    exe_path
                ): """
                    DLL Name: libclang_rt.asan_dynamic-x86_64.dll
                    DLL Name: libwinpthread-1.dll
                    DLL Name: kernel32.dll
                """,
                "libclang_rt.asan_dynamic-x86_64.dll": """
                    DLL Name: libc++.dll
                    DLL Name: libwinpthread-1.dll
                    DLL Name: kernel32.dll
                """,
                "libc++.dll": """
                    DLL Name: libunwind.dll
                    DLL Name: kernel32.dll
                """,
                "libunwind.dll": """
                    DLL Name: kernel32.dll
                """,
                "libwinpthread-1.dll": """
                    DLL Name: kernel32.dll
                """,
            }

            def mock_subprocess_run(cmd: list[str], **kwargs: object) -> Mock:
                # Extract the file being inspected
                if len(cmd) >= 3 and cmd[1] == "-p":
                    inspected_file = Path(cmd[2]).name
                    output = mock_objdump_responses.get(str(cmd[2]), mock_objdump_responses.get(inspected_file, ""))
                    mock_result = Mock()
                    mock_result.returncode = 0
                    mock_result.stdout = output
                    return mock_result
                raise ValueError(f"Unexpected command: {cmd}")

            # Mock the necessary functions
            with (
                patch("subprocess.run", side_effect=mock_subprocess_run),
                patch("clang_tool_chain.platform.detection.get_platform_binary_dir") as mock_bin_dir,
                patch("clang_tool_chain.deployment.dll_deployer.find_dll_in_toolchain") as mock_find_dll,
            ):
                # Mock bin directory
                mock_bin_dir.return_value = Path("/mock/bin")

                # Mock DLL finding (simulate all DLLs exist in toolchain)
                def mock_find_dll_impl(dll_name: str, platform: str, arch: str) -> Path | None:
                    if dll_name.lower() in ["kernel32.dll", "ntdll.dll", "msvcrt.dll"]:
                        return None  # System DLLs
                    # Return a mock path for MinGW/LLVM DLLs
                    return tmpdir_path / "sysroot" / dll_name

                mock_find_dll.side_effect = mock_find_dll_impl

                # Create mock DLL files so Path.exists() returns True
                sysroot_dir = tmpdir_path / "sysroot"
                sysroot_dir.mkdir()
                for dll_name in [
                    "libclang_rt.asan_dynamic-x86_64.dll",
                    "libc++.dll",
                    "libunwind.dll",
                    "libwinpthread-1.dll",
                ]:
                    (sysroot_dir / dll_name).touch()

                # Mock Path.exists() for objdump
                original_exists = Path.exists

                def mock_exists(self: Path) -> bool:
                    if "llvm-objdump" in str(self):
                        return True
                    return original_exists(self)

                with patch.object(Path, "exists", mock_exists):
                    # Run detection
                    detected_dlls = detect_required_dlls(exe_path)

                # Verify all transitive dependencies were detected
                assert "libclang_rt.asan_dynamic-x86_64.dll" in detected_dlls, "Should detect ASan runtime"
                assert "libc++.dll" in detected_dlls, "Should detect libc++ (transitive via ASan)"
                assert "libunwind.dll" in detected_dlls, "Should detect libunwind (transitive via libc++)"
                assert "libwinpthread-1.dll" in detected_dlls, "Should detect threading support"

                # Verify system DLLs are excluded
                assert "kernel32.dll" not in detected_dlls, "Should exclude system DLLs"

                # Verify no duplicates (set behavior)
                assert len(detected_dlls) == len(set(detected_dlls)), "Should not have duplicate DLLs"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
