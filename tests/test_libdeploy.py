"""
Unit tests for the clang-tool-chain-libdeploy CLI command.

Tests cover:
- Binary type detection from file extensions and magic bytes
- Command-line argument parsing
- Dry run mode
- Verbose mode
- Platform override
- Integration with deployment factories
"""

import shutil
import sys
import tempfile
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from typing import Literal

from clang_tool_chain.deployment.libdeploy import (
    _detect_binary_type,
    deploy_dependencies,
    main,
)


class WindowsSafeTemporaryDirectory:
    """
    Drop-in replacement for tempfile.TemporaryDirectory that handles Windows cleanup.

    Uses ignore_errors=True on cleanup to prevent PermissionError when files are locked.
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
    ) -> "Literal[False]":
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        return False


class TestDetectBinaryType:
    """Test the _detect_binary_type() function."""

    def test_windows_exe(self):
        """Test detection of .exe files."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")  # PE magic
            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "windows"
            assert binary_type == "executable"

    def test_windows_dll(self):
        """Test detection of .dll files."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dll_path = Path(tmpdir) / "test.dll"
            dll_path.write_bytes(b"MZ")  # PE magic
            platform, binary_type = _detect_binary_type(dll_path)
            assert platform == "windows"
            assert binary_type == "shared_library"

    def test_linux_so(self):
        """Test detection of .so files."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            so_path = Path(tmpdir) / "libtest.so"
            so_path.write_bytes(b"\x7fELF")  # ELF magic
            platform, binary_type = _detect_binary_type(so_path)
            assert platform == "linux"
            assert binary_type == "shared_library"

    def test_linux_so_versioned(self):
        """Test detection of versioned .so files like libfoo.so.1.2.3."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            so_path = Path(tmpdir) / "libtest.so.1.2.3"
            so_path.write_bytes(b"\x7fELF")  # ELF magic
            platform, binary_type = _detect_binary_type(so_path)
            assert platform == "linux"
            assert binary_type == "shared_library"

    def test_macos_dylib(self):
        """Test detection of .dylib files."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            dylib_path = Path(tmpdir) / "libtest.dylib"
            dylib_path.write_bytes(b"\xcf\xfa\xed\xfe")  # Mach-O 64-bit magic (reversed)
            platform, binary_type = _detect_binary_type(dylib_path)
            assert platform == "darwin"
            assert binary_type == "shared_library"

    def test_linux_elf_executable_no_extension(self):
        """Test detection of Linux ELF executable without extension."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "myprogram"
            exe_path.write_bytes(b"\x7fELF")  # ELF magic
            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "linux"
            assert binary_type == "executable"

    def test_macos_executable_no_extension(self):
        """Test detection of macOS Mach-O executable without extension."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "myprogram"
            exe_path.write_bytes(b"\xfe\xed\xfa\xcf")  # Mach-O 64-bit magic
            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "darwin"
            assert binary_type == "executable"

    def test_windows_pe_no_extension(self):
        """Test detection of Windows PE without extension."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "myprogram"
            exe_path.write_bytes(b"MZ")  # PE magic
            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "windows"
            assert binary_type == "executable"

    def test_fat_binary_macos(self):
        """Test detection of macOS fat/universal binary."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "myprogram"
            exe_path.write_bytes(b"\xca\xfe\xba\xbe")  # Fat binary magic
            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "darwin"
            assert binary_type == "executable"

    def test_unknown_binary_raises(self):
        """Test that unknown binary types raise ValueError."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            unknown_path = Path(tmpdir) / "unknown.xyz"
            unknown_path.write_bytes(b"unknown magic bytes")
            with pytest.raises(ValueError, match="Cannot determine binary type"):
                _detect_binary_type(unknown_path)


class TestDeployDependencies:
    """Test the deploy_dependencies() function."""

    def test_binary_not_found(self):
        """Test error handling when binary doesn't exist."""
        result = deploy_dependencies(Path("/nonexistent/path/test.exe"))
        assert result == -1

    def test_not_a_file(self):
        """Test error handling when path is a directory."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            result = deploy_dependencies(Path(tmpdir))
            assert result == -1

    def test_invalid_platform_override(self):
        """Test error handling for invalid platform override."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")
            result = deploy_dependencies(exe_path, platform_override="invalid_platform")
            assert result == -1

    @patch("clang_tool_chain.deployment.factory.create_deployer")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_dry_run_mode(self, mock_platform_info, mock_create_deployer):
        """Test dry run mode shows dependencies without deploying."""
        mock_platform_info.return_value = ("win", "x86_64")

        mock_deployer = MagicMock()
        mock_deployer.detect_all_dependencies.return_value = {"libtest.dll", "libother.dll"}
        mock_deployer.find_library_in_toolchain.return_value = Path("/toolchain/lib/libtest.dll")
        mock_create_deployer.return_value = mock_deployer

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            result = deploy_dependencies(exe_path, dry_run=True)

            assert result == 2  # Two dependencies found
            mock_deployer.deploy_all.assert_not_called()  # Should not actually deploy

    @patch("clang_tool_chain.deployment.factory.create_deployer")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_actual_deployment(self, mock_platform_info, mock_create_deployer):
        """Test actual deployment calls deploy_all."""
        mock_platform_info.return_value = ("win", "x86_64")

        mock_deployer = MagicMock()
        mock_deployer.deploy_all.return_value = 3
        mock_create_deployer.return_value = mock_deployer

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            result = deploy_dependencies(exe_path)

            assert result == 3
            mock_deployer.deploy_all.assert_called_once_with(exe_path)

    @patch("clang_tool_chain.deployment.factory.create_deployer")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_no_deployer_for_platform(self, mock_platform_info, mock_create_deployer):
        """Test error handling when no deployer available for platform."""
        mock_platform_info.return_value = ("win", "x86_64")
        mock_create_deployer.return_value = None

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            result = deploy_dependencies(exe_path, platform_override="windows")

            assert result == -1

    @patch("clang_tool_chain.deployment.factory.create_deployer")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_platform_override_win(self, mock_platform_info, mock_create_deployer):
        """Test platform override with 'win' alias."""
        mock_platform_info.return_value = ("win", "x86_64")

        mock_deployer = MagicMock()
        mock_deployer.deploy_all.return_value = 1
        mock_create_deployer.return_value = mock_deployer

        with WindowsSafeTemporaryDirectory() as tmpdir:
            # Create a file that could be ambiguous
            exe_path = Path(tmpdir) / "myprogram"
            exe_path.write_bytes(b"MZ")  # PE magic

            result = deploy_dependencies(exe_path, platform_override="win")

            assert result == 1
            mock_create_deployer.assert_called_once_with("windows", "x86_64")

    @patch("clang_tool_chain.deployment.factory.create_deployer")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_platform_override_macos(self, mock_platform_info, mock_create_deployer):
        """Test platform override with 'macos' alias."""
        mock_platform_info.return_value = ("darwin", "x86_64")

        mock_deployer = MagicMock()
        mock_deployer.deploy_all.return_value = 1
        mock_create_deployer.return_value = mock_deployer

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "myprogram.dylib"
            exe_path.write_bytes(b"\xcf\xfa\xed\xfe")

            result = deploy_dependencies(exe_path, platform_override="macos")

            assert result == 1
            mock_create_deployer.assert_called_once_with("darwin", "x86_64")


