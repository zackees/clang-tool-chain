"""
Unit tests for CLI functionality.

These tests verify the command-line interface works correctly.
"""

import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clang_tool_chain import cli


class TestCLICommands(unittest.TestCase):
    """Test CLI command functions."""

    @patch("clang_tool_chain.cli.wrapper.get_platform_binary_dir")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.wrapper.get_assets_dir")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_info_no_binaries(self, mock_stdout, mock_assets_dir, mock_platform, mock_bin_dir):
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
    def test_cmd_list_tools(self, mock_stdout):
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
    def test_cmd_version_success(self, mock_run_tool, mock_find):
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
    def test_cmd_version_tool_not_found(self, mock_stderr, mock_find):
        """Test version command when tool is not found."""
        mock_find.side_effect = RuntimeError("Tool not found")

        args = MagicMock()
        args.tool = "nonexistent"

        result = cli.cmd_version(args)

        self.assertEqual(result, 1)
        self.assertIn("Error", mock_stderr.getvalue())

    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("sys.stdout", new_callable=StringIO)
    def test_cmd_path_tool(self, mock_stdout, mock_find):
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
    def test_cmd_path_no_tool(self, mock_stdout, mock_bin_dir):
        """Test path command without a specific tool."""
        mock_bin_dir.return_value = Path("/fake/bin")

        args = MagicMock()
        args.tool = None

        result = cli.cmd_path(args)

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        # Path separator may be / or \ depending on platform
        self.assertTrue("fake" in output and "bin" in output)

    def test_tool_name_mapping(self):
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


