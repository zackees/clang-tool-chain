"""
Unit tests for CLI functionality.

These tests verify the command-line interface works correctly.
"""

import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from clang_tool_chain import cli


class TestCLICommands(unittest.TestCase):
    """Test CLI command functions."""

    @patch("clang_tool_chain.cli.wrapper.get_platform_binary_dir")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.wrapper.get_assets_dir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_info_no_binaries(
        self, mock_stdout: StringIO, mock_assets_dir: Mock, mock_platform: Mock, mock_bin_dir: Mock
    ) -> None:
        """Test info command when binaries are not installed."""
        mock_platform.return_value = ("linux", "x86_64")
        mock_assets_dir.return_value = Path("/fake/assets")
        mock_bin_dir.side_effect = RuntimeError("Binary directory not found")

        args = MagicMock()
        result = cli.cmd_info(args)

        output = mock_stdout.getvalue()
        self.assertIn("Clang Tool Chain", output)
        self.assertIn("linux", output)
        self.assertIn("x86_64", output)
        self.assertIn("Binaries installed: No", output)
        self.assertEqual(result, 0)

    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_list_tools(self, mock_stdout: StringIO) -> None:
        """Test list-tools command."""
        args = MagicMock()
        result = cli.cmd_list_tools(args)

        output = mock_stdout.getvalue()
        self.assertIn("clang-tool-chain-c", output)
        self.assertIn("clang-tool-chain-cpp", output)
        self.assertIn("clang-tool-chain-ld", output)
        self.assertIn("C compiler (clang)", output)
        self.assertIn("clang-tool-chain-ar", output)
        self.assertIn("clang-tool-chain-format", output)
        # Check sccache wrappers are listed
        self.assertIn("clang-tool-chain-sccache", output)
        self.assertIn("clang-tool-chain-sccache-c", output)
        self.assertIn("clang-tool-chain-sccache-cpp", output)
        self.assertIn("sccache", output.lower())
        self.assertEqual(result, 0)

    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.wrapper.run_tool")
    def test_cmd_version_success(self, mock_run_tool: Mock, mock_find: Mock) -> None:
        """Test version command with successful execution."""
        mock_find.return_value = Path("/fake/bin/clang")
        mock_run_tool.return_value = 0

        args = MagicMock()
        args.tool = "clang"

        result = cli.cmd_version(args)

        self.assertEqual(result, 0)
        mock_run_tool.assert_called_once_with("clang", ["--version"])

    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("sys.stderr", new_callable=StringIO)
    def test_cmd_version_tool_not_found(self, mock_stderr: StringIO, mock_find: Mock) -> None:
        """Test version command when tool is not found."""
        mock_find.side_effect = RuntimeError("Tool not found")

        args = MagicMock()
        args.tool = "nonexistent"

        result = cli.cmd_version(args)

        self.assertEqual(result, 1)
        self.assertIn("Error", mock_stderr.getvalue())

    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_path_tool(self, mock_stdout: StringIO, mock_find: Mock) -> None:
        """Test path command with a specific tool."""
        mock_find.return_value = Path("/fake/bin/clang")

        args = MagicMock()
        args.tool = "clang"

        result = cli.cmd_path(args)

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        # Path separator may be / or \ depending on platform
        self.assertTrue("fake" in output and "bin" in output and "clang" in output)

    @patch("clang_tool_chain.cli.wrapper.get_platform_binary_dir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_path_no_tool(self, mock_stdout: StringIO, mock_bin_dir: Mock) -> None:
        """Test path command without a specific tool."""
        mock_bin_dir.return_value = Path("/fake/bin")

        args = MagicMock()
        args.tool = None

        result = cli.cmd_path(args)

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        # Path separator may be / or \ depending on platform
        self.assertTrue("fake" in output and "bin" in output)

    def test_tool_name_mapping(self) -> None:
        """Test that common tool name mappings work."""
        with (
            patch("clang_tool_chain.cli.wrapper.find_tool_binary") as mock_find,
            patch("clang_tool_chain.cli.wrapper.run_tool") as mock_run,
        ):
            mock_find.return_value = Path("/fake/bin/clang++")
            mock_run.return_value = 0

            args = MagicMock()
            args.tool = "cpp"

            cli.cmd_version(args)

            # Should map "cpp" to "clang++"
            mock_run.assert_called_once_with("clang++", ["--version"])

    @patch("clang_tool_chain.downloader.get_home_toolchain_dir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_purge_no_directory(self, mock_stdout: StringIO, mock_get_dir: Mock) -> None:
        """Test purge command when toolchain directory doesn't exist."""
        fake_dir = Path("/fake/toolchain")
        mock_get_dir.return_value = fake_dir

        args = MagicMock()
        args.yes = False

        result = cli.cmd_purge(args)

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("No toolchain directory found", output)

    @patch("clang_tool_chain.downloader._robust_rmtree")
    @patch("clang_tool_chain.downloader.get_home_toolchain_dir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_purge_with_yes_flag(self, mock_stdout: StringIO, mock_get_dir: Mock, mock_rmtree: Mock) -> None:
        """Test purge command with --yes flag (skip confirmation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "toolchain"
            fake_dir.mkdir()
            (fake_dir / "test.txt").write_text("test")
            mock_get_dir.return_value = fake_dir

            args = MagicMock()
            args.yes = True

            result = cli.cmd_purge(args)

            self.assertEqual(result, 0)
            mock_rmtree.assert_called_once_with(fake_dir)
            output = mock_stdout.getvalue()
            self.assertIn("Successfully removed", output)

    @patch("builtins.input", return_value="n")
    @patch("clang_tool_chain.downloader.get_home_toolchain_dir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_purge_cancel(self, mock_stdout: StringIO, mock_get_dir: Mock, mock_input: Mock) -> None:
        """Test purge command when user cancels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_dir = Path(tmpdir) / "toolchain"
            fake_dir.mkdir()
            (fake_dir / "test.txt").write_text("test")
            mock_get_dir.return_value = fake_dir

            args = MagicMock()
            args.yes = False

            result = cli.cmd_purge(args)

            self.assertEqual(result, 0)
            output = mock_stdout.getvalue()
            self.assertIn("Purge cancelled", output)


class TestCLIMain(unittest.TestCase):
    """Test main CLI entry point."""

    @patch("sys.argv", ["clang-tool-chain", "--help"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_help(self, mock_stdout: StringIO) -> None:
        """Test main with --help flag."""
        try:
            cli.main()
        except SystemExit as e:
            # argparse exits with 0 for --help
            self.assertEqual(e.code, 0)

        output = mock_stdout.getvalue()
        self.assertIn("clang-tool-chain", output)
        self.assertIn("llvm/clang", output.lower())

    @patch("sys.argv", ["clang-tool-chain"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_no_command(self, mock_stdout: StringIO) -> None:
        """Test main with no command shows help."""
        result = cli.main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("usage", output.lower())

    @patch("sys.argv", ["clang-tool-chain", "list-tools"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_list_tools(self, mock_stdout: StringIO) -> None:
        """Test main with list-tools command."""
        result = cli.main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("clang-tool-chain-c", output)

    @patch("sys.argv", ["clang-tool-chain", "package-version"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_package_version(self, mock_stdout: StringIO) -> None:
        """Test main with package-version command."""
        result = cli.main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("version", output.lower())

    @patch("sys.argv", ["clang-tool-chain", "--version"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_version_flag(self, mock_stdout: StringIO) -> None:
        """Test main with --version flag."""
        try:
            cli.main()
        except SystemExit as e:
            # argparse exits with 0 for --version
            self.assertEqual(e.code, 0)

        output = mock_stdout.getvalue()
        self.assertIn("clang-tool-chain", output)
        # Should contain version number pattern
        import re

        self.assertTrue(re.search(r"\d+\.\d+\.\d+", output), "Should contain version number")

    @patch("sys.argv", ["clang-tool-chain", "-V"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_version_flag_short(self, mock_stdout: StringIO) -> None:
        """Test main with -V flag (short version)."""
        try:
            cli.main()
        except SystemExit as e:
            # argparse exits with 0 for -V
            self.assertEqual(e.code, 0)

        output = mock_stdout.getvalue()
        self.assertIn("clang-tool-chain", output)
        # Should contain version number pattern
        import re

        self.assertTrue(re.search(r"\d+\.\d+\.\d+", output), "Should contain version number")


class TestSccacheWrappers(unittest.TestCase):
    """Test sccache wrapper commands."""

    @patch("sys.argv", ["clang-tool-chain-sccache", "--show-stats"])
    @patch("clang_tool_chain.sccache_runner.subprocess.run")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.sccache_runner.get_sccache_path")
    def test_sccache_main_passthrough_windows(self, mock_which: Mock, mock_platform: Mock, mock_run: Mock) -> None:
        """Test sccache_main passthrough on Windows."""
        mock_which.return_value = "C:\\path\\to\\sccache.exe"
        mock_platform.return_value = ("win", "x86_64")
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        result = cli.sccache_main()

        self.assertEqual(result, 0)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, ["C:\\path\\to\\sccache.exe", "--show-stats"])

    @patch("sys.argv", ["clang-tool-chain-sccache", "--zero-stats"])
    @patch("clang_tool_chain.sccache_runner.subprocess.run")
    @patch("clang_tool_chain.sccache_runner.get_sccache_path")
    def test_sccache_main_passthrough_unix(self, mock_which: Mock, mock_run: Mock) -> None:
        """Test sccache_main passthrough on Unix."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        result = cli.sccache_main()

        self.assertEqual(result, 0)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, ["/usr/bin/sccache", "--zero-stats"])

    @patch("sys.argv", ["clang-tool-chain-sccache", "--version"])
    @patch("clang_tool_chain.sccache_runner.get_sccache_path")
    @patch("clang_tool_chain.sccache_runner.run_sccache_via_isoenv")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_main_not_found(self, mock_stderr: StringIO, mock_isoenv: Mock, mock_which: Mock) -> None:
        """Test sccache_main when sccache is not in PATH."""
        mock_which.return_value = None
        mock_isoenv.return_value = 0

        result = cli.sccache_main()

        self.assertEqual(result, 0)
        error_output = mock_stderr.getvalue()
        self.assertIn("isolated environment", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache", "--show-stats"])
    @patch("clang_tool_chain.sccache_runner.subprocess.run")
    @patch("clang_tool_chain.sccache_runner.get_sccache_path")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_main_execution_error(self, mock_stderr: StringIO, mock_which: Mock, mock_run: Mock) -> None:
        """Test sccache_main with execution error."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_run.side_effect = Exception("Unexpected error")

        result = cli.sccache_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Failed to execute sccache", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c", "-o", "main"])
    @patch("clang_tool_chain.sccache_runner.subprocess.run")
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("clang_tool_chain.execution.core.get_platform_info")
    def test_sccache_c_main_success_windows(
        self, mock_platform: Mock, mock_sccache: Mock, mock_find: Mock, mock_run: Mock
    ) -> None:
        """Test sccache_c_main on Windows with successful execution."""
        mock_platform.return_value = ("win", "x86_64")
        mock_sccache.return_value = "C:\\path\\to\\sccache.exe"
        mock_find.return_value = Path("C:\\path\\to\\clang.exe")
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_c_main()

        self.assertEqual(cm.exception.code, 0)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "C:\\path\\to\\sccache.exe")
        self.assertIn("clang.exe", str(call_args[1]))
        # On Windows, GNU ABI flags are added, so check for them
        args_list = list(call_args[2:])
        self.assertIn("--target=x86_64-w64-windows-gnu", args_list)
        self.assertIn("main.c", args_list)
        self.assertIn("-o", args_list)
        self.assertIn("main", args_list)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c", "-o", "main"])
    @patch("os.execv")
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("clang_tool_chain.execution.core.get_platform_info")
    def test_sccache_c_main_success_unix(
        self, mock_platform: Mock, mock_sccache: Mock, mock_find: Mock, mock_execv: Mock
    ) -> None:
        """Test sccache_c_main on Unix with successful execution."""
        mock_platform.return_value = ("linux", "x86_64")
        mock_sccache.return_value = "/usr/bin/sccache"
        mock_find.return_value = Path("/home/.clang-tool-chain/clang/linux/x86_64/bin/clang")

        cli.sccache_c_main()

        mock_execv.assert_called_once()
        call_args = mock_execv.call_args[0]
        # First arg is sccache path, second is full command list
        self.assertEqual(call_args[0], "/usr/bin/sccache")
        cmd_list = call_args[1]
        self.assertEqual(cmd_list[0], "/usr/bin/sccache")
        self.assertIn("clang", str(cmd_list[1]))
        # On Linux, lld linker flags are added
        args_list = list(cmd_list[2:])
        self.assertIn("-fuse-ld=lld", args_list)
        self.assertIn("main.c", args_list)
        self.assertIn("-o", args_list)
        self.assertIn("main", args_list)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c"])
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_c_main_sccache_not_found(self, mock_stderr: StringIO, mock_sccache: Mock, mock_find: Mock) -> None:
        """Test sccache_c_main when sccache is not found."""
        mock_sccache.side_effect = RuntimeError("sccache binary not found")
        mock_find.return_value = "/fake/path/to/clang"

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_c_main()

        self.assertEqual(cm.exception.code, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("sccache binary not found", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c"])
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_c_main_clang_not_found(self, mock_stderr: StringIO, mock_sccache: Mock, mock_find: Mock) -> None:
        """Test sccache_c_main when clang binary is not found."""
        mock_sccache.return_value = "/usr/bin/sccache"
        mock_find.side_effect = RuntimeError("clang binary not found in installation")

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_c_main()

        self.assertEqual(cm.exception.code, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("clang binary not found in installation", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c"])
    @patch("subprocess.run")
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("clang_tool_chain.execution.core.get_platform_info")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_c_main_execution_error(
        self, mock_stderr: StringIO, mock_platform: Mock, mock_sccache: Mock, mock_find: Mock, mock_run: Mock
    ) -> None:
        """Test sccache_c_main when execution fails."""
        mock_platform.return_value = ("win", "x86_64")
        mock_sccache.return_value = "C:\\path\\to\\sccache.exe"
        mock_find.return_value = Path("C:\\path\\to\\clang.exe")
        mock_run.side_effect = FileNotFoundError("sccache.exe not found")

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_c_main()

        self.assertEqual(cm.exception.code, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Error executing sccache", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp", "-o", "main", "-std=c++17"])
    @patch("clang_tool_chain.sccache_runner.subprocess.run")
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("clang_tool_chain.execution.core.get_platform_info")
    def test_sccache_cpp_main_success_windows(
        self, mock_platform: Mock, mock_sccache: Mock, mock_find: Mock, mock_run: Mock
    ) -> None:
        """Test sccache_cpp_main on Windows with successful execution."""
        mock_platform.return_value = ("win", "x86_64")
        mock_sccache.return_value = "C:\\path\\to\\sccache.exe"
        mock_find.return_value = Path("C:\\path\\to\\clang++.exe")
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_cpp_main()

        self.assertEqual(cm.exception.code, 0)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "C:\\path\\to\\sccache.exe")
        self.assertIn("clang++.exe", str(call_args[1]))
        # On Windows, GNU ABI flags are added, so check for them
        args_list = list(call_args[2:])
        self.assertIn("--target=x86_64-w64-windows-gnu", args_list)
        self.assertIn("main.cpp", args_list)
        self.assertIn("-o", args_list)
        self.assertIn("main", args_list)
        self.assertIn("-std=c++17", args_list)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("os.execv")
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("clang_tool_chain.execution.core.get_platform_info")
    def test_sccache_cpp_main_success_unix(
        self, mock_platform: Mock, mock_sccache: Mock, mock_find: Mock, mock_execv: Mock
    ) -> None:
        """Test sccache_cpp_main on Unix with successful execution."""
        mock_platform.return_value = ("linux", "x86_64")
        mock_sccache.return_value = "/usr/bin/sccache"
        mock_find.return_value = Path("/home/.clang-tool-chain/clang/linux/x86_64/bin/clang++")

        cli.sccache_cpp_main()

        mock_execv.assert_called_once()
        call_args = mock_execv.call_args[0]
        # First arg is sccache path, second is full command list
        self.assertEqual(call_args[0], "/usr/bin/sccache")
        cmd_list = call_args[1]
        self.assertEqual(cmd_list[0], "/usr/bin/sccache")
        self.assertIn("clang++", str(cmd_list[1]))
        # On Linux, lld linker flags are added
        args_list = list(cmd_list[2:])
        self.assertIn("-fuse-ld=lld", args_list)
        self.assertIn("main.cpp", args_list)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_cpp_main_sccache_not_found(
        self, mock_stderr: StringIO, mock_sccache: Mock, mock_find: Mock
    ) -> None:
        """Test sccache_cpp_main when sccache is not found."""
        mock_sccache.side_effect = RuntimeError("sccache binary not found")
        mock_find.return_value = "/fake/path/to/clang++"

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_cpp_main()

        self.assertEqual(cm.exception.code, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("sccache binary not found", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_cpp_main_clang_cpp_not_found(
        self, mock_stderr: StringIO, mock_sccache: Mock, mock_find: Mock
    ) -> None:
        """Test sccache_cpp_main when clang++ binary is not found."""
        mock_sccache.return_value = "/usr/bin/sccache"
        mock_find.side_effect = RuntimeError("clang++ binary not found")

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_cpp_main()

        self.assertEqual(cm.exception.code, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("clang++ binary not found", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("subprocess.run")
    @patch("clang_tool_chain.execution.core.find_tool_binary")
    @patch("clang_tool_chain.execution.core.find_sccache_binary")
    @patch("clang_tool_chain.execution.core.get_platform_info")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_cpp_main_unexpected_error(
        self, mock_stderr: StringIO, mock_platform: Mock, mock_sccache: Mock, mock_find: Mock, mock_run: Mock
    ) -> None:
        """Test sccache_cpp_main with unexpected error."""
        mock_platform.return_value = ("win", "x86_64")
        mock_sccache.return_value = "C:\\path\\to\\sccache.exe"
        mock_find.return_value = Path("C:\\path\\to\\clang++.exe")
        mock_run.side_effect = Exception("Unexpected error occurred")

        with self.assertRaises(SystemExit) as cm:
            cli.sccache_cpp_main()

        self.assertEqual(cm.exception.code, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Error executing sccache", error_output)
        self.assertIn("Unexpected error occurred", error_output)


class MainTester(unittest.TestCase):
    """Test the main module can be imported."""

    def test_imports(self) -> None:
        """Test that the module can be imported successfully."""
        import clang_tool_chain.cli

        self.assertTrue(hasattr(clang_tool_chain.cli, "main"))
        self.assertTrue(callable(clang_tool_chain.cli.main))

    def test_sccache_functions_exist(self) -> None:
        """Test that sccache wrapper functions exist."""
        import clang_tool_chain.cli

        self.assertTrue(hasattr(clang_tool_chain.cli, "sccache_main"))
        self.assertTrue(callable(clang_tool_chain.cli.sccache_main))
        self.assertTrue(hasattr(clang_tool_chain.cli, "sccache_c_main"))
        self.assertTrue(callable(clang_tool_chain.cli.sccache_c_main))
        self.assertTrue(hasattr(clang_tool_chain.cli, "sccache_cpp_main"))
        self.assertTrue(callable(clang_tool_chain.cli.sccache_cpp_main))

    def test_msvc_functions_exist(self) -> None:
        """Test that MSVC variant wrapper functions exist."""
        from clang_tool_chain import wrapper

        self.assertTrue(hasattr(wrapper, "clang_msvc_main"))
        self.assertTrue(callable(wrapper.clang_msvc_main))
        self.assertTrue(hasattr(wrapper, "clang_cpp_msvc_main"))
        self.assertTrue(callable(wrapper.clang_cpp_msvc_main))


@unittest.skipUnless(sys.platform == "win32", "Windows-only tests")
class TestWindowsGNUDefault(unittest.TestCase):
    """Test Windows GNU ABI default behavior."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Clean up test files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_windows_gnu_default_detection(self) -> None:
        """Test that should_use_gnu_abi returns True on Windows by default."""
        from clang_tool_chain import wrapper

        # Test that Windows without --target should use GNU
        result = wrapper._should_use_gnu_abi("win", ["test.c", "-o", "test.exe"])
        self.assertTrue(result, "Windows should default to GNU ABI")

        # Test that explicit --target disables GNU injection
        result = wrapper._should_use_gnu_abi("win", ["--target=x86_64-pc-windows-msvc", "test.c"])
        self.assertFalse(result, "Explicit --target should prevent GNU injection")

        # Test that non-Windows doesn't trigger GNU
        result = wrapper._should_use_gnu_abi("linux", ["test.c", "-o", "test"])
        self.assertFalse(result, "Non-Windows platforms should not trigger GNU injection")

    def test_list_tools_includes_msvc_variants(self) -> None:
        """Test that list-tools includes MSVC variants."""
        from io import StringIO

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            args = MagicMock()
            cli.cmd_list_tools(args)
            output = mock_stdout.getvalue()

            self.assertIn("clang-tool-chain-c-msvc", output, "Should list MSVC C compiler variant")
            self.assertIn("clang-tool-chain-cpp-msvc", output, "Should list MSVC C++ compiler variant")


if __name__ == "__main__":
    unittest.main()