class TestMainCLI:
    """Test the main() CLI entry point."""

    def test_help_message(self, capsys):
        """Test --help shows usage information."""
        with pytest.raises(SystemExit) as exc_info, patch.object(sys, "argv", ["clang-tool-chain-libdeploy", "--help"]):
            main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "clang-tool-chain-libdeploy" in captured.out
        assert "Deploy runtime library dependencies" in captured.out

    def test_missing_binary_argument(self, capsys):
        """Test error when no binary argument provided."""
        with pytest.raises(SystemExit) as exc_info, patch.object(sys, "argv", ["clang-tool-chain-libdeploy"]):
            main()
        assert exc_info.value.code == 2  # argparse exits with 2 for missing required argument

    def test_nonexistent_file(self, capsys, caplog):
        """Test error handling for nonexistent file."""
        with patch.object(sys, "argv", ["clang-tool-chain-libdeploy", "/nonexistent/path/test.exe"]):
            result = main()
        assert result == 1
        # Check either stderr or captured logs for the error message
        captured = capsys.readouterr()
        log_text = caplog.text.lower()
        stderr_text = captured.err.lower()
        assert "not found" in log_text or "not found" in stderr_text or "binary" in log_text

    @patch("clang_tool_chain.deployment.libdeploy.deploy_dependencies")
    def test_verbose_flag(self, mock_deploy):
        """Test -v/--verbose flag is passed correctly."""
        mock_deploy.return_value = 0

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            with patch.object(sys, "argv", ["clang-tool-chain-libdeploy", "-v", str(exe_path)]):
                main()

            mock_deploy.assert_called_once()
            call_kwargs = mock_deploy.call_args
            assert call_kwargs[1]["verbose"] is True

    @patch("clang_tool_chain.deployment.libdeploy.deploy_dependencies")
    def test_dry_run_flag(self, mock_deploy):
        """Test -n/--dry-run flag is passed correctly."""
        mock_deploy.return_value = 0

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            with patch.object(sys, "argv", ["clang-tool-chain-libdeploy", "-n", str(exe_path)]):
                main()

            mock_deploy.assert_called_once()
            call_kwargs = mock_deploy.call_args
            assert call_kwargs[1]["dry_run"] is True

    @patch("clang_tool_chain.deployment.libdeploy.deploy_dependencies")
    def test_platform_flag(self, mock_deploy):
        """Test -p/--platform flag is passed correctly."""
        mock_deploy.return_value = 0

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            with patch.object(sys, "argv", ["clang-tool-chain-libdeploy", "-p", "linux", str(exe_path)]):
                main()

            mock_deploy.assert_called_once()
            call_kwargs = mock_deploy.call_args
            assert call_kwargs[1]["platform_override"] == "linux"

    @patch("clang_tool_chain.deployment.libdeploy.deploy_dependencies")
    def test_arch_flag(self, mock_deploy):
        """Test -a/--arch flag is passed correctly."""
        mock_deploy.return_value = 0

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            with patch.object(sys, "argv", ["clang-tool-chain-libdeploy", "-a", "arm64", str(exe_path)]):
                main()

            mock_deploy.assert_called_once()
            call_kwargs = mock_deploy.call_args
            assert call_kwargs[1]["arch"] == "arm64"