class TestCLIMain(unittest.TestCase):
    """Test main CLI entry point."""

    @patch("sys.argv", ["clang-tool-chain", "--help"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_help(self, mock_stdout):
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
    def test_main_no_command(self, mock_stdout):
        """Test main with no command shows help."""
        result = cli.main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("usage", output.lower())

    @patch("sys.argv", ["clang-tool-chain", "list-tools"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_list_tools(self, mock_stdout):
        """Test main with list-tools command."""
        result = cli.main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("clang-tool-chain-c", output)

    @patch("sys.argv", ["clang-tool-chain", "package-version"])
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_package_version(self, mock_stdout):
        """Test main with package-version command."""
        result = cli.main()

        self.assertEqual(result, 0)
        output = mock_stdout.getvalue()
        self.assertIn("version", output.lower())


class TestSccacheWrappers(unittest.TestCase):
    """Test sccache wrapper commands."""

    @patch("sys.argv", ["clang-tool-chain-sccache", "--show-stats"])
    @patch("clang_tool_chain.cli.subprocess.run")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    def test_sccache_main_passthrough_windows(self, mock_which, mock_platform, mock_run):
        """Test sccache_main passthrough on Windows."""
        mock_which.return_value = "C:\\path\\to\\sccache.exe"
        mock_platform.return_value = ("win", "x86_64")
        mock_run.return_value = MagicMock(returncode=0)

        result = cli.sccache_main()

        self.assertEqual(result, 0)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, ["C:\\path\\to\\sccache.exe", "--show-stats"])

    @patch("sys.argv", ["clang-tool-chain-sccache", "--zero-stats"])
    @patch("clang_tool_chain.cli.os.execv")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    def test_sccache_main_passthrough_unix(self, mock_which, mock_platform, mock_execv):
        """Test sccache_main passthrough on Unix."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_platform.return_value = ("linux", "x86_64")
        mock_execv.return_value = None

        result = cli.sccache_main()

        self.assertEqual(result, 0)
        mock_execv.assert_called_once()
        call_args = mock_execv.call_args[0]
        self.assertEqual(call_args[0], "/usr/bin/sccache")
        self.assertEqual(call_args[1], ["/usr/bin/sccache", "--zero-stats"])

    @patch("sys.argv", ["clang-tool-chain-sccache", "--version"])
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_main_not_found(self, mock_stderr, mock_which):
        """Test sccache_main when sccache is not in PATH."""
        mock_which.return_value = None

        result = cli.sccache_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("sccache not found in PATH", error_output)
        self.assertIn("Installation options:", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache", "--show-stats"])
    @patch("clang_tool_chain.cli.subprocess.run")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_main_execution_error(self, mock_stderr, mock_which, mock_platform, mock_run):
        """Test sccache_main with execution error."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_platform.return_value = ("win", "x86_64")
        mock_run.side_effect = Exception("Unexpected error")

        result = cli.sccache_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Unexpected error during execution", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c", "-o", "main"])
    @patch("clang_tool_chain.cli.subprocess.run")
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    def test_sccache_c_main_success_windows(self, mock_which, mock_platform, mock_find, mock_run):
        """Test sccache_c_main on Windows with successful execution."""
        mock_which.return_value = "C:\\path\\to\\sccache.exe"
        mock_platform.return_value = ("win", "x86_64")
        mock_find.return_value = Path("C:\\path\\to\\clang.exe")
        mock_run.return_value = MagicMock(returncode=0)

        result = cli.sccache_c_main()

        self.assertEqual(result, 0)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "C:\\path\\to\\sccache.exe")
        self.assertIn("clang.exe", str(call_args[1]))
        self.assertEqual(call_args[2:], ["main.c", "-o", "main"])

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c", "-o", "main"])
    @patch("clang_tool_chain.cli.os.execv")
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    def test_sccache_c_main_success_unix(self, mock_which, mock_platform, mock_find, mock_execv):
        """Test sccache_c_main on Unix with successful execution."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_platform.return_value = ("linux", "x86_64")
        mock_find.return_value = Path("/home/.clang-tool-chain/linux/x86_64/bin/clang")
        mock_execv.return_value = None

        result = cli.sccache_c_main()

        self.assertEqual(result, 0)
        mock_execv.assert_called_once()
        call_args = mock_execv.call_args[0]
        self.assertEqual(call_args[0], "/usr/bin/sccache")
        self.assertEqual(call_args[1][0], "/usr/bin/sccache")
        self.assertIn("clang", str(call_args[1][1]))
        self.assertEqual(call_args[1][2:], ["main.c", "-o", "main"])

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c"])
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_c_main_sccache_not_found(self, mock_stderr, mock_which):
        """Test sccache_c_main when sccache is not in PATH."""
        mock_which.return_value = None

        result = cli.sccache_c_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("sccache not found in PATH", error_output)
        self.assertIn("pip install clang-tool-chain[sccache]", error_output)
        self.assertIn("cargo install sccache", error_output)
        self.assertIn("brew install sccache", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c"])
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_c_main_clang_not_found(self, mock_stderr, mock_which, mock_find):
        """Test sccache_c_main when clang binary is not found."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_find.side_effect = RuntimeError("clang binary not found in installation")

        result = cli.sccache_c_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Failed to locate clang binary", error_output)
        self.assertIn("clang binary not found in installation", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-c", "main.c"])
    @patch("clang_tool_chain.cli.subprocess.run")
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_c_main_execution_error(self, mock_stderr, mock_which, mock_platform, mock_find, mock_run):
        """Test sccache_c_main when execution fails."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_platform.return_value = ("win", "x86_64")
        mock_find.return_value = Path("C:\\path\\to\\clang.exe")
        mock_run.side_effect = FileNotFoundError("sccache.exe not found")

        result = cli.sccache_c_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Failed to execute sccache", error_output)
        self.assertIn("sccache was found at", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp", "-o", "main", "-std=c++17"])
    @patch("clang_tool_chain.cli.subprocess.run")
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    def test_sccache_cpp_main_success_windows(self, mock_which, mock_platform, mock_find, mock_run):
        """Test sccache_cpp_main on Windows with successful execution."""
        mock_which.return_value = "C:\\path\\to\\sccache.exe"
        mock_platform.return_value = ("win", "x86_64")
        mock_find.return_value = Path("C:\\path\\to\\clang++.exe")
        mock_run.return_value = MagicMock(returncode=0)

        result = cli.sccache_cpp_main()

        self.assertEqual(result, 0)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "C:\\path\\to\\sccache.exe")
        self.assertIn("clang++.exe", str(call_args[1]))
        self.assertEqual(call_args[2:], ["main.cpp", "-o", "main", "-std=c++17"])

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("clang_tool_chain.cli.os.execv")
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    def test_sccache_cpp_main_success_unix(self, mock_which, mock_platform, mock_find, mock_execv):
        """Test sccache_cpp_main on Unix with successful execution."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_platform.return_value = ("linux", "x86_64")
        mock_find.return_value = Path("/home/.clang-tool-chain/linux/x86_64/bin/clang++")
        mock_execv.return_value = None

        result = cli.sccache_cpp_main()

        self.assertEqual(result, 0)
        mock_execv.assert_called_once()
        call_args = mock_execv.call_args[0]
        self.assertEqual(call_args[0], "/usr/bin/sccache")
        self.assertEqual(call_args[1][0], "/usr/bin/sccache")
        self.assertIn("clang++", str(call_args[1][1]))

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_cpp_main_sccache_not_found(self, mock_stderr, mock_which):
        """Test sccache_cpp_main when sccache is not in PATH."""
        mock_which.return_value = None

        result = cli.sccache_cpp_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("sccache not found in PATH", error_output)
        self.assertIn("Installation options:", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_cpp_main_clang_cpp_not_found(self, mock_stderr, mock_which, mock_find):
        """Test sccache_cpp_main when clang++ binary is not found."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_find.side_effect = RuntimeError("clang++ binary not found")

        result = cli.sccache_cpp_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Failed to locate clang++ binary", error_output)
        self.assertIn("clang++ binary not found", error_output)

    @patch("sys.argv", ["clang-tool-chain-sccache-cpp", "main.cpp"])
    @patch("clang_tool_chain.cli.subprocess.run")
    @patch("clang_tool_chain.cli.wrapper.find_tool_binary")
    @patch("clang_tool_chain.cli.wrapper.get_platform_info")
    @patch("clang_tool_chain.cli.shutil.which")
    @patch("sys.stderr", new_callable=StringIO)
    def test_sccache_cpp_main_unexpected_error(self, mock_stderr, mock_which, mock_platform, mock_find, mock_run):
        """Test sccache_cpp_main with unexpected error."""
        mock_which.return_value = "/usr/bin/sccache"
        mock_platform.return_value = ("win", "x86_64")
        mock_find.return_value = Path("C:\\path\\to\\clang++.exe")
        mock_run.side_effect = Exception("Unexpected error occurred")

        result = cli.sccache_cpp_main()

        self.assertEqual(result, 1)
        error_output = mock_stderr.getvalue()
        self.assertIn("Unexpected error during execution", error_output)
        self.assertIn("Unexpected error occurred", error_output)
        self.assertIn("github.com/zackees/clang-tool-chain/issues", error_output)


class MainTester(unittest.TestCase):
    """Test the main module can be imported."""

    def test_imports(self):
        """Test that the module can be imported successfully."""
        import clang_tool_chain.cli

        self.assertTrue(hasattr(clang_tool_chain.cli, "main"))
        self.assertTrue(callable(clang_tool_chain.cli.main))

    def test_sccache_functions_exist(self):
        """Test that sccache wrapper functions exist."""
        import clang_tool_chain.cli

        self.assertTrue(hasattr(clang_tool_chain.cli, "sccache_main"))
        self.assertTrue(callable(clang_tool_chain.cli.sccache_main))
        self.assertTrue(hasattr(clang_tool_chain.cli, "sccache_c_main"))
        self.assertTrue(callable(clang_tool_chain.cli.sccache_c_main))
        self.assertTrue(hasattr(clang_tool_chain.cli, "sccache_cpp_main"))
        self.assertTrue(callable(clang_tool_chain.cli.sccache_cpp_main))


if __name__ == "__main__":
    unittest.main()