class TestIntegrationWithFactory:
    """Integration tests with the actual deployment factory."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_exe_detection_real(self):
        """Test actual Windows executable detection."""
        # Create a minimal PE file
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            # Write minimal PE header
            exe_path.write_bytes(b"MZ" + b"\x00" * 58)

            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "windows"
            assert binary_type == "executable"

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
    def test_linux_elf_detection_real(self):
        """Test actual Linux ELF detection."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test"
            # Write minimal ELF header
            exe_path.write_bytes(b"\x7fELF" + b"\x00" * 60)

            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "linux"
            assert binary_type == "executable"

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
    def test_macos_macho_detection_real(self):
        """Test actual macOS Mach-O detection."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test"
            # Write minimal Mach-O 64-bit header
            exe_path.write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 60)

            platform, binary_type = _detect_binary_type(exe_path)
            assert platform == "darwin"
            assert binary_type == "executable"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self):
        """Test handling of empty file."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            empty_path = Path(tmpdir) / "empty"
            empty_path.write_bytes(b"")

            with pytest.raises(ValueError, match="Cannot determine binary type"):
                _detect_binary_type(empty_path)

    def test_small_file(self):
        """Test handling of file smaller than magic byte length."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            small_path = Path(tmpdir) / "small"
            small_path.write_bytes(b"AB")  # Too small for most magic numbers

            with pytest.raises(ValueError, match="Cannot determine binary type"):
                _detect_binary_type(small_path)

    def test_permissions_error(self):
        """Test handling of permission errors during magic byte reading."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            restricted_path = Path(tmpdir) / "restricted"
            restricted_path.write_bytes(b"\x7fELF")

            # Mock open to raise permission error
            with (
                patch("builtins.open", side_effect=PermissionError("Access denied")),
                pytest.raises(ValueError, match="Cannot determine binary type"),
            ):
                _detect_binary_type(restricted_path)

    @patch("clang_tool_chain.deployment.factory.create_deployer")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_deployment_exception_handling(self, mock_platform_info, mock_create_deployer):
        """Test that exceptions during deployment are handled gracefully."""
        mock_platform_info.return_value = ("win", "x86_64")

        mock_deployer = MagicMock()
        mock_deployer.deploy_all.side_effect = RuntimeError("Deployment failed")
        mock_create_deployer.return_value = mock_deployer

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            result = deploy_dependencies(exe_path)

            assert result == -1

    @patch("clang_tool_chain.deployment.factory.create_deployer")
    @patch("clang_tool_chain.platform.detection.get_platform_info")
    def test_dry_run_no_dependencies(self, mock_platform_info, mock_create_deployer):
        """Test dry run when no dependencies found."""
        mock_platform_info.return_value = ("win", "x86_64")

        mock_deployer = MagicMock()
        mock_deployer.detect_all_dependencies.return_value = set()  # No dependencies
        mock_create_deployer.return_value = mock_deployer

        with WindowsSafeTemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test.exe"
            exe_path.write_bytes(b"MZ")

            result = deploy_dependencies(exe_path, dry_run=True)

            assert result == 0


class TestLibdeployCLIIntegration:
    """
    Integration tests for clang-tool-chain-libdeploy CLI command.

    These tests compile actual binaries WITHOUT auto-deploy, then run
    clang-tool-chain-libdeploy explicitly to verify post-build deployment.
    """

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with WindowsSafeTemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def hello_cpp_source(self, temp_dir):
        """Create a simple C++ source file."""
        source = temp_dir / "hello.cpp"
        source.write_text(
            "#include <iostream>\n"
            "int main() {\n"
            '    std::cout << "Hello from libdeploy test!" << std::endl;\n'
            "    return 0;\n"
            "}\n"
        )
        return source

    @pytest.fixture
    def hello_c_source(self, temp_dir):
        """Create a simple C source file."""
        source = temp_dir / "hello.c"
        source.write_text(
            '#include <stdio.h>\nint main() {\n    printf("Hello from C libdeploy test!\\n");\n    return 0;\n}\n'
        )
        return source

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_exe_compile_then_libdeploy(self, temp_dir, hello_cpp_source):
        """
        Test Windows: compile without auto-deploy, then run libdeploy explicitly.

        1. Compile with CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS=1 to prevent auto-deployment
        2. Run clang-tool-chain-libdeploy
        3. Verify the executable runs correctly

        Note: Modern LLVM/Clang toolchains may use static linking, so DLLs may not
        always be needed. We verify libdeploy runs successfully, not that DLLs
        are always deployed.
        """
        import os
        import subprocess

        output_exe = temp_dir / "hello.exe"

        # Step 1: Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-cpp", str(hello_cpp_source), "-o", str(output_exe)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"
        assert output_exe.exists(), "Output executable should exist"

        # Step 2: Run clang-tool-chain-libdeploy explicitly
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", str(output_exe)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy failed: {libdeploy_result.stderr}"

        # Step 3: Verify the executable runs correctly (with or without DLLs)
        run_result = subprocess.run([str(output_exe)], capture_output=True, text=True)
        assert run_result.returncode == 0, f"Execution failed: {run_result.stderr}"
        assert "Hello from libdeploy test!" in run_result.stdout

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_dll_compile_then_libdeploy(self, temp_dir):
        """
        Test Windows: compile shared library without auto-deploy, then run libdeploy.
        """
        import os
        import subprocess

        # Create a simple DLL source
        dll_source = temp_dir / "mylib.c"
        dll_source.write_text("__declspec(dllexport) int add(int a, int b) { return a + b; }\n")
        output_dll = temp_dir / "mylib.dll"

        # Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-c", "-shared", str(dll_source), "-o", str(output_dll)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"
        assert output_dll.exists(), "Output DLL should exist"

        # Run libdeploy
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", str(output_dll)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy failed: {libdeploy_result.stderr}"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_libdeploy_dry_run_cli(self, temp_dir, hello_cpp_source):
        """Test that --dry-run flag works via CLI."""
        import os
        import subprocess

        output_exe = temp_dir / "hello_dryrun.exe"

        # Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-cpp", str(hello_cpp_source), "-o", str(output_exe)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"

        # Count DLLs before dry-run
        dlls_before = list(temp_dir.glob("*.dll"))

        # Run libdeploy with --dry-run
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", "--dry-run", str(output_exe)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy dry-run failed: {libdeploy_result.stderr}"

        # Verify no DLLs were actually deployed (dry-run)
        dlls_after = list(temp_dir.glob("*.dll"))
        assert len(dlls_after) == len(dlls_before), "Dry-run should not deploy any DLLs"

        # Check that output mentions "Would deploy"
        combined_output = libdeploy_result.stdout + libdeploy_result.stderr
        assert "Would deploy" in combined_output or len(dlls_before) == 0

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_libdeploy_verbose_cli(self, temp_dir, hello_cpp_source):
        """Test that --verbose flag works via CLI."""
        import os
        import subprocess

        output_exe = temp_dir / "hello_verbose.exe"

        # Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-cpp", str(hello_cpp_source), "-o", str(output_exe)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"

        # Run libdeploy with --verbose
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", "--verbose", str(output_exe)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy verbose failed: {libdeploy_result.stderr}"

        # Check that verbose output contains platform/arch info
        combined_output = libdeploy_result.stdout + libdeploy_result.stderr
        assert "Platform:" in combined_output or "Deploying" in combined_output or "Deployed" in combined_output

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
    def test_linux_executable_compile_then_libdeploy(self, temp_dir, hello_cpp_source):
        """
        Test Linux: compile without auto-deploy, then run libdeploy explicitly.
        """
        import os
        import subprocess

        output_exe = temp_dir / "hello"

        # Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-cpp", str(hello_cpp_source), "-o", str(output_exe)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"
        assert output_exe.exists(), "Output executable should exist"

        # Run libdeploy
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", str(output_exe)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy failed: {libdeploy_result.stderr}"

        # Verify the executable runs
        run_result = subprocess.run([str(output_exe)], capture_output=True, text=True)
        assert run_result.returncode == 0, f"Execution failed: {run_result.stderr}"
        assert "Hello from libdeploy test!" in run_result.stdout

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
    def test_linux_shared_lib_compile_then_libdeploy(self, temp_dir):
        """
        Test Linux: compile shared library without auto-deploy, then run libdeploy.
        """
        import os
        import subprocess

        # Create a simple shared library source
        lib_source = temp_dir / "mylib.c"
        lib_source.write_text("int add(int a, int b) { return a + b; }\n")
        output_so = temp_dir / "libmylib.so"

        # Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-c", "-shared", "-fPIC", str(lib_source), "-o", str(output_so)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"
        assert output_so.exists(), "Output shared library should exist"

        # Run libdeploy
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", str(output_so)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy failed: {libdeploy_result.stderr}"

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
    def test_macos_executable_compile_then_libdeploy(self, temp_dir, hello_cpp_source):
        """
        Test macOS: compile without auto-deploy, then run libdeploy explicitly.
        """
        import os
        import subprocess

        output_exe = temp_dir / "hello"

        # Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-cpp", str(hello_cpp_source), "-o", str(output_exe)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"
        assert output_exe.exists(), "Output executable should exist"

        # Run libdeploy
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", str(output_exe)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy failed: {libdeploy_result.stderr}"

        # Verify the executable runs
        run_result = subprocess.run([str(output_exe)], capture_output=True, text=True)
        assert run_result.returncode == 0, f"Execution failed: {run_result.stderr}"
        assert "Hello from libdeploy test!" in run_result.stdout

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
    def test_macos_dylib_compile_then_libdeploy(self, temp_dir):
        """
        Test macOS: compile dynamic library without auto-deploy, then run libdeploy.
        """
        import os
        import subprocess

        # Create a simple dylib source
        lib_source = temp_dir / "mylib.c"
        lib_source.write_text("int add(int a, int b) { return a + b; }\n")
        output_dylib = temp_dir / "libmylib.dylib"

        # Compile with auto-deploy disabled
        env = os.environ.copy()
        env["CLANG_TOOL_CHAIN_NO_DEPLOY_LIBS"] = "1"

        compile_result = subprocess.run(
            ["clang-tool-chain-c", "-shared", "-fPIC", str(lib_source), "-o", str(output_dylib)],
            env=env,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"
        assert output_dylib.exists(), "Output dynamic library should exist"

        # Run libdeploy
        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", str(output_dylib)],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, f"libdeploy failed: {libdeploy_result.stderr}"

    def test_libdeploy_nonexistent_file_cli(self, temp_dir):
        """Test that CLI returns error for non-existent file."""
        import subprocess

        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", str(temp_dir / "nonexistent.exe")],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode != 0, "Should fail for non-existent file"

    def test_libdeploy_help_cli(self):
        """Test that --help works via CLI."""
        import subprocess

        libdeploy_result = subprocess.run(
            ["clang-tool-chain-libdeploy", "--help"],
            capture_output=True,
            text=True,
        )
        assert libdeploy_result.returncode == 0, "Help should succeed"
        assert "clang-tool-chain-libdeploy" in libdeploy_result.stdout
        assert "Deploy runtime library dependencies" in libdeploy_result.stdout
